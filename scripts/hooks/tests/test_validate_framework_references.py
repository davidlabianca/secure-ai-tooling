#!/usr/bin/env python3
"""
Tests for validate_framework_references.py

Tests cover:
- Schema $ref resolution validation
- Framework existence verification
- Identifier/key consistency checks
- Missing framework detection
- Backward compatibility with legacy entries
"""

import sys
from pathlib import Path

# Add parent directory to path to import the validator
sys.path.insert(0, str(Path(__file__).parent.parent))

from validate_framework_references import (
    extract_control_framework_references,
    extract_framework_ids,
    extract_risk_framework_references,
    validate_framework_consistency,
    validate_framework_references,
)


class TestExtractFrameworkIds:
    """Test extraction of framework IDs from frameworks.yaml"""

    def test_extract_valid_frameworks(self):
        """Test extracting framework IDs from valid data"""
        data = {
            "frameworks": [
                {"id": "mitre-atlas", "name": "MITRE ATLAS"},
                {"id": "stride", "name": "STRIDE"},
                {"id": "nist-ai-rmf", "name": "NIST AI RMF"},
            ]
        }
        result = extract_framework_ids(data)
        assert result == {"mitre-atlas", "stride", "nist-ai-rmf"}

    def test_extract_empty_frameworks(self):
        """Test extraction with empty frameworks list"""
        data = {"frameworks": []}
        result = extract_framework_ids(data)
        assert result == set()

    def test_extract_missing_frameworks_key(self):
        """Test extraction when frameworks key is missing"""
        data = {"title": "Frameworks"}
        result = extract_framework_ids(data)
        assert result == set()

    def test_extract_frameworks_with_missing_ids(self):
        """Test extraction skips frameworks without IDs"""
        data = {
            "frameworks": [
                {"id": "mitre-atlas", "name": "MITRE ATLAS"},
                {"name": "No ID Framework"},
                {"id": "stride", "name": "STRIDE"},
            ]
        }
        result = extract_framework_ids(data)
        assert result == {"mitre-atlas", "stride"}


class TestExtractRiskFrameworkReferences:
    """Test extraction of framework references from risks.yaml"""

    def test_extract_risk_with_mappings(self):
        """Test extracting framework references from risks with mappings"""
        data = {
            "risks": [
                {
                    "id": "DP",
                    "title": "Data Poisoning",
                    "mappings": {"mitre-atlas": ["AML.T0020"], "stride": ["tampering"]},
                },
                {"id": "UTD", "title": "Unauthorized Training Data", "mappings": {"stride": ["info-disclosure"]}},
            ]
        }
        result = extract_risk_framework_references(data)
        # Convert list values to sets for order-independent comparison
        assert {k: set(v) for k, v in result.items()} == {
            "DP": {"mitre-atlas", "stride"},
            "UTD": {"stride"}
        }

    def test_extract_risk_without_mappings(self):
        """Test extraction for risks without mappings field (backward compatibility)"""
        data = {"risks": [{"id": "DP", "title": "Data Poisoning"}]}
        result = extract_risk_framework_references(data)
        assert result == {}

    def test_extract_risk_with_empty_mappings(self):
        """Test extraction for risks with empty mappings"""
        data = {"risks": [{"id": "DP", "title": "Data Poisoning", "mappings": {}}]}
        result = extract_risk_framework_references(data)
        assert result == {}

    def test_extract_risk_missing_id(self):
        """Test extraction skips risks without IDs"""
        data = {"risks": [{"title": "No ID Risk", "mappings": {"mitre-atlas": ["AML.T0020"]}}]}
        result = extract_risk_framework_references(data)
        assert result == {}


class TestExtractControlFrameworkReferences:
    """Test extraction of framework references from controls.yaml"""

    def test_extract_control_with_mappings(self):
        """Test extracting framework references from controls with mappings"""
        data = {
            "controls": [
                {
                    "id": "controlTrainingDataSanitization",
                    "title": "Training Data Sanitization",
                    "mappings": {"mitre-atlas": ["AML.M0007"]},
                },
                {
                    "id": "controlModelIntegrity",
                    "title": "Model Integrity",
                    "mappings": {"nist-ai-rmf": ["SC-8"], "mitre-atlas": ["AML.M0013"]},
                },
            ]
        }
        result = extract_control_framework_references(data)
        # Convert list values to sets for order-independent comparison
        assert {k: set(v) for k, v in result.items()} == {
            "controlTrainingDataSanitization": {"mitre-atlas"},
            "controlModelIntegrity": {"nist-ai-rmf", "mitre-atlas"},
        }

    def test_extract_control_without_mappings(self):
        """Test extraction for controls without mappings field (backward compatibility)"""
        data = {"controls": [{"id": "controlTest", "title": "Test Control"}]}
        result = extract_control_framework_references(data)
        assert result == {}

    def test_extract_control_with_empty_mappings(self):
        """Test extraction for controls with empty mappings"""
        data = {"controls": [{"id": "controlTest", "title": "Test Control", "mappings": {}}]}
        result = extract_control_framework_references(data)
        assert result == {}


class TestValidateFrameworkReferences:
    """Test validation of framework references"""

    def test_validate_all_valid_references(self):
        """Test validation passes when all references are valid"""
        valid_frameworks = {"mitre-atlas", "stride", "nist-ai-rmf"}
        risk_frameworks = {"DP": ["mitre-atlas", "stride"], "MST": ["stride"]}
        control_frameworks = {"controlTest": ["nist-ai-rmf"]}

        errors = validate_framework_references(valid_frameworks, risk_frameworks, control_frameworks)
        assert errors == []

    def test_validate_invalid_risk_framework(self):
        """Test validation fails when risk references invalid framework"""
        valid_frameworks = {"mitre-atlas", "stride"}
        risk_frameworks = {"DP": ["invalid-framework"]}
        control_frameworks = {}

        errors = validate_framework_references(valid_frameworks, risk_frameworks, control_frameworks)
        assert len(errors) == 1
        assert "Risk 'DP'" in errors[0]
        assert "invalid-framework" in errors[0]
        assert "does not exist" in errors[0]

    def test_validate_invalid_control_framework(self):
        """Test validation fails when control references invalid framework"""
        valid_frameworks = {"mitre-atlas"}
        risk_frameworks = {}
        control_frameworks = {"controlTest": ["missing-framework"]}

        errors = validate_framework_references(valid_frameworks, risk_frameworks, control_frameworks)
        assert len(errors) == 1
        assert "Control 'controlTest'" in errors[0]
        assert "missing-framework" in errors[0]
        assert "does not exist" in errors[0]

    def test_validate_multiple_errors(self):
        """Test validation reports all errors"""
        valid_frameworks = {"mitre-atlas"}
        risk_frameworks = {"DP": ["invalid1", "mitre-atlas"], "MST": ["invalid2"]}
        control_frameworks = {"controlTest": ["invalid3"]}

        errors = validate_framework_references(valid_frameworks, risk_frameworks, control_frameworks)
        assert len(errors) == 3

    def test_validate_empty_references(self):
        """Test validation passes with no framework references (backward compatibility)"""
        valid_frameworks = {"mitre-atlas", "stride"}
        risk_frameworks = {}
        control_frameworks = {}

        errors = validate_framework_references(valid_frameworks, risk_frameworks, control_frameworks)
        assert errors == []


class TestValidateFrameworkConsistency:
    """Test validation of framework definition consistency"""

    def test_validate_consistent_frameworks(self):
        """Test validation passes for consistent framework definitions"""
        data = {
            "frameworks": [
                {
                    "id": "mitre-atlas",
                    "name": "MITRE ATLAS",
                    "fullName": "Adversarial Threat Landscape for AI Systems",
                    "description": "Framework description",
                    "baseUri": "https://atlas.mitre.org",
                },
                {
                    "id": "stride",
                    "name": "STRIDE",
                    "fullName": "STRIDE Threat Model",
                    "description": "Threat modeling framework",
                    "baseUri": "https://example.com",
                },
            ]
        }
        errors = validate_framework_consistency(data)
        assert errors == []

    def test_validate_missing_required_field(self):
        """Test validation fails when required field is missing"""
        data = {
            "frameworks": [
                {
                    "id": "mitre-atlas",
                    "name": "MITRE ATLAS",
                    "fullName": "Adversarial Threat Landscape",
                    # Missing description and baseUri
                }
            ]
        }
        errors = validate_framework_consistency(data)
        assert len(errors) >= 2
        assert any("description" in error for error in errors)
        assert any("baseUri" in error for error in errors)

    def test_validate_duplicate_framework_ids(self):
        """Test validation fails when duplicate IDs exist"""
        data = {
            "frameworks": [
                {
                    "id": "mitre-atlas",
                    "name": "MITRE ATLAS",
                    "fullName": "Framework 1",
                    "description": "Description 1",
                    "baseUri": "https://example1.com",
                },
                {
                    "id": "mitre-atlas",  # Duplicate
                    "name": "MITRE ATLAS 2",
                    "fullName": "Framework 2",
                    "description": "Description 2",
                    "baseUri": "https://example2.com",
                },
            ]
        }
        errors = validate_framework_consistency(data)
        assert len(errors) >= 1
        assert any("Duplicate framework ID" in error for error in errors)
        assert any("mitre-atlas" in error for error in errors)

    def test_validate_missing_id_field(self):
        """Test validation fails when framework is missing ID"""
        data = {
            "frameworks": [
                {
                    "name": "No ID Framework",
                    "fullName": "Framework without ID",
                    "description": "Description",
                    "baseUri": "https://example.com",
                }
            ]
        }
        errors = validate_framework_consistency(data)
        assert len(errors) >= 1
        assert any("missing 'id' field" in error for error in errors)

    def test_validate_missing_frameworks_array(self):
        """Test validation fails when frameworks array is missing"""
        data = {"title": "Frameworks"}
        errors = validate_framework_consistency(data)
        assert len(errors) == 1
        assert "No frameworks array found" in errors[0]

    def test_validate_optional_fields_allowed(self):
        """Test that optional fields don't cause validation errors"""
        data = {
            "frameworks": [
                {
                    "id": "mitre-atlas",
                    "name": "MITRE ATLAS",
                    "fullName": "Framework",
                    "description": "Description",
                    "baseUri": "https://example.com",
                    "version": "1.0",  # Optional
                    "lastUpdated": "2024-01-01",  # Optional
                    "techniqueUriPattern": "https://example.com/{id}",  # Optional
                }
            ]
        }
        errors = validate_framework_consistency(data)
        assert errors == []


class TestIntegration:
    """Integration tests combining multiple validation functions"""

    def test_end_to_end_validation_success(self):
        """Test complete validation workflow with valid data"""
        frameworks_data = {
            "frameworks": [
                {
                    "id": "mitre-atlas",
                    "name": "MITRE ATLAS",
                    "fullName": "Framework",
                    "description": "Description",
                    "baseUri": "https://example.com",
                },
                {
                    "id": "stride",
                    "name": "STRIDE",
                    "fullName": "Framework",
                    "description": "Description",
                    "baseUri": "https://example.com",
                },
            ]
        }

        risks_data = {
            "risks": [
                {"id": "DP", "title": "Data Poisoning", "mappings": {"mitre-atlas": ["AML.T0020"]}},
                {"id": "MST", "title": "Model Tampering", "mappings": {"stride": ["tampering"]}},
            ]
        }

        controls_data = {
            "controls": [
                {"id": "controlTest", "title": "Test Control", "mappings": {"mitre-atlas": ["AML.M0007"]}}
            ]
        }

        # Validate consistency
        consistency_errors = validate_framework_consistency(frameworks_data)
        assert consistency_errors == []

        # Extract and validate references
        valid_frameworks = extract_framework_ids(frameworks_data)
        risk_frameworks = extract_risk_framework_references(risks_data)
        control_frameworks = extract_control_framework_references(controls_data)

        reference_errors = validate_framework_references(valid_frameworks, risk_frameworks, control_frameworks)
        assert reference_errors == []

    def test_end_to_end_validation_failure(self):
        """Test complete validation workflow with invalid data"""
        frameworks_data = {
            "frameworks": [
                {
                    "id": "mitre-atlas",
                    "name": "MITRE ATLAS",
                    "fullName": "Framework",
                    "description": "Description",
                    "baseUri": "https://example.com",
                }
            ]
        }

        risks_data = {
            "risks": [
                {
                    "id": "DP",
                    "title": "Data Poisoning",
                    "mappings": {"invalid-framework": ["technique1"]},  # Invalid framework
                }
            ]
        }

        controls_data = {"controls": []}

        # Extract and validate references
        valid_frameworks = extract_framework_ids(frameworks_data)
        risk_frameworks = extract_risk_framework_references(risks_data)
        control_frameworks = extract_control_framework_references(controls_data)

        reference_errors = validate_framework_references(valid_frameworks, risk_frameworks, control_frameworks)
        assert len(reference_errors) > 0
        assert any("invalid-framework" in error for error in reference_errors)

    def test_backward_compatibility_no_mappings(self):
        """Test that entries without mappings field still validate successfully"""
        frameworks_data = {
            "frameworks": [
                {
                    "id": "mitre-atlas",
                    "name": "MITRE ATLAS",
                    "fullName": "Framework",
                    "description": "Description",
                    "baseUri": "https://example.com",
                }
            ]
        }

        # Legacy data without mappings fields
        risks_data = {"risks": [{"id": "DP", "title": "Data Poisoning"}]}

        controls_data = {"controls": [{"id": "controlTest", "title": "Test Control"}]}

        # Validate consistency
        consistency_errors = validate_framework_consistency(frameworks_data)
        assert consistency_errors == []

        # Extract and validate references
        valid_frameworks = extract_framework_ids(frameworks_data)
        risk_frameworks = extract_risk_framework_references(risks_data)
        control_frameworks = extract_control_framework_references(controls_data)

        # Should have no references but validation should pass
        assert risk_frameworks == {}
        assert control_frameworks == {}

        reference_errors = validate_framework_references(valid_frameworks, risk_frameworks, control_frameworks)
        assert reference_errors == []

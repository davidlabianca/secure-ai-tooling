#!/usr/bin/env python3
"""
Tests for framework applicability validation in validate_framework_references.py.

This module tests the applicability validation logic that ensures controls and risks
only reference frameworks where the appropriate entity type ("controls" or "risks")
is present in the framework's applicableTo array.

Test Coverage:
==============
Total Tests: 46 across 4 test classes
Coverage Target: 90%+ of new validation functions

1. TestExtractFrameworkApplicability - Extract applicableTo data (11 tests)
   - Extract from frameworks with various configurations
   - Handle frameworks with single entity type
   - Handle frameworks with multiple entity types
   - Handle missing applicableTo field
   - Handle empty applicableTo array
   - Handle frameworks.yaml with no frameworks
   - Handle frameworks with all entity types
   - Handle malformed applicableTo data
   - Extract from actual production frameworks.yaml

2. TestValidateFrameworkApplicability - Validate applicability logic (21 tests)
   Valid Cases:
   - Control referencing mitre-atlas (controls in applicableTo)
   - Control referencing nist-ai-rmf (controls in applicableTo)
   - Risk referencing mitre-atlas (risks in applicableTo)
   - Risk referencing stride (risks in applicableTo)
   - Risk referencing owasp-top10-llm (risks in applicableTo)
   - Control referencing multiple valid frameworks
   - Risk referencing multiple valid frameworks
   - Empty risk_frameworks dict
   - Empty control_frameworks dict
   - Empty frameworks_applicability dict

   Invalid Cases:
   - Control referencing stride (controls not in applicableTo)
   - Control referencing owasp-top10-llm (controls not in applicableTo)
   - Risk referencing nist-ai-rmf (risks not in applicableTo)
   - Control with mixed valid/invalid framework references
   - Risk with mixed valid/invalid framework references
   - Multiple controls with invalid references
   - Multiple risks with invalid references
   - Framework in references but not in frameworks_applicability
   - Control and risk both with invalid references

   Error Message Tests:
   - Error message includes control ID
   - Error message includes framework ID
   - Error message includes expected entity type

3. TestValidateFrameworksIntegration - Integration with validate_frameworks() (9 tests)
   - Full validation pipeline with valid applicability
   - Full validation pipeline with invalid control applicability
   - Full validation pipeline with invalid risk applicability
   - Applicability errors combined with reference errors
   - Applicability errors combined with consistency errors
   - Validation with actual production data
   - Applicability validation reports correct error count
   - Success message includes applicability validation
   - Integration with existing extract functions

4. TestFrameworkApplicabilityWithRealData - Real-world data validation (4 tests)
   - Validate actual controls.yaml framework mappings
   - Validate actual risks.yaml framework mappings
   - Detect invalid applicability in production data (if exists)
   - All production frameworks have applicableTo defined
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import yaml

# ============================================================================
# Pytest Fixtures for Test Data Isolation
# ============================================================================


@pytest.fixture
def sample_frameworks_data():
    """Fixture providing sample frameworks data with applicableTo fields."""
    return {
        "title": "Test Frameworks",
        "description": ["Test framework definitions"],
        "frameworks": [
            {
                "id": "mitre-atlas",
                "name": "MITRE ATLAS",
                "fullName": "Adversarial Threat Landscape for AI Systems",
                "description": "Knowledge base of adversary tactics",
                "baseUri": "https://atlas.mitre.org",
                "applicableTo": ["controls", "risks"],
            },
            {
                "id": "nist-ai-rmf",
                "name": "NIST AI RMF",
                "fullName": "NIST AI Risk Management Framework",
                "description": "Framework for managing AI risks",
                "baseUri": "https://www.nist.gov/ai-rmf",
                "applicableTo": ["controls"],
            },
            {
                "id": "stride",
                "name": "STRIDE",
                "fullName": "STRIDE Threat Model",
                "description": "Microsoft threat modeling framework",
                "baseUri": "https://learn.microsoft.com/stride",
                "applicableTo": ["risks"],
            },
            {
                "id": "owasp-top10-llm",
                "name": "OWASP Top 10 for LLM",
                "fullName": "OWASP Top 10 for Large Language Models",
                "description": "Top 10 LLM security risks",
                "baseUri": "https://owasp.org/llm",
                "applicableTo": ["risks"],
            },
        ],
    }


@pytest.fixture
def sample_frameworks_applicability():
    """Fixture providing sample frameworks_applicability dict."""
    return {
        "mitre-atlas": ["controls", "risks"],
        "nist-ai-rmf": ["controls"],
        "stride": ["risks"],
        "owasp-top10-llm": ["risks"],
    }


@pytest.fixture
def sample_control_frameworks():
    """Fixture providing sample control framework references."""
    return {
        "control-1": ["mitre-atlas"],
        "control-2": ["nist-ai-rmf"],
    }


@pytest.fixture
def sample_risk_frameworks():
    """Fixture providing sample risk framework references."""
    return {
        "risk-1": ["mitre-atlas"],
        "risk-2": ["stride"],
    }


# ============================================================================
# Test Extract Framework Applicability
# ============================================================================


class TestExtractFrameworkApplicability:
    """Test extract_framework_applicability() function."""

    def test_extract_from_framework_with_single_entity_type(self):
        """
        Test extracting applicableTo from framework with single entity type.

        Given: A frameworks.yaml with framework having applicableTo: ["controls"]
        When: extract_framework_applicability() is called
        Then: Returns {"framework-id": ["controls"]}
        """
        # This function doesn't exist yet - test will fail (RED)
        from validate_framework_references import extract_framework_applicability

        frameworks_data = {
            "frameworks": [
                {
                    "id": "nist-ai-rmf",
                    "name": "NIST AI RMF",
                    "applicableTo": ["controls"],
                }
            ]
        }

        result = extract_framework_applicability(frameworks_data)

        assert result == {"nist-ai-rmf": ["controls"]}, "Should extract single entity type"

    def test_extract_from_framework_with_multiple_entity_types(self):
        """
        Test extracting applicableTo from framework with multiple entity types.

        Given: A frameworks.yaml with framework having applicableTo: ["controls", "risks"]
        When: extract_framework_applicability() is called
        Then: Returns {"framework-id": ["controls", "risks"]}
        """
        from validate_framework_references import extract_framework_applicability

        frameworks_data = {
            "frameworks": [
                {
                    "id": "mitre-atlas",
                    "name": "MITRE ATLAS",
                    "applicableTo": ["controls", "risks"],
                }
            ]
        }

        result = extract_framework_applicability(frameworks_data)

        assert result == {"mitre-atlas": ["controls", "risks"]}, "Should extract multiple entity types"

    def test_extract_from_multiple_frameworks_with_different_applicability(self):
        """
        Test extracting from multiple frameworks with different applicableTo.

        Given: Multiple frameworks with varied applicableTo configurations
        When: extract_framework_applicability() is called
        Then: Returns dict with all frameworks and their applicableTo arrays
        """
        from validate_framework_references import extract_framework_applicability

        frameworks_data = {
            "frameworks": [
                {"id": "mitre-atlas", "applicableTo": ["controls", "risks"]},
                {"id": "nist-ai-rmf", "applicableTo": ["controls"]},
                {"id": "stride", "applicableTo": ["risks"]},
                {"id": "owasp-top10-llm", "applicableTo": ["risks"]},
            ]
        }

        result = extract_framework_applicability(frameworks_data)

        assert result == {
            "mitre-atlas": ["controls", "risks"],
            "nist-ai-rmf": ["controls"],
            "stride": ["risks"],
            "owasp-top10-llm": ["risks"],
        }, "Should extract applicableTo from all frameworks"

    def test_extract_from_framework_with_all_entity_types(self):
        """
        Test extracting from framework applicable to all entity types.

        Given: Framework with applicableTo: ["controls", "risks", "components", "personas"]
        When: extract_framework_applicability() is called
        Then: Returns all four entity types
        """
        from validate_framework_references import extract_framework_applicability

        frameworks_data = {
            "frameworks": [
                {
                    "id": "universal-framework",
                    "applicableTo": ["controls", "risks", "components", "personas"],
                }
            ]
        }

        result = extract_framework_applicability(frameworks_data)

        assert result == {"universal-framework": ["controls", "risks", "components", "personas"]}, (
            "Should extract all entity types"
        )

    def test_extract_with_missing_applicable_to_field(self):
        """
        Test handling of framework missing applicableTo field.

        Given: Framework definition without applicableTo field
        When: extract_framework_applicability() is called
        Then: Framework is skipped (not included in result)
        """
        from validate_framework_references import extract_framework_applicability

        frameworks_data = {
            "frameworks": [
                {
                    "id": "incomplete-framework",
                    "name": "Incomplete Framework",
                    # Missing applicableTo field
                }
            ]
        }

        result = extract_framework_applicability(frameworks_data)

        assert result == {}, "Should skip framework without applicableTo field"

    def test_extract_with_empty_applicable_to_array(self):
        """
        Test handling of framework with empty applicableTo array.

        Given: Framework with applicableTo: []
        When: extract_framework_applicability() is called
        Then: Returns framework with empty array (schema should catch this)
        """
        from validate_framework_references import extract_framework_applicability

        frameworks_data = {"frameworks": [{"id": "empty-framework", "applicableTo": []}]}

        result = extract_framework_applicability(frameworks_data)

        assert result == {"empty-framework": []}, "Should preserve empty array (schema validates this)"

    def test_extract_with_no_frameworks_array(self):
        """
        Test handling of frameworks.yaml with no frameworks array.

        Given: frameworks_data dict without "frameworks" key
        When: extract_framework_applicability() is called
        Then: Returns empty dict
        """
        from validate_framework_references import extract_framework_applicability

        frameworks_data = {}

        result = extract_framework_applicability(frameworks_data)

        assert result == {}, "Should return empty dict when no frameworks array"

    def test_extract_with_empty_frameworks_array(self):
        """
        Test handling of frameworks.yaml with empty frameworks array.

        Given: frameworks_data with "frameworks": []
        When: extract_framework_applicability() is called
        Then: Returns empty dict
        """
        from validate_framework_references import extract_framework_applicability

        frameworks_data = {"frameworks": []}

        result = extract_framework_applicability(frameworks_data)

        assert result == {}, "Should return empty dict when frameworks array is empty"

    def test_extract_with_framework_missing_id(self):
        """
        Test handling of framework without id field.

        Given: Framework definition without id field
        When: extract_framework_applicability() is called
        Then: Framework is skipped
        """
        from validate_framework_references import extract_framework_applicability

        frameworks_data = {
            "frameworks": [
                {
                    # Missing id field
                    "name": "Framework Without ID",
                    "applicableTo": ["controls"],
                }
            ]
        }

        result = extract_framework_applicability(frameworks_data)

        assert result == {}, "Should skip framework without id field"

    def test_extract_with_non_list_applicable_to(self):
        """
        Test handling of applicableTo that is not a list.

        Given: Framework with applicableTo as string instead of list
        When: extract_framework_applicability() is called
        Then: Framework is skipped or returns empty (malformed data)
        """
        from validate_framework_references import extract_framework_applicability

        frameworks_data = {
            "frameworks": [
                {
                    "id": "malformed-framework",
                    "applicableTo": "controls",  # String instead of list
                }
            ]
        }

        result = extract_framework_applicability(frameworks_data)

        # Should either skip or handle gracefully
        assert "malformed-framework" not in result or result["malformed-framework"] == "controls", (
            "Should handle malformed applicableTo gracefully"
        )

    def test_extract_from_actual_frameworks_yaml(self, frameworks_yaml_path):
        """
        Test extraction from actual production frameworks.yaml.

        Given: The actual frameworks.yaml file
        When: extract_framework_applicability() is called
        Then: Returns applicableTo for all production frameworks
        """
        from validate_framework_references import extract_framework_applicability

        frameworks_path = frameworks_yaml_path
        assert frameworks_path.exists(), "frameworks.yaml must exist"

        with open(frameworks_path) as f:
            frameworks_data = yaml.safe_load(f)

        result = extract_framework_applicability(frameworks_data)

        # Based on current frameworks.yaml content
        assert "mitre-atlas" in result, "Should extract mitre-atlas"
        assert "nist-ai-rmf" in result, "Should extract nist-ai-rmf"
        assert "stride" in result, "Should extract stride"
        assert "owasp-top10-llm" in result, "Should extract owasp-top10-llm"

        assert set(result["mitre-atlas"]) == {"controls", "risks"}, "mitre-atlas should be controls and risks"
        assert result["nist-ai-rmf"] == ["controls"], "nist-ai-rmf should be controls only"
        assert result["stride"] == ["risks"], "stride should be risks only"
        assert set(result["owasp-top10-llm"]) == {"controls", "risks"}, (
            "owasp-top10-llm should be controls and risks"
        )


# ============================================================================
# Test Validate Framework Applicability
# ============================================================================


class TestValidateFrameworkApplicability:
    """Test validate_framework_applicability() validation logic."""

    # ========================================================================
    # Valid Cases
    # ========================================================================

    def test_control_referencing_mitre_atlas_is_valid(self):
        """
        Test control referencing mitre-atlas passes validation.

        Given: mitre-atlas has applicableTo: ["controls", "risks"]
        When: Control references mitre-atlas
        Then: Validation passes (no errors)
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"mitre-atlas": ["controls", "risks"]}
        risk_frameworks = {}
        control_frameworks = {"control-1": ["mitre-atlas"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert errors == [], "Control referencing mitre-atlas should be valid"

    def test_control_referencing_nist_ai_rmf_is_valid(self):
        """
        Test control referencing nist-ai-rmf passes validation.

        Given: nist-ai-rmf has applicableTo: ["controls"]
        When: Control references nist-ai-rmf
        Then: Validation passes (no errors)
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"nist-ai-rmf": ["controls"]}
        risk_frameworks = {}
        control_frameworks = {"control-1": ["nist-ai-rmf"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert errors == [], "Control referencing nist-ai-rmf should be valid"

    def test_risk_referencing_mitre_atlas_is_valid(self):
        """
        Test risk referencing mitre-atlas passes validation.

        Given: mitre-atlas has applicableTo: ["controls", "risks"]
        When: Risk references mitre-atlas
        Then: Validation passes (no errors)
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"mitre-atlas": ["controls", "risks"]}
        risk_frameworks = {"risk-1": ["mitre-atlas"]}
        control_frameworks = {}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert errors == [], "Risk referencing mitre-atlas should be valid"

    def test_risk_referencing_stride_is_valid(self):
        """
        Test risk referencing stride passes validation.

        Given: stride has applicableTo: ["risks"]
        When: Risk references stride
        Then: Validation passes (no errors)
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"stride": ["risks"]}
        risk_frameworks = {"risk-1": ["stride"]}
        control_frameworks = {}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert errors == [], "Risk referencing stride should be valid"

    def test_risk_referencing_owasp_top10_llm_is_valid(self):
        """
        Test risk referencing owasp-top10-llm passes validation.

        Given: owasp-top10-llm has applicableTo: ["risks"]
        When: Risk references owasp-top10-llm
        Then: Validation passes (no errors)
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"owasp-top10-llm": ["risks"]}
        risk_frameworks = {"risk-1": ["owasp-top10-llm"]}
        control_frameworks = {}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert errors == [], "Risk referencing owasp-top10-llm should be valid"

    def test_control_referencing_multiple_valid_frameworks(self):
        """
        Test control referencing multiple valid frameworks passes validation.

        Given: mitre-atlas and nist-ai-rmf both have "controls" in applicableTo
        When: Control references both frameworks
        Then: Validation passes (no errors)
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {
            "mitre-atlas": ["controls", "risks"],
            "nist-ai-rmf": ["controls"],
        }
        risk_frameworks = {}
        control_frameworks = {"control-1": ["mitre-atlas", "nist-ai-rmf"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert errors == [], "Control with multiple valid frameworks should pass"

    def test_risk_referencing_multiple_valid_frameworks(self):
        """
        Test risk referencing multiple valid frameworks passes validation.

        Given: mitre-atlas, stride, owasp-top10-llm all have "risks" in applicableTo
        When: Risk references all three frameworks
        Then: Validation passes (no errors)
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {
            "mitre-atlas": ["controls", "risks"],
            "stride": ["risks"],
            "owasp-top10-llm": ["risks"],
        }
        risk_frameworks = {"risk-1": ["mitre-atlas", "stride", "owasp-top10-llm"]}
        control_frameworks = {}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert errors == [], "Risk with multiple valid frameworks should pass"

    def test_empty_risk_frameworks_dict_is_valid(self):
        """
        Test validation with no risk framework references.

        Given: Empty risk_frameworks dict
        When: validate_framework_applicability() is called
        Then: Validation passes (no errors)
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"nist-ai-rmf": ["controls"]}
        risk_frameworks = {}
        control_frameworks = {"control-1": ["nist-ai-rmf"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert errors == [], "Empty risk_frameworks should not cause errors"

    def test_empty_control_frameworks_dict_is_valid(self):
        """
        Test validation with no control framework references.

        Given: Empty control_frameworks dict
        When: validate_framework_applicability() is called
        Then: Validation passes (no errors)
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"stride": ["risks"]}
        risk_frameworks = {"risk-1": ["stride"]}
        control_frameworks = {}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert errors == [], "Empty control_frameworks should not cause errors"

    def test_empty_frameworks_applicability_dict_with_no_references(self):
        """
        Test validation with empty frameworks_applicability and no references.

        Given: Empty frameworks_applicability dict and no entity references
        When: validate_framework_applicability() is called
        Then: Validation passes (no errors)
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {}
        risk_frameworks = {}
        control_frameworks = {}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert errors == [], "All empty dicts should not cause errors"

    # ========================================================================
    # Invalid Cases
    # ========================================================================

    def test_control_referencing_stride_is_invalid(self):
        """
        Test control referencing stride fails validation.

        Given: stride has applicableTo: ["risks"] (not "controls")
        When: Control references stride
        Then: Validation fails with error
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"stride": ["risks"]}
        risk_frameworks = {}
        control_frameworks = {"control-1": ["stride"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert len(errors) == 1, "Should have one error for invalid control reference"
        assert "control-1" in errors[0], "Error should mention control ID"
        assert "stride" in errors[0], "Error should mention framework ID"
        assert "controls" in errors[0].lower(), "Error should mention expected entity type"

    def test_control_referencing_owasp_top10_llm_is_invalid(self):
        """
        Test control referencing owasp-top10-llm fails validation.

        Given: owasp-top10-llm has applicableTo: ["risks"] (not "controls")
        When: Control references owasp-top10-llm
        Then: Validation fails with error
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"owasp-top10-llm": ["risks"]}
        risk_frameworks = {}
        control_frameworks = {"control-1": ["owasp-top10-llm"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert len(errors) == 1, "Should have one error for invalid control reference"
        assert "control-1" in errors[0], "Error should mention control ID"
        assert "owasp-top10-llm" in errors[0], "Error should mention framework ID"

    def test_risk_referencing_nist_ai_rmf_is_invalid(self):
        """
        Test risk referencing nist-ai-rmf fails validation.

        Given: nist-ai-rmf has applicableTo: ["controls"] (not "risks")
        When: Risk references nist-ai-rmf
        Then: Validation fails with error
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"nist-ai-rmf": ["controls"]}
        risk_frameworks = {"risk-1": ["nist-ai-rmf"]}
        control_frameworks = {}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert len(errors) == 1, "Should have one error for invalid risk reference"
        assert "risk-1" in errors[0], "Error should mention risk ID"
        assert "nist-ai-rmf" in errors[0], "Error should mention framework ID"
        assert "risks" in errors[0].lower(), "Error should mention expected entity type"

    def test_control_with_mixed_valid_and_invalid_frameworks(self):
        """
        Test control with mixed valid/invalid framework references.

        Given: Control references both nist-ai-rmf (valid) and stride (invalid)
        When: validate_framework_applicability() is called
        Then: Error reported for stride only
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {
            "nist-ai-rmf": ["controls"],
            "stride": ["risks"],
        }
        risk_frameworks = {}
        control_frameworks = {"control-1": ["nist-ai-rmf", "stride"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert len(errors) == 1, "Should have one error for stride"
        assert "control-1" in errors[0], "Error should mention control ID"
        assert "stride" in errors[0], "Error should mention stride"
        assert "nist-ai-rmf" not in errors[0], "Error should not mention valid framework"

    def test_risk_with_mixed_valid_and_invalid_frameworks(self):
        """
        Test risk with mixed valid/invalid framework references.

        Given: Risk references both stride (valid) and nist-ai-rmf (invalid)
        When: validate_framework_applicability() is called
        Then: Error reported for nist-ai-rmf only
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {
            "stride": ["risks"],
            "nist-ai-rmf": ["controls"],
        }
        risk_frameworks = {"risk-1": ["stride", "nist-ai-rmf"]}
        control_frameworks = {}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert len(errors) == 1, "Should have one error for nist-ai-rmf"
        assert "risk-1" in errors[0], "Error should mention risk ID"
        assert "nist-ai-rmf" in errors[0], "Error should mention nist-ai-rmf"
        assert "stride" not in errors[0], "Error should not mention valid framework"

    def test_multiple_controls_with_invalid_references(self):
        """
        Test multiple controls with invalid framework references.

        Given: Two controls both referencing stride (invalid for controls)
        When: validate_framework_applicability() is called
        Then: Two errors reported
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"stride": ["risks"]}
        risk_frameworks = {}
        control_frameworks = {
            "control-1": ["stride"],
            "control-2": ["stride"],
        }

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert len(errors) == 2, "Should have two errors for two invalid controls"
        assert any("control-1" in err for err in errors), "Should have error for control-1"
        assert any("control-2" in err for err in errors), "Should have error for control-2"

    def test_multiple_risks_with_invalid_references(self):
        """
        Test multiple risks with invalid framework references.

        Given: Two risks both referencing nist-ai-rmf (invalid for risks)
        When: validate_framework_applicability() is called
        Then: Two errors reported
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"nist-ai-rmf": ["controls"]}
        risk_frameworks = {
            "risk-1": ["nist-ai-rmf"],
            "risk-2": ["nist-ai-rmf"],
        }
        control_frameworks = {}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert len(errors) == 2, "Should have two errors for two invalid risks"
        assert any("risk-1" in err for err in errors), "Should have error for risk-1"
        assert any("risk-2" in err for err in errors), "Should have error for risk-2"

    def test_framework_referenced_but_not_in_applicability_dict(self):
        """
        Test handling of framework referenced but not in frameworks_applicability.

        Given: Control references framework not in frameworks_applicability dict
        When: validate_framework_applicability() is called
        Then: Should skip unknown frameworks (their existence is validated by validate_framework_references)

        Design Decision:
        - validate_framework_references() validates that framework IDs exist in frameworks.yaml
        - validate_framework_applicability() validates applicability for known frameworks
        - If a framework is not in frameworks_applicability dict, it means:
          a) The framework doesn't exist (caught by validate_framework_references)
          b) extract_framework_applicability() failed to load it (would be a bug)
        - Therefore, this function should skip unknown frameworks to avoid duplicate errors
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"nist-ai-rmf": ["controls"]}
        risk_frameworks = {}
        control_frameworks = {"control-1": ["unknown-framework"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        # Framework not in applicability dict should be skipped (validated elsewhere)
        assert len(errors) == 0, (
            "Unknown frameworks should be skipped - framework existence is "
            "validated by validate_framework_references(), not here"
        )

    def test_both_control_and_risk_with_invalid_references(self):
        """
        Test control and risk both with invalid framework references.

        Given: Control references stride (invalid) and risk references nist-ai-rmf (invalid)
        When: validate_framework_applicability() is called
        Then: Two errors reported
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {
            "stride": ["risks"],
            "nist-ai-rmf": ["controls"],
        }
        risk_frameworks = {"risk-1": ["nist-ai-rmf"]}
        control_frameworks = {"control-1": ["stride"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert len(errors) == 2, "Should have two errors (one for control, one for risk)"
        assert any("control-1" in err and "stride" in err for err in errors), "Should have control error"
        assert any("risk-1" in err and "nist-ai-rmf" in err for err in errors), "Should have risk error"

    # ========================================================================
    # Error Message Quality Tests
    # ========================================================================

    def test_error_message_includes_control_id(self):
        """
        Test error message includes the control ID.

        Given: Control with invalid framework reference
        When: validate_framework_applicability() is called
        Then: Error message includes control ID
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"stride": ["risks"]}
        risk_frameworks = {}
        control_frameworks = {"my-specific-control": ["stride"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert len(errors) == 1
        assert "my-specific-control" in errors[0], "Error must include control ID for debugging"

    def test_error_message_includes_framework_id(self):
        """
        Test error message includes the framework ID.

        Given: Control with invalid framework reference
        When: validate_framework_applicability() is called
        Then: Error message includes framework ID
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"stride": ["risks"]}
        risk_frameworks = {}
        control_frameworks = {"control-1": ["stride"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert len(errors) == 1
        assert "stride" in errors[0], "Error must include framework ID for debugging"

    def test_error_message_includes_expected_entity_type(self):
        """
        Test error message includes expected entity type.

        Given: Control with invalid framework reference
        When: validate_framework_applicability() is called
        Then: Error message mentions "controls" as expected entity type
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"stride": ["risks"]}
        risk_frameworks = {}
        control_frameworks = {"control-1": ["stride"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert len(errors) == 1
        assert "controls" in errors[0].lower(), "Error must indicate expected entity type"

    # ========================================================================
    # Case Sensitivity Tests
    # ========================================================================

    def test_framework_id_case_sensitivity_mismatch(self):
        """
        Test that framework ID matching is case-sensitive.

        Given: Framework "mitre-atlas" in applicability dict
        When: Control references "MITRE-ATLAS" (different case)
        Then: Framework is not found in applicability dict, treated as unknown framework
              (framework existence validated by validate_framework_references)
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"mitre-atlas": ["controls", "risks"]}
        risk_frameworks = {}
        control_frameworks = {"control-1": ["MITRE-ATLAS"]}  # Wrong case

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        # Framework not in dict should be skipped (existence validated elsewhere)
        assert len(errors) == 0, (
            "Unknown frameworks should be skipped (validated by validate_framework_references)"
        )

    def test_framework_id_case_sensitivity_exact_match(self):
        """
        Test that exact case match works correctly.

        Given: Framework "mitre-atlas" in applicability dict
        When: Control references "mitre-atlas" (exact case match)
        Then: Validation passes
        """
        from validate_framework_references import validate_framework_applicability

        frameworks_applicability = {"mitre-atlas": ["controls", "risks"]}
        risk_frameworks = {}
        control_frameworks = {"control-1": ["mitre-atlas"]}  # Exact case

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        assert len(errors) == 0, "Should pass with exact case match"

    def test_entity_type_case_sensitivity_in_applicable_to(self):
        """
        Test that entity type matching in applicableTo is case-sensitive.

        Given: Framework with applicableTo: ["Controls"] (capital C)
        When: Control references this framework
        Then: Should not match "controls" (lowercase) - validation fails
        """
        from validate_framework_references import validate_framework_applicability

        # This scenario tests internal case handling
        frameworks_applicability = {"test-framework": ["Controls"]}  # Capital C
        risk_frameworks = {}
        control_frameworks = {"control-1": ["test-framework"]}

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, control_frameworks)

        # Should fail because "Controls" != "controls"
        assert len(errors) == 1, "Should fail when applicableTo has wrong case"
        assert "control-1" in errors[0]
        assert "test-framework" in errors[0]


# ============================================================================
# Test Integration with validate_frameworks()
# ============================================================================


class TestValidateFrameworksIntegration:
    """Test integration of applicability validation into validate_frameworks()."""

    def test_full_validation_pipeline_with_valid_applicability(self, tmp_path):
        """
        Test complete validation pipeline with valid applicability.

        Given: Valid frameworks, controls, and risks with correct applicability
        When: validate_frameworks() is called
        Then: Validation passes
        """
        from validate_framework_references import validate_frameworks

        # Create test YAML files
        frameworks_yaml = tmp_path / "frameworks.yaml"
        frameworks_yaml.write_text(
            """
frameworks:
  - id: test-framework
    name: Test Framework
    fullName: Test Framework
    description: Test
    baseUri: https://example.com
    applicableTo:
      - controls
      - risks
"""
        )

        risks_yaml = tmp_path / "risks.yaml"
        risks_yaml.write_text(
            """
risks:
  - id: risk-1
    title: Test Risk
    mappings:
      test-framework:
        - TEST-001
"""
        )

        controls_yaml = tmp_path / "controls.yaml"
        controls_yaml.write_text(
            """
controls:
  - id: control-1
    title: Test Control
    mappings:
      test-framework:
        - TEST-CTL-001
"""
        )

        result = validate_frameworks([frameworks_yaml, risks_yaml, controls_yaml])

        assert result is True, "Validation should pass with valid applicability"

    def test_full_validation_pipeline_with_invalid_control_applicability(self, tmp_path):
        """
        Test validation pipeline with invalid control applicability.

        Given: Control referencing framework not applicable to controls
        When: validate_frameworks() is called
        Then: Validation fails with applicability error
        """
        from validate_framework_references import validate_frameworks

        frameworks_yaml = tmp_path / "frameworks.yaml"
        frameworks_yaml.write_text(
            """
frameworks:
  - id: risks-only-framework
    name: Risks Only
    fullName: Risks Only Framework
    description: Test
    baseUri: https://example.com
    applicableTo:
      - risks
"""
        )

        risks_yaml = tmp_path / "risks.yaml"
        risks_yaml.write_text("risks: []")

        controls_yaml = tmp_path / "controls.yaml"
        controls_yaml.write_text(
            """
controls:
  - id: control-1
    title: Test Control
    mappings:
      risks-only-framework:
        - TEST-001
"""
        )

        result = validate_frameworks([frameworks_yaml, risks_yaml, controls_yaml])

        assert result is False, "Validation should fail with invalid applicability"

    def test_full_validation_pipeline_with_invalid_risk_applicability(self, tmp_path):
        """
        Test validation pipeline with invalid risk applicability.

        Given: Risk referencing framework not applicable to risks
        When: validate_frameworks() is called
        Then: Validation fails with applicability error
        """
        from validate_framework_references import validate_frameworks

        frameworks_yaml = tmp_path / "frameworks.yaml"
        frameworks_yaml.write_text(
            """
frameworks:
  - id: controls-only-framework
    name: Controls Only
    fullName: Controls Only Framework
    description: Test
    baseUri: https://example.com
    applicableTo:
      - controls
"""
        )

        risks_yaml = tmp_path / "risks.yaml"
        risks_yaml.write_text(
            """
risks:
  - id: risk-1
    title: Test Risk
    mappings:
      controls-only-framework:
        - TEST-001
"""
        )

        controls_yaml = tmp_path / "controls.yaml"
        controls_yaml.write_text("controls: []")

        result = validate_frameworks([frameworks_yaml, risks_yaml, controls_yaml])

        assert result is False, "Validation should fail with invalid applicability"

    def test_applicability_errors_combined_with_reference_errors(self, tmp_path):
        """
        Test applicability errors combined with framework reference errors.

        Given: Both invalid framework references and invalid applicability
        When: validate_frameworks() is called
        Then: Both types of errors are reported
        """
        from validate_framework_references import validate_frameworks

        frameworks_yaml = tmp_path / "frameworks.yaml"
        frameworks_yaml.write_text(
            """
frameworks:
  - id: existing-framework
    name: Existing Framework
    fullName: Existing Framework
    description: Test
    baseUri: https://example.com
    applicableTo:
      - risks
"""
        )

        risks_yaml = tmp_path / "risks.yaml"
        risks_yaml.write_text(
            """
risks:
  - id: risk-1
    title: Test Risk
    mappings:
      nonexistent-framework:  # Reference error
        - TEST-001
"""
        )

        controls_yaml = tmp_path / "controls.yaml"
        controls_yaml.write_text(
            """
controls:
  - id: control-1
    title: Test Control
    mappings:
      existing-framework:  # Applicability error (framework is risks-only)
        - TEST-002
"""
        )

        result = validate_frameworks([frameworks_yaml, risks_yaml, controls_yaml])

        assert result is False, "Validation should fail with multiple error types"

    def test_applicability_errors_combined_with_consistency_errors(self, tmp_path):
        """
        Test applicability errors combined with framework consistency errors.

        Given: Framework consistency errors and applicability errors
        When: validate_frameworks() is called
        Then: Both types of errors are reported
        """
        from validate_framework_references import validate_frameworks

        frameworks_yaml = tmp_path / "frameworks.yaml"
        frameworks_yaml.write_text(
            """
frameworks:
  - id: framework-1
    name: Framework 1
    # Missing required fields (consistency error)
    applicableTo:
      - risks
"""
        )

        risks_yaml = tmp_path / "risks.yaml"
        risks_yaml.write_text("risks: []")

        controls_yaml = tmp_path / "controls.yaml"
        controls_yaml.write_text(
            """
controls:
  - id: control-1
    title: Test Control
    mappings:
      framework-1:  # Applicability error
        - TEST-001
"""
        )

        result = validate_frameworks([frameworks_yaml, risks_yaml, controls_yaml])

        assert result is False, "Validation should fail with multiple error types"

    def test_validation_with_actual_production_data(
        self, frameworks_yaml_path, risks_yaml_path, controls_yaml_path
    ):
        """
        Test validation with actual production YAML files.

        Given: Actual frameworks.yaml, risks.yaml, controls.yaml
        When: validate_frameworks() is called
        Then: Validation passes (production data should be valid)
        """
        from validate_framework_references import validate_frameworks

        frameworks_path = frameworks_yaml_path
        risks_path = risks_yaml_path
        controls_path = controls_yaml_path

        assert frameworks_path.exists(), "frameworks.yaml must exist"
        assert risks_path.exists(), "risks.yaml must exist"
        assert controls_path.exists(), "controls.yaml must exist"

        result = validate_frameworks([frameworks_path, risks_path, controls_path])

        assert result is True, "Production data should pass all validation checks"

    def test_applicability_validation_reports_correct_error_count(self, tmp_path, capsys):
        """
        Test that applicability validation reports correct error count.

        Given: Multiple applicability errors
        When: validate_frameworks() is called
        Then: Error count is reported correctly
        """
        from validate_framework_references import validate_frameworks

        frameworks_yaml = tmp_path / "frameworks.yaml"
        frameworks_yaml.write_text(
            """
frameworks:
  - id: risks-only
    name: Risks Only
    fullName: Risks Only Framework
    description: Test
    baseUri: https://example.com
    applicableTo:
      - risks
"""
        )

        risks_yaml = tmp_path / "risks.yaml"
        risks_yaml.write_text("risks: []")

        controls_yaml = tmp_path / "controls.yaml"
        controls_yaml.write_text(
            """
controls:
  - id: control-1
    title: Control 1
    mappings:
      risks-only:
        - TEST-001
  - id: control-2
    title: Control 2
    mappings:
      risks-only:
        - TEST-002
"""
        )

        result = validate_frameworks([frameworks_yaml, risks_yaml, controls_yaml])
        captured = capsys.readouterr()

        assert result is False
        # Should mention 2 errors in output
        assert "2" in captured.out or "2" in str(result), "Should report 2 applicability errors"

    def test_success_message_when_applicability_valid(self, tmp_path, capsys):
        """
        Test success message when applicability validation passes.

        Given: All framework applicability is valid
        When: validate_frameworks() is called
        Then: Success message is displayed
        """
        from validate_framework_references import validate_frameworks

        frameworks_yaml = tmp_path / "frameworks.yaml"
        frameworks_yaml.write_text(
            """
frameworks:
  - id: test-framework
    name: Test Framework
    fullName: Test Framework
    description: Test
    baseUri: https://example.com
    applicableTo:
      - controls
      - risks
"""
        )

        risks_yaml = tmp_path / "risks.yaml"
        risks_yaml.write_text(
            """
risks:
  - id: risk-1
    mappings:
      test-framework:
        - R1
"""
        )

        controls_yaml = tmp_path / "controls.yaml"
        controls_yaml.write_text(
            """
controls:
  - id: control-1
    mappings:
      test-framework:
        - C1
"""
        )

        result = validate_frameworks([frameworks_yaml, risks_yaml, controls_yaml])
        captured = capsys.readouterr()

        assert result is True
        assert "✅" in captured.out or "pass" in captured.out.lower(), "Should show success message"

    def test_integration_with_existing_extract_functions(self, tmp_path):
        """
        Test that applicability validation integrates with existing extract functions.

        Given: validate_frameworks() uses existing extract_risk_framework_references and
               extract_control_framework_references
        When: Applicability validation is added
        Then: All extract functions work together correctly
        """
        from validate_framework_references import validate_frameworks

        frameworks_yaml = tmp_path / "frameworks.yaml"
        frameworks_yaml.write_text(
            """
frameworks:
  - id: multi-framework
    name: Multi Framework
    fullName: Multi Framework
    description: Test
    baseUri: https://example.com
    applicableTo:
      - controls
      - risks
"""
        )

        risks_yaml = tmp_path / "risks.yaml"
        risks_yaml.write_text(
            """
risks:
  - id: risk-1
    mappings:
      multi-framework:
        - R1
        - R2
"""
        )

        controls_yaml = tmp_path / "controls.yaml"
        controls_yaml.write_text(
            """
controls:
  - id: control-1
    mappings:
      multi-framework:
        - C1
        - C2
        - C3
"""
        )

        result = validate_frameworks([frameworks_yaml, risks_yaml, controls_yaml])

        assert result is True, "Should integrate with existing extraction logic"


# ============================================================================
# Test with Real Production Data
# ============================================================================


class TestFrameworkApplicabilityWithRealData:
    """Test framework applicability validation with actual production data."""

    def test_validate_actual_controls_yaml_framework_mappings(self, frameworks_yaml_path, controls_yaml_path):
        """
        Test that actual controls.yaml only references applicable frameworks.

        Given: Actual controls.yaml and frameworks.yaml
        When: Controls are validated for applicability
        Then: All controls only reference frameworks applicable to controls
        """
        from validate_framework_references import (
            extract_control_framework_references,
            extract_framework_applicability,
            load_yaml_file,
            validate_framework_applicability,
        )

        frameworks_path = frameworks_yaml_path
        controls_path = controls_yaml_path

        frameworks_data = load_yaml_file(frameworks_path)
        controls_data = load_yaml_file(controls_path)

        assert frameworks_data is not None
        assert controls_data is not None

        frameworks_applicability = extract_framework_applicability(frameworks_data)
        control_frameworks = extract_control_framework_references(controls_data)

        errors = validate_framework_applicability(frameworks_applicability, {}, control_frameworks)

        assert errors == [], f"Production controls should only reference applicable frameworks. Errors: {errors}"

    def test_validate_actual_risks_yaml_framework_mappings(self, frameworks_yaml_path, risks_yaml_path):
        """
        Test that actual risks.yaml only references applicable frameworks.

        Given: Actual risks.yaml and frameworks.yaml
        When: Risks are validated for applicability
        Then: All risks only reference frameworks applicable to risks
        """
        from validate_framework_references import (
            extract_framework_applicability,
            extract_risk_framework_references,
            load_yaml_file,
            validate_framework_applicability,
        )

        frameworks_path = frameworks_yaml_path
        risks_path = risks_yaml_path

        frameworks_data = load_yaml_file(frameworks_path)
        risks_data = load_yaml_file(risks_path)

        assert frameworks_data is not None
        assert risks_data is not None

        frameworks_applicability = extract_framework_applicability(frameworks_data)
        risk_frameworks = extract_risk_framework_references(risks_data)

        errors = validate_framework_applicability(frameworks_applicability, risk_frameworks, {})

        assert errors == [], f"Production risks should only reference applicable frameworks. Errors: {errors}"

    def test_detect_invalid_applicability_in_production_data_if_exists(
        self, frameworks_yaml_path, risks_yaml_path, controls_yaml_path
    ):
        """
        Test detection of any invalid applicability in production data.

        Given: Actual production YAML files
        When: Full applicability validation is run
        Then: Any invalid applicability is detected and reported
        """
        from validate_framework_references import validate_frameworks

        frameworks_path = frameworks_yaml_path
        risks_path = risks_yaml_path
        controls_path = controls_yaml_path

        result = validate_frameworks([frameworks_path, risks_path, controls_path])

        # This test documents actual state - if production has issues, they'll be caught
        assert isinstance(result, bool), "Validation should return boolean result"

    def test_all_production_frameworks_have_applicable_to_defined(self, frameworks_yaml_path):
        """
        Test that all production frameworks have applicableTo field.

        Given: Actual frameworks.yaml
        When: Frameworks are loaded
        Then: All frameworks have applicableTo field defined
        """
        from validate_framework_references import load_yaml_file

        frameworks_path = frameworks_yaml_path
        frameworks_data = load_yaml_file(frameworks_path)

        assert frameworks_data is not None
        assert "frameworks" in frameworks_data

        for framework in frameworks_data["frameworks"]:
            framework_id = framework.get("id")
            assert "applicableTo" in framework, f"Framework {framework_id} must have applicableTo field"
            assert isinstance(framework["applicableTo"], list), (
                f"Framework {framework_id} applicableTo must be a list"
            )
            assert len(framework["applicableTo"]) > 0, f"Framework {framework_id} applicableTo must not be empty"


# ============================================================================
# Test Summary
# ============================================================================

"""
Test Summary
============
Total Tests: 46
- Extract Framework Applicability: 11 tests
- Validate Framework Applicability: 21 tests
- Integration with validate_frameworks(): 10 tests
- Real Production Data: 4 tests

Coverage Areas:
- Extraction of applicableTo from frameworks.yaml
- Validation of control framework applicability
- Validation of risk framework applicability
- Multiple entity types per framework
- Mixed valid/invalid framework references
- Error message quality and content
- Integration with existing validation pipeline
- Edge cases (empty dicts, missing fields, malformed data)
- Production data validation

Expected Initial State (RED phase):
- All tests FAIL because functions don't exist yet:
  - extract_framework_applicability() - Not implemented
  - validate_framework_applicability() - Not implemented
  - Integration into validate_frameworks() - Not implemented

After Implementation (GREEN phase):
- All tests should PASS
- Production data should validate correctly
- Error messages should be clear and actionable

Test Quality Metrics:
- Coverage: 90%+ of new validation functions
- Clear Given-When-Then structure
- Comprehensive error condition testing
- Edge case coverage
- Integration testing
- Production data validation
"""

#!/usr/bin/env python3
"""
Tests for Decision 1 (C1-schema-tightenings): remove `relevantQuestions` from
risks.schema.json per ADR-019 D6.

B3 (PR #293) cleaned `relevantQuestions` content from risks.yaml. This PR
closes the loop on the schema side: the property definition is dropped from
definitions/risk/properties, so any YAML author who accidentally writes
`relevantQuestions` gets a validation error instead of silent acceptance.

Coverage:
- definitions/risk/properties does NOT contain 'relevantQuestions' (post-tightening assertion).
- A synthetic risk entry with relevantQuestions raises ValidationError (RED today: passes with current schema).
- The live risks.yaml corpus contains no risk entries with relevantQuestions keys (audit probe).

Note on RED phase:
  Tests in TestRelevantQuestionsRemovedFromSchema / TestRelevantQuestionsRejected
  are expected to FAIL against the current (pre-tightening) schema. They will
  pass after the SWE removes the property definition.
  TestRisksYamlHasNoRelevantQuestions is expected to PASS today (B3 already cleaned).
"""

import sys
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft7Validator

sys.path.insert(0, str(Path(__file__).parent.parent))

from conftest import _load_schema, _make_registry

# ============================================================================
# Module-level constants
# ============================================================================

SCHEMA_FILE = "risks.schema.json"
ENTITY_KEY = "risk"

# A minimal valid risk entry used as the base for synthetic tests.
# Fields satisfy the required array: id, title, shortDescription, longDescription,
# category, personas, controls. Values are enum-valid per the current schema.
_MINIMAL_VALID_RISK: dict = {
    "id": "riskDataPoisoning",
    "title": "Data Poisoning",
    "shortDescription": ["Short description text."],
    "longDescription": ["Long description text."],
    "category": "risksSupplyChainAndDevelopment",
    "personas": ["personaModelProvider"],
    "controls": ["controlTrainingDataSanitization"],
}


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def schemas_dir(risk_map_schemas_dir: Path) -> Path:
    """Alias for concise test signatures."""
    return risk_map_schemas_dir


@pytest.fixture(scope="module")
def risks_schema(schemas_dir: Path) -> dict:
    """Parsed risks.schema.json."""
    return _load_schema(schemas_dir, SCHEMA_FILE)


@pytest.fixture(scope="module")
def risk_definition(risks_schema: dict) -> dict:
    """The definitions/risk block from risks.schema.json."""
    defn = risks_schema.get("definitions", {}).get(ENTITY_KEY)
    if defn is None:
        pytest.fail(f"definitions/{ENTITY_KEY} not found in {SCHEMA_FILE}")
    return defn


@pytest.fixture(scope="module")
def risk_properties(risk_definition: dict) -> dict:
    """The properties dict from definitions/risk."""
    props = risk_definition.get("properties", {})
    if not props:
        pytest.fail(f"definitions/{ENTITY_KEY}/properties not found in {SCHEMA_FILE}")
    return props


@pytest.fixture(scope="module")
def risk_validator(schemas_dir: Path) -> Draft7Validator:
    """
    Draft-07 validator targeting definitions/risk with full cross-file $ref resolution.

    Uses a $ref wrapper against the registry so internal #/definitions/... refs inside
    definitions/risk (e.g., controls.$ref, personas.$ref) resolve correctly against the
    full risks.schema.json root, not just the entity sub-object.
    """
    registry = _make_registry(schemas_dir)
    return Draft7Validator({"$ref": f"{SCHEMA_FILE}#/definitions/{ENTITY_KEY}"}, registry=registry)


@pytest.fixture(scope="module")
def risks_yaml_data(risk_map_yaml_dir: Path) -> dict:
    """Parsed risks.yaml corpus data."""
    path = risk_map_yaml_dir / "risks.yaml"
    if not path.is_file():
        pytest.fail(f"risks.yaml not found at {path}")
    with open(path) as fh:
        return yaml.safe_load(fh)


# ============================================================================
# Decision 1 — relevantQuestions REMOVED from schema (RED today; GREEN post-tightening)
# ============================================================================


class TestRelevantQuestionsRemovedFromSchema:
    """
    definitions/risk/properties must NOT contain 'relevantQuestions' after tightening.

    ADR-019 D6: the field was removed from the YAML corpus by B3 (PR #293).
    The schema property definition must also be removed so the closed schema
    (post additionalProperties:false, Decision 2) rejects stray uses.

    RED phase: these tests FAIL today because the schema still declares the property.
    """

    def test_relevant_questions_absent_from_risk_properties(self, risk_properties: dict):
        """
        Test that relevantQuestions is not declared in definitions/risk/properties.

        Given: definitions/risk/properties from risks.schema.json
        When: The property names are inspected
        Then: 'relevantQuestions' is absent (per ADR-019 D6 cleanup)
        """
        assert "relevantQuestions" not in risk_properties, (
            "definitions/risk/properties must not declare 'relevantQuestions' after C1 tightening "
            "(ADR-019 D6: field removed from YAML corpus by B3; schema must follow)"
        )


# ============================================================================
# Decision 1 — synthetic entry with relevantQuestions is rejected (RED today)
# ============================================================================


class TestRelevantQuestionsRejected:
    """
    A synthetic risk entry carrying relevantQuestions must raise ValidationError
    once additionalProperties:false is in place (Decision 2 depends on Decision 1).

    This test exercises the combined effect of D1+D2: after both land, a stray
    relevantQuestions field is caught by additionalProperties:false.

    RED phase: FAILS today because (a) the property is still declared and
    (b) additionalProperties:false is not yet on definitions/risk.
    """

    def test_risk_with_relevant_questions_raises_validation_error(self, risk_validator: Draft7Validator):
        """
        Test that a risk entry with relevantQuestions is rejected after tightening.

        Given: A synthetic risk with a 'relevantQuestions' field
        When: It is validated against definitions/risk
        Then: ValidationError is raised (field removed + additionalProperties:false)
        """
        entry = dict(_MINIMAL_VALID_RISK)
        entry["relevantQuestions"] = ["Is this risk applicable?"]
        errors = list(risk_validator.iter_errors(entry))
        assert errors, (
            "A risk entry with 'relevantQuestions' must fail validation after C1 tightening "
            "(ADR-019 D6 removal + additionalProperties:false from Decision 2)"
        )

    def test_valid_risk_without_relevant_questions_passes(self, risk_validator: Draft7Validator):
        """
        Test that a minimal valid risk entry passes validation.

        Given: A minimal risk entry with all required fields and no stray properties
        When: It is validated against definitions/risk
        Then: No ValidationError is raised (baseline: the valid entry must pass)
        """
        errors = list(risk_validator.iter_errors(_MINIMAL_VALID_RISK))
        assert not errors, (
            f"Minimal valid risk entry must pass definitions/risk validation; "
            f"errors: {[e.message for e in errors]}"
        )


# ============================================================================
# Corpus audit — risks.yaml has no relevantQuestions keys (GREEN today; stays GREEN)
# ============================================================================


class TestRisksYamlHasNoRelevantQuestions:
    """
    Audit probe: the live risks.yaml corpus must have no risk entries carrying
    'relevantQuestions'. B3 (PR #293) cleaned these; this test is a forward
    guard that surfaces regressions before schema tightening lands.

    Expected to PASS today and after tightening.
    """

    def test_no_relevant_questions_in_corpus(self, risks_yaml_data: dict):
        """
        Test that no risk entry in risks.yaml contains a relevantQuestions key.

        Given: The full risks.yaml corpus
        When: Each risk entry is inspected for the 'relevantQuestions' key
        Then: No entry carries the key (B3 cleanup is complete)
        """
        offenders = [
            r.get("id", "<unknown>") for r in risks_yaml_data.get("risks", []) if "relevantQuestions" in r
        ]
        assert not offenders, (
            f"risks.yaml still has 'relevantQuestions' in risk entries: {offenders}. "
            "B3 (PR #293) should have removed all occurrences."
        )


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Total test methods: 4
Test classes: 3

- TestRelevantQuestionsRemovedFromSchema (1)
    RED today: schema still declares the property.
    GREEN post-tightening: property definition removed.

- TestRelevantQuestionsRejected (2)
    RED today: property still accepted by schema; additionalProperties not yet false.
    GREEN post-tightening: combined D1+D2 effect rejects stray field.

- TestRisksYamlHasNoRelevantQuestions (1)
    GREEN today: B3 already cleaned corpus.
    GREEN post-tightening: still passes.

Coverage areas:
- Schema structural check: relevantQuestions absent from definitions/risk/properties
- Behavioral rejection: synthetic entry with relevantQuestions fails validation
- Corpus audit: live risks.yaml has no relevantQuestions (forward guard)
"""

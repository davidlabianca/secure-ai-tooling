#!/usr/bin/env python3
"""
Tests for Decision 1 (C1-schema-tightenings): `relevantQuestions` is removed
from risks.schema.json per ADR-019 D6.

B3 (PR #293) cleaned the field from risks.yaml content; C1 closes the loop
on the schema side. With the property definition dropped from
definitions/risk/properties (and additionalProperties:false from Decision 2),
any YAML author who writes `relevantQuestions` gets a validation error
instead of silent acceptance.

Coverage:
- definitions/risk/properties does not declare 'relevantQuestions'.
- A synthetic risk entry carrying relevantQuestions fails validation
  (combined effect of D1 removal + D2 additionalProperties:false).
- The live risks.yaml corpus carries no relevantQuestions keys (forward guard
  against a regression that would reintroduce the field).
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
# Decision 1 — relevantQuestions absent from schema
# ============================================================================


class TestRelevantQuestionsRemovedFromSchema:
    """
    definitions/risk/properties does not contain 'relevantQuestions'.

    ADR-019 D6: the field was removed from the YAML corpus by B3 (PR #293) and
    from the schema by C1. With additionalProperties:false also in place
    (Decision 2), stray uses of the field are rejected at validation time.
    """

    def test_relevant_questions_absent_from_risk_properties(self, risk_properties: dict):
        """
        Test that relevantQuestions is not declared in definitions/risk/properties.

        Given: definitions/risk/properties from risks.schema.json
        When: The property names are inspected
        Then: 'relevantQuestions' is absent (per ADR-019 D6 cleanup)
        """
        assert "relevantQuestions" not in risk_properties, (
            "definitions/risk/properties must not declare 'relevantQuestions' "
            "(ADR-019 D6: field removed from YAML corpus by B3; schema follows)"
        )


# ============================================================================
# Decision 1 — synthetic entry with relevantQuestions is rejected
# ============================================================================


class TestRelevantQuestionsRejected:
    """
    A synthetic risk entry carrying relevantQuestions raises ValidationError.

    Exercises the combined effect of D1+D2: the property no longer exists in
    the schema, and additionalProperties:false on definitions/risk rejects
    any stray field — including the retired relevantQuestions key.
    """

    def test_risk_with_relevant_questions_raises_validation_error(self, risk_validator: Draft7Validator):
        """
        Test that a risk entry with relevantQuestions is rejected.

        Given: A synthetic risk with a 'relevantQuestions' field
        When: It is validated against definitions/risk
        Then: ValidationError is raised (field removed + additionalProperties:false)
        """
        entry = dict(_MINIMAL_VALID_RISK)
        entry["relevantQuestions"] = ["Is this risk applicable?"]
        errors = list(risk_validator.iter_errors(entry))
        assert errors, (
            "A risk entry with 'relevantQuestions' must fail validation "
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
# Corpus audit — risks.yaml has no relevantQuestions keys
# ============================================================================


class TestRisksYamlHasNoRelevantQuestions:
    """
    Audit probe: the live risks.yaml corpus carries no risk entries with
    'relevantQuestions'. B3 (PR #293) cleaned these; this test is a forward
    guard that catches any regression that would reintroduce the field.
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

- TestRelevantQuestionsRemovedFromSchema (1) — property absent from
  definitions/risk/properties.
- TestRelevantQuestionsRejected (2) — synthetic entry with the field is
  rejected (D1+D2 combined effect); minimal valid entry still passes.
- TestRisksYamlHasNoRelevantQuestions (1) — live corpus forward-guard.

Coverage areas:
- Schema structural check: relevantQuestions absent from definitions/risk/properties
- Behavioral rejection: synthetic entry with relevantQuestions fails validation
- Corpus audit: live risks.yaml has no relevantQuestions (forward guard)
"""

#!/usr/bin/env python3
"""
Tests for Decision 3 (C1-schema-tightenings): `maxLength` constraints on
`title` fields in risks.schema.json and controls.schema.json.

Per ADR-019 D8: risks.schema.json definitions/risk/properties/title declares
maxLength:120.
Per ADR-020 D7: controls.schema.json definitions/control/properties/title
declares maxLength:100.

The limits sit conservatively above the longest current corpus entry — max
risk title 40 chars, max control title 49 chars — capping future drift
without breaking existing content.

Coverage:
- Schema structural check: maxLength declared at the correct value.
- Behavioral boundary: at-limit titles pass, over-limit titles are rejected.
- Corpus audit: every current risks.yaml / controls.yaml title is within
  its limit (forward guard against future content drift).
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

RISK_SCHEMA_FILE = "risks.schema.json"
CONTROL_SCHEMA_FILE = "controls.schema.json"

RISK_TITLE_MAX_LENGTH = 120
CONTROL_TITLE_MAX_LENGTH = 100

# Minimal valid entries for each entity (required fields satisfied, enum-valid).
# Used as the base for boundary tests; title is overridden per test.
_MINIMAL_RISK_BASE: dict = {
    "id": "riskDataPoisoning",
    "title": "Data Poisoning",
    "shortDescription": ["Short description."],
    "longDescription": ["Long description."],
    "category": "risksSupplyChainAndDevelopment",
    "personas": ["personaModelProvider"],
    "controls": ["controlTrainingDataSanitization"],
}

_MINIMAL_CONTROL_BASE: dict = {
    "title": "Training Data Management",
    "description": ["Manage training data."],
    "category": "controlsData",
    "personas": ["personaModelProvider"],
    "components": ["componentDataSources"],
    "risks": ["riskDataPoisoning"],
}


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def schemas_dir(risk_map_schemas_dir: Path) -> Path:
    """Alias for concise test signatures."""
    return risk_map_schemas_dir


@pytest.fixture(scope="module")
def risk_title_schema(schemas_dir: Path) -> dict:
    """The title property sub-schema from definitions/risk/properties."""
    schema = _load_schema(schemas_dir, RISK_SCHEMA_FILE)
    title_prop = schema.get("definitions", {}).get("risk", {}).get("properties", {}).get("title")
    if title_prop is None:
        pytest.fail(f"definitions/risk/properties/title not found in {RISK_SCHEMA_FILE}")
    return title_prop


@pytest.fixture(scope="module")
def control_title_schema(schemas_dir: Path) -> dict:
    """The title property sub-schema from definitions/control/properties."""
    schema = _load_schema(schemas_dir, CONTROL_SCHEMA_FILE)
    title_prop = schema.get("definitions", {}).get("control", {}).get("properties", {}).get("title")
    if title_prop is None:
        pytest.fail(f"definitions/control/properties/title not found in {CONTROL_SCHEMA_FILE}")
    return title_prop


@pytest.fixture(scope="module")
def risk_validator(schemas_dir: Path) -> Draft7Validator:
    """
    Draft-07 validator targeting definitions/risk with full cross-file $ref resolution.

    Uses a $ref wrapper against the registry so internal #/definitions/... refs inside
    definitions/risk resolve correctly against the full risks.schema.json root.
    """
    registry = _make_registry(schemas_dir)
    return Draft7Validator({"$ref": f"{RISK_SCHEMA_FILE}#/definitions/risk"}, registry=registry)


@pytest.fixture(scope="module")
def control_validator(schemas_dir: Path) -> Draft7Validator:
    """
    Draft-07 validator targeting definitions/control with full cross-file $ref resolution.

    Uses a $ref wrapper against the registry so internal #/definitions/... refs inside
    definitions/control (e.g., #/definitions/category/properties/id) resolve correctly
    against the full controls.schema.json root.
    """
    registry = _make_registry(schemas_dir)
    return Draft7Validator({"$ref": f"{CONTROL_SCHEMA_FILE}#/definitions/control"}, registry=registry)


@pytest.fixture(scope="module")
def risks_yaml_data(risk_map_yaml_dir: Path) -> dict:
    """Parsed risks.yaml corpus data."""
    path = risk_map_yaml_dir / "risks.yaml"
    if not path.is_file():
        pytest.fail(f"risks.yaml not found at {path}")
    with open(path) as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def controls_yaml_data(risk_map_yaml_dir: Path) -> dict:
    """Parsed controls.yaml corpus data."""
    path = risk_map_yaml_dir / "controls.yaml"
    if not path.is_file():
        pytest.fail(f"controls.yaml not found at {path}")
    with open(path) as fh:
        return yaml.safe_load(fh)


# ============================================================================
# Decision 3 — risk title maxLength declared
# ============================================================================


class TestRiskTitleMaxLengthDeclared:
    """
    definitions/risk/properties/title declares maxLength:120 per ADR-019 D8.
    """

    def test_risk_title_has_max_length_120(self, risk_title_schema: dict):
        """
        Test that definitions/risk/properties/title declares maxLength:120.

        Given: The title property schema from definitions/risk
        When: Its maxLength is inspected
        Then: It is 120 (per ADR-019 D8)
        """
        assert risk_title_schema.get("maxLength") == RISK_TITLE_MAX_LENGTH, (
            f"definitions/risk/properties/title must declare maxLength:{RISK_TITLE_MAX_LENGTH} "
            f"(per ADR-019 D8); got: {risk_title_schema.get('maxLength')!r}"
        )


# ============================================================================
# Decision 3 — control title maxLength declared
# ============================================================================


class TestControlTitleMaxLengthDeclared:
    """
    definitions/control/properties/title declares maxLength:100 per ADR-020 D7.
    """

    def test_control_title_has_max_length_100(self, control_title_schema: dict):
        """
        Test that definitions/control/properties/title declares maxLength:100.

        Given: The title property schema from definitions/control
        When: Its maxLength is inspected
        Then: It is 100 (per ADR-020 D7)
        """
        assert control_title_schema.get("maxLength") == CONTROL_TITLE_MAX_LENGTH, (
            f"definitions/control/properties/title must declare maxLength:{CONTROL_TITLE_MAX_LENGTH} "
            f"(per ADR-020 D7); got: {control_title_schema.get('maxLength')!r}"
        )


# ============================================================================
# Decision 3 — risk title boundary enforcement
# ============================================================================


class TestRiskTitleBoundaryEnforcement:
    """
    Behavioral tests for the risk title maxLength boundary.

    A title of exactly 120 chars passes; 121 chars is rejected by the
    maxLength constraint.
    """

    def test_risk_title_at_max_length_passes(self, risk_validator: Draft7Validator):
        """
        Test that a risk title of exactly 120 characters is accepted.

        Given: A synthetic risk entry with a 120-char title
        When: It is validated against definitions/risk
        Then: No ValidationError is raised (boundary is inclusive)
        """
        entry = dict(_MINIMAL_RISK_BASE)
        entry["title"] = "A" * RISK_TITLE_MAX_LENGTH
        errors = list(risk_validator.iter_errors(entry))
        assert not errors, (
            f"Risk title of length {RISK_TITLE_MAX_LENGTH} must pass (inclusive boundary); "
            f"errors: {[e.message for e in errors]}"
        )

    def test_risk_title_one_over_max_length_fails(self, risk_validator: Draft7Validator):
        """
        Test that a risk title of 121 characters is rejected.

        Given: A synthetic risk entry with a 121-char title
        When: It is validated against definitions/risk
        Then: ValidationError is raised (maxLength:120 exceeded)
        """
        entry = dict(_MINIMAL_RISK_BASE)
        entry["title"] = "A" * (RISK_TITLE_MAX_LENGTH + 1)
        errors = list(risk_validator.iter_errors(entry))
        assert errors, (
            f"Risk title of length {RISK_TITLE_MAX_LENGTH + 1} must fail validation "
            f"(maxLength:{RISK_TITLE_MAX_LENGTH})"
        )


# ============================================================================
# Decision 3 — control title boundary enforcement
# ============================================================================


class TestControlTitleBoundaryEnforcement:
    """
    Behavioral tests for the control title maxLength boundary.

    A title of exactly 100 chars passes; 101 chars is rejected by the
    maxLength constraint.
    """

    def test_control_title_at_max_length_passes(self, control_validator: Draft7Validator):
        """
        Test that a control title of exactly 100 characters is accepted.

        Given: A synthetic control entry with a 100-char title
        When: It is validated against definitions/control
        Then: No ValidationError is raised (boundary is inclusive)
        """
        entry = dict(_MINIMAL_CONTROL_BASE)
        entry["title"] = "B" * CONTROL_TITLE_MAX_LENGTH
        errors = list(control_validator.iter_errors(entry))
        assert not errors, (
            f"Control title of length {CONTROL_TITLE_MAX_LENGTH} must pass (inclusive boundary); "
            f"errors: {[e.message for e in errors]}"
        )

    def test_control_title_one_over_max_length_fails(self, control_validator: Draft7Validator):
        """
        Test that a control title of 101 characters is rejected.

        Given: A synthetic control entry with a 101-char title
        When: It is validated against definitions/control
        Then: ValidationError is raised (maxLength:100 exceeded)
        """
        entry = dict(_MINIMAL_CONTROL_BASE)
        entry["title"] = "B" * (CONTROL_TITLE_MAX_LENGTH + 1)
        errors = list(control_validator.iter_errors(entry))
        assert errors, (
            f"Control title of length {CONTROL_TITLE_MAX_LENGTH + 1} must fail validation "
            f"(maxLength:{CONTROL_TITLE_MAX_LENGTH})"
        )


# ============================================================================
# Corpus audit — no current entry exceeds the maxLength limits
# ============================================================================


class TestRiskTitleCorpusAudit:
    """
    Forward guard: every current risks.yaml title is ≤120 characters.

    The schema constraint enforces the limit; this test surfaces a violation
    with the offending entries listed by name and length if content drift
    ever reintroduces an over-limit title.
    """

    def test_all_risk_titles_within_max_length(self, risks_yaml_data: dict):
        """
        Test that every risk title in the live corpus is ≤120 characters.

        Given: All risks from risks.yaml
        When: Each title's length is measured
        Then: No title exceeds 120 characters

        On failure: lists offending risk IDs + title lengths for the maintainer.
        """
        offenders = [
            (r.get("id", "<unknown>"), r.get("title", ""), len(r.get("title", "")))
            for r in risks_yaml_data.get("risks", [])
            if len(r.get("title", "")) > RISK_TITLE_MAX_LENGTH
        ]
        assert not offenders, (
            f"CONTENT DRIFT: risks.yaml has titles exceeding maxLength:{RISK_TITLE_MAX_LENGTH}:\n"
            + "\n".join(f"  {rid!r}: length={length}, title={title!r}" for rid, title, length in offenders)
        )


class TestControlTitleCorpusAudit:
    """
    Forward guard: every current controls.yaml title is ≤100 characters.
    """

    def test_all_control_titles_within_max_length(self, controls_yaml_data: dict):
        """
        Test that every control title in the live corpus is ≤100 characters.

        Given: All controls from controls.yaml
        When: Each title's length is measured
        Then: No title exceeds 100 characters

        On failure: lists offending control IDs + title lengths for the maintainer.
        """
        offenders = [
            (c.get("id", "<unknown>"), c.get("title", ""), len(c.get("title", "")))
            for c in controls_yaml_data.get("controls", [])
            if len(c.get("title", "")) > CONTROL_TITLE_MAX_LENGTH
        ]
        assert not offenders, (
            f"CONTENT DRIFT: controls.yaml has titles exceeding maxLength:{CONTROL_TITLE_MAX_LENGTH}:\n"
            + "\n".join(f"  {cid!r}: length={length}, title={title!r}" for cid, title, length in offenders)
        )


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Total test methods: 8
Test classes: 6

- TestRiskTitleMaxLengthDeclared (1) — schema declares maxLength:120.
- TestControlTitleMaxLengthDeclared (1) — schema declares maxLength:100.
- TestRiskTitleBoundaryEnforcement (2) — at-limit passes, over-limit fails.
- TestControlTitleBoundaryEnforcement (2) — same boundary pattern at 100.
- TestRiskTitleCorpusAudit (1) — live risks.yaml forward guard
  (current max corpus title: 40 chars).
- TestControlTitleCorpusAudit (1) — live controls.yaml forward guard
  (current max corpus title: 49 chars).

Coverage areas:
- Schema structural check: maxLength declared at correct value
- Behavioral boundary: at-limit pass, over-limit fail
- Corpus audit: no existing content exceeds limits (drift-free)
"""

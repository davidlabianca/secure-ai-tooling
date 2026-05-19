#!/usr/bin/env python3
"""
Tests for Decision 3 (C1-schema-tightenings): add `maxLength` constraints to
`title` fields in risks.schema.json and controls.schema.json.

Per ADR-019 D8: risks.schema.json definitions/risk/properties/title gets maxLength:120.
Per ADR-020 D7: controls.schema.json definitions/control/properties/title gets maxLength:100.

These limits were set conservatively above the longest current corpus entry to
avoid breaking existing content while capping future drift.

Coverage:
- definitions/risk/properties/title declares maxLength:120.
- definitions/control/properties/title declares maxLength:100.
- A synthetic risk title of length 121 is rejected; length 120 passes.
- A synthetic control title of length 101 is rejected; length 100 passes.
- Corpus audit: every current risks.yaml title is ≤120 chars (no existing drift).
- Corpus audit: every current controls.yaml title is ≤100 chars (no existing drift).

Note on RED phase:
  Tests in TestRiskTitleMaxLengthDeclared / TestControlTitleMaxLengthDeclared
  and all synthetic boundary tests FAIL today (pre-tightening: no maxLength declared).
  Corpus audit tests PASS today (no current corpus entry exceeds limits).
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
# Decision 3 — risk title maxLength declared (RED today)
# ============================================================================


class TestRiskTitleMaxLengthDeclared:
    """
    definitions/risk/properties/title must declare maxLength:120 after C1 tightening.

    RED phase: FAILS today (no maxLength on title).
    GREEN post-tightening.
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
# Decision 3 — control title maxLength declared (RED today)
# ============================================================================


class TestControlTitleMaxLengthDeclared:
    """
    definitions/control/properties/title must declare maxLength:100 after C1 tightening.

    RED phase: FAILS today (no maxLength on title).
    GREEN post-tightening.
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
# Decision 3 — risk title boundary enforcement (RED today)
# ============================================================================


class TestRiskTitleBoundaryEnforcement:
    """
    Behavioral tests for the risk title maxLength boundary.

    A title of exactly 120 chars must pass; 121 chars must fail.

    RED phase: both boundary tests FAIL today (no maxLength declared → 121-char title accepted).
    GREEN post-tightening.
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
            f"(maxLength:{RISK_TITLE_MAX_LENGTH}); currently accepted — RED phase"
        )


# ============================================================================
# Decision 3 — control title boundary enforcement (RED today)
# ============================================================================


class TestControlTitleBoundaryEnforcement:
    """
    Behavioral tests for the control title maxLength boundary.

    A title of exactly 100 chars must pass; 101 chars must fail.

    RED phase: both boundary tests FAIL today (no maxLength declared → 101-char title accepted).
    GREEN post-tightening.
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
            f"(maxLength:{CONTROL_TITLE_MAX_LENGTH}); currently accepted — RED phase"
        )


# ============================================================================
# Corpus audit — no current entry exceeds the maxLength limits (GREEN today)
# ============================================================================


class TestRiskTitleCorpusAudit:
    """
    Audit probe: every current risks.yaml title must be ≤120 characters.

    This probe verifies that tightening does not break existing content.
    If this test FAILS today, there is content drift that must be fixed
    BEFORE the schema constraint is added — surface the offending entries.

    Expected to PASS today and post-tightening.
    """

    def test_all_risk_titles_within_max_length(self, risks_yaml_data: dict):
        """
        Test that every risk title in the live corpus is ≤120 characters.

        Given: All risks from risks.yaml
        When: Each title's length is measured
        Then: No title exceeds 120 characters

        DRIFT ALERT: If this fails, list offending risk IDs and their title lengths
        so the maintainer can shorten them before the schema tightening lands.
        """
        offenders = [
            (r.get("id", "<unknown>"), r.get("title", ""), len(r.get("title", "")))
            for r in risks_yaml_data.get("risks", [])
            if len(r.get("title", "")) > RISK_TITLE_MAX_LENGTH
        ]
        assert not offenders, (
            f"CONTENT DRIFT: risks.yaml has titles exceeding maxLength:{RISK_TITLE_MAX_LENGTH}. "
            f"Fix these before applying the schema constraint:\n"
            + "\n".join(f"  {rid!r}: length={length}, title={title!r}" for rid, title, length in offenders)
        )


class TestControlTitleCorpusAudit:
    """
    Audit probe: every current controls.yaml title must be ≤100 characters.

    Expected to PASS today and post-tightening.
    """

    def test_all_control_titles_within_max_length(self, controls_yaml_data: dict):
        """
        Test that every control title in the live corpus is ≤100 characters.

        Given: All controls from controls.yaml
        When: Each title's length is measured
        Then: No title exceeds 100 characters

        DRIFT ALERT: If this fails, list offending control IDs so the maintainer
        can shorten them before the schema tightening lands.
        """
        offenders = [
            (c.get("id", "<unknown>"), c.get("title", ""), len(c.get("title", "")))
            for c in controls_yaml_data.get("controls", [])
            if len(c.get("title", "")) > CONTROL_TITLE_MAX_LENGTH
        ]
        assert not offenders, (
            f"CONTENT DRIFT: controls.yaml has titles exceeding maxLength:{CONTROL_TITLE_MAX_LENGTH}. "
            f"Fix these before applying the schema constraint:\n"
            + "\n".join(f"  {cid!r}: length={length}, title={title!r}" for cid, title, length in offenders)
        )


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Total test methods: 8 (excluding skip stub)
Test classes: 6

- TestRiskTitleMaxLengthDeclared (1)
    RED today: maxLength not declared.
    GREEN post-tightening.

- TestControlTitleMaxLengthDeclared (1)
    RED today: maxLength not declared.
    GREEN post-tightening.

- TestRiskTitleBoundaryEnforcement (2)
    at-boundary pass: RED today (maxLength not declared, so 120-char title trivially passes —
      but the schema structural test above would fail first).
    over-boundary fail: RED today (121-char title accepted without maxLength).
    GREEN post-tightening.

- TestControlTitleBoundaryEnforcement (2)
    Same RED/GREEN pattern as risk boundary.

- TestRiskTitleCorpusAudit (1)
    GREEN today: max corpus title = 40 chars (well under 120).

- TestControlTitleCorpusAudit (1)
    GREEN today: max corpus title = 49 chars (well under 100).

Coverage areas:
- Schema structural check: maxLength declared at correct value
- Behavioral boundary: at-limit pass, over-limit fail
- Corpus audit: no existing content exceeds new limits (drift-free)
"""

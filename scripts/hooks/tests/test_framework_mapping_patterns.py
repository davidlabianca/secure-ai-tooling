#!/usr/bin/env python3
"""
Tests for risk-map/schemas/frameworks.schema.json definitions/framework-mapping-patterns.

Covers the per-framework mapping-ID regex patterns per ADR-022 D5b. These
patterns are referenced from risks.schema.json and controls.schema.json to
validate canonical-form mapping IDs (e.g., AML.T0020 for MITRE ATLAS,
GOVERN-1.1 for NIST AI RMF) at the schema layer.

Coverage:
- The block exists at definitions/framework-mapping-patterns.
- It declares all 6 framework keys (mitre-atlas, nist-ai-rmf, stride,
  owasp-top10-llm, iso-22989, eu-ai-act).
- Each canonical-form framework's regex matches >=3 representative valid
  examples and rejects >=3 malformed inputs (per ADR-022 D5b commitments).
- ISO 22989 entry is bare `string` (no canonical form) per ADR-022 D5b.
- The block uses `additionalProperties: false` (closed schema).
- The framework keys align with the `framework.id` enum in
  frameworks.schema.json (drift-detection between the two surfaces).

Authoritative source for the patterns is ADR-022 D5b. This is a different
surface from `external-references.schema.json` (tested separately in
test_external_references_schema.py) — the framework-mapping-patterns block
uses the canonical-uppercase form (e.g., `AML.T0020`), where
external-references uses lowercase-kebab (`aml-t0020`).
"""

import json
import re
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Module-level constants — patterns and examples per ADR-022 D5b
# ============================================================================

# Six framework keys per ADR-022 D5b. Must match the existing
# framework.id enum in frameworks.schema.json.
EXPECTED_FRAMEWORK_KEYS = {
    "mitre-atlas",
    "nist-ai-rmf",
    "stride",
    "owasp-top10-llm",
    "iso-22989",
    "eu-ai-act",
}

# Frameworks with canonical-form regexes per ADR-022 D5b.
# ISO 22989 is the deliberate exception (bare string, see TestIso22989Entry).
CANONICAL_FRAMEWORKS = EXPECTED_FRAMEWORK_KEYS - {"iso-22989"}

# Pattern + valid/invalid examples per ADR-022 D5b.
# These are the source-of-truth patterns for the framework-mapping-patterns
# block; the SWE agent's schema must commit to these exact strings.
FRAMEWORK_PATTERN_TABLE: dict[str, dict] = {
    "mitre-atlas": {
        # Technique + mitigation union per ADR-022 D5b.
        "pattern": r"^AML\.(T|M)\d{4}(\.\d{3})?$",
        "valid": ["AML.T0020", "AML.T0020.001", "AML.M0011", "AML.M0001"],
        # lowercase (belongs in external-references surface); missing dot;
        # short technique ID; non-T/M letter; whitespace separator.
        "invalid": ["aml-t0020", "AML.T20", "AML.X0020", "AML T0020", "AML.T20020"],
    },
    "nist-ai-rmf": {
        # Function-prefix subcategories per ADR-022 D5b.
        "pattern": r"^(GOVERN|MAP|MEASURE|MANAGE)-\d+(\.\d+)*$",
        "valid": ["GOVERN-1", "MAP-1.1", "MEASURE-2.1.1", "MANAGE-4"],
        # lowercase function; underscore delimiter; wrong function name;
        # missing dash; trailing dot.
        "invalid": ["govern-1", "GOVERN_1", "GOVERNANCE-1", "GOVERN1", "GOVERN-1."],
    },
    "stride": {
        # PascalCase enum-as-pattern per ADR-022 D5b.
        # NOTE: The issue #240 body suggests lowercase-kebab values; ADR-022
        # D5b is the source of truth for this surface and uses PascalCase
        # without separators. Tests track ADR-022 D5b.
        "pattern": (
            r"^(Spoofing|Tampering|Repudiation|InformationDisclosure|"
            r"DenialOfService|ElevationOfPrivilege)$"
        ),
        "valid": [
            "Spoofing",
            "Tampering",
            "Repudiation",
            "InformationDisclosure",
            "DenialOfService",
            "ElevationOfPrivilege",
        ],
        # lowercase, abbreviated, hyphenated forms, unknown category.
        "invalid": [
            "spoofing",
            "dos",
            "info-disclosure",
            "ElevationPrivilege",
            "InfoDisclosure",
        ],
    },
    "owasp-top10-llm": {
        # Versioned per ADR-022 D5b.
        "pattern": r"^LLM\d{2}:\d{4}$",
        "valid": ["LLM01:2025", "LLM10:2025", "LLM05:2024"],
        # lowercase prefix; one digit only; dash instead of colon; missing
        # version year.
        "invalid": ["llm01:2025", "LLM1:2025", "LLM01-2025", "LLM01:25", "LLM01"],
    },
    "eu-ai-act": {
        # Article-style references per ADR-022 D5b.
        "pattern": r"^Article\s\d+(\(\d+\))?$",
        "valid": ["Article 5", "Article 5(1)", "Article 50", "Article 6(2)"],
        # lowercase; abbreviated; period subsection notation; missing space.
        "invalid": ["article 5", "Art 5", "Article 5.1", "Article5", "Article 5("],
    },
}


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def frameworks_schema(frameworks_schema_path: Path) -> dict:
    """Parsed frameworks.schema.json contents."""
    if not frameworks_schema_path.is_file():
        pytest.fail(
            f"frameworks.schema.json not found at {frameworks_schema_path}; "
            "this is a baseline file that should already exist"
        )
    with open(frameworks_schema_path) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def framework_mapping_patterns(frameworks_schema: dict) -> dict:
    """
    The definitions/framework-mapping-patterns block.

    Fails with a clear message if the block is absent — ADR-022 D5b mandates
    this block as the canonical home for per-framework mapping-ID regex
    patterns referenced from risks/controls schemas.
    """
    defs = frameworks_schema.get("definitions", {})
    if "framework-mapping-patterns" not in defs:
        pytest.fail(
            "definitions/framework-mapping-patterns missing from frameworks.schema.json (required by ADR-022 D5b)."
        )
    return defs["framework-mapping-patterns"]


# ============================================================================
# Block presence and structural shape
# ============================================================================


class TestBlockPresence:
    """The `definitions/framework-mapping-patterns` block must exist."""

    def test_definitions_block_exists(self, frameworks_schema: dict):
        """
        Test that frameworks.schema.json has a definitions block.

        Given: frameworks.schema.json
        When: It is parsed
        Then: It declares a 'definitions' object
        """
        assert "definitions" in frameworks_schema, "frameworks.schema.json must declare a 'definitions' block"

    def test_framework_mapping_patterns_definition_present(self, frameworks_schema: dict):
        """
        Test that the framework-mapping-patterns definition is present.

        Given: The definitions block of frameworks.schema.json
        When: 'framework-mapping-patterns' key is checked
        Then: It exists (per ADR-022 D5b)
        """
        defs = frameworks_schema["definitions"]
        assert "framework-mapping-patterns" in defs, (
            "definitions/framework-mapping-patterns must be added per ADR-022 D5b"
        )


class TestBlockStructure:
    """The block must be a closed object with one entry per framework."""

    def test_block_is_object_type(self, framework_mapping_patterns: dict):
        """
        Test that the block declares type: object.

        Given: The framework-mapping-patterns block
        When: Its 'type' is examined
        Then: It is 'object'
        """
        assert framework_mapping_patterns.get("type") == "object", (
            "framework-mapping-patterns must be a JSON Schema object"
        )

    def test_block_uses_additional_properties_false(self, framework_mapping_patterns: dict):
        """
        Test that the block is a closed schema.

        Given: The framework-mapping-patterns block
        When: 'additionalProperties' is examined
        Then: It is False (per ADR-022 D5b code sample)
        """
        assert framework_mapping_patterns.get("additionalProperties") is False, (
            "framework-mapping-patterns must set additionalProperties: false (closed schema per ADR-022 D5b)"
        )

    def test_block_has_six_framework_keys(self, framework_mapping_patterns: dict):
        """
        Test that all 6 framework keys are present.

        Given: The framework-mapping-patterns block
        When: Its 'properties' keys are examined
        Then: They equal the 6-framework set from ADR-022 D5b exactly
        """
        properties = framework_mapping_patterns.get("properties", {})
        actual_keys = set(properties.keys())
        assert actual_keys == EXPECTED_FRAMEWORK_KEYS, (
            f"framework-mapping-patterns properties must equal {EXPECTED_FRAMEWORK_KEYS}; "
            f"missing={EXPECTED_FRAMEWORK_KEYS - actual_keys}, "
            f"extra={actual_keys - EXPECTED_FRAMEWORK_KEYS}"
        )

    def test_keys_align_with_framework_id_enum(self, frameworks_schema: dict):
        """
        Test that the block's keys align with framework.id's enum.

        Given: The framework-mapping-patterns block keys
        When: They are compared against frameworks.schema.json
              definitions/framework/properties/id/enum
        Then: They are the same set (drift detection between surfaces)
        """
        framework_id_enum = set(frameworks_schema["definitions"]["framework"]["properties"]["id"]["enum"])
        defs = frameworks_schema["definitions"]
        if "framework-mapping-patterns" not in defs:
            pytest.fail("framework-mapping-patterns block not yet added")
        pattern_keys = set(defs["framework-mapping-patterns"]["properties"].keys())
        assert pattern_keys == framework_id_enum, (
            "Pattern keys must equal framework.id enum to prevent drift; "
            f"diff: pattern_keys-id_enum={pattern_keys - framework_id_enum}, "
            f"id_enum-pattern_keys={framework_id_enum - pattern_keys}"
        )


# ============================================================================
# Per-framework regex commitments (ADR-022 D5b)
# ============================================================================


class TestPerFrameworkPatternCommitments:
    """
    Each canonical-form framework declares the exact ADR-022 D5b pattern.

    Test-data sanity is also checked: each framework has >=3 valid + >=3
    invalid examples per the issue #240 acceptance criterion.
    """

    @pytest.mark.parametrize("framework_key", sorted(CANONICAL_FRAMEWORKS))
    def test_framework_entry_is_string_with_pattern(self, framework_mapping_patterns: dict, framework_key: str):
        """
        Test that each canonical framework entry is a string-with-pattern shape.

        Given: A canonical framework key
        When: Its sub-schema is examined
        Then: It declares type:string and a 'pattern' field
        """
        entry = framework_mapping_patterns["properties"].get(framework_key)
        assert entry is not None, f"{framework_key!r} entry missing"
        assert entry.get("type") == "string", f"{framework_key!r} entry must be type:string per ADR-022 D5b"
        assert "pattern" in entry, f"{framework_key!r} entry must declare a regex pattern per ADR-022 D5b"

    @pytest.mark.parametrize("framework_key", sorted(CANONICAL_FRAMEWORKS))
    def test_framework_pattern_matches_adr022_d5b_exactly(
        self, framework_mapping_patterns: dict, framework_key: str
    ):
        """
        Test that each pattern equals the ADR-022 D5b commitment exactly.

        Given: A canonical framework key
        When: Its 'pattern' is read
        Then: It equals the string committed in ADR-022 D5b

        The pattern strings are load-bearing — drifting from D5b silently
        relaxes or tightens validation. The schema must commit to the
        exact strings.
        """
        entry = framework_mapping_patterns["properties"][framework_key]
        expected = FRAMEWORK_PATTERN_TABLE[framework_key]["pattern"]
        actual = entry["pattern"]
        assert actual == expected, (
            f"{framework_key!r} pattern drift from ADR-022 D5b:\n  expected: {expected!r}\n  actual:   {actual!r}"
        )

    @pytest.mark.parametrize(
        ("framework_key", "valid_id"),
        [(fw, vid) for fw, info in FRAMEWORK_PATTERN_TABLE.items() for vid in info["valid"]],
    )
    def test_pattern_accepts_valid_example(
        self,
        framework_mapping_patterns: dict,
        framework_key: str,
        valid_id: str,
    ):
        """
        Test that each canonical pattern accepts representative valid examples.

        Given: A canonical framework's pattern
        When: A representative valid id is tested against it
        Then: re.fullmatch / Draft-07 validation succeeds

        Behavior is checked by validating against a one-off Draft-07 schema
        wrapping the per-framework string pattern; this exercises the actual
        schema, not just the regex string in isolation.
        """
        entry = framework_mapping_patterns["properties"][framework_key]
        validator = Draft7Validator(entry)
        errors = list(validator.iter_errors(valid_id))
        assert not errors, (
            f"{framework_key!r} pattern must accept {valid_id!r}; got: {[e.message for e in errors]}"
        )

    @pytest.mark.parametrize(
        ("framework_key", "invalid_id"),
        [(fw, iid) for fw, info in FRAMEWORK_PATTERN_TABLE.items() for iid in info["invalid"]],
    )
    def test_pattern_rejects_invalid_example(
        self,
        framework_mapping_patterns: dict,
        framework_key: str,
        invalid_id: str,
    ):
        """
        Test that each canonical pattern rejects malformed examples.

        Given: A canonical framework's pattern
        When: A malformed id is tested against it
        Then: ValidationError is raised
        """
        entry = framework_mapping_patterns["properties"][framework_key]
        validator = Draft7Validator(entry)
        errors = list(validator.iter_errors(invalid_id))
        assert errors, f"{framework_key!r} pattern must reject {invalid_id!r}; the malformed id slipped through"

    @pytest.mark.parametrize("framework_key", sorted(FRAMEWORK_PATTERN_TABLE.keys()))
    def test_test_data_has_three_or_more_valid_examples(self, framework_key: str):
        """
        Test that the test-data table has >=3 valid examples per framework
        (issue #240 acceptance criterion).
        """
        assert len(FRAMEWORK_PATTERN_TABLE[framework_key]["valid"]) >= 3

    @pytest.mark.parametrize("framework_key", sorted(FRAMEWORK_PATTERN_TABLE.keys()))
    def test_test_data_has_three_or_more_invalid_examples(self, framework_key: str):
        """
        Test that the test-data table has >=3 invalid examples per framework
        (issue #240 acceptance criterion).
        """
        assert len(FRAMEWORK_PATTERN_TABLE[framework_key]["invalid"]) >= 3


# ============================================================================
# ISO 22989 — explicit bare-string exception
# ============================================================================


class TestIso22989Entry:
    """
    ISO 22989 is the deliberate exception per ADR-022 D5b: bare `string`
    with no canonical-form regex, because persona ISO 22989 mappings are
    role descriptors (e.g., `"AI Partner (data supplier)"`), not canonical
    IDs. This is documented behavior, not an oversight.
    """

    def test_iso22989_entry_present(self, framework_mapping_patterns: dict):
        """
        Test that the iso-22989 entry exists.

        Given: The framework-mapping-patterns block
        When: 'iso-22989' is looked up
        Then: It is present
        """
        assert "iso-22989" in framework_mapping_patterns.get("properties", {}), (
            "iso-22989 entry must be present (deliberate bare-string exception)"
        )

    def test_iso22989_is_bare_string(self, framework_mapping_patterns: dict):
        """
        Test that iso-22989 is a bare string with no pattern.

        Given: The iso-22989 entry
        When: Its keys are examined
        Then: It declares type:string and does NOT declare a 'pattern'
              (per ADR-022 D5b: explicit no-canonical-form exception)
        """
        entry = framework_mapping_patterns["properties"]["iso-22989"]
        assert entry.get("type") == "string", "iso-22989 must be type:string"
        assert "pattern" not in entry, (
            "iso-22989 must NOT declare a pattern (ADR-022 D5b: explicit "
            "exception; persona role descriptors are not canonical IDs)"
        )

    @pytest.mark.parametrize(
        "valid_value",
        [
            "AI Partner (data supplier)",
            "AI Producer",
            "AI Subject",
            "Some arbitrary descriptor",
        ],
    )
    def test_iso22989_accepts_arbitrary_strings(self, framework_mapping_patterns: dict, valid_value: str):
        """
        Test that iso-22989 accepts arbitrary string values.

        Given: The iso-22989 entry (bare string)
        When: An arbitrary descriptor string is validated
        Then: Validation passes (no pattern constraint applies)
        """
        entry = framework_mapping_patterns["properties"]["iso-22989"]
        validator = Draft7Validator(entry)
        errors = list(validator.iter_errors(valid_value))
        assert not errors, (
            f"iso-22989 must accept {valid_value!r} (no pattern constraint); got: {[e.message for e in errors]}"
        )


# ============================================================================
# Schema meta-validity — the patterns must compile under Draft-07
# ============================================================================


class TestSchemaMetaValidity:
    """The block must itself be a valid JSON Schema Draft-07 fragment."""

    def test_block_passes_draft07_metaschema(self, framework_mapping_patterns: dict):
        """
        Test that the block is a valid Draft-07 schema fragment.

        Given: The framework-mapping-patterns block
        When: It is checked against the Draft-07 meta-schema
        Then: No SchemaError is raised
        """
        try:
            Draft7Validator.check_schema(framework_mapping_patterns)
        except SchemaError as exc:
            pytest.fail(f"framework-mapping-patterns is not valid Draft-07: {exc.message}")

    @pytest.mark.parametrize("framework_key", sorted(CANONICAL_FRAMEWORKS))
    def test_pattern_compiles_as_python_regex(self, framework_mapping_patterns: dict, framework_key: str):
        """
        Test that each pattern compiles as a Python regex.

        Given: A canonical framework's pattern string
        When: re.compile() is called on it
        Then: No re.error is raised

        Catches stray escapes / invalid groups before they hit the validator.
        """
        pattern = framework_mapping_patterns["properties"][framework_key]["pattern"]
        try:
            re.compile(pattern)
        except re.error as exc:
            pytest.fail(f"{framework_key!r} pattern does not compile: {exc} ({pattern!r})")


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Test classes: 6

- TestBlockPresence (2)              — definitions block exists,
                                        framework-mapping-patterns present
- TestBlockStructure (4)             — type=object, additionalProperties=false,
                                        6 keys, drift-vs-id-enum
- TestPerFrameworkPatternCommitments — parametrized: shape, exact-string match,
                                        valid/invalid examples, test-data sanity
                                        (per 5 canonical frameworks)
- TestIso22989Entry                  — present, bare string, accepts arbitrary
                                        values
- TestSchemaMetaValidity             — block passes Draft-07; each pattern
                                        compiles as Python regex

Coverage areas:
- Block existence and structural integrity
- 6-framework key set match against framework.id enum (drift detection)
- Per-framework pattern commitment to ADR-022 D5b strings
- Per-framework regex behavior (>=3 valid + >=3 invalid examples each)
- ISO 22989 bare-string exception per ADR-022 D5b
- JSON Schema Draft-07 meta-validity and Python regex compile

"""

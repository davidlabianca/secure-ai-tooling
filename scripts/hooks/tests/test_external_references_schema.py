#!/usr/bin/env python3
"""
Tests for risk-map/schemas/external-references.schema.json.

Covers the shared external-references schema per ADR-016 D3 — the canonical
shape for outbound citations, $ref'd from risks/controls/components/personas
schemas as their externalReferences field.

Coverage:
- File presence and JSON Schema Draft-07 self-validity.
- `definitions/externalReferences` array shape (rejects empty array; accepts >= 1).
- Per-item required fields (`type`, `id`, `title`, `url`).
- `type` enum covers all 10 values from ADR-016 D3 (incl. `editorial`).
- `url` rejects non-`https://` schemes via anchored regex.
- Per-type `id` regex patterns for canonical-form types (`cwe`, `cve`, `atlas`,
  `attack`) — at least 3 valid + 3 invalid examples each.
- Non-canonical types (`paper`, `news`, `editorial`, `other`, `advisory`, `spec`)
  accept author-chosen kebab-case identifiers.

Authoritative source for the `id` patterns is ADR-016 D3, which fixes the
lowercase-kebab convention for the `external-references.id` field. Note that
ADR-022 D5b's regex patterns target a different surface
(`frameworks.schema.json#/definitions/framework-mapping-patterns`) and use the
canonical-uppercase form (e.g., `AML.T0020`); see
`test_framework_mapping_patterns.py` for that surface.
"""

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for

# Allow imports of repo helpers if needed by future fixtures
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Module-level constants
# ============================================================================

SCHEMA_FILENAME = "external-references.schema.json"

# All 10 type values from ADR-016 D3.
EXPECTED_TYPE_ENUM = {
    "cwe",
    "cve",
    "atlas",
    "attack",
    "advisory",
    "paper",
    "news",
    "spec",
    "editorial",
    "other",
}

# Per-type valid/invalid id examples for canonical-form types.
# Patterns are the lowercase-kebab forms committed by ADR-016 D3.
CANONICAL_ID_EXAMPLES: dict[str, dict[str, list[str]]] = {
    "cwe": {
        "valid": ["cwe-89", "cwe-1", "cwe-12345"],
        # Wrong case, missing prefix, wrong delimiter, embedded spaces.
        "invalid": ["CWE-89", "cwe89", "cwe_89", "cwe-", "cwe-89a"],
    },
    "cve": {
        "valid": ["cve-2024-0001", "cve-2025-12345", "cve-1999-0001"],
        # Wrong case, missing year, wrong separator, missing prefix.
        "invalid": ["CVE-2024-0001", "cve-24-0001", "cve_2024_0001", "2024-0001", "cve-2024"],
    },
    "atlas": {
        # ATLAS lowercase-kebab technique form per ADR-016 D3 / issue #240 body.
        "valid": ["aml-t0020", "aml-t0020.001", "aml-t1234"],
        # Uppercase canonical (belongs in framework-mapping-patterns surface),
        # missing prefix, wrong delimiter, malformed sub-technique.
        "invalid": ["AML.T0020", "aml-t20", "aml_t0020", "aml-T0020", "aml-t0020.1"],
    },
    "attack": {
        # ATT&CK lowercase-kebab technique form, analogous to atlas.
        # ADR-016 D3 commits to "lowercase-kebab" convention; issue body says
        # "analogous to ATLAS"; this pattern follows that convention.
        "valid": ["attack-t1190", "attack-t1190.001", "attack-t1059"],
        "invalid": ["T1190", "attack-T1190", "attack_t1190", "attack-1190", "attack-t190"],
    },
}

# Non-canonical types — bare kebab-case strings expected to be permitted.
NON_CANONICAL_TYPE_EXAMPLES: dict[str, list[str]] = {
    "paper": ["zhou-2023-poisoning", "smith-et-al-2024-rag"],
    "news": ["wired-2024-ai-leak", "vendor-announcement-2025-q1"],
    "editorial": ["vendor-blog-rag-eval", "maintainer-note-on-llm-eval"],
    "other": ["misc-reference-1", "internal-doc-archive-42"],
    "advisory": ["vendor-advisory-2024-01", "ghsa-xxxx-yyyy-zzzz"],
    "spec": ["rfc-2119", "iso-iec-27001-2022"],
}


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def external_references_schema_path(risk_map_schemas_dir: Path) -> Path:
    """Absolute path to external-references.schema.json (may not exist yet)."""
    return risk_map_schemas_dir / SCHEMA_FILENAME


@pytest.fixture(scope="module")
def external_references_schema(external_references_schema_path: Path) -> dict:
    """
    Parsed external-references.schema.json contents.

    Skips with a clear message if the file is absent, distinguishing
    schema-absent failure from a fixture error.
    """
    if not external_references_schema_path.is_file():
        pytest.fail(
            f"Expected schema not found at {external_references_schema_path}. "
            "Tests assume the schema is authored per ADR-016 D3."
        )
    with open(external_references_schema_path) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def external_references_item_validator(external_references_schema: dict) -> Draft7Validator:
    """
    Draft-07 validator over the per-item object schema.

    Resolves to `definitions/externalReferences` then drills into the array's
    `items` so individual reference objects can be validated in isolation.
    The fixture asserts the path exists rather than guessing structure.
    """
    defs = external_references_schema.get("definitions", {})
    assert "externalReferences" in defs, "Schema must define 'externalReferences' under definitions per ADR-016 D3"
    array_schema = defs["externalReferences"]
    assert array_schema.get("type") == "array", "externalReferences must be an array shape per ADR-016 D3"
    item_schema = array_schema.get("items")
    assert isinstance(item_schema, dict), "externalReferences.items must be an object schema (per-item shape)"
    # Validator over the item schema in isolation; if the SWE agent uses
    # internal $refs the validator will need a registry — extend here when
    # the schema is authored if needed.
    return Draft7Validator(item_schema)


def _make_item(type_value: str, id_value: str) -> dict:
    """Construct a minimal valid-shape externalReferences entry for testing."""
    return {
        "type": type_value,
        "id": id_value,
        "title": "Test Reference",
        "url": "https://example.com/ref",
    }


# ============================================================================
# Schema file presence and JSON Schema meta-validity
# ============================================================================


class TestSchemaFilePresence:
    """The schema file must exist at the canonical path."""

    def test_schema_file_exists(self, external_references_schema_path: Path):
        """
        Test that external-references.schema.json exists.

        Given: ADR-016 D3 mandates a shared external-references schema
        When: The schemas/ directory is inspected
        Then: external-references.schema.json is present
        """
        assert external_references_schema_path.is_file(), (
            f"{SCHEMA_FILENAME} must exist at {external_references_schema_path}"
        )

    def test_schema_is_valid_json(self, external_references_schema_path: Path):
        """
        Test that the file parses as valid JSON.

        Given: The schema file exists
        When: It is read and parsed as JSON
        Then: No JSONDecodeError is raised
        """
        if not external_references_schema_path.is_file():
            pytest.fail(f"{SCHEMA_FILENAME} not found")
        with open(external_references_schema_path) as fh:
            json.load(fh)  # Raises if invalid


class TestSchemaMetaValidity:
    """The schema must itself be a valid JSON Schema Draft-07 document."""

    def test_schema_declares_draft07(self, external_references_schema: dict):
        """
        Test that the schema declares the Draft-07 meta-schema.

        Given: A loaded schema document
        When: The $schema field is examined
        Then: It points at the Draft-07 meta-schema URL
        """
        assert external_references_schema.get("$schema") == ("http://json-schema.org/draft-07/schema#"), (
            "Schema must declare Draft-07 ($schema field)"
        )

    def test_schema_passes_draft07_metaschema(self, external_references_schema: dict):
        """
        Test that the schema validates against the Draft-07 meta-schema.

        Given: A loaded schema document
        When: It is checked against the Draft-07 meta-schema
        Then: No SchemaError is raised
        """
        # check_schema raises SchemaError if the schema is itself invalid.
        try:
            Draft7Validator.check_schema(external_references_schema)
        except SchemaError as exc:
            pytest.fail(f"Schema is not valid Draft-07: {exc.message}")

    def test_validator_for_schema_resolves_to_draft07(self, external_references_schema: dict):
        """
        Test that the appropriate validator class is Draft-07.

        Given: A loaded schema document
        When: jsonschema selects a validator class via validator_for()
        Then: The resolved class is Draft7Validator
        """
        cls = validator_for(external_references_schema)
        assert cls is Draft7Validator, f"Expected Draft7Validator, got {cls.__name__}"


# ============================================================================
# definitions/externalReferences shape
# ============================================================================


class TestExternalReferencesDefinition:
    """The schema must define the externalReferences array shape per ADR-016 D3."""

    def test_definition_exists(self, external_references_schema: dict):
        """
        Test that definitions/externalReferences exists.

        Given: A loaded schema
        When: The definitions block is inspected
        Then: An `externalReferences` definition is present
        """
        assert "definitions" in external_references_schema, "Schema must declare a 'definitions' block"
        assert "externalReferences" in external_references_schema["definitions"], (
            "definitions/externalReferences must exist (ADR-016 D3 single-source-of-truth)"
        )

    def test_definition_is_array_shape(self, external_references_schema: dict):
        """
        Test that externalReferences is an array.

        Given: definitions/externalReferences is present
        When: Its `type` is examined
        Then: It is `array`
        """
        defn = external_references_schema["definitions"]["externalReferences"]
        assert defn.get("type") == "array", "externalReferences must be an array shape (ADR-016 D3)"

    def test_array_has_min_items_one(self, external_references_schema: dict):
        """
        Test that empty arrays are rejected.

        Given: The externalReferences array shape
        When: Its `minItems` is examined
        Then: It is set to 1 (per ADR-016 D3: empty arrays are rejected;
              authors should omit the field instead)
        """
        defn = external_references_schema["definitions"]["externalReferences"]
        assert defn.get("minItems") == 1, (
            "externalReferences array must reject empty arrays (minItems: 1) per ADR-016 D3 'use omission instead'"
        )

    def test_empty_array_fails_validation(self, external_references_schema: dict):
        """
        Test that an empty array fails validation in practice.

        Given: A Draft-07 validator over the array schema
        When: An empty list is validated
        Then: ValidationError is raised
        """
        defn = external_references_schema["definitions"]["externalReferences"]
        validator = Draft7Validator(defn)
        errors = list(validator.iter_errors([]))
        assert errors, "Empty array must be rejected by the schema"

    def test_single_valid_item_array_passes(self, external_references_schema: dict):
        """
        Test that a one-element array with a valid item passes.

        Given: The externalReferences array schema
        When: An array with one valid item is validated
        Then: No errors are raised
        """
        defn = external_references_schema["definitions"]["externalReferences"]
        validator = Draft7Validator(defn)
        item = _make_item("paper", "zhou-2023-poisoning")
        errors = list(validator.iter_errors([item]))
        assert not errors, f"Single valid item array must pass; got errors: {[e.message for e in errors]}"


# ============================================================================
# Per-item required fields
# ============================================================================


class TestItemRequiredFields:
    """Each entry must require type, id, title, url per ADR-016 D3."""

    @pytest.mark.parametrize("required_field", ["type", "id", "title", "url"])
    def test_required_field_declared(self, external_references_schema: dict, required_field: str):
        """
        Test that the per-item schema declares each required field.

        Given: definitions/externalReferences items schema
        When: Its `required` array is examined
        Then: It includes the named field
        """
        defn = external_references_schema["definitions"]["externalReferences"]
        item_schema = defn["items"]
        required = item_schema.get("required", [])
        assert required_field in required, (
            f"Per-item schema must declare '{required_field}' as required (ADR-016 D3)"
        )

    @pytest.mark.parametrize("missing_field", ["type", "id", "title", "url"])
    def test_missing_required_field_rejected(
        self, external_references_item_validator: Draft7Validator, missing_field: str
    ):
        """
        Test that an item missing a required field fails validation.

        Given: A complete valid item shape
        When: The named required field is removed
        Then: ValidationError is raised by the item validator
        """
        item = _make_item("paper", "test-paper")
        del item[missing_field]
        errors = list(external_references_item_validator.iter_errors(item))
        assert errors, f"Item missing '{missing_field}' must be rejected"


# ============================================================================
# type enum coverage
# ============================================================================


class TestTypeEnum:
    """The `type` enum must cover all 10 values from ADR-016 D3."""

    def test_type_field_has_enum(self, external_references_schema: dict):
        """
        Test that the type field is an enum.

        Given: The per-item schema
        When: The `type` property is examined
        Then: It declares an enum constraint
        """
        item = external_references_schema["definitions"]["externalReferences"]["items"]
        type_schema = item["properties"]["type"]
        assert "enum" in type_schema, "type must be enum-constrained per ADR-016 D3"

    def test_type_enum_covers_all_ten_values(self, external_references_schema: dict):
        """
        Test that all 10 ADR-016 D3 type values are present.

        Given: The type enum
        When: Its values are examined
        Then: It covers cwe, cve, atlas, attack, advisory, paper, news,
              spec, editorial, other (set equality, not just subset)
        """
        item = external_references_schema["definitions"]["externalReferences"]["items"]
        actual = set(item["properties"]["type"]["enum"])
        assert actual == EXPECTED_TYPE_ENUM, (
            f"type enum must equal ADR-016 D3 set; "
            f"missing={EXPECTED_TYPE_ENUM - actual}, extra={actual - EXPECTED_TYPE_ENUM}"
        )

    def test_unknown_type_rejected(self, external_references_item_validator: Draft7Validator):
        """
        Test that an unknown type value fails validation.

        Given: An item with type='regulation' (not in the enum)
        When: It is validated
        Then: ValidationError is raised
        """
        item = _make_item("regulation", "regulation-1")
        errors = list(external_references_item_validator.iter_errors(item))
        assert errors, "Unknown type values (e.g., 'regulation') must be rejected"

    @pytest.mark.parametrize("type_value", sorted(EXPECTED_TYPE_ENUM))
    def test_each_known_type_accepted(
        self,
        external_references_item_validator: Draft7Validator,
        type_value: str,
    ):
        """
        Test that each known type value is accepted (with a permissive id).

        Given: An item with one of the 10 ADR-016 D3 type values
        When: It is validated using a type-appropriate id format
        Then: Validation passes (no errors)

        Note: For canonical-form types we use a known-valid example;
        for non-canonical types any kebab-case string suffices.
        """
        if type_value in CANONICAL_ID_EXAMPLES:
            id_value = CANONICAL_ID_EXAMPLES[type_value]["valid"][0]
        else:
            # Non-canonical types accept any kebab-case string.
            id_value = "test-reference-id"
        item = _make_item(type_value, id_value)
        errors = list(external_references_item_validator.iter_errors(item))
        assert not errors, (
            f"Known type '{type_value}' with valid id '{id_value}' must pass; got: {[e.message for e in errors]}"
        )


# ============================================================================
# url scheme constraint
# ============================================================================


class TestUrlSchemeConstraint:
    """The `url` field must require https:// per ADR-016 D3."""

    def test_url_pattern_declared(self, external_references_schema: dict):
        """
        Test that the url field declares a pattern.

        Given: The per-item schema
        When: The `url` property is examined
        Then: It declares a pattern constraint anchored to https://
        """
        item = external_references_schema["definitions"]["externalReferences"]["items"]
        url_schema = item["properties"]["url"]
        assert "pattern" in url_schema, "url must declare a pattern constraint (https:// only per ADR-016 D3)"
        # The pattern must anchor to ^https:// — not merely contain https.
        assert url_schema["pattern"].startswith("^https://"), (
            f"url pattern must anchor at start with ^https://, got {url_schema['pattern']!r}"
        )

    @pytest.mark.parametrize(
        "valid_url",
        [
            "https://example.com",
            "https://cwe.mitre.org/data/definitions/89.html",
            "https://arxiv.org/abs/2305.00944",
        ],
    )
    def test_https_urls_accepted(self, external_references_item_validator: Draft7Validator, valid_url: str):
        """
        Test that https:// URLs are accepted.

        Given: An item with an https:// url
        When: It is validated
        Then: No errors are raised
        """
        item = _make_item("paper", "test-paper")
        item["url"] = valid_url
        errors = list(external_references_item_validator.iter_errors(item))
        assert not errors, f"https URL must be accepted; got: {[e.message for e in errors]}"

    @pytest.mark.parametrize(
        "invalid_url",
        [
            "http://example.com",  # plain http
            "ftp://example.com/ref",  # wrong scheme
            "//example.com/ref",  # protocol-relative
            "example.com/ref",  # bare host
            "javascript:alert(1)",  # XSS surface
            "  https://example.com",  # leading whitespace
        ],
    )
    def test_non_https_urls_rejected(self, external_references_item_validator: Draft7Validator, invalid_url: str):
        """
        Test that non-https URLs are rejected.

        Given: An item with a non-https url
        When: It is validated
        Then: ValidationError is raised (the url pattern blocks it)
        """
        item = _make_item("paper", "test-paper")
        item["url"] = invalid_url
        errors = list(external_references_item_validator.iter_errors(item))
        assert errors, f"Non-https URL {invalid_url!r} must be rejected"


# ============================================================================
# Per-type id regex patterns (canonical-form types)
# ============================================================================


class TestCanonicalIdPatterns:
    """
    Per-type id regex patterns enforce the lowercase-kebab canonical form
    (ADR-016 D3) for cwe, cve, atlas, attack.

    Each canonical type is checked with >=3 valid + >=3 invalid examples
    per the issue #240 acceptance criteria.
    """

    @pytest.mark.parametrize(
        ("type_value", "valid_id"),
        [(t, vid) for t, examples in CANONICAL_ID_EXAMPLES.items() for vid in examples["valid"]],
    )
    def test_canonical_valid_id_accepted(
        self,
        external_references_item_validator: Draft7Validator,
        type_value: str,
        valid_id: str,
    ):
        """
        Test that canonical valid id forms are accepted.

        Given: An item with type=<canonical> and a valid lowercase-kebab id
        When: It is validated
        Then: No errors are raised

        Note on conditional validation: The schema must apply the per-type
        id regex only when `type == <type_value>`. Implementations may use
        `oneOf` / `anyOf` / `if-then` / per-type subschemas. This test
        treats the wiring as opaque and just asserts the resulting behavior.
        """
        item = _make_item(type_value, valid_id)
        errors = list(external_references_item_validator.iter_errors(item))
        assert not errors, (
            f"type={type_value!r} id={valid_id!r} must be accepted; got: {[e.message for e in errors]}"
        )

    @pytest.mark.parametrize(
        ("type_value", "invalid_id"),
        [(t, iid) for t, examples in CANONICAL_ID_EXAMPLES.items() for iid in examples["invalid"]],
    )
    def test_canonical_invalid_id_rejected(
        self,
        external_references_item_validator: Draft7Validator,
        type_value: str,
        invalid_id: str,
    ):
        """
        Test that malformed canonical ids are rejected.

        Given: An item with type=<canonical> and a malformed id (wrong case,
               wrong delimiter, missing prefix, etc.)
        When: It is validated
        Then: ValidationError is raised
        """
        item = _make_item(type_value, invalid_id)
        errors = list(external_references_item_validator.iter_errors(item))
        assert errors, f"type={type_value!r} with malformed id={invalid_id!r} must be rejected"

    @pytest.mark.parametrize("type_value", sorted(CANONICAL_ID_EXAMPLES.keys()))
    def test_canonical_type_has_at_least_three_valid_examples(self, type_value: str):
        """
        Test that each canonical type has >=3 valid examples (test-data sanity).

        Given: The CANONICAL_ID_EXAMPLES table
        When: A canonical type's valid list is examined
        Then: It has at least 3 entries (issue #240 acceptance criterion)
        """
        assert len(CANONICAL_ID_EXAMPLES[type_value]["valid"]) >= 3

    @pytest.mark.parametrize("type_value", sorted(CANONICAL_ID_EXAMPLES.keys()))
    def test_canonical_type_has_at_least_three_invalid_examples(self, type_value: str):
        """
        Test that each canonical type has >=3 invalid examples (test-data sanity).

        Given: The CANONICAL_ID_EXAMPLES table
        When: A canonical type's invalid list is examined
        Then: It has at least 3 entries (issue #240 acceptance criterion)
        """
        assert len(CANONICAL_ID_EXAMPLES[type_value]["invalid"]) >= 3


# ============================================================================
# Non-canonical types accept author-chosen kebab-case ids
# ============================================================================


class TestNonCanonicalIdShapes:
    """
    Non-canonical types (`paper`, `news`, `editorial`, `other`, `advisory`,
    `spec`) permit author-chosen kebab-case shorthand ids per ADR-016 D3.
    """

    @pytest.mark.parametrize(
        ("type_value", "id_value"),
        [(t, iid) for t, examples in NON_CANONICAL_TYPE_EXAMPLES.items() for iid in examples],
    )
    def test_non_canonical_id_accepted(
        self,
        external_references_item_validator: Draft7Validator,
        type_value: str,
        id_value: str,
    ):
        """
        Test that non-canonical types accept author-chosen kebab-case ids.

        Given: An item with a non-canonical type and a kebab-case id
        When: It is validated
        Then: No errors are raised

        Examples like `zhou-2023-poisoning` and `vendor-blog-rag-eval` are
        the literal examples ADR-016 D3 names.
        """
        item = _make_item(type_value, id_value)
        errors = list(external_references_item_validator.iter_errors(item))
        assert not errors, (
            f"Non-canonical type={type_value!r} id={id_value!r} must be accepted; "
            f"got: {[e.message for e in errors]}"
        )

    def test_empty_id_rejected_for_non_canonical(self, external_references_item_validator: Draft7Validator):
        """
        Test that an empty id is rejected even for non-canonical types.

        Given: An item with type=paper and id=""
        When: It is validated
        Then: ValidationError is raised (the id is required and non-empty)
        """
        item = _make_item("paper", "")
        errors = list(external_references_item_validator.iter_errors(item))
        assert errors, "Empty id must be rejected (id is required and non-empty)"


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Test classes: 8

- TestSchemaFilePresence (2)        — file exists, parses as JSON
- TestSchemaMetaValidity (3)        — Draft-07 declared, meta-valid, validator class
- TestExternalReferencesDefinition (5) — definition exists, array shape, minItems,
                                          empty rejected, single-item accepted
- TestItemRequiredFields            — parametrized: 4 declared + 4 reject-on-missing
- TestTypeEnum                      — has enum, set equality, unknown rejected,
                                       parametrized: each of 10 types accepted
- TestUrlSchemeConstraint           — pattern declared, parametrized: 3 https
                                       accepted + 6 non-https rejected
- TestCanonicalIdPatterns           — parametrized: valid and invalid examples
                                       per (cwe, cve, atlas, attack), plus
                                       test-data sanity assertions
- TestNonCanonicalIdShapes          — parametrized: kebab-case ids accepted for
                                       6 non-canonical types, empty id rejected

Coverage areas:
- File presence and JSON parse-ability
- JSON Schema Draft-07 self-validity
- Required-field enforcement
- Enum coverage (10 type values)
- URL scheme constraint (https-only, anchored)
- Per-type id regex patterns (4 canonical types: cwe, cve, atlas, attack)
- Non-canonical type id permissiveness (6 types)
"""

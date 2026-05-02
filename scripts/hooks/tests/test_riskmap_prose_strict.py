#!/usr/bin/env python3
"""
Tests for the prose-strict sibling definition in riskmap.schema.json.

Per ADRs 018/019/020/021 D4, riskmap.schema.json defines a constrained
sibling at definitions/utils/prose-strict alongside the existing
definitions/utils/text. prose-strict:
- Accepts the same array<string | array<string>> shape (one nesting level max).
- Adds minItems: 1 on the outer array (empty prose rejected).
- Adds minLength: 1 on string items at both depths (empty strings rejected).
- Keeps minItems: 1 on the inner string array.
- Does NOT replace definitions/utils/text (coexistence required).
- Is NOT yet referenced by any consumer schema; consumer migration is a
  follow-on tightening.

Coverage:
- definitions/utils/text is unchanged (coexistence).
- definitions/utils/prose-strict exists as a sibling.
- prose-strict outer array has minItems: 1.
- prose-strict string items at depth-1 have minLength: 1.
- prose-strict inner array has minItems: 1 and its string items have minLength: 1.
- Empty outer array rejected by prose-strict, accepted by text.
- Empty string rejected by prose-strict (both depth levels).
- Empty inner array rejected by prose-strict, accepted by text.
- Valid non-empty strings and arrays accepted by both.
- riskmap.schema.json passes Draft-07 meta-schema check.
"""

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Module-level constants
# ============================================================================

SCHEMA_FILE = "riskmap.schema.json"

# Valid prose values that both text and prose-strict must accept.
VALID_PROSE_VALUES: list = [
    ["A single string item"],
    ["First item", "Second item"],
    [["bullet one", "bullet two"]],  # inner array at depth 1
    ["Prose paragraph", ["item a", "item b"]],  # mixed
]

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def riskmap_schema(risk_map_schemas_dir: Path) -> dict:
    """Parsed riskmap.schema.json."""
    path = risk_map_schemas_dir / SCHEMA_FILE
    if not path.is_file():
        pytest.fail(f"Schema not found: {path}")
    with open(path) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def utils_definitions(riskmap_schema: dict) -> dict:
    """The definitions/utils block from riskmap.schema.json."""
    utils = riskmap_schema.get("definitions", {}).get("utils", {})
    assert utils, "definitions/utils must exist in riskmap.schema.json"
    return utils


@pytest.fixture(scope="module")
def text_schema(utils_definitions: dict) -> dict:
    """The existing definitions/utils/text sub-schema."""
    if "text" not in utils_definitions:
        pytest.fail("definitions/utils/text not found — it must not have been removed")
    return utils_definitions["text"]


@pytest.fixture(scope="module")
def prose_strict_schema(utils_definitions: dict) -> dict:
    """The definitions/utils/prose-strict sub-schema."""
    if "prose-strict" not in utils_definitions:
        pytest.fail("definitions/utils/prose-strict not found in riskmap.schema.json.")
    return utils_definitions["prose-strict"]


@pytest.fixture(scope="module")
def text_validator(text_schema: dict) -> Draft7Validator:
    """Draft-07 validator over definitions/utils/text."""
    return Draft7Validator(text_schema)


@pytest.fixture(scope="module")
def prose_strict_validator(prose_strict_schema: dict) -> Draft7Validator:
    """Draft-07 validator over definitions/utils/prose-strict."""
    return Draft7Validator(prose_strict_schema)


# ============================================================================
# Schema meta-validity
# ============================================================================


class TestSchemaMetaValidity:
    """riskmap.schema.json must be a valid Draft-07 document."""

    def test_riskmap_schema_passes_draft07_metaschema(self, riskmap_schema: dict):
        """
        Test that riskmap.schema.json is a valid Draft-07 schema.

        Given: riskmap.schema.json loaded
        When: Draft7Validator.check_schema() is called
        Then: No SchemaError is raised
        """
        try:
            Draft7Validator.check_schema(riskmap_schema)
        except SchemaError as exc:
            pytest.fail(f"{SCHEMA_FILE} is not valid Draft-07: {exc.message}")


# ============================================================================
# Coexistence — text must be unchanged
# ============================================================================


class TestTextDefinitionUnchanged:
    """
    definitions/utils/text must continue to exist with its original shape.
    prose-strict is added as a sibling and does NOT replace text.
    """

    def test_text_definition_exists(self, utils_definitions: dict):
        """
        Test that definitions/utils/text is still present.

        Given: definitions/utils in riskmap.schema.json
        When: 'text' is looked up
        Then: It is present (prose-strict must not replace it)
        """
        assert "text" in utils_definitions, (
            "definitions/utils/text must still exist — prose-strict is a sibling, not a replacement"
        )

    def test_text_is_array_type(self, text_schema: dict):
        """
        Test that text remains an array shape.

        Given: definitions/utils/text
        When: Its type is examined
        Then: It is 'array' (unchanged)
        """
        assert text_schema.get("type") == "array", "definitions/utils/text must remain type: array"

    def test_text_has_no_min_items(self, text_schema: dict):
        """
        Test that text does not have minItems on the outer array.

        Given: definitions/utils/text
        When: Its minItems is checked
        Then: It is absent (text accepts empty arrays; prose-strict does not)

        This confirms the two definitions diverge intentionally.
        """
        assert "minItems" not in text_schema, (
            "definitions/utils/text must NOT have minItems on the outer array "
            "(prose-strict is the constrained sibling; text must remain permissive)"
        )

    def test_text_accepts_empty_outer_array(self, text_validator: Draft7Validator):
        """
        Test that text accepts an empty outer array.

        Given: definitions/utils/text validator
        When: An empty list is validated
        Then: No errors are raised (text does not constrain outer minItems)
        """
        errors = list(text_validator.iter_errors([]))
        assert not errors, (
            "definitions/utils/text must accept empty outer array (prose-strict diverges here with minItems: 1)"
        )


# ============================================================================
# prose-strict definition presence and structural shape
# ============================================================================


class TestProseStrictPresence:
    """definitions/utils/prose-strict must exist as a sibling to text."""

    def test_prose_strict_definition_exists(self, utils_definitions: dict):
        """
        Test that definitions/utils/prose-strict is declared.

        Given: definitions/utils in riskmap.schema.json
        When: 'prose-strict' is looked up
        Then: It is present
        """
        assert "prose-strict" in utils_definitions, (
            "definitions/utils/prose-strict must be declared in riskmap.schema.json"
        )

    def test_prose_strict_is_array_type(self, prose_strict_schema: dict):
        """
        Test that prose-strict is an array type.

        Given: definitions/utils/prose-strict
        When: Its type is examined
        Then: It is 'array' (same outer shape as text)
        """
        assert prose_strict_schema.get("type") == "array", "definitions/utils/prose-strict must be type: array"

    def test_prose_strict_has_outer_min_items_one(self, prose_strict_schema: dict):
        """
        Test that prose-strict has minItems: 1 on the outer array.

        Given: definitions/utils/prose-strict
        When: Its minItems is examined
        Then: It is 1 (empty prose rejected per ADR-018/019/020/021 D4)
        """
        assert prose_strict_schema.get("minItems") == 1, (
            "definitions/utils/prose-strict must declare minItems: 1 on the outer array"
        )


# ============================================================================
# prose-strict — string item minLength constraints
# ============================================================================


class TestProseStrictStringConstraints:
    """prose-strict must enforce minLength: 1 on string items at both depths."""

    def test_depth1_string_items_have_min_length(self, prose_strict_schema: dict):
        """
        Test that depth-1 string items (direct outer array members) have minLength: 1.

        Given: The items block of prose-strict
        When: The oneOf branch for direct strings is examined
        Then: That branch declares minLength: 1
        """
        items = prose_strict_schema.get("items", {})
        one_of = items.get("oneOf", [])
        assert one_of, "prose-strict items must use oneOf for string | array branching"

        # Find the string branch.
        string_branches = [b for b in one_of if b.get("type") == "string"]
        assert string_branches, "prose-strict items oneOf must include a type:string branch"
        string_branch = string_branches[0]
        assert string_branch.get("minLength") == 1, "prose-strict depth-1 string items must have minLength: 1"

    def test_depth2_string_items_have_min_length(self, prose_strict_schema: dict):
        """
        Test that depth-2 string items (inside the nested array) have minLength: 1.

        Given: The inner array branch in prose-strict items oneOf
        When: The inner array's items are examined
        Then: Inner string items declare minLength: 1
        """
        items = prose_strict_schema.get("items", {})
        one_of = items.get("oneOf", [])
        array_branches = [b for b in one_of if b.get("type") == "array"]
        assert array_branches, "prose-strict items oneOf must include a type:array branch"
        inner_array = array_branches[0]
        inner_items = inner_array.get("items", {})
        assert inner_items.get("minLength") == 1, (
            "prose-strict depth-2 string items (inside nested array) must have minLength: 1"
        )

    def test_inner_array_has_min_items_one(self, prose_strict_schema: dict):
        """
        Test that the inner array (nested list) requires at least one item.

        Given: The inner array branch in prose-strict items oneOf
        When: Its minItems is examined
        Then: It is 1 (same as in definitions/utils/text)
        """
        items = prose_strict_schema.get("items", {})
        one_of = items.get("oneOf", [])
        array_branches = [b for b in one_of if b.get("type") == "array"]
        assert array_branches, "prose-strict items oneOf must include a type:array branch"
        inner_array = array_branches[0]
        assert inner_array.get("minItems") == 1, "prose-strict inner array must have minItems: 1"


# ============================================================================
# Behavioral validation — prose-strict accepts valid prose
# ============================================================================


class TestProseStrictAcceptsValidProse:
    """prose-strict must accept all non-empty, non-blank prose values."""

    @pytest.mark.parametrize("value", VALID_PROSE_VALUES)
    def test_valid_prose_accepted_by_prose_strict(self, prose_strict_validator: Draft7Validator, value: list):
        """
        Test that valid prose values are accepted by prose-strict.

        Given: A non-empty prose array with non-empty strings
        When: It is validated against prose-strict
        Then: No errors are raised
        """
        errors = list(prose_strict_validator.iter_errors(value))
        assert not errors, f"prose-strict must accept {value!r}; got: {[e.message for e in errors]}"

    @pytest.mark.parametrize("value", VALID_PROSE_VALUES)
    def test_valid_prose_accepted_by_text(self, text_validator: Draft7Validator, value: list):
        """
        Test that valid prose values are also accepted by the existing text definition.

        Given: A non-empty prose array with non-empty strings
        When: It is validated against definitions/utils/text
        Then: No errors are raised (text must also accept these valid values)
        """
        errors = list(text_validator.iter_errors(value))
        assert not errors, f"definitions/utils/text must accept {value!r}; got: {[e.message for e in errors]}"


# ============================================================================
# Behavioral validation — prose-strict rejects empty/blank values
# ============================================================================


class TestProseStrictRejectsEmptyValues:
    """prose-strict must reject empty outer arrays and empty strings."""

    def test_empty_outer_array_rejected_by_prose_strict(self, prose_strict_validator: Draft7Validator):
        """
        Test that an empty outer array is rejected by prose-strict.

        Given: An empty list []
        When: It is validated against prose-strict
        Then: ValidationError is raised (minItems: 1 on outer array)
        """
        errors = list(prose_strict_validator.iter_errors([]))
        assert errors, "prose-strict must reject empty outer array (minItems: 1)"

    def test_empty_string_at_depth1_rejected_by_prose_strict(self, prose_strict_validator: Draft7Validator):
        """
        Test that an empty string at depth-1 is rejected by prose-strict.

        Given: [""] — one empty-string item in the outer array
        When: It is validated against prose-strict
        Then: ValidationError is raised (minLength: 1)
        """
        errors = list(prose_strict_validator.iter_errors([""]))
        assert errors, 'prose-strict must reject [""] (empty depth-1 string; minLength: 1)'

    def test_empty_string_at_depth2_rejected_by_prose_strict(self, prose_strict_validator: Draft7Validator):
        """
        Test that an empty string inside a nested array is rejected by prose-strict.

        Given: [[""]] — one nested array containing one empty string
        When: It is validated against prose-strict
        Then: ValidationError is raised (minLength: 1 on depth-2 items)
        """
        errors = list(prose_strict_validator.iter_errors([[""]]))
        assert errors, 'prose-strict must reject [[""]] (empty depth-2 string; minLength: 1)'

    def test_empty_inner_array_rejected_by_prose_strict(self, prose_strict_validator: Draft7Validator):
        """
        Test that an empty nested array is rejected by prose-strict.

        Given: [[]] — an outer array containing one empty inner array
        When: It is validated against prose-strict
        Then: ValidationError is raised (minItems: 1 on inner array)
        """
        errors = list(prose_strict_validator.iter_errors([[]]))
        assert errors, "prose-strict must reject [[]] (empty inner array; minItems: 1)"

    def test_non_null_null_rejected_by_prose_strict(self, prose_strict_validator: Draft7Validator):
        """
        Test that null is rejected as a prose value.

        Given: [null] — an outer array containing null
        When: It is validated against prose-strict
        Then: ValidationError is raised
        """
        errors = list(prose_strict_validator.iter_errors([None]))
        assert errors, "prose-strict must reject [null]"


# ============================================================================
# Independence — text and prose-strict can be used independently
# ============================================================================


class TestDefinitionsAreIndependent:
    """text and prose-strict are independent; neither references the other."""

    def test_text_does_not_ref_prose_strict(self, text_schema: dict):
        """
        Test that definitions/utils/text does not reference prose-strict.

        Given: definitions/utils/text
        When: It is serialised to a string
        Then: 'prose-strict' does not appear in it (no accidental cross-ref)
        """
        serialised = json.dumps(text_schema)
        assert "prose-strict" not in serialised, "definitions/utils/text must not reference prose-strict"

    def test_prose_strict_does_not_ref_text(self, prose_strict_schema: dict):
        """
        Test that definitions/utils/prose-strict does not reference text.

        Given: definitions/utils/prose-strict
        When: It is serialised to a string
        Then: '/text' does not appear in it (no accidental cross-ref)
        """
        serialised = json.dumps(prose_strict_schema)
        # Guard against accidental $ref to utils/text.
        assert "utils/text" not in serialised, "definitions/utils/prose-strict must not $ref utils/text"


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Test classes: 8

- TestSchemaMetaValidity (1)               — riskmap.schema.json valid Draft-07
- TestTextDefinitionUnchanged (4)          — text present, type=array, no outer
                                             minItems, accepts empty outer array
- TestProseStrictPresence (3)              — exists as sibling, type=array,
                                             outer minItems=1
- TestProseStrictStringConstraints (3)     — depth-1 minLength, depth-2 minLength,
                                             inner array minItems
- TestProseStrictAcceptsValidProse         — parametrized: 4 valid values accepted
                                             by prose-strict AND text
- TestProseStrictRejectsEmptyValues (5)    — empty outer, empty depth-1 string,
                                             empty depth-2 string, empty inner
                                             array, null item
- TestDefinitionsAreIndependent (2)        — text does not ref prose-strict;
                                             prose-strict does not ref text

Coverage areas:
- prose-strict existence, outer minItems, depth-1 minLength,
  depth-2 minLength, inner array minItems
- Coexistence: text unchanged (no minItems on outer, empty array accepted)
- Behavioral: valid prose accepted; empty/blank rejected
- Independence: no cross-referencing between text and prose-strict
"""

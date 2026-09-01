#!/usr/bin/env python3
"""
Schema-validity guard for MermaidConfigLoader._get_emergency_defaults().

Context (backmerge 2026-08c, §4.4): develop's componentsExternalTools category
auto-merged into _get_emergency_defaults() carrying a "subgroupFill" key, while
main's #499 stripped that key from mermaid-styles.schema.json's
definitions/componentCategory and from every sibling category's emergency-default
entry. The result is a hardcoded fallback that goes invalid the moment a real
config load fails, silently: nothing else in the suite schema-validates this
dict.

Scope: this guard covers schema *validity* only. It proves the fallback dict
parses as a structurally legal mermaid-styles document (right keys, right
value shapes) and that the shape it must have cannot be weakened out from
under it. It does not, and cannot, catch a fallback that is schema-valid but
wrong -- e.g. every category sharing one fill color, or a strokeWidth of
"0px" on every entry: both match this schema's patterns. Coverage is
therefore schema-shape regressions, not rendering-correctness regressions.

Three assertions, all required:

1. Fragment validity: every entry under sharedElements.componentCategories
   validates against definitions/componentCategory, AND the set of category
   ids examined matches the full expected set. Without the second half, a
   fix (or an unrelated regression) that drops a whole category out of
   _get_emergency_defaults() shortens the loop and this would still report
   zero failures having checked less than it claims to.
2. Pin the oracle: definitions/componentCategory's property set is exactly
   {fill, stroke, strokeWidth}, its required set is the same three, and
   additionalProperties is false. All three sub-pins are needed: pinning
   only properties/additionalProperties (dropping required from the pin)
   lets a fix delete "required" from the schema definition and drop "fill"
   from a category's emergency-default entry at the same time — the
   fragment check goes green because nothing is required anymore, and nothing
   here would catch the schema having been weakened to accommodate the code
   instead of the code being fixed.
3. Ratchet the residual set by identity, asymmetrically: every error the
   whole-object validation reports must be one of the three pre-existing,
   main-side residuals named in _PREEXISTING_RESIDUALS (backmerge plan §8,
   "Emergency-defaults schema divergence") — matched on (path, message), not
   counted. A plain "len(errors) == 3" check is defeated by a fix that
   deletes the subgroupFill key from componentsExternalTools AND relocates
   it into graphTypes.component.specialStyling: specialStyling is itself one
   of the three named residuals AND additionalProperties: false, so the
   relocation trades the "'specialStyling' is a required property" residual
   for a new "Additional properties are not allowed ('subgroupFill' was
   unexpected)" error at the same path — total count unchanged at 3, object
   still schema-invalid. Matching by identity catches this because the new
   error's (path, message) pair is not in the named set.

   The ratchet is asymmetric on purpose: an error set that is a *subset* of
   the three named residuals passes (paying down part of §8's deferred debt
   must not turn this suite red), but any error outside the named set fails
   regardless of how many total errors there are.
"""

import json
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

# Add scripts/hooks directory to path
git_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(git_root / "scripts" / "hooks"))

from riskmap_validator.graphing import MermaidConfigLoader  # noqa: E402

_SCHEMA_PATH = git_root / "risk-map" / "schemas" / "mermaid-styles.schema.json"

# The category ids _get_emergency_defaults() hardcodes under
# sharedElements.componentCategories. Pinned so the fragment-validity test
# (assertion 1) cannot pass vacuously by examining fewer categories than it
# claims to -- e.g. a regression that drops a whole category block out of
# the hardcoded dict would shorten the loop below to iterate over 4 entries
# instead of 5 and still report zero failures.
#
# componentsData is included deliberately, not an oversight: it is a
# top-level category in no current source of truth (absent from
# components.yaml's top-level `categories:` entries -- it survives there
# only as a subcategory nested under componentsInfrastructure; absent from
# components.schema.json's top-level category id enum; absent from
# mermaid-styles.schema.json's sharedElements.componentCategories.required;
# absent from the live mermaid-styles.yaml). It remains legal in
# mermaid-styles.schema.json's componentCategories.properties (not
# required) as a named pre-existing exception -- see
# test_mermaid_styles_tools_category.py's test_componentstools_in_required_list
# and git history on mermaid-styles.schema.json, where componentsData
# was required until an earlier taxonomy revision demoted it to a
# subcategory and the schema kept the property for backward compatibility.
# _get_emergency_defaults() still carries a componentsData entry, matching
# that legacy allowance. Pinning it here is intentional: this set tracks
# what the hardcoded fallback actually contains today, not what a cleanup
# might reduce it to. If a future change deletes the componentsData block
# from _get_emergency_defaults() as legitimate housekeeping (the schema
# does not require it), update this set in the same commit -- that change
# is not the regression this guard exists to catch, and turning this test
# red is a signal to update the pin, not a signal that graph_utils.py broke.
_EXPECTED_CATEGORY_IDS = frozenset(
    {
        "componentsInfrastructure",
        "componentsData",
        "componentsApplication",
        "componentsModel",
        "componentsExternalTools",
    }
)

# The three pre-existing, main-side residual errors that are out of scope for
# this merge (backmerge plan §8, "Emergency-defaults schema divergence").
# Identified by (path, message) rather than counted: a fix that relocates the
# offending "subgroupFill" key elsewhere in the dict, rather than deleting
# it, can hold the total error count at 3 while trading one of these
# specific residuals for a different error at the same or a different path
# (see assertion 3's fragment class docstring). Matching identity, not
# cardinality, is what closes that gap.
#
# Each entry is (absolute_path_tuple, message). Paths are tuples of the
# jsonschema ValidationError.absolute_path elements.
_PREEXISTING_RESIDUALS = frozenset(
    {
        (("foundation",), "'strokeWidths' is a required property"),
        (("foundation",), "'strokePatterns' is a required property"),
        (("graphTypes", "component"), "'specialStyling' is a required property"),
    }
)


@pytest.fixture
def schema():
    """Parsed mermaid-styles.schema.json from the merged tree."""
    with open(_SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture
def emergency_defaults():
    """The hardcoded fallback dict returned by _get_emergency_defaults().

    Calls _get_emergency_defaults() directly rather than going through a
    real config-load failure. MermaidConfigLoader.__init__() only stores the
    given path; it does not read the file. _get_emergency_defaults() is a
    pure method that returns a dict literal and never touches
    self.config_file, so the Path("nonexistent.yaml") argument is inert --
    any path, including one that exists, would return the identical dict.
    This fixture exercises the fallback dict's *content* in isolation; it
    does not exercise the fallback *selection* seam (_get_safe_value()
    choosing the emergency defaults when a real load fails), which
    test_mermaid_config_loader.py covers separately.
    """
    loader = MermaidConfigLoader(Path("nonexistent.yaml"))
    return loader._get_emergency_defaults()


class TestEmergencyDefaultsComponentCategoriesAreSchemaValid:
    """Fragment-level validation of each componentCategories entry."""

    def test_every_component_category_entry_validates_against_component_category_definition(
        self, schema, emergency_defaults
    ):
        """
        Given: _get_emergency_defaults()'s sharedElements.componentCategories entries
        When: each entry is validated against definitions/componentCategory
        Then: none report a validation error

        Given the merged schema's componentCategory definition, every category
        emergency-defaults entry must conform to it. Today componentsExternalTools
        still carries a "subgroupFill" key stripped from the schema by #499,
        so this must fail with "'subgroupFill' was unexpected" until that key
        is deleted from graph_utils.py.
        """
        validator = Draft7Validator(schema["definitions"]["componentCategory"])
        categories = emergency_defaults["sharedElements"]["componentCategories"]

        failures = {}
        for category_id, entry in categories.items():
            entry_errors = [e.message for e in validator.iter_errors(entry)]
            if entry_errors:
                failures[category_id] = entry_errors

        assert not failures, (
            "componentCategories entries failing schema validation "
            f"against definitions/componentCategory: {failures}"
        )

    def test_all_expected_categories_are_examined(self, emergency_defaults):
        """
        Given: _get_emergency_defaults()'s sharedElements.componentCategories
        When: its category ids are compared against _EXPECTED_CATEGORY_IDS
        Then: the two sets are identical

        Non-vacuity guard for the test above: without pinning which
        categories were examined, a regression that deletes a whole category
        block from the hardcoded dict shortens the loop to fewer entries and
        the schema-validity test above still reports zero failures having
        checked less than it claims to.
        """
        categories = emergency_defaults["sharedElements"]["componentCategories"]
        assert set(categories.keys()) == _EXPECTED_CATEGORY_IDS, (
            "sharedElements.componentCategories no longer carries the expected "
            f"category set; got {sorted(categories.keys())}"
        )


class TestComponentCategoryDefinitionPropertySetIsPinned:
    """
    Pins the oracle so a fix cannot land in the schema instead of the code.

    Without this, re-adding "subgroupFill" to definitions/componentCategory
    (a partial revert of #499's schema narrowing) would make the fragment
    check above pass while shipping the exact regression this repair exists
    to prevent.
    """

    def test_property_set_is_exactly_fill_stroke_stroke_width(self, schema):
        """
        Given: definitions/componentCategory in the merged schema
        When: its declared properties are inspected
        Then: the set is exactly {fill, stroke, strokeWidth}
        """
        definition = schema["definitions"]["componentCategory"]
        assert set(definition["properties"].keys()) == {"fill", "stroke", "strokeWidth"}

    def test_required_set_is_exactly_fill_stroke_stroke_width(self, schema):
        """
        Given: definitions/componentCategory in the merged schema
        When: its declared "required" list is inspected
        Then: the set is exactly {fill, stroke, strokeWidth}

        Without this pin, a fix could delete "required" from the definition
        entirely (rather than just leaving properties/additionalProperties
        alone) while also dropping a real key such as "fill" from a
        category's emergency-default entry. That combination still validates
        under a properties-only pin: nothing is required, so nothing is
        missing. Pinning required closes the gap.
        """
        definition = schema["definitions"]["componentCategory"]
        assert set(definition["required"]) == {"fill", "stroke", "strokeWidth"}

    def test_additional_properties_is_false(self, schema):
        """
        Given: definitions/componentCategory in the merged schema
        When: additionalProperties is inspected
        Then: it is False, so any key beyond the pinned set is rejected
        """
        definition = schema["definitions"]["componentCategory"]
        assert definition["additionalProperties"] is False


class TestEmergencyDefaultsWholeObjectResidualIsRatcheted:
    """
    Ratchets the whole-object residual error set, by identity and
    asymmetrically.

    Scoping validation to the componentCategory fragment alone would miss a
    fix that keeps the fragment green by moving the offending key elsewhere
    in the emergency-defaults dict (e.g. up into graphTypes.component) rather
    than deleting it. A plain error *count* is not enough either:
    graphTypes.component.specialStyling is itself one of the three
    pre-existing residuals (required-but-missing) AND is
    additionalProperties: false, so relocating "subgroupFill" there trades
    that residual for a new, different error at the same path while holding
    the total count at 3. Matching each error's (path, message) identity
    against the named residual set catches that trade; counting does not.

    The comparison is asymmetric: the actual error set must be a subset of
    the named residuals (any error outside that set fails the test,
    regardless of how many errors there are in total), but it is not
    required to be exactly equal. Paying down part of §8's deferred debt --
    e.g. supplying the missing graphTypes.component.specialStyling entry --
    shrinks the actual set below the named one and must still pass.

    The companion test below (test_named_residuals_have_not_grown) checks a
    different failure mode: _PREEXISTING_RESIDUALS itself being grown to
    absorb a new error instead of that error being fixed. Its bound is a
    literal, not derived from this class's named set, precisely so that
    edit does not also loosen what it checks.
    """

    def test_every_error_is_one_of_the_named_preexisting_residuals(self, schema, emergency_defaults):
        """
        Given: the full _get_emergency_defaults() dict
        When: validated against the full merged mermaid-styles.schema.json
        Then: every reported error matches one of _PREEXISTING_RESIDUALS by
              (path, message); no error outside that set is tolerated

        Today this reports the "subgroupFill" violation on
        componentsExternalTools in addition to the three named residuals.
        After that key is deleted (not relocated), the reported set must be
        a subset of _PREEXISTING_RESIDUALS.
        """
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(emergency_defaults))
        actual = {(tuple(e.absolute_path), e.message) for e in errors}

        unexpected = actual - _PREEXISTING_RESIDUALS
        assert not unexpected, (
            "whole-object validation reported error(s) outside the three named, "
            f"pre-existing §8 residuals: {sorted(unexpected)}"
        )

    def test_named_residuals_have_not_grown(self, schema, emergency_defaults):
        """
        Given: the full _get_emergency_defaults() dict
        When: validated against the full merged mermaid-styles.schema.json
        Then: at most 3 errors are reported -- 3 as a literal, not as
              len(_PREEXISTING_RESIDUALS)

        This is not a duplicate-detection check: jsonschema errors are
        identified by (path, message), so a duplicate report of the same
        residual is impossible to construct here (this schema has no
        anyOf/oneOf/allOf branch that could revalidate the same value
        twice), and a 292-mutation sweep against the fixed dict found zero
        cases where this test fails independently of the identity test
        above when the bound is left as len(_PREEXISTING_RESIDUALS).

        The bound is pinned to the literal 3 instead, which gives this test
        one job the identity test cannot do: catch _PREEXISTING_RESIDUALS
        itself being grown to absorb a new, real error instead of that
        error being fixed. If a future edit appends a fourth entry to
        _PREEXISTING_RESIDUALS that happens to match a genuinely new
        validation error, the identity test above passes -- the actual
        error set is still a subset of the (now larger) named set. Using
        len(_PREEXISTING_RESIDUALS) as this test's bound would move in
        lockstep with that same edit and also pass, so nothing in the
        suite would flag the debt growing. The literal 3 does not move:
        a fourth error, named or not, fails here.

        Paying down debt is unaffected: removing a residual from
        _PREEXISTING_RESIDUALS and fixing the corresponding error drops the
        actual count below 3, which still satisfies this bound.
        Legitimately adding a fourth, distinct residual (rather than
        growing the set to hide a bug) requires bumping this literal in
        the same commit -- that is deliberate friction, not a defect.
        """
        validator = Draft7Validator(schema)
        errors = list(validator.iter_errors(emergency_defaults))
        assert len(errors) <= 3, (
            f"expected at most 3 residual errors (the pre-existing §8 debt, pinned as a "
            f"literal so growing _PREEXISTING_RESIDUALS cannot loosen this bound), "
            f"got {len(errors)}: {[(tuple(e.absolute_path), e.message) for e in errors]}"
        )


"""
Test Summary
============
Total Tests: 7
- Happy Path: 0
- Edge Cases: 0
- Error Conditions: 7, of which 3 are RED today (schema-validity guards, RED
  until graph_utils.py:216 is fixed) and 4 are green today and stay green
  after the fix: test_all_expected_categories_are_examined,
  test_property_set_is_exactly_fill_stroke_stroke_width,
  test_required_set_is_exactly_fill_stroke_stroke_width, and
  test_additional_properties_is_false pin the schema oracle itself and the
  expected category set, neither of which the subgroupFill bug touches.
  Measured: `pytest scripts/hooks/tests/test_emergency_defaults_schema_guard.py`
  reports 3 failed, 4 passed against the tree as merged.

Coverage: schema-*validity* only (see module header). This guard proves the
fallback dict is a structurally legal mermaid-styles document; it does not
prove the values it carries are correct, so a schema-valid-but-wrong
fallback (uniform fill colors, a deleted-but-defaulted flowchartConfig
value, etc.) is out of scope.

Coverage Areas:
- Fragment-level schema validation of componentCategories entries
- Non-vacuity: the full expected category set is examined, not a shortened one
- Pinning definitions/componentCategory's property set, required set, and
  additionalProperties (oracle guard against a schema-side "fix")
- Whole-object residual set ratcheted two ways: by identity (path, message),
  asymmetrically -- the named residual set may shrink but any error outside
  it fails -- and, independently, by a literal count cap that catches the
  named set itself being grown to hide a new error
"""

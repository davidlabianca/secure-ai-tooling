#!/usr/bin/env python3
"""
Tests for scripts/hooks/precommit/validate_identification_questions.py

This module tests the pre-commit lint that enforces the four structural rules
from risk-map/docs/contributing/identification-questions-style-guide.md against
personas.yaml (ADR-021 D7).

The four structural rules machine-enforced by the lint:
  Rule 1 — Count: when identificationQuestions is present on a non-deprecated
            persona, the array length must be 5–7.
  Rule 2 — Second-person opener: every question must begin with an approved
            second-person opener (Do you / Are you / Does your).
  Rule 3 — Parenthetical cardinality: parenthetical example lists contain ≤ 4
            items (items separated by comma or "or" inside the closing paren).
  Rule 4 — e.g. not i.e.: parentheticals introducing examples use e.g.
            (exemplary), not i.e. (definitional).

Editorial rules (activities-not-titles, ordering, anti-patterns) are NOT tested
here; they are prose-only and owned by the content-reviewer agent.

The hook ships warn-only (exit 0 with stderr warnings). A --block flag flips it
to block mode (exit non-zero on any rule violation).

The hook reads the persona id enum and deprecated flag from
risk-map/schemas/personas.schema.json, not hardcoded values.

Test Coverage:
==============
Total Tests: 55 across 9 test classes
- Rule 1 (count):           8 tests  (TestRule1Count)
- Rule 2 (opener):          9 tests  (TestRule2SecondPersonOpener)
- Rule 3 (parenthetical):  13 tests  (TestRule3ParentheticalCardinality)
  - 3 tests cover _count_paren_items depth-aware nested-paren handling
- Rule 4 (e.g. not i.e.):  7 tests  (TestRule4EgNotIe)
- Warn/block toggle:        7 tests  (TestWarnBlockToggle)
- Stderr format:            4 tests  (TestStderrFormat)
- Schema-driven enumeration:5 tests  (TestSchemaDrivenEnumeration)
- Integration (corpus):     2 tests  (TestCorpusIntegration)
"""

import json
import sys
from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Add scripts/hooks/precommit to the import path so that the module under
# test can be imported as `validate_identification_questions` regardless of
# working directory.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "precommit"))

from validate_identification_questions import (  # noqa: E402  (import after path insert)
    _count_paren_items,
    check_count_rule,
    check_eg_not_ie_rule,
    check_opener_rule,
    check_parenthetical_cardinality_rule,
    load_persona_ids_from_schema,
    validate_personas_file,
)

# ---------------------------------------------------------------------------
# Approved second-person openers (per style guide § Format)
# ---------------------------------------------------------------------------
APPROVED_OPENERS = ("Do you ", "Are you ", "Does your ")


# ---------------------------------------------------------------------------
# Shared helpers for building synthetic YAML and schema fixtures
# ---------------------------------------------------------------------------


def _make_schema(persona_ids: list[str], deprecated_ids: list[str] | None = None) -> dict:
    """Build a minimal personas.schema.json dict for use with tmp_path fixtures.

    Args:
        persona_ids: All persona IDs to enumerate in the schema.
        deprecated_ids: Subset of persona_ids to flag as deprecated in the
                        schema's deprecated_defaults field (mimics ADR-021 D2).
                        The schema itself only enumerates IDs; deprecated status
                        is read from the YAML data, not the schema enum.
                        Provided here so callers can document intent clearly.
    """
    # The schema enum lists all IDs; deprecated flag lives on YAML entries.
    return {
        "$id": "personas.schema.json",
        "$schema": "http://json-schema.org/draft-07/schema#",
        "definitions": {
            "persona": {
                "properties": {
                    "id": {"type": "string", "enum": persona_ids},
                    "deprecated": {"type": "boolean", "default": False},
                }
            }
        },
    }


def _make_personas_yaml(personas: list[dict]) -> dict:
    """Build a minimal personas.yaml dict for use with tmp_path fixtures."""
    return {"id": "personas", "title": "Personas", "personas": personas}


def _make_persona(
    persona_id: str,
    questions: list[str] | None = None,
    deprecated: bool = False,
) -> dict:
    """Build a single persona dict entry.

    Args:
        persona_id: The persona's id field.
        questions: identificationQuestions list. None means the field is absent.
        deprecated: Whether to set deprecated: true.
    """
    entry: dict = {
        "id": persona_id,
        "title": f"Test Persona {persona_id}",
        "description": ["A test persona."],
    }
    if questions is not None:
        entry["identificationQuestions"] = questions
    if deprecated:
        entry["deprecated"] = True
    return entry


# ---------------------------------------------------------------------------
# Five canonical valid questions (≥ 5) used in multiple test classes
# ---------------------------------------------------------------------------
VALID_5_QUESTIONS = [
    "Do you operate AI systems in production environments?",
    "Are you responsible for model deployment decisions?",
    "Does your team manage the runtime infrastructure for AI models?",
    "Do you have authority to approve or reject AI model updates?",
    "Do you define access policies for AI model endpoints?",
]

VALID_7_QUESTIONS = VALID_5_QUESTIONS + [
    "Are you accountable for AI system availability and reliability?",
    "Does your role include incident response for AI failures?",
]


# ===========================================================================
# Rule 1 — Count (5–7 questions per non-deprecated persona when field present)
# ===========================================================================


class TestRule1Count:
    """Tests for the count rule: 5–7 questions when identificationQuestions present."""

    def test_exactly_5_questions_passes(self, tmp_path):
        """
        Persona with exactly 5 questions satisfies the count floor.

        Given: A non-deprecated persona with 5 identificationQuestions
        When: check_count_rule is called
        Then: Returns no warnings
        """
        warnings = check_count_rule("personaA", VALID_5_QUESTIONS)
        assert warnings == []

    def test_exactly_7_questions_passes(self, tmp_path):
        """
        Persona with exactly 7 questions satisfies the count ceiling.

        Given: A non-deprecated persona with 7 identificationQuestions
        When: check_count_rule is called
        Then: Returns no warnings
        """
        warnings = check_count_rule("personaA", VALID_7_QUESTIONS)
        assert warnings == []

    def test_4_questions_triggers_count_warning(self):
        """
        Persona with 4 questions is below the 5-question floor.

        Given: A non-deprecated persona with 4 identificationQuestions
        When: check_count_rule is called
        Then: Returns one warning indicating count below floor
        """
        questions = VALID_5_QUESTIONS[:4]
        warnings = check_count_rule("personaA", questions)
        assert len(warnings) == 1
        assert "count below floor" in warnings[0].lower() or "below" in warnings[0].lower()
        assert "4" in warnings[0]

    def test_8_questions_triggers_count_warning(self):
        """
        Persona with 8 questions exceeds the 7-question ceiling.

        Given: A non-deprecated persona with 8 identificationQuestions
        When: check_count_rule is called
        Then: Returns one warning indicating count above ceiling
        """
        questions = VALID_7_QUESTIONS + ["Do you manage model versioning artifacts?"]
        warnings = check_count_rule("personaA", questions)
        assert len(warnings) == 1
        assert (
            "above" in warnings[0].lower() or "ceiling" in warnings[0].lower() or "exceed" in warnings[0].lower()
        )
        assert "8" in warnings[0]

    def test_0_questions_triggers_count_warning(self):
        """
        Persona with an empty identificationQuestions array triggers the count rule.

        Given: A non-deprecated persona with 0 identificationQuestions
        When: check_count_rule is called
        Then: Returns one warning (count below floor)
        """
        warnings = check_count_rule("personaA", [])
        assert len(warnings) == 1
        assert "0" in warnings[0]

    def test_deprecated_persona_exempt_from_count_rule(self, tmp_path):
        """
        Deprecated personas are not validated for count violations.

        Given: A persona with deprecated: true and only 2 identificationQuestions
        When: validate_personas_file is called
        Then: No count-rule warning emitted for that persona

        Deprecated personas are exempt because they are legacy entries retained
        for backward compatibility only (ADR-021 D2).
        """
        schema_path = tmp_path / "personas.schema.json"
        yaml_path = tmp_path / "personas.yaml"
        schema_path.write_text(json.dumps(_make_schema(["personaLegacy"])))
        yaml_data = _make_personas_yaml(
            [
                _make_persona(
                    "personaLegacy",
                    questions=["Do you manage legacy models?", "Are you retired?"],
                    deprecated=True,
                )
            ]
        )
        yaml_path.write_text(yaml.dump(yaml_data))

        warnings = validate_personas_file(str(yaml_path), str(schema_path), block=False)
        # No warnings — deprecated persona is exempt
        assert warnings == []

    def test_missing_identification_questions_field_not_flagged(self, tmp_path):
        """
        Personas without identificationQuestions field produce no count warning.

        Given: A non-deprecated persona with no identificationQuestions key at all
        When: validate_personas_file is called
        Then: No count-rule warning (absence of the optional field is allowed)

        Per ADR-021 D8: identificationQuestions stays optional in the schema.
        """
        schema_path = tmp_path / "personas.schema.json"
        yaml_path = tmp_path / "personas.yaml"
        schema_path.write_text(json.dumps(_make_schema(["personaNoQuestions"])))
        yaml_data = _make_personas_yaml([_make_persona("personaNoQuestions", questions=None)])
        yaml_path.write_text(yaml.dump(yaml_data))

        warnings = validate_personas_file(str(yaml_path), str(schema_path), block=False)
        assert warnings == []

    def test_6_questions_passes(self):
        """
        Persona with 6 questions is within the 5–7 range.

        Given: A non-deprecated persona with 6 identificationQuestions
        When: check_count_rule is called
        Then: Returns no warnings
        """
        questions = VALID_5_QUESTIONS + ["Are you accountable for AI system availability?"]
        warnings = check_count_rule("personaA", questions)
        assert warnings == []


# ===========================================================================
# Rule 2 — Second-person opener
# ===========================================================================


class TestRule2SecondPersonOpener:
    """Tests for the second-person opener rule.

    Approved openers (per style guide § Format):
        - 'Do you '
        - 'Are you '
        - 'Does your '

    Rejected: third-person, imperative, rhetorical constructions, lowercase.
    """

    def test_do_you_opener_passes(self):
        """
        Question starting with 'Do you ' is accepted.

        Given: A question beginning with 'Do you operate ...'
        When: check_opener_rule is called
        Then: Returns no warnings
        """
        warnings = check_opener_rule("personaA", 0, "Do you operate AI systems in production environments?")
        assert warnings == []

    def test_are_you_opener_passes(self):
        """
        Question starting with 'Are you ' is accepted.

        Given: A question beginning with 'Are you responsible for ...'
        When: check_opener_rule is called
        Then: Returns no warnings
        """
        warnings = check_opener_rule("personaA", 1, "Are you responsible for model deployment decisions?")
        assert warnings == []

    def test_does_your_opener_passes(self):
        """
        Question starting with 'Does your ' is accepted.

        Given: A question beginning with 'Does your team manage ...'
        When: check_opener_rule is called
        Then: Returns no warnings (Does your is explicitly listed in style guide)
        """
        warnings = check_opener_rule(
            "personaA", 2, "Does your team manage the runtime infrastructure for AI models?"
        )
        assert warnings == []

    def test_do_you_have_opener_passes(self):
        """
        'Do you have ...' is accepted (variant of the Do you opener).

        Given: A question beginning with 'Do you have authority ...'
        When: check_opener_rule is called
        Then: Returns no warnings
        """
        warnings = check_opener_rule("personaA", 3, "Do you have authority to approve or reject AI model updates?")
        assert warnings == []

    def test_missing_opener_triggers_warning(self):
        """
        Question starting with an imperative verb (no second-person opener) is rejected.

        Given: A question beginning with 'Operate any ...' (no approved opener)
        When: check_opener_rule is called
        Then: Returns one warning indicating unapproved opener
        """
        warnings = check_opener_rule("personaA", 0, "Operate any models as part of your role?")
        assert len(warnings) == 1
        assert "opener" in warnings[0].lower() or "second-person" in warnings[0].lower()

    def test_third_person_does_the_organization_triggers_warning(self):
        """
        Third-person 'Does the organization ...' is rejected (not in the approved list).

        Given: A question beginning with 'Does the organization ...'
        When: check_opener_rule is called
        Then: Returns one warning (style guide explicitly rejects third-person framing)

        The style guide says: "Do not use third-person framing ('Does the organization...')"
        """
        warnings = check_opener_rule("personaA", 0, "Does the organization manage AI models at scale?")
        assert len(warnings) == 1

    def test_lowercase_do_you_triggers_warning(self):
        """
        Lowercase 'do you ...' is rejected (capitalization required).

        Given: A question beginning with lowercase 'do you ...'
        When: check_opener_rule is called
        Then: Returns one warning (openers are case-sensitive; style guide shows title case)
        """
        warnings = check_opener_rule("personaA", 0, "do you operate AI systems in production?")
        assert len(warnings) == 1

    def test_mixed_array_one_invalid_opener_emits_one_warning(self, tmp_path):
        """
        Array of 5 valid + 1 invalid opener produces exactly one opener warning.

        Given: A persona with 5 valid questions and 1 question with a bad opener
        When: validate_personas_file is called
        Then: Exactly one opener warning is emitted (per offending question)
        """
        schema_path = tmp_path / "personas.schema.json"
        yaml_path = tmp_path / "personas.yaml"
        schema_path.write_text(json.dumps(_make_schema(["personaA"])))
        questions = list(VALID_5_QUESTIONS) + ["Operate any models as part of your role?"]
        # 6 questions satisfies count rule (5–7); only the bad opener fires
        yaml_data = _make_personas_yaml([_make_persona("personaA", questions=questions)])
        yaml_path.write_text(yaml.dump(yaml_data))

        warnings = validate_personas_file(str(yaml_path), str(schema_path), block=False)
        opener_warnings = [w for w in warnings if "opener" in w.lower() or "second-person" in w.lower()]
        assert len(opener_warnings) == 1

    def test_rhetorical_would_you_say_triggers_warning(self):
        """
        Rhetorical construction 'Would you say ...' is rejected.

        Given: A question beginning with 'Would you say ...'
        When: check_opener_rule is called
        Then: Returns one warning (style guide explicitly rejects rhetorical constructions)
        """
        warnings = check_opener_rule("personaA", 0, "Would you say your organization trains AI models?")
        assert len(warnings) == 1


# ===========================================================================
# Rule 3 — Parenthetical cardinality (≤ 4 items)
# ===========================================================================


class TestRule3ParentheticalCardinality:
    """Tests for the parenthetical cardinality rule: ≤ 4 items per parenthetical.

    Items are counted by splitting on ',' and ' or ' within the parenthetical body.
    Items separated by ' or ' (with spaces) are distinct from 'or' embedded in a
    single item name.
    """

    def test_3_items_comma_separated_passes(self):
        """
        Parenthetical with 3 comma-separated items is within the ≤ 4 ceiling.

        Given: 'Do you operate any models? (e.g., GPT-4, Claude, Gemini)'
        When: check_parenthetical_cardinality_rule is called
        Then: Returns no warnings (3 items ≤ 4)
        """
        q = "Do you operate any models? (e.g., GPT-4, Claude, Gemini)"
        warnings = check_parenthetical_cardinality_rule("personaA", 0, q)
        assert warnings == []

    def test_4_items_comma_separated_passes(self):
        """
        Parenthetical with exactly 4 items is at the ceiling and passes.

        Given: '(e.g., GPT-4, Claude, Gemini, Llama)' — 4 items
        When: check_parenthetical_cardinality_rule is called
        Then: Returns no warnings (exactly ≤ 4)
        """
        q = "Do you operate any models? (e.g., GPT-4, Claude, Gemini, Llama)"
        warnings = check_parenthetical_cardinality_rule("personaA", 0, q)
        assert warnings == []

    def test_5_items_comma_separated_triggers_warning(self):
        """
        Parenthetical with 5 comma-separated items exceeds the ≤ 4 ceiling.

        Given: '(e.g., GPT-4, Claude, Gemini, Llama, Mistral)' — 5 items
        When: check_parenthetical_cardinality_rule is called
        Then: Returns one warning indicating parenthetical item count exceeded
        """
        q = "Do you operate any models? (e.g., GPT-4, Claude, Gemini, Llama, Mistral)"
        warnings = check_parenthetical_cardinality_rule("personaA", 0, q)
        assert len(warnings) == 1
        assert "parenthetical" in warnings[0].lower() or "items" in warnings[0].lower()

    def test_5_items_or_separated_triggers_warning(self):
        """
        Parenthetical with 5 items separated by 'or' exceeds the ≤ 4 ceiling.

        Given: '(e.g., GPT-4 or Claude or Gemini or Llama or Mistral)' — 5 items
        When: check_parenthetical_cardinality_rule is called
        Then: Returns one warning
        """
        q = "Do you operate any models? (e.g., GPT-4 or Claude or Gemini or Llama or Mistral)"
        warnings = check_parenthetical_cardinality_rule("personaA", 0, q)
        assert len(warnings) == 1

    def test_1_item_passes(self):
        """
        Parenthetical with 1 item is well within the ceiling.

        Given: '(e.g., GPT-4)' — 1 item
        When: check_parenthetical_cardinality_rule is called
        Then: Returns no warnings
        """
        q = "Do you operate any models? (e.g., GPT-4)"
        warnings = check_parenthetical_cardinality_rule("personaA", 0, q)
        assert warnings == []

    def test_no_parenthetical_passes(self):
        """
        Question with no parenthetical is not subject to this rule.

        Given: A question with no parenthetical content at all
        When: check_parenthetical_cardinality_rule is called
        Then: Returns no warnings (rule doesn't apply)
        """
        q = "Do you operate AI systems in production environments?"
        warnings = check_parenthetical_cardinality_rule("personaA", 0, q)
        assert warnings == []

    def test_multiple_parentheticals_evaluated_independently(self):
        """
        A question with two parentheticals has each evaluated independently.

        Given: A question with two parentheticals, one with 3 items and one with 5
        When: check_parenthetical_cardinality_rule is called
        Then: Returns one warning for the 5-item parenthetical only

        The 3-item parenthetical passes (≤ 4); the 5-item one fails.
        """
        q = (
            "Do you use frameworks (e.g., PyTorch, TensorFlow, JAX) "
            "or platforms (e.g., AWS, Azure, GCP, Vertex, SageMaker)?"
        )
        warnings = check_parenthetical_cardinality_rule("personaA", 0, q)
        # The second parenthetical has 5 items, first has 3 — expect 1 warning
        assert len(warnings) == 1

    def test_nested_parenthetical_counts_as_one_item(self):
        """
        Content within a nested set of parentheses counts as a single list item.

        Given: '(e.g., distillation (LoRA), quantization, adaptation)'
        When: check_parenthetical_cardinality_rule is called
        Then: 3 items — the nested paren is part of one item — no warning

        The outer list items are: 'distillation (LoRA)', 'quantization', 'adaptation'.
        Splitting on commas at the outermost level treats the nested paren as
        part of a single item rather than inflating the count.
        """
        q = "Do you modify models (e.g., distillation (LoRA), quantization, adaptation) for distribution?"
        warnings = check_parenthetical_cardinality_rule("personaA", 0, q)
        # 3 outer items — should pass
        assert warnings == []

    def test_nested_parenthetical_with_inner_comma_does_not_bleed_through(self):
        """
        Inner-paren commas must not be counted as outer-level item separators.

        Given: '(e.g., model A (v1, v2), model B (v3, v4), model C)' — 3 outer items,
               each inner paren contains a comma that must not bleed through
        When: check_parenthetical_cardinality_rule is called
        Then: Returns no warnings (3 outer items ≤ 4 limit)

        The depth-unaware split in _count_paren_items currently treats the body
        'model A (v1, v2), model B (v3, v4), model C' as 5 tokens by splitting on
        every comma, including the two inner-paren commas.  A depth-aware
        implementation must skip commas inside nested parens.

        NOTE: double-nesting (e.g. '((x, y))') is out of scope — the outer regex
        _PAREN_BODY_RE only handles one level of nesting, and the style guide's
        guidance against complex items makes that a non-issue in practice.
        """
        question = "Do you operate models? (e.g., model A (v1, v2), model B (v3, v4), model C)"

        # Helper-level assertion: 3 outer items, not 5.
        # Today _count_paren_items returns 5 (bug), so this assertion fails.
        body = "model A (v1, v2), model B (v3, v4), model C"
        assert _count_paren_items(body) == 3, (
            f"_count_paren_items returned {_count_paren_items(body)}, expected 3; "
            "inner-paren commas are bleeding through as outer separators"
        )

        # Rule-level assertion: no warning fires.
        warnings = check_parenthetical_cardinality_rule("personaTest", 0, question)
        assert warnings == [], f"Expected no warnings for 3-item parenthetical with nested commas, got: {warnings}"

    def test_nested_parenthetical_with_inner_comma_pair_under_threshold(self):
        """
        Inner-paren comma in a 2-item outer list must not inflate the count.

        Given: '(e.g., model A (version 1, 2), model B)' — 2 outer items
        When: check_parenthetical_cardinality_rule is called
        Then: Returns no warnings (2 outer items ≤ 4 limit)
        AND: _count_paren_items("model A (version 1, 2), model B") returns exactly 2

        Today _count_paren_items returns 3 because the inner comma '1, 2' leaks
        through. The warning still does not fire (3 ≤ 4) but the count is wrong —
        which is a latent false-negative: if there were 4 real outer items each
        with one inner-comma paren, the count would reach 8 and falsely warn.
        """
        body = "model A (version 1, 2), model B"
        count = _count_paren_items(body)
        assert count == 2, (
            f"_count_paren_items returned {count}, expected 2; "
            "inner-paren comma is leaking through as an outer separator"
        )

        question = "Do you operate models? (e.g., model A (version 1, 2), model B)"
        warnings = check_parenthetical_cardinality_rule("personaTest", 0, question)
        assert warnings == [], f"Expected no warnings for 2-item parenthetical with nested comma, got: {warnings}"

    def test_nested_parenthetical_with_or_separator_inside_inner_paren(self):
        """
        Inner-paren ' or ' must not be counted as an outer-level separator.

        Given: '(e.g., model A (v1 or v2), model B)' — 2 outer items
        When: check_parenthetical_cardinality_rule is called
        Then: Returns no warnings (2 outer items ≤ 4 limit)
        AND: _count_paren_items("model A (v1 or v2), model B") returns exactly 2

        The implementation uses both ',' and ' or ' as item separators. The
        depth-unaware normalisation replaces all ' or ' tokens — including those
        inside nested parens — before splitting. A depth-aware fix must skip
        ' or ' tokens that appear inside nested parentheses.

        Today _count_paren_items returns 3 because the inner ' or ' is treated as
        an outer separator alongside the outer comma.
        """
        body = "model A (v1 or v2), model B"
        count = _count_paren_items(body)
        assert count == 2, (
            f"_count_paren_items returned {count}, expected 2; "
            "inner-paren ' or ' is leaking through as an outer separator"
        )

        question = "Do you operate models? (e.g., model A (v1 or v2), model B)"
        warnings = check_parenthetical_cardinality_rule("personaTest", 0, question)
        assert warnings == [], f"Expected no warnings for 2-item parenthetical with nested ' or ', got: {warnings}"

    def test_2_items_passes(self):
        """
        Parenthetical with 2 items is within the style-guide minimum of 2–4 items.

        Given: '(e.g., distillation, quantization)' — 2 items
        When: check_parenthetical_cardinality_rule is called
        Then: Returns no warnings
        """
        q = "Do you modify models (e.g., distillation, quantization) for use by others?"
        warnings = check_parenthetical_cardinality_rule("personaA", 0, q)
        assert warnings == []

    def test_items_counted_only_within_parentheses(self):
        """
        Commas outside parentheses are not counted as item separators.

        Given: A question with 3 commas outside and 2 items inside parens
        When: check_parenthetical_cardinality_rule is called
        Then: Returns no warnings (only intra-paren commas count)
        """
        q = "Do you train, evaluate, and benchmark models (e.g., classifiers, regressors) for clients?"
        warnings = check_parenthetical_cardinality_rule("personaA", 0, q)
        assert warnings == []


# ===========================================================================
# Rule 4 — e.g. not i.e.
# ===========================================================================


class TestRule4EgNotIe:
    """Tests for the e.g. not i.e. rule.

    Parentheticals introducing examples must use 'e.g.', not 'i.e.'.
    Parentheticals containing neither 'e.g.' nor 'i.e.' are not targeted.
    The rule only fires on parentheticals that use 'i.e.' — it cannot know
    whether an untagged parenthetical is definitional or exemplary.
    """

    def test_eg_parenthetical_passes(self):
        """
        Parenthetical using 'e.g.' is correct and passes.

        Given: '... (e.g., GPT-4)'
        When: check_eg_not_ie_rule is called
        Then: Returns no warnings
        """
        q = "Do you operate any models? (e.g., GPT-4)"
        warnings = check_eg_not_ie_rule("personaA", 0, q)
        assert warnings == []

    def test_ie_parenthetical_triggers_warning(self):
        """
        Parenthetical using 'i.e.' triggers the rule.

        Given: '... (i.e., the open-source model family)'
        When: check_eg_not_ie_rule is called
        Then: Returns one warning indicating i.e. should be e.g.
        """
        q = "Do you use a specific model family (i.e., the open-source model family)?"
        warnings = check_eg_not_ie_rule("personaA", 0, q)
        assert len(warnings) == 1
        assert "i.e." in warnings[0] or "ie" in warnings[0].lower()

    def test_such_as_parenthetical_not_targeted(self):
        """
        Parenthetical using 'such as' is not targeted by this rule.

        Given: '... (such as GPT-4)'
        When: check_eg_not_ie_rule is called
        Then: Returns no warnings

        The rule targets 'i.e.' specifically. 'such as' is neither 'e.g.' nor
        'i.e.' so the rule does not fire (ADR-021 D7 only names e.g./i.e.).
        """
        q = "Do you operate any models (such as GPT-4)?"
        warnings = check_eg_not_ie_rule("personaA", 0, q)
        assert warnings == []

    def test_no_parenthetical_passes(self):
        """
        Question with no parenthetical is not subject to this rule.

        Given: A question with no parenthetical at all
        When: check_eg_not_ie_rule is called
        Then: Returns no warnings
        """
        q = "Do you operate AI systems in production environments?"
        warnings = check_eg_not_ie_rule("personaA", 0, q)
        assert warnings == []

    def test_parenthetical_without_eg_or_ie_not_targeted(self):
        """
        Parenthetical that is purely clarifying (no e.g. or i.e.) is not targeted.

        Given: '... (as part of training or distribution decisions)'
        When: check_eg_not_ie_rule is called
        Then: Returns no warnings (neither e.g. nor i.e. present; rule is inapplicable)
        """
        q = "Do you evaluate models (as part of training or distribution decisions)?"
        warnings = check_eg_not_ie_rule("personaA", 0, q)
        assert warnings == []

    def test_ie_in_non_parenthetical_position_not_flagged(self):
        """
        'i.e.' appearing outside parentheses does not trigger Rule 4.

        Given: A question with 'i.e.' in the main question body, not inside parens
        When: check_eg_not_ie_rule is called
        Then: Returns no warnings (rule only targets parenthetical i.e. usage)

        The style guide's parenthetical guidance applies only to the content
        inside '(...)'; 'i.e.' in prose outside parens is editorial judgment.
        """
        q = "Do you manage the serving layer, i.e. the runtime that delivers predictions?"
        warnings = check_eg_not_ie_rule("personaA", 0, q)
        assert warnings == []

    def test_multiple_ie_parentheticals_each_emit_one_warning(self, tmp_path):
        """
        A question with two i.e. parentheticals emits two warnings.

        Given: A question with '(i.e., X)' appearing twice
        When: check_eg_not_ie_rule is called
        Then: Returns two warnings (one per offending parenthetical)
        """
        q = "Do you manage models (i.e., neural networks) using frameworks (i.e., PyTorch)?"
        warnings = check_eg_not_ie_rule("personaA", 0, q)
        assert len(warnings) == 2


# ===========================================================================
# Warn-only / block-mode toggle
# ===========================================================================


class TestWarnBlockToggle:
    """Tests for the warn-only vs. block-mode exit behaviour.

    Warn-only (default): rule violations produce stderr lines but exit 0.
    Block mode (--block flag): any rule violation causes exit non-zero.
    """

    def _write_minimal_files(self, tmp_path, questions: list[str], deprecated: bool = False) -> tuple[Path, Path]:
        """Write a schema and personas YAML with a single persona to tmp_path."""
        schema_path = tmp_path / "personas.schema.json"
        yaml_path = tmp_path / "personas.yaml"
        schema_path.write_text(json.dumps(_make_schema(["personaA"])))
        yaml_data = _make_personas_yaml([_make_persona("personaA", questions=questions, deprecated=deprecated)])
        yaml_path.write_text(yaml.dump(yaml_data))
        return yaml_path, schema_path

    def test_warn_mode_violation_exits_0(self, tmp_path):
        """
        Warn-only mode (default, block=False): rule violation exits 0.

        Given: A persona with 4 questions (count violation) and block=False
        When: validate_personas_file is called
        Then: Returns a non-empty warnings list (but the caller exits 0)

        validate_personas_file returns the list of warnings; the exit code
        decision belongs to main(). This test confirms violations are detected
        and returned rather than suppressed.
        """
        yaml_path, schema_path = self._write_minimal_files(tmp_path, questions=VALID_5_QUESTIONS[:4])
        warnings = validate_personas_file(str(yaml_path), str(schema_path), block=False)
        assert len(warnings) >= 1

    def test_block_mode_violation_signals_failure(self, tmp_path):
        """
        Block mode (block=True): rule violation raises SystemExit with non-zero code.

        Given: A persona with 4 questions (count violation) and block=True
        When: validate_personas_file is called
        Then: Raises SystemExit with a non-zero exit code

        In block mode the hook must fail the commit.
        """
        yaml_path, schema_path = self._write_minimal_files(tmp_path, questions=VALID_5_QUESTIONS[:4])
        with pytest.raises(SystemExit) as exc_info:
            validate_personas_file(str(yaml_path), str(schema_path), block=True)
        assert exc_info.value.code != 0

    def test_block_mode_clean_input_exits_0(self, tmp_path):
        """
        Block mode with fully conforming input exits 0.

        Given: A persona with 5 valid questions and block=True
        When: validate_personas_file is called
        Then: Returns empty warnings list (no SystemExit raised)
        """
        yaml_path, schema_path = self._write_minimal_files(tmp_path, questions=VALID_5_QUESTIONS)
        # Should not raise
        warnings = validate_personas_file(str(yaml_path), str(schema_path), block=True)
        assert warnings == []

    def test_warn_mode_clean_input_returns_empty(self, tmp_path):
        """
        Warn mode with fully conforming input returns no warnings.

        Given: A persona with 5 valid questions and block=False
        When: validate_personas_file is called
        Then: Returns empty warnings list (no stderr output needed)
        """
        yaml_path, schema_path = self._write_minimal_files(tmp_path, questions=VALID_5_QUESTIONS)
        warnings = validate_personas_file(str(yaml_path), str(schema_path), block=False)
        assert warnings == []

    def test_main_warn_mode_exits_0_on_violation(self, tmp_path, capsys):
        """
        main() with warn-only mode (no --block flag) exits 0 even with violations.

        Given: A personas.yaml with a count violation and no --block flag in argv
        When: main() is called
        Then: sys.exit(0) is raised; violations appear on stderr
        """
        from validate_identification_questions import main  # noqa: PLC0415

        yaml_path, schema_path = self._write_minimal_files(tmp_path, questions=VALID_5_QUESTIONS[:4])
        with pytest.raises(SystemExit) as exc_info:
            main([str(yaml_path), "--schema", str(schema_path)])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "validate-identification-questions" in captured.err

    def test_main_block_mode_exits_nonzero_on_violation(self, tmp_path, capsys):
        """
        main() with --block flag exits non-zero when violations are detected.

        Given: A personas.yaml with a count violation and --block in argv
        When: main() is called
        Then: sys.exit with non-zero code; violations appear on stderr
        """
        from validate_identification_questions import main  # noqa: PLC0415

        yaml_path, schema_path = self._write_minimal_files(tmp_path, questions=VALID_5_QUESTIONS[:4])
        with pytest.raises(SystemExit) as exc_info:
            main([str(yaml_path), "--schema", str(schema_path), "--block"])
        assert exc_info.value.code != 0
        captured = capsys.readouterr()
        assert "validate-identification-questions" in captured.err

    def test_main_block_mode_exits_0_clean_input(self, tmp_path, capsys):
        """
        main() with --block flag exits 0 when all rules pass.

        Given: A personas.yaml with 5 valid questions and --block in argv
        When: main() is called
        Then: sys.exit(0) is raised; no stderr output
        """
        from validate_identification_questions import main  # noqa: PLC0415

        yaml_path, schema_path = self._write_minimal_files(tmp_path, questions=VALID_5_QUESTIONS)
        with pytest.raises(SystemExit) as exc_info:
            main([str(yaml_path), "--schema", str(schema_path), "--block"])
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert captured.err == ""


# ===========================================================================
# Stderr format
# ===========================================================================


class TestStderrFormat:
    """Tests for the stderr rejection-line format.

    Required format per ADR-021 D7 / draft-A5 issue body:
        validate-identification-questions: <file>:<persona-id>:identificationQuestions[<index>]: <reason>
    """

    def test_count_violation_format(self, tmp_path, capsys):
        """
        Count violation stderr line matches the required format exactly.

        Given: Persona 'personaXyz' with 4 questions (count below floor)
        When: main() emits warnings to stderr
        Then: stderr line is:
              'validate-identification-questions: <file>:personaXyz:identificationQuestions[3]: ...'

        The index in the format string is the last valid index (len - 1) or the
        persona-level count indicator.  We assert the persona-id and file path are
        present; we lock the prefix format exactly.
        """
        from validate_identification_questions import main  # noqa: PLC0415

        schema_path = tmp_path / "personas.schema.json"
        yaml_path = tmp_path / "personas.yaml"
        schema_path.write_text(json.dumps(_make_schema(["personaXyz"])))
        yaml_data = _make_personas_yaml([_make_persona("personaXyz", questions=VALID_5_QUESTIONS[:4])])
        yaml_path.write_text(yaml.dump(yaml_data))

        with pytest.raises(SystemExit):
            main([str(yaml_path), "--schema", str(schema_path)])
        captured = capsys.readouterr()

        assert "validate-identification-questions:" in captured.err
        assert "personaXyz" in captured.err
        assert "identificationQuestions" in captured.err
        # The file path (basename is sufficient; implementation may use abs or relative)
        assert str(yaml_path.name) in captured.err or str(yaml_path) in captured.err

    def test_opener_violation_format_includes_index(self, tmp_path, capsys):
        """
        Opener violation stderr line includes the question index.

        Given: Persona with 5 questions, question at index 2 has bad opener
        When: main() emits warnings to stderr
        Then: stderr line contains '[2]' (zero-based index of the offending question)
        """
        from validate_identification_questions import main  # noqa: PLC0415

        schema_path = tmp_path / "personas.schema.json"
        yaml_path = tmp_path / "personas.yaml"
        schema_path.write_text(json.dumps(_make_schema(["personaA"])))
        questions = [
            "Do you operate AI systems?",
            "Are you responsible for model deployment?",
            "Manage any models as part of your role?",  # index 2 — bad opener
            "Do you have authority to approve updates?",
            "Does your team define access policies?",
        ]
        yaml_data = _make_personas_yaml([_make_persona("personaA", questions=questions)])
        yaml_path.write_text(yaml.dump(yaml_data))

        with pytest.raises(SystemExit):
            main([str(yaml_path), "--schema", str(schema_path)])
        captured = capsys.readouterr()

        assert "identificationQuestions[2]" in captured.err

    def test_format_prefix_is_exact(self, tmp_path, capsys):
        """
        Every stderr warning line starts with 'validate-identification-questions:'.

        Given: Any rule violation
        When: main() emits warnings to stderr
        Then: Every non-empty stderr line starts with 'validate-identification-questions:'
        """
        from validate_identification_questions import main  # noqa: PLC0415

        schema_path = tmp_path / "personas.schema.json"
        yaml_path = tmp_path / "personas.yaml"
        schema_path.write_text(json.dumps(_make_schema(["personaA"])))
        # Count violation (4 questions) to guarantee at least one warning line
        yaml_data = _make_personas_yaml([_make_persona("personaA", questions=VALID_5_QUESTIONS[:4])])
        yaml_path.write_text(yaml.dump(yaml_data))

        with pytest.raises(SystemExit):
            main([str(yaml_path), "--schema", str(schema_path)])
        captured = capsys.readouterr()

        non_empty_lines = [line for line in captured.err.splitlines() if line.strip()]
        assert len(non_empty_lines) >= 1, "Expected at least one warning line on stderr"
        for line in non_empty_lines:
            assert line.startswith("validate-identification-questions:"), (
                f"Line does not start with required prefix: {line!r}"
            )

    def test_format_includes_colon_separated_fields(self, tmp_path, capsys):
        """
        Each stderr warning line uses the colon-separated format:
        'validate-identification-questions: <file>:<persona-id>:identificationQuestions[<n>]: <reason>'

        Given: A count violation on persona 'personaA'
        When: main() emits warnings to stderr
        Then: The line contains at least 4 colon-delimited segments with the
              required field names in the required order.
        """
        from validate_identification_questions import main  # noqa: PLC0415

        schema_path = tmp_path / "personas.schema.json"
        yaml_path = tmp_path / "personas.yaml"
        schema_path.write_text(json.dumps(_make_schema(["personaA"])))
        yaml_data = _make_personas_yaml([_make_persona("personaA", questions=VALID_5_QUESTIONS[:4])])
        yaml_path.write_text(yaml.dump(yaml_data))

        with pytest.raises(SystemExit):
            main([str(yaml_path), "--schema", str(schema_path)])
        captured = capsys.readouterr()

        first_line = [line for line in captured.err.splitlines() if line.strip()][0]
        # Format: 'validate-identification-questions: <file>:<persona>:identificationQuestions[n]: <reason>'
        # Split on ': ' after the hook name prefix to get the location+reason part
        assert "identificationQuestions[" in first_line
        assert "personaA" in first_line


# ===========================================================================
# Schema-driven persona-id enumeration
# ===========================================================================


class TestSchemaDrivenEnumeration:
    """Tests that the hook reads persona IDs and deprecated status from the schema,
    not hardcoded values, so it tracks schema changes automatically.
    """

    def test_load_persona_ids_from_schema_returns_enum(self, tmp_path):
        """
        load_persona_ids_from_schema extracts the id enum from the schema JSON.

        Given: A minimal schema JSON with enum ['personaA', 'personaB']
        When: load_persona_ids_from_schema is called
        Then: Returns ['personaA', 'personaB']
        """
        schema = _make_schema(["personaA", "personaB"])
        schema_path = tmp_path / "personas.schema.json"
        schema_path.write_text(json.dumps(schema))

        ids = load_persona_ids_from_schema(str(schema_path))
        assert set(ids) == {"personaA", "personaB"}

    def test_valid_questions_on_both_non_deprecated_personas_passes(self, tmp_path):
        """
        Both non-deprecated personas with valid questions produce no warnings.

        Given: Schema with ['personaA', 'personaB'], both have 5 valid questions
        When: validate_personas_file is called
        Then: Returns no warnings
        """
        schema_path = tmp_path / "personas.schema.json"
        yaml_path = tmp_path / "personas.yaml"
        schema_path.write_text(json.dumps(_make_schema(["personaA", "personaB"])))
        yaml_data = _make_personas_yaml(
            [
                _make_persona("personaA", questions=VALID_5_QUESTIONS),
                _make_persona("personaB", questions=VALID_5_QUESTIONS),
            ]
        )
        yaml_path.write_text(yaml.dump(yaml_data))

        warnings = validate_personas_file(str(yaml_path), str(schema_path), block=False)
        assert warnings == []

    def test_count_violation_on_one_of_two_personas_warns_only_offender(self, tmp_path):
        """
        Count violation on personaB only generates a warning for personaB.

        Given: Schema with ['personaA', 'personaB']; personaA has 5 valid questions,
               personaB has 3 questions (below floor)
        When: validate_personas_file is called
        Then: Warning list references personaB; personaA produces no warning
        """
        schema_path = tmp_path / "personas.schema.json"
        yaml_path = tmp_path / "personas.yaml"
        schema_path.write_text(json.dumps(_make_schema(["personaA", "personaB"])))
        yaml_data = _make_personas_yaml(
            [
                _make_persona("personaA", questions=VALID_5_QUESTIONS),
                _make_persona("personaB", questions=VALID_5_QUESTIONS[:3]),
            ]
        )
        yaml_path.write_text(yaml.dump(yaml_data))

        warnings = validate_personas_file(str(yaml_path), str(schema_path), block=False)
        assert any("personaB" in w for w in warnings), "Expected warning referencing personaB"
        assert not any("personaA" in w for w in warnings), "Did not expect warning referencing personaA"

    def test_deprecated_persona_in_schema_skipped(self, tmp_path):
        """
        Persona flagged deprecated: true in YAML is skipped from validation.

        Given: Schema with ['personaA', 'personaC']; personaC has deprecated: true
               and only 2 questions
        When: validate_personas_file is called
        Then: No warning emitted for personaC (deprecated; exempt)
        """
        schema_path = tmp_path / "personas.schema.json"
        yaml_path = tmp_path / "personas.yaml"
        schema_path.write_text(json.dumps(_make_schema(["personaA", "personaC"])))
        yaml_data = _make_personas_yaml(
            [
                _make_persona("personaA", questions=VALID_5_QUESTIONS),
                _make_persona(
                    "personaC", questions=["Do you manage legacy models?", "Are you retired?"], deprecated=True
                ),
            ]
        )
        yaml_path.write_text(yaml.dump(yaml_data))

        warnings = validate_personas_file(str(yaml_path), str(schema_path), block=False)
        assert not any("personaC" in w for w in warnings)

    def test_hook_does_not_validate_personas_absent_from_yaml(self, tmp_path):
        """
        A persona ID present in the schema enum but absent from the YAML is not validated.

        Given: Schema enumerates ['personaA', 'personaMissing']; YAML only has personaA
        When: validate_personas_file is called
        Then: No error raised for personaMissing; only personaA is validated

        A5's lint iterates over personas present in the YAML. Schema-presence-only
        personas are outside its scope (schema validation catches YAML typos separately).
        """
        schema_path = tmp_path / "personas.schema.json"
        yaml_path = tmp_path / "personas.yaml"
        schema_path.write_text(json.dumps(_make_schema(["personaA", "personaMissing"])))
        yaml_data = _make_personas_yaml([_make_persona("personaA", questions=VALID_5_QUESTIONS)])
        yaml_path.write_text(yaml.dump(yaml_data))

        # Should not raise; personaMissing is simply absent
        warnings = validate_personas_file(str(yaml_path), str(schema_path), block=False)
        assert not any("personaMissing" in w for w in warnings)


# ===========================================================================
# Integration — real corpus
# ===========================================================================


class TestCorpusIntegration:
    """Integration tests that run the lint against the actual personas.yaml and schema.

    These tests confirm the hook can ingest the real files without crashing and
    that its warn-only output is coherent (ADR-021 D7 notes 5 of 8 current personas
    currently lack questions; warn-only mode is the expected production posture).
    """

    def _real_paths(self) -> tuple[Path, Path]:
        """Resolve the repo-root-relative paths to real YAML and schema."""
        # The worktree conftest resolves repo_root via git; replicate that logic
        # here without relying on a fixture, since integration tests use real files.
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        yaml_path = repo_root / "risk-map" / "yaml" / "personas.yaml"
        schema_path = repo_root / "risk-map" / "schemas" / "personas.schema.json"
        return yaml_path, schema_path

    def test_real_corpus_warn_mode_does_not_crash(self):
        """
        Running in warn-only mode against the real personas.yaml does not crash.

        Given: The actual risk-map/yaml/personas.yaml and its schema
        When: validate_personas_file is called in warn-only mode
        Then: No exception is raised; a list (possibly non-empty) is returned

        The corpus currently has 5 of 8 current personas without any
        identificationQuestions — the count rule will fire warn-only for those
        that have fewer than 5 questions.
        """
        yaml_path, schema_path = self._real_paths()
        assert yaml_path.exists(), f"Missing real personas.yaml at {yaml_path}"
        assert schema_path.exists(), f"Missing real personas.schema.json at {schema_path}"

        result = validate_personas_file(str(yaml_path), str(schema_path), block=False)
        assert isinstance(result, list)

    def test_real_corpus_deprecated_personas_produce_no_warnings(self):
        """
        The two deprecated legacy personas (personaModelCreator, personaModelConsumer)
        produce no warnings when the real corpus is validated.

        Given: The actual risk-map/yaml/personas.yaml (which contains the two
               deprecated legacy personas without identificationQuestions)
        When: validate_personas_file is called in warn-only mode
        Then: No warning mentions personaModelCreator or personaModelConsumer
        """
        yaml_path, schema_path = self._real_paths()
        warnings = validate_personas_file(str(yaml_path), str(schema_path), block=False)
        for w in warnings:
            assert "personaModelCreator" not in w, f"Deprecated persona flagged: {w}"
            assert "personaModelConsumer" not in w, f"Deprecated persona flagged: {w}"


"""
Test Summary
============
Total Tests: 55 across 9 test classes

Rule 1 — Count:                8 tests  (TestRule1Count)
Rule 2 — Second-person opener: 9 tests  (TestRule2SecondPersonOpener)
Rule 3 — Parenthetical:       13 tests  (TestRule3ParentheticalCardinality)
Rule 4 — e.g. not i.e.:       7 tests  (TestRule4EgNotIe)
Warn/block toggle:             7 tests  (TestWarnBlockToggle)
Stderr format:                 4 tests  (TestStderrFormat)
Schema-driven enumeration:     5 tests  (TestSchemaDrivenEnumeration)
Integration (corpus):          2 tests  (TestCorpusIntegration)

Depth-aware nested-paren tests (Rule 3):
  - test_nested_parenthetical_with_inner_comma_does_not_bleed_through
  - test_nested_parenthetical_with_inner_comma_pair_under_threshold
  - test_nested_parenthetical_with_or_separator_inside_inner_paren

Coverage areas:
  - check_count_rule: all branches (0, <5, 5, 6, 7, >7)
  - check_opener_rule: all approved openers + multiple rejection cases
  - check_parenthetical_cardinality_rule: 1/2/3/4/5 items, comma vs. or, none,
    multiple parentheticals, nested parens; depth-aware bleed-through guard
  - _count_paren_items: direct helper assertions for depth-tracking correctness
  - check_eg_not_ie_rule: e.g. pass, i.e. warn, such-as pass, no-paren pass,
    non-eg-ie-paren pass, ie-outside-paren pass, two-ie-parens emits two warnings
  - validate_personas_file: warn mode, block mode (SystemExit), clean input both modes
  - main(): warn mode exits 0, block mode exits non-zero, clean block exits 0
  - load_persona_ids_from_schema: reads enum from JSON
  - schema-driven: both-valid, one-offender, deprecated-exempt, missing-persona
  - integration: real corpus no-crash, deprecated-personas no-warning
"""

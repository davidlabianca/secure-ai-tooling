#!/usr/bin/env python3
"""
Tests for A7 sentinel expansion in PersonaSummaryTableGenerator and
PersonaFullDetailTableGenerator (scripts/hooks/yaml_to_markdown.py).

This file closes the same-file consistency gap identified in the A8 lesson:
commit 2 wired FullDetailTableGenerator and SummaryTableGenerator but left both
persona-specific generators unwired. This test suite pins the missing contracts
before the SWE wires them.

Contracts pinned by this test suite:

PersonaSummaryTableGenerator.generate wiring (tasks 2.5.1 + 2.5.3):
  - Passes self.intra_lookup and a per-row ref_lookup to collapse_column when
    expanding description.  field_path uses "personas[N].description" form.
  - When lookups are None (default), sentinels pass through unchanged —
    backward-compat baseline.
  - An unresolved sentinel raises UnresolvedSentinelError; it is never swallowed.
  - Emits "## References for {persona-id}" sub-section after the main table
    for any persona with a non-empty externalReferences array.

PersonaFullDetailTableGenerator.generate wiring (tasks 2.5.1 + 2.5.3):
  - Same collapse_column wiring for description.
  - Per-item expand_sentinels_to_text applied to each string in responsibilities
    and identificationQuestions before passing to format_list.
    field_path per item: "personas[N].responsibilities[M]" or
    "personas[N].identificationQuestions[M]".
  - None lookups preserve pre-A7 passthrough for all three field paths.
  - UnresolvedSentinelError propagates from responsibilities and questions paths
    (the critical task 2.5.3 gap for non-description fields).
  - Same ## References for {persona-id} sub-section contract.

field_path format contract:
  - description: "personas[N].description"
  - responsibilities item M: "personas[N].responsibilities[M]"
  - identificationQuestions item M: "personas[N].identificationQuestions[M]"
  N and M are zero-based row/item indices (positional; entry id not required).

Wire-format sentinels used in fixtures (real tokenizer form):
  - {{controlInputValidationAndSanitization}}   intra, control
  - {{riskPromptInjection}}                     intra, risk
  - {{componentModelServing}}                   intra, component
  - {{ref:cwe-89}}                              external
  - {{ref:zhou-2023-poisoning}}                 external

Do NOT use {{idXxx}} meta-notation — that is ADR-016 meta, not wire format.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Decoupled imports: mirrors the A3 pattern in test_prose_tokens.py and the
# A7 commit-2 pattern in test_yaml_to_markdown_sentinel_expansion.py.
# If the sentinel helper fails to import, individual tests fail with a clear
# message rather than aborting the whole collection.
# ---------------------------------------------------------------------------

_SENTINEL_MODULE_ERROR: ImportError | None = None
try:
    from scripts.hooks._sentinel_expansion import UnresolvedSentinelError  # noqa: E402
except ImportError as _e:
    _SENTINEL_MODULE_ERROR = _e
    UnresolvedSentinelError = None  # type: ignore[assignment,misc]

# yaml_to_markdown exists pre-A7; the symbol lookups below fail at test-call
# time (not at collection time) if the persona generators are missing.
import scripts.hooks.yaml_to_markdown as _ytm  # noqa: E402

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _require_sentinel_module() -> None:
    """Fail clearly if the sentinel helper module is not importable."""
    if _SENTINEL_MODULE_ERROR is not None:
        pytest.fail(f"scripts/hooks/_sentinel_expansion.py is not importable: {_SENTINEL_MODULE_ERROR}")


def _get_persona_summary_generator():
    """Return PersonaSummaryTableGenerator class; fails if not present."""
    cls = getattr(_ytm, "PersonaSummaryTableGenerator", None)
    if cls is None:
        pytest.fail("yaml_to_markdown.PersonaSummaryTableGenerator is not defined")
    return cls


def _get_persona_full_detail_generator():
    """Return PersonaFullDetailTableGenerator class; fails if not present."""
    cls = getattr(_ytm, "PersonaFullDetailTableGenerator", None)
    if cls is None:
        pytest.fail("yaml_to_markdown.PersonaFullDetailTableGenerator is not defined")
    return cls


# ---------------------------------------------------------------------------
# Shared lookup fixtures used across test classes
# ---------------------------------------------------------------------------

_INTRA_LOOKUP = {
    "controlInputValidationAndSanitization": "Input Validation And Sanitization",
    "riskPromptInjection": "Prompt Injection",
    "componentModelServing": "Model Serving Infrastructure",
}

_REF_LOOKUP = {
    "cwe-89": {
        "title": "CWE-89: Improper Neutralization of SQL Commands",
        "url": "https://cwe.mitre.org/data/definitions/89.html",
    },
    "zhou-2023-poisoning": {
        "title": "Zhou et al. 2023 - Data Poisoning",
        "url": "https://example.com/zhou-2023",
    },
}


def _make_persona(
    pid: str = "personaTestAlpha",
    title: str = "Test Alpha Persona",
    description: str = "A plain description with no sentinels.",
    responsibilities: list[str] | None = None,
    identification_questions: list[str] | None = None,
    external_references: list[dict] | None = None,
    deprecated: bool = False,
) -> dict:
    """Return a minimal persona dict suitable for both persona generators."""
    p: dict = {
        "id": pid,
        "title": title,
        "description": description,
        "deprecated": deprecated,
        "responsibilities": responsibilities if responsibilities is not None else [],
        "identificationQuestions": (identification_questions if identification_questions is not None else []),
        "mappings": {},
    }
    if external_references is not None:
        p["externalReferences"] = external_references
    return p


def _make_personas_yaml(*personas) -> dict:
    """Wrap one or more persona dicts in the top-level YAML structure."""
    return {"personas": list(personas)}


# ============================================================================
# TestPersonaSummarySentinelExpansion
# ============================================================================


class TestPersonaSummarySentinelExpansion:
    """
    Tests for sentinel expansion in PersonaSummaryTableGenerator.generate().

    The generator reads description via collapse_column.  When lookups are None
    (the default), sentinels pass through unchanged.  When intra_lookup and
    ref_lookup are set on the instance, sentinels are expanded and unresolved
    ones raise UnresolvedSentinelError.  A ## References for {id} sub-section
    is appended for personas with a non-empty externalReferences array.
    """

    def test_no_lookups_preserves_legacy_passthrough(self):
        """
        Baseline: no-kwargs construction passes description sentinels through verbatim.

        Given: PersonaSummaryTableGenerator() with no lookup kwargs; persona description
               containing {{controlFoo}} (arbitrary sentinel placeholder)
        When: generate() is called
        Then: The sentinel text appears verbatim in the output (not resolved, no error)

        This is the backward-compat contract: pre-A7 call sites omit lookups
        and must keep working without change.
        """
        gen_cls = _get_persona_summary_generator()
        yaml_data = _make_personas_yaml(
            _make_persona(description="See {{controlInputValidationAndSanitization}} for details.")
        )
        gen = gen_cls()
        output = gen.generate(yaml_data, "personas")
        assert "{{controlInputValidationAndSanitization}}" in output

    def test_intra_sentinel_in_description_resolves(self):
        """
        Intra sentinel in description expands to plain title when lookups are supplied.

        Given: PersonaSummaryTableGenerator(intra_lookup=..., ref_lookup={})
               persona description "See {{controlInputValidationAndSanitization}} for details."
        When: generate() is called
        Then: Output contains "Input Validation And Sanitization" (the resolved title)
              and does NOT contain the raw sentinel span
        """
        _require_sentinel_module()
        gen_cls = _get_persona_summary_generator()
        yaml_data = _make_personas_yaml(
            _make_persona(description="See {{controlInputValidationAndSanitization}} for details.")
        )
        gen = gen_cls(intra_lookup=_INTRA_LOOKUP, ref_lookup={})
        output = gen.generate(yaml_data, "personas")
        assert "Input Validation And Sanitization" in output
        assert "{{controlInputValidationAndSanitization}}" not in output

    def test_ref_sentinel_in_description_resolves(self):
        """
        External-reference sentinel in description expands to a markdown link.

        Given: PersonaSummaryTableGenerator(intra_lookup={}, ref_lookup=...)
               persona description "See {{ref:cwe-89}}."
        When: generate() is called
        Then: Output contains the linked title and url, not the raw sentinel span
        """
        _require_sentinel_module()
        gen_cls = _get_persona_summary_generator()
        yaml_data = _make_personas_yaml(_make_persona(description="See {{ref:cwe-89}}."))
        gen = gen_cls(intra_lookup={}, ref_lookup=_REF_LOOKUP)
        output = gen.generate(yaml_data, "personas")
        assert "[CWE-89: Improper Neutralization of SQL Commands]" in output
        assert "https://cwe.mitre.org/data/definitions/89.html" in output
        assert "{{ref:cwe-89}}" not in output

    def test_unresolved_intra_sentinel_raises(self):
        """
        UnresolvedSentinelError propagates from description when the intra id is missing.

        Given: PersonaSummaryTableGenerator(intra_lookup={}, ref_lookup={})
               persona description "Mentions {{controlBogus}}."
        When: generate() is called
        Then: UnresolvedSentinelError is raised with .sentinel == "{{controlBogus}}"
        """
        _require_sentinel_module()
        gen_cls = _get_persona_summary_generator()
        yaml_data = _make_personas_yaml(_make_persona(description="Mentions {{controlBogus}}."))
        gen = gen_cls(intra_lookup={}, ref_lookup={})
        with pytest.raises(UnresolvedSentinelError) as exc_info:
            gen.generate(yaml_data, "personas")
        assert exc_info.value.sentinel == "{{controlBogus}}"

    def test_unresolved_ref_sentinel_raises(self):
        """
        UnresolvedSentinelError propagates from description when ref id is missing.

        Given: PersonaSummaryTableGenerator(intra_lookup={}, ref_lookup={})
               persona description "See {{ref:cve-2024-99999}}."
        When: generate() is called
        Then: UnresolvedSentinelError is raised with .sentinel == "{{ref:cve-2024-99999}}"
        """
        _require_sentinel_module()
        gen_cls = _get_persona_summary_generator()
        yaml_data = _make_personas_yaml(_make_persona(description="See {{ref:cve-2024-99999}}."))
        gen = gen_cls(intra_lookup={}, ref_lookup={})
        with pytest.raises(UnresolvedSentinelError) as exc_info:
            gen.generate(yaml_data, "personas")
        assert exc_info.value.sentinel == "{{ref:cve-2024-99999}}"

    def test_external_references_sub_section_emitted(self):
        """
        ## References for {persona-id} sub-section appears after the table when
        externalReferences is non-empty.

        Given: PersonaSummaryTableGenerator(); persona "personaWithRefs" having
               externalReferences=[{type: "cwe", id: "cwe-89", title: "CWE-89",
               url: "https://example.com/cwe-89"}]
        When: generate() is called
        Then: Output contains "## References for personaWithRefs" AFTER the table
              followed by a bullet "- [CWE-89](https://example.com/cwe-89) (cwe)"
        """
        gen_cls = _get_persona_summary_generator()
        refs = [{"type": "cwe", "id": "cwe-89", "title": "CWE-89", "url": "https://example.com/cwe-89"}]
        yaml_data = _make_personas_yaml(_make_persona(pid="personaWithRefs", external_references=refs))
        gen = gen_cls()
        output = gen.generate(yaml_data, "personas")

        assert "## References for personaWithRefs" in output
        # Sub-section is after the table (after the last "|" in the markdown table)
        table_end_idx = output.rfind("|")
        refs_idx = output.index("## References for personaWithRefs")
        assert refs_idx > table_end_idx, (
            f"## References section (pos {refs_idx}) must appear after the last table pipe (pos {table_end_idx})"
        )
        # Bullet contains title as link and type in parens
        assert "- [CWE-89](https://example.com/cwe-89) (cwe)" in output

    def test_no_external_references_no_sub_section(self):
        """
        No ## References for header when persona has no externalReferences field.

        Given: PersonaSummaryTableGenerator(); persona with no externalReferences key
        When: generate() is called
        Then: "## References for" does NOT appear anywhere in the output
        """
        gen_cls = _get_persona_summary_generator()
        yaml_data = _make_personas_yaml(_make_persona(pid="personaNoRefs"))
        gen = gen_cls()
        output = gen.generate(yaml_data, "personas")
        assert "## References for" not in output

    def test_multiple_personas_each_get_their_own_section(self):
        """
        Two personas with externalReferences each get a distinct ## References for section.

        Given: PersonaSummaryTableGenerator(); two personas "personaAlpha" and "personaBeta",
               each with one externalReferences entry
        When: generate() is called
        Then: Output contains both "## References for personaAlpha" and
              "## References for personaBeta"
        """
        gen_cls = _get_persona_summary_generator()
        refs_alpha = [{"type": "cwe", "id": "cwe-1", "title": "CWE-1", "url": "https://example.com/1"}]
        refs_beta = [{"type": "paper", "id": "paper-2", "title": "Paper 2", "url": "https://example.com/2"}]
        yaml_data = _make_personas_yaml(
            _make_persona(pid="personaAlpha", external_references=refs_alpha),
            _make_persona(pid="personaBeta", external_references=refs_beta),
        )
        gen = gen_cls()
        output = gen.generate(yaml_data, "personas")
        assert "## References for personaAlpha" in output
        assert "## References for personaBeta" in output


# ============================================================================
# TestPersonaFullDetailSentinelExpansion
# ============================================================================


class TestPersonaFullDetailSentinelExpansion:
    """
    Tests for sentinel expansion in PersonaFullDetailTableGenerator.generate().

    Beyond description (same contract as PersonaSummaryTableGenerator), the full
    detail generator also reads responsibilities[] and identificationQuestions[].
    Both are arrays of strings; each element must be expanded via
    expand_sentinels_to_text before being passed to format_list.

    The task 2.5.3 hard-fail gate requires UnresolvedSentinelError to propagate
    from responsibilities and identificationQuestions paths — currently they use
    bare format_list with no sentinel awareness, so the raises tests are RED.
    """

    def test_no_lookups_preserves_legacy_passthrough(self):
        """
        Baseline: no-kwargs construction passes sentinels through verbatim in all fields.

        Given: PersonaFullDetailTableGenerator() with no lookup kwargs;
               description, responsibilities, and identificationQuestions each
               containing sentinel-like text
        When: generate() is called
        Then: None of the fields cause an error; sentinel text passes through
        """
        gen_cls = _get_persona_full_detail_generator()
        yaml_data = _make_personas_yaml(
            _make_persona(
                description="See {{controlInputValidationAndSanitization}}.",
                responsibilities=["Use {{controlInputValidationAndSanitization}} on inputs."],
                identification_questions=["Does {{riskPromptInjection}} apply?"],
            )
        )
        gen = gen_cls()
        # Should not raise; sentinels pass through verbatim
        output = gen.generate(yaml_data, "personas")
        assert "{{controlInputValidationAndSanitization}}" in output

    def test_intra_sentinel_in_description_resolves(self):
        """
        Intra sentinel in description expands to plain title for full-detail generator.

        This tests a different code path from PersonaSummaryTableGenerator; both
        must be wired independently.

        Given: PersonaFullDetailTableGenerator(intra_lookup=..., ref_lookup={})
               persona description "Use {{controlInputValidationAndSanitization}} here."
        When: generate() is called
        Then: Output contains "Input Validation And Sanitization"; sentinel absent
        """
        _require_sentinel_module()
        gen_cls = _get_persona_full_detail_generator()
        yaml_data = _make_personas_yaml(
            _make_persona(description="Use {{controlInputValidationAndSanitization}} here.")
        )
        gen = gen_cls(intra_lookup=_INTRA_LOOKUP, ref_lookup={})
        output = gen.generate(yaml_data, "personas")
        assert "Input Validation And Sanitization" in output
        assert "{{controlInputValidationAndSanitization}}" not in output

    def test_ref_sentinel_in_description_resolves(self):
        """
        External-reference sentinel in description expands to markdown link.

        Given: PersonaFullDetailTableGenerator(intra_lookup={}, ref_lookup=...)
               persona description "See {{ref:cwe-89}}."
        When: generate() is called
        Then: Output contains [CWE-89: ...](url) and NOT the raw sentinel
        """
        _require_sentinel_module()
        gen_cls = _get_persona_full_detail_generator()
        yaml_data = _make_personas_yaml(_make_persona(description="See {{ref:cwe-89}}."))
        gen = gen_cls(intra_lookup={}, ref_lookup=_REF_LOOKUP)
        output = gen.generate(yaml_data, "personas")
        assert "[CWE-89: Improper Neutralization of SQL Commands]" in output
        assert "https://cwe.mitre.org/data/definitions/89.html" in output
        assert "{{ref:cwe-89}}" not in output

    def test_intra_sentinel_in_responsibilities_resolves(self):
        """
        Intra sentinel inside a responsibilities[] string expands to plain title.

        Given: PersonaFullDetailTableGenerator(intra_lookup=..., ref_lookup={})
               responsibilities=["Use {{controlInputValidationAndSanitization}} on all inputs."]
        When: generate() is called
        Then: The Responsibilities column cell in the table output contains
              "Input Validation And Sanitization" and NOT the raw sentinel
        """
        _require_sentinel_module()
        gen_cls = _get_persona_full_detail_generator()
        yaml_data = _make_personas_yaml(
            _make_persona(responsibilities=["Use {{controlInputValidationAndSanitization}} on all inputs."])
        )
        gen = gen_cls(intra_lookup=_INTRA_LOOKUP, ref_lookup={})
        output = gen.generate(yaml_data, "personas")
        assert "Input Validation And Sanitization" in output
        assert "{{controlInputValidationAndSanitization}}" not in output

    def test_ref_sentinel_in_responsibilities_resolves(self):
        """
        External-reference sentinel inside a responsibilities[] string expands to link.

        Given: PersonaFullDetailTableGenerator(intra_lookup={}, ref_lookup=...)
               responsibilities=["Comply with {{ref:cwe-89}} classification."]
        When: generate() is called
        Then: Output's Responsibilities cell contains the markdown link text
        """
        _require_sentinel_module()
        gen_cls = _get_persona_full_detail_generator()
        yaml_data = _make_personas_yaml(
            _make_persona(responsibilities=["Comply with {{ref:cwe-89}} classification."])
        )
        gen = gen_cls(intra_lookup={}, ref_lookup=_REF_LOOKUP)
        output = gen.generate(yaml_data, "personas")
        assert "[CWE-89: Improper Neutralization of SQL Commands]" in output
        assert "{{ref:cwe-89}}" not in output

    def test_intra_sentinel_in_identification_questions_resolves(self):
        """
        Intra sentinel inside an identificationQuestions[] entry resolves to title.

        Given: PersonaFullDetailTableGenerator(intra_lookup=..., ref_lookup={})
               identificationQuestions=["Does {{riskPromptInjection}} affect this role?"]
        When: generate() is called
        Then: Output contains "Prompt Injection"; raw sentinel absent
        """
        _require_sentinel_module()
        gen_cls = _get_persona_full_detail_generator()
        yaml_data = _make_personas_yaml(
            _make_persona(identification_questions=["Does {{riskPromptInjection}} affect this role?"])
        )
        gen = gen_cls(intra_lookup=_INTRA_LOOKUP, ref_lookup={})
        output = gen.generate(yaml_data, "personas")
        assert "Prompt Injection" in output
        assert "{{riskPromptInjection}}" not in output

    def test_unresolved_sentinel_in_responsibilities_raises(self):
        """
        CRITICAL task 2.5.3 gate: UnresolvedSentinelError propagates from
        the responsibilities path (currently uses bare format_list — no expansion).

        Given: PersonaFullDetailTableGenerator(intra_lookup={}, ref_lookup={})
               responsibilities=["Apply {{controlBogusTypo}} everywhere."]
               (no matching id in intra_lookup)
        When: generate() is called
        Then: UnresolvedSentinelError is raised with .sentinel == "{{controlBogusTypo}}"

        Currently FAILS because the responsibilities path uses bare format_list
        with no sentinel expansion.
        """
        _require_sentinel_module()
        gen_cls = _get_persona_full_detail_generator()
        yaml_data = _make_personas_yaml(_make_persona(responsibilities=["Apply {{controlBogusTypo}} everywhere."]))
        gen = gen_cls(intra_lookup={}, ref_lookup={})
        with pytest.raises(UnresolvedSentinelError) as exc_info:
            gen.generate(yaml_data, "personas")
        assert exc_info.value.sentinel == "{{controlBogusTypo}}"

    def test_unresolved_sentinel_in_identification_questions_raises(self):
        """
        CRITICAL task 2.5.3 gate: UnresolvedSentinelError propagates from
        the identificationQuestions path (currently uses bare format_list — no expansion).

        Given: PersonaFullDetailTableGenerator(intra_lookup={}, ref_lookup={})
               identificationQuestions=["Does {{riskBadTypo}} apply here?"]
               (no matching id in intra_lookup)
        When: generate() is called
        Then: UnresolvedSentinelError is raised with .sentinel == "{{riskBadTypo}}"

        Currently FAILS because the identificationQuestions path uses bare format_list
        with no sentinel expansion.
        """
        _require_sentinel_module()
        gen_cls = _get_persona_full_detail_generator()
        yaml_data = _make_personas_yaml(
            _make_persona(identification_questions=["Does {{riskBadTypo}} apply here?"])
        )
        gen = gen_cls(intra_lookup={}, ref_lookup={})
        with pytest.raises(UnresolvedSentinelError) as exc_info:
            gen.generate(yaml_data, "personas")
        assert exc_info.value.sentinel == "{{riskBadTypo}}"

    def test_external_references_sub_section_emitted(self):
        """
        ## References for {persona-id} sub-section appears after the table.

        Given: PersonaFullDetailTableGenerator(); persona "personaFullWithRefs"
               with externalReferences=[{cwe entry}]
        When: generate() is called
        Then: Output contains "## References for personaFullWithRefs" after the table
        """
        gen_cls = _get_persona_full_detail_generator()
        refs = [{"type": "cwe", "id": "cwe-89", "title": "CWE-89", "url": "https://example.com/cwe-89"}]
        yaml_data = _make_personas_yaml(_make_persona(pid="personaFullWithRefs", external_references=refs))
        gen = gen_cls()
        output = gen.generate(yaml_data, "personas")

        assert "## References for personaFullWithRefs" in output
        table_end_idx = output.rfind("|")
        refs_idx = output.index("## References for personaFullWithRefs")
        assert refs_idx > table_end_idx, (
            f"## References section (pos {refs_idx}) must appear after the last table pipe (pos {table_end_idx})"
        )

    def test_no_external_references_no_sub_section(self):
        """
        No ## References for header when persona has no externalReferences field.

        Given: PersonaFullDetailTableGenerator(); persona with no externalReferences key
        When: generate() is called
        Then: "## References for" does NOT appear anywhere in the output
        """
        gen_cls = _get_persona_full_detail_generator()
        yaml_data = _make_personas_yaml(_make_persona(pid="personaFullNoRefs"))
        gen = gen_cls()
        output = gen.generate(yaml_data, "personas")
        assert "## References for" not in output

    def test_field_path_in_unresolved_error_is_informative(self):
        """
        field_path in UnresolvedSentinelError identifies the offending location.

        Three sub-cases:
        A. Typo in description → field_path contains "personas" and "description"
        B. Typo in responsibilities[1] → field_path contains "personas" and
           "responsibilities" with a positional index
        C. Typo in identificationQuestions[0] → field_path contains "personas" and
           "identificationQuestions" with a positional index

        Given: PersonaFullDetailTableGenerator(intra_lookup={}, ref_lookup={})
        When: generate() raises UnresolvedSentinelError
        Then: exc.field_path is non-empty and contains the field name for all three paths
        """
        _require_sentinel_module()
        gen_cls = _get_persona_full_detail_generator()

        # Sub-case A: description
        yaml_data_a = _make_personas_yaml(_make_persona(description="Bad {{controlTypoInDesc}} here."))
        gen_a = gen_cls(intra_lookup={}, ref_lookup={})
        with pytest.raises(UnresolvedSentinelError) as exc_a:
            gen_a.generate(yaml_data_a, "personas")
        assert exc_a.value.field_path, "field_path must be non-empty for description error"
        assert "personas" in exc_a.value.field_path
        assert "description" in exc_a.value.field_path

        # Sub-case B: responsibilities (second item, index 1)
        yaml_data_b = _make_personas_yaml(
            _make_persona(
                responsibilities=[
                    "First responsibility (clean).",
                    "Second has {{controlTypoInResp}} typo.",
                ]
            )
        )
        gen_b = gen_cls(intra_lookup={}, ref_lookup={})
        with pytest.raises(UnresolvedSentinelError) as exc_b:
            gen_b.generate(yaml_data_b, "personas")
        assert exc_b.value.field_path, "field_path must be non-empty for responsibilities error"
        assert "personas" in exc_b.value.field_path
        assert "responsibilities" in exc_b.value.field_path

        # Sub-case C: identificationQuestions (first item, index 0)
        yaml_data_c = _make_personas_yaml(
            _make_persona(identification_questions=["Does {{riskTypoInIdQ}} apply?"])
        )
        gen_c = gen_cls(intra_lookup={}, ref_lookup={})
        with pytest.raises(UnresolvedSentinelError) as exc_c:
            gen_c.generate(yaml_data_c, "personas")
        assert exc_c.value.field_path, "field_path must be non-empty for identificationQuestions error"
        assert "personas" in exc_c.value.field_path
        assert "identificationQuestions" in exc_c.value.field_path


# ============================================================================
# TestPersonaFieldPathFormat
# ============================================================================


class TestPersonaFieldPathFormat:
    """
    Contracts on the exact shape of field_path strings emitted by both persona
    generators.

    These tests assert that:
    - description errors reference "personas[N]" and "description" where N is
      the zero-based row index.
    - responsibilities errors reference "personas[N]" and "responsibilities[M]"
      where M is the zero-based item index.
    """

    def test_field_path_for_description_uses_personas_index(self):
        """
        Typo in persona[2]'s description → field_path contains "personas[2]" and "description".

        Given: PersonaFullDetailTableGenerator(intra_lookup={}, ref_lookup={})
               three personas; the third (index 2) has {{controlTypoDesc}} in description
        When: generate() raises UnresolvedSentinelError
        Then: exc.field_path contains "personas[2]" and "description"

        Note: A7's commit-2 generators emit field_path against the input
        (insertion-order) index, not the sorted-by-id index. This fixture's
        ids are pre-sorted so the assertion is robust to either contract,
        but the SWE should match the established insertion-order convention.
        """
        _require_sentinel_module()
        gen_cls = _get_persona_full_detail_generator()

        # Use alphabetically ordered ids so sorted position is predictable:
        # personaA → index 0, personaB → index 1, personaC → index 2
        yaml_data = _make_personas_yaml(
            _make_persona(pid="personaA", description="Clean description for A."),
            _make_persona(pid="personaB", description="Clean description for B."),
            _make_persona(pid="personaC", description="Has {{controlTypoDesc}} at index 2."),
        )
        gen = gen_cls(intra_lookup={}, ref_lookup={})
        with pytest.raises(UnresolvedSentinelError) as exc_info:
            gen.generate(yaml_data, "personas")
        exc = exc_info.value
        assert exc.field_path, "field_path must be non-empty"
        assert "personas[2]" in exc.field_path, (
            f"Expected 'personas[2]' in field_path for third persona's description; got: {exc.field_path!r}"
        )
        assert "description" in exc.field_path

    def test_field_path_for_responsibilities_includes_item_index(self):
        """
        Typo in persona[0].responsibilities[3] → field_path contains "personas[0]"
        and "responsibilities[3]".

        Given: PersonaFullDetailTableGenerator(intra_lookup={}, ref_lookup={})
               single persona (index 0) with 4 responsibilities; only the fourth
               (index 3) contains {{controlTypoResp}}
        When: generate() raises UnresolvedSentinelError
        Then: exc.field_path contains "personas[0]" and "responsibilities[3]"
        """
        _require_sentinel_module()
        gen_cls = _get_persona_full_detail_generator()
        yaml_data = _make_personas_yaml(
            _make_persona(
                pid="personaOnlyOne",
                responsibilities=[
                    "First clean responsibility.",
                    "Second clean responsibility.",
                    "Third clean responsibility.",
                    "Fourth has {{controlTypoResp}} typo.",
                ],
            )
        )
        gen = gen_cls(intra_lookup={}, ref_lookup={})
        with pytest.raises(UnresolvedSentinelError) as exc_info:
            gen.generate(yaml_data, "personas")
        exc = exc_info.value
        assert exc.field_path, "field_path must be non-empty"
        assert "personas[0]" in exc.field_path, f"Expected 'personas[0]' in field_path; got: {exc.field_path!r}"
        assert "responsibilities[3]" in exc.field_path, (
            f"Expected 'responsibilities[3]' in field_path; got: {exc.field_path!r}"
        )


# ============================================================================
# TestPersonaSentinelBackwardCompat
# ============================================================================


class TestPersonaSentinelBackwardCompat:
    """
    Backward-compatibility guard using the live corpus.

    The current personas.yaml contains no sentinel spans (zero {{...}} markers
    in prose fields). Both persona generators must produce identical output
    whether or not lookups are supplied — the no-kwargs path must not regress
    when the same data flows through the post-A7 code.

    This test proves that Phase B B2 (corpus migration) has nothing to flip
    until actual sentinels are added to the live YAML.
    """

    def test_existing_persona_yaml_unchanged(self):
        """
        Live personas.yaml produces identical output with and without lookup kwargs.

        Given: The live risk-map/yaml/personas.yaml loaded from disk (has zero sentinels)
        When: Both PersonaSummaryTableGenerator and PersonaFullDetailTableGenerator
              are called once with no kwargs and once with non-None lookups
        Then: The no-kwargs output and the with-lookup output are identical for each
              generator — no regression from A7 wiring

        Path is relative to REPO_ROOT; the test skips if the file does not exist
        (CI running outside the full repo checkout).
        """
        import yaml as _yaml

        personas_path = REPO_ROOT / "risk-map" / "yaml" / "personas.yaml"
        if not personas_path.exists():
            pytest.skip(f"Live personas.yaml not found at {personas_path}; skipping corpus test")

        with open(personas_path, encoding="utf-8") as fh:
            yaml_data = _yaml.safe_load(fh)

        # PersonaSummaryTableGenerator
        sum_cls = _get_persona_summary_generator()
        gen_sum_no_lookup = sum_cls()
        gen_sum_with_lookup = sum_cls(intra_lookup=_INTRA_LOOKUP, ref_lookup=_REF_LOOKUP)

        out_sum_no = gen_sum_no_lookup.generate(yaml_data, "personas")
        out_sum_with = gen_sum_with_lookup.generate(yaml_data, "personas")
        assert out_sum_no == out_sum_with, (
            "PersonaSummaryTableGenerator output must be identical for no-lookup vs lookup "
            "when the corpus contains no sentinels"
        )

        # PersonaFullDetailTableGenerator
        full_cls = _get_persona_full_detail_generator()
        gen_full_no_lookup = full_cls()
        gen_full_with_lookup = full_cls(intra_lookup=_INTRA_LOOKUP, ref_lookup=_REF_LOOKUP)

        out_full_no = gen_full_no_lookup.generate(yaml_data, "personas")
        out_full_with = gen_full_with_lookup.generate(yaml_data, "personas")
        assert out_full_no == out_full_with, (
            "PersonaFullDetailTableGenerator output must be identical for no-lookup vs lookup "
            "when the corpus contains no sentinels"
        )


# ============================================================================
# Test Summary
# ============================================================================
"""
Test Summary
============
Total tests: 26

TestPersonaSummarySentinelExpansion (8):
  test_no_lookups_preserves_legacy_passthrough
  test_intra_sentinel_in_description_resolves
  test_ref_sentinel_in_description_resolves
  test_unresolved_intra_sentinel_raises
  test_unresolved_ref_sentinel_raises
  test_external_references_sub_section_emitted
  test_no_external_references_no_sub_section
  test_multiple_personas_each_get_their_own_section

TestPersonaFullDetailSentinelExpansion (11):
  test_no_lookups_preserves_legacy_passthrough
  test_intra_sentinel_in_description_resolves
  test_ref_sentinel_in_description_resolves
  test_intra_sentinel_in_responsibilities_resolves
  test_ref_sentinel_in_responsibilities_resolves
  test_intra_sentinel_in_identification_questions_resolves
  test_unresolved_sentinel_in_responsibilities_raises           ← task 2.5.3 RED
  test_unresolved_sentinel_in_identification_questions_raises   ← task 2.5.3 RED
  test_external_references_sub_section_emitted
  test_no_external_references_no_sub_section
  test_field_path_in_unresolved_error_is_informative

TestPersonaFieldPathFormat (2):
  test_field_path_for_description_uses_personas_index
  test_field_path_for_responsibilities_includes_item_index

TestPersonaSentinelBackwardCompat (1):
  test_existing_persona_yaml_unchanged

Coverage target: 90%+ on the A7 persona wiring in yaml_to_markdown.py

Key contracts pinned:
  - PersonaSummaryTableGenerator: collapse_column called with intra_lookup/ref_lookup for description
  - PersonaFullDetailTableGenerator: collapse_column for description; per-item
    expand_sentinels_to_text for responsibilities[] and identificationQuestions[]
  - Both generators emit ## References for {persona-id} sub-sections
  - field_path format: personas[N].description, personas[N].responsibilities[M],
    personas[N].identificationQuestions[M]
  - UnresolvedSentinelError propagates from all three field paths (never swallowed)
"""

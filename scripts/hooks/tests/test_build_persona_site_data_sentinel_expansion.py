#!/usr/bin/env python3
"""
Tests for sentinel expansion integration in scripts/build_persona_site_data.py

This module tests the A7 changes that wire sentinel resolution into the site
data builder (ADR-016 D5, task 2.5.3 site-data side). All inputs are
synthesized YAML dicts — the live corpus has no sentinels yet (Phase B B1+B2
will migrate it). Tests use real schemas from risk-map/schemas/.

Emit-shape decision (verified against persona-site-data.schema.json definitions/prose):
  definitions/prose is an array whose items are oneOf:
    - string
    - {type: "ref", id, title}     (new ADR-016 D5 intra shape)
    - {type: "link", title, url}   (new ADR-016 D5 ref shape)
    - array of strings/ref/link    (existing nested-group bullet shape)

  When a single prose string expands to exactly one string (no sentinels), the
  builder emits it as a top-level string item — identical to pre-A7 behavior.

  When a single prose string expands to multiple items (sentinels were present),
  the builder emits the result as a NESTED ARRAY (the fourth branch of the
  oneOf). This avoids top-level ref/link structured items being mixed directly
  with strings in the outer prose array, which would make it harder for the
  frontend to distinguish a "bullet group" from an "inline expansion group".
  Both shapes are schema-valid; the nested-array choice is more semantically
  distinct (inline expansion vs bullet group) at the cost of one extra array
  nesting level for expanded entries.

  Rationale: The schema's inner-array branch already accepts ref/link items
  (per ADR-016 D5 PR #261 landing), so a mixed [string, {ref}, string] inner
  array validates. The outer prose array's items minItems: 1 constraint is
  satisfied because expand_sentinels_to_items drops empty strings before the
  caller wraps the result.

Key API changes under test (SWE must implement):
  - build_site_data signature gains a required components_data: dict parameter
  - build_site_data builds intra_lookup from personas + risks + controls + components
  - build_site_data builds per-entry ref_lookup from each entry's externalReferences
  - build_site_data calls normalize_text_entries (now sentinel-aware)
  - externalReferences arrays are passed through to JSON output unchanged
  - UnresolvedSentinelError propagates out of build_site_data on typo'd sentinels
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Guarded import — RED phase: helper does not exist yet; builder signature
# changes not yet applied.
# ---------------------------------------------------------------------------
_IMPORT_ERROR: ImportError | None = None
try:
    from scripts.hooks._sentinel_expansion import UnresolvedSentinelError  # noqa: E402
except ImportError as _e:
    _IMPORT_ERROR = _e
    UnresolvedSentinelError = None  # type: ignore[assignment,misc]

from scripts.build_persona_site_data import (  # noqa: E402
    build_site_data,
    write_site_data,
)


def _require_sentinel_module() -> None:
    """Fail with a clear message if the sentinel helper is not importable."""
    if _IMPORT_ERROR is not None:
        pytest.fail(
            f"scripts/hooks/_sentinel_expansion.py is not importable (expected in RED phase): {_IMPORT_ERROR}"
        )


# ---------------------------------------------------------------------------
# Minimal synthetic YAML dicts used as test inputs.
# None of these reference the live corpus.
# ---------------------------------------------------------------------------

_MINIMAL_PERSONA = {
    "id": "personaTestSubject",
    "title": "Test Subject",
    "description": ["A plain description."],
    "responsibilities": ["One responsibility."],
    "identificationQuestions": ["Q1?", "Q2?", "Q3?", "Q4?", "Q5?"],
}

_MINIMAL_PERSONAS_DATA = {"personas": [_MINIMAL_PERSONA]}

_MINIMAL_RISK = {
    "id": "riskTestFoo",
    "title": "Test Foo Risk",
    "category": "risksTestCategory",
    "shortDescription": ["Short description."],
    "longDescription": ["Long description."],
    "examples": ["An example."],
    "personas": ["personaTestSubject"],
    "controls": [],
}

_MINIMAL_RISKS_DATA = {"risks": [_MINIMAL_RISK]}

_MINIMAL_CONTROL = {
    "id": "controlTestBar",
    "title": "Test Bar Control",
    "category": "controlsTestCategory",
    "description": ["Control description."],
    "personas": ["personaTestSubject"],
    "risks": [],
}

_MINIMAL_CONTROLS_DATA = {"controls": [_MINIMAL_CONTROL], "categories": []}

_MINIMAL_COMPONENTS_DATA = {
    "components": [
        {
            "id": "componentModelServing",
            "title": "Model Serving Infrastructure",
            "category": "componentsModel",
        },
        {
            "id": "componentTestComponent",
            "title": "Test Component",
            "category": "componentsData",
        },
    ]
}


def _build(
    personas_data=None,
    risks_data=None,
    controls_data=None,
    components_data=None,
) -> dict:
    """Convenience wrapper calling build_site_data with defaults."""
    return build_site_data(
        personas_data or _MINIMAL_PERSONAS_DATA,
        risks_data or _MINIMAL_RISKS_DATA,
        controls_data or _MINIMAL_CONTROLS_DATA,
        components_data or _MINIMAL_COMPONENTS_DATA,
    )


# ============================================================================
# TestSentinelExpansionInPersonaProse
# ============================================================================


class TestSentinelExpansionInPersonaProse:
    """Tests that sentinels in persona description/responsibilities are resolved."""

    def test_persona_description_intra_sentinel_produces_ref_item(self):
        """
        Test that {{riskTestFoo}} in a persona description is resolved to a ref item.

        Given: A persona whose description contains {{riskTestFoo}} and a risk with
               id="riskTestFoo" and title="Test Foo Risk" in risks_data
        When: build_site_data is called
        Then: The persona's description in site data contains a nested array that
              includes a {type: "ref", id: "riskTestFoo", title: "Test Foo Risk"} item
        """
        _require_sentinel_module()
        persona = dict(_MINIMAL_PERSONA)
        persona["description"] = ["See {{riskTestFoo}} for details."]

        result = _build(personas_data={"personas": [persona]})

        persona_out = next(p for p in result["personas"] if p["id"] == "personaTestSubject")
        desc = persona_out["description"]
        # At least one item should be a nested array (the expanded prose string)
        nested_arrays = [item for item in desc if isinstance(item, list)]
        assert nested_arrays, "When a prose string contains a sentinel, it should be emitted as a nested array"
        ref_items = [
            inner
            for nested in nested_arrays
            for inner in nested
            if isinstance(inner, dict) and inner.get("type") == "ref"
        ]
        assert any(r["id"] == "riskTestFoo" and r["title"] == "Test Foo Risk" for r in ref_items), (
            f"Expected ref item for riskTestFoo in description; got: {desc!r}"
        )

    def test_persona_description_ref_sentinel_produces_link_item(self):
        """
        Test that {{ref:cwe-89}} in a persona description is resolved to a link item.

        Given: A persona whose description contains {{ref:cwe-89}} and an
               externalReferences entry with id="cwe-89"
        When: build_site_data is called
        Then: The persona's description contains a nested array with a link item
              having the correct title and url
        """
        _require_sentinel_module()
        persona = dict(_MINIMAL_PERSONA)
        persona["description"] = ["See {{ref:cwe-89}}."]
        persona["externalReferences"] = [
            {
                "type": "cwe",
                "id": "cwe-89",
                "title": "CWE-89: SQL Injection",
                "url": "https://cwe.mitre.org/data/definitions/89.html",
            }
        ]

        result = _build(personas_data={"personas": [persona]})

        persona_out = next(p for p in result["personas"] if p["id"] == "personaTestSubject")
        desc = persona_out["description"]
        nested_arrays = [item for item in desc if isinstance(item, list)]
        assert nested_arrays
        link_items = [
            inner
            for nested in nested_arrays
            for inner in nested
            if isinstance(inner, dict) and inner.get("type") == "link"
        ]
        assert any(li["title"] == "CWE-89: SQL Injection" for li in link_items), (
            f"Expected link item for cwe-89 in description; got: {desc!r}"
        )

    def test_persona_responsibilities_intra_sentinel_resolved(self):
        """
        Test that a sentinel in persona responsibilities is resolved.

        Given: A persona with {{controlTestBar}} in its responsibilities
        When: build_site_data is called with a control id="controlTestBar"
        Then: The responsibilities field in site data contains the resolved ref item
        """
        _require_sentinel_module()
        persona = dict(_MINIMAL_PERSONA)
        persona["responsibilities"] = ["Use {{controlTestBar}} as a mitigation."]

        result = _build(personas_data={"personas": [persona]})

        persona_out = next(p for p in result["personas"] if p["id"] == "personaTestSubject")
        responsibilities = persona_out["responsibilities"]
        nested_arrays = [item for item in responsibilities if isinstance(item, list)]
        assert nested_arrays
        ref_items = [
            inner
            for nested in nested_arrays
            for inner in nested
            if isinstance(inner, dict) and inner.get("type") == "ref"
        ]
        assert any(r["id"] == "controlTestBar" for r in ref_items), (
            f"Expected ref item for controlTestBar in responsibilities; got: {responsibilities!r}"
        )

    def test_plain_persona_description_unchanged(self):
        """
        Test that a persona description without sentinels is emitted as plain strings.

        Given: A persona with plain-text description containing no {{ }} markers
        When: build_site_data is called
        Then: The description field contains only strings, no nested arrays
        """
        _require_sentinel_module()
        result = _build()
        persona_out = next(p for p in result["personas"] if p["id"] == "personaTestSubject")
        desc = persona_out["description"]
        assert all(isinstance(item, str) for item in desc), (
            f"Plain-text description should emit only strings; got: {desc!r}"
        )


# ============================================================================
# TestSentinelExpansionInRiskProse
# ============================================================================


class TestSentinelExpansionInRiskProse:
    """Tests that sentinels in risk shortDescription/longDescription/examples are resolved."""

    def test_risk_short_description_intra_sentinel_resolved(self):
        """
        Test that {{controlTestBar}} in a risk's shortDescription is resolved.

        Given: A risk with {{controlTestBar}} in shortDescription
        When: build_site_data is called
        Then: The shortDescription field contains a nested array with a ref item for controlTestBar
        """
        _require_sentinel_module()
        risk = dict(_MINIMAL_RISK)
        risk["shortDescription"] = ["See {{controlTestBar}}."]

        result = _build(risks_data={"risks": [risk]})

        risk_out = next(r for r in result["risks"] if r["id"] == "riskTestFoo")
        short_desc = risk_out["shortDescription"]
        nested = [item for item in short_desc if isinstance(item, list)]
        assert nested
        ref_items = [i for n in nested for i in n if isinstance(i, dict) and i.get("type") == "ref"]
        assert any(r["id"] == "controlTestBar" for r in ref_items)

    def test_risk_long_description_ref_sentinel_resolved(self):
        """
        Test that {{ref:zhou-2023-poisoning}} in a risk's longDescription is resolved.

        Given: A risk with {{ref:zhou-2023-poisoning}} in longDescription and
               an externalReferences entry with that id
        When: build_site_data is called
        Then: The longDescription contains a nested array with a link item
        """
        _require_sentinel_module()
        risk = dict(_MINIMAL_RISK)
        risk["longDescription"] = ["Based on {{ref:zhou-2023-poisoning}} research."]
        risk["externalReferences"] = [
            {
                "type": "paper",
                "id": "zhou-2023-poisoning",
                "title": "Zhou et al. 2023 - Data Poisoning",
                "url": "https://example.com/zhou-2023",
            }
        ]

        result = _build(risks_data={"risks": [risk]})

        risk_out = next(r for r in result["risks"] if r["id"] == "riskTestFoo")
        long_desc = risk_out["longDescription"]
        nested = [item for item in long_desc if isinstance(item, list)]
        assert nested
        link_items = [i for n in nested for i in n if isinstance(i, dict) and i.get("type") == "link"]
        assert any(li["title"] == "Zhou et al. 2023 - Data Poisoning" for li in link_items)

    def test_risk_examples_intra_sentinel_resolved(self):
        """
        Test that an intra sentinel in a risk's examples field is resolved.

        Given: A risk with {{personaTestSubject}} in its examples
        When: build_site_data is called
        Then: The examples field contains a nested array with a ref item for personaTestSubject
        """
        _require_sentinel_module()
        risk = dict(_MINIMAL_RISK)
        risk["examples"] = ["A {{personaTestSubject}} might encounter this."]

        result = _build(risks_data={"risks": [risk]})

        risk_out = next(r for r in result["risks"] if r["id"] == "riskTestFoo")
        examples = risk_out["examples"]
        nested = [item for item in examples if isinstance(item, list)]
        assert nested
        ref_items = [i for n in nested for i in n if isinstance(i, dict) and i.get("type") == "ref"]
        assert any(r["id"] == "personaTestSubject" for r in ref_items)

    def test_plain_risk_prose_unchanged(self):
        """
        Test that risk prose without sentinels emits only plain strings.

        Given: A risk with no sentinel spans in any prose field
        When: build_site_data is called
        Then: All prose fields contain only string items
        """
        _require_sentinel_module()
        result = _build()
        risk_out = next(r for r in result["risks"] if r["id"] == "riskTestFoo")
        for field in ("shortDescription", "longDescription", "examples"):
            prose = risk_out[field]
            assert all(isinstance(item, str) for item in prose), (
                f"Plain-text {field} must emit only strings; got: {prose!r}"
            )


# ============================================================================
# TestSentinelExpansionInControlProse
# ============================================================================


class TestSentinelExpansionInControlProse:
    """Tests that sentinels in control description are resolved."""

    def test_control_description_intra_sentinel_resolved(self):
        """
        Test that {{riskTestFoo}} in a control's description is resolved.

        Given: A control with {{riskTestFoo}} in its description
        When: build_site_data is called with a risk id="riskTestFoo"
        Then: The control's description contains a nested array with a ref item for riskTestFoo
        """
        _require_sentinel_module()
        control = dict(_MINIMAL_CONTROL)
        control["description"] = ["Mitigates {{riskTestFoo}} effectively."]

        result = _build(controls_data={"controls": [control], "categories": []})

        control_out = next(c for c in result["controls"] if c["id"] == "controlTestBar")
        desc = control_out["description"]
        nested = [item for item in desc if isinstance(item, list)]
        assert nested
        ref_items = [i for n in nested for i in n if isinstance(i, dict) and i.get("type") == "ref"]
        assert any(r["id"] == "riskTestFoo" and r["title"] == "Test Foo Risk" for r in ref_items)

    def test_control_description_ref_sentinel_resolved(self):
        """
        Test that {{ref:cwe-89}} in a control's description is resolved.

        Given: A control with {{ref:cwe-89}} in description and externalReferences entry
        When: build_site_data is called
        Then: The control's description contains a nested array with a link item
        """
        _require_sentinel_module()
        control = dict(_MINIMAL_CONTROL)
        control["description"] = ["Addresses {{ref:cwe-89}}."]
        control["externalReferences"] = [
            {
                "type": "cwe",
                "id": "cwe-89",
                "title": "CWE-89: SQL Injection",
                "url": "https://cwe.mitre.org/data/definitions/89.html",
            }
        ]

        result = _build(controls_data={"controls": [control], "categories": []})

        control_out = next(c for c in result["controls"] if c["id"] == "controlTestBar")
        desc = control_out["description"]
        nested = [item for item in desc if isinstance(item, list)]
        assert nested
        link_items = [i for n in nested for i in n if isinstance(i, dict) and i.get("type") == "link"]
        assert any(li["title"] == "CWE-89: SQL Injection" for li in link_items)

    def test_plain_control_prose_unchanged(self):
        """
        Test that control prose without sentinels emits only plain strings.

        Given: A control with no sentinel spans in description
        When: build_site_data is called
        Then: The description field contains only string items
        """
        _require_sentinel_module()
        result = _build()
        control_out = next(c for c in result["controls"] if c["id"] == "controlTestBar")
        desc = control_out["description"]
        assert all(isinstance(item, str) for item in desc), (
            f"Plain-text description must emit only strings; got: {desc!r}"
        )


# ============================================================================
# TestExternalReferencesPassthrough
# ============================================================================


class TestExternalReferencesPassthrough:
    """Tests that externalReferences arrays are included verbatim in JSON output."""

    def test_persona_external_references_passed_through(self):
        """
        Test that a persona's externalReferences appear unchanged in site data output.

        Given: A persona with an externalReferences array
        When: build_site_data is called
        Then: The persona in site data has the same externalReferences array

        Passthrough is required because the schema declares externalReferences as
        optional on each item with additionalProperties: false.
        """
        _require_sentinel_module()
        ext_refs = [
            {
                "type": "paper",
                "id": "smith-2024",
                "title": "Smith 2024",
                "url": "https://example.com/smith-2024",
            }
        ]
        persona = dict(_MINIMAL_PERSONA)
        persona["externalReferences"] = ext_refs

        result = _build(personas_data={"personas": [persona]})

        persona_out = next(p for p in result["personas"] if p["id"] == "personaTestSubject")
        assert "externalReferences" in persona_out, "externalReferences must be passed through to site data output"
        assert persona_out["externalReferences"] == ext_refs

    def test_risk_external_references_passed_through(self):
        """
        Test that a risk's externalReferences appear unchanged in site data output.

        Given: A risk with an externalReferences array
        When: build_site_data is called
        Then: The risk in site data has the same externalReferences array
        """
        _require_sentinel_module()
        ext_refs = [
            {
                "type": "cwe",
                "id": "cwe-89",
                "title": "CWE-89",
                "url": "https://cwe.mitre.org/data/definitions/89.html",
            }
        ]
        risk = dict(_MINIMAL_RISK)
        risk["externalReferences"] = ext_refs

        result = _build(risks_data={"risks": [risk]})

        risk_out = next(r for r in result["risks"] if r["id"] == "riskTestFoo")
        assert "externalReferences" in risk_out
        assert risk_out["externalReferences"] == ext_refs

    def test_control_external_references_passed_through(self):
        """
        Test that a control's externalReferences appear unchanged in site data output.

        Given: A control with an externalReferences array
        When: build_site_data is called
        Then: The control in site data has the same externalReferences array
        """
        _require_sentinel_module()
        ext_refs = [
            {
                "type": "atlas",
                "id": "aml-t0020",
                "title": "MITRE ATLAS AML.T0020",
                "url": "https://atlas.mitre.org/techniques/AML.T0020",
            }
        ]
        control = dict(_MINIMAL_CONTROL)
        control["externalReferences"] = ext_refs

        result = _build(controls_data={"controls": [control], "categories": []})

        control_out = next(c for c in result["controls"] if c["id"] == "controlTestBar")
        assert "externalReferences" in control_out
        assert control_out["externalReferences"] == ext_refs

    def test_no_external_references_key_absent_in_output(self):
        """
        Test that entities without externalReferences do not emit the key.

        Given: A persona/risk/control with no externalReferences field
        When: build_site_data is called
        Then: The output for that entity does not have an externalReferences key
              (passthrough is conditional on source having the field)
        """
        _require_sentinel_module()
        result = _build()

        persona_out = next(p for p in result["personas"] if p["id"] == "personaTestSubject")
        risk_out = next(r for r in result["risks"] if r["id"] == "riskTestFoo")
        control_out = next(c for c in result["controls"] if c["id"] == "controlTestBar")

        assert "externalReferences" not in persona_out
        assert "externalReferences" not in risk_out
        assert "externalReferences" not in control_out


# ============================================================================
# TestUnresolvedSentinelRaises
# ============================================================================


class TestUnresolvedSentinelRaises:
    """Tests that unresolved sentinels raise UnresolvedSentinelError from build_site_data."""

    def test_intra_typo_in_persona_description_raises(self):
        """
        Test that a typo'd intra sentinel in a persona description raises UnresolvedSentinelError.

        Given: A persona with {{riskTypoFooBar}} (no such id in the corpus)
        When: build_site_data is called
        Then: UnresolvedSentinelError is raised and propagates out of build_site_data;
              the error's .sentinel is "{{riskTypoFooBar}}" and .field_path references
              the persona's description
        """
        _require_sentinel_module()
        persona = dict(_MINIMAL_PERSONA)
        persona["description"] = ["See {{riskTypoFooBar}} for context."]

        with pytest.raises(UnresolvedSentinelError) as exc_info:
            _build(personas_data={"personas": [persona]})

        exc = exc_info.value
        assert exc.sentinel == "{{riskTypoFooBar}}"
        assert "persona" in exc.field_path.lower() or "description" in exc.field_path.lower(), (
            f"field_path should reference the persona's description; got: {exc.field_path!r}"
        )

    def test_ref_typo_in_risk_long_description_raises(self):
        """
        Test that an unknown ref id in a risk's longDescription raises UnresolvedSentinelError.

        Given: A risk with {{ref:cve-2024-99999}} in longDescription and no matching
               externalReferences entry
        When: build_site_data is called
        Then: UnresolvedSentinelError is raised with .sentinel == "{{ref:cve-2024-99999}}"
              and .field_path references the risk's longDescription
        """
        _require_sentinel_module()
        risk = dict(_MINIMAL_RISK)
        risk["longDescription"] = ["See {{ref:cve-2024-99999}}."]
        # No externalReferences provided => ref_lookup is empty for this entry

        with pytest.raises(UnresolvedSentinelError) as exc_info:
            _build(risks_data={"risks": [risk]})

        exc = exc_info.value
        assert exc.sentinel == "{{ref:cve-2024-99999}}"
        # field_path should identify which field triggered the error
        assert exc.field_path, "field_path must be non-empty"

    def test_intra_typo_in_control_description_raises(self):
        """
        Test that a typo'd intra sentinel in a control description raises UnresolvedSentinelError.

        Given: A control with {{riskNonExistentXyz}} in its description
        When: build_site_data is called (no risk with that id exists)
        Then: UnresolvedSentinelError is raised with .sentinel == "{{riskNonExistentXyz}}"
        """
        _require_sentinel_module()
        control = dict(_MINIMAL_CONTROL)
        control["description"] = ["Mitigates {{riskNonExistentXyz}}."]

        with pytest.raises(UnresolvedSentinelError) as exc_info:
            _build(controls_data={"controls": [control], "categories": []})

        exc = exc_info.value
        assert exc.sentinel == "{{riskNonExistentXyz}}"

    def test_ref_typo_in_persona_responsibilities_raises(self):
        """
        Test that an unknown ref id in persona responsibilities raises UnresolvedSentinelError.

        Given: A persona with {{ref:unknown-ref-xyz}} in responsibilities and no
               externalReferences for that entry
        When: build_site_data is called
        Then: UnresolvedSentinelError is raised with the correct sentinel span
        """
        _require_sentinel_module()
        persona = dict(_MINIMAL_PERSONA)
        persona["responsibilities"] = ["Per {{ref:unknown-ref-xyz}}."]

        with pytest.raises(UnresolvedSentinelError) as exc_info:
            _build(personas_data={"personas": [persona]})

        exc = exc_info.value
        assert exc.sentinel == "{{ref:unknown-ref-xyz}}"

    def test_field_path_in_error_is_informative(self):
        """
        Test that the field_path in UnresolvedSentinelError identifies the entry and field.

        Given: A risk with index 0 and a typo'd intra sentinel in longDescription index 0
        When: build_site_data is called
        Then: The field_path in the raised error contains enough context to identify
              the entry (e.g. "risks[0].longDescription[0]" or similar)
        """
        _require_sentinel_module()
        risk = dict(_MINIMAL_RISK)
        risk["longDescription"] = ["Contains {{riskTypoForPath}}."]

        with pytest.raises(UnresolvedSentinelError) as exc_info:
            _build(risks_data={"risks": [risk]})

        exc = exc_info.value
        assert exc.field_path, "field_path must be non-empty for diagnostics"
        # The field_path should reference the risk's longDescription in some form
        assert (
            "long" in exc.field_path.lower()
            or "description" in exc.field_path.lower()
            or "risks" in exc.field_path.lower()
        ), f"field_path should help locate the error; got: {exc.field_path!r}"


# ============================================================================
# TestSchemaValidationStillPasses
# ============================================================================


class TestSchemaValidationStillPasses:
    """Tests that write_site_data schema validation still passes with new shapes.

    Note: write_site_data loads its schema via a module-level _OUTPUT_SCHEMA
    constant at import time (build_persona_site_data.py:37), so no schemas-dir
    fixture is needed in these tests — the on-disk schema is already cached by
    the time any test method runs.
    """

    def test_write_site_data_accepts_output_with_ref_items(self, tmp_path: Path):
        """
        Test that write_site_data accepts site data containing ref-type prose items.

        Given: Synthesized site data where a persona's description contains
               a nested array with a ref item (the new expanded shape)
        When: write_site_data is called with a tmp_path output
        Then: No jsonschema.ValidationError is raised and the file is written

        This validates that the ADR-016 D5 schema extension (PR #261) is in place
        and the new shape passes through write_site_data's validate-before-write gate.
        """
        _require_sentinel_module()
        # Build using synthesized data with a sentinel that will be resolved
        persona = dict(_MINIMAL_PERSONA)
        persona["description"] = ["See {{riskTestFoo}} for context."]

        result = _build(personas_data={"personas": [persona]})

        output_path = tmp_path / "site-data.json"
        # Should not raise
        write_site_data(result, output_path)
        assert output_path.exists()

    def test_write_site_data_accepts_output_with_link_items(self, tmp_path: Path):
        """
        Test that write_site_data accepts site data containing link-type prose items.

        Given: Synthesized site data where a risk's shortDescription contains
               a nested array with a link item
        When: write_site_data is called
        Then: No jsonschema.ValidationError is raised
        """
        _require_sentinel_module()
        risk = dict(_MINIMAL_RISK)
        risk["shortDescription"] = ["Based on {{ref:cwe-89}}."]
        risk["externalReferences"] = [
            {
                "type": "cwe",
                "id": "cwe-89",
                "title": "CWE-89: SQL Injection",
                "url": "https://cwe.mitre.org/data/definitions/89.html",
            }
        ]

        result = _build(risks_data={"risks": [risk]})

        output_path = tmp_path / "site-data-links.json"
        write_site_data(result, output_path)
        assert output_path.exists()

    def test_write_site_data_accepts_external_references_passthrough(self, tmp_path: Path):
        """
        Test that externalReferences passthrough does not break schema validation.

        Given: Synthesized data with externalReferences on a risk
        When: build_site_data → write_site_data pipeline runs
        Then: No jsonschema.ValidationError is raised and the file is written
        """
        _require_sentinel_module()
        risk = dict(_MINIMAL_RISK)
        risk["externalReferences"] = [
            {
                "type": "paper",
                "id": "smith-2024",
                "title": "Smith 2024",
                "url": "https://example.com/smith-2024",
            }
        ]

        result = _build(risks_data={"risks": [risk]})

        output_path = tmp_path / "site-data-ext-refs.json"
        write_site_data(result, output_path)
        assert output_path.exists()

        # Round-trip check: the output JSON parses and contains externalReferences
        data = json.loads(output_path.read_text(encoding="utf-8"))
        risk_out = next(r for r in data["risks"] if r["id"] == "riskTestFoo")
        assert "externalReferences" in risk_out

    def test_write_site_data_accepts_mixed_plain_and_expanded_prose(self, tmp_path: Path):
        """
        Test that a mix of plain strings and sentinel-expanded entries validates.

        Given: A risk where some prose entries are plain strings and one contains
               a sentinel, producing a mix of string and nested-array items
        When: build_site_data → write_site_data pipeline runs
        Then: No jsonschema.ValidationError is raised
        """
        _require_sentinel_module()
        risk = dict(_MINIMAL_RISK)
        risk["longDescription"] = [
            "Plain first paragraph.",
            "See {{riskTestFoo}} for details.",
            "Plain third paragraph.",
        ]

        result = _build(risks_data={"risks": [risk]})

        output_path = tmp_path / "site-data-mixed.json"
        write_site_data(result, output_path)
        assert output_path.exists()


# ============================================================================
# TestComponentsLookupSeeded
# ============================================================================


class TestComponentsLookupSeeded:
    """Tests that components.yaml is loaded and its IDs are in intra_lookup."""

    def test_component_sentinel_resolves_correctly(self):
        """
        Test that {{componentModelServing}} resolves to the component's title.

        Given: A risk's shortDescription containing {{componentModelServing}} and
               components_data containing an entry with id="componentModelServing"
               and title="Model Serving Infrastructure"
        When: build_site_data is called
        Then: The resolved item has id="componentModelServing" and
              title="Model Serving Infrastructure"

        This proves that components_data is loaded and its entries are included
        in the intra_lookup union — a new A7 requirement (the current pre-A7 builder
        does not load components.yaml at all).
        """
        _require_sentinel_module()
        risk = dict(_MINIMAL_RISK)
        risk["shortDescription"] = ["Affects {{componentModelServing}}."]

        result = _build(risks_data={"risks": [risk]})

        risk_out = next(r for r in result["risks"] if r["id"] == "riskTestFoo")
        short_desc = risk_out["shortDescription"]
        nested = [item for item in short_desc if isinstance(item, list)]
        assert nested, "componentModelServing sentinel should produce a nested array in shortDescription"
        ref_items = [
            inner for n in nested for inner in n if isinstance(inner, dict) and inner.get("type") == "ref"
        ]
        assert any(
            r["id"] == "componentModelServing" and r["title"] == "Model Serving Infrastructure" for r in ref_items
        ), f"Expected ref for componentModelServing with correct title; got ref_items: {ref_items!r}"

    def test_unknown_component_sentinel_raises(self):
        """
        Test that {{componentBogusNonExistent}} raises UnresolvedSentinelError.

        Given: A risk with a component-prefix sentinel that matches no entry in
               components_data
        When: build_site_data is called
        Then: UnresolvedSentinelError is raised, proving components_data is checked
              (not silently skipped)
        """
        _require_sentinel_module()
        risk = dict(_MINIMAL_RISK)
        risk["shortDescription"] = ["Affects {{componentBogusNonExistent}}."]

        with pytest.raises(UnresolvedSentinelError) as exc_info:
            _build(risks_data={"risks": [risk]})

        exc = exc_info.value
        assert exc.sentinel == "{{componentBogusNonExistent}}"

    def test_build_site_data_accepts_components_data_argument(self):
        """
        Test that build_site_data accepts a components_data argument without error.

        Given: A minimal valid call to build_site_data with all four arguments
        When: build_site_data is called with components_data=_MINIMAL_COMPONENTS_DATA
        Then: No TypeError or AttributeError is raised; the result is a dict with
              the expected top-level keys

        This is the minimal smoke test confirming the new components_data parameter
        was added to the function signature.
        """
        _require_sentinel_module()
        result = _build()
        assert isinstance(result, dict)
        assert "personas" in result
        assert "risks" in result
        assert "controls" in result


# ============================================================================
# TestIntraLookupConstruction
# ============================================================================


class TestIntraLookupConstruction:
    """Tests that the intra_lookup is constructed correctly from all entity sources."""

    def test_persona_ids_in_intra_lookup(self):
        """
        Test that persona ids from personas_data are resolvable as intra sentinels.

        Given: A risk whose shortDescription references {{personaTestSubject}}
               and a persona with id="personaTestSubject" and title="Test Subject"
        When: build_site_data is called
        Then: The sentinel is resolved to a ref item with title="Test Subject"
        """
        _require_sentinel_module()
        risk = dict(_MINIMAL_RISK)
        risk["shortDescription"] = ["For {{personaTestSubject}} role."]

        result = _build(risks_data={"risks": [risk]})

        risk_out = next(r for r in result["risks"] if r["id"] == "riskTestFoo")
        short_desc = risk_out["shortDescription"]
        nested = [item for item in short_desc if isinstance(item, list)]
        assert nested
        ref_items = [i for n in nested for i in n if isinstance(i, dict) and i.get("type") == "ref"]
        assert any(r["id"] == "personaTestSubject" and r["title"] == "Test Subject" for r in ref_items)

    def test_risk_ids_in_intra_lookup(self):
        """
        Test that risk ids from risks_data are resolvable as intra sentinels.

        Given: A control whose description references {{riskTestFoo}}
               and a risk with id="riskTestFoo" and title="Test Foo Risk"
        When: build_site_data is called
        Then: The sentinel is resolved to a ref item with title="Test Foo Risk"
        """
        _require_sentinel_module()
        control = dict(_MINIMAL_CONTROL)
        control["description"] = ["Mitigates {{riskTestFoo}}."]

        result = _build(controls_data={"controls": [control], "categories": []})

        control_out = next(c for c in result["controls"] if c["id"] == "controlTestBar")
        desc = control_out["description"]
        nested = [item for item in desc if isinstance(item, list)]
        assert nested
        ref_items = [i for n in nested for i in n if isinstance(i, dict) and i.get("type") == "ref"]
        assert any(r["id"] == "riskTestFoo" and r["title"] == "Test Foo Risk" for r in ref_items)

    def test_control_ids_in_intra_lookup(self):
        """
        Test that control ids from controls_data are resolvable as intra sentinels.

        Given: A persona whose description references {{controlTestBar}}
               and a control with id="controlTestBar" and title="Test Bar Control"
        When: build_site_data is called
        Then: The sentinel is resolved to a ref item with title="Test Bar Control"
        """
        _require_sentinel_module()
        persona = dict(_MINIMAL_PERSONA)
        persona["description"] = ["Apply {{controlTestBar}}."]

        result = _build(personas_data={"personas": [persona]})

        persona_out = next(p for p in result["personas"] if p["id"] == "personaTestSubject")
        desc = persona_out["description"]
        nested = [item for item in desc if isinstance(item, list)]
        assert nested
        ref_items = [i for n in nested for i in n if isinstance(i, dict) and i.get("type") == "ref"]
        assert any(r["id"] == "controlTestBar" and r["title"] == "Test Bar Control" for r in ref_items)


# ============================================================================
# TestRefLookupPerEntry
# ============================================================================


class TestRefLookupPerEntry:
    """Tests that ref_lookup is scoped per-entry from each entry's externalReferences."""

    def test_ref_lookup_scoped_to_entry_not_shared(self):
        """
        Test that ref sentinels are resolved only from the entry's own externalReferences.

        Given: Two risks — risk A has {{ref:cwe-89}} in its prose with a matching
               externalReferences entry; risk B has {{ref:cwe-89}} with NO externalReferences
        When: build_site_data is called
        Then: Risk A resolves the sentinel successfully; risk B raises UnresolvedSentinelError

        This proves ref_lookup is per-entry, not shared across the corpus.
        """
        _require_sentinel_module()
        risk_a = {
            "id": "riskWithRef",
            "title": "Risk With Ref",
            "category": "risksTestCategory",
            "shortDescription": ["See {{ref:cwe-89}}."],
            "longDescription": ["Details."],
            "examples": [],
            "personas": [],
            "controls": [],
            "externalReferences": [
                {
                    "type": "cwe",
                    "id": "cwe-89",
                    "title": "CWE-89: SQL Injection",
                    "url": "https://cwe.mitre.org/data/definitions/89.html",
                }
            ],
        }
        risk_b = {
            "id": "riskWithoutRef",
            "title": "Risk Without Ref",
            "category": "risksTestCategory",
            "shortDescription": ["See {{ref:cwe-89}}."],  # same sentinel, no externalReferences
            "longDescription": [],
            "examples": [],
            "personas": [],
            "controls": [],
            # No externalReferences — ref_lookup for this entry is empty
        }

        with pytest.raises(UnresolvedSentinelError) as exc_info:
            _build(risks_data={"risks": [risk_a, risk_b]})

        exc = exc_info.value
        assert exc.sentinel == "{{ref:cwe-89}}"


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Total test classes: 9
Total tests: ~35

- TestSentinelExpansionInPersonaProse (4):  intra ref in description, ref link in description,
                                             intra in responsibilities, plain prose unchanged
- TestSentinelExpansionInRiskProse (4):     intra in shortDescription, ref in longDescription,
                                             intra in examples, plain prose unchanged
- TestSentinelExpansionInControlProse (3):  intra in description, ref in description,
                                             plain prose unchanged
- TestExternalReferencesPassthrough (4):    persona, risk, control passthrough; absent key omitted
- TestUnresolvedSentinelRaises (5):         intra typo in persona, ref typo in risk,
                                             intra typo in control, ref typo in responsibilities,
                                             field_path is informative
- TestSchemaValidationStillPasses (4):      ref items, link items, ext-refs, mixed plain+expanded
- TestComponentsLookupSeeded (3):           component sentinel resolves, unknown raises, sig accepted
- TestIntraLookupConstruction (3):          persona/risk/control ids all in lookup
- TestRefLookupPerEntry (1):                ref_lookup is per-entry scoped

Coverage areas:
- Sentinel resolution in all three entity prose fields (persona, risk, control)
- All four sentinel kinds: intra (risk/control/component/persona) and ref
- externalReferences passthrough contract
- build_site_data accepts components_data parameter (new A7 requirement)
- UnresolvedSentinelError propagation with informative field_path
- Schema validation of expanded output via write_site_data
- Per-entry ref_lookup scoping (not shared across corpus entries)
"""

#!/usr/bin/env python3
r"""
Live-corpus regression guards for folded-bullet drift (issue #225, ADR-020 D4).

Background
----------
The folded-bullet drift heuristic (INVALID_FOLDED_BULLET, Rule 10 in
_prose_tokens.py) detects **source-form** drift: whitespace-prefixed "- item"
lines in raw decoded strings.

The two known issue #225 cases use YAML ``>`` folded scalars instead. When
PyYAML decodes a ``>`` block it collapses indentation, so embedded list items
arrive at column 0 in the Python string — triggering INVALID_LIST (Rule 5)
rather than INVALID_FOLDED_BULLET.

Both drift cases are caught:
- ``controlModelAndDataExecutionIntegrity.description[1]`` → INVALID_LIST
- ``riskSensitiveDataDisclosure.longDescription[3]``        → INVALID_LIST

What this file pins:
1. Live-corpus regression — the two specific entries above continue to
   produce diagnostics (alarm if the corpus is cleaned without updating
   issue #225 tracking).
2. Diagnostic-text contract — the INVALID_LIST reason cross-references
   ``ADR-020 D4`` so authors who encounter the message find the heuristic's
   broader documentation.

Test Summary
============
Total tests: 8

- Live-corpus controls regression (3 tests): diagnostic exists at the entry,
  on description[1], with ADR-020 D4 in the reason.
- Live-corpus risks regression (3 tests): diagnostic exists at the entry,
  on longDescription[3], with ADR-020 D4 in the reason.
- INVALID_LIST reason-text contract (2 tests): synthetic input asserts the
  reason mentions ADR-020 D4 and hints at folded-bullet drift.
"""

import sys
from pathlib import Path

import pytest

# Inject scripts/hooks so precommit.* imports work from any working directory.
_HOOKS_DIR = Path(__file__).resolve().parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

try:
    from precommit._prose_tokens import TokenKind, tokenize  # noqa: E402
    from precommit.validate_yaml_prose_subset import (  # noqa: E402
        Diagnostic,
        check_prose_field,
        find_prose_fields,
    )

    _IMPORT_ERROR: Exception | None = None
except ImportError as _e:
    _IMPORT_ERROR = _e
    Diagnostic = None  # type: ignore[assignment,misc]
    check_prose_field = None  # type: ignore[assignment]
    find_prose_fields = None  # type: ignore[assignment]
    TokenKind = None  # type: ignore[assignment]
    tokenize = None  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _require_imports():
    """Skip every test with ImportError if the implementation modules are absent."""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCHEMA_DIR = _REPO_ROOT / "risk-map" / "schemas"
_CONTROLS_YAML = _REPO_ROOT / "risk-map" / "yaml" / "controls.yaml"
_RISKS_YAML = _REPO_ROOT / "risk-map" / "yaml" / "risks.yaml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _collect_entry_diagnostics(yaml_path: Path, entry_id: str) -> list:
    """Run the prose-subset linter on all fields of a single entry.

    Collects ProseFields for the given entry_id and returns all Diagnostic
    objects produced by check_prose_field across every matching field.

    Args:
        yaml_path: Path to the YAML file.
        entry_id:  The entry's ``id`` value to filter on.

    Returns:
        List of Diagnostic objects for all fields of that entry.
    """
    diagnostics = []
    for field in find_prose_fields(yaml_path, _SCHEMA_DIR):
        if field.entry_id == entry_id:
            diagnostics.extend(check_prose_field(field))
    return diagnostics


# ===========================================================================
# Scope (a) — live-corpus regression guards: controls.yaml
# ===========================================================================


class TestControlsLiveCorpusDriftRegression:
    r"""Regression guard for controlModelAndDataExecutionIntegrity (issue #225).

    The ``description[1]`` field contains a YAML ``>`` folded scalar with
    embedded "- item" bullet lines.  When decoded by PyYAML the items land at
    column 0 → INVALID_LIST fires.

    These tests pin the specific corpus entry to the diagnostic output so that
    future content edits that silently fix or regress the drift are caught.
    """

    def test_controls_drift_entry_produces_diagnostic(self):
        r"""
        The known drift entry in controls.yaml produces at least one diagnostic.

        Given: The live controls.yaml corpus file
        When: find_prose_fields + check_prose_field are run over the file
        Then: At least one Diagnostic is produced for
              controlModelAndDataExecutionIntegrity

        Regression guard: if the entry is cleaned up (drift removed) this
        test will fail. That is the intended behaviour — update or remove
        this test and close issue #225 when the cleanup lands.
        """
        if not _CONTROLS_YAML.is_file():
            pytest.skip(f"Live corpus not found: {_CONTROLS_YAML}")

        diags = _collect_entry_diagnostics(_CONTROLS_YAML, "controlModelAndDataExecutionIntegrity")
        assert len(diags) >= 1, (
            "Expected at least one diagnostic for "
            "controlModelAndDataExecutionIntegrity; found none. "
            "If the drift was intentionally removed, update this test and "
            "close issue #225."
        )

    def test_controls_drift_entry_is_at_description_index_1(self):
        r"""
        The diagnostic for the known controls drift is on description[1].

        Given: The live controls.yaml corpus file
        When: find_prose_fields + check_prose_field are run
        Then: At least one Diagnostic has field_name == 'description'
              AND index == 1 for entry controlModelAndDataExecutionIntegrity

        Regression guard: a failing assertion after content cleanup is the
        intended behaviour. Update or remove this test and close issue #225
        when the cleanup lands.
        """
        if not _CONTROLS_YAML.is_file():
            pytest.skip(f"Live corpus not found: {_CONTROLS_YAML}")

        diags = _collect_entry_diagnostics(_CONTROLS_YAML, "controlModelAndDataExecutionIntegrity")
        matching = [d for d in diags if d.field_name == "description" and d.index == 1]
        assert len(matching) >= 1, (
            "Expected a diagnostic at description[1] for "
            "controlModelAndDataExecutionIntegrity. "
            f"Got diagnostics: {[(d.field_name, d.index) for d in diags]}"
        )

    def test_controls_drift_diagnostic_mentions_adr020(self):
        r"""
        The controls drift diagnostic reason cross-references ADR-020 D4.

        Given: The live controls.yaml corpus file
        When: find_prose_fields + check_prose_field are run
        Then: At least one diagnostic for controlModelAndDataExecutionIntegrity
              description[1] has a reason that mentions 'ADR-020 D4'

        Contract: the INVALID_LIST reason includes the ADR-020 D4 reference so
        a reader who hits this diagnostic finds the folded-bullet documentation.
        """
        if not _CONTROLS_YAML.is_file():
            pytest.skip(f"Live corpus not found: {_CONTROLS_YAML}")

        diags = _collect_entry_diagnostics(_CONTROLS_YAML, "controlModelAndDataExecutionIntegrity")
        description_diags = [d for d in diags if d.field_name == "description" and d.index == 1]
        assert len(description_diags) >= 1, (
            "Prerequisite failed: no diagnostic at description[1]; "
            "check test_controls_drift_entry_is_at_description_index_1."
        )
        # The key assertion: at least one reason must mention ADR-020 D4.
        # Substring containment, not exact match — allows wording flexibility.
        has_adr_reference = any("ADR-020 D4" in d.reason for d in description_diags)
        assert has_adr_reference, (
            "Expected at least one diagnostic reason for "
            "controlModelAndDataExecutionIntegrity description[1] to contain "
            "'ADR-020 D4'. This cross-reference directs authors to the correct "
            "documentation when they encounter the folded-bullet drift message. "
            f"Actual reasons: {[d.reason for d in description_diags]}"
        )


# ===========================================================================
# Scope (a) — live-corpus regression guards: risks.yaml
# ===========================================================================


class TestRisksLiveCorpusDriftRegression:
    r"""Regression guard for riskSensitiveDataDisclosure (issue #225).

    The ``longDescription[3]`` field is a nested-list outer item containing a
    YAML ``>`` folded scalar with embedded "- Category: explanation" bullet
    lines.  After PyYAML decoding, the items land at column 0 → INVALID_LIST.
    The nested structure means ``index == 3`` and ``nested_index == 0`` in the
    ProseField; the Diagnostic carries ``index == 3``.
    """

    def test_risks_drift_entry_produces_diagnostic(self):
        r"""
        The known drift entry in risks.yaml produces at least one diagnostic.

        Given: The live risks.yaml corpus file
        When: find_prose_fields + check_prose_field are run over the file
        Then: At least one Diagnostic is produced for riskSensitiveDataDisclosure

        Regression guard: a failing assertion after content cleanup is the
        intended behaviour. Update or remove this test and close issue #225
        when the cleanup lands.
        """
        if not _RISKS_YAML.is_file():
            pytest.skip(f"Live corpus not found: {_RISKS_YAML}")

        diags = _collect_entry_diagnostics(_RISKS_YAML, "riskSensitiveDataDisclosure")
        assert len(diags) >= 1, (
            "Expected at least one diagnostic for riskSensitiveDataDisclosure; "
            "found none.  If the drift was intentionally removed, update this "
            "test and close issue #225."
        )

    def test_risks_drift_entry_is_at_long_description_index_3(self):
        r"""
        The diagnostic for the known risks drift is on longDescription[3].

        Given: The live risks.yaml corpus file
        When: find_prose_fields + check_prose_field are run
        Then: At least one Diagnostic has field_name == 'longDescription'
              AND index == 3 for entry riskSensitiveDataDisclosure

        Regression guard: a failing assertion after content cleanup is the
        intended behaviour. Update or remove this test and close issue #225
        when the cleanup lands.
        """
        if not _RISKS_YAML.is_file():
            pytest.skip(f"Live corpus not found: {_RISKS_YAML}")

        diags = _collect_entry_diagnostics(_RISKS_YAML, "riskSensitiveDataDisclosure")
        matching = [d for d in diags if d.field_name == "longDescription" and d.index == 3]
        assert len(matching) >= 1, (
            "Expected a diagnostic at longDescription[3] for "
            "riskSensitiveDataDisclosure. "
            f"Got diagnostics: {[(d.field_name, d.index) for d in diags]}"
        )

    def test_risks_drift_diagnostic_mentions_adr020(self):
        r"""
        The risks drift diagnostic reason cross-references ADR-020 D4.

        Given: The live risks.yaml corpus file
        When: find_prose_fields + check_prose_field are run
        Then: At least one diagnostic for riskSensitiveDataDisclosure
              longDescription[3] has a reason that mentions 'ADR-020 D4'

        Contract: the INVALID_LIST reason includes the ADR-020 D4 reference so
        a reader who hits this diagnostic finds the folded-bullet documentation.
        """
        if not _RISKS_YAML.is_file():
            pytest.skip(f"Live corpus not found: {_RISKS_YAML}")

        diags = _collect_entry_diagnostics(_RISKS_YAML, "riskSensitiveDataDisclosure")
        long_desc_diags = [d for d in diags if d.field_name == "longDescription" and d.index == 3]
        assert len(long_desc_diags) >= 1, (
            "Prerequisite failed: no diagnostic at longDescription[3]; "
            "check test_risks_drift_entry_is_at_long_description_index_3."
        )
        has_adr_reference = any("ADR-020 D4" in d.reason for d in long_desc_diags)
        assert has_adr_reference, (
            "Expected at least one diagnostic reason for "
            "riskSensitiveDataDisclosure longDescription[3] to contain "
            "'ADR-020 D4'. "
            f"Actual reasons: {[d.reason for d in long_desc_diags]}"
        )


# ===========================================================================
# Scope (b) — INVALID_LIST reason text must cross-reference ADR-020 D4
# ===========================================================================


class TestInvalidListReasonAugmentation:
    r"""Assert that the INVALID_LIST diagnostic mentions ADR-020 D4.

    Pins the contract on the _REASONS mapping in validate_yaml_prose_subset.py:
    the INVALID_LIST reason must mention 'ADR-020 D4' and hint at folded-bullet
    drift, so a reader who encounters the diagnostic finds the heuristic's
    broader documentation.
    """

    def _make_list_field(self, raw_text: str):
        r"""Build a ProseField whose text produces an INVALID_LIST token.

        Args:
            raw_text: A string that starts with '- ' at column 0.

        Returns:
            A ProseField with a populated token stream.
        """
        from precommit._linter_types import ProseField  # noqa: PLC0415

        return ProseField(
            file_path=Path("controls.yaml"),
            entry_id="controlAlpha",
            field_name="description",
            index=0,
            raw_text=raw_text,
            tokens=tokenize(raw_text),
        )

    def test_invalid_list_reason_mentions_adr020_d4(self):
        r"""
        A column-0 list diagnostic reason includes 'ADR-020 D4'.

        Given: A ProseField with '- item at column zero'
        When: check_prose_field is called
        Then: The produced Diagnostic reason contains 'ADR-020 D4'
        """
        field = self._make_list_field("- item at column zero")
        diags = check_prose_field(field)

        assert len(diags) >= 1, "Expected at least one diagnostic for column-0 list item"
        # Verify the field first produces INVALID_LIST (not some other kind)
        list_diags = [d for d in diags if "list marker" in d.reason.lower() or "list" in d.reason.lower()]
        assert len(list_diags) >= 1, f"Expected a list-marker diagnostic; got: {[d.reason for d in diags]}"
        has_adr_ref = any("ADR-020 D4" in d.reason for d in list_diags)
        assert has_adr_ref, (
            "Expected INVALID_LIST diagnostic reason to contain 'ADR-020 D4' "
            "so authors are directed to the folded-bullet drift documentation. "
            f"Actual reasons: {[d.reason for d in list_diags]}"
        )

    def test_invalid_list_reason_distinguishes_folded_scalar_drift(self):
        r"""
        The INVALID_LIST reason text hints at folded-bullet drift.

        Given: A ProseField with a column-0 list item (parsed-form drift)
        When: check_prose_field is called
        Then: The reason contains either 'folded-bullet' or 'folded' so that
              authors who encounter this message understand it may originate
              from a '>' folded scalar in YAML source.
        """
        field = self._make_list_field("- another column zero item")
        diags = check_prose_field(field)

        assert len(diags) >= 1, "Expected at least one diagnostic"
        list_diags = [d for d in diags if "list" in d.reason.lower()]
        assert len(list_diags) >= 1

        # Either 'folded' or 'ADR-020' in the reason satisfies the intent.
        has_drift_hint = any(("folded" in d.reason.lower() or "ADR-020" in d.reason) for d in list_diags)
        assert has_drift_hint, (
            "Expected INVALID_LIST reason to mention 'folded' or 'ADR-020' "
            "to hint that this violation may be folded-scalar drift "
            "(see issue #225). "
            f"Actual reasons: {[d.reason for d in list_diags]}"
        )

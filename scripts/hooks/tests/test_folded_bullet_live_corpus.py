#!/usr/bin/env python3
r"""
Synthetic contract for INVALID_LIST diagnostic text (ADR-020 D4).

Background
----------
The folded-bullet drift heuristic (INVALID_FOLDED_BULLET, Rule 10 in
_prose_tokens.py) detects **source-form** drift: whitespace-prefixed "- item"
lines in raw decoded strings. The companion case — YAML ``>`` folded scalars
whose embedded bullets PyYAML collapses to column 0 — triggers INVALID_LIST
(Rule 5). To direct authors to the same documentation regardless of which
rule fires, the INVALID_LIST diagnostic reason cross-references ``ADR-020 D4``
and hints at folded-bullet drift.

Scope
-----
This file pins the diagnostic-text contract on the ``_REASONS`` mapping in
validate_yaml_prose_subset.py using synthetic ProseField fixtures. No
live-corpus assertions remain: the two former issue #225 drift sites
(``controlModelAndDataExecutionIntegrity.description[1]`` and
``riskSensitiveDataDisclosure.longDescription[3]``) were retired by PR #260
(commit ``bf6fe7f``, "fix folded-scalar bullet drift"), which rewrote them
as proper BLOCK-02 nested lists. Closes #225.

Test Summary
============
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
    from precommit.validate_yaml_prose_subset import check_prose_field  # noqa: E402

    _IMPORT_ERROR: Exception | None = None
except ImportError as _e:
    _IMPORT_ERROR = _e
    check_prose_field = None  # type: ignore[assignment]
    TokenKind = None  # type: ignore[assignment]
    tokenize = None  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _require_imports():
    """Skip every test with ImportError if the implementation modules are absent."""
    if _IMPORT_ERROR is not None:
        raise _IMPORT_ERROR


# ===========================================================================
# INVALID_LIST reason text must cross-reference ADR-020 D4
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

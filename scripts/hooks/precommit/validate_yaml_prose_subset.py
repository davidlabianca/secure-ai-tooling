#!/usr/bin/env python3
"""
Pre-commit lint: ADR-017 D4 prose grammar subset for risk-map YAML files.

Walks every prose field identified by schema introspection (fields marked with
either ``$ref: riskmap.schema.json#/definitions/utils/prose-strict`` on content
schemas or ``…/utils/text`` on supporting schemas) and rejects any INVALID_*
token kind produced by the shared tokenizer, except INVALID_CAMELCASE_ID which
is explicitly delegated to validate_prose_references per ADR-017 D4 rule 5.

Ships warn-only (exit 0 with stderr output).  Pass --block to fail on violations.

Exit codes:
    0 — warn-only mode (always), or block mode with no violations
    1 — block mode with at least one violation
    2 — usage error or unreadable file
"""

import argparse
import sys
from pathlib import Path
from typing import NoReturn

# Ensure the scripts/hooks directory is on sys.path so ``precommit.*`` imports
# work both when this file is executed directly (e.g. by the test subprocess)
# and when it is imported as part of the precommit package.
_HOOKS_DIR = Path(__file__).resolve().parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from precommit._linter_types import Diagnostic, ProseField, format_diagnostic_line  # noqa: E402
from precommit._prose_fields import find_prose_fields  # noqa: E402
from precommit._prose_tokens import (  # noqa: E402
    _RE_SENTINEL_INTRA_INNER,
    _RE_SENTINEL_REF_INNER,
    TokenKind,
)

# Deliberate cross-module coupling: _RE_SENTINEL_INTRA_INNER and
# _RE_SENTINEL_REF_INNER are internal to _prose_tokens (leading-underscore per
# ADR-028 D4).  The wrapped-sentinel predicate (ADR-028 D5) reuses them directly
# so the linter's notion of a "sentinel" cannot drift from the tokenizer's own
# classification.  They are NOT promoted to public constants — ADR-028 D4 fixes
# the public surface of _prose_tokens at exactly Token, TokenKind, and tokenize();
# a consumer importing these _RE_* names accepts the reorganization-coupling risk
# that D4 describes.

# Re-export so callers can import ProseField and Diagnostic from this module
# (the test suite imports both from here, not from _linter_types).
__all__ = ["ProseField", "Diagnostic", "find_prose_fields", "check_prose_field", "main"]

# Hook identifier used as the prefix in every diagnostic line.
_HOOK_ID = "validate-yaml-prose-subset"

# Default schema directory relative to the repository root.
# Four levels up from this file: precommit/ -> hooks/ -> scripts/ -> repo root
_DEFAULT_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "risk-map" / "schemas"

# Token kinds that the subset linter rejects.
# INVALID_CAMELCASE_ID is explicitly excluded — ADR-017 D4 rule 5 delegates
# bare-camelCase rejection to the references linter.
_REJECTED_KINDS: frozenset[TokenKind] = frozenset(
    {
        TokenKind.INVALID_URL,
        TokenKind.INVALID_HTML,
        TokenKind.INVALID_HEADING,
        TokenKind.INVALID_LIST,
        TokenKind.INVALID_CODE,
        TokenKind.INVALID_IMAGE,
        TokenKind.INVALID_BLOCKQUOTE,
        TokenKind.INVALID_TABLE,
        TokenKind.INVALID_FOLDED_BULLET,
        TokenKind.INVALID_SENTINEL,
    }
)

# Maps each rejected token kind to its diagnostic reason string.
# ADR-017 D4: reason text is used as the prefix; the token snippet is appended
# at emit time as "at '<value>'".
_REASONS: dict[TokenKind, str] = {
    TokenKind.INVALID_URL: "inline URL not permitted in prose; use externalReferences + {{ref:...}} sentinel",
    TokenKind.INVALID_HTML: "raw HTML tag not permitted in prose",
    TokenKind.INVALID_HEADING: "markdown heading not permitted in prose",
    TokenKind.INVALID_LIST: (
        "list marker at column 0 not permitted in prose (may be folded-bullet drift — see ADR-020 D4)"
    ),
    TokenKind.INVALID_CODE: "code block / inline code not permitted in prose",
    TokenKind.INVALID_IMAGE: "markdown image not permitted in prose",
    TokenKind.INVALID_BLOCKQUOTE: "markdown blockquote not permitted in prose",
    TokenKind.INVALID_TABLE: "markdown pipe table not permitted in prose",
    TokenKind.INVALID_FOLDED_BULLET: "folded-bullet drift detected (ADR-020 D4); rephrase as plain prose",
    TokenKind.INVALID_SENTINEL: "malformed sentinel; expected {{<entity>Xxx}} or {{ref:identifier}}",
}

# Guard: _REJECTED_KINDS and _REASONS must stay in sync.
# INVALID_CAMELCASE_ID is excluded from _REASONS — it is delegated to the
# references linter (ADR-017 D4 rule 5), so it should not appear in _REASONS.
assert _REJECTED_KINDS == set(_REASONS.keys()), (
    "_REJECTED_KINDS and _REASONS keys must match. "
    "If you added a new INVALID_* kind to _REJECTED_KINDS, add its reason to _REASONS too."
)

# Reason strings for emphasis violations (ADR-028 D6). These are stable
# constants; any change requires a D6 amendment.
_REASON_NESTED_EMPHASIS = "nested emphasis"
_REASON_EMPHASIS_WRAPPED_SENTINEL = "emphasis-wrapped sentinel"

# The two emphasis token kinds; used in the depth-counter walk (ADR-028 D5).
_EMPHASIS_KINDS: frozenset[TokenKind] = frozenset({TokenKind.BOLD, TokenKind.ITALIC})


def _is_emphasis_wrapped_sentinel(token_value: str, delim: str) -> bool:
    """Return True if the emphasis token wraps exactly one sentinel.

    Strips the emphasis delimiter pair from token_value, .strip()s whitespace,
    then checks whether the result is a `{{ }}` span whose inner content
    fullmatches either the intra-doc or ref sentinel inner regex.

    This mirrors how _match_sentinel classifies sentinels: outer {{ }} are
    stripped first, then the inner content is matched against the patterns.

    Args:
        token_value: The full emphasis token value including delimiters.
        delim:       The delimiter string ('**', '*', or '_').

    Returns:
        True if the stripped interior is a well-formed sentinel.
    """
    interior = token_value[len(delim) : -len(delim)].strip()
    # Interior must be wrapped in {{ }} to be a sentinel form.
    if not (interior.startswith("{{") and interior.endswith("}}")):
        return False
    inner = interior[2:-2]
    return bool(_RE_SENTINEL_INTRA_INNER.fullmatch(inner) or _RE_SENTINEL_REF_INNER.fullmatch(inner))


def _delim_for_token(token_value: str) -> str:
    """Return the delimiter prefix for an emphasis token value.

    Inspects the leading characters to distinguish '**' (BOLD) from '*' (ITALIC
    asterisk) from '_' (ITALIC underscore).

    Args:
        token_value: The full token value string.

    Returns:
        The delimiter string: '**', '*', or '_'.
    """
    if token_value.startswith("**"):
        return "**"
    if token_value.startswith("*"):
        return "*"
    return "_"


def check_prose_field(field: ProseField) -> list[Diagnostic]:
    """Check one ProseField against the ADR-017 D4 grammar rejection rules.

    Iterates the pre-populated token stream and emits one Diagnostic per
    rejected token kind. INVALID_CAMELCASE_ID is intentionally skipped here
    — ADR-017 D4 rule 5 delegates bare-camelCase rejection to
    validate_prose_references.

    Also runs the ADR-028 D5 depth-counter emphasis-rejection walk, emitting
    diagnostics for nested emphasis and emphasis-wrapped sentinels.

    Args:
        field: A ProseField with tokens already populated by tokenize().

    Returns:
        List of Diagnostic objects (empty if the field is clean).
    """
    diagnostics: list[Diagnostic] = []

    def _emit_diag(reason: str) -> None:
        diagnostics.append(
            Diagnostic(
                hook_id=_HOOK_ID,
                file_path=field.file_path,
                entry_id=field.entry_id,
                field_name=field.field_name,
                index=field.index,
                reason=reason,
                nested_index=field.nested_index,
            )
        )

    # --- INVALID_* token rejection (ADR-017 D4) ---
    for token in field.tokens:
        if token.kind not in _REJECTED_KINDS:
            continue
        base_reason = _REASONS[token.kind]
        # ADR-017 D4: append the offending token value as a snippet for context.
        # Only append when token.value is non-empty (tokenizer guarantees this,
        # but guard defensively to avoid "at ''" in edge cases).
        reason = f"{base_reason} at {token.value!r}" if token.value else base_reason
        _emit_diag(reason)

    # --- ADR-028 D5 depth-counter emphasis walk ---
    # Single pass over the token stream with a bare integer depth counter.
    # Emphasis tokens with shape='open' increment depth; 'close' decrements.
    # Any emphasis token arriving at depth > 0 is a nested-emphasis violation.
    # The wrapped-sentinel predicate is independent of depth state.
    depth = 0
    for token in field.tokens:
        if token.kind not in _EMPHASIS_KINDS:
            continue

        # Nested-emphasis predicate (ADR-028 D5).
        if token.shape == "open":
            if depth > 0:
                _emit_diag(f"{_REASON_NESTED_EMPHASIS} at {token.value!r}")
            depth += 1
        elif token.shape == "close":
            # Check before decrementing: the close token is the one arriving
            # at depth > 0 in the canonical [open, text, close] stream
            # (e.g. **foo **nested** bar**), so it is the attribution point for
            # the single nested-emphasis diagnostic. ADR-028 D5 (as amended
            # 2026-05-29) emits in the close branch when depth > 0, before the
            # decrement.
            if depth > 0:
                _emit_diag(f"{_REASON_NESTED_EMPHASIS} at {token.value!r}")
            depth = max(0, depth - 1)
        elif token.shape == "complete":
            if depth > 0:
                _emit_diag(f"{_REASON_NESTED_EMPHASIS} at {token.value!r}")
            # complete = open + close, net depth change 0

        # Emphasis-wrapped-sentinel predicate (independent of depth state).
        delim = _delim_for_token(token.value)
        if _is_emphasis_wrapped_sentinel(token.value, delim):
            _emit_diag(f"{_REASON_EMPHASIS_WRAPPED_SENTINEL} at {token.value!r}")

    return diagnostics


def _emit_diagnostic(diag: Diagnostic) -> None:
    """Print a single Diagnostic to stderr in the committed format.

    Format when ``diag.nested_index`` is None (flat-array violation):
        ``<hook_id>: <file>:<entry_id>:<field>[<index>]: <reason>``

    Format when ``diag.nested_index`` is not None (inner-list violation):
        ``<hook_id>: <file>:<entry_id>:<field>[<outer>][<inner>]: <reason>``

    The optional ``[<nested_index>]`` segment is appended only for inner-list
    violations; flat-array output is byte-for-byte unchanged.

    Args:
        diag: The Diagnostic to emit.
    """
    print(format_diagnostic_line(diag), file=sys.stderr)


def main(argv: list[str] | None = None) -> NoReturn:
    """CLI entry point for validate_yaml_prose_subset.

    Accepts zero or more YAML file paths as positional arguments. With no files,
    exits 0 immediately (pre-commit may invoke with empty arg list when no files
    match the hook's ``files:`` filter). With --block, exits 1 on any violation
    and 2 on IO/usage errors; without --block, always exits 0.

    Args:
        argv: Argument list. Defaults to sys.argv[1:] when None.
    """
    parser = argparse.ArgumentParser(
        description="Lint ADR-017 D4 prose grammar subset in risk-map YAML files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s risk-map/yaml/risks.yaml\n"
            "  %(prog)s risk-map/yaml/risks.yaml --schema-dir risk-map/schemas\n"
            "  %(prog)s risk-map/yaml/risks.yaml --block\n"
        ),
    )
    parser.add_argument("files", nargs="*", help="YAML file(s) to lint (pre-commit passes these).")
    parser.add_argument(
        "--schema-dir",
        default=str(_DEFAULT_SCHEMA_DIR),
        help="Directory containing JSON schema files (default: risk-map/schemas/ from repo root).",
    )
    parser.add_argument(
        "--block",
        action="store_true",
        default=False,
        help="Exit 1 on any violation instead of warn-only (exit 0).",
    )
    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if not args.files:
        sys.exit(0)

    schema_dir = Path(args.schema_dir)

    all_diagnostics: list[Diagnostic] = []

    for file_arg in args.files:
        yaml_path = Path(file_arg)
        if not yaml_path.is_file():
            print(
                f"{_HOOK_ID}: error: file not found or not readable: {file_arg}",
                file=sys.stderr,
            )
            # A missing file is always an IO/usage error regardless of --block mode.
            sys.exit(2)

        for field in find_prose_fields(yaml_path, schema_dir):
            all_diagnostics.extend(check_prose_field(field))

    for diag in all_diagnostics:
        _emit_diagnostic(diag)

    if args.block and all_diagnostics:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main(sys.argv[1:])

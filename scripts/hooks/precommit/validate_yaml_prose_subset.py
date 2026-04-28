#!/usr/bin/env python3
"""
Pre-commit lint: ADR-017 D4 prose grammar subset for risk-map YAML files.

Walks every prose field identified by schema introspection (fields marked as
``$ref: riskmap.schema.json#/definitions/utils/text``) and rejects any INVALID_*
token kind produced by the shared tokenizer, except INVALID_CAMELCASE_ID which
is explicitly delegated to validate_prose_references per ADR-017 D4 rule 5.

Ships warn-only (exit 0 with stderr output).  Pass --block to fail on violations.

Exit codes:
    0 — warn-only mode (always), or block mode with no violations
    1 — block mode with at least one violation
    2 — usage error or unreadable file
"""

import argparse
import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import NoReturn

import yaml

# Ensure the scripts/hooks directory is on sys.path so ``precommit.*`` imports
# work both when this file is executed directly (e.g. by the test subprocess)
# and when it is imported as part of the precommit package.
_HOOKS_DIR = Path(__file__).resolve().parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from precommit._linter_types import Diagnostic, ProseField  # noqa: E402
from precommit._prose_tokens import TokenKind, tokenize  # noqa: E402

# Re-export so callers can import ProseField and Diagnostic from this module
# (the test suite imports both from here, not from _linter_types).
__all__ = ["ProseField", "Diagnostic", "find_prose_fields", "check_prose_field", "main"]

# Hook identifier used as the prefix in every diagnostic line.
_HOOK_ID = "validate-yaml-prose-subset"

# $ref value that marks a field as a prose field in schema definitions.
_PROSE_REF = "riskmap.schema.json#/definitions/utils/text"

# Default schema directory relative to the repository root.
# Four levels up from this file: precommit/ → hooks/ → scripts/ → repo root
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
    TokenKind.INVALID_LIST: "markdown list marker at column 0 not permitted in prose",
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


def _is_prose_ref(ref: str) -> bool:
    """Return True if the $ref value marks a prose field."""
    return ref == _PROSE_REF


def _walk_property(path: str, prop_schema: dict, names: list[str]) -> None:
    """Recursively collect prose-marked field paths.

    Handles three cases:
    - Leaf prose ref (e.g. shortDescription → $ref: .../utils/text)
    - Array of objects (e.g. entries[].description) — walks items.properties
    - Nested object (e.g. tourContent.introduced) — walks its properties

    Args:
        path:       Dotted field path accumulated so far.
        prop_schema: The JSON schema fragment for this property.
        names:      Accumulator list; prose field paths are appended here.
    """
    ref = prop_schema.get("$ref")
    if ref and _is_prose_ref(ref):
        names.append(path)
        return
    # Array of objects: descend into items.properties (e.g. entries[].text)
    if prop_schema.get("type") == "array":
        items = prop_schema.get("items", {})
        for sub_name, sub_schema in items.get("properties", {}).items():
            _walk_property(f"{path}.{sub_name}", sub_schema, names)
        return
    # Nested object: descend into its properties (e.g. tourContent.introduced)
    if prop_schema.get("type") == "object":
        for sub_name, sub_schema in prop_schema.get("properties", {}).items():
            _walk_property(f"{path}.{sub_name}", sub_schema, names)


def _find_prose_field_names_in_schema(schema: dict) -> list[str]:
    """Return path-qualified prose field names found in the schema.

    Walks definitions[*]/properties for the prose $ref marker, recursing
    into object-typed properties so nested prose fields like
    tourContent.introduced are discovered. Returns dotted-path field names
    (e.g. 'longDescription', 'tourContent.introduced').

    Args:
        schema: Parsed JSON schema dict.

    Returns:
        List of dotted-path field names marked as prose fields.
    """
    names: list[str] = []
    for _defname, defdata in schema.get("definitions", {}).items():
        if not isinstance(defdata, dict):
            continue
        for prop_name, prop_schema in defdata.get("properties", {}).items():
            if isinstance(prop_schema, dict):
                _walk_property(prop_name, prop_schema, names)
    return names


def _infer_schema_name(yaml_path: Path, schema_dir: Path) -> Path | None:
    """Attempt to locate a schema file for the given YAML by name matching.

    Looks for ``<stem>.schema.json`` in schema_dir (e.g. risks.yaml → risks.schema.json).
    Falls back to iterating all ``*.schema.json`` files and finding one whose
    top-level array property name matches the YAML's top-level key.

    Args:
        yaml_path:  Path to the YAML file being linted.
        schema_dir: Directory containing JSON schema files.

    Returns:
        Path to the matched schema, or None if no schema is found.
    """
    # Primary: stem-based match (risks.yaml → risks.schema.json)
    candidate = schema_dir / f"{yaml_path.stem}.schema.json"
    if candidate.is_file():
        return candidate

    # Secondary: not expected to be reached for canonical risk-map/yaml/*.yaml files
    # (their stem matches *.schema.json). Used for non-canonical paths or test fixtures.
    try:
        with open(yaml_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            return None
        yaml_top_keys = set(data.keys())
    except Exception:
        return None

    for schema_file in sorted(schema_dir.glob("*.schema.json")):
        try:
            with open(schema_file, "r", encoding="utf-8") as fh:
                schema = json.load(fh)
        except Exception:
            continue
        schema_props = set(schema.get("properties", {}).keys())
        if yaml_top_keys & schema_props:
            return schema_file

    return None


def _collect_entries(data: dict, schema: dict) -> Iterator[tuple[str, dict]]:
    """Yield (array_key, entry) pairs for every entity entry in the YAML.

    Looks for top-level keys in the YAML that correspond to array-typed
    properties in the schema, then yields each element of those arrays together
    with the array key name.

    Args:
        data:   Parsed YAML dict.
        schema: Parsed JSON schema dict.

    Yields:
        (array_key, entry_dict) pairs.
    """
    schema_array_keys = {
        k for k, v in schema.get("properties", {}).items() if isinstance(v, dict) and v.get("type") == "array"
    }
    for key in schema_array_keys:
        entries = data.get(key)
        if isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict):
                    yield key, entry


def find_prose_fields(yaml_path: Path, schema_dir: Path) -> Iterator[ProseField]:
    """Yield ProseField objects for every prose array element in a YAML file.

    Schema introspection drives field discovery: only properties marked with
    ``$ref: riskmap.schema.json#/definitions/utils/text`` are treated as prose
    fields. The YAML file is matched to a schema by stem name first, then by
    top-level array-key overlap.

    Prose fields are expected to be YAML arrays of strings (one element per
    paragraph). Each string element is yielded as a separate ProseField with its
    array index. If a prose field value is a bare string rather than a list, it
    is yielded once with index 0.

    Args:
        yaml_path:  Path to the YAML file to lint.
        schema_dir: Directory containing JSON schema files.

    Yields:
        ProseField for each prose string found.
    """
    schema_path = _infer_schema_name(yaml_path, schema_dir)
    if schema_path is None:
        return

    try:
        with open(schema_path, "r", encoding="utf-8") as fh:
            schema = json.load(fh)
    except Exception:
        return

    prose_field_names = _find_prose_field_names_in_schema(schema)
    if not prose_field_names:
        return

    try:
        with open(yaml_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except Exception:
        return

    if not isinstance(data, dict):
        return

    for _array_key, entry in _collect_entries(data, schema):
        entry_id = entry.get("id", "<unknown>")
        for field_name in prose_field_names:
            # Resolve dotted paths (e.g. "tourContent.introduced") by walking segments.
            field_value: object = entry
            for segment in field_name.split("."):
                if not isinstance(field_value, dict):
                    field_value = None
                    break
                field_value = field_value.get(segment)
            if field_value is None:
                continue
            if isinstance(field_value, list):
                for idx, item in enumerate(field_value):
                    if isinstance(item, str):
                        yield ProseField(
                            file_path=yaml_path,
                            entry_id=entry_id,
                            field_name=field_name,
                            index=idx,
                            raw_text=item,
                            tokens=tokenize(item),
                        )
            elif isinstance(field_value, str):
                yield ProseField(
                    file_path=yaml_path,
                    entry_id=entry_id,
                    field_name=field_name,
                    index=0,
                    raw_text=field_value,
                    tokens=tokenize(field_value),
                )


def check_prose_field(field: ProseField) -> list[Diagnostic]:
    """Check one ProseField against the ADR-017 D4 grammar rejection rules.

    Iterates the pre-populated token stream and emits one Diagnostic per
    rejected token kind. INVALID_CAMELCASE_ID is intentionally skipped here
    — ADR-017 D4 rule 5 delegates bare-camelCase rejection to
    validate_prose_references.

    Args:
        field: A ProseField with tokens already populated by tokenize().

    Returns:
        List of Diagnostic objects (empty if the field is clean).
    """
    diagnostics: list[Diagnostic] = []
    for token in field.tokens:
        if token.kind not in _REJECTED_KINDS:
            continue
        base_reason = _REASONS[token.kind]
        # ADR-017 D4: append the offending token value as a snippet for context.
        # Only append when token.value is non-empty (tokenizer guarantees this,
        # but guard defensively to avoid "at ''" in edge cases).
        reason = f"{base_reason} at {token.value!r}" if token.value else base_reason
        diagnostics.append(
            Diagnostic(
                hook_id=_HOOK_ID,
                file_path=field.file_path,
                entry_id=field.entry_id,
                field_name=field.field_name,
                index=field.index,
                reason=reason,
            )
        )
    return diagnostics


def _emit_diagnostic(diag: Diagnostic) -> None:
    """Print a single Diagnostic to stderr in the committed format.

    Format: ``<hook_id>: <file>:<entry_id>:<field>[<index>]: <reason>``

    Args:
        diag: The Diagnostic to emit.
    """
    idx_str = f"[{diag.index}]" if diag.index is not None else "[0]"
    line = f"{diag.hook_id}: {diag.file_path}:{diag.entry_id}:{diag.field_name}{idx_str}: {diag.reason}"
    print(line, file=sys.stderr)


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

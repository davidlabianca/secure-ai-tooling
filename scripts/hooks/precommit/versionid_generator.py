#!/usr/bin/env python3
"""
Pre-commit framework generator hook: materialize `versionId` per framework entry.

Implements ADR-027 D2b — derives a `versionId` for every entry in
`risk-map/yaml/frameworks.yaml` and writes it back in place:

    versionId = id if version is null else f"{id}@{version}"

The generator pairs with `validate_versionid_purity.py` (same generated-artifact
class as the table/diagram generators per ADR-005/013): the generator
materializes; the purity validator guards against hand-edits.

Design notes:
  - `version` is read as a string. An unquoted `version: 1.0` parses as float
    in PyYAML and silently truncates to `<id>@1`; the generator fails loudly
    on a non-string, non-null version.
  - The composed `versionId` must match the D2a charset `^[a-z0-9.@-]+$`
    and must be unique across the registry.
  - The on-disk write is a surgical text-level update of the `versionId:` line
    inside each framework entry (insert if missing, replace if present, no-op
    if equal). This preserves comments and the deliberate field ordering of
    `frameworks.yaml`; a full YAML round-trip would destroy both.

CLI:
    versionid_generator.py [--path PATH]
        --path  Optional explicit path to a frameworks.yaml. Defaults to the
                repo-relative risk-map/yaml/frameworks.yaml. Used by tests to
                operate on cloned fixtures without touching the registry.

Exit codes:
    0  Success (materialized or no-op).
    1  Validation failure (non-string version, charset violation, duplicate
       versionId). The diagnostic identifies the offending framework id.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

# Repo-relative default; the same path the pre-commit framework hook triggers on.
_DEFAULT_PATH = Path("risk-map") / "yaml" / "frameworks.yaml"

# D2a charset invariant on the composed versionId.
_VERSION_ID_CHARSET_RE = re.compile(r"^[a-z0-9.@-]+$")


def _derive_version_id(fw_id: str, version: Any) -> str:
    """
    Derive a versionId per ADR-027 D2b.

    Args:
        fw_id: The framework's concept id (kebab string).
        version: The framework's version field as parsed from YAML. May be
            None (unversioned, e.g. STRIDE) or a string. A non-None,
            non-string value (e.g. a float from an unquoted YAML scalar) is
            rejected with a ValueError by the caller before reaching here;
            this function trusts its inputs.

    Returns:
        `fw_id` alone if version is None, otherwise `f"{fw_id}@{version}"`.
    """
    if version is None:
        return fw_id
    return f"{fw_id}@{version}"


def _validate_entry(entry: dict, index: int) -> str:
    """
    Validate an entry's inputs and return its derived versionId.

    Raises:
        ValueError: If the entry's `id` is missing/non-string, its `version`
            is non-null and non-string (the YAML-float footgun), or the
            composed versionId violates the D2a charset.
    """
    fw_id = entry.get("id")
    if not isinstance(fw_id, str) or not fw_id:
        raise ValueError(
            f"frameworks[{index}]: missing or non-string `id` (got {type(fw_id).__name__}: {fw_id!r})"
        )

    version = entry.get("version")
    if version is not None and not isinstance(version, str):
        # D2b string-type guard: an unquoted `version: 1.0` parses as float
        # and would silently truncate to `<id>@1`. Fail loudly.
        raise ValueError(
            f"framework `{fw_id}`: `version` must be a quoted string or null; "
            f"got {type(version).__name__} ({version!r}). "
            "Quote the value in frameworks.yaml (e.g. `version: '1.0'`)."
        )

    derived = _derive_version_id(fw_id, version)
    if not _VERSION_ID_CHARSET_RE.match(derived):
        raise ValueError(
            f"framework `{fw_id}`: derived versionId {derived!r} violates D2a charset "
            "`^[a-z0-9.@-]+$`. Check `id` (lowercase kebab) and `version` (no whitespace)."
        )
    return derived


def _check_uniqueness(derived_by_index: dict[int, tuple[str, str]]) -> None:
    """
    Enforce D2b uniqueness: each versionId appears exactly once.

    Args:
        derived_by_index: Mapping of array-index to (fw_id, derived_versionId).

    Raises:
        ValueError: If any derived versionId appears more than once. The
            message lists the offending entries by id for actionable diagnostics.
    """
    seen: dict[str, list[str]] = {}
    for _, (fw_id, vid) in derived_by_index.items():
        seen.setdefault(vid, []).append(fw_id)
    duplicates = {vid: ids for vid, ids in seen.items() if len(ids) > 1}
    if duplicates:
        lines = [f"  - versionId {vid!r} minted by entries: {ids}" for vid, ids in duplicates.items()]
        raise ValueError("duplicate versionIds across frameworks.yaml (D2b uniqueness):\n" + "\n".join(lines))


# Matches a `versionId:` line inside an entry (any indentation, any value).
# Used by the surgical text-level update; the regex is intentionally
# conservative (4-space indent, the format the live file uses).
_VERSIONID_LINE_RE = re.compile(r"^(?P<indent>[ \t]+)versionId:\s*\S.*$")

# Matches an `id:` line — the entry boundary marker we anchor inserts against.
_ID_LINE_RE = re.compile(r"^(?P<indent>[ \t]+)-\s+id:\s*(?P<value>\S+)\s*$")

# Matches the `version:` line within an entry; the new versionId is inserted
# immediately after this line so the field order reads `version: ... / versionId: ...`.
_VERSION_LINE_RE = re.compile(r"^(?P<indent>[ \t]+)version:\s*\S.*$")


def _partition_entries(lines: list[str]) -> list[tuple[int, int, str | None]]:
    """
    Partition the line list into entry spans.

    Returns a list of (start_index, end_index_exclusive, fw_id_or_None) tuples.
    Entry spans start at the `- id:` line that opens an entry and run up to
    (exclusive of) the next entry-opening line or end-of-file. The first
    span — top-level header (`title:`, `description:`, comments, the
    `frameworks:` key) — uses fw_id None.

    Splitting on `- id:` lines is exact because the parse invariant (D3a/H3)
    bars `@` and `:` from inside concept ids, and the YAML grammar reserves
    the leading-dash + key form for sequence items; no comment or string
    matches it at the leading-dash + `id:` position.
    """
    spans: list[tuple[int, int, str | None]] = []
    span_start = 0
    span_id: str | None = None
    for i, line in enumerate(lines):
        match = _ID_LINE_RE.match(line)
        if match:
            # Close the previous span (header or prior entry).
            if i > span_start:
                spans.append((span_start, i, span_id))
            span_start = i
            span_id = match.group("value")
    # Close the final span.
    spans.append((span_start, len(lines), span_id))
    return spans


def _rewrite_entry(entry_lines: list[str], target_versionid: str) -> list[str]:
    """
    Return entry_lines with the `versionId:` field set to target_versionid.

    Two outcomes:
      - If a `versionId:` line already exists in the entry, it is replaced
        in place with the target value (indent and EOL preserved).
      - Otherwise, a new `versionId:` line is inserted immediately after the
        first `version:` line, using the same indent.

    Idempotent by construction: replacing a line that already holds the
    target value yields a byte-identical result.
    """
    # Pass 1: find existing versionId line if any.
    existing_vid_index: int | None = None
    version_line_index: int | None = None
    version_indent: str | None = None
    version_eol = "\n"
    for idx, line in enumerate(entry_lines):
        if existing_vid_index is None and _VERSIONID_LINE_RE.match(line):
            existing_vid_index = idx
        if version_line_index is None:
            ver_match = _VERSION_LINE_RE.match(line)
            if ver_match:
                version_line_index = idx
                version_indent = ver_match.group("indent")
                version_eol = "\r\n" if line.endswith("\r\n") else ("\n" if line.endswith("\n") else "")

    out = list(entry_lines)

    if existing_vid_index is not None:
        # Replace in place; preserve indent and EOL of the existing line.
        old = out[existing_vid_index]
        vid_match = _VERSIONID_LINE_RE.match(old)
        indent = vid_match.group("indent") if vid_match else (version_indent or "    ")
        eol = "\r\n" if old.endswith("\r\n") else ("\n" if old.endswith("\n") else "")
        out[existing_vid_index] = f"{indent}versionId: {target_versionid}{eol}"
        return out

    if version_line_index is not None:
        # Insert immediately after the version line.
        new_line = f"{version_indent}versionId: {target_versionid}{version_eol}"
        out.insert(version_line_index + 1, new_line)
        return out

    # No version line in this entry (malformed). The caller (_validate_entry)
    # rejects malformed entries before this function runs in the normal flow;
    # if we somehow reach here, return the entry unchanged — the purity
    # validator will surface a missing-versionId diagnostic.
    return out


def _update_text_in_place(text: str, derived_by_id: dict[str, str]) -> str:
    """
    Update or insert `versionId:` lines in `text` for each framework entry.

    Implementation: split the file into entry spans (header + one span per
    `- id:` entry), rewrite each entry independently, then re-join. Each
    rewrite either replaces an existing `versionId:` line in-place or inserts
    a new one immediately after the entry's `version:` line, preserving
    indent and EOL. Non-entry content passes through verbatim.

    Idempotent by construction: re-running on already-materialized text
    yields a byte-identical result because the replace branch writes the
    same value back.
    """
    lines = text.splitlines(keepends=True)
    spans = _partition_entries(lines)

    out: list[str] = []
    for start, end, fw_id in spans:
        if fw_id is None or fw_id not in derived_by_id:
            # Header span, or an entry whose id is missing from the derived
            # map (validation upstream would have rejected this — defensive).
            out.extend(lines[start:end])
            continue
        out.extend(_rewrite_entry(lines[start:end], derived_by_id[fw_id]))

    return "".join(out)


def _stage_in_git(path: Path) -> int:
    """
    `git add` the (possibly mutated) frameworks.yaml so the regenerated content
    lands in the same commit as the source change (Mode B auto-stage, the
    same posture as the table/diagram generators).

    Returns the git returncode; non-zero is propagated as the script exit
    code by the caller.
    """
    return subprocess.run(["git", "add", str(path)]).returncode


def main(argv: list[str]) -> int:
    """
    Run the versionId generator.

    Returns:
        0 on success, non-zero on validation or write failure.
    """
    parser = argparse.ArgumentParser(
        description="Materialize versionId per framework entry in frameworks.yaml (ADR-027 D2b)."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help=f"Path to frameworks.yaml (default: {_DEFAULT_PATH}).",
    )
    # The pre-commit framework passes staged filenames as positional args when
    # pass_filenames is true; accept and ignore them — we always operate on a
    # single canonical path. This keeps the trigger config consistent with the
    # other Mode B generators (regenerate-tables etc.).
    parser.add_argument("paths", nargs="*", help="Ignored positional args from pre-commit.")
    args = parser.parse_args(argv)

    target = args.path if args.path is not None else _DEFAULT_PATH
    if not target.is_file():
        print(f"error: frameworks.yaml not found at {target}", file=sys.stderr)
        return 1

    try:
        original = target.read_text(encoding="utf-8")
        data = yaml.safe_load(original)
    except yaml.YAMLError as exc:
        print(f"error: failed to parse {target}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, dict) or not isinstance(data.get("frameworks"), list):
        print(f"error: {target} has no `frameworks:` array", file=sys.stderr)
        return 1

    # Validate per entry, collect derived versionIds.
    derived_by_index: dict[int, tuple[str, str]] = {}
    try:
        for i, entry in enumerate(data["frameworks"]):
            if not isinstance(entry, dict):
                raise ValueError(f"frameworks[{i}] is not a mapping (got {type(entry).__name__})")
            derived = _validate_entry(entry, i)
            derived_by_index[i] = (entry["id"], derived)
        _check_uniqueness(derived_by_index)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    derived_by_id = {fw_id: vid for fw_id, vid in derived_by_index.values()}

    # Surgical text update: insert or replace the versionId line per entry.
    updated = _update_text_in_place(original, derived_by_id)

    if updated != original:
        target.write_text(updated, encoding="utf-8")
        # Auto-stage so the regenerated value lands in the same commit. Skip
        # the stage step if the file is not inside a git repo (test fixtures
        # under tmp_path) — `git add <path-outside-repo>` would non-zero exit
        # and the test would mistake the materialization for a failure.
        try:
            # Run `git -C <dir> rev-parse` to detect a repo; if it fails, skip.
            probe = subprocess.run(
                ["git", "-C", str(target.parent), "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
            )
            if probe.returncode == 0:
                stage_rc = _stage_in_git(target)
                if stage_rc != 0:
                    return stage_rc
        except FileNotFoundError:
            # git not on PATH — non-fatal in test environments
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""
Pre-commit framework hook: assert versionId purity for frameworks.yaml.

Implements ADR-027 D2b — paired with `versionid_generator.py` under the
generator-plus-purity pattern (same class as the table/diagram generators
per ADR-005/013). The generator materializes; this validator proves no
hand-edit has drifted the on-disk `versionId` (or its lineage fields) from
the derived/well-formed values.

Checks (all per ADR-027 D2a/D2b/D2c):

  1. `version` field is null or a string (D2b string-type guard).
  2. Each on-disk `versionId` equals the derived value
     (`id if version is null else f"{id}@{version}"`).
  3. Each on-disk `versionId` matches the D2a charset `^[a-z0-9.@-]+$`.
  4. The set of on-disk `versionId`s is unique across the registry (D2b).
  5. If `supersedes` is present: charset-valid AND belongs to the same
     concept-id family as the entry (D2c).
  6. If `priorVersions` is present: every member is charset-valid, the list
     contains no duplicates, and every member belongs to the same concept-id
     family as the entry (D2c).

CLI:
    validate_versionid_purity.py [--path PATH]
        --path  Optional explicit path to a frameworks.yaml. Defaults to the
                repo-relative risk-map/yaml/frameworks.yaml.

Exit codes:
    0  All checks pass.
    1  Any check fails. Stderr lists every failure with the offending
       framework id and the rule it violated.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

# Defaults mirror the generator (sibling tool, same trigger surface).
_DEFAULT_PATH = Path("risk-map") / "yaml" / "frameworks.yaml"

# D2a charset, mirrored from the generator.
_VERSION_ID_CHARSET_RE = re.compile(r"^[a-z0-9.@-]+$")


def _derive_version_id(fw_id: str, version: Any) -> str:
    """Mirror of the generator's D2b derivation rule — local to keep the validator self-contained."""
    if version is None:
        return fw_id
    return f"{fw_id}@{version}"


def _family_of(version_id: str) -> str:
    """
    Recover the concept-id family from a versionId.

    Per D2a, the delimiter is `@`. Truncating at `@` returns the family
    portion; a bare (unversioned) versionId equals its family. The D2a
    parse invariant (H3) guarantees `@` does not appear in any concept id,
    so the split is unambiguous.
    """
    return version_id.split("@", 1)[0]


def _validate_string_or_null(entry: dict, fw_id: str, errors: list[str]) -> None:
    """D2b string-type guard for `version` (the YAML-float footgun)."""
    version = entry.get("version")
    if version is not None and not isinstance(version, str):
        errors.append(
            f"framework `{fw_id}`: `version` must be a quoted string or null; "
            f"got {type(version).__name__} ({version!r}). "
            "Quote the value (e.g. `version: '1.0'`) — an unquoted '1.0' parses "
            "as a float and silently truncates to `<id>@1` (D2b)."
        )


def _validate_derived_match(entry: dict, fw_id: str, errors: list[str]) -> str | None:
    """
    Assert the on-disk versionId equals the derived value.

    Returns the on-disk value (or None if absent) so the caller can feed it
    into uniqueness and family checks. The derived value is also returned
    indirectly via the equality check.
    """
    version = entry.get("version")
    if version is not None and not isinstance(version, str):
        # _validate_string_or_null already recorded; skip the derivation to
        # avoid a misleading secondary error.
        return entry.get("versionId")

    on_disk = entry.get("versionId")
    if on_disk is None:
        errors.append(f"framework `{fw_id}`: missing `versionId` (run versionid_generator.py to materialize).")
        return None
    derived = _derive_version_id(fw_id, version)
    if on_disk != derived:
        errors.append(
            f"framework `{fw_id}`: on-disk versionId {on_disk!r} != derived {derived!r} (D2b purity). "
            "The generator restores this — do not hand-edit."
        )
    return on_disk


def _validate_charset(on_disk: str | None, fw_id: str, errors: list[str]) -> None:
    """D2a charset assertion on the on-disk versionId."""
    if on_disk is None:
        return
    if not _VERSION_ID_CHARSET_RE.match(on_disk):
        errors.append(f"framework `{fw_id}`: versionId {on_disk!r} violates D2a charset `^[a-z0-9.@-]+$`.")


def _validate_supersedes(entry: dict, fw_id: str, errors: list[str]) -> None:
    """D2c: `supersedes` is charset-valid and same-family as the entry."""
    if "supersedes" not in entry:
        return
    value = entry["supersedes"]
    if not isinstance(value, str):
        errors.append(f"framework `{fw_id}`: `supersedes` must be a string; got {type(value).__name__}.")
        return
    if not _VERSION_ID_CHARSET_RE.match(value):
        errors.append(f"framework `{fw_id}`: `supersedes` value {value!r} violates D2a charset.")
        return
    if _family_of(value) != fw_id:
        errors.append(
            f"framework `{fw_id}`: `supersedes` value {value!r} is not in the same "
            f"concept-id family (expected family `{fw_id}`, got `{_family_of(value)}`) — D2c."
        )


def _validate_prior_versions(entry: dict, fw_id: str, errors: list[str]) -> None:
    """D2c: every `priorVersions` member is charset-valid, list is unique, all same-family."""
    if "priorVersions" not in entry:
        return
    members = entry["priorVersions"]
    if not isinstance(members, list):
        errors.append(f"framework `{fw_id}`: `priorVersions` must be a list; got {type(members).__name__}.")
        return

    seen: set[str] = set()
    for i, member in enumerate(members):
        if not isinstance(member, str):
            errors.append(
                f"framework `{fw_id}`: priorVersions[{i}] must be a string; got {type(member).__name__}."
            )
            continue
        if not _VERSION_ID_CHARSET_RE.match(member):
            errors.append(f"framework `{fw_id}`: priorVersions[{i}] {member!r} violates D2a charset.")
            continue
        if member in seen:
            errors.append(f"framework `{fw_id}`: priorVersions duplicate {member!r} (D2c uniqueness within list).")
            continue
        seen.add(member)
        if _family_of(member) != fw_id:
            errors.append(
                f"framework `{fw_id}`: priorVersions[{i}] {member!r} is cross-family "
                f"(expected `{fw_id}`, got `{_family_of(member)}`) — D2c."
            )


def _validate_registry_uniqueness(version_ids: list[tuple[str, str]], errors: list[str]) -> None:
    """D2b uniqueness: the set of materialized versionIds across the registry is distinct."""
    seen: dict[str, list[str]] = {}
    for fw_id, vid in version_ids:
        if vid is None:
            continue
        seen.setdefault(vid, []).append(fw_id)
    for vid, ids in seen.items():
        if len(ids) > 1:
            errors.append(f"duplicate versionId {vid!r} across entries: {ids} (D2b uniqueness).")


def main(argv: list[str]) -> int:
    """Run the versionId purity validator. Returns 0 on success, 1 on any failure."""
    parser = argparse.ArgumentParser(
        description="Validate frameworks.yaml versionId/supersedes/priorVersions purity (ADR-027 D2b/D2c)."
    )
    parser.add_argument(
        "--path",
        type=Path,
        default=None,
        help=f"Path to frameworks.yaml (default: {_DEFAULT_PATH}).",
    )
    # Accept and ignore positional args from the pre-commit framework
    # (pass_filenames-related; same posture as the generator).
    parser.add_argument("paths", nargs="*", help="Ignored positional args from pre-commit.")
    args = parser.parse_args(argv)

    target = args.path if args.path is not None else _DEFAULT_PATH
    if not target.is_file():
        print(f"error: frameworks.yaml not found at {target}", file=sys.stderr)
        return 1

    try:
        data = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"error: failed to parse {target}: {exc}", file=sys.stderr)
        return 1

    if not isinstance(data, dict) or not isinstance(data.get("frameworks"), list):
        print(f"error: {target} has no `frameworks:` array", file=sys.stderr)
        return 1

    errors: list[str] = []
    materialized: list[tuple[str, str]] = []

    for i, entry in enumerate(data["frameworks"]):
        if not isinstance(entry, dict):
            errors.append(f"frameworks[{i}] is not a mapping (got {type(entry).__name__}).")
            continue
        fw_id = entry.get("id")
        if not isinstance(fw_id, str) or not fw_id:
            errors.append(f"frameworks[{i}]: missing or non-string `id`.")
            continue

        _validate_string_or_null(entry, fw_id, errors)
        on_disk = _validate_derived_match(entry, fw_id, errors)
        _validate_charset(on_disk, fw_id, errors)
        _validate_supersedes(entry, fw_id, errors)
        _validate_prior_versions(entry, fw_id, errors)
        if on_disk is not None:
            materialized.append((fw_id, on_disk))

    _validate_registry_uniqueness(materialized, errors)

    if errors:
        print("versionId purity check failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""
Pre-commit hook: detect mapping-value drift in content YAML files.

Implements ADR-027 D5/D5a — Tier 1 drift detection (version-known check
plus controlled-vocabulary membership). Paired with validate_mapping_purity.py
(D4c) and framework-mapping-maintainer.py (D4). See also #347, #343.

For each mapping value under a `mappings.<framework>: [values]` block in
risks/controls/components/personas.yaml, the validator classifies the value
as "skip", "current", "valid-but-superseded", or "invalid" according to the
D5/D5a/D3a algorithm:

  1. Unknown framework key → SKIP. Unknown-framework is the purity validator's
     D4c concern; drift must not crash or double-report on it. Intentional
     divergence from purity (which fails-loud on unknown framework).
  2. Framework UNVERSIONED (version is None, e.g. STRIDE, D6):
     - value in closed PascalCase enum → CURRENT ("pinned by enum").
     - value NOT in enum (legacy lowercase/kebab) → SKIP.
     compose_pinned_value distinguishes in-enum vs legacy for unversioned
     frameworks; split_pinned_value returns (value, None) without checking
     the enum, so compose_pinned_value is used here (same as purity).
  3. Framework VERSIONED + value has neither `@` nor `:` → SKIP.
     (D3a / H3: delimiter absence is the unambiguous legacy signal.)
  4. Framework VERSIONED + value has `@` or `:` (pinned-intent):
     - split_pinned_value raises FrameworkMappingError → INVALID (detail).
     - split succeeds, ver_token == current version → CURRENT.
     - split succeeds, ver_token in priorVersions → VALID-BUT-SUPERSEDED.
     - split succeeds, ver_token not in either (shouldn't occur normally,
       since split only returns recognized tokens) → INVALID (defensive).

"valid-but-superseded" is informational (D5a): it is NOT a failure.
Only "invalid" causes exit 1.

CLI:
    validate_mapping_drift.py [file ...]
        Positional file args are paths to content YAML files to validate.
        Defaults to the four standard content files when none are given.

Exit codes:
    0  All values are skip, current, or valid-but-superseded.
    1  Any value classified as invalid. Failures printed to stderr.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import yaml

# Ensure scripts/hooks is on sys.path so `precommit.*` imports work both when
# this file is executed directly (e.g. by the pre-commit framework) and when
# it is imported as a package module (e.g. by pytest with pythonpath configured).
_HOOKS_DIR = Path(__file__).resolve().parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from precommit.framework_mapping import (  # noqa: E402
    DEFAULT_FRAMEWORKS_PATH,
    DEFAULT_SCHEMA_PATH,
    FrameworkMappingError,
    compose_pinned_value,
    load_pinned_patterns,
    load_registry,
    split_pinned_value,
)

# Repo root resolved from this file's location (same pattern as framework_mapping.py).
# This file lives at scripts/hooks/precommit/validate_mapping_drift.py.
_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parent.parent.parent.parent

# Default content files scanned when no positional args are supplied.
_DEFAULT_CONTENT_FILES: list[Path] = [
    _REPO_ROOT / "risk-map" / "yaml" / "risks.yaml",
    _REPO_ROOT / "risk-map" / "yaml" / "controls.yaml",
    _REPO_ROOT / "risk-map" / "yaml" / "components.yaml",
    _REPO_ROOT / "risk-map" / "yaml" / "personas.yaml",
]


def classify_value(
    fw_id: str,
    value: str,
    *,
    registry: dict[str, dict],
    pinned_patterns: dict[str, dict],
) -> tuple[str, str | None]:
    """
    Classify a single mapping value as one of the D5a states (D5/D5a).

    States: "skip" | "current" | "valid-but-superseded" | "invalid".

    Args:
        fw_id:           Framework key from the `mappings` block.
        value:           The mapping value string to classify.
        registry:        Registry dict from load_registry().
        pinned_patterns: Pinned subschemas from load_pinned_patterns().

    Returns:
        Tuple (state, detail). detail is non-None for "valid-but-superseded"
        and "invalid"; None for "skip" and "current".
    """
    # Step 1: unknown framework — skip, not fail. Drift is not the right
    # validator to report this; D4c purity validator owns that (D5a).
    if fw_id not in registry:
        return ("skip", None)

    entry = registry[fw_id]
    current_version = entry.get("version")
    is_versioned = current_version is not None

    # Step 2: unversioned framework (STRIDE, version: null).
    # D6: integrity is "pinned by enum" — membership in the closed PascalCase
    # set is the guarantee. Use compose_pinned_value to test enum membership
    # because split_pinned_value returns (value, None) for unversioned without
    # checking the enum — it cannot distinguish in-enum from legacy.
    if not is_versioned:
        try:
            compose_pinned_value(fw_id, None, value, registry=registry, pinned_patterns=pinned_patterns)
            # compose succeeded → value is in the closed enum → current.
            return ("current", None)
        except FrameworkMappingError:
            # Not in the closed enum (legacy lowercase/kebab spelling) → skip.
            return ("skip", None)

    # Step 3: versioned framework + no delimiter → legacy unpinned form.
    # D3a / H3: `@` and `:` cannot appear in any base ref or concept id,
    # so their absence unambiguously signals a legacy (pre-ADR-027) value.
    if "@" not in value and ":" not in value:
        return ("skip", None)

    # Step 4: versioned + delimiter present → pinned-intent; attempt split.
    try:
        _base_ref, ver_token = split_pinned_value(fw_id, value, registry=registry, pinned_patterns=pinned_patterns)
    except FrameworkMappingError as exc:
        # Delimiter present but split fails (unknown token, out-of-vocab base ref).
        return ("invalid", f"{value!r}: {exc}")

    # Classify the resolved version token against current and priorVersions (D5a).
    if ver_token == current_version:
        return ("current", None)

    # Check priorVersions. Entries are versionIds of the form `<id>@<version>`;
    # extract the version token (part after the last `@`) for comparison.
    prior_tokens = {
        pv.rsplit("@", 1)[1] for pv in entry.get("priorVersions", []) if isinstance(pv, str) and "@" in pv
    }
    if ver_token in prior_tokens:
        detail = f"{value!r} pinned to superseded version {ver_token!r} (current: {current_version!r})"
        return ("valid-but-superseded", detail)

    # Defensive fallback: split returned a token that is in neither set.
    # Should not occur in normal operation (split only returns recognized tokens),
    # but treat as invalid rather than silently skip.
    return ("invalid", f"{value!r}: version token {ver_token!r} not in current or priorVersions")


def _scan_file(
    path: Path,
    registry: dict[str, dict],
    pinned_patterns: dict[str, dict],
) -> tuple[list[str], list[str]]:
    """
    Parse a content YAML file and return (invalids, supersededs) message lists.

    Iterates over every top-level list-valued key (risks, controls, personas,
    description, categories, etc.) and, within each, over every dict item that
    has a `mappings` key. Scanning all list keys (not just the first) guards
    against the silent-skip bug where description/categories precede the entity
    key and would otherwise absorb the single-key scan. Items without a
    `mappings` key are skipped silently.

    Args:
        path:            Path to the content YAML file.
        registry:        Registry dict from load_registry().
        pinned_patterns: Pinned subschemas from load_pinned_patterns().

    Returns:
        Tuple (invalids, supersededs): two lists of preformatted message strings.
        invalids contains "invalid" results; supersededs contains
        "valid-but-superseded" results. "current" and "skip" produce nothing.
    """
    with open(path, encoding="utf-8") as fh:
        data: Any = yaml.safe_load(fh)

    if not isinstance(data, dict):
        return [], []

    # Scan ALL top-level list-valued keys, not just the first.
    # Real content files have `description:` (and sometimes `categories:`) as
    # lists BEFORE the entity key (risks/controls/personas); taking only the
    # first list-valued key would silently skip all entity mappings (silent-skip
    # bug). Items from non-entity lists (prose strings, category dicts) have no
    # `mappings` key and are skipped harmlessly inside the loop below.
    invalids: list[str] = []
    supersededs: list[str] = []
    for v in data.values():
        if not isinstance(v, list):
            continue
        for entity in v:
            if not isinstance(entity, dict):
                continue
            mappings = entity.get("mappings")
            if not isinstance(mappings, dict):
                continue

            entity_id = entity.get("id", "<unknown>")
            for fw_id, values in mappings.items():
                if not isinstance(values, list):
                    continue
                for value in values:
                    if not isinstance(value, str):
                        continue
                    state, detail = classify_value(
                        fw_id, value, registry=registry, pinned_patterns=pinned_patterns
                    )
                    msg = f"  {path.name}: entity={entity_id!r} framework={fw_id!r} value={value!r}"
                    if state == "invalid":
                        invalids.append(f"{msg}: {detail}")
                    elif state == "valid-but-superseded":
                        supersededs.append(f"{msg}: {detail}")

    return invalids, supersededs


def main(argv: list[str]) -> int:
    """
    Run the mapping-value drift validator. Returns 0 on success, 1 on invalid.

    "valid-but-superseded" values are reported informationally to stderr but
    do NOT cause exit 1 (D5a). Only "invalid" values cause exit 1.

    Args:
        argv: Command-line arguments (positional file paths, or empty for defaults).

    Returns:
        0 if all values are skip, current, or valid-but-superseded.
        1 if any value is invalid.
    """
    parser = argparse.ArgumentParser(
        description="Detect framework mapping-value drift in content YAML files (ADR-027 D5/D5a)."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Content YAML file paths to validate (defaults to the four standard content files).",
    )
    args = parser.parse_args(argv)

    target_paths = [Path(p) for p in args.paths] if args.paths else _DEFAULT_CONTENT_FILES

    # Load registry and pinned patterns once at runtime; pass into every
    # classify_value call. Called as bare names so monkey-patching in tests
    # can override them — mirrors validate_mapping_purity.py exactly.
    try:
        registry = load_registry(DEFAULT_FRAMEWORKS_PATH)
        pinned_patterns = load_pinned_patterns(DEFAULT_SCHEMA_PATH)
    except Exception as exc:  # noqa: BLE001
        print(f"error: failed to load framework registry or schema: {exc}", file=sys.stderr)
        return 1

    all_invalids: list[str] = []
    all_supersededs: list[str] = []

    for path in target_paths:
        if not path.is_file():
            print(f"error: content file not found: {path}", file=sys.stderr)
            return 1
        try:
            invalids, supersededs = _scan_file(path, registry, pinned_patterns)
        except Exception as exc:  # noqa: BLE001
            print(f"error: failed to scan {path}: {exc}", file=sys.stderr)
            return 1
        all_invalids.extend(invalids)
        all_supersededs.extend(supersededs)

    # Report valid-but-superseded informationally (D5a: "Pass + report informationally").
    # These are NOT failures — they surface the audit surface for D10b step 4.
    if all_supersededs:
        print(
            f"{len(all_supersededs)} mapping(s) on superseded versions:",
            file=sys.stderr,
        )
        for msg in all_supersededs:
            print(msg, file=sys.stderr)

    if all_invalids:
        print("mapping-value drift check failed:", file=sys.stderr)
        for msg in all_invalids:
            print(msg, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

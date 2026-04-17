#!/usr/bin/env python3
"""
Apply the kitchen-sink change set to a clean checkout for parity testing.

Idempotently appends a marker comment to each of the trigger files exercised
by the pre-commit hook. Intended to run inside two separate clones (one with
the bash hook installed, one with the pre-commit framework) so the resulting
commits can be compared for tree-hash equivalence.

The marker is a one-line comment using the appropriate syntax for each file
type. If the marker is already present, the file is left unchanged.

Usage:
    python scripts/hooks/tests/fixtures/precommit_parity/apply.py [--repo-root PATH]

Default repo-root is two parents up from this file's directory's parent.

Triggers exercised:
  - risk-map/yaml/components.yaml  -> component edge val + graphs + tables (xref)
  - risk-map/yaml/controls.yaml    -> control-risk val + graphs + tables (all 4)
  - risk-map/yaml/risks.yaml       -> control-risk val + graphs + tables (xrefs)
  - risk-map/yaml/personas.yaml    -> framework refs val + tables (all 4)
  - risk-map/yaml/frameworks.yaml  -> framework refs val + issue templates regen
  - scripts/TEMPLATES/new_component.template.yml -> issue templates regen
  - risk-map/diagrams/controls-graph.mermaid     -> SVG regen
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Marker text per file syntax. Each line is its own complete comment.
_YAML_MARKER = "# parity-fixture-marker: do not remove"

# Note: SVG regen is intentionally out of scope for the parity gate. The bash
# hook checks `git diff --cached` AFTER graph regen overwrites .mermaid files
# (so SVG runs only when the .mermaid actually differs from HEAD); the
# framework schedules the SVG hook at session start based on the initial
# staged set. Both produce equivalent end states when .mermaid input is
# genuinely different — but mmdc output may drift relative to HEAD across
# Chromium/mermaid-cli versions. Including a .mermaid mutation here would
# make the parity gate fail on benign tooling drift, not behavioral drift.
_TARGETS: list[tuple[str, str]] = [
    ("risk-map/yaml/components.yaml", _YAML_MARKER),
    ("risk-map/yaml/controls.yaml", _YAML_MARKER),
    ("risk-map/yaml/risks.yaml", _YAML_MARKER),
    ("risk-map/yaml/personas.yaml", _YAML_MARKER),
    ("risk-map/yaml/frameworks.yaml", _YAML_MARKER),
    ("scripts/TEMPLATES/new_component.template.yml", _YAML_MARKER),
]


def _append_marker(path: Path, marker: str) -> bool:
    """
    Append marker as a trailing line if not already present.

    Returns True if the file was modified, False if the marker was already
    present (idempotent no-op).
    """
    content = path.read_text(encoding="utf-8")
    if marker in content:
        return False
    if not content.endswith("\n"):
        content += "\n"
    content += marker + "\n"
    path.write_text(content, encoding="utf-8")
    return True


def main(argv: list[str]) -> int:
    """Apply mutations and report what changed. Returns 0 on success."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
        help="Repo root (default: inferred from this file's location).",
    )
    args = parser.parse_args(argv)

    repo_root: Path = args.repo_root
    if not (repo_root / ".git").exists():
        print(f"Error: {repo_root} does not look like a git repo (no .git dir).", file=sys.stderr)
        return 2

    modified: list[str] = []
    skipped: list[str] = []
    missing: list[str] = []

    for relpath, marker in _TARGETS:
        target = repo_root / relpath
        if not target.exists():
            missing.append(relpath)
            continue
        if _append_marker(target, marker):
            modified.append(relpath)
        else:
            skipped.append(relpath)

    print(f"Modified ({len(modified)}):")
    for m in modified:
        print(f"  + {m}")
    print(f"Skipped (marker present, {len(skipped)}):")
    for s in skipped:
        print(f"  = {s}")
    if missing:
        print(f"Missing ({len(missing)}):", file=sys.stderr)
        for m in missing:
            print(f"  ! {m}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

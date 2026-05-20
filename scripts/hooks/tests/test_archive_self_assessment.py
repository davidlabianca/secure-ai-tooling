#!/usr/bin/env python3
"""Regression lock for the ADR-021 D6 self-assessment archive.

Marker enforcement (`_legacy: true`, `_supersededBy: persona-explorer-ux`) is
in the archived schema itself and runs via `check-jsonschema` on every commit.
This file only locks the one thing the schema cannot enforce: that documented
consumer surfaces no longer reference the pre-archive top-level paths.

ADR-021 is intentionally excluded from the sweep — it documents the archival
decision and must retain the historical paths as decision context.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parents[3]
OLD_YAML_PATH = "risk-map/yaml/self-assessment.yaml"
OLD_SCHEMA_PATH = "risk-map/schemas/self-assessment.schema.json"

CONSUMER_SURFACES = [
    "risk-map/README.md",
    "risk-map/docs/persona-pages.md",
    "risk-map/docs/design/risk-id-migration.md",
    "scripts/docs/hook-validations.md",
    "scripts/docs/validation-flow.md",
    "scripts/agents/content-reviewer.md",
    ".github/workflows/validation.yml",
    ".pre-commit-config.yaml",
]


@pytest.mark.parametrize("surface", CONSUMER_SURFACES)
@pytest.mark.parametrize("old_path", [OLD_YAML_PATH, OLD_SCHEMA_PATH])
def test_consumer_surfaces_drop_pre_archive_path(surface, old_path):
    """Each consumer surface must contain no occurrence of the pre-archive path."""
    text = (REPO_ROOT / surface).read_text(encoding="utf-8")
    assert old_path not in text, (
        f"{surface} still references pre-archive path {old_path!r}; "
        "update to the archive path or remove the reference."
    )


@pytest.mark.parametrize("old_path", [OLD_YAML_PATH, OLD_SCHEMA_PATH])
def test_adr_021_retains_historical_paths(old_path):
    """ADR-021 must keep the pre-archive paths as decision context.

    Anti-regression against a future "scrub all old paths" sweep that would
    otherwise strip the supersession rationale from the ADR documenting the move.
    """
    adr = (REPO_ROOT / "docs/adr/021-personas-and-self-assessment-schema.md").read_text(encoding="utf-8")
    assert old_path in adr, (
        f"docs/adr/021-personas-and-self-assessment-schema.md must retain "
        f"pre-archive path {old_path!r} as decision context"
    )

#!/usr/bin/env python3
"""
Generation smoke tests: componentsTools does not crash graph/table generation.

ADR-030 (docs/adr/030-agentic-component-model.md), Consequences: "The
landing commit is large — not a two-file edit. The atomic schema+YAML core
drives the pre-commit generators to rebuild ~23 tracked artifacts from the
corpus (7 diagrams + 4 SVGs + 12 tables under risk-map/)..." and Migration
sequencing step 4 names "table/SVG regeneration" as part of consumer wiring.

This module exercises the ACTUAL generator entry points — the same ones the
pre-commit hooks (scripts/hooks/precommit/regenerate_graphs.py,
regenerate_tables.py) shell out to — against a synthetic corpus containing a
componentsTools component, via subprocess so argument parsing / file-writing
/ CLI plumbing is covered, not just the underlying graph classes.

Scope note (verified 2026-07-17): risk-map/svg/ generation
(scripts/hooks/precommit/regenerate_svgs.py) invokes `npx mmdc`, which
requires a headless Chromium binary. This sandbox has no Chromium installed
(`npx mmdc` fails with "Could not find Chrome"), so real SVG rendering is not
exercised here — regenerate_svgs.py's own test suite
(test_regenerate_svgs.py) already covers that script's logic with a mocked
subprocess, which is the appropriate boundary for an external-binary
dependency. This module instead covers the two generation layers that DO run
natively in Python: the Mermaid-source generators (ComponentGraph/
ControlGraph/RiskGraph, driving the risk-map/diagrams/*.mmd / *.md inputs
that regenerate_svgs.py would otherwise convert) and the Markdown table
generator (yaml_to_markdown.py, driving risk-map/tables/*.md).

Verified 2026-07-17 (pre-implementation): none of these generators crash on
an unrecognized 4th top-level category today — ComponentGraph/ControlGraph
group components generically by whatever `.category` string is present, and
yaml_to_markdown.py's table columns just read `.get("category", "")`. These
tests are therefore GREEN today (regression guards, not red-phase drivers);
the red-phase coverage for componentsTools consumer wiring lives in
test_mermaid_styles_tools_category.py (the missing style line) and
test_category_ownership_guard.py (the missing CI guard). This module's job is
to make sure that gap-closing work does not later introduce a crash.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

_VALIDATE_SCRIPT = Path(__file__).parent.parent / "validate_riskmap.py"
_YAML_TO_MARKDOWN_SCRIPT = Path(__file__).parent.parent / "yaml_to_markdown.py"

# A synthetic corpus with one component in each of the 3 legacy categories
# plus one in componentsTools/componentsToolCore, wired into a small
# connected graph (no isolated nodes, though CLI tests below also pass
# --allow-isolated as a belt-and-suspenders measure).
_COMPONENTS_WITH_TOOLS: dict[str, Any] = {
    "id": "components",
    "title": "Test Components",
    "description": ["d"],
    "categories": [
        {
            "id": "componentsInfrastructure",
            "title": "Infrastructure",
            "subcategory": [{"id": "componentsData", "title": "Data"}],
        },
        {
            "id": "componentsTools",
            "title": "Tools",
            "subcategory": [{"id": "componentsToolCore", "title": "Tool Core"}],
        },
    ],
    "components": [
        {
            "id": "compInfra",
            "title": "Infra",
            "description": ["d"],
            "category": "componentsInfrastructure",
            "subcategory": "componentsData",
            "edges": {"to": ["compTool"], "from": []},
        },
        {
            "id": "compTool",
            "title": "Tool",
            "description": ["d"],
            "category": "componentsTools",
            "subcategory": "componentsToolCore",
            "edges": {"to": [], "from": ["compInfra"]},
        },
    ],
}

_CONTROLS_WITH_TOOLS: dict[str, Any] = {
    "controls": [
        {
            "id": "ctrlTool",
            "title": "Tool Control",
            "category": "controlsData",
            "components": ["compTool"],
            "risks": [],
            "personas": ["personaX"],
        }
    ]
}


def _write_corpus(base: Path) -> Path:
    yaml_dir = base / "risk-map" / "yaml"
    yaml_dir.mkdir(parents=True, exist_ok=True)
    (yaml_dir / "components.yaml").write_text(yaml.dump(_COMPONENTS_WITH_TOOLS), encoding="utf-8")
    (yaml_dir / "controls.yaml").write_text(yaml.dump(_CONTROLS_WITH_TOOLS), encoding="utf-8")
    (yaml_dir / "risks.yaml").write_text(yaml.dump({"risks": []}), encoding="utf-8")
    return base


@pytest.fixture
def synthetic_corpus(tmp_path: Path) -> Path:
    """A tmp_path corpus containing a componentsTools component, wired cleanly."""
    return _write_corpus(tmp_path)


# ============================================================================
# Mermaid graph generation (ComponentGraph / ControlGraph / RiskGraph via CLI)
# ============================================================================


class TestGraphGenerationDoesNotCrashOnComponentsTools:
    """validate_riskmap.py --to-graph / --to-controls-graph / --to-risk-graph."""

    def test_component_graph_generation_succeeds(self, synthetic_corpus: Path):
        """
        Given: a synthetic corpus with a componentsTools component
        When: validate_riskmap.py --to-graph is run against it
        Then: exit 0, and the output file contains 'componentsTools'
        """
        out_file = synthetic_corpus / "graph.md"
        result = subprocess.run(
            [
                sys.executable,
                str(_VALIDATE_SCRIPT),
                "--force",
                "--allow-isolated",
                "--to-graph",
                str(out_file),
                "--quiet",
            ],
            capture_output=True,
            text=True,
            cwd=str(synthetic_corpus),
        )
        assert result.returncode == 0, (
            f"Expected exit 0 generating a component graph with a componentsTools "
            f"component; got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out_file.is_file(), f"Expected graph output file at {out_file}"
        content = out_file.read_text(encoding="utf-8")
        assert "componentsTools" in content, f"Expected 'componentsTools' in graph output; got:\n{content}"

    def test_controls_graph_generation_succeeds(self, synthetic_corpus: Path):
        """
        Given: a synthetic corpus with a componentsTools component and a
               control mapped to it
        When: validate_riskmap.py --to-controls-graph is run against it
        Then: exit 0, and the output file contains 'componentsTools'
        """
        out_file = synthetic_corpus / "controls_graph.md"
        result = subprocess.run(
            [
                sys.executable,
                str(_VALIDATE_SCRIPT),
                "--force",
                "--allow-isolated",
                "--to-controls-graph",
                str(out_file),
                "--quiet",
            ],
            capture_output=True,
            text=True,
            cwd=str(synthetic_corpus),
        )
        assert result.returncode == 0, (
            f"Expected exit 0 generating a controls graph with a componentsTools "
            f"component; got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out_file.is_file(), f"Expected graph output file at {out_file}"
        content = out_file.read_text(encoding="utf-8")
        assert "componentsTools" in content, (
            f"Expected 'componentsTools' in controls graph output; got:\n{content}"
        )

    def test_risk_graph_generation_succeeds(self, synthetic_corpus: Path):
        """
        Given: a synthetic corpus with a componentsTools component (risks.yaml
               is empty; the risk graph should still generate without crashing)
        When: validate_riskmap.py --to-risk-graph is run against it
        Then: exit 0
        """
        out_file = synthetic_corpus / "risk_graph.md"
        result = subprocess.run(
            [
                sys.executable,
                str(_VALIDATE_SCRIPT),
                "--force",
                "--allow-isolated",
                "--to-risk-graph",
                str(out_file),
                "--quiet",
            ],
            capture_output=True,
            text=True,
            cwd=str(synthetic_corpus),
        )
        assert result.returncode == 0, (
            f"Expected exit 0 generating a risk graph with a componentsTools "
            f"component present; got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out_file.is_file(), f"Expected graph output file at {out_file}"


# ============================================================================
# Markdown table generation (yaml_to_markdown.py)
# ============================================================================


class TestTableGenerationDoesNotCrashOnComponentsTools:
    """yaml_to_markdown.py components --file <synthetic> ..."""

    def test_components_full_table_generation_succeeds(self, synthetic_corpus: Path):
        """
        Given: a synthetic components.yaml with a componentsTools component
        When: yaml_to_markdown.py components --format full is run against it
        Then: exit 0, and the output contains 'componentsTools'
        """
        components_yaml = synthetic_corpus / "risk-map" / "yaml" / "components.yaml"
        out_file = synthetic_corpus / "components-full.md"
        result = subprocess.run(
            [
                sys.executable,
                str(_YAML_TO_MARKDOWN_SCRIPT),
                "components",
                "--file",
                str(components_yaml),
                "--format",
                "full",
                "-o",
                str(out_file),
                "--quiet",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Expected exit 0 generating a components table with a componentsTools "
            f"component; got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out_file.is_file(), f"Expected table output file at {out_file}"
        content = out_file.read_text(encoding="utf-8")
        assert "componentsTools" in content, f"Expected 'componentsTools' in table output; got:\n{content}"

    def test_components_summary_table_generation_succeeds(self, synthetic_corpus: Path):
        """
        Given: a synthetic components.yaml with a componentsTools component
        When: yaml_to_markdown.py components --format summary is run against it
        Then: exit 0, and the output contains 'componentsTools'
        """
        components_yaml = synthetic_corpus / "risk-map" / "yaml" / "components.yaml"
        out_file = synthetic_corpus / "components-summary.md"
        result = subprocess.run(
            [
                sys.executable,
                str(_YAML_TO_MARKDOWN_SCRIPT),
                "components",
                "--file",
                str(components_yaml),
                "--format",
                "summary",
                "-o",
                str(out_file),
                "--quiet",
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Expected exit 0 generating a components summary table; got "
            f"{result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        content = out_file.read_text(encoding="utf-8")
        assert "componentsTools" in content, f"Expected 'componentsTools' in summary table; got:\n{content}"


# ============================================================================
# Live corpus, today's shape — baseline regression
# ============================================================================


class TestLiveCorpusGenerationBaseline:
    """
    Baseline: generation against TODAY's live corpus (pre-ADR-030, no
    componentsTools yet) must keep working. Not a componentsTools-specific
    test, but guards against this module's synthetic-corpus tests
    accidentally masking a live-corpus regression introduced elsewhere.
    """

    def test_live_component_graph_generation_succeeds(self, tmp_path: Path):
        """
        Given: the real repo as cwd
        When: validate_riskmap.py --to-graph is run
        Then: exit 0
        """
        repo_root = Path(__file__).resolve().parent.parent.parent.parent
        out_file = tmp_path / "graph.md"
        result = subprocess.run(
            [
                sys.executable,
                str(_VALIDATE_SCRIPT),
                "--force",
                "--allow-isolated",
                "--to-graph",
                str(out_file),
                "--quiet",
            ],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
        assert result.returncode == 0, (
            f"Expected exit 0 generating the live component graph; got "
            f"{result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out_file.is_file()


# ============================================================================
# Test Summary
# ============================================================================
"""
Test Summary
============
Total Tests: 6

- TestGraphGenerationDoesNotCrashOnComponentsTools (3): component graph,
  controls graph, risk graph — all via validate_riskmap.py subprocess CLI
  against a synthetic componentsTools corpus.
- TestTableGenerationDoesNotCrashOnComponentsTools (2): full + summary
  components tables via yaml_to_markdown.py subprocess CLI.
- TestLiveCorpusGenerationBaseline (1): today's live corpus still generates.

All 6 are GREEN today (verified 2026-07-17) — none of these generators crash
or choke on an unrecognized 4th top-level category; they are regression
guards protecting the componentsTools consumer-wiring work (schema, yaml,
mermaid-styles.yaml, the new CI guard — see test_components_schema_tools_category.py,
test_components_yaml_tools_category.py, test_mermaid_styles_tools_category.py,
test_category_ownership_guard.py for the red-phase tests) from introducing a
crash while closing those gaps.

Out of scope (documented, not silently skipped): risk-map/svg/ generation
via `npx mmdc` requires a headless Chromium binary not present in this
sandbox. regenerate_svgs.py's own mocked-subprocess test suite
(test_regenerate_svgs.py) is the appropriate coverage boundary for that
external dependency.
"""

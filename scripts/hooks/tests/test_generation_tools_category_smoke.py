#!/usr/bin/env python3
"""
Generation smoke tests: componentsExternalTools does not crash graph/table generation.

ADR-030 (docs/adr/030-agentic-component-model.md), Consequences: "The
landing change is large. The atomic core drives the pre-commit generators
to rebuild the tracked diagrams, SVGs, and tables under risk-map/, requires
a mermaid-styles.yaml entry for the new category, and forces updates across
the category-handling, nesting, rendering, models, and controls<->components
mirror test suites." Migration sequencing step 4 names "table/SVG
regeneration" as part of consumer wiring.

This module exercises the ACTUAL generator entry points — the same ones the
pre-commit hooks (scripts/hooks/precommit/regenerate_graphs.py,
regenerate_tables.py) shell out to — against a synthetic corpus containing a
componentsExternalTools component, via subprocess so argument parsing / file-writing
/ CLI plumbing is covered, not just the underlying graph classes.

Scope note: risk-map/svg/ generation
(scripts/hooks/precommit/regenerate_svgs.py) invokes `npx mmdc`, which shells
out to an external headless Chromium binary. Real SVG rendering is therefore
outside this module's boundary regardless of whether that binary is
installed — regenerate_svgs.py's own test suite (test_regenerate_svgs.py)
covers that script's logic with a mocked subprocess, which is the coverage
boundary for an external-binary dependency. This module instead covers the
two generation layers that run natively in Python: the Mermaid-source
generator (ComponentGraph, driving the risk-map/diagrams/*.mermaid / *.md
inputs that regenerate_svgs.py would otherwise convert) and the Markdown
table generator (yaml_to_markdown.py, driving risk-map/tables/*.md). #499
removed the other two Mermaid-source generators and their CLI flags along
with the diagrams they produced; only the component graph survives as a
generator this module can smoke-test.

None of these generators crash on a 4th top-level
category — ComponentGraph groups components generically by whatever
`.category` string is present, and yaml_to_markdown.py's table columns just
read `.get("category", "")`. These tests are regression guards,
not the tests that exercise componentsExternalTools-specific new behavior; that
coverage — the mermaid style entry and the category style CI guard — lives in
test_mermaid_styles_tools_category.py and test_category_style_guard.py
respectively. This module's job is to make sure that gap-closing work does
not introduce a crash.
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
# plus one in componentsExternalTools/componentsToolInvocationPath, wired into a small
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
            "id": "componentsExternalTools",
            "title": "Tools",
            "subcategory": [{"id": "componentsToolInvocationPath", "title": "Tool Core"}],
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
            "category": "componentsExternalTools",
            "subcategory": "componentsToolInvocationPath",
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
    """A tmp_path corpus containing a componentsExternalTools component, wired cleanly."""
    return _write_corpus(tmp_path)


# ============================================================================
# Mermaid graph generation (ComponentGraph via CLI)
# ============================================================================


class TestGraphGenerationDoesNotCrashOnComponentsTools:
    """validate_riskmap.py --to-graph."""

    def test_component_graph_generation_succeeds(self, synthetic_corpus: Path):
        """
        Given: a synthetic corpus with a componentsExternalTools component
        When: validate_riskmap.py --to-graph is run against it
        Then: exit 0, and the output file contains 'componentsExternalTools'
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
            f"Expected exit 0 generating a component graph with a componentsExternalTools "
            f"component; got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out_file.is_file(), f"Expected graph output file at {out_file}"
        content = out_file.read_text(encoding="utf-8")
        assert "componentsExternalTools" in content, (
            f"Expected 'componentsExternalTools' in graph output; got:\n{content}"
        )


# ============================================================================
# Markdown table generation (yaml_to_markdown.py)
# ============================================================================


class TestTableGenerationDoesNotCrashOnComponentsTools:
    """yaml_to_markdown.py components --file <synthetic> ..."""

    def test_components_full_table_generation_succeeds(self, synthetic_corpus: Path):
        """
        Given: a synthetic components.yaml with a componentsExternalTools component
        When: yaml_to_markdown.py components --format full is run against it
        Then: exit 0, and the output contains 'componentsExternalTools'
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
            f"Expected exit 0 generating a components table with a componentsExternalTools "
            f"component; got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out_file.is_file(), f"Expected table output file at {out_file}"
        content = out_file.read_text(encoding="utf-8")
        assert "componentsExternalTools" in content, (
            f"Expected 'componentsExternalTools' in table output; got:\n{content}"
        )

    def test_components_summary_table_generation_succeeds(self, synthetic_corpus: Path):
        """
        Given: a synthetic components.yaml with a componentsExternalTools component
        When: yaml_to_markdown.py components --format summary is run against it
        Then: exit 0, and the output contains 'componentsExternalTools'
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
        assert "componentsExternalTools" in content, (
            f"Expected 'componentsExternalTools' in summary table; got:\n{content}"
        )


# ============================================================================
# Live corpus, today's shape — baseline regression
# ============================================================================


class TestLiveCorpusGenerationBaseline:
    """
    Baseline: generation against TODAY's live corpus (pre-ADR-030, no
    componentsExternalTools yet) must keep working. Not a componentsExternalTools-specific
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
Total Tests: 4

- TestGraphGenerationDoesNotCrashOnComponentsTools (1): component graph via
  validate_riskmap.py subprocess CLI against a synthetic
  componentsExternalTools corpus.
- TestTableGenerationDoesNotCrashOnComponentsTools (2): full + summary
  components tables via yaml_to_markdown.py subprocess CLI.
- TestLiveCorpusGenerationBaseline (1): the live corpus still generates.

None of these generators crash or choke on the 4th top-level category; they
are regression guards protecting the componentsExternalTools consumer-wiring work
(schema, yaml, mermaid-styles.yaml, the new CI guard — see
test_components_schema_tools_category.py,
test_components_yaml_tools_category.py, test_mermaid_styles_tools_category.py,
test_category_style_guard.py for that coverage) from a future regression
introducing a crash.

Out of scope (documented, not silently skipped): risk-map/svg/ generation
via `npx mmdc` requires an external headless Chromium binary, so it is not
exercised in-process here. regenerate_svgs.py's own mocked-subprocess test
suite (test_regenerate_svgs.py) is the coverage boundary for that external
dependency.
"""

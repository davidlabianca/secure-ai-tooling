#!/usr/bin/env python3
"""
Real end-to-end subprocess tests for the `--emission-mode` CLI override
(ADR-036 D3; plan decision P8;
`working-plans/component-graph-decouple-strategy-c-implementation-plan.md`
§F, Phase 3 task 3.1).

Coverage-gap G4/G5 (adversarial review of the RED suite): every existing
`--emission-mode` test in `test_validate_riskmap.py::TestEmissionModeCLIOverride`
mocks `ComponentGraph` -- none of them run the REAL pipeline (CLI -> argparse
-> `MermaidConfigLoader` -> `ComponentGraph.build_graph()` -> `_emit_decoupled()`
-> its own D7 self-check) in one process, and none of them combine the
override with `--block` and a drift condition simultaneously. Nor does any
existing test pin P8's own stated contract ("Config remains the source of
truth; the flag never persists") against the actual file on disk.

This file closes both gaps with subprocess-based, unmocked runs of
`validate_riskmap.py` against synthetic on-disk corpora (and, for the
persistence check, the live repo). It deliberately duplicates the small
corpus-writing helpers already used by `test_emission_drift_guard.py`
rather than importing them, matching this repo's established per-file
independence convention for CLI-wiring test suites (see that file's own
module docstring for the same rationale).

RED phase: every test below fails today because `--emission-mode` is not
yet a recognized argparse flag (`parse_args()` raises SystemExit(2) with
"unrecognized arguments"). GREEN once task 3.3's `swe` step wires the flag
through to `ComponentGraph`'s `config_loader=`.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = Path(__file__).parent.parent / "validate_riskmap.py"

# ---------------------------------------------------------------------------
# Synthetic corpus -- same 4-category shape as test_emission_drift_guard.py's
# _CLEAN_COMPONENTS / _CLEAN_CONTROLS (duplicated per this file's own
# independence rationale above), plus a portStyles block so a real decoupled
# render actually draws `classDef port` (see component_graph.py
# `_decoupled_classdefs`: the classDef line is emitted whenever the config
# supplies the style, independent of whether the particular plan uses any
# port node -- confirmed against the real emitter before writing this test).
# ---------------------------------------------------------------------------

_COMPONENTS: dict[str, Any] = {
    "components": [
        {
            "id": "compInfra",
            "title": "Infra",
            "category": "componentsInfrastructure",
            "subcategory": "componentsData",
            "edges": {},
        },
        {
            "id": "compModel",
            "title": "Model",
            "category": "componentsModel",
            "subcategory": "componentsModelTraining",
            "edges": {},
        },
        {
            "id": "compApp",
            "title": "App",
            "category": "componentsApplication",
            "subcategory": "componentsAgent",
            "edges": {},
        },
        {
            "id": "compTools",
            "title": "Tools",
            "category": "componentsTools",
            "subcategory": "componentsToolCore",
            "edges": {},
        },
    ],
    "categories": [
        {
            "id": "componentsInfrastructure",
            "title": "Infrastructure",
            "subcategory": [{"id": "componentsData", "title": "Data"}],
        },
        {
            "id": "componentsModel",
            "title": "Model",
            "subcategory": [{"id": "componentsModelTraining", "title": "Model Training"}],
        },
        {
            "id": "componentsApplication",
            "title": "Application",
            "subcategory": [{"id": "componentsAgent", "title": "Agent"}],
        },
        {
            "id": "componentsTools",
            "title": "Tools",
            "subcategory": [{"id": "componentsToolCore", "title": "Tool Core"}],
        },
    ],
}

_CONTROLS: dict[str, Any] = {
    "controls": [
        {
            "id": "ctrlInfra",
            "title": "Infra Ctrl",
            "category": "controlsInfrastructure",
            "components": ["compInfra"],
            "risks": [],
            "personas": ["personaX"],
        },
        {
            "id": "ctrlModel",
            "title": "Model Ctrl",
            "category": "controlsModel",
            "components": ["compModel"],
            "risks": [],
            "personas": ["personaX"],
        },
        {
            "id": "ctrlApp",
            "title": "App Ctrl",
            "category": "controlsApplication",
            "components": ["compApp"],
            "risks": [],
            "personas": ["personaX"],
        },
        {
            "id": "ctrlTools",
            "title": "Tools Ctrl",
            "category": "controlsApplication",
            "components": ["compTools"],
            "risks": [],
            "personas": ["personaX"],
        },
    ]
}

_PORT_STYLES = {
    "port": "fill:#fff5f5,stroke:#c0392b,stroke-width:1.5px,stroke-dasharray:4 3",
    "pepport": "fill:#eef,stroke:#339,stroke-width:1.5px",
    "pepWrapOutline": "fill:none,stroke:#339,stroke-width:2px",
}

# Committed mermaid-styles.yaml carries mode: flat -- the override must flip
# the EFFECTIVE mode to decoupled without touching this value.
_CLEAN_EMISSION = {"mode": "flat", "portStyles": _PORT_STYLES}

# Same stale-aspect-id drift trigger used by test_emission_drift_guard.py
# (G-A1, test_decouple_guards.py::TestGA1AspectIdAbsentFromCorpus) --
# reused here because it's already established as the minimal, zero-edges-
# required drift condition; confirmed (see this task's investigation) that
# build_decoupled_plan() degrades it to a warning rather than raising, so it
# is a genuine "drift fires, graph still wouldn't build if reached" fixture
# -- though with --block the run must exit before graph generation.
_DIRTY_EMISSION = {
    "mode": "flat",
    "aspects": [{"id": "componentDoesNotExistInCorpus", "minCrossInDegree": 1}],
    "portStyles": _PORT_STYLES,
}


def _mermaid_styles(emission: dict[str, Any]) -> dict[str, Any]:
    return {
        "version": "1.0.0",
        "foundation": {"colors": {}, "strokeWidths": {}, "strokePatterns": {}},
        "sharedElements": {
            "cssClasses": {"hidden": "display: none;", "allControl": "stroke:#000,stroke-width:1px"},
            "componentCategories": {
                "componentsInfrastructure": {"fill": "#e6f3e6", "stroke": "#333333", "strokeWidth": "2px"},
                "componentsModel": {"fill": "#ffe6e6", "stroke": "#333333", "strokeWidth": "2px"},
                "componentsApplication": {"fill": "#e6f0ff", "stroke": "#333333", "strokeWidth": "2px"},
                "componentsTools": {"fill": "#fff3e6", "stroke": "#333333", "strokeWidth": "2px"},
            },
        },
        "graphTypes": {
            "component": {"direction": "TD", "flowchartConfig": {}, "emission": emission},
            "control": {"direction": "LR", "flowchartConfig": {}},
            "risk": {"direction": "LR", "flowchartConfig": {}},
        },
    }


def _write_corpus(base: Path, emission: dict[str, Any]) -> Path:
    """Write the 4-file synthetic corpus (components/controls/risks/mermaid-styles)."""
    yaml_dir = base / "risk-map" / "yaml"
    yaml_dir.mkdir(parents=True, exist_ok=True)
    (yaml_dir / "components.yaml").write_text(yaml.dump(_COMPONENTS), encoding="utf-8")
    (yaml_dir / "controls.yaml").write_text(yaml.dump(_CONTROLS), encoding="utf-8")
    (yaml_dir / "risks.yaml").write_text(yaml.dump({"risks": []}), encoding="utf-8")
    (yaml_dir / "mermaid-styles.yaml").write_text(yaml.dump(_mermaid_styles(emission)), encoding="utf-8")
    return base


def _run(cwd: Path, *extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--force", "--allow-isolated", *extra_args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


# ============================================================================
# G4 -- P8's "the flag never persists" contract
# ============================================================================


class TestEmissionModeFlagDoesNotPersist:
    def test_override_on_synthetic_corpus_does_not_mutate_mermaid_styles_yaml(self, tmp_path):
        """
        Given: a synthetic corpus whose mermaid-styles.yaml says mode: flat
        When: validate_riskmap.py --force --allow-isolated --to-graph <path>
              --emission-mode decoupled runs (a full pipeline run, not just
              argument parsing)
        Then: mermaid-styles.yaml on disk is byte-identical before and after

        P8: "Config remains the source of truth; the flag never persists."
        A regression here would mean the CLI override is implemented by
        writing the override back into the config file (or otherwise
        mutating it) rather than passing an in-memory override through
        `config_loader=` -- silently corrupting the committed mode value on
        the next real invocation.
        """
        _write_corpus(tmp_path, _CLEAN_EMISSION)
        styles_path = tmp_path / "risk-map" / "yaml" / "mermaid-styles.yaml"
        before = styles_path.read_bytes()

        out = tmp_path / "out.md"
        result = _run(tmp_path, "--to-graph", str(out), "--emission-mode", "decoupled")

        after = styles_path.read_bytes()
        assert after == before, (
            f"mermaid-styles.yaml must be byte-identical after an --emission-mode run "
            f"(P8: the flag never persists). Exit code: {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_override_on_live_repo_corpus_does_not_mutate_the_committed_file(self):
        """
        Same persistence guard, run against the actual repo as cwd (no
        --to-graph, so no file-write side effect other than the config read
        itself) -- proves the override never touches the real, committed
        risk-map/yaml/mermaid-styles.yaml, not just a synthetic copy.
        """
        styles_path = _REPO_ROOT / "risk-map" / "yaml" / "mermaid-styles.yaml"
        before = styles_path.read_bytes()

        result = _run(_REPO_ROOT, "--emission-mode", "decoupled")

        after = styles_path.read_bytes()
        assert after == before, (
            f"The live, committed mermaid-styles.yaml must be byte-identical after an "
            f"--emission-mode run. Exit code: {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ============================================================================
# G5 -- real end-to-end pipeline: CLI -> loader -> build_graph() -> self-check
# ============================================================================


class TestEmissionModeRealPipelineEndToEnd:
    def test_decoupled_override_with_block_and_clean_registry_exits_0_with_decoupled_marker(self, tmp_path):
        """
        Given: a synthetic corpus + valid (non-drifted) emission registry
        When: validate_riskmap.py --emission-mode decoupled --block --to-graph
              <path> runs (ComponentGraph NOT mocked -- the real
              build_graph() -> _emit_decoupled() -> D7 self-check path)
        Then: exit 0, and the output file contains a decoupled-mode marker
              (`classDef port`, drawn whenever `portStyles.port` is
              configured -- confirmed against the real emitter)

        This is the single most direct proof that the CLI override reaches
        graph construction: every existing --emission-mode test mocks
        ComponentGraph, so none of them would catch a wiring bug where the
        override is parsed but never actually reaches
        `MermaidConfigLoader.get_emission_config()`.
        """
        _write_corpus(tmp_path, _CLEAN_EMISSION)
        out = tmp_path / "out.md"

        result = _run(tmp_path, "--to-graph", str(out), "--emission-mode", "decoupled", "--block")

        assert result.returncode == 0, (
            f"Expected exit 0 for a clean registry with --emission-mode decoupled --block.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out.exists(), "Expected the graph output file to be written"
        content = out.read_text(encoding="utf-8")
        assert "classDef port" in content, (
            f"Expected a decoupled-mode marker ('classDef port') in the generated graph, "
            f"proving --emission-mode decoupled actually reached ComponentGraph.build_graph(); "
            f"got:\n{content}"
        )

    def test_decoupled_override_with_block_and_dirty_registry_exits_1_distinct_from_self_check(self, tmp_path):
        """
        Given: the same corpus, but the emission registry has a drifted
               (stale) aspect id
        When: validate_riskmap.py --emission-mode decoupled --block --to-graph
              <path> runs
        Then: exit 1, the drift warning (naming the stale id) is visible,
              and this is distinguishable from any D7 self-check failure --
              the unified warn-only exit (validate_riskmap.py's
              `warn_block_triggered` block) fires BEFORE `--to-graph`
              generation is ever attempted, so no self-check output (or
              output file) exists in this run at all. A future
              implementation that reordered the emission-drift check to run
              AFTER graph generation would still exit 1 here (masking the
              reorder) unless this test also confirms the output file was
              never written.
        """
        _write_corpus(tmp_path, _DIRTY_EMISSION)
        out = tmp_path / "out.md"

        result = _run(tmp_path, "--to-graph", str(out), "--emission-mode", "decoupled", "--block")
        combined = result.stdout + result.stderr

        assert result.returncode == 1, (
            f"Expected exit 1 for a drifted registry with --block.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "componentDoesNotExistInCorpus" in combined, (
            f"Expected the drift warning naming the stale aspect id; got:\n{combined}"
        )
        assert not out.exists(), (
            "The unified warn-only exit must fire before --to-graph generation is "
            "attempted, so no output file should exist when --block promotes a "
            f"drift warning to an error. Found: {out.exists()}\ncombined output:\n{combined}"
        )

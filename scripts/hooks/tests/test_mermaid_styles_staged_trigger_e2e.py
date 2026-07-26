#!/usr/bin/env python3
"""
Real end-to-end (real git, real subprocess) test that a commit staging only
`risk-map/yaml/mermaid-styles.yaml` actually reaches `--to-graph` generation
in `validate_riskmap.py` (ADR-036 Phase 3 P7;
`docs/adr/036-decoupled-component-graph-emission.md`).

This closes the gap left by `test_utils.py::TestGetStagedYAMLFiles` (which
proves `get_staged_yaml_files()` returns the right Path list in isolation,
via a mocked `subprocess.run`) and `test_regenerate_graphs.py::
TestMermaidStylesTrigger` (which proves `regenerate_graphs.py` dispatches
the right `validate_riskmap.py` subprocess calls, but mocks
`subprocess.run` so `validate_riskmap.py` itself never actually executes).
Neither test exercises the real chain: a genuine `git diff --cached
--name-only` in a real repository, feeding a real `get_staged_yaml_files()`
call, feeding a real `main()` run of `validate_riskmap.py`, all the way
through to a written graph file.

Unlike `test_emission_mode_e2e.py` and the `run_validate_riskmap` fixture in
conftest.py, this file deliberately does NOT pass `--force`: the bug this
guards against only reproduces when `validate_riskmap.py` is invoked the way
`regenerate_graphs.py` actually invokes it (no `--force`), so the git-staged
detection path in `get_staged_yaml_files()` must be exercised for real.

`get_staged_yaml_files()`'s `target_files` list (utils.py:221-226) includes
`mermaid-styles.yaml`, so a commit staging only that file reaches the
`--to-graph` block and the graph output file is written. This suite was RED
before that file was added to `target_files` (ADR-036 Phase 3 P7's decided
fix); it is retained as the regression pin.
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "hooks" / "validate_riskmap.py"
_REAL_COMPONENTS_YAML = _REPO_ROOT / "risk-map" / "yaml" / "components.yaml"
_REAL_MERMAID_STYLES_YAML = _REPO_ROOT / "risk-map" / "yaml" / "mermaid-styles.yaml"

# Git honors GIT_DIR/GIT_WORK_TREE/GIT_INDEX_FILE over cwd-based discovery, and
# githooks(5) says git exports exactly these when invoking a hook. If pytest ever
# ran nested inside a git hook, every subprocess call below -- including the one
# under test -- would silently resolve to the outer repo instead of the scratch
# one. Stripping them keeps discovery pinned to `cwd` unconditionally.
_CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run a git command with a fixed local identity so commits never depend on global config."""
    return subprocess.run(
        [
            "git",
            "-c",
            "user.email=test@example.com",
            "-c",
            "user.name=Test",
            *args,
        ],
        cwd=str(cwd),
        env=_CLEAN_ENV,
        capture_output=True,
        text=True,
        check=True,
    )


def _build_scratch_repo(base: Path) -> Path:
    """
    Build a scratch git repo containing only the real, currently-valid
    components.yaml, committed as a baseline.

    Using the real repo's components.yaml (rather than a synthetic minimal
    corpus) sidesteps needing --allow-isolated or any other flag beyond the
    exact regenerate_graphs.py invocation shape (--to-graph <path> -m
    --quiet, no --force, no --allow-isolated): the committed file already
    passes ComponentEdgeValidator with no isolated/missing-edge errors,
    which is a precondition of the pre-commit hooks that gate merges to
    this repo. mermaid-styles.yaml is deliberately NOT part of the baseline
    commit -- it is added and staged afterward by each test so that `git
    diff --cached --name-only` reports exactly the file under test.
    """
    yaml_dir = base / "risk-map" / "yaml"
    yaml_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(_REAL_COMPONENTS_YAML, yaml_dir / "components.yaml")

    _git(base, "init", "-q")
    _git(base, "add", "risk-map/yaml/components.yaml")
    _git(base, "commit", "-q", "-m", "baseline: components.yaml only")

    return base


def _stage_mermaid_styles(repo: Path) -> None:
    """Copy the real, currently-valid mermaid-styles.yaml into the repo and stage it (only it)."""
    yaml_dir = repo / "risk-map" / "yaml"
    shutil.copy(_REAL_MERMAID_STYLES_YAML, yaml_dir / "mermaid-styles.yaml")
    _git(repo, "add", "risk-map/yaml/mermaid-styles.yaml")


def _run_validate_riskmap(repo: Path, out_path: Path) -> subprocess.CompletedProcess:
    """
    Invoke validate_riskmap.py with the exact argv shape regenerate_graphs.py
    uses for risk-map-graph generation (CMD_RISK_MAP in
    test_regenerate_graphs.py): --to-graph <path> -m --quiet, no --force.
    """
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--to-graph", str(out_path), "-m", "--quiet"],
        cwd=str(repo),
        env=_CLEAN_ENV,
        capture_output=True,
        text=True,
    )


class TestMermaidStylesOnlyStagedReachesToGraph:
    """
    Proves a mermaid-styles.yaml-only staged commit reaches --to-graph
    generation via the real git-staged-file discovery path (no --force).
    """

    def test_staged_mermaid_styles_only_writes_graph_output_file(self, tmp_path):
        """
        Given: a scratch git repo with a valid, committed components.yaml,
               and mermaid-styles.yaml staged as the ONLY change
        When: validate_riskmap.py --to-graph <path> -m --quiet runs (the
              exact regenerate_graphs.py invocation shape, no --force)
        Then: the graph output file is actually written to disk

        Was RED-PHASE before get_staged_yaml_files() included
        mermaid-styles.yaml in target_files: yaml_files was empty, main()
        printed the "skipping" message, and exited 0 before the --to-graph
        block ever ran -- out_path was never created. That was exactly the
        ADR-036 Phase 3 P7 stale-diagram bug: staging only
        mermaid-styles.yaml silently failed to regenerate diagrams. Now
        GREEN and retained as the regression pin.
        """
        repo = _build_scratch_repo(tmp_path)
        _stage_mermaid_styles(repo)

        out_path = repo / "out.md"
        result = _run_validate_riskmap(repo, out_path)

        assert result.returncode == 0, (
            f"Expected validate_riskmap.py to exit 0 on a clean, staged-only mermaid-styles.yaml "
            f"run.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out_path.exists(), (
            f"Expected the graph output file to be written when mermaid-styles.yaml "
            f"is the only staged file (no --force). Exit code: {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_staged_mermaid_styles_only_writes_the_companion_mermaid_format_file(self, tmp_path):
        """
        Companion false-positive guard to the file-existence assertion
        above: `-m`/`--mermaid-format` also writes a `.mermaid`-suffixed
        sibling file inside the same `--to-graph` code path
        (validate_riskmap.py main(), `if args.mermaid_format:` block, which
        only executes after `graph.to_mermaid()` has already succeeded).
        Checking for this second, independently-named artifact -- and that
        it actually contains mermaid syntax -- guards against a bug that
        satisfies the primary `out_path.exists()` assertion via some
        unrelated code path (e.g. an incidental empty-file touch) rather
        than genuine graph generation.

        `--quiet` (part of the pinned regenerate_graphs.py invocation shape)
        suppresses the "No YAML files to validate - skipping" message
        entirely, so stdout/stderr text cannot distinguish the early-exit
        path from a real run here; only the written artifacts can.

        Was RED-PHASE for the same underlying cause as the file-existence
        test above -- the entire --to-graph block (including the .mermaid
        companion write) was unreachable while mermaid-styles.yaml was
        absent from get_staged_yaml_files()'s target_files. Now GREEN.
        """
        repo = _build_scratch_repo(tmp_path)
        _stage_mermaid_styles(repo)

        out_path = repo / "out.md"
        result = _run_validate_riskmap(repo, out_path)

        mermaid_path = out_path.with_suffix(".mermaid")
        assert mermaid_path.exists(), (
            f"Expected the .mermaid companion file ({mermaid_path}) to be written "
            f"alongside {out_path} when -m/--mermaid-format is passed. "
            f"Exit code: {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        content = mermaid_path.read_text(encoding="utf-8")
        assert "graph" in content or "flowchart" in content, (
            f"Expected mermaid diagram syntax in {mermaid_path}; got:\n{content!r}"
        )

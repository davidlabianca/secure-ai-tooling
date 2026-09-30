#!/usr/bin/env python3
"""
Behavioural tests for the chained-generator input discovery regenerate-svgs
needs under ADR-005 § Addendum 2026-09-28 ("Chained generators").

regenerate-graphs (U) writes risk-map/diagrams/risk-map-graph.mermaid and
stages it via `git add`. The pre-commit framework computes each hook's argv
from the staged set once, before any hook runs, so a later hook's `files:`
match never sees U's staged output within the same run. The addendum's rule
3 (input discovery) requires regenerate-svgs (D) to discover U's staged
output from the git index at run time, in addition to its own argv -- so a
commit that only touches components.yaml or mermaid-styles.yaml (U's
trigger; D's argv, per TestChainedGeneratorTriggerCoverage in
test_precommit_hook_install.py) still regenerates the SVG in the same
commit.

These tests drive regenerate_svgs.main() directly (not through the
pre-commit framework), against a real temporary git repository, with `npx`
replaced by a fake script on PATH that writes a stub SVG file at its `-o`
path and logs each `-i` input it was called with to $FAKE_NPX_LOG. Real git
is used rather than mocked: the input-discovery behaviour under test IS a
query against the git index, so mocking that query would test the mock
rather than the discovery logic.

One case (TestRealRegenerateGraphsChain) drives the real
regenerate_graphs.main() -- a real subprocess call to validate_riskmap.py
against a full copy of the repo's own scripts/hooks/{validate_riskmap.py,
riskmap_validator/} and risk-map/{yaml,schemas}/ trees -- to prove the chain
end-to-end from an actual mermaid-styles.yaml edit through to a staged
.mermaid and then a staged .svg. The remaining cases simulate
regenerate-graphs' effect directly (write + `git add` a changed .mermaid)
rather than re-running the full graph pipeline for each one:
regenerate_graphs.py's own trigger/staging behaviour is already covered by
test_regenerate_graphs.py and test_precommit_regenerate_graphs_trigger.py, so
re-driving it in every case here would exercise the same code path
repeatedly without adding coverage of the discovery logic this file exists
to pin.
"""

import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "precommit"))

from regenerate_graphs import main as regenerate_graphs_main  # noqa: E402
from regenerate_svgs import main as regenerate_svgs_main  # noqa: E402

_FAKE_NPX_SCRIPT = """#!/usr/bin/env bash
set -e
input=""
output=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    -i) input="$2"; shift 2 ;;
    -o) output="$2"; shift 2 ;;
    *) shift ;;
  esac
done
mkdir -p "$(dirname "$output")"
printf '<svg><!-- fake mmdc output for %s --></svg>' "$input" > "$output"
if [ -n "$FAKE_NPX_LOG" ]; then
  echo "$input" >> "$FAKE_NPX_LOG"
fi
"""


@pytest.fixture
def fake_npx_on_path(tmp_path, monkeypatch):
    """
    Put a fake `npx` on PATH satisfying `npx mmdc -i <in> -o <out> ...`.

    Writes a stub SVG file at <out> and appends <in> to $FAKE_NPX_LOG on
    every call, so tests can assert both "was an SVG produced" and "how many
    times, for which inputs" without a real Mermaid CLI / Chromium toolchain.

    Returns the Path to the call log file. The fake script creates it lazily
    (via the shell `>>` redirect) -- callers must not assume it exists before
    at least one call has happened.
    """
    bin_dir = tmp_path / "_fakebin"
    bin_dir.mkdir()
    npx_path = bin_dir / "npx"
    npx_path.write_text(_FAKE_NPX_SCRIPT, encoding="utf-8")
    npx_path.chmod(npx_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    log_path = tmp_path / "_fake_npx_calls.log"
    monkeypatch.setenv("FAKE_NPX_LOG", str(log_path))
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}")
    return log_path


def _init_git_repo(repo_dir: Path) -> None:
    """Initialize a real git repo with a committer identity (no commit made)."""
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo_dir, check=True)


def _staged_paths(repo_dir: Path) -> set[str]:
    """Return the repo-relative paths currently staged (git diff --cached --name-only)."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        cwd=repo_dir,
        capture_output=True,
        text=True,
        check=True,
    )
    return {line for line in result.stdout.splitlines() if line}


def _stage_new_file(repo_dir: Path, rel_path: str, content: str = "graph TD\n  A --> B\n") -> None:
    """Write and `git add` a file, simulating a generator's own staged output."""
    full = repo_dir / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", rel_path], cwd=repo_dir, check=True)


def _commit_baseline(repo_dir: Path) -> None:
    """Commit everything currently staged as a HEAD baseline (no changes left staged)."""
    subprocess.run(["git", "commit", "-q", "-m", "baseline"], cwd=repo_dir, check=True)


def _npx_log_lines(log_path: Path) -> list[str]:
    """Return the fake npx call log's `-i` inputs, one per invocation, in call order."""
    return log_path.read_text(encoding="utf-8").splitlines() if log_path.exists() else []


class TestChainedInputDiscoveryFromStagedIndex:
    """
    regenerate_svgs.main() must discover a .mermaid file regenerate-graphs
    staged in the SAME run, even when argv carries only the YAML trigger
    (styles-only or components-only), not the diagram itself.
    """

    def test_styles_only_argv_stages_the_svg_for_a_diagram_staged_mid_run(
        self, tmp_path, monkeypatch, fake_npx_on_path
    ):
        """
        Given: a temp git repo where risk-map/yaml/mermaid-styles.yaml is
               staged (the real trigger commit) and
               risk-map/diagrams/risk-map-graph.mermaid is ALSO freshly
               staged (simulating regenerate-graphs having just run and
               git-added it earlier in the same pre-commit pass), and argv is
               ["risk-map/yaml/mermaid-styles.yaml"] -- the styles trigger
               alone, per the widened files: regex, carrying no .mermaid
               path itself
        When: regenerate_svgs.main(argv) is called
        Then: the render log is EXACTLY the staged diagram, and the staged
              set is EXACTLY the two pre-existing staged files plus the new SVG

        Exact-set assertions, not containment: an index-discovery
        implementation that reads every staged path without filtering by
        `_is_mermaid_file` would also try to render the staged trigger YAML
        itself (it is staged too, as a real trigger commit would have it) --
        a bare "the SVG exists and is staged" check cannot see that extra,
        wrong render, nor a spurious extra staged output it might produce.
        """
        _init_git_repo(tmp_path)
        _stage_new_file(tmp_path, "risk-map/yaml/mermaid-styles.yaml", "placeholder: true\n")
        _stage_new_file(tmp_path, "risk-map/diagrams/risk-map-graph.mermaid")
        monkeypatch.chdir(tmp_path)

        result = regenerate_svgs_main(["risk-map/yaml/mermaid-styles.yaml"])

        assert result == 0, f"Expected exit 0; got {result}"
        log_lines = _npx_log_lines(fake_npx_on_path)
        assert set(log_lines) == {"risk-map/diagrams/risk-map-graph.mermaid"}, (
            f"Expected exactly the staged diagram rendered, not the staged trigger YAML itself; got {log_lines!r}"
        )
        assert _staged_paths(tmp_path) == {
            "risk-map/yaml/mermaid-styles.yaml",
            "risk-map/diagrams/risk-map-graph.mermaid",
            "risk-map/svg/risk-map-graph.svg",
        }, f"Expected exactly the two pre-existing staged files plus the new SVG; got {_staged_paths(tmp_path)!r}"

    def test_components_only_argv_stages_the_svg_for_a_diagram_staged_mid_run(
        self, tmp_path, monkeypatch, fake_npx_on_path
    ):
        """
        Given: the same staged-mid-run diagram, but the staged trigger and
               argv are ["risk-map/yaml/components.yaml"] -- the components
               trigger alone
        When: regenerate_svgs.main(argv) is called
        Then: the render log is EXACTLY the staged diagram, and the staged
              set is EXACTLY the two pre-existing staged files plus the new SVG

        The components-only counterpart to the styles-only case above: both
        YAML triggers must independently reach the same discovery path, and
        neither the components.yaml trigger itself may be rendered.
        """
        _init_git_repo(tmp_path)
        _stage_new_file(tmp_path, "risk-map/yaml/components.yaml", "components: []\n")
        _stage_new_file(tmp_path, "risk-map/diagrams/risk-map-graph.mermaid")
        monkeypatch.chdir(tmp_path)

        result = regenerate_svgs_main(["risk-map/yaml/components.yaml"])

        assert result == 0, f"Expected exit 0; got {result}"
        log_lines = _npx_log_lines(fake_npx_on_path)
        assert set(log_lines) == {"risk-map/diagrams/risk-map-graph.mermaid"}, (
            f"Expected exactly the staged diagram rendered, not the staged trigger YAML itself; got {log_lines!r}"
        )
        assert _staged_paths(tmp_path) == {
            "risk-map/yaml/components.yaml",
            "risk-map/diagrams/risk-map-graph.mermaid",
            "risk-map/svg/risk-map-graph.svg",
        }, f"Expected exactly the two pre-existing staged files plus the new SVG; got {_staged_paths(tmp_path)!r}"

    def test_no_diagram_staged_writes_and_stages_no_svg(self, tmp_path, monkeypatch, fake_npx_on_path):
        """
        Given: a temp git repo with NO .mermaid file staged in the index
               (e.g. the styles edit didn't change the rendered diagram
               byte-for-byte, so regenerate-graphs staged nothing) -- and no
               HEAD commit at all (the repo has never been committed)
        When: regenerate_svgs.main(["risk-map/yaml/mermaid-styles.yaml"]) is called
        Then: no SVG is written under risk-map/svg/ and nothing is staged

        False-positive guard: without this, a discovery implementation that
        unconditionally re-renders SOME diagram regardless of index state
        would pass the two cases above for the wrong reason. Distinct from
        `TestHeadBaselineNoOp` below, which covers the case where the
        diagram already exists, committed and unchanged, at HEAD.
        """
        _init_git_repo(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = regenerate_svgs_main(["risk-map/yaml/mermaid-styles.yaml"])

        assert result == 0, f"Expected exit 0 (nothing to do); got {result}"
        svg_dir = tmp_path / "risk-map" / "svg"
        written = list(svg_dir.glob("*.svg")) if svg_dir.exists() else []
        assert written == [], f"Expected no SVG written when no diagram is staged; got {written!r}"
        assert _staged_paths(tmp_path) == set(), f"Expected nothing staged; got {_staged_paths(tmp_path)!r}"


class TestHeadBaselineNoOp:
    """
    ADR-005 Addendum 2026-09-28 rule 3: "A regeneration that is byte-identical
    to HEAD stages no change, so D does no work." A repo WITH a HEAD commit
    already containing the diagram, unchanged, must render nothing -- distinct
    from `test_no_diagram_staged_writes_and_stages_no_svg` above, which has no
    HEAD at all. A discovery mechanism that checks "does the diagram exist on
    disk / in the last committed tree" rather than "is the diagram staged in
    the index right now" would wrongly re-render here.
    """

    def test_unchanged_committed_diagram_renders_nothing(self, tmp_path, monkeypatch, fake_npx_on_path):
        """
        Given: a git repo with an initial commit containing the diagram
               already, and nothing staged this run (the graph step's render
               was byte-identical to HEAD, so it staged no change)
        When: regenerate_svgs.main(["risk-map/yaml/mermaid-styles.yaml"]) is called
        Then: no render call happens and nothing is staged
        """
        _init_git_repo(tmp_path)
        _stage_new_file(tmp_path, "risk-map/yaml/mermaid-styles.yaml", "placeholder: true\n")
        _stage_new_file(tmp_path, "risk-map/diagrams/risk-map-graph.mermaid")
        _commit_baseline(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = regenerate_svgs_main(["risk-map/yaml/mermaid-styles.yaml"])

        assert result == 0, f"Expected exit 0 (nothing to do); got {result}"
        log_lines = _npx_log_lines(fake_npx_on_path)
        assert log_lines == [], f"Expected no render call for an unchanged, committed diagram; got {log_lines!r}"
        assert _staged_paths(tmp_path) == set(), f"Expected nothing staged; got {_staged_paths(tmp_path)!r}"

    def test_working_tree_only_diagrams_are_not_discovered(self, tmp_path, monkeypatch, fake_npx_on_path):
        """
        Given: a git repo with an initial commit containing a diagram, then
               two working-tree-only changes made AFTER that commit -- an
               untracked new file (risk-map/diagrams/wip.mermaid, never
               `git add`ed) and an unstaged edit to the already-committed
               diagram (modified on disk, not staged) -- with only the
               trigger YAML staged this run (the graph step's own render was
               byte-identical to HEAD, so it staged no diagram change)
        When: regenerate_svgs.main(["risk-map/yaml/mermaid-styles.yaml"]) is called
        Then: no render call happens, and the staged set is exactly what it
              was before the call (the trigger YAML, nothing added)

        Distinct from test_unchanged_committed_diagram_renders_nothing: this
        repo's working tree DOES differ from its index (an untracked file, a
        modified-but-unstaged file). A discovery mechanism reading the
        working tree (e.g. `git status --porcelain --untracked-files=all`)
        rather than strictly the staged diff would wrongly pick these up and
        render them -- neither file is part of the commit being made.
        """
        _init_git_repo(tmp_path)
        _stage_new_file(tmp_path, "risk-map/yaml/mermaid-styles.yaml", "placeholder: true\n")
        _stage_new_file(tmp_path, "risk-map/diagrams/risk-map-graph.mermaid", "graph TD\n  A --> B\n")
        _commit_baseline(tmp_path)

        # Untracked: written to disk but never `git add`ed.
        wip_path = tmp_path / "risk-map" / "diagrams" / "wip.mermaid"
        wip_path.write_text("graph TD\n  X --> Y\n", encoding="utf-8")

        # Committed, then modified on disk without staging the edit.
        (tmp_path / "risk-map" / "diagrams" / "risk-map-graph.mermaid").write_text(
            "graph TD\n  A --> B --> C\n", encoding="utf-8"
        )

        # This run's only staged change is the trigger YAML.
        _stage_new_file(tmp_path, "risk-map/yaml/mermaid-styles.yaml", "placeholder: true\nchanged: true\n")
        staged_before = _staged_paths(tmp_path)
        monkeypatch.chdir(tmp_path)

        result = regenerate_svgs_main(["risk-map/yaml/mermaid-styles.yaml"])

        assert result == 0, f"Expected exit 0 (nothing to do); got {result}"
        log_lines = _npx_log_lines(fake_npx_on_path)
        assert log_lines == [], (
            f"Expected no render call: neither the untracked file nor the unstaged edit is "
            f"staged in the index; got {log_lines!r}"
        )
        assert _staged_paths(tmp_path) == staged_before, (
            f"Expected the staged set to stay exactly what it was before this call (the "
            f"trigger YAML only); got {_staged_paths(tmp_path)!r}"
        )


class TestAllFilesArgvDedup:
    """
    `--all-files`-shaped argv (every diagram file, whether staged or not)
    must render each diagram exactly once, including a diagram that is BOTH
    in argv and separately staged in the index.
    """

    def test_each_diagram_in_all_files_argv_renders_once_including_the_doubly_present_one(
        self, tmp_path, monkeypatch, fake_npx_on_path
    ):
        """
        Given: two diagram files on disk -- "a.mermaid" staged in the index
               AND present in argv, "b.mermaid" present in argv only
        When: regenerate_svgs.main(["risk-map/diagrams/a.mermaid",
              "risk-map/diagrams/b.mermaid"]) is called (the --all-files
              form: every matching file passed positionally)
        Then: the fake npx call log shows each of a.mermaid and b.mermaid
              exactly once -- not twice for a.mermaid despite being counted
              by both argv and the staged index

        Regression guard against a naive "union by concatenation" discovery
        implementation that renders an argv+staged file twice.
        """
        _init_git_repo(tmp_path)
        _stage_new_file(tmp_path, "risk-map/diagrams/a.mermaid", "graph TD\n  A --> A2\n")
        b_path = tmp_path / "risk-map" / "diagrams" / "b.mermaid"
        b_path.parent.mkdir(parents=True, exist_ok=True)
        b_path.write_text("graph TD\n  B --> B2\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)

        result = regenerate_svgs_main(["risk-map/diagrams/a.mermaid", "risk-map/diagrams/b.mermaid"])

        assert result == 0, f"Expected exit 0; got {result}"
        log_lines = _npx_log_lines(fake_npx_on_path)
        a_calls = [line for line in log_lines if line.endswith("a.mermaid")]
        b_calls = [line for line in log_lines if line.endswith("b.mermaid")]
        assert len(a_calls) == 1, (
            f"Expected risk-map/diagrams/a.mermaid rendered exactly once (present in both "
            f"argv and the staged index); got {len(a_calls)} calls: {log_lines!r}"
        )
        assert len(b_calls) == 1, (
            f"Expected risk-map/diagrams/b.mermaid rendered exactly once; got {len(b_calls)} calls: {log_lines!r}"
        )


def _copy_real_repo_tree_for_graph_regen(repo_root: Path, dest: Path) -> None:
    """
    Copy the subset of the real repo tree regenerate_graphs.main() needs to
    shell out to a real `python3 scripts/hooks/validate_riskmap.py`: the
    script itself, its riskmap_validator package, and risk-map/{yaml,schemas}.

    Mirrors test_validate_riskmap.py's test_ci_force_form_from_a_root_copy
    pattern (a real subprocess needs the real __file__/cwd-relative layout on
    disk, not an import-time mock).
    """
    shutil.copytree(
        repo_root / "scripts" / "hooks" / "riskmap_validator", dest / "scripts" / "hooks" / "riskmap_validator"
    )
    (dest / "scripts" / "hooks").mkdir(parents=True, exist_ok=True)
    shutil.copy(
        repo_root / "scripts" / "hooks" / "validate_riskmap.py", dest / "scripts" / "hooks" / "validate_riskmap.py"
    )
    shutil.copytree(repo_root / "risk-map" / "yaml", dest / "risk-map" / "yaml")
    shutil.copytree(repo_root / "risk-map" / "schemas", dest / "risk-map" / "schemas")
    # validate_riskmap.py's --to-graph writer opens its output path directly
    # (no mkdir), so risk-map/diagrams/ must already exist -- copy the real,
    # committed diagram outputs as the pre-edit baseline.
    shutil.copytree(repo_root / "risk-map" / "diagrams", dest / "risk-map" / "diagrams")


class TestRealRegenerateGraphsChain:
    """
    The one case in this file driving the real upstream generator (rather
    than simulating its staged output) -- see module docstring.
    """

    def test_styles_edit_through_real_regenerate_graphs_stages_the_svg(
        self, tmp_path, repo_root, monkeypatch, fake_npx_on_path
    ):
        """
        Given: a full real copy of scripts/hooks/{validate_riskmap.py,
               riskmap_validator/} and risk-map/{yaml,schemas,diagrams}/,
               committed as a HEAD baseline, then a real category-fill color
               edit made and staged to mermaid-styles.yaml (a byte-changing
               edit against that baseline -- not a no-op re-render, and not
               "no mermaid-styles.yaml existed before at all")
        When: regenerate_graphs.main(["risk-map/yaml/mermaid-styles.yaml"])
              runs for real (a real subprocess call to validate_riskmap.py,
              regenerating and git-adding the .md/.mermaid pair), followed by
              regenerate_svgs.main(["risk-map/yaml/mermaid-styles.yaml"])
        Then: after the graph step alone, the staged set is EXACTLY the
              edited YAML plus the regenerated diagram pair -- no SVG (single
              writer, ADR-005 Addendum 2026-09-28 rule 4); after the SVG
              step, the staged set additionally contains the SVG

        The HEAD baseline makes "a byte-changing edit" a real diff against a
        prior committed mermaid-styles.yaml, not merely "this file did not
        exist in the index before" -- without it, `git diff --cached`
        reports the whole file as new content, which is not the scenario
        ADR-005's rule 3 (unchanged-render no-op) is contrasted against.

        The edit targets `sharedElements.componentCategories.
        componentsInfrastructure`'s fill, not `graphTypes.component.emission.
        portStyles` (the decoupled-only port/pepport/aspect styles): the
        category style line is emitted unconditionally by BOTH the flat and
        decoupled paths in ComponentGraph (`_build_flat_graph` and
        `_emit_decoupled` both call `_get_node_style("componentCategory",
        ...)`), while portStyles is read only under `mode: 'decoupled'`. A
        needle under portStyles would make this test coupled to whichever
        mode `graphTypes.component.emission.mode` currently declares, and
        would go silently vacuous (no render change, nothing staged) under
        the `mode: 'flat'` rollback lever.
        """
        _copy_real_repo_tree_for_graph_regen(repo_root, tmp_path)
        _init_git_repo(tmp_path)
        subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
        _commit_baseline(tmp_path)

        styles_path = tmp_path / "risk-map" / "yaml" / "mermaid-styles.yaml"
        original = styles_path.read_text(encoding="utf-8")
        needle = "fill: '#e6f3e6'"
        assert needle in original, (
            "Fixture assumption: the live mermaid-styles.yaml's "
            "componentCategories.componentsInfrastructure fill color "
            f"{needle!r} must be present for this edit to change the render."
        )
        edited = original.replace(needle, "fill: '#eeeeee'", 1)
        styles_path.write_text(edited, encoding="utf-8")
        subprocess.run(["git", "add", "risk-map/yaml/mermaid-styles.yaml"], cwd=tmp_path, check=True)

        monkeypatch.chdir(tmp_path)

        graph_result = regenerate_graphs_main(["risk-map/yaml/mermaid-styles.yaml"])
        assert graph_result == 0, f"Expected the real regenerate-graphs step to succeed; got {graph_result}"
        staged_after_graph = _staged_paths(tmp_path)
        assert staged_after_graph == {
            "risk-map/yaml/mermaid-styles.yaml",
            "risk-map/diagrams/risk-map-graph.md",
            "risk-map/diagrams/risk-map-graph.mermaid",
        }, (
            f"Expected regenerate-graphs to stage exactly the edited YAML and its own "
            f"diagram pair -- no SVG (single writer, ADR-005 Addendum 2026-09-28 rule 4); "
            f"got {staged_after_graph!r}"
        )

        svg_result = regenerate_svgs_main(["risk-map/yaml/mermaid-styles.yaml"])
        assert svg_result == 0, f"Expected exit 0; got {svg_result}"
        svg_path = tmp_path / "risk-map" / "svg" / "risk-map-graph.svg"
        assert svg_path.exists(), "Expected the SVG regenerated from the real graph-regen output"
        assert _staged_paths(tmp_path) == staged_after_graph | {"risk-map/svg/risk-map-graph.svg"}, (
            f"Expected the SVG step to add exactly its own output to what the graph step "
            f"already staged; got {_staged_paths(tmp_path)!r}"
        )

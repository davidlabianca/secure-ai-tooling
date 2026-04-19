#!/usr/bin/env python3
"""
Tests for scripts/hooks/precommit/regenerate_graphs.py

This module tests the pre-commit framework hook that regenerates Mermaid
graph files whenever source YAML files change. The hook is invoked by the
pre-commit framework with staged filenames as positional argv (pass_filenames:
true) and must regenerate the appropriate graphs and git-add them so they land
in the same commit as the source change (Mode B auto-stage pattern).

The three conditional regenerations and their triggers are:

  Graph output pair                             | Trigger file(s)
  ----------------------------------------------|------------------------------
  risk-map-graph.md + .mermaid                  | components.yaml
  controls-graph.md + .mermaid                  | components.yaml OR controls.yaml
  controls-to-risk-graph.md + .mermaid          | components.yaml OR controls.yaml OR risks.yaml

Test Coverage:
==============
Total Tests: 26
- Trigger combinatorics:  7  (scenarios 1-7)
- Failure modes:          6  (scenarios 8-11, partial-failure, second-fails-third-runs)
- Exit-code verification: 3  (all-success, first-fails-rest-ok, all-fail)
- Edge cases:             5  (whitespace, absolute paths, partial staging,
                              duplicate argv, mixed relevant+unrelated files)
- Call-count guards:      5  (no double-generation, git-add alignment)

Coverage Target: 90%+ of regenerate_graphs.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Add scripts/hooks/precommit to the import path so that the module under
# test can be imported as `regenerate_graphs` regardless of working directory.
# Module is imported under the name it is shipped as (wrapper lives in
# scripts/hooks/precommit/).
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "precommit"))

from regenerate_graphs import main  # noqa: E402  (intentional late import)

# ---------------------------------------------------------------------------
# Constants mirroring what the implementation is expected to export/use.
# Tests reference these so that a single change here propagates everywhere.
# ---------------------------------------------------------------------------

VALIDATE_CMD = "python3"
VALIDATOR_SCRIPT = "scripts/hooks/validate_riskmap.py"

COMPONENTS_YAML = "risk-map/yaml/components.yaml"
CONTROLS_YAML = "risk-map/yaml/controls.yaml"
RISKS_YAML = "risk-map/yaml/risks.yaml"

RISK_MAP_MD = "risk-map/diagrams/risk-map-graph.md"
RISK_MAP_MERMAID = "risk-map/diagrams/risk-map-graph.mermaid"

CONTROLS_MD = "risk-map/diagrams/controls-graph.md"
CONTROLS_MERMAID = "risk-map/diagrams/controls-graph.mermaid"

RISK_GRAPH_MD = "risk-map/diagrams/controls-to-risk-graph.md"
RISK_GRAPH_MERMAID = "risk-map/diagrams/controls-to-risk-graph.mermaid"

# Expected subprocess commands for each generation step
CMD_RISK_MAP = [
    VALIDATE_CMD,
    VALIDATOR_SCRIPT,
    "--to-graph",
    RISK_MAP_MD,
    "-m",
    "--quiet",
]
CMD_CONTROLS = [
    VALIDATE_CMD,
    VALIDATOR_SCRIPT,
    "--to-controls-graph",
    CONTROLS_MD,
    "-m",
    "--quiet",
]
CMD_RISK_GRAPH = [
    VALIDATE_CMD,
    VALIDATOR_SCRIPT,
    "--to-risk-graph",
    RISK_GRAPH_MD,
    "-m",
    "--quiet",
]

# Expected git-add calls for each generation step
GIT_ADD_RISK_MAP = ["git", "add", RISK_MAP_MD, RISK_MAP_MERMAID]
GIT_ADD_CONTROLS = ["git", "add", CONTROLS_MD, CONTROLS_MERMAID]
GIT_ADD_RISK_GRAPH = ["git", "add", RISK_GRAPH_MD, RISK_GRAPH_MERMAID]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_subprocess_mock(returncode: int = 0) -> MagicMock:
    """Return a MagicMock for subprocess.run that reports success by default."""
    mock = MagicMock()
    mock.returncode = returncode
    return mock


# ===========================================================================
# Trigger Combinatorics — Which graphs are generated for which staged files
# ===========================================================================


class TestTriggerCombinatorics:
    """Tests verifying that each staged file triggers the correct graph(s)."""

    def test_components_change_triggers_all_three_graphs(self):
        """
        Only components.yaml staged generates all three graphs and stages 6 files.

        Given: pre-commit framework passes ["risk-map/yaml/components.yaml"]
        When: main() is called
        Then: All three validate_riskmap commands are run, all six diagram files
              are git-added, and main() returns 0
        """
        # Implementation must use `subprocess.run(...)` (not `from subprocess import run`)
        # for these patches to intercept calls. If you change patch target later, also
        # update to `patch("regenerate_graphs.subprocess.run")` for namespace specificity.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML])

        assert result == 0

        # Collect all list-style calls to subprocess.run
        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        assert CMD_RISK_MAP in subprocess_calls, "risk-map-graph generation missing"
        assert CMD_CONTROLS in subprocess_calls, "controls-graph generation missing"
        assert CMD_RISK_GRAPH in subprocess_calls, "controls-to-risk-graph generation missing"
        assert GIT_ADD_RISK_MAP in subprocess_calls, "git add for risk-map-graph missing"
        assert GIT_ADD_CONTROLS in subprocess_calls, "git add for controls-graph missing"
        assert GIT_ADD_RISK_GRAPH in subprocess_calls, "git add for controls-to-risk-graph missing"

    def test_controls_change_triggers_controls_and_risk_graphs_only(self):
        """
        Only controls.yaml staged generates controls-graph and risk-graph (NOT risk-map-graph).

        Given: pre-commit framework passes ["risk-map/yaml/controls.yaml"]
        When: main() is called
        Then: controls-graph and controls-to-risk-graph commands are run,
              risk-map-graph command is NOT run, and main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([CONTROLS_YAML])

        assert result == 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        assert CMD_CONTROLS in subprocess_calls, "controls-graph generation missing"
        assert CMD_RISK_GRAPH in subprocess_calls, "controls-to-risk-graph generation missing"
        assert CMD_RISK_MAP not in subprocess_calls, (
            "risk-map-graph should NOT be generated when only controls.yaml is staged"
        )

    def test_risks_change_triggers_only_risk_graph(self):
        """
        Only risks.yaml staged generates only the controls-to-risk graph.

        Given: pre-commit framework passes ["risk-map/yaml/risks.yaml"]
        When: main() is called
        Then: Only the controls-to-risk-graph command is run, 2 files are
              git-added, and main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([RISKS_YAML])

        assert result == 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        assert CMD_RISK_GRAPH in subprocess_calls, "controls-to-risk-graph generation missing"
        assert CMD_RISK_MAP not in subprocess_calls, (
            "risk-map-graph should NOT be generated when only risks.yaml is staged"
        )
        assert CMD_CONTROLS not in subprocess_calls, (
            "controls-graph should NOT be generated when only risks.yaml is staged"
        )

    def test_components_and_controls_staged_generates_all_three_without_duplication(self):
        """
        components.yaml + controls.yaml staged generates all three graphs, each exactly once.

        Given: pre-commit passes ["risk-map/yaml/components.yaml",
               "risk-map/yaml/controls.yaml"]
        When: main() is called
        Then: All three generation commands are run exactly once each,
              no command is duplicated, and main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML, CONTROLS_YAML])

        assert result == 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        # All three present
        assert CMD_RISK_MAP in subprocess_calls
        assert CMD_CONTROLS in subprocess_calls
        assert CMD_RISK_GRAPH in subprocess_calls

        # Each appears exactly once (no double-generation)
        assert subprocess_calls.count(CMD_RISK_MAP) == 1, "risk-map-graph generated more than once"
        assert subprocess_calls.count(CMD_CONTROLS) == 1, "controls-graph generated more than once"
        assert subprocess_calls.count(CMD_RISK_GRAPH) == 1, (
            "controls-to-risk-graph generated more than once"
        )

    def test_all_three_yaml_files_staged_generates_all_three_without_duplication(self):
        """
        All three YAML files staged still generates each graph exactly once.

        Given: pre-commit passes components.yaml, controls.yaml, and risks.yaml
        When: main() is called
        Then: Each of the three generation commands runs exactly once and
              main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML, CONTROLS_YAML, RISKS_YAML])

        assert result == 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        assert subprocess_calls.count(CMD_RISK_MAP) == 1
        assert subprocess_calls.count(CMD_CONTROLS) == 1
        assert subprocess_calls.count(CMD_RISK_GRAPH) == 1

    def test_unrelated_file_in_argv_triggers_no_generation(self):
        """
        An unrelated file passed by pre-commit triggers no generation (defensive behaviour).

        Given: pre-commit passes ["README.md"] (framework filters via `files:`
               regex, but the wrapper defends against residual non-YAML matches)
        When: main() is called
        Then: subprocess.run is never called, main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            result = main(["README.md"])

        assert result == 0
        mock_run.assert_not_called()

    def test_empty_argv_triggers_no_generation(self):
        """
        Empty argv (defensive case) triggers no generation and exits 0.

        Given: main() is called with an empty list (no filenames from framework)
        When: main([]) is called
        Then: subprocess.run is never called, main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            result = main([])

        assert result == 0
        mock_run.assert_not_called()


# ===========================================================================
# Failure Modes — Subprocess failures and exit-code propagation
# ===========================================================================


class TestFailureModes:
    """Tests verifying correct failure propagation and continue-on-error behaviour."""

    def test_first_generation_failure_continues_to_subsequent_generations(self):
        """
        If the first validate command fails, the wrapper still runs the others.

        Given: components.yaml is staged; risk-map-graph generation fails (rc=1)
               but controls-graph and risk-graph succeed
        When: main() is called
        Then: All three generation commands are attempted, main() returns non-zero
        """
        call_count = {"n": 0}

        def side_effect(cmd, **kwargs):
            call_count["n"] += 1
            mock = _make_subprocess_mock(0)
            # The first validate invocation (risk-map-graph) fails
            if cmd == CMD_RISK_MAP:
                mock.returncode = 1
            return mock

        with patch("subprocess.run", side_effect=side_effect):
            result = main([COMPONENTS_YAML])

        assert result != 0, "Should return non-zero when any generation fails"
        # All three generation commands must have been attempted
        assert call_count["n"] >= 3, (
            "Wrapper must attempt all generations even after an earlier failure"
        )

    def test_generation_succeeds_but_git_add_fails_returns_nonzero(self):
        """
        If validate_riskmap succeeds but git add fails, exit code is non-zero.

        Given: risks.yaml staged; validate command exits 0 but git add exits 1
        When: main() is called
        Then: main() returns non-zero
        """
        def side_effect(cmd, **kwargs):
            mock = _make_subprocess_mock(0)
            if cmd[0] == "git":
                mock.returncode = 1
            return mock

        with patch("subprocess.run", side_effect=side_effect):
            result = main([RISKS_YAML])

        assert result != 0

    def test_all_three_generations_succeed_returns_zero(self):
        """
        All three generations and git adds succeed → exit code 0.

        Given: components.yaml staged; all subprocess calls return 0
        When: main() is called
        Then: main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML])

        assert result == 0

    def test_all_three_generations_fail_returns_nonzero(self):
        """
        All three validate commands fail → exit code non-zero.

        Given: components.yaml staged; every subprocess call returns rc=1
        When: main() is called
        Then: main() returns non-zero
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(1)

            result = main([COMPONENTS_YAML])

        assert result != 0

    def test_all_three_generations_fail_git_add_never_called(self):
        """
        When validate commands fail, git add is NOT called for those failures.

        Given: components.yaml staged; all three validate commands return rc=1
        When: main() is called
        Then: No "git add" call is made for any failed generation
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(1)

            main([COMPONENTS_YAML])

        git_add_calls = [
            c for c in mock_run.call_args_list if c.args[0][0] == "git"
        ]
        assert len(git_add_calls) == 0, (
            "git add must not be called when the corresponding generation fails"
        )

    def test_second_generation_failure_does_not_prevent_third(self):
        """
        If the second generation fails, the third is still attempted.

        Given: controls.yaml staged; controls-graph fails (rc=1), risk-graph succeeds
        When: main() is called
        Then: Both controls-graph and risk-graph commands are attempted;
              main() returns non-zero (because one failed)
        """
        def side_effect(cmd, **kwargs):
            mock = _make_subprocess_mock(0)
            if cmd == CMD_CONTROLS:
                mock.returncode = 1
            return mock

        with patch("subprocess.run", side_effect=side_effect) as mock_run:
            result = main([CONTROLS_YAML])

        assert result != 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert CMD_CONTROLS in subprocess_calls, "controls-graph attempt missing"
        assert CMD_RISK_GRAPH in subprocess_calls, "risk-graph should still be attempted"

    def test_partial_failure_git_add_called_only_for_successes(self):
        """
        When one generation fails and others succeed, git add is called only
        for the successful ones, not the failed one.

        Given: controls.yaml staged; controls-graph validation fails (rc=1) but
               risk-graph validation succeeds (rc=0)
        When: main() is called
        Then: GIT_ADD_RISK_GRAPH is called, GIT_ADD_CONTROLS is NOT called,
              and main() returns non-zero
        """
        def side_effect(cmd, **kwargs):
            mock = _make_subprocess_mock(0)
            if cmd == CMD_CONTROLS:
                mock.returncode = 1
            return mock

        with patch("subprocess.run", side_effect=side_effect) as mock_run:
            result = main([CONTROLS_YAML])

        assert result != 0
        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert GIT_ADD_RISK_GRAPH in subprocess_calls, "git add must be called for succeeded graph"
        assert GIT_ADD_CONTROLS not in subprocess_calls, "git add must not be called for failed graph"


# ===========================================================================
# Git-Add Alignment — Each successful generation stages exactly its two files
# ===========================================================================


class TestGitAddAlignment:
    """Tests that git add is called with the correct file pairs."""

    def test_risk_map_graph_git_add_stages_correct_file_pair(self):
        """
        After risk-map-graph generation, git add is called with the .md and .mermaid pair.

        Given: components.yaml staged; all commands succeed
        When: main() is called
        Then: git add receives risk-map-graph.md and risk-map-graph.mermaid
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([COMPONENTS_YAML])

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert GIT_ADD_RISK_MAP in subprocess_calls

    def test_controls_graph_git_add_stages_correct_file_pair(self):
        """
        After controls-graph generation, git add is called with the .md and .mermaid pair.

        Given: controls.yaml staged; all commands succeed
        When: main() is called
        Then: git add receives controls-graph.md and controls-graph.mermaid
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([CONTROLS_YAML])

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert GIT_ADD_CONTROLS in subprocess_calls

    def test_risk_graph_git_add_stages_correct_file_pair(self):
        """
        After risk-graph generation, git add is called with the .md and .mermaid pair.

        Given: risks.yaml staged; all commands succeed
        When: main() is called
        Then: git add receives controls-to-risk-graph.md and controls-to-risk-graph.mermaid
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([RISKS_YAML])

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert GIT_ADD_RISK_GRAPH in subprocess_calls

    def test_git_add_not_called_for_unrelated_file(self):
        """
        No git add is called when only an unrelated file is passed.

        Given: argv contains only "README.md"
        When: main() is called
        Then: subprocess.run is never called (no generation, no staging)
        """
        with patch("subprocess.run") as mock_run:
            main(["README.md"])

        mock_run.assert_not_called()


# ===========================================================================
# Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Tests for path normalisation, duplicates, and unusual input shapes."""

    def test_components_yaml_path_with_repo_prefix_still_triggers(self):
        """
        Argv may contain paths with a leading repo-relative prefix or just the
        filename component. The wrapper must recognise components.yaml regardless.

        Given: argv contains "risk-map/yaml/components.yaml" (repo-relative)
        When: main() is called
        Then: All three graphs are generated (same as scenario 1)
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main(["risk-map/yaml/components.yaml"])

        assert result == 0
        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert CMD_RISK_MAP in subprocess_calls

    def test_absolute_path_to_components_yaml_triggers_generation(self):
        """
        pre-commit may pass absolute paths in some configurations.

        Given: argv contains "/workspace/repo/risk-map/yaml/components.yaml"
               (absolute path whose basename is components.yaml)
        When: main() is called
        Then: All three graphs are generated and main() returns 0
        """
        abs_path = "/workspace/repo/risk-map/yaml/components.yaml"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([abs_path])

        assert result == 0
        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert CMD_RISK_MAP in subprocess_calls, (
            "Absolute path to components.yaml should trigger risk-map-graph generation"
        )

    def test_duplicate_argv_entries_do_not_cause_double_generation(self):
        """
        Duplicate entries in argv (e.g., pre-commit bug or glob expansion)
        must not cause any graph to be generated more than once.

        Given: argv contains components.yaml twice
        When: main() is called
        Then: Each generation command is invoked exactly once
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML, COMPONENTS_YAML])

        assert result == 0
        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert subprocess_calls.count(CMD_RISK_MAP) == 1
        assert subprocess_calls.count(CMD_CONTROLS) == 1
        assert subprocess_calls.count(CMD_RISK_GRAPH) == 1

    def test_path_with_whitespace_in_directory_is_handled_safely(self):
        """
        File paths containing whitespace must be passed as list arguments to
        subprocess.run (never shell=True with string interpolation).

        Given: argv contains a path whose directory component has a space
               (edge case — paths in this repo never have spaces, but the
               wrapper must not break if they do)
        When: main() is called
        Then: subprocess.run is called with a list (not a string), so shell
              splitting cannot corrupt the arguments; main() returns 0 or
              non-zero without raising an exception
        """
        spaced_path = "/workspace/my repo/risk-map/yaml/components.yaml"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            # Must not raise — any exit code is acceptable here
            try:
                main([spaced_path])
            except Exception as exc:
                pytest.fail(f"main() raised an unexpected exception for path with space: {exc}")

        # If any subprocess calls were made, verify they used list form
        for c in mock_run.call_args_list:
            cmd = c.args[0]
            assert isinstance(cmd, list), (
                "subprocess.run must be called with a list argument, not a string, "
                "to avoid shell-splitting bugs with paths containing whitespace"
            )

    def test_mixed_relevant_and_unrelated_files_only_triggers_matching(self):
        """
        Mixed argv (one relevant, several unrelated) triggers only the relevant graphs.

        Given: argv contains ["README.md", "risk-map/yaml/risks.yaml",
               ".github/ISSUE_TEMPLATE/risk.yml"]
        When: main() is called
        Then: Only the risk-graph is generated; main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main(["README.md", RISKS_YAML, ".github/ISSUE_TEMPLATE/risk.yml"])

        assert result == 0
        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert CMD_RISK_GRAPH in subprocess_calls
        assert CMD_RISK_MAP not in subprocess_calls
        assert CMD_CONTROLS not in subprocess_calls


# ===========================================================================
# Subprocess Call Ordering and Shape
# ===========================================================================


class TestSubprocessCallShape:
    """Tests that subprocess calls use the correct form (list, not shell string)."""

    def test_validate_commands_are_called_as_lists_not_shell_strings(self):
        """
        Subprocess invocations must use list form so that argument splitting
        is not delegated to the shell.

        Given: components.yaml staged; all commands succeed
        When: main() is called
        Then: Every subprocess.run call receives a list as its first argument
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([COMPONENTS_YAML])

        for c in mock_run.call_args_list:
            cmd = c.args[0]
            assert isinstance(cmd, list), (
                f"subprocess.run must receive a list, got {type(cmd)}: {cmd!r}"
            )

    def test_git_add_commands_are_called_as_lists_not_shell_strings(self):
        """
        git add invocations must use list form for the same safety reasons.

        Given: risks.yaml staged; all commands succeed
        When: main() is called
        Then: The git add call receives a list as its first argument
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([RISKS_YAML])

        git_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "git"]
        assert len(git_calls) >= 1, "Expected at least one git add call"
        for c in git_calls:
            cmd = c.args[0]
            assert isinstance(cmd, list), (
                f"git add must be called with a list, got {type(cmd)}: {cmd!r}"
            )

    def test_generation_precedes_git_add_for_each_graph(self):
        """
        For each graph, the generation command must be called BEFORE its git add.

        Given: components.yaml staged; all commands succeed
        When: main() is called
        Then: In the call sequence, CMD_RISK_MAP appears before GIT_ADD_RISK_MAP,
              CMD_CONTROLS appears before GIT_ADD_CONTROLS, and CMD_RISK_GRAPH
              appears before GIT_ADD_RISK_GRAPH
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([COMPONENTS_YAML])

        calls = [c.args[0] for c in mock_run.call_args_list]

        def index_of(cmd):
            try:
                return calls.index(cmd)
            except ValueError:
                pytest.fail(f"Expected call {cmd!r} was not made")

        assert index_of(CMD_RISK_MAP) < index_of(GIT_ADD_RISK_MAP), (
            "risk-map-graph generation must happen before its git add"
        )
        assert index_of(CMD_CONTROLS) < index_of(GIT_ADD_CONTROLS), (
            "controls-graph generation must happen before its git add"
        )
        assert index_of(CMD_RISK_GRAPH) < index_of(GIT_ADD_RISK_GRAPH), (
            "controls-to-risk-graph generation must happen before its git add"
        )


# ===========================================================================
# Test Summary
# ===========================================================================
"""
Test Summary
============
Total Tests: 26
- Trigger combinatorics:          7  (TestTriggerCombinatorics)
- Failure modes / exit codes:     7  (TestFailureModes)
- Git-add alignment:              4  (TestGitAddAlignment)
- Edge cases:                     5  (TestEdgeCases)
- Subprocess call shape / order:  3  (TestSubprocessCallShape)

Coverage Areas:
- components.yaml trigger (risk-map-graph + controls-graph + risk-graph)
- controls.yaml trigger (controls-graph + risk-graph only)
- risks.yaml trigger (risk-graph only)
- No double-generation when multiple triggers present in argv
- Continue-on-error semantics (all generations attempted despite earlier failures)
- git add not called when generation fails
- Exit code 0 iff all attempted generations and git adds succeed
- Subprocess list-form safety (no shell=True string interpolation)
- Call ordering: generation precedes git add for each pair
- Defensive behaviour: empty argv, unrelated files, duplicate argv, absolute paths
"""

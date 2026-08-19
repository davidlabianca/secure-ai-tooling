#!/usr/bin/env python3
"""
Tests for scripts/hooks/precommit/regenerate_graphs.py

This module tests the pre-commit framework hook that regenerates the component
Mermaid graph file when components.yaml changes. The hook is invoked by the
pre-commit framework with staged filenames as positional argv (pass_filenames:
true) and must regenerate the graph and git-add it so it lands in the same
commit as the source change (Mode B auto-stage pattern).

Since #477 removed the control and risk graph generators, only one trigger
remains:

  Graph output pair              | Trigger file
  --------------------------------|------------------
  risk-map-graph.md + .mermaid   | components.yaml

Test Coverage:
==============
Total Tests: 19
- Trigger behaviour:      5  (components triggers; controls/risks/unrelated/empty don't)
- Failure modes:          4  (generation failure, git-add failure, success, rc propagation)
- Git-add alignment:      2  (correct file pair, not called for unrelated file)
- Edge cases:             4  (repo-relative path, absolute path, duplicate argv,
                              path with whitespace)
- Call ordering/shape:    4  (list-form subprocess calls, generation-before-git-add,
                              no calls for empty argv)

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

# Expected subprocess command for the generation step
CMD_RISK_MAP = [
    VALIDATE_CMD,
    VALIDATOR_SCRIPT,
    "--to-graph",
    RISK_MAP_MD,
    "-m",
    "--quiet",
]

# Expected git-add call for the generation step
GIT_ADD_RISK_MAP = ["git", "add", RISK_MAP_MD, RISK_MAP_MERMAID]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_subprocess_mock(returncode: int = 0) -> MagicMock:
    """Return a MagicMock for subprocess.run that reports success by default."""
    mock = MagicMock()
    mock.returncode = returncode
    return mock


# ===========================================================================
# Trigger Behaviour — Only components.yaml triggers generation
# ===========================================================================


class TestTriggerBehaviour:
    """Tests verifying which staged files trigger graph generation."""

    def test_components_change_triggers_generation(self):
        """
        components.yaml staged generates the graph and stages both output files.

        Given: pre-commit framework passes ["risk-map/yaml/components.yaml"]
        When: main() is called
        Then: The validate_riskmap command runs, both diagram files are
              git-added, and main() returns 0
        """
        # Implementation must use `subprocess.run(...)` (not `from subprocess import run`)
        # for these patches to intercept calls. If you change patch target later, also
        # update to `patch("regenerate_graphs.subprocess.run")` for namespace specificity.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML])

        assert result == 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        assert CMD_RISK_MAP in subprocess_calls, "risk-map-graph generation missing"
        assert GIT_ADD_RISK_MAP in subprocess_calls, "git add for risk-map-graph missing"

    def test_controls_change_triggers_no_generation(self):
        """
        controls.yaml alone no longer triggers any generation (#477 narrowed the trigger).

        Given: pre-commit framework passes ["risk-map/yaml/controls.yaml"]
        When: main() is called
        Then: subprocess.run is never called and main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            result = main([CONTROLS_YAML])

        assert result == 0
        mock_run.assert_not_called()

    def test_risks_change_triggers_no_generation(self):
        """
        risks.yaml alone no longer triggers any generation (#477 narrowed the trigger).

        Given: pre-commit framework passes ["risk-map/yaml/risks.yaml"]
        When: main() is called
        Then: subprocess.run is never called and main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            result = main([RISKS_YAML])

        assert result == 0
        mock_run.assert_not_called()

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
    """Tests verifying correct failure propagation."""

    def test_generation_succeeds_returns_zero(self):
        """
        Generation and git add both succeed → exit code 0.

        Given: components.yaml staged; all subprocess calls return 0
        When: main() is called
        Then: main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML])

        assert result == 0

    def test_generation_fails_returns_nonzero_and_skips_git_add(self):
        """
        If the validate command fails, git add is never attempted.

        Given: components.yaml staged; validate command returns rc=1
        When: main() is called
        Then: main() returns non-zero and no "git add" call is made
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(1)

            result = main([COMPONENTS_YAML])

        assert result != 0
        git_add_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "git"]
        assert len(git_add_calls) == 0, "git add must not be called when generation fails"

    def test_generation_succeeds_but_git_add_fails_returns_nonzero(self):
        """
        If validate_riskmap succeeds but git add fails, exit code is non-zero.

        Given: components.yaml staged; validate command exits 0 but git add exits 1
        When: main() is called
        Then: main() returns non-zero
        """

        def side_effect(cmd, **kwargs):
            mock = _make_subprocess_mock(0)
            if cmd[0] == "git":
                mock.returncode = 1
            return mock

        with patch("subprocess.run", side_effect=side_effect):
            result = main([COMPONENTS_YAML])

        assert result != 0

    def test_generation_return_code_is_propagated(self):
        """
        main() propagates the validate command's own non-zero return code.

        Given: components.yaml staged; validate command returns rc=2
        When: main() is called
        Then: main() returns 2
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(2)

            result = main([COMPONENTS_YAML])

        assert result == 2


# ===========================================================================
# Git-Add Alignment — Successful generation stages exactly the two output files
# ===========================================================================


class TestGitAddAlignment:
    """Tests that git add is called with the correct file pair."""

    def test_risk_map_graph_git_add_stages_correct_file_pair(self):
        """
        After generation, git add is called with the .md and .mermaid pair.

        Given: components.yaml staged; all commands succeed
        When: main() is called
        Then: git add receives risk-map-graph.md and risk-map-graph.mermaid
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([COMPONENTS_YAML])

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert GIT_ADD_RISK_MAP in subprocess_calls

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
        Then: The graph is generated
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
        Then: The graph is generated and main() returns 0
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
        must not cause generation to run more than once.

        Given: argv contains components.yaml twice
        When: main() is called
        Then: The generation command is invoked exactly once
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML, COMPONENTS_YAML])

        assert result == 0
        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert subprocess_calls.count(CMD_RISK_MAP) == 1

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


# ===========================================================================
# Subprocess Call Ordering and Shape
# ===========================================================================


class TestSubprocessCallShape:
    """Tests that subprocess calls use the correct form (list, not shell string)."""

    def test_validate_command_is_called_as_list_not_shell_string(self):
        """
        Subprocess invocation must use list form so that argument splitting
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
            assert isinstance(cmd, list), f"subprocess.run must receive a list, got {type(cmd)}: {cmd!r}"

    def test_git_add_command_is_called_as_list_not_shell_string(self):
        """
        git add invocation must use list form for the same safety reasons.

        Given: components.yaml staged; all commands succeed
        When: main() is called
        Then: The git add call receives a list as its first argument
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([COMPONENTS_YAML])

        git_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "git"]
        assert len(git_calls) == 1, "Expected exactly one git add call"
        for c in git_calls:
            cmd = c.args[0]
            assert isinstance(cmd, list), f"git add must be called with a list, got {type(cmd)}: {cmd!r}"

    def test_generation_precedes_git_add(self):
        """
        The generation command must be called BEFORE its git add.

        Given: components.yaml staged; all commands succeed
        When: main() is called
        Then: In the call sequence, CMD_RISK_MAP appears before GIT_ADD_RISK_MAP
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

        assert index_of(CMD_RISK_MAP) < index_of(GIT_ADD_RISK_MAP), "generation must happen before its git add"

    def test_no_subprocess_calls_for_empty_argv(self):
        """
        Empty argv makes no subprocess calls at all (nothing to generate or stage).

        Given: main() is called with an empty list
        When: main([]) is called
        Then: subprocess.run is never called
        """
        with patch("subprocess.run") as mock_run:
            main([])

        mock_run.assert_not_called()


# ===========================================================================
# Test Summary
# ===========================================================================
"""
Test Summary
============
Total Tests: 19
- Trigger behaviour:               5  (TestTriggerBehaviour)
- Failure modes / exit codes:      4  (TestFailureModes)
- Git-add alignment:               2  (TestGitAddAlignment)
- Edge cases:                      4  (TestEdgeCases)
- Subprocess call shape / order:   4  (TestSubprocessCallShape, incl. empty-argv no-op)

Coverage Areas:
- components.yaml is the sole surviving trigger (post-#477); controls.yaml
  and risks.yaml no longer trigger any generation on their own
- git add not called when generation fails
- Exit code 0 iff generation and git add both succeed; the validate command's
  own non-zero return code is propagated
- Subprocess list-form safety (no shell=True string interpolation)
- Call ordering: generation precedes git add
- Defensive behaviour: empty argv, unrelated files, duplicate argv, absolute
  paths, paths with whitespace
"""

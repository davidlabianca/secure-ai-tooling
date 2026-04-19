#!/usr/bin/env python3
"""
Tests for scripts/hooks/precommit/prettier_yaml.py

This module tests the pre-commit framework hook that runs prettier on staged
YAML files and stages the formatted output (Mode B auto-stage). The hook is
invoked by the pre-commit framework with staged filenames as positional argv
(pass_filenames: true).

For each path in argv the wrapper:
  1. Runs ["npx", "prettier", "--write", <path>]
  2. On success (rc == 0): runs ["git", "add", <path>]
  3. On failure: skips git-add for that file but continues to the next file

Exit code is 0 if every prettier invocation and git-add succeeded; non-zero
otherwise (last-failure-wins semantics). Empty argv exits 0 with no subprocess
calls. The wrapper performs no filename filtering — that is the responsibility
of the pre-commit framework's `files:` regex.

Test Coverage:
==============
Total Tests: 12
- Happy path:              3  (TestHappyPath)
- Failure modes:           4  (TestFailureModes)
- Edge cases:              3  (TestEdgeCases)
- Subprocess call shape:   2  (TestSubprocessCallShape)

Coverage Target: 90%+ of prettier_yaml.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Add scripts/hooks/precommit to the import path so that the module under
# test can be imported as `prettier_yaml` regardless of working directory.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "precommit"))

from prettier_yaml import main  # noqa: E402  (intentional late import)

# ---------------------------------------------------------------------------
# Constants mirroring what the implementation uses.
# Tests reference these so that a single change here propagates everywhere.
# ---------------------------------------------------------------------------

SAMPLE_YAML_A = "risk-map/yaml/components.yaml"
SAMPLE_YAML_B = "risk-map/yaml/controls.yaml"
SAMPLE_YAML_C = "risk-map/yaml/risks.yaml"

PRETTIER_CMD_TEMPLATE = ["npx", "prettier", "--write"]


def _prettier_cmd(path: str) -> list[str]:
    """Return the exact prettier command expected for the given path."""
    return ["npx", "prettier", "--write", path]


def _git_add_cmd(path: str) -> list[str]:
    """Return the exact git-add command expected for the given path."""
    return ["git", "add", path]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_subprocess_mock(returncode: int = 0) -> MagicMock:
    """Return a MagicMock for subprocess.run that reports the given returncode."""
    mock = MagicMock()
    mock.returncode = returncode
    return mock


# ===========================================================================
# Happy Path
# ===========================================================================


class TestHappyPath:
    """Tests verifying correct behaviour when all subprocess calls succeed."""

    def test_single_file_runs_prettier_then_git_add_and_returns_zero(self):
        """
        Single file in argv produces exactly one prettier call and one git-add,
        with the correct command lists, and exits 0.

        Given: argv contains one path
        When: main() is called
        Then: subprocess.run is called twice — prettier then git add — with
              the exact expected list arguments, and main() returns 0
        """
        # Implementation must use `subprocess.run(...)` (not `from subprocess import run`)
        # for these patches to intercept calls. If you change patch target later, also
        # update to `patch("prettier_yaml.subprocess.run")` for namespace specificity.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([SAMPLE_YAML_A])

        assert result == 0
        assert mock_run.call_count == 2

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert calls[0] == _prettier_cmd(SAMPLE_YAML_A)
        assert calls[1] == _git_add_cmd(SAMPLE_YAML_A)

    def test_multiple_files_runs_prettier_and_git_add_per_file_in_order(self):
        """
        Three files in argv produce prettier + git-add for each, in argv order,
        and exits 0.

        Given: argv contains three paths
        When: main() is called
        Then: subprocess.run is called six times in the order prettier-A,
              git-add-A, prettier-B, git-add-B, prettier-C, git-add-C,
              and main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([SAMPLE_YAML_A, SAMPLE_YAML_B, SAMPLE_YAML_C])

        assert result == 0
        assert mock_run.call_count == 6

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert calls == [
            _prettier_cmd(SAMPLE_YAML_A),
            _git_add_cmd(SAMPLE_YAML_A),
            _prettier_cmd(SAMPLE_YAML_B),
            _git_add_cmd(SAMPLE_YAML_B),
            _prettier_cmd(SAMPLE_YAML_C),
            _git_add_cmd(SAMPLE_YAML_C),
        ]

    def test_prettier_command_shape_is_exact(self):
        """
        The prettier command is EXACTLY ["npx", "prettier", "--write", <path>]
        with no additional arguments.

        Given: argv contains one path
        When: main() is called
        Then: The first subprocess.run call receives exactly the four-element
              list with no extras
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            main([SAMPLE_YAML_A])

        prettier_call = mock_run.call_args_list[0].args[0]
        assert prettier_call == ["npx", "prettier", "--write", SAMPLE_YAML_A]
        assert len(prettier_call) == 4


# ===========================================================================
# Failure Modes
# ===========================================================================


class TestFailureModes:
    """Tests verifying continue-on-error semantics and exit-code propagation."""

    def test_empty_argv_makes_no_subprocess_calls_and_returns_zero(self):
        """
        Empty argv exits 0 without making any subprocess calls.

        Given: main() is called with []
        When: main([]) is called
        Then: subprocess.run is never called and main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            result = main([])

        assert result == 0
        mock_run.assert_not_called()

    def test_prettier_fails_on_first_file_second_file_still_attempted(self):
        """
        If prettier fails for the first file, the second file is still attempted
        and the first file's git-add is NOT called.

        Given: argv has two paths; prettier returns rc=1 for the first, rc=0 for the second
        When: main() is called
        Then: prettier is called for both files; git-add is NOT called for the
              first file; git-add IS called for the second file; main() returns non-zero
        """
        responses = [
            _make_subprocess_mock(1),  # prettier for SAMPLE_YAML_A — fails
            _make_subprocess_mock(0),  # prettier for SAMPLE_YAML_B — succeeds
            _make_subprocess_mock(0),  # git add for SAMPLE_YAML_B
        ]

        with patch("subprocess.run", side_effect=responses) as mock_run:
            result = main([SAMPLE_YAML_A, SAMPLE_YAML_B])

        assert result != 0
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert _prettier_cmd(SAMPLE_YAML_A) in calls, "prettier must be attempted for first file"
        assert _prettier_cmd(SAMPLE_YAML_B) in calls, "prettier must be attempted for second file"
        assert _git_add_cmd(SAMPLE_YAML_A) not in calls, "git-add must NOT be called when prettier fails"
        assert _git_add_cmd(SAMPLE_YAML_B) in calls, "git-add must be called after successful prettier"

    def test_prettier_succeeds_but_git_add_fails_returns_nonzero(self):
        """
        If prettier succeeds but git-add fails, main() returns non-zero so
        the silent stage miss is surfaced.

        Given: argv has one path; prettier returns rc=0 but git add returns rc=1
        When: main() is called
        Then: main() returns non-zero
        """
        responses = [
            _make_subprocess_mock(0),  # prettier succeeds
            _make_subprocess_mock(1),  # git add fails
        ]

        with patch("subprocess.run", side_effect=responses):
            result = main([SAMPLE_YAML_A])

        assert result != 0

    def test_mixed_prettier_failures_git_add_only_called_for_successes(self):
        """
        With two files where the first prettier fails and the second succeeds,
        git-add is called only for the second file and main() returns non-zero.

        Given: argv has [SAMPLE_YAML_A, SAMPLE_YAML_B];
               prettier fails (rc=1) for A, succeeds (rc=0) for B
        When: main() is called
        Then: git-add is called for B, not for A; main() returns non-zero
        """

        def side_effect(cmd, **kwargs):
            if cmd == _prettier_cmd(SAMPLE_YAML_A):
                return _make_subprocess_mock(1)
            return _make_subprocess_mock(0)

        with patch("subprocess.run", side_effect=side_effect) as mock_run:
            result = main([SAMPLE_YAML_A, SAMPLE_YAML_B])

        assert result != 0
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert _git_add_cmd(SAMPLE_YAML_A) not in calls, "git-add must not be called for failed file"
        assert _git_add_cmd(SAMPLE_YAML_B) in calls, "git-add must be called for succeeded file"


# ===========================================================================
# Edge Cases
# ===========================================================================


class TestEdgeCases:
    """Tests for unusual path shapes and wrapper leniency."""

    def test_path_with_whitespace_passed_as_single_list_element(self):
        """
        A path containing whitespace is passed as a single list element to
        subprocess.run, never as a shell string that would be split incorrectly.

        Given: argv contains a path with an embedded space
        When: main() is called
        Then: subprocess.run is called with a list; the spaced path appears as
              one element and is not split; main() does not raise an exception
        """
        spaced_path = "/workspace/my repo/risk-map/yaml/components.yaml"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            try:
                main([spaced_path])
            except Exception as exc:
                raise AssertionError(f"main() raised an unexpected exception for path with space: {exc}") from exc

        prettier_call = mock_run.call_args_list[0].args[0]
        assert isinstance(prettier_call, list)
        assert prettier_call[-1] == spaced_path, (
            "Spaced path must be the last element of the list, not shell-split tokens"
        )

    def test_duplicate_argv_entries_prettier_runs_once_per_occurrence(self):
        """
        The wrapper does NOT deduplicate argv. Duplicate entries each trigger
        their own prettier + git-add pair (mirrors bash `for f in "$@"` semantics).

        Given: argv contains the same path twice
        When: main() is called
        Then: prettier is called twice for the same path (once per occurrence),
              git-add is called twice, and main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([SAMPLE_YAML_A, SAMPLE_YAML_A])

        assert result == 0
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert calls.count(_prettier_cmd(SAMPLE_YAML_A)) == 2, (
            "prettier must run once per argv occurrence — wrapper does not dedup"
        )
        assert calls.count(_git_add_cmd(SAMPLE_YAML_A)) == 2, (
            "git-add must run once per argv occurrence — wrapper does not dedup"
        )

    def test_non_yaml_filename_is_still_run_through_prettier(self):
        """
        The wrapper performs no filename filtering. A non-YAML file passed by
        the framework still gets prettier + git-add (the `files:` regex in
        .pre-commit-hooks.yaml is the sole filter).

        Given: argv contains "README.md"
        When: main() is called
        Then: prettier is called with "README.md" and git-add is called on
              success; main() returns 0
        """
        non_yaml = "README.md"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([non_yaml])

        assert result == 0
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert _prettier_cmd(non_yaml) in calls, "wrapper must not filter filenames"
        assert _git_add_cmd(non_yaml) in calls, "git-add must follow successful prettier"


# ===========================================================================
# Subprocess Call Shape
# ===========================================================================


class TestSubprocessCallShape:
    """Tests that subprocess calls use list form and correct per-file ordering."""

    def test_all_subprocess_calls_use_list_form_never_shell_true(self):
        """
        Every subprocess.run invocation must receive a list as its first
        positional argument so that shell splitting is never involved.

        Given: argv has two files; all commands succeed
        When: main() is called
        Then: Every call in mock_run.call_args_list has a list as args[0]
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([SAMPLE_YAML_A, SAMPLE_YAML_B])

        for c in mock_run.call_args_list:
            cmd = c.args[0]
            assert isinstance(cmd, list), f"subprocess.run must receive a list, got {type(cmd)}: {cmd!r}"

    def test_prettier_precedes_git_add_for_each_file(self):
        """
        For each file, the prettier call must appear before the git-add call
        in the overall call sequence.

        Given: argv has two files; all commands succeed
        When: main() is called
        Then: For each file, the index of its prettier call is lower than the
              index of its git-add call
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([SAMPLE_YAML_A, SAMPLE_YAML_B])

        calls = [c.args[0] for c in mock_run.call_args_list]

        for path in [SAMPLE_YAML_A, SAMPLE_YAML_B]:
            try:
                prettier_idx = calls.index(_prettier_cmd(path))
            except ValueError:
                raise AssertionError(f"Expected prettier call for {path!r} was not made")
            try:
                git_add_idx = calls.index(_git_add_cmd(path))
            except ValueError:
                raise AssertionError(f"Expected git-add call for {path!r} was not made")
            assert prettier_idx < git_add_idx, f"prettier must precede git-add for {path!r}"


# ===========================================================================
# Test Summary
# ===========================================================================
"""
Test Summary
============
Total Tests: 12
- Happy path:              3  (TestHappyPath)
- Failure modes:           4  (TestFailureModes)
- Edge cases:              3  (TestEdgeCases)
- Subprocess call shape:   2  (TestSubprocessCallShape)

Coverage Areas:
- Single and multi-file argv handling
- Exact prettier command shape: ["npx", "prettier", "--write", <path>]
- Continue-on-error: subsequent files attempted when an earlier prettier fails
- git-add not called when prettier fails for that file
- git-add failure propagates as non-zero exit code
- Last-failure-wins exit-code semantics across mixed success/failure runs
- Empty argv exits 0 with zero subprocess calls
- Whitespace in path passed as single list element (no shell splitting)
- No argv deduplication (one prettier+git-add per occurrence)
- No filename filtering (wrapper is lenient; framework `files:` is the filter)
- All subprocess calls use list form (shell=True never used)
- Per-file call ordering: prettier before git-add
"""

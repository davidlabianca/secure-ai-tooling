#!/usr/bin/env python3
"""
Tests for scripts/hooks/precommit/regenerate_tables.py

This module tests the pre-commit framework hook that regenerates Markdown
table files whenever source YAML files change. The hook is invoked by the
pre-commit framework with staged filenames as positional argv (pass_filenames:
true) and must regenerate the appropriate tables and git-add them so they land
in the same commit as the source change (Mode B auto-stage pattern).

The 8 generation rules across 4 triggers (yaml_to_markdown.py is the
generator; outputs go to risk-map/tables/):

  Trigger: components.yaml
    - components --all-formats --quiet  -> components-*.md
    - controls --format xref-components --quiet  -> controls-xref-components.md
  Trigger: risks.yaml
    - risks --all-formats --quiet  -> risks-*.md
    - controls --format xref-risks --quiet  -> controls-xref-risks.md
    - personas --format xref-risks --quiet  -> personas-xref-risks.md
  Trigger: controls.yaml
    - controls --all-formats --quiet  -> controls-*.md
    - personas --format xref-controls --quiet  -> personas-xref-controls.md
  Trigger: personas.yaml
    - personas --all-formats --quiet  -> personas-*.md

No dedup across triggers: if components.yaml AND controls.yaml are both staged,
both `controls --format xref-components` (components trigger) AND
`controls --all-formats` (controls trigger) are run — parity with bash hook.

Test Coverage:
==============
Total Tests: 25
- Trigger combinatorics:  9  (TestTriggerCombinatorics)
- Git-add alignment:      4  (TestGitAddAlignment)
- Failure modes:          6  (TestFailureModes)
- Edge cases:             4  (TestEdgeCases)
- Subprocess call shape:  2  (TestSubprocessCallShape)

Coverage Target: 90%+ of regenerate_tables.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Add scripts/hooks/precommit to the import path so that the module under
# test can be imported as `regenerate_tables` regardless of working directory.
# Module is imported under the name it is shipped as (wrapper lives in
# scripts/hooks/precommit/).
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "precommit"))

from regenerate_tables import main  # noqa: E402  (intentional late import)

# ---------------------------------------------------------------------------
# Constants mirroring what the implementation is expected to export/use.
# Tests reference these so that a single change here propagates everywhere.
# ---------------------------------------------------------------------------

COMPONENTS_YAML = "risk-map/yaml/components.yaml"
CONTROLS_YAML = "risk-map/yaml/controls.yaml"
RISKS_YAML = "risk-map/yaml/risks.yaml"
PERSONAS_YAML = "risk-map/yaml/personas.yaml"

YAML_TO_MD = "scripts/hooks/yaml_to_markdown.py"

# Generation commands — must match the spec table exactly
CMD_COMPONENTS_ALL_FORMATS = [
    "python3",
    YAML_TO_MD,
    "components",
    "--all-formats",
    "--quiet",
]
CMD_CONTROLS_XREF_COMPONENTS = [
    "python3",
    YAML_TO_MD,
    "controls",
    "--format",
    "xref-components",
    "--quiet",
]
CMD_RISKS_ALL_FORMATS = [
    "python3",
    YAML_TO_MD,
    "risks",
    "--all-formats",
    "--quiet",
]
CMD_CONTROLS_XREF_RISKS = [
    "python3",
    YAML_TO_MD,
    "controls",
    "--format",
    "xref-risks",
    "--quiet",
]
CMD_PERSONAS_XREF_RISKS = [
    "python3",
    YAML_TO_MD,
    "personas",
    "--format",
    "xref-risks",
    "--quiet",
]
CMD_CONTROLS_ALL_FORMATS = [
    "python3",
    YAML_TO_MD,
    "controls",
    "--all-formats",
    "--quiet",
]
CMD_PERSONAS_XREF_CONTROLS = [
    "python3",
    YAML_TO_MD,
    "personas",
    "--format",
    "xref-controls",
    "--quiet",
]
CMD_PERSONAS_ALL_FORMATS = [
    "python3",
    YAML_TO_MD,
    "personas",
    "--all-formats",
    "--quiet",
]

# git add targets — glob patterns are expanded by git itself
GIT_ADD_COMPONENTS_TABLES = ["git", "add", "risk-map/tables/components-*.md"]
GIT_ADD_CONTROLS_XREF_COMPONENTS = ["git", "add", "risk-map/tables/controls-xref-components.md"]
GIT_ADD_RISKS_TABLES = ["git", "add", "risk-map/tables/risks-*.md"]
GIT_ADD_CONTROLS_XREF_RISKS = ["git", "add", "risk-map/tables/controls-xref-risks.md"]
GIT_ADD_PERSONAS_XREF_RISKS = ["git", "add", "risk-map/tables/personas-xref-risks.md"]
GIT_ADD_CONTROLS_TABLES = ["git", "add", "risk-map/tables/controls-*.md"]
GIT_ADD_PERSONAS_XREF_CONTROLS = ["git", "add", "risk-map/tables/personas-xref-controls.md"]
GIT_ADD_PERSONAS_TABLES = ["git", "add", "risk-map/tables/personas-*.md"]

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_subprocess_mock(returncode: int = 0) -> MagicMock:
    """Return a MagicMock for subprocess.run that reports success by default."""
    mock = MagicMock()
    mock.returncode = returncode
    return mock


# ===========================================================================
# Trigger Combinatorics — Which tables are generated for which staged files
# ===========================================================================


class TestTriggerCombinatorics:
    """Tests verifying that each staged file triggers the correct generation(s)."""

    def test_only_components_yaml_staged_runs_two_generations(self):
        """
        Only components.yaml staged triggers exactly 2 generations and 2 git-adds.

        Given: pre-commit framework passes ["risk-map/yaml/components.yaml"]
        When: main() is called
        Then: CMD_COMPONENTS_ALL_FORMATS and CMD_CONTROLS_XREF_COMPONENTS are run,
              their git-adds are called, total subprocess calls == 4, returns 0
        """
        # Implementation must use `subprocess.run(...)` (not `from subprocess import run`)
        # for these patches to intercept calls. Patch target: `subprocess.run`.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML])

        assert result == 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        assert CMD_COMPONENTS_ALL_FORMATS in subprocess_calls, "components --all-formats generation missing"
        assert CMD_CONTROLS_XREF_COMPONENTS in subprocess_calls, "controls xref-components generation missing"
        assert GIT_ADD_COMPONENTS_TABLES in subprocess_calls, "git add for components-*.md missing"
        assert GIT_ADD_CONTROLS_XREF_COMPONENTS in subprocess_calls, (
            "git add for controls-xref-components.md missing"
        )
        assert len(subprocess_calls) == 4, (
            f"Expected exactly 4 subprocess calls for components.yaml, got {len(subprocess_calls)}"
        )

    def test_only_risks_yaml_staged_runs_three_generations(self):
        """
        Only risks.yaml staged triggers exactly 3 generations and 3 git-adds.

        Given: pre-commit framework passes ["risk-map/yaml/risks.yaml"]
        When: main() is called
        Then: CMD_RISKS_ALL_FORMATS, CMD_CONTROLS_XREF_RISKS, and
              CMD_PERSONAS_XREF_RISKS are run with their git-adds (6 total calls),
              returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([RISKS_YAML])

        assert result == 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        assert CMD_RISKS_ALL_FORMATS in subprocess_calls, "risks --all-formats missing"
        assert CMD_CONTROLS_XREF_RISKS in subprocess_calls, "controls xref-risks missing"
        assert CMD_PERSONAS_XREF_RISKS in subprocess_calls, "personas xref-risks missing"
        assert GIT_ADD_RISKS_TABLES in subprocess_calls
        assert GIT_ADD_CONTROLS_XREF_RISKS in subprocess_calls
        assert GIT_ADD_PERSONAS_XREF_RISKS in subprocess_calls
        assert len(subprocess_calls) == 6, (
            f"Expected exactly 6 subprocess calls for risks.yaml, got {len(subprocess_calls)}"
        )

    def test_only_controls_yaml_staged_runs_two_generations(self):
        """
        Only controls.yaml staged triggers exactly 2 generations and 2 git-adds.

        Given: pre-commit framework passes ["risk-map/yaml/controls.yaml"]
        When: main() is called
        Then: CMD_CONTROLS_ALL_FORMATS and CMD_PERSONAS_XREF_CONTROLS are run,
              total subprocess calls == 4, returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([CONTROLS_YAML])

        assert result == 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        assert CMD_CONTROLS_ALL_FORMATS in subprocess_calls, "controls --all-formats missing"
        assert CMD_PERSONAS_XREF_CONTROLS in subprocess_calls, "personas xref-controls missing"
        assert GIT_ADD_CONTROLS_TABLES in subprocess_calls
        assert GIT_ADD_PERSONAS_XREF_CONTROLS in subprocess_calls
        assert len(subprocess_calls) == 4, (
            f"Expected exactly 4 subprocess calls for controls.yaml, got {len(subprocess_calls)}"
        )

    def test_only_personas_yaml_staged_runs_one_generation(self):
        """
        Only personas.yaml staged triggers exactly 1 generation and 1 git-add.

        Given: pre-commit framework passes ["risk-map/yaml/personas.yaml"]
        When: main() is called
        Then: CMD_PERSONAS_ALL_FORMATS is run, GIT_ADD_PERSONAS_TABLES is called,
              total subprocess calls == 2, returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([PERSONAS_YAML])

        assert result == 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        assert CMD_PERSONAS_ALL_FORMATS in subprocess_calls, "personas --all-formats missing"
        assert GIT_ADD_PERSONAS_TABLES in subprocess_calls
        assert len(subprocess_calls) == 2, (
            f"Expected exactly 2 subprocess calls for personas.yaml, got {len(subprocess_calls)}"
        )

    def test_all_four_yaml_staged_runs_eight_generations_in_order(self):
        """
        All four YAML files staged triggers all 8 generations and 8 git-adds (16 total).

        Given: pre-commit passes all four YAML filenames
        When: main() is called
        Then: All 8 generation commands and their 8 git-adds are called, with
              components triggers first, then risks, then controls, then personas.
              Total subprocess calls == 16, returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML, RISKS_YAML, CONTROLS_YAML, PERSONAS_YAML])

        assert result == 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        # All 8 generation commands present
        assert CMD_COMPONENTS_ALL_FORMATS in subprocess_calls
        assert CMD_CONTROLS_XREF_COMPONENTS in subprocess_calls
        assert CMD_RISKS_ALL_FORMATS in subprocess_calls
        assert CMD_CONTROLS_XREF_RISKS in subprocess_calls
        assert CMD_PERSONAS_XREF_RISKS in subprocess_calls
        assert CMD_CONTROLS_ALL_FORMATS in subprocess_calls
        assert CMD_PERSONAS_XREF_CONTROLS in subprocess_calls
        assert CMD_PERSONAS_ALL_FORMATS in subprocess_calls

        # All 8 git-adds present
        assert GIT_ADD_COMPONENTS_TABLES in subprocess_calls
        assert GIT_ADD_CONTROLS_XREF_COMPONENTS in subprocess_calls
        assert GIT_ADD_RISKS_TABLES in subprocess_calls
        assert GIT_ADD_CONTROLS_XREF_RISKS in subprocess_calls
        assert GIT_ADD_PERSONAS_XREF_RISKS in subprocess_calls
        assert GIT_ADD_CONTROLS_TABLES in subprocess_calls
        assert GIT_ADD_PERSONAS_XREF_CONTROLS in subprocess_calls
        assert GIT_ADD_PERSONAS_TABLES in subprocess_calls

        # Verify trigger groups execute in spec order: components → risks → controls → personas
        def index_of(target):
            return next(i for i, c in enumerate(subprocess_calls) if c == target)

        assert index_of(CMD_COMPONENTS_ALL_FORMATS) < index_of(CMD_RISKS_ALL_FORMATS), (
            "Components trigger group must run before risks trigger group"
        )
        assert index_of(CMD_RISKS_ALL_FORMATS) < index_of(CMD_CONTROLS_ALL_FORMATS), (
            "Risks trigger group must run before controls trigger group"
        )
        assert index_of(CMD_CONTROLS_ALL_FORMATS) < index_of(CMD_PERSONAS_ALL_FORMATS), (
            "Controls trigger group must run before personas trigger group"
        )

        assert len(subprocess_calls) == 16, (
            f"Expected 16 subprocess calls for all 4 YAMLs, got {len(subprocess_calls)}"
        )

    def test_components_and_controls_staged_runs_both_controls_generations(self):
        """
        components.yaml + controls.yaml both staged triggers controls xref-components
        AND controls --all-formats (no dedup — parity with bash hook).

        Given: pre-commit passes components.yaml and controls.yaml
        When: main() is called
        Then: Both CMD_CONTROLS_XREF_COMPONENTS (from components trigger) AND
              CMD_CONTROLS_ALL_FORMATS (from controls trigger) are run; returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML, CONTROLS_YAML])

        assert result == 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        assert CMD_CONTROLS_XREF_COMPONENTS in subprocess_calls, (
            "controls xref-components (from components trigger) must still run"
        )
        assert CMD_CONTROLS_ALL_FORMATS in subprocess_calls, (
            "controls --all-formats (from controls trigger) must also run"
        )
        assert len(subprocess_calls) == 8, (
            f"Expected 8 subprocess calls for components+controls, got {len(subprocess_calls)}"
        )

    def test_risks_and_personas_staged_runs_three_risks_plus_one_personas_generation(self):
        """
        risks.yaml + personas.yaml staged triggers all 3 risks generations
        plus 1 personas generation.

        Given: pre-commit passes risks.yaml and personas.yaml
        When: main() is called
        Then: CMD_RISKS_ALL_FORMATS, CMD_CONTROLS_XREF_RISKS, CMD_PERSONAS_XREF_RISKS,
              and CMD_PERSONAS_ALL_FORMATS are all run; returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([RISKS_YAML, PERSONAS_YAML])

        assert result == 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]

        assert CMD_RISKS_ALL_FORMATS in subprocess_calls
        assert CMD_CONTROLS_XREF_RISKS in subprocess_calls
        assert CMD_PERSONAS_XREF_RISKS in subprocess_calls
        assert CMD_PERSONAS_ALL_FORMATS in subprocess_calls
        assert len(subprocess_calls) == 8, (
            f"Expected 8 subprocess calls for risks+personas, got {len(subprocess_calls)}"
        )

    def test_unrelated_file_in_argv_triggers_no_generation(self):
        """
        An unrelated file passed by pre-commit triggers no generation.

        Given: argv contains "README.md" (not a recognised YAML trigger)
        When: main() is called
        Then: subprocess.run is never called, main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            result = main(["README.md"])

        assert result == 0
        mock_run.assert_not_called()

    def test_empty_argv_triggers_no_generation(self):
        """
        Empty argv triggers no generation and exits 0.

        Given: main() is called with an empty list
        When: main([]) is called
        Then: subprocess.run is never called, main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            result = main([])

        assert result == 0
        mock_run.assert_not_called()


# ===========================================================================
# Git-Add Alignment — Each successful generation stages exactly its target
# ===========================================================================


class TestGitAddAlignment:
    """Tests that git add is called with the correct pathspec after each generation."""

    def test_components_generation_git_add_uses_glob_pattern(self):
        """
        After components --all-formats succeeds, git add uses the glob pattern.

        Given: components.yaml staged; all commands succeed
        When: main() is called
        Then: git add is called with "risk-map/tables/components-*.md"
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([COMPONENTS_YAML])

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert GIT_ADD_COMPONENTS_TABLES in subprocess_calls

    def test_xref_generation_git_add_uses_exact_filename_not_glob(self):
        """
        After each xref generation, git add is called with the exact filename.

        Given: risks.yaml staged; all commands succeed
        When: main() is called
        Then: git add for controls-xref-risks.md uses the exact filename (not a glob),
              and git add for personas-xref-risks.md also uses an exact filename
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([RISKS_YAML])

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert GIT_ADD_CONTROLS_XREF_RISKS in subprocess_calls
        assert GIT_ADD_PERSONAS_XREF_RISKS in subprocess_calls
        # Exact filenames — no wildcards
        assert "controls-xref-risks.md" in GIT_ADD_CONTROLS_XREF_RISKS[-1]
        assert "*" not in GIT_ADD_CONTROLS_XREF_RISKS[-1]
        assert "*" not in GIT_ADD_PERSONAS_XREF_RISKS[-1]

    def test_git_add_not_called_when_generation_fails(self):
        """
        git add is NOT called when its preceding generation fails.

        Given: personas.yaml staged; CMD_PERSONAS_ALL_FORMATS returns rc=1
        When: main() is called
        Then: GIT_ADD_PERSONAS_TABLES is never called
        """

        def side_effect(cmd, **kwargs):
            mock = _make_subprocess_mock(0)
            if cmd == CMD_PERSONAS_ALL_FORMATS:
                mock.returncode = 1
            return mock

        with patch("subprocess.run", side_effect=side_effect) as mock_run:
            main([PERSONAS_YAML])

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert GIT_ADD_PERSONAS_TABLES not in subprocess_calls, "git add must not be called when generation fails"

    def test_git_add_not_called_for_unrelated_file(self):
        """
        No git add is called when only an unrelated file is passed.

        Given: argv contains only "risk-map/yaml/something-else.yaml"
        When: main() is called
        Then: subprocess.run is never called
        """
        with patch("subprocess.run") as mock_run:
            main(["risk-map/yaml/something-else.yaml"])

        mock_run.assert_not_called()


# ===========================================================================
# Failure Modes — Subprocess failures and exit-code propagation
# ===========================================================================


class TestFailureModes:
    """Tests verifying correct failure propagation and continue-on-error behaviour."""

    def test_first_generation_failure_continues_to_subsequent_generations(self):
        """
        If the first generation fails, the wrapper still attempts the remaining ones.

        Given: components.yaml staged; CMD_COMPONENTS_ALL_FORMATS fails (rc=1),
               CMD_CONTROLS_XREF_COMPONENTS succeeds
        When: main() is called
        Then: Both generation commands are attempted, main() returns non-zero
        """

        def side_effect(cmd, **kwargs):
            mock = _make_subprocess_mock(0)
            if cmd == CMD_COMPONENTS_ALL_FORMATS:
                mock.returncode = 1
            return mock

        with patch("subprocess.run", side_effect=side_effect) as mock_run:
            result = main([COMPONENTS_YAML])

        assert result != 0, "Should return non-zero when any generation fails"

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert CMD_CONTROLS_XREF_COMPONENTS in subprocess_calls, (
            "Second generation must still be attempted after first failure"
        )

    def test_generation_succeeds_but_git_add_fails_returns_nonzero(self):
        """
        If generation succeeds but git add fails, exit code is non-zero.

        Given: personas.yaml staged; CMD_PERSONAS_ALL_FORMATS exits 0 but git add exits 1
        When: main() is called
        Then: main() returns non-zero
        """

        def side_effect(cmd, **kwargs):
            mock = _make_subprocess_mock(0)
            if cmd[0] == "git":
                mock.returncode = 1
            return mock

        with patch("subprocess.run", side_effect=side_effect):
            result = main([PERSONAS_YAML])

        assert result != 0

    def test_all_generations_succeed_returns_zero(self):
        """
        All generations and git adds succeed → exit code 0.

        Given: components.yaml staged; all subprocess calls return 0
        When: main() is called
        Then: main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML])

        assert result == 0

    def test_all_generations_fail_git_add_never_called(self):
        """
        When all generation commands fail, git add is never called.

        Given: risks.yaml staged; all three generation commands return rc=1
        When: main() is called
        Then: No git add call is made, main() returns non-zero
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(1)

            result = main([RISKS_YAML])

        assert result != 0
        git_add_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "git"]
        assert len(git_add_calls) == 0, "git add must not be called when generation fails"

    def test_failure_in_components_trigger_does_not_skip_subsequent_triggers(self):
        """
        Given: components.yaml + risks.yaml + controls.yaml + personas.yaml all staged;
               components-trigger first generation (CMD_COMPONENTS_ALL_FORMATS) fails (rc=1)
        When: main() is called
        Then: all subsequent triggers (risks, controls, personas) still execute their
              generations; final exit code is non-zero.
        """

        def side_effect(cmd, **kwargs):
            mock = _make_subprocess_mock(0)
            if cmd == CMD_COMPONENTS_ALL_FORMATS:
                mock.returncode = 1
            return mock

        with patch("subprocess.run", side_effect=side_effect) as mock_run:
            result = main([COMPONENTS_YAML, RISKS_YAML, CONTROLS_YAML, PERSONAS_YAML])

        assert result != 0
        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        # All 8 generations must still be attempted
        assert CMD_COMPONENTS_ALL_FORMATS in subprocess_calls
        assert CMD_CONTROLS_XREF_COMPONENTS in subprocess_calls
        assert CMD_RISKS_ALL_FORMATS in subprocess_calls
        assert CMD_CONTROLS_XREF_RISKS in subprocess_calls
        assert CMD_PERSONAS_XREF_RISKS in subprocess_calls
        assert CMD_CONTROLS_ALL_FORMATS in subprocess_calls
        assert CMD_PERSONAS_XREF_CONTROLS in subprocess_calls
        assert CMD_PERSONAS_ALL_FORMATS in subprocess_calls

    def test_mixed_failure_git_add_called_only_for_successes(self):
        """
        When some generations fail and others succeed, git add is called only
        for the successful ones.

        Given: risks.yaml staged; CMD_RISKS_ALL_FORMATS succeeds (rc=0),
               CMD_CONTROLS_XREF_RISKS fails (rc=1), CMD_PERSONAS_XREF_RISKS succeeds (rc=0)
        When: main() is called
        Then: git add called for risks and personas-xref-risks, NOT for controls-xref-risks;
              main() returns non-zero
        """

        def side_effect(cmd, **kwargs):
            mock = _make_subprocess_mock(0)
            if cmd == CMD_CONTROLS_XREF_RISKS:
                mock.returncode = 1
            return mock

        with patch("subprocess.run", side_effect=side_effect) as mock_run:
            result = main([RISKS_YAML])

        assert result != 0

        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert GIT_ADD_RISKS_TABLES in subprocess_calls, "git add must be called for succeeded risks generation"
        assert GIT_ADD_PERSONAS_XREF_RISKS in subprocess_calls, (
            "git add must be called for succeeded personas-xref-risks generation"
        )
        assert GIT_ADD_CONTROLS_XREF_RISKS not in subprocess_calls, (
            "git add must not be called for failed controls-xref-risks generation"
        )


# ===========================================================================
# Edge Cases — Path normalisation, duplicates, unusual input shapes
# ===========================================================================


class TestEdgeCases:
    """Tests for path normalisation, duplicates, and unusual input shapes."""

    def test_absolute_path_to_trigger_yaml_triggers_correctly(self):
        """
        pre-commit may pass absolute paths. The wrapper must use endswith() matching.

        Given: argv contains "/workspace/repo/risk-map/yaml/components.yaml"
        When: main() is called
        Then: components.yaml triggers fire correctly, returns 0
        """
        abs_path = "/workspace/repo/risk-map/yaml/components.yaml"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([abs_path])

        assert result == 0
        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert CMD_COMPONENTS_ALL_FORMATS in subprocess_calls, (
            "Absolute path to components.yaml must trigger generation"
        )

    def test_duplicate_argv_entries_do_not_cause_double_generation(self):
        """
        Duplicate entries in argv must not cause any generation to run more than once.

        Given: argv contains components.yaml twice
        When: main() is called
        Then: Each generation command is invoked exactly once, returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([COMPONENTS_YAML, COMPONENTS_YAML])

        assert result == 0
        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        # NOTE: This dedup is for duplicate argv values (same file passed twice by
        # pre-commit). It is distinct from the inter-trigger no-dedup rule: when
        # *different* trigger YAMLs both produce the same generation command (e.g.,
        # components + controls both producing controls output), those MUST both run.
        # See test_components_and_controls_staged_runs_both_controls_generations.
        assert subprocess_calls.count(CMD_COMPONENTS_ALL_FORMATS) == 1, (
            "components --all-formats must not run twice for duplicate argv"
        )
        assert subprocess_calls.count(CMD_CONTROLS_XREF_COMPONENTS) == 1, (
            "controls xref-components must not run twice for duplicate argv"
        )

    def test_path_with_prefix_triggers_correctly(self):
        """
        Paths with a leading "./" prefix must still trigger via endswith().

        Given: argv contains "./risk-map/yaml/risks.yaml"
        When: main() is called
        Then: All 3 risks.yaml generations are triggered, returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main(["./risk-map/yaml/risks.yaml"])

        assert result == 0
        subprocess_calls = [c.args[0] for c in mock_run.call_args_list]
        assert CMD_RISKS_ALL_FORMATS in subprocess_calls, "risks.yaml with ./ prefix must trigger generation"

    def test_non_trigger_yaml_in_directory_does_not_generate(self):
        """
        A YAML file in the same directory but not in the trigger set generates nothing.

        Given: argv contains "risk-map/yaml/something-else.yaml"
        When: main() is called
        Then: subprocess.run is never called, main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            result = main(["risk-map/yaml/something-else.yaml"])

        assert result == 0
        mock_run.assert_not_called()


# ===========================================================================
# Subprocess Call Shape and Ordering
# ===========================================================================


class TestSubprocessCallShape:
    """Tests that subprocess calls use the correct form and ordering."""

    def test_all_commands_use_list_form_not_shell_strings(self):
        """
        All subprocess.run calls must use list form (never shell=True with strings).

        Given: all four YAML files staged; all commands succeed
        When: main() is called
        Then: Every subprocess.run call receives a list as its first argument
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([COMPONENTS_YAML, RISKS_YAML, CONTROLS_YAML, PERSONAS_YAML])

        for c in mock_run.call_args_list:
            cmd = c.args[0]
            assert isinstance(cmd, list), f"subprocess.run must be called with a list, got {type(cmd)}: {cmd!r}"

    def test_generation_precedes_git_add_for_each_rule(self):
        """
        For each rule, the generation command must appear before its git add.

        Given: components.yaml staged; all commands succeed
        When: main() is called
        Then: CMD_COMPONENTS_ALL_FORMATS precedes GIT_ADD_COMPONENTS_TABLES,
              CMD_CONTROLS_XREF_COMPONENTS precedes GIT_ADD_CONTROLS_XREF_COMPONENTS
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

        assert index_of(CMD_COMPONENTS_ALL_FORMATS) < index_of(GIT_ADD_COMPONENTS_TABLES), (
            "components generation must happen before its git add"
        )
        assert index_of(CMD_CONTROLS_XREF_COMPONENTS) < index_of(GIT_ADD_CONTROLS_XREF_COMPONENTS), (
            "controls xref-components generation must happen before its git add"
        )


# ===========================================================================
# Test Summary
# ===========================================================================
"""
Test Summary
============
Total Tests: 25
- Trigger combinatorics:    9  (TestTriggerCombinatorics)
- Git-add alignment:        4  (TestGitAddAlignment)
- Failure modes:            6  (TestFailureModes)
- Edge cases:               4  (TestEdgeCases)
- Subprocess call shape:    2  (TestSubprocessCallShape)

Coverage Areas:
- components.yaml trigger (components --all-formats + controls xref-components)
- risks.yaml trigger (risks --all-formats + controls xref-risks + personas xref-risks)
- controls.yaml trigger (controls --all-formats + personas xref-controls)
- personas.yaml trigger (personas --all-formats)
- No dedup across triggers: components + controls both staged → both controls
  generations run (xref-components AND --all-formats)
- Continue-on-error: all generations attempted despite earlier failures
- git add not called when generation fails
- Exit code 0 iff all attempted generations and git adds succeed
- Subprocess list-form safety (no shell=True string interpolation)
- Call ordering: generation precedes git add for each rule
- Defensive behaviour: empty argv, unrelated files, duplicate argv,
  absolute paths, ./-prefixed paths
"""

#!/usr/bin/env python3
"""
Tests for scripts/hooks/precommit/regenerate_issue_templates.py

This module tests the pre-commit framework hook that regenerates GitHub Issue
Templates whenever template sources, schemas, or the frameworks YAML change.
The hook is invoked by the pre-commit framework with staged filenames as
positional argv (pass_filenames: true) and must regenerate issue templates and
git-add the output directory so the generated files land in the same commit as
the source change (Mode B auto-stage pattern).

THREE alternative trigger conditions — ANY one matched invokes the SAME single
regeneration:

  Trigger                                  | Pattern
  -----------------------------------------|-------------------------------
  Template source files                    | scripts/TEMPLATES/*.yml
  JSON schema files                        | risk-map/schemas/*.schema.json
  Frameworks YAML                          | risk-map/yaml/frameworks.yaml

Key design note: multiple triggers present in a single argv produce EXACTLY
ONE regeneration (single-dedup by design). This differs from wrappers like
regenerate_tables.py where each distinct trigger may fire its own generation.

Action when triggered:
  1. python3 scripts/generate_issue_templates.py
  2. On success: git add .github/ISSUE_TEMPLATE  (whole directory)
  3. Exit 0 if both succeed, non-zero otherwise

Test Coverage:
==============
Total Tests: 26
- Helper functions:        11  (TestHelperFunctions)
- Trigger combinatorics:    6  (TestTriggerCombinatorics)
- Subprocess command shape: 3  (TestSubprocessCommandShape)
- Failure modes:            3  (TestFailureModes)
- Edge cases:               3  (TestEdgeCases)

Coverage Target: 90%+ of regenerate_issue_templates.py
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Add scripts/hooks/precommit to the import path so that the module under
# test can be imported as `regenerate_issue_templates` regardless of working
# directory. The module does not exist yet (TDD red phase) — the import is
# expected to fail with ModuleNotFoundError until the implementation is written.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "precommit"))

from regenerate_issue_templates import (  # noqa: E402  (intentional late import)
    _has_frameworks,
    _has_schema,
    _has_template_source,
    main,
)

# ---------------------------------------------------------------------------
# Constants mirroring what the implementation is expected to export/use.
# Tests reference these so that a single change here propagates everywhere.
# ---------------------------------------------------------------------------

CMD_GENERATE = ["python3", "scripts/generate_issue_templates.py"]
GIT_ADD_TEMPLATES = ["git", "add", ".github/ISSUE_TEMPLATE"]

SAMPLE_TEMPLATE = "scripts/TEMPLATES/bug.yml"
SAMPLE_SCHEMA = "risk-map/schemas/components.schema.json"
FRAMEWORKS_YAML = "risk-map/yaml/frameworks.yaml"

SAMPLE_TEMPLATE_TXT = "scripts/TEMPLATES/foo.txt"
SAMPLE_OTHER_YAML = "risk-map/yaml/components.yaml"
SAMPLE_UNRELATED = "README.md"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_subprocess_mock(returncode: int = 0) -> MagicMock:
    """Return a MagicMock for subprocess.run that reports the given returncode."""
    mock = MagicMock()
    mock.returncode = returncode
    return mock


# ===========================================================================
# Helper Functions — _has_template_source(), _has_schema(), _has_frameworks()
# ===========================================================================


class TestHelperFunctions:
    """Tests for the three path-matching helper functions."""

    # --- _has_template_source ---

    def test_has_template_source_true_for_yml_in_templates_dir(self):
        """
        _has_template_source returns True for a .yml file under scripts/TEMPLATES/.

        Given: argv containing "scripts/TEMPLATES/foo.yml"
        When: _has_template_source() is called
        Then: returns True
        """
        assert _has_template_source(["scripts/TEMPLATES/foo.yml"]) is True

    def test_has_template_source_false_for_non_yml_in_templates_dir(self):
        """
        _has_template_source returns False for a non-.yml file under scripts/TEMPLATES/.

        Given: argv containing "scripts/TEMPLATES/foo.txt"
        When: _has_template_source() is called
        Then: returns False
        """
        assert _has_template_source(["scripts/TEMPLATES/foo.txt"]) is False

    def test_has_template_source_true_for_absolute_path_to_templates_yml(self):
        """
        _has_template_source returns True for a real absolute path ending in scripts/TEMPLATES/*.yml.

        Given: argv containing "/workspace/repo/scripts/TEMPLATES/foo.yml"
        When: _has_template_source() is called
        Then: returns True regardless of any leading path prefix
        """
        assert _has_template_source(["/workspace/repo/scripts/TEMPLATES/foo.yml"]) is True

    def test_has_template_source_true_for_nested_relative_path(self):
        """
        _has_template_source returns True for a relative path with a leading prefix segment.

        Given: argv containing "other/scripts/TEMPLATES/foo.yml"
        When: _has_template_source() is called
        Then: returns True regardless of any leading path prefix
        """
        assert _has_template_source(["other/scripts/TEMPLATES/foo.yml"]) is True

    def test_has_template_source_false_for_yml_outside_templates_dir(self):
        """
        _has_template_source returns False for a .yml file not under scripts/TEMPLATES/.

        Given: argv containing "other/dir/foo.yml"
        When: _has_template_source() is called
        Then: returns False
        """
        assert _has_template_source(["other/dir/foo.yml"]) is False

    # --- _has_schema ---

    def test_has_schema_true_for_schema_json_in_schemas_dir(self):
        """
        _has_schema returns True for a .schema.json file under risk-map/schemas/.

        Given: argv containing "risk-map/schemas/components.schema.json"
        When: _has_schema() is called
        Then: returns True
        """
        assert _has_schema(["risk-map/schemas/components.schema.json"]) is True

    def test_has_schema_true_for_any_schema_json_filename(self):
        """
        _has_schema returns True for any *.schema.json file under risk-map/schemas/.

        Given: argv containing "risk-map/schemas/anything.schema.json"
        When: _has_schema() is called
        Then: returns True
        """
        assert _has_schema(["risk-map/schemas/anything.schema.json"]) is True

    def test_has_schema_false_for_yaml_in_yaml_dir(self):
        """
        _has_schema returns False for a .yaml file, even if in risk-map.

        Given: argv containing "risk-map/yaml/components.yaml"
        When: _has_schema() is called
        Then: returns False
        """
        assert _has_schema(["risk-map/yaml/components.yaml"]) is False

    def test_has_schema_false_for_plain_json_in_schemas_dir(self):
        """
        _has_schema returns False for a plain .json file (not .schema.json).

        Given: argv containing "risk-map/schemas/config.json"
        When: _has_schema() is called
        Then: returns False
        """
        assert _has_schema(["risk-map/schemas/config.json"]) is False

    # --- _has_frameworks ---

    def test_has_frameworks_true_for_exact_frameworks_yaml(self):
        """
        _has_frameworks returns True for the exact frameworks.yaml path.

        Given: argv containing "risk-map/yaml/frameworks.yaml"
        When: _has_frameworks() is called
        Then: returns True
        """
        assert _has_frameworks(["risk-map/yaml/frameworks.yaml"]) is True

    def test_has_frameworks_false_for_other_yaml_in_same_dir(self):
        """
        _has_frameworks returns False for a different YAML file in the same directory.

        Given: argv containing "risk-map/yaml/components.yaml"
        When: _has_frameworks() is called
        Then: returns False
        """
        assert _has_frameworks(["risk-map/yaml/components.yaml"]) is False


# ===========================================================================
# Trigger Combinatorics — Which conditions fire generation
# ===========================================================================


class TestTriggerCombinatorics:
    """Tests verifying that any trigger fires exactly one generation + one git add."""

    def test_single_template_source_triggers_one_generation_and_one_git_add(self):
        """
        A single scripts/TEMPLATES/*.yml file triggers 1 generation and 1 git add.

        Given: pre-commit framework passes ["scripts/TEMPLATES/bug.yml"]
        When: main() is called
        Then: subprocess.run is called exactly twice (generate + git add), returns 0
        """
        # Implementation must use `subprocess.run(...)` (not `from subprocess import run`)
        # for these patches to intercept calls. Patch target: `subprocess.run`.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([SAMPLE_TEMPLATE])

        assert result == 0
        assert mock_run.call_count == 2, (
            f"Expected 2 subprocess calls (generate + git add), got {mock_run.call_count}"
        )

    def test_single_schema_triggers_one_generation_and_one_git_add(self):
        """
        A single risk-map/schemas/*.schema.json file triggers 1 generation and 1 git add.

        Given: pre-commit framework passes ["risk-map/schemas/components.schema.json"]
        When: main() is called
        Then: subprocess.run is called exactly twice, returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([SAMPLE_SCHEMA])

        assert result == 0
        assert mock_run.call_count == 2, (
            f"Expected 2 subprocess calls (generate + git add), got {mock_run.call_count}"
        )

    def test_frameworks_yaml_triggers_one_generation_and_one_git_add(self):
        """
        risk-map/yaml/frameworks.yaml triggers 1 generation and 1 git add.

        Given: pre-commit framework passes ["risk-map/yaml/frameworks.yaml"]
        When: main() is called
        Then: subprocess.run is called exactly twice, returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([FRAMEWORKS_YAML])

        assert result == 0
        assert mock_run.call_count == 2, (
            f"Expected 2 subprocess calls (generate + git add), got {mock_run.call_count}"
        )

    def test_all_three_triggers_in_argv_produce_exactly_one_generation(self):
        """
        All three trigger types in a single argv still produce EXACTLY one generation.

        Given: argv contains one template source, one schema, and frameworks.yaml
        When: main() is called
        Then: subprocess.run is called exactly twice (no duplication), returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([SAMPLE_TEMPLATE, SAMPLE_SCHEMA, FRAMEWORKS_YAML])

        assert result == 0
        assert mock_run.call_count == 2, (
            f"Expected exactly 2 subprocess calls despite 3 triggers (dedup), "
            f"got {mock_run.call_count}"
        )
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert calls.count(CMD_GENERATE) == 1, "Generation must run exactly once"
        assert calls.count(GIT_ADD_TEMPLATES) == 1, "git add must run exactly once"

    def test_no_triggers_in_argv_makes_no_subprocess_calls(self):
        """
        An argv with no matching trigger paths makes no subprocess calls.

        Given: argv contains only "README.md" (no recognised trigger)
        When: main() is called
        Then: subprocess.run is never called, main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            result = main([SAMPLE_UNRELATED])

        assert result == 0
        mock_run.assert_not_called()

    def test_empty_argv_makes_no_subprocess_calls(self):
        """
        Empty argv makes no subprocess calls and exits 0 (defensive case).

        Given: main() is called with an empty list
        When: main([]) is called
        Then: subprocess.run is never called, main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            result = main([])

        assert result == 0
        mock_run.assert_not_called()


# ===========================================================================
# Subprocess Command Shape — Exact commands and list-form requirement
# ===========================================================================


class TestSubprocessCommandShape:
    """Tests that subprocess calls use the correct exact commands."""

    def test_generation_command_is_exactly_cmd_generate(self):
        """
        The generation subprocess call must be exactly CMD_GENERATE.

        Given: a single template source in argv; all commands succeed
        When: main() is called
        Then: the first subprocess.run call receives CMD_GENERATE as its argument
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            main([SAMPLE_TEMPLATE])

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert CMD_GENERATE in calls, (
            f"Expected {CMD_GENERATE!r} in subprocess calls, got {calls!r}"
        )

    def test_git_add_command_is_exactly_git_add_templates_dir(self):
        """
        The git add subprocess call must be exactly GIT_ADD_TEMPLATES.

        Given: a single template source in argv; all commands succeed
        When: main() is called
        Then: the git add subprocess.run call receives GIT_ADD_TEMPLATES as its argument
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            main([SAMPLE_TEMPLATE])

        calls = [c.args[0] for c in mock_run.call_args_list]
        assert GIT_ADD_TEMPLATES in calls, (
            f"Expected {GIT_ADD_TEMPLATES!r} in subprocess calls, got {calls!r}"
        )

    def test_all_subprocess_calls_use_list_form_not_shell_strings(self):
        """
        Every subprocess.run call must use list form (never shell=True with a string).

        Given: a trigger file in argv; all commands succeed
        When: main() is called
        Then: every subprocess.run call receives a list as its first argument
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([SAMPLE_SCHEMA])

        for c in mock_run.call_args_list:
            cmd = c.args[0]
            assert isinstance(cmd, list), (
                f"subprocess.run must be called with a list, got {type(cmd)}: {cmd!r}"
            )


# ===========================================================================
# Failure Modes — Subprocess failures and exit-code propagation
# ===========================================================================


class TestFailureModes:
    """Tests verifying correct failure propagation and git-add skip-on-failure."""

    def test_generation_succeeds_but_git_add_fails_returns_nonzero(self):
        """
        If generation succeeds but git add fails, main() returns non-zero.

        Given: a trigger file in argv; generation exits 0 but git add exits 1
        When: main() is called
        Then: main() returns non-zero
        """
        def side_effect(cmd, **kwargs):
            mock = _make_subprocess_mock(0)
            if cmd[0] == "git":
                mock.returncode = 1
            return mock

        with patch("subprocess.run", side_effect=side_effect):
            result = main([SAMPLE_TEMPLATE])

        assert result != 0

    def test_generation_fails_git_add_not_called_and_returns_nonzero(self):
        """
        If generation fails, git add must NOT be called and main() returns non-zero.

        Given: a trigger file in argv; generation exits non-zero
        When: main() is called
        Then: git add is never called, main() returns non-zero
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(1)

            result = main([SAMPLE_TEMPLATE])

        assert result != 0
        git_add_calls = [
            c for c in mock_run.call_args_list if c.args[0][0] == "git"
        ]
        assert len(git_add_calls) == 0, (
            "git add must not be called when generation fails"
        )

    def test_both_commands_succeed_returns_zero(self):
        """
        Both generation and git add succeed → main() returns 0.

        Given: a trigger file in argv; all subprocess calls return 0
        When: main() is called
        Then: main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([FRAMEWORKS_YAML])

        assert result == 0


# ===========================================================================
# Edge Cases — Absolute paths, mixed argv, call ordering
# ===========================================================================


class TestEdgeCases:
    """Tests for path handling, mixed argv, and subprocess ordering."""

    def test_absolute_path_to_trigger_still_fires_generation(self):
        """
        An absolute path whose suffix matches a trigger pattern still fires.

        Given: argv contains "/workspace/repo/scripts/TEMPLATES/bug.yml"
        When: main() is called
        Then: generation is triggered, main() returns 0
        """
        abs_path = "/workspace/repo/scripts/TEMPLATES/bug.yml"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([abs_path])

        assert result == 0
        assert mock_run.call_count == 2, (
            "Absolute path matching a trigger pattern must fire generation"
        )

    def test_mixed_argv_one_trigger_plus_unrelated_fires_exactly_one_generation(self):
        """
        argv containing one trigger and several unrelated files fires exactly one generation.

        Given: argv contains a schema trigger, README.md, and another unrelated file
        When: main() is called
        Then: subprocess.run is called exactly twice (generate + git add), returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([SAMPLE_SCHEMA, "README.md", "docs/guide.md"])

        assert result == 0
        assert mock_run.call_count == 2, (
            f"Mixed argv should trigger exactly once, got {mock_run.call_count} calls"
        )

    def test_generation_precedes_git_add_in_call_order(self):
        """
        The generation command must be called BEFORE the git add command.

        Given: a trigger file in argv; all commands succeed
        When: main() is called
        Then: CMD_GENERATE appears before GIT_ADD_TEMPLATES in the call sequence
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([SAMPLE_TEMPLATE])

        calls = [c.args[0] for c in mock_run.call_args_list]

        assert CMD_GENERATE in calls, "CMD_GENERATE must be called"
        assert GIT_ADD_TEMPLATES in calls, "GIT_ADD_TEMPLATES must be called"

        generate_index = calls.index(CMD_GENERATE)
        git_add_index = calls.index(GIT_ADD_TEMPLATES)

        assert generate_index < git_add_index, (
            "Generation must precede git add in the subprocess call sequence"
        )


# ===========================================================================
# Test Summary
# ===========================================================================
"""
Test Summary
============
Total Tests: 26
- Helper functions:        11  (TestHelperFunctions)
- Trigger combinatorics:    6  (TestTriggerCombinatorics)
- Subprocess command shape: 3  (TestSubprocessCommandShape)
- Failure modes:            3  (TestFailureModes)
- Edge cases:               3  (TestEdgeCases)

Coverage Areas:
- _has_template_source: .yml in TEMPLATES dir, .txt rejected, real absolute path,
  nested relative prefix path, wrong dir
- _has_schema: *.schema.json in schemas dir, plain .json rejected, non-schema yaml rejected
- _has_frameworks: exact frameworks.yaml match, other yaml rejected
- Single template source trigger → 1 generate + 1 git add
- Single schema trigger → 1 generate + 1 git add
- Single frameworks.yaml trigger → 1 generate + 1 git add
- All three triggers in argv → EXACTLY 1 generate + 1 git add (dedup)
- No trigger in argv → 0 subprocess calls, exit 0
- Empty argv → 0 subprocess calls, exit 0
- CMD_GENERATE exact command shape
- GIT_ADD_TEMPLATES targets whole .github/ISSUE_TEMPLATE directory
- All subprocess calls use list form (no shell=True)
- Generation failure → git add skipped, exit non-zero
- git add failure → exit non-zero (continue-on-failure)
- Both succeed → exit 0
- Absolute path to trigger still fires
- Mixed argv (trigger + unrelated) fires exactly once
- Generation precedes git add in call ordering
"""

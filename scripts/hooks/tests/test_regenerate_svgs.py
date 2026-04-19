#!/usr/bin/env python3
"""
Tests for scripts/hooks/precommit/regenerate_svgs.py

This module tests the pre-commit framework hook that regenerates SVG files
whenever staged Mermaid source files change. The hook is invoked by the
pre-commit framework with staged filenames as positional argv (pass_filenames:
true) and must regenerate the appropriate SVGs and git-add them so they land
in the same commit as the source change (Mode B auto-stage pattern).

Trigger: any .mmd or .mermaid file under risk-map/diagrams/
Output: risk-map/svg/<basename>.svg

Each input file is converted independently. The puppeteer config written to a
temp file controls Chromium settings; CHROMIUM_PATH env var optionally sets
the browser executable path. The temp config file is cleaned up in a finally
block regardless of outcome.

Test Coverage:
==============
Total Tests: 42
- Helper functions:         13  (TestPuppeteerConfig, TestPathMatching)
- Happy path / main:         5  (TestMainHappyPath)
- Filtering:                 3  (TestFiltering)
- Failure modes:             4  (TestFailureModes)
- Env handling:              3  (TestEnvHandling)
- Cleanup:                   1  (TestCleanup)
- Subprocess call shape:     2  (TestSubprocessCallShape)
- Chromium discovery:       11  (TestChromiumDiscovery)

Coverage Target: 90%+ of regenerate_svgs.py
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Add scripts/hooks/precommit to the import path so that the module under
# test can be imported as `regenerate_svgs` regardless of working directory.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "precommit"))

from regenerate_svgs import (  # noqa: E402  (late import after sys.path mutation)
    _build_puppeteer_config,
    _discover_chromium,
    _is_mermaid_file,
    _output_path,
    main,
)

# ---------------------------------------------------------------------------
# Constants mirroring what the implementation is expected to export/use.
# Tests reference these so that a single change here propagates everywhere.
# ---------------------------------------------------------------------------

DIAGRAMS_DIR = "risk-map/diagrams"
SVG_DIR = "risk-map/svg"

CHROMIUM_ENV_VAR = "CHROMIUM_PATH"

PUPPETEER_ARGS = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]

SAMPLE_MMD = "risk-map/diagrams/foo.mmd"
SAMPLE_MERMAID = "risk-map/diagrams/bar.mermaid"
SAMPLE_SVG_FROM_MMD = "risk-map/svg/foo.svg"
SAMPLE_SVG_FROM_MERMAID = "risk-map/svg/bar.svg"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_subprocess_mock(returncode: int = 0) -> MagicMock:
    """Return a MagicMock for subprocess.run that reports success by default."""
    mock = MagicMock()
    mock.returncode = returncode
    return mock


def _mmdc_cmd(input_path: str, output_path: str, config_path: str) -> list:
    """Return the expected mmdc command for a given input/output/config path."""
    return [
        "npx",
        "mmdc",
        "-i",
        input_path,
        "-o",
        output_path,
        "-t",
        "neutral",
        "-b",
        "transparent",
        "-p",
        config_path,
    ]


def _git_add_cmd(output_path: str) -> list:
    """Return the expected git add command for a given SVG output path."""
    return ["git", "add", output_path]


# ===========================================================================
# Puppeteer Config — _build_puppeteer_config()
# ===========================================================================


class TestPuppeteerConfig:
    """Tests for the _build_puppeteer_config() helper function."""

    def test_none_chromium_path_returns_dict_without_executable_path_key(self):
        """
        _build_puppeteer_config(None) returns a dict without executablePath.

        Given: chromium_path is None
        When: _build_puppeteer_config(None) is called
        Then: returned dict has no 'executablePath' key
        """
        config = _build_puppeteer_config(None)

        assert "executablePath" not in config

    def test_empty_string_chromium_path_returns_dict_without_executable_path_key(self):
        """
        _build_puppeteer_config("") treats empty string same as None.

        Given: chromium_path is "" (empty string)
        When: _build_puppeteer_config("") is called
        Then: returned dict has no 'executablePath' key
        """
        config = _build_puppeteer_config("")

        assert "executablePath" not in config

    def test_set_chromium_path_returns_dict_with_executable_path_key(self):
        """
        _build_puppeteer_config("/path/to/chrome") includes executablePath.

        Given: chromium_path is "/path/to/chrome"
        When: _build_puppeteer_config("/path/to/chrome") is called
        Then: returned dict has 'executablePath' == "/path/to/chrome"
        """
        config = _build_puppeteer_config("/path/to/chrome")

        assert config["executablePath"] == "/path/to/chrome"

    def test_both_branches_include_same_args_list(self):
        """
        Both config variants (with and without executablePath) include the same args.

        Given: two calls — one with None, one with a path
        When: _build_puppeteer_config is called with each
        Then: both returned dicts have 'args' == PUPPETEER_ARGS
        """
        config_no_path = _build_puppeteer_config(None)
        config_with_path = _build_puppeteer_config("/usr/bin/chromium")

        assert config_no_path["args"] == PUPPETEER_ARGS
        assert config_with_path["args"] == PUPPETEER_ARGS

    def test_config_dict_has_no_extra_keys(self):
        """
        Given: both branches of _build_puppeteer_config
        When: called with None and with a path
        Then: the returned dict contains exactly the expected keys, no extras
        """
        assert _build_puppeteer_config(None) == {"args": PUPPETEER_ARGS}
        assert _build_puppeteer_config("/usr/bin/chromium") == {
            "args": PUPPETEER_ARGS,
            "executablePath": "/usr/bin/chromium",
        }


# ===========================================================================
# Path Matching — _output_path() and _is_mermaid_file()
# ===========================================================================


class TestPathMatching:
    """Tests for _output_path() and _is_mermaid_file() helper functions."""

    def test_output_path_for_mmd_extension(self):
        """
        _output_path converts .mmd input under risk-map/diagrams/ to .svg under risk-map/svg/.

        Given: input path "risk-map/diagrams/foo.mmd"
        When: _output_path is called
        Then: returns "risk-map/svg/foo.svg"
        """
        assert _output_path("risk-map/diagrams/foo.mmd") == "risk-map/svg/foo.svg"

    def test_output_path_for_mermaid_extension(self):
        """
        _output_path converts .mermaid extension to .svg.

        Given: input path "risk-map/diagrams/bar.mermaid"
        When: _output_path is called
        Then: returns "risk-map/svg/bar.svg"
        """
        assert _output_path("risk-map/diagrams/bar.mermaid") == "risk-map/svg/bar.svg"

    def test_output_path_only_last_extension_swapped(self):
        """
        _output_path swaps only the last extension (dot in stem is preserved).

        Given: input path "risk-map/diagrams/multi.dot.name.mmd"
        When: _output_path is called
        Then: returns "risk-map/svg/multi.dot.name.svg"
        """
        assert _output_path("risk-map/diagrams/multi.dot.name.mmd") == "risk-map/svg/multi.dot.name.svg"

    def test_is_mermaid_file_true_for_mmd_in_diagrams(self):
        """
        _is_mermaid_file returns True for a .mmd file under risk-map/diagrams/.

        Given: path "risk-map/diagrams/foo.mmd"
        When: _is_mermaid_file is called
        Then: returns True
        """
        assert _is_mermaid_file("risk-map/diagrams/foo.mmd") is True

    def test_is_mermaid_file_true_for_mermaid_extension_in_diagrams(self):
        """
        _is_mermaid_file returns True for a .mermaid file under risk-map/diagrams/.

        Given: path "risk-map/diagrams/foo.mermaid"
        When: _is_mermaid_file is called
        Then: returns True
        """
        assert _is_mermaid_file("risk-map/diagrams/foo.mermaid") is True

    def test_is_mermaid_file_false_for_non_mermaid_extension_in_diagrams(self):
        """
        _is_mermaid_file returns False for a .txt file even under risk-map/diagrams/.

        Given: path "risk-map/diagrams/foo.txt"
        When: _is_mermaid_file is called
        Then: returns False
        """
        assert _is_mermaid_file("risk-map/diagrams/foo.txt") is False

    def test_is_mermaid_file_false_for_mmd_outside_diagrams_dir(self):
        """
        _is_mermaid_file returns False for a .mmd file not under risk-map/diagrams/.

        Given: path "other-dir/foo.mmd"
        When: _is_mermaid_file is called
        Then: returns False (directory requirement not met)
        """
        assert _is_mermaid_file("other-dir/foo.mmd") is False

    def test_is_mermaid_file_false_for_readme(self):
        """
        _is_mermaid_file returns False for a completely unrelated file.

        Given: path "README.md"
        When: _is_mermaid_file is called
        Then: returns False
        """
        assert _is_mermaid_file("README.md") is False


# ===========================================================================
# Happy Path — main() with valid mermaid files
# ===========================================================================


class TestMainHappyPath:
    """Tests verifying the happy path through main() for single and multiple files."""

    def test_single_mmd_file_makes_one_mmdc_call_and_one_git_add(self):
        """
        A single .mmd file in argv triggers exactly 1 mmdc call and 1 git add.

        Given: pre-commit framework passes ["risk-map/diagrams/foo.mmd"]
        When: main() is called
        Then: subprocess.run is called twice (mmdc + git add), main() returns 0
        """
        # Implementation must use `subprocess.run(...)` (not `from subprocess import run`)
        # for these patches to intercept calls. Patch target: `subprocess.run`.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([SAMPLE_MMD])

        assert result == 0
        assert mock_run.call_count == 2, f"Expected 2 subprocess calls (mmdc + git add), got {mock_run.call_count}"

    def test_mmdc_command_includes_required_flags(self):
        """
        The mmdc command includes -t neutral, -b transparent, and -p <config_path>.

        Given: "risk-map/diagrams/foo.mmd" in argv; all commands succeed
        When: main() is called
        Then: the mmdc subprocess call includes -t, neutral, -b, transparent, and -p
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            main([SAMPLE_MMD])

        calls = [c.args[0] for c in mock_run.call_args_list]
        mmdc_calls = [c for c in calls if c[0] == "npx"]
        assert len(mmdc_calls) == 1, "Expected exactly one npx mmdc call"

        mmdc_cmd = mmdc_calls[0]
        assert mmdc_cmd[0:6] == [
            "npx",
            "mmdc",
            "-i",
            SAMPLE_MMD,
            "-o",
            SAMPLE_SVG_FROM_MMD,
        ]
        assert mmdc_cmd[6:10] == ["-t", "neutral", "-b", "transparent"]
        assert mmdc_cmd[10] == "-p"
        assert len(mmdc_cmd) == 12

    def test_git_add_invoked_with_svg_output_path(self):
        """
        After successful mmdc, git add is called with the SVG output path.

        Given: "risk-map/diagrams/foo.mmd" in argv; mmdc succeeds
        When: main() is called
        Then: git add is called with "risk-map/svg/foo.svg"
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            main([SAMPLE_MMD])

        calls = [c.args[0] for c in mock_run.call_args_list]
        git_calls = [c for c in calls if c[0] == "git"]
        assert len(git_calls) == 1, "Expected exactly one git add call"
        assert git_calls[0] == _git_add_cmd(SAMPLE_SVG_FROM_MMD), f"git add called with wrong path: {git_calls[0]}"

    def test_two_mmd_files_make_two_mmdc_calls_and_two_git_adds(self):
        """
        Two .mmd files in argv trigger 2 mmdc calls and 2 git adds.

        Given: pre-commit passes two .mmd files
        When: main() is called
        Then: 4 total subprocess calls (2 mmdc + 2 git add), returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main(["risk-map/diagrams/foo.mmd", "risk-map/diagrams/baz.mmd"])

        assert result == 0
        assert mock_run.call_count == 4, (
            f"Expected 4 subprocess calls (2x mmdc + 2x git add), got {mock_run.call_count}"
        )

    def test_mmd_and_mermaid_and_txt_only_two_conversions(self):
        """
        Mixed argv (.mmd + .mermaid + .txt) triggers 2 conversions; .txt is ignored.

        Given: argv contains one .mmd, one .mermaid, one .txt (all in risk-map/diagrams/)
        When: main() is called
        Then: 4 total subprocess calls (2 mmdc + 2 git add), .txt ignored, returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main(
                [
                    "risk-map/diagrams/foo.mmd",
                    "risk-map/diagrams/bar.mermaid",
                    "risk-map/diagrams/ignored.txt",
                ]
            )

        assert result == 0
        assert mock_run.call_count == 4, f"Expected 4 subprocess calls (2 valid files), got {mock_run.call_count}"


# ===========================================================================
# Filtering — Non-mermaid and out-of-scope files silently ignored
# ===========================================================================


class TestFiltering:
    """Tests that non-matching argv entries are silently ignored."""

    def test_only_non_mermaid_files_in_argv_makes_no_subprocess_calls(self):
        """
        argv containing only non-mermaid files → 0 subprocess calls, exit 0.

        Given: argv contains "README.md" and "setup.py" (no mermaid files)
        When: main() is called
        Then: subprocess.run is never called, main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            result = main(["README.md", "setup.py"])

        assert result == 0
        mock_run.assert_not_called()

    def test_mmd_outside_diagrams_dir_is_ignored(self):
        """
        A .mmd file outside risk-map/diagrams/ is silently ignored.

        Given: argv contains "other-dir/foo.mmd" (not in risk-map/diagrams/)
        When: main() is called
        Then: subprocess.run is never called, main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            result = main(["other-dir/foo.mmd"])

        assert result == 0
        mock_run.assert_not_called()

    def test_empty_argv_exits_zero_with_no_subprocess_calls(self):
        """
        Empty argv → exit 0, no subprocess calls (defensive case).

        Given: main() is called with an empty list
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

    def test_mmdc_failure_for_first_file_still_attempts_second_file(self):
        """
        If mmdc fails for the first file, the second file is still attempted.

        Given: two .mmd files staged; first mmdc call fails (rc=1), second succeeds
        When: main() is called
        Then: both mmdc calls are attempted, main() returns non-zero
        """

        def side_effect(cmd, **kwargs):
            if cmd[0] == "npx" and cmd[cmd.index("-i") + 1] == "risk-map/diagrams/first.mmd":
                return _make_subprocess_mock(1)
            return _make_subprocess_mock(0)

        with patch("subprocess.run", side_effect=side_effect) as mock_run:
            result = main(
                [
                    "risk-map/diagrams/first.mmd",
                    "risk-map/diagrams/second.mmd",
                ]
            )

        assert result != 0, "Should return non-zero when any mmdc call fails"
        npx_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "npx"]
        assert len(npx_calls) == 2, "Both mmdc calls must be attempted even after the first failure"

    def test_mmdc_succeeds_but_git_add_fails_returns_nonzero(self):
        """
        If mmdc succeeds but git add fails, main() returns non-zero.

        Given: single .mmd file; mmdc exits 0 but git add exits 1
        When: main() is called
        Then: main() returns non-zero
        """

        def side_effect(cmd, **kwargs):
            mock = _make_subprocess_mock(0)
            if cmd[0] == "git":
                mock.returncode = 1
            return mock

        with patch("subprocess.run", side_effect=side_effect):
            result = main([SAMPLE_MMD])

        assert result != 0

    def test_all_files_succeed_returns_zero(self):
        """
        All mmdc conversions and git adds succeed → exit code 0.

        Given: two .mmd files staged; all subprocess calls return 0
        When: main() is called
        Then: main() returns 0
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)

            result = main([SAMPLE_MMD, SAMPLE_MERMAID])

        assert result == 0

    def test_all_files_fail_mmdc_no_git_adds_made(self):
        """
        When all mmdc calls fail, git add is never called and main() returns non-zero.

        Given: two .mmd files staged; every subprocess call returns rc=1
        When: main() is called
        Then: No git add calls are made, main() returns non-zero
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(1)

            result = main([SAMPLE_MMD, SAMPLE_MERMAID])

        assert result != 0
        git_add_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "git"]
        assert len(git_add_calls) == 0, "git add must not be called when mmdc fails"


# ===========================================================================
# Env Handling — CHROMIUM_PATH environment variable
# ===========================================================================


class TestEnvHandling:
    """Tests for CHROMIUM_PATH environment variable influence on puppeteer config."""

    def test_chromium_path_unset_produces_config_without_executable_path(self, monkeypatch, tmp_path):
        """
        When CHROMIUM_PATH is unset and ARM64 discovery finds nothing, config has no executablePath.

        Given: CHROMIUM_PATH not in env; platform forced to non-ARM64-Linux so discovery returns None
        When: main() is called with a .mmd file
        Then: the JSON config passed to mmdc via -p has no 'executablePath' key
        """
        monkeypatch.delenv(CHROMIUM_ENV_VAR, raising=False)

        captured_configs = []

        def side_effect(cmd, **kwargs):
            if cmd[0] == "npx":
                p_index = cmd.index("-p")
                config_file = cmd[p_index + 1]
                try:
                    with open(config_file) as f:
                        captured_configs.append(json.load(f))
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
            return _make_subprocess_mock(0)

        # Force discovery to skip the Playwright-cache branch so this test is
        # deterministic regardless of the host's actual installed browsers.
        with (
            patch("regenerate_svgs.platform.system", return_value="Darwin"),
            patch("regenerate_svgs.platform.machine", return_value="x86_64"),
            patch("subprocess.run", side_effect=side_effect),
        ):
            main([SAMPLE_MMD])

        assert len(captured_configs) == 1, "Expected one config to be captured"
        assert "executablePath" not in captured_configs[0], (
            "Config must not contain executablePath when CHROMIUM_PATH is unset and discovery finds nothing"
        )

    def test_chromium_path_empty_string_produces_config_without_executable_path(self, monkeypatch):
        """
        When CHROMIUM_PATH is "" (empty) and discovery finds nothing, config has no executablePath.

        Given: CHROMIUM_PATH="" in env; platform forced to non-ARM64-Linux so discovery returns None
        When: main() is called with a .mmd file
        Then: the written puppeteer config has no 'executablePath' key
        """
        monkeypatch.setenv(CHROMIUM_ENV_VAR, "")

        captured_configs = []

        def side_effect(cmd, **kwargs):
            if cmd[0] == "npx":
                p_index = cmd.index("-p")
                config_file = cmd[p_index + 1]
                try:
                    with open(config_file) as f:
                        captured_configs.append(json.load(f))
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
            return _make_subprocess_mock(0)

        with (
            patch("regenerate_svgs.platform.system", return_value="Darwin"),
            patch("regenerate_svgs.platform.machine", return_value="x86_64"),
            patch("subprocess.run", side_effect=side_effect),
        ):
            main([SAMPLE_MMD])

        assert len(captured_configs) == 1
        assert "executablePath" not in captured_configs[0], "Empty CHROMIUM_PATH must be treated the same as unset"

    def test_chromium_path_set_produces_config_with_executable_path(self, monkeypatch):
        """
        When CHROMIUM_PATH=/usr/bin/chromium, config includes executablePath.

        Given: CHROMIUM_PATH="/usr/bin/chromium" in the environment
        When: main() is called with a .mmd file
        Then: the written puppeteer config has executablePath == "/usr/bin/chromium"
        """
        monkeypatch.setenv(CHROMIUM_ENV_VAR, "/usr/bin/chromium")

        captured_configs = []

        def side_effect(cmd, **kwargs):
            if cmd[0] == "npx":
                p_index = cmd.index("-p")
                config_file = cmd[p_index + 1]
                try:
                    with open(config_file) as f:
                        captured_configs.append(json.load(f))
                except (FileNotFoundError, json.JSONDecodeError):
                    pass
            return _make_subprocess_mock(0)

        with patch("subprocess.run", side_effect=side_effect):
            main([SAMPLE_MMD])

        assert len(captured_configs) == 1
        assert captured_configs[0].get("executablePath") == "/usr/bin/chromium", (
            "Config must include executablePath when CHROMIUM_PATH is set"
        )


# ===========================================================================
# Cleanup — Temp puppeteer config file deleted in finally block
# ===========================================================================


class TestCleanup:
    """Tests that the temp puppeteer config file is cleaned up even on failure."""

    def test_temp_config_deleted_even_when_subprocess_raises(self, monkeypatch):
        """
        The temp puppeteer config file is deleted in a finally block.

        Given: subprocess.run raises RuntimeError on the mmdc call
        When: main() is called with a .mmd file
        Then: the temp config file created for the puppeteer config no longer
              exists after main() returns (cleaned up despite the exception)
        """
        monkeypatch.delenv(CHROMIUM_ENV_VAR, raising=False)

        written_temp_paths = []
        original_named_temporary_file = tempfile.NamedTemporaryFile

        def capturing_ntf(**kwargs):
            f = original_named_temporary_file(**kwargs)
            written_temp_paths.append(f.name)
            return f

        def raising_run(cmd, **kwargs):
            if cmd[0] == "npx":
                raise RuntimeError("simulated mmdc crash")
            return _make_subprocess_mock(0)

        # Patch target: regenerate_svgs.tempfile.NamedTemporaryFile
        # (Implementation must use `import tempfile`, not `from tempfile import NamedTemporaryFile`,
        # for this patch to intercept the call.)
        with patch("regenerate_svgs.tempfile.NamedTemporaryFile", side_effect=capturing_ntf) as mock_ntf:
            with patch("subprocess.run", side_effect=raising_run):
                try:
                    main([SAMPLE_MMD])
                except Exception:
                    pass  # main() may re-raise or swallow — either is acceptable

        assert len(written_temp_paths) >= 1, "Expected at least one temp file to have been created"
        for call_args in mock_ntf.call_args_list:
            assert call_args.kwargs.get("delete") is False, (
                "NamedTemporaryFile must use delete=False so finally block owns cleanup"
            )
        for temp_path in written_temp_paths:
            assert not Path(temp_path).exists(), f"Temp config file {temp_path!r} was not deleted in finally block"


# ===========================================================================
# Subprocess Call Shape and Ordering
# ===========================================================================


class TestSubprocessCallShape:
    """Tests that subprocess calls use list form and correct per-file ordering."""

    def test_all_commands_use_list_form_not_shell_strings(self):
        """
        Every subprocess.run call must use list form (never shell=True with a string).

        Given: two .mmd files staged; all commands succeed
        When: main() is called
        Then: every subprocess.run call receives a list as its first argument
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([SAMPLE_MMD, SAMPLE_MERMAID])

        for c in mock_run.call_args_list:
            cmd = c.args[0]
            assert isinstance(cmd, list), f"subprocess.run must be called with a list, got {type(cmd)}: {cmd!r}"

    def test_mmdc_precedes_git_add_for_each_file(self):
        """
        For each file, the mmdc conversion must be called before the git add.

        Given: two .mmd files staged; all commands succeed
        When: main() is called
        Then: the mmdc call for each file appears before its corresponding git add
              in the subprocess.run call sequence
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main(
                [
                    "risk-map/diagrams/alpha.mmd",
                    "risk-map/diagrams/beta.mmd",
                ]
            )

        calls = [c.args[0] for c in mock_run.call_args_list]

        npx_indices = [i for i, c in enumerate(calls) if c[0] == "npx"]
        git_indices = [i for i, c in enumerate(calls) if c[0] == "git"]

        assert len(npx_indices) == 2, "Expected 2 mmdc calls"
        assert len(git_indices) == 2, "Expected 2 git add calls"

        # First mmdc must precede first git add; second mmdc must precede second git add
        assert npx_indices[0] < git_indices[0], "First mmdc call must precede first git add"
        assert npx_indices[1] < git_indices[1], "Second mmdc call must precede second git add"


# ===========================================================================
# Chromium Discovery — _discover_chromium()
# ===========================================================================


class TestChromiumDiscovery:
    """Tests for the _discover_chromium() helper function.

    This class covers the priority-ordered Chromium discovery logic:
      1. CHROMIUM_PATH env var (explicit override)
      2. On Linux ARM64: search Playwright cache for headless_shell then chrome
      3. None — fall back to mmdc auto-detection
    """

    def test_chromium_path_env_set_returns_env_value_verbatim(self, monkeypatch, tmp_path):
        """
        When CHROMIUM_PATH is set to a non-empty value, return it verbatim.

        Given: CHROMIUM_PATH="/usr/bin/chromium" in the environment; Linux ARM64;
               Playwright cache also contains a headless_shell binary
        When: _discover_chromium() is called
        Then: returns "/usr/bin/chromium" — env var wins at priority 1 regardless
              of platform (adversarial: even on the ARM64 path that would otherwise
              consult the cache)
        """
        monkeypatch.setenv("CHROMIUM_PATH", "/usr/bin/chromium")

        # Populate a fake Playwright cache to confirm it is NOT consulted
        fake_binary = tmp_path / "chromium-1234" / "chrome-linux" / "headless_shell"
        fake_binary.parent.mkdir(parents=True)
        fake_binary.write_text("")
        fake_binary.chmod(0o755)
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

        # Patch target: regenerate_svgs.platform.<func> requires the implementation
        # to use `import platform` (not `from platform import system, machine`).
        with (
            patch("regenerate_svgs.platform.system", return_value="Linux"),
            patch("regenerate_svgs.platform.machine", return_value="aarch64"),
        ):
            result = _discover_chromium()

        assert result == "/usr/bin/chromium"

    def test_chromium_path_env_empty_string_falls_through(self, monkeypatch, tmp_path):
        """
        When CHROMIUM_PATH is "" (empty), it is treated the same as unset.

        Given: CHROMIUM_PATH="" in the environment; Darwin with ARM machine —
               the Linux gate excludes Darwin entirely, so returns None regardless
               of machine arch
        When: _discover_chromium() is called
        Then: returns None (empty env var is not used as a path; Darwin excluded)
        """
        monkeypatch.setenv("CHROMIUM_PATH", "")
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

        with (
            patch("regenerate_svgs.platform.system", return_value="Darwin"),
            patch("regenerate_svgs.platform.machine", return_value="arm64"),
        ):
            result = _discover_chromium()

        assert result is None

    def test_chromium_path_unset_darwin_returns_none(self, monkeypatch, tmp_path):
        """
        On macOS (darwin), no Playwright auto-discovery is performed.

        Given: CHROMIUM_PATH is unset; platform.system() == "Darwin"
        When: _discover_chromium() is called
        Then: returns None
        """
        monkeypatch.delenv("CHROMIUM_PATH", raising=False)
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

        with (
            patch("regenerate_svgs.platform.system", return_value="Darwin"),
            patch("regenerate_svgs.platform.machine", return_value="arm64"),
        ):
            result = _discover_chromium()

        assert result is None

    def test_chromium_path_unset_linux_x86_64_returns_none(self, monkeypatch, tmp_path):
        """
        On Linux x86_64, no Playwright auto-discovery is performed.

        Given: CHROMIUM_PATH is unset; platform is Linux x86_64
        When: _discover_chromium() is called
        Then: returns None (ARM64 requirement not met)
        """
        monkeypatch.delenv("CHROMIUM_PATH", raising=False)
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

        with (
            patch("regenerate_svgs.platform.system", return_value="Linux"),
            patch("regenerate_svgs.platform.machine", return_value="x86_64"),
        ):
            result = _discover_chromium()

        assert result is None

    def test_linux_aarch64_playwright_cache_has_headless_shell_returns_it(self, monkeypatch, tmp_path):
        """
        On Linux aarch64 with headless_shell in Playwright cache, return its path.

        Given: CHROMIUM_PATH unset; Linux aarch64; Playwright cache has
               an executable headless_shell nested under the cache root
        When: _discover_chromium() is called
        Then: returns the absolute path to headless_shell
        """
        monkeypatch.delenv("CHROMIUM_PATH", raising=False)
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

        binary = tmp_path / "chromium-1234" / "chrome-linux" / "headless_shell"
        binary.parent.mkdir(parents=True)
        binary.write_text("")
        binary.chmod(0o755)

        with (
            patch("regenerate_svgs.platform.system", return_value="Linux"),
            patch("regenerate_svgs.platform.machine", return_value="aarch64"),
        ):
            result = _discover_chromium()

        assert result == str(binary)

    def test_linux_aarch64_playwright_cache_has_only_chrome_returns_it(self, monkeypatch, tmp_path):
        """
        On Linux aarch64 with only chrome (no headless_shell) in cache, return chrome.

        Given: CHROMIUM_PATH unset; Linux aarch64; Playwright cache has an
               executable chrome binary but no headless_shell
        When: _discover_chromium() is called
        Then: returns the absolute path to chrome
        """
        monkeypatch.delenv("CHROMIUM_PATH", raising=False)
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

        binary = tmp_path / "chromium-1234" / "chrome-linux" / "chrome"
        binary.parent.mkdir(parents=True)
        binary.write_text("")
        binary.chmod(0o755)

        with (
            patch("regenerate_svgs.platform.system", return_value="Linux"),
            patch("regenerate_svgs.platform.machine", return_value="aarch64"),
        ):
            result = _discover_chromium()

        assert result == str(binary)

    def test_linux_aarch64_empty_playwright_cache_returns_none(self, monkeypatch, tmp_path):
        """
        On Linux aarch64 with an empty Playwright cache, return None.

        Given: CHROMIUM_PATH unset; Linux aarch64; Playwright cache directory
               exists but contains no headless_shell or chrome binaries
        When: _discover_chromium() is called
        Then: returns None
        """
        monkeypatch.delenv("CHROMIUM_PATH", raising=False)
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

        # Cache dir exists but is empty
        (tmp_path / "chromium-1234").mkdir()

        with (
            patch("regenerate_svgs.platform.system", return_value="Linux"),
            patch("regenerate_svgs.platform.machine", return_value="aarch64"),
        ):
            result = _discover_chromium()

        assert result is None

    def test_linux_aarch64_headless_shell_preferred_over_chrome_when_both_exist(self, monkeypatch, tmp_path):
        """
        When both headless_shell and chrome are present, headless_shell wins.

        Given: CHROMIUM_PATH unset; Linux aarch64; Playwright cache has both
               headless_shell and chrome executables under the same directory
        When: _discover_chromium() is called
        Then: returns the absolute path to headless_shell (higher priority)
        """
        monkeypatch.delenv("CHROMIUM_PATH", raising=False)
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

        browser_dir = tmp_path / "chromium-1234" / "chrome-linux"
        browser_dir.mkdir(parents=True)

        headless = browser_dir / "headless_shell"
        headless.write_text("")
        headless.chmod(0o755)

        chrome = browser_dir / "chrome"
        chrome.write_text("")
        chrome.chmod(0o755)

        with (
            patch("regenerate_svgs.platform.system", return_value="Linux"),
            patch("regenerate_svgs.platform.machine", return_value="aarch64"),
        ):
            result = _discover_chromium()

        assert result == str(headless)

    def test_playwright_browsers_path_env_overrides_default_cache_location(self, monkeypatch, tmp_path):
        """
        PLAYWRIGHT_BROWSERS_PATH env directs the search to a custom directory.

        Given: CHROMIUM_PATH unset; Linux aarch64; PLAYWRIGHT_BROWSERS_PATH
               points to a custom tmp directory containing headless_shell
        When: _discover_chromium() is called
        Then: returns the binary found in the custom directory (not ~/.cache/ms-playwright)
        """
        monkeypatch.delenv("CHROMIUM_PATH", raising=False)
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

        binary = tmp_path / "chromium-9999" / "chrome-linux" / "headless_shell"
        binary.parent.mkdir(parents=True)
        binary.write_text("")
        binary.chmod(0o755)

        with (
            patch("regenerate_svgs.platform.system", return_value="Linux"),
            patch("regenerate_svgs.platform.machine", return_value="aarch64"),
        ):
            result = _discover_chromium()

        assert result == str(binary)

    def test_chromium_path_env_wins_over_playwright_cache(self, monkeypatch, tmp_path):
        """
        CHROMIUM_PATH at priority 1 is returned even when ARM64 Playwright cache has binaries.

        Given: CHROMIUM_PATH="/explicit/chromium"; Linux aarch64; Playwright
               cache also contains an executable headless_shell
        When: _discover_chromium() is called
        Then: returns "/explicit/chromium" — env var takes priority over ARM64 discovery
        """
        monkeypatch.setenv("CHROMIUM_PATH", "/explicit/chromium")
        monkeypatch.setenv("PLAYWRIGHT_BROWSERS_PATH", str(tmp_path))

        binary = tmp_path / "chromium-1234" / "chrome-linux" / "headless_shell"
        binary.parent.mkdir(parents=True)
        binary.write_text("")
        binary.chmod(0o755)

        with (
            patch("regenerate_svgs.platform.system", return_value="Linux"),
            patch("regenerate_svgs.platform.machine", return_value="aarch64"),
        ):
            result = _discover_chromium()

        assert result == "/explicit/chromium"

    def test_linux_aarch64_uses_default_cache_when_playwright_env_unset(self, monkeypatch, tmp_path):
        """
        On linux-aarch64 with PLAYWRIGHT_BROWSERS_PATH unset, falls back to
        ~/.cache/ms-playwright by treating $HOME as the user's home.

        Given: CHROMIUM_PATH unset, PLAYWRIGHT_BROWSERS_PATH unset, HOME points
               to a tmp dir containing .cache/ms-playwright/chromium-1234/
               chrome-linux/headless_shell
        When: _discover_chromium() is called on linux-aarch64
        Then: returns the binary path under the default cache location
        """
        monkeypatch.delenv("CHROMIUM_PATH", raising=False)
        monkeypatch.delenv("PLAYWRIGHT_BROWSERS_PATH", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path))

        binary = tmp_path / ".cache" / "ms-playwright" / "chromium-1234" / "chrome-linux" / "headless_shell"
        binary.parent.mkdir(parents=True)
        binary.touch()
        binary.chmod(0o755)

        with (
            patch("regenerate_svgs.platform.system", return_value="Linux"),
            patch("regenerate_svgs.platform.machine", return_value="aarch64"),
        ):
            result = _discover_chromium()

        assert result == str(binary)


# ===========================================================================
# Test Summary
# ===========================================================================
"""
Test Summary
============
Total Tests: 42
- Helper functions:         13  (TestPuppeteerConfig x5, TestPathMatching x8)
- Happy path / main:         5  (TestMainHappyPath)
- Filtering:                 3  (TestFiltering)
- Failure modes:             4  (TestFailureModes)
- Env handling:              3  (TestEnvHandling)
- Cleanup:                   1  (TestCleanup)
- Subprocess call shape:     2  (TestSubprocessCallShape)
- Chromium discovery:       11  (TestChromiumDiscovery)

Coverage Areas:
- _build_puppeteer_config: None, empty string, and set path branches
- _output_path: .mmd and .mermaid extensions, multi-dot filenames
- _is_mermaid_file: .mmd, .mermaid, non-mermaid, wrong directory
- main(): single file, two files, mixed extensions+txt (filtering)
- mmdc command shape: -t neutral -b transparent -p flags present
- git add called with SVG output path on success
- git add not called when mmdc fails
- Continue-on-error: second file attempted after first mmdc failure
- Exit code 0 iff all conversions + git adds succeed
- CHROMIUM_PATH unset/empty → no executablePath in config JSON
- CHROMIUM_PATH set → executablePath present in config JSON
- Temp config file cleaned up in finally even when subprocess raises
- All subprocess.run calls use list form (no shell=True)
- Per-file ordering: mmdc precedes git add for each file
- _discover_chromium: CHROMIUM_PATH priority 1 (set/empty/wins-over-cache)
- _discover_chromium: no ARM64 discovery on darwin or linux x86_64
- _discover_chromium: headless_shell found on linux aarch64
- _discover_chromium: chrome fallback when headless_shell absent
- _discover_chromium: returns None when cache is empty
- _discover_chromium: headless_shell preferred over chrome when both present
- _discover_chromium: PLAYWRIGHT_BROWSERS_PATH env controls cache root
- _discover_chromium: default ~/.cache/ms-playwright used when PLAYWRIGHT_BROWSERS_PATH unset
"""

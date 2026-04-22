#!/usr/bin/env python3
"""Tests for scripts/hooks/precommit/prettier_site_assets.py

This module tests the pre-commit framework hook that runs prettier on staged
site-asset files (``.mjs``, ``.css``, ``.html``, etc.) and stages the
formatted output (Mode B auto-stage). The hook is invoked by the pre-commit
framework with staged filenames as positional argv (pass_filenames: true)
and is semantically identical to the YAML sibling at
``scripts/hooks/precommit/prettier_yaml.py`` — the only meaningful difference
is the ``files:`` regex in ``.pre-commit-hooks.yaml``, NOT the Python module.

For each path in argv the wrapper:
  1. Runs ["npx", "prettier", "--write", <path>]
  2. On success (rc == 0): runs ["git", "add", <path>]
  3. On failure: skips git-add for that file but continues to the next file

Exit code is 0 if every prettier invocation and git-add succeeded; non-zero
otherwise (first-failure-wins semantics). Empty argv exits 0 with no
subprocess calls. The wrapper performs no filename filtering.

Test Coverage:
==============
Total Tests: 6

- Happy path:              2  (single + many files success, exact call shape)
- Failure modes:           3  (prettier fails mid-run, git-add fails,
                               empty argv)
- File-type leniency:      1  (non-assets argv still runs through prettier)

Coverage Target: 90%+ of prettier_site_assets.py

RED-phase note
--------------
The hook module does not exist at the time these tests are authored. Every
test in this file is expected to fail with ModuleNotFoundError until the
SWE creates ``scripts/hooks/precommit/prettier_site_assets.py`` as part of
the GREEN phase (a near-verbatim clone of prettier_yaml.py).
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Add scripts/hooks/precommit to the import path so the module under test
# can be imported as ``prettier_site_assets`` regardless of working directory.
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent / "precommit"))

from prettier_site_assets import main  # noqa: E402  (intentional late import)

# ---------------------------------------------------------------------------
# Constants mirroring realistic staged site-asset paths.
# ---------------------------------------------------------------------------

SAMPLE_MJS = "site/assets/app.mjs"
SAMPLE_CSS = "site/assets/styles.css"
SAMPLE_HTML = "site/index.html"


def _prettier_cmd(path: str) -> list[str]:
    """Return the exact prettier command expected for the given path."""
    return ["npx", "prettier", "--write", path]


def _git_add_cmd(path: str) -> list[str]:
    """Return the exact git-add command expected for the given path."""
    return ["git", "add", path]


def _make_subprocess_mock(returncode: int = 0) -> MagicMock:
    """Return a MagicMock for subprocess.run that reports the given returncode."""
    mock = MagicMock()
    mock.returncode = returncode
    return mock


# ===========================================================================
# Happy path
# ===========================================================================


def test_main_runs_prettier_write_on_each_staged_file():
    """
    The wrapper must invoke prettier then git-add for every argv entry, in order.

    Given: argv contains three site-asset paths (.mjs, .css, .html) and every
           subprocess call succeeds
    When: main(argv) is invoked
    Then: subprocess.run is called six times in the order prettier-A,
          git-add-A, prettier-B, git-add-B, prettier-C, git-add-C, and main()
          returns 0
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_subprocess_mock(0)

        result = main([SAMPLE_MJS, SAMPLE_CSS, SAMPLE_HTML])

    assert result == 0
    assert mock_run.call_count == 6

    calls = [c.args[0] for c in mock_run.call_args_list]
    assert calls == [
        _prettier_cmd(SAMPLE_MJS),
        _git_add_cmd(SAMPLE_MJS),
        _prettier_cmd(SAMPLE_CSS),
        _git_add_cmd(SAMPLE_CSS),
        _prettier_cmd(SAMPLE_HTML),
        _git_add_cmd(SAMPLE_HTML),
    ]


def test_main_returns_zero_on_all_success():
    """
    A single-file happy path must yield exit code 0 with exactly two subprocess calls.

    Given: argv contains one site-asset path and every subprocess call succeeds
    When: main(argv) is invoked
    Then: main() returns 0 and exactly one prettier call + one git-add call
          are made, with the exact expected list arguments
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_subprocess_mock(0)

        result = main([SAMPLE_MJS])

    assert result == 0
    assert mock_run.call_count == 2

    calls = [c.args[0] for c in mock_run.call_args_list]
    assert calls[0] == _prettier_cmd(SAMPLE_MJS)
    assert calls[1] == _git_add_cmd(SAMPLE_MJS)


# ===========================================================================
# Failure modes
# ===========================================================================


def test_main_returns_nonzero_on_prettier_failure():
    """
    Prettier failure on one file must not block later files, and git-add is skipped.

    Given: argv has three paths; prettier succeeds for the first, FAILS for the
           second, and succeeds for the third
    When: main(argv) is invoked
    Then: prettier is attempted for every file; git-add is called for files 1
          and 3 but NOT for file 2; main() returns non-zero
    """

    def side_effect(cmd, **kwargs):
        if cmd == _prettier_cmd(SAMPLE_CSS):
            return _make_subprocess_mock(1)
        return _make_subprocess_mock(0)

    with patch("subprocess.run", side_effect=side_effect) as mock_run:
        result = main([SAMPLE_MJS, SAMPLE_CSS, SAMPLE_HTML])

    assert result != 0

    calls = [c.args[0] for c in mock_run.call_args_list]
    # Prettier was attempted for every file
    assert _prettier_cmd(SAMPLE_MJS) in calls
    assert _prettier_cmd(SAMPLE_CSS) in calls
    assert _prettier_cmd(SAMPLE_HTML) in calls
    # git-add skipped for the failed file, but kept for the successes
    assert _git_add_cmd(SAMPLE_MJS) in calls
    assert _git_add_cmd(SAMPLE_CSS) not in calls, "git-add must not run when prettier fails for that file"
    assert _git_add_cmd(SAMPLE_HTML) in calls


def test_main_returns_nonzero_on_git_add_failure():
    """
    A git-add failure after a successful prettier must still produce a non-zero exit.

    Given: argv has one path; prettier succeeds (rc=0) but git-add fails (rc=1)
    When: main(argv) is invoked
    Then: main() returns non-zero so the silent stage miss is surfaced to the
          pre-commit framework
    """
    responses = [
        _make_subprocess_mock(0),  # prettier succeeds
        _make_subprocess_mock(1),  # git add fails
    ]

    with patch("subprocess.run", side_effect=responses):
        result = main([SAMPLE_MJS])

    assert result != 0


def test_main_returns_zero_on_empty_argv():
    """
    Empty argv must short-circuit with no subprocess calls.

    Given: main([]) is invoked
    When: The wrapper executes
    Then: subprocess.run is never called and main() returns 0
    """
    with patch("subprocess.run") as mock_run:
        result = main([])

    assert result == 0
    mock_run.assert_not_called()


# ===========================================================================
# File-type leniency
# ===========================================================================


@pytest.mark.parametrize(
    "path",
    [
        "site/assets/app.mjs",
        "site/assets/styles.css",
        "site/index.html",
        "README.md",
    ],
    ids=["mjs", "css", "html", "md"],
)
def test_main_file_type_support(path):
    """
    The wrapper must not filter filenames — every argv entry runs through prettier.

    Given: argv contains a path that the site-assets hook might or might not
           be expected to handle (`.mjs`, `.css`, `.html`, `.md`)
    When: main([path]) is invoked
    Then: prettier is called with that path and git-add is called on success;
          main() returns 0 — pinning the "no filtering in the Python module"
          contract (the `files:` regex in .pre-commit-hooks.yaml is the sole
          filter)
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _make_subprocess_mock(0)

        result = main([path])

    assert result == 0

    calls = [c.args[0] for c in mock_run.call_args_list]
    assert _prettier_cmd(path) in calls, "wrapper must not filter filenames"
    assert _git_add_cmd(path) in calls, "git-add must follow successful prettier"


# ===========================================================================
# Test Summary
# ===========================================================================
"""
Test Summary
============
Total Tests: 6 (plus 4 parametrize IDs on test_main_file_type_support -> 9 total)

- test_main_runs_prettier_write_on_each_staged_file
- test_main_returns_zero_on_all_success
- test_main_returns_nonzero_on_prettier_failure
- test_main_returns_nonzero_on_git_add_failure
- test_main_returns_zero_on_empty_argv
- test_main_file_type_support (parametrized x4: mjs, css, html, md)

Coverage Areas:
- Exact prettier command shape: ["npx", "prettier", "--write", <path>]
- Per-file ordering: prettier before git-add
- Continue-on-error: subsequent files attempted after a mid-run prettier fail
- git-add skipped when prettier fails for that file
- git-add failure propagates as non-zero exit code
- Empty argv exits 0 with zero subprocess calls
- No filename filtering (regex in .pre-commit-hooks.yaml is the sole filter)
"""

#!/usr/bin/env python3
"""Tests for scripts/hooks/precommit/validate_persona_site_build.py

This module tests the pre-commit framework hook that runs the persona-site
builder in-process against the currently-staged YAML files and schemas. The
hook is invoked by the pre-commit framework with `pass_filenames: false`, so
positional argv is informational only and MUST NOT influence the build.

On a clean tree the hook must return 0 without polluting the working tree:
the module is expected to write its JSON output into a
`tempfile.TemporaryDirectory()` so nothing leaks into `site/generated/`.
On any pipeline failure (malformed YAML, missing inputs, schema rejection,
etc.) the hook must return a non-zero exit code and surface a clear error
message on stderr.

Test Coverage:
==============
Total Tests: 8

- Happy path:                2  (current YAML succeeds; argv is ignored)
- Argv contract:             1  (variety of argv payloads behave identically)
- Failure modes:             4  (broken YAML, missing YAML, schema rejection,
                                 stderr/stdout contract on failure)
- Working-tree isolation:    1  (repo `site/generated/` is untouched)

Coverage Target: 85%+ of validate_persona_site_build.py

RED-phase note
--------------
The hook module does not exist at the time these tests are authored. Every
test in this file is expected to fail with ModuleNotFoundError until the
SWE creates `scripts/hooks/precommit/validate_persona_site_build.py` as part
of the GREEN phase.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Make both the precommit hook module AND the scripts package importable.
# The hook module lives at scripts/hooks/precommit/validate_persona_site_build.py
# and internally imports scripts.build_persona_site_data, so both roots must be
# on sys.path before the late import below.
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts" / "hooks" / "precommit"))

from validate_persona_site_build import main  # noqa: E402  (intentional late import)

# ---------------------------------------------------------------------------
# Constants & helpers
# ---------------------------------------------------------------------------

# The module the hook is expected to delegate to. Monkeypatching the default
# path constants on this module is how several failure-mode tests simulate
# broken framework YAML without touching the real files on disk.
BUILDER_MODULE = "scripts.build_persona_site_data"

# Output file written by the builder. The hook must route this into a temp
# directory so the repo's site/generated/ tree is never mutated.
GENERATED_JSON_REL = Path("site") / "generated" / "persona-site-data.json"


def _write_broken_risks_yaml(tmp_path: Path) -> Path:
    """Write a risks.yaml variant that triggers TypeError in normalize_text_entries.

    Three levels of list nesting is explicitly unsupported (see
    test_normalize_text_entries_raises_on_deeper_nesting in
    test_build_persona_site_data.py); the builder surfaces a TypeError which
    the hook must catch and convert into a non-zero exit + stderr message.
    """
    path = tmp_path / "risks.yaml"
    path.write_text(
        """title: Broken Risks
description:
  - Broken
risks:
  - id: riskBroken
    title: Broken
    category: risksRuntimeInputSecurity
    shortDescription:
      - short
    longDescription:
      - - - too-deep
    personas:
      - personaModelProvider
    controls:
      - controlInputValidationAndSanitization
""",
        encoding="utf-8",
    )
    return path


# ===========================================================================
# Happy path
# ===========================================================================


def test_main_returns_zero_on_current_yaml():
    """
    The hook must succeed against the currently-committed framework YAML.

    Given: The live risk-map/yaml/*.yaml files and the live schemas
    When: main([]) is invoked (pre-commit default — no filenames passed)
    Then: The hook returns 0
    """
    assert main([]) == 0


def test_main_ignores_argv_filenames():
    """
    The hook must treat argv as informational only.

    Given: argv contains a non-empty list of filenames (as would happen if a
           future maintainer accidentally set `pass_filenames: true`)
    When: main(argv) is invoked
    Then: The hook still returns 0 — the argv is ignored, not parsed
    """
    argv = [
        "risk-map/yaml/personas.yaml",
        "risk-map/yaml/risks.yaml",
        "risk-map/yaml/controls.yaml",
    ]
    assert main(argv) == 0


# ===========================================================================
# Argv contract
# ===========================================================================


@pytest.mark.parametrize(
    "argv",
    [
        [],
        ["risk-map/yaml/risks.yaml"],
        [
            "risk-map/yaml/personas.yaml",
            "risk-map/yaml/risks.yaml",
            "risk-map/yaml/controls.yaml",
        ],
        ["--unexpected-flag", "arbitrary", "strings"],
    ],
    ids=["empty", "one-file", "many-files", "arbitrary-tokens"],
)
def test_main_argv_contract_is_ignored(argv):
    """
    The hook must behave identically regardless of what argv contains.

    Given: A variety of argv payloads (empty, one file, many files, arbitrary
           tokens including strings that look like flags)
    When: main(argv) is invoked
    Then: The exit code is 0 in every case — pinning the "argv is ignored"
          contract that follows from pass_filenames: false
    """
    assert main(argv) == 0


# ===========================================================================
# Failure modes
# ===========================================================================


def test_main_returns_nonzero_on_broken_yaml(tmp_path, monkeypatch, capsys):
    """
    A malformed risks.yaml must surface as a non-zero exit with stderr output.

    Given: DEFAULT_RISKS_PATH is monkeypatched to point at a risks.yaml whose
           longDescription nests three levels deep (triggers TypeError in
           normalize_text_entries)
    When: main([]) is invoked
    Then: The return code is non-zero AND stderr is non-empty

    Spec-resolution note: the hook is expected to import the default-path
    constants from scripts.build_persona_site_data (rather than hard-coding
    its own copies) so that this style of monkeypatching works.
    """
    broken = _write_broken_risks_yaml(tmp_path)
    monkeypatch.setattr(f"{BUILDER_MODULE}.DEFAULT_RISKS_PATH", broken)

    result = main([])

    captured = capsys.readouterr()
    assert result != 0, "broken risks.yaml must cause a non-zero exit"
    assert captured.err.strip() != "", "failure path must write an error to stderr"


def test_main_returns_nonzero_on_missing_yaml(tmp_path, monkeypatch, capsys):
    """
    A missing personas.yaml must surface as a non-zero exit with stderr output.

    Given: DEFAULT_PERSONAS_PATH is monkeypatched to a path that does not exist
    When: main([]) is invoked
    Then: The return code is non-zero AND stderr mentions the missing path
          (or otherwise identifies the failure surface)
    """
    missing = tmp_path / "does-not-exist" / "personas.yaml"
    assert not missing.exists()
    monkeypatch.setattr(f"{BUILDER_MODULE}.DEFAULT_PERSONAS_PATH", missing)

    result = main([])

    captured = capsys.readouterr()
    assert result != 0, "missing personas.yaml must cause a non-zero exit"
    assert captured.err.strip() != "", "failure path must write an error to stderr"


def test_main_returns_nonzero_on_schema_validation_failure(tmp_path, monkeypatch, capsys):
    """
    A builder output that fails the output schema must exit non-zero.

    Given: The builder's in-memory _OUTPUT_SCHEMA is monkeypatched to a schema
           that requires a top-level key the real builder never emits
    When: main([]) is invoked
    Then: The return code is non-zero AND stderr is non-empty

    This pins the contract that the hook surfaces jsonschema.ValidationError
    raised by write_site_data() — the last line of defence before the
    generated JSON is written.
    """
    rejecting_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "required": ["nonExistentKey"],
    }
    monkeypatch.setattr(f"{BUILDER_MODULE}._OUTPUT_SCHEMA", rejecting_schema)

    result = main([])

    captured = capsys.readouterr()
    assert result != 0, "schema-rejecting output must cause a non-zero exit"
    assert captured.err.strip() != "", "failure path must write an error to stderr"


def test_main_failure_leaves_stdout_free_of_success_marker(tmp_path, monkeypatch, capsys):
    """
    On failure, stdout must not contain the builder's success marker.

    Given: Any failure mode (here: a missing personas.yaml)
    When: main([]) is invoked
    Then: stdout does NOT contain the "Wrote ..." success line that the CLI
          builder prints on the happy path; this prevents operators from
          being misled by partial output
    """
    missing = tmp_path / "missing.yaml"
    monkeypatch.setattr(f"{BUILDER_MODULE}.DEFAULT_PERSONAS_PATH", missing)

    result = main([])

    captured = capsys.readouterr()
    assert result != 0
    assert "Wrote" not in captured.out, (
        "failure path must not emit the builder's 'Wrote <path>' success marker on stdout"
    )


# ===========================================================================
# Working-tree isolation
# ===========================================================================


def test_main_does_not_write_into_repo_site_generated():
    """
    The hook must not mutate the repository's site/generated/ tree.

    Given: The repository already has a committed persona-site-data.json
           inside site/generated/
    When: main([]) is invoked on a clean tree
    Then: The mtime of site/generated/persona-site-data.json is
          unchanged — i.e. the hook routed its build into a temp directory
          rather than touching the committed artifact

    This guards against a regression where a future refactor drops the
    tempfile.TemporaryDirectory() sandbox and starts overwriting the
    committed JSON on every commit (which would either trip the pre-commit
    framework's modify-and-fail detector or silently churn the tree).
    """
    committed_json = REPO_ROOT / GENERATED_JSON_REL
    if not committed_json.exists():
        pytest.skip(
            f"Committed {committed_json.relative_to(REPO_ROOT)} is not present; "
            "cannot assert the hook left it untouched."
        )

    before = committed_json.stat().st_mtime_ns

    assert main([]) == 0

    after = committed_json.stat().st_mtime_ns
    assert before == after, (
        f"Hook must not touch the committed {committed_json.name}; mtime changed from {before} to {after}"
    )


# ===========================================================================
# Test Summary
# ===========================================================================
"""
Test Summary
============
Total Tests: 8

- test_main_returns_zero_on_current_yaml
- test_main_ignores_argv_filenames
- test_main_argv_contract_is_ignored (parametrized x4)
- test_main_returns_nonzero_on_broken_yaml
- test_main_returns_nonzero_on_missing_yaml
- test_main_returns_nonzero_on_schema_validation_failure
- test_main_failure_leaves_stdout_free_of_success_marker
- test_main_does_not_write_into_repo_site_generated

Coverage Areas:
- main([]) returns 0 on current framework YAML
- argv is ignored (pass_filenames: false contract)
- Non-zero exit + stderr on TypeError raised by normalize_text_entries
- Non-zero exit + stderr when an input YAML is missing
- Non-zero exit + stderr on output schema validation failure
- Failure stdout does not contain the builder's "Wrote ..." success marker
- Working tree isolation: committed site/generated/ JSON is never touched
"""

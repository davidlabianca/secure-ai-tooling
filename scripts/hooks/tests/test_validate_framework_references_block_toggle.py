#!/usr/bin/env python3
"""
Tests for the --block toggle on validate_framework_references.py (task 2.3.6).

Per ADR-021 D8: deprecated-persona reference enforcement ships as a
warn-only-first validator with a block toggle. Default (no --block): warnings
print, exit 0. With --block and any deprecated-persona warnings: exit 1.
With --block and a clean corpus (no deprecated refs): exit 0.

These tests follow the warn-only-first / block-toggle pattern established by
A3 (validate_yaml_prose_subset.py) and A3.7 (lifecycle uniqueness).

Test structure
--------------
1. TestCheckDeprecatedPersonaUsageRegressionGuard
   Pure-function tests on the already-existing
   check_deprecated_persona_usage() at line 345 of
   validate_framework_references.py.  These tests PASS today (red phase for
   the function is already green) and serve as regression guards so SWE cannot
   accidentally change the function's semantics while wiring the toggle.

2. TestBlockToggleCLI
   Subprocess-based end-to-end tests that pin the observable CLI exit codes.
   These tests FAIL today because --block does not yet exist on the script's
   argparse, causing argparse to exit 2 ("unrecognized arguments").  That exit-2
   is the expected red-phase failure mode.

Synthesized-corpus harness
--------------------------
For the clean-corpus subprocess tests we need to point the script at YAML files
that have no deprecated-persona references.  The script's get_staged_yaml_files()
reads files at the paths risk-map/yaml/frameworks.yaml, risks.yaml, controls.yaml,
personas.yaml relative to cwd.  The cleanest approach is:
  - create tmp_path / "risk-map" / "yaml"
  - write minimal valid YAML at each of the four paths
  - invoke the script via subprocess with cwd=tmp_path and --force

The live-corpus subprocess tests use the actual repo-root as cwd (risk-map/yaml/
files already exist there); they pin:
  - no --block -> exit 0  (today's behaviour, must not regress)
  - --block    -> exit 1  (corpus has 88 deprecated-persona refs; toggle fires)
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

# ---------------------------------------------------------------------------
# sys.path injection — same pattern as the existing test file
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

from validate_framework_references import check_deprecated_persona_usage  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Absolute path to the script under test — used in all subprocess invocations.
_SCRIPT = Path(__file__).parent.parent / "validate_framework_references.py"

# Repository root (worktree root) — used as cwd for live-corpus tests.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Minimal frameworks.yaml content: one valid framework so validate_frameworks()
# does not short-circuit at "no frameworks found".
_MINIMAL_FRAMEWORKS: dict[str, Any] = {
    "frameworks": [
        {
            "id": "mitre-atlas",
            "name": "MITRE ATLAS",
            "fullName": "Adversarial Threat Landscape for AI Systems",
            "description": "MITRE ATLAS framework",
            "baseUri": "https://atlas.mitre.org",
            "applicableTo": ["risks", "controls"],
        }
    ]
}

# Deprecated persona and one current persona.
_PERSONAS_WITH_DEPRECATED: dict[str, Any] = {
    "personas": [
        {
            "id": "personaModelCreator",
            "title": "Model Creator",
            "description": ["Legacy persona, retained for backward compatibility."],
            "deprecated": True,
        },
        {
            "id": "personaModelProvider",
            "title": "Model Provider",
            "description": ["A current persona."],
            "deprecated": False,
        },
    ]
}

# Personas with NO deprecated members (all current).
_PERSONAS_ALL_CURRENT: dict[str, Any] = {
    "personas": [
        {
            "id": "personaModelProvider",
            "title": "Model Provider",
            "description": ["A current persona."],
        },
        {
            "id": "personaApplicationDeveloper",
            "title": "Application Developer",
            "description": ["A current persona."],
        },
    ]
}

# Controls that reference the deprecated persona.
_CONTROLS_WITH_DEPRECATED_REF: dict[str, Any] = {
    "controls": [
        {
            "id": "controlA",
            "title": "Control A",
            "personas": ["personaModelCreator"],  # deprecated
        },
        {
            "id": "controlB",
            "title": "Control B",
            "personas": ["personaModelProvider"],  # current — no warning
        },
    ]
}

# Controls that reference only current personas.
_CONTROLS_CLEAN: dict[str, Any] = {
    "controls": [
        {
            "id": "controlA",
            "title": "Control A",
            "personas": ["personaModelProvider"],
        },
    ]
}

# Risks that reference the deprecated persona.
_RISKS_WITH_DEPRECATED_REF: dict[str, Any] = {
    "risks": [
        {
            "id": "riskAlpha",
            "title": "Risk Alpha",
            "personas": ["personaModelCreator"],  # deprecated
        },
        {
            "id": "riskBeta",
            "title": "Risk Beta",
            "personas": ["personaModelProvider"],  # current — no warning
        },
    ]
}

# Risks that reference only current personas.
_RISKS_CLEAN: dict[str, Any] = {
    "risks": [
        {
            "id": "riskAlpha",
            "title": "Risk Alpha",
            "personas": ["personaModelProvider"],
        },
    ]
}

# Risks with NO personas field at all.
_RISKS_NO_PERSONAS: dict[str, Any] = {
    "risks": [
        {
            "id": "riskAlpha",
            "title": "Risk Alpha",
        }
    ]
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_corpus(base: Path, personas: dict, controls: dict, risks: dict) -> Path:
    """Write a minimal four-file corpus under base/risk-map/yaml/ and return base.

    Args:
        base: Temporary directory root (passed in from tmp_path).
        personas: Parsed personas.yaml content.
        controls: Parsed controls.yaml content.
        risks: Parsed risks.yaml content.

    Returns:
        The base path (for use as subprocess cwd).
    """
    yaml_dir = base / "risk-map" / "yaml"
    yaml_dir.mkdir(parents=True)
    (yaml_dir / "frameworks.yaml").write_text(yaml.dump(_MINIMAL_FRAMEWORKS), encoding="utf-8")
    (yaml_dir / "personas.yaml").write_text(yaml.dump(personas), encoding="utf-8")
    (yaml_dir / "controls.yaml").write_text(yaml.dump(controls), encoding="utf-8")
    (yaml_dir / "risks.yaml").write_text(yaml.dump(risks), encoding="utf-8")
    return base


def _run(cwd: Path, *extra_args: str) -> subprocess.CompletedProcess:
    """Run the script via subprocess with --force and any extra args.

    Always passes --force so the script validates regardless of git-staged state.
    cwd is set to the given directory so get_staged_yaml_files() resolves
    risk-map/yaml/* relative to it.

    Args:
        cwd: Working directory for the subprocess.
        *extra_args: Additional CLI arguments (e.g. "--block").

    Returns:
        CompletedProcess with returncode, stdout, stderr.
    """
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--force", *extra_args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


# ===========================================================================
# 1. Pure-function regression guard — check_deprecated_persona_usage()
# ===========================================================================


class TestCheckDeprecatedPersonaUsageRegressionGuard:
    """Regression guard for check_deprecated_persona_usage() — these tests pass today.

    The function already exists at validate_framework_references.py:345.
    These tests lock its observable behaviour so SWE cannot accidentally change
    the signature or semantics while wiring the --block toggle.
    """

    def test_control_referencing_deprecated_persona_returns_warning(self):
        """
        A control that references a deprecated persona produces a warning.

        Given: personas_data with personaModelCreator (deprecated: true),
               controls_data with a control whose personas list includes
               personaModelCreator, and risks_data with no personas
        When: check_deprecated_persona_usage is called
        Then: Returns a non-empty list; warning mentions the control ID and persona ID
        """
        result = check_deprecated_persona_usage(
            _PERSONAS_WITH_DEPRECATED,
            _CONTROLS_WITH_DEPRECATED_REF,
            _RISKS_CLEAN,
        )
        assert len(result) >= 1
        combined = " ".join(result)
        assert "controlA" in combined, f"Expected 'controlA' in warnings; got: {result}"
        assert "personaModelCreator" in combined, f"Expected 'personaModelCreator' in warnings; got: {result}"

    def test_risk_referencing_deprecated_persona_returns_warning(self):
        """
        A risk that references a deprecated persona produces a warning.

        Given: personas_data with personaModelCreator (deprecated: true),
               risks_data with a risk whose personas list includes personaModelCreator,
               and controls_data with no deprecated refs
        When: check_deprecated_persona_usage is called
        Then: Returns a non-empty list; warning mentions the risk ID and persona ID
        """
        result = check_deprecated_persona_usage(
            _PERSONAS_WITH_DEPRECATED,
            _CONTROLS_CLEAN,
            _RISKS_WITH_DEPRECATED_REF,
        )
        assert len(result) >= 1
        combined = " ".join(result)
        assert "riskAlpha" in combined, f"Expected 'riskAlpha' in warnings; got: {result}"
        assert "personaModelCreator" in combined, f"Expected 'personaModelCreator' in warnings; got: {result}"

    def test_both_control_and_risk_with_deprecated_ref_returns_two_warnings(self):
        """
        Both a control and a risk referencing a deprecated persona produce two warnings.

        Given: personas_data with personaModelCreator (deprecated: true),
               controls_data with one deprecated ref, risks_data with one deprecated ref
        When: check_deprecated_persona_usage is called
        Then: Returns at least 2 warnings (one per deprecated reference found)
        """
        result = check_deprecated_persona_usage(
            _PERSONAS_WITH_DEPRECATED,
            _CONTROLS_WITH_DEPRECATED_REF,
            _RISKS_WITH_DEPRECATED_REF,
        )
        # controlA + riskAlpha both reference personaModelCreator
        assert len(result) >= 2

    def test_current_persona_reference_returns_empty_list(self):
        """
        References to non-deprecated personas produce no warnings.

        Given: personas_data with all current personas (no deprecated: true),
               controls_data and risks_data referencing only current personas
        When: check_deprecated_persona_usage is called
        Then: Returns empty list
        """
        result = check_deprecated_persona_usage(
            _PERSONAS_ALL_CURRENT,
            _CONTROLS_CLEAN,
            _RISKS_CLEAN,
        )
        assert result == [], f"Expected no warnings for current-persona refs; got: {result}"

    def test_reference_to_nonexistent_persona_id_returns_empty_list(self):
        """
        A reference to a persona ID that does not appear in personas_data at all
        is silently ignored (no warning; the function only warns on known-deprecated IDs).

        Given: personas_data with only current personas,
               controls_data referencing an ID that is not in personas_data at all
        When: check_deprecated_persona_usage is called
        Then: Returns empty list (no deprecated set to match against)
        """
        controls_with_unknown_ref: dict[str, Any] = {
            "controls": [{"id": "controlX", "title": "X", "personas": ["personaDoesNotExist"]}]
        }
        result = check_deprecated_persona_usage(
            _PERSONAS_ALL_CURRENT,
            controls_with_unknown_ref,
            _RISKS_CLEAN,
        )
        assert result == [], f"Expected no warnings for unknown persona refs; got: {result}"

    def test_none_personas_data_returns_empty_list(self):
        """
        Passing None as personas_data returns empty list (no deprecated set to build).

        Given: personas_data=None
        When: check_deprecated_persona_usage is called
        Then: Returns empty list (graceful handling)
        """
        result = check_deprecated_persona_usage(None, _CONTROLS_WITH_DEPRECATED_REF, _RISKS_WITH_DEPRECATED_REF)
        assert result == [], f"Expected empty list when personas_data is None; got: {result}"

    def test_none_controls_data_returns_empty_list_for_controls(self):
        """
        Passing None as controls_data does not crash; no control warnings are emitted.

        Given: personas_data with a deprecated persona, controls_data=None,
               risks_data with no deprecated refs
        When: check_deprecated_persona_usage is called
        Then: Returns empty list (no controls to scan)
        """
        result = check_deprecated_persona_usage(_PERSONAS_WITH_DEPRECATED, None, _RISKS_CLEAN)
        assert result == [], f"Expected empty list when controls_data is None; got: {result}"

    def test_none_risks_data_returns_empty_list_for_risks(self):
        """
        Passing None as risks_data does not crash; no risk warnings are emitted.

        Given: personas_data with a deprecated persona, controls_data with no deprecated refs,
               risks_data=None
        When: check_deprecated_persona_usage is called
        Then: Returns empty list (no risks to scan)
        """
        result = check_deprecated_persona_usage(_PERSONAS_WITH_DEPRECATED, _CONTROLS_CLEAN, None)
        assert result == [], f"Expected empty list when risks_data is None; got: {result}"

    def test_all_none_returns_empty_list(self):
        """
        All-None inputs return empty list without raising.

        Given: personas_data=None, controls_data=None, risks_data=None
        When: check_deprecated_persona_usage is called
        Then: Returns empty list
        """
        result = check_deprecated_persona_usage(None, None, None)
        assert result == [], f"Expected empty list for all-None inputs; got: {result}"

    def test_risk_without_personas_field_ignored(self):
        """
        A risk entry with no personas field is silently skipped.

        Given: personas_data with a deprecated persona, risks_data whose risks have
               no personas key
        When: check_deprecated_persona_usage is called
        Then: Returns empty list (no refs to check)
        """
        result = check_deprecated_persona_usage(
            _PERSONAS_WITH_DEPRECATED,
            _CONTROLS_CLEAN,
            _RISKS_NO_PERSONAS,
        )
        assert result == [], f"Expected no warnings for risks without personas field; got: {result}"

    def test_persona_with_no_deprecated_flag_is_not_treated_as_deprecated(self):
        """
        A persona with no 'deprecated' key (field absent) is not treated as deprecated.

        Given: personas_data where one persona has no 'deprecated' key at all,
               controls_data referencing that persona
        When: check_deprecated_persona_usage is called
        Then: Returns empty list (absent field defaults to False)
        """
        personas_no_flag: dict[str, Any] = {
            "personas": [
                {
                    "id": "personaNoFlag",
                    "title": "No Flag Persona",
                    "description": ["No deprecated field at all."],
                    # No 'deprecated' key
                }
            ]
        }
        controls_ref_no_flag: dict[str, Any] = {
            "controls": [{"id": "controlX", "title": "X", "personas": ["personaNoFlag"]}]
        }
        result = check_deprecated_persona_usage(personas_no_flag, controls_ref_no_flag, _RISKS_CLEAN)
        assert result == [], f"Expected no warnings when deprecated flag is absent; got: {result}"

    def test_returns_list_type(self):
        """
        The function always returns a list, never None.

        Given: Any valid input combination
        When: check_deprecated_persona_usage is called
        Then: Return value is a list instance
        """
        result = check_deprecated_persona_usage(
            _PERSONAS_WITH_DEPRECATED,
            _CONTROLS_CLEAN,
            _RISKS_CLEAN,
        )
        assert isinstance(result, list), f"Expected list; got {type(result)}"

    def test_each_warning_is_a_string(self):
        """
        Every element in the returned list is a string.

        Given: A corpus with at least one deprecated-persona reference
        When: check_deprecated_persona_usage is called
        Then: All elements in the returned list are str instances
        """
        result = check_deprecated_persona_usage(
            _PERSONAS_WITH_DEPRECATED,
            _CONTROLS_WITH_DEPRECATED_REF,
            _RISKS_WITH_DEPRECATED_REF,
        )
        assert len(result) > 0
        for item in result:
            assert isinstance(item, str), f"Expected str element; got {type(item)!r}: {item!r}"


# ===========================================================================
# 2. CLI exit-code tests — --block toggle
#    These tests FAIL today (red phase): --block not yet in argparse.
# ===========================================================================


class TestBlockToggleCLI:
    """End-to-end CLI tests for the --block toggle.

    These tests fail in the red phase because --block does not yet exist on
    validate_framework_references.py's argparse.  When argparse encounters an
    unrecognised argument it exits 2.  After SWE adds --block the tests are
    expected to pass (green phase).

    Live-corpus tests use _REPO_ROOT as cwd; synthesised-corpus tests build a
    minimal four-file corpus in tmp_path.
    """

    # -----------------------------------------------------------------------
    # Live-corpus: uses the actual risk-map/yaml/ tree in the worktree.
    # The corpus has 88 deprecated-persona refs (49 controls + 39 risks).
    # -----------------------------------------------------------------------

    def test_live_corpus_no_block_flag_exits_0(self):
        """
        Running without --block against the live corpus exits 0.

        This is today's existing behaviour and must not regress after adding --block.

        Given: The live risk-map/yaml/ corpus (88 deprecated-persona refs)
        When: validate_framework_references.py --force (no --block)
        Then: Exit code is 0
        """
        result = _run(_REPO_ROOT)
        assert result.returncode == 0, (
            f"Expected exit 0 without --block; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_live_corpus_with_block_flag_exits_1(self):
        """
        Running with --block against the live corpus exits 1 (88 deprecated refs).

        Given: The live risk-map/yaml/ corpus (88 deprecated-persona refs)
        When: validate_framework_references.py --force --block
        Then: Exit code is 1 (deprecated-persona warnings promoted to failures)
        """
        result = _run(_REPO_ROOT, "--block")
        assert result.returncode == 1, (
            f"Expected exit 1 with --block on live corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_live_corpus_with_block_flag_stdout_contains_deprecated_warning(self):
        """
        When --block fires, the output contains the deprecated-persona warning text.

        Given: The live corpus and --block flag
        When: validate_framework_references.py --force --block
        Then: Output contains the deprecation warning strings (so the developer
              can see which entries triggered the block)
        """
        result = _run(_REPO_ROOT, "--block")
        # Script already prints deprecation warnings to stdout; they must still appear.
        combined = result.stdout + result.stderr
        assert "deprecated" in combined.lower(), (
            f"Expected 'deprecated' in output; stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

    # -----------------------------------------------------------------------
    # Synthesised clean corpus: no deprecated refs -> --block does NOT fire.
    # -----------------------------------------------------------------------

    def test_clean_corpus_with_block_flag_exits_0(self, tmp_path):
        """
        Running with --block against a corpus with NO deprecated refs exits 0.

        The --block toggle must only promote warnings to failures when warnings
        actually exist; a clean corpus must always exit 0 regardless of --block.

        Given: A synthesised corpus where all personas are current (no deprecated: true)
               and controls/risks reference only current personas
        When: validate_framework_references.py --force --block (cwd=tmp_path)
        Then: Exit code is 0 (no deprecated-persona warnings to promote)
        """
        _write_corpus(tmp_path, _PERSONAS_ALL_CURRENT, _CONTROLS_CLEAN, _RISKS_CLEAN)
        result = _run(tmp_path, "--block")
        assert result.returncode == 0, (
            f"Expected exit 0 with --block on clean corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_clean_corpus_no_block_flag_exits_0(self, tmp_path):
        """
        Running without --block against a clean corpus exits 0.

        Baseline sanity check: the synthesised corpus harness itself is correct.

        Given: A synthesised clean corpus
        When: validate_framework_references.py --force (no --block)
        Then: Exit code is 0
        """
        _write_corpus(tmp_path, _PERSONAS_ALL_CURRENT, _CONTROLS_CLEAN, _RISKS_CLEAN)
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Expected exit 0 on clean corpus without --block; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dirty_synthesised_corpus_with_block_exits_1(self, tmp_path):
        """
        Running with --block against a synthesised dirty corpus (deprecated refs) exits 1.

        Cross-checks that the block toggle fires correctly on a synthetic corpus,
        not just the live one.

        Given: A synthesised corpus with a deprecated persona referenced by a control
        When: validate_framework_references.py --force --block
        Then: Exit code is 1
        """
        _write_corpus(tmp_path, _PERSONAS_WITH_DEPRECATED, _CONTROLS_WITH_DEPRECATED_REF, _RISKS_CLEAN)
        result = _run(tmp_path, "--block")
        assert result.returncode == 1, (
            f"Expected exit 1 with --block on dirty corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dirty_synthesised_corpus_no_block_exits_0(self, tmp_path):
        """
        Running WITHOUT --block against a dirty synthesised corpus exits 0.

        Confirms that warn-only (default) behaviour is preserved even when
        deprecated refs are present.

        Given: A synthesised corpus with a deprecated persona referenced by a control
        When: validate_framework_references.py --force (no --block)
        Then: Exit code is 0 (warnings only, no failure)
        """
        _write_corpus(tmp_path, _PERSONAS_WITH_DEPRECATED, _CONTROLS_WITH_DEPRECATED_REF, _RISKS_CLEAN)
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Expected exit 0 without --block on dirty corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    # -----------------------------------------------------------------------
    # Flag discovery: --help must list --block
    # -----------------------------------------------------------------------

    def test_help_output_contains_block_flag(self):
        """
        The --help output documents the --block flag.

        Given: The script is invoked with --help
        When: validate_framework_references.py --help
        Then: The --help text contains '--block'
        """
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--help"],
            capture_output=True,
            text=True,
        )
        # argparse --help exits 0
        assert result.returncode == 0, f"--help unexpectedly exited {result.returncode}"
        assert "--block" in result.stdout, f"Expected '--block' in --help output; got:\n{result.stdout}"


# ===========================================================================
# Test Summary
# ===========================================================================
# Total tests: 21
#
# TestCheckDeprecatedPersonaUsageRegressionGuard  (13 tests)
#   — control with deprecated ref produces warning; risk with deprecated ref
#     produces warning; both produce >=2 warnings; current-only refs produce
#     empty list; nonexistent persona ID ignored; None personas_data;
#     None controls_data; None risks_data; all-None inputs; risk without
#     personas field; absent deprecated flag treated as False; return type
#     is list; each element is str.
#
# TestBlockToggleCLI  (8 tests)
#   — live corpus + no --block -> exit 0 (regression guard);
#     live corpus + --block -> exit 1 (88 deprecated refs fire the toggle);
#     live corpus + --block -> output contains "deprecated" text;
#     clean synthesised corpus + --block -> exit 0;
#     clean synthesised corpus + no --block -> exit 0;
#     dirty synthesised corpus + --block -> exit 1;
#     dirty synthesised corpus + no --block -> exit 0 (warn-only preserved);
#     --help output contains '--block'.
#
# Red-phase failure mode
#   - Regression-guard class: PASS today (function already exists).
#   - Block-toggle CLI class: FAIL today with argparse exit 2
#     ("unrecognised arguments: --block").

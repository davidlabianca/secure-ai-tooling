#!/usr/bin/env python3
"""
Tests for the controls↔components mirror check (task 2.3.8 / issue #268).

Per ADR-020 D7: every component ID listed in controls[].components[] must
exist as a top-level component ID in components.yaml.  The literals "all"
and "none" are escape hatches — they are valid and must not be flagged.
Direction is one-way: control → component (NOT bidirectional).

The check ships warn-only with a --block toggle:
  default (no --block): print warnings, exit 0
  --block:              warnings become errors, exit 1

This mirrors the pattern established by A3 (validate_yaml_prose_subset.py)
and A3.7 / 2.3.6 (validate_framework_references.py / check_deprecated_persona_usage).

Symbol contract
---------------
The pure-function tests import `check_controls_components_mirror` from
`riskmap_validator.validator`.  SWE must expose a callable with that name.
Signature (SWE's call, but tests assume this shape):

    check_controls_components_mirror(
        controls: dict[str, ControlNode],
        component_ids: set[str],
    ) -> list[str]

Returns a list of human-readable warning strings, one per (control_id,
missing_component_id) pair or per control (SWE's call).  Empty list means
clean.

Test structure
--------------
1. TestCheckControlsComponentsMirror
   Pure-function tests on check_controls_components_mirror().
   These tests FAIL today with ImportError (function not yet implemented).
   They pin the observable contract so SWE can implement to make them pass.

2. TestBlockToggleCLI
   Subprocess-based end-to-end tests for the --block flag on validate_riskmap.py.
   These tests FAIL today with argparse exit 2 ("unrecognised arguments: --block").

Synthesised-corpus harness
--------------------------
validate_riskmap.py's --force mode reads components.yaml at the path
risk-map/yaml/components.yaml relative to cwd.  The ComponentEdgeValidator
runs first; components.yaml must therefore be structurally valid (bidirectional
edges, no missing references).  We use --allow-isolated to skip the orphan check
so minimal corpora don't need a fully-connected graph.

Minimal components.yaml shape expected by parse_components_yaml():
  - top-level key: components (list)
  - each entry has: id (str), title (str), category (str)
  - edges: {to: [...], from: [...]}  (optional, defaults to [])

Minimal controls.yaml shape expected by parse_controls_yaml():
  - top-level key: controls (list)
  - each entry has: id (str), title (str), category (str)
  - components: list[str]  (the field under test)

Live-corpus debt (verified 2026-05-04):
  controls.yaml references componentInputHandling (line 338) and
  componentOutputHandling (lines 73 and 377).  Neither exists in
  components.yaml — the actual components are
  componentApplicationInputHandling / componentApplicationOutputHandling.
  This produces ≥3 dangling reference instances across 3 controls.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# sys.path injection — same pattern as the existing test files
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "riskmap_validator"))

from riskmap_validator.models import ControlNode  # noqa: E402

# Deferred import: check_controls_components_mirror does not exist yet.
# We capture the ImportError here and re-raise it inside a pytest fixture so
# that pure-function tests fail individually while CLI test collection succeeds.
try:
    from riskmap_validator.validator import check_controls_components_mirror  # noqa: E402

    _MIRROR_IMPORT_ERROR: ImportError | None = None
except ImportError as _e:
    check_controls_components_mirror = None  # type: ignore[assignment]
    _MIRROR_IMPORT_ERROR = _e

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# Absolute path to the CLI script under test.
_SCRIPT = Path(__file__).parent.parent / "validate_riskmap.py"

# Repository root (worktree root) — used as cwd for live-corpus subprocess tests.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Known dangling component IDs in the live corpus (as of 2026-05-04).
_LIVE_DANGLING_COMPONENT_IDS = {"componentInputHandling", "componentOutputHandling"}

# Escape-hatch literals that must never produce a warning.
_ESCAPE_HATCHES = ("all", "none")

# A set of component IDs that represent a minimal valid component map for
# pure-function tests — these IDs do NOT need to match any real YAML file.
_VALID_COMPONENT_IDS = {"componentAlpha", "componentBeta", "componentGamma"}


# ---------------------------------------------------------------------------
# Helpers for pure-function tests
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Fixture that makes the deferred import visible to pure-function tests.
# If the function does not yet exist the fixture raises, failing the test
# with an informative error (rather than AttributeError on None).
# ---------------------------------------------------------------------------


@pytest.fixture
def mirror_fn():
    """Return check_controls_components_mirror, or fail with ImportError.

    Pure-function tests request this fixture so that the ImportError from
    the deferred import surfaces as a test failure rather than a collection
    error.  This keeps the CLI tests collectible and runnable independently.
    """
    if _MIRROR_IMPORT_ERROR is not None:
        raise _MIRROR_IMPORT_ERROR
    return check_controls_components_mirror


def _make_control(
    ctrl_id: str,
    components: list[str],
    category: str = "controlsModel",
) -> ControlNode:
    """Construct a ControlNode for testing.

    Args:
        ctrl_id: Control identifier (also used as title for simplicity).
        components: The components list to attach.
        category: Category string (any non-empty value satisfies ControlNode).

    Returns:
        A ControlNode with minimal required fields populated.
    """
    return ControlNode(
        title=ctrl_id,
        category=category,
        components=components,
        risks=[],
        personas=[],
    )


# ---------------------------------------------------------------------------
# Helpers for synthesised-corpus subprocess tests
# ---------------------------------------------------------------------------

# Minimal components.yaml whose two components reference each other so
# ComponentEdgeValidator does not fail on missing back-edges. The categories
# block + subcategory fields make this corpus opaque to task 2.3.9's nesting
# check (after 2.3.9 wires, every component has a valid (category, subcategory)
# pair so the nesting check stays silent and the mirror behavior remains
# isolated).
_MINIMAL_COMPONENTS: dict[str, Any] = {
    "components": [
        {
            "id": "componentAlpha",
            "title": "Alpha",
            "category": "componentsInfrastructure",
            "subcategory": "componentsData",
            "edges": {"to": ["componentBeta"], "from": []},
        },
        {
            "id": "componentBeta",
            "title": "Beta",
            "category": "componentsInfrastructure",
            "subcategory": "componentsData",
            "edges": {"to": [], "from": ["componentAlpha"]},
        },
    ],
    "categories": [
        {
            "id": "componentsInfrastructure",
            "title": "Infrastructure",
            "subcategory": [
                {"id": "componentsData", "title": "Data"},
            ],
        },
    ],
}

# controls.yaml that references only IDs present in _MINIMAL_COMPONENTS.
_CLEAN_CONTROLS: dict[str, Any] = {
    "controls": [
        {
            "id": "controlClean",
            "title": "Clean Control",
            "category": "controlsModel",
            "components": ["componentAlpha", "componentBeta"],
            "risks": [],
            "personas": [],
        }
    ]
}

# controls.yaml that references a component ID absent from _MINIMAL_COMPONENTS.
_DIRTY_CONTROLS: dict[str, Any] = {
    "controls": [
        {
            "id": "controlDirty",
            "title": "Dirty Control",
            "category": "controlsModel",
            "components": ["componentAlpha", "componentDoesNotExist"],
            "risks": [],
            "personas": [],
        }
    ]
}

# controls.yaml using only "all" escape hatch — must not trigger mirror warning.
_ESCAPE_ALL_CONTROLS: dict[str, Any] = {
    "controls": [
        {
            "id": "controlAll",
            "title": "All Control",
            "category": "controlsGovernance",
            "components": ["all"],
            "risks": [],
            "personas": [],
        }
    ]
}


def _write_corpus(
    base: Path,
    components: dict[str, Any],
    controls: dict[str, Any],
) -> Path:
    """Write a minimal two-file corpus under base/risk-map/yaml/ and return base.

    validate_riskmap.py also reads risks.yaml; we write a minimal stub.
    The risks file is not exercised by the mirror check so its contents are
    irrelevant as long as parse_risks_yaml() does not error.

    Args:
        base: Temporary directory root (from tmp_path fixture).
        components: Parsed components.yaml content dict.
        controls: Parsed controls.yaml content dict.

    Returns:
        The base path (for use as subprocess cwd).
    """
    yaml_dir = base / "risk-map" / "yaml"
    yaml_dir.mkdir(parents=True)
    (yaml_dir / "components.yaml").write_text(yaml.dump(components), encoding="utf-8")
    (yaml_dir / "controls.yaml").write_text(yaml.dump(controls), encoding="utf-8")
    # Minimal risks stub so the script doesn't fail on a missing file.
    (yaml_dir / "risks.yaml").write_text(yaml.dump({"risks": []}), encoding="utf-8")
    return base


def _run(cwd: Path, *extra_args: str) -> subprocess.CompletedProcess:
    """Run validate_riskmap.py via subprocess with --force and any extra args.

    Always passes --force so the script validates regardless of git-staged state.
    Always passes --allow-isolated so minimal synthesised corpora do not fail
    the ComponentEdgeValidator's orphan check.

    Args:
        cwd: Working directory for the subprocess.
        *extra_args: Additional CLI arguments (e.g. "--block").

    Returns:
        CompletedProcess with returncode, stdout, stderr.
    """
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--force", "--allow-isolated", *extra_args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


# ===========================================================================
# 1. Pure-function tests — check_controls_components_mirror()
#    These tests FAIL today with ImportError (red phase).
# ===========================================================================


class TestCheckControlsComponentsMirror:
    """Pure-function tests for check_controls_components_mirror().

    The function does not exist yet.  Every test in this class requests the
    `mirror_fn` fixture which raises ImportError when the symbol is absent,
    causing each test to FAIL (not ERROR at collection time).  This keeps
    TestBlockToggleCLI collectible and runnable independently.

    Once SWE implements the function in riskmap_validator/validator.py,
    these tests are the green-phase acceptance criteria.
    """

    def test_clean_controls_return_empty_list(self, mirror_fn):
        """
        All controls referencing only known component IDs returns empty list.

        Given: controls dict where every component reference is in component_ids
        When: check_controls_components_mirror() is called
        Then: Returns an empty list (no warnings)
        """
        controls = {
            "controlA": _make_control("controlA", ["componentAlpha", "componentBeta"]),
            "controlB": _make_control("controlB", ["componentGamma"]),
        }
        result = mirror_fn(controls, _VALID_COMPONENT_IDS)
        assert result == [], f"Expected no warnings for clean controls; got: {result}"

    def test_single_dangling_ref_returns_warning_naming_control_and_component(self, mirror_fn):
        """
        One control referencing a missing component ID produces a warning
        that names both the control ID and the missing component ID.

        Given: controls dict with one control that references componentDoesNotExist
               which is absent from component_ids
        When: check_controls_components_mirror() is called
        Then: Returns a non-empty list; warning text contains both
              "controlMissing" and "componentDoesNotExist"
        """
        controls = {"controlMissing": _make_control("controlMissing", ["componentAlpha", "componentDoesNotExist"])}
        result = mirror_fn(controls, _VALID_COMPONENT_IDS)
        assert len(result) >= 1, f"Expected at least one warning; got: {result}"
        combined = " ".join(result)
        assert "controlMissing" in combined, f"Expected 'controlMissing' in warning text; got: {result}"
        assert "componentDoesNotExist" in combined, (
            f"Expected 'componentDoesNotExist' in warning text; got: {result}"
        )

    def test_multiple_dangling_refs_in_one_control_each_produces_warning(self, mirror_fn):
        """
        A control referencing two missing component IDs produces warnings
        that mention both missing IDs.

        Given: controlX references [componentAlpha, componentMissingA, componentMissingB]
               where only componentAlpha is in component_ids
        When: check_controls_components_mirror() is called
        Then: The combined warning text mentions componentMissingA AND componentMissingB
        """
        controls = {
            "controlX": _make_control(
                "controlX",
                ["componentAlpha", "componentMissingA", "componentMissingB"],
            )
        }
        result = mirror_fn(controls, _VALID_COMPONENT_IDS)
        assert len(result) >= 1, f"Expected at least one warning; got: {result}"
        combined = " ".join(result)
        assert "componentMissingA" in combined, f"Expected 'componentMissingA' in warnings; got: {result}"
        assert "componentMissingB" in combined, f"Expected 'componentMissingB' in warnings; got: {result}"

    def test_multiple_controls_with_dangling_refs_each_appears_in_warnings(self, mirror_fn):
        """
        Each control with a dangling reference appears in the warning output.

        Given: controlP and controlQ each reference a missing component
        When: check_controls_components_mirror() is called
        Then: The combined warning text mentions controlP AND controlQ
        """
        controls = {
            "controlP": _make_control("controlP", ["componentMissingX"]),
            "controlQ": _make_control("controlQ", ["componentMissingY"]),
        }
        result = mirror_fn(controls, _VALID_COMPONENT_IDS)
        assert len(result) >= 1, f"Expected at least one warning; got: {result}"
        combined = " ".join(result)
        assert "controlP" in combined, f"Expected 'controlP' in warnings; got: {result}"
        assert "controlQ" in combined, f"Expected 'controlQ' in warnings; got: {result}"

    def test_escape_hatch_all_produces_no_warning(self, mirror_fn):
        """
        A control with components: ["all"] produces no warning.

        "all" is a documented escape hatch meaning the control applies to
        all components.  It must not be flagged as a missing component ID.

        Given: A control with components=["all"]
        When: check_controls_components_mirror() is called
        Then: Returns empty list
        """
        controls = {"controlAll": _make_control("controlAll", ["all"])}
        result = mirror_fn(controls, _VALID_COMPONENT_IDS)
        assert result == [], f"Expected no warning for escape hatch 'all'; got: {result}"

    def test_escape_hatch_none_produces_no_warning(self, mirror_fn):
        """
        A control with components: ["none"] produces no warning.

        "none" is a documented escape hatch meaning the control applies to
        no specific component.  It must not be flagged as a missing component ID.

        Given: A control with components=["none"]
        When: check_controls_components_mirror() is called
        Then: Returns empty list
        """
        controls = {"controlNone": _make_control("controlNone", ["none"])}
        result = mirror_fn(controls, _VALID_COMPONENT_IDS)
        assert result == [], f"Expected no warning for escape hatch 'none'; got: {result}"

    def test_empty_components_list_produces_no_warning(self, mirror_fn):
        """
        A control with an empty components list produces no warning.

        There is nothing to check; the function must not raise and must
        return an empty list.

        Given: A control with components=[]
        When: check_controls_components_mirror() is called
        Then: Returns empty list
        """
        controls = {"controlEmpty": _make_control("controlEmpty", [])}
        result = mirror_fn(controls, _VALID_COMPONENT_IDS)
        assert result == [], f"Expected no warning for empty components list; got: {result}"

    def test_empty_controls_dict_returns_empty_list(self, mirror_fn):
        """
        Passing an empty controls dict returns an empty list without raising.

        Given: controls={}
        When: check_controls_components_mirror() is called
        Then: Returns empty list
        """
        result = mirror_fn({}, _VALID_COMPONENT_IDS)
        assert result == [], f"Expected empty list for empty controls dict; got: {result}"

    def test_returns_list_type(self, mirror_fn):
        """
        The function always returns a list, never None.

        Given: Any valid input
        When: check_controls_components_mirror() is called
        Then: Return value is a list instance
        """
        result = mirror_fn({}, set())
        assert isinstance(result, list), f"Expected list; got {type(result)}"

    def test_each_warning_is_a_string(self, mirror_fn):
        """
        Every element in the returned warnings list is a str.

        Given: A controls dict with at least one dangling reference
        When: check_controls_components_mirror() is called
        Then: Every element in the returned list is a str instance
        """
        controls = {"controlBad": _make_control("controlBad", ["componentGhost"])}
        result = mirror_fn(controls, _VALID_COMPONENT_IDS)
        assert len(result) >= 1, "Expected at least one warning for this input"
        for item in result:
            assert isinstance(item, str), f"Expected str element; got {type(item)!r}: {item!r}"

    def test_valid_component_refs_not_flagged_as_missing(self, mirror_fn):
        """
        Component IDs that exist in component_ids do not appear as missing refs.

        Guards against false-positives: the function must only report IDs that
        are absent from component_ids.

        Given: A control referencing componentAlpha (present) and componentGhost (absent)
        When: check_controls_components_mirror() is called
        Then: "componentGhost" appears in the combined warning text;
              the warning count does not exceed the number of missing IDs (1)
        """
        controls = {"controlMixed": _make_control("controlMixed", ["componentAlpha", "componentGhost"])}
        result = mirror_fn(controls, _VALID_COMPONENT_IDS)
        assert len(result) >= 1, "Expected a warning for componentGhost"
        combined = " ".join(result)
        assert "componentGhost" in combined, f"Expected 'componentGhost' in warning text; got: {result}"
        # The valid reference must NOT appear in any warning text — guards
        # against a false-positive where every listed component (valid or not)
        # is flagged as missing.
        assert "componentAlpha" not in combined, (
            f"Expected 'componentAlpha' (valid ref) NOT in warning text; got: {result}"
        )

    def test_live_corpus_regression_produces_known_dangling_refs(self, mirror_fn):
        """
        Running against the actual controls.yaml + components.yaml surfaces
        the 3 known dangling references present as of 2026-05-04.

        Given: Parsed controls from risk-map/yaml/controls.yaml
               Parsed components from risk-map/yaml/components.yaml
        When: check_controls_components_mirror() is called
        Then: Warning count >= 3 AND warnings mention componentInputHandling
              AND warnings mention componentOutputHandling

        This is a live-corpus regression guard.  If the content debt is ever
        remediated (componentInputHandling → componentApplicationInputHandling,
        etc.), this test will need updating to reflect the new expected count.
        """
        from riskmap_validator.utils import parse_components_yaml, parse_controls_yaml

        components_path = _REPO_ROOT / "risk-map" / "yaml" / "components.yaml"
        controls_path = _REPO_ROOT / "risk-map" / "yaml" / "controls.yaml"

        components = parse_components_yaml(components_path)
        controls = parse_controls_yaml(controls_path)
        component_ids = set(components.keys())

        result = mirror_fn(controls, component_ids)

        assert len(result) >= 3, f"Expected >= 3 warnings for known dangling refs; got {len(result)}: {result}"
        combined = " ".join(result)
        assert "componentInputHandling" in combined, (
            f"Expected 'componentInputHandling' in warnings; got: {result}"
        )
        assert "componentOutputHandling" in combined, (
            f"Expected 'componentOutputHandling' in warnings; got: {result}"
        )


# ===========================================================================
# 2. CLI tests — --block toggle on validate_riskmap.py
#    These tests FAIL today with argparse exit 2 (red phase).
# ===========================================================================


class TestBlockToggleCLI:
    """End-to-end CLI tests for the --block flag on validate_riskmap.py.

    These tests fail in the red phase because --block does not yet exist on
    validate_riskmap.py's argparse.  argparse exits 2 for unrecognised args.

    Live-corpus tests use _REPO_ROOT as cwd.
    Synthesised-corpus tests build a minimal two-file corpus in tmp_path.
    """

    # -----------------------------------------------------------------------
    # Live corpus: the actual risk-map/yaml/ tree in the worktree.
    # Has 3 known dangling refs (componentInputHandling ×1, componentOutputHandling ×2).
    # -----------------------------------------------------------------------

    def test_live_corpus_no_block_flag_exits_0(self):
        """
        Running without --block against the live corpus exits 0.

        Warn-only default must not be broken by adding --block.  This is a
        regression guard: today validate_riskmap.py exits 0 on the live corpus.

        Given: The live risk-map/yaml/ corpus (3 dangling component refs)
        When: validate_riskmap.py --force --allow-isolated (no --block)
        Then: Exit code is 0
        """
        result = _run(_REPO_ROOT)
        assert result.returncode == 0, (
            f"Expected exit 0 without --block on live corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_live_corpus_with_block_flag_exits_1(self):
        """
        Running with --block against the live corpus exits 1 because the 3
        dangling component refs promote warnings to errors.

        Given: The live risk-map/yaml/ corpus (3 dangling component refs)
        When: validate_riskmap.py --force --allow-isolated --block
        Then: Exit code is 1 (mirror warnings promoted to failures)
        """
        result = _run(_REPO_ROOT, "--block")
        assert result.returncode == 1, (
            f"Expected exit 1 with --block on live corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_live_corpus_with_block_output_names_dangling_components(self):
        """
        When --block fires on the live corpus, the output text names the
        dangling component IDs so developers can locate the defects.

        Given: The live corpus and --block
        When: validate_riskmap.py --force --allow-isolated --block
        Then: Output (stdout or stderr) mentions at least one of
              componentInputHandling or componentOutputHandling
        """
        result = _run(_REPO_ROOT, "--block")
        combined = result.stdout + result.stderr
        mentions_known_dangling = any(cid in combined for cid in _LIVE_DANGLING_COMPONENT_IDS)
        assert mentions_known_dangling, (
            "Expected output to name at least one dangling component ID "
            f"({_LIVE_DANGLING_COMPONENT_IDS}); "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

    # -----------------------------------------------------------------------
    # Synthesised clean corpus: no dangling refs → --block must NOT fire.
    # -----------------------------------------------------------------------

    def test_clean_corpus_with_block_flag_exits_0(self, tmp_path):
        """
        Running with --block against a corpus with no dangling refs exits 0.

        The toggle must only promote warnings to failures when warnings
        actually exist; a clean corpus always exits 0.

        Given: A synthesised corpus where all controls reference components
               that exist in components.yaml
        When: validate_riskmap.py --force --allow-isolated --block (cwd=tmp_path)
        Then: Exit code is 0 (no mirror warnings to promote)
        """
        _write_corpus(tmp_path, _MINIMAL_COMPONENTS, _CLEAN_CONTROLS)
        result = _run(tmp_path, "--block")
        assert result.returncode == 0, (
            f"Expected exit 0 with --block on clean corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_clean_corpus_no_block_flag_exits_0(self, tmp_path):
        """
        Running without --block against a clean corpus exits 0.

        Baseline sanity check that the synthesised-corpus harness is correct.

        Given: A synthesised clean corpus
        When: validate_riskmap.py --force --allow-isolated (no --block)
        Then: Exit code is 0
        """
        _write_corpus(tmp_path, _MINIMAL_COMPONENTS, _CLEAN_CONTROLS)
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Expected exit 0 on clean corpus without --block; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    # -----------------------------------------------------------------------
    # Synthesised dirty corpus: dangling refs present.
    # -----------------------------------------------------------------------

    def test_dirty_corpus_with_block_flag_exits_1(self, tmp_path):
        """
        Running with --block against a synthesised dirty corpus exits 1.

        Cross-checks that the toggle fires on a synthetic corpus, not just
        the live one.

        Given: A synthesised corpus where controlDirty references
               componentDoesNotExist (absent from components.yaml)
        When: validate_riskmap.py --force --allow-isolated --block
        Then: Exit code is 1
        """
        _write_corpus(tmp_path, _MINIMAL_COMPONENTS, _DIRTY_CONTROLS)
        result = _run(tmp_path, "--block")
        assert result.returncode == 1, (
            f"Expected exit 1 with --block on dirty corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dirty_corpus_no_block_flag_exits_0(self, tmp_path):
        """
        Running WITHOUT --block against a dirty synthesised corpus exits 0.

        Confirms warn-only default behaviour is preserved even when dangling
        component refs exist.

        Given: A synthesised corpus where controlDirty references
               componentDoesNotExist (absent from components.yaml)
        When: validate_riskmap.py --force --allow-isolated (no --block)
        Then: Exit code is 0 (warnings only, no failure)
        """
        _write_corpus(tmp_path, _MINIMAL_COMPONENTS, _DIRTY_CONTROLS)
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Expected exit 0 without --block on dirty corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Warn-only must still emit the warning — exit-0 alone doesn't prove
        # the check ran. Without this assertion, a silent skip would pass.
        combined = result.stdout + result.stderr
        assert "componentDoesNotExist" in combined, (
            f"Expected warn output naming 'componentDoesNotExist' even without --block; "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

    def test_dirty_corpus_with_block_output_names_missing_component(self, tmp_path):
        """
        When --block fires, the output names the missing component ID.

        Given: A synthesised dirty corpus (componentDoesNotExist dangling)
        When: validate_riskmap.py --force --allow-isolated --block
        Then: Output mentions "componentDoesNotExist"
        """
        _write_corpus(tmp_path, _MINIMAL_COMPONENTS, _DIRTY_CONTROLS)
        result = _run(tmp_path, "--block")
        combined = result.stdout + result.stderr
        assert "componentDoesNotExist" in combined, (
            f"Expected 'componentDoesNotExist' in output; stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

    def test_escape_hatch_all_corpus_with_block_exits_0(self, tmp_path):
        """
        A corpus where all controls use the "all" escape hatch exits 0 with --block.

        The escape hatches must be respected end-to-end; the CLI must not
        flag "all" as a missing component.

        Given: A synthesised corpus where all controls use components: ["all"]
        When: validate_riskmap.py --force --allow-isolated --block
        Then: Exit code is 0
        """
        _write_corpus(tmp_path, _MINIMAL_COMPONENTS, _ESCAPE_ALL_CONTROLS)
        result = _run(tmp_path, "--block")
        assert result.returncode == 0, (
            f"Expected exit 0 with --block when controls use 'all' escape hatch; "
            f"got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    # -----------------------------------------------------------------------
    # Flag discovery: --help must list --block
    # -----------------------------------------------------------------------

    def test_help_output_contains_block_flag(self):
        """
        The --help output documents the --block flag.

        Given: The script is invoked with --help
        When: validate_riskmap.py --help
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
# Total tests: 22
#
# TestCheckControlsComponentsMirror  (12 tests — pure function)
#   — clean controls return empty list; single dangling ref names control +
#     component; multiple missing refs in one control both appear; multiple
#     controls each appear; escape "all" no warning; escape "none" no warning;
#     empty components list no warning; empty controls dict no warning; return
#     type is list; each element is str; valid refs not in warnings; live-corpus
#     regression (>=3 warnings, componentInputHandling + componentOutputHandling).
#
# TestBlockToggleCLI  (10 tests — subprocess CLI)
#   — live corpus + no --block -> exit 0 (regression guard);
#     live corpus + --block -> exit 1 (3 dangling refs fire the toggle);
#     live corpus + --block -> output names dangling component IDs;
#     clean synthesised corpus + --block -> exit 0;
#     clean synthesised corpus + no --block -> exit 0;
#     dirty synthesised corpus + --block -> exit 1;
#     dirty synthesised corpus + no --block -> exit 0 (warn-only preserved);
#     dirty corpus + --block -> output names missing component;
#     escape-hatch "all" corpus + --block -> exit 0;
#     --help output contains '--block'.
#
# Red-phase failure modes
#   - TestCheckControlsComponentsMirror: ImportError at collection time
#     (check_controls_components_mirror not yet defined in validator.py)
#   - TestBlockToggleCLI: argparse exit 2
#     ("unrecognised arguments: --block") for all tests that pass --block,
#     including --help (which today shows no --block flag in the output);
#     the no-block exit-code tests pass today (see note below).
#
# Tests that pass today (intentional)
#   - test_live_corpus_no_block_flag_exits_0: regression guard on existing
#     behaviour; validate_riskmap.py already exits 0 on the live corpus.
#   - test_clean_corpus_no_block_flag_exits_0: same reason.
#   - test_dirty_corpus_no_block_flag_exits_0: validate_riskmap.py exits 0
#     today because it does not yet run the mirror check at all.

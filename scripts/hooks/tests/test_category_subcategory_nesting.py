#!/usr/bin/env python3
"""
Tests for the category/subcategory nesting check (task 2.3.9 / issue #268).

Per ADR-018 D6: every component's `(category, subcategory)` pair must match
the file's `categories[].subcategory[]` declaration. The schema enforces
individual enum membership but NOT the nesting (e.g., a component declaring
`category: componentsModel, subcategory: componentsData` passes schema
today even though `componentsData` is nested under `componentsInfrastructure`).

The check ships warn-only and rides the SAME `--block` flag on
`validate_riskmap.py` that 2.3.8 introduced (no new flag).

Path A (orchestrator-pinned): emit warnings for BOTH classes.
  - Class 1 (mismatch): subcategory present + not nested under claimed category.
  - Class 2 (absent):   category present + subcategory missing.

Live corpus state (verified 2026-05-04):
  - 0 mismatched-nesting components (per ADR-018 D6, "no component has this
    drift today; the gap is a backstop class").
  - 7 components missing subcategory: componentDataStorage, componentModelStorage,
    componentModelServing, componentTheModel, componentApplication,
    componentApplicationOutputHandling, componentApplicationInputHandling.

Symbol contract
---------------
Pure-function tests import `check_category_subcategory_nesting` from
`riskmap_validator.validator`. SWE must expose a callable with that name.
Signature (SWE's call, but tests assume this shape):

    check_category_subcategory_nesting(
        components: dict[str, ComponentNode],
        category_to_subcategories: dict[str, set[str]],
    ) -> list[str]

`category_to_subcategories` maps each top-level category ID -> set of valid
subcategory IDs nested under it. Caller derives this from the YAML's
top-level `categories:` block.

Returns a list of human-readable warning strings; empty list when clean.

Test structure
--------------
1. TestCheckCategorySubcategoryNesting
   Pure-function tests on check_category_subcategory_nesting().
   FAIL today with ImportError (function not yet implemented).

2. TestNestingBlockToggleCLI
   Subprocess-based end-to-end tests on validate_riskmap.py reusing the
   --block flag from 2.3.8. The dirty-with-block test FAILS today because
   the nesting check is not yet wired into main(). The --help-shows-block
   test PASSES today (regression guard on 2.3.8's flag).
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# sys.path injection — same pattern as the mirror test
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

# Deferred import: check_category_subcategory_nesting does not exist yet.
# Re-raised inside the fixture so pure-function tests fail individually
# while CLI test collection succeeds.
try:
    from riskmap_validator.validator import check_category_subcategory_nesting  # noqa: E402

    _NESTING_IMPORT_ERROR: ImportError | None = None
except ImportError as _e:
    check_category_subcategory_nesting = None  # type: ignore[assignment]
    _NESTING_IMPORT_ERROR = _e

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# CLI script under test.
_SCRIPT = Path(__file__).parent.parent / "validate_riskmap.py"

# Repository root — used as cwd for live-corpus subprocess tests.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Known live-corpus components missing the `subcategory` field (2026-05-04).
_LIVE_MISSING_SUBCATEGORY_IDS: frozenset[str] = frozenset(
    {
        "componentDataStorage",
        "componentModelStorage",
        "componentModelServing",
        "componentTheModel",
        "componentApplication",
        "componentApplicationOutputHandling",
        "componentApplicationInputHandling",
    }
)

# Test-only nesting map — matches the exact live category declarations (verified 2026-05-04).
_NESTING_MAP: dict[str, set[str]] = {
    "componentsInfrastructure": {"componentsData"},
    "componentsModel": {"componentsModelTraining", "componentsOrchestration"},
    "componentsApplication": {"componentsAgent"},
}


# ---------------------------------------------------------------------------
# Fixture for deferred import
# ---------------------------------------------------------------------------


@pytest.fixture
def nesting_fn():
    """Return check_category_subcategory_nesting, or fail with ImportError.

    Lets the CLI test class collect and run independently of the function's
    presence.
    """
    if _NESTING_IMPORT_ERROR is not None:
        raise _NESTING_IMPORT_ERROR
    return check_category_subcategory_nesting


# ComponentNode construction is delegated to the shared `make_component`
# fixture in conftest.py; corpus writing and CLI invocation use
# `write_riskmap_corpus` and `run_validate_riskmap` from the same module.


# ---------------------------------------------------------------------------
# Synthesized-corpus harness for subprocess tests
# ---------------------------------------------------------------------------

# Components.yaml with valid nesting + clean components (no mismatches, all
# subcategories declared). One category ("componentsInfrastructure") has a
# nested subcategory; components reference it consistently.
_CLEAN_COMPONENTS: dict[str, Any] = {
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
        {
            "id": "componentsModel",
            "title": "Model",
            "subcategory": [
                {"id": "componentsModelTraining", "title": "Model Training"},
            ],
        },
    ],
}

# Components.yaml with a mismatched-nesting component: componentBad claims
# category=componentsModel, subcategory=componentsData (which is declared
# under componentsInfrastructure, not componentsModel).
_DIRTY_NESTING_COMPONENTS: dict[str, Any] = {
    "components": [
        {
            "id": "componentAlpha",
            "title": "Alpha",
            "category": "componentsInfrastructure",
            "subcategory": "componentsData",
            "edges": {"to": ["componentBad"], "from": []},
        },
        {
            "id": "componentBad",
            "title": "Bad Nesting",
            "category": "componentsModel",
            "subcategory": "componentsData",  # MISMATCH — under Infrastructure
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
        {
            "id": "componentsModel",
            "title": "Model",
            "subcategory": [
                {"id": "componentsModelTraining", "title": "Model Training"},
            ],
        },
    ],
}

# Clean controls — no dangling refs so the mirror check stays silent and
# only the nesting check produces output.
_CLEAN_CONTROLS: dict[str, Any] = {
    "controls": [
        {
            "id": "controlClean",
            "title": "Clean",
            "category": "controlsGovernance",
            "components": ["componentAlpha"],
            "risks": [],
            "personas": [],
        }
    ]
}


# ===========================================================================
# 1. Pure-function tests — check_category_subcategory_nesting()
# ===========================================================================


class TestCheckCategorySubcategoryNesting:
    """Pure-function tests for check_category_subcategory_nesting().

    Path A: emit warnings for both mismatched nesting (Class 1) and absent
    subcategory (Class 2). All tests use module-level _NESTING_MAP plus
    custom ComponentNode dicts.
    """

    def test_clean_components_return_empty_list(self, nesting_fn, make_component):
        """
        Given: components with consistent (category, subcategory) pairs
        When: check_category_subcategory_nesting() is called
        Then: returns an empty list
        """
        components = {
            "componentX": make_component("X", "componentsInfrastructure", "componentsData"),
            "componentY": make_component("Y", "componentsModel", "componentsModelTraining"),
        }
        result = nesting_fn(components, _NESTING_MAP)
        assert result == [], f"Expected no warnings on clean input; got: {result}"

    def test_class1_mismatched_nesting_produces_warning_naming_component_and_subcategory(
        self, nesting_fn, make_component
    ):
        """
        Given: a component claims category=componentsModel, subcategory=componentsData
               (componentsData is nested under componentsInfrastructure, not Model)
        When: check_category_subcategory_nesting() is called
        Then: 1 warning naming the component ID, the claimed category, and the
              orphan subcategory
        """
        components = {
            "componentMismatch": make_component("Mismatch", "componentsModel", "componentsData"),
        }
        result = nesting_fn(components, _NESTING_MAP)
        assert len(result) >= 1, f"Expected ≥1 warning for mismatched nesting; got: {result}"
        combined = " ".join(result)
        assert "componentMismatch" in combined, f"Expected 'componentMismatch' in warning text; got: {result}"
        assert "componentsData" in combined, (
            f"Expected 'componentsData' (orphan subcategory) in warning text; got: {result}"
        )

    def test_class1_multiple_mismatches_each_surfaces_independently(self, nesting_fn, make_component):
        """
        Given: two components with different mismatch pairs
        When: check_category_subcategory_nesting() is called
        Then: both component IDs appear in the combined warning text
        """
        components = {
            "componentBad1": make_component("Bad1", "componentsModel", "componentsData"),
            "componentBad2": make_component("Bad2", "componentsApplication", "componentsModelTraining"),
        }
        result = nesting_fn(components, _NESTING_MAP)
        combined = " ".join(result)
        assert "componentBad1" in combined, f"Expected 'componentBad1'; got: {result}"
        assert "componentBad2" in combined, f"Expected 'componentBad2'; got: {result}"

    def test_class2_absent_subcategory_produces_warning(self, nesting_fn, make_component):
        """
        Given: a component with category but no subcategory (absent)
        When: check_category_subcategory_nesting() is called
        Then: 1 warning naming the component ID and the claimed category
              (Path A: schema permits absence, but the validator surfaces it)
        """
        components = {
            "componentMissing": make_component("Missing", "componentsModel", subcategory=None),
        }
        result = nesting_fn(components, _NESTING_MAP)
        assert len(result) >= 1, f"Expected ≥1 warning for absent subcategory; got: {result}"
        combined = " ".join(result)
        assert "componentMissing" in combined, f"Expected 'componentMissing' in warning text; got: {result}"

    def test_mixed_class1_and_class2_both_surfaced(self, nesting_fn, make_component):
        """
        Given: one Class-1 mismatch + one Class-2 absence in the same input
        When: check_category_subcategory_nesting() is called
        Then: both offending component IDs appear in the combined output
        """
        components = {
            "componentMismatchCase": make_component("Mismatch", "componentsModel", "componentsData"),
            "componentAbsentCase": make_component("Absent", "componentsApplication", subcategory=None),
        }
        result = nesting_fn(components, _NESTING_MAP)
        combined = " ".join(result)
        assert "componentMismatchCase" in combined, f"Expected mismatch case in warning; got: {result}"
        assert "componentAbsentCase" in combined, f"Expected absent case in warning; got: {result}"

    def test_empty_components_dict_returns_empty_list(self, nesting_fn):
        """
        Given: an empty components dict
        When: check_category_subcategory_nesting() is called
        Then: empty list (nothing to check)
        """
        result = nesting_fn({}, _NESTING_MAP)
        assert result == [], f"Expected empty list on empty input; got: {result}"

    def test_returns_list_type(self, nesting_fn):
        """
        Given: any input
        When: check_category_subcategory_nesting() is called
        Then: returns a list (never None or other type)
        """
        result = nesting_fn({}, _NESTING_MAP)
        assert isinstance(result, list), f"Expected list, got {type(result)}: {result}"

    def test_each_warning_is_a_string(self, nesting_fn, make_component):
        """
        Given: a dirty input that produces warnings
        When: check_category_subcategory_nesting() is called
        Then: every element of the returned list is a str
        """
        components = {
            "componentBad": make_component("Bad", "componentsModel", "componentsData"),
        }
        result = nesting_fn(components, _NESTING_MAP)
        assert all(isinstance(w, str) for w in result), (
            f"Expected all-str warnings; got types: {[type(w) for w in result]}"
        )

    def test_unknown_category_in_component_produces_warning(self, nesting_fn, make_component):
        """
        Given: a component claims a category absent from the nesting map
        When: check_category_subcategory_nesting() is called
        Then: 1 warning naming the component (the nesting check builds its map
              from the YAML categories block; a category not present there has
              no valid subcategories and always mismatches)
        """
        components = {
            "componentUnknownCat": make_component("UnknownCat", "componentsDoesNotExist", "componentsData"),
        }
        result = nesting_fn(components, _NESTING_MAP)
        assert len(result) >= 1, f"Expected ≥1 warning when category is absent from nesting map; got: {result}"
        combined = " ".join(result)
        assert "componentUnknownCat" in combined, f"Expected component ID in warning; got: {result}"

    def test_live_corpus_regression_surfaces_known_missing_subcategory(self, nesting_fn):
        """
        Given: the actual risk-map/yaml/components.yaml on disk
        When: check_category_subcategory_nesting() is called against parsed input
        Then: returns exactly 7 warnings, and every known missing-subcategory component ID
              appears in the combined output

        The 7 known missing IDs are listed in _LIVE_MISSING_SUBCATEGORY_IDS (as of 2026-05-04).
        This assertion is intentionally exact (==, not >=) to guard BOTH directions of drift:
        - cleanup reduces the count below 7 → fail (update the expected count + ID list)
        - new content debt increases the count above 7 → fail (track the new defect)
        Update this test and _LIVE_MISSING_SUBCATEGORY_IDS whenever the corpus changes.
        """
        from riskmap_validator.utils import parse_components_yaml  # noqa: E402

        components_path = _REPO_ROOT / "risk-map" / "yaml" / "components.yaml"
        components = parse_components_yaml(components_path)

        # Build the nesting map from the YAML's top-level categories block.
        with open(components_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        nesting_map: dict[str, set[str]] = {}
        for cat in data.get("categories", []):
            cat_id = cat.get("id")
            if not isinstance(cat_id, str):
                continue
            sub_ids = {sub.get("id") for sub in cat.get("subcategory", []) if isinstance(sub.get("id"), str)}
            nesting_map[cat_id] = sub_ids

        result = nesting_fn(components, nesting_map)
        assert len(result) == 7, (
            "Expected exactly 7 warnings (the 7 known missing-subcategory components as of 2026-05-04). "
            "If the corpus drifted (cleanup OR new defects), update this test and "
            f"_LIVE_MISSING_SUBCATEGORY_IDS. Got {len(result)}: {result}"
        )
        combined = " ".join(result)
        for component_id in _LIVE_MISSING_SUBCATEGORY_IDS:
            assert component_id in combined, (
                f"Expected '{component_id}' (known missing-subcategory case) in warning text; got: {result}"
            )


# ===========================================================================
# 2. Subprocess CLI tests — validate_riskmap.py --block (reuses 2.3.8 flag)
# ===========================================================================


class TestNestingBlockToggleCLI:
    """End-to-end tests on validate_riskmap.py for the nesting check.

    Reuses the --block flag introduced by task 2.3.8. The dirty-with-block
    cases FAIL today because the nesting check is not yet wired into main().
    The clean and no-block cases PASS today (regression guards).
    """

    def test_live_corpus_no_block_flag_exits_0(self, run_validate_riskmap):
        """
        Given: actual repo as cwd, no --block
        When: validate_riskmap.py --force --allow-isolated runs
        Then: exit 0 (warnings printed but don't fail; today's behavior)
        """
        result = run_validate_riskmap(_REPO_ROOT)
        assert result.returncode == 0, (
            f"Expected exit 0 without --block on live corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_live_corpus_with_block_flag_exits_1(self, run_validate_riskmap):
        """
        Given: actual repo as cwd, --block
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 1 (combined nesting + mirror warnings fire the toggle;
              7 missing subcategories + 3 mirror dangle ≥ 10 total)

        Today (pre-2.3.9) exit 1 comes from the 3 mirror-dangle warnings from
        task 2.3.8. After 2.3.9 is wired, both the nesting warnings and the
        mirror warnings contribute.
        """
        result = run_validate_riskmap(_REPO_ROOT, "--block")
        assert result.returncode == 1, (
            f"Expected exit 1 with --block on live corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert any(cid in combined for cid in _LIVE_MISSING_SUBCATEGORY_IDS), (
            f"Expected output to name at least one known missing-subcategory ID; "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

    def test_clean_corpus_with_block_exits_0(self, tmp_path, write_riskmap_corpus, run_validate_riskmap):
        """
        Given: synthesised corpus with consistent nesting + clean controls
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 0 (no warnings to promote)
        """
        write_riskmap_corpus(tmp_path, _CLEAN_COMPONENTS, _CLEAN_CONTROLS)
        result = run_validate_riskmap(tmp_path, "--block")
        assert result.returncode == 0, (
            f"Expected exit 0 with --block on clean corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dirty_nesting_with_block_exits_1(self, tmp_path, write_riskmap_corpus, run_validate_riskmap):
        """
        Given: synthesised corpus with mismatched nesting (componentBad) + clean controls
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 1 (nesting warning fires the toggle; mirror stays silent)
        """
        write_riskmap_corpus(tmp_path, _DIRTY_NESTING_COMPONENTS, _CLEAN_CONTROLS)
        result = run_validate_riskmap(tmp_path, "--block")
        assert result.returncode == 1, (
            f"Expected exit 1 with --block on dirty-nesting corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dirty_nesting_no_block_flag_exits_0_and_emits_warning(
        self, tmp_path, write_riskmap_corpus, run_validate_riskmap
    ):
        """
        Given: synthesised dirty-nesting corpus, no --block
        When: validate_riskmap.py --force --allow-isolated runs
        Then: exit 0 (warn-only preserved) AND output names the offending component
        """
        write_riskmap_corpus(tmp_path, _DIRTY_NESTING_COMPONENTS, _CLEAN_CONTROLS)
        result = run_validate_riskmap(tmp_path)
        assert result.returncode == 0, (
            f"Expected exit 0 without --block on dirty-nesting corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Without this assertion a silent skip would also pass exit-code-only.
        combined = result.stdout + result.stderr
        assert "componentBad" in combined, (
            f"Expected warn output naming 'componentBad' even without --block; "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

    def test_help_output_contains_block_flag(self):
        """
        Given: --help output
        When: validate_riskmap.py --help runs
        Then: --block is documented (regression guard on 2.3.8's flag wiring;
              must continue to be documented after 2.3.9 wires the second consumer)
        """
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--help"],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        combined = result.stdout + result.stderr
        assert "--block" in combined, f"Expected --block in --help output; got:\n{combined}"


# ===========================================================================
# Test Summary
# ===========================================================================
# Total tests: 16
#
# TestCheckCategorySubcategoryNesting (10 tests)
#   — clean → empty list; class-1 mismatch → warning naming component +
#     orphan subcategory; multiple class-1 mismatches; class-2 absence →
#     warning naming component; mixed class-1 + class-2; empty dict;
#     return type list; each element str; unknown category produces warning;
#     live-corpus regression surfaces known 7 missing IDs.
#
# TestNestingBlockToggleCLI (6 tests)
#   — live + no --block → exit 0; live + --block → exit 1;
#     clean synthesised + --block → exit 0; dirty nesting + --block → exit 1;
#     dirty nesting + no --block → exit 0 + warning emitted;
#     --help still documents --block (regression guard).
#
# Red-phase failure modes
#   - TestCheckCategorySubcategoryNesting: ImportError at fixture setup
#     (check_category_subcategory_nesting not yet defined).
#   - TestNestingBlockToggleCLI: dirty-with-block + dirty-no-block-emits-warning
#     fail because the nesting check is not yet wired into main().
#     live-no-block, clean-with-block, live-with-block (already exits 1
#     because of mirror's 3 dangling refs after task 2.3.8 — passing for
#     compatible reason), and --help (already passes after 2.3.8) pass today.

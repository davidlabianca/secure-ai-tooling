#!/usr/bin/env python3
"""
Tests for a new real-corpus CI guard: category styling + persona ownership.

ADR-030 (docs/adr/030-agentic-component-model.md), Consequences:

  "mermaid-styles.yaml needs a componentsTools style or the new category
  renders unstyled; a real-corpus guard should fail CI on a styleless
  category."

  "The fourth category needs a persona owner. Per ADR-021, a Tools category
  with no responsible persona is orphaned in the responsibility model;
  persona mappings and the persona-site must place it."

And "Migration sequencing" step 4 (Consumer wiring, fail-loud): "...tests —
including a real-corpus guard so an unstyled or owner-less category fails CI
rather than rendering silently."

This is a NEW check — no equivalent exists today. The repo has no formal
"persona owns a component category" schema field (verified 2026-07-17: no
such relationship exists in personas.schema.json or components.schema.json).
Ownership is therefore DERIVED from the existing controls↔components↔personas
graph: a category is "owned" if at least one control (a) references a
SPECIFIC component in that category — directly by id — AND (b) declares at
least one persona. This is a conservative, defensible reading using only data
that already exists; it requires no new schema field.

The "all" escape hatch does NOT confer ownership. Permanent universal
governance controls (controlRedTeaming, controlVulnerabilityManagement,
controlThreatDetection, controlIncidentResponseManagement, ...) use
components: ['all'] and carry non-empty personas; if 'all' counted toward
ownership, every category — present and future, real or fictional — would be
trivially "owned" by these controls regardless of whether it has any actual
category-specific persona responsibility, making the ownership warning class
structurally incapable of ever firing against the real corpus. This is
distinct from check_controls_components_mirror's (ADR-020 D7) use of 'all' as
an escape hatch: that check answers "is this control's component reference
dangling?", where universality is correct semantics. Ownership answers a
different question — "does a persona own this category specifically?" — and
reusing the same escape hatch there would conflate referential validity with
responsibility assignment.

Verified 2026-07-17: on the CURRENT (pre-ADR-030) live corpus, all 3 existing
categories are both styled and owned this way, each via multiple controls
that name specific (non-'all') components in the category with non-empty
personas — not merely via the 'all' loophole. componentTools' controls
(controlAgentPluginPermissions et al.) all declare non-empty personas
(personaAgenticProvider, personaPlatformProvider, ...) and name componentTools
directly (not via 'all'), so once componentTools is recategorized into
componentsTools per D1, componentsTools inherits an owner "for free" through
the SAME control mappings — no new content-authoring step is required for D1
to pass this guard, matching the ADR's own note that "the Agentic Platform /
tool-provider persona is the candidate owner."

Symbol contract
----------------
Pure-function tests import `check_category_style_and_ownership` from
`riskmap_validator.validator`. SWE must expose a callable with this name and
signature:

    check_category_style_and_ownership(
        schema_categories: set[str],
        styled_categories: set[str],
        components: dict[str, ComponentNode],
        controls: dict[str, ControlNode],
    ) -> list[str]

Two independent warning classes, both keyed by category id (do not conflate
into one message per category — a category can be missing one, the other, or
both, and CI output should let a reader triage them separately):

  Class STYLE: `cat in schema_categories` and `cat not in styled_categories`.
  Class OWNERSHIP: `cat in schema_categories` and no control satisfies
    (references a component whose `.category == cat`, by id — the "all"
    escape hatch does NOT count) AND (`control.personas` is non-empty).

Returns a list of human-readable warning strings; empty when every schema
category is both styled and owned. Order is not asserted by these tests.

CLI wiring: validate_riskmap.py should run this as a warn-only check
following the existing controls↔components-mirror / category-subcategory-
nesting pattern (same --block promotion, same print-label convention). Tests
below assert on a label containing "Category style" and "ownership" appearing
in stdout — see TestCLIWiring for the exact substrings asserted.

Test structure
--------------
1. TestCheckCategoryStyleAndOwnership — pure-function tests. FAIL today with
   ImportError (function not yet implemented).
2. TestCLIWiring — subprocess end-to-end tests against validate_riskmap.py.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from riskmap_validator.validator import check_category_style_and_ownership  # noqa: E402

    _OWNERSHIP_IMPORT_ERROR: ImportError | None = None
except ImportError as _e:
    check_category_style_and_ownership = None  # type: ignore[assignment]
    _OWNERSHIP_IMPORT_ERROR = _e

_SCRIPT = Path(__file__).parent.parent / "validate_riskmap.py"
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


@pytest.fixture
def ownership_fn():
    """Return check_category_style_and_ownership, or raise ImportError."""
    if _OWNERSHIP_IMPORT_ERROR is not None:
        raise _OWNERSHIP_IMPORT_ERROR
    return check_category_style_and_ownership


# ===========================================================================
# 1. Pure-function tests
# ===========================================================================


class TestCheckCategoryStyleAndOwnership:
    """Pure-function tests for check_category_style_and_ownership()."""

    def test_clean_all_styled_and_owned_returns_empty_list(self, ownership_fn, make_component):
        """
        Given: 1 category, styled, with a component referenced by a control
               that declares a persona
        When: check_category_style_and_ownership() is called
        Then: returns []
        """
        components = {"compA": make_component("A", "componentsData")}
        from riskmap_validator.models import ControlNode

        controls = {
            "ctrlA": ControlNode(
                title="Ctrl A", category="controlsData", components=["compA"], risks=[], personas=["personaX"]
            )
        }
        result = ownership_fn({"componentsData"}, {"componentsData"}, components, controls)
        assert result == [], f"Expected no warnings on clean input; got: {result}"

    def test_missing_style_only_produces_style_warning(self, ownership_fn, make_component):
        """
        Given: a category that IS owned but has NO styling entry
        When: check_category_style_and_ownership() is called
        Then: exactly one warning naming the category, mentioning styling
        """
        components = {"compA": make_component("A", "componentsData")}
        from riskmap_validator.models import ControlNode

        controls = {
            "ctrlA": ControlNode(
                title="Ctrl A", category="controlsData", components=["compA"], risks=[], personas=["personaX"]
            )
        }
        result = ownership_fn({"componentsData"}, set(), components, controls)
        assert len(result) == 1, f"Expected exactly 1 warning (style only); got: {result}"
        assert "componentsData" in result[0]
        assert "styl" in result[0].lower(), f"Expected warning to mention styling; got: {result[0]!r}"

    def test_missing_ownership_only_produces_ownership_warning(self, ownership_fn, make_component):
        """
        Given: a category that IS styled but has NO owning control (no
               control references any of its components with a non-empty
               personas list)
        When: check_category_style_and_ownership() is called
        Then: exactly one warning naming the category, mentioning
              persona/owner
        """
        components = {"compA": make_component("A", "componentsData")}
        controls: dict = {}
        result = ownership_fn({"componentsData"}, {"componentsData"}, components, controls)
        assert len(result) == 1, f"Expected exactly 1 warning (ownership only); got: {result}"
        assert "componentsData" in result[0]
        combined_lower = result[0].lower()
        assert "persona" in combined_lower or "owner" in combined_lower, (
            f"Expected warning to mention persona/ownership; got: {result[0]!r}"
        )

    def test_missing_both_produces_two_warnings(self, ownership_fn, make_component):
        """
        Given: a category with neither a style entry nor an owning control
        When: check_category_style_and_ownership() is called
        Then: 2 independent warnings — style is NOT conflated with ownership
        """
        components = {"compA": make_component("A", "componentsData")}
        controls: dict = {}
        result = ownership_fn({"componentsData"}, set(), components, controls)
        assert len(result) == 2, (
            f"Expected 2 independent warnings (style + ownership), not one conflated "
            f"message; got {len(result)}: {result}"
        )

    def test_category_with_no_components_is_ownerless(self, ownership_fn):
        """
        Given: a schema category with zero components assigned to it
        When: check_category_style_and_ownership() is called
        Then: an ownership warning fires (nothing to be owned via)
        """
        result = ownership_fn({"componentsEmpty"}, {"componentsEmpty"}, {}, {})
        assert len(result) == 1
        assert "componentsEmpty" in result[0]

    def test_control_with_empty_personas_does_not_confer_ownership(self, ownership_fn, make_component):
        """
        Given: a control references the category's component but declares
               personas=[] (no responsible persona)
        When: check_category_style_and_ownership() is called
        Then: an ownership warning still fires — a control mapping without a
              persona does not establish ownership
        """
        components = {"compA": make_component("A", "componentsData")}
        from riskmap_validator.models import ControlNode

        controls = {
            "ctrlA": ControlNode(
                title="Ctrl A", category="controlsData", components=["compA"], risks=[], personas=[]
            )
        }
        result = ownership_fn({"componentsData"}, {"componentsData"}, components, controls)
        assert len(result) == 1, f"Expected ownership warning (empty personas); got: {result}"
        assert "componentsData" in result[0]

    def test_second_control_with_personas_rescues_ownership(self, ownership_fn, make_component):
        """
        Given: two controls reference the same component — one with
               personas=[], one with personas=['personaX']
        When: check_category_style_and_ownership() is called
        Then: no ownership warning — at least ONE owning control is enough
        """
        components = {"compA": make_component("A", "componentsData")}
        from riskmap_validator.models import ControlNode

        controls = {
            "ctrlBare": ControlNode(
                title="Bare", category="controlsData", components=["compA"], risks=[], personas=[]
            ),
            "ctrlOwned": ControlNode(
                title="Owned", category="controlsData", components=["compA"], risks=[], personas=["personaX"]
            ),
        }
        result = ownership_fn({"componentsData"}, {"componentsData"}, components, controls)
        assert result == [], f"Expected no warnings (one owning control is sufficient); got: {result}"

    def test_all_escape_hatch_does_not_confer_ownership(self, ownership_fn, make_component):
        """
        Given: two categories, each with a component, and ONLY a control
               with components=['all'] and a non-empty personas list — no
               control names a specific component in either category
        When: check_category_style_and_ownership() is called
        Then: an ownership warning fires for BOTH categories — 'all' is a
              universal governance escape hatch (see e.g. controlRedTeaming,
              controlVulnerabilityManagement, controlThreatDetection,
              controlIncidentResponseManagement in the live corpus, all
              components=['all'] with non-empty personas) and must NOT count
              toward category-specific ownership. Counting it would make the
              ownership warning class structurally incapable of ever firing,
              since a universal control satisfies it for every category,
              present and future, regardless of real persona responsibility.
              This is deliberately narrower than
              check_controls_components_mirror (ADR-020 D7), which treats
              'all' as a valid escape hatch for a different question (is this
              control's component reference dangling?) where universality is
              correct semantics; ownership answers "does a persona own this
              category specifically?" and must not conflate the two.
        """
        components = {
            "compA": make_component("A", "componentsData"),
            "compB": make_component("B", "componentsAgent"),
        }
        from riskmap_validator.models import ControlNode

        controls = {
            "ctrlAll": ControlNode(
                title="Universal",
                category="controlsGovernance",
                components=["all"],
                risks=[],
                personas=["personaX"],
            )
        }
        result = ownership_fn(
            {"componentsData", "componentsAgent"}, {"componentsData", "componentsAgent"}, components, controls
        )
        assert len(result) == 2, (
            f"Expected an ownership warning for BOTH categories since 'all' does not "
            f"confer category-specific ownership; got {len(result)}: {result}"
        )
        combined = " ".join(result)
        assert "componentsData" in combined
        assert "componentsAgent" in combined

    def test_multiple_categories_evaluated_independently(self, ownership_fn, make_component):
        """
        Given: 3 categories — one clean, one missing style, one missing
               ownership
        When: check_category_style_and_ownership() is called
        Then: exactly the 2 dirty categories are named in the output; the
              clean one is not mentioned
        """
        from riskmap_validator.models import ControlNode

        components = {
            "compClean": make_component("Clean", "componentsClean"),
            "compNoStyle": make_component("NoStyle", "componentsNoStyle"),
            "compNoOwner": make_component("NoOwner", "componentsNoOwner"),
        }
        controls = {
            "ctrlClean": ControlNode(
                title="Clean", category="controlsX", components=["compClean"], risks=[], personas=["personaX"]
            ),
            "ctrlNoStyle": ControlNode(
                title="NoStyle", category="controlsX", components=["compNoStyle"], risks=[], personas=["personaX"]
            ),
        }
        schema_categories = {"componentsClean", "componentsNoStyle", "componentsNoOwner"}
        styled_categories = {"componentsClean", "componentsNoOwner"}
        result = ownership_fn(schema_categories, styled_categories, components, controls)

        combined = " ".join(result)
        assert "componentsClean" not in combined, f"Clean category should not be warned about; got: {result}"
        assert "componentsNoStyle" in combined, f"Expected componentsNoStyle warning; got: {result}"
        assert "componentsNoOwner" in combined, f"Expected componentsNoOwner warning; got: {result}"

    def test_empty_schema_categories_returns_empty_list(self, ownership_fn):
        """
        Given: schema_categories = set()
        When: check_category_style_and_ownership() is called
        Then: returns [] (nothing to check)
        """
        result = ownership_fn(set(), set(), {}, {})
        assert result == [], f"Expected empty list for empty schema_categories; got: {result}"

    def test_return_type_is_list_of_str(self, ownership_fn, make_component):
        """
        Given: a dirty input
        When: check_category_style_and_ownership() is called
        Then: returns a list, and every element is a str
        """
        components = {"compA": make_component("A", "componentsData")}
        result = ownership_fn({"componentsData"}, set(), components, {})
        assert isinstance(result, list)
        assert all(isinstance(w, str) for w in result)

    def test_live_corpus_today_all_three_categories_clean(self, ownership_fn):
        """
        Given: the REAL components.schema.json category enum, the REAL
               mermaid-styles.yaml styled-category keys, and the REAL
               components.yaml / controls.yaml parsed
        When: check_category_style_and_ownership() is called
        Then: returns [] — verified 2026-07-17, all 3 pre-ADR-030 categories
              are both styled and owned today

        Forward guard: once ADR-030 D1 lands (componentsTools added to the
        schema enum, styled in mermaid-styles.yaml, and componentTools'
        existing controls carry it along), this test's inputs pick up the
        4th category automatically — no edit to this test is needed — and it
        continues to assert [] as the CI guard's steady state.
        """
        import json

        from riskmap_validator.graphing.graph_utils import MermaidConfigLoader
        from riskmap_validator.utils import parse_components_yaml, parse_controls_yaml

        schema_path = _REPO_ROOT / "risk-map" / "schemas" / "components.schema.json"
        styles_path = _REPO_ROOT / "risk-map" / "yaml" / "mermaid-styles.yaml"
        components_path = _REPO_ROOT / "risk-map" / "yaml" / "components.yaml"
        controls_path = _REPO_ROOT / "risk-map" / "yaml" / "controls.yaml"

        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        schema_categories = set(schema["definitions"]["category"]["properties"]["id"]["enum"])

        loader = MermaidConfigLoader(styles_path)
        styled_categories = set(loader.get_component_category_styles().keys())

        components = parse_components_yaml(components_path)
        controls = parse_controls_yaml(controls_path)

        result = ownership_fn(schema_categories, styled_categories, components, controls)
        assert result == [], f"Expected 0 warnings on the live corpus; got {len(result)}: {result}"


# ===========================================================================
# 2. Subprocess CLI tests — validate_riskmap.py wiring
# ===========================================================================


def _write_corpus(
    base: Path,
    components: dict[str, Any],
    controls: dict[str, Any],
    mermaid_styles: dict[str, Any],
) -> Path:
    """Write a 4-file synthetic corpus: components/controls/risks/mermaid-styles."""
    yaml_dir = base / "risk-map" / "yaml"
    yaml_dir.mkdir(parents=True, exist_ok=True)
    (yaml_dir / "components.yaml").write_text(yaml.dump(components), encoding="utf-8")
    (yaml_dir / "controls.yaml").write_text(yaml.dump(controls), encoding="utf-8")
    (yaml_dir / "risks.yaml").write_text(yaml.dump({"risks": []}), encoding="utf-8")
    (yaml_dir / "mermaid-styles.yaml").write_text(yaml.dump(mermaid_styles), encoding="utf-8")
    return base


def _run(cwd: Path, *extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--force", "--allow-isolated", *extra_args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


# Minimal components covering the 3 REAL (pre-ADR-030) top-level categories.
# No edges needed — CLI tests always pass --allow-isolated. Each component
# declares a subcategory nested consistently under its category in the
# categories: block below, so the pre-existing category/subcategory nesting
# check (ADR-018 D6) stays silent and only this module's ownership/style
# check produces output.
_THREE_CATEGORY_COMPONENTS: dict[str, Any] = {
    "components": [
        {
            "id": "compInfra",
            "title": "Infra",
            "category": "componentsInfrastructure",
            "subcategory": "componentsData",
            "edges": {},
        },
        {
            "id": "compModel",
            "title": "Model",
            "category": "componentsModel",
            "subcategory": "componentsModelTraining",
            "edges": {},
        },
        {
            "id": "compApp",
            "title": "App",
            "category": "componentsApplication",
            "subcategory": "componentsAgent",
            "edges": {},
        },
    ],
    "categories": [
        {
            "id": "componentsInfrastructure",
            "title": "Infrastructure",
            "subcategory": [{"id": "componentsData", "title": "Data"}],
        },
        {
            "id": "componentsModel",
            "title": "Model",
            "subcategory": [{"id": "componentsModelTraining", "title": "Model Training"}],
        },
        {
            "id": "componentsApplication",
            "title": "Application",
            "subcategory": [{"id": "componentsAgent", "title": "Agent"}],
        },
    ],
}

# Controls giving every one of the 3 categories an owning persona.
_THREE_CATEGORY_CONTROLS_ALL_OWNED: dict[str, Any] = {
    "controls": [
        {
            "id": "ctrlInfra",
            "title": "Infra Ctrl",
            "category": "controlsInfrastructure",
            "components": ["compInfra"],
            "risks": [],
            "personas": ["personaX"],
        },
        {
            "id": "ctrlModel",
            "title": "Model Ctrl",
            "category": "controlsModel",
            "components": ["compModel"],
            "risks": [],
            "personas": ["personaX"],
        },
        {
            "id": "ctrlApp",
            "title": "App Ctrl",
            "category": "controlsApplication",
            "components": ["compApp"],
            "risks": [],
            "personas": ["personaX"],
        },
    ]
}

# Same as above but componentsModel has no owning control (personas omitted
# entirely for that category).
_THREE_CATEGORY_CONTROLS_MODEL_UNOWNED: dict[str, Any] = {
    "controls": [
        _THREE_CATEGORY_CONTROLS_ALL_OWNED["controls"][0],
        _THREE_CATEGORY_CONTROLS_ALL_OWNED["controls"][2],
    ]
}

_FULLY_STYLED_MERMAID: dict[str, Any] = {
    "version": "1.0.0",
    "foundation": {"colors": {}, "strokeWidths": {}, "strokePatterns": {}},
    "sharedElements": {
        "cssClasses": {"hidden": "display: none;", "allControl": "stroke:#000,stroke-width:1px"},
        "componentCategories": {
            "componentsInfrastructure": {"fill": "#e6f3e6", "stroke": "#333333", "strokeWidth": "2px"},
            "componentsModel": {"fill": "#ffe6e6", "stroke": "#333333", "strokeWidth": "2px"},
            "componentsApplication": {"fill": "#e6f0ff", "stroke": "#333333", "strokeWidth": "2px"},
        },
    },
    "graphTypes": {
        "component": {"direction": "TD", "flowchartConfig": {}},
        "control": {"direction": "LR", "flowchartConfig": {}},
        "risk": {"direction": "LR", "flowchartConfig": {}},
    },
}

# Same, but missing the componentsModel style entry.
_MODEL_UNSTYLED_MERMAID: dict[str, Any] = {
    **_FULLY_STYLED_MERMAID,
    "sharedElements": {
        "cssClasses": _FULLY_STYLED_MERMAID["sharedElements"]["cssClasses"],
        "componentCategories": {
            "componentsInfrastructure": {"fill": "#e6f3e6", "stroke": "#333333", "strokeWidth": "2px"},
            "componentsApplication": {"fill": "#e6f0ff", "stroke": "#333333", "strokeWidth": "2px"},
        },
    },
}


class TestCLIWiring:
    """
    End-to-end tests on validate_riskmap.py.

    Note: the schema-category set the CLI derives this check's inputs from
    is read from the REAL, repo-relative risk-map/schemas/components.schema.json
    (via riskmap_validator.graphing.graph_utils._get_schema_categories(), which
    resolves the schema path relative to its own module location, not cwd —
    see that module's docstring). Synthetic tmp-cwd corpora below therefore
    use the 3 REAL pre-ADR-030 category ids, not fictional ones; only
    mermaid-styles.yaml (cwd-relative, per riskmap_validator.config) and
    components.yaml/controls.yaml (also cwd-relative) are actually synthetic.
    """

    def test_dirty_style_with_block_exits_1(self, tmp_path):
        """
        Given: synthetic corpus, all 3 categories owned, but componentsModel
               missing its mermaid-styles.yaml entry
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 1 (style warning promoted to error)
        """
        _write_corpus(
            tmp_path, _THREE_CATEGORY_COMPONENTS, _THREE_CATEGORY_CONTROLS_ALL_OWNED, _MODEL_UNSTYLED_MERMAID
        )
        result = _run(tmp_path, "--block")
        assert result.returncode == 1, (
            f"Expected exit 1 with --block on style-dirty corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dirty_ownership_with_block_exits_1(self, tmp_path):
        """
        Given: synthetic corpus, all 3 categories styled, but componentsModel
               has no owning control (no control with personas references a
               componentsModel component)
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 1 (ownership warning promoted to error)
        """
        _write_corpus(
            tmp_path, _THREE_CATEGORY_COMPONENTS, _THREE_CATEGORY_CONTROLS_MODEL_UNOWNED, _FULLY_STYLED_MERMAID
        )
        result = _run(tmp_path, "--block")
        assert result.returncode == 1, (
            f"Expected exit 1 with --block on ownership-dirty corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_clean_corpus_with_block_exits_0(self, tmp_path):
        """
        Given: synthetic corpus, all 3 categories styled AND owned
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 0

        Weak red-phase signal in isolation (an unwired check also exits 0
        here), but a necessary regression companion to the two dirty tests
        above — see test_category_subcategory_nesting.py for the same
        acknowledged pattern.
        """
        _write_corpus(
            tmp_path, _THREE_CATEGORY_COMPONENTS, _THREE_CATEGORY_CONTROLS_ALL_OWNED, _FULLY_STYLED_MERMAID
        )
        result = _run(tmp_path, "--block")
        assert result.returncode == 0, (
            f"Expected exit 0 with --block on clean corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dirty_style_no_block_exits_0_and_prints_warning_naming_category(self, tmp_path):
        """
        Given: synthetic style-dirty corpus, no --block
        When: validate_riskmap.py --force --allow-isolated runs
        Then: exit 0 (warn-only preserved) AND stdout/stderr names
              'componentsModel'

        Primary red driver independent of ImportError: requires the CLI to
        actually print something naming the dirty category, not just exist.
        """
        _write_corpus(
            tmp_path, _THREE_CATEGORY_COMPONENTS, _THREE_CATEGORY_CONTROLS_ALL_OWNED, _MODEL_UNSTYLED_MERMAID
        )
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Expected exit 0 without --block; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "componentsModel" in combined, (
            f"Expected warn output naming 'componentsModel' even without --block; "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

    def test_live_corpus_no_block_exits_0(self):
        """
        Given: actual repo as cwd, no --block
        When: validate_riskmap.py --force --allow-isolated runs
        Then: exit 0 — live corpus is clean today (verified 2026-07-17)
        """
        result = _run(_REPO_ROOT)
        assert result.returncode == 0, (
            f"Expected exit 0 without --block on live corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_live_corpus_with_block_exits_0(self):
        """
        Given: actual repo as cwd, --block
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 0 — verified 2026-07-17, all 3 pre-ADR-030 categories are
              clean; remains the target post-D1 steady state too (componentsTools
              inherits ownership through componentTools' existing controls, per
              this module's top-level docstring)
        """
        result = _run(_REPO_ROOT, "--block")
        assert result.returncode == 0, (
            f"Expected exit 0 with --block on live corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ===========================================================================
# Test Summary
# ===========================================================================
"""
Test Summary
============
TestCheckCategoryStyleAndOwnership (pure function): 12 tests
- clean -> []; style-only warning; ownership-only warning; both independent;
  no-components category is ownerless; empty-personas control does not confer
  ownership; a second owning control rescues it; 'all' escape hatch does NOT
  confer ownership on any category; multi-category independence; empty input;
  return-type contract; live-corpus regression (today's 3 categories clean).

TestCLIWiring (subprocess): 6 tests
- dirty style + --block -> exit 1; dirty ownership + --block -> exit 1;
  clean + --block -> exit 0; dirty style without --block -> exit 0 + names
  the category; live corpus no --block -> exit 0; live corpus + --block ->
  exit 0.

RED today (all fail — function does not exist / check not wired):
- All of TestCheckCategoryStyleAndOwnership (ImportError via the ownership_fn
  fixture)
- TestCLIWiring.test_dirty_style_with_block_exits_1
- TestCLIWiring.test_dirty_ownership_with_block_exits_1
- TestCLIWiring.test_dirty_style_no_block_exits_0_and_prints_warning_naming_category
  (exit code matches by coincidence; the category-name assertion is the real
  red driver)

GREEN today (weak/no-op signal, included for regression parity once wired):
- TestCLIWiring.test_clean_corpus_with_block_exits_0
- TestCLIWiring.test_live_corpus_no_block_exits_0
- TestCLIWiring.test_live_corpus_with_block_exits_0
"""

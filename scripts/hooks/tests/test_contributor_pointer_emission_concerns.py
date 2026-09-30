#!/usr/bin/env python3
"""
Tests for the content-contributor pointer to the emission-concerns registry
(ADR-036 D12).

D12: assigning a cross-category edge to an existing `emission.concerns` label
in `risk-map/yaml/mermaid-styles.yaml` is content, reviewed on the `develop`
PR alongside the edge it labels. That obligation is documented only in
`scripts/docs/styling-configuration.md` -- a doc a component contributor has
no reason to discover, since nothing in the component-authoring surfaces (the
review-findings doc, the issue templates) names it.

Each surface below must, in a VISIBLE field (never only a YAML comment):
link to `scripts/docs/styling-configuration.md`, name its "Emission Mode"
section specifically (not just the doc's top), name the `emission.concerns`
field, and state that concern entries ride the content PR. Four independent
substrings rather than one fixed sentence, so the wording is not pinned to a
single phrasing; "concern" alone is not used because `common-review-findings.md`
already contains that word for unrelated findings (scope creep, framework
mapping IDs) and would pass vacuously.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).parent.parent.parent.parent

_STYLING_CONFIG_DOC = REPO_ROOT / "scripts" / "docs" / "styling-configuration.md"
_LINK_TARGET = "scripts/docs/styling-configuration.md"
# ADR-036 D3 names the emission block; D12's contributor-pointer requirement
# is satisfied only when a surface names this section specifically, not just
# links the doc's top.
_SECTION_HEADING = "Emission Mode"
_REGISTRY_FIELD = "emission.concerns"

# Matches a `{{TOKEN}}` placeholder that is a YAML scalar's ENTIRE value on
# its own line (with or without a leading `- `), e.g. an `options:` sequence
# item substituted by scripts/generate_issue_templates.py. Unquoted, `{` at
# the start of a scalar starts a YAML flow mapping, which is why the raw
# .template.yml source fails yaml.safe_load without this rewrite -- prose
# occurrences of `{{...}}` inside a text line (e.g. sentinel examples) don't
# match (they aren't the line's sole content) and are left untouched.
_BARE_PLACEHOLDER_LINE = re.compile(r"^(\s*(?:-\s*)?)(\{\{[^}\n]*\}\})\s*$", re.MULTILINE)

_MD_SURFACES = [
    ("common-review-findings.md", REPO_ROOT / "risk-map" / "docs" / "contributing" / "common-review-findings.md"),
]

_YAML_SURFACES = [
    ("new_component.template.yml", REPO_ROOT / "scripts" / "TEMPLATES" / "new_component.template.yml"),
    ("update_component.template.yml", REPO_ROOT / "scripts" / "TEMPLATES" / "update_component.template.yml"),
    ("new_component.yml (generated)", REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "new_component.yml"),
    ("update_component.yml (generated)", REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "update_component.yml"),
]

_ALL_SURFACES = _MD_SURFACES + _YAML_SURFACES


def _visible_yaml_text(path: Path) -> str:
    """
    Parse a YAML issue-template file and return every leaf string VALUE,
    concatenated.

    PyYAML discards both whole-line AND trailing inline `#` comments while
    parsing, so a pointer left only in a comment never reaches this string --
    a pointer must be typed into an actual field (description/value/label/
    placeholder) a contributor reads in the rendered GitHub issue form.

    `scripts/TEMPLATES/*.template.yml` sources are not valid standalone YAML
    as committed: a bare `{{PLACEHOLDER}}` token substituted by
    scripts/generate_issue_templates.py can be the sole content of a
    sequence-item line (e.g. under `options:`), which YAML reads as the
    start of a flow mapping and fails to parse. `_BARE_PLACEHOLDER_LINE`
    quote-wraps exactly that shape before parsing so the source round-trips
    through the same real YAML parser as the generated files -- string
    values containing a literal `#` elsewhere on the line (a URL fragment
    like `#L45-L52`, an issue reference like `#123`) are read correctly
    because the parser, not a hand-rolled comment scanner, decides what is
    or is not a comment.
    """
    raw = path.read_text(encoding="utf-8")
    doc = yaml.safe_load(_BARE_PLACEHOLDER_LINE.sub(r'\1"\2"', raw))

    leaves: list[str] = []

    def _walk(node: Any) -> None:
        if isinstance(node, str):
            leaves.append(node)
        elif isinstance(node, dict):
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(doc)
    return "\n".join(leaves)


def _surface_text(path: Path) -> str:
    """Text to search: raw prose for a .md surface, visible YAML values only for a .yml surface."""
    assert path.exists(), f"Expected surface to exist: {path}"
    if path.suffix in (".yml", ".yaml"):
        return _visible_yaml_text(path)
    return path.read_text(encoding="utf-8")


class TestStylingConfigurationDocKeepsTheEmissionSection:
    def test_doc_has_the_emission_mode_heading(self):
        """
        Precondition for every pointer test below: styling-configuration.md
        must actually carry the "Emission Mode" section the pointers name,
        or the surface tests below would be pinning a target that does not
        exist in the doc they point at.
        """
        text = _STYLING_CONFIG_DOC.read_text(encoding="utf-8")
        assert _SECTION_HEADING in text, (
            f"Expected a heading containing {_SECTION_HEADING!r} in {_STYLING_CONFIG_DOC}; "
            f"got none. The surface pointer tests below assume this heading survives."
        )


class TestEmissionConcernContributorPointer:
    """
    Every component-authoring surface a contributor might read must link to
    the emission-config doc's Emission Mode section and name the
    emission.concerns field, so a contributor adding a cross-category edge
    learns about the matching registry entry from the surface they are
    already reading, not only from a tooling doc under scripts/docs/.
    """

    @pytest.mark.parametrize("label,path", _ALL_SURFACES, ids=[s[0] for s in _ALL_SURFACES])
    def test_surface_links_the_styling_configuration_doc(self, label, path):
        """
        Given: one of the five component-authoring surfaces
        When: its visible text (YAML comments excluded for the .yml surfaces)
              is searched for the emission-config doc's path
        Then: `scripts/docs/styling-configuration.md` appears in a visible
              field, not only in a comment
        """
        content = _surface_text(path)
        assert _LINK_TARGET in content, (
            f"Expected {label} to link {_LINK_TARGET!r} in a visible field "
            f"(ADR-036 D3/D12's emission config doc); got no match in {path}"
        )

    @pytest.mark.parametrize("label,path", _ALL_SURFACES, ids=[s[0] for s in _ALL_SURFACES])
    def test_surface_names_the_emission_mode_section(self, label, path):
        """
        Given: one of the five component-authoring surfaces
        When: its visible text is searched for the section heading name
        Then: "Emission Mode" appears -- proving the link targets that
              section specifically, not just the top of the doc

        Anchor-slug matching (GitHub's exact "#4-emission-mode-..." fragment
        computation) is deliberately not pinned here -- fragile against a
        heading-number renumber -- the heading NAME surviving in the surface
        is the signal that the link targets this section, not the doc's top.
        """
        content = _surface_text(path)
        assert _SECTION_HEADING in content, (
            f"Expected {label} to name the {_SECTION_HEADING!r} section (not just link "
            f"the doc's top); got no match in {path}"
        )

    @pytest.mark.parametrize("label,path", _ALL_SURFACES, ids=[s[0] for s in _ALL_SURFACES])
    def test_surface_names_the_emission_concerns_field(self, label, path):
        """
        Given: one of the five component-authoring surfaces
        When: its visible text is searched for the specific config field
        Then: "emission.concerns" appears

        Not "concern" alone: `common-review-findings.md` already uses that
        word for unrelated findings (scope creep, framework mapping IDs), so
        a bare substring match would pass vacuously without the pointer
        landing at all. "emission.concerns" names the exact field a
        cross-category edge needs an entry in, and does not collide with
        those unrelated occurrences.
        """
        content = _surface_text(path)
        assert _REGISTRY_FIELD in content, (
            f"Expected {label} to name the {_REGISTRY_FIELD!r} field; got no match in {path}"
        )

    @pytest.mark.parametrize("label,path", _ALL_SURFACES, ids=[s[0] for s in _ALL_SURFACES])
    def test_surface_states_concern_entries_ride_the_content_pr(self, label, path):
        """
        Given: one of the five component-authoring surfaces
        When: its visible text is searched, case-insensitively
        Then: it states the entry travels with a "content PR" (ADR-036 D12:
              `emission.concerns` entries route with the edges they label,
              on the `develop` content PR)
        """
        content = _surface_text(path).lower()
        assert "content pr" in content, (
            f"Expected {label} to state the concern entry rides the content PR "
            f"(ADR-036 D12); got no 'content PR' phrase in {path}"
        )

#!/usr/bin/env python3
"""
Tests for ADR-030 D1 mermaid-styles.yaml / ComponentGraph consumer wiring.

ADR-030 Consequences: "mermaid-styles.yaml needs a componentsTools style or
the new category renders unstyled in generated diagrams" and "The
ComponentGraph hardcoded-category handling is a hard blocker... Graph
generation will not pick up componentsTools until that code is fixed."

Two independent surfaces are exercised here:

1. risk-map/schemas/mermaid-styles.schema.json declares
   sharedElements.componentCategories with additionalProperties: false and a
   required list naming the 3 existing categories. Adding a componentsTools
   entry to mermaid-styles.yaml WITHOUT first widening this schema's
   properties/required list fails check-jsonschema — a second, independently
   discoverable "schema forgot the consumer" gap distinct from
   components.schema.json (ADR-030 names components.schema.json explicitly;
   this module additionally covers mermaid-styles.schema.json, which the ADR
   text does not call out by name but which the same "atomic schema+yaml"
   principle applies to).

2. ComponentGraph (riskmap_validator.graphing.component_graph), exercised via
   MermaidConfigLoader against the LIVE mermaid-styles.yaml on disk: a
   component in category=componentsTools must render with both a
   `style componentsTools ...` line and a `subgraph componentsTools` block.
   Verified 2026-07-17: ComponentGraph does not crash on a 4th category (it
   renders the subgraph structure generically); an unstyled category would be
   silently dropped from styling (not from structure) because the "Node
   style definitions" loop only iterates
   config_loader.get_component_category_styles(). These tests pin that the
   STYLE line specifically appears now that mermaid-styles.yaml carries a
   componentsTools entry.
"""

import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from riskmap_validator.graphing import ComponentGraph  # noqa: E402
from riskmap_validator.graphing.graph_utils import MermaidConfigLoader  # noqa: E402
from riskmap_validator.models import ComponentNode  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_MERMAID_STYLES_SCHEMA = _REPO_ROOT / "risk-map" / "schemas" / "mermaid-styles.schema.json"
_MERMAID_STYLES_YAML = _REPO_ROOT / "risk-map" / "yaml" / "mermaid-styles.yaml"
_COMPONENTS_SCHEMA = _REPO_ROOT / "risk-map" / "schemas" / "components.schema.json"


@pytest.fixture(scope="module")
def mermaid_styles_schema() -> dict:
    """Parsed mermaid-styles.schema.json."""
    with open(_MERMAID_STYLES_SCHEMA, encoding="utf-8") as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def mermaid_styles_yaml() -> dict:
    """Parsed mermaid-styles.yaml."""
    with open(_MERMAID_STYLES_YAML, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture(scope="module")
def component_categories_schema(mermaid_styles_schema: dict) -> dict:
    """properties/sharedElements/properties/componentCategories sub-schema."""
    props = mermaid_styles_schema.get("properties", {}).get("sharedElements", {}).get("properties", {})
    assert "componentCategories" in props, (
        "Expected properties/sharedElements/properties/componentCategories in mermaid-styles.schema.json"
    )
    return props["componentCategories"]


# ============================================================================
# mermaid-styles.schema.json — componentCategories must allow componentsTools
# ============================================================================


class TestMermaidStylesSchemaAllowsComponentsTools:
    """
    sharedElements.componentCategories has additionalProperties: false; a
    componentsTools key in mermaid-styles.yaml is REJECTED by check-jsonschema
    unless this schema's properties (and, for parity with the 3 existing
    entries, required) list also names it.
    """

    def test_componentstools_in_component_categories_properties(self, component_categories_schema: dict):
        """
        Given: sharedElements.componentCategories.properties
        When: its keys are inspected
        Then: 'componentsTools' is present

        Without this, additionalProperties: false rejects any componentsTools
        entry a content author adds to mermaid-styles.yaml, even though the
        entry is exactly what ADR-030 asks for.
        """
        properties = component_categories_schema.get("properties", {})
        assert "componentsTools" in properties, (
            f"Expected 'componentsTools' in sharedElements.componentCategories.properties "
            f"(mermaid-styles.schema.json); got keys: {sorted(properties.keys())}"
        )

    def test_componentstools_property_refs_componentcategory_definition(self, component_categories_schema: dict):
        """
        Given: sharedElements.componentCategories.properties.componentsTools
        When: its shape is inspected
        Then: it $refs the shared componentCategory definition, consistent
              with componentsInfrastructure/componentsApplication/componentsModel
        """
        properties = component_categories_schema.get("properties", {})
        if "componentsTools" not in properties:
            pytest.fail("componentsTools property not declared; cannot check its shape")
        assert properties["componentsTools"].get("$ref") == "#/definitions/componentCategory", (
            f"Expected componentsTools to $ref '#/definitions/componentCategory' like the "
            f"other 3 category entries; got: {properties['componentsTools']}"
        )

    def test_componentstools_in_required_list(self, component_categories_schema: dict):
        """
        Given: sharedElements.componentCategories.required
        When: its members are inspected
        Then: 'componentsTools' is present, matching the existing pattern where
              componentsInfrastructure/componentsApplication/componentsModel are
              all required (componentsData is the one pre-existing exception —
              declared in properties but not required; componentsTools is a
              genuine 4th top-level category and should follow the required
              3, not the legacy exception)
        """
        required = component_categories_schema.get("required", [])
        assert "componentsTools" in required, (
            f"Expected 'componentsTools' in sharedElements.componentCategories.required "
            f"(ADR-030 D1: an unstyled top-level category should fail schema validation, "
            f"not silently render unstyled); got: {required}"
        )


# ============================================================================
# mermaid-styles.yaml — the actual style entry
# ============================================================================


class TestMermaidStylesYamlHasComponentsToolsEntry:
    """The live mermaid-styles.yaml must carry a componentsTools style entry."""

    def test_componentstools_entry_present(self, mermaid_styles_yaml: dict):
        """
        Given: the live mermaid-styles.yaml
        When: sharedElements.componentCategories is inspected
        Then: 'componentsTools' is a key
        """
        categories = mermaid_styles_yaml.get("sharedElements", {}).get("componentCategories", {})
        assert "componentsTools" in categories, (
            f"Expected 'componentsTools' in sharedElements.componentCategories "
            f"(mermaid-styles.yaml); got keys: {sorted(categories.keys())}"
        )

    def test_componentstools_entry_has_required_style_fields(self, mermaid_styles_yaml: dict):
        """
        Given: the componentsTools style entry
        When: its fields are inspected
        Then: fill, stroke, and strokeWidth are all present (required by the
              componentCategory schema definition)
        """
        categories = mermaid_styles_yaml.get("sharedElements", {}).get("componentCategories", {})
        if "componentsTools" not in categories:
            pytest.fail("componentsTools style entry not present; cannot check its fields")
        entry = categories["componentsTools"]
        for field in ("fill", "stroke", "strokeWidth"):
            assert field in entry, f"Expected '{field}' in componentsTools style entry; got: {entry}"

    def test_live_mermaid_styles_yaml_passes_check_jsonschema(self):
        """
        Given: the live mermaid-styles.yaml and mermaid-styles.schema.json
        When: check-jsonschema validates the yaml against the schema
        Then: exit code 0

        The atomic-pairing guard for this consumer: a componentsTools entry
        added to the yaml without the matching schema property addition (or
        vice versa) fails this check.
        """
        import subprocess

        base_uri = f"file://{_MERMAID_STYLES_SCHEMA.parent}/"
        result = subprocess.run(
            [
                "check-jsonschema",
                "--base-uri",
                base_uri,
                "--schemafile",
                str(_MERMAID_STYLES_SCHEMA),
                str(_MERMAID_STYLES_YAML),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"Live mermaid-styles.yaml must pass check-jsonschema against "
            f"mermaid-styles.schema.json.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ============================================================================
# MermaidConfigLoader / _get_schema_categories — live wiring
# ============================================================================


class TestLoaderSeesComponentsToolsOnLiveCorpus:
    """
    MermaidConfigLoader and the schema-category helper, exercised against the
    REAL files on disk (not synthetic tmp fixtures) — the same live-corpus
    pattern used by TestMissingCategoryWarnings.test_live_corpus_produces_zero_warnings
    in test_mermaid_config_loader.py, scoped specifically to componentsTools.
    """

    def test_schema_categories_includes_componentstools(self):
        """
        Given: the live components.schema.json category.id enum
        When: read directly
        Then: 'componentsTools' is a member
        """
        with open(_COMPONENTS_SCHEMA, encoding="utf-8") as fh:
            schema = json.load(fh)
        schema_categories = set(schema["definitions"]["category"]["properties"]["id"]["enum"])
        assert "componentsTools" in schema_categories, (
            f"Expected 'componentsTools' in the live components.schema.json category "
            f"enum; got: {schema_categories}"
        )

    def test_live_loader_component_category_styles_includes_componentstools(self):
        """
        Given: MermaidConfigLoader pointed at the live mermaid-styles.yaml
        When: get_component_category_styles() is called
        Then: 'componentsTools' is a key in the returned dict
        """
        loader = MermaidConfigLoader(_MERMAID_STYLES_YAML)
        styles = loader.get_component_category_styles()
        assert "componentsTools" in styles, (
            f"Expected 'componentsTools' in live get_component_category_styles(); "
            f"got keys: {sorted(styles.keys())}"
        )

    def test_live_corpus_has_zero_missing_category_warnings_including_tools(self):
        """
        Given: the live components.schema.json category enum and the live
               mermaid-styles.yaml
        When: get_missing_category_warnings() is called with the live schema
              categories (now including componentsTools)
        Then: returns [] — componentsTools has a styling entry, same as the
              other 3 categories

        This is a componentsTools-scoped variant of the pre-existing
        TestMissingCategoryWarnings.test_live_corpus_produces_zero_warnings in
        test_mermaid_config_loader.py (ADR-022 D6a); that test will ALSO start
        failing once components.schema.json gains componentsTools, for the
        same underlying reason, until mermaid-styles.yaml is updated in the
        same commit.
        """
        with open(_COMPONENTS_SCHEMA, encoding="utf-8") as fh:
            schema = json.load(fh)
        schema_categories = set(schema["definitions"]["category"]["properties"]["id"]["enum"])

        loader = MermaidConfigLoader(_MERMAID_STYLES_YAML)
        result = loader.get_missing_category_warnings(schema_categories)
        assert result == [], f"Expected 0 missing-category warnings on the live corpus; got: {result}"


# ============================================================================
# ComponentGraph rendering — live styling wired into generated output
# ============================================================================


class TestComponentGraphRendersComponentsToolsStyled:
    """
    ComponentGraph, constructed with the DEFAULT (live, singleton)
    MermaidConfigLoader reading the real risk-map/yaml/mermaid-styles.yaml —
    the same loader validate_riskmap.py --to-graph uses in production.
    """

    def test_componentstools_subgraph_and_style_both_render(self):
        """
        Given: a synthetic component set with one member in
               category=componentsTools, subcategory=componentsToolCore, and
               ComponentGraph built with the default (live) config loader
        When: to_mermaid() is called
        Then: the output contains BOTH a 'subgraph componentsTools' block AND
              a 'style componentsTools' line

        The subgraph line renders regardless (ComponentGraph's category
        grouping is generic); the style line depends on the "Node style
        definitions" loop in ComponentGraph.build_graph, which iterates
        config_loader.get_component_category_styles() — this is the concrete
        form of ADR-030's "renders unstyled" consequence that the
        componentsTools mermaid-styles.yaml entry closes.
        """
        components = {
            "compA": ComponentNode(
                title="A", category="componentsInfrastructure", subcategory=None, to_edges=["compB"], from_edges=[]
            ),
            "compB": ComponentNode(
                title="B",
                category="componentsTools",
                subcategory="componentsToolCore",
                to_edges=[],
                from_edges=["compA"],
            ),
        }
        forward_map = {"compA": ["compB"]}

        # Explicit live loader instance (not the module singleton) so this test
        # is not order-dependent on other tests' singleton mutation, while
        # still reading the real file on disk.
        loader = MermaidConfigLoader(_MERMAID_STYLES_YAML)
        graph = ComponentGraph(forward_map, components, config_loader=loader)
        output = graph.to_mermaid()

        assert "subgraph componentsTools" in output, (
            f"Expected a 'subgraph componentsTools' block in ComponentGraph output; got:\n{output}"
        )
        assert "style componentsTools" in output, (
            f"Expected a 'style componentsTools' line in ComponentGraph output "
            f"(ADR-030: 'mermaid-styles.yaml needs a componentsTools style or the new "
            f"category renders unstyled'); got:\n{output}"
        )


# ============================================================================
# Test Summary
# ============================================================================
"""
Test Summary
============
Total Tests: 10

- TestMermaidStylesSchemaAllowsComponentsTools (3): properties key, $ref
  shape, required-list membership
- TestMermaidStylesYamlHasComponentsToolsEntry (3): entry present, required
  style fields present, live check-jsonschema pass
- TestLoaderSeesComponentsToolsOnLiveCorpus (3): schema enum membership,
  loader styles membership, zero missing-category warnings
- TestComponentGraphRendersComponentsToolsStyled (1): subgraph AND style line
  both render via the live default loader

componentsTools has a mermaid-styles.yaml styling entry and a matching
schema allowance (ADR-030 D1, closing the "renders unstyled" consequence);
all 10 tests are green:
- TestMermaidStylesSchemaAllowsComponentsTools (all 3)
- TestMermaidStylesYamlHasComponentsToolsEntry.test_componentstools_entry_present
- TestMermaidStylesYamlHasComponentsToolsEntry.test_componentstools_entry_has_required_style_fields
- TestLoaderSeesComponentsToolsOnLiveCorpus (all 3)
- TestComponentGraphRendersComponentsToolsStyled.test_componentstools_subgraph_and_style_both_render
  (both the subgraph line and the style line render)

Forward guard (atomicity, regression protection):
- TestMermaidStylesYamlHasComponentsToolsEntry.test_live_mermaid_styles_yaml_passes_check_jsonschema
"""

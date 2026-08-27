#!/usr/bin/env python3
"""
Tests for the BaseGraph class

This test suite validates the foundational graph generation class used by
ComponentGraph. The tests focus on initialization validation, category
handling, cluster finding, node grouping, and style generation.

Test Coverage:
==============
1. BaseGraph Class Initialization:
   - TypeError when components is not dict
   - TypeError when components contains non-ComponentNode values
   - Config loader initialization

2. Category Name Loading (_load_category_names):
   - Successful YAML loading
   - Exception handling for missing/corrupt files
   - Caching behavior

3. Node Clustering (_find_node_clusters):
   - Component clusters finding
   - Invalid node_type (should return {})
   - Cluster naming conflict resolution
   - Fallback subgroup naming

4. Node Grouping (_group_node_by):
   - Components grouping with/without subcategories
   - ValueError with invalid node_type
   - Subcategory processing

5. Nested Subgraph Generation (_get_nested_subgraph_new):
   - Components without subcategory
   - Subgroup iteration and line generation
   - Empty line removal
   - Empty category_subgroups handling

6. Node Styling (_get_node_style):
   - componentCategory style type
   - Unknown style_type default

Coverage Target: 95%+ for graphing/base.py (up from 78%)
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

# Add scripts/hooks directory to path
git_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(git_root / "scripts" / "hooks"))

from riskmap_validator.graphing.base import BaseGraph  # noqa: E402
from riskmap_validator.graphing.graph_utils import MermaidConfigLoader  # noqa: E402
from riskmap_validator.models import ComponentNode  # noqa: E402


class TestBaseGraphInitialization:
    """
    Test BaseGraph initialization validation.

    Tests focus on type validation for the components dictionary.
    """

    @pytest.fixture
    def valid_components(self):
        """Provide valid components dictionary."""
        return {
            "comp1": ComponentNode(
                title="Component 1",
                category="componentsData",
                to_edges=["comp2"],
                from_edges=[],
            ),
            "comp2": ComponentNode(
                title="Component 2",
                category="componentsModel",
                to_edges=[],
                from_edges=["comp1"],
            ),
        }

    @pytest.fixture
    def mock_config_loader(self):
        """Provide mock MermaidConfigLoader."""
        mock = Mock(spec=MermaidConfigLoader)
        mock.get_component_category_styles.return_value = {
            "componentsData": {
                "fill": "#fff5e6",
                "stroke": "#333333",
                "strokeWidth": "2px",
            },
        }
        return mock

    def test_basegraph_creation_with_valid_components_succeeds(self, valid_components, mock_config_loader):
        """
        Test that BaseGraph can be created with valid components.

        Given: Valid components dictionary
        When: BaseGraph is instantiated
        Then: Object is created successfully
        """
        graph = BaseGraph(components=valid_components, config_loader=mock_config_loader)

        assert graph.components == valid_components
        assert len(graph.components) == 2

    def test_basegraph_components_not_dict_raises_typeerror(self, mock_config_loader):
        """
        Test that non-dict components raises TypeError.

        Given: Components parameter that is not a dict
        When: BaseGraph is instantiated
        Then: TypeError is raised
        """
        with pytest.raises(TypeError, match="'components' must be a dict of ComponentNodes"):
            BaseGraph(components=["not", "a", "dict"], config_loader=mock_config_loader)  # pyright: ignore[reportArgumentType]

    def test_basegraph_components_contains_non_componentnode_raises_typeerror(self, mock_config_loader):
        """
        Test that components dict with non-ComponentNode values raises TypeError.

        Given: Components dict containing non-ComponentNode values
        When: BaseGraph is instantiated
        Then: TypeError is raised
        """
        invalid_components = {
            "comp1": ComponentNode(
                title="Component 1",
                category="componentsData",
                to_edges=[],
                from_edges=[],
            ),
            "comp2": "not a component node",  # Invalid
        }

        with pytest.raises(TypeError, match="'components' must be a dict of ComponentNodes"):
            BaseGraph(components=invalid_components, config_loader=mock_config_loader)


class TestCategoryNameLoading:
    """
    Test _load_category_names method.

    Tests focus on YAML loading, exception handling, caching, and filtering.
    """

    @pytest.fixture
    def mock_config_loader(self):
        """Provide mock config loader."""
        return Mock(spec=MermaidConfigLoader)

    @pytest.fixture
    def temp_yaml_files(self):
        """Create temporary YAML files for testing."""
        # Create temp directory structure
        temp_dir = Path(tempfile.mkdtemp())
        risk_map_dir = temp_dir / "risk-map" / "yaml"
        risk_map_dir.mkdir(parents=True)

        controls_file = risk_map_dir / "controls.yaml"
        components_file = risk_map_dir / "components.yaml"

        controls_data = {
            "categories": [
                {"id": "controlsData", "title": "Data Controls"},
                {"id": "controlsModel", "title": "Model Controls"},
            ]
        }
        components_data = {
            "categories": [
                {"id": "componentsData", "title": "Data Components"},
                {"id": "componentsModel", "title": "Model Components"},
            ]
        }

        with open(controls_file, "w") as f:
            yaml.dump(controls_data, f)
        with open(components_file, "w") as f:
            yaml.dump(components_data, f)

        yield temp_dir, controls_file, components_file

        # Cleanup
        import shutil

        shutil.rmtree(temp_dir)

    def test_load_category_names_caching(self, mock_config_loader):
        """
        Test that category names are cached after first load.

        Given: BaseGraph instance
        When: _load_category_names is called multiple times
        Then: Categories are loaded once and cached
        """
        components = {
            "comp1": ComponentNode(title="C1", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)

        # First call - should load
        with patch("pathlib.Path.exists", return_value=False):
            _ = graph._load_category_names()

        # Set cache manually
        graph._category_names_cache = {"test": "Test Category"}

        # Second call - should use cache
        names2 = graph._load_category_names()

        assert names2 == {"test": "Test Category"}

    def test_load_category_names_with_exception_returns_empty_dict(self, mock_config_loader):
        """
        Test that exception during YAML loading is handled gracefully.

        Given: YAML files that cause exceptions
        When: _load_category_names is called
        Then: Returns empty dict and doesn't raise exception
        """
        components = {
            "comp1": ComponentNode(title="C1", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)

        with patch("pathlib.Path.exists", return_value=True):
            with patch("builtins.open", side_effect=IOError("File error")):
                names = graph._load_category_names()

        # Should return empty dict on exception
        assert names == {}


class TestCategoryDisplayName:
    """
    Test _get_category_display_name method.

    Every real ComponentGraph render passes a category id that is present in
    the YAML-loaded cache (component_graph.py:113), so the "configured name"
    return path is the one every production call actually takes. The other
    tests in this module cover it only indirectly, via mocked config loaders
    that never populate _category_names_cache with the category under test.
    """

    @pytest.fixture
    def mock_config_loader(self):
        """Provide mock config loader."""
        return Mock(spec=MermaidConfigLoader)

    def test_returns_configured_name_for_cached_category(self, mock_config_loader):
        """
        Test that a category present in the cached YAML-loaded names returns
        the configured display name directly.

        Given: A category id already present in _category_names_cache
        When: _get_category_display_name is called
        Then: The cached configured name is returned verbatim, not a
              dynamically generated one
        """
        components = {
            "comp1": ComponentNode(title="C1", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        graph._category_names_cache = {"componentsData": "Configured Data Components"}

        assert graph._get_category_display_name("componentsData") == "Configured Data Components"


class TestNodeClustering:
    """
    Test _find_node_clusters method.

    Tests focus on component clustering and the invalid-node_type fallback.
    """

    @pytest.fixture
    def mock_config_loader(self):
        """Provide mock config loader."""
        return Mock(spec=MermaidConfigLoader)

    def test_find_component_clusters(self, mock_config_loader):
        """
        Test finding component clusters.

        Given: Components and node-to-controls mapping
        When: _find_component_clusters is called
        Then: Clusters are identified correctly
        """
        components = {
            "comp1": ComponentNode(title="C1", category="componentsData", to_edges=[], from_edges=[]),
            "comp2": ComponentNode(title="C2", category="componentsData", to_edges=[], from_edges=[]),
            "comp3": ComponentNode(title="C3", category="componentsModel", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        graph.component_by_category = {"componentsData": ["comp1", "comp2"]}

        # Node to controls mapping with shared controls
        node_to_controls = {
            "comp1": {"ctrl1", "ctrl2"},
            "comp2": {"ctrl1", "ctrl2"},  # Shares 2 controls with comp1
            "comp3": {"ctrl3"},
        }

        clusters = graph._find_component_clusters(node_to_controls, min_shared_controls=2, min_nodes=2)

        # comp1 and comp2 should be clustered together
        assert len(clusters) >= 1
        # At least one cluster should contain both comp1 and comp2
        cluster_found = False
        for cluster_name, cluster_members in clusters.items():
            if "comp1" in cluster_members and "comp2" in cluster_members:
                cluster_found = True
                break
        assert cluster_found

    def test_find_node_clusters_with_invalid_node_type_returns_empty_dict(self, mock_config_loader):
        """
        Test that invalid node_type returns empty dict.

        Given: Invalid node_type
        When: _find_node_clusters is called
        Then: Returns empty dict
        """
        components = {
            "comp1": ComponentNode(title="C1", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)

        node_to_controls = {
            "comp1": {"ctrl1"},
        }

        clusters = graph._find_node_clusters("invalid_type", node_to_controls)

        assert clusters == {}

    def test_cluster_naming_conflict_resolution(self, mock_config_loader):
        """
        Test that cluster naming resolves conflicts with existing categories.

        Given: Components that would create conflicting cluster names
        When: _find_node_clusters is called
        Then: Conflict is resolved with modified name
        """
        components = {
            "componentData1": ComponentNode(title="Data 1", category="componentsData", to_edges=[], from_edges=[]),
            "componentData2": ComponentNode(title="Data 2", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        graph.component_by_category = {"componentsData": ["componentData1", "componentData2"]}

        node_to_controls = {
            "componentData1": {"ctrl1", "ctrl2"},
            "componentData2": {"ctrl1", "ctrl2"},
        }

        clusters = graph._find_node_clusters("component", node_to_controls, min_shared_controls=2, min_nodes=2)

        # Check that cluster names don't conflict
        for cluster_name in clusters.keys():
            # Should have some name (possibly with suffix to avoid conflict)
            assert cluster_name is not None
            assert len(cluster_name) > 0

    def test_cluster_naming_conflict_appends_parent_category_when_prefix_differs(self, mock_config_loader):
        """
        Test that a colliding cluster name is disambiguated by appending the
        parent category, for the case where the common prefix is NOT the
        same string as the parent category name.

        test_cluster_naming_conflict_resolution above always constructs a
        common prefix identical to the parent category, which only reaches
        the "append literal Subgroup" branch. This is the sibling branch:
        #488 (the ComponentGraph collision fix this clustering machinery is
        retained for) will need both.

        Given: A cluster whose derived name ("componentsFoo") collides with
               an existing category, where "Foo" (the common prefix) differs
               from "Data" (the parent category, stripped of its prefix)
        When: _find_node_clusters is called
        Then: The parent category name is appended to disambiguate, rather
              than the literal "Subgroup" suffix
        """
        components = {
            "componentFoo1": ComponentNode(title="Foo 1", category="componentsData", to_edges=[], from_edges=[]),
            "componentFoo2": ComponentNode(title="Foo 2", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        # Pre-seed "componentsFoo" as an already-taken category name so the
        # derived cluster name collides with it.
        graph.component_by_category = {
            "componentsFoo": [],
            "componentsData": ["componentFoo1", "componentFoo2"],
        }

        node_to_controls = {
            "componentFoo1": {"ctrl1", "ctrl2"},
            "componentFoo2": {"ctrl1", "ctrl2"},
        }

        clusters = graph._find_node_clusters("component", node_to_controls, min_shared_controls=2, min_nodes=2)

        assert "componentsFooData" in clusters
        assert "componentsFooSubgroup" not in clusters

    def test_cluster_fallback_naming(self, mock_config_loader):
        """
        Test fallback subgroup naming when no common prefix exists.

        Given: Components with no meaningful common prefix
        When: _find_node_clusters is called
        Then: Fallback naming pattern is used
        """
        components = {
            "compA": ComponentNode(title="A", category="componentsData", to_edges=[], from_edges=[]),
            "compZ": ComponentNode(title="Z", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        graph.component_by_category = {"componentsData": ["compA", "compZ"]}

        node_to_controls = {
            "compA": {"ctrl1", "ctrl2"},
            "compZ": {"ctrl1", "ctrl2"},
        }

        clusters = graph._find_node_clusters("component", node_to_controls, min_shared_controls=2, min_nodes=2)

        # Should use fallback naming like "componentsSubgroup1"
        if clusters:  # Clustering might not occur if common prefix is too short
            for cluster_name in clusters.keys():
                assert "components" in cluster_name.lower() or "subgroup" in cluster_name.lower()


class TestSubgraphIdUniqueness:
    """
    Guard the Mermaid rendering contract that every generated graph must satisfy:
    no "subgraph <id>" declaration id is emitted more than once. A duplicated
    subgraph id makes the whole file unrenderable (mmdc exits 1 with a
    TypeError; mermaid.live fails on it too).

    This lives at the BaseGraph level -- not against a concrete graph type's
    rendered output -- because GitHub issue #477 removed controls_graph.py and
    risks_graph.py, and a guard written against either one's output would have
    been deleted along with it. ComponentGraph is now the only graph type, and
    it is built on the same BaseGraph clustering (_find_node_clusters /
    _find_component_clusters) and subgraph-emission (_create_subgraph_section)
    primitives exercised here directly.

    The test asserts the guarantee (no duplicate id in emitted output), not a
    mechanism: it does not assert which naming branch is taken, what a name is
    spelled, or that any particular code path inside _find_node_clusters ran.
    """

    @pytest.fixture
    def mock_config_loader(self):
        """Provide mock config loader."""
        return Mock(spec=MermaidConfigLoader)

    def test_clusters_from_independent_categories_do_not_emit_duplicate_subgraph_ids(self, mock_config_loader):
        """
        Reproduce a duplicate subgraph id using clusters whose members span two
        different component categories.

        Fixture shape: two categories (componentsApplication,
        componentsExternalTools), each containing a pair of components that
        shares 2+ controls (the clustering threshold) and whose IDs have no
        meaningful common prefix once "component" is stripped -- e.g.
        "componentA1"/"componentB2" strip to "A1"/"B2", which share no prefix,
        forcing the positional fallback subgroup name. Component clustering is
        scoped to one category at a time -- that was the calling convention in
        the controls_graph.py per-category loop #477 removed, and it is the
        convention the clustering API still assumes -- so this fixture calls
        _find_component_clusters once per category rather than driving it
        through a graph type.

        Given: two independently-clustered categories, each producing one
               2-member cluster via BaseGraph._find_component_clusters
        When: a subgraph section is emitted for every discovered cluster, the
              same way every graph type emits sections via
              BaseGraph._create_subgraph_section
        Then: no subgraph id appears in more than one "subgraph <id> [...]"
              declaration across the combined output
        """
        components = {
            "componentA1": ComponentNode(
                title="A1 Title", category="componentsApplication", to_edges=[], from_edges=[]
            ),
            "componentB2": ComponentNode(
                title="B2 Title", category="componentsApplication", to_edges=[], from_edges=[]
            ),
            "componentC3": ComponentNode(
                title="C3 Title", category="componentsExternalTools", to_edges=[], from_edges=[]
            ),
            "componentD4": ComponentNode(
                title="D4 Title", category="componentsExternalTools", to_edges=[], from_edges=[]
            ),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        graph.component_by_category = {
            "componentsApplication": ["componentA1", "componentB2"],
            "componentsExternalTools": ["componentC3", "componentD4"],
        }

        # Each category's node-to-controls map is independent, mirroring a
        # caller that builds one map per category before clustering within it
        # (the calling convention #488's ComponentGraph fix will use).
        node_to_controls_by_category = {
            "componentsApplication": {
                "componentA1": {"ctrl1", "ctrl2"},
                "componentB2": {"ctrl1", "ctrl2"},
            },
            "componentsExternalTools": {
                "componentC3": {"ctrl3", "ctrl4"},
                "componentD4": {"ctrl3", "ctrl4"},
            },
        }

        emitted_ids: list[str] = []
        for category, node_to_controls in node_to_controls_by_category.items():
            clusters = graph._find_component_clusters(node_to_controls, min_shared_controls=2, min_nodes=2)

            # Vacuity guard: if clustering stops producing subgroups for this
            # fixture (threshold tuning, a shape assumption breaking elsewhere
            # in the module), the test must fail loudly instead of silently
            # passing over an empty set -- this module's history includes
            # guards that passed because their derivation returned nothing.
            assert clusters, (
                f"No clusters found for category {category!r}; fixture no longer "
                "exercises clustering -- update the fixture, don't let this pass empty."
            )

            for subgroup_name, member_ids in clusters.items():
                section = graph._create_subgraph_section(
                    category=subgroup_name,
                    category_name=subgroup_name,
                    item_ids=member_ids,
                    items=graph.components,
                )
                for line in section:
                    stripped = line.strip()
                    if stripped.startswith("subgraph "):
                        # Line format: 'subgraph <id> ["<display name>"]'
                        emitted_ids.append(stripped.split()[1])

        # Sanity check on the harness itself: two sections should have been
        # emitted (one per category) before checking for collisions between
        # them.
        assert len(emitted_ids) == 2

        duplicate_ids = {sid for sid in emitted_ids if emitted_ids.count(sid) > 1}
        assert not duplicate_ids, (
            f"Duplicate subgraph id(s) {duplicate_ids} emitted across categories "
            f"{list(node_to_controls_by_category)}; a Mermaid graph with a repeated "
            "subgraph id fails to render (mmdc exits 1, mermaid.live fails too)."
        )

    def test_common_prefix_branch_collision_across_categories_does_not_emit_duplicate_subgraph_ids(
        self, mock_config_loader
    ):
        """
        Same guarantee as the test above, reached via the OTHER naming branch in
        _find_node_clusters (base.py:230-242, the common-prefix branch) instead of
        the positional fallback. A fix that only patches the fallback branch (e.g.
        making its positional index globally unique) leaves this branch shipping
        an identical collision, since it computes names independently via
        commonprefix() and never consults what the fallback branch or a sibling
        category's call produced.

        Fixture shape: two categories, each clustering a pair of components whose
        IDs share a >2-char prefix once "component" is stripped
        ("GizmoAlpha"/"GizmoBeta" -> "Gizmo"; "GizmoGamma"/"GizmoDelta" -> "Gizmo"),
        so both independent per-category calls derive the same name
        "componentsGizmo" via the common-prefix branch specifically. "Gizmo" is a
        fictitious prefix, chosen so this fixture doesn't also collide with the
        real schema's "componentsModel" category (a genuine top-level component
        category), which would confound the assertion with an unrelated,
        pre-existing collision.

        Given: two independently-clustered categories, each producing one
               2-member cluster whose name resolves through the common-prefix
               branch to the same string
        When: a subgraph section is emitted for every discovered cluster via
              BaseGraph._create_subgraph_section
        Then: no subgraph id appears in more than one declaration, AND (fixture-
              reach guard) the two categories' derived names actually match each
              other and are not fallback-pattern names -- proving this fixture
              still exercises the common-prefix branch and not the scenario the
              previous test already covers
        """
        components = {
            "componentGizmoAlpha": ComponentNode(
                title="Gizmo Alpha", category="componentsApplication", to_edges=[], from_edges=[]
            ),
            "componentGizmoBeta": ComponentNode(
                title="Gizmo Beta", category="componentsApplication", to_edges=[], from_edges=[]
            ),
            "componentGizmoGamma": ComponentNode(
                title="Gizmo Gamma", category="componentsExternalTools", to_edges=[], from_edges=[]
            ),
            "componentGizmoDelta": ComponentNode(
                title="Gizmo Delta", category="componentsExternalTools", to_edges=[], from_edges=[]
            ),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        graph.component_by_category = {
            "componentsApplication": ["componentGizmoAlpha", "componentGizmoBeta"],
            "componentsExternalTools": ["componentGizmoGamma", "componentGizmoDelta"],
        }

        node_to_controls_by_category = {
            "componentsApplication": {
                "componentGizmoAlpha": {"ctrl1", "ctrl2"},
                "componentGizmoBeta": {"ctrl1", "ctrl2"},
            },
            "componentsExternalTools": {
                "componentGizmoGamma": {"ctrl3", "ctrl4"},
                "componentGizmoDelta": {"ctrl3", "ctrl4"},
            },
        }

        derived_names: list[str] = []
        emitted_ids: list[str] = []
        for category, node_to_controls in node_to_controls_by_category.items():
            clusters = graph._find_component_clusters(node_to_controls, min_shared_controls=2, min_nodes=2)

            assert clusters, (
                f"No clusters found for category {category!r}; fixture no longer "
                "exercises clustering -- update the fixture, don't let this pass empty."
            )

            for subgroup_name, member_ids in clusters.items():
                derived_names.append(subgroup_name)
                section = graph._create_subgraph_section(
                    category=subgroup_name,
                    category_name=subgroup_name,
                    item_ids=member_ids,
                    items=graph.components,
                )
                for line in section:
                    stripped = line.strip()
                    if stripped.startswith("subgraph "):
                        emitted_ids.append(stripped.split()[1])

        # Fixture-reach guard: confirm this fixture actually reaches the
        # common-prefix collision it was built for -- both categories' clusters
        # resolved to the identical name, and that name did not come from the
        # positional fallback branch already covered by the previous test. This
        # is a mechanism assertion on the fixture's own construction (what
        # inputs were fed in and what name resulted), not on which production
        # branch fired -- it exists so a refactor of the naming logic can't
        # silently make this fixture stop exercising the common-prefix branch
        # while the test keeps passing for the wrong reason.
        assert len(derived_names) == 2 and derived_names[0] == derived_names[1], (
            f"Fixture no longer produces identical names across categories (got {derived_names}); "
            "it no longer reaches the collision this test targets -- update the fixture."
        )
        assert "Subgroup" not in derived_names[0], (
            "Fixture drifted onto the positional fallback naming branch instead of "
            "the common-prefix branch this test is meant to exercise."
        )

        duplicate_ids = {sid for sid in emitted_ids if emitted_ids.count(sid) > 1}
        assert not duplicate_ids, (
            f"Duplicate subgraph id(s) {duplicate_ids} emitted across categories via the "
            f"common-prefix naming branch; a Mermaid graph with a repeated subgraph id "
            "fails to render (mmdc exits 1, mermaid.live fails too)."
        )


class TestGroupNodeBy:
    """
    Test _group_node_by method.

    Tests focus on grouping nodes by category with subcategory support.
    """

    @pytest.fixture
    def mock_config_loader(self):
        """Provide mock config loader."""
        return Mock(spec=MermaidConfigLoader)

    def test_group_components_by_category_without_subcategories(self, mock_config_loader):
        """
        Test grouping components by category without subcategories.

        Given: Components with different categories
        When: _group_node_by("components") is called
        Then: Components are grouped by category
        """
        components = {
            "comp1": ComponentNode(title="C1", category="componentsData", to_edges=[], from_edges=[]),
            "comp2": ComponentNode(title="C2", category="componentsData", to_edges=[], from_edges=[]),
            "comp3": ComponentNode(title="C3", category="componentsModel", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)

        groups, subcat_groups = graph._group_node_by("components", w_subcategories=False)

        assert "componentsData" in groups
        assert "componentsModel" in groups
        assert "comp1" in groups["componentsData"]
        assert "comp2" in groups["componentsData"]
        assert "comp3" in groups["componentsModel"]
        assert subcat_groups == {}

    def test_group_components_with_subcategories(self, mock_config_loader):
        """
        Test grouping components with subcategory processing.

        Given: Components with subcategories
        When: _group_node_by("components", w_subcategories=True) is called
        Then: Subcategory groups are created
        """
        components = {
            "comp1": ComponentNode(
                title="C1",
                category="componentsData",
                to_edges=[],
                from_edges=[],
                subcategory="Storage",
            ),
            "comp2": ComponentNode(
                title="C2",
                category="componentsData",
                to_edges=[],
                from_edges=[],
                subcategory="Processing",
            ),
            "comp3": ComponentNode(
                title="C3",
                category="componentsData",
                to_edges=[],
                from_edges=[],
            ),  # No subcategory
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)

        groups, subcat_groups = graph._group_node_by("components", w_subcategories=True)

        assert "componentsData" in groups
        assert "componentsData" in subcat_groups
        assert "Storage" in subcat_groups["componentsData"]
        assert "Processing" in subcat_groups["componentsData"]
        assert "comp1" in subcat_groups["componentsData"]["Storage"]
        assert "comp2" in subcat_groups["componentsData"]["Processing"]

    def test_group_node_by_invalid_node_type_raises_valueerror(self, mock_config_loader):
        """
        Test that invalid node_type raises ValueError.

        Given: Invalid node_type
        When: _group_node_by is called
        Then: ValueError is raised
        """
        components = {
            "comp1": ComponentNode(title="C1", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)

        with pytest.raises(ValueError, match="node_type must be 'components'"):
            graph._group_node_by("invalid_type")


class TestNestedSubgraphGeneration:
    """
    Test _get_nested_subgraph_new method.

    Tests focus on nested subgraph generation with subcategories.
    """

    @pytest.fixture
    def mock_config_loader(self):
        """Provide mock config loader."""
        return Mock(spec=MermaidConfigLoader)

    def test_nested_subgraph_with_empty_subcategories_returns_none(self, mock_config_loader):
        """
        Test that empty category_subgroups returns None.

        Given: Category with no subcategories
        When: _get_nested_subgraph_new is called
        Then: Returns None
        """
        components = {
            "comp1": ComponentNode(title="C1", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        graph.component_by_subcategory = {}  # No subcategories

        result = graph._get_nested_subgraph_new(["comp1"], "componentsData", "Data Components")

        assert result is None

    def test_nested_subgraph_with_components_without_subcategory(self, mock_config_loader):
        """
        Test nested subgraph includes components without subcategory.

        Given: Components with and without subcategories
        When: _get_nested_subgraph_new is called
        Then: Components without subcategory are included at top level
        """
        components = {
            "comp1": ComponentNode(
                title="C1",
                category="componentsData",
                to_edges=[],
                from_edges=[],
            ),  # No subcategory
            "comp2": ComponentNode(
                title="C2",
                category="componentsData",
                to_edges=[],
                from_edges=[],
                subcategory="Storage",
            ),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        graph.component_by_subcategory = {
            "componentsData": {
                "Storage": ["comp2"],
            }
        }

        result = graph._get_nested_subgraph_new(["comp1", "comp2"], "componentsData", "Data Components")

        assert result is not None
        result_str = "\n".join(result)
        # comp1 should be at top level (no nested subgroup)
        assert "comp1" in result_str

    def test_nested_subgraph_generates_subgroup_sections(self, mock_config_loader):
        """
        Test that subgroups are generated for subcategories.

        Given: Components with multiple subcategories
        When: _get_nested_subgraph_new is called
        Then: Subgroup sections are generated
        """
        components = {
            "comp1": ComponentNode(
                title="C1",
                category="componentsData",
                to_edges=[],
                from_edges=[],
                subcategory="Storage",
            ),
            "comp2": ComponentNode(
                title="C2",
                category="componentsData",
                to_edges=[],
                from_edges=[],
                subcategory="Processing",
            ),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        graph.component_by_subcategory = {
            "componentsData": {
                "Storage": ["comp1"],
                "Processing": ["comp2"],
            }
        }

        result = graph._get_nested_subgraph_new(["comp1", "comp2"], "componentsData", "Data Components")

        assert result is not None
        result_str = "\n".join(result)
        # Should contain subgroup keywords
        assert "subgraph" in result_str
        assert "end" in result_str

    def test_nested_subgraph_removes_empty_lines_at_end(self, mock_config_loader):
        """
        Test that empty lines are removed from subgroup sections.

        Given: Subgroup generation that produces empty lines
        When: _get_nested_subgraph_new is called
        Then: Empty lines at end of subgroup sections are removed
        """
        components = {
            "comp1": ComponentNode(
                title="C1",
                category="componentsData",
                to_edges=[],
                from_edges=[],
                subcategory="Storage",
            ),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        graph.component_by_subcategory = {
            "componentsData": {
                "Storage": ["comp1"],
            }
        }

        result = graph._get_nested_subgraph_new(["comp1"], "componentsData", "Data Components")

        assert result is not None
        # Check that we don't have consecutive empty lines at the end
        # The implementation removes empty line from subgroup sections
        assert result[-1] == ""  # Final empty line should be present
        if len(result) > 2:
            # But not duplicate empty lines
            assert not (result[-2] == "" and result[-3] == "")


class TestNodeStyling:
    """
    Test _get_node_style method.

    Tests focus on different style types and fallback mechanisms.
    """

    @pytest.fixture
    def mock_config_loader(self):
        """Provide mock config loader with category styles."""
        mock = Mock(spec=MermaidConfigLoader)
        mock.get_component_category_styles.return_value = {
            "componentsData": {
                "fill": "#fff5e6",
                "stroke": "#333333",
                "strokeWidth": "2px",
            },
            "componentsModel": {
                "fill": "#ffe6e6",
                "stroke": "#333333",
                "strokeWidth": "2px",
            },
        }
        return mock

    def test_get_node_style_component_category(self, mock_config_loader):
        """
        Test componentCategory style type.

        Given: Category config with style properties
        When: _get_node_style("componentCategory") is called
        Then: Returns formatted style string
        """
        components = {
            "comp1": ComponentNode(title="C1", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)

        category_config = {"fill": "#fff5e6", "stroke": "#333333", "strokeWidth": "2px"}
        style = graph._get_node_style("componentCategory", category_config=category_config)

        assert "fill:#fff5e6" in style
        assert "stroke:#333333" in style
        assert "stroke-width:2px" in style

    def test_get_node_style_unknown_type_returns_default(self, mock_config_loader):
        """
        Test that unknown style_type returns default style.

        Given: Unknown style_type
        When: _get_node_style is called
        Then: Returns default style
        """
        components = {
            "comp1": ComponentNode(title="C1", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)

        style = graph._get_node_style("unknownStyleType")

        assert "fill:#ffffff" in style  # Default fill
        assert "stroke:#333333" in style  # Default stroke
        assert "stroke-width:2px" in style


class TestToMermaid:
    """
    Test to_mermaid method.

    Tests focus on output formatting.
    """

    @pytest.fixture
    def mock_config_loader(self):
        """Provide mock config loader."""
        return Mock(spec=MermaidConfigLoader)

    def test_to_mermaid_markdown_format(self, mock_config_loader):
        """
        Test to_mermaid with markdown format.

        Given: BaseGraph with graph content
        When: to_mermaid("markdown") is called
        Then: Returns graph wrapped in markdown code fence
        """
        components = {
            "comp1": ComponentNode(title="C1", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        graph.graph = "graph TD\n    comp1[Component 1]"

        result = graph.to_mermaid(output_format="markdown")

        assert result.startswith("```mermaid\n")
        assert "graph TD" in result
        assert result.strip().endswith("```")

    def test_to_mermaid_raw_format(self, mock_config_loader):
        """
        Test to_mermaid with raw format.

        Given: BaseGraph with graph content
        When: to_mermaid(output_format not markdown) is called
        Then: Returns graph content without markdown wrapper
        """
        components = {
            "comp1": ComponentNode(title="C1", category="componentsData", to_edges=[], from_edges=[]),
        }
        graph = BaseGraph(components=components, config_loader=mock_config_loader)
        graph.graph = "graph TD\n    comp1[Component 1]"

        result = graph.to_mermaid(output_format="raw")

        assert not result.startswith("```")
        assert "graph TD" in result
        assert "comp1[Component 1]" in result

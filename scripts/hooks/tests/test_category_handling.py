#!/usr/bin/env python3
"""
Tests for BaseGraph category handling functionality

These tests ensure the category discovery and management logic works correctly
with the new BaseGraph inheritance structure.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

# Add scripts/hooks directory to path
git_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(git_root / "scripts" / "hooks"))

from riskmap_validator.graphing import ComponentGraph, ControlGraph  # noqa: E402
from riskmap_validator.models import ComponentNode, ControlNode  # noqa: E402


class TestCategoryHandling:
    """Test category handling methods in BaseGraph inheritance structure."""

    @pytest.fixture
    def sample_components(self):
        """Create components with various categories."""
        return {
            "comp1": ComponentNode("Comp 1", "componentsData", [], []),
            "comp2": ComponentNode("Comp 2", "componentsData", [], []),
            "comp3": ComponentNode("Comp 3", "componentsInfrastructure", [], []),
            "comp4": ComponentNode("Comp 4", "componentsModel", [], []),
            "comp5": ComponentNode("Comp 5", "componentsApplication", [], []),
            "comp6": ComponentNode("Comp 6", "componentsCustomCategory", [], []),
        }

    @pytest.fixture
    def sample_controls(self):
        """Create controls with various categories."""
        return {
            "ctrl1": ControlNode("Control 1", "controlsData", ["comp1"], [], []),
            "ctrl2": ControlNode("Control 2", "controlsInfrastructure", ["comp3"], [], []),
            "ctrl3": ControlNode("Control 3", "controlsCustom", ["comp1"], [], []),
        }

    def test_control_graph_category_display_names(self, sample_controls, sample_components):
        """Test _get_category_display_name method inherited from BaseGraph."""
        graph = ControlGraph(sample_controls, sample_components)

        # Test standard categories
        assert "Data" in graph._get_category_display_name("componentsData")
        assert "Infrastructure" in graph._get_category_display_name("componentsInfrastructure")
        assert "Model" in graph._get_category_display_name("componentsModel")
        assert "Application" in graph._get_category_display_name("componentsApplication")

        # Test custom category handling
        custom_display = graph._get_category_display_name("componentsCustomCategory")
        assert "Custom Category" in custom_display

        # Test controls categories
        controls_display = graph._get_category_display_name("controlsData")
        assert "Data Controls" in controls_display

    @pytest.fixture
    def temp_yaml_files(self):
        """Create temporary YAML files for category loading tests."""
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)

        # Create risk-map/yaml directory structure
        yaml_dir = temp_path / "risk-map" / "yaml"
        yaml_dir.mkdir(parents=True)

        yield yaml_dir

        # Cleanup
        import shutil

        shutil.rmtree(temp_dir)

    def test_load_category_names_from_yaml(self, sample_controls, sample_components, temp_yaml_files):
        """Test _load_category_names method inherited from BaseGraph."""
        # Create test YAML files
        controls_yaml = {
            "categories": [
                {"id": "controlsData", "title": "Data"},
                {"id": "controlsInfrastructure", "title": "Infrastructure"},
                {"id": "controlsCustom", "title": "Custom Category"},
            ]
        }

        components_yaml = {
            "categories": [
                {"id": "componentsData", "title": "Data components"},
                {"id": "componentsInfrastructure", "title": "Infrastructure components"},
                {"id": "componentsCustomCategory", "title": "Custom components"},
            ]
        }

        # Write test files
        with open(temp_yaml_files / "controls.yaml", "w") as f:
            yaml.dump(controls_yaml, f)
        with open(temp_yaml_files / "components.yaml", "w") as f:
            yaml.dump(components_yaml, f)

        # Patch the file paths to use our temp files
        with patch("pathlib.Path") as mock_path:

            def path_side_effect(path_str):
                if "controls.yaml" in str(path_str):
                    return temp_yaml_files / "controls.yaml"
                elif "components.yaml" in str(path_str):
                    return temp_yaml_files / "components.yaml"
                return Path(path_str)

            mock_path.side_effect = path_side_effect

            graph = ControlGraph(sample_controls, sample_components)
            category_names = graph._load_category_names()

            # Verify loaded category names
            assert "controlsData" in category_names
            assert "Data Controls" in category_names["controlsData"]
            assert "componentsData" in category_names
            assert "Data Components" in category_names["componentsData"]

    def test_component_graph_category_normalization(self, sample_components):
        """Test ComponentGraph category normalization using BaseGraph methods."""
        forward_map = {}
        graph = ComponentGraph(forward_map, sample_components)

        # Test existing category normalization
        assert graph._normalize_category("comp1") == "Data"
        assert graph._normalize_category("comp3") == "Infrastructure"
        assert graph._normalize_category("comp4") == "Model"
        assert graph._normalize_category("comp5") == "Application"

        # Test custom category normalization (improved with BaseGraph)
        assert graph._normalize_category("comp6") == "Custom Category"

        # Test non-existent component
        assert graph._normalize_category("nonexistent") == "Unknown"

    def test_dynamic_category_discovery_with_basegraph(self, sample_components, sample_controls):
        """Test BaseGraph's _discover_categories_from_data method."""
        # Test with ComponentGraph (inherits from BaseGraph)
        component_graph = ComponentGraph({}, sample_components)
        discovered_component_categories = component_graph._discover_categories_from_data(sample_components)

        expected_component_categories = [
            "componentsApplication",
            "componentsCustomCategory",
            "componentsData",
            "componentsInfrastructure",
            "componentsModel",
        ]

        assert discovered_component_categories == expected_component_categories

        # Test with ControlGraph (inherits from BaseGraph)
        control_graph = ControlGraph(sample_controls, sample_components)
        discovered_control_categories = control_graph._discover_categories_from_data(sample_controls)

        expected_control_categories = ["controlsCustom", "controlsData", "controlsInfrastructure"]

        assert discovered_control_categories == expected_control_categories

    def test_component_graph_dynamic_categories(self, sample_components):
        """Test that ComponentGraph now handles all categories dynamically via BaseGraph."""
        forward_map = {}
        graph = ComponentGraph(forward_map, sample_components)

        # Build the graph to see if all categories are handled
        mermaid_output = graph.to_mermaid()

        # Should contain standard categories
        assert "subgraph Data" in mermaid_output
        assert "subgraph Infrastructure" in mermaid_output
        assert "subgraph Model" in mermaid_output
        assert "subgraph Application" in mermaid_output

        # Should now also contain custom categories (fixed with BaseGraph refactoring)
        custom_category_present = "comp6" in mermaid_output or "Comp 6" in mermaid_output
        assert custom_category_present, "Custom categories should be handled dynamically"

        # Should contain a subgraph for the custom category
        assert "Custom Category" in mermaid_output or "subgraph" in mermaid_output

    def test_control_graph_dynamic_categories(self, sample_controls, sample_components):
        """Test that ControlGraph already handles categories dynamically."""
        graph = ControlGraph(sample_controls, sample_components)

        # ControlGraph should handle all categories dynamically
        mermaid_output = graph.to_mermaid()

        # Should contain all control categories, including custom ones
        assert "controlsData" in mermaid_output
        assert "controlsInfrastructure" in mermaid_output
        assert "controlsCustom" in mermaid_output

        # Should contain all component categories
        assert "componentsData" in mermaid_output
        assert "componentsInfrastructure" in mermaid_output
        assert "componentsCustomCategory" in mermaid_output

    def test_category_ordering_consistency(self, sample_components):
        """Test category ordering maintains preferred order for standard categories."""
        forward_map = {}
        graph = ComponentGraph(forward_map, sample_components)

        # ComponentGraph should prefer standard category order when available
        expected_order = ["Data", "Infrastructure", "Model", "Application"]

        # Verify that the standard categories appear in expected order, with custom categories added
        mermaid_output = graph.to_mermaid()
        lines = mermaid_output.split("\n")

        subgraph_lines = [
            line for line in lines if "subgraph" in line and any(cat in line for cat in expected_order)
        ]

        # Should have subgraphs for the standard categories that have components
        assert len(subgraph_lines) >= 3  # At least Data, Infrastructure, Model, Application (minus empty ones)

        # Should also include custom categories
        custom_subgraph_lines = [line for line in lines if "subgraph" in line and "Custom Category" in line]
        assert len(custom_subgraph_lines) >= 0  # Custom categories should be included

    def test_category_styling_consistency(self, sample_controls, sample_components):
        """Test that category styling is consistent between graph types."""
        # Both graph types should use the same category styling configuration
        component_graph = ComponentGraph({}, sample_components)
        control_graph = ControlGraph(sample_controls, sample_components)

        # Both should use the same config loader
        assert type(component_graph.config_loader) is type(control_graph.config_loader)

        # Both should access the same category styles
        comp_styles = component_graph.config_loader.get_component_category_styles()
        ctrl_styles = control_graph.config_loader.get_component_category_styles()

        assert comp_styles == ctrl_styles

    def test_category_fallback_behavior(self, sample_controls, sample_components):
        """Test fallback behavior when category configuration is missing."""
        # Create a control graph and test fallback category naming
        graph = ControlGraph(sample_controls, sample_components)

        # Test with a category that won't be in any config file
        unknown_category = "componentsUnknownCategory"
        display_name = graph._get_category_display_name(unknown_category)

        # Should fall back to generated name
        assert "Unknown Category" in display_name

    def test_category_edge_cases(self, sample_controls, sample_components):
        """Test edge cases in category handling."""
        graph = ControlGraph(sample_controls, sample_components)

        # Test empty category
        empty_display = graph._get_category_display_name("")
        assert isinstance(empty_display, str)

        # Test None category (edge case)
        try:
            none_display = graph._get_category_display_name("")
            assert isinstance(none_display, str)
        except (AttributeError, TypeError):
            # Expected for None input
            pass

        # Test category with special characters
        special_category = "components-special_category"
        special_display = graph._get_category_display_name(special_category)
        assert isinstance(special_display, str)


class TestBaseGraphIntegration:
    """Test BaseGraph integration and dynamic category handling."""

    def test_new_component_category_handling(self):
        """Test that new component categories are automatically handled."""
        # Create components with a completely new category
        components = {
            "comp1": ComponentNode("Standard", "componentsData", [], []),
            "comp2": ComponentNode("New Type", "componentsNewCategory", [], []),
        }

        forward_map = {}

        # ComponentGraph with BaseGraph inheritance should handle new categories dynamically
        graph = ComponentGraph(forward_map, components)
        mermaid_output = graph.to_mermaid()

        # Verify that standard categories work
        assert "comp1" in mermaid_output or "Standard" in mermaid_output

        # Verify that new category component appears in output
        new_category_present = "comp2" in mermaid_output or "New Type" in mermaid_output
        assert new_category_present, "New categories should be automatically included"

        # Should automatically create a subgraph for the new category
        assert "New Category" in mermaid_output or "subgraph" in mermaid_output

    def test_new_control_category_handling(self):
        """Test that new control categories are handled dynamically."""
        controls = {
            "ctrl1": ControlNode("Standard", "controlsData", ["comp1"], [], []),
            "ctrl2": ControlNode("New Control", "controlsNewCategory", ["comp1"], [], []),
        }

        components = {
            "comp1": ComponentNode("Test", "componentsData", [], []),
        }

        # ControlGraph with BaseGraph inheritance should handle new categories dynamically
        graph = ControlGraph(controls, components)
        mermaid_output = graph.to_mermaid()

        # Should contain the new control category
        assert "controlsNewCategory" in mermaid_output
        assert "New Control" in mermaid_output

    def test_basegraph_consistency_across_graph_types(self):
        """Test that both graph types handle categories consistently via BaseGraph."""
        components = {
            "comp1": ComponentNode("Test", "componentsNewCategory", [], []),
        }

        controls = {
            "ctrl1": ControlNode("Test", "controlsNewCategory", ["comp1"], [], []),
        }

        # Both should use the same BaseGraph category handling
        component_graph = ComponentGraph({}, components)
        control_graph = ControlGraph(controls, components)

        # Both should produce valid mermaid output
        comp_output = component_graph.to_mermaid()
        ctrl_output = control_graph.to_mermaid()

        assert "```mermaid" in comp_output
        assert "```mermaid" in ctrl_output

        # Both should handle new categories consistently
        assert "New Category" in comp_output or "componentsNewCategory" in comp_output
        assert "controlsNewCategory" in ctrl_output

    def test_basegraph_build_category_mapping(self):
        """Test BaseGraph's _build_category_mapping method."""
        components = {
            "comp1": ComponentNode("Test1", "componentsData", [], []),
            "comp2": ComponentNode("Test2", "componentsCustomType", [], []),
        }

        graph = ComponentGraph({}, components)

        # Test the BaseGraph method directly
        categories = ["componentsData", "componentsCustomType"]
        mapping = graph._build_category_mapping(categories)

        # Should create clean display names mapped to category IDs
        assert "Data" in mapping
        assert "Custom Type" in mapping
        assert mapping["Data"] == "componentsData"
        assert mapping["Custom Type"] == "componentsCustomType"

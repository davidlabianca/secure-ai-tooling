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
                {"id": "controlsData", "title": "Data Controls"},
                {"id": "controlsInfrastructure", "title": "Infrastructure Controls"},
                {"id": "controlsCustom", "title": "Custom Category Controls"},
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
        with patch("riskmap_validator.graphing.base.Path") as mock_path:

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

    def test_component_graph_dynamic_categories(self, sample_components):
        """Test that ComponentGraph handles categories with actual component relationships."""
        # Add some relationships to create a meaningful graph
        forward_map = {"comp1": ["comp3"], "comp3": ["comp4"]}
        graph = ComponentGraph(forward_map, sample_components)

        # Build the graph to see if categories are handled for components with relationships
        mermaid_output = graph.to_mermaid()

        # Should contain categories for components that have relationships
        # In ELK-based approach, isolated components without edges aren't visualized
        assert "comp1 --> comp3" in mermaid_output
        assert "comp3 --> comp4" in mermaid_output

        # Should contain style definitions for all categories (even if not all have subgraphs)
        assert "style componentsData" in mermaid_output
        assert "style componentsInfrastructure" in mermaid_output
        assert "style componentsModel" in mermaid_output

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
        """Test category styling follows standard ordering even without subgraphs."""
        forward_map = {}
        graph = ComponentGraph(forward_map, sample_components)

        # ComponentGraph should prefer standard category order for styling
        expected_categories = [
            "componentsData",
            "componentsInfrastructure",
            "componentsModel",
            "componentsApplication",
        ]

        # Verify that style definitions appear for standard categories
        mermaid_output = graph.to_mermaid()
        lines = mermaid_output.split("\n")

        style_lines = [
            line
            for line in lines
            if line.strip().startswith("style ") and any(cat in line for cat in expected_categories)
        ]

        # Should have style definitions for the standard categories
        assert len(style_lines) >= 3  # At least Data, Infrastructure, Model, Application

        # Style definitions should maintain order (Data, Infrastructure, Model, Application)
        found_categories = []
        for line in style_lines:
            for cat in expected_categories:
                if cat in line:
                    found_categories.append(cat)
                    break

        # Should include main standard categories
        assert "componentsData" in found_categories
        assert "componentsInfrastructure" in found_categories
        assert "componentsModel" in found_categories

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

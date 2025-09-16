#!/usr/bin/env python3
"""
Tests for MermaidConfigLoader

This test suite ensures the configuration loading system works correctly
before and after refactoring. Critical for ensuring BaseGraph refactoring
doesn't break existing functionality.
"""

import sys
import tempfile
from pathlib import Path

import pytest
import yaml

# Add scripts/hooks directory to path
git_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(git_root / "scripts" / "hooks"))

from riskmap_validator.graphing import MermaidConfigLoader  # noqa: E402


class TestMermaidConfigLoader:
    """Test MermaidConfigLoader functionality before refactoring."""

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file for testing."""
        temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
        yield Path(temp_file.name)
        Path(temp_file.name).unlink(missing_ok=True)

    @pytest.fixture
    def valid_config_data(self):
        """Create valid configuration data."""
        return {
            "version": "1.0.0",
            "foundation": {
                "colors": {
                    "primary": "#4285f4",
                    "success": "#34a853",
                }
            },
            "sharedElements": {
                "cssClasses": {
                    "hidden": "display: none;",
                    "allControl": "stroke:#4285f4,stroke-width:2px,stroke-dasharray: 5 5",
                },
                "componentCategories": {
                    "componentsData": {
                        "fill": "#fff5e6",
                        "stroke": "#333333",
                        "strokeWidth": "2px",
                    }
                },
            },
            "graphTypes": {
                "component": {
                    "direction": "TD",
                    "flowchartConfig": {"nodeSpacing": 25, "rankSpacing": 30},
                },
                "control": {
                    "direction": "LR",
                    "flowchartConfig": {"nodeSpacing": 25, "rankSpacing": 30},
                    "specialStyling": {
                        "componentsContainer": {
                            "fill": "#f0f0f0",
                            "stroke": "#666666",
                        },
                        "edgeStyles": {
                            "allControlEdges": {"stroke": "#4285f4"},
                            "multiEdgeStyles": [{"stroke": "#9c27b0"}],
                        },
                    },
                },
            },
        }

    def create_config_file(self, file_path: Path, data: dict):
        """Helper to create config file with given data."""
        with open(file_path, "w") as f:
            yaml.dump(data, f)

    def test_singleton_pattern(self, temp_config_file, valid_config_data):
        """Test that singleton pattern works correctly."""
        self.create_config_file(temp_config_file, valid_config_data)

        loader1 = MermaidConfigLoader.get_instance(temp_config_file)
        loader2 = MermaidConfigLoader.get_instance(temp_config_file)
        loader3 = MermaidConfigLoader.get_instance()  # Default config

        # Same file should return same instance
        assert loader1 is loader2
        # Different file should return different instance
        assert loader1 is not loader3

    def test_load_valid_config(self, temp_config_file, valid_config_data):
        """Test loading valid configuration."""
        self.create_config_file(temp_config_file, valid_config_data)

        loader = MermaidConfigLoader(temp_config_file)
        success, error = loader.get_load_status()

        assert success is True
        assert error is None

    def test_load_missing_config_file(self):
        """Test loading non-existent configuration file."""
        missing_file = Path("nonexistent_config.yaml")
        loader = MermaidConfigLoader(missing_file)
        success, error = loader.get_load_status()

        assert success is False
        assert "Configuration file not found" in error

    def test_load_invalid_yaml(self, temp_config_file):
        """Test loading invalid YAML configuration."""
        temp_config_file.write_text("invalid: yaml: [content")

        loader = MermaidConfigLoader(temp_config_file)
        success, error = loader.get_load_status()

        assert success is False
        assert "YAML parsing error" in error

    def test_load_invalid_structure(self, temp_config_file):
        """Test loading YAML with invalid structure."""
        invalid_data = {"invalid": "structure"}
        self.create_config_file(temp_config_file, invalid_data)

        loader = MermaidConfigLoader(temp_config_file)
        success, error = loader.get_load_status()

        assert success is False
        assert "missing required keys" in error

    def test_emergency_defaults_fallback(self):
        """Test that emergency defaults are used when config fails."""
        missing_file = Path("nonexistent.yaml")
        loader = MermaidConfigLoader(missing_file)

        # Should fall back to emergency defaults
        css_classes = loader.get_css_classes()
        assert "hidden" in css_classes
        assert "allControl" in css_classes

        categories = loader.get_component_category_styles()
        assert "componentsData" in categories
        assert "componentsInfrastructure" in categories

    def test_get_safe_value_with_valid_config(self, temp_config_file, valid_config_data):
        """Test _get_safe_value with valid configuration."""
        self.create_config_file(temp_config_file, valid_config_data)

        loader = MermaidConfigLoader(temp_config_file)

        # Test nested value retrieval
        hidden_class = loader._get_safe_value("sharedElements", "cssClasses", "hidden")
        assert hidden_class == "display: none;"

        # Test missing value with default
        missing_value = loader._get_safe_value("nonexistent", "path", default="default_value")
        assert missing_value == "default_value"

    def test_get_graph_config(self, temp_config_file, valid_config_data):
        """Test graph configuration retrieval."""
        self.create_config_file(temp_config_file, valid_config_data)

        loader = MermaidConfigLoader(temp_config_file)

        # Test component graph config
        config, preamble = loader.get_graph_config("component")
        assert config["direction"] == "TD"
        assert isinstance(preamble, list)
        assert len(preamble) > 0
        assert "```mermaid" in preamble

        # Test control graph config
        config, preamble = loader.get_graph_config("control")
        assert config["direction"] == "LR"
        assert "specialStyling" in config

    def test_create_flowchart_preamble(self, temp_config_file, valid_config_data):
        """Test flowchart preamble generation."""
        self.create_config_file(temp_config_file, valid_config_data)

        loader = MermaidConfigLoader(temp_config_file)
        graph_config = {"direction": "TD", "flowchartConfig": {"nodeSpacing": 25}}

        preamble = loader._create_flowchart_preamble(graph_config)

        assert isinstance(preamble, list)
        assert "```mermaid" in preamble
        assert "graph TD" in preamble
        assert any("classDef hidden" in line for line in preamble)
        assert any("classDef allControl" in line for line in preamble)

    def test_get_css_classes(self, temp_config_file, valid_config_data):
        """Test CSS classes retrieval."""
        self.create_config_file(temp_config_file, valid_config_data)

        loader = MermaidConfigLoader(temp_config_file)
        css_classes = loader.get_css_classes()

        assert isinstance(css_classes, dict)
        assert "hidden" in css_classes
        assert "allControl" in css_classes
        assert css_classes["hidden"] == "display: none;"

    def test_get_component_category_styles(self, temp_config_file, valid_config_data):
        """Test component category styles retrieval."""
        self.create_config_file(temp_config_file, valid_config_data)

        loader = MermaidConfigLoader(temp_config_file)
        categories = loader.get_component_category_styles()

        assert isinstance(categories, dict)
        assert "componentsData" in categories
        assert categories["componentsData"]["fill"] == "#fff5e6"

    def test_get_control_edge_styles(self, temp_config_file, valid_config_data):
        """Test control edge styles retrieval."""
        self.create_config_file(temp_config_file, valid_config_data)

        loader = MermaidConfigLoader(temp_config_file)
        edge_styles = loader.get_control_edge_styles()

        assert isinstance(edge_styles, dict)
        assert "allControlEdges" in edge_styles
        assert "multiEdgeStyles" in edge_styles

    def test_get_components_container_style(self, temp_config_file, valid_config_data):
        """Test components container style retrieval."""
        self.create_config_file(temp_config_file, valid_config_data)

        loader = MermaidConfigLoader(temp_config_file)
        container_style = loader.get_components_container_style()

        assert isinstance(container_style, dict)
        assert "fill" in container_style
        assert container_style["fill"] == "#f0f0f0"

    def test_cache_clearing(self, temp_config_file, valid_config_data):
        """Test cache clearing functionality."""
        self.create_config_file(temp_config_file, valid_config_data)

        loader = MermaidConfigLoader(temp_config_file)

        # Load config first
        success1, _ = loader.get_load_status()
        assert success1 is True

        # Clear cache
        loader.clear_cache()

        # Should reload on next access
        success2, _ = loader.get_load_status()
        assert success2 is True

    def test_invalid_graph_config_fallback(self, temp_config_file, valid_config_data):
        """Test fallback behavior for invalid graph configuration."""
        self.create_config_file(temp_config_file, valid_config_data)

        loader = MermaidConfigLoader(temp_config_file)

        # Test with non-existent graph type
        config, preamble = loader.get_graph_config("nonexistent")
        assert config == {}
        assert preamble == []

    def test_emergency_defaults_structure(self):
        """Test that emergency defaults have required structure."""
        loader = MermaidConfigLoader(Path("nonexistent.yaml"))
        emergency_defaults = loader._get_emergency_defaults()

        # Check required top-level keys
        required_keys = ["version", "foundation", "sharedElements", "graphTypes"]
        for key in required_keys:
            assert key in emergency_defaults

        # Check foundation structure
        assert "colors" in emergency_defaults["foundation"]

        # Check shared elements structure
        assert "cssClasses" in emergency_defaults["sharedElements"]
        assert "componentCategories" in emergency_defaults["sharedElements"]

        # Check graph types structure
        assert "component" in emergency_defaults["graphTypes"]
        assert "control" in emergency_defaults["graphTypes"]


class TestMermaidConfigLoaderIntegration:
    """Test integration between MermaidConfigLoader and graph classes."""

    def test_component_graph_uses_config_loader(self):
        """Test that ComponentGraph properly uses MermaidConfigLoader."""
        from riskmap_validator.graphing import ComponentGraph
        from riskmap_validator.models import ComponentNode

        components = {"comp1": ComponentNode("Test", "componentsData", [], [])}
        forward_map = {}

        # Should work with default config loader
        graph = ComponentGraph(forward_map, components)
        assert hasattr(graph, "config_loader")
        assert isinstance(graph.config_loader, MermaidConfigLoader)

        # Should work with custom config loader
        custom_loader = MermaidConfigLoader()
        graph_custom = ComponentGraph(forward_map, components, config_loader=custom_loader)
        assert graph_custom.config_loader is custom_loader

    def test_control_graph_uses_config_loader(self):
        """Test that ControlGraph properly uses MermaidConfigLoader."""
        from riskmap_validator.graphing import ControlGraph
        from riskmap_validator.models import ComponentNode, ControlNode

        controls = {"ctrl1": ControlNode("Test", "controlsData", ["comp1"], [], [])}
        components = {"comp1": ComponentNode("Test", "componentsData", [], [])}

        # Should work with default config loader
        graph = ControlGraph(controls, components)
        assert hasattr(graph, "config_loader")
        assert isinstance(graph.config_loader, MermaidConfigLoader)

        # Should work with custom config loader
        custom_loader = MermaidConfigLoader()
        graph_custom = ControlGraph(controls, components, config_loader=custom_loader)
        assert graph_custom.config_loader is custom_loader

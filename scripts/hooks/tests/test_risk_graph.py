"""
Tests for RiskGraph - Risk-to-Control-to-Component Visualization

This test suite validates the RiskGraph functionality that generates
three-layer Mermaid visualizations showing risk mitigation chains
from security risks through controls to AI system components.

Test Coverage:
==============
1. Initialization & Composition:
   - RiskGraph composition with ControlGraph
   - Risk-to-control mapping generation
   - Risk categorization and organization
   - Configuration loader integration

2. Graph Generation:
   - Three-layer structure validation
   - Risk subgraph creation
   - Control and component layer reuse
   - Edge styling and formatting

3. Integration Testing:
   - Real data compatibility
   - Configuration-driven styling
   - Debug mode functionality
   - Error handling and fallbacks

4. Edge Cases:
   - Risks with no mitigating controls
   - Controls with no risk mappings
   - Missing configuration scenarios
   - Invalid data handling

The tests use the shared fixtures from conftest.py and focus specifically
on RiskGraph functionality while ensuring integration with existing
ControlGraph optimizations.
"""

from unittest.mock import MagicMock, patch

from riskmap_validator.graphing.base import MermaidConfigLoader
from riskmap_validator.graphing.risks_graph import RiskGraph
from riskmap_validator.models import ComponentNode, ControlNode, RiskNode


class TestRiskGraphInitialization:
    """Test RiskGraph initialization and composition patterns."""

    def test_basic_initialization(self, sample_risks, sample_controls, sample_components):
        """Test basic RiskGraph initialization with valid data."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)

        # Verify composition with ControlGraph
        assert hasattr(risk_graph, "control_graph")
        assert risk_graph.control_graph is not None

        # Verify risk-specific attributes
        assert hasattr(risk_graph, "risk_to_control_map")
        assert hasattr(risk_graph, "risk_by_category")
        assert len(risk_graph.risks) == len(sample_risks)

    def test_initialization_with_debug(self, sample_risks, sample_controls, sample_components):
        """Test RiskGraph initialization with debug mode enabled."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components, debug=True)

        assert risk_graph.debug is True
        assert risk_graph.control_graph.debug is True

    def test_initialization_with_custom_config(self, sample_risks, sample_controls, sample_components):
        """Test RiskGraph initialization with custom configuration loader."""
        config_loader = MermaidConfigLoader()
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components, config_loader=config_loader)

        assert risk_graph.config_loader is config_loader
        assert risk_graph.control_graph.config_loader is config_loader

    def test_empty_data_initialization(self):
        """Test RiskGraph initialization with empty data."""
        risk_graph = RiskGraph({}, {}, {})

        assert len(risk_graph.risks) == 0
        assert len(risk_graph.risk_to_control_map) == 0
        assert len(risk_graph.risk_by_category["risks"]) == 0


class TestRiskControlMapping:
    """Test risk-to-control mapping functionality."""

    def test_basic_risk_control_mapping(self, sample_risks, sample_controls, sample_components):
        """Test basic risk-to-control mapping generation."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)

        # Verify mappings exist for all risks
        assert "DP" in risk_graph.risk_to_control_map
        assert "PIJ" in risk_graph.risk_to_control_map
        assert "MST" in risk_graph.risk_to_control_map
        assert "MDT" in risk_graph.risk_to_control_map

        # Verify specific mappings
        dp_controls = risk_graph.risk_to_control_map["DP"]
        assert "controlInputValidation" in dp_controls

        mst_controls = risk_graph.risk_to_control_map["MST"]
        assert "controlModelIntegrity" in mst_controls

    def test_universal_control_mapping(self, sample_risks, sample_components):
        """Test mapping for controls that apply to all risks."""
        # Create control that applies to all risks
        universal_control = {
            "controlUniversalSecurity": ControlNode(
                title="Universal Security",
                category="controlsGovernance",
                components=["all"],
                risks=["all"],
                personas=["personaModelCreator"],
            )
        }

        risk_graph = RiskGraph(sample_risks, universal_control, sample_components)

        # All risks should have the universal control
        for risk_id in sample_risks.keys():
            assert "controlUniversalSecurity" in risk_graph.risk_to_control_map[risk_id]

    def test_no_risk_control_mapping(self, sample_risks, sample_components):
        """Test mapping for controls that apply to no risks."""
        # Create control with no risk mappings
        no_risk_control = {
            "controlNoRisks": ControlNode(
                title="No Risk Control",
                category="controlsData",
                components=["componentDataSources"],
                risks=["none"],
                personas=["personaModelCreator"],
            )
        }

        risk_graph = RiskGraph(sample_risks, no_risk_control, sample_components)

        # No risks should map to this control
        for risk_controls in risk_graph.risk_to_control_map.values():
            assert "controlNoRisks" not in risk_controls

    def test_orphaned_risk_mapping(self, sample_components):
        """Test risk with no mitigating controls."""
        orphaned_risk = {"OrphanRisk": RiskNode(title="Orphaned Risk", category="risks")}

        # Controls without universal "all" control to create truly orphaned risk
        limited_controls = {
            "controlInputValidation": ControlNode(
                title="Input Validation",
                category="controlsData",
                components=["componentDataSources", "componentDataValidation"],
                risks=["DP", "PIJ"],
                personas=["personaModelCreator"],
            )
        }

        risk_graph = RiskGraph(orphaned_risk, limited_controls, sample_components)

        # Orphaned risk should have empty control list
        assert risk_graph.risk_to_control_map["OrphanRisk"] == []

    def test_control_list_sorting(self, sample_components):
        """Test that control lists are sorted consistently."""
        # Create risks and controls with predictable alphabetical order
        risks = {"TestRisk": RiskNode(title="Test Risk", category="risks")}
        controls = {
            "controlZeta": ControlNode("Zeta Control", "controlsData", ["componentDataSources"], ["TestRisk"], []),
            "controlAlpha": ControlNode(
                "Alpha Control", "controlsData", ["componentDataSources"], ["TestRisk"], []
            ),
            "controlBeta": ControlNode("Beta Control", "controlsData", ["componentDataSources"], ["TestRisk"], []),
        }

        risk_graph = RiskGraph(risks, controls, sample_components)

        # Controls should be sorted alphabetically
        test_risk_controls = risk_graph.risk_to_control_map["TestRisk"]
        assert test_risk_controls == ["controlAlpha", "controlBeta", "controlZeta"]


class TestRiskCategorization:
    """Test risk categorization functionality."""

    def test_default_risk_categorization(self, sample_risks, sample_controls, sample_components):
        """Test default risk categorization (all risks in 'risks' category)."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)

        # All risks should be in 'risks' category
        assert "risks" in risk_graph.risk_by_category
        risks_in_category = risk_graph.risk_by_category["risks"]

        # All sample risks should be present
        for risk_id in sample_risks.keys():
            assert risk_id in risks_in_category

    def test_empty_risk_categorization(self, sample_controls, sample_components):
        """Test categorization with no risks."""
        risk_graph = RiskGraph({}, sample_controls, sample_components)

        assert "risks" in risk_graph.risk_by_category
        assert risk_graph.risk_by_category["risks"] == []


class TestGraphGeneration:
    """Test Mermaid graph generation functionality."""

    def test_basic_graph_generation(self, sample_risks, sample_controls, sample_components):
        """Test basic three-layer graph generation."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)
        mermaid_output = risk_graph.to_mermaid()

        # Verify basic Mermaid structure
        assert mermaid_output.startswith("```mermaid")
        assert mermaid_output.endswith("```")
        assert "graph LR" in mermaid_output

        # Verify three-layer structure
        assert 'subgraph risks ["Risks"]' in mermaid_output
        assert "controlsData" in mermaid_output  # Control subgraphs
        assert "subgraph components" in mermaid_output  # Component container

    def test_risk_subgraph_content(self, sample_risks, sample_controls, sample_components):
        """Test risk subgraph contains expected risks."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)
        mermaid_output = risk_graph.to_mermaid()

        # Verify all risks appear in the graph
        assert "DP[Data Poisoning]" in mermaid_output
        assert "PIJ[Prompt Injection]" in mermaid_output
        assert "MST[Model Source Tampering]" in mermaid_output
        assert "MDT[Model Deployment Tampering]" in mermaid_output

    def test_risk_control_edges(self, sample_risks, sample_controls, sample_components):
        """Test risk-to-control edges are generated."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)
        mermaid_output = risk_graph.to_mermaid()

        # Verify risk-to-control edges
        assert "DP --> controlInputValidation" in mermaid_output
        assert "PIJ --> controlInputValidation" in mermaid_output
        assert "MST --> controlModelIntegrity" in mermaid_output
        assert "MDT --> controlModelIntegrity" in mermaid_output

    def test_edge_styling(self, sample_risks, sample_controls, sample_components):
        """Test edge styling is applied correctly."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)
        mermaid_output = risk_graph.to_mermaid()

        # Verify edge styling section exists
        assert "%% Edge styling" in mermaid_output
        assert "linkStyle" in mermaid_output

        # Verify risk-control edge styling
        assert "stroke:#e91e63" in mermaid_output  # Pink risk edges

    def test_node_styling(self, sample_risks, sample_controls, sample_components):
        """Test node styling is applied correctly."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)
        mermaid_output = risk_graph.to_mermaid()

        # Verify node styling section exists
        assert "%% Node style definitions" in mermaid_output

        # Verify risk category styling
        assert "style risks" in mermaid_output
        assert "fill:#ffeef0" in mermaid_output  # Risk category fill

    def test_debug_mode_output(self, sample_risks, sample_controls, sample_components):
        """Test debug mode includes additional comments."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components, debug=True)
        mermaid_output = risk_graph.to_mermaid()

        # Verify debug comments are present
        assert "%% DEBUG:" in mermaid_output
        assert "risk mitigation" in mermaid_output

    def test_orphaned_risk_handling(self, sample_components):
        """Test handling of risks with no mitigating controls."""
        orphaned_risk = {"OrphanRisk": RiskNode(title="Orphaned Risk", category="risks")}

        # Controls without universal "all" control to create truly orphaned risk
        limited_controls = {
            "controlInputValidation": ControlNode(
                title="Input Validation",
                category="controlsData",
                components=["componentDataSources", "componentDataValidation"],
                risks=["DP", "PIJ"],
                personas=["personaModelCreator"],
            )
        }

        risk_graph = RiskGraph(orphaned_risk, limited_controls, sample_components, debug=True)
        mermaid_output = risk_graph.to_mermaid()

        # Orphaned risk should appear in subgraph but have no edges
        assert "OrphanRisk[Orphaned Risk]" in mermaid_output
        assert "OrphanRisk -->" not in mermaid_output

        # Debug mode should note the skip
        assert "no mitigating controls" in mermaid_output

    def test_control_graph_integration(self, sample_risks, sample_controls, sample_components):
        """Test integration with ControlGraph functionality."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)
        mermaid_output = risk_graph.to_mermaid()

        # Verify control-to-component relationships are preserved
        # Universal control should map to components container
        assert "controlUniversalSecurity -.-> components" in mermaid_output

        # Regular control mappings should be present
        control_lines = [
            line
            for line in mermaid_output.split("\n")
            if "-->" in line and "control" in line and "component" in line
        ]
        assert len(control_lines) > 0


class TestConfigurationIntegration:
    """Test integration with MermaidConfigLoader."""

    def test_configuration_loading(self, sample_risks, sample_controls, sample_components):
        """Test configuration loading for risk graphs."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)

        # Verify configuration is loaded
        config, preamble = risk_graph.config_loader.get_graph_config("risk")
        assert config["direction"] == "LR"
        assert "graph LR" in preamble[1]

    def test_risk_category_styling(self, sample_risks, sample_controls, sample_components):
        """Test risk category styling configuration."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)

        risk_styles = risk_graph.config_loader.get_risk_category_styles()
        assert "risks" in risk_styles
        assert "fill" in risk_styles["risks"]
        assert "stroke" in risk_styles["risks"]

    def test_risk_edge_styling(self, sample_risks, sample_controls, sample_components):
        """Test risk edge styling configuration."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)

        edge_styles = risk_graph.config_loader.get_risk_edge_styles()
        assert "riskControlEdges" in edge_styles
        assert "allControlEdges" in edge_styles
        assert "multiEdgeStyles" in edge_styles


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_risk_data(self, sample_controls, sample_components):
        """Test handling of invalid risk data."""
        # This should not raise an exception
        risk_graph = RiskGraph(None, sample_controls, sample_components)
        assert risk_graph.risks is None

    def test_missing_config_fallback(self, sample_risks, sample_controls, sample_components):
        """Test fallback behavior when configuration is missing."""
        # Mock config loader to return empty config
        with patch("riskmap_validator.graphing.base.MermaidConfigLoader") as mock_loader:
            mock_instance = MagicMock()
            mock_instance.get_risk_category_styles.return_value = {}
            mock_instance.get_risk_edge_styles.return_value = {}
            mock_instance.get_graph_config.return_value = []  # This triggers the fallback
            mock_instance.get_components_container_style.return_value = {}
            mock_loader.return_value = mock_instance

            risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)
            mermaid_output = risk_graph.to_mermaid()

            # Should still generate valid output with fallbacks
            assert "graph LR" in mermaid_output
            assert "classDef hidden display: none;" in mermaid_output

    def test_large_dataset_performance(self):
        """Test performance with larger datasets."""
        # Create larger test dataset
        large_risks = {f"risk{i}": RiskNode(f"Risk {i}", "risks") for i in range(50)}
        large_controls = {
            f"control{i}": ControlNode(
                f"Control {i}",
                "controlsData",
                [f"component{i % 10}"],
                [f"risk{j}" for j in range(i * 3, min((i + 1) * 3, 50))],
                ["persona1"],
            )
            for i in range(30)
        }
        large_components = {
            f"component{i}": ComponentNode(f"Component {i}", "componentsData", [], []) for i in range(10)
        }

        risk_graph = RiskGraph(large_risks, large_controls, large_components)
        mermaid_output = risk_graph.to_mermaid()

        # Should handle large datasets without issues
        assert len(mermaid_output) > 1000  # Substantial output
        assert mermaid_output.count("-->") > 50  # Many relationships


class TestCompositionPattern:
    """Test the composition pattern with ControlGraph."""

    def test_control_graph_delegation(self, sample_risks, sample_controls, sample_components):
        """Test that control-component logic is properly delegated."""
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)

        # Verify ControlGraph methods are accessible
        assert hasattr(risk_graph.control_graph, "control_to_component_map")
        assert hasattr(risk_graph.control_graph, "component_by_category")

        # Verify optimization algorithms are applied
        assert len(risk_graph.control_graph.control_to_component_map) > 0

    def test_control_graph_consistency(self, sample_risks, sample_controls, sample_components):
        """Test consistency between standalone ControlGraph and composed version."""
        from riskmap_validator.graphing.controls_graph import ControlGraph

        # Create standalone ControlGraph
        standalone_control_graph = ControlGraph(sample_controls, sample_components)

        # Create RiskGraph with composed ControlGraph
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components)

        # Compare key mappings for consistency
        assert (
            standalone_control_graph.control_to_component_map == risk_graph.control_graph.control_to_component_map
        )
        assert standalone_control_graph.component_by_category == risk_graph.control_graph.component_by_category

    def test_config_sharing(self, sample_risks, sample_controls, sample_components):
        """Test that configuration is properly shared with composed ControlGraph."""
        config_loader = MermaidConfigLoader()
        risk_graph = RiskGraph(sample_risks, sample_controls, sample_components, config_loader=config_loader)

        # Both should use the same config loader instance
        assert risk_graph.config_loader is config_loader
        assert risk_graph.control_graph.config_loader is config_loader


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_real_world_scenario(self):
        """Test with realistic risk-control-component relationships."""
        # Create realistic scenario data
        risks = {
            "DataPoisoning": RiskNode("Data Poisoning Attack", "risks"),
            "ModelTheft": RiskNode("Model Intellectual Property Theft", "risks"),
            "PromptInjection": RiskNode("Malicious Prompt Injection", "risks"),
        }

        controls = {
            "InputValidation": ControlNode(
                "Input Validation and Sanitization",
                "controlsData",
                ["DataIngestion", "DataPreprocessing"],
                ["DataPoisoning", "PromptInjection"],
                ["ModelCreator"],
            ),
            "ModelSecurity": ControlNode(
                "Model Security Controls",
                "controlsModel",
                ["ModelTraining", "ModelDeployment"],
                ["ModelTheft"],
                ["ModelCreator", "ModelConsumer"],
            ),
            "UniversalSecurity": ControlNode(
                "Universal Security Framework",
                "controlsGovernance",
                ["all"],
                ["all"],
                ["ModelCreator", "ModelConsumer"],
            ),
        }

        components = {
            "DataIngestion": ComponentNode("Data Ingestion", "componentsData", ["DataPreprocessing"], []),
            "DataPreprocessing": ComponentNode(
                "Data Preprocessing", "componentsData", ["ModelTraining"], ["DataIngestion"]
            ),
            "ModelTraining": ComponentNode(
                "Model Training", "componentsModel", ["ModelDeployment"], ["DataPreprocessing"]
            ),
            "ModelDeployment": ComponentNode(
                "Model Deployment", "componentsInfrastructure", [], ["ModelTraining"]
            ),
        }

        risk_graph = RiskGraph(risks, controls, components)
        mermaid_output = risk_graph.to_mermaid()

        # Verify complete three-layer structure
        assert "DataPoisoning[Data Poisoning Attack]" in mermaid_output
        assert "InputValidation[Input Validation and Sanitization]" in mermaid_output
        assert "DataIngestion[Data Ingestion]" in mermaid_output

        # Verify risk-control relationships
        assert "DataPoisoning --> InputValidation" in mermaid_output
        assert "ModelTheft --> ModelSecurity" in mermaid_output

        # Verify universal mappings
        assert "UniversalSecurity -.-> components" in mermaid_output

    def test_minimal_scenario(self):
        """Test with minimal data set."""
        risks = {"MinimalRisk": RiskNode("Minimal Risk", "risks")}
        controls = {
            "MinimalControl": ControlNode(
                "Minimal Control", "controlsData", ["MinimalComponent"], ["MinimalRisk"], ["persona"]
            )
        }
        components = {"MinimalComponent": ComponentNode("Minimal Component", "componentsData", [], [])}

        risk_graph = RiskGraph(risks, controls, components)
        mermaid_output = risk_graph.to_mermaid()

        # Should generate valid minimal graph
        assert "MinimalRisk[Minimal Risk]" in mermaid_output
        assert "MinimalRisk --> MinimalControl" in mermaid_output
        # ControlGraph optimization maps to category when it contains all components in that category
        assert "MinimalControl --> componentsData" in mermaid_output

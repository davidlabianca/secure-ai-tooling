"""
Risk-to-control-to-component visualization for CoSAI Risk Map.

Generates three-layer Mermaid graphs (Risks → Controls → Components).
Reuses ControlGraph functionality through composition to avoid code duplication.
"""

from ..models import ComponentNode, ControlNode, RiskNode
from .base import BaseGraph, MermaidConfigLoader
from .controls_graph import ControlGraph


class RiskGraph(BaseGraph):
    """
    Generates three-layer Mermaid graphs for risk-to-control-to-component relationships.

    Uses composition with ControlGraph to reuse control-component optimizations.
    Adds risk-to-control mapping layer on top.

    Attributes:
        risks: Risk ID to RiskNode mappings
        control_graph: Composed ControlGraph for control-component functionality
        risk_to_control_map: Risk-to-control mappings
        risk_by_category: Risks grouped by category
    """

    def __init__(
        self,
        risks: dict[str, RiskNode],
        controls: dict[str, ControlNode],
        components: dict[str, ComponentNode],
        debug: bool = False,
        config_loader: MermaidConfigLoader = None,
    ):
        """
        Initialize with risks, controls, and components data.

        Process sequence:
        1. Create composed ControlGraph for control-component functionality
        2. Build risk-to-control mappings
        3. Group risks by category
        """
        super().__init__(components=components, controls=controls, config_loader=config_loader)
        self.risks = risks
        self.debug = debug

        # Compose with ControlGraph to reuse all control-component optimizations
        self.control_graph = ControlGraph(controls, components, debug=debug, config_loader=self.config_loader)

        # Build risk mappings
        self.risk_to_control_map = self._build_risk_control_mapping()
        self.risk_by_category = self._group_risks_by_category()
        self.graph = self.build_risk_control_component_graph()


    def _build_risk_control_mapping(self) -> dict[str, list[str]]:
        """
        Build risk-to-control mappings.

        Creates reverse mapping from controls→risks to risks→controls.
        Handles "all" and "none" control mappings.

        Returns:
            Dict mapping risk IDs to lists of control IDs that mitigate them
        """
        mapping = {}

        # Handle None risks data
        if self.risks is None:
            return mapping

        # Initialize mapping for all risks
        for risk_id in self.risks.keys():
            mapping[risk_id] = []

        # Create reverse mapping: controls→risks becomes risks→controls
        for control_id, control in self.controls.items():
            if control.risks == ["all"]:
                # Control mitigates all risks
                for risk_id in mapping.keys():
                    mapping[risk_id].append(control_id)
            elif control.risks == ["none"] or not control.risks:
                # Control mitigates no risks
                continue
            else:
                # Control mitigates specific risks
                for risk_id in control.risks:
                    if risk_id in mapping:
                        mapping[risk_id].append(control_id)

        # Sort control lists for consistent output
        for risk_id in mapping:
            mapping[risk_id] = sorted(mapping[risk_id])

        return mapping

    def _group_risks_by_category(self) -> dict[str, list[str]]:
        """
        Group risks by category.

        Currently all risks go into single "risks" category.
        Prepared for future risk categorization.

        Returns:
            Dict mapping category names to risk ID lists
        """
        groups = {}

        # All risks in single category for now (can be enhanced later)
        if self.risks is not None:
            groups["risks"] = list(self.risks.keys())
        else:
            groups["risks"] = []

        return groups

    def _get_risk_subgraphs(self) -> list[str]:
        """
        Generate risk subgraphs using BaseGraph functionality.

        Returns:
            List of Mermaid syntax lines for risk subgraphs
        """
        subgraph_lines = []

        for category, risk_ids in self.risk_by_category.items():
            if not risk_ids:
                continue

            category_name = self._get_category_display_name(category)
            subgraph_lines.extend(self._create_subgraph_section(category, category_name, risk_ids, self.risks))

        return subgraph_lines

    def build_risk_control_component_graph(self) -> str:
        """
        Build three-layer Mermaid graph: risks → controls → components.

        Graph structure:
        1. Risk subgraphs (pink styling)
        2. Control subgraphs (reused from ControlGraph)
        3. Component container (reused from ControlGraph)
        4. Pink edges for risk-control, existing styling for control-component

        Returns:
            Complete Mermaid graph with three-layer hierarchy and styling
        """
        # Get graph configuration for risk graph type
        config_result = self.config_loader.get_graph_config("risk")
        if isinstance(config_result, tuple) and len(config_result) == 2:
            _, graph_preamble = config_result
        else:
            # Fallback config if format unexpected
            graph_preamble = ["graph LR", "    classDef hidden display: none;"]
        lines = graph_preamble

        # Add risk subgraphs (top layer)
        risk_subgraphs = self._get_risk_subgraphs()
        lines.extend(risk_subgraphs)

        # Reuse control subgraphs (middle layer)
        control_subgraphs = self.control_graph._get_controls_subgraph()
        lines.extend(control_subgraphs)

        # Reuse component container (bottom layer)
        lines.append("    subgraph components")
        component_subgraphs = self.control_graph._get_component_subgraph()
        lines.extend(component_subgraphs)
        lines.append("    end")
        lines.append("")

        # Add risk→control edges with pink styling
        lines.append("    %% Risk to Control relationships")
        risk_control_edge_indices = []
        edge_index = 0

        for risk_id, control_ids in self.risk_to_control_map.items():
            if not control_ids:  # Skip risks with no mitigating controls
                if self.debug:
                    lines.append(f"    %% DEBUG: {risk_id} has no controls")
                continue

            for control_id in sorted(control_ids):
                if self.debug:
                    lines.append(f"    %% DEBUG: {risk_id} → {control_id}")
                lines.append(f"    {risk_id} --> {control_id}")
                risk_control_edge_indices.append(edge_index)
                edge_index += 1

        # Reuse control→component edges from ControlGraph
        lines.append("")
        lines.append("    %% Control to Component relationships (reused from ControlGraph)")

        # Extract control→component edges, continuing edge indexing
        for control_id, component_ids in self.control_graph.control_to_component_map.items():
            if not component_ids:
                continue

            for component_id in sorted(component_ids):
                if component_id == "components":
                    # Universal control - dotted line to all components
                    lines.append(f"    {control_id} -.-> {component_id}")
                elif component_id in self.control_graph.component_by_category.keys():
                    # Category mapping - solid line to category
                    lines.append(f"    {control_id} --> {component_id}")
                elif component_id in self.components:
                    # Individual component - solid line
                    lines.append(f"    {control_id} --> {component_id}")
                edge_index += 1

        # Apply styling
        lines.append("")
        lines.append("    %% Edge styling")

        # Style risk→control edges with cycling styles
        if risk_control_edge_indices:
            # Pre-calculate the 4 possible style strings to avoid redundant calls
            style_strings = []
            for style_index in range(4):
                style_config = self.config_loader.get_risk_control_edge_style(style_index)
                style_str = self._get_edge_style(style_config)
                style_strings.append(style_str)

            # Group edges by their style (index % 4) for efficient styling
            style_groups = {}
            for i, edge_idx in enumerate(risk_control_edge_indices):
                style_str = style_strings[i % 4]

                if style_str not in style_groups:
                    style_groups[style_str] = []
                style_groups[style_str].append(edge_idx)

            # Apply styles to grouped edges
            for style_str, edge_indices in style_groups.items():
                edge_list = ",".join(map(str, edge_indices))
                lines.append(f"    linkStyle {edge_list} {style_str}")

        # Note: ControlGraph edge styling not applied here (would need adjusted indices)

        # Add node styling
        lines.extend(
            [
                "",
                "%% Node style definitions",
            ]
        )

        # Style risk category subgraphs
        risk_categories = self.config_loader.get_risk_category_styles()
        for category_key, category_config in risk_categories.items():
            if category_config:
                style_str = self._get_node_style("riskCategory", category_config=category_config)
                lines.append(f"    style {category_key} {style_str}")

        # Reuse component styling from ControlGraph
        component_categories = self.config_loader.get_component_category_styles()
        components_container_style = self.config_loader.get_components_container_style()

        # Style main components container
        if components_container_style:
            style_str = self._get_node_style("componentsContainer")
            lines.append(f"    style components {style_str}")

        # Style component category subgraphs
        for category_key, category_config in component_categories.items():
            if category_config:
                style_str = self._get_node_style("componentCategory", category_config=category_config)
                lines.append(f"    style {category_key} {style_str}")

        return "\n".join(lines)

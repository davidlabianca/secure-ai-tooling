"""
Risk-to-control-to-component relationship visualization for the CoSAI Risk Map framework.

This module generates optimized Mermaid graph visualizations showing how security risks
map to controls and subsequently to AI system components. It leverages the existing
ControlGraph functionality through composition to minimize code duplication while
adding risk-specific visualization capabilities.

The RiskGraph class specializes in:
    - Risk-to-control relationship mapping and visualization
    - Three-layer hierarchical visualization (Risks → Controls → Components)
    - Category-based organization for risks, controls, and components
    - Composition-based reuse of ControlGraph optimization algorithms

Use Cases:
    - Visualizing complete risk mitigation chains from threats to controls to components
    - Understanding security control coverage across AI system architecture
    - Demonstrating comprehensive risk management to stakeholders and auditors
    - Identifying risk mitigation gaps or over-controlled areas

Dependencies:
    - ..models: RiskNode, ControlNode, and ComponentNode data structures
    - .base: BaseGraph foundation and MermaidConfigLoader
    - .controls_graph: ControlGraph for control-to-component reuse
"""

from ..models import ComponentNode, ControlNode, RiskNode
from .base import BaseGraph, MermaidConfigLoader
from .controls_graph import ControlGraph


class RiskGraph(BaseGraph):
    """
    Generates optimized Mermaid graph visualizations for risk-to-control-to-component relationships.

    The RiskGraph class creates three-layer visual representations showing how security risks
    map to controls and subsequently to AI system components. It leverages ControlGraph
    functionality through composition to maximize code reuse while adding risk-specific
    visualization capabilities.

    Key Features:
    - **Risk-to-Control Mapping**: Maps risks to the controls that mitigate them
    - **Control-Component Reuse**: Leverages ControlGraph optimizations through composition
    - **Three-Layer Visualization**: Risks → Controls → Components with proper hierarchy
    - **Category Organization**: Groups risks, controls, and components by category
    - **Configuration-Driven Styling**: Uses MermaidConfigLoader for consistent styling
    - **Optimization Algorithms**: Applies optimization techniques to risk-control relationships

    Graph Structure:
    The generated graph consists of three main sections:
    1. **Risk Subgraphs**: Grouped by risk category (currently single "risks" category)
    2. **Control Subgraphs**: Reused from ControlGraph - grouped by control category
    3. **Component Container**: Reused from ControlGraph - nested component subgraphs

    Composition Pattern:
    Rather than inheriting from ControlGraph, this class composes with it to:
    - Reuse control-to-component optimization algorithms automatically
    - Prevent code duplication across graph implementations
    - Enable independent evolution of risk-specific vs. control-specific logic
    - Maintain single source of truth for control-component relationships

    Example:
        >>> risks = {"DP": RiskNode("Data Poisoning", "risks")}
        >>> controls = {"ctrl1": ControlNode("Input Validation", "controlsData", ["comp1"], ["DP"], [])}
        >>> components = {"comp1": ComponentNode("Data Sources", "componentsData", [], [])}
        >>> graph = RiskGraph(risks, controls, components, debug=True)
        >>> mermaid_code = graph.to_mermaid()
        >>> print("```mermaid" in mermaid_code)
        True

    Attributes:
        risks (dict[str, RiskNode]): Dictionary of risk ID to RiskNode mappings
        controls (dict[str, ControlNode]): Dictionary of control ID to ControlNode mappings
        components (dict[str, ComponentNode]): Dictionary of component ID to ComponentNode mappings
        debug (bool): Whether to include debug comments in generated graphs
        control_graph (ControlGraph): Composed ControlGraph instance for reuse
        risk_to_control_map (dict[str, list[str]]): Optimized risk-to-control mappings
        risk_by_category (dict[str, list[str]]): Risks grouped by category

    Note:
        - The class automatically applies optimizations during initialization
        - Control-to-component logic is delegated to the composed ControlGraph
        - Risk-specific functionality focuses only on risk-to-control relationships
        - Generated Mermaid code includes styling for three-layer visualization
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
        Initialize RiskGraph with risks, controls, and components data.

        Performs initialization including risk categorization, risk-to-control mapping,
        and composition with ControlGraph for control-component functionality.

        The initialization process follows this sequence:
        1. Initialize base graph capabilities
        2. Create composed ControlGraph for control-component reuse
        3. Build risk-to-control mappings
        4. Group risks by their categories
        5. Prepare graph generation data structures

        Args:
            risks (dict[str, RiskNode]): Dictionary mapping risk IDs to RiskNode objects.
                Each RiskNode should have valid title and category.
            controls (dict[str, ControlNode]): Dictionary mapping control IDs to ControlNode objects.
                Passed through to composed ControlGraph for optimization.
            components (dict[str, ComponentNode]): Dictionary mapping component IDs to ComponentNode objects.
                Passed through to composed ControlGraph for optimization.
            debug (bool, optional): Whether to include debug information in generated output.
                Defaults to False. When True, adds debug comments to Mermaid diagrams.
            config_loader (MermaidConfigLoader, optional): Configuration loader for
                styling and layout options. Defaults to None, which creates a singleton
                instance using default configuration paths.

        Raises:
            TypeError: If risks, controls, or components are not dictionaries, or if they contain
                      invalid RiskNode/ControlNode/ComponentNode objects.
            ValueError: If risk, control, or component IDs are empty or contain invalid characters.

        Side Effects:
            - Creates self.control_graph with composed ControlGraph functionality
            - Builds self.risk_to_control_map with optimized mappings
            - Populates self.risk_by_category with categorized risks

        Example:
            >>> risks = {"DP": RiskNode("Data Poisoning", "risks")}
            >>> controls = {"ctrl1": ControlNode("Input Validation", "controlsData", ["comp1"], ["DP"], [])}
            >>> components = {"comp1": ComponentNode("Data Sources", "componentsData", [], [])}
            >>> graph = RiskGraph(risks, controls, components, debug=True)
            >>> assert hasattr(graph, 'control_graph')
            >>> assert hasattr(graph, 'risk_to_control_map')
        """
        super().__init__(components=components, controls=controls, config_loader=config_loader)
        self.risks = risks
        self.debug = debug

        # Compose with ControlGraph for control-component functionality
        # This enables reuse of all ControlGraph optimizations automatically
        self.control_graph = ControlGraph(controls, components, debug=debug, config_loader=self.config_loader)

        # Build risk-specific mappings
        self.risk_to_control_map = self._build_risk_control_mapping()
        self.risk_by_category = self._group_risks_by_category()
        self.graph = self.build_risk_control_component_graph()


    def _build_risk_control_mapping(self) -> dict[str, list[str]]:
        """
        Build mapping of risk IDs to control IDs that mitigate them.

        This method analyzes control-risk relationships to create optimized mappings
        showing which controls mitigate each risk. It handles special cases like
        "all" and "none" control mappings similar to how ControlGraph handles components.

        Mapping Strategy:
        1. **Extract Control-Risk Relationships**: Read risk references from each control
        2. **Reverse Mapping**: Create risk → controls mapping from control → risks data
        3. **Handle Special Cases**: Process "all" and "none" risk mappings appropriately
        4. **Optimization**: Future enhancement could add category-level optimizations

        Returns:
            dict[str, list[str]]: Dictionary mapping risk IDs to lists of control IDs
            that mitigate those risks. Empty lists for risks with no mitigating controls.

        Example:
            >>> # Control references specific risks
            >>> controls = {"ctrl1": ControlNode(..., risks=["DP", "PIJ"], ...)}
            >>> # Result: {"DP": ["ctrl1"], "PIJ": ["ctrl1"]}

        Note:
            - This method creates the reverse mapping from controls → risks to risks → controls
            - Future enhancement could add category-level optimizations similar to ControlGraph
            - Invalid control references are silently filtered out
        """
        mapping = {}

        # Handle None risks data
        if self.risks is None:
            return mapping

        # Initialize mapping for all risks
        for risk_id in self.risks.keys():
            mapping[risk_id] = []

        # Build reverse mapping from controls to risks
        for control_id, control in self.controls.items():
            if control.risks == ["all"]:
                # Control applies to all risks - add to all risk mappings
                for risk_id in mapping.keys():
                    mapping[risk_id].append(control_id)
            elif control.risks == ["none"] or not control.risks:
                # Control applies to no risks - skip
                continue
            else:
                # Control applies to specific risks
                for risk_id in control.risks:
                    if risk_id in mapping:
                        mapping[risk_id].append(control_id)

        # Sort control lists for consistent output
        for risk_id in mapping:
            mapping[risk_id] = sorted(mapping[risk_id])

        return mapping

    def _group_risks_by_category(self) -> dict[str, list[str]]:
        """
        Group risk IDs by their category.

        Currently, risks don't have explicit categories in the YAML structure,
        so this method assigns all risks to a default "risks" category.
        This method is prepared for future enhancement when risk categories are added.

        Returns:
            dict[str, list[str]]: Dictionary mapping category names to lists of risk IDs.
            Currently returns single "risks" category containing all risks.

        Example:
            >>> # Current implementation
            >>> {"risks": ["DP", "PIJ", "SDD", ...]}
            >>> # Future enhancement with categories
            >>> {"dataRisks": ["DP", "SDD"], "modelRisks": ["PIJ", "MS"], ...}

        Note:
            - Prepared for future risk categorization enhancement
            - Currently uses single "risks" category for all risks
            - Category display names are handled by BaseGraph._get_category_display_name()
        """
        groups = {}

        # For now, all risks go into a single "risks" category
        # This can be enhanced when risk categories are added to the YAML schema
        if self.risks is not None:
            groups["risks"] = list(self.risks.keys())
        else:
            groups["risks"] = []

        return groups

    def _get_risk_subgraphs(self) -> list[str]:
        """
        Generate risk subgraphs using the shared BaseGraph functionality.

        Creates Mermaid subgraph sections for all risk categories using the
        extracted _create_subgraph_section method from BaseGraph.

        Returns:
            list[str]: List of Mermaid syntax lines for risk subgraphs

        Example Output:
            [
                'subgraph risks ["Risks"]',
                '    DP[Data Poisoning]',
                '    PIJ[Prompt Injection]',
                'end',
                ''
            ]
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
        Build a complete three-layer Mermaid graph showing risk-to-control-to-component relationships.

        Generates a comprehensive Mermaid flowchart that visualizes the complete risk mitigation
        chain from security risks through controls to AI system components. The graph reuses
        ControlGraph functionality for the control-component portion while adding risk-specific
        elements.

        Graph Structure:
        1. **Risk Subgraphs**: Groups risks by category with pink styling
        2. **Control Subgraphs**: Reused from ControlGraph - grouped by control category
        3. **Component Container**: Reused from ControlGraph - nested component subgraphs
        4. **Risk-Control Edges**: Pink dashed edges showing risk-to-control relationships
        5. **Control-Component Edges**: Reused from ControlGraph with existing styling

        Three-Layer Hierarchy:
        - **Top Layer (Risks)**: Security threats and vulnerabilities
        - **Middle Layer (Controls)**: Security measures that mitigate risks
        - **Bottom Layer (Components)**: AI system components protected by controls

        Reuse Strategy:
        - **Control Subgraphs**: Generated by composed ControlGraph._get_controls_subgraph()
        - **Component Subgraphs**: Generated by composed ControlGraph._get_component_subgraph()
        - **Control-Component Edges**: Generated by composed ControlGraph edge logic
        - **Styling**: Reused ControlGraph styling plus risk-specific pink edges

        Returns:
            str: Complete Mermaid graph definition wrapped in ```mermaid code blocks,
                ready for rendering in documentation or web interfaces. Includes all
                styling definitions, three-layer structure, and relationship mappings.

        Example Output Structure:
            ```mermaid
            graph LR
                subgraph risks ["Risks"]
                    DP[Data Poisoning]
                end
                subgraph controlsData ["Data Controls"]
                    control1[Input Validation]
                end
                subgraph components
                    subgraph componentsData ["Data Components"]
                        comp1[Data Sources]
                    end
                end
                DP --> control1
                control1 --> componentsData
            ```

        Side Effects:
            - None. This method is read-only and generates output based on existing state.

        Performance Notes:
            - Leverages ControlGraph optimizations automatically through composition
            - Graph complexity scales with number of risks, controls, and components
            - Generated strings can be large for complex risk frameworks

        Note:
            - Uses left-to-right layout (graph LR) for three-layer hierarchy visualization
            - All ControlGraph styling and optimizations are automatically included
            - Risk-specific styling uses pink color scheme for visual distinction
            - Edge indices are calculated automatically for proper styling application
        """
        # Get configuration from loader for risk graph type
        config_result = self.config_loader.get_graph_config("risk")
        if isinstance(config_result, tuple) and len(config_result) == 2:
            _, graph_preamble = config_result
        else:
            # Fallback if config doesn't return expected format
            graph_preamble = ["graph LR", "    classDef hidden display: none;"]
        lines = graph_preamble

        # Add risk subgraphs at the top of the hierarchy
        risk_subgraphs = self._get_risk_subgraphs()
        lines.extend(risk_subgraphs)

        # Reuse control subgraphs from composed ControlGraph
        control_subgraphs = self.control_graph._get_controls_subgraph()
        lines.extend(control_subgraphs)

        # Reuse component container from composed ControlGraph
        lines.append("    subgraph components")
        component_subgraphs = self.control_graph._get_component_subgraph()
        lines.extend(component_subgraphs)
        lines.append("    end")
        lines.append("")

        # Add risk-to-control relationships
        lines.append("    %% Risk to Control relationships")
        risk_control_edge_indices = []
        edge_index = 0

        for risk_id, control_ids in self.risk_to_control_map.items():
            if not control_ids:  # Skip risks with no mitigating controls
                if self.debug:
                    lines.append(f"    %% DEBUG: Skipping {risk_id} - no mitigating controls")
                continue

            for control_id in sorted(control_ids):
                if self.debug:
                    lines.append(f"    %% DEBUG: {risk_id} → {control_id} (risk mitigation)")
                lines.append(f"    {risk_id} --> {control_id}")
                risk_control_edge_indices.append(edge_index)
                edge_index += 1

        # Reuse control-to-component relationships from ControlGraph
        lines.append("")
        lines.append("    %% Control to Component relationships (reused from ControlGraph)")

        # Extract control-component edges from composed ControlGraph
        # Start edge indexing after risk-control edges
        for control_id, component_ids in self.control_graph.control_to_component_map.items():
            if not component_ids:
                continue

            for component_id in sorted(component_ids):
                if component_id == "components":
                    # Universal control mapping
                    lines.append(f"    {control_id} -.-> {component_id}")
                elif component_id in self.control_graph.component_by_category.keys():
                    # Category-level mapping
                    lines.append(f"    {control_id} --> {component_id}")
                elif component_id in self.components:
                    # Individual component mapping
                    lines.append(f"    {control_id} --> {component_id}")
                edge_index += 1

        # Apply styling
        lines.append("")
        lines.append("    %% Edge styling")

        # Style risk-to-control edges
        if risk_control_edge_indices:
            edge_list = ",".join(map(str, risk_control_edge_indices))
            risk_edge_styles = self.config_loader.get_risk_edge_styles()
            style_config = risk_edge_styles.get("riskControlEdges", {})
            style_str = self._get_edge_style(style_config)
            lines.append(f"    linkStyle {edge_list} {style_str}")

        # Reuse control styling from ControlGraph
        # Note: ControlGraph styling would need to be applied here with adjusted edge indices
        # For now, we'll apply basic styling to maintain visual consistency

        # Add node styling
        lines.extend(
            [
                "",
                "%% Node style definitions",
            ]
        )

        # Style risk categories
        risk_categories = self.config_loader.get_risk_category_styles()
        for category_key, category_config in risk_categories.items():
            if category_config:
                style_str = self._get_node_style("riskCategory", category_config=category_config)
                lines.append(f"    style {category_key} {style_str}")

        # Reuse component and control styling from ControlGraph
        component_categories = self.config_loader.get_component_category_styles()
        components_container_style = self.config_loader.get_components_container_style()

        # Style components container
        if components_container_style:
            style_str = self._get_node_style("componentsContainer")
            lines.append(f"    style components {style_str}")

        # Style component categories
        for category_key, category_config in component_categories.items():
            if category_config:
                style_str = self._get_node_style("componentCategory", category_config=category_config)
                lines.append(f"    style {category_key} {style_str}")

        return "\n".join(lines)

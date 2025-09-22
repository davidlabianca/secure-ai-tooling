"""
Security control to AI component mapping visualization for the CoSAI Risk Map framework.

This module generates optimized Mermaid graph visualizations showing how security controls
map to AI system components. It applies sophisticated optimization algorithms to reduce
visual complexity while maintaining accuracy, featuring dynamic component clustering,
category-level optimizations, and multi-edge styling.

The ControlGraph class specializes in:
    - Dynamic component clustering to reduce edge complexity
    - Category-level control mapping optimization
    - Multi-edge styling with cycling colors for complex controls
    - Subgroup detection and visualization for related components

Optimization Features:
    - Automatic detection when controls apply to entire component categories
    - Clustering of components that share multiple controls into subgroups
    - Edge count reduction through hierarchical mapping strategies
    - Visual styling that scales with control complexity

Use Cases:
    - Mapping security controls to AI system components for compliance
    - Visualizing control coverage across AI system architecture
    - Identifying control gaps or over-controlled areas
    - Demonstrating security posture to stakeholders and auditors

Dependencies:
    - ..models: ComponentNode and ControlNode data structures
    - .base: BaseGraph foundation, MermaidConfigLoader, and MultiEdgeStyler
"""

from typing import Any

from ..models import ComponentNode, ControlNode
from .base import BaseGraph, MultiEdgeStyler
from .graph_utils import MermaidConfigLoader


class ControlGraph(BaseGraph):
    """
    Generates optimized Mermaid graph visualizations for control-to-component relationships.

    The ControlGraph class creates visual representations of how security controls map
    to AI system components, applying optimization algorithms to reduce
    visual complexity while maintaining accuracy. It supports dynamic component clustering,
    category-level optimizations, and multi-edge styling to create clear, readable diagrams.

    Key Features:
    - **Dynamic Component Clustering**: Automatically groups components that share multiple
      controls into subgroups to reduce edge complexity
    - **Category Optimization**: Maps controls to entire categories when they apply to all
      components in that category
    - **Multi-Edge Styling**: Applies distinct visual styles to controls with 3+ edges
      using 4 cycling colors (purple, orange, pink, brown)
    - **Special Control Handling**: Provides dedicated styling for "all" controls and
      subgraph-targeted controls
    - **Dynamic Category Loading**: Loads category display names from YAML configuration files

    Graph Structure:
    The generated graph consists of three main sections:
    1. **Control Subgraphs**: Grouped by control category (Data, Infrastructure, etc.)
    2. **Component Container**: Nested subgraphs for component categories and dynamic clusters
    3. **Relationship Edges**: Styled connections showing control-to-component mappings

    Optimization Algorithms:
    - **Subgrouping Detection**: Uses `_find_component_clusters()` to identify components
      with shared control relationships (min 2 shared controls, min 2 components)
    - **Category Mapping**: Uses `_maps_to_full_category()` to detect when controls apply
      to complete component categories
    - **Edge Styling**: Applies different visual treatments based on edge type and count

    Example:
        >>> controls = {
        ...     "control1": ControlNode(
        ...         "Data Encryption", "controlsData", ["comp1", "comp2"], ["SDD"], ["persona1"]
        ...     )
        ... }
        >>> components = {
        ...     "comp1": ComponentNode("Data Storage", "componentsData", [], []),
        ...     "comp2": ComponentNode("Model Storage", "componentsModel", [], [])
        ... }
        >>> graph = ControlGraph(controls, components, debug=True)
        >>> mermaid_code = graph.to_mermaid()
        >>> print("```mermaid" in mermaid_code)
        True

    Attributes:
        controls (dict[str, ControlNode]): Dictionary of control ID to ControlNode mappings
        components (dict[str, ComponentNode]): Dictionary of component ID to ComponentNode mappings
        debug (bool): Whether to include debug comments in generated graphs
        component_by_category (dict[str, list[str]]): Components grouped by category/subgroup
        subgroupings (dict[str, dict[str, list[str]]]): Dynamic subgroups within categories
        control_to_component_map (dict[str, list[str]]): Optimized control-to-component mappings
        controls_mapped_to_all (Set[str]): Controls originally mapped to "all" components
        control_by_category (dict[str, list[str]]): Controls grouped by category

    Note:
        - The class automatically applies optimizations during initialization
        - Subgrouping algorithms have configurable thresholds (min_shared_controls=2, min_components=2)
        - Category display names are loaded from risk-map/yaml/ configuration files
        - Multi-edge styling only applies to individual component mappings, not category mappings
        - The generated Mermaid code includes styling for visualization
    """

    def __init__(
        self,
        controls: dict[str, ControlNode],
        components: dict[str, ComponentNode],
        debug: bool = False,
        config_loader: MermaidConfigLoader = None,
    ):
        """
        Initialize ControlGraph with controls and components data.

        Performs initialization including component categorization,
        dynamic subgrouping detection, control-to-component mapping optimization,
        and preparation of all data structures needed for graph generation.

        The initialization process follows this sequence:
        1. Group components by their categories
        2. Detect optimal subgroupings using clustering algorithms
        3. Integrate subgroupings into the category structure
        4. Build optimized control-to-component mappings
        5. Track controls mapped to "all" components
        6. Group controls by their categories

        Args:
            controls (dict[str, ControlNode]): Dictionary mapping control IDs to ControlNode objects.
                Each ControlNode should have valid title, category, components, risks, and personas.
            components (dict[str, ComponentNode]): Dictionary mapping component IDs to ComponentNode objects.
                Each ComponentNode should have valid title, category, and edge relationships.
            debug (bool, optional): Whether to include debug information in generated output.
                Defaults to False. When True, adds debug comments to Mermaid diagrams.
            config_loader (MermaidConfigLoader, optional): Configuration loader for
                styling and layout options. Defaults to None, which creates a singleton
                instance using default configuration paths.

        Raises:
            TypeError: If controls or components are not dictionaries, or if they contain
                      invalid ControlNode/ComponentNode objects.
            ValueError: If control or component IDs are empty or contain invalid characters.

        Side Effects:
            - Populates self.component_by_category with categorized components
            - Creates self.subgroupings with dynamically detected component clusters
            - Builds self.control_to_component_map with optimized mappings
            - Initializes self.controls_mapped_to_all set
            - Creates self.control_by_category groupings

        Example:
            >>> controls = {"ctrl1": ControlNode("Test", "controlsData", ["comp1"], [], [])}
            >>> components = {"comp1": ComponentNode("Test", "componentsData", [], [])}
            >>> graph = ControlGraph(controls, components, debug=True)
            >>> assert hasattr(graph, 'control_to_component_map')
            >>> assert hasattr(graph, 'subgroupings')
        """
        super().__init__(components=components, controls=controls, config_loader=config_loader)
        self.debug = debug

        # Build mappings for graph generation
        self._group_components_by_category()
        self._group_controls_by_category()

        self.initial_mapping: dict[str, list[str]] = dict()
        # Find optimal subgroupings and merge them into component_by_category
        self.subgroupings = self._find_optimal_subgroupings()
        if self.debug and self.subgroupings:
            self._debug_subgroupings()
        self._integrate_subgroupings()

        # Graph build private variables
        self._processed_subgroups = set()
        self._universal_control_edge_indices = []
        self._category_edge_indices = []
        self._multi_edge_styler = MultiEdgeStyler(self)

        self.control_to_component_map = self._build_control_component_mapping()
        self.controls_mapped_to_all = self._track_controls_mapped_to_all()
        self.graph = self.build_controls_graph()

    def _debug_subgroupings(self) -> None:
        """Print debug information about discovered subgroupings."""
        print("DEBUG: Discovered subgroupings:")
        for parent_category, subgroups in self.subgroupings.items():
            print(f"  {parent_category}:")
            for subgroup_name, components in subgroups.items():
                print(f"    {subgroup_name}: {components}")

    def _maps_to_full_category(self, control_components: list[str], category: str) -> bool:
        """
        Check if a control's component list covers ALL components in a specific category.

        Args:
            control_components: List of component IDs from the control
            category: Category ID to check (e.g., 'componentsData')

        Returns:
            True if control maps to all components in the category, False otherwise
        """
        if category not in self.component_by_category:
            return False

        category_components = set(self.component_by_category[category])
        control_component_set = set(control_components)

        # Check if all components in this category are present in the control's component list
        return category_components.issubset(control_component_set)

    def _find_optimal_subgroupings(self) -> dict[str, dict[str, list[str]]]:
        """
        Analyze control-component relationships to find optimal subgroupings.

        Returns:
            Dict mapping parent categories to their optimal subgroups:
            {
                "componentsInfrastructure": {
                    "componentsModelInfrastructure": ["comp1", "comp2", ...],
                    "componentsDataInfrastructure": ["comp3", "comp4", ...]
                }
            }
        """
        # Build initial control-component map (without optimization)
        self._component_to_control_mapping()
        initial_mapping = self.initial_mapping

        # Find categories with 3+ components that could benefit from subgrouping
        subgroupings = {}

        for category, components in self.component_by_category.items():
            if len(components) < 2:
                continue  # Skip small categories

            # Build a map of component -> set of controls that target it
            component_to_controls = {}
            for component_id in components:
                component_to_controls[component_id] = set()

            for control_id, target_components in initial_mapping.items():
                for component_id in target_components:
                    if component_id in component_to_controls:
                        component_to_controls[component_id].add(control_id)

            # Find groups of components that share 2+ controls
            subgroups = self._find_component_clusters(component_to_controls, min_shared_controls=2, min_nodes=2)

            if subgroups:
                subgroupings[category] = subgroups

        return subgroupings

    def _integrate_subgroupings(self) -> None:
        """
        Integrate discovered subgroupings into component_by_category.
        Remove subgrouped components from parent categories and add subgroups.
        """
        for parent_category, subgroups in self.subgroupings.items():
            if parent_category not in self.component_by_category:
                continue

            # Remove subgrouped components from parent category
            all_subgrouped_components = set()
            for subgroup_components in subgroups.values():
                all_subgrouped_components.update(subgroup_components)

            # Update parent category to exclude subgrouped components
            self.component_by_category[parent_category] = [
                component_id
                for component_id in self.component_by_category[parent_category]
                if component_id not in all_subgrouped_components
            ]

            # Add subgroups as new categories
            for subgroup_name, subgroup_components in subgroups.items():
                self.component_by_category[subgroup_name] = subgroup_components

    def _get_category_check_order(self) -> list[str]:
        """
        Get the order in which to check categories for optimization.
        Returns subgroups first (most specific), then main categories.
        """
        # Collect all dynamically created subgroups
        subgroup_names = []
        main_categories = []

        for parent_category, subgroups in self.subgroupings.items():
            subgroup_names.extend(subgroups.keys())

        # Add main categories (excluding those that have subgroups)
        for category in self.component_by_category.keys():
            if category not in subgroup_names:
                main_categories.append(category)

        # Return subgroups first, then main categories
        return subgroup_names + main_categories

    def _build_control_component_mapping(self) -> dict[str, list[str]]:
        """
        Build optimized mapping of control IDs to component IDs they apply to.

        This method performs optimization to reduce visual complexity by
        detecting when controls apply to complete categories or subgroups and mapping
        to those higher-level constructs instead of individual components.

        Optimization Strategy:
        1. **Special Cases**: Handle "all" and "none" component mappings
        2. **Component Validation**: Filter out non-existent component references
        3. **Category Detection**: Identify controls that map to complete categories
        4. **Subgroup Detection**: Identify controls that map to complete subgroups
        5. **Hierarchical Mapping**: Prefer subgroups over categories, categories over individuals

        Mapping Types:
        - **"all" Controls**: Mapped to ["components"] (entire component container)
        - **"none" Controls**: Mapped to [] (empty list)
        - **Category Complete**: Mapped to [category_name] when all category components included
        - **Subgroup Complete**: Mapped to [subgroup_name] when all subgroup components included
        - **Individual**: Mapped to [comp1, comp2, ...] for partial category coverage

        Priority Order (highest to lowest):
        1. Dynamic subgroups (most specific)
        2. Component categories (broader scope)
        3. Individual components (fallback)

        Returns:
            dict[str, list[str]]: Dictionary mapping control IDs to lists of target identifiers.
            Targets can be individual component IDs, category names, or subgroup names,
            depending on optimization results.

        Example:
            >>> # Control mapping to full category
            >>> control1_components = ["comp1", "comp2"]  # All components in "componentsData"
            >>> # Result: {"control1": ["componentsData"]}
            >>>
            >>> # Control mapping to subgroup
            >>> control2_components = ["comp3", "comp4"]  # All components in "componentsComp" subgroup
            >>> # Result: {"control2": ["componentsComp"]}
            >>>
            >>> # Control mapping to individuals
            >>> control3_components = ["comp1"]  # Partial category coverage
            >>> # Result: {"control3": ["comp1"]}

        Side Effects:
            - Validates component references against self.components
            - Uses self.component_by_category for category detection
            - Applies category check order from _get_category_check_order()

        Note:
            - Invalid component references are silently filtered out
            - Empty component lists result in empty mappings
            - The optimization significantly reduces edge count in generated graphs
            - Category mappings take precedence over individual component mappings
        """
        for control_id, valid_components in self.initial_mapping.items():
            if valid_components and not valid_components == ["components"]:
                # Check if this control maps to complete categories and optimize accordingly
                optimized_mapping = []
                remaining_components = set(valid_components)

                # Check each category to see if control covers all components in that category
                # Start with sub-categories first (more specific), then main categories
                categories_to_check = self._get_category_check_order()

                for category in categories_to_check:
                    if self._maps_to_full_category(valid_components, category):
                        # Control covers all components in this category - use category-level mapping
                        optimized_mapping.append(category)
                        # Remove all components from this category from remaining list
                        category_components = set(self.component_by_category[category])
                        remaining_components -= category_components

                # Add any remaining individual components that don't form complete categories
                optimized_mapping.extend(sorted(remaining_components))

                self.initial_mapping[control_id] = optimized_mapping

        return self.initial_mapping

    def _track_controls_mapped_to_all(self) -> set[str]:
        """
        Track which controls were originally mapped to 'all' components.

        Returns:
            Set of control IDs that were mapped to 'all'
        """
        controls_with_all = set()
        for control_id, control in self.controls.items():
            if control.components == ["all"]:
                controls_with_all.add(control_id)
        return controls_with_all

    def _get_controls_subgraph(self):
        return self._get_subgraph(subgraph_type="controls")

    def _get_component_subgraph(self):
        return self._get_subgraph(subgraph_type="components")

    def _get_subgraph(self, subgraph_type: str):
        if not isinstance(subgraph_type, str) or not (
            subgraph_type == "controls" or subgraph_type == "components"
        ):
            return []

        subgraph_lines = []

        if subgraph_type == "controls":
            item_by_category = self.control_by_category.items()
            items = self.controls
        else:
            item_by_category = self.component_by_category.items()
            items = self.components

        for category, item_ids in item_by_category:
            if not item_ids or category in self._processed_subgroups:
                continue

            category_name = self._get_category_display_name(category)

            if subgraph_type == "components" and (
                nested_subgraph := self._get_nested_subgraph(item_ids, category, category_name)
            ):
                subgraph_lines.extend(nested_subgraph)
            else:
                subgraph_lines.extend(self._create_subgraph_section(category, category_name, item_ids, items))

        return subgraph_lines

    def _get_nested_subgraph(
        self, component_ids: list[str], category: str, category_name: str
    ) -> list[Any] | None:
        if not (category_subgroups := self.subgroupings.get(category, {})):
            return None

        nested_subgraph = []
        nested_subgraph.append(f'    subgraph {category} ["{category_name}"]')

        # Add remaining components in the main category (not subgrouped)
        for component_id in sorted(component_ids):
            component = self.components[component_id]
            nested_subgraph.append(f"        {component_id}[{component.title}]")

        # Add nested subgroups using the helper method
        for subgroup_name, subgroup_components in category_subgroups.items():
            subgroup_display_name = self._get_category_display_name(subgroup_name)
            subgroup_lines = self._create_subgraph_section(
                subgroup_name, subgroup_display_name, subgroup_components, self.components, "        "
            )
            # Remove the empty line at the end for nested subgroups
            if subgroup_lines and subgroup_lines[-1] == "":
                subgroup_lines.pop()
            nested_subgraph.extend(subgroup_lines)
            self._processed_subgroups.add(subgroup_name)

        nested_subgraph.append("    end")
        nested_subgraph.append("")

        return nested_subgraph

    def _get_all_edge(self, control_id: str, component_id: str, edge_index: int) -> str:
        self._universal_control_edge_indices.append(edge_index)
        return f"    {control_id} -.-> {component_id}"

    def _get_edge_subgraph(self, control_id: str, component_id: str, edge_index: int) -> str:
        self._category_edge_indices.append(edge_index)
        return self._get_edge(control_id, component_id)

    def _get_edge(self, control_id: str, component_id: str) -> str:
        return f"    {control_id} --> {component_id}"

    def build_controls_graph(self) -> str:
        """
        Build a Mermaid graph showing optimized control-to-component relationships.

        Generates a complete Mermaid flowchart with consistent styling that visualizes
        how security controls map to AI system components. The graph includes multiple
        optimization techniques to reduce complexity while maintaining clarity and accuracy.

        Graph Structure:
        1. **Control Subgraphs**: Groups controls by category (Data, Infrastructure, Model, etc.)
        2. **Component Container**: Nested subgraph structure with:
           - Main component categories (componentsData, componentsModel, etc.)
           - Dynamic subgroups for clustered components
           - Individual component nodes
        3. **Styled Relationships**: Edges with different visual treatments:
           - Dotted blue edges for "all" controls (apply to everything)
           - Solid green edges for category/subgroup mappings
           - Multi-colored edges for controls with 3+ individual component mappings
        4. **Styling**: Color-coded categories and visual hierarchy

        Visual Optimizations Applied:
        - **Component Clustering**: Groups related components into subgroups
        - **Category Mapping**: Maps controls to entire categories when applicable
        - **Edge Styling**: Differentiates edge types through color and pattern
        - **Node Styling**: Color-codes categories for better visual organization

        Edge Styling Legend:
        - **Blue Dotted (All Controls)**: stroke:#4285f4, dasharray:8 4 - Universal controls
        - **Green Solid (Categories)**: stroke:#34a853 - Category-level mappings
        - **Purple/Orange/Pink/Brown (Multi-edge)**: Various colors for individual mappings

        Returns:
            str: Complete Mermaid graph definition wrapped in ```mermaid code blocks,
                ready for rendering in documentation or web interfaces. Includes all
                styling definitions, subgraph structures, and relationship mappings.

        Example Output Structure:
            ```mermaid
            graph LR
                subgraph controlsData ["Data Controls"]
                    control1[Input Validation]
                end
                subgraph components
                    subgraph componentsData ["Data Components"]
                        comp1[Data Sources]
                    end
                end
                control1 --> componentsData
            ```

        Side Effects:
            - None. This method is read-only and generates output based on existing state.

        Performance Notes:
            - Graph complexity scales with number of controls and components
            - Optimizations significantly reduce edge count for large datasets
            - Generated strings can be large for complex control frameworks

        Note:
            - The graph uses left-to-right layout (graph LR) for optimal readability
            - All styling is embedded for standalone rendering
            - Subgraph nesting follows hierarchical component organization
            - Edge indices are automatically calculated for proper styling application
        """

        # Get configuration from loader
        _, graph_preamble = self.config_loader.get_graph_config("control")
        lines = graph_preamble

        # Add control subgraphs
        control_subgraphs = self._get_controls_subgraph()
        lines.extend(control_subgraphs)

        # Add components container subgraph to hold all components subgraphs
        lines.append("    subgraph components")

        # Add component subgraphs with dynamic nested structure
        component_subgraphs = self._get_component_subgraph()
        lines.extend(component_subgraphs)

        # Closing the components container subgraph
        lines.append("    end")
        lines.append("")

        # Add control-to-component relationships
        lines.append("    %% Control to Component relationships")

        # Track edge indices for styling
        edge_index: int = 0
        control_edge_counts = {}  # Track edge count per control

        # First pass: count edges per control
        for control_id, component_ids in self.control_to_component_map.items():
            if component_ids:
                control_edge_counts[control_id] = len(component_ids)

            # Generate edges and track indices with per-control styling
            if not component_ids:  # Skip controls with no component mappings
                if self.debug:
                    lines.append(f"    %% DEBUG: Skipping {control_id} - no component mappings")
                continue

            is_multi_edge_control = control_edge_counts.get(control_id, 0) >= 3
            if self.debug and is_multi_edge_control:
                lines.append(f"    %% DEBUG: {control_id} is multi-edge control ({len(component_ids)} edges)")
            self._multi_edge_styler.reset_index()

            for component_id in sorted(component_ids):
                if component_id == "components":
                    # This is a mapping to the components container (for 'all' controls)
                    if self.debug:
                        lines.append(f"    %% DEBUG: {control_id} → universal (all components)")
                    lines.append(self._get_all_edge(control_id, component_id, edge_index))

                elif component_id in self.component_by_category.keys():
                    # This is a category-level mapping (including sub-categories)
                    if self.debug:
                        category_size = len(self.component_by_category[component_id])
                        lines.append(
                            f"    %% DEBUG: {control_id} → {component_id} category ({category_size} components)"
                        )
                    lines.append(self._get_edge_subgraph(control_id, component_id, edge_index))

                elif component_id in self.components:
                    # This is an individual component mapping
                    if self.debug:
                        lines.append(f"    %% DEBUG: {control_id} → {component_id} (individual)")
                    lines.append(self._get_edge(control_id=control_id, component_id=component_id))

                    # Track multi-edge controls with cyclic style assignment per control
                    if is_multi_edge_control:
                        self._multi_edge_styler.set_edge(edge_index)

                edge_index += 1

        # Apply styling to controls that were mapped to "all"
        lines.append("")
        lines.append("    %% Apply styling to controls mapped to 'all'")
        for control_id in sorted(self.controls_mapped_to_all):
            if control_id in self.control_to_component_map and self.control_to_component_map[control_id]:
                lines.append(f"    {control_id}:::allControl")

        # Add edge styling
        lines.append("")
        lines.append("    %% Edge styling")

        # Style edges from 'all' controls
        if self._universal_control_edge_indices:
            edge_list = ",".join(map(str, self._universal_control_edge_indices))
            style_str = self._get_edge_style("allControlEdges")
            lines.append(f"    linkStyle {edge_list} {style_str}")

        # Style edges to subgraphs/categories
        if self._category_edge_indices:
            edge_list = ",".join(map(str, self._category_edge_indices))
            style_str = self._get_edge_style("subgraphEdges")
            lines.append(f"    linkStyle {edge_list} {style_str}")

        # Style edges from controls with 3+ individual component mappings
        lines.extend(self._multi_edge_styler.get_edge_style_lines())

        # Get node styling configuration
        component_categories = self.config_loader.get_component_category_styles()
        components_container_style = self.config_loader.get_components_container_style()

        # Add node styling
        lines.extend(
            [
                "",
                "%% Node style definitions",
            ]
        )

        # Style components container
        if components_container_style:
            style_str = self._get_node_style("componentsContainer")
            lines.append(f"    style components {style_str}")

        # Style component categories
        for category_key, category_config in component_categories.items():
            if category_config:
                style_str = self._get_node_style("componentCategory", category_config=category_config)
                lines.append(f"    style {category_key} {style_str}")

        # Add dynamic styling for subgroups using configuration
        for parent_category, subgroups in self.subgroupings.items():
            style_str = self._get_node_style("dynamicSubgroup", parent_category=parent_category)
            for subgroup_name in subgroups.keys():
                lines.append(f"    style {subgroup_name} {style_str}")

        lines.extend([])

        return "\n".join(lines)

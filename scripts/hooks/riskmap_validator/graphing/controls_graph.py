"""
Control-to-component mapping visualization for CoSAI Risk Map.

Generates Mermaid graphs showing how security controls map to AI components.
Applies optimization algorithms to reduce visual complexity:
- Component clustering when controls are shared
- Category-level mapping when controls apply to entire categories
- Multi-edge styling for controls with 3+ individual mappings
"""

from typing import Any

from ..models import ComponentNode, ControlNode
from .base import BaseGraph, MultiEdgeStyler
from .graph_utils import MermaidConfigLoader


class ControlGraph(BaseGraph):
    """
    Generates Mermaid graphs for control-to-component relationships.

    Optimizations applied:
    - Component clustering: Groups components sharing 2+ controls (min 2 components)
    - Category mapping: Maps to categories when control applies to all components in category
    - Multi-edge styling: Uses 4 cycling colors for controls with 3+ individual mappings

    Attributes:
        controls: Control ID to ControlNode mappings
        components: Component ID to ComponentNode mappings
        debug: Include debug comments in output
        subgroupings: Dynamic component clusters within categories
        control_to_component_map: Optimized control mappings
    """

    def __init__(
        self,
        controls: dict[str, ControlNode],
        components: dict[str, ComponentNode],
        debug: bool = False,
        config_loader: MermaidConfigLoader = None,
    ):
        """
        Initialize with controls and components data.

        Process sequence:
        1. Group components by category
        2. Find component clusters (2+ shared controls, 2+ components)
        3. Build optimized control-to-component mappings
        4. Track controls mapped to "all"
        """
        super().__init__(components=components, controls=controls, config_loader=config_loader)
        self.debug = debug

        # Build initial mappings
        self._group_components_by_category()
        self._group_controls_by_category()

        self.initial_mapping: dict[str, list[str]] = dict()
        # Find subgroupings and integrate them
        self.subgroupings = self._find_optimal_subgroupings()
        if self.debug and self.subgroupings:
            self._debug_subgroupings()
        self._integrate_subgroupings()

        # Graph generation state
        self._processed_subgroups = set()
        self._universal_control_edge_indices = []
        self._category_edge_indices = []
        self._multi_edge_styler = MultiEdgeStyler(self)

        self.control_to_component_map = self._build_control_component_mapping()
        self.controls_mapped_to_all = self._track_controls_mapped_to_all()
        self.graph = self.build_controls_graph()

    def _debug_subgroupings(self) -> None:
        """Print debug info for discovered subgroupings."""
        print("DEBUG: Discovered subgroupings:")
        for parent_category, subgroups in self.subgroupings.items():
            print(f"  {parent_category}:")
            for subgroup_name, components in subgroups.items():
                print(f"    {subgroup_name}: {components}")

    def _maps_to_full_category(self, control_components: list[str], category: str) -> bool:
        """
        Check if control covers all components in a category.
        """
        if category not in self.component_by_category:
            return False

        category_components = set(self.component_by_category[category])
        control_component_set = set(control_components)

        # Check if control covers all category components
        return category_components.issubset(control_component_set)

    def _find_optimal_subgroupings(self) -> dict[str, dict[str, list[str]]]:
        """
        Find component clusters that share 2+ controls.

        Returns:
            Dict mapping parent categories to subgroups.
        """
        # Build initial mapping before optimization
        self._component_to_control_mapping()
        initial_mapping = self.initial_mapping

        # Find categories with 2+ components for potential subgrouping
        subgroupings = {}

        for category, components in self.component_by_category.items():
            if len(components) < 2:
                continue  # Skip categories with <2 components

            # Map component to its controls
            component_to_controls = {}
            for component_id in components:
                component_to_controls[component_id] = set()

            for control_id, target_components in initial_mapping.items():
                for component_id in target_components:
                    if component_id in component_to_controls:
                        component_to_controls[component_id].add(control_id)

            # Find component clusters sharing 2+ controls
            subgroups = self._find_component_clusters(component_to_controls, min_shared_controls=2, min_nodes=2)

            if subgroups:
                subgroupings[category] = subgroups

        return subgroupings

    def _integrate_subgroupings(self) -> None:
        """
        Move subgrouped components from parent categories to subgroups.
        """
        for parent_category, subgroups in self.subgroupings.items():
            if parent_category not in self.component_by_category:
                continue

            # Collect all subgrouped components
            all_subgrouped_components = set()
            for subgroup_components in subgroups.values():
                all_subgrouped_components.update(subgroup_components)

            # Remove subgrouped components from parent
            self.component_by_category[parent_category] = [
                component_id
                for component_id in self.component_by_category[parent_category]
                if component_id not in all_subgrouped_components
            ]

            # Add subgroups as categories
            for subgroup_name, subgroup_components in subgroups.items():
                self.component_by_category[subgroup_name] = subgroup_components

    def _get_category_check_order(self) -> list[str]:
        """
        Get category check order: subgroups first, then main categories.
        """
        # Collect subgroups and main categories
        subgroup_names = []
        main_categories = []

        for parent_category, subgroups in self.subgroupings.items():
            subgroup_names.extend(subgroups.keys())

        # Add main categories excluding subgroups
        for category in self.component_by_category.keys():
            if category not in subgroup_names:
                main_categories.append(category)

        # Subgroups first for most specific matching
        return subgroup_names + main_categories

    def _build_control_component_mapping(self) -> dict[str, list[str]]:
        """
        Build control-to-component mappings with optimization.

        Optimization strategy:
        1. Map to categories when control covers all components in category
        2. Map to subgroups when control covers all components in subgroup
        3. Map to individual components otherwise

        Priority: subgroups > categories > individuals

        Returns:
            Dict mapping control IDs to target lists (component IDs, category names, or subgroup names)
        """
        for control_id, valid_components in self.initial_mapping.items():
            if valid_components and not valid_components == ["components"]:
                # Optimize by mapping to categories/subgroups when possible
                optimized_mapping = []
                remaining_components = set(valid_components)

                # Check categories in order: subgroups first (more specific), then main
                categories_to_check = self._get_category_check_order()

                for category in categories_to_check:
                    if self._maps_to_full_category(valid_components, category):
                        # Control covers entire category - map to category instead of individuals
                        optimized_mapping.append(category)
                        category_components = set(self.component_by_category[category])
                        remaining_components -= category_components

                # Add remaining components that don't form complete categories
                optimized_mapping.extend(sorted(remaining_components))

                self.initial_mapping[control_id] = optimized_mapping

        return self.initial_mapping

    def _track_controls_mapped_to_all(self) -> set[str]:
        """
        Track controls originally mapped to 'all' for special styling.
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
        Build Mermaid graph showing control-to-component relationships.

        Graph structure:
        1. Control subgraphs grouped by category
        2. Component container with nested subgraphs and dynamic clusters
        3. Styled edges: dotted blue (all controls), green (categories), multi-colored (individuals)

        Returns:
            Complete Mermaid graph with styling and subgraph structures
        """

        # Get configuration from loader
        _, graph_preamble = self.config_loader.get_graph_config("control")
        lines = graph_preamble

        # Add control subgraphs
        control_subgraphs = self._get_controls_subgraph()
        lines.append("    subgraph controls")
        lines.extend(control_subgraphs)

        # Closing the controls container subgraph
        lines.append("    end")
        lines.append("")

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

        # Count edges per control to identify multi-edge controls (3+ edges)
        for control_id, component_ids in self.control_to_component_map.items():
            if component_ids:
                control_edge_counts[control_id] = len(component_ids)

            # Generate edges with styling based on edge count
            if not component_ids:  # Skip controls with no component mappings
                if self.debug:
                    lines.append(f"    %% DEBUG: Skipping {control_id} - no component mappings")
                continue

            is_multi_edge_control = control_edge_counts.get(control_id, 0) >= 3  # 3+ edges get special styling
            if self.debug and is_multi_edge_control:
                lines.append(f"    %% DEBUG: {control_id} is multi-edge control ({len(component_ids)} edges)")
            self._multi_edge_styler.reset_index()

            for component_id in sorted(component_ids):
                if component_id == "components":
                    # Universal control - maps to entire component container
                    if self.debug:
                        lines.append(f"    %% DEBUG: {control_id} → universal (all components)")
                    lines.append(self._get_all_edge(control_id, component_id, edge_index))

                elif component_id in self.component_by_category.keys():
                    # Category/subgroup mapping - optimized from individual components
                    if self.debug:
                        category_size = len(self.component_by_category[component_id])
                        lines.append(
                            f"    %% DEBUG: {control_id} → {component_id} category ({category_size} components)"
                        )
                    lines.append(self._get_edge_subgraph(control_id, component_id, edge_index))

                elif component_id in self.components:
                    # Individual component mapping
                    if self.debug:
                        lines.append(f"    %% DEBUG: {control_id} → {component_id} (individual)")
                    lines.append(self._get_edge(control_id=control_id, component_id=component_id))

                    # Apply cycling colors for multi-edge controls
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

        # Style universal control edges (dotted blue)
        if self._universal_control_edge_indices:
            edge_list = ",".join(map(str, self._universal_control_edge_indices))
            style_str = self._get_edge_style("allControlEdges")
            lines.append(f"    linkStyle {edge_list} {style_str}")

        # Style category mapping edges (solid green)
        if self._category_edge_indices:
            edge_list = ",".join(map(str, self._category_edge_indices))
            style_str = self._get_edge_style("subgraphEdges")
            lines.append(f"    linkStyle {edge_list} {style_str}")

        # Style multi-edge control edges (cycling colors)
        lines.extend(self._multi_edge_styler.get_edge_style_lines())

        # Get node styling configuration
        component_categories = self.config_loader.get_component_category_styles()
        components_container_style = self.config_loader.get_components_container_style("control")
        controls_container_style = self.config_loader.get_controls_container_style("control")

        # Add node styling
        lines.extend(
            [
                "",
                "%% Node style definitions",
            ]
        )

        # Style main components container
        if components_container_style:
            style_str = self._style_node_from_dict(components_container_style)
            lines.append(f"    style components {style_str}")

        # Style main controls container
        if controls_container_style:
            style_str = self._style_node_from_dict(controls_container_style)
            lines.append(f"    style controls {style_str}")

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

"""
Core foundation classes for Mermaid graph generation in the CoSAI Risk Map framework.

This module provides the foundational components used by graph generation:
- BaseGraph: Common functionality for category handling, display names, and configuration
- MermaidConfigLoader: Configuration management with caching and fallback mechanisms

ComponentGraph is the sole consumer of BaseGraph. Issue #477 removed ControlGraph and
RiskGraph; the clustering machinery (_find_node_clusters / _find_component_clusters /
UnionFind) is retained without a current production caller because ComponentGraph's
category/subcategory id-collision fix (#488) needs it.

Key Features:
    - Dynamic category discovery from YAML configuration files
    - Singleton configuration management with emergency fallbacks
    - Category display name mapping and normalization

Dependencies:
    - ..config: Configuration constants and default paths
    - pathlib: File system path handling
    - yaml: YAML configuration file parsing
"""

from os.path import commonprefix
from pathlib import Path

import yaml

from riskmap_validator.models import ComponentNode

from .graph_utils import MermaidConfigLoader, UnionFind, _get_schema_categories


class BaseGraph:
    """
    Base class for Mermaid graph generation with shared utilities.

    This class provides common functionality for ComponentGraph, including category
    handling, display name generation, and configuration management.

    Key Features:
    - Dynamic category discovery from component data
    - Category display name generation with YAML config loading
    - Shared configuration patterns
    """

    def __init__(
        self,
        components: dict[str, ComponentNode],
        config_loader: "MermaidConfigLoader|None" = None,
    ):
        """
        Initialize BaseGraph with optional configuration loader.

        Args:
            config_loader (MermaidConfigLoader, optional): Configuration loader for
                styling and layout options. Defaults to None, which creates a singleton
                instance using default configuration paths.
        """
        self.config_loader = config_loader or MermaidConfigLoader.get_instance()
        # Emit a warning for each schema category that lacks a styling entry.
        # Fires once per (message, category, module) by default; test suites using
        # warnings.simplefilter("always") will see all occurrences.
        self.config_loader.emit_missing_category_warnings(_get_schema_categories())
        self._category_names_cache = None

        # Subgraph ids actually written by _create_subgraph_section, across
        # every call made against this instance. Cluster naming (_find_node_
        # clusters) derives a candidate id independently per call/category, so
        # two different categories can legitimately derive the identical
        # candidate (same common prefix, or same positional fallback index).
        # _create_subgraph_section is the single place that turns a candidate
        # into a declared "subgraph <id>" line, so it is the only place that
        # can see -- and must guarantee -- that no id is declared twice.
        self._declared_subgraph_ids: set[str] = set()

        self.component_by_category: dict[str, list[str]] = dict()
        self.component_by_subcategory: dict[str, dict[str, list[str]]] = dict()

        self.graph: str = ""

        if not isinstance(components, dict) or not all(
            isinstance(node, ComponentNode) for node in components.values()
        ):
            raise TypeError("'components' must be a dict of ComponentNodes")
        self.components = components

    def _reset_declared_subgraph_ids(self) -> None:
        """
        Clear subgraph-id collision tracking at the start of a render pass.

        _declared_subgraph_ids accumulates every id _create_subgraph_section
        has written for this instance. Scoped to the instance's whole
        lifetime rather than to a single render pass, that history leaks
        across calls: a category id that legitimately reappears every render
        (categories don't change between calls) gets misread as an
        already-taken id left over from a prior pass and is disambiguated
        for no reason -- see _create_subgraph_section's docstring for why
        that disambiguation exists in the first place.

        Any method that begins a fresh render pass over the same instance
        must call this first. ComponentGraph.build_graph is the only such
        caller today. The reset lives on BaseGraph rather than on
        ComponentGraph because _declared_subgraph_ids itself is declared
        here.
        """
        self._declared_subgraph_ids.clear()

    def to_mermaid(self, output_format: str = "markdown"):
        lines = self.graph
        if output_format == "markdown":
            lines = "```mermaid\n" + lines + "\n```"

        return lines + "\n"

    def _load_category_names(self) -> dict[str, str]:
        """
        Load category names from YAML files.

        Loads category display names from both controls.yaml and components.yaml
        configuration files, providing human-readable names for category IDs.

        Returns:
            dict[str, str]: Dictionary mapping category IDs to display names.
                           Returns empty dict if loading fails.
        """
        category_names: dict[str, str] = {}

        if not hasattr(self, "_category_names_cache") or self._category_names_cache is None:
            yaml_paths = [Path("risk-map/yaml/controls.yaml"), Path("risk-map/yaml/components.yaml")]

            # Load control categories & component categories
            for yaml_path in yaml_paths:
                try:
                    if yaml_path.exists():
                        with open(yaml_path, "r", encoding="utf-8") as f:
                            controls_data = yaml.safe_load(f)

                        for category in controls_data.get("categories", []):
                            if "id" in category and "title" in category:
                                # Append "Controls" to control category titles
                                category_names[category["id"]] = category["title"].title()
                except Exception:
                    pass  # Fallback to generated names if loading fails
            self._category_names_cache = category_names
        else:
            category_names = self._category_names_cache

        return category_names

    def _find_component_clusters(
        self, node_to_controls: dict[str, set], min_shared_controls: int = 2, min_nodes: int = 2
    ) -> dict[str, list[str]]:
        """
        Find clusters of components that share significant control overlap using graph clustering using
        Union Find class
        """
        return self._find_node_clusters("component", node_to_controls, min_shared_controls, min_nodes)

    def _find_node_clusters(
        self, node_type: str, node_to_controls: dict[str, set], min_shared_controls: int = 2, min_nodes: int = 2
    ) -> dict[str, list[str]]:
        """
        Find clusters of nodes that share significant control overlap using graph clustering using
        Union Find class
        """
        if node_type == "component":
            node_prefix = "component"
            node_category_prefix = "components"
        else:
            return {}

        nodes = list(node_to_controls.keys())

        uf = UnionFind(nodes)

        # Step 3: Union nodes with significant control overlap
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                comp1, comp2 = nodes[i], nodes[j]

                # Calculate shared controls using set intersection
                shared_controls = node_to_controls[comp1] & node_to_controls[comp2]

                # If significant overlap, these nodes should be clustered
                if len(shared_controls) >= min_shared_controls:
                    uf.union(comp1, comp2)

        # Step 4: Extract final clusters
        merged_clusters = uf.get_clusters()

        # Convert to named subgroups and filter by size
        result = {}
        for i, cluster in enumerate(merged_clusters):
            if len(cluster) >= min_nodes:
                # Generate a meaningful subgroup name
                cluster_list = sorted(list(cluster))

                # Try to find a common prefix for naming, avoiding conflicts
                common_prefix = commonprefix([comp.replace(node_prefix, "") for comp in cluster_list])
                if common_prefix and len(common_prefix) > 2:
                    # Check if this would conflict with existing categories
                    subgroup_name = f"{node_category_prefix}{common_prefix.title()}"
                    if subgroup_name in self.component_by_category:
                        # Avoid conflict by adding parent category context
                        parent_title = self.components[cluster_list[0]].category.replace(node_category_prefix, "")

                        if common_prefix.title() == parent_title:
                            subgroup_name += "Subgroup"
                        else:
                            subgroup_name += parent_title
                else:
                    subgroup_name = f"{node_category_prefix}Subgroup{i + 1}"

                # NOTE: this name is derived from this call's own cluster list
                # only and is not guaranteed unique across separate calls (one
                # per category -- the calling convention #488's ComponentGraph
                # fix will use). Two categories can legitimately derive the identical
                # candidate here. That collision is resolved downstream, at
                # actual declaration time, by _create_subgraph_section -- see
                # its docstring for why the fix lives there and not here.
                result[subgroup_name] = cluster_list

        return result

    def _get_category_display_name(self, category: str) -> str:
        """
        Convert category ID to display name.

        Generates human-readable display names for category IDs, with fallback
        to auto-generated names when YAML configuration is not available.

        Args:
            category (str): Category ID to convert (e.g., "componentsData")

        Returns:
            str: Human-readable display name (e.g., "Data Components")
        """
        # Load category names if not already cached
        if not hasattr(self, "_category_names_cache") or self._category_names_cache is None:
            self._category_names_cache = self._load_category_names()

        category_names = self._category_names_cache

        # Handle dynamically generated category names
        if category not in category_names:
            # Remove "components" prefix and capitalize
            if category.startswith("components"):
                display_name = category.replace("components", "").strip()
            # This isn't an expected dynamic category
            else:
                return category.title()

            if display_name:
                # Add spacing before capital letters for better readability
                import re

                spaced_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", display_name)
                return spaced_name.title()

        return category_names.get(category, category.title())

    def _group_components_by_category(self, w_subcategories: bool = False):
        """Group component IDs by their category (simple mapping without subgroups)."""
        self.component_by_category, self.component_by_subcategory = self._group_node_by("components", True)

    def _group_node_by(
        self, node_type: str, w_subcategories: bool = False
    ) -> tuple[dict[str, list[str]], dict[str, dict[str, list[str]]]]:
        if node_type == "components":
            items = self.components
        else:
            raise ValueError("node_type must be 'components'")

        """Group node IDs by their category (simple mapping without subgroups)."""
        groups: dict[str, list[str]] = {}
        subcat_groups: dict[str, dict[str, list[str]]] = dict()

        # Initialize main categories only - subgrouping handled dynamically in optimization
        for node_id, node in items.items():
            category = node.category

            process_subcategories = False
            subcat: str = ""

            if isinstance(node, ComponentNode) and node.subcategory and w_subcategories:
                process_subcategories = True
                subcat = node.subcategory

            if category not in groups:
                groups[category] = [node_id]
            else:
                groups[category].append(node_id)

            if process_subcategories:
                if category not in subcat_groups:
                    subcat_groups[category] = dict()
                if subcat not in subcat_groups[category]:
                    subcat_groups[category][subcat] = []

                subcat_groups[category][subcat].append(node_id)

        return (groups, subcat_groups)

    def _create_subgraph_section(
        self, category: str, category_name: str, item_ids: list[str], items: dict, indent: str = "    "
    ) -> list[str]:
        """
        Create a subgraph section with items.

        This is a generic utility method for creating Mermaid subgraph sections;
        it is not specific to any one item type (works with components today).

        Args:
            category: Category ID for the subgraph
            category_name: Display name for the subgraph
            item_ids: List of item IDs to include in the subgraph
            items: Dictionary mapping item IDs to objects with .title attributes
            indent: Indentation string for nested subgraphs

        Returns:
            List of Mermaid syntax lines for the subgraph section

        Note:
            A Mermaid graph with two "subgraph <id>" declarations sharing the
            same <id> fails to render. Callers derive `category` independently
            per invocation (see _find_node_clusters), so two different callers
            can legitimately request the same id -- most notably, one
            per-category call to cluster-derived subgroup naming can collide
            with another. This method is the single place every DYNAMICALLY
            (cluster-)derived subgraph id is turned into a declaration, so it
            is the only place that can guarantee that specific invariant for
            those ids: on collision, it declares the requested content under
            a disambiguated id instead of silently overwriting or dropping
            it. It is NOT the only place a literal "subgraph <id>" line is
            written in this codebase -- fixed-id containers (e.g. each parent
            category's own container line in _get_nested_subgraph_new) are
            written directly and never registered here, because their ids
            are schema-fixed and cannot collide the way a derived cluster
            name can. The return type stays
            list[str] (not the (lines, id) tuple that would make the actual
            id explicit) because callers -- including test harnesses -- treat
            the return value as the literal rendered lines; the id actually
            used is always recoverable from the first line.
        """
        subgraph_id = category
        if subgraph_id in self._declared_subgraph_ids:
            suffix = 2
            while (candidate_id := f"{category}{suffix}") in self._declared_subgraph_ids:
                suffix += 1
            subgraph_id = candidate_id
        self._declared_subgraph_ids.add(subgraph_id)

        lines = []
        lines.append(f'{indent}subgraph {subgraph_id} ["{category_name}"]')

        for item_id in sorted(item_ids):
            item = items[item_id]
            lines.append(f"{indent}    {item_id}[{item.title}]")

        lines.append(f"{indent}end")
        lines.append("")
        return lines

    def _get_nested_subgraph_new(
        self, component_ids: list[str], category: str, category_name: str
    ) -> list[str] | None:
        if not (category_subgroups := self.component_by_subcategory.get(category, {})):
            return None

        nested_subgraph = []
        nested_subgraph.append(f'    subgraph {category} ["{category_name}"]')

        for component_id in sorted(component_ids):
            if not self.components[component_id].subcategory:
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

        nested_subgraph.append("    end")
        nested_subgraph.append("")

        return nested_subgraph

    def _get_node_style(self, style_type: str, **kwargs) -> str:
        """
        Get formatted node style string for different node types.

        This is a shared utility method for creating Mermaid node styling
        that can be used by all graph types.

        Args:
            style_type: Type of node styling ('componentCategory' is the only
                        recognized value; anything else falls back to a default)
            **kwargs: Additional parameters specific to style type
                     - For 'componentCategory': category_config dict

        Returns:
            Formatted style string for use in style commands
        """
        if style_type == "componentCategory":
            category_config = kwargs.get("category_config", {})
            fill = category_config.get("fill", "#ffffff")
            stroke = category_config.get("stroke", "#333333")
            stroke_width = category_config.get("strokeWidth", "2px")
            return f"fill:{fill},stroke:{stroke},stroke-width:{stroke_width}"

        else:
            # Default fallback
            return "fill:#ffffff,stroke:#333333,stroke-width:2px"

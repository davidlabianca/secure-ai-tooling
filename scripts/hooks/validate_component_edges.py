#!/usr/bin/env python3
"""
Git Pre-Commit Hook: Component Edge Consistency Validator and Graph Generator

This script validates the integrity of component relationships in YAML configuration files,
ensuring that edge definitions are bidirectionally consistent and identifying orphaned components.
Additionally, it can generate Mermaid graph visualizations of the component relationships.

VALIDATION RULES:
    1. Bidirectional Consistency: Each component's 'to' edges must have corresponding
       'from' edges in the target components
    2. Reverse Consistency: Each component's 'from' edges must have corresponding
       'to' edges in the source components
    3. No Isolation: Components should not exist without any connections (configurable)

GRAPH GENERATION:
    - Generates Mermaid-compatible graph visualizations
    - Automatically calculates topological ranks using zero-based indexing (componentDataSources is always rank 0)
    - Organizes components into category-based subgraphs (Data, Infrastructure, Model, Application)
    - Uses dynamic tilde spacing based on rank hierarchy
    - Supports debug mode for rank annotations

USAGE:
    As a git pre-commit hook:
        python validate_component_edges.py

    For manual validation:
        python validate_component_edges.py --force

    For custom file paths:
        python validate_component_edges.py --file path/to/components.yaml

    Generate component graph visualization:
        python validate_component_edges.py --to-graph output.md

    Generate control-to-component graph visualization:
        python validate_component_edges.py --to-controls-graph controls.md

    Generate graph with debug annotations:
        python validate_component_edges.py --to-graph output.md --debug

    Allow isolated components:
        python validate_component_edges.py --allow-isolated

    Quiet mode (errors only):
        python validate_component_edges.py --quiet

COMMAND LINE OPTIONS:
    --force               Force validation even if files not staged for commit
    --file PATH           Path to YAML file to validate (default: risk-map/yaml/components.yaml)
    --allow-isolated      Allow components with no edges (isolated components)
    --quiet, -q           Minimize output (only show errors)
    --to-graph PATH       Output component graph visualization to specified file
    --to-controls-graph PATH  Output control-to-component graph visualization to specified file
    --debug               Include rank comments in graph output

EXIT CODES:
    0 - All validations passed
    1 - Validation failures found
    2 - Configuration or runtime error

YAML STRUCTURE EXPECTED:
    components:
      - id: component-a
        title: Component A
        category: infrastructure
        edges:
          to:
            - component-b
            - component-c
          from: component-d
      - id: component-b
        title: Component B
        category: application
        edges:
          to: []
          from:
          - component-a

GRAPH OUTPUT FORMAT:
    The generated graph uses Mermaid syntax with:
    - Topological ranking using zero-based indexing (componentDataSources = rank 0)
    - Category-based subgraphs with color coding
    - Dynamic tilde spacing: anchor = 3 + min_node_rank, end = 3 + (global_max_rank - max_node_rank)
    - Optional debug comments showing node ranks
    - Automatic cross-subgraph linkage via anchor nodes

EXAMPLES:
    # Basic validation
    python validate_component_edges.py --force

    # Generate clean graph
    python validate_component_edges.py --force --to-graph component_map.md

    # Generate graph with rank debugging
    python validate_component_edges.py --force --to-graph debug_graph.md --debug

    # Validate custom file with isolated components allowed
    python validate_component_edges.py --file custom/components.yaml --allow-isolated


"""
## Graph generation implementation complete with proper subgraph structure and component placement

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

import yaml

# Configuration Constants
DEFAULT_COMPONENTS_FILE = Path("risk-map/yaml/components.yaml")
SUPPORTED_EXTENSIONS = {".yaml", ".yml"}


class EdgeValidationError(Exception):
    """Custom exception for edge validation failures."""

    pass


class ComponentNode:
    """
    This class encapsulates a component's title and its connections (edges)
    to and from other components. It includes validation to ensure data integrity.
    """

    def __init__(self, title: str, category: str, to_edges: List[str], from_edges: List[str]) -> None:
        """
        Initializes a Component object with validation.

        Args:
            title: The name of the component.
            to_edges: A list of component titles it connects to.
            from_edges: A list of component titles that connect to it.

        Raises:
            TypeError: If arguments are not of the expected type.
            ValueError: If the title is an empty string.
        """
        # Validate and set the title
        if not isinstance(title, str) or not title.strip():
            raise TypeError("The 'title' must be a string consisting of at least one printing character.")
        self.title: str = title

        # Validate and set the category
        if not isinstance(category, str) or not category.strip():
            raise TypeError("The 'category' must be a string consisting of at least one printing character.")
        self.category: str = category

        # Validate and set 'to_edges'
        if not isinstance(to_edges, list) or not all(isinstance(edge, str) for edge in to_edges):
            raise TypeError("The 'to_edges' must be a list of strings.")
        self.to_edges: List[str] = to_edges

        # Validate and set 'from_edges'
        if not isinstance(from_edges, list) or not all(isinstance(edge, str) for edge in from_edges):
            raise TypeError("The 'from_edges' must be a list of strings.")
        self.from_edges: List[str] = from_edges

    def __repr__(self) -> str:
        """
        Provides an unambiguous, official string representation of the object.
        Useful for debugging.
        """
        return (
            f"Component(title='{self.title}', "
            f"category={self.category}, "
            f"to_edges={self.to_edges}, "
            f"from_edges={self.from_edges})"
        )

    def __str__(self) -> str:
        """
        Provides a user-friendly, readable string representation of the object.
        """
        return (
            f"Component '{self.title}':\n"
            f"category: '{self.category}'\n"
            f"  -> Connects To: {self.to_edges}\n"
            f"  <- From: {self.from_edges}"
        )

    def __eq__(self, other) -> bool:
        """
        Defines equality between two Component objects.
        They are equal if their title, to_edges, and from_edges are identical.
        """
        if not isinstance(other, ComponentNode):
            return NotImplemented
        return (
            self.title == other.title
            and self.category == other.category
            and self.to_edges == other.to_edges
            and self.from_edges == other.from_edges
        )


class ControlNode:
    """
    Encapsulates a control's metadata and its relationships to components and risks.
    Used for generating control-to-component graphs.
    """

    def __init__(
        self,
        title: str,
        category: str,
        components: List[str],
        risks: List[str],
        personas: List[str],
    ) -> None:
        """
        Initializes a ControlNode with validation.

        Args:
            title: The control's title
            category: The control category (controlsData, controlsInfrastructure, etc.)
            components: List of component IDs this control applies to
            risks: List of risk IDs this control mitigates
            personas: List of persona IDs responsible for this control

        Raises:
            TypeError: If arguments are not of the expected type.
        """
        if not isinstance(title, str) or not title.strip():
            raise TypeError("Control 'title' must be a non-empty string.")
        self.title: str = title

        if not isinstance(category, str) or not category.strip():
            raise TypeError("Control 'category' must be a non-empty string.")
        self.category: str = category

        if not isinstance(components, list) or not all(isinstance(c, str) for c in components):
            raise TypeError("Control 'components' must be a list of strings.")
        self.components: List[str] = components

        if not isinstance(risks, list) or not all(isinstance(r, str) for r in risks):
            raise TypeError("Control 'risks' must be a list of strings.")
        self.risks: List[str] = risks

        if not isinstance(personas, list) or not all(isinstance(p, str) for p in personas):
            raise TypeError("Control 'personas' must be a list of strings.")
        self.personas: List[str] = personas

    def __repr__(self) -> str:
        return (
            f"ControlNode(title='{self.title}', category='{self.category}', "
            f"components={self.components}, risks={self.risks}, personas={self.personas})"
        )

    def __str__(self) -> str:
        return (
            f"Control '{self.title}':\n"
            f"  Category: {self.category}\n"
            f"  Components: {self.components}\n"
            f"  Risks: {self.risks}\n"
            f"  Personas: {self.personas}"
        )


class RiskNode:
    """
    Encapsulates a risk's metadata for graph generation.
    Used for risk-to-control visualization.
    """

    def __init__(self, title: str, category: str = "") -> None:
        """
        Initializes a RiskNode with validation.

        Args:
            title: The risk's title
            category: The risk category (optional for now)
        """
        if not isinstance(title, str) or not title.strip():
            raise TypeError("Risk 'title' must be a non-empty string.")
        self.title: str = title

        if not isinstance(category, str):
            raise TypeError("Risk 'category' must be a string.")
        self.category: str = category

    def __repr__(self) -> str:
        return f"RiskNode(title='{self.title}', category='{self.category}')"

    def __str__(self) -> str:
        return f"Risk '{self.title}' (Category: {self.category or 'Unknown'})"


class ComponentEdgeValidator:
    """
    Main validator class for component edge consistency.

    This class encapsulates all validation logic and can be easily extended
    with additional validation rules or integrated into other systems.
    """

    def __init__(self, allow_isolated: bool = False, verbose: bool = True):
        """
        Initialize the validator.

        Args:
            allow_isolated: If True, isolated components won't trigger validation failure
            verbose: If True, print detailed validation progress
        """
        self.allow_isolated = allow_isolated
        self.verbose = verbose
        self.components: Dict[str, ComponentNode] = {}
        self.forward_map: Dict[str, List[str]] = {}

    def log(self, message: str, level: str = "info") -> None:
        """Log messages based on verbosity setting."""
        if self.verbose:
            icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
            print(f"   {icons.get(level, 'ℹ️')} {message}")

    def load_yaml_file(self, file_path: Path) -> Optional[Dict]:
        """
        Load and parse YAML file with comprehensive error handling.

        Args:
            file_path: Path to the YAML file

        Returns:
            Parsed YAML data as dictionary, None if loading fails

        Raises:
            EdgeValidationError: If file cannot be loaded or parsed
        """
        try:
            if not file_path.exists():
                raise EdgeValidationError(f"File not found: {file_path}")

            with open(file_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if data is None:
                self.log(
                    f"Warning: {file_path} is empty or contains only comments",
                    "warning",
                )
                return {}

            return data

        except yaml.YAMLError as e:
            raise EdgeValidationError(f"YAML parsing error in {file_path}: {e}")
        except (IOError, OSError) as e:
            raise EdgeValidationError(f"File access error for {file_path}: {e}")

    def extract_component_edges(self, yaml_data: Dict) -> dict[str, ComponentNode]:
        """
        Extract component IDs and their edge relationships from YAML data.

        Args:
            yaml_data: Parsed YAML data

        Returns:
            Dictionary mapping component IDs to their edge definitions
            Format: {component_id: {'to': [targets], 'from': [sources]}}
        """
        components = {}

        if not yaml_data or "components" not in yaml_data:
            self.log("No 'components' section found in YAML data", "warning")
            return components

        for i, component in enumerate(yaml_data["components"]):
            if not isinstance(component, dict):
                self.log(
                    f"Skipping invalid component at index {i}: not a dictionary",
                    "warning",
                )
                continue

            component_id: str | None = component.get("id")
            if not component_id:
                self.log(f"Skipping component at index {i}: missing 'id' field", "warning")
                continue

            if not isinstance(component_id, str):
                self.log(f"Skipping component at index {i}: 'id' must be a string", "warning")
                continue

            # Extract title
            component_title: str | None = component.get("title")
            if not component_title:
                self.log(f"Skipping component at index {i}: missing 'title' field", "warning")
                continue

            if not isinstance(component_title, str):
                self.log(
                    f"Skipping component at index {i}: 'title' must be a string",
                    "warning",
                )
                continue

            # Extract category
            category: str | None = component.get("category")
            if not category:
                self.log(
                    f"Skipping component '{component_id}': missing 'category' field",
                    "warning",
                )
                continue

            if not isinstance(category, str):
                self.log(
                    f"Skipping component '{component_id}': 'category' must be a string",
                    "warning",
                )
                continue

            # Extract edges with default empty lists
            edges = component.get("edges", {})
            if not isinstance(edges, dict):
                self.log(
                    f"Component '{component_id}': 'edges' must be a dictionary, using empty edges",
                    "warning",
                )
                edges = {}

            # Ensure edge lists are actually lists
            to_edges = edges.get("to", [])
            from_edges = edges.get("from", [])

            if not isinstance(to_edges, list):
                self.log(
                    f"Component '{component_id}': 'to' edges must be a list, using empty list",
                    "warning",
                )
                to_edges = []

            if not isinstance(from_edges, list):
                self.log(
                    f"Component '{component_id}': 'from' edges must be a list, using empty list",
                    "warning",
                )
                from_edges = []

            # Create the ComponentNode instance, which handles internal validation
            try:
                components[component_id] = ComponentNode(
                    title=component_title,
                    category=category,
                    to_edges=[str(edge) for edge in to_edges if edge],
                    from_edges=[str(edge) for edge in from_edges if edge],
                )
            except (TypeError, ValueError) as e:
                self.log(
                    f"Skipping component '{component_id}' due to invalid data: {e}",
                    "error",
                )
                continue

        self.log(f"Extracted {len(components)} components from YAML data")
        return components

    def build_edge_maps(
        self, components: dict[str, ComponentNode]
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """
        Build forward and reverse edge mappings for validation.

        Args:
            components: Component edge definitions

        Returns:
            Tuple of (forward_map, reverse_map)
            - forward_map: component -> list of components it points to
            - reverse_map: component -> list of components that point to it
        """
        forward_map = {}
        reverse_map = {}

        for component_id, node in components.items():
            # Forward edges (this component -> other components)
            if node.to_edges:
                forward_map[component_id] = node.to_edges[:]  # Create copy

            # Build reverse mapping from 'from' edges
            for from_node in node.from_edges:
                if from_node not in reverse_map:
                    reverse_map[from_node] = []
                reverse_map[from_node].append(component_id)

        self.forward_map = forward_map  # Store for potential future use

        return forward_map, reverse_map

    def find_isolated_components(self, components: dict[str, ComponentNode]) -> set[str]:
        """
        Identify components with no edges (neither to nor from).

        Args:
            components: Component edge definitions

        Returns:
            Set of isolated component IDs
        """
        isolated = set()

        for component_id, node in components.items():
            if not node.to_edges and not node.from_edges:
                isolated.add(component_id)

        return isolated

    def find_missing_components(self, components: dict[str, ComponentNode]) -> Set[str]:
        """
        Find components that are referenced in edges but don't exist in the components list.

        Args:
            components: Component edge definitions

        Returns:
            Set of missing component IDs
        """
        existing_components = set(components.keys())
        referenced_components = set()

        # Collect all referenced component IDs
        for node in components.values():
            referenced_components.update(node.to_edges)
            referenced_components.update(node.from_edges)

        return referenced_components - existing_components

    def validate_edge_consistency(
        self, forward_map: dict[str, list[str]], reverse_map: dict[str, list[str]]
    ) -> list[str]:
        """
        Compare forward and reverse edge maps to find inconsistencies.

        Args:
            forward_map: Component -> list of outgoing connections
            reverse_map: Component -> list of incoming connections

        Returns:
            List of error messages describing inconsistencies
        """
        errors = []

        # Check forward -> reverse consistency
        for component, targets in forward_map.items():
            if component not in reverse_map:
                errors.append(f"Component '{component}' has outgoing edges but no corresponding incoming edges")
            else:
                expected_incoming = set(targets)
                actual_incoming = set(reverse_map[component])

                missing = expected_incoming - actual_incoming
                extra = actual_incoming - expected_incoming

                if missing:
                    errors.append(
                        f"Component '{component}' → missing incoming edges from: {', '.join(sorted(missing))}"
                    )
                if extra:
                    errors.append(
                        f"Component '{component}' → unexpected incoming edges from: {', '.join(sorted(extra))}"
                    )

        # Check reverse -> forward consistency
        for component in reverse_map.keys():
            if component not in forward_map:
                errors.append(f"Component '{component}' has incoming edges but no corresponding outgoing edges")

        return errors

    def validate_file(self, file_path: Path) -> bool:
        """
        Validate component edge consistency in a single YAML file.

        Args:
            file_path: Path to YAML file to validate

        Returns:
            True if validation passes, False otherwise
        """
        self.log(f"Validating component edges in: {file_path}")

        try:
            # Load and parse YAML
            yaml_data = self.load_yaml_file(file_path)
            if not yaml_data:
                self.log("No data to validate - skipping", "warning")
                return True

            # Extract component edges
            self.components = self.extract_component_edges(yaml_data)

            if not self.components:
                self.log("No components found - skipping validation", "info")
                return True

            # Run all validation checks
            success = True

            # Check for missing component references
            missing_components = self.find_missing_components(self.components)
            if missing_components:
                self.log(
                    f"Found {len(missing_components)} missing component references:",
                    "error",
                )
                for component in sorted(missing_components):
                    self.log(f"  - {component}", "error")
                success = False

            # Check for isolated components
            isolated = self.find_isolated_components(self.components)
            if isolated and not self.allow_isolated:
                self.log(f"Found {len(isolated)} isolated components (no edges):", "error")
                for component in sorted(isolated):
                    self.log(f"  - {component}", "error")
                success = False
            elif isolated:
                self.log(
                    f"Found {len(isolated)} isolated components (allowed by configuration)",
                    "warning",
                )

            # Check edge consistency
            forward_map, reverse_map = self.build_edge_maps(self.components)
            consistency_errors = self.validate_edge_consistency(forward_map, reverse_map)

            if consistency_errors:
                self.log(f"Found {len(consistency_errors)} edge consistency errors:", "error")
                for error in consistency_errors:
                    self.log(f"  - {error}", "error")
                success = False

            if success:
                self.log("Component edges are consistent", "success")

            return success

        except EdgeValidationError as e:
            self.log(f"Validation error: {e}", "error")
            return False


class ComponentGraph:
    """
    Represents the component graph and outputs mermaid.js syntax for rendering
    """

    def __init__(
        self,
        forward_map: Dict[str, List[str]],
        components: dict[str, ComponentNode],
        debug: bool = False,
    ):
        self.components = components
        self.forward_map = forward_map
        self.debug = debug
        self.graph = self.build_graph(debug=debug)

    def build_graph(self, layout="horizontal", debug=False) -> str:
        """
        Build a Mermaid-compatible graph representation with controlled layout.

        Args:
            layout: "horizontal" (data left to right) or "vertical" (data bottom to top)
            debug: If True, include rank comments in the output
        """

        # Calculate node ranks first
        node_ranks = self._calculate_node_ranks()

        # Define category order and layout positioning
        category_order = ["Data", "Infrastructure", "Model", "Application"]

        # Collect components by category first
        components_by_category = {}
        for category in category_order:
            components_by_category[category] = []

        # Categorize all components
        for comp_id, comp_node in self.components.items():
            category = self._normalize_category(comp_id)
            if category not in components_by_category:
                components_by_category[category] = []
            components_by_category[category].append((comp_id, comp_node.title))

        # Build graph structure
        graph_content = [
            "```mermaid",
            "graph TD",
            "    classDef hidden display: none;",
            "",
        ]

        # Add invisible root node
        graph_content.append("    root:::hidden")
        graph_content.append("    ")

        # Build subgraphs (components only, no internal links)
        for category in category_order:
            if category in components_by_category and components_by_category[category]:
                subgraph_lines = self._build_subgraph_structure(
                    category, components_by_category[category], node_ranks, debug
                )
                graph_content.extend(subgraph_lines)

        # Add root connections to lowest rank items in each subgraph
        anchor_connections = []
        for category in category_order:
            if category in components_by_category and components_by_category[category]:
                anchor_name = f"{category}Anchor:::hidden"
                anchor_connections.append(f"    root ~~~ {anchor_name}")

        graph_content.extend(anchor_connections)

        # Add all inter-component connections outside of subgraphs
        graph_content.append("")
        for src, targets in self.forward_map.items():
            src_title = self.components[src].title if src in self.components else src
            for tgt in targets:
                tgt_title = self.components[tgt].title if tgt in self.components else tgt

                # Add connection with optional rank comments
                if debug:
                    src_rank = node_ranks.get(src, 0)
                    tgt_rank = node_ranks.get(tgt, 0)
                    graph_content.append(f"    %% {src} rank {src_rank}, {tgt} rank {tgt_rank}")
                graph_content.append(f"    {src}[{src_title}] --> {tgt}[{tgt_title}]")

        # Add styling
        graph_content.extend(
            [
                "",
                "%% Style definitions",
                "    style Infrastructure fill:#e6f3e6,stroke:#333,stroke-width:2px",
                "    style Data fill:#fff5e6,stroke:#333,stroke-width:2px",
                "    style Application fill:#e6f0ff,stroke:#333,stroke-width:2px",
                "    style Model fill:#ffe6e6,stroke:#333,stroke-width:2px",
                "```",
            ]
        )

        return "\n".join(graph_content)

    def _normalize_category(self, component_id: str) -> str:
        """Normalize category name by removing 'components' prefix."""
        if component_id in self.components:
            category = self.components[component_id].category
            return category.replace("components", "").strip().title()
        return "Unknown"

    def _get_first_component_in_category(self, components_by_category: dict, target_category: str) -> str | None:
        """Get the first component ID in the specified category."""
        if target_category in components_by_category and components_by_category[target_category]:
            return components_by_category[target_category][0][0]
        return None

    def _calculate_node_ranks(self) -> dict[str, int]:
        """
        Calculate the topological rank of each node in the graph using zero-based indexing.
        Rank 0 = root nodes (componentDataSources) or nodes in cycles
        Rank 1 = nodes that depend only on rank 0 nodes
        etc.

        Special handling for nodes with no incoming edges but outgoing connections:
        - Their rank is based on their lowest-ranked target: min_target_rank - 1

        For graphs with cycles, we use a modified approach:
        1. Find strongly connected components (cycles)
        2. Assign same rank to all nodes in a cycle
        3. Calculate ranks based on dependencies between components
        """
        # Build reverse map to find incoming edges
        incoming_edges = {}
        for node in self.components:
            incoming_edges[node] = []

        for src, targets in self.forward_map.items():
            for target in targets:
                if target in incoming_edges:
                    incoming_edges[target].append(src)

        # Initialize ranks
        ranks = {}

        # Hardcode componentDataSources as the single root (rank 0 - zero-based)
        if "componentDataSources" in self.components:
            ranks["componentDataSources"] = 0
        else:
            # Fallback if componentDataSources doesn't exist
            if self.components:
                first_node = next(iter(self.components))
                ranks[first_node] = 0

        # Calculate ranks for remaining nodes using iterative approach
        max_iterations = len(self.components) * 2  # Prevent infinite loops
        iteration = 0

        while iteration < max_iterations:
            changed = False
            iteration += 1

            for node in self.components:
                if node not in ranks:
                    dependencies = incoming_edges[node]

                    # If node has dependencies, check if any have ranks
                    ranked_deps = [dep for dep in dependencies if dep in ranks]

                    if ranked_deps:
                        # Use maximum rank of ranked dependencies + 1
                        # This ensures proper topological ordering
                        max_dep_rank = max(ranks[dep] for dep in ranked_deps)
                        ranks[node] = max_dep_rank + 1
                        changed = True
                    elif not dependencies and node in self.forward_map:
                        # Node has no incoming edges but has outgoing edges (not isolated)
                        # Find the lowest ranked target and set rank = target_rank - 1
                        targets = self.forward_map[node]
                        ranked_targets = [target for target in targets if target in ranks]

                        if ranked_targets:
                            min_target_rank = min(ranks[target] for target in ranked_targets)
                            ranks[node] = max(0, min_target_rank - 1)  # Ensure non-negative
                            changed = True

            if not changed:
                break

        # Handle any remaining unranked nodes (nodes in cycles without ranked dependencies)
        for node in self.components:
            if node not in ranks:
                ranks[node] = 0  # Assign rank 0 to break cycles

        return ranks

    def _build_subgraph_structure(
        self,
        category: str,
        components: list,
        node_ranks: dict[str, int],
        debug: bool = False,
    ) -> list:
        """
        Build a single subgraph structure with proper anchor and end elements.

        Args:
            category: Subgraph category name (Data, Infrastructure, Model, Application)
            components: List of (component_id, component_title) tuples in this category
            node_ranks: Dictionary mapping component IDs to their zero-based ranks
            debug: If True, include debug comments with rank information

        Returns:
            List of Mermaid syntax lines for the subgraph

        Tilde calculation formula:
        - anchor_tildes = 3 + min_node_rank_in_subgraph
        - end_tildes = 3 + (global_max_rank - max_node_rank_in_subgraph)
        - global_max_rank = 11 (highest component rank 9 + 2 for anchor/end spacing)
        """
        subgraph_lines = [f"subgraph {category}"]

        # Calculate global max rank (highest node rank is 9 with zero-based, plus 2 for anchor/end = 11 total)
        global_max_rank = 11

        # Add min rank comment if debug
        if debug and components:
            min_rank = min(node_ranks.get(comp_id, 0) for comp_id, _ in components)
            subgraph_lines.append(f"%% min = {min_rank}")

        # Add anchor node and end connections only if we have components
        if components:
            # Find lowest and highest rank components in this subgraph
            components_with_ranks = [
                (comp_id, comp_title, node_ranks.get(comp_id, 0)) for comp_id, comp_title in components
            ]
            lowest_rank_comp = min(components_with_ranks, key=lambda x: x[2])
            highest_rank_comp = max(components_with_ranks, key=lambda x: x[2])

            min_node_rank_in_subgraph = lowest_rank_comp[2]
            max_node_rank_in_subgraph = highest_rank_comp[2]

            # Calculate tilde counts using the formula:
            # anchor_incr = min_node_in_subgraph_rank
            # end_incr = max_rank - max_node_rank_in_subgraph
            anchor_incr = min_node_rank_in_subgraph
            end_incr = global_max_rank - max_node_rank_in_subgraph

            # Minimum 3 tildes + increment
            anchor_tilde_count = 3 + anchor_incr
            end_tilde_count = 3 + end_incr

            # Add anchor node
            anchor_name = f"{category}Anchor:::hidden"
            anchor_tildes = "~" * anchor_tilde_count
            subgraph_lines.append(f"    {anchor_name} {anchor_tildes} {lowest_rank_comp[0]}")

            # Add all components with optional rank comments
            for comp_id, comp_title in components:
                if debug:
                    rank = node_ranks.get(comp_id, 1)
                    subgraph_lines.append(f"    %% {comp_id} Rank {rank}")
                subgraph_lines.append(f"    {comp_id}[{comp_title}]")

            # Add highest rank to end element connection
            end_name = f"{category}End:::hidden"
            end_tildes = "~" * end_tilde_count
            subgraph_lines.append(f"    {highest_rank_comp[0]} {end_tildes} {end_name}")

            if debug:
                subgraph_lines.append(f"%% anchor_incr={anchor_incr}, end_incr={end_incr}")

        subgraph_lines.append("end")
        return subgraph_lines

    def to_mermaid(self) -> str:
        return self.graph


class ControlGraph:
    """
    Generates Mermaid graph visualization for control-to-component relationships.
    """

    def __init__(
        self,
        controls: Dict[str, ControlNode],
        components: Dict[str, ComponentNode],
        debug: bool = False,
    ):
        """
        Initialize ControlGraph with controls and components data.

        Args:
            controls: Dictionary mapping control IDs to ControlNode objects
            components: Dictionary mapping component IDs to ComponentNode objects
            debug: Whether to include debug information in output
        """
        self.controls = controls
        self.components = components
        self.debug = debug

        # Build mappings for graph generation
        self.control_to_component_map = self._build_control_component_mapping()
        self.controls_mapped_to_all = self._track_controls_mapped_to_all()
        self.control_by_category = self._group_controls_by_category()
        self.component_by_category = self._group_components_by_category()

    def _build_control_component_mapping(self) -> Dict[str, List[str]]:
        """
        Build mapping of control IDs to component IDs they apply to.
        Handles special cases: 'all', 'none', and specific component lists.

        Returns:
            Dictionary mapping control IDs to lists of component IDs
        """
        mapping = {}
        all_component_ids = list(self.components.keys())

        for control_id, control in self.controls.items():
            if control.components == ["all"]:
                # Control applies to all components
                mapping[control_id] = all_component_ids.copy()
            elif control.components == ["none"] or not control.components:
                # Control applies to no components
                mapping[control_id] = []
            else:
                # Control applies to specific components
                # Filter to only include components that actually exist
                valid_components = [comp_id for comp_id in control.components if comp_id in self.components]
                mapping[control_id] = valid_components

        return mapping

    def _track_controls_mapped_to_all(self) -> Set[str]:
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

    def _group_controls_by_category(self) -> Dict[str, List[str]]:
        """Group control IDs by their category."""
        groups = {}
        for control_id, control in self.controls.items():
            category = control.category
            if category not in groups:
                groups[category] = []
            groups[category].append(control_id)
        return groups

    def _group_components_by_category(self) -> Dict[str, List[str]]:
        """Group component IDs by their category."""
        groups = {}
        for comp_id, component in self.components.items():
            category = component.category
            if category not in groups:
                groups[category] = []
            groups[category].append(comp_id)
        return groups

    def _get_category_display_name(self, category: str) -> str:
        """Convert category ID to display name."""
        category_names = {
            # Control categories
            "controlsData": "Data Controls",
            "controlsInfrastructure": "Infrastructure Controls",
            "controlsModel": "Model Controls",
            "controlsApplication": "Application Controls",
            "controlsAssurance": "Assurance Controls",
            "controlsGovernance": "Governance Controls",
            # Component categories
            "componentsData": "Data Components",
            "componentsInfrastructure": "Infrastructure Components",
            "componentsModel": "Model Components",
            "componentsApplication": "Application Components",
        }
        return category_names.get(category, category.title())

    def build_controls_graph(self) -> str:
        """
        Build Mermaid graph showing control-to-component relationships.

        Returns:
            Mermaid graph syntax as a string
        """
        lines = [
            "graph LR",
            "    classDef hidden display: none;",
            "    classDef allControl stroke:#4285f4,stroke-width:2px,stroke-dasharray: 5 5;",
            "",
        ]

        # Add control subgraphs
        for category, control_ids in self.control_by_category.items():
            if not control_ids:
                continue

            category_name = self._get_category_display_name(category)
            lines.append(f'    subgraph "{category_name}"')

            for control_id in sorted(control_ids):
                control = self.controls[control_id]
                lines.append(f"        {control_id}[{control.title}]")

            lines.append("    end")
            lines.append("")

        # Add component subgraphs
        for category, comp_ids in self.component_by_category.items():
            if not comp_ids:
                continue

            category_name = self._get_category_display_name(category)
            lines.append(f'    subgraph "{category_name}"')

            for comp_id in sorted(comp_ids):
                component = self.components[comp_id]
                lines.append(f"        {comp_id}[{component.title}]")

            lines.append("    end")
            lines.append("")

        # Add control-to-component relationships
        lines.append("    %% Control to Component relationships")
        for control_id, component_ids in self.control_to_component_map.items():
            if not component_ids:  # Skip controls with no component mappings
                continue

            # Check if this control was originally mapped to "all"
            is_all_control = control_id in self.controls_mapped_to_all

            for comp_id in sorted(component_ids):
                if comp_id in self.components:  # Ensure component exists
                    if is_all_control:
                        # Use dotted arrow for controls mapped to "all"
                        lines.append(f"    {control_id} -.-> {comp_id}")
                    else:
                        # Use solid arrow for specific control mappings
                        lines.append(f"    {control_id} --> {comp_id}")

        # Apply styling to controls that were mapped to "all"
        lines.append("")
        lines.append("    %% Apply styling to controls mapped to 'all'")
        for control_id in sorted(self.controls_mapped_to_all):
            if control_id in self.control_to_component_map and self.control_to_component_map[control_id]:
                lines.append(f"    {control_id} :::allControl")

        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """Generate the Mermaid graph output."""
        return self.build_controls_graph()


def parse_controls_yaml(file_path: Path = None) -> Dict[str, ControlNode]:
    """
    Parse controls.yaml file and return dictionary of ControlNode objects.

    Args:
        file_path: Path to controls.yaml file. Defaults to risk-map/yaml/controls.yaml

    Returns:
        Dictionary mapping control IDs to ControlNode objects

    Raises:
        FileNotFoundError: If controls.yaml file doesn't exist
        yaml.YAMLError: If YAML parsing fails
        KeyError: If required fields are missing
    """
    if file_path is None:
        file_path = Path("risk-map/yaml/controls.yaml")

    if not file_path.exists():
        raise FileNotFoundError(f"Controls file not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        controls = {}

        for control_data in data.get("controls", []):
            control_id = control_data["id"]
            title = control_data["title"]
            category = control_data["category"]

            # Handle components field - can be list, "all", or "none"
            components_raw = control_data.get("components", [])
            if isinstance(components_raw, str):
                components = [components_raw]  # Convert "all" or "none" to list
            elif isinstance(components_raw, list):
                components = components_raw
            else:
                components = []

            # Handle risks and personas fields
            risks = control_data.get("risks", [])
            personas = control_data.get("personas", [])

            # Ensure all fields are lists of strings
            if not isinstance(risks, list):
                risks = []
            if not isinstance(personas, list):
                personas = []

            controls[control_id] = ControlNode(
                title=title, category=category, components=components, risks=risks, personas=personas
            )

        return controls

    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error parsing controls YAML: {e}")
    except KeyError as e:
        raise KeyError(f"Missing required field in controls.yaml: {e}")


def get_staged_yaml_files(target_file: Path | None = None, force_check: bool = False) -> List[Path]:
    """
    Get YAML files that are staged for commit or force check specific file.

    Args:
        target_file: Specific file to check (defaults to DEFAULT_COMPONENTS_FILE)
        force_check: If True, return target file regardless of git status

    Returns:
        List of Path objects for files to validate
    """
    if target_file is None:
        target_file = DEFAULT_COMPONENTS_FILE

    # Force check mode - return file if it exists
    if force_check:
        if target_file.exists():
            return [target_file]
        else:
            print(f"  ⚠️  Target file {target_file} does not exist")
            return []

    try:
        # Get all staged files from git
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )

        staged_files = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # Filter for our target file
        if str(target_file) in staged_files and target_file.exists():
            return [target_file]
        else:
            return []

    except subprocess.CalledProcessError as e:
        print(f"⚠️  Error getting staged files: {e}")
        print("   Make sure you're in a git repository")
        return []
    except FileNotFoundError:
        print("⚠️  Git command not found - make sure git is installed")
        return []


def parse_args() -> argparse.Namespace:
    """
    Parse and validate command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Validate component edge consistency in YAML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Check staged components.yaml
  %(prog)s --force                            # Force check default file
  %(prog)s --file custom/components.yaml      # Check specific file
  %(prog)s --allow-isolated                   # Allow components with no edges
  %(prog)s --to-graph graph.md                # Output component graph as .md code block
  %(prog)s --to-controls-graph controls.md    # Output control-to-component graph
  %(prog)s --quiet                            # Minimal output
  %(prog)s --help                             # Show this help

Exit Codes:
  0 - All validations passed
  1 - Validation failures found
  2 - Configuration or runtime error
        """,
    )

    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force validation even if files not staged for commit",
    )

    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_COMPONENTS_FILE,
        help=f"Path to YAML file to validate (default: {DEFAULT_COMPONENTS_FILE})",
    )

    parser.add_argument(
        "--allow-isolated",
        action="store_true",
        help="Allow components with no edges (isolated components)",
    )

    parser.add_argument("--quiet", "-q", action="store_true", help="Minimize output (only show errors)")

    parser.add_argument(
        "--to-graph",
        type=Path,
        help="Output component graph visualization to specified txt file",
    )

    parser.add_argument(
        "--to-controls-graph",
        type=Path,
        help="Output control-to-component graph visualization to specified file",
    )

    parser.add_argument("--debug", action="store_true", help="Include rank comments in graph output")

    return parser.parse_args()


def main() -> None:
    """
    Main entry point for the component edge validator.

    Designed to be used as a git pre-commit hook or standalone validation tool.
    Exit codes follow standard conventions for shell integration.
    """
    try:
        args = parse_args()

        # Initialize validator
        validator = ComponentEdgeValidator(allow_isolated=args.allow_isolated, verbose=not args.quiet)

        if not args.quiet:
            if args.force:
                print("🔍 Force checking components...")
            else:
                print("🔍 Checking for staged YAML files...")

        # Get files to validate
        yaml_files = get_staged_yaml_files(args.file, args.force)

        if not yaml_files:
            if not args.quiet:
                print("   No YAML files to validate - skipping")
            sys.exit(0)

        if not args.quiet:
            file_count = len(yaml_files)
            file_word = "file" if file_count == 1 else "files"
            print(f"   Found {file_count} YAML {file_word} to validate")

        # Validate all files
        all_valid = True
        for yaml_file in yaml_files:
            if not validator.validate_file(yaml_file):
                all_valid = False
            if not args.quiet and len(yaml_files) > 1:
                print()  # Add spacing between files

        # Report final results
        if not all_valid:
            print("❌ Component edge validation failed!")
            print("   Fix the above errors before committing.")
            sys.exit(1)

        if not args.quiet:
            print("✅ All YAML files passed component edge validation")

        if args.to_graph:
            graph = ComponentGraph(validator.forward_map, validator.components, debug=args.debug)
            try:
                graph_output = graph.to_mermaid()
                # Write graph_output to file
                with open(args.to_graph, "w", encoding="utf-8") as f:
                    f.write(graph_output)

                print(f"   Graph visualization saved to {args.to_graph}")
            except Exception as e:
                print(f"⚠️  Failed to generate graph: {e}")

        if args.to_controls_graph:
            try:
                # Parse controls and generate controls graph
                controls = parse_controls_yaml()
                control_graph = ControlGraph(controls, validator.components, debug=args.debug)

                controls_graph_output = control_graph.to_mermaid()

                # Write controls graph to file
                with open(args.to_controls_graph, "w", encoding="utf-8") as f:
                    f.write(controls_graph_output)

                print(f"   Controls graph visualization saved to {args.to_controls_graph}")
            except Exception as e:
                print(f"⚠️  Failed to generate controls graph: {e}")

        sys.exit(0)

    except KeyboardInterrupt:
        print("\n⚠️  Validation interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print("   Please report this issue to the maintainers")
        sys.exit(2)


if __name__ == "__main__":
    main()

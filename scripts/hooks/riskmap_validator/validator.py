"""
Core validation logic for component edge consistency.

Provides the ComponentEdgeValidator class that validates bidirectional
edge consistency in component relationship YAML files.

Dependencies:
    - PyYAML: For YAML file parsing
    - .models: ComponentNode data model
"""

from pathlib import Path

import yaml

from .models import ComponentNode


class EdgeValidationError(Exception):
    """Custom exception for edge validation failures."""

    pass

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
        self.components: dict[str, ComponentNode] = {}
        self.forward_map: dict[str, list[str]] = {}

    def log(self, message: str, level: str = "info") -> None:
        """Log messages based on verbosity setting."""
        if self.verbose:
            icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
            print(f"   {icons.get(level, 'ℹ️')} {message}")

    def load_yaml_file(self, file_path: Path) -> dict | None:
        """
        Load and parse YAML file with error handling.

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

    def extract_component_edges(self, yaml_data: dict) -> dict[str, ComponentNode]:
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

    def find_missing_components(self, components: dict[str, ComponentNode]) -> set[str]:
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


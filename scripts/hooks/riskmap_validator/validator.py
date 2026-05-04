"""
Core validation logic for component edge consistency and lifecycle stage ordering.

Provides the ComponentEdgeValidator class that validates bidirectional
edge consistency in component relationship YAML files, and the
check_lifecycle_stage_order_uniqueness function that validates order
uniqueness across lifecycle stage entries.

Dependencies:
    - PyYAML: For YAML file parsing
    - .models: ComponentNode data model
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import ComponentNode
from .utils import parse_components_yaml


class EdgeValidationError(Exception):
    """Custom exception for edge validation failures."""

    pass


class ComponentEdgeValidator:
    """
    Validates component edge consistency.

    Encapsulates validation logic and can be extended with additional rules.
    """

    def __init__(self, allow_isolated: bool = False, verbose: bool = True):
        """
        Initialize validator.

        Args:
            allow_isolated: If True, isolated components don't cause failure
            verbose: If True, print detailed progress
        """
        self.allow_isolated = allow_isolated
        self.verbose = verbose
        self.components: dict[str, ComponentNode] = {}
        self.forward_map: dict[str, list[str]] = {}

    def log(self, message: str, level: str = "info") -> None:
        """Log messages if verbose enabled."""
        if self.verbose:
            icons = {"info": "ℹ️", "success": "✅", "warning": "⚠️", "error": "❌"}
            print(f"   {icons.get(level, 'ℹ️')} {message}")

    def build_edge_maps(
        self, components: dict[str, ComponentNode]
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        """
        Build forward and reverse edge mappings.

        Args:
            components: Component edge definitions

        Returns:
            Tuple of (forward_map, reverse_map) for edge validation
        """
        forward_map = {}
        reverse_map = {}

        for component_id, node in components.items():
            # Forward edges: this component → other components
            if node.to_edges:
                forward_map[component_id] = node.to_edges[:]  # Create copy

            # Build reverse mapping from from_edges
            for from_node in node.from_edges:
                if from_node not in reverse_map:
                    reverse_map[from_node] = []
                reverse_map[from_node].append(component_id)

        self.forward_map = forward_map  # Store for potential future use

        return forward_map, reverse_map

    def find_isolated_components(self, components: dict[str, ComponentNode]) -> set[str]:
        """
        Find components with no edges.

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
        Find referenced components that don't exist.

        Returns:
            Set of missing component IDs
        """
        existing_components = set(components.keys())
        referenced_components = set()

        # Collect all referenced components
        for node in components.values():
            referenced_components.update(node.to_edges)
            referenced_components.update(node.from_edges)

        return referenced_components - existing_components

    def validate_edge_consistency(
        self, forward_map: dict[str, list[str]], reverse_map: dict[str, list[str]]
    ) -> list[str]:
        """
        Compare edge maps to find inconsistencies.

        Args:
            forward_map: Component → outgoing connections
            reverse_map: Component → incoming connections

        Returns:
            List of error messages
        """
        errors = []

        # Check forward → reverse consistency
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

        # Check reverse → forward consistency
        for component in reverse_map.keys():
            if component not in forward_map:
                errors.append(f"Component '{component}' has incoming edges but no corresponding outgoing edges")

        return errors

    def validate_file(self, file_path: Path) -> bool:
        """
        Validate component edge consistency in YAML file.

        Args:
            file_path: Path to YAML file

        Returns:
            True if validation passes, False otherwise
        """
        self.log(f"Validating component edges in: {file_path}")

        try:
            self.components = parse_components_yaml(file_path)

            if not self.components:
                self.log("No components found - skipping validation", "info")
                return True

            # Run validation checks
            success = True

            # Check for missing components
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


# ---------------------------------------------------------------------------
# Lifecycle stage order uniqueness check (ADR-022 D4)
# ---------------------------------------------------------------------------


@dataclass
class LifecycleOrderCheckResult:
    """
    Result of a lifecycle stage order uniqueness check.

    Attributes:
        is_valid: True when all order values are unique, False if any duplicate found.
        errors: List of human-readable error strings, empty on success.
    """

    is_valid: bool
    errors: list[str] = field(default_factory=list)


def check_lifecycle_stage_order_uniqueness(data: dict[str, Any]) -> LifecycleOrderCheckResult:
    """
    Check that every lifecycleStage carries a unique order value.

    Per ADR-022 D4: uniqueness across array items is awkward in JSON Schema;
    this validator check is the cleaner path. This function blocks immediately
    on any duplicate — there is no warn-only mode, because the corpus is clean
    at landing.

    The function assumes each stage dict contains an 'order' key (integer). Structural
    validation (missing keys, wrong types) is the schema layer's responsibility.

    Args:
        data: Parsed lifecycle-stage YAML content, expected shape:
              {"lifecycleStages": [{"id": str, "order": int, ...}, ...]}

    Returns:
        LifecycleOrderCheckResult with is_valid=True and empty errors if all
        order values are unique; is_valid=False and a non-empty errors list
        identifying each set of colliding stage IDs and the duplicated value.
    """
    stages: list[dict[str, Any]] = data.get("lifecycleStages", [])

    # Map each order value to the list of stage IDs that carry it.
    order_to_ids: dict[int, list[str]] = {}
    for stage in stages:
        order = stage["order"]
        stage_id = stage["id"]
        order_to_ids.setdefault(order, []).append(stage_id)

    errors: list[str] = []
    for order_value, ids in order_to_ids.items():
        if len(ids) > 1:
            # Include both the duplicated value and all colliding IDs so a developer
            # reading CI output can locate the defect without inspecting the YAML directly.
            colliders = ", ".join(ids)
            errors.append(
                f"Duplicate lifecycleStage order value {order_value}: stages [{colliders}] all carry this order"
            )

    return LifecycleOrderCheckResult(is_valid=len(errors) == 0, errors=errors)

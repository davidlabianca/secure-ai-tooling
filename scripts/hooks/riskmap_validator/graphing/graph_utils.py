import json
from pathlib import Path
from typing import Any

import yaml

from ..config import DEFAULT_COMPONENTS_SCHEMA_FILE, DEFAULT_MERMAID_CONFIG_FILE

# ---------------------------------------------------------------------------
# Schema category helper
# ---------------------------------------------------------------------------

_schema_categories_cache: set[str] | None = None


class SchemaCategoriesUnavailableError(RuntimeError):
    """Raised when component category IDs cannot be read from the schema.

    Callers that use the category set as an assertion (the category
    style guard) must surface this rather than proceed with an
    empty set, which would make every category-keyed check iterate nothing
    and report success.
    """


def _get_schema_categories() -> set[str]:
    """
    Read component category IDs from components.schema.json, with caching.

    Resolves the schema path relative to the current working directory, the
    same way components.yaml, controls.yaml and mermaid-styles.yaml are
    resolved (see riskmap_validator.config). Resolving it from this module's
    own location instead breaks wherever the module tree is relocated
    relative to the corpus — notably CI, which copies validate_riskmap.py and
    riskmap_validator/* to the repo root before running them from there.

    Returns:
        Non-empty set of category ID strings declared in the schema enum.

    Raises:
        SchemaCategoriesUnavailableError: The schema is missing, unreadable,
            not valid JSON, structured unexpectedly, or declares an empty
            category enum. Failures are not cached, so a later call from a
            working directory that does have the schema still succeeds.
    """
    global _schema_categories_cache
    if _schema_categories_cache is not None:
        return _schema_categories_cache

    schema_path = DEFAULT_COMPONENTS_SCHEMA_FILE
    try:
        with open(schema_path, encoding="utf-8") as fh:
            schema = json.load(fh)
        categories = set(schema["definitions"]["category"]["properties"]["id"]["enum"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        raise SchemaCategoriesUnavailableError(
            f"Could not read component categories from {schema_path} (resolved from the "
            f"current working directory): {e}"
        ) from e

    if not categories:
        raise SchemaCategoriesUnavailableError(
            f"{schema_path} declares an empty definitions.category.properties.id enum; "
            f"no component categories to check"
        )

    _schema_categories_cache = categories
    return _schema_categories_cache


def clear_schema_categories_cache() -> None:
    """Drop the cached category set so the next call re-reads from disk.

    The cache is a module-level global keyed on nothing, so anything that
    changes the working directory within a single process — tests, most of
    all — must clear it or leak one directory's categories into another's.
    """
    global _schema_categories_cache
    _schema_categories_cache = None


class MermaidStylesUnavailableError(RuntimeError):
    """Raised when styling must come from real config but does not.

    MermaidConfigLoader answers every style lookup, falling back to
    _get_emergency_defaults() when the configured file cannot be loaded. That
    keeps graph rendering working, but callers that use the styling config as
    an assertion (the category style guard) must distinguish the two and
    surface this rather than accept the hardcoded defaults as configuration.
    """


class MermaidConfigLoader:
    """
    Loads Mermaid styling configuration from YAML files with caching and fallbacks.

    Uses singleton pattern per file path. Provides emergency defaults if config fails to load.
    Thread-safe for read operations after initial loading.

    Fallback hierarchy: YAML config → emergency defaults → minimal defaults
    """

    _instances = {}  # Class-level cache for singleton pattern

    def __init__(self, config_file: Path = None) -> None:
        """
        Initialize with optional custom configuration file.

        Implements singleton pattern per file path to prevent duplicate loading.
        """
        self.config_file = config_file or DEFAULT_MERMAID_CONFIG_FILE
        self._config = None
        self._loaded = False
        self._load_error = None

    @classmethod
    def get_instance(cls, config_file: Path = None) -> "MermaidConfigLoader":
        """
        Get singleton instance for specified config file.
        """
        file_key = str(config_file or DEFAULT_MERMAID_CONFIG_FILE)
        if file_key not in cls._instances:
            cls._instances[file_key] = cls(config_file)
        return cls._instances[file_key]

    def _load_config(self) -> bool:
        """
        Load configuration from YAML file with error handling.

        Returns:
            True if loaded successfully, False otherwise
        """
        if self._loaded:
            return self._config is not None

        self._loaded = True

        try:
            if not self.config_file.exists():
                self._load_error = f"Configuration file not found: {self.config_file}"
                return False

            with open(self.config_file, "r", encoding="utf-8") as f:
                self._config = yaml.safe_load(f)

            if not isinstance(self._config, dict):
                self._load_error = f"Configuration file contains invalid YAML structure: {self.config_file}"
                self._config = None
                return False

            # Validate required top-level keys
            required_keys: list[str] = ["version", "foundation", "sharedElements", "graphTypes"]
            missing_keys: list[str] = [key for key in required_keys if key not in self._config]
            if missing_keys:
                self._load_error = f"Configuration missing required keys: {missing_keys}"
                self._config = None
                return False

            return True

        except yaml.YAMLError as e:
            self._load_error = f"YAML parsing error in {self.config_file}: {e}"
            self._config = None
            return False
        except Exception as e:
            self._load_error = f"Unexpected error loading {self.config_file}: {e}"
            self._config = None
            return False

    def _get_emergency_defaults(self) -> dict:
        """
        Get hardcoded emergency defaults for graph generation.

        Ensures graphs work even if config file is missing or corrupt.
        """
        return {
            "version": "1.0.0",
            "foundation": {
                "colors": {
                    "primary": "#4285f4",
                    "success": "#34a853",
                    "accent": "#9c27b0",
                    "warning": "#ff9800",
                    "error": "#e91e63",
                    "neutral": "#333333",
                    "lightGray": "#f0f0f0",
                    "darkGray": "#666666",
                }
            },
            "sharedElements": {
                "componentCategories": {
                    "componentsInfrastructure": {
                        "fill": "#e6f3e6",
                        "stroke": "#333333",
                        "strokeWidth": "2px",
                    },
                    "componentsData": {
                        "fill": "#fff5e6",
                        "stroke": "#333333",
                        "strokeWidth": "2px",
                    },
                    "componentsApplication": {
                        "fill": "#e6f0ff",
                        "stroke": "#333333",
                        "strokeWidth": "2px",
                    },
                    "componentsModel": {
                        "fill": "#ffe6e6",
                        "stroke": "#333333",
                        "strokeWidth": "2px",
                    },
                    "componentsExternalTools": {
                        "fill": "#f3e6ff",
                        "stroke": "#333333",
                        "strokeWidth": "2px",
                    },
                },
            },
            "graphTypes": {
                "component": {
                    "direction": "TD",
                    "flowchartConfig": {"nodeSpacing": 25, "rankSpacing": 30, "padding": 5, "wrappingWidth": 250},
                },
            },
        }

    def _get_safe_value(self, *path, default=None):
        """
        Get nested value from config with fallback to emergency defaults.

        Traverses config using key path. Falls back to emergency defaults, then final default.

        Args:
            *path: Sequence of keys to traverse (e.g., 'sharedElements', 'componentCategories')
            default: Final fallback value if not found

        Returns:
            Value at path, or default if not found
        """
        use_defaults = False
        use_emergency_defaults = False

        # Get emergency defaults once to avoid multiple calls
        emergency_defaults: dict[Any, Any] = self._get_emergency_defaults()

        # Load config if not already loaded
        if not self._load_config():
            if not isinstance(emergency_defaults, dict):
                use_defaults = True  # Emergency defaults invalid - use final default
            config: dict[Any, Any] = emergency_defaults
        else:
            if not isinstance(self._config, dict):
                config = {}
                use_emergency_defaults = True  # Primary config invalid - use emergency defaults
            else:
                config = self._config

        # Short-circuit if only final default is available
        if use_emergency_defaults and use_defaults:
            return default

        # Navigate config path using EAFP (try/except)
        try:
            current: dict[Any, Any] = config
            for key in path:
                current = current[key]
            return current
        except (KeyError, TypeError):
            # Path not found in primary config - try emergency defaults
            if use_defaults:
                return default  # Skip emergency defaults if already determined invalid
            else:
                try:
                    emergency_current: dict[Any, Any] = emergency_defaults
                    for emergency_key in path:
                        emergency_current = emergency_current[emergency_key]
                    return emergency_current
                except (KeyError, TypeError):
                    # Path not in emergency defaults either - use final default
                    return default

    def _create_flowchart_preamble(self, graph_config: dict) -> list[str] | None:
        """
        Generate Mermaid flowchart preamble from configuration.

        Creates graph declaration, initialization config, and CSS class definitions.

        Args:
            graph_config: Config dict with direction and flowchartConfig

        Returns:
            List of Mermaid syntax lines, or None if config invalid
        """
        if not isinstance(graph_config, dict) or not graph_config:
            return None

        graph_direction = graph_config.get("direction", "LR")
        flowchart_config = graph_config.get("flowchartConfig", {})
        node_spacing = flowchart_config.get("nodeSpacing", 25)
        rank_spacing = flowchart_config.get("rankSpacing", 30)
        node_padding = flowchart_config.get("padding", 5)
        wrapping_width = flowchart_config.get("wrappingWidth", 250)

        flowchart_params = f"'nodeSpacing': {node_spacing}, 'rankSpacing': {rank_spacing}"
        flowchart_params += f", 'padding': {node_padding}, 'wrappingWidth': {wrapping_width}"
        flowchart_init = flowchart_params
        mermaid_config = f"%%{{init: {{'flowchart': {{{flowchart_init}}}}}}}%%"

        lines: list[str] = []

        if frontmatter_config := graph_config.get("metadata"):  # Optional frontmatter config
            layout = frontmatter_config.get("layout")
            merge_edges = frontmatter_config.get("mergeEdges")
            node_strategy = frontmatter_config.get("nodePlacementStrategy")
            lines.extend(
                [
                    "---",
                    "config:",
                    f"  layout: {layout}",
                    "  elk:",
                    f"    mergeEdges: {merge_edges}",
                    f"    nodePlacementStrategy: {node_strategy}",
                    "---",
                    "",
                ]
            )

        lines.extend(
            [
                f"graph {graph_direction}",
                f"   {mermaid_config}",
                "",
            ]
        )

        return lines

    def get_component_category_styles(self) -> dict:
        """
        Get component category styling configuration.

        Returns styling for each category: fill, stroke, strokeWidth.
        Used by ComponentGraph for visual differentiation.

        Returns:
            Dict mapping category IDs to style properties, empty if not found
        """
        result = self._get_safe_value("sharedElements", "componentCategories", default={})
        return result if isinstance(result, dict) else {}

    def get_missing_category_warnings(self, schema_categories: set[str]) -> list[str]:
        """
        Return one warning string per schema category absent from styling config.

        Checks schema_categories against the keys in
        sharedElements.componentCategories in the loaded config (or emergency
        defaults). Direction is schema → styling only: extra styling keys that
        the schema does not enumerate are ignored and produce no warning.

        Args:
            schema_categories: Set of category IDs declared by
                components.schema.json (e.g. from the "id" enum). Caller is
                responsible for deriving this set; this method does not load
                the schema itself.

        Returns:
            List of warning strings, one per missing category. Each string
            contains the missing category ID. Returns [] when every schema
            category has a styling entry, or when schema_categories is empty.
        """
        if not schema_categories:
            return []

        styled_keys = set(self.get_component_category_styles().keys())
        return [
            f"Missing styling entry for component category '{cat}' in componentCategories config"
            for cat in schema_categories
            if cat not in styled_keys
        ]

    def emit_missing_category_warnings(self, schema_categories: set[str]) -> None:
        """
        Emit a warning for each schema category absent from styling config.

        Thin wrapper around get_missing_category_warnings() that surfaces
        warnings via the standard warnings module so they are visible to
        operators at runtime without requiring callers to inspect the return
        value.

        Args:
            schema_categories: Set of category IDs declared by
                components.schema.json. See get_missing_category_warnings().
        """
        import warnings

        for message in self.get_missing_category_warnings(schema_categories):
            warnings.warn(message, stacklevel=2)

    def get_graph_config(self, graph_type: str) -> tuple[dict, list]:
        """
        Get graph configuration and generated preamble for specified graph type.

        Combines config retrieval with preamble generation. Handles fallbacks for missing configs.

        Args:
            graph_type: Key under the config's top-level 'graphTypes' mapping
                (currently only 'component' is defined)

        Returns:
            Tuple of (config dict, preamble lines list). Always returns valid containers.
        """
        # Get graph config with fallback to empty dict
        result = self._get_safe_value("graphTypes", graph_type, default={})
        if result is None:
            result = {}  # Ensure we always have a valid dictionary

        # Generate preamble from config
        preamble = self._create_flowchart_preamble(result)
        if preamble is None:
            preamble = []  # Ensure we always have a valid list

        return result, preamble

    def clear_cache(self):
        """
        Clear cached config to force reload on next access.

        Resets _config, _loaded, and _load_error. Next access will reload from file.
        Useful during development when config files are modified.
        """
        self._config = None
        self._loaded = False
        self._load_error = None

    def get_load_status(self) -> tuple:
        """
        Get configuration loading status for debugging.

        Triggers loading if not already attempted. Safe to call multiple times.

        Returns:
            Tuple of (success bool, error message or None)
        """
        if not self._loaded:
            self._load_config()
        return (self._config is not None, self._load_error)

    def is_using_emergency_defaults(self) -> bool:
        """
        Report whether style lookups are being answered from hardcoded defaults.

        Every getter on this class succeeds either way — _get_safe_value()
        falls back to _get_emergency_defaults() when the configured file is
        missing, unparseable, or missing required top-level keys — so a caller
        cannot tell real configuration from the fallback by inspecting the
        values it gets back. Rendering does not need to know (degrading is the
        point); a guard asserting on the configured styling does, because the
        defaults style every real category and would mask an absent or corrupt
        styles file.

        Triggers loading if not already attempted.

        Returns:
            True when the configured file could not be loaded and lookups are
            served from _get_emergency_defaults(); False when real
            configuration is in use.
        """
        loaded, _ = self.get_load_status()
        return not loaded


class UnionFind:
    def __init__(self, elements):
        """
        Initialize Union-Find data structure.

        Creates parent and rank mappings. Each element starts as its own parent.
        """
        self.parent = {elem: elem for elem in elements}  # Each element starts as its own parent
        self.rank = {elem: 0 for elem in elements}  # All trees start with rank 0

    def find(self, x):
        """
        Find root representative with path compression.
        """
        if self.parent[x] != x:
            # Path compression: make x point directly to the root
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        """
        Merge sets containing x and y using union by rank.
        """
        root_x = self.find(x)  # Find root of x's set
        root_y = self.find(y)  # Find root of y's set

        if root_x != root_y:  # Only union if in different sets
            # Union by rank: attach smaller tree under larger tree
            if self.rank[root_x] < self.rank[root_y]:
                # y's tree is taller, make y's root the new root
                self.parent[root_x] = root_y
            elif self.rank[root_x] > self.rank[root_y]:
                # x's tree is taller, make x's root the new root
                self.parent[root_y] = root_x
            else:
                # Same rank: arbitrarily choose x's root and increment rank
                self.parent[root_y] = root_x
                self.rank[root_x] += 1

    def get_clusters(self):
        """
        Extract all disjoint sets as clusters.

        Groups elements by their root representative.
        Applies path compression for true roots.

        Returns:
            List of sets, each set is a cluster of related elements
        """
        clusters = {}
        for elem in self.parent:
            root = self.find(elem)  # Get root with path compression
            if root not in clusters:
                clusters[root] = set()
            clusters[root].add(elem)
        return list(clusters.values())

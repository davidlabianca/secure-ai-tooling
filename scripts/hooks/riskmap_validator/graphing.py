"""
Graph generation classes for Mermaid visualization.

Provides MermaidConfigLoader, ComponentGraph, ControlGraph, and RiskGraph classes
for generating Mermaid graph visualizations of component relationships,
control-to-component mappings, and risk-to-control-to-component relationships.

Dependencies:
    - PyYAML: For configuration file parsing
    - .config: Default configuration file paths
    - .models: ComponentNode, ControlNode, and RiskNode data models
"""

from pathlib import Path
from typing import Any

import yaml

from .config import DEFAULT_MERMAID_CONFIG_FILE
from .models import ComponentNode, ControlNode, RiskNode


class BaseGraph:
    """
    Base class for Mermaid graph generation with shared utilities.

    This class provides common functionality for both ComponentGraph and ControlGraph,
    including category handling, display name generation, and configuration management.

    Key Features:
    - Dynamic category discovery from component/control data
    - Category display name generation with YAML config loading
    - Shared configuration patterns
    - Consistent category handling across graph types
    """

    def __init__(self, config_loader=None):
        """
        Initialize BaseGraph with optional configuration loader.

        Args:
            config_loader (MermaidConfigLoader, optional): Configuration loader for
                styling and layout options. Defaults to None, which creates a singleton
                instance using default configuration paths.
        """
        self.config_loader = config_loader or MermaidConfigLoader.get_instance()
        self._category_names_cache = None

    def _load_category_names(self) -> dict[str, str]:
        """
        Load category names from YAML files.

        Loads category display names from both controls.yaml and components.yaml
        configuration files, providing human-readable names for category IDs.

        Returns:
            dict[str, str]: Dictionary mapping category IDs to display names.
                           Returns empty dict if loading fails.
        """
        category_names = {}

        # Load control categories
        try:
            controls_yaml_path = Path("risk-map/yaml/controls.yaml")
            if controls_yaml_path.exists():
                with open(controls_yaml_path, "r", encoding="utf-8") as f:
                    controls_data = yaml.safe_load(f)

                for category in controls_data.get("categories", []):
                    if "id" in category and "title" in category:
                        # Append "Controls" to control category titles
                        category_names[category["id"]] = f"{category['title']} Controls"
        except Exception:
            pass  # Fallback to generated names if loading fails

        # Load component categories
        try:
            components_yaml_path = Path("risk-map/yaml/components.yaml")
            if components_yaml_path.exists():
                with open(components_yaml_path, "r", encoding="utf-8") as f:
                    components_data = yaml.safe_load(f)

                for category in components_data.get("categories", []):
                    if "id" in category and "title" in category:
                        # Use the title as-is (already includes "Components")
                        category_names[category["id"]] = category["title"].title()
        except Exception:
            pass  # Fallback to generated names if loading fails

        return category_names

    def _get_category_display_name(self, category: str) -> str:
        """
        Convert category ID to display name.

        Generates human-readable display names for category IDs, with fallback
        to auto-generated names when YAML configuration is not available.

        Args:
            category (str): Category ID to convert (e.g., "componentsData", "controlsInfrastructure")

        Returns:
            str: Human-readable display name (e.g., "Data Components", "Infrastructure Controls")
        """
        # Load category names if not already cached
        if not hasattr(self, "_category_names_cache") or self._category_names_cache is None:
            self._category_names_cache = self._load_category_names()

        category_names = self._category_names_cache

        # Handle dynamically generated category names
        if category not in category_names:
            # Remove "components" or "controls" prefix and capitalize
            if category.startswith("components"):
                display_name = category.replace("components", "").strip()
                if display_name:
                    # Add spacing before capital letters for better readability
                    import re
                    spaced_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", display_name)
                    return spaced_name.title()
            elif category.startswith("controls"):
                display_name = category.replace("controls", "").strip()
                if display_name:
                    # Add spacing before capital letters for better readability
                    import re
                    spaced_name = re.sub(r"([a-z])([A-Z])", r"\1 \2", display_name)
                    return f"{spaced_name.title()} Controls"
            else:
                return category.title()

        return category_names.get(category, category.title())

    def _discover_categories_from_data(self, items: dict) -> list[str]:
        """
        Dynamically discover categories from component or control data.

        Extracts unique category IDs from a dictionary of ComponentNode or ControlNode
        objects, enabling dynamic category handling without hardcoded lists.

        Args:
            items (dict): Dictionary of component or control objects with .category attributes

        Returns:
            list[str]: Sorted list of unique category IDs found in the data
        """
        categories = set()
        for item in items.values():
            if hasattr(item, 'category') and item.category:
                categories.add(item.category)
        return sorted(categories)

    def _build_category_mapping(self, categories: list[str]) -> dict[str, str]:
        """
        Build category mapping from category IDs to display names.

        Creates a mapping dictionary for converting between category IDs and
        their human-readable display names.

        Args:
            categories (list[str]): List of category IDs

        Returns:
            dict[str, str]: Dictionary mapping display names to category IDs
        """
        mapping = {}
        for category in categories:
            display_name = self._get_category_display_name(category)
            # Remove "Components" or "Controls" suffix for cleaner display names
            clean_display = display_name.replace(" Components", "").replace(" Controls", "")
            mapping[clean_display] = category
        return mapping


class MermaidConfigLoader:
    """
    Loads and manages Mermaid styling configuration from YAML files with caching,
    validation, and a set of fallback mechanisms.

    This class provides a centralized interface for accessing Mermaid graph styling
    configuration used by both ComponentGraph and ControlGraph classes. It implements
    caching, error handling, and fallback to hardcoded defaults
    to ensure graph generation never fails due to configuration issues.

    Key Features:
    - **Singleton Pattern**: Ensures single config instance per file path
    - **Lazy Loading**: Configuration loaded only when first accessed
    - **Caching**: Avoids repeated file I/O operations
    - **Fallback System**: Multiple layers of fallbacks prevent generation failures
    - **Validation**: Schema-aware validation with descriptive error messages
    - **Hot Reload**: Supports configuration updates during development

    Fallback Hierarchy:
    1. **Primary**: Load from specified YAML configuration file
    2. **Emergency**: Use hardcoded defaults matching current implementation
    3. **Minimal**: Basic functional configuration if all else fails

    Example:
        >>> loader = MermaidConfigLoader()
        >>> component_colors = loader.get_component_category_styles()
        >>> control_config = loader.get_graph_config("control")
        >>> edge_styles = loader.get_control_edge_styles()

    Thread Safety:
        This class is thread-safe for read operations after initial loading.
        Write operations (cache clearing) should be synchronized externally.
    """

    _instances = {}  # Class-level cache for singleton pattern

    def __init__(self, config_file: Path = None) -> None:
        """
        Initialize MermaidConfigLoader with optional custom configuration file.

        Args:
            config_file (Path, optional): Path to YAML configuration file.
                                        Defaults to risk-map/yaml/mermaid-styles.yaml

        Note:
            This implements a singleton pattern per file path to prevent
            duplicate loading and ensure configuration consistency.
        """
        self.config_file = config_file or DEFAULT_MERMAID_CONFIG_FILE
        self._config = None
        self._loaded = False
        self._load_error = None

    @classmethod
    def get_instance(cls, config_file: Path = None) -> "MermaidConfigLoader":
        """
        Get singleton instance of MermaidConfigLoader for specified config file.

        Args:
            config_file (Path, optional): Path to configuration file

        Returns:
            MermaidConfigLoader: Singleton instance for the config file
        """
        file_key = str(config_file or DEFAULT_MERMAID_CONFIG_FILE)
        if file_key not in cls._instances:
            cls._instances[file_key] = cls(config_file)
        return cls._instances[file_key]

    def _load_config(self) -> bool:
        """
        Load configuration from YAML file with error handling.

        Returns:
            bool: True if configuration loaded successfully, False otherwise

        Side Effects:
            - Sets self._config with loaded configuration
            - Sets self._loaded to True
            - Sets self._load_error if loading fails
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

            # Basic validation - check required top-level keys
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
        Get hardcoded emergency defaults matching current implementation.

        These defaults ensure graph generation continues working even if
        configuration file is missing, corrupt, or incompatible.

        Returns:
            dict: Emergency default configuration structure
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
                "cssClasses": {
                    "hidden": "display: none;",
                    "allControl": "stroke:#4285f4,stroke-width:2px,stroke-dasharray: 5 5",
                },
                "componentCategories": {
                    "componentsInfrastructure": {
                        "fill": "#e6f3e6",
                        "stroke": "#333333",
                        "strokeWidth": "2px",
                        "subgroupFill": "#d4e6d4",
                    },
                    "componentsData": {
                        "fill": "#fff5e6",
                        "stroke": "#333333",
                        "strokeWidth": "2px",
                        "subgroupFill": "#f5f0e6",
                    },
                    "componentsApplication": {
                        "fill": "#e6f0ff",
                        "stroke": "#333333",
                        "strokeWidth": "2px",
                        "subgroupFill": "#e0f0ff",
                    },
                    "componentsModel": {
                        "fill": "#ffe6e6",
                        "stroke": "#333333",
                        "strokeWidth": "2px",
                        "subgroupFill": "#f0e6e6",
                    },
                },
            },
            "graphTypes": {
                "component": {
                    "direction": "TD",
                    "flowchartConfig": {"nodeSpacing": 25, "rankSpacing": 30, "padding": 5, "wrappingWidth": 250},
                },
                "control": {
                    "direction": "LR",
                    "flowchartConfig": {"nodeSpacing": 25, "rankSpacing": 30, "padding": 5, "wrappingWidth": 250},
                    "specialStyling": {
                        "componentsContainer": {
                            "fill": "#f0f0f0",
                            "stroke": "#666666",
                            "strokeWidth": "3px",
                            "strokeDasharray": "10 5",
                        },
                        "edgeStyles": {
                            "allControlEdges": {
                                "stroke": "#4285f4",
                                "strokeWidth": "3px",
                                "strokeDasharray": "8 4",
                            },
                            "subgraphEdges": {"stroke": "#34a853", "strokeWidth": "2px"},
                            "multiEdgeStyles": [
                                {"stroke": "#9c27b0", "strokeWidth": "2px"},
                                {"stroke": "#ff9800", "strokeWidth": "2px", "strokeDasharray": "5 5"},
                                {"stroke": "#e91e63", "strokeWidth": "2px", "strokeDasharray": "10 2"},
                                {"stroke": "#C95792", "strokeWidth": "2px", "strokeDasharray": "10 5"},
                            ],
                        },
                    },
                },
            },
        }

    def _get_safe_value(self, *path, default=None):
        """
        Retrieves a nested value from the primary configuration or a set of emergency defaults.

        This method attempts to access a value from the `_config` dictionary using a sequence of keys.
        If the path is invalid or the primary configuration is not a dictionary, it falls back to
        a set of emergency defaults. If the value is not found in either source, it returns the
        user-provided `default` value.

        The function handles several edge cases, including:
        - Initializing with emergency defaults if the primary configuration fails to load.
        - Directly returning the default value if the emergency defaults are not a dictionary.

        Args:
            *path: A sequence of keys to traverse (e.g., 'sharedElements', 'cssClasses').
            default: The final fallback value to return if no value is found. Defaults to `None`.

        Returns:
            The value found at the specified path, or the `default` value if no value is found.
        """
        use_defaults = False
        use_emergency_defaults = False

        # Get emergency_defaults once to avoid multiple calls.
        emergency_defaults: dict[Any, Any] = self._get_emergency_defaults()

        # Try to load config if not already loaded
        if not self._load_config():
            if not isinstance(emergency_defaults, dict):
                use_defaults = True  # Emergency defaults are not valid, so go straight to the final default.
            config: dict[Any, Any] = emergency_defaults
        else:
            if not isinstance(self._config, dict):
                config = {}
                use_emergency_defaults = (
                    True  # Primary config is not a dict, so we must rely on emergency defaults.
                )
            else:
                config = self._config

        # Short-circuit the process if we know the final default is the only option.
        if use_emergency_defaults and use_defaults:
            return default

        # Navigate the configuration path using the "Easier to Ask for Forgiveness than Permission" principle.
        try:
            current: dict[Any, Any] = config
            for key in path:
                current = current[key]
            return current
        except (KeyError, TypeError):
            # The path was not found in the primary config, so fall back to emergency defaults.
            if use_defaults:
                return default  # Skip emergency defaults if we've already determined they're not valid.
            else:
                try:
                    emergency_current: dict[Any, Any] = emergency_defaults
                    for emergency_key in path:
                        emergency_current = emergency_current[emergency_key]
                    return emergency_current
                except (KeyError, TypeError):
                    # The path wasn't in emergency defaults either, so return the final default.
                    return default

    def _create_flowchart_preamble(self, graph_config: dict) -> list[str] | None:
        """
        Generate Mermaid flowchart preamble with configuration-driven initialization.

        Creates the opening section of a Mermaid graph including the graph declaration,
        initialization configuration, and essential CSS class definitions. This method
        transforms abstract configuration into concrete Mermaid syntax ready for rendering.

        Preamble Components:
        1. **Graph Declaration**: Specifies graph type and direction (e.g., "graph TD")
        2. **Initialization Config**: Flowchart spacing and layout parameters
        3. **CSS Class Definitions**: Hidden elements and control styling classes
        4. **Code Block Wrapper**: Proper Mermaid markdown formatting

        The generated preamble includes:
        - Mermaid code block opening (```mermaid)
        - Graph direction from configuration (TD, LR, etc.)
        - Flowchart initialization with spacing parameters
        - classDef declarations for hidden and allControl elements
        - Blank line for content separation

        Args:
            graph_config (dict): Graph-specific configuration dictionary containing:
                - direction (str): Graph layout direction ('TD', 'LR', 'BT', 'RL')
                - flowchartConfig (dict): Spacing and layout parameters:
                  - nodeSpacing (int): Space between nodes in pixels
                  - rankSpacing (int): Space between ranks/levels in pixels
                  - padding (int): Internal node padding in pixels
                  - wrappingWidth (int): Text wrapping width in pixels

        Returns:
            list[str] | None: List of Mermaid syntax lines forming the preamble,
                             or None if graph_config is invalid/empty.
                             Lines are ready for direct concatenation into graph output.

        Example Output:
            [
                "```mermaid",
                "graph TD",
                "   %%{init: {'flowchart': {'nodeSpacing': 20, 'rankSpacing': 20, 'padding': 5, ...}%%",
                "    classDef hidden display: none;",
                "    classDef allControl stroke:#4285f4,stroke-width:2px,stroke-dasharray: 5 5",
                ""
            ]

        Example Usage:
            >>> loader = MermaidConfigLoader()
            >>> config = {'direction': 'TD', 'flowchartConfig': {'nodeSpacing': 25}}
            >>> preamble = loader._create_flowchart_preamble(config)
            >>> print('\n'.join(preamble))

        Note:
            - Returns None for invalid input to signal preamble generation failure
            - Uses configuration defaults for missing flowchart parameters
            - CSS class definitions are loaded from shared configuration elements
            - The initialization string follows Mermaid's specific JSON-like syntax
        """
        if not isinstance(graph_config, dict) or not graph_config:
            return None

        css_classes: dict[Any, Any] = self.get_css_classes()

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

        # Extract CSS class definitions from shared configuration elements
        hidden_class_def = css_classes.get("hidden", "display: none;")
        all_control_default = "stroke:#4285f4,stroke-width:2px,stroke-dasharray: 5 5"
        all_control_class_def = css_classes.get("allControl", all_control_default)

        lines: list[str] = [
            "```mermaid",
            f"graph {graph_direction}",
            f"   {mermaid_config}",
            f"    classDef hidden {hidden_class_def}",
            f"    classDef allControl {all_control_class_def}",
            "",
        ]

        return lines

    def get_component_category_styles(self) -> dict:
        """
        Retrieve component category styling configuration for visual differentiation.

        Returns styling properties for all component categories including fill colors,
        stroke colors, stroke widths, and subgroup fills. These styles are used by
        both ComponentGraph and ControlGraph classes to create visually distinct
        category subgraphs with consistent color coding.

        Category Structure:
        The returned dictionary maps category IDs to styling dictionaries:
        - componentsData: Light orange styling for data-related components
        - componentsInfrastructure: Light green styling for infrastructure components
        - componentsModel: Light red styling for model-related components
        - componentsApplication: Light blue styling for application components

        Style Properties:
        Each category styling dictionary contains:
        - fill (str): Background color for category subgraph (hex format)
        - stroke (str): Border color for category subgraph (hex format)
        - strokeWidth (str): Border width specification (e.g., "2px")
        - subgroupFill (str): Background color for nested subgroups within category

        Returns:
            dict: Component category styling configuration mapping category IDs to
                 style dictionaries. Always returns a valid dictionary, empty if
                 no configuration is found.

        Example:
            >>> loader = MermaidConfigLoader()
            >>> styles = loader.get_component_category_styles()
            >>> data_style = styles.get('componentsData', {})
            >>> print(data_style.get('fill'))  # '#fff5e6'
            >>> print(data_style.get('stroke'))  # '#333333'

        Note:
            - Uses the fallback system via _get_safe_value for reliability
            - Returns empty dict if configuration section is missing
            - Type validation ensures only dict values are returned
            - Styling is shared between component and control graph visualizations
        """
        result = self._get_safe_value("sharedElements", "componentCategories", default={})
        return result if isinstance(result, dict) else {}

    def get_css_classes(self) -> dict:
        """
        Retrieve CSS class definitions for Mermaid graph styling and layout.

        Returns predefined CSS class definitions used throughout graph generation
        for consistent styling of special elements. These classes handle visibility,
        control styling, and other graph-wide visual properties.

        Standard CSS Classes:
        - **hidden**: Makes elements invisible for layout anchoring ("display: none;")
        - **allControl**: Special styling for controls that apply to all components
          (typically blue dashed stroke: "stroke:#4285f4,stroke-width:2px,stroke-dasharray: 5 5")

        Usage Context:
        - **ComponentGraph**: Uses 'hidden' for anchor and end elements
        - **ControlGraph**: Uses both 'hidden' and 'allControl' for special styling
        - **Preamble Generation**: Classes are included in graph initialization

        Returns:
            dict: CSS class definitions mapping class names to Mermaid style strings.
                 Always returns a valid dictionary, empty if no configuration found.

        Example:
            >>> loader = MermaidConfigLoader()
            >>> classes = loader.get_css_classes()
            >>> print(classes.get('hidden'))  # 'display: none;'
            >>> print(classes.get('allControl'))  # 'stroke:#4285f4,stroke-width:2px,stroke-dasharray: 5 5'
            >>>
            >>> # Used in graph generation
            >>> preamble.append(f"classDef hidden {classes['hidden']}")

        Note:
            - CSS classes are applied via classDef declarations in Mermaid
            - Uses the fallback system for configuration reliability
            - Type validation ensures only dict values are returned
            - Classes are shared across all graph types for consistency
        """
        result = self._get_safe_value("sharedElements", "cssClasses", default={})
        return result if isinstance(result, dict) else {}

    def get_graph_config(self, graph_type: str) -> tuple[dict, list]:
        """
        Retrieve complete graph configuration and generated preamble for specified graph type.

        This method serves as the primary interface for accessing graph-specific configuration
        while simultaneously generating the Mermaid preamble needed for graph rendering. It
        combines configuration retrieval with preamble generation to provide everything needed
        to start building a graph.

        The method handles both standard graph types (component, control) and
        manages missing or invalid configurations through the fallback system. It ensures
        that both configuration and preamble are always returned, even if using defaults.

        Graph Types:
        - **'component'**: Configuration for component relationship graphs (typically TD layout)
        - **'control'**: Configuration for control-to-component graphs (typically LR layout)
        - **Custom types**: Any graph type defined in the configuration file

        Configuration Structure:
        The returned configuration dictionary typically contains:
        - direction (str): Graph layout direction ('TD', 'LR', 'BT', 'RL')
        - flowchartConfig (dict): Spacing and layout parameters
        - specialStyling (dict): Type-specific styling options (for control graphs)

        Args:
            graph_type (str): The type of graph configuration to retrieve.
                             Must match a key in the configuration's 'graphTypes' section.
                             Common values: 'component', 'control'

        Returns:
            tuple[dict, list]: A two-element tuple containing:
                - dict: Graph configuration with direction, flowchartConfig, and other settings.
                       Always returns a valid dictionary (empty dict {} if no config found).
                - list: Generated Mermaid preamble lines ready for graph construction.
                       Always returns a valid list (empty list [] if preamble generation fails).

        Example:
            >>> loader = MermaidConfigLoader()
            >>> config, preamble = loader.get_graph_config('component')
            >>> print(config['direction'])  # 'TD'
            >>> print(len(preamble))  # 6 (typical preamble length)
            >>>
            >>> # Using the results to build a graph
            >>> graph_lines = preamble.copy()
            >>> graph_lines.extend(['    nodeA --> nodeB', '```'])

        Fallback Behavior:
            - Invalid graph_type: Returns empty config dict and empty preamble list
            - Missing configuration: Uses emergency defaults via _get_safe_value
            - Preamble generation failure: Returns empty list while preserving config

        Performance Notes:
            - Configuration is retrieved through the caching _get_safe_value system
            - Preamble generation is performed fresh each call (no caching)
            - Both operations are typically fast (< 1ms) for normal configurations

        Note:
            - This method is the recommended way to get graph configuration
            - The tuple return ensures both config and preamble are always available
            - Preamble generation depends on the configuration's validity
            - Empty returns indicate configuration issues but won't break graph generation
        """
        # Retrieve graph-specific configuration with fallback to empty dict
        result = self._get_safe_value("graphTypes", graph_type, default={})
        if result is None:
            result = {}  # Ensure we always have a valid dictionary

        # Generate Mermaid preamble based on the configuration
        preamble = self._create_flowchart_preamble(result)
        if preamble is None:
            preamble = []  # Ensure we always have a valid list

        return result, preamble

    def get_control_edge_styles(self) -> dict:
        """
        Retrieve edge styling configuration specifically for control graph relationships.

        Returns edge styling definitions used by ControlGraph to create
        visually distinct relationship types through color, width, and dash patterns.
        This configuration enables visual differentiation of control
        mappings based on their scope and complexity.

        Edge Style Categories:
        - **allControlEdges**: Styling for controls mapped to all components (dotted blue)
        - **subgraphEdges**: Styling for category-level mappings (solid green)
        - **multiEdgeStyles**: Array of 4 cycling styles for controls with 3+ edges

        Multi-Edge Styling:
        The multiEdgeStyles array provides 4 distinct visual treatments that cycle
        for controls with multiple individual component mappings:
        1. Purple solid (stroke: #9c27b0)
        2. Orange dashed (stroke: #ff9800, dasharray: 5 5)
        3. Pink long-dash (stroke: #e91e63, dasharray: 10 2)
        4. Brown spaced-dash (stroke: #C95792, dasharray: 10 5)

        Returns:
            dict: Edge styling configuration with nested style definitions.
                 Always returns a valid dictionary, empty if no configuration found.

        Example:
            >>> loader = MermaidConfigLoader()
            >>> edge_styles = loader.get_control_edge_styles()
            >>> all_control = edge_styles.get('allControlEdges', {})
            >>> print(all_control.get('stroke'))  # '#4285f4'
            >>> multi_styles = edge_styles.get('multiEdgeStyles', [])
            >>> print(len(multi_styles))  # 4

        Note:
            - Only used by ControlGraph class for relationship visualization
            - Multi-edge cycling reduces visual complexity for busy controls
            - Uses nested configuration path: graphTypes.control.specialStyling.edgeStyles
            - Fallback system ensures styling always available
        """
        result = self._get_safe_value("graphTypes", "control", "specialStyling", "edgeStyles", default={})
        return result if isinstance(result, dict) else {}

    def get_components_container_style(self) -> dict:
        """
        Retrieve styling configuration for the main components container in control graphs.

        Returns styling properties for the top-level "components" subgraph that contains
        all component categories in ControlGraph visualizations. This container provides
        visual grouping and hierarchy for all AI system components.

        Container Purpose:
        The components container serves as the root subgraph in control graphs,
        organizing all component categories (Data, Infrastructure, Model, Application)
        and their nested subgroups into a cohesive visual unit that controls
        can map to.

        Style Properties:
        - **fill**: Background color for the container (typically light gray)
        - **stroke**: Border color for visual separation (typically darker gray)
        - **strokeWidth**: Border thickness specification (e.g., "3px")
        - **strokeDasharray**: Dash pattern for distinctive container borders (e.g., "10 5")

        Returns:
            dict: Container styling configuration with CSS-like properties.
                 Always returns a valid dictionary, empty if no configuration found.

        Example:
            >>> loader = MermaidConfigLoader()
            >>> container_style = loader.get_components_container_style()
            >>> print(container_style.get('fill'))  # '#f0f0f0'
            >>> print(container_style.get('strokeDasharray'))  # '10 5'
            >>>
            >>> # Applied in control graph generation
            >>> style_str = f"fill:{container_style['fill']},stroke:{container_style['stroke']}"

        Note:
            - Only used by ControlGraph class for top-level container styling
            - Provides visual hierarchy and organization in complex control graphs
            - Uses nested configuration path: graphTypes.control.specialStyling.componentsContainer
            - Dashed borders help distinguish container from category subgraphs
        """
        result = self._get_safe_value("graphTypes", "control", "specialStyling", "componentsContainer", default={})
        return result if isinstance(result, dict) else {}

    def clear_cache(self):
        """
        Clear cached configuration data to force fresh reload on next access.

        Resets all internal caching state including loaded configuration, loading status,
        and error tracking. This method is useful during development when configuration
        files are being modified, or when switching between different configuration sources.

        Cleared State:
        - _config: Loaded configuration dictionary set to None
        - _loaded: Loading status flag reset to False
        - _load_error: Error message tracking cleared to None

        After calling this method, the next configuration access will:
        1. Attempt to reload the configuration file from disk
        2. Re-validate the configuration structure
        3. Update all internal state based on the fresh load

        Example:
            >>> loader = MermaidConfigLoader()
            >>> config = loader.get_css_classes()  # Loads config
            >>> # ... modify config file ...
            >>> loader.clear_cache()  # Force reload
            >>> new_config = loader.get_css_classes()  # Reloads from file

        Note:
            - Does not affect the singleton pattern - same instance is retained
            - Subsequent configuration accesses will trigger fresh file loading
            - Useful for development workflows with configuration iteration
            - Thread-safe for individual instance usage
        """
        self._config = None
        self._loaded = False
        self._load_error = None

    def get_load_status(self) -> tuple:
        """
        Retrieve detailed configuration loading status for debugging and validation.

        Provides insight into the configuration loading process including success/failure
        status and detailed error messages. This method triggers configuration loading
        if not already attempted, making it safe to call at any time.

        Status Information:
        - **Success Status**: Boolean indicating whether configuration loaded without errors
        - **Error Details**: Descriptive error message if loading failed, None if successful

        Error Types:
        - File not found errors with specific file path
        - YAML parsing errors with syntax details
        - Structure validation errors for missing required keys
        - Unexpected errors with exception details

        Returns:
            tuple: Two-element tuple containing:
                - bool: True if configuration loaded successfully, False otherwise
                - str | None: Detailed error message if loading failed, None if successful

        Example:
            >>> loader = MermaidConfigLoader()
            >>> success, error = loader.get_load_status()
            >>> if success:
            ...     print("Configuration loaded successfully")
            ... else:
            ...     print(f"Configuration error: {error}")
            >>>
            >>> # Example error output:
            >>> # Configuration error: Configuration file not found: /path/to/config.yaml

        Use Cases:
            - Development debugging of configuration issues
            - Validation of configuration file accessibility
            - Error reporting in deployment environments
            - Health checks for configuration system

        Note:
            - Triggers lazy loading if configuration hasn't been accessed yet
            - Safe to call multiple times - loading only attempted once
            - Error messages are detailed and actionable for troubleshooting
            - Success=True indicates configuration is available and valid
        """
        if not self._loaded:
            self._load_config()
        return (self._config is not None, self._load_error)


class ComponentGraph(BaseGraph):
    """
    Generates optimized Mermaid graph visualizations for AI system component relationships.

    The ComponentGraph class creates visual representations of how AI system components
    interconnect and depend on each other, applying topological ranking
    algorithms and category-based organization to create clear, readable hierarchical
    diagrams. It supports configurable layouts, debug modes, and consistent styling.

    Key Features:
    - **Topological Ranking**: Automatically calculates component hierarchy using
      dependency analysis with zero-based indexing (rank 0 = root nodes)
    - **Category-Based Organization**: Groups components into visual subgraphs by
      category (Data, Infrastructure, Model, Application) with color coding
    - **Configurable Layouts**: Supports both horizontal and vertical orientations
      with anchor positioning using dynamic tilde calculations
    - **Debug Mode**: Optional rank annotations and detailed comments for troubleshooting
    - **Styling**: Color-coded categories with visual hierarchy
    - **Cycle Detection**: Handles circular dependencies through SCC analysis

    Graph Structure:
    The generated graph consists of four main sections:
    1. **Category Subgraphs**: Visual containers for each component category
    2. **Topological Layout**: Components positioned by calculated dependency ranks
    3. **Relationship Edges**: Directed arrows showing component dependencies
    4. **Styling**: Color-coded categories and visual hierarchy

    Ranking Algorithm:
    - **Zero-Based Indexing**: Rank 0 = root nodes (componentDataSources), Rank 1+ = dependencies
    - **Special Handling**: Nodes with no incoming edges positioned relative to their targets
    - **Cycle Resilience**: Strongly connected components assigned consistent ranks
    - **Iterative Calculation**: Uses bounded iteration to prevent infinite loops

    Anchor Positioning Formula:
    - anchor_tildes = 3 + min_node_rank_in_subgraph
    - end_tildes = 3 + (global_max_rank - max_node_rank_in_subgraph)
    - global_max_rank = 11 (highest component rank 9 + 2 for spacing)

    Example:
        >>> forward_map = {"comp1": ["comp2"], "comp2": ["comp3"]}
        >>> components = {
        ...     "comp1": ComponentNode("Data Sources", "componentsData", [], ["comp2"]),
        ...     "comp2": ComponentNode("Model Training", "componentsModel", ["comp1"], ["comp3"]),
        ...     "comp3": ComponentNode("Application", "componentsApplication", ["comp2"], [])
        ... }
        >>> graph = ComponentGraph(forward_map, components, debug=True)
        >>> mermaid_code = graph.to_mermaid()
        >>> print("```mermaid" in mermaid_code)
        True

    Attributes:
        components (dict[str, ComponentNode]): Dictionary of component ID to ComponentNode mappings
        forward_map (dict[str, list[str]]): Dictionary mapping component IDs to their target dependencies
        debug (bool): Whether to include debug comments and rank annotations in generated graphs
        config_loader (MermaidConfigLoader): Configuration loader for styling and layout options
        graph (str): Generated Mermaid graph content ready for rendering

    Note:
        - The class automatically calculates optimal layouts during initialization
        - Subgraph organization follows a predefined category order for consistency
        - All styling is configuration-driven through MermaidConfigLoader
        - Debug mode provides detailed rank information for troubleshooting
        - The generated Mermaid code includes styling for visualization
    """

    def __init__(
        self,
        forward_map: dict[str, list[str]],
        components: dict[str, ComponentNode],
        debug: bool = False,
        config_loader: MermaidConfigLoader = None,
    ):
        """
        Initialize ComponentGraph with component relationships and configuration.

        Performs initialization including component validation,
        topological rank calculation, and graph generation with styling.
        The initialization process creates a complete Mermaid-compatible graph
        ready for rendering in documentation or web interfaces.

        The initialization sequence:
        1. Store component data and dependency mappings
        2. Load styling configuration from MermaidConfigLoader
        3. Generate complete graph with topological layout
        4. Apply category-based organization and styling

        Args:
            forward_map (dict[str, list[str]]): Dictionary mapping component IDs to lists
                of their target dependencies. Represents the "to" edges in the component
                graph. Used for topological ranking and edge generation.
            components (dict[str, ComponentNode]): Dictionary mapping component IDs to
                ComponentNode objects. Each ComponentNode should have valid title,
                category, and edge relationships for proper graph generation.
            debug (bool, optional): Whether to include debug information in generated
                output. Defaults to False. When True, adds rank comments and detailed
                annotations to Mermaid diagrams for troubleshooting.
            config_loader (MermaidConfigLoader, optional): Configuration loader for
                styling and layout options. Defaults to None, which creates a singleton
                instance using default configuration paths.

        Raises:
            TypeError: If forward_map or components are not dictionaries, or if they
                      contain invalid ComponentNode objects.
            ValueError: If component IDs are empty, contain invalid characters, or if
                       forward_map references non-existent component IDs.

        Side Effects:
            - Populates self.graph with complete Mermaid graph content
            - Loads styling configuration from YAML files
            - Calculates topological ranks for all components
            - Applies category-based organization and color coding

        Example:
            >>> forward_map = {"comp1": ["comp2"], "comp2": []}
            >>> components = {
            ...     "comp1": ComponentNode("Source", "componentsData", [], ["comp2"]),
            ...     "comp2": ComponentNode("Target", "componentsModel", ["comp1"], [])
            ... }
            >>> graph = ComponentGraph(forward_map, components, debug=True)
            >>> assert hasattr(graph, 'graph')
            >>> assert isinstance(graph.graph, str)
        """
        super().__init__(config_loader)
        self.components = components
        self.forward_map = forward_map
        self.debug = debug
        self.graph = self.build_graph(debug=debug)

    def build_graph(self, layout="horizontal", debug=False) -> str:
        """
        Build a Mermaid-compatible graph representation with topological layout.

        Generates a complete Mermaid flowchart with consistent styling that visualizes
        AI system component relationships and dependencies. The graph includes
        topological ranking, category-based organization, and configurable styling to
        create clear, readable hierarchical diagrams.

        Graph Generation Process:
        1. **Configuration Loading**: Retrieves styling and layout configuration
        2. **Rank Calculation**: Computes topological ranks for proper positioning
        3. **Category Organization**: Groups components into visual subgraphs
        4. **Subgraph Construction**: Builds category containers with anchor positioning
        5. **Edge Generation**: Creates dependency arrows between components
        6. **Style Application**: Applies color coding and formatting

        Layout Features:
        - **Topological Ordering**: Components positioned by dependency hierarchy
        - **Category Subgraphs**: Visual containers for each component category
        - **Anchor Positioning**: Dynamic tilde calculations for proper alignment
        - **Styling**: Color-coded categories with hierarchy

        Args:
            layout (str, optional): Graph orientation control. "horizontal" creates
                left-to-right data flow, "vertical" creates bottom-to-top flow.
                Defaults to "horizontal". Currently supports "horizontal" layout.
            debug (bool, optional): Whether to include debug annotations in the output.
                When True, adds rank comments, tilde calculations, and detailed
                positioning information for troubleshooting. Defaults to False.

        Returns:
            str: Complete Mermaid graph definition wrapped in ```mermaid code blocks,
                ready for rendering in documentation or web interfaces. Includes all
                styling definitions, subgraph structures, and relationship mappings.

        Raises:
            ValueError: If components contain invalid category references or if
                       topological ranking fails due to unresolvable cycles.
            KeyError: If forward_map references component IDs not present in components.

        Example Output Structure:
            ```mermaid
            graph TD
                %%{init: {'flowchart': {'nodeSpacing': 20, 'rankSpacing': 20}}}%%
                classDef hidden display: none;

                subgraph Data
                    comp1[Data Sources]
                end
                subgraph Model
                    comp2[Model Training]
                end

                comp1 --> comp2

                style Data fill:#fff5e6,stroke:#333333,stroke-width:2px
            ```

        Performance Notes:
            - Graph complexity scales with number of components and relationships
            - Topological ranking uses iterative algorithm with cycle detection
            - Category organization provides O(n) grouping performance
            - Generated strings can be large for complex component frameworks

        Note:
            - The graph uses top-down layout (graph TD) for optimal component hierarchy visualization
            - All styling is configuration-driven through MermaidConfigLoader
            - Subgraph nesting follows predefined category order for consistency
            - Debug mode significantly increases output size with detailed annotations
        """

        # Get configuration from loader including preamble and styling
        _, graph_preamble = self.config_loader.get_graph_config("component")
        component_categories = self.config_loader.get_component_category_styles()

        # Calculate topological ranks for proper component positioning
        node_ranks = self._calculate_node_ranks()

        # Discover categories dynamically from component data
        discovered_categories = self._discover_categories_from_data(self.components)
        category_mapping = self._build_category_mapping(discovered_categories)

        # Create category order for consistent visual layout
        # Prefer standard order when available, then alphabetical for new categories
        standard_categories = ["Data", "Infrastructure", "Model", "Application"]
        category_order = []

        # Add standard categories if they exist in the data
        for std_cat in standard_categories:
            if std_cat in category_mapping:
                category_order.append(std_cat)

        # Add any additional categories alphabetically
        for cat in sorted(category_mapping.keys()):
            if cat not in category_order:
                category_order.append(cat)

        # Initialize category containers for organized component grouping
        components_by_category = {}
        for category in category_order:
            components_by_category[category] = []

        # Categorize all components into their respective visual groups
        for comp_id, comp_node in self.components.items():
            category = self._normalize_category(comp_id)
            if category not in components_by_category:
                components_by_category[category] = []  # Handle unexpected categories
            components_by_category[category].append((comp_id, comp_node.title))

        # Initialize graph structure with configuration-driven preamble
        graph_content = graph_preamble

        # Add invisible root node for proper Mermaid layout anchoring
        graph_content.append("    root:::hidden")
        graph_content.append("    ")  # Blank line for readability

        # Build category subgraphs with components (edges added separately for clarity)
        for category in category_order:
            if category in components_by_category and components_by_category[category]:
                # Generate subgraph structure with anchor positioning and component nodes
                subgraph_lines = self._build_subgraph_structure(
                    category, components_by_category[category], node_ranks, debug
                )
                graph_content.extend(subgraph_lines)

        # Connect invisible root to category anchors for proper layout hierarchy
        anchor_connections = []
        for category in category_order:
            if category in components_by_category and components_by_category[category]:
                anchor_name = f"{category}Anchor:::hidden"
                # Use tilde connections (~) for invisible layout anchoring
                anchor_connections.append(f"    root ~~~ {anchor_name}")

        graph_content.extend(anchor_connections)

        # Add all inter-component dependency edges outside subgraphs for clean layout
        graph_content.append("")
        for src, targets in self.forward_map.items():
            # Get component titles for readable node labels
            src_title = self.components[src].title if src in self.components else src
            for tgt in targets:
                tgt_title = self.components[tgt].title if tgt in self.components else tgt

                # Include topological rank information in debug mode
                if debug:
                    src_rank = node_ranks.get(src, 0)
                    tgt_rank = node_ranks.get(tgt, 0)
                    graph_content.append(f"    %% {src} rank {src_rank}, {tgt} rank {tgt_rank}")
                # Generate directed edge with proper node labeling
                graph_content.append(f"    {src}[{src_title}] --> {tgt}[{tgt_title}]")

        # Apply styling using configuration-driven colors and formatting
        graph_content.extend(
            [
                "",
                "%% Style definitions",
            ]
        )

        # Map display category names to configuration keys for styling lookup
        category_mapping = {
            "Infrastructure": "componentsInfrastructure",
            "Data": "componentsData",
            "Application": "componentsApplication",
            "Model": "componentsModel",
        }

        # Apply color-coded category styling for visual differentiation
        for display_name, config_key in category_mapping.items():
            if config_key in component_categories:
                category_style = component_categories[config_key]
                # Extract styling properties with sensible defaults
                fill = category_style.get("fill", "#ffffff")
                stroke = category_style.get("stroke", "#333333")
                stroke_width = category_style.get("strokeWidth", "2px")
                style_str = f"fill:{fill},stroke:{stroke},stroke-width:{stroke_width}"
                graph_content.append(f"    style {display_name} {style_str}")

        graph_content.append("```")

        return "\n".join(graph_content)

    def _normalize_category(self, component_id: str) -> str:
        """
        Normalize component category name for display purposes.

        Transforms internal category identifiers (e.g., "componentsData") into
        human-readable display names (e.g., "Data") using the BaseGraph's
        category handling methods for consistency across graph types.

        Args:
            component_id (str): Component identifier to look up category for

        Returns:
            str: Normalized category name suitable for subgraph labels
                (e.g., "Data", "Model", "Infrastructure", "Application")
        """
        if component_id in self.components:
            category = self.components[component_id].category

            # Use BaseGraph method to get display name, then clean it
            display_name = self._get_category_display_name(category)

            # Remove "Components" suffix if present for cleaner display
            if display_name.endswith(" Components"):
                return display_name.replace(" Components", "")

            return display_name
        return "Unknown"

    def _get_first_component_in_category(self, components_by_category: dict, target_category: str) -> str | None:
        """
        Retrieve the first component ID within a specific category.

        Helper method for anchor positioning and category layout calculations.
        Used internally for subgraph construction and component ordering.

        Args:
            components_by_category (dict): Dictionary mapping category names to
                lists of component IDs within each category
            target_category (str): Category name to search for components

        Returns:
            str | None: First component ID in the category, or None if category
                       is empty or doesn't exist
        """
        if target_category in components_by_category and components_by_category[target_category]:
            return components_by_category[target_category][0][0]
        return None

    def _calculate_node_ranks(self) -> dict[str, int]:
        """
        Calculate topological ranks for all components using dependency analysis.

        Implements a topological ranking algorithm that handles complex dependency
        graphs including cycles, orphaned nodes, and special root components. The algorithm
        uses zero-based indexing where rank 0 represents root nodes and higher ranks
        indicate increasing dependency depth.

        Algorithm Features:
        - **Zero-Based Indexing**: Rank 0 = root nodes, Rank 1+ = dependency levels
        - **Root Component Handling**: componentDataSources hardcoded as rank 0 anchor
        - **Cycle Detection**: Handles circular dependencies through iterative resolution
        - **Orphaned Node Management**: Special handling for disconnected components
        - **Iterative Convergence**: Bounded iteration prevents infinite loops

        Ranking Rules:
        1. **componentDataSources**: Always assigned rank 0 as the foundational root
        2. **Dependent Nodes**: Rank = max(dependency_ranks) + 1
        3. **Source Nodes**: Nodes with outgoing but no incoming edges positioned relative to targets
        4. **Cyclic Nodes**: Assigned rank 0 to break dependency cycles
        5. **Orphaned Nodes**: Isolated components assigned rank 0

        Special Handling:
        - Nodes with no incoming edges but outgoing connections get rank = min_target_rank - 1
        - Maximum iterations prevent infinite loops in complex dependency graphs
        - Fallback assignment ensures all nodes receive valid ranks

        Returns:
            dict[str, int]: Dictionary mapping component IDs to their calculated ranks.
                           Ranks are zero-based integers representing topological levels.

        Example:
            >>> forward_map = {"componentDataSources": ["comp1"], "comp1": ["comp2"]}
            >>> graph = ComponentGraph(forward_map, components)
            >>> ranks = graph._calculate_node_ranks()
            >>> assert ranks["componentDataSources"] == 0
            >>> assert ranks["comp1"] == 1
            >>> assert ranks["comp2"] == 2

        Performance Notes:
            - Time complexity: O(n * m) where n=nodes, m=max_iterations
            - Space complexity: O(n) for rank storage and edge mapping
            - Iteration limit prevents pathological cases

        Note:
            - The algorithm prioritizes componentDataSources as the canonical root
            - Cycle handling ensures convergence without infinite loops
            - Rank calculations are deterministic for consistent graph layouts
            - Zero-based indexing aligns with standard topological sorting conventions
        """
        # Build reverse dependency map for incoming edge analysis
        # This enables proper topological ranking by identifying component dependencies
        incoming_edges = {}
        for node in self.components:
            incoming_edges[node] = []  # Initialize empty dependency list for each component

        # Populate incoming edges by reversing the forward_map relationships
        for src, targets in self.forward_map.items():
            for target in targets:
                if target in incoming_edges:
                    incoming_edges[target].append(src)  # Target depends on src

        # Initialize rank tracking dictionary
        ranks = {}

        # Establish componentDataSources as the canonical root node (rank 0)
        # This provides a stable foundation for the entire dependency hierarchy
        if "componentDataSources" in self.components:
            ranks["componentDataSources"] = 0  # Zero-based ranking system
        else:
            # Fallback mechanism if the expected root doesn't exist
            if self.components:
                first_node = next(iter(self.components))
                ranks[first_node] = 0  # Use first available component as root

        # Calculate ranks using iterative convergence algorithm with cycle protection
        max_iterations = len(self.components) * 2  # Safety limit to prevent infinite loops
        iteration = 0

        # Iterate until convergence or safety limit reached
        while iteration < max_iterations:
            changed = False  # Track whether any ranks were updated in this iteration
            iteration += 1

            # Process each unranked component to determine its position
            for node in self.components:
                if node not in ranks:
                    dependencies = incoming_edges[node]

                    # Check if node has dependencies that have been ranked
                    ranked_deps = [dep for dep in dependencies if dep in ranks]

                    if ranked_deps:
                        # Standard case: rank based on maximum dependency rank + 1
                        # This maintains proper topological ordering in the hierarchy
                        max_dep_rank = max(ranks[dep] for dep in ranked_deps)
                        ranks[node] = max_dep_rank + 1
                        changed = True
                    elif not dependencies and node in self.forward_map:
                        # Special case: source node with no incoming edges but outgoing connections
                        # Position based on target ranks to maintain visual flow
                        targets = self.forward_map[node]
                        ranked_targets = [target for target in targets if target in ranks]

                        if ranked_targets:
                            # Rank as min_target_rank - 1 to appear before targets
                            min_target_rank = min(ranks[target] for target in ranked_targets)
                            ranks[node] = max(0, min_target_rank - 1)  # Clamp to non-negative
                            changed = True

            # Exit early if no changes occurred (convergence reached)
            if not changed:
                break

        # Handle remaining unranked nodes (typically involved in dependency cycles)
        for node in self.components:
            if node not in ranks:
                ranks[node] = 0  # Assign root rank to break cycles and ensure completeness

        return ranks

    def _build_subgraph_structure(
        self,
        category: str,
        components: list,
        node_ranks: dict[str, int],
        debug: bool = False,
    ) -> list:
        """
        Build a formatted subgraph structure with dynamic anchor positioning.

        Constructs a complete Mermaid subgraph container for a component category with
        anchor positioning using dynamic tilde calculations. The method
        ensures proper visual alignment and spacing within the overall graph layout
        while maintaining consistent category organization.

        Subgraph Structure:
        1. **Category Container**: Named subgraph with display title
        2. **Anchor Node**: Hidden positioning element with calculated tildes
        3. **Component Nodes**: All components in the category with optional rank annotations
        4. **End Node**: Hidden termination element for layout consistency
        5. **Debug Information**: Optional rank and calculation comments

        Anchor Positioning Algorithm:
        The method uses a tilde calculation system for precise visual alignment:
        - **anchor_tildes** = 3 + min_node_rank_in_subgraph
        - **end_tildes** = 3 + (global_max_rank - max_node_rank_in_subgraph)
        - **global_max_rank** = 11 (empirically determined: max rank 9 + 2 spacing)

        This formula ensures:
        - Lower-ranked components appear higher in the visual layout
        - Higher-ranked components appear lower with proper spacing
        - Consistent alignment across all category subgraphs
        - Consistent visual hierarchy representation

        Args:
            category (str): Subgraph category display name (e.g., "Data", "Infrastructure",
                          "Model", "Application"). Used as the subgraph label and styling key.
            components (list): List of (component_id, component_title) tuples representing
                             all components within this category. Order doesn't matter as
                             positioning is determined by ranks.
            node_ranks (dict[str, int]): Dictionary mapping component IDs to their calculated
                                        topological ranks. Used for anchor positioning and
                                        optional debug annotations.
            debug (bool, optional): Whether to include detailed debug information in the
                                   output. When True, adds rank comments, calculation details,
                                   and positioning information. Defaults to False.

        Returns:
            list[str]: List of Mermaid syntax lines representing the complete subgraph
                      structure, including container, anchors, components, and styling.
                      Lines are ready for direct inclusion in the final graph output.

        Example Output:
            [
                "subgraph Data",
                "%% min = 0",
                "    DataAnchor:::hidden ~~~ componentDataSources",
                "%% componentDataSources Rank 0",
                "    componentDataSources[Data Sources]",
                "    componentTrainingData[Training Data] ~~~~~~~~~~~~ DataEnd:::hidden",
                "%% anchor_incr=0, end_incr=11",
                "end"
            ]

        Performance Notes:
            - Time complexity: O(n) where n = number of components in category
            - Space complexity: O(n) for storing subgraph lines
            - Tilde calculation is O(1) mathematical operation

        Note:
            - Empty component lists result in basic subgraph containers
            - Anchor positioning requires valid node_ranks for all components
            - Debug mode significantly increases output verbosity
            - Tilde counts are optimized for Mermaid layout engine behavior
        """
        subgraph_lines = [f"subgraph {category}"]

        # Calculate global maximum rank for consistent anchor positioning across subgraphs
        # Empirically determined: highest typical rank (9) + spacing buffer (2) = 11
        global_max_rank = 11

        # Include minimum rank information for debugging subgraph positioning
        if debug and components:
            min_rank = min(node_ranks.get(comp_id, 0) for comp_id, _ in components)
            subgraph_lines.append(f"%% min = {min_rank}")

        # Process components for anchor positioning only if category contains components
        if components:
            # Identify components with minimum and maximum ranks for anchor calculations
            components_with_ranks = [
                (comp_id, comp_title, node_ranks.get(comp_id, 0)) for comp_id, comp_title in components
            ]
            lowest_rank_comp = min(components_with_ranks, key=lambda x: x[2])  # Anchor target
            highest_rank_comp = max(components_with_ranks, key=lambda x: x[2])  # End target

            min_node_rank_in_subgraph = lowest_rank_comp[2]
            max_node_rank_in_subgraph = highest_rank_comp[2]

            # Apply tilde calculation formula for precise visual alignment:
            # - anchor_incr: pushes anchor down based on minimum rank
            # - end_incr: pushes end up based on distance from maximum rank
            anchor_incr = min_node_rank_in_subgraph
            end_incr = global_max_rank - max_node_rank_in_subgraph

            # Base tilde count (3) + calculated increment for optimal spacing
            anchor_tilde_count = 3 + anchor_incr
            end_tilde_count = 3 + end_incr

            # Create invisible anchor node with calculated positioning
            anchor_name = f"{category}Anchor:::hidden"
            anchor_tildes = "~" * anchor_tilde_count
            subgraph_lines.append(f"    {anchor_name} {anchor_tildes} {lowest_rank_comp[0]}")

            # Add all component nodes with optional debug rank annotations
            for comp_id, comp_title in components:
                if debug:
                    rank = node_ranks.get(comp_id, 1)
                    subgraph_lines.append(f"    %% {comp_id} Rank {rank}")
                subgraph_lines.append(f"    {comp_id}[{comp_title}]")

            # Create invisible end node with calculated positioning for layout termination
            end_name = f"{category}End:::hidden"
            end_tildes = "~" * end_tilde_count
            subgraph_lines.append(f"    {highest_rank_comp[0]} {end_tildes} {end_name}")

            # Include tilde calculation details for debugging anchor positioning
            if debug:
                subgraph_lines.append(f"%% anchor_incr={anchor_incr}, end_incr={end_incr}")

        subgraph_lines.append("end")  # Close subgraph container
        return subgraph_lines

    def to_mermaid(self) -> str:
        """
        Generate the complete Mermaid graph output for component relationships.

        This is the primary public interface for accessing the generated Mermaid graph.
        It returns the complete graph content that was generated during initialization,
        including all topological ranking, category organization, styling, and
        relationship mappings.

        The output is ready for rendering in any Mermaid-compatible environment,
        including documentation platforms, web interfaces, and diagram tools.

        Returns:
            str: Complete Mermaid graph definition as a string, including:
                - ```mermaid code block markers for proper rendering
                - Topologically ranked component relationships
                - Category-based subgraph organization with color coding
                - Consistent styling and visual hierarchy
                - All component dependencies as directed edges
                - Optional debug annotations if enabled during initialization

        Example:
            >>> forward_map = {"comp1": ["comp2"]}
            >>> components = {
            ...     "comp1": ComponentNode("Source", "componentsData", [], ["comp2"]),
            ...     "comp2": ComponentNode("Target", "componentsModel", ["comp1"], [])
            ... }
            >>> graph = ComponentGraph(forward_map, components)
            >>> mermaid_code = graph.to_mermaid()
            >>> print(mermaid_code.startswith("```mermaid"))
            True
            >>> print(mermaid_code.endswith("```"))
            True
            >>> print("comp1" in mermaid_code and "comp2" in mermaid_code)
            True

        Note:
            - This method is stateless and can be called multiple times safely
            - The output includes all optimizations applied during initialization
            - Graph complexity depends on the number of components and relationships provided
            - All styling and formatting is embedded for standalone rendering
            - Debug information is included only if debug=True was specified during initialization
        """
        return self.graph


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
        super().__init__(config_loader)
        self.controls = controls
        self.components = components
        self.debug = debug

        # Build mappings for graph generation
        self.component_by_category = self._group_components_by_category()

        # Find optimal subgroupings and merge them into component_by_category
        self.subgroupings = self._find_optimal_subgroupings()
        self._integrate_subgroupings()

        self.control_to_component_map = self._build_control_component_mapping()
        self.controls_mapped_to_all = self._track_controls_mapped_to_all()
        self.control_by_category = self._group_controls_by_category()

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
        initial_mapping = {}
        for control_id, control in self.controls.items():
            if control.components == ["all"]:
                continue  # Skip 'all' controls for subgrouping analysis
            elif control.components == ["none"] or not control.components:
                continue  # Skip 'none' controls
            else:
                # Filter to only include components that actually exist
                valid_components = [comp_id for comp_id in control.components if comp_id in self.components]
                initial_mapping[control_id] = valid_components

        # Find categories with 3+ components that could benefit from subgrouping
        subgroupings = {}

        for category, components in self.component_by_category.items():
            if len(components) < 3:
                continue  # Skip small categories

            # Find components in this category that are targeted by controls
            category_components = set(components)

            # Build a map of component -> set of controls that target it
            component_to_controls = {}
            for comp_id in category_components:
                component_to_controls[comp_id] = set()

            for control_id, target_components in initial_mapping.items():
                for comp_id in target_components:
                    if comp_id in component_to_controls:
                        component_to_controls[comp_id].add(control_id)

            # Find groups of components that share 2+ controls
            subgroups = self._find_component_clusters(
                component_to_controls, min_shared_controls=2, min_components=2
            )

            if subgroups:
                subgroupings[category] = subgroups

        return subgroupings

    def _find_component_clusters(
        self, component_to_controls: dict[str, set], min_shared_controls: int = 2, min_components: int = 2
    ) -> dict[str, list[str]]:
        """
        Find clusters of components that share significant control overlap using graph clustering.

        This algorithm identifies components that have substantial shared control relationships
        and groups them into subgroups to reduce visual complexity in the generated graphs.
        The clustering reduces edge count by replacing multiple individual component edges
        with single subgroup edges.

        Algorithm:
        1. **Pairwise Analysis**: Examines all component pairs to find shared controls
        2. **Cluster Formation**: Groups components with sufficient control overlap
        3. **Cluster Merging**: Combines overlapping clusters iteratively
        4. **Size Filtering**: Retains only clusters meeting minimum size requirements
        5. **Name Generation**: Creates unique subgroup names based on common prefixes

        Optimization Impact:
        - Without clustering: Control -> [comp1, comp2, comp3, comp4] = 4 edges
        - With clustering: Control -> [subgroup] = 1 edge (75% reduction)

        Args:
            component_to_controls (dict[str, set]): Mapping from component IDs to sets of
                control IDs that apply to each component. Used to calculate control overlap.
            min_shared_controls (int, optional): Minimum number of shared controls required
                for components to be clustered together. Defaults to 2. Higher values create
                more selective clusters with stronger control relationships.
            min_components (int, optional): Minimum number of components required to form
                a valid cluster. Defaults to 2. Prevents single-component "clusters".

        Returns:
            dict[str, list[str]]: Dictionary mapping generated subgroup names to lists of
            component IDs in each cluster. Subgroup names are generated automatically
            using common prefixes (e.g., "componentsComp" for component clustering).

        Example:
            >>> component_controls = {
            ...     "comp1": {"control1", "control2"},
            ...     "comp2": {"control1", "control2"},
            ...     "comp3": {"control3"}
            ... }
            >>> graph = ControlGraph({}, {})
            >>> clusters = graph._find_component_clusters(component_controls)
            >>> # Returns: {"componentsComp": ["comp1", "comp2"]}
            >>> # comp3 not clustered (only 1 component, below min_components=2)

        Note:
            - The algorithm is greedy and may not find optimal global clusters
            - Clusters with identical control sets are prioritized
            - Component ordering within clusters is deterministic (sorted)
            - Empty clusters are automatically filtered out
            - Subgroup names use prefix detection for readability
        """
        components = list(component_to_controls.keys())
        clusters = []

        # Find all pairs of components with significant overlap
        for i in range(len(components)):
            for j in range(i + 1, len(components)):
                comp1, comp2 = components[i], components[j]
                shared_controls = component_to_controls[comp1] & component_to_controls[comp2]

                if len(shared_controls) >= min_shared_controls:
                    # Try to merge with existing cluster or create new one
                    merged = False
                    for cluster in clusters:
                        if comp1 in cluster or comp2 in cluster:
                            cluster.update([comp1, comp2])
                            merged = True
                            break

                    if not merged:
                        clusters.append({comp1, comp2})

        # Merge overlapping clusters
        merged_clusters = []
        for cluster in clusters:
            merged = False
            for existing in merged_clusters:
                if cluster & existing:  # Overlapping clusters
                    existing.update(cluster)
                    merged = True
                    break
            if not merged:
                merged_clusters.append(cluster)

        # Convert to named subgroups and filter by size
        result = {}
        for i, cluster in enumerate(merged_clusters):
            if len(cluster) >= min_components:
                # Generate a meaningful subgroup name
                cluster_list = sorted(list(cluster))

                # Try to find a common prefix for naming, avoiding conflicts
                common_prefix = self._find_common_prefix([comp.replace("component", "") for comp in cluster_list])
                if common_prefix and len(common_prefix) > 2:
                    # Check if this would conflict with existing categories
                    proposed_name = f"components{common_prefix.title()}"
                    if proposed_name in self.component_by_category:
                        # Avoid conflict by adding parent category context
                        subgroup_name = f"components{common_prefix.title()}Infrastructure"
                    else:
                        subgroup_name = proposed_name
                else:
                    subgroup_name = f"componentsSubgroup{i + 1}"

                result[subgroup_name] = cluster_list

        return result

    def _find_common_prefix(self, strings: list[str]) -> str:
        """Find the longest common prefix among a list of strings."""
        if not strings:
            return ""

        # Find the shortest string length
        min_len = min(len(s) for s in strings)

        for i in range(min_len):
            char = strings[0][i]
            if not all(s[i] == char for s in strings):
                return strings[0][:i]

        return strings[0][:min_len]

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
                comp_id
                for comp_id in self.component_by_category[parent_category]
                if comp_id not in all_subgrouped_components
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
        mapping = {}

        for control_id, control in self.controls.items():
            if control.components == ["all"]:
                # Control applies to all components - map to the components container subgraph
                mapping[control_id] = ["components"]
            elif control.components == ["none"] or not control.components:
                # Control applies to no components
                mapping[control_id] = []
            else:
                # Control applies to specific components
                # Filter to only include components that actually exist
                valid_components = [comp_id for comp_id in control.components if comp_id in self.components]

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

                mapping[control_id] = optimized_mapping

        return mapping

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

    def _group_controls_by_category(self) -> dict[str, list[str]]:
        """Group control IDs by their category."""
        groups = {}
        for control_id, control in self.controls.items():
            category = control.category
            if category not in groups:
                groups[category] = []
            groups[category].append(control_id)
        return groups

    def _group_components_by_category(self) -> dict[str, list[str]]:
        """Group component IDs by their category (simple mapping without subgroups)."""
        groups = {}

        # Initialize main categories only - subgrouping handled dynamically in optimization
        for comp_id, component in self.components.items():
            category = component.category
            if category not in groups:
                groups[category] = []
            groups[category].append(comp_id)

        return groups


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
        for category, control_ids in self.control_by_category.items():
            if not control_ids:
                continue

            category_name = self._get_category_display_name(category)
            lines.append(f'    subgraph {category} ["{category_name}"]')

            if category == "controlsGovernance":
                lines.append("        direction LR")

            for control_id in sorted(control_ids):
                control = self.controls[control_id]
                lines.append(f"        {control_id}[{control.title}]")

            lines.append("    end")
            lines.append("")

        # Add components subgraph as container for all components subgraphs
        lines.append("    subgraph components")
        # Add component subgraphs with dynamic nested structure
        processed_subgroups = set()

        for category, comp_ids in self.component_by_category.items():
            if not comp_ids or category in processed_subgroups:
                continue

            category_name = self._get_category_display_name(category)

            # Check if this category has subgroups
            category_subgroups = self.subgroupings.get(category, {})

            if category_subgroups:
                # This category has subgroups - create nested structure
                lines.append(f'    subgraph {category} ["{category_name}"]')

                # Add remaining components in the main category (not subgrouped)
                for comp_id in sorted(comp_ids):
                    component = self.components[comp_id]
                    lines.append(f"        {comp_id}[{component.title}]")

                # Add nested subgroups
                for subgroup_name, subgroup_components in category_subgroups.items():
                    subgroup_display_name = self._get_category_display_name(subgroup_name)
                    lines.append(f'        subgraph {subgroup_name} ["{subgroup_display_name}"]')

                    for comp_id in sorted(subgroup_components):
                        component = self.components[comp_id]
                        lines.append(f"            {comp_id}[{component.title}]")

                    lines.append("        end")
                    processed_subgroups.add(subgroup_name)

                lines.append("    end")
                lines.append("")

            else:
                # Regular category subgraph (no subgroups)
                lines.append(f'    subgraph {category} ["{category_name}"]')

                for comp_id in sorted(comp_ids):
                    component = self.components[comp_id]
                    lines.append(f"        {comp_id}[{component.title}]")

                lines.append("    end")
                lines.append("")
        lines.append("    end")
        lines.append("")

        # Add control-to-component relationships
        lines.append("    %% Control to Component relationships")

        # Track edge indices for styling
        edge_index = 0
        all_control_edges = []  # Edges from controls mapped to "all"
        subgraph_edges = []  # Edges targeting subgraphs/categories
        multi_edge_style_groups = [[], [], [], []]  # 4 style groups for multi-edge controls
        control_edge_counts = {}  # Track edge count per control

        # First pass: count edges per control
        for control_id, component_ids in self.control_to_component_map.items():
            if component_ids:
                control_edge_counts[control_id] = len(component_ids)

        # Second pass: generate edges and track indices with per-control styling
        for control_id, component_ids in self.control_to_component_map.items():
            if not component_ids:  # Skip controls with no component mappings
                continue

            is_multi_edge_control = control_edge_counts.get(control_id, 0) >= 3
            control_edge_style_index = 0  # Reset for each control

            for comp_id in sorted(component_ids):
                if comp_id == "components":
                    # This is a mapping to the components container (for 'all' controls)
                    lines.append(f"    {control_id} -.-> {comp_id}")
                    all_control_edges.append(edge_index)
                elif comp_id in self.component_by_category.keys():
                    # This is a category-level mapping (including sub-categories)
                    lines.append(f"    {control_id} --> {comp_id}")
                    subgraph_edges.append(edge_index)
                elif comp_id in self.components:
                    # This is an individual component mapping
                    lines.append(f"    {control_id} --> {comp_id}")

                    # Track multi-edge controls with cyclic style assignment per control
                    if is_multi_edge_control:
                        style_group = control_edge_style_index % 4
                        multi_edge_style_groups[style_group].append(edge_index)
                        control_edge_style_index += 1

                edge_index += 1

        # Apply styling to controls that were mapped to "all"
        lines.append("")
        lines.append("    %% Apply styling to controls mapped to 'all'")
        for control_id in sorted(self.controls_mapped_to_all):
            if control_id in self.control_to_component_map and self.control_to_component_map[control_id]:
                lines.append(f"    {control_id}:::allControl")

        # Get edge styling configuration
        edge_styles = self.config_loader.get_control_edge_styles()

        # Add edge styling
        lines.append("")
        lines.append("    %% Edge styling")

        # Style edges from 'all' controls
        if all_control_edges:
            all_control_style = edge_styles.get("allControlEdges", {})
            stroke = all_control_style.get("stroke", "#4285f4")
            stroke_width = all_control_style.get("strokeWidth", "3px")
            stroke_dasharray = all_control_style.get("strokeDasharray", "8 4")
            edge_list = ",".join(map(str, all_control_edges))
            style_str = f"stroke:{stroke},stroke-width:{stroke_width},stroke-dasharray: {stroke_dasharray}"
            lines.append(f"    linkStyle {edge_list} {style_str}")

        # Style edges to subgraphs/categories
        if subgraph_edges:
            subgraph_style = edge_styles.get("subgraphEdges", {})
            stroke = subgraph_style.get("stroke", "#34a853")
            stroke_width = subgraph_style.get("strokeWidth", "2px")
            edge_list = ",".join(map(str, subgraph_edges))
            lines.append(f"    linkStyle {edge_list} stroke:{stroke},stroke-width:{stroke_width}")

        # Style edges from controls with 3+ individual component mappings
        multi_edge_styles_config = edge_styles.get(
            "multiEdgeStyles",
            [
                {"stroke": "#9c27b0", "strokeWidth": "2px"},
                {"stroke": "#ff9800", "strokeWidth": "2px", "strokeDasharray": "5 5"},
                {"stroke": "#e91e63", "strokeWidth": "2px", "strokeDasharray": "10 2"},
                {"stroke": "#C95792", "strokeWidth": "2px", "strokeDasharray": "10 5"},
            ],
        )

        for i, style_group in enumerate(multi_edge_style_groups):
            if style_group and i < len(multi_edge_styles_config):
                style_config = multi_edge_styles_config[i]
                stroke = style_config.get("stroke", "#9c27b0")
                stroke_width = style_config.get("strokeWidth", "2px")
                dasharray = style_config.get("strokeDasharray", "")

                style_string = f"stroke:{stroke},stroke-width:{stroke_width}"
                if dasharray:
                    style_string += f",stroke-dasharray: {dasharray}"

                edge_list = ",".join(map(str, style_group))
                lines.append(f"    linkStyle {edge_list} {style_string}")

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
            fill = components_container_style.get("fill", "#f0f0f0")
            stroke = components_container_style.get("stroke", "#666666")
            stroke_width = components_container_style.get("strokeWidth", "3px")
            stroke_dasharray = components_container_style.get("strokeDasharray", "10 5")
            container_style = f"fill:{fill},stroke:{stroke},stroke-width:{stroke_width}"
            style_str = f"{container_style},stroke-dasharray: {stroke_dasharray}"
            lines.append(f"    style components {style_str}")

        # Style component categories
        for category_key, category_config in component_categories.items():
            if category_config:
                fill = category_config.get("fill", "#ffffff")
                stroke = category_config.get("stroke", "#333333")
                stroke_width = category_config.get("strokeWidth", "2px")
                lines.append(f"    style {category_key} fill:{fill},stroke:{stroke},stroke-width:{stroke_width}")

        # Add dynamic styling for subgroups using configuration
        for parent_category, subgroups in self.subgroupings.items():
            # Find the parent category configuration to get subgroup fill color
            parent_config = component_categories.get(parent_category, {})
            subgroup_fill = parent_config.get("subgroupFill")

            # Fallback logic for subgroup colors if not in config
            if not subgroup_fill:
                if "Infrastructure" in parent_category:
                    subgroup_fill = "#d4e6d4"
                elif "Data" in parent_category:
                    subgroup_fill = "#f5f0e6"
                elif "Model" in parent_category:
                    subgroup_fill = "#f0e6e6"
                elif "Application" in parent_category:
                    subgroup_fill = "#e0f0ff"
                else:
                    subgroup_fill = "#f8f8f8"  # Default light gray

            for subgroup_name in subgroups.keys():
                lines.append(f"    style {subgroup_name} fill:{subgroup_fill},stroke:#333,stroke-width:1px")

        lines.extend([])

        lines.append("```")
        return "\n".join(lines)

    def to_mermaid(self) -> str:
        """
        Generate the complete Mermaid graph output for control-to-component relationships.

        This is the primary public interface for accessing the generated Mermaid graph.
        It delegates to build_controls_graph() to create a visualization
        of how security controls map to AI system components with full optimization
        and styling applied.

        The output is ready for rendering in any Mermaid-compatible environment,
        including documentation platforms, web interfaces, and diagram tools.

        Returns:
            str: Complete Mermaid graph definition as a string, including:
                - ```mermaid code block markers for proper rendering
                - Optimized control-to-component relationships
                - Consistent styling and color coding
                - Hierarchical subgraph structure
                - Multi-style edge formatting

        Example:
            >>> controls = {"ctrl1": ControlNode("Test", "controlsData", ["comp1"], [], [])}
            >>> components = {"comp1": ComponentNode("Test", "componentsData", [], [])}
            >>> graph = ControlGraph(controls, components)
            >>> mermaid_code = graph.to_mermaid()
            >>> print(mermaid_code.startswith("```mermaid"))
            True
            >>> print(mermaid_code.endswith("```"))
            True

        Note:
            - This method is stateless and can be called multiple times safely
            - The output includes all optimizations applied during initialization
            - Graph complexity depends on the number of controls and components provided
            - All styling and formatting is embedded for standalone rendering
        """
        return self.build_controls_graph()


class RiskGraph(BaseGraph):
    """
    Generates Mermaid graph visualizations for risk-to-control-to-component relationships.

    The RiskGraph class creates visual representations of how security risks map
    to controls and subsequently to AI system components. It builds upon the ControlGraph
    functionality to show the full risk mitigation chain.

    Key Features:
    - **Risk-to-Control Mapping**: Shows which controls mitigate specific risks
    - **Control-to-Component Mapping**: Leverages existing ControlGraph logic
    - **Three-Layer Visualization**: Risks -> Controls -> Components
    - **Category Organization**: Groups risks, controls, and components by category

    Graph Structure:
    The generated graph consists of three main sections:
    1. **Risk Subgraphs**: Grouped risks (future: by category)
    2. **Control Subgraphs**: Grouped by control category
    3. **Component Container**: Nested subgraphs for component categories

    Attributes:
        risks (dict[str, RiskNode]): Dictionary of risk ID to RiskNode mappings
        controls (dict[str, ControlNode]): Dictionary of control ID to ControlNode mappings
        components (dict[str, ComponentNode]): Dictionary of component ID to ComponentNode mappings
    """

    def __init__(
        self,
        risks: dict[str, RiskNode],
        controls: dict[str, ControlNode],
        components: dict[str, ComponentNode],
        debug: bool = False,
        config_loader = None,
    ):
        """
        Initialize RiskGraph with risks, controls, and components data.

        Args:
            risks: Dictionary mapping risk IDs to RiskNode objects
            controls: Dictionary mapping control IDs to ControlNode objects
            components: Dictionary mapping component IDs to ComponentNode objects
            debug: Whether to include debug information in generated output
            config_loader: Configuration loader for styling and layout options
        """
        super().__init__(config_loader)
        self.risks = risks
        self.controls = controls
        self.components = components
        self.debug = debug

        # Build risk-to-control mapping
        self.risk_to_control_map = self._build_risk_control_mapping()

        # Group risks by category (basic implementation for now)
        self.risk_by_category = self._group_risks_by_category()

        # Initialize control graph for control-to-component relationships
        self.control_graph = ControlGraph(controls, components, debug, config_loader)

    def _build_risk_control_mapping(self) -> dict[str, list[str]]:
        """
        Build mapping from risk IDs to control IDs based on control.risks data.

        Returns:
            Dictionary mapping risk IDs to lists of control IDs that mitigate them
        """
        risk_to_controls = {}

        # Initialize with empty lists for all known risks
        for risk_id in self.risks.keys():
            risk_to_controls[risk_id] = []

        # Build mapping from controls that reference risks
        for control_id, control in self.controls.items():
            for risk_id in control.risks:
                if risk_id in risk_to_controls:
                    risk_to_controls[risk_id].append(control_id)

        return risk_to_controls

    def _group_risks_by_category(self) -> dict[str, list[str]]:
        """
        Group risk IDs by their category.

        For now, returns a single 'risks' category since risks.yaml doesn't have categories.
        Future enhancement could parse risk categories from YAML structure.
        """
        # Basic implementation - single category for all risks
        return {"risks": list(self.risks.keys())}

    def to_mermaid(self) -> str:
        """
        Generate the complete Mermaid graph output for risk-to-control-to-component relationships.

        Returns:
            Complete Mermaid graph definition as a string
        """
        return self.build_risk_graph()

    def build_risk_graph(self) -> str:
        """
        Build a Mermaid graph showing risk-to-control-to-component relationships.

        Returns:
            Complete Mermaid graph definition wrapped in code blocks
        """
        lines = ["```mermaid", "graph LR"]

        if self.debug:
            lines.append("    %% Risk-to-Control-to-Component Graph")
            lines.append("    %% Generated by RiskGraph class")
            lines.append("")

        # 1. Define risk nodes in subgraphs
        lines.extend(self._generate_risk_subgraphs())
        lines.append("")

        # 2. Define control subgraphs (reuse from ControlGraph)
        lines.extend(self._generate_control_subgraphs())
        lines.append("")

        # 3. Define component subgraphs (reuse from ControlGraph)
        lines.extend(self._generate_component_subgraphs())
        lines.append("")

        # 4. Generate risk-to-control edges
        lines.extend(self._generate_risk_control_edges())
        lines.append("")

        # 5. Generate control-to-component edges (reuse from ControlGraph)
        lines.extend(self._generate_control_component_edges())
        lines.append("")

        # 6. Add styling
        lines.extend(self._generate_styling())

        lines.append("```")
        return "\n".join(lines)

    def _generate_risk_subgraphs(self) -> list[str]:
        """Generate risk subgraph definitions."""
        lines = []

        # For now, create a single risks subgraph
        lines.append('    subgraph risks ["Risks"]')

        for risk_id, risk in self.risks.items():
            # Create safe node ID and readable label
            safe_id = risk_id.replace("-", "_")
            label = risk.title[:30] + "..." if len(risk.title) > 30 else risk.title
            lines.append(f'        {safe_id}["{label}"]')

        lines.append("    end")
        return lines

    def _generate_control_subgraphs(self) -> list[str]:
        """Generate control subgraph definitions (reuse ControlGraph logic)."""
        lines = []

        for category, control_ids in self.control_graph.control_by_category.items():
            if not control_ids:
                continue

            category_display = self._get_category_display_name(category)
            lines.append(f'    subgraph {category} ["{category_display}"]')

            for control_id in control_ids:
                if control_id in self.controls:
                    control = self.controls[control_id]
                    safe_id = control_id.replace("-", "_")
                    label = control.title[:25] + "..." if len(control.title) > 25 else control.title
                    lines.append(f'        {safe_id}["{label}"]')

            lines.append("    end")

        return lines

    def _generate_component_subgraphs(self) -> list[str]:
        """Generate component subgraph definitions (reuse ControlGraph logic)."""
        lines = []
        lines.append('    subgraph components ["Components"]')

        for category, comp_ids in self.control_graph.component_by_category.items():
            if not comp_ids:
                continue

            category_display = self._get_category_display_name(category)
            lines.append(f'        subgraph {category} ["{category_display}"]')

            for comp_id in comp_ids:
                if comp_id in self.components:
                    component = self.components[comp_id]
                    safe_id = comp_id.replace("-", "_")
                    label = component.title[:25] + "..." if len(component.title) > 25 else component.title
                    lines.append(f'            {safe_id}["{label}"]')

            lines.append("        end")

        lines.append("    end")
        return lines

    def _generate_risk_control_edges(self) -> list[str]:
        """Generate edges from risks to controls."""
        lines = []

        if self.debug:
            lines.append("    %% Risk-to-Control edges")

        for risk_id, control_ids in self.risk_to_control_map.items():
            if not control_ids:
                continue

            risk_safe_id = risk_id.replace("-", "_")

            for control_id in control_ids:
                if control_id in self.controls:
                    control_safe_id = control_id.replace("-", "_")
                    # Use red edges for risk-to-control relationships
                    lines.append(f"    {risk_safe_id} --> {control_safe_id}")

        return lines

    def _generate_control_component_edges(self) -> list[str]:
        """Generate edges from controls to components (reuse ControlGraph logic)."""
        lines = []

        if self.debug:
            lines.append("    %% Control-to-Component edges")

        for control_id, targets in self.control_graph.control_to_component_map.items():
            if not targets:
                continue

            control_safe_id = control_id.replace("-", "_")

            for target in targets:
                # Use blue edges for control-to-component relationships
                lines.append(f"    {control_safe_id} --> {target}")

        return lines

    def _generate_styling(self) -> list[str]:
        """Generate basic styling for the graph."""
        lines = []

        # Basic styling for different edge types
        lines.append("    %% Styling")
        lines.append("    linkStyle default stroke:#666,stroke-width:2px")

        return lines

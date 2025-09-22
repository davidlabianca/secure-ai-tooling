from pathlib import Path
from typing import Any

import yaml

from ..config import DEFAULT_MERMAID_CONFIG_FILE


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
                "risk": {
                    "direction": "TD",
                    "flowchartConfig": {"nodeSpacing": 30, "rankSpacing": 40, "padding": 5, "wrappingWidth": 250},
                    "specialStyling": {
                        "componentsContainer": {
                            "fill": "#f0f0f0",
                            "stroke": "#666666",
                            "strokeWidth": "3px",
                            "strokeDasharray": "10 5",
                        },
                        "riskCategories": {
                            "risks": {
                                "fill": "#ffeef0",
                                "stroke": "#e91e63",
                                "strokeWidth": "2px",
                                "subgroupFill": "#ffe0e6",
                            }
                        },
                        "edgeStyles": {
                            "riskControlEdges": {
                                "stroke": "#e91e63",
                                "strokeWidth": "2px",
                                "strokeDasharray": "5 3",
                            },
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

        lines: list[str] = []

        if frontmatter_config := graph_config.get("metadata"):
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
                f"    classDef hidden {hidden_class_def}",
                f"    classDef allControl {all_control_class_def}",
                "",
            ]
        )

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

    def get_risk_category_styles(self) -> dict:
        """
        Retrieve risk category styling configuration for visual differentiation.

        Returns styling properties for risk categories including fill colors,
        stroke colors, stroke widths, and subgroup fills. These styles are used by
        RiskGraph to create visually distinct risk category subgraphs.

        Returns:
            dict: Risk category styling configuration mapping category IDs to
                 style dictionaries. Always returns a valid dictionary, empty if
                 no configuration is found.

        Example:
            >>> loader = MermaidConfigLoader()
            >>> styles = loader.get_risk_category_styles()
            >>> risk_style = styles.get('risks', {})
            >>> print(risk_style.get('fill'))  # '#ffeef0'
        """
        result = self._get_safe_value("graphTypes", "risk", "specialStyling", "riskCategories", default={})
        return result if isinstance(result, dict) else {}

    def get_risk_edge_styles(self) -> dict:
        """
        Retrieve edge styling configuration specifically for risk graph relationships.

        Returns edge styling definitions used by RiskGraph to create
        visually distinct relationship types through color, width, and dash patterns.
        This includes risk-to-control edges as well as inherited control-component edges.

        Edge Style Categories:
        - **riskControlEdges**: Styling for risk-to-control relationships (pink dashed)
        - **allControlEdges**: Styling for controls mapped to all components (dotted blue)
        - **subgraphEdges**: Styling for category-level mappings (solid green)
        - **multiEdgeStyles**: Array of 4 cycling styles for controls with 3+ edges

        Returns:
            dict: Edge styling configuration with nested style definitions.
                 Always returns a valid dictionary, empty if no configuration found.

        Example:
            >>> loader = MermaidConfigLoader()
            >>> edge_styles = loader.get_risk_edge_styles()
            >>> risk_control = edge_styles.get('riskControlEdges', {})
            >>> print(risk_control.get('stroke'))  # '#e91e63'
        """
        result = self._get_safe_value("graphTypes", "risk", "specialStyling", "edgeStyles", default={})
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


class UnionFind:
    def __init__(self, elements):
        """
        Initialize Union-Find data structure for a collection of elements.

        Creates two key data structures:
        - parent: Maps each element to its parent in the tree structure
        - rank: Tracks tree depth for optimization (union by rank)

        Initially, each element is its own parent (separate set).
        """
        self.parent = {elem: elem for elem in elements}  # Each element starts as its own parent
        self.rank = {elem: 0 for elem in elements}  # All trees start with rank 0

    def find(self, x):
        """
        Find the root representative of the set containing element x.
        """
        if self.parent[x] != x:
            # Path compression: make x point directly to the root
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        """
        Merge the sets containing elements x and y.

        Uses UNION BY RANK optimization
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
        Extract all disjoint sets as a list of clusters.

        Process:
        1. For each element, find its root representative
        2. Group all elements with the same root into a cluster
        3. Return list of clusters (sets)

        Note: We call find() to ensure path compression is applied
        and we get the true root after all union operations.

        Returns: List of sets, where each set is a cluster of related elements
        """
        clusters = {}
        for elem in self.parent:
            root = self.find(elem)  # Get root (with path compression)
            if root not in clusters:
                clusters[root] = set()
            clusters[root].add(elem)
        return list(clusters.values())

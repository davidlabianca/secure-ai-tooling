# Customizing Graph Appearance

The CoSAI Risk Map system generates a visual Mermaid graph of component relationships. You can fully customize its appearance through the `risk-map/yaml/mermaid-styles.yaml` configuration file.

## Understanding the Configuration Structure

The `mermaid-styles.yaml` file uses a hierarchical structure with four main sections:

### Foundation Design Tokens

Define semantic colors, stroke widths, and patterns used throughout the system:

```yaml
foundation:
  colors:
    primary: '#4285f4' # Google Blue - used for primary actions and "all" controls
    success: '#34a853' # Google Green - used for success states and category mappings
    accent: '#9c27b0' # Purple - first multi-edge style color
    warning: '#ff9800' # Orange - second multi-edge style color
    error: '#e91e63' # Pink - third multi-edge style color
    neutral: '#333333' # Dark gray - used for borders and strokes
    lightGray: '#f0f0f0' # Light gray - container backgrounds
    darkGray: '#666666' # Medium gray - container borders
  strokeWidths:
    thin: '1px' # Subgroup borders
    medium: '2px' # Standard component and control borders
    thick: '3px' # Emphasis elements like container borders
  strokePatterns:
    solid: '' # No dash pattern (solid lines)
    dashed: '5 5' # Standard dashed pattern
    dotted: '8 4' # Dotted pattern for "all" control edges
    longDash: '10 2' # Long dash pattern for multi-edge styles
    longDashSpaced: '10 5' # Long dash with spacing for containers
```

### Shared Elements

Elements used by the component graph:

```yaml
sharedElements:
  cssClasses:
    hidden: 'display: none;'
    allControl: 'stroke:#4285f4,stroke-width:2px,stroke-dasharray: 5 5'
  componentCategories:
    componentsInfrastructure:
      fill: '#e6f3e6' # Light green for infrastructure components
      stroke: '#333333' # Dark gray border
      strokeWidth: '2px' # Medium border width
    componentsApplication:
      fill: '#e6f0ff' # Light blue for application components
      stroke: '#333333' # Dark gray border
      strokeWidth: '2px' # Medium border width
    componentsModel:
      fill: '#ffe6e6' # Light red for model components
      stroke: '#333333' # Dark gray border
      strokeWidth: '2px' # Medium border width
```

### Graph Type Configurations

Specific settings for the component graph:

```yaml
graphTypes:
  component:
    direction: 'TD' # Top-down layout for component relationships
    flowchartConfig:
      padding: 5 # Internal node padding
      wrappingWidth: 250 # Text wrapping width
```

## Common Customization Examples

### 1. Change Component Category Color Scheme

To modify the color scheme for component categories:

```yaml
sharedElements:
  componentCategories:
    componentsInfrastructure:
      fill: '#e3f2fd' # Light blue instead of green
      stroke: '#333333'
      strokeWidth: '2px'
    componentsApplication:
      fill: '#f3e5f5' # Light purple instead of blue
      stroke: '#333333'
      strokeWidth: '2px'
```

### 2. Modify Graph Layout and Spacing

To change graph orientation and spacing:

```yaml
graphTypes:
  component:
    direction: 'LR' # Change to left-right layout
    flowchartConfig:
      nodeSpacing: 40 # Increase space between nodes
      rankSpacing: 50 # Increase space between levels
      wrappingWidth: 300 # Allow wider text labels
```

### 3. Adjust Foundation Colors for Brand Consistency

To align with organizational brand colors:

```yaml
foundation:
  colors:
    primary: '#0066cc' # Your brand primary color
    success: '#00aa44' # Your brand success color
    accent: '#6600cc' # Your brand accent color
    neutral: '#404040' # Darker borders for better contrast
```

## Testing Your Customizations

1. **Edit the configuration**: Modify `risk-map/yaml/mermaid-styles.yaml`

2. **Validate your changes** using the pre-commit hooks:

   ```bash
   # Stage your changes
   git add risk-map/yaml/mermaid-styles.yaml

   # Commit to trigger validation
   git commit -m "Update graph styling"
   ```

3. **Generate a test graph** to preview your changes:

   ```bash
   # Generate component graph with your styling
   python3 scripts/hooks/validate_riskmap.py --to-graph test-component.md --force
   ```

4. **View the results** by opening the generated Markdown files in a compatible viewer (see Visualizing Graphs below).

## Configuration Validation

The system automatically validates your configuration against a JSON schema that enforces:

- **Color format**: All colors must be valid 6-digit hex codes (`#RRGGBB`)
- **Required properties**: Essential configuration elements cannot be omitted
- **Value constraints**: Node spacing must be positive integers, direction must be valid Mermaid values (`TD`, `LR`, etc.)
- **Structural integrity**: Proper YAML structure and object nesting

If your configuration is invalid, you'll see detailed error messages indicating exactly what needs to be fixed.

## Fallback and Error Handling

The system includes robust fallback mechanisms:

- **Missing configuration file**: Uses built-in defaults that match the original hardcoded styling
- **Invalid configuration**: Falls back to defaults while displaying clear error messages
- **Partial configuration**: Missing elements use sensible defaults from the emergency configuration

This ensures that graph generation never fails due to configuration issues, allowing you to iterate on styling without breaking functionality.

## Visualizing Graphs During Development

The generated Mermaid graphs use the **Elk layout engine** for automatic positioning. To properly view these graphs during development:

### Compatible Viewers:

- **Mermaid.ink**: Online service that supports Elk layout
  - Copy the `.mermaid` file content to https://mermaid.ink/
  - Provides accurate rendering of complex layouts
- **VS Code with Mermaid extensions** that support Elk (check extension documentation)
- **GitHub**: Native Mermaid rendering does not support Elk layout and the maps will appear as poorly organized or unwieldy to review

### Generate Both Formats:

```bash
# Generate both .md and .mermaid formats for easier viewing
python scripts/hooks/validate_riskmap.py --to-graph ./test.md --mermaid-format --force

# This creates:
# - test.md (markdown with code block)
# - test.mermaid (raw mermaid content for online viewers)
```

### Troubleshooting Visualization:

- **Layout appears broken**: Ensure your viewer supports Elk layout engine
- **Components overlap**: Try mermaid.ink which handles Elk positioning correctly
- **Styling not applied**: Some viewers may not support all Mermaid styling features

## Advanced Customization Tips

- **Consistent color schemes**: Use the `foundation.colors` section to define a palette, then reference these colors throughout the configuration
- **Accessibility**: Choose colors with sufficient contrast ratios for accessibility compliance
- **Testing**: Generate graphs with diverse content (few vs. many components/controls) to ensure your styling works across different scenarios
- **Version control**: Document your customization rationale in commit messages for future reference

---

**Related:** See [Validation Tools](validation.md) for graph generation commands, or [Troubleshooting](troubleshooting.md) if you encounter issues with graph visualization.

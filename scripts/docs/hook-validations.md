# Pre-commit Hook Validations

The pre-commit hook runs seven validations before allowing commits:

## 1. YAML Schema Validation

Validates all YAML files against their corresponding JSON schemas.

**Files validated:**

- `yaml/components.yaml` → `schemas/components.schema.json`
- `yaml/controls.yaml` → `schemas/controls.schema.json`
- `yaml/personas.yaml` → `schemas/personas.schema.json`
- `yaml/risks.yaml` → `schemas/risks.schema.json`
- `yaml/self-assessment.yaml` → `schemas/self-assessment.schema.json`
- `yaml/mermaid-styles.yaml` → `schemas/mermaid-styles.schema.json`

## 2. Prettier YAML Formatting

Automatically formats YAML files in the `risk-map/yaml/` directory using Prettier to ensure consistent code style.

**Behavior:**

- **Normal mode**: Formats only staged YAML files in `risk-map/yaml/`
- **Force mode**: Formats all YAML files in `risk-map/yaml/`
- **Auto-staging**: Formatted files are automatically re-staged in normal mode

**Files formatted:**

- `risk-map/yaml/components.yaml`
- `risk-map/yaml/controls.yaml`
- `risk-map/yaml/personas.yaml`
- `risk-map/yaml/risks.yaml`
- `risk-map/yaml/self-assessment.yaml`
- `risk-map/yaml/mermaid-styles.yaml`

## 3. Ruff Python Linting

Runs ruff linting on Python files to enforce code quality and style standards.

**Behavior:**

- **Normal mode**: Lints only staged Python files
- **Force mode**: Lints all Python files in the repository
- **Strict enforcement**: Commit fails if any linting issues are found

**Configuration**: Uses the project's `pyproject.toml` or `ruff.toml` configuration file.

## 4. Component Edge Validation & Graph Generation

Validates the consistency of component relationships in `components.yaml` and generates visual graphs:

**Validation Features:**

- **Edge consistency**: Ensures that if Component A has `to: [B]`, then Component B has `from: [A]`
- **Bidirectional matching**: Verifies that all `to` edges have corresponding `from` edges and vice versa
- **Isolated component detection**: Identifies components with no edges (neither `to` nor `from`)

**Automatic Graph Generation Features:**

- **Component Graph**: When `components.yaml` is staged for commit, automatically generates `./risk-map/diagrams/risk-map-graph.md`
  - Topological ranking with `componentDataSources` always at rank 1
  - Category-based subgraphs (Data, Infrastructure, Model, Application)
  - Mermaid format with color coding and dynamic spacing
- **Control Graph**: When `components.yaml` OR `controls.yaml` is staged for commit, automatically generates `./risk-map/diagrams/controls-graph.md`
  - Shows control-to-component relationships with optimization
  - Dynamic component clustering and category-level mappings
  - Multi-edge styling with consistent color schemes
- **Risk Graph**: When `components.yaml`, `controls.yaml` OR `risks.yaml` is staged for commit, automatically generates `./risk-map/diagrams/controls-to-risk-graph.md`
  - Maps controls to risks they mitigate with component context
  - Organizes risks into 5 color-coded category subgraphs
  - Visualizes three-layer relationships: risks → controls → components
- **Auto-staging**: Both generated graphs are automatically added to staged files for inclusion in commit

**Example validation:**

```yaml
components:
  - id: componentA
    edges:
      to: [componentB]
      from: []
  - id: componentB
    edges:
      to: []
      from: [componentA] # ✅ Matches componentA's 'to' edge
```

## 5. Control-to-Risk Reference Validation

Validates cross-reference consistency between `controls.yaml` and `risks.yaml`:

- **Bidirectional consistency**: Ensures that if a control lists a risk, that risk also references the control
- **Isolated entry detection**: Finds controls with no risk references or risks with no control references
- **all or none awareness**: Will not flag controls that leverage the `all` or `none` risk mappings

**Example validation:**

```yaml
# controls.yaml
controls:
  - id: CTRL-001
    risks: # Control addresses these risks
      - RISK-001
      - RISK-002

# risks.yaml
risks:
  - id: RISK-001
    controls:
      - CTRL-001 # ✅ Risk references the control back
  - id: RISK-002
    controls:
      - CTRL-001 # ✅ Bidirectional consistency maintained
```

## 6. Mermaid SVG Generation

Automatically generates SVG files from Mermaid diagrams when `.mmd` or `.mermaid` files are staged for commit:

**Features:**

- **Automatic conversion**: Converts staged Mermaid files in `risk-map/docs/` to SVG format
- **Output location**: SVG files are saved to `risk-map/svg/` with matching filenames
- **Auto-staging**: Generated SVG files are automatically added to staged files for commit
- **Prerequisites check**: Validates that required tools (npx, mermaid-cli, Chrome/Chromium) are available
- **Platform-aware**: Handles Chrome/Chromium detection across different platforms

**Dependencies:**

- **Node.js 18+**: Required for npx and mermaid-cli execution
- **@mermaid-js/mermaid-cli**: Installed via `npm install` (converts .mmd to .svg)
- **Chrome/Chromium**: Used by mermaid-cli via puppeteer for rendering SVGs
  - **Mac/Windows/Linux x64**: Automatic Chrome detection (puppeteer bundled with dependencies handles Chrome)
  - **Linux ARM64**: Manual Chromium setup required since Google Chrome is not available for ARM64

**Example workflow:**

```bash
# Stage a mermaid file for commit
git add risk-map/docs/component-flow.mmd

# Pre-commit hook automatically:
# 1. Detects the staged .mmd file
# 2. Converts it to risk-map/svg/component-flow.svg
# 3. Stages the generated SVG for commit

git commit -m "Add component flow diagram"
# Both the .mmd source and generated .svg are committed
```

**Behavior:**

- **Normal mode**: Only processes staged `.mmd/.mermaid` files in `risk-map/docs/`
- **Force mode**: Skips SVG generation (generation only runs for actual commits)
- **Error handling**: Gracefully handles missing Chrome/Chromium with clear error messages

## 7. Markdown Table Generation

Automatically generates markdown tables from YAML files when staged for commit:

**Features:**

- **Automatic conversion**: Converts staged YAML to multiple table formats
- **Output location**: Tables saved to `risk-map/tables/` with format-specific filenames
- **Smart regeneration**: Cross-reference tables regenerated when dependencies change
- **Auto-staging**: Generated tables automatically added to commit

**Generation rules:**

- `components.yaml` staged → generates `components-full.md`, `components-summary.md`, and regenerates `controls-xref-components.md`
- `risks.yaml` staged → generates `risks-full.md`, `risks-summary.md`, and regenerates `controls-xref-risks.md`
- `controls.yaml` staged → generates all 4 formats: `controls-full.md`, `controls-summary.md`, `controls-xref-risks.md`, `controls-xref-components.md`

**Dependencies:**

- Python 3.10+
- pandas (already in requirements.txt)

**Example workflow:**

```bash
# Edit controls.yaml
git add risk-map/yaml/controls.yaml

# Pre-commit hook automatically:
# 1. Detects staged controls.yaml
# 2. Generates all 4 control table formats
# 3. Stages the generated markdown files

git commit -m "Update controls"
# Both YAML and 4 generated tables are committed
```

**Behavior:**

- **Normal mode**: Only processes staged YAML files in `risk-map/yaml/`
- **Force mode**: Skips table generation (generation only runs for actual commits)

---

**Related:**
- [Validation Flow](validation-flow.md) - When each validation runs
- [Manual Validation](manual-validation.md) - Running validations manually
- [Troubleshooting](troubleshooting.md) - Common validation errors

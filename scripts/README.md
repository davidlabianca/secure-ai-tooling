# Scripts
Development tools and utilities for this project.

## Git Hooks

### Setup

**Prerequisites:**
- Python 3.10 or higher
- Node.js and npm

Install dependencies and pre-commit hook (one-time setup):
```bash
# Install required Python packages
pip install -r requirements.txt

# Install Node.js dependencies (prettier, etc.)
npm install

# Install ruff (Python linter)
pip install ruff

# Install the pre-commit hook
./install-precommit-hook.sh
```

### What it does
The pre-commit hook runs five validations before allowing commits:

#### 1. YAML Schema Validation
Validates all YAML files against their corresponding JSON schemas.

**Files validated:**
- `yaml/components.yaml` → `schemas/components.schema.json`
- `yaml/controls.yaml` → `schemas/controls.schema.json`
- `yaml/personas.yaml` → `schemas/personas.schema.json`
- `yaml/risks.yaml` → `schemas/risks.schema.json`
- `yaml/self-assessment.yaml` → `schemas/self-assessment.schema.json`

#### 2. Prettier YAML Formatting
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

#### 3. Ruff Python Linting
Runs ruff linting on Python files to enforce code quality and style standards.

**Behavior:**
- **Normal mode**: Lints only staged Python files
- **Force mode**: Lints all Python files in the repository
- **Strict enforcement**: Commit fails if any linting issues are found

**Configuration**: Uses the project's `pyproject.toml` or `ruff.toml` configuration file.

#### 4. Component Edge Validation & Graph Generation
Validates the consistency of component relationships in `components.yaml` and generates visual graphs:

**Validation Features:**
- **Edge consistency**: Ensures that if Component A has `to: [B]`, then Component B has `from: [A]`
- **Bidirectional matching**: Verifies that all `to` edges have corresponding `from` edges and vice versa
- **Isolated component detection**: Identifies components with no edges (neither `to` nor `from`)

**Graph Generation Features:**
- **Automatic generation**: When `components.yaml` is staged for commit, automatically generates `./risk-map/docs/risk-map-graph.md`
- **Topological ranking**: Components are ranked with `componentDataSources` always at rank 1
- **Category-based subgraphs**: Organizes components into Data, Infrastructure, Model, and Application subgraphs
- **Mermaid format**: Generates Mermaid-compatible diagrams with color coding and dynamic spacing
- **Auto-staging**: Generated graph is automatically added to staged files for inclusion in commit

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
      from: [componentA]  # ✅ Matches componentA's 'to' edge
```

#### 5. Control-to-Risk Reference Validation
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
    - CTRL-001  # ✅ Risk references the control back
  - id: RISK-002
    controls:
    - CTRL-001  # ✅ Bidirectional consistency maintained
```

### Requirements
Install all required Python packages:
```bash
pip install -r requirements.txt
```

**Required packages** (from `requirements.txt`):
- `PyYAML` - YAML file parsing and manipulation
- `check-jsonschema` - JSON schema validation for YAML files
- `pytest` - Testing framework for validation scripts
- `ruff` - Python linting and formatting

**Additional dependencies** (from `package.json`):
- `prettier` - Code formatting for YAML files

**Individual installation** (if needed):
```bash
pip install PyYAML check-jsonschema pytest ruff
npm install prettier
```

### Files
- `hooks/pre-commit` - The main git hook script that orchestrates all validations
- `hooks/validate_component_edges.py` - Python script for component edge validation
- `hooks/validate_control_risk_references.py` - Python script for control-risk cross-reference validation
- `install-precommit-hook.sh` - Installs all hooks to your local `.git/hooks/`

### Validation Flow
When you commit changes, the hook will:

1. **Schema Validation** - Check YAML structure and data types
2. **Prettier Formatting** - Format YAML files in `risk-map/yaml/` and re-stage them
3. **Ruff Linting** - Lint Python files for code quality
4. **Edge Validation** - Verify component relationship consistency
5. **Graph Generation** - If `components.yaml` changed, generate and stage `./risk-map/docs/risk-map-graph.md`
6. **Control-Risk Validation** - Verify control-risk cross-reference consistency
7. **Block commit** if any validation fails

**Note**: Graph generation only occurs when `components.yaml` is staged for commit, not in `--force` mode.

#### Manual Validation of Unstaged Files
The `pre-commit` hook and all individual validation scripts support the `--force` flag to validate all files regardless of their git staging status (useful during development).

```bash
# Validating unstaged files during development...
# Note: --force validates all relevant files, not just those staged for commit

# Run all validation steps
.git/hooks/pre-commit --force

# Run component edge validation-only
.git/hooks/validate_component_edges.py --force

# Run control-to-risk reference validation-only
.git/hooks/validate_control_risk_references.py --force

```

#### Manual Graph Generation
Generate component graphs and control-to-component graphs manually using the validation script:

```bash
# Validate edges and generate clean component graph without debug comments
.git/hooks/validate_component_edges.py --to-graph ./docs/component-map.md --force

# Generate component graph with rank debugging information
.git/hooks/validate_component_edges.py --to-graph ./docs/debug-graph.md --debug --force

# Generate control-to-component graph visualization
.git/hooks/validate_component_edges.py --to-controls-graph ./docs/controls-graph.md --force
```

**Graph Generation Options:**
- `--to-graph PATH` - Output component relationship Mermaid graph to specified file
- `--to-controls-graph PATH` - Output control-to-component relationship graph to specified file
- `--debug` - Include rank comments for debugging (component graphs only)
- `--quiet` - Minimize output (only show errors)
- `--allow-isolated` - Allow components with no edges

### Troubleshooting

#### Installing over existing hooks
If you already have git hooks and want to replace them:
```bash
./install-precommit-hook.sh --force
```

#### Bypassing validation (emergencies only)
To temporarily skip all validation:
```bash
git commit --no-verify -m "emergency commit"
```

#### Common edge validation errors
```
❌ Component 'componentA': missing incoming edges for: componentB
```
**Fix**: Add `componentA` to `componentB`'s `from` list

```
❌ Found 1 isolated components (no edges): componentOrphan
```
**Fix**: Either add edges to the component or remove it if it's unused

#### Common control-to-risk validation errors
```
❌ [ISSUE: risks.yaml] Control 'CTRL-001' claims to address risks ['RISK-005'] in controls.yaml,
   but these risks don't list this control in their 'controls' section in risks.yaml
```
**Fix**: Add `CTRL-001` to the `controls` list for `RISK-005` in `risks.yaml`

```
❌ [ISSUE: controls.yaml] Risks ['RISK-003'] reference control 'CTRL-999' in risks.yaml,
   but this control doesn't list these risks in its 'risks' section in controls.yaml
```
**Fix**: Add `RISK-003` to the `risks` list for `CTRL-999` in `controls.yaml`, or remove the invalid control reference

```
❌ [ISSUE: controls.yaml] Control 'CTRL-002' is referenced by risks ['RISK-001'] in risks.yaml,
   but this control doesn't exist in controls.yaml
```
**Fix**: Either create `CTRL-002` in `controls.yaml` or remove the reference from `risks.yaml`

#### Common prettier formatting errors
```
❌ Prettier formatting failed for risk-map/yaml/components.yaml
```
**Fix**: Check that prettier is installed (`npm install -g prettier`) and the YAML file syntax is valid

```
⚠️ Warning: Could not stage formatted file risk-map/yaml/components.yaml
```
**Fix**: Check file permissions and git repository status

#### Common ruff linting errors
```
❌ Ruff linting failed for staged files
```
**Fix**: Run `ruff check --fix .` to automatically fix auto-fixable issues, or manually address the linting violations shown in the output

```
❌ Ruff linting failed
```
**Fix**: Check that ruff is installed (`pip install ruff`) and review the specific linting errors in the output

#### Debugging validation manually
Run the component edge validator manually:
```bash
python3 .git/hooks/validate_component_edges.py
```

Run the component edge validator even if files aren't staged:
```bash
python3 .git/hooks/validate_component_edges.py --force
```

Run the control-risk validator manually:
```bash
python3 .git/hooks/validate_control_risk_references.py
```

Force validation of control-risk references even if files aren't staged:
```bash
python3 .git/hooks/validate_control_risk_references.py --force
```

Run prettier formatting manually:
```bash
# Format all YAML files in risk-map/yaml/
npx prettier --write risk-map/yaml/*.yaml

# Check formatting without modifying files
npx prettier --check risk-map/yaml/*.yaml
```

Run ruff linting manually:
```bash
# Lint all Python files
ruff check .

# Lint specific files
ruff check tools/ scripts/

# Auto-fix issues where possible
ruff check --fix .
```

#### Debugging graph generation
Test graph generation without affecting git staging:
```bash
# Generate component graph to test output
python3 .git/hooks/validate_component_edges.py --to-graph ./test-graph.md --force

# Generate component graph with debug information to understand ranking
python3 .git/hooks/validate_component_edges.py --to-graph ./debug-graph.md --debug --force

# Generate control-to-component graph to test relationships
python3 .git/hooks/validate_component_edges.py --to-controls-graph ./controls-test.md --force

# View help for all graph options
python3 .git/hooks/validate_component_edges.py --help
```

**Common graph generation issues:**
```
❌ Graph generation failed
```
**Fix**: Check that the component and control YAML files are valid and accessible, ensure write permissions for output directory

```
⚠️ Warning: Could not stage generated graph
```
**Fix**: This occurs during pre-commit when git staging fails - check file permissions and git repository status

**Control graph specific issues:**
```
❌ Control-to-component graph generation failed
```
**Fix**: Verify that both `controls.yaml` and `components.yaml` are accessible and properly formatted. Check that control component references are valid.

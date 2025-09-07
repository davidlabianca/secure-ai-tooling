# Scripts
Development tools and utilities for this project.

## Git Hooks

### Setup
Install the pre-commit hook (one-time setup):
```bash
./install-precommit-hook.sh
```

### What it does
The pre-commit hook runs two validations before allowing commits:

#### 1. YAML Schema Validation
Validates all YAML files against their corresponding JSON schemas.

**Files validated:**
- `yaml/components.yaml` → `schemas/components.schema.json`
- `yaml/controls.yaml` → `schemas/controls.schema.json`
- `yaml/personas.yaml` → `schemas/personas.schema.json`
- `yaml/risks.yaml` → `schemas/risks.schema.json`
- `yaml/self-assessment.yaml` → `schemas/self-assessment.schema.json`

#### 2. Component Edge Validation
Validates the consistency of component relationships in `components.yaml`:

- **Edge consistency**: Ensures that if Component A has `to: [B]`, then Component B has `from: [A]`
- **Bidirectional matching**: Verifies that all `to` edges have corresponding `from` edges and vice versa
- **Isolated component detection**: Identifies components with no edges (neither `to` nor `from`)

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

### Requirements
- `check-jsonschema`: Install with `pip install check-jsonschema`
- `python3` with `pyyaml`: Install with `pip install pyyaml`

### Files
- `hooks/pre-commit` - The main git hook script that orchestrates both validations
- `hooks/validate_component_edges.py` - Python script for component edge validation
- `install-precommit-hook.sh` - Installs both hooks to your local `.git/hooks/`

### Validation Flow
When you commit changes to YAML files, the hook will:

1. **Schema Validation** - Check YAML structure and data types
2. **Edge Validation** - Verify component relationship consistency
3. **Block commit** if either validation fails
4. **Allow commit** only when both validations pass

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

#### Debugging edge validation
Run the edge validator manually on any YAML file:
```bash
python3 .git/hooks/validate_component_edges.py path/to/components.yaml
```

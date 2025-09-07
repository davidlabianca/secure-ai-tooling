# Scripts
Development tools and utilities for this project.

## Git Hooks

### Setup
Install the pre-commit hook (one-time setup):
```bash
./install-precommit-hook.sh
```

### What it does
The pre-commit hook runs three validations before allowing commits:

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

#### 3. Control-to-Risk Reference Validation
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
- `check-jsonschema`: Install with `pip install check-jsonschema`
- `python3` with `pyyaml`: Install with `pip install pyyaml`

### Files
- `hooks/pre-commit` - The main git hook script that orchestrates all validations
- `hooks/validate_component_edges.py` - Python script for component edge validation
- `hooks/validate_control_risk_references.py` - Python script for control-risk cross-reference validation
- `install-precommit-hook.sh` - Installs all hooks to your local `.git/hooks/`

### Validation Flow
When you commit changes to YAML files, the hook will:

1. **Schema Validation** - Check YAML structure and data types
2. **Edge Validation** - Verify component relationship consistency
3. **Control-Risk Validation** - Verify control-risk cross-reference consistency
4. **Block commit** if any validation fails

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

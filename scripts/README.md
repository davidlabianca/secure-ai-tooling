# Scripts

Development tools and utilities for this project.

## Git Hooks

### Setup
Install the pre-commit hook (one-time setup):
```bash
./install-precommit-hook.sh
```

### What it does
The pre-commit hook validates all YAML files against their corresponding JSON schemas before allowing commits.

**Files validated:**
- `yaml/components.yaml` → `schemas/components.schema.json`
- `yaml/controls.yaml` → `schemas/controls.schema.json`
- `yaml/personas.yaml` → `schemas/personas.schema.json`
- `yaml/risks.yaml` → `schemas/risks.schema.json`
- `yaml/self-assessment.yaml` → `schemas/self-assessment.schema.json`

**Requirements:**
- `check-jsonschema`: Install with `pip install check-jsonschema`

### Files
- `hooks/pre-commit` - The actual git hook script
- `install-precommit-hook.sh` - Installs the hook to your local `.git/hooks/`

### Troubleshooting
If you already have a pre-commit hook and want to replace it:
```bash
./install-precommit-hook.sh --force
```

To temporarily bypass validation (emergencies only):
```bash
git commit --no-verify -m "emergency commit"
```
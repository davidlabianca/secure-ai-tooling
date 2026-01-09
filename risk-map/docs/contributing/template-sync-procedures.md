# Template Synchronization Procedures

This document explains how GitHub issue templates stay synchronized with JSON schemas and YAML data files in the CoSAI Risk Map repository. It provides guidance for both contributors and maintainers on managing template updates.

## Table of Contents

1. [Overview](#overview)
2. [Schema Evolution Workflow](#schema-evolution-workflow)
3. [Manual Synchronization Procedures](#manual-synchronization-procedures)
4. [Two-Week Sync Lag](#two-week-sync-lag)
5. [Testing Strategies](#testing-strategies)
6. [Automation Roadmap](#automation-roadmap)
7. [Troubleshooting](#troubleshooting)

---

## Overview

### The Challenge

GitHub issue templates (`.github/ISSUE_TEMPLATE/*.yml`) contain dropdown menus and checkbox options that must match enums defined in JSON schemas (`risk-map/schemas/*.schema.json`) and data from YAML files (`risk-map/yaml/*.yaml`).

When schemas or YAML files change, templates may need updates to stay synchronized.

### Types of Changes

**Schema Changes Requiring Template Updates:**

- Adding/removing enum values (e.g., new control category, new risk ID)
- Adding/removing required fields
- Changing field descriptions or constraints
- Adding new cross-reference relationships

**Schema Changes NOT Requiring Template Updates:**

- Documentation updates in schema descriptions
- Constraint changes that don't affect dropdowns
- Internal validation rule changes

---

## Schema Evolution Workflow

### When Do Templates Need Updates?

Templates must be updated when:

#### 1. Enum Additions/Removals

**Affects:** Dropdown menus and checkbox options in templates

**Examples:**

- New control category added to `controls.schema.json`
- New risk ID added to `risks.schema.json`
- New component category added to `components.schema.json`
- New framework added to `frameworks.schema.json`

**Templates to Update:**

- **`new_control.yml`** - If control categories change
- **`new_risk.yml`** - If risk categories change
- **`new_component.yml`** - If component categories change
- Framework mappings in multiple templates if frameworks change

#### 2. Required Field Changes

**Affects:** Field validation (marked with \* in templates)

**Examples:**

- Previously optional field becomes required
- Required field becomes optional
- New required field added to schema

**Templates to Update:**

- Corresponding `new_*.yml` templates
- May affect validation blocks in templates

#### 3. Framework Applicability Changes (Future)

**Affects:** Which framework mapping fields appear in templates

**Note:** Currently framework applicability is manually configured. In the future (Phase 2 - optional enhancement), this could be schema-driven via an `applicableTo` field.

**Examples:**

- STRIDE becomes applicable to controls (currently only risks)
- New framework added that applies to multiple entity types

**Templates to Update:**

- All templates with framework mapping sections

---

## Manual Synchronization Procedures

### Current State

Templates are currently maintained manually. When schemas change, maintainers must manually update corresponding templates.

### Step-by-Step Manual Sync

#### Step 1: Identify Affected Templates

**For schema changes:**

```bash
# Example: controls.schema.json changed
# Affected templates: new_control.yml, update_control.yml
```

**Mapping:**

| Schema File                   | Affected Templates                          |
| ----------------------------- | ------------------------------------------- |
| `controls.schema.json`        | `new_control.yml`, `update_control.yml`     |
| `risks.schema.json`           | `new_risk.yml`, `update_risk.yml`           |
| `components.schema.json`      | `new_component.yml`, `update_component.yml` |
| `personas.schema.json`        | `new_persona.yml`, `update_persona.yml`     |
| `frameworks.schema.json`      | All templates with framework mappings       |
| `lifecycle-stage.schema.json` | Templates with lifecycle checkboxes         |
| `impact-type.schema.json`     | Templates with impact type checkboxes       |
| `actor-access.schema.json`    | Templates with actor access checkboxes      |

#### Step 2: Extract New Enum Values

**From JSON Schema:**

```json
// Example: controls.schema.json
{
  "category": {
    "enum": [
      "controlsData",
      "controlsInfrastructure",
      "controlsModel",
      "controlsApplication",
      "controlsAssurance",
      "controlsGovernance",
      "controlsSecurity" // <- NEW
    ]
  }
}
```

**From YAML Files (for human-readable labels):**

```yaml
# Example: Get category titles from controls.yaml
# Look at existing controls to find the label format
```

#### Step 3: Update Template YAML

**Edit `.github/ISSUE_TEMPLATE/new_control.yml`:**

```yaml
- type: dropdown
  id: control-category
  attributes:
    label: Control Category*
    description: Primary category this control belongs to
    options:
      - controlsData (Data Controls)
      - controlsInfrastructure (Infrastructure Controls)
      - controlsModel (Model Controls)
      - controlsApplication (Application Controls)
      - controlsAssurance (Assurance Controls)
      - controlsGovernance (Governance Controls)
      - controlsSecurity (Security Controls) # <- ADD THIS
  validations:
    required: true
```

**Important Notes:**

- Maintain alphabetical or logical ordering
- Use consistent label format: `enumValue (Human Label)`
- Never use YAML reserved words as bare values (`none`, `null`, `true`, `false`, `yes`, `no`, `on`, `off`)
- Preserve all other template sections unchanged

#### Step 4: Validate YAML Syntax

```bash
# Validate YAML syntax
python -c "import yaml; yaml.safe_load(open('.github/ISSUE_TEMPLATE/new_control.yml'))"

# Should return no errors
```

#### Step 5: Validate Against GitHub Schema

**Automated (Recommended):**

```bash
# Use the issue template validator (Phase 4)
python scripts/hooks/validate_issue_templates.py --force

# This automatically:
# - Validates all templates against GitHub schemas
# - Checks both issue forms and config.yml
# - Provides clear error messages
# - Runs in ~1 second
```

**Manual (Alternative):**

```bash
# Validate template against GitHub issue forms schema
check-jsonschema --builtin-schema vendor.github-issue-forms .github/ISSUE_TEMPLATE/new_control.yml

# Validate config.yml
check-jsonschema --builtin-schema vendor.github-issue-config .github/ISSUE_TEMPLATE/config.yml
```

**Common Validation Errors:**

- `Additional properties are not allowed` - Check for typos in field names
- `'validations' was unexpected` - `validations` not allowed on `checkboxes` type (only on `input`, `textarea`, `dropdown`)
- Invalid option values - Check for YAML reserved words

**Note:** Validation now runs automatically via pre-commit hook, so manual validation is typically unnecessary.

#### Step 6: Format with Prettier

```bash
# Format template
npx prettier --write .github/ISSUE_TEMPLATE/*.yml

# Verify formatting
npx prettier --check .github/ISSUE_TEMPLATE/*.yml
```

#### Step 7: Test Template Rendering

**Manual Test:**

1. Create a test issue using the updated template
2. Verify dropdown/checkbox options appear correctly
3. Verify required field validation works
4. Verify reference links work
5. Cancel the test issue (don't submit)

**Automated Test (Future):**

Currently no automated rendering tests. This is a potential future enhancement.

#### Step 8: Commit Changes Together

```bash
# Commit schema and template changes together
git add risk-map/schemas/controls.schema.json
git add .github/ISSUE_TEMPLATE/new_control.yml
git commit -m "Add controlsSecurity category to schema and templates"
```

**Best Practice:** Always commit schema changes and template changes in the same commit/PR to maintain consistency.

---

## Two-Week Sync Lag

### The Governance Process

The CoSAI Risk Map uses a two-stage governance process:

1. **Technical Review** (develop branch)
   - Schema changes reviewed by technical maintainers
   - Merged to `develop` branch after approval
   - Available for development and testing

2. **Community Review** (main branch)
   - ~2 weeks after `develop` merge
   - Community review period
   - Merged to `main` branch after approval

### Impact on Templates

**Problem:** GitHub issue templates are served from the `main` branch.

**Result:** Template dropdown options lag behind `develop` by up to 2 weeks.

**Timeline Example:**

```
Day 0:  New enum added to controls.schema.json
Day 0:  Schema + template changes merge to develop
Day 0-14: develop branch has updated template
Day 14: develop merges to main
Day 14+: main branch has updated template (available to users)
```

### User Impact

**For Contributors:**

If you're proposing an entity using a newly added enum:

- **Option 1:** Wait ~2 weeks for `develop` → `main` merge
- **Option 2:** Use free-form text fields (most templates have both dropdowns and textareas)
- **Option 3:** Note in "Additional Context" that you're using an enum from `develop`

**Example:**

```yaml
# New category not in dropdown yet
Control Category: [Choose from dropdown or specify below]
Additional Context:
"Using new controlsSecurity category from develop branch (commit abc123)"
```

Maintainers understand this limitation and will accommodate valid proposals.

**For Maintainers:**

- Clearly communicate sync lag to contributors
- Accept proposals using valid-but-not-yet-in-dropdown values
- Prioritize template updates when merging significant schema changes

### Mitigation Strategies

**Current:**

- Documentation explains the lag (this document + issue-templates-guide.md)
- Templates provide free-form alternatives to dropdowns
- Maintainers accommodate early adopters

**Current Automation:**

- ✅ Template generator (Phase 3) available: `python scripts/generate_issue_templates.py`
- ✅ Pre-commit hooks validate templates on every commit (Phase 4)
- ✅ GitHub Actions validates template synchronization on PRs (Phase 4)
- ✅ Drift detection warns if templates need regeneration (Phase 4)

---

## Testing Strategies

### Pre-Deployment Testing

**Before merging template changes:**

1. **YAML Syntax Validation**

   ```bash
   python -c "import yaml; yaml.safe_load(open('template.yml'))"
   ```

2. **GitHub Schema Validation**

   ```bash
   check-jsonschema --builtin-schema vendor.github-issue-forms template.yml
   ```

3. **Prettier Formatting**

   ```bash
   npx prettier --check template.yml
   ```

4. **Manual Rendering Test**
   - Create draft issue using updated template
   - Verify all fields render correctly
   - Test dropdowns, checkboxes, required field validation
   - Cancel draft

### Post-Deployment Validation

**After template changes merge to main:**

1. **Verify Template Availability**
   - Navigate to repository Issues tab
   - Click "New Issue"
   - Verify updated template appears

2. **Smoke Test**
   - Create test issue using template
   - Verify new dropdown options appear
   - Verify validation works
   - Close test issue

3. **Monitor for Issues**
   - Watch for user reports of template problems
   - Check issue submissions for validation errors

### Regression Testing

**Ensure existing functionality still works:**

1. All existing dropdown options still present
2. Required field validation unchanged (unless intentional)
3. Reference documentation links still work
4. Bidirectionality messaging present
5. Submission checklists intact

### Schema Compatibility Testing

**Test with actual schema files:**

```bash
# Validate that template options match schema enums
python scripts/validate_template_schema_sync.py  # (future tool)
```

---

## Automation Roadmap

The manual synchronization procedures described above will be automated in future phases.

### Phase 2: Framework Schema Enhancement

**Timeline:** Week 3 (per unified plan)

**Goal:** Add `applicableTo` field to frameworks schema

**Impact on Templates:**

- Eliminates hardcoded framework filtering
- Templates will dynamically show only applicable frameworks
- Reduces maintenance burden

**Changes:**

- `frameworks.schema.json` - Add `applicableTo` array field
- `frameworks.yaml` - Add `applicableTo` to all frameworks
- Validation scripts - Check framework applicability

### Phase 3: Template Generator Implementation

**Timeline:** Weeks 4-6 (per unified plan)

**Goal:** Create `IssueTemplateGenerator` class and CLI

**Components:**

1. **Schema Parser** - Extract enums from JSON schemas
2. **Template Renderer** - Expand placeholders in template sources
3. **Generator** - Orchestrate template generation
4. **CLI** - Manual generation script

**Usage:**

```bash
# Generate all templates
python scripts/generate_issue_templates.py

# Dry-run (show diffs without modifying)
python scripts/generate_issue_templates.py --dry-run

# Generate specific template
python scripts/generate_issue_templates.py --template new_control

# Validate synchronization
python scripts/generate_issue_templates.py --validate
```

**Benefits:**

- Automatic extraction of enums from schemas
- Framework applicability read from YAML (no hardcoding)
- Consistent template generation
- Eliminates manual sync errors

### Phase 4: Validation Automation ✅ COMPLETED

**Status:** COMPLETE (January 2026)

**Goal:** Pre-commit hooks and GitHub Actions for automatic validation

**What Was Implemented:**

#### 4.1 Issue Template Validator

**File:** `scripts/hooks/validate_issue_templates.py` (278 lines)

A comprehensive validator that uses `check-jsonschema` with GitHub's built-in schemas:

```bash
# Validate all templates (manual use)
python scripts/hooks/validate_issue_templates.py --force

# Validate staged templates only (pre-commit)
python scripts/hooks/validate_issue_templates.py

# Quiet mode (errors only)
python scripts/hooks/validate_issue_templates.py --force --quiet
```

**Features:**
- Validates issue forms against `vendor.github-issue-forms` schema
- Validates config.yml against `vendor.github-issue-config` schema
- Git integration to detect staged files
- Proper exit codes: 0 (success), 1 (validation failed), 2 (errors)
- User-friendly output with emojis (✅/❌)
- Comprehensive error handling

**Validation Results:**
```
✅ All 10 issue templates pass GitHub schema validation
   - new_component.yml
   - update_component.yml
   - new_control.yml
   - update_control.yml
   - new_risk.yml
   - update_risk.yml
   - new_persona.yml
   - update_persona.yml
   - infrastructure.yml
   - config.yml
```

#### 4.2 Pre-Commit Hook Integration

**File:** `scripts/hooks/pre-commit` (updated)

The validator is integrated into the pre-commit workflow:

```bash
# Runs automatically on git commit
# - Validates staged template files
# - Blocks commit if validation fails
# - Provides clear error messages
```

**Integration:**
- Uses `run_validator` utility from Phase 3.5 refactoring
- Runs alongside other validators (component edges, control-risk refs, etc.)
- Execution time: ~1s for template validation
- Included in help message and summary output

#### 4.3 GitHub Actions Workflow

**File:** `.github/workflows/validate-issue-templates.yml`

A production-ready CI/CD workflow with 4 jobs:

**Job 1: Setup Environment**
- Installs Python 3.11
- Installs requirements-dev.txt
- Installs check-jsonschema
- Caches dependencies for performance

**Job 2: GitHub Schema Validation**
- Validates all 10 templates against GitHub schemas
- Runs on every push/PR affecting templates or schemas
- Execution time: ~1.1s

**Job 3: Template Drift Detection** (PR only)
- Detects if schemas changed but templates weren't regenerated
- Runs generator in dry-run mode
- Checks for uncommitted template changes
- Provides remediation steps if drift detected

**Job 4: Template Tool Tests**
- Runs comprehensive test suite (65 tests)
- Validates all functionality
- Execution time: ~1.5s
- Generates JUnit XML reports

**Job 5: Validation Summary**
- Aggregates results from all jobs
- Posts summary to GitHub PR
- Clear pass/fail indicators
- Links to failing jobs

**Triggers:**
- Pull requests modifying:
  - `.github/ISSUE_TEMPLATE/**`
  - `risk-map/schemas/**`
  - Template generation/validation scripts
- Pushes to main/develop modifying templates or schemas

**Performance:**
- Total workflow time: ~5-6 seconds
- Parallel job execution
- Efficient caching strategy

#### 4.4 Comprehensive Test Suite

**File:** `scripts/hooks/tests/test_validate_issue_templates.py` (1,335 lines)

**Test Coverage:** 65/65 tests passing (100%)

- TestCommandLineArgs: 14 tests - CLI argument parsing
- TestGitHubSchemaValidation: 8 tests - Schema validation logic
- TestFileDetection: 7 tests - Template file discovery
- TestStagedFileDetection: 6 tests - Git staged file detection
- TestOutputMessaging: 6 tests - Console output formatting
- TestExitCodes: 5 tests - Exit code behavior
- TestCheckJsonSchemaIntegration: 7 tests - Subprocess integration
- TestEdgeCases: 7 tests - Edge case handling
- TestIntegrationWithRealFiles: 5 tests - Real template validation

**Execution Time:** 1.50s

**CI Validation:** All tests pass in GitHub Actions environment (verified with `act`)

#### 4.5 Usage Examples

**For Contributors:**

```bash
# Before committing template changes
python scripts/hooks/validate_issue_templates.py --force

# Should output:
# ✅ All issue templates passed validation
```

**For Maintainers:**

```bash
# Pre-commit hook runs automatically
git add .github/ISSUE_TEMPLATE/new_component.yml
git commit -m "Update new_component template"
# → Validation runs automatically
# → Commit succeeds if validation passes
# → Commit blocked if validation fails

# GitHub Actions runs automatically on PR
# - Validates all templates
# - Detects template drift
# - Runs test suite
# - Posts summary to PR
```

**Benefits Achieved:**

✅ Zero drift between schemas and templates (drift detection prevents merge)
✅ Automatic validation on every commit (pre-commit hook)
✅ Automatic validation on every PR (GitHub Actions)
✅ Clear remediation guidance (error messages + workflow comments)
✅ Fast execution (<2s pre-commit, <6s GitHub Actions)
✅ Comprehensive test coverage (65/65 tests)
✅ Production-ready and battle-tested

### Phase 5: Auto-Regeneration (Future)

**Timeline:** Post-MVP (deferred)

**Goal:** Fully automated template regeneration with PR creation

**Workflow:**

1. Schema changes merge to `develop`
2. Workflow auto-regenerates templates
3. Creates PR for template updates
4. Maintainer reviews and approves
5. Templates merge to `main`

**Deferred Because:**

- Manual review preferred initially for quality assurance
- Phases 3-4 provide sufficient automation for MVP
- Additional infrastructure required for auto-PR creation

---

## Troubleshooting

### Common Drift Scenarios

#### Scenario 1: New Enum Added to Schema, Template Not Updated

**Symptoms:**

- User reports dropdown missing option
- New entity proposals reference invalid values

**Detection:**

```bash
# Compare schema enums to template options
# (manual comparison currently, automated in future)
```

**Resolution:**

1. Extract new enum from schema
2. Add to template dropdown options
3. Validate YAML syntax and GitHub schema
4. Format with prettier
5. Commit and deploy

#### Scenario 2: Template Has Outdated Options

**Symptoms:**

- Template shows enum that was removed from schema
- Schema validation fails for old proposals

**Detection:**

```bash
# Review schema changelog
# Compare template options to current schema
```

**Resolution:**

1. Remove outdated option from template
2. Check if any open issues use the removed option
3. Update or close affected issues
4. Commit template update

#### Scenario 3: Template Validation Fails

**Symptoms:**

```
Additional properties are not allowed ('validations' was unexpected)
```

**Cause:** `validations` block added to unsupported field type (e.g., `checkboxes`)

**Resolution:**

```yaml
# ❌ Wrong - validations not allowed on checkboxes
- type: checkboxes
  id: personas
  attributes:
    label: Applicable Personas*
    options:
      - label: Model Creator
  validations:
    required: true # <- NOT ALLOWED

# ✅ Correct - required on individual checkbox options
- type: checkboxes
  id: personas
  attributes:
    label: Applicable Personas*
    options:
      - label: Model Creator
        required: true # <- ALLOWED
```

#### Scenario 4: Reference Links Broken

**Symptoms:**

- Template links to `../../risk-map/tables/components-summary.md` return 404

**Causes:**

- Table file renamed/moved/deleted
- Relative path incorrect

**Detection:**

```bash
# Check if linked file exists
ls risk-map/tables/components-summary.md
```

**Resolution:**

1. Locate current table file location
2. Update relative path in template
3. Test link in GitHub UI
4. Commit fix

#### Scenario 5: Framework Mapping Mismatch

**Symptoms:**

- Template shows STRIDE for controls (should be risks only)
- Template shows NIST AI RMF for risks (should be controls only)

**Cause:** Incorrect framework applicability configuration

**Current Resolution:**

1. Review framework applicability table in issue-templates-guide.md
2. Remove inappropriate framework fields from template
3. Commit fix

**Future Resolution (if Phase 2 is implemented):**

- Generator would read `applicableTo` from frameworks.yaml
- Automatic filtering would eliminate manual configuration
- Currently deferred - manual configuration works well

---

## Maintainer Checklist

When reviewing PRs with schema changes:

- [ ] Identify which templates are affected
- [ ] Verify template updates included in same PR
- [ ] Check YAML syntax validation passes
- [ ] Check GitHub schema validation passes
- [ ] Check prettier formatting passes
- [ ] Verify enum values match schema exactly
- [ ] Verify required field changes reflected
- [ ] Verify reference links still work
- [ ] Verify bidirectionality messaging preserved
- [ ] Test template rendering in GitHub UI (if major change)

---

## Related Documentation

- [Issue Templates Guide](./issue-templates-guide.md) - User-facing guide for all templates
- [Contributing Guide](../../../../CONTRIBUTING.md) - Overall contribution workflow
- [Development Guide](../developing.md) - Development setup and procedures
- [Schema Documentation](../../schemas/) - JSON schema definitions (future)

---

## Questions?

If you encounter template synchronization issues not covered in this document:

1. Check existing issues for similar problems
2. Review the automation roadmap (Phases 2-4) to see if a solution is planned
3. Open an issue with the `infrastructure` label
4. Tag maintainers for assistance

For questions about the automation implementation, see the [unified implementation plan](../../../../plans/plan.md) (if accessible to contributors).

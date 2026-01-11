# GitHub Issue Templates Guide

This guide explains how to use the GitHub issue templates available in the CoSAI Risk Map repository. These templates streamline the process of proposing new content or updating existing content in the AI security framework.

## Table of Contents

1. [Overview](#overview)
2. [Control Templates](#control-templates)
3. [Risk Templates](#risk-templates)
4. [Component Templates](#component-templates)
5. [Persona Templates](#persona-templates)
6. [Infrastructure Template](#infrastructure-template)
7. [Key Concepts](#key-concepts)
8. [Common Pitfalls](#common-pitfalls)

---

## Overview

### Why Use Issue Templates?

GitHub issue templates provide structured forms that:

- **Capture required information** - Ensure all necessary details are provided upfront
- **Reduce back-and-forth** - Minimize clarification cycles with maintainers
- **Maintain consistency** - Standardize how content is proposed across the project
- **Enable automation** - Allow automatic labeling and validation

### Available Templates

The repository provides 9 issue templates organized into 5 categories:

| Category       | New Entity Template  | Update Entity Template   |
| -------------- | -------------------- | ------------------------ |
| **Controls**   | `new_control.yml`    | `update_control.yml`     |
| **Risks**      | `new_risk.yml`       | `update_risk.yml`        |
| **Components** | `new_component.yml`  | `update_component.yml`   |
| **Personas**   | `new_persona.yml`    | `update_persona.yml`     |
| **Other**      | `infrastructure.yml` | (framework enhancements) |

### Template Design Philosophy

- **New templates**: Comprehensive fields for creating entirely new entities
- **Update templates**: KISS (Keep It Simple, Stupid) approach with GitHub permalinks and free-form descriptions
- **Automatic bidirectionality**: The system automatically creates reverse mappings (you don't need to update both sides manually)

---

## Control Templates

### New Control Template

**When to use:** Proposing a brand new security control that doesn't exist in the framework.

**File:** `.github/ISSUE_TEMPLATE/new_control.yml`

**Required Fields (5):**

1. **Control Title** - Concise, descriptive name (e.g., "Privacy Enhancing Technologies")
2. **Control Description** - Detailed explanation of purpose, implementation, and expected outcomes
3. **Control Category** - Primary category from: Data, Infrastructure, Model, Application, Assurance, Governance
4. **Applicable Personas** - Which personas implement this (Model Creator, Model Consumer)
5. **Applicable Components** - Component IDs this control applies to (one per line) or "all"/"none"
6. **Mitigated Risks** - Risk IDs this control addresses (one per line) or "all"

**Optional Fields:**

- Framework mappings (dynamically shown based on entity type)
- Lifecycle stages
- Impact types
- Actor access levels
- Additional context

**Example Walkthrough:**

```yaml
Control Title: Model Input Validation
Control Description: Implement validation checks on all inputs to AI models to detect and reject malicious or malformed data before processing.
Control Category: controlsModel (Model Controls)
Applicable Personas:
  ☑ Model Creator
  ☑ Model Consumer
Applicable Components:
componentInputHandling
componentModelServing
Mitigated Risks:
PIJ
SSRF
```

**Reference Links:**

The template includes inline links to:

- [Component list](../../risk-map/tables/components-summary.md) - Browse valid component IDs
- [Risk list](../../risk-map/tables/risks-summary.md) - Browse valid risk IDs

**Automatic Cross-Mapping:**

✨ When you map this control to risks (e.g., PIJ, SSRF), the reverse mappings are automatically created. Each risk you list will automatically get this control added to its applicable controls. You don't need to create a separate issue to update the risks.

---

### Update Control Template

**When to use:** Modifying an existing control (description changes, adding/removing mappings, updating metadata).

**File:** `.github/ISSUE_TEMPLATE/update_control.yml`

**Required Fields (3):**

1. **Control Permalink** - GitHub permalink to the control in `controls.yaml` (right-click line number → Copy permalink)
2. **Change Type** - What you're changing (description, mappings, category, metadata, other)
3. **Proposed Changes** - Free-form description of what to change and why

**Optional Quick Actions:**

- **Component Changes** - Use `+` to add, `-` to remove (e.g., `+ componentModelEvaluation`, `- componentDataSources`)
- **Risk Changes** - Same syntax (e.g., `+ MST`, `- PIJ`)
- **Framework Changes** - Same syntax (e.g., `+ mitre-atlas: AML.M0015`, `- nist-ai-rmf: GV-6.2`)
- **Supporting Evidence** - Links to discussions, standards, references

**Example Walkthrough:**

```
Control Permalink: https://github.com/cosai-oasis/secure-ai-tooling/blob/abc123/risk-map/yaml/controls.yaml#L45-L52

Change Type: Add mappings (components, risks, frameworks)

Proposed Changes:
Current state: Control only applies to training phase
Proposed change: Add componentModelEvaluation to components list
Rationale: This control is equally relevant during the evaluation phase when assessing model behavior

Component Changes:
+ componentModelEvaluation

Framework Changes:
+ mitre-atlas: AML.M0015
```

**GitHub Permalink Best Practices:**

1. Navigate to `risk-map/yaml/controls.yaml` in GitHub
2. Find the control you want to update
3. Click the line number(s) to highlight
4. Right-click → "Copy permalink" (includes commit hash, file path, and line numbers)
5. Paste into the template

This provides exact context for maintainers to see what you're changing.

**Automatic Cross-Mapping:**

✨ Risk and component mappings are automatically bidirectional. When you add/remove mappings here, the reverse updates happen automatically.

---

## Risk Templates

### New Risk Template

**When to use:** Proposing a brand new AI security risk that doesn't exist in the framework.

**File:** `.github/ISSUE_TEMPLATE/new_risk.yml`

**Required Fields (7):**

1. **Risk ID** - Short identifier (2-4 uppercase letters, e.g., PIJ, DP, MST)
2. **Risk Title** - Human-readable name
3. **Short Description** - One-sentence summary
4. **Long Description** - Detailed explanation of the risk
5. **Risk Category** - Category from schema (e.g., Integrity, Confidentiality, Availability)
6. **Applicable Personas** - Which personas face this risk
7. **Applicable Controls** - Control IDs that mitigate this risk (one per line) or "all"

**Optional Fields:**

- Examples (real-world scenarios)
- Relevant questions (for risk assessment)
- Framework mappings (MITRE ATLAS, STRIDE, OWASP Top 10 for LLM)
- Lifecycle stages
- Impact types
- Actor access levels

**Example Walkthrough:**

```yaml
Risk ID: MBTD
Risk Title: Model Backdoor Trojan Deployment
Short Description: Adversary embeds hidden functionality in model that activates on specific triggers
Long Description: An attacker inserts malicious logic into the AI model during training or fine-tuning that remains dormant until triggered by specific inputs, allowing unauthorized actions or data exfiltration.

Risk Category: Integrity
Applicable Personas:
  ☑ Model Creator
  ☑ Model Consumer
Applicable Controls:
controlModelValidation
controlSupplyChainSecurity
controlAdversarialTesting

Examples:
- Backdoor triggered by specific pixel patterns in images
- Hidden functionality activated by rare token sequences

Framework Mappings:
MITRE ATLAS: AML.T0018
STRIDE: Tampering
```

**Reference Links:**

- [Controls list](../../risk-map/tables/controls-summary.md) - Browse valid control IDs

**Automatic Cross-Mapping:**

✨ When you map this risk to controls, the reverse mappings are automatically created. Each control you list will automatically get this risk added to its mitigated risks.

---

### Update Risk Template

**When to use:** Modifying an existing risk (descriptions, examples, mappings, assessment questions).

**File:** `.github/ISSUE_TEMPLATE/update_risk.yml`

**Required Fields (3):**

1. **Risk Permalink** - GitHub permalink to the risk in `risks.yaml`
2. **Change Type** - What you're changing (description, examples, mappings, etc.)
3. **Proposed Changes** - Free-form description

**Optional Quick Actions:**

- **Control Changes** - `+`/`-` syntax
- **Framework Changes** - `+`/`-` syntax
- **Examples Updates** - Add/modify real-world scenarios
- **Assessment Questions** - Add/modify relevant questions
- **Tour Content** - Updates for interactive risk tour
- **Supporting Evidence** - Research, CVEs, standards

**Example Walkthrough:**

```
Risk Permalink: https://github.com/cosai-oasis/secure-ai-tooling/blob/def456/risk-map/yaml/risks.yaml#L123-L145

Change Type: Add examples and framework mappings

Proposed Changes:
Add recent real-world example of this attack and map to OWASP Top 10 for LLM

Examples to Add:
- "Research paper documenting backdoor attack on image classifier (https://arxiv.org/...)"

Framework Changes:
+ owasp-top10-llm: LLM03

Supporting Evidence:
- CVE-2024-XXXXX: Backdoor discovered in production model
- NIST guidance: https://nvlpubs.nist.gov/...
```

**Automatic Cross-Mapping:**

✨ Control mappings are automatically bidirectional. Updates propagate to connected controls.

---

## Component Templates

### New Component Template

**When to use:** Proposing a new AI system component that isn't in the framework.

**File:** `.github/ISSUE_TEMPLATE/new_component.yml`

**Required Fields (5):**

1. **Component ID** - camelCase identifier starting with "component" (e.g., `componentFeatureStore`)
2. **Component Title** - Human-readable name
3. **Component Description** - What this component does and why it's important
4. **Component Category** - Data, Infrastructure, Model, or Application
5. **Edges** - Relationships to other components

**Edge Relationships:**

- **Edges To (Downstream)** - Components this component sends data/models to
- **Edges From (Upstream)** - Components this component receives data/models from

**Example Walkthrough:**

```yaml
Component ID: componentFeatureStore
Component Title: Feature Store
Component Description: Centralized repository for storing, managing, and serving features for ML training and inference.
Component Category: Data

Edges To (downstream):
componentModelTraining
componentModelServing

Edges From (upstream):
componentDataSources
componentDataProcessing
```

**Reference Links:**

- [Components summary](../../risk-map/tables/components-summary.md) - Browse existing components

**Automatic Bidirectionality:**

✨ When you specify edges, the reverse edges are automatically created. If you say `componentFeatureStore` → `componentModelTraining`, the system automatically creates `componentModelTraining` ← `componentFeatureStore`. You don't need to update both components.

---

### Update Component Template

**When to use:** Modifying an existing component (description, category, edges).

**File:** `.github/ISSUE_TEMPLATE/update_component.yml`

**Required Fields (3):**

1. **Component Permalink** - GitHub permalink to component in `components.yaml`
2. **Change Type** - What you're changing
3. **Proposed Changes** - Free-form description

**Optional Quick Actions:**

- **Edges To Changes** - `+`/`-` syntax (e.g., `+ componentNewDestination`, `- componentOldDestination`)
- **Edges From Changes** - `+`/`-` syntax
- **Related Components** - Other components affected by edge changes
- **Supporting Evidence** - Architecture diagrams, discussions

**Example Walkthrough:**

```
Component Permalink: https://github.com/cosai-oasis/secure-ai-tooling/blob/ghi789/risk-map/yaml/components.yaml#L67-L74

Change Type: Update edges (add connections)

Proposed Changes:
Add edge to new componentFeatureStore since model training now pulls features from centralized store

Edges From Changes:
+ componentFeatureStore

Related Components:
- componentFeatureStore (new upstream dependency)

Supporting Evidence:
- Architecture diagram: https://example.com/diagram.png
```

**Automatic Bidirectionality:**

✨ Edge changes automatically update connected components. When you add an edge from ComponentA to ComponentB, the reverse edge is created automatically.

---

## Persona Templates

### New Persona Template

**When to use:** Proposing a new persona (user role) for the framework.

**File:** `.github/ISSUE_TEMPLATE/new_persona.yml`

**Important Note:** Personas are rarely added. The framework currently has 2 personas (Model Creator, Model Consumer) that cover most use cases. Before proposing a new persona, carefully justify why existing personas don't suffice.

**Required Fields (4):**

1. **Persona ID** - camelCase starting with "persona" (e.g., `personaModelAuditor`)
2. **Persona Title** - Human-readable name
3. **Persona Description** - Who this persona is and their responsibilities
4. **Justification** - Why existing personas don't cover this use case

**Additional Fields:**

- Use cases and examples
- Relationship to existing personas
- Framework impact assessment (how many controls/risks affected)
- Control responsibilities
- Risk exposure

**Example Walkthrough:**

```yaml
Persona ID: personaModelAuditor
Persona Title: Model Auditor
Persona Description: External third-party auditor responsible for independent assessment and certification of AI systems for compliance and security.

Justification:
Existing personas (Model Creator, Model Consumer) don't cover external auditors who:
  - Don't create or deploy models
  - Need read-only access to inspect training data, model artifacts, and logs
  - Assess compliance against regulatory frameworks
  - Issue certification reports

Use Cases:
  - Third-party AI system certification
  - Regulatory compliance audits
  - Independent security assessments

Framework Impact:
  - ~15 controls would apply to this persona
  - ~8 risks would be relevant to auditors
```

**No Bidirectionality:**

Personas don't have bidirectional relationships, so there's no automatic cross-mapping.

---

### Update Persona Template

**When to use:** Clarifying or refining an existing persona (typically description updates).

**File:** `.github/ISSUE_TEMPLATE/update_persona.yml`

**Required Fields (3):**

1. **Persona Permalink** - GitHub permalink to persona in `personas.yaml`
2. **Change Type** - What you're changing
3. **Proposed Changes** - Free-form description

**Additional Fields:**

- Framework impact assessment
- Scope clarification (included/excluded roles)
- Supporting evidence (industry standards, role definitions)

**Example Walkthrough:**

```
Persona Permalink: https://github.com/cosai-oasis/secure-ai-tooling/blob/jkl012/risk-map/yaml/personas.yaml#L12-L18

Change Type: Clarify scope and responsibilities

Proposed Changes:
Clarify that Model Consumer also includes organizations that fine-tune foundation models, not just those deploying off-the-shelf models.

Scope Clarification:
Included roles:
- Organizations deploying pre-trained models
- Organizations fine-tuning foundation models
- SaaS providers integrating AI capabilities

Excluded roles:
- End users of AI applications (not responsible for model deployment)

Supporting Evidence:
- NIST AI RMF guidance on consumer responsibilities
- MLOps maturity model: https://...
```

---

## Infrastructure Template

### Infrastructure Template

**When to use:** Proposing infrastructure improvements, framework enhancements, schema changes, automation, tooling, or documentation updates.

**File:** `.github/ISSUE_TEMPLATE/infrastructure.yml`

**Design Philosophy:** Maximum flexibility for diverse enhancement types with structured guidance.

**Key Fields:**

1. **Enhancement Category** - Schema, Automation, Tooling, Documentation, Validation, CI/CD, Testing, Other
2. **Scope** - Small, Medium, Large, Epic
3. **Rationale & Justification** - Why this enhancement is needed
4. **Implementation Approach** - How to implement (supports phased rollouts)
5. **Task List** - Markdown checkboxes for subtask tracking
6. **Breaking Changes** - Impact assessment
7. **Migration Plan** - If breaking changes required
8. **Dependencies & Prerequisites** - Blockers or requirements
9. **Testing & Validation Strategy**
10. **Related Issues** - Parent/child/sibling issue linking

**Use Cases:**

- Schema changes and framework architecture updates
- Automation/CI/CD improvements
- Tooling enhancements (validation scripts, generators, hooks)
- Documentation infrastructure
- Multi-phase enhancements requiring sub-issues

**Sub-Issue Pattern:**

For large enhancements (epics), the infrastructure issue serves as the parent:

```yaml
Task List:
- [ ] Step 1: Initial implementation
- [ ] Step 2: Testing and validation
- [ ] Sub-issue: #123 - Component A implementation
- [ ] Sub-issue: #124 - Component B implementation

Related Issues:
Parent issue: #100
Sub-issues:
- #123 - Component A
- #124 - Component B
```

**Example Walkthrough:**

```yaml
Enhancement Category: Automation
Scope: Medium

Rationale & Justification:
Add pre-commit hook to automatically validate YAML files against schemas before commits. This prevents invalid YAML from being committed and reduces maintainer review burden.

Implementation Approach:
1. Create validation script that runs check-jsonschema
2. Integrate script into pre-commit hook
3. Add GitHub Actions workflow for CI validation
4. Document usage in contributing guide

Task List:
- [ ] Create validation script
- [ ] Update pre-commit hook
- [ ] Add GitHub Actions workflow
- [ ] Update documentation
- [ ] Test with sample commits

Breaking Changes: No
- Pre-commit validation is optional (can be bypassed with --no-verify)
- Existing commits remain valid

Testing & Validation Strategy:
- Validation script correctly identifies invalid YAML
- Pre-commit hook blocks invalid commits
- GitHub Actions detects issues in PRs
- Documentation includes troubleshooting guidance
```

---

## Key Concepts

### Automatic Bidirectionality

The CoSAI Risk Map framework maintains bidirectional relationships automatically. You don't need to update both sides of a relationship manually.

**Component Edges:**

- ✨ When you specify `componentA` → `componentB`, the system creates `componentB` ← `componentA`
- Update templates handle reverse edges automatically
- Validation ensures consistency

**Control ↔ Risk Cross-Mapping:**

- ✨ When you map a control to risks, those risks automatically get the control added
- ✨ When you map a risk to controls, those controls automatically get the risk added
- No need to create separate issues for both sides

**Benefits:**

- Reduces user burden (no manual cross-referencing)
- Prevents errors from missing reverse mappings
- Maintains consistency across the framework

### GitHub Permalinks

Update templates require GitHub permalinks instead of entity IDs. This provides:

**Traceability:**

- Exact commit hash (historical context)
- Line numbers (precise location)
- File path (no ambiguity)

**How to Create:**

1. Navigate to the YAML file in GitHub (e.g., `controls.yaml`)
2. Click the line number(s) to highlight
3. Right-click → "Copy permalink"
4. Paste into the template

**Example:**
`https://github.com/cosai-oasis/secure-ai-tooling/blob/abc123def456/risk-map/yaml/controls.yaml#L45-L52`

### Git Diff Syntax

Update templates support quick actions using familiar git diff syntax:

**Add:** Prefix with `+`

```
+ componentNewItem
+ mitre-atlas: AML.M0015
```

**Remove:** Prefix with `-`

```
- componentOldItem
- nist-ai-rmf: GV-6.2
```

**Benefits:**

- Familiar to developers
- Concise notation
- Easy to parse programmatically

### Framework Applicability

Different entity types map to different external frameworks:

| Framework        | Controls | Risks | Components | Personas |
| ---------------- | -------- | ----- | ---------- | -------- |
| MITRE ATLAS      | ✅       | ✅    | ❌         | ❌       |
| NIST AI RMF      | ✅       | ❌    | ❌         | ❌       |
| STRIDE           | ❌       | ✅    | ❌         | ❌       |
| OWASP Top 10 LLM | ✅       | ✅    | ❌         | ❌       |

**Controls** use MITRE ATLAS mitigations (AML.M\*), NIST AI RMF subcategories, and OWASP Top 10 for LLM.

**Risks** use MITRE ATLAS techniques (AML.T\*), STRIDE threat categories, and OWASP Top 10 for LLM.

**Components and Personas** currently have no framework mappings in practice.

Templates automatically show only applicable frameworks for each entity type based on dynamic configuration.

### Schema Evolution and Two-Week Lag

**Important:** Template dropdown options may lag behind the `develop` branch by up to 2 weeks.

**Why the Lag:**

The CoSAI Risk Map uses a two-stage governance process:

1. **Technical Review:** Changes merge to `develop` branch
2. **Community Review:** After ~2 weeks, `develop` merges to `main`

GitHub issue templates are served from the `main` branch, so new enums added to schemas in `develop` won't appear in template dropdowns until merged to `main`.

**What This Means for You:**

- If you're proposing a new entity using a recently added category/enum that's only in `develop`, it may not appear in the dropdown yet
- **Workaround:** Use the free-form text fields (most templates have both dropdowns and text areas)
- **Alternative:** Wait ~2 weeks for `develop` → `main` merge
- Maintainers understand this limitation and will accommodate proposals using valid-but-not-yet-in-dropdown values

**Example:**

```
# New control category added to develop branch but not in dropdown yet
Control Category: controlsSecurity  # Not in dropdown yet
# → Use Additional Context field to note: "Using new controlsSecurity category from develop branch"
```

---

## Common Pitfalls

### 1. Not Using Reference Links

**Problem:** Submitting invalid component IDs, risk IDs, or framework mappings.

**Solution:** Click the reference documentation links in templates:

- [Components summary](../../risk-map/tables/components-summary.md)
- [Risks summary](../../risk-map/tables/risks-summary.md)
- [Controls summary](../../risk-map/tables/controls-summary.md)

These tables show all valid IDs.

### 2. Manual Bidirectional Updates

**Problem:** Creating separate issues to update both sides of a relationship (e.g., issue to add control→risk mapping, then another issue to add risk→control mapping).

**Solution:** Only update one side. The system handles bidirectionality automatically. Read the ✨ Automatic Cross-Mapping messages in templates.

### 3. Incorrect Permalink Format

**Problem:** Linking to the latest version instead of a permalink with commit hash.

**Solution:** Use "Copy permalink" (not "Copy link"). Permalinks include commit hashes and are immutable.

❌ Wrong: `https://github.com/org/repo/blob/main/file.yaml#L10`
✅ Correct: `https://github.com/org/repo/blob/abc123def456/file.yaml#L10`

### 4. Using Reserved YAML Words

**Problem:** Proposal uses reserved YAML words (`none`, `null`, `true`, `false`, `yes`, `no`, `on`, `off`) as bare values.

**Solution:** Use descriptive alternatives or quote the value. Example: Use "N/A - No subcategory" instead of bare "None".

### 5. Incomplete New Entity Proposals

**Problem:** Missing required fields, especially references to related entities (components, risks, controls).

**Solution:** Check the template for asterisks (\*) marking required fields. Use reference links to find valid related entities.

### 6. Update Without Justification

**Problem:** Update template submissions without explaining _why_ the change is needed.

**Solution:** Always provide rationale in the "Proposed Changes" field. Explain the current state, proposed change, and why it improves the framework.

### 7. Wrong Framework for Entity Type

**Problem:** Trying to map STRIDE to a control, or NIST AI RMF to a risk.

**Solution:** Review the Framework Applicability table in [Key Concepts](#framework-applicability). Templates only show applicable frameworks.

---

## Getting Help

If you're unsure which template to use or how to fill it out:

1. **Review existing issues:** Look for similar proposals in closed issues
2. **Check documentation:**
   - [Main contribution guide](../../CONTRIBUTING.md)
   - [Development workflow](../workflow.md)
   - [Entity-specific guides](../) (guide-controls.md, guide-risks.md, etc.)
3. **Ask questions:** Open a discussion or draft issue to get feedback before formal submission

---

## Next Steps

After reading this guide:

1. Choose the appropriate template for your proposal
2. Gather necessary information (entity details, related IDs, references)
3. Fill out required fields carefully
4. Review submission checklist at the bottom of each template
5. Submit the issue

Maintainers will review your proposal, potentially ask clarifying questions, and work with you to integrate approved changes into the framework.

For more information on the overall contribution workflow and branching strategy, see [CONTRIBUTING.md](../../../../CONTRIBUTING.md).

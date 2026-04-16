# Control Titles Style Guide

This guide covers how to write `title` fields for controls in `risk-map/yaml/controls.yaml`. Control titles are the primary human-readable identifier for each security measure in the framework.

---

## Purpose

Control titles serve three functions:

1. **Identification** — Contributors and readers use titles to quickly understand what a control provides without reading the full description.
2. **ID derivation** — Control IDs are mechanically derived from titles using `control` + camelCase (e.g., "Training Data Management" becomes `controlTrainingDataManagement`).
3. **Complementarity with risks** — Risk titles name threats; control titles name defenses. The two should read as natural complements (e.g., risk "Data Poisoning" is addressed by control "Training Data Sanitization").

---

## Title Structure

### Length

Write titles of 2-6 words. Most controls use 3-4 words.

| Words | Example | Notes |
|-------|---------|-------|
| 2 | Red Teaming | Established security concept |
| 3 | Training Data Management | Common — subject + capability |
| 4 | Input Validation and Sanitization | Paired capabilities using "and" |
| 5 | Model and Data Access Controls | Compound subject + capability |
| 6 | Privacy Enhancing Technologies for Inference | Upper bound — uses "for" scope qualifier |

### Form

Titles must be **noun phrases** that name the defensive capability, security measure, or governance practice. They describe what the control provides, not what risk it prevents.

**Correct pattern:** `[Subject/Domain] [Capability/Measure]`

```
Training Data Sanitization
Model and Data Access Controls
Agent Observability
Threat Detection
Orchestrator and Route Integrity
```

---

## Content Rules

### Name the defense, not the risk

Control titles describe the protective capability. They do not restate the risk they mitigate.

| Avoid | Prefer | Why |
|-------|--------|-----|
| Preventing Data Poisoning | Training Data Sanitization | Names the capability, not the risk |
| Stopping Prompt Injection | Input Validation and Sanitization | Names the measure, not the attack |

### Use "and" for paired capabilities

Unlike risk titles (which avoid compound conjunctions), control titles commonly pair related capabilities with "and" when both are essential to the control's scope.

```
Input Validation and Sanitization
Model and Data Integrity Management
Adversarial Training and Testing
User Transparency and Controls
```

Keep to two terms. Do not chain three or more concepts with "and."

### Use "for" to scope context when needed

When the same capability applies to different lifecycle stages or domains, use "for [context]" to distinguish.

```
Privacy Enhancing Technologies for Model Training
Privacy Enhancing Technologies for Inference
```

This pattern is appropriate when the control's implementation differs materially between contexts. Do not add "for" qualifiers when the context is already clear from the subject.

### Scope to AI/ML domain when needed

When a title uses a generic security term, add a domain qualifier to distinguish it from general IT security practices.

| Generic | Scoped | Qualifier |
|---------|--------|-----------|
| Access Controls | Model and Data Access Controls | "Model and Data" |
| Tooling Security | Secure-by-Default ML Tooling | "ML" |
| Observability | Agent Observability | "Agent" |
| Permissions | Agent Permissions | "Agent" |

Established security terms that already imply the domain do not need additional scoping:

```
Red Teaming                     # Already understood in AI context
Threat Detection                # Generic but appropriately broad
Vulnerability Management        # Standard security practice
```

### Avoid verb-led titles

Control titles should not start with verbs or read as instructions.

| Avoid | Prefer |
|-------|--------|
| Manage Training Data | Training Data Management |
| Detect Threats | Threat Detection |
| Isolate Compute | Isolated and Confidential Computing |

---

## Reviewer Checklist

When reviewing a proposed control title, check each criterion:

- [ ] **2-6 words** — is the title within the expected length range?
- [ ] **Noun phrase** — does it read as a capability/measure, not a sentence or instruction?
- [ ] **Names the defense** — does it describe what the control provides, not what risk it prevents?
- [ ] **"And" used correctly** — are paired capabilities joined, not three-way chains?
- [ ] **AI/ML scoped** — if using a generic security term, is it scoped to the AI domain?
- [ ] **No verb-led phrasing** — does it avoid starting with an imperative verb?
- [ ] **Clean ID derivation** — does `control` + camelCase of this title produce a readable ID?

---

## Reference: Current Control Titles

All 29 titles in the current framework, sorted alphabetically:

```
Adversarial Training and Testing
Agent Observability
Agent Permissions
Agent User Control
Application Access and Resource Management
Incident Response Management
Input Validation and Sanitization
Internal Policies and Education
Isolated and Confidential Computing
Model and Data Access Controls
Model and Data Execution Integrity
Model and Data Integrity Management
Model and Data Inventory Management
Orchestrator and Route Integrity
Output Validation and Sanitization
Privacy Enhancing Technologies for Inference
Privacy Enhancing Technologies for Model Training
Product Governance
Red Teaming
Retrieval and Vector System Integrity Management
Risk Governance
Secure-by-Default ML Tooling
Threat Detection
Training Data Management
Training Data Sanitization
User Data Management
User Policies and Education
User Transparency and Controls
Vulnerability Management
```

---

**Related:**
- [Adding a Control](../guide-controls.md) — Step-by-step guide for adding control entries
- [Risk Titles Style Guide](risk-titles-style-guide.md) — Complementary conventions for risk titles
- [Framework Mappings Style Guide](framework-mappings-style-guide.md) — How to map controls to external frameworks

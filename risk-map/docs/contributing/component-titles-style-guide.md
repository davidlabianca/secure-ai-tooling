# Component Titles Style Guide

This guide covers how to write `title` fields for components in `risk-map/yaml/components.yaml`. Component titles name the building blocks of AI systems in the framework's architecture model.

---

## Purpose

Component titles serve three functions:

1. **Architecture communication** — Titles label nodes in the component relationship graph. They must be immediately understandable to someone reading the diagram.
2. **ID derivation** — Component IDs are mechanically derived from titles using `component` + camelCase (e.g., "Training Data" becomes `componentTrainingData`).
3. **Cross-reference clarity** — Components appear in control mappings, risk descriptions, and persona scoping. Consistent naming prevents confusion when the same component is referenced across entity types.

---

## Title Structure

### Length

Write titles of 1-4 words. Components are architectural elements, not descriptions — brevity is essential.

| Words | Example | Notes |
|-------|---------|-------|
| 1 | Application | Only for top-level, broadly scoped elements |
| 2 | Training Data | Most common — subject + qualifier |
| 3 | Model Serving Infrastructure | Adds infrastructure/system context |
| 4 | External Tools and Services | Upper bound — compound with "and" |

### Form

Titles must be **concrete nouns** that name the architectural element. They answer "what is this thing in the system?" — not "what does it do?"

**Correct pattern:** `[Domain Qualifier] [Element]`

```
Training Data
Model Storage
Agent Reasoning Core
Output Handling
Data Sources
```

---

## Content Rules

### Name the element, not the function

Component titles identify a part of the system architecture. They do not describe an activity, process, or capability.

| Avoid | Prefer | Why |
|-------|--------|-----|
| Filtering Data | Data Filtering and Processing | Names the element, not the action |
| How Models Are Served | Model Serving Infrastructure | Names the component, not the process |
| Stores for Models | Model Storage | Concise noun form |

### Reuse titles across categories when appropriate

When the same functional role appears in multiple architectural categories (Application, Agent, Orchestration), the same title can be reused. The category provides the distinguishing context.

```
# Application category
componentApplicationInputHandling   → "Input Handling"
componentApplicationOutputHandling  → "Output Handling"

# Agent category
componentAgentInputHandling         → "Input Handling"
componentAgentOutputHandling        → "Output Handling"

# Orchestration category
componentOrchestrationInputHandling → "Input Handling"
componentOrchestrationOutputHandling→ "Output Handling"
```

The ID carries the category prefix; the title stays clean and reusable.

### Use "and" sparingly for compound elements

Join two tightly coupled elements with "and" when they form a single architectural concept that would be artificial to separate.

```
Data Filtering and Processing       # Tightly coupled pipeline stages
External Tools and Services         # Both are external integrations
Model Frameworks and Code           # Both are development artifacts
```

Do not use "and" to merge architecturally distinct components that happen to be related.

### Add "Infrastructure" for deployment-layer components

When a component names the serving, storage, or compute layer (rather than the logical element), append "Infrastructure" to distinguish it from the logical concept.

```
Data Storage Infrastructure         # The storage system, not the data
Model Serving Infrastructure        # The serving layer, not the model
```

Compare with logical elements that omit the suffix:

```
Training Data                       # The data itself
The Model                           # The model artifact itself
Model Storage                       # Acceptable shorthand when context is clear
```

### Avoid acronyms except established terms

Spell out concepts in full. The exception is industry-standard terms where the acronym is more recognizable than the expansion.

| Avoid | Prefer |
|-------|--------|
| RAG Content | Retrieval Augmented Generation & Content |
| ML Frameworks | Model Frameworks and Code |

The ampersand (`&`) is acceptable in component titles where "and" would be ambiguous or overly long (e.g., "Retrieval Augmented Generation & Content").

---

## Reviewer Checklist

When reviewing a proposed component title, check each criterion:

- [ ] **1-4 words** — is the title within the expected length range?
- [ ] **Concrete noun** — does it name an architectural element, not an activity?
- [ ] **Reuse check** — if the same functional role exists in another category, does the title match?
- [ ] **"And" justified** — if "and" is used, are the two elements genuinely inseparable?
- [ ] **Infrastructure suffix** — if this is a deployment-layer component, is "Infrastructure" appended?
- [ ] **Clean ID derivation** — does `component` + camelCase of this title produce a readable ID?

---

## Reference: Current Component Titles

All 23 titles in the current framework, organized by category:

**Data:**
```
Data Sources
Data Filtering and Processing
Training Data
Data Storage Infrastructure
```

**Model:**
```
Model Frameworks and Code
Model Evaluation
Training and Tuning
Model Storage
Model Serving Infrastructure
The Model
```

**Application:**
```
Application
Output Handling
Input Handling
```

**Orchestration:**
```
Agent Reasoning Core
Output Handling
Input Handling
External Tools and Services
Model Memory
Retrieval Augmented Generation & Content
```

**Agent:**
```
Agent User Query
Agent System Instructions
Input Handling
Output Handling
```

---

**Related:**
- [Adding a Component](../guide-components.md) — Step-by-step guide for adding component entries
- [Risk Titles Style Guide](risk-titles-style-guide.md) — Naming conventions for risks
- [Control Titles Style Guide](control-titles-style-guide.md) — Naming conventions for controls

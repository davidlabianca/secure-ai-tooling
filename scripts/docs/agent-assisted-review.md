# Agent-Assisted Content Review

_(Experimental — v0.2.0-draft)_

## Overview

Agent-assisted review uses an LLM with a structured prompt to review content changes to the CoSAI Risk Map framework. Risk map content updates involve cross-referencing risks, controls, personas, and external framework mappings (MITRE ATLAS, NIST AI RMF, OWASP). A structured agent catches integrity and semantic issues that automated validation and manual review can miss.

**Current agent:** content-reviewer
**Definition:** [`scripts/agents/content-reviewer.md`](../agents/content-reviewer.md)

The agent definitions are LLM-neutral — they work with any model that can follow a structured system prompt.

---

## Modes and Formats

The content-reviewer operates in three modes:

| Mode    | Purpose                                        | When to Use                                       |
| ------- | ---------------------------------------------- | ------------------------------------------------- |
| `diff`  | PR review of changed YAML                      | After making YAML changes, before submitting a PR |
| `full`  | Pre-submission quality check on complete files | Before a major submission or periodic audit       |
| `issue` | Evaluate a GitHub issue proposal               | Before implementing a proposed change             |

Output format is specified per invocation:

| Format  | Audience                             | Output Style                                          |
| ------- | ------------------------------------ | ----------------------------------------------------- |
| `human` | Contributors reading the review      | Narrative with rationale, suggestions, and next steps |
| `agent` | Orchestrator agents routing findings | Structured data, minimal prose                        |

---

## How to Use

1. Copy the contents of [`scripts/agents/content-reviewer.md`](../agents/content-reviewer.md) as a system prompt to any LLM
2. Provide the relevant YAML files as context:
   - `risk-map/yaml/risks.yaml`
   - `risk-map/yaml/controls.yaml`
   - `risk-map/yaml/components.yaml`
   - `risk-map/yaml/personas.yaml`
3. Specify mode and format in your user message
4. For `diff` mode, include the proposed YAML changes (diff or full modified file)
5. For `issue` mode, include the GitHub issue body

### Example Invocation (diff / human)

```
mode: diff
format: human

Proposed change: Adding new entry to controls.yaml:

  - id: controlModelCardValidation
    title: "Model Card Validation"
    description: "Validate that model cards contain required security-relevant
      metadata before deployment."
    category: controlsModel
    risks:
      - riskModelDeploymentTampering
      - riskModelSourceTampering
    components:
      - componentModelRegistry
    personas:
      - personaModelConsumer
```

The agent returns a structured review with per-entity findings grouped by severity. See the [full agent definition](../agents/content-reviewer.md) for complete example outputs.

---

## Severity Model

### diff and full modes

| Level    | Meaning                                                               | Blocks Merge?                                            |
| -------- | --------------------------------------------------------------------- | -------------------------------------------------------- |
| **FAIL** | Structural or mechanical violation (dangling reference, ID collision) | Yes                                                      |
| **WARN** | Potential quality or integrity concern requiring attention            | No (triggers `NEEDS_HUMAN_REVIEW` for semantic findings) |
| **INFO** | Observation — useful context, no action required                      | No                                                       |
| **PASS** | Explicit confirmation that a check succeeded                          | No                                                       |

Verdicts:

| Verdict              | Condition                                                                        |
| -------------------- | -------------------------------------------------------------------------------- |
| `READY`              | No FAIL findings. Safe to proceed (with optional human review of flagged items). |
| `BLOCKING`           | One or more FAIL findings. Must resolve before merge.                            |
| `NEEDS_HUMAN_REVIEW` | No FAIL findings, but WARN-level semantic findings that need human judgment.     |

### issue mode

| Level           | Meaning                                              |
| --------------- | ---------------------------------------------------- |
| **CONCERN**     | Potential problem to discuss before implementation   |
| **GAP**         | Missing information needed for implementation        |
| **OBSERVATION** | Useful context (e.g., overlap with existing content) |

Verdicts:

| Verdict   | Condition                                                          |
| --------- | ------------------------------------------------------------------ |
| `PROCEED` | Well-formed proposal, no major concerns. Ready for implementation. |
| `DISCUSS` | Concerns or gaps to resolve before implementation begins.          |
| `RETHINK` | Fundamental fit or overlap issues suggesting a different approach. |

See the [full agent definition](../agents/content-reviewer.md) for the complete check tables, finding structure, and output format specifications.

---

## Relationship to Automated Validation

The agent does **not** replace existing automated validation. It adds a semantic layer above it.

| Layer                              | Tools                                                   | What It Catches                                                                              |
| ---------------------------------- | ------------------------------------------------------- | -------------------------------------------------------------------------------------------- |
| **Schema validation**              | `check-jsonschema`, JSON schemas in `risk-map/schemas/` | Missing fields, wrong types, invalid enum values                                             |
| **Edge consistency**               | `validate_riskmap.py`                                   | Bidirectional component relationship violations                                              |
| **Cross-reference validation**     | `validate_control_risk_references.py`                   | Control-risk reference mismatches                                                            |
| **Framework reference validation** | `validate_framework_references.py`                      | Invalid MITRE ATLAS, NIST, OWASP references                                                  |
| **Agent review**                   | content-reviewer                                        | Vague descriptions, semantic overlap, coverage gaps, impact assessment, governance awareness |

Run automated validation first. The agent assumes schema and structural checks already pass.

---

## Future Work

- Current coverage: content-reviewer only
- Additional agent definitions may be added to `scripts/agents/` as the workflow matures (e.g., framework mapping review, component graph analysis)
- The `scripts/prompts/` directory is reserved for reusable prompt fragments shared across agents

---

**Related:**

- [Agent definition: content-reviewer](../agents/content-reviewer.md) — Full specification
- [Hook Validations](hook-validations.md) — Automated validation checks
- [Validation Flow](validation-flow.md) — Commit validation process
- [Risk Map Developer Guide](../../risk-map/docs/developing.md) — Main contribution guide

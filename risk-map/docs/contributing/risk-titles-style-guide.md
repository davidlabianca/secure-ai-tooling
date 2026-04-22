# Risk Titles Style Guide

This guide covers how to write `title` fields for risks in `risk-map/yaml/risks.yaml`. Risk titles are the primary human-readable identifier for each risk and must be consistent across the framework.

---

## Purpose

Risk titles serve three functions:

1. **Identification** — Contributors and readers use titles to quickly understand what a risk describes without reading the full description.
2. **ID derivation** — Risk IDs are mechanically derived from titles using `risk` + camelCase (e.g., "Data Poisoning" becomes `riskDataPoisoning`). A clear title produces a clear ID.
3. **Framework consistency** — Titles appear in summary tables, graph visualizations, issue templates, and cross-references. Inconsistent titles degrade the framework's usability.

---

## Title Structure

### Length

Write titles of 2-5 words. Shorter titles are preferred when they capture the risk without ambiguity.

| Words | Example | Notes |
|-------|---------|-------|
| 2 | Data Poisoning | Ideal — concise and precise |
| 3 | Model Source Tampering | Common — subject + threat |
| 4 | Economic Denial of Wallet | Acceptable — established term |
| 5 | Excessive Data Handling During Inference | Upper bound — only when scoping is essential |
| 6+ | — | Avoid — rephrase or split |

### Form

Titles must be **noun phrases** that name the threat, vulnerability, or attack vector. They are not sentences, not descriptions of missing controls, and not explanations of consequences.

**Correct pattern:** `[Subject/Scope] [Threat Noun]`

```
Model Source Tampering
Prompt Injection
Tool Registry Tampering
Agent Over-Permissioning
MCP Transport Hijacking
```

---

## Content Rules

### Name the threat, not the missing control

Titles describe what the attacker does or what goes wrong — not what defense is absent. Avoid "insufficient," "failure to," "lack of," or "missing" framing.

| Avoid | Prefer | Why |
|-------|--------|-----|
| Insufficient Logging of Delegation Chains | Agent Delegation Chain Opacity | Names the threat state, not the absent control |
| Failure to Bind Agent Identity to Model Artifacts | Stale Agent Identity Binding | Names the vulnerability, not the process failure |
| Input Validation Failures in MCP Interactions | MCP Parameter Injection | Names the attack vector, not the missing defense |
| MCP Session and Transport Security Failures | MCP Transport Hijacking | Names the attack, not the absent security |

### No mechanism or scope clauses

Do not embed "via...", "in...", "due to...", or "through..." clauses that explain how or where the risk occurs. That detail belongs in the description.

| Avoid | Prefer | Why |
|-------|--------|-----|
| Resource Exhaustion via Uncontrolled Agent Tool Chaining | Runaway Agent Tool Loops | "via..." is a mechanism explanation |
| Cross-Tenant Propagation via Shared Agent Identities | Cross-Tenant Credential Propagation | "via..." is redundant context |
| Input Validation Failures in MCP Interactions | MCP Parameter Injection | "in..." is a scope qualifier |

### No compound conjunctions

Do not join two concepts with "and" unless both are essential to the risk's identity. If the second clause describes a consequence rather than a co-equal threat, drop it.

| Avoid | Prefer | Why |
|-------|--------|-----|
| Broken Delegation Chains and Loss of Actor Clarity | Agent Delegation Chain Opacity | "Loss of Actor Clarity" is a consequence, not a second threat |
| Input Validation and Sanitization Failures | MCP Parameter Injection | "Validation and Sanitization" is a compound where one term suffices |

### Scope to AI/agentic domain when needed

When a title uses a generic security concept that could apply to any software system, add an AI/agentic qualifier to scope it to this framework's domain.

| Generic | Scoped | Pattern |
|---------|--------|---------|
| Confused Deputy Delegation | Agentic Delegation Confused Deputy | Adds "agentic" to scope the classic pattern |
| Delegation Chain Opacity | Agent Delegation Chain Opacity | Adds "agent" to distinguish from general delegation |
| Over-Permissioning | Agent Over-Permissioning | Adds "agent" like "Denial of ML Service" adds "ML" |

Established AI/agentic terms that already imply the domain do not need additional scoping:

```
MCP Transport Hijacking          # "MCP" is inherently agentic
Tool Registry Tampering           # "Tool Registry" is framework-specific
Prompt Injection                  # "Prompt" is inherently AI
```

### Slashes for alternatives

When a title involves two complementary or alternative terms, use a slash without spaces to join them. Both terms are retained in the derived ID.

```
Adapter/PEFT Injection           → riskAdapterPEFTInjection
Prompt/Response Cache Poisoning  → riskPromptResponseCachePoisoning
Zombie / Shadow MCP Servers      → riskZombieShadowMCPServers
```

---

## Reviewer Checklist

When reviewing a proposed risk title, check each criterion:

- [ ] **2-5 words** — is the title within the expected length range?
- [ ] **Noun phrase** — does it read as a thing, not a sentence or action?
- [ ] **Names the threat** — does it describe the attack/vulnerability, not the missing control?
- [ ] **No mechanism clauses** — free of "via...", "in...", "due to..." qualifiers?
- [ ] **No compound conjunctions** — free of "and [consequence]" appendages?
- [ ] **AI/agentic scoped** — if using a generic security term, is it scoped to the AI domain?
- [ ] **Clean ID derivation** — does `risk` + camelCase of this title produce a readable ID?

---

## Reference: Current Risk Titles

All 28 titles in the current framework, sorted alphabetically:

```
Accelerator and System Side-channels
Adapter/PEFT Injection
Agent Delegation Chain Opacity
Agent Over-Permissioning
Agentic Delegation Confused Deputy
Covert Channels in Model Outputs
Cross-Tenant Credential Propagation
Data Poisoning
Denial of ML Service
Economic Denial of Wallet
Evaluation/Benchmark Manipulation
Excessive Data Handling
Excessive Data Handling During Inference
Federated/Distributed Training Privacy
Inferred Sensitive Data
Insecure Integrated Component
Insecure Model Output
Malicious Loader/Deserialization
MCP Parameter Injection
MCP Transport Hijacking
Model Deployment Tampering
Model Evasion
Model Exfiltration
Model Reverse Engineering
Model Source Tampering
Orchestrator/Route Hijack
Prompt Injection
Prompt/Response Cache Poisoning
Retrieval/Vector Store Poisoning
Rogue Actions
Runaway Agent Tool Loops
Sensitive Data Disclosure
Shadow and Unknown Agents
Stale Agent Identity Binding
Tool Registry Tampering
Tool Source Provenance
Unauthorized Training Data
Zombie / Shadow MCP Servers
```

**Note:** This list includes proposed new risks currently under review (issues #188-#199) alongside established entries. Proposed entries are subject to consolidation decisions and may not all be accepted.

---

**Related:**
- [Adding a Risk](../guide-risks.md) — Step-by-step guide for adding risk entries
- [Risk ID Migration](../design/risk-id-migration.md) — ID naming rules and full legacy-to-new mapping
- [Framework Mappings Style Guide](framework-mappings-style-guide.md) — How to map risks to external frameworks

---
name: audit-framework-mappings
description: Audit all framework mappings in risks.yaml, controls.yaml, and personas.yaml against the framework mappings style guide. Use when reviewing or proposing changes to mappings sections.
---

# Framework Mappings Audit

Audit framework mappings for correctness, style compliance, and term validity.

## Scope

Target: a single entity id (e.g., `riskModelEvasion`, `controlInputValidationAndSanitization`, `personaEndUser`), or the whole corpus — every entity across `risks.yaml`, `controls.yaml`, `personas.yaml` (the default). If a specific entity id is given, audit only that entity's mappings.

## Reference documents

Read these before auditing:

1. **Style guide** (authoritative): `risk-map/docs/contributing/framework-mappings-style-guide.md`

## Audit checklist

For each entity with mappings, verify ALL of the following. Report pass/fail per item.

### Format and version compliance

Mapping values are **version-pinned** (ADR-027): every value carries its framework's version token, except STRIDE, which is intentionally unversioned. Verify each value against the **canonical pinned pattern for its framework in the authoritative style guide** (`risk-map/docs/contributing/framework-mappings-style-guide.md`, "Identifier Enforcement" table) — read the patterns from the guide every time; do not restate them from memory or inline here. The guide is the single source for pattern and version-token conventions across every supported framework, including any framework registered after this skill was written — new frameworks are a recurring, actively-requested change (see open issues against `frameworks.yaml`), so nothing about the pinned-pattern set may live in two places.

Flag any value whose form or version token does not match the guide's current pinned pattern.

*(This skill AUDITS existing mappings across the corpus; to SELECT mappings while authoring a single control or risk, use the `mapping-selection` skill.)*

### Structural compliance

- [ ] **No parent + sub-technique collisions**: If `AML.T0010.002` is used, `AML.T0010` must NOT appear on the same entity
- [ ] **No technique/mitigation crossover**: Risks use only `AML.T####`; controls use only `AML.M####`
- [ ] **applicableTo respected**: Each framework is only used on entity types listed in its `applicableTo` (per style guide table)

### Selectivity compliance

- [ ] **Soft limit (4 per framework)**: Flag any entity with more than 4 mappings in a single framework. Not a hard error, but requires justification.
- [ ] **Direct relevance**: Each mapping should be defensible with a one-sentence rationale. Flag mappings where the connection is "related" rather than "directly relevant."

### Term and identifier verification

Two distinct checks — do not conflate them. The first is structural and runs at whatever scope the audit is already covering; the second is a live, per-entity lookup that is never an automatic side effect of the first.

- [ ] **Verify identifiers are well-formed against the style guide's patterns.** For MITRE ATLAS, technique/mitigation IDs match the pinned regex. For OWASP, the category title matches the guide. For ISO 22989, role names match the controlled vocabulary. This is a structural check — no live lookup — and applies at whatever scope the audit already covers, whole-corpus included, the same as the structural-compliance and selectivity checks above.
- [ ] **Live-verify identifier currency (search the web)** when a specific identifier's currency is actually in question: proposing a new mapping value, or auditing a single **targeted** entity (per Scope) whose identifiers you are specifically confirming. This is a heavier, per-entity check. **It is not run automatically across every entry as a side effect of a whole-corpus audit** — a whole-corpus audit's job is the structural/selectivity/overlap sweep above, not a live web-search of every existing mapping in the file. If comprehensive liveness verification of the full corpus is genuinely wanted, invoke it as its own explicit, separately-requested pass — never as an implicit consequence of the routine audit.

## Coverage analysis (for whole-corpus scope only)

- Count entities with vs. without mappings per entity type
- Identify unmapped entities where obvious framework matches exist
- Note underutilized frameworks (e.g., NIST AI RMF, OWASP LLM08)
- Note STRIDE categories never used

## Output format

For targeted audits (single entity), provide:

1. Current mappings listed per framework
2. Pass/fail on each checklist item
3. Any recommended additions or removals with rationale

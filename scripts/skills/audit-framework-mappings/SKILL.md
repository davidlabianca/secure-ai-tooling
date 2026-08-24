---
name: audit-framework-mappings
description: Audit framework mappings — an existing entity's mappings, the whole corpus, or a candidate value proposed for an entity not yet in the corpus — against the framework mappings style guide. Use when reviewing, auditing, or pre-PR authoring mapping changes for risks.yaml, controls.yaml, or personas.yaml.
---

# Framework Mappings Audit

Audit framework mappings for correctness, style compliance, and term validity.

## Scope

Three modes, chosen by what the caller provides — each is a first-class mode, not a side effect of another:

- **Single entity**: a specific entity id already in the corpus (e.g., `riskModelEvasion`, `controlInputValidationAndSanitization`, `personaEndUser`). Audit that entity's existing mappings, or a new value being proposed for addition to that entity. Both are single-entity scope: the entity already exists, so this is distinct from candidate mode below, which is for an entity that does not exist yet.
- **Whole corpus** (the default): every entity across `risks.yaml`, `controls.yaml`, `personas.yaml`.
- **Candidate value(s)** for an entity not yet in the corpus (pre-PR authoring): audit the given value(s) directly. No corpus id lookup applies — the entity doesn't exist yet, so there is nothing to look up by id. The caller must also state the entity type the candidate targets (risk, control, or persona), since parts of the checklist (e.g., MITRE ATLAS technique-vs-mitigation) depend on it. See [Candidate mode checklist](#candidate-mode-checklist-pre-pr-entity-not-yet-in-corpus).

## Reference documents

Read these before auditing:

1. **Style guide** (authoritative): `risk-map/docs/contributing/framework-mappings-style-guide.md`

## Audit checklist (for whole-corpus and single-entity scope)

For each entity with mappings, verify ALL of the following. Report pass/fail per item. Candidate mode (an entity not yet in the corpus) does not have "mappings" on an entity to iterate over — it uses its own [Candidate mode checklist](#candidate-mode-checklist-pre-pr-entity-not-yet-in-corpus) below instead.

### Format and version compliance

Mapping values are **version-pinned** (ADR-027): every value carries its framework's version token, except STRIDE, which is intentionally unversioned. Verify each value against the **canonical pinned pattern for its framework in the authoritative style guide** (`risk-map/docs/contributing/framework-mappings-style-guide.md`, "Identifier Enforcement" table) — read the patterns from the guide every time; do not restate them from memory or inline here. The guide is the single source for pattern and version-token conventions across every supported framework, including any framework registered after this skill was written — new frameworks are a recurring, actively-requested change (see open issues against `frameworks.yaml`), so nothing about the pinned-pattern set may live in two places.

Flag any value whose form or version token does not match the guide's current pinned pattern.

*(Division of labor: `mapping-selection` makes the affirmative, broader authoring judgment of WHICH mappings to propose in the first place — browsing the corpus, picking the components/risks a control or risk should connect to, choosing the correct NIST AI RMF function — before a candidate value exists. This skill, in any of its three scope modes including candidate mode, then audits the chosen or proposed value(s): well-formed, current, structurally sound, AND not over-selective or tangential. Selectivity compliance (the soft cap, direct relevance — see [Selectivity compliance](#selectivity-compliance) and candidate-mode step 3) is explicitly part of THIS skill's checklist in every mode, not `mapping-selection`'s exclusive territory — it runs whether the entity is new (candidate) or already exists.)*

### Structural compliance

- [ ] **No parent + sub-technique collisions**: If `AML.T0010.002` is used, `AML.T0010` must NOT appear on the same entity
- [ ] **No technique/mitigation crossover**: Risks use only `AML.T####`; controls use only `AML.M####`
- [ ] **applicableTo respected**: Each framework is only used on entity types listed in its `applicableTo` (per style guide table)

### Selectivity compliance

- [ ] **Soft limit (4 per framework)**: Flag any entity with more than 4 mappings in a single framework. Not a hard error, but requires justification.
- [ ] **Direct relevance**: Each mapping should be defensible with a one-sentence rationale. Flag mappings where the connection is "related" rather than "directly relevant."

### Term and identifier verification

Two distinct checks — do not conflate them. The first is structural and runs at whatever scope the audit is already covering; the second is a live, per-entity or per-candidate-value lookup that is never an automatic side effect of the first.

- [ ] **Verify identifiers are well-formed against the style guide's patterns.** For MITRE ATLAS, technique/mitigation IDs match the pinned regex. For OWASP, the category title matches the guide. For ISO 22989, role names match the controlled vocabulary. This is a structural check — no live lookup — and applies at whatever scope the audit already covers, whole-corpus included, the same as the structural-compliance and selectivity checks above.
- [ ] **Live-verify identifier currency (search the web)** when a specific identifier's currency is actually in question: proposing a **candidate** mapping value (per Scope; see [Candidate mode checklist](#candidate-mode-checklist-pre-pr-entity-not-yet-in-corpus)), or auditing a single **targeted** entity (per Scope) — whether confirming an identifier already on that entity, or a new value being proposed for addition to it. This is a heavier, per-entity or per-candidate-value check. **It is not run automatically across every entry as a side effect of a whole-corpus audit** — a whole-corpus audit's job is the structural/selectivity/overlap sweep above, not a live web-search of every existing mapping in the file. If comprehensive liveness verification of the full corpus is genuinely wanted, invoke it as its own explicit, separately-requested pass — never as an implicit consequence of the routine audit. **Exception:** a framework skips this step entirely only if its identifiers are a closed, *unversioned* enum encoded directly in this repo's schema, with no external registry that could ever add, retire, or renumber a member — for those, the structural/enum-membership check above is their complete verification. Both halves of that test matter — closed AND unversioned — not closed alone. A framework whose schema check is instead a version-pinned pattern or regex (MITRE ATLAS, NIST AI RMF, OWASP Top 10 for LLM, EU AI Act) never qualifies for this exemption, regardless of how infrequently a given edition changes, because its identifier space remains open-ended by construction. ISO 22989 also does not qualify, despite being a closed enum encoded directly in the schema: it is *versioned* (`@2022`), and `risk-map/schemas/frameworks.schema.json`'s `iso-22989` definition is deliberately structured as a `oneOf` with a comment stating each future ISO 22989 edition appends a new member carrying that edition's enum — i.e., ISO periodically revises 22989 through a real external process that can add, retire, or rename role descriptors, exactly what live-verify exists to catch. STRIDE is the only framework that is both closed and unversioned, which is why it alone is the current instance of this exception (see [Candidate mode checklist](#candidate-mode-checklist-pre-pr-entity-not-yet-in-corpus) for why).

### Candidate mode checklist (pre-PR, entity not yet in corpus)

Candidate mode audits a value (or set of values) intended for an entity that does not yet exist in the corpus — there is no entity id to look up. The caller must state the entity type the candidate targets (risk, control, or persona) before this checklist can run, since step 2 depends on it (e.g., MITRE ATLAS technique-vs-mitigation). **If the entity type is not stated, halt and ask the caller for it — never infer, default, or silently proceed.** For each candidate value, run, in order:

1. **Format/version compliance** — the same check as [Format and version compliance](#format-and-version-compliance) above: match the value against the canonical pinned pattern for its framework in the style guide.
2. **Full structural compliance** — the same checklist as [Structural compliance](#structural-compliance) above, evaluated against the stated entity type and against the full set of values proposed together (not each value in isolation): parent/sub-technique collisions, technique/mitigation crossover, `applicableTo`. A well-formed value can still fail here — do not stop at step 1.
3. **Selectivity compliance** — the same checklist as [Selectivity compliance](#selectivity-compliance) above, evaluated against the full set of candidate values proposed together (not each value in isolation): the soft limit of 4 mappings per framework, and direct relevance. A set of candidate values can each pass structural compliance individually and still be over-selective as a set — do not stop at step 2. **The "full set" must be the caller's complete intended set, not whatever has been mentioned so far.** If the caller's prompt signals that more candidate values may follow for this entity/framework combination (e.g., says "I'll have more later," "I might add a couple more," or similar), ask the caller to confirm the complete set of candidate values before finalizing a selectivity verdict, rather than evaluating the partial set as final — a partial view risks seeing a "full set" of size one or two and never catching a cross-value overshoot of the soft cap once the remaining values arrive.
4. **Live-verify identifier currency (search the web)** — a candidate value's currency is always in question, so this step always applies, **except for frameworks with no external evolving registry to check currency against**: a closed, *unversioned* enum encoded directly in this repo's schema, with no external registry that could ever add, retire, or renumber a member. Both halves of that test matter — closed AND unversioned — not closed alone. STRIDE is the current instance of this exception: it is a closed, unversioned, six-member enum (`Spoofing`, `Tampering`, `Repudiation`, `InformationDisclosure`, `DenialOfService`, `ElevationOfPrivilege`) with no external registry that issues new members over time. A live web search against a closed enum is a no-op at best; at worst it surfaces out-of-enum variants from adjacent but distinct models (e.g., STRIDE-LM's added "Lateral Movement" category) that this repo's schema enum rejects, and mistaking a web hit for a valid addition would introduce a value that fails `check-jsonschema`. A framework whose schema check is instead a version-pinned pattern or regex (MITRE ATLAS, NIST AI RMF, OWASP Top 10 for LLM, EU AI Act) never qualifies for this exemption, regardless of how infrequently a given edition changes, because its identifier space remains open-ended by construction — for example, NIST AI RMF's pattern permits any subcategory number, so a fabricated value like `MEASURE-2.99@1.0` would pass the schema and still requires live-verify. ISO 22989 also does not qualify for this exemption, even though it too is a closed enum encoded directly in the schema: unlike STRIDE it is *versioned* (`@2022`), and `risk-map/schemas/frameworks.schema.json`'s `iso-22989` definition documents that each future ISO 22989 edition appends a new `oneOf` member for that edition's enum — ISO periodically revises 22989, so its role descriptors have a real external revision process (additions, retirements, renamings) that live-verify exists to catch, distinct from the open-ended-regex reason MITRE ATLAS/NIST/OWASP/EU AI Act are excluded. For STRIDE-class frameworks, the enum-membership check inside step 1 (format/version compliance) is the complete verification — report it as such rather than silently skipping the step (see [Output format](#output-format)).

This mechanism generalizes: any framework registered in `frameworks.yaml` with no external evolving registry behind its identifiers (a closed, unversioned enum, as opposed to a versioned taxonomy like MITRE ATLAS, a numbered list like OWASP Top 10 for LLM, or a versioned/editioned closed enum like ISO 22989) is exempt from step 4 on the same reasoning. STRIDE is the only framework meeting that description today.

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

For candidate mode (values for an entity not yet in the corpus), provide, per candidate value:

1. Pass/fail on format/version compliance
2. Pass/fail on each structural compliance item (parent/sub-technique collision, technique/mitigation crossover, `applicableTo`)
3. Pass/fail on selectivity, evaluated against the full candidate set (soft cap of 4 mappings per framework, direct relevance)
4. The live-verify result (found current / not found / doesn't exist), or, for a framework with no external registry (STRIDE-class), the explicit statement "live-verify not applicable (closed enum, no registry)" rather than omitting the item
5. An overall accept/reject recommendation for the value, with rationale for any failure. If the complete candidate set could not be confirmed (per step 3's drip-feed clause), report the recommendation as provisional/pending rather than a final accept/reject, and state what is needed to finalize it (confirmation of the complete candidate set)

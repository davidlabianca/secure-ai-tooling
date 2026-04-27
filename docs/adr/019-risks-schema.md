# ADR-019: `risks.schema.json` design and tradeoffs

**Status:** Accepted
**Date:** 2026-04-24
**Authors:** Architect agent, with maintainer review

---

## Context

`risk-map/schemas/risks.schema.json` is the JSON Schema (Draft-07) that governs `risk-map/yaml/risks.yaml`, the largest and most-cited content surface in the framework. Risks are read by every downstream consumer the framework owns: `scripts/hooks/yaml_to_markdown.py` (table generation under `risk-map/tables/`), `scripts/hooks/riskmap_validator/graphing/` (Mermaid generation under `risk-map/diagrams/`), and `scripts/build_persona_site_data.py` (the persona-site JSON contract codified in [ADR-011](011-persona-site-data-schema-contract.md)). External redistributors per [ADR-014](014-yaml-content-security-posture.md) P1 also read the YAML directly.

The schema landed incrementally and has not been documented as a unit. It carries 28 risk IDs in a closed enum, two open string fields (`title`, untyped) alongside `riskmap.schema.json#/definitions/utils/text` references for prose, three closed category enums (`category`, `lifecycleStage`, `impactType`, `actorAccess`), an open `mappings` object whose property names are constrained to `frameworks.schema.json` IDs but whose values are free-form string arrays, and a `relevantQuestions` field that no validator reads, no generator consumes, and no contributing doc explains.

[ADR-014](014-yaml-content-security-posture.md) establishes the security posture; ADRs 015-017 set the rendering, reference, and authoring rules that this ADR threads into the schema. ADR-018 documents `components.schema.json` in parallel; this ADR documents `risks.schema.json`. ADRs 020-022 follow for controls, personas, and supporting schemas. The five per-file schema ADRs are non-overlapping.

The discovery work that motivated this set of architectural ADRs surfaced systemic gaps specific to risks:

- **Ghost field.** `relevantQuestions` is defined at `risks.schema.json:83-86` as `array` of `string`. Two entries (`riskToolRegistryTampering` at risks.yaml:1683 and `riskToolSourceProvenance` at risks.yaml:2071) populate it. No code path in `scripts/hooks/`, `scripts/build_persona_site_data.py`, `scripts/hooks/yaml_to_markdown.py`, or anywhere else reads the field. No `risk-map/docs/` page documents what it is for. It is dead weight that two recent contributors expended effort to populate.
- **Outbound citations are prose-embedded.** `risks.yaml` carries approximately 55 outbound `<a href="https://...">` tags inside `longDescription` and `examples` prose. None of them are structured; per [ADR-016](016-reference-strategy.md) every one migrates to `externalReferences` during the conformance sweep.
- **Intra-document anchors are prose-embedded.** Approximately 14 `<a href="#riskXxx">` tags and approximately 41 bare camelCase risk identifiers appear in prose, all of which migrate to `{{idXxx}}` sentinels per [ADR-016](016-reference-strategy.md) D2.
- **Mapping fields are loosely typed.** `mappings.*` accepts any string array per framework key. There is no per-framework regex on the mapping IDs, so `AML.T0020` and `aml-t0020` and `AML T0020` all pass schema validation; the canonical-form discipline lives only in author convention.
- **BLOCK-02 nested-list shape.** Three risks (notably `riskSensitiveDataDisclosure` and `riskRogueActions` and `riskInsecureIntegratedComponent`) use the `- - >` nested-array pattern inside prose fields to express a semantic sub-group. The shape is enforced by [ADR-011](011-persona-site-data-schema-contract.md)'s `persona-site-data.schema.json#/definitions/prose` for the *output* artifact; the *input* schema (`risks.schema.json`) currently constrains those prose fields only by `riskmap.schema.json#/definitions/utils/text`, which is shape-only.

This ADR documents the schema's existing shape under [ADR-014](014-yaml-content-security-posture.md) P2's content-class taxonomy, declares per-rule machine-enforcement vs. validator-enforcement vs. prose-only guidance, threads in [ADR-016](016-reference-strategy.md)'s `externalReferences` `$ref` integration and [ADR-017](017-yaml-prose-authoring-subset.md)'s prose-content boundary, and lists the tightenings the conformance sweep will apply. It does not migrate the YAML or remove `relevantQuestions` from the schema; the sweep executes those changes against the decisions recorded here.

## Decision

`risks.schema.json` is documented retroactively under the content-class taxonomy of [ADR-014](014-yaml-content-security-posture.md) P2, with the additions and retirements named below. Sub-decisions follow the D-prefix convention.

### D1. Field taxonomy under ADR-014 P2

Every top-level field in the `risk` definition maps to one of the five P2 content classes. The taxonomy declares the enforcement layer for each class.

| Field | P2 class | Enforcement |
|---|---|---|
| `id` | identifier | Schema (closed enum, 28 values) |
| `title` | metadata | Schema shape only (`string`, no length cap) |
| `shortDescription`, `longDescription`, `examples` | prose | Schema shape via `riskmap.schema.json#/definitions/utils/text`; ADR-017 lint enforces token grammar; ADR-016 sentinels resolve at lint and generator time |
| `tourContent.{introduced,exposed,mitigated}` | prose | Same as above |
| `category` | identifier (taxonomic) | Schema (closed enum, 5 values) |
| `personas` | structured reference | Schema (`$ref` to `personas.schema.json#/definitions/persona/properties/id`) |
| `controls` | structured reference | Schema (`$ref` to `controls.schema.json#/definitions/control/properties/id`); cross-file integrity by `validate_control_risk_references.py` |
| `mappings` | metadata (structured) | Schema constrains property names to `frameworks.schema.json` IDs; values are open string arrays; per-framework ID patterns are not currently enforced (D5) |
| `lifecycleStage` | identifier (taxonomic) | Schema (`$ref` array OR `"all" \| "none"` literal) |
| `impactType` | identifier (taxonomic) | Schema (same shape as `lifecycleStage`) |
| `actorAccess` | identifier (taxonomic) | Schema (same shape as `lifecycleStage`) |
| `externalReferences` (new, per ADR-016) | structured reference | Shared schema `external-references.schema.json` `$ref`'d (D7) |
| `relevantQuestions` (current, retired) | n/a — ghost field | Removed from schema in conformance sweep (D6) |

The class boundary is load-bearing per [ADR-014](014-yaml-content-security-posture.md) P2: identifiers and structured references are authoritative and schema-constrained; prose and metadata are authored and require the stacked authoring/generation/render enforcement of P4. Risks is the canonical example of the taxonomy because every class is present.

### D2. Identifier and enum decisions

- **Risk `id`.** Closed enum at `risks.schema.json:22-51`, currently 28 values. Each value is camelCase with a `risk` prefix (`riskPromptInjection`, `riskToolRegistryTampering`). The closed-enum form is chosen over an open `pattern: "^risk[A-Z][A-Za-z0-9]*$"` because it forces every new risk to land via a schema-edit PR that is itself reviewable, which is the same property [ADR-016](016-reference-strategy.md) D6 relies on for the sentinel linter's allowlist (the linter reads the enum directly). An open pattern would let a typo'd new risk pass schema validation; the closed enum makes that impossible.

  The authoring guide commits each new risk's id-and-enum addition to the same PR; the enum is the authoritative list for risks across every consumer.

- **`category`.** Closed enum, 5 values: `risksSupplyChainAndDevelopment`, `risksDeploymentAndInfrastructure`, `risksRuntimeInputSecurity`, `risksRuntimeDataSecurity`, `risksRuntimeOutputSecurity`. Tracks the taxonomy section in `risk-map/docs/design/`. New categories are an ADR question (framework-content design lives in `risk-map/docs/design/` per [ADR-001](001-adopt-adrs.md)), not a silent schema edit.

- **`lifecycleStage`, `impactType`, `actorAccess`.** Each is `oneOf: [array<enum-id>, "all" | "none"]`. The `"all" | "none"` literal alternative exists so authors can express "applies everywhere" and "applies nowhere" without enumerating every enum member. The two literal escape hatches are deliberately the only ones; an enum value of `"all"` would collide.

  The enum sources live in dedicated schemas (`lifecycle-stage.schema.json`, `impact-type.schema.json`, `actor-access.schema.json`), `$ref`'d here. This matches the repo's single-source-of-truth pattern for shared enums (`frameworks.schema.json`, `riskmap.schema.json#/definitions/utils/text`) and the [ADR-016](016-reference-strategy.md) `external-references.schema.json` direction.

- **`tourContent`.** The three sub-fields (`introduced`, `exposed`, `mitigated`) are explicit object properties rather than a `tourContent[].stage` enum. The existing shape is preserved; an enum-keyed alternative would be a framework-content design change owned by `risk-map/docs/design/` rather than a schema-uplift concern.

### D3. Structured-reference fields

`personas` and `controls` are typed arrays of identifiers, validated against the corresponding source schemas:

- `personas` → `$ref: personas.schema.json#/definitions/persona/properties/id`
- `controls` → `$ref: controls.schema.json#/definitions/control/properties/id`

Both are required at the entry level (per the `required` array at line 153). An empty `controls` list is currently allowed by the schema; in practice every risk lists at least one control, and the bidirectional integrity check in `scripts/hooks/validate_control_risk_references.py` enforces that whatever risk-listed controls exist also reference the risk back from `controls.yaml`.

The schema does **not** enforce bidirectionality directly. Per [ADR-014](014-yaml-content-security-posture.md) P2, cross-file referential integrity is a validator concern, not a schema concern: a JSON Schema cannot express "every entry in this array must also appear in another file's corresponding array." `validate_control_risk_references.py` is the enforcement point, and it is invoked via `.pre-commit-config.yaml` per [ADR-005](005-pre-commit-framework.md) on every commit that touches `risks.yaml` or `controls.yaml`.

The schema-vs-validator boundary for D3:

- **Schema:** identifier shape, identifier resolves to a known enum value, array typing.
- **Validator:** bidirectional referential integrity, orphaned-control detection, dangling-reference detection.

This split is the same pattern `ComponentEdgeValidator` uses for `components[].edges.{to,from}`. ADR-018 documents that surface; this ADR adopts the same boundary for risks.

### D4. Prose-field shape

Five fields are prose: `shortDescription`, `longDescription`, `examples`, `tourContent.introduced`, `tourContent.exposed`, `tourContent.mitigated`. Each is `$ref`'d to `riskmap.schema.json#/definitions/utils/text`, which constrains shape but not content.

[ADR-017](017-yaml-prose-authoring-subset.md) defines the canonical authoring subset (`**bold**`, `*italic*`/`_italic_`, sentinels) and the new pre-commit lint `validate-yaml-prose-subset` is the authoritative content enforcement point per [ADR-014](014-yaml-content-security-posture.md) P4. The schema does not duplicate the lint's grammar.

**ADR-017 D3 opt-in (the optional `<>()` reject pattern).** ADR-017 leaves it to each per-file schema ADR to opt into the optional schema-level pattern that rejects strings containing `<`, `>`, `(`, or `)` characters as a coarse second filter on top of the lint. This ADR **defers** the opt-in. Rationale:

- Risks prose currently contains parenthetical asides freely (`(direct or indirect)`, `(such as ...)`); rejecting `(` at schema level would force a stylistic rewrite of legitimate prose during the conformance sweep that is unrelated to the security posture.
- The lint runs on every commit; the schema-level reject is a defense-in-depth filter, not a primary defense. Skipping it costs nothing as long as the lint runs.
- The five other consumer schemas (controls, components, personas, mermaid-styles) are pending or in-flight; deferring lets the controls/components/personas ADRs decide independently and lets risks adopt the pattern later if the prose is rewritten.

If the conformance sweep's prose rewrite removes parenthetical asides as a side effect of converting `<a href>` to sentinels, this decision is revisited; otherwise the lint is sufficient.

**BLOCK-02 nested-list shape.** Three risks use the nested-array pattern (`- - >`) inside `longDescription` to express a sub-group:

```yaml
longDescription:
  - >
    Top-level paragraph.
  - - >
      Nested item one (renders as a bulleted sub-group).
    - >
      Nested item two.
  - >
    Another top-level paragraph.
```

The shape is the prose-shape invariant from BLOCK-02 (`a66128d`) and lives in `persona-site-data.schema.json#/definitions/prose` per [ADR-011](011-persona-site-data-schema-contract.md). Today the *input* schema (`riskmap.schema.json#/definitions/utils/text`) is more permissive than the *output* schema; an authoring bug that produced two-deep nesting would pass `risks.schema.json` validation and then trip `persona-site-data.schema.json` validation when the persona-site builder ran.

The conformance sweep tightens `riskmap.schema.json#/definitions/utils/text` (or introduces a more constrained sibling) to match the output shape — `array` of `string | array<string>`, one level of nesting maximum, `array<string>` items must contain at least one element. The tightening is owned by the conformance sweep, not by this ADR; this ADR records the decision that the input/output gap closes in the sweep.

The ADR-017 lint walks prose strings inside both top-level array items and one-level-nested array items; the nested-list shape remains the only authoring-time list primitive per [ADR-017](017-yaml-prose-authoring-subset.md) D2.

### D5. Framework-mapping fields (`mappings.*`)

`mappings` is currently:

```json
{
  "type": "object",
  "propertyNames": { "$ref": "frameworks.schema.json#/definitions/framework/properties/id" },
  "additionalProperties": {
    "type": "array",
    "items": { "type": "string" }
  }
}
```

Property names (e.g., `mitre-atlas`, `stride`, `owasp-top10-llm`) are validated against `frameworks.schema.json`. The values are open string arrays. There is **no per-framework regex** on the mapping IDs today, so `AML.T0020`, `aml-t0020`, `AML T0020`, and `T0020` all pass.

Per-framework rationale fields (a sentence explaining *why* `riskDataPoisoning` maps to MITRE ATLAS technique `AML.T0020`) do not exist on any framework today. The current shape is taxonomy-ID-only.

**Conformance-sweep tightening.** The conformance sweep adds per-framework ID patterns to the schema. Each canonical framework (MITRE ATLAS, STRIDE, OWASP LLM Top 10, NIST) gets a per-key regex. The patterns live in a new `definitions/framework-mapping-patterns` block inside `frameworks.schema.json` (single-source-of-truth, same pattern as `external-references.schema.json` from [ADR-016](016-reference-strategy.md) D3) and are applied via `propertyNames` + per-property `items.pattern` constraints. The tightening is **schema-only** and does not require validator changes; it is a conformance-sweep deliverable, not an in-ADR architectural decision. This ADR records the gap and the planned tightening; the exact regexes are picked when the sweep authors the patterns.

Per-framework rationale fields are deliberately **not** added. A free-text rationale per mapping is prose, prose has the editorial-judgment problems [ADR-014](014-yaml-content-security-posture.md) P3 closes, and the same information lives in the risk's `longDescription` where citations live as `externalReferences` per ADR-016. If a future consumer needs structured rationale, it is a framework-content design question for `risk-map/docs/design/`, not a schema-uplift one.

### D6. Ghost-field retirement — `relevantQuestions`

`relevantQuestions` is defined at `risks.schema.json:83-86` as:

```json
"relevantQuestions": {
  "type": "array",
  "items": { "type": "string" }
}
```

Two risks populate it:

- `riskToolRegistryTampering` (`risks.yaml:1683-1686`, 3 questions)
- `riskToolSourceProvenance` (`risks.yaml:2071-2074`, 3 questions)

No generator reads it. `scripts/hooks/yaml_to_markdown.py` does not include it in any column. `scripts/build_persona_site_data.py` does not export it to the persona-site JSON. The `risk-map/diagrams/` Mermaid generators do not consume it. No `risk-map/docs/` page documents its purpose. The `controls.yaml` schema does have a top-level `questions` field with a different shape (per persona, used by the persona Pages MVP); risks' `relevantQuestions` is unrelated to that flow and predates it.

The field is **retired**. The conformance sweep:

1. Removes the `relevantQuestions` definition from `risks.schema.json`.
2. Removes the field from the two risk entries in `risks.yaml`.
3. The 6 questions across the two entries either land in the entry's `longDescription` prose as authored sentences (judged per-question by the content-reviewer agent), or are dropped if duplicative of existing prose.

Retirement is recorded here as a sub-deliverable of this ADR; the conformance sweep PR executes both the schema removal and the YAML cleanup in the same commit so a `check-jsonschema` run in either order does not fail.

### D7. `externalReferences` integration per ADR-016

Per [ADR-016](016-reference-strategy.md) D3, a new optional array-valued field `externalReferences` is added to the `risk` definition. The shape lives in a single shared schema at `risk-map/schemas/external-references.schema.json`; this consumer schema adds one `$ref` line:

```json
"externalReferences": { "$ref": "external-references.schema.json#/definitions/externalReferences" }
```

The field is **optional** at the risk-entry level. Empty arrays are rejected (per ADR-016 D3); risks that carry no citations omit the field.

Risks-specific concerns:

- **Volume.** Risks is the heaviest consumer of outbound citations in the framework. Approximately 55 outbound `<a href>` tags currently live in risks prose; after the conformance sweep they all migrate to `externalReferences` entries. A representative entry like `riskDataPoisoning` will carry roughly 4-6 entries (covering the arxiv papers, vendor advisories, and news articles cited in `longDescription` and `examples`). The largest entries (`riskSensitiveDataDisclosure`, `riskInsecureIntegratedComponent`) will likely carry 8-12. The shared schema's array shape handles this; no risks-specific min/max cap is added.
- **Required vs. optional.** Optional, consistent with controls/components/personas. Most risks have at least one citation; not every risk needs one (a few — `riskCovertChannelsInModelOutputs`, the newer agent-era risks — are conceptual enough that citations are always present, but the contract is "if present, well-formed").
- **Per-type frequency.** No type cap is enforced. Risks dominated by academic citations (`paper`) coexist with risks dominated by vendor advisories (`advisory`) and news incidents (`news`). The `editorial` type covers any "see also" pointer that doesn't underpin a specific claim.

The `$ref` integration is a **single-line schema edit** plus the shared-schema authoring (which ADR-016 D3 commits to as a deliverable owned by the conformance sweep). This ADR's scope is the integration declaration; the shared schema's authoring is owned by the sweep.

### D8. Other follow-ups from the discovery report

- **`title` is unbounded `string`.** No `maxLength`, no `pattern`, no required-prefix rule. In practice every risk title is 3-7 words, but a maliciously long title would pass schema validation and break Mermaid layout. The conformance sweep adds `"maxLength": 120` (chosen to accommodate the longest current title — `Federated/Distributed Training Privacy` plus headroom).
- **`tourContent` itself is not required.** The `required` array at line 153 lists `id, title, shortDescription, longDescription, category, personas, controls`. `tourContent` is optional, and 5 risks (the recently-authored agent-era ones: `riskAcceleratorAndSystemSideChannels`, `riskEconomicDenialOfWallet`, `riskFederatedDistributedTrainingPrivacy`, `riskAdapterPEFTInjection`, the original three-question entries) have inconsistent `tourContent` populations. Whether `tourContent` becomes required is a framework-content design question (`risk-map/docs/design/`), not a schema-uplift one. The schema continues to mark it optional; the content-reviewer agent flags missing `tourContent` during review.
- **`additionalProperties: false` on the risk object.** The schema today does **not** set `additionalProperties: false` on the `risk` definition. A typo'd field name (`shortDescritpion`) would silently pass and silently produce an empty rendered field. The conformance sweep adds `"additionalProperties": false` after `relevantQuestions` is retired and `externalReferences` is added; without that ordering a stray `relevantQuestions` would fail validation. This is the same strictness ADR-011 D1 applies to `persona-site-data.schema.json`'s top-level keys.
- **Top-level `description`.** The file's top-level `description` field at line 9 is `$ref`'d to `riskmap.schema.json#/definitions/utils/text` and is currently a 5-paragraph preamble that includes a nested-list shape. The same prose-shape concerns as D4 apply; the conformance sweep addresses both at once.

### D9. Per-rule machine-enforcement summary

| Rule | Mechanism | Status |
|---|---|---|
| D1 risk `id` is closed-enum | schema enum | Machine-enforced (existing) |
| D1 prose fields conform to `definitions/utils/text` shape | schema `$ref` | Machine-enforced (existing); tightened in conformance sweep (D4) |
| D1 prose content conforms to ADR-017 subset | `validate-yaml-prose-subset` lint | Machine-enforced (conformance sweep, ADR-017) |
| D2 `category` enum closed | schema enum | Machine-enforced (existing) |
| D2 `lifecycleStage`/`impactType`/`actorAccess` enum-or-literal | schema `oneOf` | Machine-enforced (existing) |
| D3 `personas`/`controls` are typed identifier arrays | schema `$ref` | Machine-enforced (existing) |
| D3 `controls` ↔ risk bidirectional integrity | `validate_control_risk_references.py` | Validator-enforced (existing) |
| D3 `personas` resolve to known persona IDs | schema `$ref` to `personas.schema.json` | Machine-enforced (existing) |
| D4 prose nesting depth ≤ 1 | output schema (`persona-site-data.schema.json`); input tightened in conformance sweep | Partially machine-enforced (output); input tightened in sweep |
| D4 ADR-017 `<>()` schema reject pattern | not adopted | Deferred (D4 rationale) |
| D5 `mappings` property names resolve to known framework IDs | schema `propertyNames` `$ref` | Machine-enforced (existing) |
| D5 per-framework mapping ID regex | not enforced today; added in conformance sweep | Deferred to sweep (D5) |
| D5 per-mapping rationale fields | not added | Decided against (D5) |
| D6 `relevantQuestions` retirement | schema removal + YAML cleanup | Conformance-sweep deliverable (D6) |
| D7 `externalReferences` shape | shared schema `external-references.schema.json` `$ref` | Machine-enforced (conformance sweep, ADR-016) |
| D7 `externalReferences` content (sentinel resolution, URL shape, type enum) | shared schema + `validate_prose_references.py` | Machine-enforced (conformance sweep, ADR-016) |
| D8 `title` `maxLength: 120` | schema constraint | Conformance-sweep deliverable (D8) |
| D8 `additionalProperties: false` on `risk` | schema constraint | Conformance-sweep deliverable (D8) |
| D8 `tourContent` required | not enforced; framework-content design question | Prose-only guidance |

Every content rule is machine-enforced or has a named conformance-sweep mechanism. The only "prose-only guidance" row is `tourContent` requiredness, which is deliberately a framework-content design question owned by `risk-map/docs/design/` rather than the schema.

## Alternatives Considered

- **Defer the per-file ADRs and tighten everything in a single conformance-sweep PR.** Rejected. The sweep PR is large enough already (relevantQuestions retirement + 55 citation migrations + 14 intra-document anchor migrations + nested-list tightening + per-framework mapping regexes). Without a per-file ADR recording the decisions, the sweep author re-derives the rationale for each tightening from scratch and the maintainer has no durable record of why a tightening was chosen. The ADR is the cheap part; the sweep does the work the ADR records.
- **Make `relevantQuestions` real instead of retiring it.** Rejected. The persona Pages MVP introduced a `questions` flow on `controls.yaml` that drives the per-persona explorer; that flow is the framework's mechanism for "questions about a topic." Adding a parallel risk-questions flow would duplicate the persona-site builder's logic and split where readers find guidance. The two existing risks' questions are valuable content, but they belong in `longDescription` prose as authored sentences (or in a `controls.yaml` entry's `questions` field if the question is properly a control question), not in a parallel field with no consumer.
- **Adopt ADR-017 D3's optional `<>()` schema reject pattern for risks immediately.** Rejected for risks; see D4. Risks prose carries legitimate parenthetical asides, and the ADR-017 lint is the authoritative enforcement point. The schema-level pattern is defense-in-depth; deferring it does not weaken the posture as long as the lint runs. Other per-file schema ADRs (controls, personas, components) decide independently.
- **Add per-framework mapping-rationale fields (`mappings.mitre-atlas[].rationale`).** Rejected. Free-text rationale per mapping ID is prose; prose belongs in `longDescription`. The schema would force every mapping to grow a string field, most of which would be empty or duplicative of the surrounding prose. Framework cross-walks are taxonomy-ID-only by design.
- **Make `externalReferences` required on every risk.** Rejected. Most risks need at least one citation, but the conceptual risks (a few of the agent-era and side-channel ones) are legitimately citation-free at authoring time. Required-on-every-risk would force authors to add a citation that doesn't underpin a claim, which is exactly the editorial-judgment problem [ADR-016](016-reference-strategy.md) D3's `editorial` type was supposed to *avoid* generalizing.
- **Tighten `riskmap.schema.json#/definitions/utils/text` in this ADR rather than deferring to the sweep.** Rejected. The shared definition is consumed by every YAML schema (controls, personas, components, mermaid-styles); tightening it from a per-file risks ADR would commit decisions affecting four other surfaces without their ADRs being authored. The conformance sweep is the right scope; this ADR records the decision that the input/output prose-shape gap closes there.

## Consequences

**Positive**

- **Risks schema is now documented as a unit.** Future readers find every field's class, every enforcement layer, every gap, and every conformance-sweep deliverable in one place. The 28-risk-id enum, the five-category enum, the four `oneOf`-shaped taxonomy enums, and the open `mappings` object are no longer institutional knowledge.
- **Ghost field retirement is durable.** `relevantQuestions` was an institutional-memory liability; two recent contributors expended effort to populate a field nobody read. The retirement decision is recorded; the sweep removes the field; future contributors do not re-discover it as "looks like something I should fill in."
- **`externalReferences` integration is decoupled from the citation-count work.** Risks is the largest citation consumer (~55 entries). The shared-schema pattern from [ADR-016](016-reference-strategy.md) D3 means risks' integration is one `$ref` line plus the sweep's content migration — not a per-file regex authoring task that risks-specific concerns would force.
- **The schema-vs-validator boundary is explicit.** D3's split (schema for shape, validator for cross-file integrity) names a pattern that `ComponentEdgeValidator` already uses for components and that ADR-018 documents in parallel for components. Future per-file schema ADRs (controls, personas) inherit the same boundary.
- **Conformance-sweep scope is enumerated.** The sweep PR has a checklist: retire `relevantQuestions`, add `externalReferences` `$ref`, add `additionalProperties: false`, add `title.maxLength`, add per-framework mapping-ID patterns, tighten `definitions/utils/text` to match output prose shape. Without this ADR, that checklist would be re-derived during sweep authoring.

**Negative**

- **The conformance-sweep PR for risks is the largest of any per-file schema sweep.** 55 citation migrations + 14 intra-document anchor migrations + ~41 bare-ID sentinel conversions + 2 `relevantQuestions` cleanups + 5-6 schema tightenings. The sweep is real work and likely warrants splitting (citations + sentinels in one commit, schema tightening in another). The split is a sweep-execution concern, not an ADR concern.
- **Deferring the ADR-017 D3 schema reject means risks lacks a defense-in-depth filter that other per-file schemas may adopt.** If the lint regresses (a hook bypass, a `--no-verify` commit), risks prose has only the lint as a barrier; controls/components/personas may have schema-level `<>()` rejection on top. This is a small asymmetry acceptable as long as the lint is reliable; if the lint regresses repeatedly, the deferral is revisited.
- **Per-framework mapping-ID regex is deferred.** The conformance sweep authors the patterns; until that lands, `AML.T0020` and `AML T0020` and `aml-t0020` continue to pass schema validation. Content-reviewer is the human enforcement layer in the meantime.
- **`relevantQuestions` retirement leaves 6 questions to triage.** The two affected risks each have 3 questions that have not yet been folded into prose or migrated to `controls.yaml` `questions` fields. The triage is content work; the content-reviewer agent owns the call per question.
- **The `mappings` open-string-array shape is preserved.** A schema that constrained the values more tightly would catch typos earlier, but it would also block the framework from adopting a new mapping target without a schema edit. The current loose shape favors framework agility; the per-key regex tightening (D5) is the surgical compromise.
- **`tourContent` requiredness stays a framework-content design question.** Five risks have inconsistent `tourContent` populations today. The schema continues to allow that; the content-reviewer agent flags it; a future framework-content ADR may decide to make `tourContent` required and force a content sweep.

**Follow-up**

- **Conformance sweep — risks-specific deliverables.** A coordinated commit (or sequence) that:
  1. Adds `risks.schema.json` `externalReferences` `$ref` line per D7 (depends on `external-references.schema.json` being authored first per [ADR-016](016-reference-strategy.md)).
  2. Removes `relevantQuestions` from `risks.schema.json` and from `riskToolRegistryTampering` and `riskToolSourceProvenance` per D6; folds the 6 questions into `longDescription` prose or migrates them to `controls.yaml` `questions` fields per content-reviewer judgment.
  3. Adds `additionalProperties: false` to the `risk` definition per D8.
  4. Adds `"maxLength": 120` to `title` per D8.
  5. Tightens `riskmap.schema.json#/definitions/utils/text` (or introduces a sibling) to match the output prose shape per D4 (cross-file with controls/personas/components ADRs).
  6. Adds per-framework mapping-ID regex patterns to `frameworks.schema.json` per D5; the patterns themselves are picked during sweep authoring with the canonical-form discipline as input (`AML\.T\d{4}(\.\d{3})?` for ATLAS, etc.).
- **Content sweep — citation migration.** The 55 outbound `<a href>` tags in risks prose migrate to `externalReferences` entries with appropriate `type` values (`paper` for arxiv, `advisory` for vendor advisories, `news` for news articles, `cve` for the few CVE references, `editorial` for the "see also" links, etc.) per [ADR-016](016-reference-strategy.md) D3. Coordinated with the sweep above.
- **Content sweep — sentinel migration.** The 14 intra-document `<a href="#riskXxx">` anchors and ~41 bare-ID mentions migrate to `{{idXxx}}` sentinels per [ADR-016](016-reference-strategy.md) D2. Coordinated with the citation migration; same PR or sequential.
- **Sibling ADRs.** [ADR-018](018-components-schema.md) documents `components.schema.json`; [ADR-020](020-controls-schema.md) documents controls; [ADR-021](021-personas-and-self-assessment-schema.md) documents personas + self-assessment archive; [ADR-022](022-supporting-schemas.md) covers grouped supporting schemas. Each decides independently on the ADR-017 D3 opt-in question.
- **If a future risks-specific structured field is needed** (a `severity` enum, a `cve-cvss` numeric field, a `disclosure-status` taxonomy), it lands as a schema-edit PR that cites this ADR for the existing taxonomy and either fits into one of the five P2 classes or motivates a P2 revisit. Adding open prose fields is discouraged per [ADR-014](014-yaml-content-security-posture.md) P3.

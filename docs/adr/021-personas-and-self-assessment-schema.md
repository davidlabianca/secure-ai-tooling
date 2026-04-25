# ADR-021: `personas.schema.json` design and `self-assessment.yaml` archiving

**Status:** Accepted
**Date:** 2026-04-25
**Authors:** Architect agent, with maintainer review

---

## Context

`risk-map/schemas/personas.schema.json` is the JSON Schema (Draft-07) governing `risk-map/yaml/personas.yaml`. Personas is the smallest of the four primary content surfaces by entry count (10 entries), but it is the most heavily-consumed surface per entry: every active persona drives the persona-guided UX in the static SPA via `scripts/build_persona_site_data.py` (the producer that codifies the persona-site-data contract per [ADR-011](011-persona-site-data-schema-contract.md)), every persona is referenced as a structured target by `risks.yaml` and `controls.yaml`, and every persona is `$ref`-ed by name from `self-assessment.schema.json` and (per [ADR-016](016-reference-strategy.md) D6) by the future sentinel linter.

The personas surface has been actively reshaped. The original two-persona model (`personaModelCreator`, `personaModelConsumer`) was superseded by an eight-persona model that splits responsibilities across the AI lifecycle (Model Provider, Data Provider, AI Platform Provider, AI Model Serving, Agentic Platform and Framework Providers, Application Developer, AI System Governance, AI System Users). The two original personas are retained as `deprecated: true` for backward compatibility, giving the file a 10-entry shape: 8 current + 2 legacy. The schema's `id` enum (`personas.schema.json:22-33`) lists all 10; the `deprecated` flag (lines 37-41) is the marker that distinguishes legacy from current, with no schema-level partition between the two sub-sets.

Two pieces of related state matter to this ADR:

- **`risk-map/yaml/self-assessment.yaml` is locked to the legacy two-persona model.** `self-assessment.schema.json:28-31` constrains the persona-set `value` enum to `[1, 2]`, and `self-assessment.yaml:24-28` populates the two slots with `personaModelCreator: 1` and `personaModelConsumer: 2`. Every question in the file lists `personaModelCreator` and/or `personaModelConsumer` in its `personas` array; no question references any of the eight current personas. The schema's per-question `personas` array (`self-assessment.schema.json:53-56`) `$ref`s the personas-schema `id` enum, which means a contributor *could* add a question targeting a current persona — but the persona-set header at the top of the file would still only accept the two legacy IDs. The artifact is consistent only in the legacy model.
- **`risk-map/docs/contributing/identification-questions-style-guide.md` exists** and codifies the rules for `identificationQuestions` (5–7 questions per persona, second-person framing, scoping clauses, parenthetical examples with "e.g.", etc.). Neither `personas.schema.json` nor any pre-commit hook reads this guide. The guide itself notes "currently three of eight non-deprecated personas have them"; the remaining five gaps are content work, not schema work, but the systemic gap surfaced by the discovery report is that the *style* rules are prose-only with no machine check.

The discovery work that motivated this Phase 1 epic surfaced personas-specific gaps:

- **GAP-9 (BLOCKER) — `self-assessment.yaml` legacy persona lock.** Resolved here.
- **Identification-questions style consistency.** The style guide lives in prose only.
- **Persona ordering.** `personas.yaml` orders entries by lifecycle role (provider → developer → governance → user) with legacy entries last. The schema does not constrain order; the persona-site builder reads `active_personas` in source order and emits them to the SPA in that order. Order is therefore an authoring convention with a non-trivial UX consequence.
- **`identificationQuestions` shape.** The schema permits any non-empty string as a question item. The style guide's structure rules (count 5–7, yes/no answerability, second-person opener) are not encoded.
- **Framework mappings.** `mappings.iso-22989` populates 5 of 8 current personas with strings like `"AI Partner (data supplier)"` — free-form strings with parenthetical role qualifiers, not canonical IDs. The schema constrains the property name (framework ID) but not the value shape.

This ADR documents the schema's existing shape under [ADR-014](014-yaml-content-security-posture.md) P2's content-class taxonomy, declares per-rule machine-enforcement, threads in [ADR-016](016-reference-strategy.md)'s `externalReferences` `$ref` integration, and resolves GAP-9 with an archiving plan for `self-assessment.yaml`. It does not migrate any YAML or remove `self-assessment.yaml` from the repo; the conformance sweep executes the archiving against the decision recorded here.

## Decision

`personas.schema.json` is documented retroactively under the content-class taxonomy of [ADR-014](014-yaml-content-security-posture.md) P2, with the additions and retirements named below. `self-assessment.yaml` and `self-assessment.schema.json` are **archived as legacy artifacts** per D6. Sub-decisions follow the D-prefix convention.

### D1. Field taxonomy under ADR-014 P2

Every top-level field in the `persona` definition (and on the file-level `personas.yaml` envelope) maps to one of the five P2 content classes.

| Field | P2 class | Schema shape | Enforcement |
|---|---|---|---|
| `id` | identifier | closed `enum` of 10 camelCase IDs | schema |
| `title` | metadata | bare `string` | schema (type only) |
| `description` (file-level and per-persona) | prose | `$ref riskmap.schema.json#/definitions/utils/text` | schema (shape) + ADR-017 lint |
| `deprecated` | metadata | `boolean`, default `false` | schema |
| `mappings` | metadata (structured) | `propertyNames` `$ref` to `frameworks.schema.json` framework `id`; values are open string arrays | schema (key shape only) |
| `responsibilities` | prose (structured) | `array<string>`, `minLength: 1` per item | schema (shape) + ADR-017 lint |
| `identificationQuestions` | prose (structured) | `array<string>`, `minLength: 1` per item | schema (shape) + ADR-017 lint; style guide is prose-only (D7) |
| `personas` (file-level array) | structured reference | array of `persona` definitions | schema |
| `externalReferences` (planned, D5) | structured reference | `$ref` to shared `external-references.schema.json` | schema once D5 lands |

The schema currently carries no per-persona `version`, `lifecycleStage`, or `category` field. Personas do not participate in the per-category enums that risks and controls carry; the lifecycle-role grouping (provider / developer / governance / user) is an authoring convention reflected in source order, not a schema constraint. This asymmetry with risks and controls is intentional: the persona model is a small, stable taxonomy that does not benefit from a `category` partition. The asymmetry is documented here so a future contributor proposing `category: personasProviders` does not silently introduce one.

`responsibilities` and `identificationQuestions` are classified as **structured prose**: each is an array of single-string items with `minLength: 1`, not a `$ref` to `riskmap.schema.json#/definitions/utils/text` (which permits a nested-list shape). The single-string shape is correct for these fields — every item is a single sentence or noun-phrase, never a multi-paragraph block — and the existing schema constraint is exactly what the persona-site builder consumes (`build_persona_site_data.py:170-205`, where each item flows through `normalize_text_entries` and out to a flat string array per persona). No field-shape change is needed.

### D2. Identifier and enum decisions

The schema closes the persona identifier surface against typos by enumeration:

- **`persona.id`.** Closed enum at `personas.schema.json:22-33`, 10 values: `personaModelProvider`, `personaDataProvider`, `personaPlatformProvider`, `personaModelServing`, `personaAgenticProvider`, `personaApplicationDeveloper`, `personaGovernance`, `personaEndUser` (the 8 current) plus `personaModelCreator`, `personaModelConsumer` (the 2 legacy, marked `deprecated: true` in the YAML). Adding a new persona requires a schema edit and a content edit in the same PR — the same property risks/controls/components rely on for their identifier enums.

  **Closed vs. open.** The closed-enum form is chosen over an open `pattern: "^persona[A-Z][A-Za-z0-9]*$"` for the same reason every other identifier surface in the framework is closed-enum: cross-file references (`risks[].personas`, `controls[].personas`, `self-assessment.yaml` per-question `personas` arrays) all `$ref` this enum, and an open pattern would let a typo'd persona ID pass schema validation while never resolving in the persona-site builder's `active_persona_ids` set.

- **Current vs. legacy partition — convention, not schema.** The schema does **not** carry separate enums for "current personas" and "legacy personas." Both are members of a single `id` enum; the `deprecated: boolean` field on the persona definition is the marker. The persona-site builder filters out deprecated personas at runtime (`build_persona_site_data.py:108`, `active_personas = [persona for persona in personas_data["personas"] if not persona.get("deprecated")]`). No schema-level constraint enforces that a `risks[].personas` array references only current personas; today's content happens to comply, but a regression that added a deprecated persona reference would pass schema validation and silently propagate as a non-rendered link.

  **Decision.** Keep the single-enum + `deprecated` flag pattern. Rationale: (a) the `deprecated` flag is read by the existing builder and is the contract `self-assessment.yaml` archiving (D6) preserves for backward compatibility; (b) splitting the enum into `id-current` and `id-legacy` would force every consumer schema (risks, controls) to choose which enum to `$ref`, and the natural choice (`id-current`) would reject any pre-existing risk that legitimately references a legacy persona during the transition; (c) JSON Schema cannot express "a `risks[].personas` array may not reference an entry whose `deprecated` flag is true" without a cross-file conditional, so the constraint belongs in a validator if it lands at all (see D8).

  The conformance sweep does not split the enum. A future sweep that audits cross-file references for deprecated-persona drift is a candidate validator extension; this ADR scopes it as a follow-up rather than a Phase 1 deliverable.

- **`mappings` property names.** `propertyNames` `$ref`s `frameworks.schema.json#/definitions/framework/properties/id`, the same closed framework-ID enum risks and controls use. Personas inherits the framework single-source-of-truth pattern at zero additional cost.

### D3. Structured-reference fields — schema/validator boundary

Personas is a *target* of structured references, not a *source*. The fields that point *at* personas live on other content types:

- `risks[].personas` (`risks.schema.json`) — `$ref`s `personas.schema.json#/definitions/persona/properties/id`.
- `controls[].personas` (`controls.schema.json`) — same pattern.
- `self-assessment.yaml` per-question `personas` and per-header `label` (`self-assessment.schema.json:27`, `:55`) — same pattern; the `value` enum at `self-assessment.schema.json:30` is the field that *actually* constrains the persona set, since the per-question array's enum (via `$ref`) accepts all 10 IDs but only the two legacy IDs have `value` slots.

The schema/validator boundary on personas-related references:

- **Schema:** identifier shape, ID resolves to a known persona via the `$ref` to the personas `id` enum, array typing.
- **Validator (today):** none. There is no `validate_persona_references.py` analogue to `validate_control_risk_references.py`. Cross-file persona references rely on the schema's `$ref` to catch typos.

The schema-only enforcement is sufficient *today* because every cross-file persona reference is a single ID rather than a bidirectional edge — there is nothing to mirror, and a `$ref`-resolved enum value is either present or absent. The conformance sweep does **not** add a persona-references validator; the `$ref` chain is the contract. A future cross-file integrity check (e.g., "every active persona is referenced by at least one risk and at least one control") would be a coverage check, not a referential-integrity check, and belongs in a separate validator if the framework adopts that posture.

[ADR-016](016-reference-strategy.md) D6's `validate_prose_references.py` walks `personas.yaml` prose for sentinel resolution; that hook reads the personas `id` enum at hook load. Personas inherit the sentinel-resolution machinery without owning it.

### D4. Prose-field shape

Personas carries four prose-shaped fields. Three (`description`, `responsibilities`, `identificationQuestions`) are per-persona; the fourth (`description`) is at file level.

- **`description` (file-level and per-persona).** `$ref riskmap.schema.json#/definitions/utils/text` — `array<string | array<string>>`, one nesting level. Same shape as risks/controls/components. Today's content uses the top-level array form for paragraph splits (see `personas.yaml:36-45` for the Model Provider description's two-paragraph shape); no persona uses the nested-array form for sub-grouping. The shape is permissive but unused; the conformance sweep tightening of the shared `definitions/utils/text` (per ADR-019 D4) cascades to personas without a schema-side change.

- **`responsibilities`.** `array<string>` with `minLength: 1` per item. **Single-string shape, not the nested `definitions/utils/text` shape.** Every item is a single sentence or noun-phrase ("Model architecture design and training", "Data quality assurance"); the persona-site builder consumes them as a flat list (`build_persona_site_data.py:195`). The single-string constraint is correct and stays.

- **`identificationQuestions`.** `array<string>` with `minLength: 1` per item, same shape as `responsibilities`. Every item is a single yes/no question. The persona-site builder uses these to drive the persona-guided UX (`build_persona_site_data.py:171-185`), assigning each question a synthetic `{persona['id']}-q{index}` ID and surfacing it as a quiz prompt. The `GUIDED_QUESTION_THRESHOLD = 5` constant (`build_persona_site_data.py:25`) determines whether a persona enters the guided flow or falls back to manual selection — a persona with fewer than 5 questions is added to `manualFallbackPersonaIds`. This thresholding is the *only* identification-questions semantic the schema enforces by structural shape (the `minLength: 1` per item ensures each question is a non-empty string), and the threshold itself lives in the builder, not the schema.

  The style-guide rules (D7) — count 5–7, yes/no answerability, second-person framing, scoping clauses, parenthetical examples — are **not** encoded. This is the systemic gap discussed in D7.

**ADR-017 D3 opt-in (the optional `<>()` schema reject pattern).** ADR-017 leaves it to each per-file schema ADR to opt into the optional schema-level reject pattern. This ADR **defers** the opt-in. Rationale:

- Personas prose is the lightest of the four content surfaces. The 10 persona descriptions, 8 responsibilities lists, and 3 identification-questions arrays today contain no `<a>` tags, no `<strong>`/`<em>`, no inline URLs. The lint (per [ADR-017](017-yaml-prose-authoring-subset.md) D4) catches drift if it appears.
- `identificationQuestions` and the style guide explicitly *require* parenthetical asides for technical-term examples (e.g., "Do you modify existing models (e.g., distillation, quantization, or adaptation) for use by others?" at `personas.yaml:60`). A schema-level `(` reject would make the style guide's explicit guidance unauthorable. This is a stronger argument against the `(` reject than the one in ADR-018 (components defers because parentheticals are common-but-incidental); for personas the parentheticals are a documented authoring pattern.
- The optional pattern lives on the shared `definitions/utils/text` definition; personas defers in lockstep with components (ADR-018 D4) and risks (ADR-019 D4). Adopting it locally would either fork the shared shape (drift class) or only narrow the personas schema while leaving the others untouched. The sweep-wide call is the right scope.

The position aligns with ADRs 018, 019, and (per coordination) 020: defer the optional `<>()` schema reject, rely on the lint, revisit if the sweep adopts the pattern globally.

### D5. `externalReferences` integration

Per [ADR-016](016-reference-strategy.md) D3 (revised), `personas.schema.json` is included alongside risks, controls, and components as a `$ref` consumer of the shared `risk-map/schemas/external-references.schema.json`. The conformance sweep adds an optional `externalReferences` field to the `persona` definition by `$ref`:

```json
"externalReferences": { "$ref": "external-references.schema.json#/definitions/externalReferences" }
```

The field is **optional** at the persona-entry level. Empty arrays are rejected (per ADR-016 D3); personas with no citations omit the field.

**Personas-specific concerns.**

- **Volume.** Personas prose carries no outbound citations today. The 10 persona descriptions are taxonomic and self-contained; the existing `<a href="risks.html">` and `<a href="controls.html">` cross-page links in the file-level `description` (`personas.yaml:18-22`) are intra-document anchors that migrate to `{{idXxx}}` sentinels per [ADR-016](016-reference-strategy.md) D2 and do not become `externalReferences`. The most likely future citations are framework-mapping references (e.g., a paper-style citation underpinning the choice to map `personaDataProvider` to `iso-22989: AI Partner (data supplier)`), but adding those is a content decision, not a schema obligation.

- **Required vs. optional.** Optional, consistent with risks/controls/components. The shared schema's array shape and per-type regex coverage are sufficient; no personas-specific minimum is appropriate.

- **No personas-specific `type` clause.** Personas does not need a narrower `type` enum than the shared schema enforces. The shared `editorial`, `paper`, `spec` types cover every plausible persona citation.

**Co-evolution.** ADR-016 D3 commits the shared schema's authoring to the conformance sweep. This ADR's `$ref` integration is a single-line schema edit that lands in the same sweep PR.

### D6. Self-assessment archiving — GAP-9 resolution

This is the load-bearing decision in this ADR. `self-assessment.yaml` and `self-assessment.schema.json` are **archived as legacy artifacts**, not migrated to the new persona model and not replaced with a successor in this ADR's scope.

**State of the artifact today.** `self-assessment.yaml` encodes a two-persona quiz: 12 questions, each with `Yes`/`No`/`Maybe` answer values and a `personas` array drawn from `[personaModelCreator, personaModelConsumer]`. The schema's `personas.answers[].value` enum at `self-assessment.schema.json:30` is `[1, 2]`, which structurally hard-codes the two-persona model: adding a third persona slot requires a schema edit (extend the enum) plus a content edit (add a third `label`/`value` entry plus update every question's `personas` array). The question text references "Generative AI" specifically, which predates the broader AI/ML scope the eight-persona model covers (e.g., `personaModelProvider`'s description explicitly includes "classical ML, statistical, optimization, and rule-based models").

**Consumer survey.** No code path consumes `self-assessment.yaml`. `scripts/build_persona_site_data.py` does not read it (the file is not in `DEFAULT_PERSONAS_PATH` / `DEFAULT_RISKS_PATH` / `DEFAULT_CONTROLS_PATH` and is not loaded). `scripts/hooks/yaml_to_markdown.py` does not generate a table for it (no `risk-map/tables/self-assessment-*.md` exists). `scripts/hooks/validate_riskmap.py` does not validate it. The pre-commit framework's `check-jsonschema` hook does include it (the file is matched by the YAML-pattern hook and validated against `self-assessment.schema.json`), so the file does pay a validation cost on every commit — but no downstream consumer reads its content. The artifact is currently **shape-validated dead weight**, with the additional liability that its persona model is incompatible with the framework's current persona model.

**Options considered.**

1. **Archive — keep the artifact for historical reference, mark as deprecated, do not maintain.** Both `self-assessment.yaml` and `self-assessment.schema.json` move under a `risk-map/yaml/archive/` (or similar) subdirectory, with a top-level `_archived: true` flag (or an explicit prose note in the file header). Schema validation continues against a frozen schema; no cross-references to the current persona model are added. Future content updates do not touch the file.

2. **Migrate to the new persona model.** Expand the `value` enum from `[1, 2]` to `[1, 2, 3, 4, 5, 6, 7, 8]` (or `[1..8]` declared per persona ID), restructure the persona-set header to list all 8 current personas, and rewrite every question to reference the appropriate current personas. Significant content rewrite (12 questions × 8 personas of relevance analysis, plus the framework-wording shift from "Generative AI" to the broader AI scope). High cost, no current consumer.

3. **Replace with a successor artifact.** Design a new `risk-map/yaml/persona-self-assessment.yaml` (or similar) that fits the eight-persona model from scratch, with its own schema; deprecate the legacy file. Lowest re-use of existing question text; cleanest break with the legacy shape. Same content cost as Option 2 plus the design cost of the new schema.

4. **Combined: archive the legacy artifact and design a successor.** The cleanest path if the self-assessment concept is still valuable but the legacy shape is not. Defers the successor design to a future ADR.

**Decision: Option 1 — archive.** Rationale:

- **No current consumer.** No code reads the artifact. The persona-site builder does not consume it; the table generator does not emit a derived artifact for it; the validators do not enforce cross-references against it. Migration cost is paid for zero downstream rendering benefit.
- **Persona-site builder is the framework's current self-assessment surface.** The persona-guided UX in the static SPA — driven by `identificationQuestions` per-persona — *is* the self-assessment for the eight-persona model. The persona explorer takes a reader's yes/no answers to identify which persona(s) apply and surfaces the relevant risks and controls. This is the same shape `self-assessment.yaml` was reaching for in the legacy model, implemented differently and against the current persona set. A successor artifact would duplicate the persona-explorer's job.
- **The legacy quiz is content of historical value.** The 12 questions encode legacy framing that may be useful as input for future content work (an authoritative "Gen-AI specific" quiz for the legacy two-persona model is itself a fact of the framework's history). Archiving preserves it under a clear `legacy` marker; deletion would destroy the artifact and the institutional memory.
- **Successor design is out of scope here.** A successor artifact (Option 3 or the second half of Option 4) is a framework-content design decision: what does the eight-persona-era self-assessment look like, and is it the persona-site explorer or a distinct artifact? That decision belongs in `risk-map/docs/design/` per [ADR-014](014-yaml-content-security-posture.md)'s scope rule, not in this tooling-side ADR. If the successor design ultimately concludes the persona-site explorer *is* the successor, no new artifact is authored; if it concludes a new artifact is needed, that artifact's schema is the subject of a future ADR. Either way, archiving the legacy artifact is the right immediate step.

**Archive mechanics (executed by the conformance sweep).**

1. Move `risk-map/yaml/self-assessment.yaml` to `risk-map/yaml/archive/self-assessment-legacy.yaml`. Add a top-level `_legacy: true` and `_supersededBy: persona-explorer-ux` (or comparable marker) field; update the schema accordingly.
2. Move `risk-map/schemas/self-assessment.schema.json` to `risk-map/schemas/archive/self-assessment-legacy.schema.json`. Freeze the schema as-is; do not extend the `value` enum.
3. Update `.pre-commit-config.yaml` — the existing `check-jsonschema` hook continues to validate the archived files against the archived schema; the rule pattern matches the new path. Or, alternatively, exclude the archive subdirectory from the active hooks if the maintainer prefers; this is a sweep-execution decision rather than an architectural one.
4. Add a header note inside the archived YAML stating the deprecation, the date, the persona-site explorer as the active surface, and a pointer to this ADR. The persona-site builder is unchanged (it does not read the file in either location).
5. Update `risk-map/docs/` cross-references that mention the self-assessment artifact (if any) to point at the persona explorer or this ADR. Content-reviewer scope.

**Conformance-sweep deliverable.** The archive move lands in the same PR (or sequence) that completes the personas-related sweep work; it does not block the rest of the personas schema tightening.

### D7. Identification-questions style alignment

The style guide at `risk-map/docs/contributing/identification-questions-style-guide.md` codifies authoring rules for `identificationQuestions`:

1. Count 5–7 questions per persona (gap: currently 3 of 8 current personas have any).
2. Yes/no answerability; second-person framing (`Do you...`, `Are you...`, `Does your...`).
3. Activities not titles; scoping clauses for boundary-shared activities; parenthetical examples for technical terms with "e.g." (not "i.e."); 2–4 illustrative items per parenthetical.
4. Question ordering: distinguishing first, scope-expanding next, boundary-clarifying last.
5. Anti-patterns: overlapping questions, title-only questions, embedded conditionals, leading questions, exhaustive parenthetical catalogs.

**None of these rules are machine-enforced today.** The schema's `array<string>` with `minLength: 1` per item is the only structural constraint. The systemic gap surfaced by the discovery report is that the style guide is prose-only with no machine check, which means drift (a question opens with "Would you say...", or a parenthetical lists 8 items, or a question asks about a job title) is invisible to the validator.

**Decision: machine-enforce the structural rules; keep the editorial rules prose-only.**

| Style-guide rule | Mechanism | Status |
|---|---|---|
| **Count 5–7 questions per persona (when present)** | new `validate-identification-questions.py` pre-commit hook | Phase 2 conformance-sweep deliverable; warn-only until coverage reaches 8 of 8 |
| **Each question is non-empty** | schema `minLength: 1` per item | Machine-enforced (existing) |
| **Second-person opener (`Do you`, `Are you`, `Does your`)** | new lint, regex match on prefix | Phase 2 conformance-sweep deliverable |
| **No exhaustive parenthetical catalogs (≤ 4 items between `(` and `)`)** | new lint, regex on parenthetical bodies | Phase 2 conformance-sweep deliverable |
| **`e.g.` not `i.e.` for parentheticals** | new lint | Phase 2 conformance-sweep deliverable |
| **Activities not titles** | reviewer checklist, content-reviewer agent | Prose-only (editorial) |
| **Scoping clauses for boundary-shared activities** | content-reviewer agent | Prose-only (editorial) |
| **Question ordering (distinguishing first, boundary-clarifying last)** | content-reviewer agent | Prose-only (editorial) |
| **Anti-patterns (leading, embedded conditionals, overlapping)** | content-reviewer agent | Prose-only (editorial) |

The **structural** rules (count, opener prefix, parenthetical-list cardinality, e.g.-not-i.e.) are machine-checkable with a small amount of regex; the **editorial** rules (activities-not-titles, scoping-clause appropriateness, question ordering, leading-question detection) require judgment that a regex cannot adjudicate. The editorial rules stay with the content-reviewer agent and the existing reviewer checklist; the structural rules become a new pre-commit hook.

**Coordination with the existing `audit-identification-questions` skill.** The repository carries an existing skill that audits identification questions during content review. The new lint is the *machine-enforcement* layer; the skill is the *editorial-review* layer. They overlap on the structural rules — the skill is welcome to flag a count of 4 in its review output, and the lint is welcome to block the same count. The skill remains authoritative for the editorial rules.

**The `validate-identification-questions.py` hook (Phase 2 deliverable).** Pattern matches [ADR-013](013-site-precommit-hooks.md)'s pre-commit-hook conventions. Walks `personas.yaml`, reads the personas `id` enum from the schema, walks each non-deprecated persona's `identificationQuestions`, applies the four structural rules, blocks on violations. Ships in **warn-only** mode for the duration of the sweep (because the count-5-to-7 rule will fail today for 5 of 8 personas; the warn phase gives content authors time to write the missing questions); flips to block in the same commit that completes the personas-related sweep, including the gap-fill content. This staging mirrors [ADR-016](016-reference-strategy.md) D6's and [ADR-017](017-yaml-prose-authoring-subset.md) D4's warn-then-block staging patterns.

The hook is a personas-specific concern; it does not generalize to risks/controls/components style rules. A future per-content style guide (if one emerges) gets its own hook by the same pattern.

### D8. Other personas-specific follow-ups

Smaller personas-specific gaps surfaced by the discovery work, scoped to the conformance sweep or out of scope as named:

- **`mappings` value shape (minor).** Current values are free-form strings with parenthetical role qualifiers (`"AI Partner (data supplier)"`, `"AI Partner (infrastructure provider)"`, `"AI Partner (tooling provider)"`, all on `iso-22989` mappings). Risks and controls' equivalent `mappings.*` values are typically canonical-form IDs (`AML.T0020`); personas' values are prose role labels. ADR-019 D5 commits per-framework regex patterns for risks/controls mappings; personas does not benefit from the same patterns because the personas-side mapping values are role descriptors, not technique IDs. **Decision: defer.** The personas-side mapping shape is a framework-content design question (do personas map to canonical actor IDs, or to prose role labels?) and lives in `risk-map/docs/design/` rather than this ADR. The schema continues to allow open string arrays for personas mappings; the framework cross-walk for personas remains less rigorous than for risks/controls until the design question is resolved.

- **Persona ordering.** The persona-site builder reads personas in source order (`build_persona_site_data.py:108`). Today's ordering — providers first, governance and end-user last, legacy at the bottom — is the UX order. The schema does not constrain order; an author who reordered the entries would change the SPA's display order silently. **Decision: stays an authoring convention.** Encoding the order in the schema (e.g., via a per-persona `displayOrder: integer` field) is a content-model change owned by `risk-map/docs/design/`. The content-reviewer agent flags reordering during review; that is the enforcement layer.

- **Deprecated-persona reference enforcement.** The schema does not enforce that `risks[].personas` and `controls[].personas` arrays reference only non-deprecated personas. Today's content complies; a regression would be invisible to validation. **Decision: scope a follow-up validator.** A new `validate_persona_active_references.py` (or a check inside `validate_control_risk_references.py`) that fails when a structured persona reference points at a `deprecated: true` entry. Phase 2 conformance-sweep deliverable, separate from D6's archiving work.

- **Required `identificationQuestions`.** The schema marks `identificationQuestions` as optional. Today's content has 3 of 8 current personas with questions, 5 without. The style guide says "All non-deprecated personas should eventually have identification questions" — an aspirational rule, not an enforced one. **Decision: stays optional in the schema.** Making the field required-when-not-deprecated is a conditional constraint that JSON Schema can express (`if not deprecated then required: identificationQuestions`) but the content does not yet satisfy it; tightening the schema before the gap-fill content lands would block every commit. The style-guide gap-fill is content work owned by future PRs; once 8 of 8 current personas have questions, the schema can tighten in a coordinated commit.

- **`additionalProperties: false` on the persona object.** The schema today does **not** set `additionalProperties: false` on the `persona` definition. A typo'd field name (`identificationQuestion` singular, `responsabilities` misspelled) would silently pass and silently produce nothing in the persona-site builder's output. The Phase 2 sweep adds `"additionalProperties": false` to the `persona` definition. Coordinated with the analogous tightening in ADR-019 D8 for risks.

### D9. Per-rule machine-enforcement summary

| Rule | Mechanism | Status |
|---|---|---|
| D1 every field maps to a P2 class | this ADR, schema structure | Documentation (machine-enforceable rules per row below) |
| D2 `persona.id` is closed-enum (10 values) | schema enum | Machine-enforced (existing) |
| D2 `mappings` property names resolve to known framework IDs | schema `propertyNames` `$ref` | Machine-enforced (existing) |
| D2 `deprecated` is boolean | schema | Machine-enforced (existing) |
| D2 current vs. legacy partition | `deprecated: true` flag, no schema-level partition | Convention (deliberate per D2) |
| D3 cross-file persona references resolve to known IDs | schema `$ref` from risks/controls/self-assessment | Machine-enforced (existing) |
| D3 active-only persona references in cross-file arrays | recommended new validator | Phase 2 sweep deliverable (D8) |
| D4 prose shape (`description` `array<string \| array<string>>`) | `riskmap.schema.json#/definitions/utils/text` | Machine-enforced (existing); tightened in sweep per ADR-019 D4 |
| D4 `responsibilities`/`identificationQuestions` non-empty per item | schema `minLength: 1` | Machine-enforced (existing) |
| D4 prose content subset (markdown subset, no inline URLs) | `validate-yaml-prose-subset` ([ADR-017](017-yaml-prose-authoring-subset.md)) | Machine-enforced (Phase 2 sweep) |
| D4 sentinel-ID resolution in prose | `validate_prose_references.py` ([ADR-016](016-reference-strategy.md)) | Machine-enforced (Phase 2 sweep) |
| D4 schema-side `<>()` coarse reject on prose | `definitions/prose` pattern (optional) | Deferred (D4 rationale; aligned with ADRs 018/019) |
| D5 `externalReferences` shape | shared schema `external-references.schema.json` `$ref` ([ADR-016](016-reference-strategy.md)) | Machine-enforced once Phase 2 sweep lands |
| D6 `self-assessment.yaml` archived under `risk-map/yaml/archive/` | conformance-sweep file move + header marker | Phase 2 sweep deliverable |
| D6 `self-assessment.schema.json` frozen | conformance-sweep file move | Phase 2 sweep deliverable |
| D7 identification-questions count 5–7 (when present) | new `validate-identification-questions.py` lint | Phase 2 sweep deliverable; warn-only until 8/8 coverage |
| D7 second-person opener | new lint | Phase 2 sweep deliverable |
| D7 parenthetical cardinality ≤ 4, "e.g." not "i.e." | new lint | Phase 2 sweep deliverable |
| D7 activities-not-titles, scoping clauses, ordering, anti-patterns | content-reviewer agent + audit-identification-questions skill | Prose-only (editorial) |
| D8 `mappings` value shape | not enforced; framework-content design question | Prose-only (deferred to design) |
| D8 persona ordering | not enforced; authoring convention | Prose-only (editorial) |
| D8 `additionalProperties: false` on `persona` | schema constraint | Phase 2 sweep deliverable |
| D8 `identificationQuestions` required when not deprecated | not enforced today; revisit after gap-fill | Deferred (D8 rationale) |

Every machine-enforceable rule is enforced or has a named Phase 2 mechanism. The rows that resolve to "prose-only" are explicit editorial-judgment carve-outs (the four D7 editorial rules, the two D8 design questions) rather than rot-prone gaps.

## Alternatives Considered

- **Migrate `self-assessment.yaml` to the eight-persona model.** Rejected per D6. No current consumer reads the artifact; the persona-site explorer is the framework's current self-assessment surface; migration pays significant content cost (12 questions × 8 personas of relevance reanalysis) for zero downstream rendering benefit. The legacy artifact's value is as historical content, not as a maintained consumer surface.
- **Replace `self-assessment.yaml` with a new artifact in this ADR.** Rejected. Successor design is a framework-content design question — does the persona-site explorer suffice, or is a distinct quiz artifact needed? — that belongs in `risk-map/docs/design/`. This ADR archives the legacy and scopes the design question as out-of-scope future work.
- **Split the persona `id` enum into `id-current` and `id-legacy` sub-enums.** Rejected per D2. Splitting the enum would force every consumer schema (risks, controls, self-assessment) to choose which enum to `$ref`, and the natural choice (`id-current`) would reject any pre-existing reference to a legacy persona during the transition. The `deprecated: true` flag is the right marker; an active-only validator (D8) is the right tightening if it lands.
- **Encode the identification-questions style-guide rules in JSON Schema.** Rejected. The structural rules (count 5–7, second-person opener, parenthetical cardinality) are technically expressible in JSON Schema via `pattern` and `maxItems`/`minItems`, but the patterns are clearer as a per-rule lint, the count rule needs to ship warn-only until content catches up, and the editorial rules are not schema-expressible at all. A separate lint per ADR-013's pattern is the cleaner split.
- **Adopt the [ADR-017](017-yaml-prose-authoring-subset.md) D3 schema reject pattern on personas directly (without waiting for the shared `definitions/utils/text` decision).** Rejected per D4. Personas' `identificationQuestions` style guide explicitly *requires* parenthetical asides for technical-term examples; a schema-level `(` reject would make the documented authoring pattern unauthorable. Defer to the sweep-wide call; align with ADRs 018, 019, 020.
- **Add a structured `lifecycleRole` enum to personas.** Rejected as out of scope. The lifecycle-role grouping (provider / developer / governance / user) is implicit in source order and persona names today; encoding it in a schema field is a content-model change that belongs in `risk-map/docs/design/persona-design.md`. The schema asymmetry with risks/controls (which have `category` enums) is intentional and documented in D1.
- **Keep `self-assessment.yaml` in place but un-archived, with a deprecation header note only.** Rejected. The file's persona model is structurally incompatible with the framework's current model (locked `value: [1, 2]`); leaving it in `risk-map/yaml/` alongside the active YAML invites a future contributor to "fix" the inconsistency by editing the file rather than recognizing it is legacy. Moving it under `archive/` is the structural marker that makes the legacy status visible from the directory layout — the same property [ADR-010](010-site-repo-root-module-boundary.md) relies on for the site/risk-map module boundary.
- **Defer D6 to a separate framework-content ADR in `risk-map/docs/design/`.** Rejected. The decision to archive vs. migrate vs. replace is a tooling-side decision (it touches schema files, validators, pre-commit configuration, file layout), not a framework-content decision. The successor-artifact design — *if* one is authored — is the framework-content question, and that is correctly deferred to `risk-map/docs/design/` per D6's rationale. This ADR archives; the future ADR (if any) designs.

## Consequences

**Positive**

- **Personas schema is documented as a unit.** D1's table is the lookup a future contributor uses to know whether a new persona-side field belongs in identifiers, structured references, prose, or metadata. The 10-id closed enum, the framework-keyed `mappings`, the structured-prose `responsibilities`/`identificationQuestions` shape, and the file's lack of a `category` partition are no longer institutional knowledge.
- **GAP-9 is resolved.** `self-assessment.yaml` is no longer dead weight in the active YAML directory carrying a persona model incompatible with the rest of the framework. The archive move makes the legacy status visible from the directory layout; future contributors do not waste effort migrating an artifact with no consumer.
- **Identification-questions style alignment is concrete.** D7 names which rules become machine-enforced and which stay editorial. The systemic gap from #8 discovery — style guide that nothing reads — closes for the structural rules; the editorial rules stay where they belong (with the content-reviewer agent and the existing skill). A future contributor adding an identification question sees a lint failure on a 4-item parenthetical list rather than a silent merge.
- **Cross-ADR alignment is explicit.** Personas defers the ADR-017 D3 opt-in in lockstep with ADRs 018, 019, 020 (the four per-file schema ADRs land with consistent positions on the same shared optional pattern). The sweep-wide call applies to all four at once or to none.
- **The `externalReferences` integration is unambiguous.** D5 declares the `$ref` line and the optional posture; the conformance sweep PR has no degrees of freedom on shape (it inherits from [ADR-016](016-reference-strategy.md)).
- **Discovered gaps have named owners.** The deprecated-persona-reference gap (D8), the `additionalProperties: false` gap (D8), the mappings-value-shape gap (D8), and the persona-ordering gap (D8) are scoped to the conformance sweep with a recommended enforcement layer or a deliberate prose-only carve-out, rather than left as ambient backlog.

**Negative**

- **Conformance-sweep work for personas is now committed.** The deliverables: the `externalReferences` `$ref`, `additionalProperties: false` on the persona definition, the `validate-identification-questions.py` lint, the self-assessment archive move, and (separately) the deprecated-persona-reference validator. The personas slice of the sweep is smaller than risks (which carries 55 citation migrations) but larger than components (which is mostly settled).
- **Successor-artifact design is deferred, not decided.** D6 archives the legacy quiz but does not author a successor. If the framework's eventual conclusion is "the persona-site explorer is the successor," nothing further is needed; if the conclusion is "a distinct quiz artifact is needed," that is a future ADR that this ADR has not pre-empted. A reader who expects a successor in this ADR will not find one.
- **The identification-questions lint flips to block only after content catches up.** The count-5-to-7 rule today fails for 5 of 8 current personas. The lint ships warn-only and flips to block in the sweep-closing commit, which means the content gap-fill (writing missing questions for `personaDataProvider`, `personaModelServing`, `personaApplicationDeveloper`, `personaGovernance`, and the inferred fifth gap) is on the critical path of the sweep. Per the style guide, that is content work for a separate PR; it gates the lint flip.
- **The single-enum + `deprecated`-flag pattern leaves cross-file deprecated-persona references undetected today.** The schema accepts a `risks[].personas: [personaModelCreator]` reference that propagates a deprecated persona into the active surface. Today's content complies; a regression would be invisible. The follow-up validator (D8) is recommended but is a separate deliverable from this ADR.
- **Defer-on-`<>()` is a soft commitment.** Same posture as ADRs 018, 019, 020; if the conformance sweep adopts the pattern globally, personas inherits; if the sweep declines, personas stays as-is. The ADR pins the deferral, not the eventual outcome.
- **The archive move changes the directory layout.** A `risk-map/yaml/archive/` (or comparable) subdirectory is new. Tools that walk `risk-map/yaml/` for content need to know to skip it (or to handle archived content explicitly). The pre-commit framework's path patterns may need updating; the content-reviewer agent may need updating; redistributors that ingest the YAML directly may need to be told the archive subdirectory is not active framework content. Each of these is small individually; collectively they are a coordination cost.

**Follow-up**

- **Phase 2 conformance sweep — personas-specific deliverables.** A coordinated commit (or sequence) that:
  1. Adds `personas.schema.json` `externalReferences` `$ref` line per D5 (depends on `external-references.schema.json` being authored first per [ADR-016](016-reference-strategy.md) D3).
  2. Adds `additionalProperties: false` to the `persona` definition per D8.
  3. Authors `scripts/hooks/precommit/validate_identification_questions.py` per D7 (Python, TDD via the testing agent per [ADR-005](005-pre-commit-framework.md) / [ADR-013](013-site-precommit-hooks.md) patterns). Ships warn-only; flips to block in the sweep-closing commit, after the content gap-fill (below) lands.
- **Phase 2 conformance sweep — self-assessment archive (D6).** Move `self-assessment.yaml` to `risk-map/yaml/archive/self-assessment-legacy.yaml`. Move `self-assessment.schema.json` to `risk-map/schemas/archive/self-assessment-legacy.schema.json`. Add header markers (`_legacy: true`, supersession pointer to this ADR). Update `.pre-commit-config.yaml` to validate (or exclude) the archived files. Update `risk-map/docs/` cross-references.
- **Content sweep — identification-questions gap-fill.** Author 5–7 questions each for `personaDataProvider`, `personaModelServing`, `personaApplicationDeveloper`, `personaGovernance`, and any other current persona without questions. Per the style guide. Content-reviewer agent owns the review; the existing `audit-identification-questions` skill is the editorial gate. Lands before the lint flips to block.
- **Phase 2 conformance sweep — deprecated-persona reference validator (D8).** A new check (in `validate_control_risk_references.py` or a sibling) that fails when `risks[].personas` or `controls[].personas` references a `deprecated: true` persona. TDD. Ships block-mode from day one (today's content already complies).
- **Epic follow-up — formal removal of the two legacy personas.** Sequenced strictly **after** the self-assessment archive (D6) lands, since `self-assessment.yaml`'s `value: [1, 2]` persona-set enum is the only remaining hard dependency on the legacy IDs. Once the archive is complete and the deprecated-persona reference validator (above) confirms no active risk/control content references the legacy IDs, a follow-up PR removes `personaModelCreator` and `personaModelConsumer` from `personas.yaml`, removes them from the `personas.schema.json` `id` enum (changing the closed enum from 10 values to 8), and clears any remaining cross-references. The removal is a single coordinated commit touching the schema and the YAML. This work is **out of the current epic's Phase 2 scope** — the epic archives the self-assessment and lands the validator; legacy-persona removal is the clean follow-on once both are in place. Track it as a separate issue or roll into the next content-sweep cycle per maintainer preference.
- **Successor self-assessment design (deferred).** If the framework concludes that the persona-site explorer is *not* a sufficient successor for the legacy quiz, a future framework-content ADR in `risk-map/docs/design/` designs the successor artifact and a future tooling-side ADR adds its schema. This ADR does not pre-empt either decision; it archives the legacy and clears the path.
- **`definitions/utils/text` schema-pattern call (sweep-wide).** The optional `<>()` reject pattern in [ADR-017](017-yaml-prose-authoring-subset.md) D3 lives on the shared `riskmap.schema.json#/definitions/utils/text`. A sweep-wide decision applies to risks, controls, components, and personas at once. If adopted, personas inherits via the existing `$ref` with no further edit.
- **Persona-design framework-content ADR (out of this ADR's scope).** Open questions on `mappings` value shape (D8), persona ordering (D8), `lifecycleRole` enum (alternative considered), and successor self-assessment design (D6) all belong in `risk-map/docs/design/persona-design.md` rather than `docs/adr/`. Tracked as a separate concern; this ADR records the deliberate split.

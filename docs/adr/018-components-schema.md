# ADR-018: `components.schema.json` design and tradeoffs

**Status:** Accepted
**Date:** 2026-04-24
**Authors:** Architect agent, with maintainer review

---

## Context

`risk-map/schemas/components.schema.json` is the JSON Schema for `risk-map/yaml/components.yaml`. It describes the component graph at the centre of the CoSAI Risk Map: 27 component IDs grouped under three top-level categories (`componentsInfrastructure`, `componentsModel`, `componentsApplication`) and four subcategories (`componentsModelTraining`, `componentsData`, `componentsAgent`, `componentsOrchestration`), with a directed bidirectional edge graph (`edges.{to,from}`) connecting them. The schema is already strict on identifiers (closed enums on every ID-shaped field) and intentionally thin on prose (a single `riskmap.schema.json#/definitions/utils/text` `$ref` for free-text content). The validators at `scripts/hooks/riskmap_validator/` carry the cross-cutting integrity rules — bidirectional edge consistency, isolated-component detection, missing-target detection — that JSON Schema cannot express.

[ADR-014](014-yaml-content-security-posture.md) P2 names five YAML content classes (identifiers, structured references, prose, metadata, generated artifacts) and commits the framework to per-file schema work that maps each field into one of those classes. [ADR-016](016-reference-strategy.md) D3 commits every consumer schema to `$ref` a shared `risk-map/schemas/external-references.schema.json` for outbound citations. [ADR-017](017-yaml-prose-authoring-subset.md) D3 leaves an optional schema-side `<>()` reject pattern on prose fields as a coarse second filter to the authoring lint. None of those decisions has yet been threaded through `components.schema.json`. The Phase 1 Track A pair ADRs (this one for components, ADR-019 for risks) document the existing shape, declare per-rule machine enforcement, and scope the conformance-sweep edits.

The components schema is the most settled of the four content schemas. Identifiers are fully enum-closed; the schema/validator boundary on edges has been stable since the validator was extracted into `riskmap_validator/`. Two components-specific gaps remain: a `category`/`subcategory` cross-consistency hole (a component may declare a `subcategory` that is not nested under its claimed `category`), and an `edges` shape ambiguity (the `anyOf` on `to`/`from` permits empty-array combinations that the validator must then reject as isolated). Neither blocks the Phase 1 posture; both are candidates for the conformance sweep, scoped in D6.

A separate observation from the components data: the schema is **read-only of `riskmap.schema.json#/definitions/utils/text`** for prose, so changes to that shared definition propagate automatically. There is no duplicated prose definition to drift.

## Decision

The components schema documents, with this ADR, the seven decisions below. The schema is mostly settled; the load-bearing additions are the `externalReferences` `$ref` (D5), the optional prose-pattern opt-in (D4), and the conformance-sweep follow-ups (D6).

### D1. Field taxonomy under ADR-014 P2

Every top-level field on the component definition (and on the file-level `components.yaml` envelope) maps to exactly one P2 content class. The classes drive handling — identifiers and structured references are schema-enforced and authoritative; prose is shape-only at the schema layer and content-bounded by the lint per [ADR-017](017-yaml-prose-authoring-subset.md); metadata is short scalar; the file emits no generated-artifact fields directly.

| Field | P2 class | Schema shape | Enforcement |
|---|---|---|---|
| `id` (component, category, subcategory) | identifier | closed `enum` of camelCase IDs | schema |
| `category` (on component) | structured reference | `$ref` to `category.id` enum | schema |
| `subcategory` (on component) | structured reference | `$ref` to `subcategory.id` enum | schema |
| `edges.to`, `edges.from` | structured reference | array of `$ref` to component `id` enum | schema (membership) + validator (bidirectionality, isolation) |
| `title` | metadata | bare `string` | schema (type only) |
| `description` (component, category, subcategory, file) | prose | `$ref riskmap.schema.json#/definitions/utils/text` | schema (shape) + lint per [ADR-017](017-yaml-prose-authoring-subset.md) D4 |
| `categories`, `subcategory` (file-level arrays) | structured reference | array of `category` / `subcategory` definitions | schema |
| `components` (file-level array) | structured reference | array of `component` definitions | schema |
| `externalReferences` (planned, D5) | structured reference | `$ref` to shared `external-references.schema.json` | schema once D5 lands |

The schema currently carries no metadata fields beyond `title`. There is no `version`, `lifecycleStage`, `mappings`, or `deprecated` on components today. **Maintainer direction (2026-04-25): `mappings` is the exception.** The Phase 2 conformance sweep adds a `mappings` field to `components.schema.json` mirroring the existing `mappings` shape on risks/controls/personas, coordinated with [ADR-022](022-supporting-schemas.md) D5c which activates the `applicableTo: components` enum value on the framework side. Components-side gap and remediation are scoped in D6 / Follow-up below. The remaining absences (`version`, `lifecycleStage`, `deprecated`) stay; they are not catalog-style metadata and a future proposal would need its own ADR. The asymmetry framing in earlier drafts ("components do not participate in framework cross-walks, intentional") is superseded.

### D2. Identifier and enum decisions

The schema closes every identifier surface against author-side typos by enumeration:

- `category.id` — closed enum of three values: `componentsInfrastructure`, `componentsModel`, `componentsApplication`. Adding a category requires a schema edit. The Mermaid graph generator at `scripts/hooks/riskmap_validator/graphing/` has hardcoded category handling that does not automatically pick up new categories; the closed enum is the upstream pin that lets the generator stay coupled without silent drift.
- `subcategory.id` — closed enum of four values: `componentsModelTraining`, `componentsData`, `componentsAgent`, `componentsOrchestration`. Same closure rationale.
- `component.id` — closed enum of 27 component IDs. Schema-level uniqueness is implicit in `enum` semantics. A new component requires a schema edit and (per the validator) a paired edge in some other component's `edges`, since the validator rejects isolated components by default.
- `component.category` and `component.subcategory` — `$ref` to the category/subcategory `id` enum, so a component cannot claim a category or subcategory the file does not define. This is the schema's tightest internal consistency check; it does **not** check that the `subcategory` is declared under the `category` (see D6, GAP-14).

**Closed vs. open.** All three enums are closed — additions go through schema review. The components schema accepts the cost (a schema edit on every taxonomy expansion) in exchange for the property that every consumer of the schema (the validator, the Mermaid generators, the table generator, any downstream tool) sees the same taxonomy at the same time. An open `category`/`subcategory` field would let `components.yaml` introduce a category that the generator has not been taught to colour, which is exactly the drift class the closed enum exists to prevent.

### D3. Structured-reference fields — schema/validator boundary

`component.edges` is the canonical structured-reference field on components. The schema enforces *membership* — every `to`/`from` value is a valid component `id` — and a weak presence rule (`anyOf`: at least one of `to` or `from` must be declared, but either may be empty). Everything else lives in `ComponentEdgeValidator` at `scripts/hooks/riskmap_validator/validator.py`:

- **Bidirectionality.** If component A's `edges.to` lists B, then B's `edges.from` must list A. The validator builds forward and reverse edge maps and reports any mismatch (`validate_edge_consistency`, lines 112-152).
- **Isolation.** A component with empty `to` and `from` (or absent edges) is reported as isolated and fails validation by default (`find_isolated_components`, lines 80-93). The `--allow-isolated` flag downgrades this to a warning for ad-hoc work.
- **Missing targets.** A `to`/`from` ID that does not appear as a defined component fails validation (`find_missing_components`, lines 95-110). The schema enum already catches *typos* against the closed set; this validator check catches the case where the schema enum has been extended but the matching component definition has not yet been added.

The schema-validator boundary is deliberate: JSON Schema can express "every value is in this enum" and "at least one of these arrays is present"; it cannot express "the contents of array A on entity X must mirror the contents of array B on entity Y." The validator owns the bidirectional invariant; the schema owns the membership invariant. Per [ADR-014](014-yaml-content-security-posture.md) P2, both layers stay machine-enforced — neither devolves to prose-only guidance.

### D4. Prose-field shape and the optional ADR-017 D3 reject pattern

Component prose lives in four places: file-level `description`, per-category `description`, per-subcategory `description`, and per-component `description`. All four reference the same shared shape, `riskmap.schema.json#/definitions/utils/text` — `array<string | array<string>>`, one nesting level. The schema asserts shape only; content (which markdown tokens the strings may contain) is enforced by `validate-yaml-prose-subset` per [ADR-017](017-yaml-prose-authoring-subset.md) D4.

[ADR-017](017-yaml-prose-authoring-subset.md) D3 leaves a coarse `<>()` reject pattern on prose fields as an optional schema-level second filter — `<` and `>` catch raw HTML, `(` catches the `](` opening of a markdown link. The components schema **defers** opting in. Rationale:

- Components prose is comparatively quiet. The 27 component descriptions, three category descriptions, and four subcategory descriptions today contain no `<a>` tags, no `<strong>`/`<em>`, and no inline URLs — a sample inspection of `components.yaml` confirms this. The lint catches drift if it appears; the schema-side filter would be a second backstop with no current cases to backstop.
- The `(` reject would force authors to rephrase legitimate parenthetical asides. Components prose is technical and uses parentheticals freely (e.g., `(also known as inferences)` at `components.yaml:75-76`, `(a centralized model repository)` at line 236). A schema-level reject would block these; the lint's `](` pair check rejects only the markdown-link form, which is the actual safety target.
- The optional pattern lives on the shared `definitions/utils/text` definition, not on the components schema directly. Adopting it would affect every consumer of that shared definition (risks, controls, personas) at once, and that is a Phase 2 conformance-sweep call rather than a per-file decision. Components defers to the sweep; if the sweep adopts the pattern globally, components inherits it; if the sweep declines, components stays as-is.

The lint is the authoritative content layer for components prose either way. Deferring the schema pattern does not weaken the eventual posture.

### D5. `externalReferences` integration

Per [ADR-016](016-reference-strategy.md) D3, the conformance sweep adds an optional `externalReferences` field to each consumer schema by `$ref`-ing a new shared `risk-map/schemas/external-references.schema.json`. Components is one of the four consumers (alongside risks, controls, personas) and adopts the same `$ref` pattern.

Concrete edit (Phase 2): under `definitions/component/properties`, add a single line `"externalReferences": { "$ref": "external-references.schema.json#/definitions/externalReferences" }` and leave the property out of `required`. The shape — array of objects with `type`, `id`, `title`, `url`; the `type` enum and per-type `id` patterns — lives in the shared schema and is owned by [ADR-016](016-reference-strategy.md). This ADR does not redefine it.

**Component-specific posture.**

- **Optional, not required.** Components are structural primitives with short technical descriptions; few component entries today would carry citations. Most components will never have an `externalReferences` array. Required-with-`minItems: 1` would force authors to fabricate citations on component definitions that genuinely do not need them.
- **Empty arrays remain rejected.** [ADR-016](016-reference-strategy.md) D3 already constrains the shared definition so that an empty array fails validation; authors omit the field instead. Components inherits that without adding a redundant component-side constraint.
- **No component-specific scope clauses.** Components do not need a narrower `type` enum or a tighter URL constraint than the shared schema enforces. The shared schema is the right level of generality.

### D6. Existing follow-ups and ghost fields

Two components-specific gaps remain in the schema's current shape. Neither blocks Phase 1; both belong to the Phase 2 conformance sweep.

- **`category`/`subcategory` cross-consistency (major).** Today the schema enforces that `component.category` is a member of the category enum and `component.subcategory` is a member of the subcategory enum, but not that the `subcategory` is *nested under* the `category` in the file's declared hierarchy. A component with `category: componentsModel` and `subcategory: componentsData` would pass schema validation, even though `componentsData` is declared only under `componentsInfrastructure` (`components.yaml:52-64`). In practice no component has this drift today; the gap is a backstop class, not a current bug. JSON Schema cannot express the conditional cleanly without `if`/`then`/`else` or `oneOf` over `(category, subcategory)` pairs. The conformance-sweep call: either encode the pairs in the schema (verbose but machine-enforced) or add a check in `ComponentEdgeValidator` (lighter, follows the existing schema/validator boundary). This ADR recommends the validator route; it matches the precedent set for bidirectional edges and keeps the schema lean.
- **Empty-edges shape (minor).** The current `edges` `anyOf` permits `to: []` paired with `from` present, or vice versa, or both empty if either is the present-and-empty side of the `anyOf`. The validator's isolation check catches the both-empty case at the consequence level; the schema does not catch it at the syntactic level. Tightening: either require at least one of `to`/`from` to have `minItems: 1`, or move the check fully into the validator. The current state is benign — no entry has shipped with both arrays empty — but the schema's tolerance and the validator's reject can drift in the future. Conformance-sweep call: align with the validator (the validator already refuses isolation; the schema can stay generous) or pre-empt at the schema layer (`minItems: 1` on whichever side is required by the `anyOf`).

**Missing field — `mappings` on components (major; coordinated with [ADR-022](022-supporting-schemas.md) D5c).** `components.schema.json` does not declare a `mappings` field today, while `frameworks.schema.json:71-74`'s `applicableTo` enum includes `components`. The asymmetry was framed in earlier drafts as deliberate ("components do not participate in framework cross-walks"); maintainer direction (2026-04-25) supersedes that framing. The Phase 2 sweep adds `mappings` to the component definition mirroring the risks/controls/personas shape: `propertyNames` `$ref` to `frameworks.schema.json#/definitions/framework/properties/id` for the framework-ID closed enum; per-framework value patterns inherit from ADR-022 D5b; `additionalProperties: false`; the field is optional. The components-side addition coordinates with the framework-side enum activation in [ADR-022](022-supporting-schemas.md) D5c — the two ADRs land their parts of the change in the same conformance-sweep PR.

**No ghost fields on components.** Every other defined field on the components schema is read by at least one of the validator, the Mermaid generator, or the table generator. There is no analogue of risks' `relevantQuestions` ghost field on components.

### D7. Per-rule machine-enforcement summary

| Rule | Mechanism | Status |
|---|---|---|
| D1 every field maps to a P2 class | this ADR, schema structure | Documentation (machine-enforceable rules per row below) |
| D2 `category.id` / `subcategory.id` / `component.id` are closed enums | `components.schema.json` `enum` | Machine-enforced (existing) |
| D2 `component.category` / `component.subcategory` ref the category/subcategory `id` enum | schema `$ref` | Machine-enforced (existing) |
| D3 `edges.to`/`from` membership against component `id` enum | schema `$ref` | Machine-enforced (existing) |
| D3 at least one of `edges.to`/`from` present | schema `anyOf` | Machine-enforced (existing) |
| D3 bidirectional edge consistency | `ComponentEdgeValidator.validate_edge_consistency` | Machine-enforced (validator) |
| D3 isolated-component rejection (default) | `ComponentEdgeValidator.find_isolated_components` | Machine-enforced (validator) |
| D3 missing-target rejection | `ComponentEdgeValidator.find_missing_components` | Machine-enforced (validator) |
| D4 prose shape (`array<string \| array<string>>`) | `riskmap.schema.json#/definitions/utils/text` | Machine-enforced (existing) |
| D4 prose content subset (markdown subset, no inline URLs) | `validate-yaml-prose-subset` ([ADR-017](017-yaml-prose-authoring-subset.md)) | Machine-enforced (new, ADR-017) |
| D4 sentinel-ID resolution in prose | `validate_prose_references.py` ([ADR-016](016-reference-strategy.md)) | Machine-enforced (new, ADR-016) |
| D4 schema-side `<>()` coarse reject on prose | `definitions/prose` pattern (optional) | Deferred to conformance sweep |
| D5 `externalReferences` shape | `external-references.schema.json` `$ref` ([ADR-016](016-reference-strategy.md)) | Machine-enforced once Phase 2 lands |
| D6 `category`/`subcategory` nesting consistency | recommended: `ComponentEdgeValidator` | Conformance-sweep deliverable |
| D6 `edges` non-empty | recommended: `ComponentEdgeValidator` or schema `minItems` | Conformance-sweep deliverable |
| D6 `mappings` field on components (coordinated with [ADR-022](022-supporting-schemas.md) D5c) | `components.schema.json` (new field) + `frameworks.schema.json` (enum value already present) | Conformance-sweep deliverable |

Every rule above is machine-enforced or scheduled to become so under a named follow-up. There is no row that resolves to "documented in prose only"; the components schema does not carry guidance the validator does not own.

## Alternatives Considered

- **Open `category`/`subcategory` enums (allow new values without a schema edit).** Rejected. The Mermaid generator and the table generator both branch on the current closed values; an open enum would let `components.yaml` introduce a category the downstream code has not been taught to render. The closed enum is the upstream pin; opening it pushes the drift problem into the generator.
- **Encode `category`/`subcategory` nesting in the schema via `if`/`then`/`else` per-pair.** Rejected for now. JSON Schema can express `if (category == X) then (subcategory in {Y, Z})`, but the construction is verbose, hard to read, and brittle when a new subcategory lands. The validator route (D6) keeps the schema readable and follows the precedent set by `ComponentEdgeValidator` for cross-cutting integrity.
- **Require `externalReferences` on every component.** Rejected. Components are structural primitives; most do not warrant citations. Required-with-`minItems: 1` would force authors to fabricate references. Optional matches the actual usage pattern.
- **Adopt the [ADR-017](017-yaml-prose-authoring-subset.md) D3 schema reject pattern on the components schema directly (without waiting for the shared `definitions/utils/text` decision).** Rejected. The pattern lives on the shared definition; adopting it locally would either fork the shared shape (drift class) or only narrow the components schema while leaving risks/controls/personas untouched. The Phase 2 sweep is the right scope; deferring keeps the four schemas aligned by construction.
- **Move the bidirectional edge check into the schema (via JSON Schema's `not` and `contains` over the full file).** Rejected. The construction is theoretically possible but would require expressing every `(component, target)` pair as a schema constraint at file scope, which inverts the per-component definition shape and degrades validator performance. The Python validator is the right tool; the schema/validator split is intentional.
- **~~Add `mappings` to components for taxonomy cross-walks (mirror risks/controls).~~** Earlier drafts rejected this as out of scope. Maintainer direction (2026-04-25) overrides: the Phase 2 conformance sweep adds `mappings` to components mirroring the risks/controls/personas shape, coordinated with [ADR-022](022-supporting-schemas.md) D5c which activates the `applicableTo: components` enum value. Scoped in D6 / Follow-up; not deferred to a separate framework-content design ADR.
- **Defer all of D4-D6 to a single combined conformance-sweep ADR rather than declaring them here.** Rejected. The Phase 1 Track A pair ADRs (this one + ADR-019) document the *current* shape and *scope* the sweep; the sweep PR(s) implement what is scoped. Without this ADR, the sweep would be reasoning about the schema's intent from the schema alone, which is exactly the gap that motivated retroactive ADR work in Phase 0.

## Consequences

**Positive**

- **Field-level taxonomy is documented once.** D1's table is the lookup a future contributor uses to know whether a new components-side field belongs in identifiers, structured references, prose, or metadata. The classes are not re-derived per change.
- **The schema/validator boundary is explicit.** D3 names which checks live in JSON Schema and which live in `ComponentEdgeValidator`. A future change to either layer has a documented expectation to honour or revisit.
- **The `externalReferences` integration is unambiguous.** D5 declares the `$ref` line and the optional posture; the conformance-sweep PR has no degrees of freedom on shape (it inherits from [ADR-016](016-reference-strategy.md)).
- **The deferred schema reject pattern is decided, not silent.** D4 records why components defers the optional `<>()` filter and ties the eventual decision to the sweep's global call. A future contributor proposing the pattern locally sees the reasoning.
- **Discovered gaps have named owners.** The `category`/`subcategory` nesting consistency gap and the empty-edges shape gap (D6) are scoped to the conformance sweep with a recommended enforcement layer rather than left as ambient backlog.

**Negative**

- **Conformance-sweep work is now committed.** Three deliverables (the `externalReferences` `$ref`, the `category`/`subcategory` nesting check, the edges-shape tightening) land as part of the sweep PR(s). They are small individually; they are real work.
- **The `category`/`subcategory` closed-enum coupling stays.** Adding a new component category is a schema edit, a Mermaid generator update (the generator has hardcoded category handling that does not automatically pick up new categories), and a table generator review. The closed enum is the right call but it is not free.
- **The schema-validator split is durable but invisible.** A reader of `components.schema.json` alone cannot tell that bidirectional edges are enforced; they have to know about `ComponentEdgeValidator`. D3 makes the boundary explicit in this ADR, but the schema file itself stays terse. Future contributors who edit the schema without reading this ADR may misjudge what coverage they have.
- **Defer-on-`<>()` is a soft commitment.** If the conformance sweep chooses to adopt the schema-side reject globally, components inherits it; if the sweep declines, components stays as-is. The ADR does not pin a specific outcome — it declares the deferral is until the sweep settles.

**Follow-up**

- **Phase 2 conformance sweep — `externalReferences` `$ref`.** Add the single `$ref` line under `definitions/component/properties` once `risk-map/schemas/external-references.schema.json` lands per [ADR-016](016-reference-strategy.md). No content migration is required for components today (no current component carries an outbound URL); the field stays optional.
- **Phase 2 conformance sweep — `mappings` field on components (D6, coordinated with [ADR-022](022-supporting-schemas.md) D5c).** Add `properties.mappings` to the component definition mirroring the risks/controls/personas shape: `propertyNames` `$ref` to `frameworks.schema.json#/definitions/framework/properties/id`; per-framework value patterns inherit from [ADR-022](022-supporting-schemas.md) D5b; optional. Lands in the same sweep PR as the [ADR-022](022-supporting-schemas.md) D5c framework-side activation.
- **Phase 2 conformance sweep — `category`/`subcategory` nesting consistency.** Recommended: extend `ComponentEdgeValidator` with a `validate_taxonomy_nesting` check that asserts each component's `(category, subcategory)` pair matches a declared `category.subcategory[]` entry in the file's hierarchy. Tests via the testing agent per [ADR-005](005-pre-commit-framework.md) / [ADR-013](013-site-precommit-hooks.md) patterns.
- **Phase 2 conformance sweep — `edges` non-empty.** Recommended: tighten the validator's existing isolation check to also reject the syntactic case where one of `edges.to`/`from` is present-and-empty (the current isolation check is on the *both-empty* consequence). Alternative: schema-level `minItems: 1` on whichever array satisfies the `anyOf`; the maintainer's call.
- **`definitions/utils/text` schema-pattern call (sweep-wide).** The optional `<>()` reject pattern in [ADR-017](017-yaml-prose-authoring-subset.md) D3 lives on the shared `riskmap.schema.json#/definitions/utils/text`. A sweep-wide decision applies to risks, controls, components, and personas at once. If adopted, components inherits via the existing `$ref` with no further edit.
- **Mermaid generator decoupling (out of this ADR's scope).** `ComponentGraph` has hardcoded category handling that does not automatically pick up new categories. If a future ADR opens the category enum or refactors the generator, the components schema's closed enums are the upstream pin to revisit. Tracked as a separate concern.
- **`components.yaml` content fix (minor, content drift).** `componentApplicationInputHandling` description (`components.yaml:316-321`) appears copy-pasted from output handling — the prose says "Similar to input handling, output handling…" while the entry is itself the input-handling component. Out of scope for this ADR (content fix, not schema), but flagged so it does not get folded into the conformance sweep by accident.

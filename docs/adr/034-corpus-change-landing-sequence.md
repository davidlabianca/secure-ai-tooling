# ADR-034: Dependency-ordered landing sequence for risk-map corpus changes

**Status:** Draft
**Date:** 2026-07-09
**Authors:** Architect agent, with maintainer review

---

## Context

The risk-map corpus is a reference graph, and its edges constrain what can land when. Verified against the schemas, the edges are:

- `components ← controls` (`control.components`, `controls.schema.json:90-101`) and `components ← risks` (`risk.components` is expressed through the component edge model; components are referenced by controls and risks but carry no back-reference to them). Components are **referenced-only leaves**: `components.schema.json` defines no `controls` or `risks` property.
- `personas ← controls` (`control.personas`, `controls.schema.json:86-89`) and `personas ← risks` (`risk.personas`, `risks.schema.json:74-77`). Both reference `personas.schema.json#/definitions/persona/properties/id` and both are **required** array fields (`controls.schema.json:197`, `risks.schema.json:174`; the array may be empty). `personas.schema.json` defines **no** `risks` or `controls` property — a persona carries only `mappings`, `responsibilities`, `identificationQuestions`, and `externalReferences`. Personas are therefore **referenced-only leaves**, exactly like components: the reference is one-way, TO the persona, with no reciprocal back-link.
- One real cycle, `controls ↔ risks` (`control.risks` ↔ `risk.controls`, `controls.schema.json:102-113` and `risks.schema.json:86-89`).

A change that lands a referencing node before the node it references, or that lands one half of a reciprocal pair without the other, leaves the corpus in a broken intermediate state. Without a fixed landing order, two failure modes follow:

1. **Dangling references.** A referencing entity is landed before its referent exists. A new control that points at a not-yet-landed component, or a new risk that references a not-yet-landed peer risk, has nowhere correct to attach. For persona and component references, a dangling reference is caught at schema-validation time (both are closed id-enums, so a reference to an id not yet added fails `check-jsonschema`); the sequencing rule keeps the corpus from ever *reaching* that failing state on an intermediate merge.

2. **Late-checked integrity.** Landing an entire change-set as one monolithic PR defers every referential-integrity check to the end, blocks the whole set on any single contested entry, and produces a diff too large to review with confidence.

A **fixed, dependency-ordered landing sequence** — one that every corpus change follows — prevents both: it keeps the corpus validator-green at every intermediate merge and guarantees every reference has a target that already exists before the reference is introduced.

The scope is deliberately general. This ordering governs **any change that adds to or modifies the corpus**, whatever its size or origin: a hand-authored single-risk addition and a large batch derived from an external source document both obey the same sequence. A change-set may be produced by direct authoring (the usual path for small changes) or by the paper-decomposition pipeline, which is the maximal batch source — it exercises every layer at once. The pipeline decides *what* changes; it does not change *the order in which those changes land*.

## Decision

We adopt a **topological, dependency-ordered landing sequence** for all corpus changes, keyed to the corpus reference graph. Changes land in the layer order below; each layer is one PR or a grouped PR set, and **layer order is the invariant** while PR granularity within a layer is an operational choice.

A given change uses **only the layers whose entity types it touches**. The layers form a subsequence: an empty layer is skipped, and skipping it does not disturb the relative order of the layers that are used. Adding a single risk exercises only the new-risk layer plus its reciprocal control back-links; adding a component together with controls and risks exercises several layers; a full paper decomposition is the **maximal case** that exercises all of them. The invariant in D2 holds on whatever subsequence a change actually uses.

Every layer lands as a content PR against the `develop` integration branch, and a layer that introduces a new entity bundles its schema id-enum edit with its `*.yaml` entry as a **single content unit** — `risk-map/schemas/**` and `risk-map/yaml/**` land together per [ADR-002](002-branching-strategy.md), so a schema-plus-YAML layer is not a disallowed mixed PR. (This ordering convention is itself infrastructure and lives on `main`; the corpus changes it governs are content and land on `develop`.)

### D1. Landing layers

Layers are numbered in topological order over the reference graph. Referenced-only leaves (components, personas) land first, then the nodes that reference them, then the `controls ↔ risks` cycle, then modifications, then deprecations.

- **Layer 1 — New component additions.** Complete each new component: schema id-enum addition (`components.schema.json`) plus the `components.yaml` entry, **with its bidirectional component edges**. New components land with edges, never edgeless (see D3).
- **Layer 2 — New persona additions.** Add each new persona: schema id-enum addition (`personas.schema.json`) plus the `personas.yaml` entry. Personas are referenced-only leaves, so a new persona lands before any control or risk that references it (`control.personas`, `risk.personas` arrive in Layers 4–5). Adding a persona is a **breaking, closed-enum change** — it widens the enum that `risk.personas` and `control.personas` validate against, and per [ADR-021](021-personas-and-self-assessment-schema.md) requires the schema id-enum edit and the `personas.yaml` entry in the same PR — and is rare and held to a high bar (the necessity test of [ADR-031](031-authoring-time-agents-and-skills.md)); when it does happen it obeys this ordering like any other addition. Because personas carry no reciprocal back-link, there is no back-link half to co-locate.
- **Layer 3 — Existing component and persona updates.** YAML-only edits to components and personas already in the corpus. No deletions.
- **Layer 4 — New controls.** New controls, plus the new risks those controls require, plus the reciprocal back-links added to every existing risk the new controls reference (`risk.controls`). Any persona a new control references (`control.personas`) already exists from Layer 2.
- **Layer 5 — New risks.** New risks not already pulled in by Layer 4, plus the reciprocal back-links added to every control those risks reference (`control.risks`). Any persona a new risk references (`risk.personas`) already exists from Layer 2.
- **Layer 6 — Modifications to existing risks and controls.** Tuneups and description improvements **not** driven by any new node.
- **Layer 7 — Deprecations.** Unneeded components, controls, risks, **and personas** are retired by a **status flip to `deprecated`, not enum deletion**. The corpus already models `deprecated` status for personas and components (per [ADR-021](021-personas-and-self-assessment-schema.md); `personas.schema.json:37-41` defines the `deprecated` boolean); keeping closed id-enums intact preserves every prior reference and avoids reopening a closed enum. A status flip removes no edges and no references, so it introduces no dangling reference regardless of when it lands; it is placed last so retirement follows every addition and modification that might have kept the entity in use.

### D2. The governing invariant

**Every layer merges independently validator-green.** At every intermediate commit there is no dangling component / persona / control / risk reference, no broken control↔risk reciprocity, and no edgeless component. The dependency order in D1 is precisely what guarantees this PR-by-PR, on whatever subsequence of layers a change uses. Two supporting rules make the ordering total:

#### D2a. Cycle break (control ↔ risk)

The one real cycle in the graph cannot be topologically ordered on its own. Break it by **co-locating the reciprocal back-links in the same layer that introduces the new node**: control-driven back-links land in Layer 4, risk-driven back-links land in Layer 5. The reciprocal pair is never split across a layer boundary. (Component and persona references have no such cycle — both are referenced-only leaves — so they need no analogous rule; they are handled by landing the leaf first, in Layers 1 and 2.)

#### D2b. Co-dependent-new-node tie-break

When a new node references another new node, both land together in the **earlier** of their two layers. A new risk that requires a *new* control lands with that control in Layer 4 rather than at its own Layer 5, so the two are never split across the Layer 4/5 boundary. This keeps a new-node reference from ever dangling across a layer boundary.

### D3. New components land with edges, never edgeless

Layer 1 lands a new component before any control or risk references it (control/risk coverage arrives in Layers 4–5). That interim state is validator-green, but for a narrower reason than it appears:

- The isolated-component check **is** live by default. The `validate-component-edges` pre-commit hook runs `python3 scripts/hooks/validate_riskmap.py --block` on any staged `components|controls|risks.yaml` (`.pre-commit-config.yaml:208-213`) and does **not** pass `--allow-isolated`, so the strict default — reject edgeless components — is in force. The `--allow-isolated` flag exists (`scripts/hooks/validate_riskmap.py`) but is unused by pre-commit.
- "Isolated" means **no component-to-component edges only**. `find_isolated_components` in `scripts/hooks/riskmap_validator/validator.py` flags a component solely when `not node.to_edges and not node.from_edges` (`validator.py:99`). It never consults control or risk references.
- **No validator anywhere requires a component to be referenced by a control or risk.** `validate_control_risk_references.py` checks only control↔risk reciprocity; it does not touch components.

Therefore a new component lands green in Layer 1 **provided it carries at least one bidirectional component edge**; its control/risk coverage arriving later in Layers 4–5 produces zero interim failure. **New components land with their edges, never edgeless.**

The analogous question for the new-persona layer (Layer 2) resolves the same way: **no validator requires a newly-added persona to be referenced by any risk or control.** The persona-touching validators do not impose such a constraint — `validate_framework_references.py` checks only that a persona's `mappings` reference personas-applicable frameworks (`validate_framework_references.py:9`), and the `validate-persona-site-build` hook re-runs the site builder, which initializes an empty risk/control list for every active persona (`scripts/build_persona_site_data.py:356`) and so succeeds on an unreferenced persona. A new persona therefore lands green in Layer 2 with no risk or control yet pointing at it. The one-way direction of the persona reference is what makes this safe: a risk or control referencing a not-yet-added persona would fail schema validation (closed id-enum), but landing the persona first, before any referencing node, never reaches that state.

#### D3a. Orphan leaves are deliberately allowed

That a new component or persona can be referenced by nothing is **an intentional allowance, not a gap to be closed**. An unreferenced component is a legitimate modeled locus for controls or risks not yet authored, and a persona may precede the risks and controls that will cite it. This non-requirement is precisely what makes standalone leaf landing (Layers 1–2) possible, so it is load-bearing for the sequence rather than incidental.

Because the green-interim of Layers 1–2 depends on the *absence* of a coverage check, that absence is **guarded**: a regression test asserts that an unreferenced component and an unreferenced persona pass validation, and the component and control↔risk validators carry a comment pointing to this ADR. **Introducing any per-PR check that requires a component or persona to be referenced would break the Layer 1–2 green-interim and must revisit this ADR.** If a coverage guarantee is ever wanted, it belongs at assemble time over the complete change-set — never on an interim leaf PR.

## Alternatives Considered

- **Single monolithic PR** — land the entire change-set in one PR. Rejected: a single deferred or contested entry blocks the whole set; the diff is too large to review with confidence; and referential integrity is validated only at the end, so a break surfaces late and is expensive to localize.
- **Ad-hoc per-change sequencing** — decide landing order fresh for each change. Rejected: without a fixed order, a referencing node can be landed before its referent (the dangling-reference failure mode), there is no invariant guaranteeing a green intermediate state, and every change re-derives the ordering and re-incurs the same risk.
- **A pipeline-specific sequence** — define the landing order only for paper decompositions. Rejected: the ordering constraint comes from the reference graph, not from how a change-set was authored, so a decomposition-only rule would leave hand-authored single-entity changes ungoverned while duplicating the same topological logic. Generalizing to any corpus change, with the decomposition pipeline demoted to one optional change-set *source*, covers both with a single invariant.

## Consequences

**Positive**

- Content is always routed into an entity that already exists. A new control and the new risks it references land together (Layer 4) before any content is merged into them, so re-pointing a paragraph into a new control is safe by construction — the target exists before content is routed into it.
- Every intermediate merge is validator-green by construction; a break cannot be introduced by landing a referencing node before its referent, or one half of a reciprocal pair without the other. This holds for whatever subsequence of layers a change uses.
- One invariant governs every corpus change — single-entity edits and full decomposition batches alike — so landing order is never re-derived per change, and the decomposition pipeline is decoupled from it as merely one way to author a change-set.
- Reviewable PR-sized units replace an unreviewable monolith, with the dependency order carrying the correctness guarantee rather than reviewer vigilance.

**Negative**

- More PRs and more coordination for multi-layer changes; the layer order is a hard sequencing constraint that cannot be reordered for convenience. (Single-layer changes — the common case — incur none of this: they use one layer and land as one PR.)
- The green-interim guarantee for Layers 1 and 2 rests on a **deliberate non-requirement** (orphan components/personas are allowed — D3a), not on positive enforcement. This is a real dependency: a future per-PR coverage validator would break it. It is mitigated, not eliminated — the D3a guard (a regression test plus validator comments pointing here) makes the dependency explicit so such a validator cannot be added silently, but the convention still relies on that guard being honored.
- Adding a persona (Layer 2) is a breaking closed-enum change and should stay rare and high-bar; the sequence accommodates it but does not lower the bar for it.
- Deprecation-by-status-flip (D1 Layer 7) means retired ids persist in closed enums indefinitely; the corpus grows monotonically. This is the accepted cost of keeping prior references intact.

**Follow-up**

- The operational procedure a contributor performs — which files to edit in which layer, and in what order — lives in a companion contributing guide under `risk-map/docs/` (developer guidance; infrastructure, base `main` per [ADR-002](002-branching-strategy.md)). This ADR records the *decision and rationale*; the companion guide records the *how-to*. Keep the two in sync — the same decision/how-to division ADR-002 maintains between itself and `CONTRIBUTING.md`.
- This landing/PR-sequencing convention is **distinct from** how a change-set is authored. The paper-decomposition pipeline decides *what* changes and is only one possible source of a change-set; keep it documented separately. This ADR does not govern disposition or authoring logic.
- Coverage is decided (D3a): orphan components and personas are **allowed**, guarded by a regression test and validator comments. Should a coverage guarantee ever be wanted, it is an **assemble-time** check over the complete change-set — authored as a separate change that revisits D3a — never a per-PR gate, which would break Layer 1–2 independence.
- **Guard implementation is owed** (the D3a regression test + the validator pointer-comments). It is infrastructure (base `main`); until it lands, D3a's guard is documented but not yet enforced in CI.

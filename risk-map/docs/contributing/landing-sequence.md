# Landing Sequence for Corpus Changes

This guide is the step-by-step companion to ADR-034 (Dependency-ordered landing sequence for risk-map corpus changes). ADR-034 records the decision and rationale; this guide records the how-to — which files you edit, in which layer, and in what order, for your specific change.

If you're proposing a new risk, control, component, or persona — or updating an existing one — read this **before** you decide how many PRs your change needs.

---

## Who this guide is for

- Your change touches more than one entity type (e.g. a new component plus the controls and risks that reference it) and you're not sure how to split it into PRs.
- You want to know whether a new component or persona needs control/risk coverage before it can merge (it doesn't — see Layers 1 and 2 below).
- You're following [Adding a Component](../guide-components.md), [Adding a Control](../guide-controls.md), [Adding a Risk](../guide-risks.md), or [Adding a Persona](../guide-personas.md) and got pointed here because your change spans more than one of them.

If your change touches exactly one entity type and only references entities that already exist in the corpus, you don't need this guide — follow the relevant content-type guide and the [General Content Contribution Workflow](../workflow.md) as usual; you'll land in one layer, one PR.

---

## The invariant

Corpus changes land in a fixed, dependency-ordered sequence of layers, keyed to the corpus reference graph. **Every layer merges independently validator-green** — at every intermediate commit there is no dangling reference, no broken control-risk reciprocity, and no edgeless component. A change uses only the layers its entity types touch; an empty layer is skipped without disturbing the relative order of the layers used. See ADR-034 for the full rationale — the reference graph, the two failure modes a fixed order prevents, and the alternatives considered.

---

## The 7 layers

Work through the layers that apply to your change, in order. Layer order is the invariant; how many PRs a layer takes is an operational choice — most single-layer changes are one PR.

### Layer 1 — New components

**Triggers when:** you're adding a component that doesn't exist in the corpus yet.

**Files:** `risk-map/schemas/components.schema.json` (id-enum) + `risk-map/yaml/components.yaml` (the entry, **with its bidirectional edges** — both the new component's `edges.to`/`edges.from` and the reciprocal edge on every peer component it connects to).

**Rule:** the new component must carry at least one real component-to-component edge. It does **not** need to be referenced by any control or risk yet — that's not required and not expected. See [New components and personas don't need control/risk coverage](#new-components-and-personas-dont-need-controlrisk-coverage) below.

Follow [Adding a Component](../guide-components.md).

### Layer 2 — New personas

**Triggers when:** you're adding a persona that doesn't exist in the corpus yet. This is rare and held to a high bar — confirm the necessity case before drafting.

**Files:** `risk-map/schemas/personas.schema.json` (id-enum) + `risk-map/yaml/personas.yaml` (the entry). Nothing else — a persona carries no reciprocal back-link field, so there's no back-link half to co-locate.

**Rule:** the new persona does **not** need to be referenced by any risk or control yet — same non-requirement as Layer 1.

Follow [Adding a Persona](../guide-personas.md), Steps 1-2. (Wiring the persona into existing risks/controls is a separate, later PR — see Layer 6.)

### Layer 3 — Existing component and persona updates

**Triggers when:** you're editing a component or persona already in the corpus (description, responsibilities, etc.) — no new ids, no deletions.

**Files:** `risk-map/yaml/components.yaml` or `risk-map/yaml/personas.yaml` (YAML only, no schema edit).

### Layer 4 — New controls

**Triggers when:** you're adding a control that doesn't exist in the corpus yet.

**Files:** `risk-map/schemas/controls.schema.json` (id-enum) + `risk-map/yaml/controls.yaml` (the entry), plus:

- Any **new** risk the control requires lands in this same layer/PR, not in Layer 5 — a new risk co-dependent with a new control always lands in the earlier of the two layers (`risk-map/schemas/risks.schema.json` + `risk-map/yaml/risks.yaml`).
- The **reciprocal back-link**: every already-existing risk the new control references gets the new control's id added to its `controls` list in `risks.yaml`, in the same PR. This is the control-half of the control-risk cycle break — the pair is never split across a layer boundary.

Any persona or component the new control references already exists (Layers 1-2), so no schema edit is needed for those references.

Follow [Adding a Control](../guide-controls.md).

### Layer 5 — New risks

**Triggers when:** you're adding a risk that doesn't exist in the corpus yet **and** it wasn't already pulled into Layer 4 as a co-dependency of a new control.

**Files:** `risk-map/schemas/risks.schema.json` (id-enum) + `risk-map/yaml/risks.yaml` (the entry), plus the **reciprocal back-link**: every already-existing control the new risk references gets the new risk's id added to its `risks` list in `controls.yaml`, in the same PR.

Follow [Adding a Risk](../guide-risks.md).

### Layer 6 — Modifications to existing risks and controls

**Triggers when:** you're editing a risk or control already in the corpus — tuneups, description improvements, or wiring in a reference to an entity that landed in an earlier layer (for example, adding a newly-landed persona to an existing risk's or control's `personas` list).

**Files:** `risk-map/yaml/risks.yaml` or `risk-map/yaml/controls.yaml` (YAML only, no schema edit, no new ids).

### Layer 7 — Deprecations

**Triggers when:** retiring a component, control, risk, or persona.

**Files:** the relevant `*.yaml` file — flip `deprecated: true` (or the entity's status field). **Never delete the id from the schema enum**; a status flip removes no edges and no references, so it's safe to land any time after every addition and modification that might have kept the entity in use, which is why it's last.

---

## New components and personas don't need control/risk coverage

A new component or persona can land in Layer 1 or 2 with **nothing** referencing it yet, and it can stay that way indefinitely. This is intentional, not a gap: an unreferenced component is a legitimate modeled locus for controls or risks not yet authored, and a persona may precede the risks and controls that will cite it. No validator requires coverage — that non-requirement is guarded by a regression test, `scripts/hooks/tests/test_adr034_orphan_leaves_guard.py`, which pins this behavior. See ADR-034 §D3/§D3a for the full reasoning.

---

## Worked examples

### Example A: single-entity change — one new risk, no new control

You're adding a risk that's addressed entirely by controls already in the corpus.

1. **Layer 5 only, one PR:**
   - Add the id to `risk-map/schemas/risks.schema.json`.
   - Add the entry to `risk-map/yaml/risks.yaml`, listing the existing controls that address it.
   - Add the reciprocal back-link: for each of those existing controls, add your new risk's id to its `risks` list in `risk-map/yaml/controls.yaml`.
2. Validate (see [Validation Tools](../validation.md)) and open the PR.

No other layer is touched — the component and persona references on your new risk all point at entities that already exist.

### Example B: multi-entity change — a new component with controls and risks that reference it

You're adding a component, plus a control that governs it (which in turn requires a new risk), plus an additional risk against the same component that's addressed by an existing control.

1. **Layer 1, PR 1:** add the new component (schema id-enum + `components.yaml` entry) with real bidirectional edges to at least one peer component. No control or risk references it yet — that's expected. Merge before starting PR 2.
2. **Layer 4, PR 2:** add the new control (schema id-enum + `controls.yaml` entry) referencing the new component, plus the new risk it requires (schema id-enum + `risks.yaml` entry, bundled into this same PR per the co-dependent-new-node rule), plus the reciprocal back-link on every already-existing risk the new control also references. Merge before starting PR 3.
3. **Layer 5, PR 3:** add the additional new risk (schema id-enum + `risks.yaml` entry) referencing the new component and an already-existing control, plus the reciprocal back-link on that existing control.

Layers 2, 3, 6, and 7 are skipped — this change doesn't touch personas, existing-entity edits, or deprecations. Skipping a layer doesn't disturb the order of the layers used: 1, then 4, then 5.

---

## Validating each PR

Each layer's PR must pass the same validators as any content change. See [Validation Tools](../validation.md) for the commands — schema validation, component edge consistency, and control-to-risk reference checks all run per-PR, and each layer is designed to pass every one of them on its own.

---

## Related documentation

- ADR-034 (Dependency-ordered landing sequence for risk-map corpus changes) — the decision and rationale behind this guide
- [General Content Contribution Workflow](../workflow.md) — the overall contribution process this guide slots into
- [Adding a Component](../guide-components.md), [Adding a Control](../guide-controls.md), [Adding a Risk](../guide-risks.md), [Adding a Persona](../guide-personas.md) — the per-entity how-tos this guide sequences
- [Validation Tools](../validation.md) — validator commands referenced above

---
name: explore-exposure
description: "Answer \"what risks and controls attach to <a product or component> in an agentic/AI system?\" (e.g. AWS Nitro Enclaves, Pinecone as my vector store, LangChain orchestration, or a component id directly). Maps the product/technology to the CoSAI component(s) it implements or protects, then surfaces that component's exposure — the controls that apply and the risks they address — plus, for a boundary product, the protected workloads' exposure too. Read-only, for security architects and engineers. The subject must be a *specific* named product, vendor, technology, or component id; for a role/persona (e.g. \"I'm a data provider\") or a generic product category (e.g. \"an AI coding assistant\"), use explore-risks-by-activity instead. For a plain-language definition of a single entry, use explain-entity instead. NOT for authoring content (use the creator agents)."
---

# Explore Exposure (by product or component)

Given a product/technology or a component, show its CoSAI Risk Map exposure — the controls that apply to it and the risks those controls address — and, when it's a curated two-part lexicon row, the exposure of the components it *protects* too (the *exposure via* candidates). **Read-only.**

**Key structural fact:** risks do *not* reference components directly. Exposure flows **component → the controls that apply to it (a control's `components` field) → the risks those controls address (the control's `risks` field)**. Make that indirection explicit to the reader.

## Audience and voice

Security architects/engineers. Explain framework terms (component, how controls/risks connect); **link every entity id**. When you map a product to a component, say *why*.

## How to answer

1. **Resolve to component(s).**
   - If the input is a **component** (id or name), use it directly.
   - If it's a **product/technology** (AWS Nitro, LangChain, Pinecone, an MCP server…), map it to the component(s) it implements or protects using `references/product-component-lexicon.md` (curated). *(Explain: components are the framework's architectural building blocks — the loci where risks and controls attach.)*
   - **Hybrid — if the product isn't in the lexicon:** reason about the role it plays, optionally confirm with a live web lookup, and map it to the nearest component(s) — but **flag it as an inferred mapping**, not a curated one. Do not present inference as corpus fact.

2. **State the component's own applying controls — no walk.** "Applying controls" means controls in `risk-map/yaml/controls.yaml` whose `components` list contains the component's id. Grep for it. This is a measured statement about the current corpus: some components have none today. If there are none, say so plainly — never invent one, and never borrow another component's controls to fill the gap. A component's `edges` carry no exposure semantics, whatever the edge kind: ADR-018 D3 defines `edges` only as a structured-reference field the schema/validator check for membership and bidirectional consistency, not as an "applies to" relation; and even where an edge is a containment relationship rather than data flow — ADR-030 D9 types `componentIsolationRuntime → componentToolHosting`/`componentRuntimeHosting` as containment, not data flow — the contained workload's controls are still not the containing component's own. You may name a neighbour, by any edge kind, as a place to explore next, without listing its controls.

3. **List the universals separately, once.** The controls whose `components` field is `all` apply to every component: list them once, on their own, labelled universal — never as this component's own, and never omitted for a "no applying controls" component. These same controls typically have `risks` field `all` too; do not expand that into a risk list or a separate block enumerating every risk — say only that they're universal. Controls whose `components` field is `none` are a policy/governance layer (ADR-020 D3): do not present them as applying to any component; mention them, if at all, only as policy-layer controls.

4. **Reverse-look-up the curated lexicon, keyed on what a row implements.** If step 1 already resolved the input to one specific product's row, use that row and cite it by name. Otherwise (a direct component-id input, with no single product row already in hand) check whether one or more rows in `references/product-component-lexicon.md` **implement** the resolved component (the row's *implements* column for a two-part row, or its listed id for a one-part row); if several rows implement it (e.g. the confidential-compute group all implement `componentIsolationRuntime`), list the candidates once and cite the rows collectively (e.g. "the confidential-compute rows"), not per row. A one-part row contributes nothing further. A two-part row (reserved for isolation/hosting-boundary products) **implements** the boundary component and **protects** the workloads that run inside it — its **exposure via** candidates *are* those protected components. Treat the candidates as a **property of the row**, shown whatever the implemented component's own control count is:
   - Show the implemented component's own controls first (step 2), if any.
   - Then show each candidate, attributed to the row by name (never to an edge of the component's own, or to a hosting relationship you infer yourself): its own applying controls (conditionally — say plainly if a candidate has none today) and the risks those controls address, attributed to that candidate by id.
   - Mention the row's note-only components (if it has any), only as covered by the control the row's note names — never as candidates, and never with their own controls or risks — unless the prompt names that note-only component as the workload, in which case the next bullet applies instead.
   - If the prompt names no specific workload, list every candidate. If it names a specific workload that matches a candidate, lead with that candidate; the row's other candidates may still follow, marked secondary. If it names a workload that is *not* a candidate (including a note-only component), resolve it to its own component (via the lexicon or inference) and present it as the user's workload with that component's own controls, stating plainly whether it's note-only or not covered by the row at all; the row's candidates still follow afterward, marked secondary.
   - **Never let a candidate be treated as if it implements the row itself.** `componentModelServing` being a candidate of the isolation-boundary row does not make the isolation row's candidates *its* exposure; a component is only entitled to the row's candidates when it is itself what the row implements.

5. **Find the risks the applying controls address.** For the component (and, per step 4, for each candidate) collect the risks its own applying controls address (each control's `risks` field) — that is the exposure, reached *through* the controls.

6. **Separately, note risks the corpus describes at this locus in prose but does not reach through its controls.** Scope: the **resolved component only** — never a step-4 candidate. Evidence: a risk's own `shortDescription`/`longDescription` naming this component's role or locus, or the resolved component's own description naming the same kind of failure a risk describes (e.g. the component's description names data poisoning of its knowledge source, and a risk's description is poisoning of that kind of store) — not a keyword match. If step 5 doesn't already reach such a risk through an applying control, it's a corpus gap, not exposure. Present these in their own labelled section, distinct from the control-mediated exposure in step 5: never merge them in, and never call them "applies to" or "exposure". State plainly that they are not reached through the component's controls.

7. **Present the exposure.** For each component in play (the resolved one, plus any candidates from step 4): its own controls, the universals (once, separately), and the risks those controls address. Step 6's separate prose-described section is scoped to the resolved component only — never attach it to a step-4 candidate. Call out the **product-specific angle** — what about *this product* matters most.

8. **Link ids;** adaptive; read-only.

## Output (adaptive)

- **"risks & controls for X"** → table(s): `Component` | risks (ids) | applying controls (ids), with the universals called out separately and, for a two-part row, the candidates in their own rows attributed to the row.
- **"explain my exposure using X"** → a narrative: the product→component mapping, then the risks and controls that matter most, following the presentation in step 7.
- **Unknown product** → state the (curated or inferred) mapping, flag inferred ones, then answer.
- **No applying controls today** → say so plainly as a measured statement about the current corpus; still show the universals.
- Always link ids; note this reflects the current corpus; note when a product→component mapping is inferred rather than curated.

## Boundaries

- **Read-only.** To author a risk/control/component, redirect to the creator agents.
- **Be honest about the bridge.** The product→component mapping is a bridge (curated or inferred); the risks/controls are from the corpus. Don't blur the two, and flag inferred mappings.
- **No walk, no borrowing.** Exposure comes only from a component's own applying controls and, for a curated two-part row, its named candidates — never from a neighbour reached by any edge (data flow or an ADR-030 D9 consult/containment mapping), and never invented.
- Surface only corpus risks/controls; don't invent exposure that isn't in the map.

## Reference

- `references/product-component-lexicon.md` — the curated product→component map (a living seed; live lookup fills gaps). Two-part rows implement one boundary component and protect its *exposure via* candidates; reverse lookup is keyed on *implements* only.
- `risk-map/yaml/{components,controls,risks}.yaml` (the live corpus — source of truth).

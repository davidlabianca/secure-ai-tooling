---
name: explain-entity
description: Explain a specific CoSAI Risk Map entry — a risk, control, component, or persona (by id or name) — in plain language for someone new to the framework, including its classical roots and how it connects to other entries. Read-only. Use when someone asks "what is <riskX / controlY / componentZ / personaW>?", "explain this risk/control", or wants to understand an entry and its relationships — a plain-language definition of one entry. For the risks and controls that attach to a component (its exposure) rather than a definition, use explore-exposure instead. NOT for authoring or editing an entry (use the creator agents).
---

# Explain Entity

Give a framework newcomer a clear, plain-language explanation of a single risk / control / component / persona — what it is, why it matters, its classical roots, and how it connects to the rest of the map. **Read-only.**

**Key structural fact:** risks do *not* reference components directly. A risk's components are always **derived**, through the controls that address it — risk → controls (`controls.yaml`, the control's own `components` field) → components — never a direct link, and never presented as where the risk "manifests."

## Audience and voice

Security-literate, new to CoSAI-RM. Plain language; explain the framework's structure terms as you use them; **link every related entity id** so the reader can drill in.

## How to answer

1. **Resolve the entity.** Find it by id or name across `risk-map/yaml/{risks,controls,components,personas}.yaml` (grep). If a name matches several, list the candidates and ask which — or explain the closest and say so.
2. **Read its full definition** — risk: `shortDescription` + `longDescription` + `examples`; control: objective/description; component: description + `edges` + category; persona: description + `responsibilities` + `identificationQuestions`. For a risk or a component, also grep `controls.yaml` for the controls in play (below).
3. **Explain plainly:**
   - **What it is** — one plain sentence.
   - **Why it matters / what it's for.**
   - **Classical roots** — consult the `classical-lexicon` skill for the established concept it extends (a control's PEP / least-privilege grounding; a risk's classical analog such as confused deputy). Bridge classical→AI.
   - **Relationships** (the map connections), by type:
     - **risk** → every control in its own `controls` field, listed as addressing it whatever that control's `components` sentinel (a `components: none` control still addresses the risk; at most note that it contributes no component below); the personas it impacts; and the components its addressing controls apply to — a **derived** set (risk → controls → components; the corpus has no structured risk→component link), not where the risk "manifests." Separately, surface every control whose `risks` field is `all` from the controls side — the risk's own field won't list them — labelled universal (addresses every risk), never merged into the risk's own control list.
     - **control** → the risks it addresses, the components it applies to (or, when its `components` field is `all` or `none`, say so instead of listing components), and the personas who implement it.
     - **component** → its `edges` (to/from), and the controls whose `components` list contains its id, and, through them, the risks those controls address. List the universal (`components: all`) controls once, separately, labelled universal — never folded into the component's own controls, and never expand their `risks: all` coverage into a risk list. If the component has no component-specific controls today, say so plainly, as a measured statement about the current corpus, and point to `explore-exposure` for its exposure — do not import a neighbour's controls, reached by any edge, or a lexicon-row's candidates; that derivation is `explore-exposure`'s job, not this skill's.
     - **persona** → the risks that impact it, the controls it implements, its ISO 22989 / EU AI Act mapping.
4. **Link ids** for every related entity.

## Output (adaptive)

- **Default:** a concise explanation — what / why / classical roots / the key relationships.
- **"tell me more / full"** → expand all relationships and examples.
- **Ambiguous id/name** → list the candidate entries.
- Always link ids; note this reflects the current corpus.

## Boundaries

- **Read-only.** To change the entry, redirect to the relevant creator agent (`risk-/control-/component-/persona-creator`).
- Explain only what the corpus (plus its classical grounding) says; do not embellish beyond the definition or invent relationships.

## Reference

- `risk-map/yaml/{risks,controls,components,personas}.yaml` (the live corpus — source of truth).
- The `classical-lexicon` skill (for classical roots).

# ADR-032: Read-only consumer exploration skill surface

**Status:** Draft
**Date:** 2026-07-06
**Authors:** Architect agent, with maintainer review

---

## Context

ADR-031 productized an *authoring* surface — creator/critic agents plus authoring skills — for contributors *producing* Risk Map content, and established `scripts/skills/` as the canonical skill home (ADR-031 D5) authored to the Agent Skills open standard (ADR-031 D6). That surface serves people who write the corpus.

A separate need is unmet. Framework *consumers* — security architects, developers new to the framework, technology and system architects who are security-literate but not assumed to know the framework internals — want to *explore and understand* the existing corpus (risks, controls, personas, components), not author it. Nothing serves them today: the review surface gates submissions, and the ADR-031 authoring surface mutates the corpus. Neither offers a low-friction, read-only way in.

This ADR decides the tooling architecture for that surface only. It inherits ADR-031's infrastructure rather than re-deciding it, and defers the framework-content and UX specifics to a companion design note.

## Decision

We establish a **read-only, consumer-facing exploration skill surface** for the Risk Map, distinct from the ADR-031 authoring surface.

### D1. A distinct read-only consumer exploration surface

We establish this as its own skill family, separate from the ADR-031 authoring surface, for three reasons: a different audience (consumers, not content authors); a **read-only** posture (it never mutates the corpus, unlike the ADR-031 creators); and a different eval story (a query maps to an *expected set of surfaced entities*, not to schema or altitude conformance). It **inherits** rather than re-decides infrastructure — the same `scripts/skills/` canonical home (ADR-031 D5) and the same Agent Skills format (ADR-031 D6). That inheritance is why this is its own ADR rather than folded into ADR-031.

### D2. Focused skills, one per query mode

We build several focused skills, one per query mode — not one mega-skill and not a router. Six skills share an `explore-*` naming convention (the prefix groups them and signals consumer/read-only intent):

- **`explore-risks-by-activity`** — an activity or role → the risks that affect it plus their addressing controls.
- **`explore-controls-by-classical`** — a classical security concept → controls whose grounding matches.
- **`explore-exposure`** — a product/technology or a component → that component's risks and the controls that apply.
- **`explore-persona-self-id`** — walk the persona `identificationQuestions` → identify the reader's persona → its impacted risks plus implemented controls.
- **`explore-framework-coverage`** — a framework identifier → reverse-index the mappings across risks, controls, and personas.
- **`explain-entity`** — a single entity id → plain-language explanation including its classical roots and its relationships.

Output is **adaptive to the query**: a table for "show me all", a short narrative for "explain", a clarifying question when ambiguous. Output always **names specific entity ids** for drill-down and **explains framework terms inline** (it assumes security literacy, not framework familiarity).

### D3. Self-contained skills with thin-sibling reuse

Each skill is self-contained for general corpus orientation: it reads the live `risk-map/yaml/*.yaml` plus the generated `risk-map/tables/` with only a tiny inline orientation, no shared corpus-map file, so skills stay portable. But where a skill overlaps an authoring skill's specialized knowledge, it **defers to that skill as the source rather than duplicating** — `explore-controls-by-classical` consults `classical-lexicon`; `explore-framework-coverage` reuses the mapping-structure knowledge of the framework-mappings audit skill. This is the same defer-don't-duplicate principle as ADR-031 D1, applied across the authoring/consumer boundary.

### D4. Read-only boundary and handoffs

These skills read and explain; they never add or change corpus content. A reader who actually wants to author or edit is redirected to the ADR-031 creator agents. The exploration surface is also distinct from `content-reviewer`, the submission gate. Three roles stay separated: **explore** (consumer, this ADR), **author** (contributor, ADR-031), and **gate** (`content-reviewer`).

### D5. Hybrid product→component resolution

`explore-exposure` is the one mode needing knowledge outside the corpus — mapping a named product or technology to the component model. It uses a **curated product→component lexicon** for common products plus **live lookup** for unknowns, and must **flag an inferred mapping as inferred** rather than presenting it as corpus fact.

## Alternatives Considered

- **A single mega "explore the Risk Map" skill, or a router front-end** — one entry point that dispatches to modes. Rejected: poor triggering and an over-broad context; focused skills with disambiguated descriptions (D2) serve consumers better.
- **Fold the surface into ADR-031's authoring charter** — extend the authoring ADR to cover exploration. Rejected: different audience, read-only posture, and a different eval story (D1).
- **A separate UI or web app instead of skills** — build a browsing front-end. Rejected / out of scope: skills are the harness-neutral, in-context surface and reuse the ADR-031 D6 format.

## Consequences

**Positive**

- Consumers get a low-friction way into the framework; the read-only posture (D1, D4) keeps it safe.
- Reuse (D3) avoids drift with the authoring skills instead of copying their knowledge.

**Negative**

- Six more skills to maintain and eval (D2).
- The product→component lexicon (D5) is a curation surface that can go stale and needs the inferred-vs-curated honesty.
- Consumer skills that defer to authoring skills (D3) create a cross-family dependency to keep in sync.

**Follow-up**

- The framework-content and UX specifics — the exact query phrasings, and the product→component lexicon contents and curation ownership — are content/design-shaped and belong in a companion `risk-map/docs/design/` note, not this ADR, which records only the tooling-architecture decision.
- Per-skill `evals/` ship with each skill.

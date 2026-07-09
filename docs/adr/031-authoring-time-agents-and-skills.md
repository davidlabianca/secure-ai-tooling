# ADR-031: Authoring-time agents and skills for Risk Map content

**Status:** Draft
**Date:** 2026-07-01
**Authors:** Architect agent, with maintainer review
**Conforms to:** [ADR-033](033-vendor-neutral-agent-skill-shipping.md) — the authoring corpus this ADR defines ships under ADR-033's vendor-neutral shipping standard and lifecycle.

---

## Context

The repository has a mature *review* surface for Risk Map content and no *authoring* surface. `content-reviewer` (ADR-007) reviews YAML in three modes (`diff`, `full`, `issue`); `issue-response-reviewer` composes it into a maintainer comment; the framework-mapping tooling audits and pins mappings. Every one of these tools evaluates content someone else already drafted. Nothing in `scripts/agents/` — and there is no canonical skill surface at all — helps a contributor *produce* a conformant Control, Risk, Component, or Persona in the first place.

Meanwhile, a large body of authoring discipline has been developed — but it only materializes during maintainer-led authoring and CoSAI paper review, applied by hand each time. That discipline is substantial and hard-won, and falls into three strands:

- **Altitude rules.** The right granularity for an entry: specific enough to instruct a reader where a control or risk applies, general enough not to sprawl into per-instance siblings. For controls, state an objective rather than an implementation and do not restate the risk; for risks, a two-test for whether a candidate is genuinely distinct or should merge into an existing one; for components, an absorb-or-decompose base test.
- **Generalization and classical grounding.** Name an entry by the role it plays, not by a specific product or protocol (those are variations), and align terminology to established security reference architectures — for access control, the NIST SP 800-162 policy-point model (PEP / PDP / PIP / PAP) — rather than coining new terms. The rule "never invent a term when an established term of art exists" runs through all of it.
- **Counterfactual recording.** Capture not just the chosen entry but the rejected alternatives and the classical precedent that grounded the choice, so a later reviewer can see why.

This discipline is applied but largely unwritten: it lives in recurring maintainer review and in the reviewer's head, not in the contributing guides and not in any reusable tool. That is the gap.

Two forces make this an architectural decision rather than a content task:

1. **The discipline is trapped.** It only fires when a maintainer is in the loop authoring or reviewing. A contributor authoring a *single* Control or Risk before opening a PR — the common case — gets none of it.
2. **The obvious homes are wrong.** Folding authoring into `content-reviewer` overloads a submission gate with an interactive authoring loop (different cadence, different verdict vocabulary). Spinning up "one agent per mapped framework" mistakes reference knowledge for delegated work. Neither respects the existing agent-architecture pattern (ADR-006) or the skill-vs-agent distinction.

The adversarial-critic pattern this ADR productizes is already proven in practice: a skeptical-architect review pass over a prior draft ADR, tagging each finding by how strongly the evidence supports it and applying exactly the altitude, generalization, and classical-fidelity lenses named above. That is an authoring-time critic run by hand; this ADR gives it a durable home.

This ADR **decides the architecture only**. It authors no agent, no skill, and no content. Implementation is downstream work routed through the normal workflows.

## Decision

We productize this authoring discipline as **reusable, harness-neutral authoring-time agents and skills**, distinct from the existing review surface and from any batch extraction tooling. The split follows one rule: *invoke knowledge as a skill, delegate work as an agent.* Canonical, vendor-neutral definitions live under `scripts/agents/` (agents) and a new `scripts/skills/` (skills); any per-harness form is a derived wrapper, per ADR-006.

### D1. Productize the authoring discipline

We build durable authoring-time tooling that captures the three discipline strands — **altitude rules, generalization / classical-grounding, and counterfactual recording** — as first-class, invocable artifacts, rather than leaving them as judgment applied by hand each time a maintainer authors or reviews.

The target user is a contributor authoring a *single* Control, Risk, Component, or — least often, and only against the higher necessity bar of D5 — Persona, interactively, before a PR exists. Where the project already records a rule — in the contributing guides, or as settled maintainer review practice — the authoring tooling references it as the source rather than re-deriving it, so the guides, the review practice, and the tooling do not drift.

### D2. Agent-vs-skill boundary

The productized surface is two agent *roles* — a content *creator* and an authoring-time *critic* — instantiated once per content type, plus a small set of skills. The two roles are defined generically below; each is realized as a **creator/critic pair per content type** (Control, Risk, Component, Persona — D5), because the altitude tests, id conventions, and cross-reference obligations differ enough per type that one generic pair cannot carry them all without collapsing back into per-type branching. The roles are shared; the instantiations are per type.

**Agent roles** (own their context, delegated work):

- **A content *creator*** — new capability. Current tooling only reviews; nothing authors. The creator drafts a conformant entry of its content type: it applies the altitude rules at authoring time, generalizes to role-grain, grounds terms classically, and records the counterfactual (what it rejected and why). It is the interactive analog of the drafting a maintainer does by hand during review, without the maintainer having to be in the loop.
- **An authoring-time *critic*** — new capability, distinct from `content-reviewer`. The critic applies the altitude + generalization + classical-grounding lenses to a *draft in progress*, adversarially, echoing the skeptical-architect review pattern already used by hand (see Context). It is pre-PR and iterative; `content-reviewer` is the submission gate (D5).

**Skills** (invoked knowledge, no delegated context) — three that package authoring discipline, plus one that verifies framework mappings:

- A cross-cutting **classical-lexicon** skill — the shared "established term of art" knowledge (D3).
- An in-repo **mapping-selection** skill — the in-repo direction-selection discipline: for a control, which components does it apply to; for a risk, which controls adequately address its mechanism. This is the selection *judgment*, not the framework knowledge itself.
- An **altitude-check** skill — the packaged altitude tests (the component absorb/reader-instructive base test, the risk merge-vs-distinct two-test, the control objective-vs-implementation check).
- A **framework-mappings audit skill** (`audit-framework-mappings`) — verifies that a mapping's framework identifiers actually exist in the source frameworks (MITRE ATLAS, OWASP LLM, NIST AI RMF, STRIDE, ISO 22989, EU AI Act) and that mapping *format* conforms to `framework-mappings-style-guide.md` (which encodes ADR-027 version-pinning). The authoring surface relies on this for framework correctness instead of standing up per-framework reference-pack skills.

Framework knowledge itself therefore gets **no per-framework reference-pack skills**. The framework-mappings audit skill above, the style guide, and the existing `scripts/framework_mapping_maintainer.py` (ADR-027's generate-not-author machinery) cover identifier existence and format between them. Standing up N per-framework reference packs would recreate the defect D4 and the "one agent per framework" Alternative reject: N independent reference sets each going stale on independent cadences (ADR-027). One audit skill plus the style guide is the defer-to-the-source principle of D1 applied to framework knowledge — one verification surface, no drifting copies.

The dividing rule: *you invoke knowledge (skill) and delegate work (agent).* A framework taxonomy is reference knowledge that many callers consult identically — skill-shaped, and here served by the framework-mappings audit skill rather than duplicated. Drafting an entry, or adversarially critiquing one, is delegated work needing its own context and iteration — agent-shaped. "One agent per framework" is over-decomposition (see Alternatives): it multiplies routing, spreads N reference sets that each go stale independently, and pays a context-switch tax to retrieve what a skill returns inline.

### D3. Classical grounding as a cross-cutting skill and rule, not a standalone expert agent

The rule "never invent a term when an established term of art exists" must be **omnipresent at authoring time**. A standalone "classical-grounding expert" agent would be bypassable: a creator that simply neglects to call the siloed expert would coin a novel term and never be corrected. Grounding has to be a property of every draft, not an optional consultation.

We therefore realize classical grounding three ways at once:

- **A shared classical-lexicon skill** (D2) that any creator or critic consults for the established term.
- **A hard rule baked into every creator's guidance** — the creator cannot draft an identity/title/description without checking the lexicon first; grounding is a precondition, not a lookup it may skip.
- **An explicit critic lens** — the authoring critic independently checks whether a drafted term should have been a classical one, flagging a misapplied analogy or an unnecessary neologism.

#### D3a. Canonical naming default

To keep terminology consistent, the project adopts a single default source for the *canonical rendering* of a concept: **NIST**. This is a practical choice — NIST is comprehensive, openly published, actively versioned, and densely cross-referenced to other frameworks. A concept is grounded only when it is an **established term of art with international currency**; NIST is simply where its canonical label is fixed first (for example, aligning to the NIST SP 800-162 policy-point model — PEP / PDP / PIP / PAP — rather than coining protocol-specific names). When a recognized international standard uses a different established term, or NIST has none, the project adopts the international term instead — recorded as a deliberate, documented choice and adjudicated by maintainers through the normal CoSAI governance review (issue, discussion), never a silent rename or a call made unilaterally inside a draft.

#### D3b. Global legitimacy and equivalence

A NIST label is adopted only after the concept is corroborated as **globally recognized**: the classical-lexicon skill records each term as a **cross-standard equivalence set** — the canonical label alongside its equivalent(s) in recognized international standards — so the choice rests on an international base, with the global standard taking precedence over any single national source. This does not displace NIST as the naming default (D3a); it establishes that the *concept* must be internationally current, not merely nationally named. The skill materializes this rather than leaving it to manual diligence, and **flags to maintainers** when a term has **no international equivalent** (a parochialism signal — possibly an unnecessary coinage or a term current only in one jurisdiction) or when recognized international standards use a **different established term** (a naming conflict for governance to adjudicate). Capturing, for each entry, the international equivalent and the rejected alternative is exactly the distinction maintainers already draw by hand in review, extracted for reuse.

### D4. Out-of-repo knowledge freshness and provenance

Framework knowledge lives outside the repo and re-versions on independent cadences (ADR-027). The framework-mappings audit skill (D2) — the authoring surface's one consumer of out-of-repo framework knowledge — needs a freshness policy, and it is a **split by volatility**, not a uniform "always live-verify":

- **STABLE canonical terms are pinned to dated snapshots.** The NIST policy-point vocabulary (PEP / PDP / PIP / PAP) will not change; pinning a dated snapshot is correct and cheaper than re-verifying a stable term on every invocation.
- **VOLATILE specifics are live-verified.** Whether a given MITRE ATLAS technique ID still exists (or was retired/renumbered — the exact failure ADR-027 makes expressible) is checked at use time via the framework-mappings audit skill, not trusted from a snapshot.

Because framework knowledge is consolidated rather than fanned out into per-framework packs (D2), this policy has a **single consumer** — the framework-mappings audit skill — not N packs each applying the split independently. That is what keeps the STABLE/VOLATILE split from itself becoming N drifting freshness regimes.

This reuses existing machinery rather than reinventing it. `scripts/framework_mapping_maintainer.py` already exists in the repo and implements ADR-027's generate-not-author version pinning, and the framework-mappings audit skill (D2) does term/identifier existence verification against the source frameworks. The authoring surface consumes both; it does not re-implement pinning or verification.

*(Note: D4 is kept in this ADR rather than split into its own record. The freshness policy is what governs framework knowledge for the skills of D2, so the two decide together.)*

### D5. Reuse-vs-new, sequencing, and boundaries

**`content-reviewer` remains the submission gate; the authoring critic is complementary, not a replacement.** Submitted YAML already routes through `content-reviewer` in `diff` mode. That division holds: the authoring critic operates on a *draft in progress* pre-PR (recall/altitude/grounding, cheap to iterate); `content-reviewer` operates on the *submitted change* in-corpus (precision/integration, `READY`/`BLOCKING`/`NEEDS_HUMAN_REVIEW`). Conflating them would mix two verdict vocabularies and two cadences into one agent.

**Sequencing: Control first, then Risk, then Component, then Persona.** This matches the dependency structure and blast radius. Controls need component *homes* to map to; risks need both the controls that address them and the components they affect; components have a wide blast radius — adding one cascades into edges, control mappings, and prose — so they come after the control and risk tooling has exercised the shared skills.

Persona sits at the high-blast-radius end alongside Component, for a different reason. Personas are rarely added, the persona model is already governed by ADR-021, and adding one is a **breaking change**: the persona id set is a closed enum, and risks and controls carry reciprocal persona references, so a new persona ripples through the enum and every reciprocal reference. The persona creator/critic pair therefore leads with a **necessity test** — *is this role genuinely distinct, or does an existing persona (per ADR-021) already cover it?* — as a precondition before any drafting begins. That is a higher bar than the merge-vs-distinct and absorb-or-decompose tests the other three verticals apply: for Control, Risk, and Component the altitude test gates *shape*; for Persona the necessity test gates *existence at all*. Persona comes last because it is the rarest and most disruptive to add, and its reciprocal wiring into risks and controls presumes those verticals already exist.

**Branch boundary.** This tooling and ADR are infrastructure and base on `main` (ADR-002: `main` for tooling, `develop` for content). The Risk Map content it complements is authored on `develop`. Keeping the tooling on `main` avoids coupling the reusable authoring surface to any single content branch.

**Harness- and vendor-neutrality.** CoSAI is a cross-provider, model-neutral ecosystem, so canonical definitions are vendor-neutral and no product-named path is enshrined in the tracked artifacts (cf. the vendor-neutral `AI Assistant` commit trailer, ADR-004). Canonical agent specs already live under `scripts/agents/` (six exist today), and the canonical→wrapper direction is the established pattern: a tracked harness wrapper opens with a "Source of truth" callout deferring to its `scripts/agents/*.md` canonical (e.g. the `issue-response-reviewer` wrapper). Skills, by contrast, have **no canonical home yet** — they exist only as harness-specific wrappers. This ADR establishes `scripts/skills/` as their canonical, vendor-neutral home, paralleling `scripts/agents/`, in the open skill format decided in D6 so the published examples run across harnesses. The new creator and critic get canonical `scripts/agents/*.md` specs; the new skills get canonical `scripts/skills/*` definitions. Any per-harness wrapper is derived from those canonicals — not the reverse — and is deliberately left unnamed in this decision.

**Evaluability.** Skills are the more evaluable surface (a discrete knowledge lookup with checkable output), and will be validated with a dedicated skill-evaluation harness (with-skill vs. baseline, graded on fixed expectations). The creator/critic agents are validated the way other agents are (contract-only canonicals per ADR-006, exercised through the workflow), not through that harness.

### D6. Skill format: the Agent Skills open standard

Skills are authored to the **Agent Skills** open standard (`agentskills.io`; specification at `github.com/agentskills/agentskills`), not a bespoke or harness-specific schema. A skill is a directory containing a `SKILL.md` — YAML frontmatter requiring only `name` and `description`, plus Markdown instructions — with optional bundled `scripts/`, `references/`, and `assets/`. This is the concrete mechanism behind the harness-neutrality of D5: an openly-licensed (Apache-2.0 code, CC-BY-4.0 docs), cross-harness format lets the canonical `scripts/skills/*` definitions run across agent runtimes rather than binding to one. The standard is adopted on its merits — openness and cross-platform support — not its origin, the same posture D3a takes toward a practical naming default.

Because the standard is maintained externally and versions on its own cadence, conformance is recorded against a known revision so external changes are adopted deliberately, not silently — the provenance discipline ADR-027 applies to framework mappings and D4 to framework knowledge. The first skill PR fixes the revision the canonical surface targets; later skills follow it.

## Alternatives Considered

- **One agent per mapped framework — or one reference-pack skill per framework** — a dedicated MITRE-ATLAS agent, OWASP agent, NIST agent, and so on; or, the skill-shaped variant, a per-framework reference-pack skill for each. Both rejected, for the same reason: whether an agent or a skill, N per-framework surfaces spread N independent reference sets that each go stale on independent cadences (ADR-027), multiply the maintenance surface, and add a retrieval tax. The per-agent form additionally over-decomposes routing. D2/D4 instead consolidate to a single in-repo mapping-selection skill and use a single framework-mappings audit skill (`audit-framework-mappings`, D2) for identifier/format verification, with mapping format deferred to `framework-mappings-style-guide.md` — one framework surface, no drifting copies.

- **Extend `content-reviewer` to cover authoring** — add a fourth mode or an authoring path to the existing reviewer. Rejected: `content-reviewer` is a *submission gate* with a `READY`/`BLOCKING`/`NEEDS_HUMAN_REVIEW` vocabulary and an in-corpus, post-draft cadence. Authoring is an *interactive pre-PR loop* with a different rhythm and a different output. Folding them conflates the roles and the verdict vocabularies; authoring judgment and submission review are already kept separate in practice. D5 keeps `content-reviewer` as the gate.

- **Leave the discipline as by-hand maintainer practice only** — the status quo. Rejected: it then only fires when a maintainer is in the loop and never reaches a contributor authoring a single entry pre-PR. Most of this judgment is applied but unwritten — reusable nowhere. D1 extracts it.

- **A single monolithic "content authoring" agent** — one agent that both drafts and critiques. Rejected: it mixes the creator and critic stances in one context, losing the *adversarial independence* that makes the critic valuable (the by-hand review pattern works precisely because the reviewer has no prior involvement in the draft). It is also less evaluable — a single blob is harder to test than a creator agent plus discrete, checkable skills. D2 splits creator from critic.

## Consequences

**Positive**

- The authoring discipline becomes reusable outside maintainer-led review. A contributor drafting one Control gets altitude, generalization, classical-grounding, and counterfactual recording interactively, pre-PR.
- The skill-vs-agent split follows ADR-006 and keeps each surface evaluable — skills as discrete knowledge lookups, agents as delegated work with their own context.
- Classical grounding is omnipresent (D3): baked into every creator's preconditions and independently checked by the critic, so a novel-term default cannot slip through un-flagged.
- Freshness reuses ADR-027 machinery — `framework_mapping_maintainer.py` plus the framework-mappings audit skill (D2) — rather than reinventing pinning or verification; the STABLE/VOLATILE split (D4) avoids both stale snapshots and gratuitous live verification.
- `content-reviewer` stays a clean submission gate; the existing review handoff is unchanged. The new surface is additive.

**Negative**

- New surface to maintain: a creator/critic agent pair per content type (Control, Risk, Component, Persona — D5) plus four skills (classical-lexicon, mapping-selection, altitude-check, and the framework-mappings audit skill), each with a harness wrapper, all subject to the ADR-006 drift discipline. The classical-lexicon skill adds curation load (D3b's cross-standard equivalence sourcing — corroborating each term's global equivalents — especially); framework curation is bounded to the framework-mappings audit skill and the style guide rather than N per-framework packs.
- **Discipline duplication risk.** The authoring rules now live in more than one place — settled maintainer practice, the contributing guides, and the authoring skills/agents. D1's "reference the source rule, don't re-derive it" mandate mitigates this but does not eliminate it, and there is no automated check that they agree.
- **Provenance is a supply-chain axis.** The authoring surface pulls framework knowledge from outside the repo — through the framework-mappings audit skill, not N per-framework packs. The VOLATILE live-verify path (D4) introduces a network fetch at authoring time; the STABLE snapshots must be re-pinned deliberately or they silently rot. Both are the exact failure shapes ADR-027 catalogs, now present in an authoring skill rather than only in content — but concentrated in one consumer rather than fanned out across N.
- **Residual naming bias.** Defaulting to a single national source for the *canonical label* (D3a) can still smuggle in US framing if the global-equivalence check (D3b) is skipped; the cross-standard equivalence set mitigates but does not eliminate this, and depends on curators actually recording the international equivalents.
- **External format dependency.** The skill format tracks the externally-maintained Agent Skills standard (D6), which versions on its own cadence. Conformance must be recorded against a pinned revision or the canonical skills drift against the spec — the same provenance failure shape ADR-027 catalogs for framework mappings, now on the format axis rather than the content axis.

**Follow-up**

- Sequenced implementation plans (Control → Risk → Component → Persona per D5, with the Persona pair leading on the necessity test), each routed through the normal workflow: agent/skill definitions and their harness wrappers are config/infrastructure (`swe` → `code-reviewer`), not test-driven code.
- The unwritten authoring rules this tooling encodes will *also* be filed against the contributing guides (`guide-controls.md`, `framework-mappings-style-guide.md`, `submission-readiness-guide.md`), so humans and the tooling improve together — a virtuous loop. This is a separate content-surface task with its own issue/PR, not part of this ADR.
- Curation ownership (settled): the NIST-first term set and the escape-hatch adjudication (D3a) are owned by maintainers via CoSAI governance review (issues, offline discussion); the global-legitimacy check (D3b) is materialized by the classical-lexicon skill, which records the cross-standard equivalence set and flags parochialism / naming-conflict gaps for maintainers to carry into that review; STABLE-snapshot re-pinning (D4) is triggered per framework-version bump through the existing ADR-027 mapping cadence. Implementation obligation: the classical-lexicon skill must include the equivalence-recording and gap-flagging behavior so the maintainer can establish global legitimacy correctly.
- This ADR introduces `scripts/skills/` as a new canonical, tracked directory — none exists today. The skill format is decided in D6 (the Agent Skills open standard); the first skill PR establishes the on-disk layout and pins the spec revision the canonical surface targets (D6), setting the pattern every later skill follows.
- A lightweight consistency check that the authoring skills/agents and their source rules (the contributing guides) stay in sync is deferred to the backlog. Until it exists, D1's "reference the source, don't re-derive" mandate is enforced by review.

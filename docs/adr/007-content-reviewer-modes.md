# ADR-007: `content-reviewer` three-mode architecture

**Status:** Draft
**Date:** 2026-04-20
**Authors:** Architect agent, with maintainer review

---

## Context

The `content-reviewer` canonical at [`scripts/agents/content-reviewer.md`](../../scripts/agents/content-reviewer.md) is a 599-line specification that encodes schema-aware review logic for the CoSAI Risk Map framework. It is invoked in three distinct situations:

1. **PR review** — proposed YAML changes need to be evaluated against current framework state, with attention to the delta and its ripple effects.
2. **Pre-submission quality review** — a complete YAML file needs a holistic quality pass before a contributor opens a PR.
3. **Pre-implementation review** — a GitHub issue describes a proposed change in prose (not YAML), and a reviewer needs to evaluate fit, overlap, completeness, and projected impact *before* any YAML is written.

All three situations share the same underlying body of knowledge: the schema structure for risks, controls, components, and personas; the ID conventions; the cross-content integrity invariants (bidirectional consistency, dangling references, orphan detection); the overlap-detection heuristics; and the style-guide rules for `identificationQuestions` and `mappings`. That shared body spans roughly 400+ of the file's 599 lines — specifically the Schema Awareness, Review Checks, Impact Analysis, and Output Contract sections — and evolves with the framework. Recent evolutions include the Style Guide Compliance section (which triggers a read of external style-guide files when matching fields appear in scope) and the Governance Awareness escalation rule (which elevates finding severity on content under active governance review). Each such evolution lands in one place and reaches all three review situations at once.

The question this ADR records is a structural one: **one agent with a mode switch, or separate agents per situation?** The project has been operating on the one-agent answer since `content-reviewer` was introduced, but the decision was never tracked. The status-quo shape has already produced real downstream artifacts — a recent batch pre-implementation review of twelve newly filed content-update issues was produced through `content-reviewer` in `issue` mode, and its findings (a uniform `DISCUSS` verdict across the batch, with consolidation guidance) fed directly into maintainer triage without any mode-specific re-tooling.

A downstream composition — `issue-response-reviewer` invoking `content-reviewer` in `issue` mode at [`scripts/agents/issue-response-reviewer.md` §3 "Overlap Analysis"](../../scripts/agents/issue-response-reviewer.md) — also now depends on the three-mode shape. Elevating the choice to a tracked decision prevents a future session from proposing to split the agent without new information, and gives composing agents a stable contract to build against.

This decision lives within the vendor-neutral canonical-agent pattern established by [ADR-006](006-agent-architecture-pattern.md). That ADR fixes the *surface* (one canonical `.md` per agent under `scripts/agents/`); this ADR fixes the *shape* of one specific canonical on that surface.

## Decision

`content-reviewer` is a **single canonical agent with three explicit operating modes**, declared and selected by the caller:

- **`diff`** — PR review of proposed YAML changes against the current framework state.
- **`full`** — Holistic review of a complete YAML file for pre-submission quality.
- **`issue`** — Pre-implementation review of a GitHub issue described in prose.

Modes are declared in the canonical at [`scripts/agents/content-reviewer.md`](../../scripts/agents/content-reviewer.md) lines 43-59 (`## Invocation` → `### Modes`). The caller specifies mode explicitly on invocation — mode is not inferred from input shape.

The caller also specifies a **`format` flag** (`human` | `agent`) that is orthogonal to mode: every mode can emit narrative-rich output for a contributor or structured output for an orchestrator. This is fixed in the canonical at lines 53-58 (`### Caller Format`).

All three modes read the same Input Contract (current framework state: `risks.yaml`, `controls.yaml`, `components.yaml`, `personas.yaml`, plus optional schema files) and share the same body of schema awareness, integrity checks, and style-guide application. What differs across modes is narrow and explicit:

- **Input shape.** `diff` receives a delta against current state; `full` receives a complete file; `issue` receives prose from a GitHub issue.
- **Verdict vocabulary.** YAML modes emit `READY` / `BLOCKING` / `NEEDS_HUMAN_REVIEW`. Issue mode emits `PROCEED` / `DISCUSS` / `RETHINK`. Each vocabulary reflects what it means to "pass" at that stage of the review lifecycle.
- **Evaluation dimensions.** Issue mode adds a dedicated four-dimension pre-implementation pass (Fit / Overlap / Completeness / Impact Preview) because prose proposals cannot be mechanically validated against a schema the way YAML can.

Everything else — the schema conventions, the ID rules, the cross-content integrity checks, the style-guide triggers, the governance-awareness escalation, the impact-analysis dimensions — is shared and lives once.

The three-mode shape is part of `content-reviewer`'s public contract. `issue-response-reviewer` composes `content-reviewer` by name and mode (`issue` mode, `format: human` or `format: agent` depending on downstream consumer), per [`scripts/agents/issue-response-reviewer.md` "Composition with Content Reviewer"](../../scripts/agents/issue-response-reviewer.md). Removing or renaming a mode is a breaking change to that composition.

## Alternatives Considered

- **One agent per mode** — three separate canonicals (`content-reviewer-diff`, `content-reviewer-full`, `content-reviewer-issue`). Rejected: each would carry its own copy of the 400+-line schema-awareness and integrity body, and the three copies would drift as the framework evolves. It also breaks the `issue-response-reviewer` composition contract, which currently dispatches by mode on a single agent.

- **Two agents (YAML modes + issue mode)** — merge `diff` and `full` into one agent and split `issue` out. Rejected for the same reason at smaller scale: the schema and style knowledge is as load-bearing for issue-mode evaluation ("does this proposal overlap an existing risk?") as for YAML-mode evaluation ("does this YAML duplicate an existing risk?"). Splitting still duplicates the body, just across two files instead of three.

- **No modes; one generic reviewer inferring intent from input shape.** Rejected: the boundary between `diff` and `full` is ambiguous (is this a partial file?), and `issue` mode's input is prose, not YAML — shape-based detection is brittle. Explicit mode switches are clearer for callers and easier to compose against.

- **Modes as separate files sharing a common include.** Rejected: the canonical agent pattern established by ADR-006 is single self-contained Markdown files. This repository has no include mechanism for agent specifications, and introducing one to support this single case is disproportionate.

## Consequences

**Positive**

- The schema-aware body lives in exactly one file. As the framework taxonomy, ID conventions, or style guides evolve, a single edit updates all three review surfaces simultaneously. Drift across review situations is structurally impossible.
- Composition is clean. `issue-response-reviewer` invokes `content-reviewer` by name with an explicit mode, and the invocation semantics are documented in both canonicals. Future composing agents can follow the same pattern without needing to know which underlying file to target.
- Mode and format are orthogonal. Any mode can serve either a contributor (`format: human`) or an orchestrator (`format: agent`) without duplicating logic — the mode selects the review procedure, the format selects the emission style.
- The canonical remains vendor-neutral (per ADR-006). Modes are declared in prose; no harness-specific dispatch is baked in. A harness wrapper can choose to expose modes as distinct invocation surfaces (for example, three slash-commands routing to one agent) without changing the canonical.
- Evolution is observably cheaper on one agent than three. When the Style Guide Compliance section was added, a single edit gave all three modes — including the specific `In issue mode` clause — the new trigger logic without cross-file coordination. The same edit against a three-canonical split would have required three coordinated changes with the risk of one copy drifting.

**Negative**

- The canonical is long (599 lines). Readers scanning for a single mode must skim past sections irrelevant to that mode. Mitigated by the section structure — `## Invocation / Modes`, `## Issue Mode: Pre-Implementation Review`, per-mode output-contract entries — which lets readers jump to the mode-specific material. Not a full mitigation.
- Mode-specific behavior is sometimes expressed as conditional prose within shared sections (for example, the Style Guide Compliance section carries a dedicated "In `issue` mode" clause). This conditional shape is harder to audit than fully separated mode bodies would be. Accepted because it preserves the single source of truth on the shared body.
- Adding a fourth mode (if ever needed) is a canonical-wide change: the Input Contract, Output Contract, verdict vocabulary, and any mode-specific conditional clauses all need coordinated updates. Acceptable because new modes are rare and the coordination is exactly the discipline this decision preserves.
- The three-mode shape is now part of the public contract. Downstream composers (today: `issue-response-reviewer`; tomorrow: any new agent that consumes `content-reviewer`) depend on the mode names. Renaming or removing a mode is a breaking change and must be treated as such.
- A caller that invokes the agent with an ambiguous or implicit mode will get undefined behavior rather than a sensible default. The canonical treats mode as required, not inferred — which is correct given the input-shape differences, but it shifts the burden of mode selection onto every caller. Wrappers that provide a default mode per invocation context (for example, a `/review-pr` skill that always invokes `diff` mode) absorb this burden, but the raw canonical contract does not.

**Follow-up**

- No new work is implied by this ADR. It captures the status quo as a tracked decision.
- If a future situation arises that does not fit cleanly into `diff`, `full`, or `issue` (for example, evaluating a partial-file draft, or reviewing a batch of related issues as one unit), the decision to add a mode versus to compose modes externally is a new ADR, not an amendment to this one.
- [ADR-008](008-sub-agent-orchestration.md) will capture the broader orchestration workflow that ties `content-reviewer` together with the other canonical agents; the mode architecture recorded here is one of the building blocks that ADR will reference.
- The contributor-facing submission and review documentation (tracked separately) should reference `content-reviewer` by its mode vocabulary (`diff` / `full` / `issue`) rather than by situational phrases, so that doc text and agent contract stay aligned as the canonical evolves. Not a blocker for this ADR.
- If mode selection ever becomes a recurring source of caller error (for example, callers invoking `full` on a partial file and getting surprising results), a thin mode-guard check at the front of the canonical — "if input does not match the declared mode's expected shape, fail fast with a clear message" — would mitigate the burden noted under Negative. That is a follow-on refinement of this decision, not a reason to revisit the one-agent choice.

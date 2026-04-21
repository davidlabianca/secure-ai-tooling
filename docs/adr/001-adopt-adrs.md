# ADR-001: Adopt ADRs for tooling/infrastructure decisions

**Status:** Draft
**Date:** 2026-04-20
**Authors:** Repository maintainer, with AI-assisted drafting

---

## Context

The CoSAI Risk Map repository has accumulated a growing set of decisions that shape how the project is built, tested, released, and extended. A representative sample from the past several months:

- The branching strategy (`develop` for content vs. `main` for infrastructure).
- The devcontainer + `mise` tool-management setup and the `install-deps.sh` / `verify-deps.sh` pattern that supports it.
- The vendor-neutral `Co-authored-by: AI Assistant <ai-assistant@coalitionforsecureai.org>` commit trailer for AI-assisted contributions, tracked in governance issue #149.
- The adoption of the `pre-commit` framework (PRs #211, #221, #222) and the subsequent removal of the parity gate.
- The vendor-neutral canonical agent-architecture pattern in `scripts/agents/`.
- The `content-reviewer` agent's three operating modes (`diff`, `full`, `issue`) sharing one schema-aware body.
- The broader sub-agent orchestration workflow that ties published agents together with slash-command skills.

These decisions are real and load-bearing, but today they are scattered across contributor-facing operating guides (such as `CLAUDE.md` or `AGENTS.md`), commit messages, PR descriptions, and maintainer-local plan documents held in untracked working directories. A contributor — or a future session — who wants to understand *why* the repository looks the way it does has to reconstruct rationale from fragments. This has already caused two specific problems:

1. **Decisions get re-litigated.** The same tradeoff question surfaces in a new session because the prior resolution is not discoverable.
2. **Retroactive context decays.** When a decision is only captured inside the plan that produced it, the plan eventually gets archived or forgotten, and the rationale disappears with it.

At the same time, the repository already has `risk-map/docs/design/` — long-form design documents for **framework-content** decisions (the persona model expansion, the risk-ID migration, metadata mappings). Those documents serve a different audience (framework consumers) and operate at a different cadence (substantial, versioned design write-ups). Folding tooling decisions into that surface would dilute both audiences.

We need a lightweight, separate home for tooling, infrastructure, and process decisions — one that is cheap enough to write per-decision that the overhead does not itself become a reason to skip documentation.

## Decision

Adopt **Architecture Decision Records (ADRs)** as the tracked home for tooling, infrastructure, and process decisions in this repository.

Concrete shape:

- **Location:** `docs/adr/`, tracked in git.
- **Template:** lean five-section format — *Status / Context / Decision / Alternatives Considered / Consequences*. Source at [`docs/adr/TEMPLATE.md`](TEMPLATE.md).
- **Numbering:** classic sequential `NNN-slug.md` (zero-padded, kebab-case slug). Numbers are claimed by updating the [ADR index](README.md) in the same commit that introduces the ADR.
- **Lifecycle:** ADRs land as `Status: Draft`. Maintainer review flips `Draft → Accepted`. When a later ADR replaces an earlier one, the earlier one's status becomes `Superseded by ADR-XXX` and the file stays in place (history is preserved; it is never deleted).
- **Authorship:** ADRs are typically drafted by the `architect` agent (see [ADR-006](006-agent-architecture-pattern.md)). Maintainers may also author ADRs directly. Either way, draft status is the default until sign-off.
- **Triggers — when to write an ADR:** schema changes, adding a new top-level directory, cross-module refactors, adding or removing an external tool dependency, adding or changing a CI workflow, and introducing new features or tools that shape how the repo is built (for example the upcoming GitHub Pages build surface).
- **Single decision per ADR.** If a draft grows a second decision, split it.

**Explicit separation from framework-content design:**

| Surface | Scope | Audience |
|---|---|---|
| `docs/adr/` | Tooling, infrastructure, CI, agent architecture, repo-wide conventions | Maintainers, contributors, tool integrators |
| `risk-map/docs/design/` | Risk taxonomy, persona model, schema semantics, migration logic | Framework authors and consumers |
| Local untracked plans directory (template source at [`docs/contributing/plan-template.md`](../contributing/plan-template.md)) | Phased execution of a specific piece of work | Maintainer, in-flight sessions |

A decision about how the Risk Map *content model* is shaped belongs in `risk-map/docs/design/`. A decision about how the *repository itself* is built, tested, released, or extended belongs in `docs/adr/`. Plans are maintainer-local and do not substitute for either — when a plan produces a decision worth preserving, that decision is lifted into an ADR.

## Alternatives Considered

- **Status quo: decisions distributed across operating guides, commit messages, and plans.** Rejected because it has already produced the two problems listed in Context (re-litigation, decay). Operating guides (such as `CLAUDE.md` or `AGENTS.md`) are manuals, not decision logs; commit messages are commit-scoped; plans are deliberately untracked and temporary.

- **Single combined decision surface under `risk-map/docs/design/`.** Rejected because it mixes two audiences with different needs. Framework consumers reading the persona model design should not have to page past a devcontainer ADR; contributors debugging a CI workflow should not be buried in taxonomy documents. The split is load-bearing.

- **Tracked `docs/plans/` replacing both ADRs and untracked local plans.** Rejected because plans and decisions have different lifecycles. Plans are transient (they document an execution path); decisions are durable (they document a commitment). Forcing them into one surface either inflates plans with over-long decision justifications or flattens decisions into execution narratives.

- **Heavier RFC template** (problem statement, proposal, detailed design, debate threads, review record). Rejected as over-engineered for this repository's cadence. The overhead of an RFC would raise the bar for documentation to the point where small-but-meaningful decisions get skipped — exactly the failure mode we are trying to fix.

- **Freeform `docs/decisions/`** without a numbering or template convention. Rejected because unstructured decision logs are nearly as hard to navigate as the status quo. The small cost of a template and numbering buys substantial searchability and cross-reference.

## Consequences

**Positive**

- Tooling decisions have a stable, tracked home with a consistent shape. Contributors and future sessions can answer "why is it this way?" without archaeology.
- The `architect` agent has a concrete output surface. Its job becomes "produce an ADR against `TEMPLATE.md`" rather than "write a document somewhere."
- Clear boundary between infrastructure decisions (`docs/adr/`), framework-content design (`risk-map/docs/design/`), and transient execution plans (local untracked directories). Each surface has a defined audience and does not compete with the others.
- `Status: Superseded by ADR-XXX` preserves history. When a decision is revisited years later, the prior ADR and its reasoning remain legible.

**Negative**

- Small ongoing authoring cost on every qualifying change. Mitigated by the lean five-section template and by the architect agent carrying most of the drafting load.
- Risk of ADR sprawl if triggers are interpreted too loosely. Mitigated by the explicit trigger list in this ADR and by the "single decision per ADR" rule.
- Risk of `docs/adr/` and `risk-map/docs/design/` drifting in scope over time. Mitigated by this ADR and by `docs/adr/README.md` both stating the split explicitly; any future ADR that blurs the line should either refine the split or be rejected.
- Retroactive ADRs depend on maintainer memory and git archaeology. Mitigated by requiring concrete citations (commits, PRs, issues, file paths) in every retroactive ADR, and by the `Status: Draft` gate before acceptance.

**Follow-up**

- Seven retroactive ADRs (ADR-002 through ADR-008) capture prior tooling decisions under the practice this ADR establishes. See the [ADR index](README.md) for the list; they land as `Status: Draft` pending maintainer acceptance.
- The `architect` agent itself, canonical vendor-neutral source at [`scripts/agents/architect.md`](../../scripts/agents/architect.md). See [ADR-006](006-agent-architecture-pattern.md) for the agent-architecture pattern that governs the canonical-vs-wrapper split.
- The upcoming GitHub Pages build may want to render `docs/adr/` as a navigable surface. Flagged for that work, not coupled to this ADR.

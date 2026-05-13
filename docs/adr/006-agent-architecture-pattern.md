# ADR-006: Vendor-neutral agent architecture under `scripts/agents/`

**Status:** Accepted
**Date:** 2026-04-20
**Authors:** Architect agent, with maintainer review

---

## Context

The CoSAI Risk Map repository delegates increasingly large amounts of work to AI sub-agents: content review, issue-proposal triage, test authoring, implementation, code review, and architectural decision drafting. Each of these agents is defined by a prose specification that names the agent, states its purpose, fixes its input and output contracts, and describes how it composes with other agents.

The pattern emerged implicitly. The first canonical specification was [`scripts/agents/content-reviewer.md`](../../scripts/agents/content-reviewer.md), a 599-line full specification that encodes schema-aware review logic across three modes (`diff`, `full`, `issue`). The second was [`scripts/agents/issue-response-reviewer.md`](../../scripts/agents/issue-response-reviewer.md), a 299-line specification that composes `content-reviewer` in `issue` mode and assembles a contributor-facing review comment. Both were authored as tracked, vendor-neutral prose, allowing contributors to leverage them with harness-specific wrappers appropriate to their own agent environment.

Four more canonical agents were later added in the same directory: [`architect.md`](../../scripts/agents/architect.md) (233 lines), and the contract-only specifications [`testing.md`](../../scripts/agents/testing.md) (91 lines), [`code-reviewer.md`](../../scripts/agents/code-reviewer.md) (94 lines), and [`swe.md`](../../scripts/agents/swe.md) (95 lines). The three implementation-workflow agents previously existed only as harness-specific wrappers; their vendor-neutral logic was lifted into `scripts/agents/` and the wrappers reduced to thin adapters.

Two forces motivate capturing the pattern as a decision:

1. **Vendor neutrality is load-bearing.** The CoSAI coalition's credibility depends on not privileging any single vendor's tooling in its published artifacts (see [ADR-004](004-ai-assistant-trailer.md) for the parallel argument about commit trailers). Agent specifications that bake in tool bindings, model identifiers, or harness-specific example dialogue commit the repository to one AI environment. A contributor running a different harness should be able to consume the same agent logic without rewriting it.
2. **Drift between canonical and wrapper is a recurring risk.** With two files per agent, an edit to one that is not mirrored into the other produces silent divergence. The pattern needs a clear rule for which file is authoritative and what the other one is allowed to contain.

Today the pattern is asserted in several places — [ADR-001](001-adopt-adrs.md)'s Context explicitly names "the vendor-neutral canonical agent-architecture pattern in `scripts/agents/`" (line 17); `architect.md`'s Style Conventions section names the wrappers as "implementation details of each environment, not part of the canonical pattern"; where harness-level skill or orchestration wrappers exist, they are expected to open with a "Source of truth" callout deferring to their canonical source under `scripts/agents/`. But the pattern itself has no tracked decision record. This ADR is that record.

## Decision

Agent sub-specifications in this repository live as **vendor-neutral prose under `scripts/agents/*.md`**. That directory is the canonical surface. Every agent the repository defines has exactly one canonical file there, and that file is the authority on the agent's role, input contract, output contract, composition with other agents, and boundaries.

Concrete shape:

- **Location.** `scripts/agents/`, tracked in git. One file per agent, `kebab-case-name.md`. Current canonicals: `architect.md`, `content-reviewer.md`, `issue-response-reviewer.md`, `testing.md`, `code-reviewer.md`, `swe.md`.
- **Canonical shape.** A canonical agent file opens with a header block (`# <Agent Name> Sub-Agent Definition`, version, scope), then `## Agent` (name and description with invocation examples), then `## Composition` (how this agent invokes or is invoked by other canonicals), then body sections that define the agent's method. The `content-reviewer.md` layout (lines 1-100) is the established reference for full specifications.
- **Two canonical sizes, both valid.** `content-reviewer.md` is a full specification (599 lines): a stable, heavily reusable procedural methodology is worth encoding in detail. `testing.md`, `code-reviewer.md`, and `swe.md` are contract-only (~90-95 lines each): for agents whose methodology varies materially across harnesses or projects, the canonical fixes only the role, input, output, and composition, leaving the procedure to the harness wrapper. The right size is determined by how portable the methodology is, not by agent importance.
- **Vendor-neutral body.** Canonical files do not name specific AI harnesses (Claude Code, Cursor, Aider, etc.), do not reference harness-specific directories (`.claude/`, `.cursor/`), do not specify tool bindings or model identifiers, and do not embed harness-specific example dialogue. These are environment concerns. Architect's own Style Conventions section (line 217 of `scripts/agents/architect.md`) codifies this rule for ADRs; the same rule applies to agent canonicals.
- **Composition by name.** Canonical agents reference each other by canonical filename or agent name only. `architect.md` composes with `testing`, `code-reviewer`, and `swe`; `issue-response-reviewer.md` composes with `content-reviewer`. Because all canonicals live in one directory with stable names, cross-references resolve without harness-specific path lookups.
- **Harness wrappers are outside the pattern.** A specific AI environment may layer its own wrappers over the canonical sources — typically an agent-wrapper file (YAML frontmatter binding tools, model, and any environment-specific metadata, on top of the canonical body with the `## Agent` and `## Composition` sections stripped, since their content is duplicated in frontmatter) and optional skill or orchestration files (thin slash-command or equivalent entry points that invoke a canonical agent). Wrappers of this kind are **implementation details of the environment that consumes the canonical**, not part of the canonical pattern. Different harnesses layer different wrappers over the same `scripts/agents/*.md` sources and are equally valid consumers.
- **The canonical-to-wrapper transform is shallow.** A wrapper is the canonical source with harness-specific frontmatter prepended and the sections made redundant by that frontmatter removed. It is not a rewrite. A typical wrapper adds a YAML block (name, description, tool bindings, model identifier, optional display metadata) and drops the `## Agent` and `## Composition` sections whose content is already carried by the frontmatter's `name` and `description` fields. Drift beyond this shape is a bug.
- **Authority.** When a canonical and a wrapper disagree, the canonical wins. Wrappers should open with a "Source of truth" callout — phrased along the lines of "when review logic changes, update the canonical source first, then reconcile this wrapper" — so the operating norm is visible to anyone editing the wrapper. Edits flow canonical → wrapper, not the other direction.

## Alternatives Considered

- **Single surface, harness-specific only.** Define agents exclusively in whatever single AI environment the project uses, with tool bindings, model identifiers, and harness-idiomatic framings baked into each agent file. Rejected: this commits the repository to one AI environment. Future harness adoption would require rewriting every agent rather than wrapping it, and the coalition's vendor-neutral posture (see [ADR-004](004-ai-assistant-trailer.md)) would be contradicted in the agent surface just as it would be in commit trailers.

- **Single surface, vendor-neutral only.** Define agents exclusively as `scripts/agents/*.md` and leave each environment to figure out its own invocation mechanics. Rejected: harness-specific concerns (tool permissions, example dialogue shaped like the harness's invocation syntax, model-selection hints) are real and operational. Pushing them into contributor-local configuration leaves every new contributor to rediscover them. A thin wrapper layer gives those concerns a home that is close to the canonical without polluting it.

- **Co-equal surfaces with implicit inheritance.** Treat `scripts/agents/*.md` and a specific harness's wrapper directory as parallel definitions, with a convention that they "should stay aligned." Rejected: this was the earlier, looser framing the pattern started with, and it was explicitly rejected on 2026-04-20 during the ADR-001 review. Elevating a specific harness's wrappers to "part of the pattern" reads as prescribing that harness, which the coalition's vendor-neutrality posture does not allow. It also invites drift, because "co-equal" provides no tie-breaking rule when the two files disagree.

- **Full duplication, no transform relationship.** Maintain completely separate canonical and wrapper versions, each authored independently. Rejected: the whole value of a canonical is that wrappers are shallow adaptations of it. Duplication without a transform relationship guarantees drift over time and multiplies the cost of every future agent edit.

## Consequences

**Positive**

- The repository has a single authoritative surface for agent definitions. A contributor asking "what does `content-reviewer` do?" has one file to read, not two.
- Portability is preserved. A contributor using Cursor, Aider, or a plain-CLI harness can consume `scripts/agents/*.md` verbatim and wrap them in their environment's conventions. The canonical logic does not depend on any specific harness.
- Composition is stable. Canonical agents reference each other by name; those references resolve inside `scripts/agents/` without any harness-specific resolution. This makes `architect → testing → code-reviewer → swe` workflows describable in vendor-neutral prose (as they are in `architect.md`).
- The contract-only vs full-spec split matches the actual reusability of each agent's methodology. High-reuse, harness-stable methodology (schema-aware content review) lands as a full spec; lower-reuse, harness-variable methodology (TDD implementation) lands as a contract that harness wrappers flesh out.
- The vendor-neutral posture established in [ADR-004](004-ai-assistant-trailer.md) for commit trailers extends coherently to the agent surface. The two decisions reinforce each other.

**Negative**

- Every agent has two files to keep in sync: the canonical plus at least one harness wrapper for each AI environment in active use. Drift between them is a real failure mode. Mitigated by the "canonical wins" rule, by the shallow transform shape, and by the "Source of truth" callouts in wrapper files — but the discipline is ongoing.
- Contract-only canonicals push methodology into harness wrappers. This keeps canonicals portable but means a new harness cannot reproduce the full agent behavior by reading the canonical alone — it must also study an existing wrapper as a reference implementation. Acceptable for agents whose methodology is genuinely environment-specific (TDD loops bind to available test runners and editors); less acceptable for agents that could in principle be fully specified.
- Adding a new agent is a multi-file change: one canonical, one wrapper per active harness. Mitigated by the shallow transform — most wrappers are a few lines of frontmatter plus a body copy — but it is real authoring cost.
- Wrappers for harnesses the project does not officially support are not tracked — harness-specific wrapper directories remain contributor-local via `.git/info/exclude` or equivalent exclusion. A future decision to officially support a specific harness will need to address whether to track its wrappers or keep them local.

**Follow-up**

- **ADR-007** will capture the `content-reviewer` agent's three-mode architecture (`diff`, `full`, `issue`) as a decision in its own right, building on the pattern this ADR records.
- **ADR-008** will capture the broader sub-agent orchestration workflow (how published agents compose with harness-level skills for end-to-end tasks), also building on this ADR.
- The contributor-facing documentation work (tracked separately in the contributing-guides plan) should describe the canonical-vs-wrapper split in terms a new contributor can act on, pointing at this ADR for the *why*.
- If the project ever officially supports a specific AI harness, the wrapper-tracking question (contributor-local via `.git/info/exclude`, or tracked in-tree) is a follow-on decision. Not in scope here.

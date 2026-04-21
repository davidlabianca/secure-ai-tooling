# ADR-008: Sub-agent orchestration: composition contracts and routing boundaries

**Status:** Draft
**Date:** 2026-04-20
**Authors:** Architect agent, with maintainer review

---

## Context

[ADR-006](006-agent-architecture-pattern.md) establishes that canonical sub-agent specifications live as vendor-neutral prose under [`scripts/agents/`](../../scripts/agents/). [ADR-007](007-content-reviewer-modes.md) captures the `content-reviewer` agent's three-mode architecture. Neither ADR answers the next question: *how do canonical sub-agents compose into end-to-end, contributor-facing workflows?*

Two composition shapes are already in production use in this repository:

1. **Agent-to-agent composition.** [`scripts/agents/issue-response-reviewer.md`](../../scripts/agents/issue-response-reviewer.md) (299 lines) invokes [`scripts/agents/content-reviewer.md`](../../scripts/agents/content-reviewer.md) in `issue` mode with `format: agent`, consumes the structured findings, and assembles a maintainer-facing draft review comment with field-by-field feedback, quality gates, and a summary-of-changes table. The composition is declared in `content-reviewer.md`'s `## Composition` section (line 29-31) and in `issue-response-reviewer.md`'s `## Composition with Content Reviewer` section (line 240-250).
2. **Skill-to-agent composition.** A harness-level slash command (e.g., a `/draft-issue-comment` skill under a specific harness's skills directory) receives a natural-language invocation — typically a GitHub issue URL — fetches the external context using harness-available tools (`gh` CLI, HTTP fetches, file I/O), invokes the appropriate canonical agent, and translates the agent's findings into an external side effect (a posted or drafted comment, a file written, a PR updated).

This pattern has been exercised most visibly in the batch review of risk-map issues #188-199: twelve issues processed through `issue-response-reviewer` composing `content-reviewer` in `issue` mode, producing twelve maintainer-facing draft comments. The pattern works. It is not yet recorded.

Two forces motivate capturing it now:

- **Composition contracts are load-bearing.** `issue-response-reviewer` only works because `content-reviewer` returns findings in a stable `format: agent` shape the caller can parse. If either side of that contract drifts without coordination, the composed workflow breaks. The contract needs to be named as a contract, not left implicit.
- **Routing boundaries keep canonicals portable.** A canonical agent that knows it is being consumed by a specific skill, orchestrator, or harness has been contaminated. ADR-006's vendor-neutrality guarantee depends on canonicals returning findings and letting callers translate them into external side effects. This boundary is currently upheld by convention; it should be stated.

This ADR is scoped narrowly to the composition patterns already battle-tested in live use: `issue-response-reviewer` → `content-reviewer`, and the harness-skill → canonical-agent shape demonstrated by the draft-issue-comment flow. The newer canonicals (`architect`, `testing`, `code-reviewer`, `swe`) declare composition relationships in prose but have not yet been exercised through a published orchestration flow. **Their orchestration patterns are out of scope for this ADR; they will be captured in a future ADR once the patterns are battle-tested in live use.**

## Decision

Sub-agent orchestration in this repository follows two composition shapes, each with an explicit contract and a fixed routing boundary.

**1. Agent-to-agent composition (canonical → canonical).**

A composing canonical invokes a composed canonical by name, passing explicit mode and format flags. The composed canonical returns findings in the specified format; the composing canonical assembles a higher-level artifact from those findings.

- **Contract.** The caller specifies `mode` and `format`. `issue-response-reviewer` fixes `mode=issue` and `format=agent` because its role is specifically post-issue, agent-consumable findings (see `issue-response-reviewer.md` line 248: "Invoke `content-reviewer` in `issue` mode with `format: human` when the output will be integrated into a contributor-facing review. Use `format: agent` when consuming findings programmatically inside this agent's pipeline.").
- **Return shape.** The composed canonical's output follows its documented `format: agent` schema. The composing canonical does not parse prose; it consumes structured findings.
- **Delegation vs assembly.** The composing canonical delegates what the composed canonical already does well (overlap detection, structural integrity, style-guide checklist application) and adds what is unique to its role (field-by-field feedback, quality gates, YAML drafting, summary table). It does not duplicate composed-canonical checks.
- **Reference by filename.** Composition references use the canonical filename (`scripts/agents/content-reviewer.md`) or the agent name (`content-reviewer`), never a harness-specific path.

**2. Skill-to-agent composition (harness → canonical).**

A harness-level skill receives a natural-language invocation, gathers external context using harness-specific tools, invokes the appropriate canonical agent, and translates the returned findings into an external side effect.

- **Contract.** The skill is harness-specific. It may use `gh` CLI, web fetches, file reads, editor APIs, or any other tool the harness provides. The canonical agent it invokes is harness-neutral.
- **Return shape.** The skill receives the agent's documented output (findings, draft YAML, review comment) and performs the side effect (posts a comment, writes a file, opens a PR draft). The canonical agent does not know its output is being posted anywhere.
- **Per-harness layering.** A `/draft-issue-comment` slash command is one harness's layering over `issue-response-reviewer`. A different harness could layer a Cursor command, an Aider recipe, or a plain-CLI wrapper over the same canonical. Per ADR-006, harness layering is an implementation detail of the consuming environment, not part of the canonical pattern.

**3. Routing boundaries (what canonicals never do).**

Canonical agents under `scripts/agents/` do not perform external side effects. They do not post to GitHub, write files outside their declared outputs, call external APIs, or modify the repository. They return findings. Skills and orchestrators translate findings into side effects. This separation is what keeps canonicals portable.

The architect agent is the negative example that anchors the rule. [`scripts/agents/architect.md`](../../scripts/agents/architect.md) line 24-26 declares: "The architect does not itself invoke sub-agents; its output is the input for later phases. Callers route to the architect *before* invoking `swe` or `testing` when an architectural trigger fires." Orchestration is a caller concern, not an architect concern. The same is true of every other canonical: composition is declared; orchestration is performed by the caller above the canonical.

## Alternatives Considered

- **Monolithic agent (no composition).** Have `content-reviewer` emit contributor-facing comment drafts directly in `issue` mode, eliminating `issue-response-reviewer`. Rejected: this couples framework-content-review logic (what `content-reviewer` owns) to comment-assembly logic (what `issue-response-reviewer` owns). A second caller that wants raw findings — for example, a maintainer-facing audit tool or a batch-review pipeline — would have to parse a review comment to extract structured findings. The composition split keeps findings-generation reusable.

- **Skill-only orchestration (no `issue-response-reviewer` agent).** Have the harness skill invoke `content-reviewer issue` directly and assemble the comment itself. Rejected: comment-assembly logic (field-by-field feedback, quality gates, YAML drafting, summary-of-changes table) is portable across harnesses. The same comment shape works under any AI environment that can invoke the canonical agent. Pushing assembly into each harness's skill duplicates work, invites drift, and pushes canonical knowledge (the persona model, universal-control hygiene, style-guide citations) into harness-specific code where it does not belong.

- **Tight coupling via shared state.** Have composed agents communicate through a shared scratchpad file that each writes to and reads from. Rejected: this is fragile (every agent must agree on the scratchpad schema and file location), harness-specific (file I/O conventions differ across harnesses), and contradicts the canonical-as-portable principle. Explicit input-and-output contracts via mode/format flags are simpler and more durable.

## Consequences

**Positive**

- The two published orchestration flows (`issue-response-reviewer` composing `content-reviewer`; a harness skill wrapping `issue-response-reviewer`) have named, stable contracts. Breaking changes to either side now have a documented boundary to respect.
- Canonicals remain portable. A new harness can consume `issue-response-reviewer` or `content-reviewer` without inheriting any assumption about external side effects.
- The agent-to-agent composition pattern is reusable. When a future canonical needs to compose with an existing one, the `mode` + `format` flag contract is a template: name what you want, name how you want it back.
- Routing boundaries are explicit. "Canonicals return findings; callers perform side effects" is now a stated rule, not a convention enforced only by code review.

**Negative**

- Two-layer composition (skill → composing canonical → composed canonical) has more moving parts than a single-agent shape. When a bug appears in the end-to-end output, the maintainer must triage across three layers to locate the fault.
- The `format: agent` contract is an implicit schema. If `content-reviewer`'s `agent`-format output shape evolves, every composing canonical that consumes it must be reconciled. Mitigated by keeping the format documented in `content-reviewer.md` under Output Contract, but there is no automated schema-check today.
- Skill-layer code is untracked when the harness is contributor-local (per ADR-006, harness-specific wrapper directories remain excluded via `.git/info/exclude` or equivalent). Contributors using a different harness need to write their own skill from scratch; they cannot copy a tracked reference implementation from this repo.

**Follow-up**

- When the newer canonicals (`architect`, `testing`, `code-reviewer`, `swe`) have been exercised through one or more published orchestration flows, a follow-up ADR should capture their composition patterns. Expected flows include `architect → testing → swe → code-reviewer` for test-first implementation and `architect → swe → code-reviewer` for infrastructure work. Neither is currently battle-tested; both are declared in `architect.md` but have not been run end-to-end in live contributor-facing work.
- If a second harness is officially supported, the question of whether skill-layer code becomes tracked (versus maintainer-local) is a separate decision. Not in scope here.
- The `format: agent` output schema of `content-reviewer` would benefit from a JSON schema or equivalent contract document if the number of composing canonicals grows beyond `issue-response-reviewer`. Defer until that pressure exists.

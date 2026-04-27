# ADR-NNN: Short Decision Title

**Status:** Draft | Accepted | Superseded by [ADR-XXX](XXX-slug.md)
**Date:** YYYY-MM-DD
**Authors:** Name(s) or role(s)

---

## Context

What forces are at play? What problem, constraint, or opportunity motivates this decision? Link to the specific issue, PR, incident, or thread that surfaced the need. Keep to the facts that a future reader needs to understand *why a decision had to be made*, not a history of everything considered.

## Decision

What did we decide? State the outcome directly, in the present tense. If the decision has concrete shape (a file path, a tool, a pattern, a convention), name it explicitly. A reader should be able to answer "what are we doing now?" from this section alone.

If the decision has more than one component, structure it as numbered sub-sections with a `D` prefix: `### D1. {{Title}}`, `### D2. {{Title}}`, etc. Use sub-sub-sections (`#### D3a.`, `#### D3b.`) only when a parent decision has internal layering that earns its own heading. Internal cross-references use the same prefix (`D3`, `D3b`), not `§3` or "decision (3)". The stable IDs let per-rule enforcement tables and other ADRs cite specific decision components without depending on heading text.

Example shape:

```markdown
### D1. Allowlist

The renderer emits `<strong>`, `<em>`, `<a>`. …

### D2. Failure mode

Disallowed input is escaped, not stripped. …
```

## Alternatives Considered

Each alternative in one short paragraph: what it was, and the specific reason it was not chosen. Rejected options matter — they prevent the same debate from being reopened later without new information.

- **Option A** — summary; rejected because …
- **Option B** — summary; rejected because …

## Consequences

What does this decision commit us to, and what does it cost?

- **Positive:** capabilities gained, problems solved.
- **Negative:** new obligations, new ways to get it wrong, debt taken on.
- **Follow-up:** work this decision implies but does not itself perform (separate ADRs, issues, PRs).

---

### Authoring notes

- File name: `NNN-slug.md` where `NNN` is a zero-padded sequential number and `slug` is a short kebab-case phrase. Claim the next number by updating [`README.md`](README.md) in the same commit.
- Lifecycle: new ADRs land as `Status: Draft`. Maintainer review flips `Draft → Accepted`. When a later ADR replaces this one, change status to `Superseded by ADR-XXX` and link it.
- Scope: ADRs live here for **tooling, infrastructure, and process** decisions. Framework-content design (risk taxonomy, persona model, schema semantics) stays in [`risk-map/docs/design/`](../../risk-map/docs/design/).
- Style: keep each ADR focused on a single decision. If you find yourself writing two decisions, split them. Cite git commits, PRs, and issues with concrete references — retroactive ADRs especially need these.
- Delete this "Authoring notes" section from finalized ADRs.

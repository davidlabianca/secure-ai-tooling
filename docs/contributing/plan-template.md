# Implementation Plan Template

This file is the **canonical, tracked source** for implementation-plan documents. Plans themselves are maintainer-local working documents — they live in an untracked directory of your choosing, excluded from version control via `.gitignore` or `.git/info/exclude`. The specific path is a convention of your working environment and is not load-bearing.

Copy this template into that local directory when starting a new plan. For example, a contributor using Claude Code might keep working plans under `.claude/plans/`:

```sh
cp docs/contributing/plan-template.md <your-local-plans-dir>/<short-slug>.md
```

Plans capture phased execution of a specific piece of work. When a plan produces a **decision worth preserving** (tooling, infrastructure, or process), capture that decision as an ADR under [`docs/adr/`](../adr/) rather than leaving it buried in the plan.

Delete this intro and the "Authoring notes" section below from real plans; keep only the body template.

---

# Plan: {{Short title}}

**Status:** Proposed | In Progress | Completed | Abandoned
**Created:** YYYY-MM-DD
**Branch:** `feature/short-slug` (to be created from `main` or `develop`)
**Worktree:** `.worktree/<name>` (if applicable)

---

## Summary

One or two paragraphs stating what this work accomplishes and why now. A reader who lands here cold should understand the goal and the rough shape of the work without needing to read the phase breakdown.

## Decision matrix (locked)

Use this section when there are open choices that were debated and resolved before execution began. Each row is a specific question with a locked answer. If there are no pre-execution decisions, delete this section.

| # | Decision | Resolution |
|---|---|---|
| A | … | … |
| B | … | … |

---

## Phases

Break the work into ordered phases. Each phase has an exit criterion that can be objectively checked.

### Phase 1 — {{Phase name}}

One-sentence description of what this phase achieves.

| ID | Task | Agent | Output |
|---|---|---|---|
| 1.1 | … | swe / testing / architect / code-reviewer / content-reviewer | Concrete artifact |
| 1.2 | … | … | … |

**Exit criteria:** Specific observable state that means this phase is done.

---

### Phase 2 — {{Phase name}}

…repeat structure…

---

## Commit strategy

State how phase work maps to commits. Follow repo commit conventions (concise bodies, vendor-neutral `Co-authored-by: AI Assistant <ai-assistant@coalitionforsecureai.org>` trailer, no operator instructions).

1. **`type(scope): subject`** — what this commit contains
2. **`type(scope): subject`** — …

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| … | … |

## Out of scope (explicit)

List things that might be mistaken for part of this work but are not. Keeps scope creep honest.

- …
- …

## Open items to resolve during execution

Small enough to decide in-flight without blocking the plan:

1. …
2. …

## Dependencies

- Branching: which base branch, any worktree requirements.
- External: CI, service, or tooling changes required before execution.
- Internal: other plans or ADRs this work depends on.

## Rough effort estimate

| Phase | Estimate |
|---|---|
| Phase 1 | N focused session(s) |
| Phase 2 | N focused session(s) |

Total: …

---

### Authoring notes

- This template lives at `docs/contributing/plan-template.md` (tracked). Working copies live in whatever untracked local plans directory your working environment uses.
- Plans are **not** the place to store architectural decisions long-term. Lift decisions into ADRs under [`docs/adr/`](../adr/) as they solidify.
- When a plan is abandoned or completed, leave it in your local plans directory — it's untracked anyway. Successor plans may reference it for history.
- Delete this "Authoring notes" section from real plans.

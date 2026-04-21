# ADR-002: Branching strategy — `develop` for content, `main` for tooling

**Status:** Draft
**Date:** 2026-04-20
**Authors:** Architect agent, with maintainer review

---

## Context

Work in this repository lands in two visibly different streams:

- **Framework content** — edits to the risk, control, persona, and component YAML under `risk-map/yaml/` and the generated tables and design notes that track them. Authoritative review for these changes is *framework-expert*: the reviewer is judging taxonomy coherence, persona-model fit, and citation quality. The cadence is batched — content updates tend to arrive as themed sets (for example persona refinements, risk-ID migrations, framework-mapping edits) and are merged together after community review.
- **Tooling, infrastructure, and process** — devcontainer setup, pre-commit hooks, CI workflows, validators, agent definitions, issue templates, dependency bumps. Authoritative review here is *engineering*: the reviewer is judging correctness, test coverage, and blast radius. The cadence is incremental — small PRs land as soon as they pass review, not held for a themed batch.

Reflog evidence of both streams existing side by side:

- Content branches based off `develop`: `feature/content-update-1-april-2026`, `feature/compliance-to-style-guides-april-2026`, `feature/risk-id-camelcase-migration`, `feature/persona-updates-152-153`, `feature/risk-content-updates-apr-2026`.
- Tooling branches based off `main`: `codebugfix/format-list-trailing-newlines`, `codebugfix/env-issues-and-container`, `feature/precommit-framework-211-squashed` (merged as PR #222), Dependabot updates (PRs #219, #220).
- Periodic `main → develop` sync: commit `1bbc07f` on branch `merge/main-into-develop` with subject `merge: incorporate main infrastructure updates into develop`. This is the direction of travel for tooling fixes that content branches need.
- The current feature branch — `feature/architect-adr-adoption` — was cut from `main` because the work is tooling (introducing `docs/adr/`, an architect agent, and retroactive ADRs), not content. It is itself a live example of the split.

Forcing both streams onto a single trunk creates two specific frictions:

1. **Review contention.** A content PR sitting in the queue under framework-expert review blocks an unrelated infrastructure fix, or vice versa. The reviewers are different people with different availability; combining queues serializes work that does not need to be serialized.
2. **History pollution.** Content review generates long, taxonomy-specific discussion threads. Infrastructure review generates test and CI-log discussion. Merging both into one trunk makes `git log` and PR archaeology harder for both audiences — someone tracing a regression in a validator does not want to page through persona-model debate.

Today this split exists in practice but is documented only in `CLAUDE.md`, which is itself a maintainer-local file excluded via `.git/info/exclude` (entry `CLAUDE.md`). Contributors who clone the repository have no tracked reference for where to branch from or where to target their PRs. This ADR is the first tracked statement of the convention, captured under the ADR practice established by [ADR-001](001-adopt-adrs.md).

## Decision

Use a two-branch model:

- **`develop`** — integration branch for framework-content changes. New content work branches from `develop`, PRs target `develop`, and `develop` is periodically merged into `main` after community review of the accumulated content.
- **`main`** — trunk for tooling, infrastructure, CI, and process changes. Non-content work branches from `main` and PRs target `main` directly. `main` is also what external consumers pull as the published state of the repository.
- **Cross-pollination direction:** `main → develop` via an explicit merge commit when content branches need an infrastructure fix before the next `develop → main` batch (example: `1bbc07f`, `merge: incorporate main infrastructure updates into develop`). `develop → main` happens on the content-review cadence.

Concretely, when opening a PR:

- If the diff touches `risk-map/yaml/**` or the generated tables and design docs derived from it, branch from `develop` and target `develop`.
- If the diff touches `scripts/`, `.github/`, `.devcontainer/`, `pyproject.toml`, pre-commit config, dependencies, or other repository plumbing, branch from `main` and target `main`.
- Mixed PRs are discouraged; if a change genuinely spans both, split it, and land the tooling half on `main` first so the content half can rebase onto a `develop` that has absorbed the fix.

## Alternatives Considered

- **Single trunk (`main` only, all branches cut from `main`).** Rejected. The two review audiences are different, and batching content for community review is load-bearing for framework quality. A single trunk forces either per-PR community review (too slow for infrastructure) or per-PR engineering review of content (wrong expertise). It also merges the two commentary streams into one `git log`, making both harder to read.

- **Three-way split (adding `staging` or `release` between `develop` and `main`).** Rejected as overkill. The project has no scheduled release train and no staging environment to promote to. A third branch would add merge overhead without changing who reviews what, which is the actual reason the split exists.

- **GitFlow-style release branches.** Rejected for the same reason — GitFlow is designed around versioned releases with hotfix branches. The Risk Map publishes by merging `develop` into `main` on a rolling content-review cadence; there is no versioned artifact that a release branch would stabilize.

## Consequences

**Positive**

- Review queues stay separated by expertise. Framework reviewers see `develop` PRs; engineering reviewers see `main` PRs. Neither queue blocks the other.
- `main`'s history reads as an engineering log; `develop`'s history reads as a content log. Both are easier to mine than a combined trunk.
- External consumers who pull `main` get a coherent published state, not a snapshot mid-content-batch.
- The convention is now tracked. A contributor reading `docs/adr/002-branching-strategy.md` can answer "where do I branch from?" without access to maintainer-local files.

**Negative**

- Periodic `develop → main` merges require attention — content must be reviewed as a batch, not only per-PR. This is the tradeoff that buys the review-queue separation.
- Occasional `main → develop` sync merges are needed when a tooling fix must reach content branches before the next content batch. These merges are cheap but not free; see commit `1bbc07f` as the reference pattern.
- Mixed-intent PRs (one change that edits both content YAML and validator code) are awkward under this model and must be split. This is a real authoring cost when a content change uncovers a validator bug.
- Contributors unfamiliar with the split will occasionally target the wrong base branch. Mitigated by documenting the convention here and in the contributor-facing guides; PR template guidance is a follow-up.

**Follow-up**

- Reflect this convention in tracked contributor-facing documentation (the contributing guide plan tracks this). The goal is that new contributors do not need to read this ADR to pick the right base branch, but the ADR remains the authoritative *why*.
- Consider a PR template hint ("Is this a content change or a tooling change?") to reduce mistargeted PRs. Not part of this ADR.
- If the repository ever grows a scheduled release cadence or a published-site staging surface, revisit this ADR — a third branch may become justified, and this decision would be superseded rather than amended.

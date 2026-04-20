# Architecture Decision Records

This directory holds Architecture Decision Records (ADRs) for **tooling, infrastructure, and process** decisions in the CoSAI Risk Map repository. Each ADR captures the context that motivated a choice, the choice itself, alternatives that were considered, and the consequences the project is now living with.

ADRs complement — not replace — two other surfaces in this repo:

| Surface | Lives in | Audience | Scope |
|---|---|---|---|
| **ADRs** (this directory) | `docs/adr/` | Maintainers, contributors, tool integrators | Tooling, infra, CI/CD, agent architecture, repo-wide conventions |
| **Framework design docs** | [`risk-map/docs/design/`](../../risk-map/docs/design/) | Risk-map framework authors and consumers | Risk taxonomy, persona model, schema semantics, migration logic |
| **Implementation plans** | Local untracked plans directory (template source at [`docs/contributing/plan-template.md`](../contributing/plan-template.md)) | Maintainer, in-flight sessions | Phased execution of a specific piece of work |

If a decision is about *how the Risk Map content model is shaped*, it belongs in `risk-map/docs/design/`. If it is about *how the repository itself is built, tested, released, or extended*, it belongs here.

## Index

| # | Title | Status | Date |
|---|---|---|---|
| [001](001-adopt-adrs.md) | Adopt ADRs for tooling/infrastructure decisions | Draft | 2026-04-20 |

## Conventions

- **File name:** `NNN-slug.md` — zero-padded sequential number, kebab-case slug.
- **Numbering:** claim the next number by adding a row to the index table in the same commit that introduces the ADR.
- **Template:** start from [`TEMPLATE.md`](TEMPLATE.md). Sections are Status / Context / Decision / Alternatives Considered / Consequences.
- **Lifecycle:** `Draft` on first commit → `Accepted` after maintainer sign-off → `Superseded by ADR-XXX` when replaced. Superseded ADRs stay in place; do not delete history.
- **Single decision per ADR.** If the draft grows two decisions, split it.
- **Cite sources.** Retroactive ADRs in particular must cite the commits, PRs, and issues they summarize.

## Contributing

New ADRs are typically authored by the `architect` agent (to be introduced in a subsequent change; will live at `scripts/agents/architect.md`) when an in-flight change trips one of its triggers: schema changes, a new top-level directory, cross-module refactors, adding or removing an external tool dependency, adding or changing a CI workflow, and new features or tools that shape how the repo is built. Maintainers can also author ADRs directly. Either way, the ADR lands as `Status: Draft` and waits for sign-off before being marked `Accepted`.

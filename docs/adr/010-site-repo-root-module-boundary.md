# ADR-010: `site/` as a repo-root peer of `risk-map/`

**Status:** Accepted
**Date:** 2026-04-21
**Authors:** Architect agent, with maintainer review

---

## Context

The persona Pages MVP introduced a static GitHub Pages surface — HTML, CSS, and browser-side ES modules — that consumes framework data (personas, risks, controls) out of `risk-map/yaml/` and renders a persona-driven explorer. The MVP's initial commits (notably the `48565ca` / `e0dd0bb` / `0ccd701` triple) shipped those sources under `risk-map/site/`, nested inside the framework directory alongside the schemas and YAML they consume.

That nesting conflated two module boundaries that point in different directions:

- **`risk-map/`** is the framework itself — the YAML data model, the JSON schemas that govern it, the design docs under `risk-map/docs/design/`, and the generated tables and graphs derived from that content. Its audience is framework authors and framework consumers.
- **The static site** is a *consumer* of the framework. It reads framework YAML through a Python builder (`scripts/build_persona_site_data.py`), renders persona-matching UI, and ships to GitHub Pages. Its audience is end users of the explorer, and its lifecycle is a deployable build surface with its own CI workflow.

The nesting also broke an existing convention: every other subdirectory of `risk-map/` — `diagrams/`, `docs/`, `schemas/`, `svg/`, `tables/`, `yaml/` — holds framework data or documentation *about* that data. `risk-map/site/` was the only sibling that was neither, a deployable consumer app visually indistinguishable from its data-dir peers.

With the site nested inside `risk-map/`, a contributor editing framework data could not tell from path alone whether they were editing the framework or editing a consumer of it. The same question would recur for every future consumer: where does the next build surface land?

Commit `9c24ad3` (review finding tag `NIT-09`) resolved this within the MVP PR itself — not as a post-MVP follow-up — by relocating the site sources out of `risk-map/site/` and into a new top-level `/site/` directory, making it a peer of `/risk-map/` (framework) and `/scripts/` (build, hooks, agents) rather than a child of the framework. The move touched paths and absorbed in-worktree prettier formatting normalization; no renderer logic, no schema, and no workflow semantics changed. `NIT-09` was sequenced first in the PR's implementation plan so the downstream findings (`BLOCK-02` fix, `REC-*` UX/a11y work, workflow hardening) did not commit against paths about to be renamed. This ADR captures the module-boundary decision that move embodied, under the practice established by [ADR-001](001-adopt-adrs.md).

A **forward pointer exists** in [ADR-005](005-pre-commit-framework.md)'s Follow-up section (line 96), which speculatively named `risk-map/site/` as a possible future orchestration surface. That parenthetical predates `9c24ad3` and is now outdated. ADR-005 is an accepted historical record and is not edited; this ADR supersedes the parenthetical path guidance specifically.

## Decision

The static site sources live at the repository root as **`/site/`**, a peer of `/risk-map/` and `/scripts/`, not nested inside the framework directory.

Concrete shape:

- **Location.** `site/` at the repo root. Current contents: `site/index.html`, `site/assets/*.{mjs,css}`, `site/tests/*.test.mjs`, `site/generated/` (builder output target, gitignored).
- **Module role.** `site/` is a *consumer* of framework data, not part of the framework. It reads from `risk-map/yaml/` through `scripts/build_persona_site_data.py` and emits a static build artifact; it does not define or own any schema.
- **Data direction.** Framework → builder → site. The site never writes back into `risk-map/`, and `risk-map/` never imports from `site/`.
- **Future consumers.** Additional build or consumer surfaces land as their own top-level directories (peers of `site/` and `risk-map/`), not nested inside `risk-map/`. Nesting is reserved for surfaces that are part of the framework.

## Alternatives Considered

- **Keep `risk-map/site/` nested** (the original MVP layout, shipped in `48565ca` and moved by `9c24ad3`). Rejected: it conflates a consumer of framework data with the framework itself. Any future consumer would face the same question, and the answer should be the same for all of them; encoding that at the directory level is cheaper than re-deciding per surface.
- **Collapse into `docs/`.** Rejected: `site/` is a deployable build surface with its own CI workflow (`.github/workflows/persona-pages.yml`), generated artifacts, and a per-commit lifecycle. `docs/` already hosts ADRs, design notes, and contributing guides with a prose-documentation lifecycle; the two do not share build, deploy, or review cadence, and merging them would obscure both.
- **New top-level `site/`** (chosen). Preserves the "consumer of framework data" boundary, keeps the framework directory focused on framework content, and leaves room for additional build surfaces under their own top-levels without framework-shaped coupling.

## Consequences

**Positive**

- Module boundary reads correctly from the directory layout: `risk-map/` is the framework, `site/` consumes it, `scripts/` supports both. A contributor can tell from path alone which surface they are editing.
- Future build or consumer surfaces have an obvious landing pattern: their own top-level directory, not a subdirectory of the framework.
- Downstream references (the persona-pages CI workflow's `paths:` filters, the pre-commit `prettier_site_assets` hook's `^site/` regex, the persona-data builder's default output path, the renderer's relative asset paths) all resolve against a short, stable prefix.

**Negative**

- The `risk-map/site/` path is burned — anyone reading old commit history or PR threads will see a path that no longer exists.
- The top-level directory count grew by one. Adding a top-level is itself a trigger for this ADR practice (see [ADR-001](001-adopt-adrs.md)); this is the first exercise of that trigger for a non-tooling surface, and future surfaces should expect to do the same.
- Path-shaped cross-references are cheap to miss. Any docs, scripts, or workflow hooks that held `risk-map/site/` must be updated in the same change as the move; `9c24ad3` did this sweep, but the discipline is ongoing for future rearrangements.

**Follow-up**

- **Supersedes** the parenthetical path guidance in [ADR-005](005-pre-commit-framework.md)'s Follow-up (line 96) that named `risk-map/site/` as a possible future orchestration surface. The broader question it raised — whether `pre-commit` remains the right orchestration layer for a non-Python site-build surface — is unchanged and still open; only the path is corrected.
- The downstream persona-Pages decisions that depend on this module boundary land as separate ADRs: the CI workflow (ADR-009), the builder output contract (ADR-011), the renderer SPA architecture (ADR-012), and the `site/**` pre-commit hook (ADR-013). Each cites this ADR as prior decision.
- If a future consumer surface is proposed to nest inside `risk-map/` (for example, a framework-specific viewer tightly coupled to the schema rather than to the content), revisit this ADR — the boundary argument may not apply, and a targeted supersession would be clearer than bending the rule.

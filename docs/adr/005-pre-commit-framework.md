# ADR-005: Adopt the `pre-commit` framework for hook orchestration

**Status:** Draft
**Date:** 2026-04-20
**Authors:** Architect agent, with maintainer review

---

## Context

Before the framework migration, this repository enforced its pre-commit checks with a custom bash harness under `scripts/` — a single `pre-commit` shell script plus per-hook installation logic (`install-precommit-hook.sh`), all maintained in-tree. That harness had grown to roughly 1,500 lines across the installer, the dispatcher, and the individual validators' shell wrappers (deleted in #211). Four specific problems were visible from the outside:

1. **Per-hook install drift.** Every hook had its own install path (`scripts/install-precommit-hook.sh` and adjacent wrappers). When a contributor's local copy diverged — a missing `chmod +x`, a stale symlink, a hook added after their last clone — commits that should have been rejected landed clean. The failure mode was silent.
2. **Duplicate YAML parsing.** Several hooks each re-implemented "load the risk-map YAML, iterate components/risks/controls." Schema and consistency logic were not sharing a parser, so keeping them in agreement required edits in multiple shell scripts per change.
3. **No standard runner.** Running "all hooks against the full tree" — the equivalent of `pre-commit run --all-files` — required either committing a throwaway change or scripting an ad-hoc loop. There was no single supported command for contributors (or CI) to pre-validate a working copy end-to-end.
4. **No idiomatic way to consume upstream hooks.** Wiring a packaged hook like `check-jsonschema` or `ruff` into the bash harness meant writing another wrapper and another install step, rather than adding a few lines of config. The ergonomic cost kept hook coverage lower than it should have been.

On top of this, the set of checks the repository actually wanted was growing: per-YAML schema validation, metaschema validation of the `.schema.json` files themselves, prettier for YAML formatting, ruff for Python lint and format, risk-map consistency validators (component edges, control-to-risk references, framework references), GitHub issue-template regeneration and validation, and three generators (Mermaid graphs, markdown tables, Mermaid→SVG). Continuing to wire each of those into a bespoke bash harness — with its own install drift, its own duplicated parsing, and its own lack of a standard runner — was not sustainable.

The generator hooks in particular were the forcing function. Each of the three generators (graphs, tables, SVGs) needed to run in "Mode B auto-stage" — detect that a source file was staged, regenerate the derived artifact, and `git add` the regenerated output so it landed in the same commit. Implementing that pattern correctly in bash is possible but fiddly: staged-file detection, parallelism guards to avoid `git add` racing over `.git/index.lock`, and the interaction with `--all-files` semantics all had to be handled by the harness author. Moving to a framework that already understood hook lifecycle, file filtering, and serialization was considerably cheaper than continuing to implement those primitives ourselves.

The motivating PRs:

- **PR #211 — `feat: adopt pre-commit framework`** (also titled later as *"fix: --all-files regressions, schema meta-validation, side-effect caveat"* after its scope expanded during review). Introduced `.pre-commit-config.yaml`, the `scripts/hooks/precommit/` wrapper modules, and deleted the legacy bash harness.
- **PR #222 — squashed merge** of branch `feature/precommit-framework-211-squashed`, the commit that actually landed the framework on `main`.
- **PR #221 — `chore: remove pre-commit framework parity gate`**, which retired a temporary belt-and-suspenders that had run the legacy bash hook and the new framework side by side on every commit to catch behavioral drift during the transition.

This ADR documents the decision retroactively, under the ADR practice established by [ADR-001](001-adopt-adrs.md).

## Decision

Use the [`pre-commit` framework](https://pre-commit.com) as the single orchestration layer for repository-wide git hooks. Concrete shape:

- **Configuration:** [`.pre-commit-config.yaml`](../../.pre-commit-config.yaml) at the repo root. All hooks — upstream and local — are declared there.
- **Install command:** `pre-commit install`. Step 8 of `scripts/tools/install-deps.sh` runs this as part of the standard environment bootstrap, so a fresh devcontainer arrives with hooks already wired up.
- **Full-tree run:** `pre-commit run --all-files`. This is the canonical "validate everything" command, documented in `CLAUDE.md` and used by CI.
- **Python-side hooks** live under [`scripts/hooks/precommit/`](../../scripts/hooks/precommit/) (framework-invoked wrappers: `prettier_yaml.py`, `regenerate_issue_templates.py`, `regenerate_graphs.py`, `regenerate_tables.py`, `regenerate_svgs.py`, `validate_all_schemas.py`) and under [`scripts/hooks/`](../../scripts/hooks/) (validators directly invoked by the framework: `validate_riskmap.py`, `validate_control_risk_references.py`, `validate_framework_references.py`, `validate_issue_templates.py`).

The hook categories the framework now orchestrates:

| Category | Hooks |
|---|---|
| Schema validation (per YAML) | `check-jsonschema` per `(yaml, schema)` pair under `risk-map/` |
| Schema meta-validation | `check-metaschema` over every `risk-map/schemas/*.schema.json` |
| Master-schema fan-out | `validate-all-yaml-on-master-schema-change`, triggered by `riskmap.schema.json` edits |
| YAML formatting | `prettier-yaml` (local, via project's existing Node + `.prettierrc.yml`) |
| Python lint + format | `ruff` and `ruff-format` (from `astral-sh/ruff-pre-commit`) |
| Risk-map consistency | `validate-component-edges`, `validate-control-risk-references`, `validate-framework-references` |
| Issue templates | `regenerate-issue-templates` followed by `validate-issue-templates` (sources under `scripts/TEMPLATES/`, generated output under `.github/ISSUE_TEMPLATE/`) |
| Generators (Mode B auto-stage) | `regenerate-graphs`, `regenerate-tables`, `regenerate-svgs` — each `git add`s its outputs so generated artifacts land in the same commit as the source edit |

Operational properties worth pinning:

- **Parity gate is gone.** During the transition period, #211 kept the legacy bash harness running alongside the framework and required both to agree before a commit was accepted — a belt-and-suspenders intended to surface any behavioral drift. That gate was retired by #221 once the framework had run in production long enough to establish equivalence; the target state is framework-only. A structural test suite (`scripts/hooks/tests/test_precommit_hook_install.py`) was added in the same era to assert that the expected hook ids, file regexes, and `pass_filenames` settings remain declared in `.pre-commit-config.yaml`, and that `install-deps.sh` still invokes `pre-commit install`.
- **Schema meta-validation posture.** The metaschema check (`check-metaschema`) runs whenever any `risk-map/schemas/*.schema.json` file is staged — it validates each schema document against its declared `$schema` metaschema, catching typo'd keywords (e.g., `requried` for `required`), invalid regex patterns, and broken `$ref`s at author time rather than at validation time. Separately, edits to the master `riskmap.schema.json` trigger a full re-validation of every YAML via the `validate-all-yaml-on-master-schema-change` hook, because a change to the master can affect any downstream YAML's validity through `$ref` resolution. These two behaviors are distinct and complementary: meta-validation checks that the schemas are well-formed; the master-trigger fan-out checks that the content still matches them. The combined posture means a commit that edits schemas always pays for structural correctness and, when the master changes, also pays for downstream consistency — the two costs are independent.
- **`pass_filenames` discipline.** Several local hooks set `pass_filenames: false` deliberately — `regenerate-issue-templates` does this to avoid parallel `git add` contention over `.git/index.lock` when many trigger files match at once, and the schema validators do it because the framework would otherwise append both the YAML and its schema as positional args to `check-jsonschema`. These are not cosmetic choices; the inline comments in `.pre-commit-config.yaml` document the rationale and should be preserved through future edits.

## Alternatives Considered

- **Keep the custom bash hooks.** Rejected. The four problems listed in Context — install drift, duplicated YAML parsing, no standard runner, no idiomatic path for upstream hooks — were all symptoms of owning the orchestration layer ourselves. Staying on bash would require us to keep building (and keep fixing) the plumbing that `pre-commit` already provides, with no offsetting benefit. The ~1,500 lines of legacy harness were pure liability once an equivalent ecosystem tool existed.

- **Husky (Node-based hook manager).** Rejected. Husky is a capable orchestrator, but it ties hook management to a Node runtime. The repository's primary toolchain for validation logic is Python (validators, generators, schema checks), and the YAML-formatting Node dependency is already scoped narrowly to prettier. Adopting Husky would broaden Node's footprint from "one formatter" to "the thing that decides whether a commit succeeds," for no capability gain over `pre-commit`. It would also make a contributor's ability to commit depend on a successful `npm install`, which is a stronger dependency than the current "prettier runs when YAML is staged" arrangement.

- **Lefthook.** Rejected. Lefthook is a reasonable alternative and has grown a real ecosystem, but `pre-commit`'s hook registry is the de facto standard in the Python-heavy open-source space we sit in (`check-jsonschema`, `ruff-pre-commit`, and similar are published as `pre-commit` hooks first). Choosing Lefthook would mean either re-wrapping those upstream hooks as local Lefthook entries — reintroducing the very "local wrapper per upstream tool" tax that the migration was intended to eliminate — or accepting the maintenance cost of running them outside any orchestration layer.

- **No hooks at all — rely on CI.** Rejected. Schema, consistency, and generator errors are expensive to catch at PR time compared to pre-commit time: the author has already pushed, a reviewer has already been requested, and the feedback loop is now minutes-to-hours instead of seconds. Pre-commit hooks are the cheap local gate; CI remains the authoritative final gate, but the two serve different roles. Generators in particular cannot reasonably live in CI-only — they modify the tree, and a CI-only generator would flag every PR as "generated outputs are stale" rather than keeping them fresh with the source edit.

- **Framework with the parity gate kept in place permanently.** Considered during the transition and ultimately rejected by #221. The parity gate was valuable while we lacked confidence that the framework had captured the legacy harness's full behavior, but once that confidence was established, the gate was pure overhead: every commit paid the cost of running both systems, and every hook change had to be mirrored in two places. The target state is framework-only; the gate was a transitional posture, not a steady-state design. Permanence would also have blocked the legacy harness's deletion, keeping the 1,500 lines of bash on life support and defeating a primary motivation for the migration.

## Consequences

**Positive**

- **One supported way to install and run hooks.** `pre-commit install` and `pre-commit run --all-files` are the only commands contributors or CI need to know. Install drift across contributor machines is no longer a failure mode.
- **~1,500 lines of bespoke harness deleted** in #211. The repository no longer owns and maintains an orchestration layer; it consumes one.
- **Standard ecosystem integration.** Upstream-maintained hooks (`check-jsonschema`, `check-metaschema`, `ruff`, `ruff-format`) arrive pre-packaged with pinned revisions, and `pre-commit autoupdate` is the supported upgrade path. Local hooks and upstream hooks share the same declaration surface, so a contributor adding a new validator follows the same config pattern as any existing hook.
- **Hook isolation by default.** The framework creates an isolated environment per upstream hook repo (cached under `~/.cache/pre-commit/`), which eliminates "works on my machine" version skew for `check-jsonschema` and `ruff`. Local hooks still run in the project's own Python environment, which is the intended boundary — validators that need to import `scripts.hooks.riskmap_validator` must share the project venv, while upstream tools must not.
- **Two-stage schema posture is explicit.** Per-file schema validation, metaschema validation of the schemas themselves, and master-schema fan-out are now three distinct hook entries in `.pre-commit-config.yaml` — anyone reading the config can see the validation model at a glance.
- **Generators run with sources.** The Mode B auto-stage pattern (`regenerate-graphs`, `regenerate-tables`, `regenerate-svgs`) ensures generated artifacts land in the same commit as their source edits, eliminating "forgot to regenerate" PR comments.

**Negative**

- **New external dependency.** `pre-commit` itself is now a pinned requirement in `requirements.txt`, and the devcontainer bootstrap depends on it. Supply-chain risk is bounded (it is a well-maintained, widely-used Python package) but not zero.
- **Framework semantics contributors must learn.** `pass_filenames`, `require_serial`, `files:` regex filters, and `local` vs. upstream repo entries all have behaviors that diverge from "just run this script." The `.pre-commit-config.yaml` in this repo documents several of these in inline comments (for example, the `pass_filenames: false` rationale on `regenerate-issue-templates` to avoid parallel `git add` contention), but the learning curve is real. Contributors writing their first local hook should expect to consult those comments and the upstream framework docs before matching an existing pattern.
- **Parity confidence is now historical.** The parity gate removed in #221 was the live, per-commit evidence that the framework matched legacy behavior. After removal, equivalence is asserted rather than continuously measured. If a behavioral regression is introduced during a hook refactor, it would be caught by tests and CI but not by a parity harness.
- **`--all-files` has sharper edges than a bash loop.** The framework invokes hooks with full batched file lists, which surfaced regressions in wrappers that had been written for the single-file case. #211 fixed several of these explicitly (noted in the PR's "--all-files regressions" scope), but the general caveat stands: any new local hook must be correct under both partial-staging and `--all-files` invocation.
- **Side-effect hooks are a framework-specific pattern.** The generators (`regenerate-graphs`, `regenerate-tables`, `regenerate-svgs`) modify the working tree and `git add` the result. This is idiomatic in `pre-commit` but worth flagging: a hook that changes files means `pre-commit run` is not a pure check — running it can alter the diff. This was called out in #211 as the "side-effect caveat" and is the reason each generator hook sets `require_serial: true`.

**Follow-up**

- Keep the `.pre-commit-config.yaml` inline comments current as hooks evolve — they encode non-obvious operational rationale (the `pass_filenames` notes, the `require_serial` notes) that is expensive to rediscover.
- If a future hook refactor materially changes validation coverage, consider reintroducing a bounded parity check (new-vs-old, or framework-vs-golden-output) for the duration of that refactor, modeled on the #221 gate.
- Revisit `pre-commit autoupdate` cadence. Pinned revisions in `.pre-commit-config.yaml` (`check-jsonschema` 0.37.1, `ruff-pre-commit` v0.15.10 at time of writing) are good hygiene but need periodic bumps; Dependabot does not currently track them.
- If the repository adds a non-Python orchestration surface in the future (for example, a site build under `risk-map/site/`), confirm that `pre-commit` remains the right orchestration layer for that surface or document the split explicitly.
- Consider adding a CI job that runs `pre-commit run --all-files` against every PR as a belt-and-braces over local hook execution — contributors can skip hooks locally with `--no-verify`, and a CI gate closes that escape hatch without forcing the parity harness back into the commit path.

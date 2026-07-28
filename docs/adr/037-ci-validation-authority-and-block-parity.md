# ADR-037: CI as the enforcing gate for risk-map validation — `--block` parity and the graph-generation exception

**Status:** Draft
**Date:** 2026-07-27
**Authors:** Architect agent, with maintainer review

---

## Context

[ADR-025 D9](025-testing-strategy.md) declared the project's parity posture: **CI is the authoritative final gate**, local `pre-commit` is the cheap iteration gate, and divergence between them is tolerated. The tolerated divergence was assumed to run one direction — CI reproducing a clean checkout and fresh dependency install that local cannot cheaply match.

For risk-map validation the divergence ran the *other* direction, and inverted the posture. Line references below are as of the base commit `f87db8e`.

- `.github/workflows/validation.yml:195` ran `python3 validate_riskmap.py --force` with **no** `--block`. `.pre-commit-config.yaml:211` did pass `--block`. Risk-map warn-only checks were therefore blocking locally and advisory in CI.
- The practical effect was backwards: a contributor who installed the hooks was gated by findings that a contributor who had *not* installed them could merge past. The worse-configured setup got the more permissive gate, and the merge decision depended on a contributor's local state rather than on the repository's.
- The repository already conceded that hook installation cannot be assumed. `validate_tables.yml:256` prints "The pre-commit hook should do this automatically. If tables are out of sync, the hook may not be installed."
- `--block` is **per-check, not global.** It gates a single `warn_block_triggered` boolean (`validate_riskmap.py:286`) that only warn-only checks set — `check_controls_components_mirror` (`:296-303`) and `check_category_subcategory_nesting` (`:327-336`) — consumed by a unified exit at `:346-348`. Component edge consistency, missing-component references, isolated components, and lifecycle-stage order uniqueness (`:249-271`) already exit 1 with no `--block`. The blast radius of adding the flag is confined to the warn-only tier.
- The flip was empirically safe when measured. `--force --block` exited 0 on `develop`, on `main`, and on the branch implementing [ADR-036](036-decoupled-component-graph-emission.md), with zero warnings from any warn-only check. Non-vacuity was confirmed rather than assumed: injecting a bogus component reference made the mirror check fire and exit 1.
- A hard ordering constraint blocked the naive "add `--block` everywhere" version. `sys.exit(1)` at `validate_riskmap.py:346-348` sits **before** the `if args.to_graph:` block at `:350` and the sibling emission blocks after it. Verified: `--force --block --to-graph` exits 1 and writes **no graph file**. Adding `--block` to the graph-validation job (`validation.yml:336`) would surface a content warning as "`${graph_name}` generation via `validate_riskmap.py` failed", masking the real cause and skipping the diff-against-committed comparison entirely.
- A parallel gap of the same class existed. `validate_framework_references.py` also has `--block` (promoting deprecated-persona warnings to errors, `:533-539`, `:600`); `.pre-commit-config.yaml:225` passed it and `validation.yml:269` did not.
- Motivating the general rule rather than the one-line fix: a path-resolution bug had made a category guard **vacuous** under CI's copy-to-root layout — it resolved its schema relative to its own module path, which the copy invalidates, then swallowed the miss and iterated an empty set. A check can be wired into CI, run, report success, and verify nothing. That is the ADR-025 D10 failure class extended one level — reachable from the execution surface, yet still not enforcing.

## Decision

### D1. CI is the enforcing gate; pre-commit is a fast preview of it

We adopt **strictness monotonicity** as the corollary ADR-025 D9 left unstated: for any validator invoked from both surfaces, the CI invocation is at least as strict as the pre-commit invocation. Where the two differ, CI is stricter, never laxer.

This settles the developer question directly. Contributors who have not installed hooks are fully covered, because nothing depends on their having done so. Hooks are an accelerator that moves a failure from minutes-after-push to seconds-before-commit; they are not load-bearing for correctness. "The hook may not be installed" stops being a caveat and becomes a statement about latency.

*Testable requirement:* for every validator invoked by both `.pre-commit-config.yaml` and a workflow under `.github/workflows/`, the strictness flags in the CI invocation are a superset of those in the hook invocation. This is assertable as a config-level test that parses both files and compares argument sets — it needs no subprocess execution.

### D2. `--block` is added to the risk-map validation job

`validation.yml:195` becomes `python3 validate_riskmap.py --force --block`.

The general rule: **every CI invocation of a validator whose job is to decide pass/fail carries the strictness flags its corresponding pre-commit hook carries.** A warn-only check therefore has exactly two supported states — warn everywhere (no `--block` on either surface) or block everywhere. "Blocking locally, advisory in CI" is not a supported state.

Because all warn-only checks share the single `warn_block_triggered` boolean, adding a new warn-only check to `validate_riskmap.py` automatically makes it CI-blocking. That is intended: a new warn-only check lands block-ready or it does not land. [ADR-036](036-decoupled-component-graph-emission.md)'s emission work adds two such checks — category style/ownership and emission drift — both wired into the same boolean, and D2 governs them like any other.

### D3. `--block` is prohibited on graph-generation invocations

No invocation of `validate_riskmap.py` that passes `--to-graph`, `--to-controls-graph`, or `--to-risk-graph` may also pass `--block`. This applies to the graph-validation job at `validation.yml:336` and to any future emission call site.

The reason is the ordering constraint in Context: the warn-only exit at `:346-348` precedes every emission block, so `--block` causes the process to terminate before writing any graph. The job would then report a generation failure for what is actually a content warning, misattributing the cause, and the diff-versus-committed comparison — the entire point of that job — would never execute. A check that reports the wrong cause is worse than one that reports nothing.

This codifies existing practice rather than changing it: the local graph-regeneration hook already invokes `--to-graph` without `--block` (`scripts/hooks/precommit/regenerate_graphs.py:62`), so D3 is consistent with D1 — the two surfaces agree here.

D3 is a prohibition on the **invocation**, not an endorsement of the ordering. We deliberately do not reorder `sys.exit` relative to the emission blocks in this decision; doing so would make graph emission conditional on warn-only content state and change what a generated graph file means. That is a larger change with its own blast radius, recorded as follow-up.

D3 costs no coverage. The dedicated risk-map job under D2 runs `--block` against the same corpus in the same CI run, so a warn-only failure still fails the pull request — it just fails in the job whose error message is accurate.

*Testable requirement:* a test asserts that no workflow step passes `--block` together with any graph-emission flag.

### D4. The `validate_framework_references.py` parity gap closes in this decision

`validation.yml:269` becomes `python3 validate_framework_references.py --force --block`.

This is the same class of gap governed by the same rule, so splitting it into its own ADR would produce a second document with one rationale while leaving a known gap open in the interim. It closes here.

Safety is established the same way as D2. `--block` on this validator promotes deprecated-persona warnings to errors, and `check_deprecated_persona_usage` (`:345-388`) inspects only `controls[].personas` and `risks[].personas` against personas marked `deprecated: true`. `personaModelCreator` and `personaModelConsumer` are defined-and-deprecated in `personas.yaml` and referenced by **zero** controls and **zero** risks across the tracked corpus; the only other occurrences are in `risk-map/yaml/archive/self-assessment-legacy.yaml`, which this validator does not read. The check yields no warnings today.

*Testable requirement:* implementation confirms this empirically by running the command, not by inspection alone, and confirms non-vacuity by injecting a deprecated-persona reference and observing exit 1 — per ADR-025 D10.

One consequence to flag, narrower than it first appears: reintroducing a reference to a deprecated persona now fails CI rather than warning. This does not pre-empt the open question of whether the legacy personas are retained as `deprecated` or removed from the id enum — the gate is compatible with either. Under retention it enforces the no-new-references posture; under removal the closed id enum rejects such a reference at schema validation anyway, and the check becomes redundant rather than wrong. What changes is only that a *deliberate* re-reference — during a backward-compatibility migration, say — becomes an error requiring an explicit decision rather than a warning that can be passed over.

### D5. The copy-to-root arrangement stays, with the reasoning recorded

Five steps in `validation.yml` (`:44-47`, `:183-185`, `:222`, `:259`, `:298-300`) copy validator sources to the repository root before running them. We do not replace this with `PYTHONPATH` in this decision, and we record why the arrangement is nonetheless a liability.

The arrangement materializes a **different directory layout in CI than the one contributors and the test suite run against**. Any code that resolves a path relative to its own module location behaves differently across the two. That is precisely the mechanism behind the vacuous category guard cited in Context, and it is a standing source of the "wired but checking nothing" failure that D1 exists to prevent. A `PYTHONPATH`-based invocation that runs the validators in place would eliminate the divergence.

It is not changed here for two reasons: replacing it touches five steps across five jobs, and the fix for the vacuous guard resolves the schema relative to the working directory, which assumes the current layout. Changing the layout in the same decision would collide with that fix; the two must be sequenced, not merged.

*Constraint for implementers:* do not "improve" the copy-to-root layout as part of the `--block` flip. D2 and D4 must not be blocked on D5, and the implementation diff should contain no layout change.

### D6. Landing surface

This is `main`-based infrastructure per [ADR-002](002-branching-strategy.md): the change touches `.github/workflows/` and no file under `risk-map/yaml/`. Branches based on `develop` inherit the stricter gate when `develop` next merges from `main`.

Any change that adds a warn-only check under the shared boolean (D2) carries the obligation to verify `--force --block` exits 0 against its own corpus before merging. The rule governs the change; the verification lands with it, not here. This applies to every such change, not only those open when this decision was taken.

## Alternatives Considered

- **Remove `--block` from pre-commit instead** — restore monotonicity by making the warn-only tier advisory on both surfaces. Rejected: it restores consistency by discarding the checks. The warn-only tier exists to become blocking once the corpus is clean, and the corpus is clean now; this option spends that readiness for nothing.
- **Replace per-check `--block` with a global `--strict` flag** — rejected: `--block` is already tier-scoped with a unified exit, so this is a rename with no behavior change. It would break every pre-commit entry and every branch carrying a `--block` invocation simultaneously, to buy a nicer flag name.
- **Defer the framework-references gap (D4) to a separate ADR** — rejected: identical class, identical rule, identical safety argument. Splitting yields two documents sharing one rationale and leaves a known gap open meanwhile.
- **Reorder `sys.exit` to follow graph emission, making `--block` safe everywhere** — rejected for this decision: it makes emission depend on warn-only content state and changes the meaning of a generated graph file. D3's prohibition achieves the same safety at no risk; the reordering question is recorded as follow-up rather than resolved by omission.
- **Move risk-map validation into a single `pre-commit run --all-files` CI job** — genuinely attractive: it delivers parity by construction and eliminates the copy-to-root problem (D5) outright. Rejected here because it collapses the per-job `status` outputs that the workflow's summary job consumes, making it a workflow-topology change rather than a strictness change. Worth revisiting as its own ADR.

## Consequences

**Positive**

- The merge decision no longer depends on a contributor's local configuration. What CI enforces is what the repository enforces.
- The warn-only tier becomes real. Controls↔components mirror drift and category/subcategory nesting violations can no longer reach `main` or `develop`.
- The rule is general, so the next validator that grows a strictness flag has a stated answer instead of a fresh debate, and any warn-only check added later is governed on arrival rather than needing its own decision.
- Schema-integrity axis: closes a path by which malformed cross-references between controls, components, risks, and personas could pass CI. The change strictly narrows what merges.
- No new dependency, no new network fetch, no new workflow permission, and no new use of `secrets.*`. Supply-chain and workflow-exposure surface are unchanged.

**Negative**

- CI can now fail on findings that previously passed silently, including on branches opened before this lands. The failure output is per-warning (each is printed before the unified exit line at `:347`), so messages are actionable, but the first occurrence will surprise someone.
- The warn-only tier loses any "soak" capability: there is no longer a way to land a check in observe-only mode in CI while a backlog is cleaned up. This was already true locally; the decision extends it rather than introducing it.
- D3 creates a rule that is invisible at the call site — nothing in `validate_riskmap.py` prevents passing `--block` with `--to-graph`, and the failure it produces is misleading rather than loud. The prohibition depends on the test named in D3 to hold.
- D5 knowingly leaves a fragile arrangement in place, and with it the class of bug that motivated the general rule.

**Follow-up**

- Replace copy-to-root with a `PYTHONPATH`-based invocation (D5). Sequenced after the working-directory-relative schema resolution it would otherwise collide with, since that fix assumes the current layout.
- Resolve the `sys.exit` ordering relative to graph emission (D3), or record that the current ordering is intentional and permanent.
- Implement the strictness-monotonicity test from D1 as a standing guard, so a future workflow edit cannot silently reintroduce the gap this ADR closes.
- Revisit the single `pre-commit run --all-files` CI job once the workflow-summary dependency on per-job outputs is addressed. Note that `--all-files` enumerates tracked files only, so a newly added file is invisible to it until first staged — a limitation to account for if that job is adopted as the verification surface.

No follow-up is owed for the deprecated-personas terminal-state question. D4's gate holds under either resolution — retention or removal from the id enum — so it neither decides that question nor waits on it.

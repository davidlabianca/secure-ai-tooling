# ADR-029: Dual Python package-management path with `uv` devcontainers

**Status:** Draft
**Date:** 2026-06-06
**Authors:** Architect agent, with maintainer review

---

## Context

Issue [#159](https://github.com/cosai-oasis/secure-ai-tooling/issues/159) proposes replacing `pip` with [`uv`](https://docs.astral.sh/uv/) across the repository's Python dependency-management surface. The issue was filed because [`scripts/tools/install-deps.sh`](../../scripts/tools/install-deps.sh) installs packages with `python3 -m pip install -r requirements.txt`, while [`scripts/tools/verify-deps.sh`](../../scripts/tools/verify-deps.sh) later verifies them with `python3 -m pip show`. In environments mediated by `mise` shims, those two commands can resolve to different Python package locations, so verification can report packages missing after installation succeeded.

The current repository is intentionally scriptable outside the devcontainer. [ADR-003](003-devcontainer-mise-architecture.md) makes `install-deps.sh` and `verify-deps.sh` separately invocable for contributors who cannot or do not use the VS Code devcontainer. [`requirements.txt`](../../requirements.txt) is the current Python dependency input; [`pyproject.toml`](../../pyproject.toml) only holds pytest and coverage configuration; [`.github/dependabot.yml`](../../.github/dependabot.yml) tracks Python dependencies through the `pip` ecosystem; and workflows such as [`.github/workflows/validate_python.yml`](../../.github/workflows/validate_python.yml) install from `requirements.txt`.

The scope this ADR records is narrower than the original issue proposal: the repository should not force every contributor to adopt `uv` instead of `pip`. The devcontainer can be opinionated because it is the repository-managed bootstrap path, but contributors working outside the container should have a supported choice between the existing `pip` path and a `uv` path.

The decision also has to preserve the pre-commit architecture. [ADR-005](005-pre-commit-framework.md) adopts the `pre-commit` framework, and [ADR-013](013-site-precommit-hooks.md) deliberately keeps local hooks on `language: system` so they use the project's Python environment instead of isolated pre-commit-managed virtual environments. A `uv` implementation that syncs packages into `.venv` but leaves hook execution resolving `python3` from the ambient shell would only move the mismatch from install/verify into commit-time validation.

This ADR is a tooling/infrastructure decision under [ADR-002](002-branching-strategy.md): it targets `main`, not `develop`.

## Decision

Adopt a **dual Python package-management path**: the devcontainer uses `uv` with a repo-local virtual environment, while non-container contributors may choose either `pip` or `uv`.

Concrete shape:

- `requirements.txt` remains the shared dependency input for this decision.
- The devcontainer invokes `install-deps.sh` in `uv` mode.
- `install-deps.sh` and `verify-deps.sh` expose an explicit package-manager selector.
- Verification and pre-commit installation use the same Python environment selected during installation.
- CI, tests, and documentation keep both modes real.

### D1. Keep `requirements.txt` as the dependency input

Python development dependency pins remain in [`requirements.txt`](../../requirements.txt). Both package-management modes consume that file:

- `pip` mode installs with `python3 -m pip install -r requirements.txt`.
- `uv` mode creates or reuses a repo-local `.venv` and syncs the same input with `uv`'s pip-compatible interface, for example `uv venv` followed by `uv pip sync requirements.txt`.

This ADR does **not** migrate the dependency declaration into `pyproject.toml` (`[dependency-groups]` or `[project.dependencies]`), introduce `uv.lock`, or remove `requirements.txt`. These are independent of the bootstrap fix: `requirements.txt` is already consumable by both `pip` (`-r`) and `uv` (`uv pip sync` / `uv pip install -r`), so no declaration-format change is a prerequisite for fixing issue #159. Deferring the move also keeps this PR off the current six-workflow CI cascade a format change would trigger (see Consequences). A future change may adopt `pyproject.toml` `[dependency-groups]`, but it must update or supersede this ADR rather than fold that migration into the bootstrap fix.

### D2. Use `uv` unconditionally in the devcontainer

The devcontainer path uses `uv` for Python package installation and package verification. `uv` is declared as a **pinned** `mise`-managed tool in [`.mise.toml`](../../.mise.toml) - an explicit version, not `latest` - so the forced-`uv` path stays deterministic (upgrade cadence reconciled with ADR-023 when it lands). [`.devcontainer/devcontainer.json`](../../.devcontainer/devcontainer.json) invokes:

```bash
bash scripts/tools/install-deps.sh --python-package-manager uv
```

If `uv` is unavailable on the devcontainer path, `install-deps.sh` fails with an actionable error. It does not silently fall back to `pip`, because fallback would preserve the exact class of mismatch issue #159 is trying to remove from the managed bootstrap path.

### D3. Make the non-container choice explicit

Outside the devcontainer, `install-deps.sh` and `verify-deps.sh` support:

```bash
./scripts/tools/install-deps.sh --python-package-manager pip
./scripts/tools/install-deps.sh --python-package-manager uv
./scripts/tools/verify-deps.sh --python-package-manager pip
./scripts/tools/verify-deps.sh --python-package-manager uv
```

Mode selection follows a fixed precedence in both scripts: explicit `--python-package-manager {pip|uv}` flag, then a `RISKMAP_PYTHON_PACKAGE_MANAGER` environment variable, then the default. **Outside the devcontainer the default is `pip`**, preserving the existing contributor path; the devcontainer always passes the flag explicitly (D2), so the default never applies there. `install-deps.sh` forwards the resolved mode to its final `verify-deps.sh` invocation. For a **standalone** `verify-deps.sh` run, the selected mode is recovered from install-time repo-local state, such as a marker written by `install-deps.sh` and/or `.venv` presence as the `uv` signal, before falling back to the precedence chain. A bare verification therefore inspects the same environment that was installed instead of silently defaulting to `pip` and mis-reporting a populated `uv` `.venv`.

### D4. Bind install, verify, and hook execution to the selected Python environment

**Invariant (required):** in either mode, `pre-commit` installation, commit-time `language: system` hooks, and package verification all resolve the same Python environment that `install-deps.sh` populated for that mode.

**Delta vs today.** Today every dependency lives in the global `mise`-managed Python's site-packages, and `language: system` hooks resolve them by running `python3` off the `mise`-shim `PATH` - one environment, no binding needed. `pip` mode keeps this behavior. `uv` mode changes it: dependencies live in a repo-local `.venv` that is **not** on the default `PATH`, so without explicit binding a `language: system` hook running `python3` resolves the dependency-empty global interpreter. The binding requirement therefore bites only in `uv` mode, and is the price of `.venv` isolation; leaving it unaddressed would move the #159 mismatch from install/verify into commit time.

**Illustrative mechanisms (not prescribed):** put `.venv/bin` first on the hook execution `PATH`, use environment-aware wrapper entries, or another repo-local mechanism. The ADR fixes the invariant, not the mechanism, and preserves ADR-005/ADR-013's `language: system` boundary either way.

### D5. Keep both modes covered by tests, CI, and documentation

Tests cover `pip` mode, `uv` mode, mode selection, devcontainer forced-`uv` behavior, and mode-aware verification. Documentation in [`scripts/docs/setup.md`](../../scripts/docs/setup.md) and [`risk-map/docs/setup.md`](../../risk-map/docs/setup.md) shows both non-container package-management choices and states that devcontainers use `uv`.

CI may continue to use `pip` from `requirements.txt`. A future workflow may adopt `uv` for speed or parity with the devcontainer, but the repository must retain automated coverage for the `pip` path as long as `pip` remains a supported contributor choice.

### D6. Environment authority and migration

In `uv` mode the repo-local `.venv` is authoritative: verification and hooks inspect `.venv` and ignore ambient/global site-packages, so a `pip`-populated base environment can neither mask a missing `.venv` nor be mistaken for the selected one. `install-deps.sh` is idempotent across rebuilds and reconciles a stale or partial `.venv` by re-syncing it. Switching modes is supported by re-running `install-deps.sh` with the new selector; the newly selected environment becomes authoritative for subsequent verify and hook runs.

## Alternatives Considered

- **Move the dependency declaration into `pyproject.toml` `[dependency-groups]`.** Deferred, not rejected. Both `pip` (>= 25.1) and `uv` can consume a pyproject group, but both already consume `requirements.txt` today, so the move buys no capability needed for issue #159 while cascading to 15 CI install steps across six workflows, the `pip` caches, Dependabot, and a pip >= 25.1 floor. Sequence this as its own follow-up ADR to keep this PR a bootstrap fix.
- **Add `uv.lock` as the committed lockfile.** Deferred because it is an independent lockfile decision, not required for issue #159.
- **Make `uv sync` the only installer and remove `pip` support.** Rejected because it forces every contributor and every dependency-update workflow onto `uv`. A full `uv`-only packaging migration is also disproportionate to a bootstrap reliability fix for a repository not modeled as an installable Python package.
- **Keep the current pip-only bootstrap and fix PATH ordering around `mise` shims.** Rejected because it treats the current failure as a shell-ordering bug rather than an environment-contract bug. The devcontainer would still depend on ambient interpreter resolution for install and verify.
- **Add `uv` as an optional helper but keep the devcontainer on `pip`.** Rejected because the devcontainer is the managed path and should be the most deterministic path. Leaving it on `pip` preserves the failure mode where new contributors are most likely to encounter it.
- **Maintain parallel dependency manifests for `pip` and `uv`.** Rejected because two editable sources of truth invite drift. `requirements.txt` is already consumed by scripts, CI, docs, tests, and Dependabot; `uv` can consume the same input through its pip-compatible interface.

## Consequences

**Positive**

- Devcontainer bootstrap uses one repo-local Python environment for package install, package verification, and hook setup.
- Contributors outside the devcontainer keep the existing `pip` workflow while gaining an explicit `uv` option.
- `requirements.txt` remains the dependency source of truth, so the issue #159 implementation does not need to redesign packaging metadata or dependency-update automation.
- The decision preserves ADR-003's reusable script surface while making the devcontainer path deterministic.

**Negative**

- The scripts, tests, and docs now carry two Python package-management modes.
- `pip` mode can still inherit ambient-interpreter problems on a contributor's machine. That is the accepted cost of keeping `pip` as a supported non-container choice.
- `uv` becomes a new `mise`-managed tool dependency in the devcontainer supply chain. It is pinned to an explicit version in `.mise.toml` (not `latest`) for determinism; upgrade cadence is reconciled with the reserved devcontainer dependency-pinning policy in ADR-023 when that ADR lands.
- The `language: system` pre-commit hooks make the implementation sharper than a simple installer swap. The selected Python environment has to be visible at commit time, not only during `install-deps.sh`.

**Follow-up**

- Implement D1-D6 across `.mise.toml`, `.devcontainer/devcontainer.json`, `.gitignore`, `install-deps.sh`, `verify-deps.sh`, setup docs, and the relevant script/devcontainer tests.
- Add or update tests for mode selection, `.venv` creation, mode-aware package verification, devcontainer forced-`uv` behavior, pre-commit installation through the selected environment, and preservation of the `pip` path. Per D6, also cover: (1) `uv` selected while the ambient environment is `pip`-populated - verify checks `.venv`, not ambient, and ambient packages do not let a missing `.venv` pass; (2) `pip` to `uv` switch in place; (3) `uv` to `pip` switch back; (4) non-container rebuild with a stale or partial `.venv` (idempotent reconcile, no manual cleanup); (5) leftover site-packages or PATH carryover does not let `uv`-mode verify false-pass; (6) devcontainer forced-`uv` rebuild is idempotent.
- Add a `verify-deps.sh` presence/version check for `uv` with a test, per ADR-003's pattern that each `mise`-managed tool carries a verification check.
- If a future change wants `[project.dependencies]`, `uv.lock`, or `uv sync` as the repository-wide dependency source of truth, write a follow-up ADR or explicitly supersede this one.
- GitHub Actions surface: six workflows currently install via `pip install -r requirements.txt` across 15 install steps, with `cache: 'pip'` used by the Python setup jobs that opt into dependency caching. Because `requirements.txt` is retained, no workflow edit is required by this ADR. Two open items remain: (1) the forced-`uv` devcontainer path (D2) has no end-to-end CI coverage today because the devcontainer suites are static/unit; (2) if a future job exercises `uv` in CI, it adds a SHA-pinned `astral-sh/setup-uv` action under ADR-024, since `actions/setup-python` does not supply `uv`. A future move to `pyproject.toml` would instead rewrite those 15 install steps, the `pip` caches, and one path filter; track that with the follow-up ADR.

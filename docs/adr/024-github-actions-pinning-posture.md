# ADR-024: GitHub Actions pinning posture

**Status:** Accepted
**Date:** 2026-05-01
**Authors:** Codex agent, with maintainer review

---

## Context

Issue [#251](https://github.com/cosai-oasis/secure-ai-tooling/issues/251) asks the repository to choose a posture for GitHub Actions `uses:` references. The workflows under `.github/workflows/` run against pull-request payloads, including external-contributor pull requests, and some jobs receive repository-scoped `GITHUB_TOKEN` permissions for validation summaries, Pages publishing, or pull-request comments. That makes workflow dependency integrity part of the repository supply-chain boundary.

Before this ADR, workflow references used movable tags such as `actions/checkout@v6`, `actions/cache@v5`, and `browser-actions/setup-chrome@latest`. Tags and branch names are convenient for updates, but they are mutable references. If a referenced Action maintainer account, repository, or tag is compromised, the workflow can execute different code without a visible diff in this repository.

GitHub's security guidance identifies a full-length commit SHA as the immutable way to reference third-party Actions. OpenSSF Scorecard's pinned-dependencies check also treats dependency pinning as a supply-chain hardening signal. Dependabot is already configured for the `github-actions` ecosystem in `.github/dependabot.yml`, so the remaining decision is whether to keep tag-major references for convenience or switch to commit SHAs while preserving update automation through semver comments.

This ADR is a tooling/infrastructure decision under [ADR-002](002-branching-strategy.md): it targets `main`, not `develop`.

## Decision

Use full-length commit SHA pins for every non-local GitHub Actions `uses:` reference in `.github/workflows/*.yml`. Keep the human-readable semver release tag as a trailing comment on the same line so Dependabot can track and update the pinned Action version.

### D1. Pin all external Actions by full commit SHA

Every external workflow reference uses this form:

```yaml
uses: owner/repo@0123456789abcdef0123456789abcdef01234567 # v1.2.3
```

The part after `@` is the 40-character commit SHA that GitHub Actions resolves and executes. The trailing comment is not executable workflow input; it is a maintainer and Dependabot hint that records the upstream release tag corresponding to the pin.

The same rule applies to subpath references such as `owner/repo/path/to/action@<sha> # vX.Y.Z`; only the SHA portion is what GitHub Actions resolves and executes, so the pinning rule is identical regardless of subpath.

This ADR does not address `docker://image:tag` references in `uses:` fields. The repository does not currently use that shape; if a workflow ever introduces a containerized Action, that reference's pinning policy is governed by the future devcontainer / Docker-image policy in ADR-023, not by this ADR.

This applies to GitHub-owned Actions and third-party Actions alike. The repository currently uses both (`actions/*` and `browser-actions/setup-chrome`), and a single rule is easier to review and enforce than a split policy.

### D2. Do not use floating refs for external Actions

External `uses:` references must not use:

- branch names such as `main` or `master`
- moving tags such as `latest`
- major-only tags such as `v6`
- minor-only tags such as `v6.2`

Those references are mutable. They may still be acceptable for local reusable workflows or local composite Actions referenced with `./...`, because those paths are versioned by this repository's own commit. This ADR does not introduce any local reusable workflow path.

### D3. Preserve Dependabot version-update compatibility with comments

The `github-actions` entry in `.github/dependabot.yml` remains enabled. Dependabot version updates can update SHA-pinned Actions when the line includes a version comment, so the semver comment is required whenever a SHA pin corresponds to a tagged release.

Reviewers should reject SHA-pinned Action updates that drop the version comment. Without the comment, the pin remains immutable but maintenance becomes manual and Dependabot cannot produce useful version-update PRs.

The comment format is ` # vX.Y.Z` (single leading space, `#`, single space, `v` prefix, semver). Dependabot's update-comments-in-workflows feature parses that shape; deviations may degrade silently to a SHA-only diff with no version context.

### D4. Treat security alerts and version updates as separate signals

SHA pinning protects against silent upstream tag movement, but it changes the update workflow. Maintainers still review Dependabot PRs for Action updates, and security-relevant Action updates should be prioritized like other dependency updates.

The repository accepts the operational cost because the workflow threat model is not read-only documentation: workflows execute code from external repositories and process pull-request-controlled files.

### D5. Keep the policy small

This ADR does not decide Docker image digest pinning, devcontainer feature exact-version pinning, or base-image date-stamping. Those are tracked by issue [#248](https://github.com/cosai-oasis/secure-ai-tooling/issues/248) and the planned ADR-023 devcontainer maintenance policy.

## Alternatives Considered

- **Keep major tags (`actions/checkout@v6`).** Rejected. It preserves easy updates, but the executed code can change when the upstream tag moves. That leaves no visible diff in this repository for a supply-chain-relevant change.
- **Pin only third-party Actions, leave `actions/*` on tags.** Rejected. It creates an exception reviewers must remember, and GitHub-owned Actions are still external code fetched at workflow runtime. A uniform rule is easier to audit.
- **Pin SHAs without semver comments.** Rejected. It gives immutability but weakens routine maintenance because maintainers lose the version context and Dependabot comment-based update tracking.
- **Vendor Actions into this repository.** Rejected. Vendoring would give strong control but adds ongoing maintenance burden, makes updates harder to review, and is disproportionate for this repository's workflow surface.

## Consequences

**Positive**

- Workflow execution is bound to immutable commits, not mutable upstream refs.
- Pull requests that update Action code now show an explicit diff in this repository.
- The previous `browser-actions/setup-chrome@latest` reference is removed.
- Dependabot remains useful because semver comments preserve update tracking.

**Negative**

- Workflow `uses:` lines are less readable because the executable reference is a SHA.
- Maintainers must preserve the version comments during manual edits.
- Reviewers must verify that a SHA update corresponds to the commented release tag when a change is not produced by Dependabot.
- Routine Action-update PRs are SHA diffs rather than tag bumps; the volume is dominated by GitHub-published `actions/*` updates, which a third-party-only pinning policy would have left on tag pins. The repository accepts this review surface in exchange for a uniform rule that does not require reviewers to remember per-publisher exceptions.

**Follow-up**

- Add an automated lint that rejects external `uses:` references not pinned to 40-character SHAs and rejects SHA pins without semver comments. Tracked at [#264](https://github.com/cosai-oasis/secure-ai-tooling/issues/264).
- Once ADR-023 lands and creates `docs/devcontainer-maintenance.md` with cadence content, add a back-link from there to this ADR so dependency maintenance decisions for workflows and devcontainers remain discoverable together.

## References

- [Issue #251: GitHub Actions pinning posture](https://github.com/cosai-oasis/secure-ai-tooling/issues/251)
- [Issue #248: devcontainer lifecycle maintenance (ADR-023 parent)](https://github.com/cosai-oasis/secure-ai-tooling/issues/248) — sibling decision; ADR-023 will cover devcontainer / Docker-image pinning deferred from D5
- [GitHub Actions security hardening guidance](https://docs.github.com/en/actions/security-guides/security-hardening-for-github-actions)
- [Dependabot changelog: update comments in SHA-pinned GitHub Actions workflows](https://github.blog/changelog/2022-10-31-dependabot-now-updates-comments-in-github-actions-workflows-referencing-action-versions/)
- [OpenSSF Scorecard pinned-dependencies check](https://github.com/ossf/scorecard/blob/main/docs/checks.md#pinned-dependencies)

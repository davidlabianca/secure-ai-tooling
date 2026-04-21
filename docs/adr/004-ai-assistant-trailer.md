# ADR-004: Vendor-neutral `Co-authored-by` trailer for AI-assisted commits

**Status:** Draft
**Date:** 2026-04-20
**Authors:** Architect agent, with maintainer review

---

## Context

The CoSAI Risk Map is produced under the Coalition for Secure AI — a multi-vendor initiative whose credibility depends on not privileging any single vendor in its published artifacts. Commit history is one of those artifacts: `git log` on this repository is a long-lived, externally visible record, and attribution trailers in that log function as signals about the project's posture.

AI coding assistants are used routinely in this repository — for drafting content, authoring scripts, composing commit messages, and responding to reviews. Most of those tools, left on their defaults, emit a `Co-authored-by` trailer that embeds a specific model identifier and a vendor-owned no-reply address. The exact string varies by tool and version, but the shape is consistent: a human-readable product or model name, plus a vendor domain. Letting those defaults land in this repository's commit log would produce a history that visibly favors whichever vendor's tooling the current maintainer happens to run — a signal the coalition does not intend to send.

A convention already exists to address this: every AI-assisted commit carries the trailer

```
Co-authored-by: AI Assistant <ai-assistant@coalitionforsecureai.org>
```

Evidence the convention is in force today:

- **Governance issue [#149](https://github.com/cosai-oasis/secure-ai-tooling/issues/149)** is the authoritative source of the decision, raised on the umbrella `cosai-oasis/secure-ai-tooling` repository.
- **`scripts/hooks/prepare-commit-msg`** — a tracked `prepare-commit-msg` hook that appends exactly this trailer when `AI_ASSISTED=1` is set, using a literal-string match to avoid duplication. This is the enforcement surface.
- **The maintainer operating guide** references the convention and links to issue #149 (see the "Development Guidelines" section of the repository's local `CLAUDE.md`).
- **ADR-001** (the ADR-adoption decision itself) lists this trailer as one of the representative tooling decisions that motivated introducing a tracked decision log.

The problem this ADR addresses is not that the convention is wrong — it is that the convention is currently *documented* only in `CLAUDE.md`, which is excluded from git via `.git/info/exclude` (entry: `CLAUDE.md`). External contributors cloning the repository have no tracked reference for the trailer, why it exists, or what rejected alternatives it supersedes. The `prepare-commit-msg` hook enforces the string, but enforcement without published rationale leaves contributors guessing — and leaves the convention vulnerable to being dropped the next time an AI-assistant harness changes its default output.

This is a **retroactive** ADR: it documents reasoning behind an already-locked decision (#149), not a new decision.

## Decision

All AI-assisted contributions to this repository — code, framework content, commit messages, documentation, review responses, and any other artifact produced with AI assistance — carry this single, vendor-neutral `Co-authored-by` trailer:

```
Co-authored-by: AI Assistant <ai-assistant@coalitionforsecureai.org>
```

Concrete shape:

- **Identity:** `AI Assistant` — a generic role name, not a product or model name.
- **Email:** `ai-assistant@coalitionforsecureai.org` — attributes the co-authorship to a neutral coalition-owned address rather than a vendor's no-reply domain.
- **Scope:** any commit where AI assistance materially shaped the committed output. "Materially" means content the assistant generated or substantively revised; it does not include trivial assists such as autocomplete.
- **Enforcement:** the tracked `prepare-commit-msg` hook at [`scripts/hooks/prepare-commit-msg`](../../scripts/hooks/prepare-commit-msg) appends the trailer when `AI_ASSISTED=1` is set in the commit environment. The hook is idempotent (literal-string `grep -qF` guard).
- **Vendor defaults are replaced, not augmented.** Any AI tool whose default trailer embeds a model identifier or vendor domain must have that default suppressed or overwritten before the commit lands. Mixing the vendor default with the neutral trailer defeats the purpose.
- **Authoritative source:** governance issue [#149](https://github.com/cosai-oasis/secure-ai-tooling/issues/149). If the trailer text ever needs to change, that issue (or its successor) is where the change is negotiated; this ADR is updated to match.

## Alternatives Considered

- **Use the vendor-default trailer** emitted by whatever assistant the committer happens to run (typically of the form `Co-authored-by: <Product/Model Name> <noreply@<vendor-domain>>`). Rejected: a multi-vendor coalition's commit log should not visibly favor any vendor. The signal sent by thousands of model-branded trailers in published history runs directly counter to the coalition's stated posture, independent of any individual tool's merits.

- **Omit any AI trailer** and treat AI assistance as invisible in commit metadata. Rejected: provenance matters. Reviewers benefit from knowing a patch was AI-assisted when calibrating their review depth; future auditors benefit from being able to identify AI-assisted contributions in aggregate; and the coalition's own transparency posture favors disclosing AI involvement rather than hiding it.

- **Per-vendor neutral trailers** — each contributor emits a trailer naming whichever tool they used, but with a coalition-owned email. Rejected: the outcome is still a log that enumerates vendors and advertises relative usage. It also creates a downstream grep/query burden: any process that wants to find "all AI-assisted commits" has to maintain a growing list of identity strings. A single canonical identity is both simpler and more neutral.

- **Repository-specific custom identity** (the chosen path, e.g., `AI Assistant <ai-assistant@coalitionforsecureai.org>`). Accepted. The email is on a coalition-owned domain, the display name carries no vendor information, and a single string is easy to enforce and to query.

## Consequences

**Positive**

- The published commit history reads as vendor-neutral. No reader of `git log` can infer which AI tool was used, preserving the coalition's multi-vendor posture in the artifact external parties actually see.
- Provenance is preserved. AI-assisted commits remain grep-able via a single literal string, which supports both review calibration and any future audit of AI involvement in the codebase.
- The rationale for the convention now lives in a tracked file. The `prepare-commit-msg` hook and `CLAUDE.md` continue to enforce and mention the trailer, but contributors without access to maintainer-local files can now read the *why* in `docs/adr/004-ai-assistant-trailer.md`.
- The convention is insulated against harness churn. If an AI tool changes its default trailer format in a future release, the ADR and hook are unaffected; only the suppression step in the relevant tool configuration needs updating.

**Negative**

- Contributors must actively suppress or overwrite their tool's default trailer. This is a real authoring cost, and a missed suppression produces a mixed trailer set that must be amended before merge.
- The `AI Assistant` identity is coarse. It does not distinguish between heavily AI-generated work and lightly AI-assisted work, nor between different assistants. This is a deliberate tradeoff in favor of neutrality; if finer-grained provenance is ever needed, it should be carried in commit bodies or PR descriptions, not in the trailer.
- The coalition-owned email address becomes infrastructure the project depends on. If the domain or mailbox is ever retired, the trailer becomes a dangling reference and this ADR must be superseded with a replacement identity.

**Follow-up**

- Contributor-facing documentation (the contributing guide work tracked separately) should surface the trailer convention and link to this ADR, so new contributors do not have to discover it via the hook or maintainer guidance.
- A PR-level check that flags commits carrying vendor-default AI trailers would harden the convention beyond the local hook. Not part of this ADR; a candidate for a later tooling ADR if the failure mode is observed in practice.
- If governance issue #149 is ever closed with a revised trailer text, this ADR is updated in the same change and the `prepare-commit-msg` hook's `TRAILER` constant is updated to match.

# ADR-033: Vendor-neutral shipping and lifecycle for CoSAI agents and skills

**Status:** Draft
**Date:** 2026-07-08
**Authors:** Architect agent, with maintainer review

---

## Context

CoSAI ships agents and skills as vendor-neutral, cloneable artifacts. A consumer clones the repository, points their own agent runtime at `scripts/agents/**` and `scripts/skills/**`, and runs the definitions in whatever harness they operate. The value of those artifacts to a cross-provider, model-neutral coalition depends on their staying free of any single product line: the same posture [ADR-004](004-ai-assistant-trailer.md) fixed for commit trailers and [ADR-006](006-agent-architecture-pattern.md) fixed for agent bodies.

Three prior ADRs built the surfaces this standard governs. [ADR-006](006-agent-architecture-pattern.md) established `scripts/agents/` as the vendor-neutral canonical home for agent definitions and the rule that the canonical is authoritative — harness-specific invocation mechanics are environment concerns, not part of the canonical pattern. [ADR-031](031-authoring-time-agents-and-skills.md) (Draft, [#402](https://github.com/cosai-oasis/secure-ai-tooling/pull/402)) established `scripts/skills/` as the canonical, vendor-neutral skill home in the Agent Skills open standard (`agentskills.io`, its D6) and defined the authoring corpus — creator/critic agent pairs and authoring/audit skills. [ADR-032](032-consumer-exploration-skills.md) (Draft, [#407](https://github.com/cosai-oasis/secure-ai-tooling/pull/407)) defined the read-only consumer exploration corpus (`explore-*` skills) inheriting that home and format.

Those ADRs each answer *what a given corpus is*. None answers the cross-cutting questions that bind all of them: what makes a shipped artifact vendor-neutral, precisely enough to be enforced rather than asserted; how a consumer takes a neutral artifact and runs it in their own environment; and how a new agent or skill is developed, evaluated, and admitted into the shipped set. This ADR defines that shipping standard and lifecycle. It enumerates no corpus — ADR-031 and ADR-032 own their rosters — and selects no concrete tool; it fixes the constraints a tool must satisfy and defers the pick to downstream work.

Two forces make this an architectural decision rather than a convention note. First, "vendor-neutral" is load-bearing but under-specified: without a definition precise enough for a check to enforce, the neutral surfaces silently re-accumulate harness leakage on the next edit, and reviewers arbitrate neutrality by taste. Second, the shipped set grows — new skills and agents will be proposed — and "how does a new artifact enter the shipped set, and what must it carry?" needs a stable answer so growth stays consistent with the standard rather than drifting from it.

## Decision

We adopt a vendor-neutral shipping standard and lifecycle for the agents and skills CoSAI publishes. The shipped artifact is the neutral canonical; neutrality is defined as a contract with a mechanically-checkable core; consumers adapt the neutral artifact to their own harness; and new artifacts enter the shipped set by amending or adding an ADR that conforms to this standard.

### D1. Canonical-only, neutral, cloneable

The shipped artifact is the neutral canonical definition under `scripts/agents/**` (agents) or `scripts/skills/**` (skills). That canonical is the single, complete, authoritative form of the artifact, and it is what a consumer clones and runs. **No harness-specific wrapper files are tracked in the repository.** The repository does not ship, generate, or maintain a first-party per-harness form of any agent or skill; harness adaptation is the consumer's, not the project's (D3). This keeps the tracked surface singular — one file per artifact, no parallel copy to reconcile — and keeps the published set genuinely neutral, since there is no first-party artifact in which harness-specific mechanics could accumulate.

### D2. The neutrality contract

An artifact is vendor-neutral when it conforms to the following contract. The contract has two parts: a mechanically-enumerable core that a check can enforce (D5), and author-judgment guidance that no check can decide.

#### D2a. Mechanically-enumerable constraints (machine-checkable)

A neutral artifact contains **none** of the following, enumerated as a denylist:

- **Vendor, product, company, CLI, and model identifiers** — the name of any specific AI-assistant product, the company behind it, its command-line entry point, or any model identifier or version string.
- **Harness-invocation tokens** — harness-specific dispatch mechanics: subagent-type keys, `<uses … tool>` / `<invoke … tool>` stage directions, tool-name tokens, and "auto-loads" / "auto-triggers" phrasing that describes a specific runtime's dispatch rather than the neutral operative form ("invoke the *X* agent", "consult the *X* skill").
- **Harness config paths** — any product-named configuration directory or path. References resolve to the repo-relative canonical path (`scripts/agents/…`, `scripts/skills/…`) instead.
- **Runtime-binding frontmatter** — frontmatter beyond the neutral schema the shipping format defines (D4). The canonical carries only that neutral schema: the [ADR-006](006-agent-architecture-pattern.md) prose form for agents, and the required Agent Skills frontmatter for skills (ADR-031 D6). Any additional key encodes a specific runtime's wiring and belongs in the consumer's adaptation, not the shipped artifact — so the check enforces the neutral schema as an **allowlist** (only the schema's own keys are present) rather than chasing any one runtime's key names.

The denylist carries an explicit **allowlist carve-out** for framework-authority names that are legitimate neutral content and must **not** be flagged: **MITRE, NIST, OWASP, ISO, EU AI Act, STRIDE** (and the specific framework identifiers under them). These are the security reference frameworks the corpus legitimately names — `explore-framework-coverage` and `audit-framework-mappings` exist precisely to reference them — and they are framework authorities, not AI-harness vendors. A neutrality check must treat them as allowed content, not as vendor leakage.

#### D2b. Author-judgment guidance (not machine-checkable)

The following clauses shape a neutral artifact but cannot be decided by a check; they are review-enforced:

- **Prefer the neutral role term, and omit where the sentence reads cleanly.** Where a removed vendor or harness reference leaves a sentence that reads cleanly without any replacement, omit it rather than substituting a neutral placeholder. Substitute a neutral role term ("the AI assistant", "the model", "the harness") only where the sentence needs a referent.
- **Self-description stays neutral.** The artifact describes itself by role and behavior; it does not announce which harness it runs under or assume a specific runtime is present.
- **Capabilities in prose, not bindings.** Where a capability would have been expressed as a tool or model binding, it is re-expressed in prose that states the capability without naming the mechanism (D4).

This contract is the operative content of "vendor-neutral" wherever this ADR uses the term. It governs the shipped canonical artifacts — the canonical agents and the canonical skills with their bundled material. It does **not** govern the **adoption material** (the worked adaptation examples of D3 and the consumer adaptation / known-gaps note of D3/D6): that material is *deliberately* harness-specific — naming the harnesses it targets is its whole purpose — so it is an intentionally non-neutral surface, outside this contract and the D5 check.

### D3. Consumer leverage

After `git clone`, a consumer runs the neutral artifacts in their own harness. Adapting a neutral artifact to a specific runtime — supplying invocation mechanics, tool permissions, and whatever frontmatter that runtime expects — is the **consumer's responsibility**, not the project's. The repository ships no first-party per-harness wrapper for any artifact.

To make that responsibility tractable — and to prove it is actually tractable — the project provides a **small, curated set of worked adaptation examples that is *exercised* in at least two independent harnesses**, including at least one third-party harness independent of the standard's origin. Exercising the set (not merely writing it) is what makes it evidence that a neutral artifact runs after adaptation, rather than an untested illustration of how it might. The set is deliberately small and **contributor-extensible**: a contributor who runs a harness not yet represented can add a worked example for it. These examples are proof-of-portability for the adaptation a consumer performs, not a tracked first-party wrapper set the project commits to maintaining for every artifact; they carry no per-artifact obligation and do not reintroduce the parallel copy D1 excludes. Because a worked example must name the harness it targets, the adaptation material is an intentionally harness-specific surface — outside the D2 neutrality contract and the D5 check (see D5).

### D4. Shipping format

- **Agents** ship in the [ADR-006](006-agent-architecture-pattern.md) prose "Sub-Agent Definition" form: a header block, then `## Agent`, then `## Composition`, then body sections that define the agent's method and state its required capabilities in prose. The canonical carries the definition itself, not a runtime's binding metadata; a consumer supplies whatever wiring their runtime expects at adoption time (D3). Canonical agents reference each other by name, resolving within `scripts/agents/`.
- **Skills** ship in the Agent Skills open standard as defined in **ADR-031 D6**. That standard — the `SKILL.md` shape, its required frontmatter, its bundled-directory layout, and the pinned-revision discipline — is authoritative there and is **not restated here**; a second copy would drift from the original. This ADR requires only that shipped skills conform to it.

### D5. A neutrality check is required

A check that enforces the D2a denylist over the neutral surfaces **is required**. Its constraints:

- **Scope.** It runs over the shipped canonical artifacts — `scripts/agents/**` and `scripts/skills/**` — **not** the whole repository, and **not** the adoption material. Two categories are deliberately out of scope: the rest of the repository (devcontainer config, IDE settings, CI, dependency manifests) legitimately names specific tools; and the **adoption material — the worked adaptation examples (D3) and the consumer adaptation / known-gaps note (D3/D6) — must name the harnesses it targets to serve its purpose**, so it is an intentionally harness-specific surface, not a neutral one (D2). Those references are all correct where they are. Scoping the check to the genuinely neutral shipped artifacts is what lets both categories stay honest about their tooling while the artifacts themselves stay neutral.
- **Allowlist fidelity.** It must **not** false-fire on the D2a allowlist (MITRE, NIST, OWASP, ISO, EU AI Act, STRIDE and their identifiers). A check that flagged `audit-framework-mappings` or `explore-framework-coverage` for naming the frameworks they exist to reference would be wrong.
- **Conformance to the shipping standard.** Beyond the denylist, the check confirms each shipped skill validates against the Agent Skills standard's own reference validator and carries only the standard's required-field core (D2a; the standard itself is ADR-031 D6). This is the highest-leverage guard against *silent* incompatibility: harness-specific frontmatter beyond that core is ignored without error by harnesses that do not support it (see Consequences), so keeping shipped skills to the validated required-field core is what makes them port silently-cleanly. Validating against the standard's own reference oracle leans on the adopted standard's conformance mechanism — it is not a tool selection.
- **Enforcement point.** It gates the neutral surfaces before merge.

This ADR **requires** the check and fixes its constraints; it does **not** select or mandate a specific implementation. The linter implementation is downstream work, routed as infrastructure (`swe` → `code-reviewer`).

### D6. Develop, evaluate, and expand lifecycle

**Authoring and exercise.** A new agent or skill is authored directly in neutral canonical form (D1, D4) — there is no non-neutral intermediate to convert from. It is exercised against the corpus it operates on before it enters the shipped set.

**Portable evals travel with the artifact.** Every shipped skill (and, where applicable, agent) carries a **portable eval that ships with it** — a behavior specification, expressed independently of any runtime, that states the artifact's expected behavior on fixed inputs. An eval is **required** to ship: an artifact with no eval is not admissible to the shipped set. The eval is the artifact's portable trust anchor — the executable check a consumer runs in their own runtime to confirm an adaptation preserved behavior — the same role the conformance/reference oracle plays in every write-once-consume-anywhere standard that has succeeded.

**Constraints on any eval-runner.** Whatever runner executes the portable eval must be: **vendor-neutral** (not tied to a single product line); **permissively licensed**; **free of any dependency on a non-portable harness**; and **able to run the portable eval spec** the artifact ships. This ADR fixes those constraints; it does **not** select or build the runner. The eval spec is the durable, portable artifact; the runner is a replaceable execution detail deferred to downstream work.

**Expansion rule.** A new agent or skill enters the shipped set by an **amendment to the relevant ADR (ADR-031 for authoring, ADR-032 for exploration) or a new ADR that conforms to this standard.** The new artifact must satisfy D1–D5: neutral canonical only, conforming to the neutrality contract, in the shipping format, passing the neutrality check, and carrying a portable eval. This is the answer to "how is a new agent or skill added": not by dropping a file, but by an ADR-level decision that admits it and records that it conforms.

## Alternatives Considered

- **Ship first-party per-harness wrappers alongside the canonical.** Track, for each artifact, a project-maintained wrapper for one or more harnesses. Rejected on neutrality and maintenance grounds: a tracked first-party wrapper is a surface in which harness-specific and vendor-specific mechanics accumulate, re-coupling the published set to a product line the coalition must not privilege; and it reintroduces the parallel-copy drift [ADR-006](006-agent-architecture-pattern.md) already rejected — two files per artifact per active harness, kept in sync by discipline. D1 ships the neutral canonical only; D3 makes adaptation the consumer's, with contributor-extensible worked examples instead of a maintained wrapper set.
- **Leave "vendor-neutral" as a review-judgment call.** Define no enforceable core and let reviewers arbitrate neutrality case by case. Rejected: neutrality then rests on reviewer taste and re-accumulates silently on edits a reviewer misses. D2a gives the contract a mechanically-checkable core and D5 requires a check to enforce it, while D2b keeps the genuinely judgment-bound clauses explicitly in review's hands rather than pretending a check can decide them.
- **Select the neutrality-check implementation and the eval-runner now.** Name and mandate a specific linter and a specific eval-runner in this ADR. Rejected per the principle that an ADR constrains a choice rather than making it: naming a concrete tool binds the standard to one implementation's lifecycle and licensing, and the constraints (D5, D6) are the durable part. The picks are downstream work against the stated constraints.
- **Admit new artifacts by dropping files, no ADR.** Let a new skill or agent enter the shipped set as an ordinary PR with no decision record. Rejected: the shipped set is a governed, neutral surface with a standard to uphold; an artifact that enters without an ADR carries no record that it was checked against D1–D5. D6 makes admission an ADR-level act.

## Consequences

**Positive**

- One neutral, authoritative file per artifact, cloneable and runnable as-is. A consumer clones exactly what they run; there is no parallel first-party copy to reconcile and no product line baked into the shipped surface.
- Neutrality is enforceable, not aspirational. The D2a denylist plus the D5 check keep the shipped surfaces from silently re-accumulating harness leakage, while the D2a allowlist keeps the check honest about legitimate framework-authority content.
- The consumer's adaptation burden is bounded by worked examples that contributors can extend to new harnesses, without the project taking on a per-artifact wrapper-maintenance obligation.
- Portability is provable per artifact: a required, runtime-independent eval (D6) travels with each shipped artifact, so its behavior is checkable in any conforming runner rather than only in the environment it was authored in.
- Growth stays consistent with the standard: new artifacts enter through an ADR that records their conformance (D6), so the shipped set does not drift from the standard as it expands.

**Negative**

- **The neutrality contract is a standing obligation.** The D2a denylist and allowlist must be maintained as harnesses and their vocabularies evolve: a new harness introduces new invocation tokens and config paths to deny, and a new framework authority may need adding to the allowlist. A too-aggressive rule false-fires on legitimate content; a too-loose one lets leakage through. Scoping the D5 check to the neutral surfaces bounds the blast radius but does not remove the maintenance duty.
- **Silent frontmatter incompatibility is the residual portability risk.** A well-formed neutral skill ports cleanly, but any *extended*, harness-specific frontmatter a consumer adds during adaptation is, on a harness that does not support it, ignored **without error** rather than rejected — so a mis-adaptation surfaces as wrong behavior, not a failed load. This is why D5 validates shipped skills against the standard's required-field core and D6 requires a portable eval: the core keeps the shipped artifact silently-clean, and the eval gives the consumer an executable way to catch a silent mis-adaptation on their side.
- **Harness adaptation is the consumer's burden.** Because no first-party wrapper ships (D1, D3), a consumer must wire each neutral artifact into their runtime themselves. The worked examples lighten this but do not eliminate it, and a consumer on an unrepresented harness has more to do until someone contributes an example for it.
- **The neutrality check is a supply-chain-adjacent surface.** A merge-gating check (D5) is code in the contributor path; its denylist/allowlist is security-relevant to maintain, and its scope must stay correct as the neutral surfaces move.
- **Every shipped artifact must carry a portable eval.** Requiring an eval to ship (D6) is real authoring cost, and the eval must be kept runtime-independent or it stops being portable — a discipline that holds only as long as authors resist encoding runner-specific assumptions into the spec.
- **AI-assisted provenance stays governance-sensitive.** The shipped artifacts and their adoption docs are AI-authored; they carry the [ADR-004](004-ai-assistant-trailer.md) `Co-authored-by: AI Assistant` trailer, and neither the artifacts nor the neutrality check may introduce a vendor marker into that provenance chain.

**Follow-up**

- **Build the neutrality check (D5)** enforcing the D2a denylist and allowlist over the shipped canonical artifacts (`scripts/agents/**`, `scripts/skills/**`), without selecting it here — the harness-specific adoption material (D3/D6) is out of scope. Routed as infrastructure (`swe` → `code-reviewer`).
- **Select an eval-runner (D6)** against the stated constraints — vendor-neutral, permissively licensed, no non-portable-harness dependency, runs the portable eval spec — as a downstream decision. The portable eval spec is the durable artifact; the runner is the replaceable detail.
- **Provide and extend the worked adaptation examples (D3)** — a small, curated set *exercised* in at least two independent harnesses (one of them third-party), kept contributor-extensible.
- **Write a one-page consumer adaptation / known-gaps note (D3/D6)** documenting, by harness, where extended frontmatter is silently ignored, and pointing consumers at the existing open-source cross-harness converters and installers instead of a first-party per-harness wrapper. This is the adoption-friction lever the consumption research identified, and it keeps the project on the neutral-canonical side of D1.
- **Admit new agents and skills (D6)** via amendments to ADR-031 / ADR-032 or new ADRs that record conformance to this standard; each must satisfy D1–D5 and ship a portable eval.

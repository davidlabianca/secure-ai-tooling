# Submission Readiness Guide

This guide tells contributors how to prepare a high-quality proposal before opening a GitHub issue against CoSAI-RM. It covers the quality bar that reviewers apply, the conventions enforced by the content-reviewer, and the most common reasons proposals get sent back for revision.

If you want to propose a new risk, control, component, or persona — or update an existing one — start here.

---

## Who this guide is for

- You have an issue in mind and want to know what "good" looks like before you submit.
- You've opened the issue template but aren't sure how strict the fields are.
- You've received reviewer feedback and want to understand the rules behind it.

If you just want to browse the framework, see [`risk-map/docs/README.md`](../README.md) and the summary tables instead.

---

## Pre-submission checklist

Work through this list before opening an issue. Every item maps to a section below.

- [ ] **Title yields a valid ID** — the ID is auto-derived as prefix + camelCase from the title (e.g., "Data Poisoning" → `riskDataPoisoning`, "Red Teaming" → `controlRedTeaming`); confirm your title produces a clean, non-colliding ID.
- [ ] **Title follows the style guide** — noun phrase, correct length, no "via/through/due to" clauses.
- [ ] **Description is AI- or agentic-specific** — not a restatement of a generic security concern.
- [ ] **Classical security equivalent is named** — the long description maps to a pre-AI risk/defense, then explains the AI-specific amplifier.
- [ ] **Personas use the correct model** — risks list _impacted_ personas; controls list _implementer_ personas.
- [ ] **No universal controls on risks** — the 7 universal controls apply to all risks implicitly.
- [ ] **Examples are real** — incidents, research, or vulnerability disclosures with verifiable URLs.
- [ ] **Framework mappings use valid IDs from the correct framework** — no parent + sub-technique, no wrong entity type.
- [ ] **No overlap with existing entries** — searched `risks-summary.md` / `controls-summary.md` and found nothing close.
- [ ] **Short description is 1-2 sentences** — the long-form detail belongs in the description field.

---

## Section 1: Creating a valid ID

IDs are **mechanically derived** from titles using the pattern `<prefix>` + `camelCase(title)`:

| Entity    | Prefix      | Title          | ID                      |
| --------- | ----------- | -------------- | ----------------------- |
| Risk      | `risk`      | Data Poisoning | `riskDataPoisoning`     |
| Control   | `control`   | Red Teaming    | `controlRedTeaming`     |
| Component | `component` | Model Storage  | `componentModelStorage` |
| Persona   | `persona`   | Model Provider | `personaModelProvider`  |

Write the title first. The ID follows.

**Common mistakes:**

- **Uppercase abbreviations** (`riskMCPInjection`) — use `riskMcpInjection`. CoSAI-RM migrated away from uppercase abbreviations; see the [risk ID migration design doc](../design/risk-id-migration.md) for history.
- **Underscores or hyphens** (`risk_data_poisoning`, `risk-data-poisoning`) — always camelCase, no separators.
- **Plural prefix** (`risksDataPoisoning`) — the prefix is singular even though the YAML key is plural.
- **Collision with an existing ID** — if your derived ID matches one already in `<entity>.yaml`, refine the **title** to disambiguate (add the discriminating dimension — surface, technique, scope). Do not suffix numbers (`riskPromptInjection2`), abbreviate (`riskPI`), or otherwise hand-edit the ID; the title is the only knob.

---

## Section 2: Writing a good title

Each entity type has a dedicated style guide. Read the one that applies before drafting:

- Risks → [`risk-titles-style-guide.md`](./risk-titles-style-guide.md)
- Controls → [`control-titles-style-guide.md`](./control-titles-style-guide.md)
- Components → [`component-titles-style-guide.md`](./component-titles-style-guide.md)

**Quick self-test:** Does the title read as a _thing_ (noun phrase) rather than an _action_ (verb phrase) or a _sentence_? If it starts with "Insufficient," "Failure to," "Lack of," or "Missing," rephrase it to name the threat or defense directly.

| Avoid                                 | Prefer                        |
| ------------------------------------- | ----------------------------- |
| Insufficient Logging of Agent Actions | Agent Action Opacity          |
| Failure to Validate Tool Inputs       | Tool Input Injection          |
| Lack of Output Sanitization           | Output Sanitization (control) |

---

## Section 3: The persona model

CoSAI-RM uses **two different persona models** depending on the entity type. Getting this wrong is one of the most common review findings.

### For risks: personas = who is _impacted_

List the personas **harmed by** the risk, not the personas who could mitigate it.

- `personaEndUser` appears on most risks. End users are almost always impacted.
- `personaGovernance` **does not appear on risks**. Governance is a control-side role — governance personas implement policy; they are not harmed by threats in the same direct sense as operational personas.
- `personaModelProvider`, `personaApplicationDeveloper`, `personaEndUser`, etc. appear on risks whose failure modes directly hit those roles.

### For controls: personas = who _implements_ the defense

List the personas **responsible for** putting the control in place.

- `personaGovernance` is common on policy, governance, and assurance controls.
- `personaEndUser` rarely appears on controls — end users generally cannot implement technical defenses.
- `personaApplicationDeveloper`, `personaModelServing`, etc. appear on controls they own operationally.

### Common mistake

Listing implementers on a risk (e.g., adding `personaApplicationDeveloper` to a risk because developers are the ones who should fix it). Fix it by asking: _is this persona harmed when this risk materializes?_ If not, remove them.

---

## Section 4: Universal controls

Seven controls have `risks: all` in `controls.yaml` — they apply to **every risk implicitly**:

1. `controlRedTeaming` — Red Teaming
2. `controlVulnerabilityManagement` — Vulnerability Management
3. `controlThreatDetection` — Threat Detection
4. `controlIncidentResponseManagement` — Incident Response Management
5. `controlInternalPoliciesAndEducation` — Internal Policies and Education
6. `controlProductGovernance` — Product Governance
7. `controlRiskGovernance` — Risk Governance

**Rule:** never list a universal control in a risk's `controls` field, and never list a risk in a universal control's `risks` field. The `all` sentinel handles the relationship.

**Why:** the framework checks bidirectional integrity — if a risk lists a universal control explicitly, it creates a duplicate edge that fails validation and confuses downstream tables.

When you propose a new risk, do **not** enumerate the 7 universal controls as applicable. Only list non-universal controls.

---

## Section 5: Examples requirements

The `examples` field anchors a risk or control to observable reality. Reviewers apply three checks:

1. **Real, not hypothetical.** Published incidents, academic research, vulnerability disclosures, or documented bugs qualify. Thought experiments and "what if an attacker..." scenarios do not.
2. **Not a vendor product announcement.** A blog post announcing a new defensive product is not evidence of a risk or control. A post-mortem describing how that product caught an incident is.
3. **Verifiable URLs.** Every example must cite a source the reader can open. Format examples as HTML anchors matching existing entries in the YAML files.

When in doubt, browse existing `examples` fields in `risks.yaml` or `controls.yaml` to calibrate.

---

## Section 6: Framework mappings

Different entity types map to different external frameworks. See [`framework-mappings-style-guide.md`](./framework-mappings-style-guide.md) for the full rules.

| Entity  | STRIDE                 | MITRE ATLAS               | OWASP LLM Top 10 | NIST AI RMF           |
| ------- | ---------------------- | ------------------------- | ---------------- | --------------------- |
| Risk    | ✓ (lowercase category) | Techniques (`AML.T####`)  | ✓ (`LLM##`)      | —                     |
| Control | —                      | Mitigations (`AML.M####`) | —                | ✓ (subcategory level) |

**Rules of thumb:**

- Risks map to **techniques**; controls map to **mitigations**. Do not mix.
- Never map a parent technique **and** one of its sub-techniques. Pick the most specific applicable ID.
- Verify every mapping ID exists in the referenced framework before submitting.

---

## Section 7: Checking for overlap

Before you open a new-entry issue, verify your proposal doesn't duplicate or near-duplicate an existing entry.

1. **Browse the summary tables**
   - Risks → [`risk-map/tables/risks-summary.md`](../../tables/risks-summary.md)
   - Controls → [`risk-map/tables/controls-summary.md`](../../tables/controls-summary.md)
2. **Search the YAML** for keywords from your title and description.
3. **If you find a close match**, propose an **update** to the existing entry rather than a new entry. Use the appropriate `update_*.yml` template.

If the overlap is partial (your proposal covers an additional angle), call that out explicitly in the issue so the reviewer can decide whether to extend the existing entry or create a new one.

---

## Section 8: What happens after you submit

1. **Triage.** A maintainer labels the issue and confirms it has enough detail to review.
2. **Automated checks.** The content-reviewer agent runs structural and style checks and posts findings as a comment.
3. **Human review.** A maintainer reviews the proposal against this guide, overlap with existing content, and framework fit.
4. **Verdict.** One of:
   - **PROCEED** — the proposal is accepted; a PR follows.
   - **DISCUSS** — the proposal needs scoping, clarification, or consolidation before it can proceed.
   - **RETHINK** — the proposal doesn't fit CoSAI-RM's scope as currently framed.

Common revision requests:

- Split one proposal into two (scope creep).
- Consolidate with an existing entry.
- Rename the title to conform to the style guide.
- Remove universal controls, or move governance personas off a risk.
- Replace hypothetical examples with cited incidents.

See [`common-review-findings.md`](./common-review-findings.md) for the full list of flagged issues.

---

## Related documentation

- **Style guides:**
  - [`risk-titles-style-guide.md`](./risk-titles-style-guide.md)
  - [`control-titles-style-guide.md`](./control-titles-style-guide.md)
  - [`component-titles-style-guide.md`](./component-titles-style-guide.md)
  - [`identification-questions-style-guide.md`](./identification-questions-style-guide.md)
  - [`framework-mappings-style-guide.md`](./framework-mappings-style-guide.md)
- **Process:**
  - [`issue-templates-guide.md`](./issue-templates-guide.md) — which template to use and when
  - [`common-review-findings.md`](./common-review-findings.md) — top reviewer findings with fix guidance
  - [`template-sync-procedures.md`](./template-sync-procedures.md) — for maintainers keeping templates in sync

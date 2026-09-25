---
name: mapping-selection
description: "Select the structured references and framework mappings for a CoSAI Risk Map control or risk — for a control: which components it applies to, which risks it addresses, and which mappings (MITRE ATLAS mitigations, NIST AI RMF subcategories, OWASP LLM, EU AI Act articles) fit; for a risk: which components it impacts, which controls address it, and which mappings (MITRE ATLAS techniques, STRIDE, OWASP LLM) fit. Use when authoring or reviewing a control and choosing its components/risks/mappings, or when a mapping looks off (wrong NIST function, a technique used where a mitigation belongs, or over-mapping). Grounds every choice in the actual corpus and the framework applicability rules rather than guessing."
---

# Mapping Selection

Choose a control's structured references — **components**, **risks**, and **framework mappings** — and justify each. The failure this skill prevents is confident-but-wrong selection: mapping to "related" rather than directly-relevant items, over-mapping, mixing MITRE techniques with mitigations, or picking the wrong NIST AI RMF function.

Scope: both the **control** direction (a control's components/risks/mappings) and the **risk** direction (a risk's components/controls/mappings) — see the two sections below.

## Procedure

### 1. Components — where the defense lives

Read `risk-map/yaml/components.yaml`. Select the components where the control's mechanism actually operates — the locus of the defense. Guidance:

- Prefer the **specific** components. Each one you list should be a place the control genuinely acts, not merely a place the risk appears.
- Use `"all"` only for a universal/governance/assurance control that genuinely applies framework-wide.
- Use `"none"` only when the control applies to no specific component.
- Do not over-select. If you are tempted to list five components, check whether the control is really one control or several.

### 2. Risks — what the control addresses

Read `risk-map/yaml/risks.yaml`. Select the risks this control directly mitigates. A mapping should be defensible in one sentence ("this control reduces the likelihood/impact of risk X because…"). Flag any that are merely "related." Be selective.

If you set `risks: "all"`, the control is **universal** — and those risks must **not** list it back (application is implicit). `"none"` is not valid for `risks`.

### 3. Framework mappings — the discipline

Read `references/frameworks-applicability.md` for the rules. In brief:

- **Applicability:** map only to frameworks that apply to controls.
- **MITRE ATLAS:** controls map to **mitigations** (`AML.M####`), never techniques (`AML.T####`). If no mitigation fits cleanly, omit ATLAS rather than forcing a technique.
- **NIST AI RMF:** use the **subcategory** id (e.g., `MEASURE-2.7`), never the category alone, and pick the **right function** — this is the most common mistake:
  - **GOVERN** — policy, roles, responsibilities, oversight, culture, risk tolerance. *Most preventive design and human-oversight controls land here.*
  - **MAP** — establishing context, framing intended use, identifying impacts.
  - **MEASURE** — assessment, testing, metrics, evaluation, tracking.
  - **MANAGE** — responding to, prioritizing, treating, and recovering from identified risks (reactive/operational). *Do not use MANAGE for a preventive design control.*
- **OWASP Top 10 for LLM:** `LLMxx:2025`.
- **EU AI Act:** `Article N@2024`, only when the control implements a specific regulatory obligation (e.g. human oversight → Article 14). Do not force it onto a generic technical control — see `references/frameworks-applicability.md`'s non-US counterbalance note (D3b).
- **Selective:** soft cap of 4 per framework; one-sentence rationale each.
- **Generate, don't hand-spell:** mapping values are version-pinned. For an entity that already has a row in the corpus, produce the value with `scripts/framework_mapping_maintainer.py` (ADR-027). For a control being drafted pre-PR (no row yet), the tool's composition step runs *before* entity lookup, meaning it will compose a value structurally even for a fabricated identifier — but `add` still requires a corpus row (real or a stub) to complete the command; without one, the command exits 1 at the lookup step. Pointed at a scratch copy of `controls.yaml` with a stub row for the not-yet-real id, `add` composes correctly. The real reason to hand-compose here isn't that the tool can't run (with a stub row, it can): it's that the tool gives **no fabrication protection either way** — it composes a plausible-but-nonexistent `--framework-specific-ref` exactly as readily as a real one, exit 0, no existence check, and a correctly hand-composed value is byte-identical in structure to a tool-generated one, so it passes the round-trip purity check just as cleanly. So compose the value directly against the pinned pattern in `risk-map/docs/contributing/framework-mappings-style-guide.md`, then verify it through `audit-framework-mappings`: **single-entity mode**, naming the real id, if `controlXxx` already has a row in `controls.yaml`; **candidate mode**, stating entity type `control`, if it's a pre-PR draft with no row yet. If the entity has no row yet (goes through **candidate mode**) and you are **deliberately deferring** any other value for that same framework to a later pass, say so — see [Output format](#output-format) for the full scope-selection and deferred-value rules (rejecting a value as not directly relevant is not deferral and needs no declaration). This declaration only matters for candidate mode; single-entity mode has no drip-feed mechanism to route it to.

### 4. Reciprocity

For each risk in the control's `risks` list (unless universal), name the reciprocal `risks.yaml` edit: that risk's `controls` array must list this control back.

## Risk direction

For a **risk** entry, the mirror of the control procedure:

### Components — where the risk manifests
Read `risk-map/yaml/components.yaml`. Select the components where the risk actually arises or takes effect (its locus). Be specific; do not list components the risk is merely "related" to.

### Controls — what addresses it (control-selection)
Read `risk-map/yaml/controls.yaml`. Select the controls that directly mitigate this risk, each defensible in one sentence. "Related" is not "addresses." Do **not** list a universal control (one with `risks: "all"`) — its application is implicit.

### Framework mappings — the risk-side rules
- **MITRE ATLAS:** risks map to **techniques** (`AML.T####`), never mitigations (`AML.M####`) — the mirror of the control rule. Do not map both a parent technique and its sub-technique.
- **STRIDE:** one or more of the six categories (`Spoofing`, `Tampering`, `Repudiation`, `InformationDisclosure`, `DenialOfService`, `ElevationOfPrivilege`) — bare PascalCase, no separators, no version token. STRIDE is risk-side.
- **OWASP Top 10 for LLM:** `LLMxx:2025`.
- **NIST AI RMF and EU AI Act do NOT apply to risks.** NIST AI RMF is control-side only. EU AI Act's `applicableTo` is `personas` and `controls` (`risk-map/yaml/frameworks.yaml`) — risks are not listed. Do not add either mapping to a risk; the schema does not catch this (only `scripts/hooks/validate_framework_references.py` does, at commit time), so get it right at authoring time.
- **Generate, don't hand-spell** applies here too (see §3 above for the full discipline): compose the pinned value directly against the style guide's pattern, then verify it through `audit-framework-mappings`: **single-entity mode**, naming the real id, if the risk already has a row in `risks.yaml`; **candidate mode**, stating entity type `risk`, if it's a pre-PR draft with no row yet. If the entity has no row yet (goes through **candidate mode**) and you are **deliberately deferring** any other value for that same framework to a later pass, say so — see [Output format](#output-format) for the full scope-selection and deferred-value rules (rejecting a value as not directly relevant is not deferral and needs no declaration). This declaration only matters for candidate mode; single-entity mode has no drip-feed mechanism to route it to.
- Selective (≤4/framework), one-sentence rationale each. A pinned value that is not yet generated/confirmed is omitted from the mappings entirely — never marked inline in the YAML — and noted in Flags instead.

### Reciprocity
For each control in the risk's `controls` list, that control's `risks` array must list this risk back (`risk.controls` ↔ `control.risks`).

## Output format

- **Components:** list, each with a one-line reason (the locus).
- **Risks:** list, each with a one-line reason (direct relevance).
- **Mappings:** per framework, each value with a one-line rationale. A value not yet generated/confirmed is omitted from the mappings entirely — never marked inline in the YAML (the pinned-pattern regexes are fully anchored and reject any suffix) — and listed in Flags instead, with the reason. (This is about the entity's *final* `controls.yaml`/`risks.yaml` mappings output — a distinct surface from the audit-submission request described below, which can legitimately bundle unconfirmed values together.)
- **Reciprocal edits:** the exact `risks.yaml` `controls` additions.
- **Flags:** anything uncertain — a mapping that needs framework-text verification, a component you were unsure about, a possible over-map, or a pinned value omitted pending generation/confirmation.
- **Submitting to `audit-framework-mappings`:** first pick scope. If the entity already has a row in `controls.yaml`/`risks.yaml` (you are confirming or adding to its real mappings), hand off to **single-entity mode** and name the real entity id, supplying the complete set for the framework(s) being submitted — that entity's actual existing corpus mappings for that framework plus any newly proposed value(s) — up front. This is scoped per framework: it does not require also bundling the entity's mappings for a framework not part of this submission. **Single-entity mode has no drip-feed clause and no provisional-verdict option: its checklist returns only a final result, never a pending one.** There is no partial-submission-with-a-provisional-verdict escape hatch here — a value that isn't ready is never submitted as a placeholder while expecting a pending result. Two legitimate paths remain, and the caller picks whichever fits the situation: (a) **finalize now**, submitting the confirmed value(s) together with the entity's existing corpus mappings for that framework as the complete set to audit this pass — appropriate when no further value for that framework is actually coming; or (b) **wait**, and submit the complete set together once the remaining value is confirmed — appropriate when more values genuinely are coming soon. **If you cannot yet say a further value is genuinely coming** — you suspect one might apply but haven't confirmed which, or its fit is still unresolved — that does not qualify as "coming soon": default to (a), finalize now. Whichever is chosen, what's submitted in a single-entity pass is evaluated as final, not provisional. If the entity has no row yet (a pre-PR draft), hand off to **candidate mode** and state the entity type explicitly (`risk` or `control`) — the checklist halts and asks if it isn't told. **Candidate mode alone carries the drip-feed mechanism:** if you are **deliberately deferring** any other value for that same framework from this submission (not yet drafted, or planned for a later pass — e.g., "I'll add more mappings for this framework in a follow-up"), say so explicitly — that is what candidate mode's checklist step 3, its drip-feed clause, checks for: it first *asks you to confirm the complete candidate set* before finalizing a verdict, and returns a provisional verdict only if that confirmation isn't obtained, rather than a misleadingly final one. Rejecting a value as not directly relevant is a different act — ordinary selective mapping, required on every submission — and needs no declaration; only a value you deliberately defer to add later triggers the flag, and that flag (and the provisional-verdict outcome it can produce) is available in candidate mode only. A complete set submitted together to either mode triggers no incompleteness flag, even though none of its co-submitted values are individually confirmed yet: confirmation status alone is never the signal, only a deliberately deferred value is (and, again, only candidate mode has anywhere to route that flag). When a candidate-mode flagged value is later confirmed, don't just append it to an already-finalized mappings list — resubmit it together with that framework's other already-accepted values as the complete candidate set, so the soft cap is evaluated against the true final total, not just the newly confirmed value in isolation.

## Reference

- `references/frameworks-applicability.md` — applicability matrix, MITRE mitigation-vs-technique rule, and the NIST AI RMF function cheat-sheet.
- Authoritative source: `risk-map/docs/contributing/framework-mappings-style-guide.md` (canonical pinned patterns and the maintainer tool).

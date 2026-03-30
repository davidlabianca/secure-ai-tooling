# Framework Mappings Style Guide

This guide covers how to write framework mappings across all entity types (risks, controls, personas) in the CoSAI Risk Map. It documents identifier formats, per-framework conventions, and the principles that should guide mapping decisions.

---

## Table of Contents

1. [Purpose](#purpose)
2. [General Principles](#general-principles)
3. [Framework Applicability](#framework-applicability)
4. [Per-Framework Conventions](#per-framework-conventions)
   - [MITRE ATLAS](#mitre-atlas)
   - [NIST AI RMF](#nist-ai-rmf)
   - [STRIDE](#stride)
   - [OWASP Top 10 for LLM](#owasp-top-10-for-llm)
   - [ISO 22989](#iso-22989)
   - [EU AI Act](#eu-ai-act)
5. [Granularity Guidelines](#granularity-guidelines)
6. [Entity-Specific Guidance](#entity-specific-guidance)
7. [Adding Mappings for a New Framework](#adding-mappings-for-a-new-framework)
8. [Reviewer Checklist](#reviewer-checklist)
9. [Related Documentation](#related-documentation)

---

## Purpose

Framework mappings connect CoSAI Risk Map entities to external security and AI governance standards. They serve two purposes:

- **Cross-referencing**: Let practitioners locate CoSAI content from within the frameworks they already use (MITRE ATLAS, NIST AI RMF, etc.)
- **Validation**: Support claims about coverage — which threats does CoSAI address, and where?

Mappings are not exhaustive catalogs. Every entry should be there because it is directly relevant, not because it is adjacent or related.

---

## General Principles

**Use official identifiers.** Copy IDs exactly from the source framework. Do not paraphrase, abbreviate, or construct identifiers that don't appear in the framework's own documentation.

**Be selective.** Map to items that are directly relevant to the CoSAI entity. A mapping should be defensible with a one-sentence rationale: "This risk is an instance of [technique]" or "This control implements [mitigation]."

**Do not map to both a parent and its sub-technique.** If `AML.T0010` applies, and `AML.T0010.002` is the more specific and accurate match, use only the sub-technique. Using both creates redundancy and implies the parent covers something the sub-technique does not.

**Document non-obvious rationale in the PR description.** The YAML file is not the place for inline justification. If a mapping requires explanation (e.g., a risk maps to an ATLAS technique only partially, or a control maps to a framework category that isn't the obvious first choice), explain it in the PR body.

**If you are mapping to more than four items in one framework, pause.** Either the CoSAI entity is too broad and should be split, or the mapping criteria are too loose. Four is a soft limit, not a hard rule, but consistently exceeding it signals a problem.

**Omit a framework entirely if there is no strong match.** An empty `mappings` block is valid and common. Do not map to the closest available item just to have a mapping.

**Mappings are not authoritative endorsements.** No framework maintainer has reviewed or approved these mappings. They represent the CoSAI working group's best-effort interpretation.

---

## Framework Applicability

Not every framework applies to every entity type. The `applicableTo` field in `frameworks.yaml` controls which entities may reference each framework. The schema enforces this — using an inapplicable framework will fail validation.

| Framework         | Risks | Controls | Personas |
|-------------------|:-----:|:--------:|:--------:|
| MITRE ATLAS       | yes   | yes      | no       |
| NIST AI RMF       | no    | yes      | no       |
| STRIDE            | yes   | no       | no       |
| OWASP Top 10 LLM  | yes   | yes      | no       |
| ISO 22989         | no    | no       | yes      |
| EU AI Act         | no    | yes      | yes      |

STRIDE, NIST AI RMF, and EU AI Act are asymmetric by design: STRIDE categorizes threats (risks), not countermeasures; NIST AI RMF is control-oriented and does not provide a threat taxonomy; EU AI Act defines obligations (controls) and roles (personas) but not a risk catalog.

---

## Per-Framework Conventions

### MITRE ATLAS

**Applies to:** risks, controls

**Source:** [https://atlas.mitre.org](https://atlas.mitre.org) — version 5.0.1 as of October 2025

**Identifier formats:**
- Techniques: `AML.T####` (e.g., `AML.T0020`)
- Sub-techniques: `AML.T####.###` (e.g., `AML.T0010.002`)
- Mitigations: `AML.M####` (e.g., `AML.M0007`)

**Risks map to techniques.** ATLAS techniques (`AML.T####`) describe adversary actions; a risk in CoSAI describes what can go wrong. The connection is: "An attacker using [technique] realizes [this risk]." Use the most specific technique available. If only a sub-technique applies, use the sub-technique, not the parent.

**Controls map to mitigations.** ATLAS mitigations (`AML.M####`) describe defensive actions. The connection is: "[This control] implements or contributes to [mitigation]." Some controls have no mitigation equivalent in ATLAS (ATLAS is more technique-heavy than mitigation-heavy); it is valid to leave `mitre-atlas` out of a control's mappings.

**Do not mix techniques and mitigations within one entity.** Risks reference `AML.T####`; controls reference `AML.M####`.

```yaml
# Risk — technique identifiers
mappings:
  mitre-atlas:
    - AML.T0020
    - AML.T0010.002   # sub-technique is more specific than AML.T0010

# Control — mitigation identifiers
mappings:
  mitre-atlas:
    - AML.M0007
```

---

### NIST AI RMF

**Applies to:** controls only

**Source:** NIST AI 100-1 — [https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf](https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf)

**Identifier format:** `[Function]-[Category].[Subcategory]`

The four functions are:
- `GV` — Govern
- `MP` — Map
- `MS` — Measure
- `MG` — Manage

Examples: `GV-1.1`, `MS-2.7`, `MP-4.1`, `MG-4.1`

Always use the subcategory-level identifier (e.g., `MS-2.7`), not the category level alone (`MS-2`). The framework's subcategories are the actionable units; the category level is too coarse for meaningful mapping.

```yaml
mappings:
  nist-ai-rmf:
    - MS-2.7
    - MS-2.3
```

**Limitation:** NIST AI RMF v1.0 is control-oriented and relatively coarse-grained. Some CoSAI controls span multiple RMF subcategories, and some have no close match. Do not force a mapping where the fit is weak.

---

### STRIDE

**Applies to:** risks only

**Source:** [https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats](https://learn.microsoft.com/en-us/azure/security/develop/threat-modeling-tool-threats)

**Identifier format:** lowercase category name (no codes — STRIDE uses descriptive names, not IDs)

Valid values:
- `spoofing`
- `tampering`
- `repudiation`
- `information-disclosure`
- `denial-of-service`
- `elevation-of-privilege`

Map based on the primary security impact of the risk. Multiple STRIDE categories are appropriate when a risk has meaningfully distinct impacts across categories. However, be conservative — most risks have one or two primary STRIDE categories.

```yaml
mappings:
  stride:
    - tampering
    - elevation-of-privilege
```

**Limitation:** STRIDE was designed for traditional software systems. The categories are coarse and do not capture AI-specific threat nuances. Use MITRE ATLAS alongside STRIDE to provide more precise classification.

---

### OWASP Top 10 for LLM

**Applies to:** risks, controls

**Source:** [https://owasp.org/www-project-top-10-for-large-language-model-applications](https://owasp.org/www-project-top-10-for-large-language-model-applications) — version 2025 (released November 2024)

**Identifier format:** `LLM##` (zero-padded two-digit number, e.g., `LLM04`, not `LLM4`)

The 2025 Top 10:
| ID    | Title |
|-------|-------|
| LLM01 | Prompt Injection |
| LLM02 | Sensitive Information Disclosure |
| LLM03 | Supply Chain Vulnerabilities |
| LLM04 | Data and Model Poisoning |
| LLM05 | Improper Output Handling |
| LLM06 | Excessive Agency |
| LLM07 | System Prompt Leakage |
| LLM08 | Vector and Embedding Weaknesses |
| LLM09 | Misinformation |
| LLM10 | Unbounded Consumption |

**Risks map to OWASP categories that describe the same threat.** The OWASP list is LLM-specific; apply it only when the CoSAI risk is genuinely within scope of LLM application security. Not all CoSAI risks have an OWASP counterpart.

**Controls also map to OWASP categories** when the control directly mitigates that category's risks. The rationale is: "Implementing [this control] reduces exposure to [LLM##]."

```yaml
# Risk
mappings:
  owasp-top10-llm:
    - LLM04

# Control that mitigates prompt injection
mappings:
  owasp-top10-llm:
    - LLM01
```

---

### ISO 22989

**Applies to:** personas only

**Source:** ISO/IEC 22989:2022 — [https://www.iso.org/standard/74296.html](https://www.iso.org/standard/74296.html)

**Identifier format:** Free-text role names from the standard. No codes. Parenthetical qualifiers are part of the identifier when the standard uses them.

Examples of valid values:
- `AI Producer`
- `AI Partner (data supplier)`
- `AI Partner (infrastructure provider)`
- `AI Partner (tooling provider)`
- `AI Customer (application builder)`
- `AI Customer (end user)`

The parenthetical qualifier (e.g., `data supplier`, `application builder`) disambiguates broad roles that ISO 22989 further divides. Preserve the parenthetical exactly as it appears in the standard.

Some CoSAI personas have no direct ISO 22989 equivalent. Omit the `iso-22989` key rather than mapping to the closest available role.

```yaml
mappings:
  iso-22989:
    - AI Partner (data supplier)
```

---

### EU AI Act

**Applies to:** personas, controls (newly added — no mappings exist in the project yet)

**Source:** EUR-Lex — [https://eur-lex.europa.eu/eli/reg/2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689)

**Conventions are not yet established for this project.** The guidance below is a starting recommendation, not settled practice. Early contributions should use this as a baseline and note in their PR if they are departing from it.

**Recommended identifier format:** Article-level references using the pattern `Article {N}` or `Article {N}({paragraph})`. Use the official EUR-Lex text as the source for article numbering.

Examples:
- `Article 9` (risk management system requirements)
- `Article 13` (transparency and provision of information)
- `Article 72` (obligations for providers of general-purpose AI models)

**For personas:** Map to the EU AI Act's defined roles where the CoSAI persona corresponds to a legal obligation-bearer. The Act defines roles including "provider", "deployer", "importer", "distributor", and "authorised representative" (Articles 3 and 25). Use the Act's own terminology.

**For controls:** Map to articles that impose the obligation the control helps satisfy. The goal is to answer: "Which article requires or recommends this type of control?"

Because no mappings exist yet, the first contributions will set the de facto conventions. Raise questions in the PR discussion before merging novel patterns.

---

## Granularity Guidelines

**Prefer sub-techniques over parent techniques (MITRE ATLAS).** Sub-techniques are more precise and reduce the ambiguity of the mapping. Only use the parent when no sub-technique is specific enough, or when multiple sub-techniques apply and the parent is the accurate shared level.

**Do not map to a parent and its sub-technique simultaneously.**

```yaml
# Wrong — redundant
mappings:
  mitre-atlas:
    - AML.T0010
    - AML.T0010.002

# Correct — use only the most specific level that is accurate
mappings:
  mitre-atlas:
    - AML.T0010.002
```

**More than four mappings in one framework warrants review.** It often means:
- The CoSAI entity is covering too broad a concept and should be split
- The mapping criteria drifted from "directly relevant" toward "related"

There is no hard cap, but treat five or more as a prompt to re-examine the mapping, not a validation error.

---

## Entity-Specific Guidance

### Risks

Risks map to: MITRE ATLAS techniques, STRIDE categories, OWASP Top 10 for LLM categories.

The MITRE ATLAS mapping answers: "What attacker technique realizes this risk?"
The STRIDE mapping answers: "What class of security harm does this risk represent?"
The OWASP mapping answers: "Which LLM-specific risk category describes this?"

A risk with no strong ATLAS technique match (e.g., a compliance/policy-oriented risk like excessive data handling) should omit the `mitre-atlas` key rather than force a partial match.

### Controls

Controls map to: MITRE ATLAS mitigations, NIST AI RMF subcategories, OWASP Top 10 for LLM categories.

The MITRE ATLAS mapping answers: "Which ATLAS mitigation does this control implement?"
The NIST AI RMF mapping answers: "Which RMF subcategory does this control satisfy?"
The OWASP mapping answers: "Which LLM risk category does this control help mitigate?"

Controls that address broad concerns (e.g., assurance and governance controls) often lack specific framework equivalents. It is appropriate for these to have sparse or absent `mappings` sections.

### Personas

Personas map to: ISO 22989 actor roles, EU AI Act defined roles.

The ISO 22989 mapping answers: "Which standardized AI ecosystem actor corresponds to this CoSAI persona?"
The EU AI Act mapping answers: "Which legal role defined by the Act corresponds to this CoSAI persona?"

Not every CoSAI persona has a clear counterpart in these frameworks. The `personaGovernance` persona, for example, has no direct ISO 22989 equivalent and correctly omits `iso-22989` mappings.

---

## Adding Mappings for a New Framework

If you are proposing to add mappings for a framework not currently in `frameworks.yaml`, the process is:

1. **Read the framework registration process** in [guide-frameworks.md](../guide-frameworks.md). The framework must be registered before any entity can reference it.

2. **Establish identifier conventions** before adding entity-level mappings. Document the format in this file (in [Per-Framework Conventions](#per-framework-conventions)) as part of the PR that introduces the framework.

3. **Define `applicableTo`** in `frameworks.yaml` deliberately. Adding a framework to `applicableTo: [risks, controls, personas]` implies you have conventions ready for all three. Start with only the entity types you are actively mapping.

4. **Add a sample mapping** in the PR to illustrate the convention. Reviewers can evaluate whether the identifier format is correct and the mapping is well-reasoned.

5. **Note gaps and limitations** in the PR description. Every framework has areas where it does not align well with CoSAI's structure. Document known gaps so future contributors know where not to force mappings.

---

## Reviewer Checklist

When reviewing a PR that adds or modifies `mappings:` fields:

- [ ] Identifiers match the format specified in this guide for each framework
- [ ] No parent technique is mapped alongside its sub-technique
- [ ] Risks reference only techniques (`AML.T####`) and controls reference only mitigations (`AML.M####`) for MITRE ATLAS
- [ ] STRIDE values are lowercase and match the six valid categories exactly
- [ ] OWASP identifiers are zero-padded (`LLM04`, not `LLM4`) and from the 2025 version
- [ ] ISO 22989 role names preserve parenthetical qualifiers exactly as they appear in the standard
- [ ] Mappings with more than four entries per framework have been scrutinized
- [ ] No framework is used for an entity type not listed in its `applicableTo`
- [ ] Non-obvious mappings are explained in the PR description, not the YAML

---

## Related Documentation

- [guide-frameworks.md](../guide-frameworks.md) — How to register a new framework, framework definition file structure, validation rules
- [design/metadata-mappings.md](../design/metadata-mappings.md) — Phase 2 methodology: rationale tables for initial mappings, per-framework gap analysis, sources used (forthcoming)
- [guide-risks.md](../guide-risks.md) — Complete guide for adding or updating risks
- [guide-controls.md](../guide-controls.md) — Complete guide for adding or updating controls
- [guide-personas.md](../guide-personas.md) — Complete guide for adding or updating personas

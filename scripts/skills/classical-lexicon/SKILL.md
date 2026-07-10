---
name: classical-lexicon
description: Ground CoSAI Risk Map terminology in established security terms of art. Use when authoring or critiquing a Control, Risk, or Component title or description to check a proposed term against the canonical (NIST-first) vocabulary, replace an invented term with its established equivalent, generalize a product/protocol-specific name to its role, or confirm a term is already grounded.
---

# Classical Lexicon

Check Risk Map terminology against established security terms of art. The governing rule: **never invent a term when an established term of art already exists.** This skill grounds a proposed term, regrounds an invented one, or confirms an existing term is already sound — it does not rewrite content wholesale.

## When to use

- Authoring a new Control / Risk / Component title or description.
- Critiquing a draft for coined or product-specific terminology.
- Deciding what to call a capability, role, mechanism, or locus.

## When not to use

- Framework mapping IDs (MITRE ATLAS, NIST AI RMF, etc.) — that is the framework-mappings audit tooling's job.
- Prose style/format rules (bold, sentinels, length) — that is the prose-subset linter's job.

## Procedure

1. **Extract candidate terms** from the input: the nouns and noun-phrases that name a capability, security measure, role, mechanism, or architectural locus. These are where terminology matters.
2. **Look each up in the lexicon:** `references/lexicon.md`.
3. **Classify each candidate:**
   - **Grounded** — already an established term of art. Accept; name the source.
   - **Reground** — an invented or informal term with an established equivalent. Return the canonical term and the mapping.
   - **Generalize** — the term encodes a specific product or protocol (e.g. an `MCP`-prefixed name). The identity is the *role/locus*; the product is an attribute. Return the role-grain term; keep the product only as an example.
   - **Novel — flag** — no established term of art found. Do **not** coin one silently (see D3b below). "novel-flag" applies only when **no established term of art exists in the field**, not merely when the term is absent from this pinned lexicon snapshot; when you can ground a term via general NIST-first sourcing knowledge that the snapshot lacks, **ground it and propose the lexicon addition** rather than flagging it novel.
4. **Record the counterfactual** for every reground/generalize/novel result: `proposed → chosen → source (or "none found")`. This is inspectable reasoning, not a silent rename.

## NIST-first priority (ADR-031 D3a)

NIST's term is the term unless there is a strong, documented argument that it fails. Prefer, in order: NIST (SP 800-53 / 800-207 / 800-162, AI RMF), then other US/international standards bodies and classical literature (RFC, OWASP, MITRE, ISO, foundational papers).

If a contributor argues the NIST term fails and a new term is needed, **do not decide that here.** Surface it as a documented deviation for the maintainer to take into CoSAI governance review (issue / discussion). This skill grounds and flags; maintainers adjudicate.

## Contrarian counterbalance (ADR-031 D3b)

To keep grounding from being solely US-centric: when NIST is silent, or the canonical term is contested, **surface the non-US framing** (ENISA, ISO, other national/international bodies) and **flag it to the maintainer** as a counterbalance gap. The maintainer decides in governance review; this skill's obligation is to make sure they *see* the gap rather than having to watch non-US bodies by hand. Never resolve a contested or NIST-silent term by inventing one.

## Term verification (ADR-031 D4)

The lexicon holds **stable** canonical terms (PEP/PDP/PIP/PAP, reference monitor, least privilege) — treat these as a pinned snapshot. For a term or identifier that may have changed (a framework's evolving vocabulary), verify it against the source via WebSearch/WebFetch at use time rather than trusting the snapshot.

## Output format

For each candidate term, report:

| Candidate | Verdict | Canonical term | Source | Maintainer flag |
|---|---|---|---|---|

- **Verdict:** `grounded` · `reground` · `generalize` · `novel-flag`
- **Maintainer flag:** present only for `novel-flag` or a contested/NIST-silent term — state the counterbalance gap and any non-US framing found.

Close with the counterfactual list (`proposed → chosen → source`) for anything not already grounded.

## Reference

- `references/lexicon.md` — the canonical term set and the invented→canonical mappings, with sources.

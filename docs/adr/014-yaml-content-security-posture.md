# ADR-014: YAML content security posture for the CoSAI Risk Map

**Status:** Accepted
**Date:** 2026-04-24
**Authors:** Architect agent, with maintainer review

---

## Context

`risk-map/yaml/{components,controls,risks,personas,mermaid-styles}.yaml` is the authoritative source for the CoSAI Risk Map framework. Everything else — generated tables under `risk-map/tables/`, generated Mermaid and SVG artifacts under `risk-map/diagrams/` and `risk-map/svg/`, the persona-site JSON emitted by `scripts/build_persona_site_data.py`, and the static renderer under `site/` — is derived from it. The framework is published for wide reuse; external parties routinely ingest the raw YAML into LLMs, prompt libraries, vendor tooling, and downstream frameworks.

Four consumer surfaces coexist today with incompatible trust assumptions:

1. **External redistribution.** Third parties read the YAML directly. No repo-side code is in the path; the only contract is whatever the YAML and its schemas assert.
2. **The `site/` static SPA.** The renderer at `site/assets/app.mjs` escapes scalar YAML through `escapeHtml` (defined at `app.mjs:21-33`) for titles, categories, and question prompts, but `renderRichParagraphs` (lines 68-78) writes prose directly into `innerHTML` without escaping. [ADR-012](012-static-spa-architecture.md) names this as the trust boundary the renderer leans on `escapeHtml` discipline to defend, and flags the un-escaped prose path as a known XSS-adjacent surface. The maintainer's stated direction is a minimal markdown subset (`**bold**`, `*italic*`, outbound `[text](url)`) with everything else stripped — that policy is the subject of a sibling ADR, not this one.
3. **CI/CD tooling.** `scripts/hooks/validate_riskmap.py`, `scripts/hooks/validate_control_risk_references.py`, `check-jsonschema`, the generators (`scripts/hooks/yaml_to_markdown.py`, `scripts/build_persona_site_data.py`), and the pre-commit hooks catalogued in [ADR-005](005-pre-commit-framework.md) and [ADR-013](013-site-precommit-hooks.md). These tools execute YAML content through Python and Node, and they run on every contributor's machine.
4. **Generated markdown tables under `risk-map/tables/`.** Committed artifacts, rendered on GitHub. `collapse_column` in `scripts/hooks/yaml_to_markdown.py` (around line 123) passes prose through with only newline-to-`<br>` substitution; literal HTML the author wrote is propagated verbatim into the table cell.

A cross-reference conventions investigation surfaced that the whole space is under-specified. `risk-map/tables/risks-full.md` contains 8 dead `href="#risk..."` links with zero matching anchor targets in the file — the table generator does not emit targets, and the flat-table layout has no heading slugs to auto-resolve. `risks.yaml` and `controls.yaml` mix 14 anchored-HTML cross-references with 41 bare-identifier mentions across 17 entries, with two entries using both conventions in the same prose field. `site/` is the only surface where any of those links resolve today, via the `innerHTML` path that skips `escapeHtml` for prose. No documented rule tells authors which convention to use, no validator catches drift, and no policy exists for what HTML or markdown prose is allowed to carry into either the site or the redistributed YAML. There is no coherent answer to "what counts as safe YAML content," "where does sanitization live," or "what do we tell downstream consumers about redistribution safety." Without an explicit posture, every sibling decision — the site sanitization subset, the reference-strategy convention, per-file schema tightening — re-derives a trust model from scratch and risks contradicting the next one.

This ADR establishes the frame. It does not decide the subset, the sentinel syntax, or the per-field schema rules; those are sibling ADRs that this one constrains.

## Decision

The CoSAI Risk Map adopts the following security posture for its YAML content. Six policy primitives define the posture; sibling ADRs instantiate them.

### P1. YAML is untrusted input at every consumer boundary

Repository contributors are reviewed, but the YAML is published under an open license and ingested by parties outside that review process. Every consumer — the site renderer, the table generator, the persona-site builder, any downstream tool — treats YAML prose as **untrusted input** and handles it accordingly at its own boundary. "Trusted because a maintainer merged it" is not a posture the framework can export.

### P2. Content classes drive handling

YAML fields fall into five classes, and each class has a different handling contract:

- **Identifiers** — `id`, enum-backed references (`personas`, `controls`, `edges.to`, `edges.from`, `category`). Schema-enforced enums or regex. Authoritative for cross-references; never rendered as prose.
- **Structured references** — typed arrays of identifiers (`risks[].controls`, `controls[].risks`, `components[].edges`). Validated against identifier enums and cross-file referential integrity (`validate_control_risk_references.py`, `ComponentEdgeValidator`). These are the canonical shape for intra-framework linking; prose is not.
- **Prose** — `description`, `shortDescription`, `longDescription`, `examples`, `responsibilities`, `tourContent.*`, and equivalents. Authored free-text intended for rendering. This is the class that needs sanitization at generation and render boundaries.
- **Metadata** — `title`, versioning fields, `mappings.*` (framework cross-walks), `deprecated`. Short scalar or structured values; treated as prose for escaping purposes when rendered, but not a vector for multi-paragraph markup.
- **Generated artifacts** — `risk-map/tables/*.md`, `risk-map/diagrams/*.{md,mermaid}`, `risk-map/svg/*`, `site/generated/persona-site-data.json`. Derived from the four classes above; reproducible from YAML alone.

Sibling schema ADRs are free to split these further or rename them, but the class boundary between **identifiers / structured references** (authoritative, schema-constrained) and **prose / metadata** (authored, requires escaping) is load-bearing.

### P3. Cross-references are structured, not prose

Intra-framework links (risk↔control, risk↔risk, control↔control, component↔component, persona↔risk) are expressed through the **structured-reference** fields whose values are enum-checked. Prose is not a linking surface. The cross-reference convention ADR picks the specific authoring syntax for mentions that appear *inside* prose (bare camelCase ID, sentinel, or similar), but the authoritative edge set lives in the structured fields and is what every validator, generator, and renderer reads.

This prevents the site and table surfaces from diverging on what "related" means, and it is what lets schema enums catch rename failures across every surface at once.

### P4. Sanitization belongs at the generation and render boundaries, not at authoring

Three enforcement points handle prose safely; they stack, they do not substitute for each other:

- **Authoring time (schema + lint).** Schemas constrain **shape** — types, enums, required fields, prose-shape invariants (see [ADR-011](011-persona-site-data-schema-contract.md)'s `definitions/prose`). A pre-commit lint may additionally **reject** prose that contains markup outside the allowed subset, so a YAML author sees the failure at `git commit` rather than at render time. This is a reject-and-block posture, not a rewrite posture: the author fixes the source.
- **Generation time (table and site builders).** `scripts/hooks/yaml_to_markdown.py` and `scripts/build_persona_site_data.py` apply the markdown subset when transforming prose into their output formats. The builders are responsible for emitting output that is safe for their consumer even if the YAML itself somehow slipped past the authoring-time lint.
- **Render time (site DOM writes).** The renderer continues to route prose through the allowed-subset transform before `innerHTML` assignment. [ADR-012](012-static-spa-architecture.md)'s `escapeHtml` discipline is the current defense; the sibling site-sanitization ADR tightens it.

Relative to each consumer, YAML prose is **untrusted**. The repo is responsible for making it **safe** at the moment of rendering into a specific output format — and for documenting the contract so downstream consumers can do the same at their own boundaries.

### P5. Redistribution contract is honest and minimal

The framework cannot tell downstream consumers "the YAML is safe for your pipeline" — the repo does not know what their pipeline is. It can make two honest statements:

- **Content provenance.** Every change to `risk-map/yaml/**` lands through reviewed PRs, attributed to identifiable contributors, with AI-assisted contributions tagged per [ADR-004](004-ai-assistant-trailer.md). The commit history is the provenance record.
- **Shape guarantees.** The schemas at `risk-map/schemas/*.schema.json` describe what every field is, and the validators in `scripts/hooks/` enforce cross-file integrity. Downstream consumers that validate against the published schemas get the same shape guarantee the repo's own tooling relies on.

Everything else — HTML escaping for web consumers, prompt-injection defenses for LLM consumers, markup stripping for PDF exporters — is **the downstream consumer's responsibility**, because the repo does not know which threat model applies. The framework documents this as the contract, in a location sibling ADRs can point at (likely a section in `risk-map/docs/` authored alongside the schema tightening work, not in this ADR).

### P6. Threat surfaces are named, not silently inherited

The sibling ADRs defend against specific threats; each ADR names which surfaces it addresses. The threat set this posture recognizes:

- **XSS via the site renderer** — prose with `<script>`, `on*=`, `javascript:` URIs, or arbitrary tags flowing into `innerHTML`. Addressed by the site-sanitization ADR (subset + allowlist) and by the existing schema-shape invariants.
- **Prompt injection in LLM consumers** — prose crafted to subvert a downstream model's instructions. The repo cannot defend this for consumers, but it can (a) refuse content whose evident intent is to inject, via content review, and (b) document that consumers must sanitize before embedding in prompts. Not a code-level defense on the repo side.
- **Malformed markup breaking generators** — nested-list shape drift of the kind [ADR-011](011-persona-site-data-schema-contract.md) fixed (BLOCK-02). Addressed by schema-shape invariants and in-builder fail-before-write.
- **Cross-reference drift** — IDs that no longer resolve, bare-ID typos in prose, rename failures across surfaces. Addressed by P3 (structured references) and by the cross-reference convention ADR plus a prose-token linter.
- **Content integrity** — who can land changes and how it is verified. Addressed by GitHub branch protection, PR review, and the provenance commitment in P5.
- **Supply chain of tooling that reads the YAML** — pinned validators ([ADR-011](011-persona-site-data-schema-contract.md)), pinned tool versions ([ADR-003](003-devcontainer-mise-architecture.md)), pre-commit framework ([ADR-005](005-pre-commit-framework.md)). Not a YAML-content concern directly, but the enforcement points depend on these pins.

Sibling ADRs add to this list as needed; this ADR is the starting frame.

## Alternatives Considered

- **Treat YAML as trusted because maintainers review it.** Rejected. The YAML is published and ingested by parties outside the review process; "reviewed upstream" is not an assertion the repo can export, and it is not sufficient defense for the site renderer today where `innerHTML` discipline is a single-line defense against arbitrary authored markup. It also pushes every threat-model question onto every sibling ADR's author rather than settling it once.
- **Push all sanitization to authoring time (strict schemas, no render-time defense).** Rejected. Schemas are good at shape, weak at semantics. A schema can assert "prose is `string | array<string>`"; it cannot cheaply assert "this string contains no dangerous markup" without becoming a parser. Render-time defense stays in place regardless; layering authoring-time lint on top catches authors early without removing the load-bearing defense.
- **Push all sanitization to render time (permissive authoring, site/table builders handle everything).** Rejected. The site is not the only consumer; external redistribution has no render layer under the repo's control. Leaving the YAML permissive means exporting a liability. Authoring-time lint is cheap — a `pre-commit` hook per [ADR-013](013-site-precommit-hooks.md)'s pattern — and raises the safety baseline the published file carries with it.
- **Adopt an industry taxonomy (OSCAL, STIX, ATT&CK) for the content model.** Rejected as out of scope for this ADR. Framework-content design belongs in `risk-map/docs/design/`; this ADR is about the security posture of the existing content model, not its shape. A migration to an external taxonomy would be a separate, much larger ADR and does not need to block this frame.
- **Defer the posture until each sibling ADR needs it.** Rejected. The sibling ADRs — site sanitization, cross-reference convention, per-file schema tightening — all depend on the same trust model. Deriving it three times produces three subtly different models; deriving it once here is cheaper and keeps them coherent.

## Consequences

**Positive**

- **Sibling ADRs have a frame to cite.** The site-sanitization ADR can say "per ADR-014 P4, sanitization belongs at the render boundary" instead of re-arguing the point. The reference-strategy ADR can say "per ADR-014 P3, prose is not a linking surface" and move on to the authoring syntax question. The per-file schema ADRs can cite P2's content classes to justify field-by-field rules.
- **The trust boundary is now explicit.** Contributors reading the YAML, the builders, or the renderer can tell which class of content they are handling and what the handling contract is. `escapeHtml` discipline in [ADR-012](012-static-spa-architecture.md) becomes a named implementation of P4's render-time layer rather than an improvisation.
- **The redistribution contract is honest.** The framework documents what it guarantees (shape, provenance) and what it does not (safety in any specific consumer pipeline). Downstream consumers know to sanitize; the repo does not overpromise.
- **Cross-surface coherence.** Because structured references (P3) are authoritative, the site, the tables, and any future consumer all read the same edge set. A rename of `riskFoo` propagates through enums and validators on every surface at once; prose mentions are a secondary, cosmetic concern handled by a linter rather than a correctness concern.

**Negative**

- **Posture enforcement is distributed.** P4 stacks three enforcement points (authoring, generation, render), and each has to stay in sync with the others. If the authoring-time lint drifts from the render-time subset, authors will see confusing failures (or worse, silent pass-through). Sibling ADRs own the instantiation; this ADR cannot make the drift go away, only name it.
- **The "untrusted YAML" framing is a new discipline for contributors.** Contributors who have historically thought of YAML as repository-local and therefore safe will now encounter prose-content review findings (markup outside the subset, IDs that bypass structured references) that previously would have slipped through. Contributor-facing docs need to explain the posture so reviews do not land as surprises.
- **Downstream consumers carry real responsibility.** P5 makes this explicit rather than hidden, which is the right trade, but it means the framework is publicly declining to guarantee things that consumers may expect ("this YAML is safe to put in my LLM prompt"). The honest contract is the right long-term posture; in the short term, consumers used to an implicit safety assumption may push back.
- **The six primitives constrain sibling ADRs.** A sibling ADR that wants to, say, treat structured references as non-authoritative, or push sanitization entirely to authoring, now has to argue against this ADR rather than just pick a convenient approach. That is the intended effect; it is also a real authoring cost for the sibling.
- **Content-class taxonomy is a commitment.** P2 names five classes. A future field that doesn't fit cleanly (for example, a field that is partly structured and partly prose, like a cited-reference block with a URL and a quotation) will need either a schema split or an ADR revisit. The taxonomy is deliberately coarse; sibling ADRs may find corners.

**Follow-up**

- **Site sanitization invariants ADR.** Picks the specific markdown subset (`**bold**`, `*italic*`, outbound `[text](url)`), names the allowlist, and specifies where the transform runs (render-time). Instantiates P4's render-time layer and closes the `renderRichParagraphs` un-escaped path flagged in [ADR-012](012-static-spa-architecture.md).
- **Cross-reference strategy ADR.** Picks between bare camelCase IDs (Option B in the draft investigation) and sentinel syntax (Option D-sentinel / ATLAS-style `{{riskXxx}}`) for intra-prose mentions. Instantiates P3 for the authoring layer and specifies the accompanying prose-token linter.
- **Per-file schema tightening ADRs (one per file, or a combined one).** Apply P2's content-class taxonomy to each of `components.schema.json`, `controls.schema.json`, `risks.schema.json`, `personas.schema.json`, `mermaid-styles.schema.json`. Expected outputs: tighter field-level constraints on prose fields, explicit enum coverage on structured-reference fields, and `additionalProperties: false` where it is not already set.
- **Redistribution contract documentation.** Author a section under `risk-map/docs/` (not `docs/adr/`) that states P5 in the terms a downstream consumer needs: what the framework guarantees, what it does not, and the minimum sanitization downstream consumers should apply before embedding content in their own surfaces. This is documentation, not decision; it references this ADR as the source of the commitment.
- **Authoring-time prose lint (P4).** The pre-commit hook that rejects prose containing markup outside the site-sanitization ADR's subset. Pattern is already established by [ADR-013](013-site-precommit-hooks.md); this hook is a sibling entry in `.pre-commit-config.yaml` once the subset is fixed.
- **If a future consumer surface proposes its own trust model** (for example, an SDK that parses YAML client-side and needs a different sanitization boundary), revisit this ADR. The six primitives should generalize, but a concrete counter-example is a signal to check rather than an assumption the model still holds.

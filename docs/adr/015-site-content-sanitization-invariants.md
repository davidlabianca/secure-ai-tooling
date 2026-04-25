# ADR-015: `/site/` content sanitization invariants

**Status:** Accepted
**Date:** 2026-04-25
**Authors:** Architect agent, with maintainer review

---

## Context

[ADR-014](014-yaml-content-security-posture.md) establishes the trust model: YAML prose is untrusted at every consumer boundary (P1), prose is one of five content classes that needs sanitization at generation and render boundaries (P2), cross-references are carried by structured fields rather than prose (P3), and sanitization stacks across authoring, generation, and render (P4). ADR-014 names the `/site/` renderer path as the load-bearing render-time surface.

This ADR is **render-time only**. The canonical YAML prose authoring subset — the markdown tokens authors may write in prose fields, and the pre-commit lint that enforces them — is decided in [ADR-017](017-yaml-prose-authoring-subset.md). The authoring subset is a YAML *source* contract that affects multiple consumers (this site, the table generator, third-party redistribution per ADR-014 P5, future export surfaces); it does not belong in a site-specific ADR. ADR-015 cites the ADR-017 subset by reference and decides only what the site renderer does with subset-compliant input.

Two-layer responsibility split:

- **ADR-017 (authoring time + builder pass-through).** Defines the canonical markdown subset. Owns the pre-commit lint that rejects out-of-subset prose. Guarantees that prose strings reaching any consumer are subset-compliant.
- **ADR-015 (render time, this ADR).** Consumes prose guaranteed to conform to ADR-017's subset and produces DOM that conforms to the allowlist below. Escapes anything outside the allowlist (and strips disallowed attributes within an allowed tag) as defense-in-depth against an authoring-lint regression.

[ADR-016](016-reference-strategy.md) decides `{{idXxx}}` and `{{ref:identifier}}` sentinels for intra-document and external references. By the time prose reaches the renderer, those sentinels have already been expanded by `scripts/build_persona_site_data.py` per ADR-016 D5 to **structured prose items** — `{type: "ref", id, title}` for intra-document references and `{type: "link", title, url}` for external references. The renderer does not see sentinels or raw markup; it sees a stream of post-expansion strings (containing the markdown subset only) and structured items (which it formats into in-page anchors and outbound links). ADR-015's allowlist applies to both shapes.

The concrete state of the render surface, at commit `6945285`:

- `site/assets/app.mjs:21-33` defines `escapeHtml`. It is called on titles, category names, control and persona labels, and question prompts (call sites at lines 425, 431, 447, 511, 513, 539, 677).
- `site/assets/app.mjs:68-78` defines `renderRichParagraphs`. It assigns prose items into `innerHTML` **without** calling `escapeHtml`. Every call site that emits `description`, `shortDescription`, `longDescription`, or `examples` (lines 433, 462, 467, 518, 521, 524) flows through this path. This is the un-escaped surface [ADR-012](012-static-spa-architecture.md) names as XSS-adjacent.
- [ADR-011](011-persona-site-data-schema-contract.md) `definitions/prose` constrains prose *shape* (`array` of `string | array<string>`, one level of nesting) but intentionally does not constrain *string contents*. Without a render-time transform, arbitrary markup in those strings reaches `innerHTML` directly.

Without a render-time allowlist, every renderer change is a per-reviewer judgment call, and the `renderRichParagraphs` un-escaped path stays as a single-line defect away from shipping arbitrary script to every visitor.

## Decision

The `/site/` renderer treats post-expansion YAML prose as untrusted input and emits an explicit HTML allowlist at render time, escaping everything else. The transform is the sole path by which prose reaches `innerHTML`.

### D1. Rendered-HTML allowlist

The renderer consumes two input shapes (both described in Context) and emits exactly these elements:

- `<strong>`, `</strong>` — emitted from the `**bold**` token in ADR-017's markdown subset. No attributes.
- `<em>`, `</em>` — emitted from `*italic*` / `_italic_` tokens in ADR-017's markdown subset. No attributes.
- `<a …>`, `</a>` — emitted **only** from structured prose items (`{type: "ref", ...}` or `{type: "link", ...}`) produced by the builder per ADR-016 D5. Authors do not write `<a>` markup in prose; sentinels were the only authoring path for anchors, and the builder consumed them before the renderer ran. The renderer constructs the element with attributes `href` (required, `https:` scheme only; for `ref` items the href is the in-page fragment derived from the resolved entity), `rel` (set to `noopener noreferrer` for outbound `link` items), `target` (set to `_blank` for outbound `link` items). All other attributes are stripped.

The `rel="noopener noreferrer" target="_blank"` attributes are **constructed** by the renderer; authors do not write them in YAML and cannot override them. The `https:`-only constraint is enforced both upstream (ADR-017 authoring lint) and at render time (defense-in-depth).

Paragraph and hard-break handling is unchanged: `renderRichParagraphs` continues to wrap each array item in `<p>`, with nested arrays becoming a `<div class="subsection">` block. The transform operates on the string contents of each paragraph, not on paragraph structure.

Any other tag found as literal HTML in the input (including `<br>`, `<p>`, `<div>`, `<span>`, `<img>`, `<script>`, and any prose-embedded `<a href="#…">` anchor) is **escaped**, not stripped — the characters `<` and `>` are rendered as `&lt;` / `&gt;` so a contributor who bypassed the upstream lint can see that their markup did not land, and so a silently-dropped tag cannot mask an XSS attempt.

Intra-document navigation within the site (risk → control cross-links at `app.mjs:446` and `app.mjs:538`) is produced from the **structured** `relatedControlIds` / `relatedRiskIds` fields per [ADR-014](014-yaml-content-security-posture.md) P3, and from ADR-016 sentinels expanded by the builder before prose reaches the renderer. Prose-embedded `<a href="#…">` literals are not part of the allowlist.

### D2. Transform location

The transform lives in a new module, **`site/assets/sanitizer.mjs`**, with a single exported function `renderProse(input: string): string` that returns the allowlisted HTML string. `renderRichParagraphs` calls `renderProse(paragraph)` in place of the current raw interpolation at `app.mjs:72` and `app.mjs:75`. No other call site in `app.mjs` changes; `escapeHtml` remains the correct tool for scalar fields (titles, categories, question prompts) where the markdown subset does not apply.

The module is vanilla ESM with zero runtime dependencies, consistent with [ADR-012](012-static-spa-architecture.md). Its exported surface is testable under `node --test` without a DOM, closing part of the `NIT-07` untested-helper gap ([issue #224](https://github.com/cosai-oasis/secure-ai-tooling/issues/224)) for the prose path specifically.

### D3. Sanitizer approach

The transform is **hand-rolled**, not a library. ADR-017's subset is three productions; a regex-driven tokenizer with a small state machine handles it in well under 100 lines. Introducing a library (`DOMPurify`, `marked`, `markdown-it`) would invert the zero-dep posture ADR-012 commits to, and the subset is small enough that a library's configuration surface is larger than the replacement code.

#### D3a. Bounded emission surface is the safety property

Hand-rolled HTML sanitization is a known antipattern when the sanitizer is asked to *parse and clean arbitrary HTML input*. That is not what `renderProse` does. The property that makes this approach defensible — and which must be preserved for it to remain defensible — is that the renderer's **emission surface is bounded by a hard-coded set of tag names**:

- The allowlist is a literal constant in `sanitizer.mjs` (e.g., `const ALLOWED_TAGS = ['strong', 'em', 'a']`). It is not a runtime parameter, not a configuration field, not derived from input. The renderer cannot emit a tag that is not literally written into the output string by `sanitizer.mjs` itself.
- HTML attribute values for `<a>` (`href`, `rel`, `target`) are **constructed** by the renderer, not copied from input. The `href` value is validated against the `https:` scheme before insertion; `rel` is the constant `"noopener noreferrer"`; `target` is the constant `"_blank"`. No attribute name or value flows from input to output uninspected.
- The input grammar reaching the renderer is bounded: post-expansion strings carry ADR-017's two markdown productions (`**bold**`, `*italic*`/`_italic_`) only — sentinels have already been resolved to structured items by the builder per ADR-016 D5. The structured items are typed objects with a fixed shape (`{type: "ref", id, title}` or `{type: "link", title, url}`), not free-form input. The transform is a tokenizer over the fixed markdown grammar paired with an emitter over a fixed output set, plus a typed formatter for the structured items; there is no general HTML parser to attack.

Together these constraints turn "hand-rolled HTML sanitizer" — a known footgun — into "tokenizer over a known input grammar emitting a known output set," which is a tractable problem at this size. The footgun is **scope creep**: a future contributor adding "just one more tag" to the allowlist erodes the bounded-emission property. Once the allowlist grows past a small fixed set, or once attribute values start flowing from input to output, the renderer becomes a real HTML sanitizer — and a real HTML sanitizer is exactly what hand-rolled fails at.

This property is not a polite request. It is the load-bearing assumption of D3 and is structurally enforced by D3b below.

#### D3b. Test coverage is the scope-creep guardrail

Test coverage is the mechanism that prevents the bounded-emission property from drifting. Unit tests are not optional on this module; they are the structural enforcement of the property the safety claim rests on.

- **Per-tag fixtures are mandatory.** Every entry in the allowlist constant has at least one **positive fixture** (input → expected safe output) and one **negative fixture** (a related disallowed input → escaped or stripped output). A new tag in `ALLOWED_TAGS` without matching fixtures is not a runtime failure; it is a *test-suite failure*.
- **Allowlist–fixture meta-test.** The test suite contains a meta-test that asserts the allowlist constant matches the fixture set, e.g., `assert(ALLOWED_TAGS.every(tag => fixtures.has(tag)))`. Adding a tag to the allowlist without adding a fixture for it fails CI.
- **Attack-corpus fixture for `<a>`.** The corpus covers known XSS vectors against the link form specifically: `javascript:`, `data:`, `vbscript:`, mixed-case schemes (`JaVaScRiPt:`), schemeless URLs, IDN homograph examples, attribute-injection attempts via quote handling in the link text, and leading/trailing whitespace tricks in the URL. Each vector has an expected escaped/stripped output.
- **Test location.** Tests live at `site/tests/sanitizer.test.mjs` under ADR-012's `node --test` discipline. The fixture corpus is committed under `site/tests/fixtures/sanitizer/` (one file per category: positive, negative, attack-corpus). The fixtures are data, not code; a contributor adding a vector adds a file, not a test function.
- **CI is the enforcement point.** Any sanitizer change that lacks matching fixture updates fails CI. This is the only mechanism preventing the bounded-emission property from drifting silently. There is no "fix it in a follow-up" path: a sanitizer PR without test coverage is incomplete.

The test discipline is what turns the bounded-emission property from a code-review convention into a structural invariant. D3 without D3b is not defensible; the two are one decision.

### D4. Render-time failure mode

Per [ADR-014](014-yaml-content-security-posture.md) P4, render time is one of the stacked enforcement points. The other two — authoring-time block and builder pass-through — are owned by ADR-017. ADR-015 commits to the render-time behavior:

- **Render time — escape with console warning.** `renderProse` applies the transform. Any literal HTML outside the allowlist is escaped (not silently dropped), and the sanitizer emits `console.warn("renderProse: escaped unexpected markup", {input, escaped})` once per offending paragraph. The warning is a diagnostic for a contributor who bypassed the upstream lint (for example by committing with `--no-verify`, or under a lint regression); it is not a user-facing message.

Silent strip is rejected at render time because it hides contributor mistakes and masks an upstream-lint regression. Visible escape (with `&lt;` / `&gt;` reaching the page) is loud but accurate, and the console warning gives a contributor running the site locally a precise diagnostic.

### D5. Threat model

The site-specific threat model this ADR addresses:

- **XSS via `innerHTML`.** `renderRichParagraphs` is the only un-escaped `innerHTML` write path for content the site renders today. Routing every paragraph through `renderProse` closes that path by construction.
- **`target="_blank"` rel discipline.** Outbound anchors must carry `rel="noopener noreferrer"` to prevent the new-tab page from accessing `window.opener` and to suppress referrer leakage. The renderer constructs these attributes; authors cannot omit them.
- **URL scheme escape.** A `javascript:` or `data:` URL in an author-written link is a script-execution vector. `renderProse` rejects any non-`https:` scheme even though ADR-017 also rejects it upstream; the duplicate check is intentional defense-in-depth.

This is a render-time threat model. Threats specific to the YAML source contract (third-party-renderer hostility, redistribution safety) are ADR-014's domain and ADR-017's responsibility to address upstream.

### D6. Render-time enforcement

Every render-time rule in this ADR is machine-enforced by `renderProse`; none are prose-only guidance.

| Rule | Render-time enforcement |
|---|---|
| HTML allowlist limited to `<strong>`, `<em>`, `<a>` (with restricted attributes) | `renderProse` construct + escape disallowed |
| Allowlist is a hard-coded literal constant in `sanitizer.mjs`, not a runtime parameter | Code structure; reviewer-enforced; meta-test asserts allowlist matches fixture set |
| URL scheme restricted to `https:` (defense-in-depth; also enforced upstream by ADR-017) | `renderProse` rejects non-`https:` |
| `<a>` attribute values constructed by renderer, not copied from input | `renderProse` (literal `rel`/`target`; validated `href`) |
| Outbound links get `rel="noopener noreferrer" target="_blank"` | `renderProse` constructs attributes |
| Disallowed markup is escaped, not stripped | `renderProse` |
| Console warning on escaped input | `renderProse` |
| Every allowlist entry has positive + negative fixtures | `site/tests/sanitizer.test.mjs` meta-test (`ALLOWED_TAGS.every(tag => fixtures.has(tag))`) |
| Attack-corpus fixture covers known `<a>` XSS vectors | `site/tests/fixtures/sanitizer/attack-corpus/` |

Authoring-time enforcement of the markdown subset (block on commit) is **enforced upstream by ADR-017** and is not duplicated here.

## Alternatives Considered

- **Library-based sanitizer (DOMPurify, marked + DOMPurify).** Rejected. Introduces a runtime dependency the site does not currently carry, inverts [ADR-012](012-static-spa-architecture.md)'s zero-dep posture, and the configuration surface to restrict a library to ADR-017's three-production subset is larger than the hand-rolled transform. If the subset ever grows to the size that a library pays for itself, revisit.
- **Strip silently, no warning.** Rejected. Silent strip hides contributor mistakes and makes the stacked posture harder to debug when the upstream lint regresses. Escape-with-warning makes failures visible both to the contributor (in the browser console) and to the visitor (as visible `&lt;tag&gt;` text), which is loud but accurate.
- **Skip the render-time layer; rely on the upstream authoring lint alone.** Rejected. [ADR-014](014-yaml-content-security-posture.md) P4 commits to a stacked posture specifically because single-layer defenses regress. Removing the render-time layer means a `--no-verify` commit or a lint bug ships unescaped `<script>` to every visitor.
- **Sanitize inside `renderRichParagraphs` rather than a new module.** Rejected. Extraction into `site/assets/sanitizer.mjs` makes the transform directly testable under `node --test` without touching the DOM-bound `app.mjs` (which has zero exports today, per [ADR-012](012-static-spa-architecture.md)'s known gap). The module boundary matches the MVP's "extract when a second caller appears" posture; the second caller here is the unit test.
- **Transform at build time in `scripts/build_persona_site_data.py`.** Rejected. [ADR-014](014-yaml-content-security-posture.md) P4 names render-time as the load-bearing layer for the site, and transforming at build time leaves the gitignored JSON artifact as a surface that may be consumed by future downstream tooling expecting raw prose. Keeping the builder as pass-through preserves the "one artifact, one shape, one contract" property of [ADR-011](011-persona-site-data-schema-contract.md).
- **Decide the markdown authoring subset in this ADR.** Rejected. The subset is a YAML source contract that affects the table generator, third-party redistribution, and any future export surface — not a site-renderer-only concern. ADR-017 owns it.
- **Expand the allowlist when a future content need surfaces (e.g., add `<code>`, `<br>`, `<ul>`).** Rejected as a routine code change. Any expansion of `ALLOWED_TAGS` erodes the bounded-emission property in D3a, which is the load-bearing safety claim of this ADR. Allowlist expansion is treated as a new ADR-scope question — coordinated with ADR-017 (input-grammar change), the schema-uplift sub-deliverable, and the table generator's pass-through behavior — rather than a per-PR judgment call. The forcing function is mechanical: the meta-test in D3b fails until a fixture exists, and a fixture lands only when the expansion has been justified somewhere durable. "Just one more tag" is the failure mode this ADR is shaped to prevent.

## Consequences

**Positive**

- The known XSS-adjacent path at `app.mjs:72` and `app.mjs:75` is closed. `renderRichParagraphs` no longer writes raw prose into `innerHTML`; every paragraph routes through `renderProse`.
- The render-time allowlist is small enough to hand-roll, keeping [ADR-012](012-static-spa-architecture.md)'s zero-dep renderer posture intact.
- `sanitizer.mjs` is testable without a DOM, closing the prose-path portion of the `NIT-07` untested-helper gap ([issue #224](https://github.com/cosai-oasis/secure-ai-tooling/issues/224)).
- The render-time layer remains effective even if the upstream ADR-017 lint regresses: out-of-subset markup escapes loudly rather than silently shipping.
- Every render-time rule is machine-enforced. No contributor-facing prose carries the contract alone.

**Negative**

- The render-time allowlist must stay in sync with ADR-017's authoring subset. If ADR-017 expands the subset, `renderProse` must expand the allowlist; if ADR-017 narrows it, the renderer's allowlist can stay broader (defense-in-depth) but should be reviewed for dead branches. The two ADRs are coupled; cross-linking in both directions is required.
- The sanitizer is hand-rolled, which means this repo owns a small XSS-relevant transform. A library would defer that responsibility; the trade is explicit here. The hand-rolled choice is defensible *only* under the two constraints in D3a–D3b: a bounded emission surface (hard-coded allowlist literal, renderer-constructed attribute values) and structural test enforcement (per-tag fixtures, allowlist–fixture meta-test, attack-corpus fixture). Without both, the choice would not survive review. The maintainer's commitment to enforce the test discipline through CI — sanitizer PRs without matching fixture updates fail — is the load-bearing assumption of this ADR.
- Escape-with-warning surfaces `&lt;` / `&gt;` to visitors on a subset violation. This is louder than a silent strip, which is the intent — but a visitor who sees escaped markup should read it as "the site is diagnosing a contributor issue," not "the site is broken." Docs should note this.
- Machine-enforcement of `rel="noopener noreferrer" target="_blank"` means authors cannot opt out of new-tab opening for specific links. If a future UX argument wants same-tab navigation for some outbound links, that is an ADR revisit, not a per-link flag.

**Follow-up**

- **Conformance sweep — sanitizer module.** Implement `site/assets/sanitizer.mjs` with `renderProse(input)`. Hand-rolled tokenizer for the ADR-017 productions; escape-with-warning for disallowed markup; restrict URL schemes to `https:`; always emit `rel="noopener noreferrer" target="_blank"` on `<a>`. Update `renderRichParagraphs` call sites at `app.mjs:72` and `app.mjs:75`.
- **Conformance sweep — unit tests.** New `site/tests/sanitizer.test.mjs` under `node --test`. Coverage: each accepted production renders to the expected HTML; each rejected form escapes correctly; `https:` pass / `http:` / `javascript:` / `data:` / relative URL all rejected; `<script>` / `<img onerror>` / `<a href="#id">` all escaped; `rel` and `target` attributes always present on accepted anchors; `console.warn` called exactly once per offending paragraph. This is a new test surface; [ADR-012](012-static-spa-architecture.md)'s zero-dep property is preserved (still `node --test`, no framework).
- **Authoring lint coverage.** Owned by **ADR-017**. The pre-commit hook that enforces the markdown subset upstream — and the wrapper at `scripts/hooks/precommit/validate_yaml_prose_subset.py` — are ADR-017's deliverables. ADR-015 cites them as the upstream layer of the stacked posture but does not re-decide them.
- **YAML migration.** Owned by ADR-017 (subset conformance) and ADR-016 (sentinel conversion). ADR-015's render-time layer becomes effective once subset-compliant prose is reaching it; before that point, `renderProse` will surface escapes for any out-of-subset markup that survives in the YAML.
- **Regenerate tables.** Once ADR-017's subset migration completes, regenerate `risk-map/tables/*.md`. The `collapse_column` code is unchanged; the output improves by virtue of subset-compliant input. This is a downstream consequence of ADR-017, cited here only to note that the render-time layer does not affect table generation.
- **Docs.** A short author-facing section under `risk-map/docs/` explaining the subset belongs with ADR-017. ADR-015's render-time behavior is contributor-internal and does not require author documentation beyond the test suite.
- **If a future renderer surface consumes the same YAML** (for example, a PDF export or a second site), it either (a) applies `renderProse` at its own render boundary or (b) authors its own boundary-appropriate transform. The ADR-017 authoring lint guarantees the input is subset-compliant; the render-side transform is a per-surface choice.
- **Revisit trigger — native `Element.setHTML` Sanitizer API reaches Baseline.** As of this ADR, the native HTML Sanitizer API (`Element.setHTML(...)` with a sanitizer config) is **not** Baseline: Firefox 148 shipped it (February 2026), Chrome ships it behind a flag, and Safari has no public commitment. It does not displace today's hand-rolled choice — a renderer that depends on it would degrade silently on Safari. When `Element.setHTML` reaches Baseline (i.e., Safari ships it and removes the cross-browser gap), this ADR is the revisit point: the native API replaces the hand-rolled emitter, the bounded-emission property becomes a browser-enforced invariant rather than a hand-rolled one, and ADR-015 may be superseded by a small follow-on ADR. This entry is **informational**; no issue is filed today, and no work is scheduled until the trigger fires. Tracking the trigger is the maintainer's responsibility, not a CI concern.

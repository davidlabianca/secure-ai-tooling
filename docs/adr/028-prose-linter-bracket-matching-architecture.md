# ADR-028: Prose-linter emphasis enforcement via bracket-matching depth pass over a Token-shape contract

**Status:** Accepted
**Date:** 2026-05-27 (Draft); 2026-05-28 (Accepted)
**Authors:** Architect agent, with maintainer review

---

## Context

[ADR-017](017-yaml-prose-authoring-subset.md) D1 admits one nesting level for `**bold**`, `*italic*`, and `_italic_`; nesting another same-family emphasis inside is rejected. D5 commits to a single shared tokenizer at `scripts/hooks/precommit/_prose_tokens.py` consumed by both `validate-yaml-prose-subset` (ADR-017) and `validate_prose_references.py` ([ADR-016](016-reference-strategy.md) D6). The grammar lives in ADR-017; the enforcement mechanism for the "one nesting level" rule does not.

The mechanism implemented on the archive branch split the emphasis-shape decision across two layers. The tokenizer's non-greedy bold and italic regexes produce delimiter-bounded spans whose interior whitespace edges carry the structural signal — `**foo **` retains a trailing space because the regex closed at what the author intended as an inner open. The linter then runs a second set of regex constants against each emphasis token's `value` to recover that signal. The shape decision is encoded as a side effect at one layer and decoded at the other, with the load-bearing knowledge ("whitespace-at-edge means greedy early-close") implicit in both. The two layers must stay in sync, and a reader of either alone cannot tell that the synchronization is load-bearing.

This split is the architectural problem ADR-028 addresses. Attempts to restructure the linter without first raising the contract failed for three reasons that are properties of the design surface, not of any specific implementation. First, a token stream that carries no structural open/close events cannot support a stack-based or counter-based walk: any algorithm that treats every emphasis token as a "push" degenerates to faux-depth, because sibling complete-emphasis spans separated by plain text (`**hello** world **goodbye**`) become indistinguishable from one emphasis nested inside another. Second, the whitespace-at-edge heuristic can be relocated freely — from a linter-side regex constant to a derived method, an inline string check, a comment, anywhere — without ever being eliminated; the load-bearing knowledge that "trailing space inside the delimiter means greedy early-close" still has to live somewhere, and whichever layer hosts it carries the synchronization burden. Third, any shape information that is meaningful only for some token kinds produces an asymmetric API (`str | None` returns, value-passthrough fallbacks, branching on kind before reading shape), which forces every consumer to handle a "doesn't apply" case at every read site. All three failure modes resolve to the same root cause: the `Token` contract under-specifies what consumers may assume about shape, so each refactor has to re-establish invariants that should already exist on the token. Without raising the contract, the restructure surface stays load-bearing.

ADR-028 specifies the contract this surface needs. The `Token` NamedTuple structure, the `TokenKind` enumeration, the invariants every token stream from `tokenize()` satisfies, and the consumer surface every reader accesses are documented here as ADR-grade architecture rather than implementation detail; emphasis-shape classification is part of the contract, carried on the token rather than reconstructed downstream. The full planning inventory — alternatives, consumer audit, fixture corpus, cross-ADR alignment matrix, shape-determination rules, and 21 locked decision points — was produced at `working-plans/028-prose-linter-planning-inventory.md` (local, untracked) and is the analytical input.

Line references in this ADR are GitHub permalinks pinned against `upstream/main` at commit `7320136`.

## Decision

The tokenizer emits `Token` instances carrying a `shape` field classified at emission time; the prose-subset linter walks tokens once with a depth counter and reads `shape` directly. The decision has seven components.

### D1. Token contract

The `Token` NamedTuple at `scripts/hooks/precommit/_prose_tokens.py` is the durable contract between the tokenizer and every consumer. Fields, in declaration order:

| Field | Type | Semantics |
|---|---|---|
| `kind` | `TokenKind` | Token classification per D2. |
| `value` | `str` | Exact substring from the input the token covers. For INVALID_* kinds, the offending substring. |
| `shape` | `Literal["complete", "open", "close", "neutral"]` | Emphasis classification per D3. `"neutral"` for every non-emphasis token. Default `"neutral"`. |

`shape` is declared as the **third** field with a default of `"neutral"`. Two-positional construction (`Token(TokenKind.X, value)`) continues to compile and yields a token with `shape="neutral"`; emission sites that classify emphasis pass `shape=` as a keyword argument.

Equality is structural NamedTuple equality. Two tokens with identical `kind` and `value` but different `shape` values are not equal. Test code that constructs tokens manually for comparison against `tokenize()` output must either supply the matching `shape` or compare via the fixture-format projection that drops `shape` (see D4 and the fixture migration in Follow-up).

The NamedTuple structure, defaults, and equality semantics are part of the ADR-grade specification rather than implementation detail. Future field additions (e.g., a hypothetical `source_line`) require a new ADR or an amendment here; new `shape` values likewise.

### D2. TokenKind enumeration

The tokenizer emits exactly the following sixteen kinds. The accept/reject column matches `_REJECTED_KINDS` in [`validate_yaml_prose_subset.py:49-62`](https://github.com/cosai-oasis/secure-ai-tooling/blob/7320136/scripts/hooks/precommit/validate_yaml_prose_subset.py#L49-L62) with one carve-out documented after the table.

| TokenKind | Defining regex / character class | Accept / Reject | Semantic meaning | Defining ADR |
|---|---|---|---|---|
| `BOLD` | `\*\*(.+?)\*\*` (`re.DOTALL`) | Accept | One nesting level bold; non-greedy close. Italic inside permitted; nested `**bold**` rejected by D5. | [ADR-017](017-yaml-prose-authoring-subset.md) D1 |
| `ITALIC` | `\*(.+?)\*` or whitespace-flanked `_(.+?)_` | Accept | One nesting level italic. Two delimiters so authors can italicize text containing the other delimiter. | [ADR-017](017-yaml-prose-authoring-subset.md) D1 |
| `SENTINEL_INTRA` | inner: `(risk\|control\|component\|persona)[A-Z]\w*` | Accept | Intra-document reference sentinel. | [ADR-016](016-reference-strategy.md) D2 |
| `SENTINEL_REF` | inner: `ref:[A-Za-z0-9_.\-]+` | Accept | External-reference sentinel. | [ADR-016](016-reference-strategy.md) D2 |
| `TEXT` | catch-all run accumulator | Accept | Plain prose. | [ADR-017](017-yaml-prose-authoring-subset.md) D1 |
| `INVALID_HTML` | `<[A-Za-z/][^>]*>` | Reject | Any HTML tag. | [ADR-017](017-yaml-prose-authoring-subset.md) D2 |
| `INVALID_URL` | scheme-with-authority, opaque-data scheme, or markdown link | Reject | Inline URL in any form. | [ADR-017](017-yaml-prose-authoring-subset.md) D2 / D4 rule 2 |
| `INVALID_HEADING` | `#+[^\n]*` at line start | Reject | Markdown heading. | [ADR-017](017-yaml-prose-authoring-subset.md) D2 |
| `INVALID_LIST` | `-\s`, `\*\s`, `\d+\.\s` at column 0 | Reject | Markdown list marker at column 0. | [ADR-017](017-yaml-prose-authoring-subset.md) D2 |
| `INVALID_CODE` | ```` ```...``` ```` (`re.DOTALL`) or `` `[^`]+` `` | Reject | Fenced or inline code. | [ADR-017](017-yaml-prose-authoring-subset.md) D2 |
| `INVALID_IMAGE` | `!\[[^\]]*\]\([^)]*\)` | Reject | Markdown image. | [ADR-017](017-yaml-prose-authoring-subset.md) D2 |
| `INVALID_BLOCKQUOTE` | `>[^\n]*` at line start | Reject | Markdown blockquote. | [ADR-017](017-yaml-prose-authoring-subset.md) D2 |
| `INVALID_TABLE` | `\|[^\n]*(?:\n\|$)` at line start | Reject | Markdown pipe-table row. | [ADR-017](017-yaml-prose-authoring-subset.md) D2 |
| `INVALID_FOLDED_BULLET` | `\s+\-\s[^\n]*(?:\n\|$)` at line start | Reject | Folded-bullet drift — leading-whitespace `- ` line. | [ADR-020](020-controls-schema.md) follow-up (citation defect — see D7) |
| `INVALID_CAMELCASE_ID` | `(risk\|control\|component\|persona)[A-Z]\w*` | Reject (**delegated**) | Bare entity-prefix camelCase outside a sentinel. | [ADR-017](017-yaml-prose-authoring-subset.md) D4 rule 5 / [ADR-016](016-reference-strategy.md) D6 |
| `INVALID_SENTINEL` | `\{\{ ... \}\}` with brace-depth scan, inner fails both sentinel forms | Reject | Structurally well-formed `{{ }}` with content matching neither sentinel grammar. | [ADR-016](016-reference-strategy.md) D2 |

**Delegation carve-out.** `INVALID_CAMELCASE_ID` is the only rejecting kind that the prose-subset linter intentionally excludes from `_REJECTED_KINDS`. Ownership lives in `validate_prose_references.py` per ADR-017 D4 rule 5 and ADR-016 D6. A consumer that iterates `if kind.name.startswith("INVALID")` to count rejections will diverge from the prose-subset linter's behavior unless it applies the same exclusion. The carve-out is load-bearing for both consumers and any third-party reader; it is part of the contract.

The enumeration is closed for ADR-028. Adding a new kind requires an amendment here.

### D3. Tokenizer emission invariants

Every token stream produced by `tokenize()` satisfies four invariants.

1. **Partition-of-input.** `"".join(t.value for t in tokenize(text)) == text` for every input. Every character lands in exactly one token's `value`. Asserted in the test corpus at [`test_prose_tokens.py:1043-1072`](https://github.com/cosai-oasis/secure-ai-tooling/blob/7320136/scripts/hooks/tests/test_prose_tokens.py#L1043-L1072) (`TestMixedRuns.test_tokens_cover_full_input`).
2. **Rule-precedence ordering.** The sixteen rules apply per-character in the precedence order documented at [`_prose_tokens.py:11-27`](https://github.com/cosai-oasis/secure-ai-tooling/blob/7320136/scripts/hooks/precommit/_prose_tokens.py#L11-L27). Higher-priority match wins; ties do not exist because each rule anchors on a distinct character or substring. Line-anchored rules (headings, list markers, blockquotes, pipe-tables, folded-bullet drift) fire only at index 0 or immediately after `\n` per `at_line_start()`.
3. **Greedy / non-greedy specification.** Bold non-greedy on close; italic non-greedy on close — asterisk italic is intraword-permissive, underscore italic additionally requires whitespace-or-boundary flanking per ADR-017 D1, so an intraword `\S_\S` underscore does not qualify as a delimiter and the run consumes as TEXT; URL regexes greedy with bracketed exclusion `[^\s{]+` so a URL adjacent to a `{{` sentinel terminates at the brace boundary; fenced code non-greedy across newlines with `re.DOTALL`; sentinel scan brace-depth-aware so `{{id{{ref:x}}}}` consumes as one `INVALID_SENTINEL` token. Unclosed `{{` returns `None` from `_match_sentinel`; the caller emits the remainder as `TEXT`.
4. **Shape classification at emission.** Every emphasis token (`BOLD`, `ITALIC`) carries a `shape` value classified at emission time from leading/trailing whitespace in the matched span's interior. Every non-emphasis token carries `shape="neutral"`. The classification rules per delimiter (`**`, `*`, `_`):

| Matched span shape | `shape` value | Rationale |
|---|---|---|
| `**foo**` — neither edge whitespace in interior | `"complete"` | Well-formed emphasis. |
| `**foo bar**` — internal whitespace only | `"complete"` | Only **edge** whitespace is the signal. |
| `**foo **` — trailing whitespace before close | `"open"` | Greedy non-greedy closed on what the author intended as an inner open. |
| `** bar**` — leading whitespace after open | `"close"` | Mirror — trailing half of the same early-close pattern. |
| `** foo **` — both edges whitespace | `"open"` | Convention: leading-whitespace test fires first; consistent with the wrapped-sentinel case `**\n{{ref:x}}\n**` rendering as `"open"`. |
| `**\n**` — interior is a single `\n` | `"open"` | `\n` counts as `isspace()`; both-edges-whitespace falls under the `"open"` convention. |

Edge cases the tokenizer does not emit as emphasis at all carry `shape="neutral"` like any other TEXT: `**` alone; `**foo` unclosed; `**` paired with no inner character; `****` consumed as two TEXT runs because `(.+?)` requires at least one inner character; `__bold__` consumed as TEXT per ADR-017 D1's asterisk-only-bold stance; and **intraword underscore runs like `home_bar and foo_baz` consumed as TEXT** because the underscores fail the whitespace-flanking requirement — a snake_case identifier pair is not an italic span.

The classification is implemented as a private helper `_classify_emphasis_shape(span, delim) -> str` in `_prose_tokens.py`, invoked from the three emphasis emission sites at [`_prose_tokens.py:421-440`](https://github.com/cosai-oasis/secure-ai-tooling/blob/7320136/scripts/hooks/precommit/_prose_tokens.py#L421-L440) (one per delimiter family). The helper is a pure function over the matched span; it takes no global state. Emit-site call shape: `emit(TokenKind.BOLD, m.group(), shape=_classify_emphasis_shape(m.group(), "**"))`.

The shape decision is encapsulated in the tokenizer. The linter never reads whitespace edges directly; it reads `token.shape`.

### D4. Consumer contract

The public surface of `_prose_tokens.py` is exactly three names: `Token`, `TokenKind`, and `tokenize()`. The leading underscore in the module name marks the module as one of the precommit-sibling internals coordinated by ADR-017 D5 and ADR-016 D6; it does **not** mark every name in the module as private. Internal helpers (`_match_sentinel`, `_classify_emphasis_shape`, `emit`, `flush_text`, `pending_text_start`, the `_RE_*` regex constants) are not part of the contract and may be reorganized without an ADR amendment.

Stable consumer API:

- **Field access** on tokens is stable: `token.kind`, `token.value`, `token.shape`.
- **Iteration** is stable: `for token in tokens:` and indexed access (`tokens[N]`) for positional reads.
- **Positional unpacking** is **not** stable. No `kind, value = token` destructuring appears in production code or tests; future contributors must not introduce it. Tuple positionality is therefore reserved for forward-compatible field additions (D1's `shape` is the first such addition).
- **Construction** is via `tokenize()`. Test code may construct `Token(...)` via keyword arguments for assertion-side comparisons; production code outside `_prose_tokens.py` itself must not construct `Token` instances directly.

The known production consumers are three: `validate_yaml_prose_subset.py` (the prose-subset linter; reads `kind`, `value`, and `shape` per D1); `validate_prose_references.py` (the references linter per ADR-016 D6; reads `kind` and `value` only); and `_sentinel_expansion.py` (the shared sentinel expander per ADR-016 D5; reads `kind` and `value` only). The two latter consumers are unaffected by the `shape` field's introduction because they never read it; under D1's default-`"neutral"` posture, they see tokens whose new field carries the no-op value.

The test corpus's contract is the `_tokens_to_dicts` projection at [`test_prose_tokens.py:203`](https://github.com/cosai-oasis/secure-ai-tooling/blob/7320136/scripts/hooks/tests/test_prose_tokens.py#L203), currently `{"kind": t.kind.name, "value": t.value}`. The projection drops `shape` and remains stable. Fixtures continue to assert two-field equality. The fixture migration (Follow-up below) is **additive**: existing emphasis-bearing fixtures stay byte-identical and implicitly assert `shape="complete"` by virtue of the tokenizer emitting that value; new fixtures cover `"open"`, `"close"`, and other shape cases without disturbing the existing corpus.

### D5. Linter algorithm — depth-counter bracket-matching pass

The prose-subset linter's emphasis-rejection logic in `validate_yaml_prose_subset.py` is a single pass over `field.tokens` with an integer depth counter and two one-line predicates. The current helpers `_detect_nested_emphasis_indices` and `_is_emphasis_wrapped_sentinel`, along with the three `_RE_*_EARLY_CLOSE` and three `_RE_*_WRAPPED_SENTINEL` regex constants, are deleted.

Algorithm (textbook bracket-matching shape):

```text
depth = 0
for token in field.tokens:
    if token.kind in (BOLD, ITALIC):
        if token.shape == "open":
            if depth > 0:                 # already inside emphasis of same family
                emit_diagnostic(...)
            depth += 1
        elif token.shape == "close":
            if depth > 0:                 # close of an unmatched open -> nested emphasis
                emit_diagnostic(...)
            depth = max(0, depth - 1)     # floor: a standalone close-shape (e.g. " ** bar**") would underflow
        elif token.shape == "complete":
            if depth > 0:                 # nested complete-emphasis inside open emphasis
                emit_diagnostic(...)
            # complete = open + close, net depth change 0
        # shape == "neutral" on emphasis kinds is not emitted (see D3)
        if _is_emphasis_wrapped_sentinel(token):
            emit_diagnostic(...)
```

The two predicates:

- **Nested-emphasis predicate.** Fires when an emphasis token is encountered with `depth > 0` and a same-family emphasis open is unmatched. Implemented as the `depth > 0` check inline in the walk above, applied on the `open`, `complete`, **and** `close` branches; the `close` branch checks `depth > 0` *before* decrementing, and is the attribution point for the canonical split-token nested case (`**foo **nested** bar**` tokenizes as `[open, text, close]`, and the `close` token at `depth == 1` is where the single diagnostic lands). The kind comparison is via `token.kind` directly (a bare counter suffices; a kind-stack is not needed for the current ADR-017 D1 rule, which detects any nesting regardless of delimiter family).
- **Emphasis-wrapped-sentinel predicate.** Fires when an emphasis token's interior (its `value` minus the delimiter pair) `.strip()`s to a string that fullmatches either of the tokenizer's two internal sentinel-inner regexes — `_RE_SENTINEL_INTRA_INNER` or `_RE_SENTINEL_REF_INNER` (defined in `_prose_tokens.py`). The prose-subset linter imports these `_RE_*` constants directly: a deliberate cross-module coupling permitted by D4 (the `_RE_*` constants are internal and reorganizable) and flagged with an inline coupling comment at the import site. They are **not** shared with the references linter, which resolves sentinels structurally via `_resolve_intra_sentinel` against the id-index rather than by inner-regex match. Independent of the depth state.

Both predicates are one-line expressions over `token.shape` (or `token.kind` and `token.value`) and the depth state. There are no regex constants in the linter for shape detection. The whitespace-adjacency heuristic that previously lived in `_RE_*_EARLY_CLOSE` has been moved into the tokenizer's `_classify_emphasis_shape` per D3; the linter cannot see it and cannot drift from it.

The walk handles the false-positive patterns a naive stack would faux-depth on. `**hello** world **goodbye**` tokenizes as `[BOLD shape="complete", TEXT shape="neutral", BOLD shape="complete"]` and walks depth `0 → 0 → 0 → 0`; no diagnostic. `**hello** world {{ref:x}}` tokenizes as `[BOLD shape="complete", TEXT, SENTINEL_REF]` and the sentinel is at `depth == 0`; no diagnostic. The prospective D6-of-ADR-017 rules ("no sentinel inside any emphasis", "no link text containing emphasis") would express as `depth > 0 and token is sentinel/link` — predicates with a real depth value, not a faux one.

Reason strings (`_REASON_NESTED_EMPHASIS`, `_REASON_EMPHASIS_WRAPPED_SENTINEL`) and the diagnostic format are preserved per D6.

**Addendum (2026-05-29) — erratum.** The original D5 draft omitted the `close`-branch emit and the depth floor from the pseudocode, leaving the pseudocode inconsistent with the Nested-emphasis predicate prose (which has always covered every emphasis token, including `close`-shape) and with planning-inventory §5.2's load-bearing-case analysis of `**foo **nested** bar**` (tokens `[open, text, close]`, where the `close` token at `depth == 1` is the only attribution point). The pseudocode now (1) emits the nested-emphasis diagnostic in the `close` branch when `depth > 0`, checked before the decrement, and (2) floors the decrement with `max(0, depth - 1)` because a standalone leading-space bold classifies as `shape="close"` and would otherwise drive `depth` to `-1` (the prior `# depth-floor enforced by tokenizer invariants` comment was false). This is an erratum reconciling the pseudocode with D5's own governing predicate prose; it is **not** a new decision — §5.2 flagged "clarify the predicate" but §8 never created a corresponding locked D-Open decision, so no §8 lock changes. Status remains **Accepted**.

**Addendum (2026-05-29) — second erratum.** The original D5 Emphasis-wrapped-sentinel predicate bullet named a single unified `SENTINEL_INNER_RE` "defined once in `_prose_tokens.py` and shared with the references linter." Both claims were false against the as-built code. No `SENTINEL_INNER_RE` exists; the tokenizer carries two internal constants, `_RE_SENTINEL_INTRA_INNER` and `_RE_SENTINEL_REF_INNER` (`_prose_tokens.py:174-175`), which the prose-subset linter imports directly with an inline coupling comment (`validate_yaml_prose_subset.py:39-45`). That direct import of internal `_RE_*` constants is exactly the coupling D4 sanctions (the `_RE_*` constants are internal and reorganizable), and a single public `SENTINEL_INNER_RE` would have been a 4th public name contradicting D4's "exactly three names" surface. The constants are **not** shared with the references linter, which resolves sentinels structurally via `_resolve_intra_sentinel` (prefix + id-index, dispatched on `token.kind`) rather than by inner-regex match. The predicate bullet above is corrected to describe this reality. This is a doc-accuracy erratum only: the implementation already matches the corrected text, no code changes, no §8 lock changes, and Status remains **Accepted**.

**Addendum (2026-05-29) — third erratum.** The "are deleted" framing in the D5 prose above (the named helpers `_detect_nested_emphasis_indices` and `_is_emphasis_wrapped_sentinel`, plus the three `_RE_*_EARLY_CLOSE` and three `_RE_*_WRAPPED_SENTINEL` constants) and the matching "linter shrinks" bullet in Consequences describe a delete-and-replace diff that did not occur on this branch. This is a fresh branch off clean `upstream/main = 7320136` per D-Open-11; none of those symbols ever existed on this base. The prior emphasis-rejection layer they describe lived only on the abandoned archive branch `feature/353-c4-followons`. The as-built is therefore a greenfield addition of the depth-walk emphasis enforcement, not a reduction: the "are deleted" / "linter shrinks" language records the logical supersession of that archived design, not a diff against this branch's base. The two predicates are also independent and may both fire on a single emphasis token — a `close`-shape token at `depth > 0` whose stripped interior matches a sentinel-inner regex emits **both** the `nested emphasis` and the `emphasis-wrapped sentinel` diagnostics (e.g. `**foo **{{ref:x}}** bar**`); the wrapped-sentinel predicate runs unconditionally on every emphasis token while the nested-emphasis predicate gates on depth, so the two are orthogonal and the double-emit is intended. This is a doc-accuracy erratum only: no code change, no §8 lock change, and Status remains **Accepted**.

### D6. Diagnostic conformance

ADR-017 D4's diagnostic format spec is preserved byte-for-byte:

```text
validate-yaml-prose-subset: <file>:<entry-id>:<field>[<index>]: <reason> at <token-snippet>
```

The two reason strings — `"nested emphasis"` and `"emphasis-wrapped sentinel"` — are unchanged. The nested-index `<field>[<outer>][<inner>]` second-segment format introduced by PR #286 (per ADR-017 D4 line 81's "Addendum" amendment) is unchanged. The token-snippet is the same `token.value` substring the existing implementation emits.

`TestDiagnosticFormat`, the live-corpus baseline, and third-party tooling that scrapes the linter's stderr output continue to work without modification.

### D7. Cross-ADR alignment

**In scope for the ADR-028 commit:**

- **ADR-017 D5 amendment.** One additive paragraph at the end of D5 stating that the Token contract (NamedTuple structure including emphasis-shape field, TokenKind enumeration, emission invariants, consumer surface) is formally specified in ADR-028 D1-D4. Does not amend any existing rule; only adds the pointer.
- **ADR-017 D1 amendment.** One forward pointer at the end of D1 indicating that the canonical mechanism for enforcing the "no nested same-family emphasis" and "no emphasis-wrapped sentinel" rules is the depth-counter pass specified in ADR-028 D5.

**One-way cross-references this ADR makes:**

- [ADR-005](005-pre-commit-framework.md): `validate-yaml-prose-subset` is one of the local hooks declared under the pre-commit framework; ADR-005's hook-orchestration shape is preserved.
- [ADR-012](012-static-spa-architecture.md): the zero-dep posture for the SPA's runtime path is the prior art that motivated ADR-015's hand-rolled sanitizer and ADR-017's hand-rolled tokenizer. ADR-028 keeps the hand-rolled approach; no library dependency is introduced.
- [ADR-015](015-site-content-sanitization-invariants.md) D3: the bounded-emission property and the hand-rolled-sanitizer-with-grammar-sync rationale apply symmetrically to the lint-side tokenizer. Neither the emitted token kinds nor the partition-of-input invariant changes, so the site/lint grammar parity is preserved.
- [ADR-016](016-reference-strategy.md) D5 and D6: `validate_prose_references.py` and `_sentinel_expansion.py` are the two consumers of the shared tokenizer besides the prose-subset linter itself. Per D4 above, neither reads `shape`; the contract raise is transparent to them.
- [ADR-025](025-testing-strategy.md) D2 and D10: the testing chain (Testing → Code-Reviewer → SWE → Code-Reviewer) authors failing tests before implementation; the `_classify_emphasis_shape` helper and the depth-counter walk both flow through the chain. D10's wire-up requirement is satisfied by including at least one test that calls `tokenize()` and inspects `shape` on the emitted tokens (rather than only testing the classifier helper in isolation).

**Deferred to future maintenance edits:**

- **ADR-016 D6 amendment to mention the `shape` field's existence.** Not in scope. `validate_prose_references.py` does not read `shape`; the courtesy amendment would add scope without value. A future amendment lands when the field becomes load-bearing for the references linter.
- **ADR-020 D4 / folded-bullet citation defect.** The `INVALID_FOLDED_BULLET` kind is documented in `_prose_tokens.py` and `_REASONS` strings as belonging to ADR-020 D4, but D4 is the prose-shape decision; the folded-bullet rule's actual home is ADR-020's follow-up section. This is a pre-existing documentation defect, not load-bearing here. Cleanup lands in a separate one-line commit.

## Alternatives Considered

- **Status quo — regex-driven shape detection in the linter.** Three `_RE_*_EARLY_CLOSE` constants in `validate_yaml_prose_subset.py` extract the whitespace-edge signal from token values that the greedy non-greedy bold/italic regexes encoded as side effects. Rejected because the shape decision is split across two layers, the regex constants encode an implicit channel from the tokenizer to the linter, and three accreted commits (`a71ae47`, `817e00d`, `5e72a2a`) on the archived `feature/353-c4-followons` branch motivated the restructure in the first place.
- **Path B — derived methods `Token.delim()` and `Token.interior()`, shape inference at the linter via `interior().endswith(whitespace)`.** Stashed at `stash@{0}` on `.worktree/353-c4-followons`. Rejected on four grounds: (1) faux-depth — the kind-stack had no pop conditions, so `**hello** world **goodbye**` would false-positive as depth-2 nested; (2) the whitespace heuristic was renamed-not-removed — moved from a regex constant to a method-then-string-operation chain with the same load-bearing knowledge requirement; (3) D6 forward-compat predicates degenerated to "is there any prior emphasis in this string"; (4) asymmetric API — `delim()` returned `str | None` and `interior()` returned `value` unchanged for non-emphasis kinds, forcing every consumer to handle two different "doesn't apply" fallbacks.
- **Open/close event tokens — emit `BOLD_OPEN` and `BOLD_CLOSE` as distinct kinds.** Rejected because it breaks the partition-of-input invariant: an event token has no `value` substring of its own, or the `value` must be split across multiple tokens (the open's `**` and the close's `**`), neither of which the consumer audit and existing fixture format tolerate. BOLD and ITALIC remain single tokens covering the delimiter-bounded span; shape is a field on the token, not a kind.
- **Extend the test projection to include `shape` and annotate every emphasis-bearing fixture.** Rejected. The fixture corpus has 56 pairs; the migration would touch ~150 `shape` keys across files, most of them defaulting to `"neutral"` with low signal density. The existing five emphasis-bearing fixtures already implicitly lock in `shape="complete"` (because the tokenizer emits that value and the projection drops it).
- **Suppress the projection extension and assert `shape` only via per-test attribute checks, never via fixtures.** Rejected. Loses the auditability of fixture-driven shape assertions for new `"open"` / `"close"` cases.
- **Use a markdown library (`markdown-it-py`, `commonmark`).** Rejected per ADR-017 D5 line 80 and ADR-015 D3's zero-dep posture for the matching sanitizer. The grammar is small enough to hand-roll; a library brings a configuration surface larger than the replacement code.
- **Kind-stack rather than bare depth counter in the linter.** Reasonable for prospective D6-of-ADR-017 rules that would need to know the enclosing kind (e.g., "no link text containing emphasis"), but the current rule set — ADR-017 D1's "no nested same-family emphasis" plus the wrapped-sentinel check — needs only a depth value; kind comparison happens via `token.kind` directly on the emphasis token under inspection. A kind-stack adds zero current capability and complicates the algorithm's textbook shape. If a future rule needs the enclosing-kind dimension, the stack arrives then.

## Consequences

**Positive**

- **One shape decision, encapsulated in the tokenizer.** The whitespace-adjacency heuristic exists in exactly one place — `_classify_emphasis_shape` — and runs on the matched span before the token is appended to the stream. The linter sees a four-value enum and dispatches on it; future contributors do not need to know that whitespace-at-edge is load-bearing to read the linter.
- **Faux-depth false positives are eliminated by construction.** `**hello** world **goodbye**` tokenizes as two `shape="complete"` BOLDs, walks depth `0 → 0`, and emits no diagnostic. Prospective D6-of-ADR-017 rules can use `depth > 0` with confidence that the depth value is structurally meaningful.
- **The Token API is symmetric.** Every token carries `shape: Literal[…]`; there is no `None` fallback to branch on. Consumers that need shape read it; consumers that do not read it (`validate_prose_references.py`, `_sentinel_expansion.py`) are unaffected by its presence.
- **The contract is ADR-grade.** The Token NamedTuple, TokenKind enumeration, tokenizer emission invariants, and consumer surface are specified here. Future refactors of the tokenizer-internal helpers (`_match_sentinel`, `_classify_emphasis_shape`, the `_RE_*` constants) need no ADR amendment; surface changes (new fields, new kinds, new emission invariants) do.
- **The linter shrinks.** Three `_RE_*_EARLY_CLOSE` constants, three `_RE_*_WRAPPED_SENTINEL` constants, `_detect_nested_emphasis_indices`, and `_is_emphasis_wrapped_sentinel` are deleted from `validate_yaml_prose_subset.py`. The replacement is a single-pass walk with two one-line predicates over `token.shape` and the depth state.
- **Diagnostic format is preserved.** The existing test corpus (including `TestDiagnosticFormat` and the live-corpus baseline) and any third-party tooling that scrapes the linter's stderr output continue to work without modification.

**Negative**

- **The classifier helper is now part of the contract.** `_classify_emphasis_shape` is internal to `_prose_tokens.py` per D4, but its behavior — the both-edges-whitespace `"open"` convention, the leading-whitespace-first ordering — is observable through the `shape` field on emphasis tokens. A future change to the convention is a tokenizer change; downstream tests assert against the values it emits.
- **Two BOLD tokens with different `shape` are not structurally equal.** D1's NamedTuple equality posture means test code that constructs a token manually for comparison against `tokenize()` output must supply the correct `shape` or compare via the projection that drops `shape`. The TDD chain's reviewers carry this as a checklist item.
- **The `shape` field name is generic.** A future ADR adding (e.g.) `position` or `category` to the NamedTuple may force a rename to `emphasis_shape` for clarity. The generic name is accepted on the basis that the field's semantics are documented in D1.
- **The underscore-italic tightening (D3 invariant 3) is content-visible.** Snake_case identifier pairs like `home_bar and foo_baz` no longer tokenize as italic — a corpus-observable shift even though no new rejection is added. The corpus impact probe (Follow-up below) runs before Status flips from Draft to Accepted; if surprises surface, the rule is revisited.
- **Authors who copy prose containing `_X Y_` constructs from upstream where they were intended as italic must now flank with whitespace explicitly.** The friction is intentional; the false-positive case it eliminates is the load-bearing reason.

**Follow-up**

- **Underscore-italic corpus diff — the lockdown validation gate.** Before maintainer flips Status: Draft → Accepted, a one-off script runs both the current `_RE_ITALIC_UNDERSCORE` and the proposed whitespace-flanked variant against all four content YAMLs (`risks.yaml`, `controls.yaml`, `components.yaml`, `personas.yaml`) and emits a diff listing every prose field whose tokenization changes (e.g., `<file>:<entry-id>:<field>: was ITALIC("_X Y_"), now TEXT`). Two outcomes: diff is empty or only matches expected snake_case false positives → lock confirmed; diff includes authorially-intended italic spans → maintainer reopens the underscore decision before the ADR is Accepted. **Resolved 2026-05-28:** probe run over all 569 prose fields in the four content YAMLs reported **zero** tokenization changes (first outcome). The probe was validated as non-blind — `home_bar and foo_baz` flips ITALIC→TEXT as designed while genuine whitespace-flanked italics and `__double__` are preserved. D-Open-21 lock confirmed; Status flipped Draft → Accepted.
- **Triple-asterisk tokenizer probe.** Captures the tokenizer's output for `***foo***`, `****`, `*****foo*****`, `**foo***`, `***foo**`, and `***`. Feeds the classifier test fixtures. Runs as part of the testing agent's RED phase, parallel to the SWE implementation.
- **Live-corpus regression baseline.** Captures the current zero-diagnostic state of `validate-yaml-prose-subset` against the four content YAMLs as a `pytest.mark.live_corpus` test. Gates the post-migration regression check; the new linter must produce the same zero-diagnostic result.
- **Fixture migration — additive only.** Add 6-10 new emphasis-shape fixtures under (likely) `scripts/hooks/tests/fixtures/prose_subset/accepting/emphasis_shapes/` or equivalent, covering `shape="open"`, `shape="close"`, depth-3 nested input asserted multi-token, and italic variants per delimiter. The existing five emphasis-bearing fixtures stay byte-identical; they implicitly assert `shape="complete"` via the tokenizer's emission and the projection's drop-of-`shape`. The `_tokens_to_dicts` projection at [`test_prose_tokens.py:203`](https://github.com/cosai-oasis/secure-ai-tooling/blob/7320136/scripts/hooks/tests/test_prose_tokens.py#L203) stays at `{"kind", "value"}`; tests that need to assert `shape` use per-test attribute checks.
- **Stale corpus-size comments.** The module docstring at [`_prose_tokens.py:266`](https://github.com/cosai-oasis/secure-ai-tooling/blob/7320136/scripts/hooks/precommit/_prose_tokens.py#L266) references "42 grammar cases"; the test header at [`test_prose_tokens.py:90-97`](https://github.com/cosai-oasis/secure-ai-tooling/blob/7320136/scripts/hooks/tests/test_prose_tokens.py#L90-L97) references "55 fixture-parametrized pairs". The current corpus is 56 pairs (with the additive emphasis-shape fixtures, 62-66). Cleanup lands with the fixture migration commit.
- **Future kind additions.** Adding a new TokenKind member (e.g., for a hypothetical fourth allowed authoring token) is an amendment to D2 here, plus the corresponding ADR-017 D1 amendment. The contract is ADR-grade, so future additions surface as ADR work, not implementation drift.
- **Future shape values.** Adding a fifth `shape` value (e.g., for cross-delimiter italic-in-italic detection per ADR-017 D1 line 36's deferred case) is an amendment to D1 and D3 here. The cross-delimiter case continues to tokenize as a single ITALIC token because the outer match consumes the inner.

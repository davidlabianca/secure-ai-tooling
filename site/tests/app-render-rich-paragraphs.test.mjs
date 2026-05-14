/**
 * Tests for renderRichParagraphs in site/assets/app.mjs.
 *
 * Regression-lock for task 2.4.3 (sanitizer wiring) bundled into B2 PR #295.
 * Pre-fix, structured-item segments rendered as "[object Object]" because
 * renderRichParagraphs template-interpolated each segment directly instead
 * of routing through renderProse. These tests exercise the four branches:
 *
 *   1. Top-level string item              -> <p>renderProse(string)</p>
 *   2. Top-level object item              -> <p>renderProse(object)</p>
 *   3. Nested array, all strings (legacy) -> <div class="subsection"><p>...</p>...</div>
 *   4. Nested array, contains-object      -> single <p> joining renderProse(seg)
 *
 * Plus a regression test using the actual riskRetrievalVectorStorePoisoning
 * shape from site/generated/persona-site-data.json — the kind of structured
 * input that produced "[object Object]" without the fix.
 *
 * app.mjs reads document.querySelector("[data-app]") at module-load time, so
 * a minimal stub is installed on globalThis before the dynamic import.
 */

import test from "node:test";
import assert from "node:assert/strict";

// Minimal DOM/window/fetch shim — app.mjs touches all three during module load
// (document.querySelector for the app root, event-listener registration on
// that element, renderApp() writing innerHTML, loadSiteData() calling fetch).
// The Proxy makes every property access return either a chainable proxy or a
// noop function so we can let the entire module body execute without errors.
const elementMock = new Proxy(
  {
    addEventListener: () => {},
    querySelector: () => elementMock,
    querySelectorAll: () => [],
    closest: () => null,
    dataset: {},
    innerHTML: "",
  },
  {
    get(target, prop) {
      if (prop in target) {
        return target[prop];
      }
      // Default: any other property is a noop function returning the proxy.
      return () => elementMock;
    },
    set() {
      return true;
    },
  },
);
globalThis.document = {
  querySelector: () => elementMock,
  querySelectorAll: () => [],
};
globalThis.window = {
  addEventListener: () => {},
  matchMedia: () => ({ matches: false }),
  scrollTo: () => {},
};
// loadSiteData() fires fetch on import; return a rejected promise so the
// error path runs to completion without crashing the module.
globalThis.fetch = () => Promise.reject(new Error("fetch stubbed in node test"));

const { renderRichParagraphs } = await import("../assets/app.mjs");

test("string item renders as a single <p> via renderProse", () => {
  const out = renderRichParagraphs(["Plain sentence."]);
  assert.equal(out, '<p class="body-copy">Plain sentence.</p>');
});

test("string item uses caller-supplied className", () => {
  const out = renderRichParagraphs(["Body."], "lead-copy");
  assert.equal(out, '<p class="lead-copy">Body.</p>');
});

test("string item with markdown bold renders <strong> (ADR-017 grammar at call site)", () => {
  // Side effect of wiring renderProse: ADR-017 markdown grammar now renders
  // at the call site (was previously inert because raw template interpolation
  // passed asterisks through as literal text).
  const out = renderRichParagraphs(["Risk: **Critical**"]);
  assert.equal(out, '<p class="body-copy">Risk: <strong>Critical</strong></p>');
});

test("top-level object item renders as <p><a>…</a></p>", () => {
  const item = {
    type: "link",
    title: "Sample Citation",
    url: "https://example.com/paper",
  };
  const out = renderRichParagraphs([item]);
  assert.equal(
    out,
    '<p class="body-copy"><a href="https://example.com/paper" rel="noopener noreferrer" target="_blank">Sample Citation</a></p>',
  );
});

test("nested array of all strings renders as subsection-of-<p> (legacy shape)", () => {
  const out = renderRichParagraphs([["First.", "Second.", "Third."]]);
  assert.equal(
    out,
    '<div class="subsection"><p class="body-copy">First.</p><p class="body-copy">Second.</p><p class="body-copy">Third.</p></div>',
  );
});

test("nested array containing an object renders as a single <p> with joined segments", () => {
  const out = renderRichParagraphs([
    [
      "Researchers demonstrated attacks (",
      { type: "link", title: "Paper Title", url: "https://arxiv.org/abs/0000.0001" },
      ") on retrieval systems.",
    ],
  ]);
  assert.equal(
    out,
    '<p class="body-copy">Researchers demonstrated attacks (' +
      '<a href="https://arxiv.org/abs/0000.0001" rel="noopener noreferrer" target="_blank">Paper Title</a>' +
      ") on retrieval systems.</p>",
  );
});

test("nested array containing an object never produces '[object Object]'", () => {
  // Direct regression assertion for the broken-rendering symptom that
  // triggered task 2.4.3's bundling into B2.
  const out = renderRichParagraphs([
    ["Prefix (", { type: "link", title: "T", url: "https://example.com/" }, ") suffix."],
  ]);
  assert.ok(
    !out.includes("[object Object]"),
    `renderRichParagraphs leaked [object Object] for a structured-item input: ${out}`,
  );
});

test("regression: riskRetrievalVectorStorePoisoning shape from persona-site-data.json", () => {
  // Use the exact shape from the generated site data — alternating string and
  // {type:"link",...} segments inside a nested array (single inline paragraph).
  const examples = [
    [
      "Researchers have demonstrated adversarial attacks on retrieval systems (",
      {
        type: "link",
        title: "Poisoning Retrieval Corpora by Injecting Adversarial Passages",
        url: "https://arxiv.org/abs/2310.19156",
      },
      ") where malicious documents are crafted to rank highly for specific queries while containing harmful content.",
    ],
    [
      "Studies show that poisoning attacks on vector databases (",
      {
        type: "link",
        title: "Backdoor Attacks on Dense Retrieval via Public and Unintentional Triggers",
        url: "https://arxiv.org/abs/2402.13532",
      },
      ") can successfully manipulate RAG system outputs by injecting adversarial embeddings.",
    ],
  ];
  const out = renderRichParagraphs(examples);
  // Two paragraphs, one per example.
  assert.equal((out.match(/<p class="body-copy">/g) || []).length, 2);
  // Both citation titles appear as anchor text.
  assert.ok(
    out.includes(
      '<a href="https://arxiv.org/abs/2310.19156" rel="noopener noreferrer" target="_blank">Poisoning Retrieval Corpora by Injecting Adversarial Passages</a>',
    ),
  );
  assert.ok(
    out.includes(
      '<a href="https://arxiv.org/abs/2402.13532" rel="noopener noreferrer" target="_blank">Backdoor Attacks on Dense Retrieval via Public and Unintentional Triggers</a>',
    ),
  );
  // No [object Object] leak.
  assert.ok(!out.includes("[object Object]"));
});

test("mixed item types: string + nested-with-object + plain nested array", () => {
  // Sanity check that branches are dispatched independently and concatenated.
  const out = renderRichParagraphs([
    "Top-level string.",
    ["Inline (", { type: "link", title: "Cite", url: "https://example.org/" }, ") segment."],
    ["Legacy nested A.", "Legacy nested B."],
  ]);
  // Expect:
  //   1. <p>Top-level string.</p>
  //   2. <p>Inline (<a ...>Cite</a>) segment.</p>
  //   3. <div class="subsection"><p>Legacy nested A.</p><p>Legacy nested B.</p></div>
  assert.equal(
    out,
    '<p class="body-copy">Top-level string.</p>' +
      '<p class="body-copy">Inline (<a href="https://example.org/" rel="noopener noreferrer" target="_blank">Cite</a>) segment.</p>' +
      '<div class="subsection"><p class="body-copy">Legacy nested A.</p><p class="body-copy">Legacy nested B.</p></div>',
  );
});

test("empty items array produces empty string", () => {
  assert.equal(renderRichParagraphs([]), "");
});

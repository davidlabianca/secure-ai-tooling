/**
 * sanitizer.mjs — render-time prose sanitizer for the CoSAI Risk Map site.
 *
 * Exports renderProse(input) which accepts either a plain string or a
 * structured link object ({type: "link", title, url}) and returns an
 * HTML-safe string suitable for assignment to innerHTML.
 *
 * Design: ADR-015 D3 (hand-rolled, bounded emission), D3a (ALLOWED_TAGS
 * literal const), D3b (per-tag fixtures + meta-test enforce the boundary).
 *
 * Allowed output tags: <strong>, <em>, <a> with restricted attributes only.
 * Everything else is escaped with &lt;/&gt; and triggers one console.warn
 * per renderProse call.
 *
 * This file must remain browser-compatible (no node: imports).
 */

// Bounded-emission literal constant — ADR-015 D3a.
// Must be a literal const at module scope. Never derive from input or config.
// The meta-test in sanitizer.test.mjs reads this file's source and asserts
// this pattern exists. Adding a tag here requires a matching fixture update.
const ALLOWED_TAGS = ["strong", "em", "a"];

// ---------------------------------------------------------------------------
// HTML character escaping
// ---------------------------------------------------------------------------

/**
 * Escape a string for safe inclusion in HTML text content or attribute values.
 * Replaces &, <, >, ", ' with their named HTML entities.
 *
 * @param {string} text - Raw text to escape
 * @returns {string} HTML-escaped text
 */
function escapeHtml(text) {
  return String(text).replace(/[&<>"']/g, (ch) => {
    switch (ch) {
      case "&":
        return "&amp;";
      case "<":
        return "&lt;";
      case ">":
        return "&gt;";
      case '"':
        return "&quot;";
      case "'":
        return "&#39;";
    }
  });
}

/**
 * Escape a string for use as anchor text content.
 * Extends escapeHtml by also encoding `=` as `&#61;` so that attribute-
 * injection patterns like `onclick=` cannot appear as a raw substring in the
 * rendered HTML output, even inside text content where they are already
 * structurally harmless.
 *
 * This defence-in-depth prevents the raw string `onclick=` from surfacing in
 * the serialised output, which is the requirement the attack-corpus fixture
 * for attribute-injection-quote-in-text asserts.
 *
 * @param {string} text - Raw title text from a structured link item
 * @returns {string} HTML-escaped text safe for anchor inner content
 */
function escapeLinkTitle(text) {
  return escapeHtml(text).replaceAll("=", "&#61;");
}

// ---------------------------------------------------------------------------
// URL validation for <a href>
// ---------------------------------------------------------------------------

/**
 * Validate a URL from a structured link item for use in href.
 * Per ADR-015 D3a (bounded-emission posture) and D5 (RFC-3986 conformance):
 *   1. Trim leading/trailing whitespace, then reject control chars (U+0000–U+001F).
 *   2. Reject RFC 3986-illegal characters with HTML-attribute or URL-parser breakout
 *      history: `"`, `<`, `>`, `\`, `` ` ``, and any whitespace (`\s`).
 *   3. Require scheme to be exactly https://.
 *
 * @param {string} rawUrl - URL string from the structured item
 * @returns {{valid: boolean, trimmedUrl: string}} Result of validation
 */
function validateUrl(rawUrl) {
  const trimmed = String(rawUrl).trim();

  // Layer 1: Reject any control character (U+0000–U+001F inclusive); catches null bytes and C0 injection.
  // eslint-disable-next-line no-control-regex
  if (/[\x00-\x1f]/.test(trimmed)) {
    return { valid: false, trimmedUrl: trimmed };
  }

  // Layer 2: Reject RFC 3986-illegal characters that have HTML-attribute or URL-parser breakout history
  // (see ADR-015 D3a, D5). escapeHtml at emit time neutralizes them at the HTML layer, but rejection
  // here matches D3a's bounded-emission posture (no copied-through input) and removes URL-parser-confusion
  // vectors (e.g. backslash treated as slash by some legacy parsers, backtick as attribute delimiter in IE).
  // \s covers space, \t, \n, \r, \f, \v — broader than strictly needed but cheap; layer 1 already caught
  // \t/\n/\r, so this is intentional defense-in-depth redundancy.
  if (/["<>\\`\s]/.test(trimmed)) {
    return { valid: false, trimmedUrl: trimmed };
  }

  // Layer 3: Scheme must be exactly https:// (case-insensitive).
  if (!/^https:\/\//i.test(trimmed)) {
    return { valid: false, trimmedUrl: trimmed };
  }

  return { valid: true, trimmedUrl: trimmed };
}

// ---------------------------------------------------------------------------
// Tokenizer
// ---------------------------------------------------------------------------

// Token kinds produced by tokenize().
// "text"       — plain text fragment, HTML-safe after escaping
// "bold-open"  — opening **
// "bold-close" — closing **
// "em-open"    — opening * or _
// "em-close"   — closing * or _
// "sentinel"   — {{...}} passthrough token
// "md-link"    — markdown [text](url) — disallowed, emit display text only
// "raw-html"   — literal HTML tag — disallowed, must escape and warn

/**
 * Tokenize a prose string into an array of token objects.
 *
 * The tokenizer is markdown-driven: it recognises ** (bold), * and _ (italic),
 * {{...}} (sentinels), [text](url) (markdown links, disallowed), and raw HTML
 * tags <...> (disallowed). Everything else is plain text.
 *
 * The tokenizer is greedy and scan-based: it walks the string character by
 * character, emitting the longest match at each position.
 *
 * @param {string} input - Raw prose string
 * @returns {Array<{kind: string, value?: string, url?: string}>} Token list
 */
function tokenize(input) {
  const tokens = [];
  let pos = 0;
  const len = input.length;

  // Accumulated plain-text buffer — flushed before emitting any non-text token.
  let textBuf = "";

  function flushText() {
    if (textBuf.length > 0) {
      tokens.push({ kind: "text", value: textBuf });
      textBuf = "";
    }
  }

  while (pos < len) {
    // --- Sentinel: {{...}} ---
    if (input[pos] === "{" && input[pos + 1] === "{") {
      const end = input.indexOf("}}", pos + 2);
      if (end !== -1) {
        flushText();
        // Capture the full sentinel including braces.
        tokens.push({ kind: "sentinel", value: input.slice(pos, end + 2) });
        pos = end + 2;
        continue;
      }
    }

    // --- Bold: ** ---
    // Two asterisks in a row. We emit open/close tokens based on scan
    // context; the emitter will pair them up.
    if (input[pos] === "*" && input[pos + 1] === "*") {
      flushText();
      tokens.push({ kind: "bold-delim", value: "**" });
      pos += 2;
      continue;
    }

    // --- Italic: single * or _ ---
    // Single asterisk not followed by another asterisk.
    if (input[pos] === "*" && input[pos + 1] !== "*") {
      flushText();
      tokens.push({ kind: "em-delim", value: "*" });
      pos += 1;
      continue;
    }

    // Underscore italic: single underscore.
    // Double underscore __ is NOT bold and NOT italic per ADR-017 D1.
    // We must not split __ into two em-delims; instead treat __ as text.
    if (input[pos] === "_") {
      if (input[pos + 1] === "_") {
        // Double underscore — not a recognised delimiter; emit as text.
        textBuf += "__";
        pos += 2;
        continue;
      }
      flushText();
      tokens.push({ kind: "em-delim", value: "_" });
      pos += 1;
      continue;
    }

    // --- Raw HTML tag: <...> ---
    // Any literal < followed by an alpha char, `/`, or `!` starts an HTML tag.
    // Capture from < to the matching >.
    if (input[pos] === "<") {
      const nextCh = input[pos + 1];
      if (/[a-zA-Z/!]/.test(nextCh)) {
        const end = input.indexOf(">", pos + 1);
        if (end !== -1) {
          flushText();
          tokens.push({ kind: "raw-html", value: input.slice(pos, end + 1) });
          pos = end + 1;
          continue;
        }
      }
      // Lone < without a matching tag pattern — treat as text.
      textBuf += "&lt;";
      pos += 1;
      continue;
    }

    // --- Markdown link: [text](url) ---
    // Disallowed by ADR-017 D2. Recognise and emit as md-link so the
    // emitter can suppress the URL (preventing javascript: from appearing).
    if (input[pos] === "[") {
      const closeBracket = input.indexOf("]", pos + 1);
      if (closeBracket !== -1 && input[closeBracket + 1] === "(") {
        const closeParen = input.indexOf(")", closeBracket + 2);
        if (closeParen !== -1) {
          flushText();
          const displayText = input.slice(pos + 1, closeBracket);
          const url = input.slice(closeBracket + 2, closeParen);
          tokens.push({ kind: "md-link", value: displayText, url });
          pos = closeParen + 1;
          continue;
        }
      }
      // Not a valid markdown link syntax — treat [ as text.
      textBuf += input[pos];
      pos += 1;
      continue;
    }

    // --- Default: accumulate as plain text ---
    // Handle & as HTML entity to avoid double-escaping later.
    if (input[pos] === "&") {
      textBuf += "&amp;";
      pos += 1;
    } else if (input[pos] === ">") {
      // Bare > not part of a tag (we only get here if < was not matched).
      textBuf += "&gt;";
      pos += 1;
    } else if (input[pos] === '"') {
      textBuf += "&quot;";
      pos += 1;
    } else if (input[pos] === "'") {
      textBuf += "&#39;";
      pos += 1;
    } else {
      textBuf += input[pos];
      pos += 1;
    }
  }

  flushText();
  return tokens;
}

// ---------------------------------------------------------------------------
// Emitter
// ---------------------------------------------------------------------------

/**
 * Walk the token stream and emit an HTML string.
 *
 * Bold and italic use a simple open/close stack: each bold-delim token
 * toggles between open and close state. Unmatched delimiters that don't
 * get a closing partner are treated as plain text (this is a best-effort
 * approach for well-formed prose from the authoring subset).
 *
 * @param {Array} tokens - Token list from tokenize()
 * @param {string} originalInput - Original input string (for warn payload)
 * @returns {{html: string, hadInvalid: boolean}} Emitted HTML and invalid-token flag
 */
function emit(tokens, originalInput) {
  let html = "";
  let hadInvalid = false;

  // State for bold/em matching.
  let boldOpen = false;
  let emOpen = false;
  // Track which em delimiter opened (so we close with the same tag).
  // We allow * and _ to be interchangeable here per the simple grammar.

  for (const token of tokens) {
    switch (token.kind) {
      case "text":
        // Text was accumulated already-escaped (& < > " ' were escaped
        // as they were read by the tokenizer into textBuf).
        html += token.value;
        break;

      case "sentinel":
        // Sentinels pass through verbatim — { and } are not HTML-special.
        html += token.value;
        break;

      case "bold-delim":
        if (!boldOpen) {
          html += "<strong>";
          boldOpen = true;
        } else {
          html += "</strong>";
          boldOpen = false;
        }
        break;

      case "em-delim":
        if (!emOpen) {
          html += "<em>";
          emOpen = true;
        } else {
          html += "</em>";
          emOpen = false;
        }
        break;

      case "raw-html":
        // Escape the entire raw HTML span — both < and > and any
        // embedded quotes. The token.value is the literal HTML string.
        html += escapeHtml(token.value);
        hadInvalid = true;
        break;

      case "md-link": {
        // Disallowed form (ADR-017 D2). Emit only the display text,
        // HTML-escaped. The URL is suppressed entirely so that dangerous
        // schemes like javascript: never appear in the output.
        html += escapeHtml(token.value);
        hadInvalid = true;
        break;
      }

      default:
        // Unknown token kind — defensive escape.
        html += escapeHtml(String(token.value ?? ""));
        hadInvalid = true;
        break;
    }
  }

  // Close any unclosed bold/em (malformed input from the authoring subset).
  if (boldOpen) {
    html += "</strong>";
  }
  if (emOpen) {
    html += "</em>";
  }

  return { html, hadInvalid };
}

// ---------------------------------------------------------------------------
// renderProse — the exported public API
// ---------------------------------------------------------------------------

/**
 * Render a prose item to an HTML-safe string.
 *
 * Accepts two input shapes:
 *   - string: tokenized through the markdown-subset grammar
 *   - {type: "link", title: string, url: string}: rendered as an outbound <a>
 *
 * Any other input shape is coerced to string, escaped, and warned about.
 *
 * Per ADR-015 D4, disallowed markup is escaped (not stripped) and exactly one
 * console.warn("renderProse: escaped unexpected markup", {input, escaped}) is
 * emitted per call if any disallowed token was found.
 *
 * @param {string | {type: string, title?: string, url?: string}} input
 * @returns {string} HTML-safe prose fragment
 */
export function renderProse(input) {
  // --- Structured link item ---
  if (input !== null && typeof input === "object") {
    if (input.type === "link") {
      const { valid, trimmedUrl } = validateUrl(input.url ?? "");
      const escapedTitle = escapeLinkTitle(String(input.title ?? ""));

      if (valid) {
        // Construct the <a> with renderer-owned attributes only.
        // href is HTML-escaped after validation to prevent attribute breakout (e.g. " in URL).
        // rel and target are hardcoded constants per ADR-015 D3a.
        return `<a href="${escapeHtml(trimmedUrl)}" rel="noopener noreferrer" target="_blank">${escapedTitle}</a>`;
      }

      // Invalid URL: escape the title text and warn.
      const escaped = escapedTitle;
      console.warn("renderProse: escaped unexpected markup", { input, escaped });
      return escaped;
    }

    // Unknown structured type — escape and warn.
    const escaped = escapeHtml(String(input));
    console.warn("renderProse: escaped unexpected markup", { input, escaped });
    return escaped;
  }

  // --- Plain string path ---
  const str = String(input);
  const tokens = tokenize(str);
  const { html, hadInvalid } = emit(tokens, str);

  if (hadInvalid) {
    console.warn("renderProse: escaped unexpected markup", { input: str, escaped: html });
  }

  return html;
}

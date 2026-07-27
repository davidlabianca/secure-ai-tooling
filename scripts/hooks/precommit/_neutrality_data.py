"""
Denylist/allowlist data for the ADR-033 vendor-neutrality checker.

This module is the one sanctioned place vendor, product, CLI, and model
tokens legitimately appear in this codebase: as detection data consumed by
validate_neutrality.py, not as endorsement or usage guidance. Nothing here
should be read as "use this tool" — it exists so authoring surfaces
(scripts/agents/**, scripts/skills/**) can be checked for accidental
harness-specific references.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Category 1: vendor/product/company/CLI names.
#
# Matched as whole phrases with word boundaries, case-sensitive. Case-
# sensitivity (rather than a blanket case-insensitive substring match) is
# what keeps "CLAUDE.md" (this repo's own instructions filename) from
# colliding with the product name "Claude Code" or the company "Anthropic":
# there is no bare "Claude" entry in this list, only the two-word phrase.
# ---------------------------------------------------------------------------
# "Cody" and "Devin" also double as common English first names. Accepted,
# low-likelihood tradeoff: the scanned surfaces are technical agent/skill
# definitions, not prose about people, so the false-positive risk is small.
VENDOR_PRODUCT_TERMS: tuple[str, ...] = (
    "GitHub Copilot",
    "Claude Code",
    "Anthropic",
    "OpenAI",
    "ChatGPT",
    "GPT",
    "Copilot",
    "Cursor",
    "Windsurf",
    "Codeium",
    "Gemini",
    "Cody",
    "Devin",
    "Aider",
    "Replit",
)

# Lowercase vendor/product tokens that leak through the case-sensitive scan
# above (e.g. `import openai`, `from anthropic import`, "the copilot
# suggestion"). Matched case-sensitively as whole words so they catch the
# lowercase forms without re-flagging capitalized prose already covered above.
# Kept out of VENDOR_PRODUCT_TERMS (and out of a blanket IGNORECASE) on purpose:
# making the vendor regex case-insensitive would re-flag "CLAUDE.md", the repo's
# own instructions filename, which is not a harness-product reference.
VENDOR_PRODUCT_LOWERCASE_TERMS: tuple[str, ...] = (
    "openai",
    "anthropic",
    "copilot",
    "codeium",
    "chatgpt",
)

# Longest-first so a multi-word phrase (e.g. "GitHub Copilot") wins over a
# shorter term it contains (e.g. "Copilot") at the same starting position.
_VENDOR_PRODUCT_ALTERNATION = "|".join(
    re.escape(term) for term in sorted(VENDOR_PRODUCT_TERMS, key=len, reverse=True)
)
_VENDOR_PRODUCT_LOWERCASE_ALTERNATION = "|".join(
    re.escape(term) for term in sorted(VENDOR_PRODUCT_LOWERCASE_TERMS, key=len, reverse=True)
)
# Two branches share one case-sensitive pattern: the mixed-case product/company
# phrases and the lowercase-only leakage tokens. A single regex keeps
# _DENYLIST_CATEGORIES emitting one "vendor" description for either shape.
VENDOR_PRODUCT_RE = re.compile(rf"\b(?:{_VENDOR_PRODUCT_ALTERNATION}|{_VENDOR_PRODUCT_LOWERCASE_ALTERNATION})\b")

# ---------------------------------------------------------------------------
# Category 1: model-identifier-shaped strings (e.g. claude-sonnet-4-5,
# gpt-4o, gemini-1.5-pro).
#
# Keyed to known model-family prefixes rather than a generic "word-hyphen-
# number" shape, so the bare word "model" — used pervasively as neutral
# terminology (Model Provider persona, threat model, model card) — never
# matches. Case-insensitive so lowercase mentions in example commands are
# still caught.
# ---------------------------------------------------------------------------
_MODEL_FAMILY_PREFIXES = (
    "claude",
    "gpt",
    "gemini",
    "llama",
    "mistral",
    "codex",
    "palm",
    "deepseek",
    "grok",
    "qwen",
)
MODEL_IDENTIFIER_RE = re.compile(
    rf"\b(?:{'|'.join(_MODEL_FAMILY_PREFIXES)})-[A-Za-z0-9]+(?:[.-][A-Za-z0-9]+)*\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Category 1: harness CLI entry points in backticks, e.g. `claude --resume`,
# `cursor --resume`, `aider ...`.
#
# Case-insensitive and scoped to a backtick-delimited span so it never
# collides with prose mentions of "CLAUDE.md" (which is never backtick-
# wrapped as a shell command in this corpus). The entry-point word is anchored
# to the start of the backtick span so an incidental backticked path containing
# one of these words mid-string is not matched.
#
# Known v1 limitation: this only catches the inline-backtick form. A fenced
# code block (``` ... claude --resume ... ```) or a bare shell-prompt form
# with no backticks at all ($ claude --resume) is not matched. Broadening
# this is deliberately left as follow-up work rather than expanding the
# regex here untested.
# ---------------------------------------------------------------------------
CLI_ENTRYPOINT_NAMES: tuple[str, ...] = (
    "claude",
    "cursor",
    "aider",
    "windsurf",
    "codex",
    "cline",
)
_CLI_ENTRYPOINT_ALTERNATION = "|".join(re.escape(name) for name in CLI_ENTRYPOINT_NAMES)
CLI_ENTRYPOINT_RE = re.compile(rf"`(?:{_CLI_ENTRYPOINT_ALTERNATION})\b[^`\n]*`", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Category 1: harness-invocation stage directions, e.g. `<invoke the Bash
# tool>`, `<uses the Read tool>`, including the backslash-escaped form
# (`\<invoke the Bash tool\>`) this repo's own agent docs use to keep
# markdown renderers from treating angle brackets as HTML.
#
# The literal word "tool" is required inside the brackets. This repo's own
# cross-agent-handoff convention (`\<invoke <agent-name> agent\>`) names an
# agent, never a tool, so it never collides with this pattern.
# ---------------------------------------------------------------------------
INVOKE_TOOL_RE = re.compile(
    r"\\?<[^<>]*\b(?:uses|invoke)\b[^<>]*\btool\b[^<>]*>\\?",
    re.IGNORECASE,
)

# subagent_type / subagent-type key or token.
SUBAGENT_TYPE_RE = re.compile(r"subagent[_-]type", re.IGNORECASE)

# "auto-loads"/"auto-triggers" phrasing and its paraphrases (tense/aspect
# variants plus -activates/-invokes and the bare "auto-load" stem). The
# optional trailing group lets the bare stem ("auto-load") match while still
# catching "auto-loading"/"auto-activates"/"auto-invokes".
AUTO_LOAD_TRIGGER_RE = re.compile(r"auto-(?:load|trigger|activate|invoke)(?:s|d|ed|ing)?", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Category 1: harness-specific config-path fragments.
#
# ".github/copilot" is the denylisted fragment, not bare ".github/" (an
# ordinary repository directory referenced constantly in legitimate agent
# prose for CI workflows, issue templates, etc.).
# ---------------------------------------------------------------------------
HARNESS_CONFIG_PATH_TERMS: tuple[str, ...] = (
    ".claude/",
    ".cursor/",
    ".windsurf/",
    ".aider/",
    ".continue/",
    ".codeium/",
    ".github/copilot",
)
_HARNESS_CONFIG_PATH_ALTERNATION = "|".join(
    re.escape(term) for term in sorted(HARNESS_CONFIG_PATH_TERMS, key=len, reverse=True)
)
# IGNORECASE so case variants of the same harness config path (`.Claude/`,
# `.github/Copilot`) are caught. Safe here because these fragments are
# product-named directories, not ordinary words: `.vscode/` and other neutral
# config dirs are not in the list, so widening case does not start matching them.
HARNESS_CONFIG_PATH_RE = re.compile(_HARNESS_CONFIG_PATH_ALTERNATION, re.IGNORECASE)

# ---------------------------------------------------------------------------
# Category 2: framework-authority allowlist.
#
# Legitimate framework-mapping references. Any denylist match whose span
# overlaps one of these allowlist matches, on the same line, is suppressed.
# `FRAMEWORK_ALLOWLIST_TERMS` is the plain-label export a maintainer would
# grep for; `FRAMEWORK_ALLOWLIST_PATTERNS` is what validate_neutrality.py
# actually scans with.
# ---------------------------------------------------------------------------
FRAMEWORK_ALLOWLIST_TERMS: tuple[str, ...] = (
    "MITRE ATLAS",
    "MITRE ATT&CK",
    "NIST AI RMF",
    "OWASP Top 10",
    "ISO",
    "EU AI Act",
    "STRIDE",
)

FRAMEWORK_ALLOWLIST_PATTERNS: tuple[re.Pattern, ...] = (
    re.compile(r"\bMITRE\b"),
    re.compile(r"\bATLAS\b"),
    re.compile(r"\bATT&CK\b"),
    re.compile(r"\bAML\.[TM]\d{4}\b"),  # MITRE ATLAS technique/mitigation IDs
    re.compile(r"\bNIST\b"),
    re.compile(r"\bAI\s+RMF\b"),
    # NIST AI RMF subcategory IDs (full-word function prefix), e.g. GOVERN-1.1.
    re.compile(r"\b(?:GOVERN|MAP|MEASURE|MANAGE)-\d+(?:\.\d+)?\b"),
    re.compile(r"\bOWASP\b"),
    re.compile(r"\bTop\s+10\b"),
    re.compile(r"\bLLM\d{2}:\d{4}\b"),  # OWASP LLM Top 10 IDs, e.g. LLM01:2025
    re.compile(r"\bISO(?:/IEC)?\s?\d+\b"),  # ISO 22989, ISO/IEC 42001
    re.compile(r"\bEU\s+AI\s+Act\b"),
    re.compile(r"\bArticle\s+\d+\b"),
    re.compile(
        r"\bSTRIDE\b|\bSpoofing\b|\bTampering\b|\bRepudiation\b"
        r"|\bInformation Disclosure\b|\bDenial of Service\b|\bElevation of Privilege\b"
    ),
)

"""Tokenizer-driven sentinel resolution shared by yaml_to_markdown.py and
build_persona_site_data.py.

Implements ADR-016 D5: both downstream generators expand intra-document
sentinels ({{<entity-id>}}) and external-reference sentinels
({{ref:<identifier>}}) into rendered output. An unresolved sentinel is a
hard build failure — never silently passed through.

Wire-format note: the tokenizer at scripts/hooks/precommit/_prose_tokens.py
accepts the bare entity-prefix camelCase form ({{riskFoo}}, {{controlFoo}},
{{componentFoo}}, {{personaFoo}}) — NOT the {{idXxx}} meta-notation that
appears in ADR-016 D2 prose.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from scripts.hooks.precommit._prose_tokens import TokenKind, tokenize


class UnresolvedSentinelError(ValueError):
    """Raised when a sentinel's id cannot be resolved during expansion.

    Attributes:
        sentinel: full sentinel span as it appeared in source (e.g.
            "{{riskTypoFooBar}}" or "{{ref:cve-2024-99999}}").
        field_path: caller-supplied path string identifying the prose field
            that contained the unresolved sentinel (e.g.
            "risks[3].longDescription[0]"). Lets the build error point an
            author straight at the offending YAML location.
    """

    def __init__(self, sentinel: str, field_path: str, message: str = "") -> None:
        self.sentinel = sentinel
        self.field_path = field_path
        # Build a message that always includes both sentinel and field_path so
        # str(exc) satisfies the test contract regardless of whether message is empty.
        full_message = message or f"Unresolved sentinel {sentinel!r} at {field_path!r}"
        # Ensure sentinel and field_path appear in str(exc) even when message omits them.
        if sentinel not in full_message:
            full_message = f"{full_message} (sentinel: {sentinel})"
        if field_path not in full_message:
            full_message = f"{full_message} (field_path: {field_path})"
        super().__init__(full_message)


def expand_sentinels_to_text(
    text: str,
    *,
    intra_lookup: Mapping[str, str],
    ref_lookup: Mapping[str, dict],
    field_path: str,
    link_format: Callable[[str, str], str] = lambda title, url: f"[{title}]({url})",
) -> str:
    """Expand every sentinel in `text` to a rendered string.

    For yaml_to_markdown.py. Intra-document sentinels resolve to the entity
    title as plain text; external-reference sentinels resolve via
    `link_format(title, url)` (defaults to standard markdown link syntax).
    Non-sentinel tokens (TEXT, BOLD, ITALIC, INVALID_*) pass through verbatim
    by their `.value`. No whitespace stripping — the substitution is purely
    string replacement at sentinel positions.

    Args:
        text: prose string from a YAML field value.
        intra_lookup: maps entity-id -> title.
        ref_lookup: maps ref-id -> {"title": str, "url": str}.
        field_path: caller-supplied location string for error messages.
        link_format: callable that turns (title, url) into the rendered
            external-reference string. Default produces "[title](url)".

    Returns:
        The text with sentinels replaced.

    Raises:
        UnresolvedSentinelError: any sentinel whose id is not in the
            corresponding lookup. Surfaces the sentinel span and field_path.
    """
    tokens = tokenize(text)
    parts: list[str] = []

    for token in tokens:
        if token.kind == TokenKind.SENTINEL_INTRA:
            entity_id = token.value[2:-2]  # strip {{ and }}
            if entity_id not in intra_lookup:
                raise UnresolvedSentinelError(
                    sentinel=token.value,
                    field_path=field_path,
                    message=f"Intra sentinel {token.value!r} not in intra_lookup at {field_path!r}",
                )
            parts.append(intra_lookup[entity_id])

        elif token.kind == TokenKind.SENTINEL_REF:
            # Strip {{ and }} to get "ref:<id>", then strip the "ref:" prefix.
            inner = token.value[2:-2]
            ref_id = inner[4:]  # strip "ref:"
            if ref_id not in ref_lookup:
                raise UnresolvedSentinelError(
                    sentinel=token.value,
                    field_path=field_path,
                    message=f"Ref sentinel {token.value!r} not in ref_lookup at {field_path!r}",
                )
            entry = ref_lookup[ref_id]
            parts.append(link_format(entry["title"], entry["url"]))

        else:
            # TEXT, BOLD, ITALIC, and all INVALID_* tokens pass through verbatim.
            parts.append(token.value)

    return "".join(parts)


def expand_sentinels_to_items(
    text: str,
    *,
    intra_lookup: Mapping[str, str],
    ref_lookup: Mapping[str, dict],
    field_path: str,
) -> list:
    """Expand every sentinel in `text` to a list of strings and structured items.

    For build_persona_site_data.py. Intra-document sentinels become
    {"type": "ref", "id": <entity-id>, "title": <entity-title>} dicts;
    external-reference sentinels become
    {"type": "link", "title": <ref-title>, "url": <ref-url>} dicts.
    Adjacent non-sentinel tokens (TEXT, BOLD, ITALIC, INVALID_*) are
    concatenated into a single string segment between sentinels.

    Contract:
      - For empty input: returns [] (the caller should drop the field).
      - For any non-empty input: returns at least one item.
      - Empty TEXT segments between adjacent sentinels are dropped — the
        result never contains "" entries. Mirrors the NIT-08 semantics in
        normalize_text_entries: empty/whitespace-only spans are not surfaced.

    Args:
        text: prose string from a YAML field value.
        intra_lookup: maps entity-id -> title.
        ref_lookup: maps ref-id -> {"title": str, "url": str}.
        field_path: caller-supplied location string for error messages.

    Returns:
        A list whose elements are either strings (text segments) or
        structured dicts ({"type": "ref", ...} or {"type": "link", ...}).

    Raises:
        UnresolvedSentinelError: any sentinel whose id is not in the
            corresponding lookup.
    """
    tokens = tokenize(text)
    items: list = []
    # Buffer for accumulating adjacent non-sentinel token values.
    pending_text: list[str] = []

    def flush_pending() -> None:
        """Emit the accumulated text buffer as a string item if non-whitespace."""
        if pending_text:
            segment = "".join(pending_text)
            # Drop whitespace-only segments (NIT-08 parity).
            if segment.strip():
                items.append(segment)
            pending_text.clear()

    for token in tokens:
        if token.kind == TokenKind.SENTINEL_INTRA:
            flush_pending()
            entity_id = token.value[2:-2]
            if entity_id not in intra_lookup:
                raise UnresolvedSentinelError(
                    sentinel=token.value,
                    field_path=field_path,
                    message=f"Intra sentinel {token.value!r} not in intra_lookup at {field_path!r}",
                )
            items.append({"type": "ref", "id": entity_id, "title": intra_lookup[entity_id]})

        elif token.kind == TokenKind.SENTINEL_REF:
            flush_pending()
            inner = token.value[2:-2]
            ref_id = inner[4:]  # strip "ref:"
            if ref_id not in ref_lookup:
                raise UnresolvedSentinelError(
                    sentinel=token.value,
                    field_path=field_path,
                    message=f"Ref sentinel {token.value!r} not in ref_lookup at {field_path!r}",
                )
            entry = ref_lookup[ref_id]
            items.append({"type": "link", "title": entry["title"], "url": entry["url"]})

        else:
            # Accumulate TEXT, BOLD, ITALIC, and INVALID_* tokens into the text buffer.
            pending_text.append(token.value)

    flush_pending()
    return items

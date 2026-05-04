#!/usr/bin/env python3
"""
Tests for scripts/hooks/_sentinel_expansion.py

This module tests the shared sentinel-expansion helper (ADR-016 D5). The helper
is the single source of truth for tokenizer-driven sentinel resolution used by
both downstream generators:
  - scripts/build_persona_site_data.py  (via expand_sentinels_to_items)
  - scripts/yaml_to_markdown.py         (via expand_sentinels_to_text)

Public API under test:
  UnresolvedSentinelError(sentinel, field_path, message="")
  expand_sentinels_to_text(text, *, intra_lookup, ref_lookup, field_path,
                            link_format=lambda title, url: f"[{title}]({url})")
  expand_sentinels_to_items(text, *, intra_lookup, ref_lookup, field_path)

Wire-format sentinel examples used in fixtures (real tokenizer forms):
  {{riskPromptInjection}}                    intra; id = "riskPromptInjection"
  {{controlInputValidationAndSanitization}}  intra; id = "controlInputValidationAndSanitization"
  {{componentModelServing}}                  intra; id = "componentModelServing"
  {{personaModelCreator}}                    intra; id = "personaModelCreator"
  {{ref:cwe-89}}                             ref;  ref-id = "cwe-89"
  {{ref:zhou-2023-poisoning}}                ref;  ref-id = "zhou-2023-poisoning"

Do NOT use {{idRiskPromptInjection}} -- that is ADR meta-notation, not real wire format.

Design choices locked in by these tests:
  - expand_sentinels_to_text: TEXT spans are passed through verbatim (no strip).
  - expand_sentinels_to_items: empty TEXT spans (after .strip()) are NOT emitted.
  - expand_sentinels_to_items on a single-item TEXT-only result returns ["text"].
  - INVALID_* tokens and BOLD/ITALIC tokens pass through by .value in both funcs.
  - UnresolvedSentinelError carries .sentinel and .field_path attributes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

# ---------------------------------------------------------------------------
# Guarded import — RED-phase: helper does not exist yet.
# Tests fail with ImportError until SWE creates the module.
# ---------------------------------------------------------------------------
_IMPORT_ERROR: ImportError | None = None
try:
    from scripts.hooks._sentinel_expansion import (  # noqa: E402
        UnresolvedSentinelError,
        expand_sentinels_to_items,
        expand_sentinels_to_text,
    )
except ImportError as _e:
    _IMPORT_ERROR = _e
    UnresolvedSentinelError = None  # type: ignore[assignment,misc]
    expand_sentinels_to_text = None  # type: ignore[assignment]
    expand_sentinels_to_items = None  # type: ignore[assignment]


def _require_module() -> None:
    """Skip-with-fail if the module is missing; produces clear RED failure."""
    if _IMPORT_ERROR is not None:
        pytest.fail(
            f"scripts/hooks/_sentinel_expansion.py is not importable (expected in RED phase): {_IMPORT_ERROR}"
        )


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

INTRA_LOOKUP = {
    "riskPromptInjection": "Prompt Injection",
    "controlInputValidationAndSanitization": "Input Validation And Sanitization",
    "componentModelServing": "Model Serving Infrastructure",
    "personaModelCreator": "Model Creator",
}

REF_LOOKUP = {
    "cwe-89": {
        "title": "CWE-89: Improper Neutralization of SQL Commands",
        "url": "https://cwe.mitre.org/data/definitions/89.html",
    },
    "zhou-2023-poisoning": {"title": "Zhou et al. 2023 - Data Poisoning", "url": "https://example.com/zhou-2023"},
}


# ============================================================================
# TestExpandSentinelsToText
# ============================================================================


class TestExpandSentinelsToText:
    """Tests for expand_sentinels_to_text (markdown-side output)."""

    def test_plain_text_passthrough(self):
        """
        Test that text with no sentinels is returned unchanged.

        Given: A plain prose string with no {{ }} markers
        When: expand_sentinels_to_text is called
        Then: The exact input string is returned
        """
        _require_module()
        result = expand_sentinels_to_text(
            "Just plain text with no sentinels.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].shortDescription[0]",
        )
        assert result == "Just plain text with no sentinels."

    def test_intra_sentinel_replaced_with_title(self):
        """
        Test that an intra-doc sentinel is replaced by its entity title.

        Given: Text containing {{riskPromptInjection}} and a matching intra_lookup entry
        When: expand_sentinels_to_text is called
        Then: The sentinel span is replaced by the entity title (bare text, no link)
        """
        _require_module()
        result = expand_sentinels_to_text(
            "See {{riskPromptInjection}} for details.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].longDescription[0]",
        )
        assert result == "See Prompt Injection for details."

    def test_ref_sentinel_replaced_with_link_format(self):
        """
        Test that a ref sentinel is replaced using the link_format callable.

        Given: Text containing {{ref:cwe-89}} and a matching ref_lookup entry
        When: expand_sentinels_to_text is called with the default link_format
        Then: The sentinel span is replaced by [title](url) markdown
        """
        _require_module()
        result = expand_sentinels_to_text(
            "Relates to {{ref:cwe-89}} vulnerability class.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[1].longDescription[0]",
        )
        expected_link = (
            "[CWE-89: Improper Neutralization of SQL Commands](https://cwe.mitre.org/data/definitions/89.html)"
        )
        assert result == f"Relates to {expected_link} vulnerability class."

    def test_ref_sentinel_custom_link_format(self):
        """
        Test that a custom link_format callable is used for ref sentinels.

        Given: Text with {{ref:cwe-89}} and a custom link_format returning HTML <a>
        When: expand_sentinels_to_text is called with that custom link_format
        Then: The output uses the custom format rather than the default markdown
        """
        _require_module()

        def html_link(title: str, url: str) -> str:
            return f'<a href="{url}">{title}</a>'

        result = expand_sentinels_to_text(
            "See {{ref:cwe-89}}.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="controls[0].description[0]",
            link_format=html_link,
        )
        assert 'href="https://cwe.mitre.org/data/definitions/89.html"' in result
        assert "CWE-89" in result

    def test_multiple_sentinels_in_one_string(self):
        """
        Test that multiple sentinels in one string are all replaced.

        Given: A string containing both {{riskPromptInjection}} and {{ref:cwe-89}}
        When: expand_sentinels_to_text is called
        Then: Both sentinels are replaced in a single pass
        """
        _require_module()
        result = expand_sentinels_to_text(
            "{{riskPromptInjection}} is related to {{ref:cwe-89}}.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].longDescription[1]",
        )
        assert "Prompt Injection" in result
        assert "{{riskPromptInjection}}" not in result
        assert "{{ref:cwe-89}}" not in result
        assert "[CWE-89" in result

    def test_whitespace_preserved_verbatim_around_sentinels(self):
        """
        Test that internal whitespace is preserved verbatim; no stripping on TEXT spans.

        Given: A string with leading spaces, trailing spaces, and spaces around a sentinel
        When: expand_sentinels_to_text is called
        Then: All whitespace is preserved exactly; only the sentinel span is substituted

        This is the critical no-strip regression test: expand_sentinels_to_text must
        not call .strip() on TEXT spans. Sentinel substitution is a string replacement,
        not a normalization step.
        """
        _require_module()
        result = expand_sentinels_to_text(
            "  spaces  {{riskPromptInjection}}  more  ",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].shortDescription[0]",
        )
        assert result == "  spaces  Prompt Injection  more  "

    def test_bold_token_passthrough(self):
        """
        Test that bold markup passes through unchanged.

        Given: A string containing **bold text** alongside a sentinel
        When: expand_sentinels_to_text is called
        Then: The bold markup is preserved verbatim; only the sentinel is substituted
        """
        _require_module()
        result = expand_sentinels_to_text(
            "**Important**: see {{riskPromptInjection}}.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].shortDescription[0]",
        )
        assert result == "**Important**: see Prompt Injection."

    def test_italic_token_passthrough(self):
        """
        Test that italic markup passes through unchanged.

        Given: A string containing *italic text* alongside a sentinel
        When: expand_sentinels_to_text is called
        Then: The italic markup is preserved verbatim
        """
        _require_module()
        result = expand_sentinels_to_text(
            "*Note:* {{controlInputValidationAndSanitization}} applies.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="controls[0].description[0]",
        )
        assert result == "*Note:* Input Validation And Sanitization applies."

    def test_empty_string_input(self):
        """
        Test that an empty string input returns an empty string.

        Given: An empty string
        When: expand_sentinels_to_text is called
        Then: An empty string is returned with no error
        """
        _require_module()
        result = expand_sentinels_to_text(
            "",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].shortDescription[0]",
        )
        assert result == ""

    def test_component_sentinel_replaced(self):
        """
        Test that a component-prefix intra sentinel is resolved.

        Given: Text containing {{componentModelServing}} with a matching intra_lookup
        When: expand_sentinels_to_text is called
        Then: The sentinel is replaced by the component's title text
        """
        _require_module()
        result = expand_sentinels_to_text(
            "Affects {{componentModelServing}} directly.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].longDescription[0]",
        )
        assert result == "Affects Model Serving Infrastructure directly."

    def test_persona_sentinel_replaced(self):
        """
        Test that a persona-prefix intra sentinel is resolved.

        Given: Text containing {{personaModelCreator}} with a matching intra_lookup
        When: expand_sentinels_to_text is called
        Then: The sentinel is replaced by the persona's title text
        """
        _require_module()
        result = expand_sentinels_to_text(
            "Relevant to {{personaModelCreator}} role.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="controls[0].description[0]",
        )
        assert result == "Relevant to Model Creator role."


# ============================================================================
# TestExpandSentinelsToItems
# ============================================================================


class TestExpandSentinelsToItems:
    """Tests for expand_sentinels_to_items (builder-side structured output)."""

    def test_plain_text_returns_single_string(self):
        """
        Test that text with no sentinels returns a list with one string element.

        Given: A plain prose string with no sentinel spans
        When: expand_sentinels_to_items is called
        Then: Returns a list containing exactly one string equal to the input
        """
        _require_module()
        result = expand_sentinels_to_items(
            "Plain prose text.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].shortDescription[0]",
        )
        assert result == ["Plain prose text."]

    def test_intra_sentinel_returns_ref_item(self):
        """
        Test that an intra-doc sentinel is represented as a ref structured item.

        Given: Text containing only {{riskPromptInjection}}
        When: expand_sentinels_to_items is called
        Then: Returns a list with one dict: {type: "ref", id: "riskPromptInjection", title: "Prompt Injection"}
        """
        _require_module()
        result = expand_sentinels_to_items(
            "{{riskPromptInjection}}",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].shortDescription[0]",
        )
        assert result == [{"type": "ref", "id": "riskPromptInjection", "title": "Prompt Injection"}]

    def test_ref_sentinel_returns_link_item(self):
        """
        Test that a ref sentinel is represented as a link structured item.

        Given: Text containing only {{ref:cwe-89}}
        When: expand_sentinels_to_items is called
        Then: Returns a list with one dict: {type: "link", title: ..., url: ...}
        """
        _require_module()
        result = expand_sentinels_to_items(
            "{{ref:cwe-89}}",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[1].longDescription[0]",
        )
        assert result == [
            {
                "type": "link",
                "title": "CWE-89: Improper Neutralization of SQL Commands",
                "url": "https://cwe.mitre.org/data/definitions/89.html",
            }
        ]

    def test_sentinel_surrounded_by_text_produces_three_items(self):
        """
        Test that a sentinel surrounded by text produces [str, structured, str].

        Given: Text of the form "prefix {{sentinel}} suffix"
        When: expand_sentinels_to_items is called
        Then: Returns [prefix_str, sentinel_item, suffix_str] — three elements
        """
        _require_module()
        result = expand_sentinels_to_items(
            "See {{riskPromptInjection}} for details.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].longDescription[0]",
        )
        assert len(result) == 3
        assert result[0] == "See "
        assert result[1] == {"type": "ref", "id": "riskPromptInjection", "title": "Prompt Injection"}
        assert result[2] == " for details."

    def test_two_adjacent_sentinels_no_whitespace_between(self):
        """
        Test that two adjacent sentinels with no text between them produce two items.

        Given: Text "{{riskPromptInjection}}{{ref:cwe-89}}" with no TEXT between
        When: expand_sentinels_to_items is called
        Then: Returns [ref_item, link_item] — exactly two elements, no empty string between
        """
        _require_module()
        result = expand_sentinels_to_items(
            "{{riskPromptInjection}}{{ref:cwe-89}}",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].longDescription[0]",
        )
        assert len(result) == 2
        assert result[0]["type"] == "ref"
        assert result[1]["type"] == "link"
        # No empty string between them
        assert not any(item == "" for item in result)

    def test_empty_text_between_sentinels_is_not_emitted(self):
        """
        Test that empty/whitespace-only TEXT spans between sentinels are dropped.

        Given: Two sentinels with only whitespace between them
        When: expand_sentinels_to_items is called
        Then: No empty or whitespace-only string element appears in the result

        This is the NIT-08 regression test: matches normalize_text_entries behavior
        that drops empty / whitespace-only items.
        """
        _require_module()
        result = expand_sentinels_to_items(
            "{{riskPromptInjection}} {{ref:cwe-89}}",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].examples[0]",
        )
        # The single space between sentinels is whitespace-only; after .strip() it is ""
        # It must NOT appear in the output.
        string_items = [item for item in result if isinstance(item, str)]
        assert not any(s.strip() == "" for s in string_items), (
            "Whitespace-only TEXT spans must be dropped from expand_sentinels_to_items output"
        )

    def test_empty_string_input(self):
        """
        Test that an empty string input returns an empty list.

        Given: An empty string
        When: expand_sentinels_to_items is called
        Then: Returns an empty list (no items, including no empty string)
        """
        _require_module()
        result = expand_sentinels_to_items(
            "",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].shortDescription[0]",
        )
        assert result == []

    def test_multiple_intra_sentinels_all_resolved(self):
        """
        Test that multiple intra-doc sentinels in one string are all resolved.

        Given: A string with two intra sentinels separated by text
        When: expand_sentinels_to_items is called
        Then: Both sentinels produce ref items in source order; TEXT segments preserved
        """
        _require_module()
        result = expand_sentinels_to_items(
            "Both {{riskPromptInjection}} and {{controlInputValidationAndSanitization}} matter.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].longDescription[2]",
        )
        types = [item.get("type") if isinstance(item, dict) else "text" for item in result]
        assert "ref" in types
        assert types.count("ref") == 2
        # First ref is the risk, second is the control
        ref_items = [item for item in result if isinstance(item, dict) and item["type"] == "ref"]
        assert ref_items[0]["id"] == "riskPromptInjection"
        assert ref_items[1]["id"] == "controlInputValidationAndSanitization"

    def test_bold_and_italic_tokens_concatenated_into_text(self):
        """
        Test that BOLD and ITALIC tokens are concatenated into TEXT segments.

        Given: A string with **bold** and *italic* content adjacent to a sentinel
        When: expand_sentinels_to_items is called
        Then: Bold/italic tokens are concatenated with adjacent TEXT into string segments;
              sentinels produce structured items
        """
        _require_module()
        result = expand_sentinels_to_items(
            "**Critical**: {{riskPromptInjection}}.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].shortDescription[0]",
        )
        # Expect: ["**Critical**: ", {ref item}, "."]
        assert any(isinstance(item, dict) and item["type"] == "ref" for item in result)
        string_parts = [item for item in result if isinstance(item, str)]
        combined = "".join(string_parts)
        assert "**Critical**" in combined

    def test_invalid_sentinel_token_treated_as_text(self):
        """
        Test that INVALID_SENTINEL tokens are treated as text (passed through by .value).

        Given: A malformed sentinel like {{notValidPrefix}} that produces INVALID_SENTINEL
        When: expand_sentinels_to_items is called
        Then: The invalid sentinel span appears in the output as a text segment,
              not as a structured item, and no error is raised
        """
        _require_module()
        result = expand_sentinels_to_items(
            "Has {{notValidPrefix}} in it.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].longDescription[0]",
        )
        combined = "".join(item if isinstance(item, str) else "" for item in result)
        assert "{{notValidPrefix}}" in combined

    def test_component_intra_sentinel_resolves_to_ref_item(self):
        """
        Test that a component-prefix sentinel is resolved as a ref item.

        Given: Text containing {{componentModelServing}}
        When: expand_sentinels_to_items is called with intra_lookup containing that id
        Then: Returns a ref item with id="componentModelServing" and the correct title
        """
        _require_module()
        result = expand_sentinels_to_items(
            "{{componentModelServing}}",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].longDescription[0]",
        )
        assert result == [{"type": "ref", "id": "componentModelServing", "title": "Model Serving Infrastructure"}]

    def test_ref_sentinel_with_dotted_id(self):
        """
        Test that a ref sentinel with a hyphenated/compound id is resolved.

        Given: Text containing {{ref:zhou-2023-poisoning}}
        When: expand_sentinels_to_items is called with matching ref_lookup
        Then: Returns a link item with the correct title and url
        """
        _require_module()
        result = expand_sentinels_to_items(
            "See {{ref:zhou-2023-poisoning}} for the attack description.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].longDescription[0]",
        )
        link_items = [item for item in result if isinstance(item, dict) and item["type"] == "link"]
        assert len(link_items) == 1
        assert link_items[0]["title"] == "Zhou et al. 2023 - Data Poisoning"
        assert link_items[0]["url"] == "https://example.com/zhou-2023"


# ============================================================================
# TestUnresolvedSentinelError
# ============================================================================


class TestUnresolvedSentinelError:
    """Tests for UnresolvedSentinelError exception class and raise behavior."""

    def test_exception_is_subclass_of_value_error(self):
        """
        Test that UnresolvedSentinelError is a ValueError subclass.

        Given: The UnresolvedSentinelError class
        When: Checked with issubclass
        Then: It is a subclass of ValueError
        """
        _require_module()
        assert issubclass(UnresolvedSentinelError, ValueError)

    def test_exception_carries_sentinel_attribute(self):
        """
        Test that UnresolvedSentinelError stores the full sentinel span.

        Given: An UnresolvedSentinelError constructed with a sentinel and field_path
        When: The .sentinel attribute is accessed
        Then: It equals the sentinel span as it appeared in source
        """
        _require_module()
        exc = UnresolvedSentinelError(
            sentinel="{{riskTypoFooBar}}",
            field_path="risks[3].longDescription[0]",
        )
        assert exc.sentinel == "{{riskTypoFooBar}}"

    def test_exception_carries_field_path_attribute(self):
        """
        Test that UnresolvedSentinelError stores the field_path string.

        Given: An UnresolvedSentinelError constructed with a field_path
        When: The .field_path attribute is accessed
        Then: It equals the caller-supplied field_path string
        """
        _require_module()
        exc = UnresolvedSentinelError(
            sentinel="{{riskTypoFooBar}}",
            field_path="risks[3].longDescription[0]",
        )
        assert exc.field_path == "risks[3].longDescription[0]"

    def test_exception_message_includes_sentinel_and_field_path(self):
        """
        Test that str(UnresolvedSentinelError) includes both sentinel and field_path.

        Given: An UnresolvedSentinelError with a custom message
        When: str(exc) is evaluated
        Then: The string contains both the sentinel span and the field_path
        """
        _require_module()
        exc = UnresolvedSentinelError(
            sentinel="{{ref:cve-2024-99999}}",
            field_path="controls[2].description[0]",
            message="No matching externalReferences entry",
        )
        msg = str(exc)
        assert exc.sentinel in msg
        assert exc.field_path in msg
        assert exc.field_path == "controls[2].description[0]"

    def test_expand_to_text_raises_on_unknown_intra_id(self):
        """
        Test that expand_sentinels_to_text raises UnresolvedSentinelError for unknown intra id.

        Given: Text containing {{riskTypoFooBar}} and an intra_lookup with no such id
        When: expand_sentinels_to_text is called
        Then: UnresolvedSentinelError is raised with .sentinel == "{{riskTypoFooBar}}"
              and .field_path matching the caller's field_path argument
        """
        _require_module()
        with pytest.raises(UnresolvedSentinelError) as exc_info:
            expand_sentinels_to_text(
                "Contains {{riskTypoFooBar}} which is wrong.",
                intra_lookup={"riskOther": "Other Risk"},
                ref_lookup={},
                field_path="risks[3].longDescription[0]",
            )
        exc = exc_info.value
        assert exc.sentinel == "{{riskTypoFooBar}}"
        assert exc.field_path == "risks[3].longDescription[0]"

    def test_expand_to_text_raises_on_unknown_ref_id(self):
        """
        Test that expand_sentinels_to_text raises UnresolvedSentinelError for unknown ref id.

        Given: Text containing {{ref:cve-2024-99999}} and a ref_lookup with no such entry
        When: expand_sentinels_to_text is called
        Then: UnresolvedSentinelError is raised with .sentinel == "{{ref:cve-2024-99999}}"
        """
        _require_module()
        with pytest.raises(UnresolvedSentinelError) as exc_info:
            expand_sentinels_to_text(
                "See {{ref:cve-2024-99999}} for the vulnerability.",
                intra_lookup=INTRA_LOOKUP,
                ref_lookup={},  # empty — no entry matches
                field_path="risks[1].longDescription[2]",
            )
        exc = exc_info.value
        assert exc.sentinel == "{{ref:cve-2024-99999}}"
        assert exc.field_path == "risks[1].longDescription[2]"

    def test_expand_to_items_raises_on_unknown_intra_id(self):
        """
        Test that expand_sentinels_to_items raises UnresolvedSentinelError for unknown intra id.

        Given: Text containing {{riskTypoFooBar}} and an intra_lookup with no such id
        When: expand_sentinels_to_items is called
        Then: UnresolvedSentinelError is raised with .sentinel == "{{riskTypoFooBar}}"
        """
        _require_module()
        with pytest.raises(UnresolvedSentinelError) as exc_info:
            expand_sentinels_to_items(
                "Contains {{riskTypoFooBar}} which is wrong.",
                intra_lookup={},
                ref_lookup={},
                field_path="risks[3].longDescription[0]",
            )
        exc = exc_info.value
        assert exc.sentinel == "{{riskTypoFooBar}}"
        assert exc.field_path == "risks[3].longDescription[0]"

    def test_expand_to_items_raises_on_unknown_ref_id(self):
        """
        Test that expand_sentinels_to_items raises UnresolvedSentinelError for unknown ref id.

        Given: Text containing {{ref:cve-2024-99999}} and an empty ref_lookup
        When: expand_sentinels_to_items is called
        Then: UnresolvedSentinelError is raised with the correct sentinel span and field_path
        """
        _require_module()
        with pytest.raises(UnresolvedSentinelError) as exc_info:
            expand_sentinels_to_items(
                "See {{ref:cve-2024-99999}}.",
                intra_lookup=INTRA_LOOKUP,
                ref_lookup={},
                field_path="controls[0].description[1]",
            )
        exc = exc_info.value
        assert exc.sentinel == "{{ref:cve-2024-99999}}"
        assert exc.field_path == "controls[0].description[1]"

    @pytest.mark.parametrize(
        "bad_sentinel,field_path",
        [
            ("{{riskTypoFooBar}}", "risks[0].longDescription[0]"),
            ("{{controlNonExistent}}", "controls[1].description[0]"),
            ("{{componentBogus}}", "risks[2].examples[0]"),
            ("{{personaMissing}}", "controls[0].description[2]"),
        ],
    )
    def test_expand_to_text_raises_for_various_unknown_intra_ids(self, bad_sentinel, field_path):
        """
        Test that expand_sentinels_to_text raises for various unknown intra-doc ids.

        Given: A sentinel that looks syntactically valid but has no entry in intra_lookup
        When: expand_sentinels_to_text is called
        Then: UnresolvedSentinelError is raised with the right sentinel and field_path
        """
        _require_module()
        with pytest.raises(UnresolvedSentinelError) as exc_info:
            expand_sentinels_to_text(
                f"Text with {bad_sentinel} sentinel.",
                intra_lookup={},
                ref_lookup={},
                field_path=field_path,
            )
        exc = exc_info.value
        assert exc.sentinel == bad_sentinel
        assert exc.field_path == field_path


# ============================================================================
# TestPartitionInvariant
# ============================================================================


class TestPartitionInvariant:
    """Sanity tests: every input character is accounted for in the output."""

    def test_to_text_reconstructs_input_modulo_sentinel_substitution(self):
        """
        Test that expand_sentinels_to_text accounts for every input character.

        Given: A string with text and sentinels
        When: expand_sentinels_to_text is called
        Then: The result equals what you would get by substituting the sentinel spans
              in the original string; no characters are lost or duplicated

        The invariant: result == input.replace(sentinel_span, title_substitution)
        for each sentinel, applied in source order.
        """
        _require_module()
        input_text = "Before {{riskPromptInjection}} middle {{ref:cwe-89}} after."
        result = expand_sentinels_to_text(
            input_text,
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].longDescription[0]",
        )
        expected = (
            "Before Prompt Injection middle "
            "[CWE-89: Improper Neutralization of SQL Commands](https://cwe.mitre.org/data/definitions/89.html)"
            " after."
        )
        assert result == expected

    def test_to_items_string_reconstruction_matches_input(self):
        """
        Test that concatenating all string segments from expand_sentinels_to_items
        (with sentinel spans replaced by sentinel id/title) reconstructs the input.

        Given: A string with text and one intra sentinel
        When: expand_sentinels_to_items is called
        Then: Joining the text parts and substituting sentinel spans reconstructs the input

        This is the partition invariant for the items output: no characters are lost,
        dropped, or duplicated by the tokenization + expansion process.
        """
        _require_module()
        input_text = "Before {{riskPromptInjection}} after."
        result = expand_sentinels_to_items(
            input_text,
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].longDescription[0]",
        )
        # Reconstruct: strings pass through, sentinels contribute their span (for comparison)
        reconstructed_parts = []
        for item in result:
            if isinstance(item, str):
                reconstructed_parts.append(item)
            elif isinstance(item, dict) and item["type"] == "ref":
                # The sentinel span is {{<id>}}, so the reconstruction substitutes back
                reconstructed_parts.append(f"{{{{{item['id']}}}}}")
            elif isinstance(item, dict) and item["type"] == "link":
                # Ref sentinels are {{ref:<id>}} in source; find the ref_lookup key
                for ref_id, ref_data in REF_LOOKUP.items():
                    if ref_data == {"title": item["title"], "url": item["url"]}:
                        reconstructed_parts.append(f"{{{{ref:{ref_id}}}}}")
                        break
        assert "".join(reconstructed_parts) == input_text

    def test_to_items_no_empty_strings_dropped_from_between_sentinels(self):
        """
        Test the drop-empty invariant: no empty strings appear in items output.

        Given: Adjacent sentinels with empty/whitespace TEXT between them
        When: expand_sentinels_to_items is called
        Then: No empty string ('') appears in the result list

        This is a critical invariant: empty-string items would cause schema validation
        issues since string items in the prose schema allow empty strings at the
        item level (the schema has no minLength on string items), but we want to
        keep the output clean and consistent with normalize_text_entries NIT-08.
        """
        _require_module()
        # Adjacent sentinels, no whitespace
        result = expand_sentinels_to_items(
            "{{riskPromptInjection}}{{ref:cwe-89}}",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].examples[0]",
        )
        assert "" not in result

    def test_to_text_no_op_on_whitespace_only_string(self):
        """
        Test that a whitespace-only string is returned unchanged by expand_sentinels_to_text.

        Given: A whitespace-only string (no sentinels)
        When: expand_sentinels_to_text is called
        Then: The exact whitespace string is returned (no stripping)
        """
        _require_module()
        result = expand_sentinels_to_text(
            "   \t  ",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="risks[0].shortDescription[0]",
        )
        assert result == "   \t  "

    def test_to_items_on_text_only_string_returns_exact_input(self):
        """
        Test that a string with no sentinels is returned unchanged as a single item.

        Given: A plain text string "Hello, world."
        When: expand_sentinels_to_items is called
        Then: Returns exactly ["Hello, world."] — the input is not stripped or modified
        """
        _require_module()
        result = expand_sentinels_to_items(
            "Hello, world.",
            intra_lookup=INTRA_LOOKUP,
            ref_lookup=REF_LOOKUP,
            field_path="controls[0].description[0]",
        )
        assert result == ["Hello, world."]


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Total tests: ~40 (across 4 test classes)
- TestExpandSentinelsToText (11):       plain passthrough, intra/ref substitution,
                                         custom link_format, multiple sentinels,
                                         whitespace preservation (critical regression),
                                         bold/italic passthrough, empty string, component, persona
- TestExpandSentinelsToItems (11):      plain → single string, intra → ref item,
                                         ref → link item, surrounding text, adjacent sentinels,
                                         empty-between-sentinels dropped, empty input,
                                         multiple sentinels, bold/italic concatenated,
                                         INVALID_SENTINEL passthrough, component sentinel
- TestUnresolvedSentinelError (9+4par): ValueError subclass, .sentinel/.field_path attrs,
                                         message includes both, raises from _to_text (intra+ref),
                                         raises from _to_items (intra+ref), parametrized intra miss
- TestPartitionInvariant (5):            _to_text reconstructs modulo substitution,
                                         _to_items reconstruction, no empty strings,
                                         whitespace-only passthrough, text-only unchanged

Coverage target: 90%+ on scripts/hooks/_sentinel_expansion.py

Key design constraints pinned by these tests:
  - expand_sentinels_to_text: TEXT spans passed through verbatim (no .strip())
  - expand_sentinels_to_items: empty/whitespace TEXT spans dropped (NIT-08 parity)
  - INVALID_* tokens pass through by .value in both functions
  - UnresolvedSentinelError is a ValueError with .sentinel and .field_path attributes
"""

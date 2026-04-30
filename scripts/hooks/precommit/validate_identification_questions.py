#!/usr/bin/env python3
"""
Pre-commit lint: structural rules for identificationQuestions in personas.yaml.

Enforces four rules from risk-map/docs/contributing/identification-questions-style-guide.md
against every non-deprecated persona that has an identificationQuestions field:

  Rule 1 — Count:            5 ≤ len(questions) ≤ 7
  Rule 2 — Second-person:    every question starts with an approved opener
  Rule 3 — Parenthetical:    each parenthetical contains ≤ 4 items
  Rule 4 — e.g. not i.e.:   parentheticals use e.g., not i.e.

Ships warn-only (exit 0 with stderr warnings). Pass --block to fail on any violation.
"""

import argparse
import json
import re
import sys
from typing import NoReturn

import yaml

# Hook name used as the stderr prefix on every warning line.
HOOK_NAME = "validate-identification-questions"

# Approved second-person openers (case-sensitive, trailing space required).
# Per style guide § Format: Do you / Are you / Does your.
# NOT "Is your" — locked per code-reviewer phase.
APPROVED_OPENERS = ("Do you ", "Are you ", "Does your ")

# Count bounds for identificationQuestions.
COUNT_MIN = 5
COUNT_MAX = 7

# Maximum items allowed inside a single parenthetical.
PAREN_ITEM_LIMIT = 4


# ---------------------------------------------------------------------------
# Schema helper
# ---------------------------------------------------------------------------


def load_persona_ids_from_schema(schema_path: str) -> list[str]:
    """
    Read persona ID enum from personas.schema.json.

    Reads definitions.persona.properties.id.enum — the closed list of all
    known persona IDs (current + deprecated).

    Args:
        schema_path: Path to personas.schema.json.

    Returns:
        List of persona ID strings from the schema enum.
    """
    with open(schema_path, "r", encoding="utf-8") as fh:
        schema = json.load(fh)
    return schema["definitions"]["persona"]["properties"]["id"]["enum"]


# ---------------------------------------------------------------------------
# Rule 1 — Count
# ---------------------------------------------------------------------------


def check_count_rule(persona_id: str, questions: list) -> list[str]:
    """
    Check that the question count is within the 5–7 range.

    Args:
        persona_id: Persona ID (used in warning text for context).
        questions:  The identificationQuestions list.

    Returns:
        List of warning strings. Empty list means the rule passes.
    """
    n = len(questions)
    if n < COUNT_MIN:
        return [f"count below floor (got {n}, need {COUNT_MIN}-{COUNT_MAX})"]
    if n > COUNT_MAX:
        return [f"count above ceiling (got {n}, need {COUNT_MIN}-{COUNT_MAX})"]
    return []


# ---------------------------------------------------------------------------
# Rule 2 — Second-person opener
# ---------------------------------------------------------------------------


def check_opener_rule(persona_id: str, index: int, question: str) -> list[str]:
    """
    Check that a question starts with an approved second-person opener.

    Approved set: ("Do you ", "Are you ", "Does your ") — case-sensitive.

    Args:
        persona_id: Persona ID (context only).
        index:      Zero-based position of the question in the array.
        question:   The question string.

    Returns:
        List with one warning string if the opener is not approved; empty otherwise.
    """
    if any(question.startswith(opener) for opener in APPROVED_OPENERS):
        return []
    approved_display = ", ".join(f'"{o.strip()}"' for o in APPROVED_OPENERS)
    return [f"opener not in approved set ({approved_display}): {question!r}"]


# ---------------------------------------------------------------------------
# Rule 3 — Parenthetical cardinality
# ---------------------------------------------------------------------------

# Regex to find the body of every top-level parenthetical in a string.
# We extract content between matching ( and ) at depth 1 (not nested).
_PAREN_BODY_RE = re.compile(r"\(([^()]*(?:\([^()]*\)[^()]*)*)\)")


_PAREN_INTRO_RE = re.compile(r"^(e\.g\.|i\.e\.)\s*,?\s*", re.IGNORECASE)


def _count_paren_items(body: str) -> int:
    """
    Count list items inside a parenthetical body.

    Items are separated by ',' or ' or ' (space-padded to avoid splitting
    words that contain "or"). Separators inside nested parentheses (depth >= 1)
    are treated as part of the current item, not as boundaries.

    A leading "e.g.," or "i.e.," abbreviation is stripped before counting
    so it is not tallied as an item itself.

    Args:
        body: Text between the outer parentheses (may contain nested parens).

    Returns:
        Number of distinct items.
    """
    # Strip leading "e.g.," / "i.e.," abbreviation — not a list item.
    body = _PAREN_INTRO_RE.sub("", body).strip()

    if not body:
        return 0

    # Walk character-by-character tracking nesting depth.
    # ',' and ' or ' are only item separators at depth 0.
    items: list[str] = []
    current: list[str] = []
    depth = 0
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "(":
            depth += 1
            current.append(ch)
            i += 1
        elif ch == ")":
            # Guard against malformed input with unmatched closing paren.
            depth = max(0, depth - 1)
            current.append(ch)
            i += 1
        elif depth == 0 and ch == ",":
            items.append("".join(current).strip())
            current = []
            i += 1
        elif depth == 0 and body[i : i + 4] == " or ":
            items.append("".join(current).strip())
            current = []
            i += 4
        else:
            current.append(ch)
            i += 1

    # Flush the last segment.
    if current:
        items.append("".join(current).strip())

    # Filter out empty strings produced by trailing separators.
    return len([x for x in items if x])


def check_parenthetical_cardinality_rule(persona_id: str, index: int, question: str) -> list[str]:
    """
    Check that no parenthetical in the question exceeds PAREN_ITEM_LIMIT items.

    Each parenthetical is evaluated independently. Multiple offending
    parentheticals in one question produce one warning per parenthetical.

    Args:
        persona_id: Persona ID (context only).
        index:      Zero-based position of the question.
        question:   The question string.

    Returns:
        List of warning strings, one per offending parenthetical.
    """
    warnings = []
    for match in _PAREN_BODY_RE.finditer(question):
        body = match.group(1)
        count = _count_paren_items(body)
        if count > PAREN_ITEM_LIMIT:
            warnings.append(f"parenthetical has {count} items (limit {PAREN_ITEM_LIMIT}): ({body})")
    return warnings


# ---------------------------------------------------------------------------
# Rule 4 — e.g. not i.e.
# ---------------------------------------------------------------------------

# Match parentheticals that open with i.e. (literal period required).
_IE_PAREN_RE = re.compile(r"\(i\.e\.")


def check_eg_not_ie_rule(persona_id: str, index: int, question: str) -> list[str]:
    """
    Check that parentheticals use "e.g." rather than "i.e.".

    One warning per (i.e., ...) parenthetical. "i.e." outside parentheses
    is not flagged — the rule targets only parenthetical usage.

    Args:
        persona_id: Persona ID (context only).
        index:      Zero-based position of the question.
        question:   The question string.

    Returns:
        List of warning strings, one per offending (i.e., ...) parenthetical.
    """
    warnings = []
    for match in _IE_PAREN_RE.finditer(question):
        # Verify the match is inside a parenthetical by checking for the opening '('.
        # The regex already anchors on '\(' so every match is inside a paren.
        warnings.append(
            f"parenthetical uses i.e. (should be e.g.): found at position {match.start()} in {question!r}"
        )
    return warnings


# ---------------------------------------------------------------------------
# File-level validation
# ---------------------------------------------------------------------------


def _format_warning(yaml_path: str, persona_id: str, field_index: str, reason: str) -> str:
    """
    Format a single warning line per the required stderr format.

    Format: validate-identification-questions: <file>:<persona-id>:identificationQuestions[<n>]: <reason>

    Args:
        yaml_path:   Path to the YAML file (as provided by the caller).
        persona_id:  Persona ID string.
        field_index: Index token — "[*]" for array-level (count), "[n]" for per-question.
        reason:      Human-readable rule violation description.

    Returns:
        Formatted warning string (does not include a trailing newline).
    """
    return f"{HOOK_NAME}: {yaml_path}:{persona_id}:identificationQuestions{field_index}: {reason}"


def validate_personas_file(yaml_path: str, schema_path: str, block: bool) -> list[str]:
    """
    Validate identificationQuestions in every non-deprecated persona.

    Iterates over all persona entries present in the YAML file (not over the
    schema enum). Skips personas with deprecated: true. Applies all four
    structural rules to each non-deprecated persona that has an
    identificationQuestions field.

    In warn-only mode (block=False) returns the full list of warning strings.
    In block mode (block=True) calls sys.exit(1) if any warnings are found,
    emitting each warning to stderr first.

    Args:
        yaml_path:   Path to personas.yaml.
        schema_path: Accepted for CLI compatibility; reserved. Validation
            iterates the YAML directly; the schema enum is not consulted here.
        block:       If True, exit non-zero on any violation.

    Returns:
        List of formatted warning strings (only returned in warn-only mode;
        block mode exits instead).
    """
    with open(yaml_path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)

    personas = data.get("personas", [])
    all_warnings: list[str] = []

    for persona in personas:
        persona_id = persona.get("id", "<unknown>")

        # Deprecated personas are fully exempt from all structural rules.
        if persona.get("deprecated", False):
            continue

        questions = persona.get("identificationQuestions")
        # Field absence is allowed (optional per ADR-021 D8); no warning.
        if questions is None:
            continue

        # Rule 1 — Count (array-level; index token is [*])
        for reason in check_count_rule(persona_id, questions):
            all_warnings.append(_format_warning(yaml_path, persona_id, "[*]", reason))

        # Rules 2, 3, 4 — per-question
        for idx, question in enumerate(questions):
            idx_token = f"[{idx}]"

            for reason in check_opener_rule(persona_id, idx, question):
                all_warnings.append(_format_warning(yaml_path, persona_id, idx_token, reason))

            for reason in check_parenthetical_cardinality_rule(persona_id, idx, question):
                all_warnings.append(_format_warning(yaml_path, persona_id, idx_token, reason))

            for reason in check_eg_not_ie_rule(persona_id, idx, question):
                all_warnings.append(_format_warning(yaml_path, persona_id, idx_token, reason))

    if block and all_warnings:
        for w in all_warnings:
            print(w, file=sys.stderr)
        sys.exit(1)

    return all_warnings


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

# Default schema path relative to repo root (used when --schema is not given).
_DEFAULT_SCHEMA = "risk-map/schemas/personas.schema.json"


def main(argv: list[str]) -> NoReturn:
    """
    CLI entry point. Always calls sys.exit().

    Pre-commit passes matched filenames as positional args. The --schema flag
    is optional; if absent, the schema path defaults to the repo-root-relative
    location (suitable for pre-commit invocations from the repo root).

    Args:
        argv: Argument list (typically sys.argv[1:] or injected by tests).
    """
    parser = argparse.ArgumentParser(
        description="Lint identificationQuestions structural rules in personas.yaml.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  %(prog)s risk-map/yaml/personas.yaml\n"
            "  %(prog)s risk-map/yaml/personas.yaml --schema risk-map/schemas/personas.schema.json\n"
            "  %(prog)s risk-map/yaml/personas.yaml --schema ... --block\n"
        ),
    )
    parser.add_argument("files", nargs="+", help="Path(s) to personas.yaml (pre-commit passes these).")
    parser.add_argument(
        "--schema",
        default=_DEFAULT_SCHEMA,
        help="Path to personas.schema.json (default: %(default)s).",
    )
    parser.add_argument(
        "--block",
        action="store_true",
        default=False,
        help="Exit non-zero on any rule violation (default: warn-only, exit 0).",
    )
    args = parser.parse_args(argv)

    all_warnings: list[str] = []
    for yaml_path in args.files:
        # In block mode, validate_personas_file exits on violation; in warn mode it returns.
        file_warnings = validate_personas_file(yaml_path, args.schema, block=args.block)
        all_warnings.extend(file_warnings)

    # Warn-only mode: emit all warnings to stderr and exit 0.
    for w in all_warnings:
        print(w, file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main(sys.argv[1:])

#!/usr/bin/env python3
"""
Advisory report of one-way control mentions in `controls.yaml` guidance.

A pair `A -> B` is reported when A's `guidance` mentions `{{B}}` (a `{{control...}}`
sentinel) and B's `guidance` does not mention `{{A}}`. A B with no `guidance`, or absent
from the file, does not reciprocate. Only `guidance` is scanned (flat items and nested
sub-lists); `description` is ignored, and self-mentions are skipped.

The report is a review aid per DG10 of
risk-map/docs/design/control-description-and-guidance.md: whether a listed mention is a
distinction or a dependency is a reviewer judgment. Findings never fail a build, so the
exit code is 0 whenever the file is readable. Unusable input (missing file, invalid YAML,
no `controls` list, malformed entry) exits 1 with an error on stderr.

Usage: report_one_way_control_mentions.py [controls.yaml]
"""

import argparse
import sys
from pathlib import Path

import yaml

# Ensure scripts/hooks is on sys.path so `precommit.*` imports work when run as a script.
_HOOKS_DIR = Path(__file__).resolve().parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from precommit._prose_tokens import TokenKind, tokenize  # noqa: E402

DEFAULT_PATH = Path("risk-map/yaml/controls.yaml")


def _guidance_strings(node):
    """Yield every string in `guidance`, descending into nested lists."""
    if isinstance(node, str):
        yield node
    elif isinstance(node, list):
        for item in node:
            yield from _guidance_strings(item)


def _control_ids(text: str) -> set[str]:
    """Return control ids from `{{control...}}` sentinels in `text`, including inside emphasis."""
    found: set[str] = set()
    for token in tokenize(text):
        # SENTINEL_INTRA covers risk/control/component/persona; keep controls only.
        if token.kind == TokenKind.SENTINEL_INTRA and token.value.startswith("{{control"):
            found.add(token.value[2:-2])
        # The tokenizer emits a complete emphasis span as one opaque token, so a sentinel
        # inside it is not tokenized. Strip the delimiters and re-tokenize the inner text.
        elif token.kind in (TokenKind.BOLD, TokenKind.ITALIC) and token.shape == "complete":
            width = 2 if token.kind == TokenKind.BOLD else 1
            found |= _control_ids(token.value[width:-width])
    return found


def _mentions(guidance) -> set[str]:
    """Return the control ids mentioned via `{{control...}}` sentinels in `guidance`."""
    found: set[str] = set()
    for text in _guidance_strings(guidance):
        found |= _control_ids(text)
    return found


def load_mentions(path: Path) -> dict[str, set[str]]:
    """Map each control id to the control ids its guidance mentions.

    Raises ValueError with an actionable message on unusable input.
    """
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"cannot parse {path}: {exc}") from exc

    controls = data.get("controls") if isinstance(data, dict) else None
    if not isinstance(controls, list):
        raise ValueError(f"{path}: expected a top-level `controls` list")

    mentions: dict[str, set[str]] = {}
    for index, entry in enumerate(controls):
        if not isinstance(entry, dict) or not isinstance(entry.get("id"), str):
            raise ValueError(f"{path}: controls[{index}] is not a mapping with a string `id`")
        if entry["id"] in mentions:
            raise ValueError(f"{path}: duplicate control id `{entry['id']}`")
        mentions[entry["id"]] = _mentions(entry.get("guidance"))
    return mentions


def find_one_way(mentions: dict[str, set[str]]) -> list[tuple[str, str]]:
    """Return sorted (source, target) pairs where the target does not mention the source."""
    return sorted(
        (source, target)
        for source, targets in mentions.items()
        for target in targets
        if target != source and source not in mentions.get(target, set())
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n\n")[0])
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        default=DEFAULT_PATH,
        help=f"controls YAML file (default: {DEFAULT_PATH})",
    )
    args = parser.parse_args(argv)

    try:
        pairs = find_one_way(load_mentions(args.path))
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if not pairs:
        print("no one-way mentions")
    for source, target in pairs:
        print(f"{source} -> {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

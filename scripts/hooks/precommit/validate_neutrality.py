#!/usr/bin/env python3
"""
Pre-commit lint: enforce ADR-033 D2a/D5 vendor-neutrality for shipped surfaces.

`scripts/agents/**` and `scripts/skills/**` are the two authoring surfaces
that ship in this repository. Prose in those trees must not name a specific
AI harness product, company, CLI entry point, or model identifier; must not
embed harness-invocation stage directions (`<invoke ... tool>`,
`subagent_type`, "auto-loads"/"auto-triggers"); and must not reference
harness-specific config paths (`.claude/`, `.cursor/`, etc.). Framework-
authority references (MITRE, NIST, OWASP, ISO, EU AI Act, STRIDE) are
legitimate content and are allowlisted by span, so a denylist hit is only
suppressed where it actually overlaps an allowlist match on the same line —
not for the whole line.

A separate structural rule governs YAML frontmatter: a `SKILL.md` file may
declare only `name`/`description`; an agent `.md` file must not declare a
runtime-binding key (`tools`, `model`, `color`, `allowed-tools`/
`allowed_tools`) if it happens to carry a frontmatter block at all.

`scripts/hooks/precommit/_neutrality_data.py` holds the denylist/allowlist
patterns; this module only implements the scan and CLI.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# Ensure scripts/hooks is on sys.path so ``precommit.*`` imports work both
# when this file is executed directly (pre-commit's `entry:` and manual CLI
# use) and when it is imported as part of the precommit package (e.g.
# ``python3 -m precommit.validate_neutrality``). Mirrors the idiom in
# validate_yaml_prose_subset.py / validate_prose_references.py.
_HOOKS_DIR = Path(__file__).resolve().parent.parent
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import precommit._neutrality_data as data  # noqa: E402

HOOK_NAME = "validate-neutrality"

# Denylist categories scanned per line: (compiled pattern, human-readable
# description used to build the violation message).
_DENYLIST_CATEGORIES: tuple[tuple[re.Pattern[str], str], ...] = (
    (data.VENDOR_PRODUCT_RE, "names a specific AI harness vendor, product, or company"),
    (data.MODEL_IDENTIFIER_RE, "names a specific model identifier"),
    (data.CLI_ENTRYPOINT_RE, "names a specific harness CLI entry point"),
    (data.INVOKE_TOOL_RE, "embeds a harness-invocation stage direction"),
    (data.SUBAGENT_TYPE_RE, "embeds a harness-specific subagent_type token"),
    (data.AUTO_LOAD_TRIGGER_RE, "embeds harness-specific auto-load/auto-trigger phrasing"),
    (data.HARNESS_CONFIG_PATH_RE, "references a harness-specific config path"),
)

# Frontmatter structural rules (ADR-033 category 3).
SKILL_FRONTMATTER_ALLOWED_KEYS = frozenset({"name", "description"})
_AGENT_FRONTMATTER_FORBIDDEN_KEYS_NORMALIZED = frozenset({"tools", "model", "color", "allowed-tools"})

# Text-file extensions eligible for discovery. Restricting discovery to known
# text extensions (rather than a bare `rglob("*")` plus a try/except around
# the decode) keeps a binary file staged under scripts/agents/** or
# scripts/skills/** (e.g. a future skill package's bundled icon or sample
# data) from ever reaching `path.read_text()` and crashing the hook with
# `UnicodeDecodeError`. Mirrors how `discover_workflow_files` in
# validate_workflow_uses_pinning.py restricts to `*.yml`.
_DISCOVERABLE_TEXT_EXTENSIONS = frozenset({".md", ".py", ".yaml", ".yml", ".json", ".txt"})


@dataclass(frozen=True)
class Violation:
    """A single vendor-neutrality or frontmatter-structure violation."""

    path: Path
    line: int
    token: str
    message: str


def _allowlist_spans(line: str) -> list[tuple[int, int]]:
    """Return every framework-authority allowlist match span found in `line`."""
    spans: list[tuple[int, int]] = []
    for pattern in data.FRAMEWORK_ALLOWLIST_PATTERNS:
        spans.extend((match.start(), match.end()) for match in pattern.finditer(line))
    return spans


def _overlaps(span: tuple[int, int], others: list[tuple[int, int]]) -> bool:
    """True if `span` intersects any span in `others`."""
    start, end = span
    return any(start < other_end and other_start < end for other_start, other_end in others)


def _scan_line(path: Path, line_number: int, line: str) -> list[Violation]:
    """
    Scan one source line for denylist hits, suppressing allowlist overlaps.

    Suppression is per-match: an allowlisted span (e.g. "MITRE ATLAS") only
    suppresses a denylist hit whose span it actually overlaps, so a
    denylisted term sharing a line with legitimate framework content (but not
    overlapping it) is still flagged.
    """
    allow_spans = _allowlist_spans(line)
    violations: list[Violation] = []

    for pattern, description in _DENYLIST_CATEGORIES:
        for match in pattern.finditer(line):
            if _overlaps((match.start(), match.end()), allow_spans):
                continue
            # Strip enclosing backticks (CLI-entrypoint matches) for a clean token.
            token = match.group(0).strip("`")
            violations.append(
                Violation(
                    path=path,
                    line=line_number,
                    token=token,
                    message=f"{description}: {token!r}",
                )
            )

    return violations


def _find_key_line(lines: list[str], start: int, end: int, key: str) -> int:
    """
    Return the 1-based source line number of `key:` within lines[start:end].

    Falls back to the first line of the frontmatter block if the exact key
    line cannot be located (should not happen for well-formed YAML).
    """
    for index in range(start, end):
        if lines[index].strip().startswith(f"{key}:"):
            return index + 1
    return start + 1


def _frontmatter_violations(path: Path, lines: list[str]) -> list[Violation]:
    """
    Check a YAML frontmatter block (if present) against structural rules.

    SKILL.md files may declare only `name`/`description`. Agent `.md` files
    must not declare a runtime-binding key. A file with no frontmatter block,
    or an unterminated/malformed one, is out of scope for this check — the
    former is trivially compliant, the latter is another validator's job.

    Note: a UTF-8-BOM-prefixed file has a non-"-" first character on
    `lines[0]`, so it is treated as having no frontmatter block. BOM
    stripping is not implemented; this is a documented gap, not a fix target.
    """
    if not lines or lines[0].strip() != "---":
        return []

    closing_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing_index = index
            break
    if closing_index is None:
        return []

    block_lines = lines[1:closing_index]
    try:
        frontmatter = yaml.safe_load("\n".join(block_lines)) or {}
    except yaml.YAMLError:
        return []

    if not isinstance(frontmatter, dict):
        return []

    # Exact-case match on the fixed "SKILL.md" convention. A misnamed
    # "skill.md"/"Skill.md" falls through to the more permissive agent rule
    # rather than the skill rule — not a bug, just the boundary of this check.
    is_skill = path.name == "SKILL.md"
    if is_skill:
        offending_keys = [key for key in frontmatter if key not in SKILL_FRONTMATTER_ALLOWED_KEYS]
        rule = "SKILL.md frontmatter may declare only 'name' and 'description'"
    else:
        offending_keys = [
            key for key in frontmatter if key.replace("_", "-") in _AGENT_FRONTMATTER_FORBIDDEN_KEYS_NORMALIZED
        ]
        rule = "agent frontmatter must not declare a runtime-binding key"

    violations = []
    for key in offending_keys:
        line_number = _find_key_line(lines, 1, closing_index, key)
        violations.append(Violation(path=path, line=line_number, token=key, message=f"{rule}: found {key!r}"))
    return violations


def validate_file(path: Path) -> list[Violation]:
    """
    Validate one file against the ADR-033 denylist/allowlist and frontmatter rules.

    Args:
        path: File to validate.

    Returns:
        List of violations, empty if the file is clean.
    """
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    violations: list[Violation] = []
    for line_number, line in enumerate(lines, start=1):
        violations.extend(_scan_line(path, line_number, line))
    violations.extend(_frontmatter_violations(path, lines))

    return violations


def discover_neutral_surface_files(root: Path) -> list[Path]:
    """
    Return files under `root/scripts/agents/**` and `root/scripts/skills/**`.

    Deliberately targets only these two subtrees directly rather than walking
    a common `scripts/` ancestor and filtering — that would risk reaching
    `scripts/hooks/`, this checker's own home and the one place denylist
    tokens legitimately appear as detection data.

    Args:
        root: Repository root to scan.

    Only files with a known text extension (`_DISCOVERABLE_TEXT_EXTENSIONS`)
    are returned; a non-text file (e.g. a bundled icon or sample data asset)
    is silently excluded rather than crashing `validate_file` on decode.

    Returns:
        Discovered files, agents subtree first, skills subtree second, each
        subtree sorted. Either subtree may be empty (or absent) without error.
    """
    discovered: list[Path] = []
    for subdir in ("scripts/agents", "scripts/skills"):
        base = root / subdir
        if not base.is_dir():
            continue
        discovered.extend(
            sorted(
                path for path in base.rglob("*") if path.is_file() and path.suffix in _DISCOVERABLE_TEXT_EXTENSIONS
            )
        )
    return discovered


def format_violation(violation: Violation) -> str:
    """Format one violation for stderr with actionable file:line context."""
    return f"{HOOK_NAME}: {violation.path}:{violation.line}: {violation.message}"


def main(argv: list[str]) -> int:
    """
    CLI entry point for pre-commit and manual validation.

    Pre-commit passes matched filenames explicitly; those are validated as-is
    with no re-filtering by scope, since pre-commit's own `files:` regex
    already restricts which files reach this hook. With no file arguments,
    the command self-discovers via `discover_neutral_surface_files` from the
    current working directory.

    Returns:
        1 if any violations are found, else 0.
    """
    parser = argparse.ArgumentParser(description="Validate ADR-033 vendor-neutrality for shipped surfaces.")
    parser.add_argument("files", nargs="*", help="Files to validate.")
    args = parser.parse_args(argv)

    files = [Path(file) for file in args.files] if args.files else discover_neutral_surface_files(Path.cwd())

    all_violations: list[Violation] = []
    for path in files:
        if not path.exists():
            continue
        all_violations.extend(validate_file(path))

    for violation in all_violations:
        print(format_violation(violation), file=sys.stderr)

    return 1 if all_violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

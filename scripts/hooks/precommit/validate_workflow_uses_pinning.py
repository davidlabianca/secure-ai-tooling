#!/usr/bin/env python3
"""
Pre-commit lint: enforce ADR-024 pinning for GitHub Actions `uses:` references.

Parses each workflow file via PyYAML's `yaml.compose()` to obtain an AST with
source line numbers. Walking the AST finds every `uses:` key at any nesting
depth, including quoted keys and keys inside matrix-strategy mappings.

For each `uses:` value the validator re-reads the corresponding source line to
extract any trailing `# comment` (PyYAML does not preserve comments). If the
value is a block scalar (folded `>` or literal `|`), it spans multiple source
lines and can carry no same-line comment; that is an ADR-024 D6 violation.

ADR-024 D6: external references must be pinned to a full 40-character SHA with
a same-line ` # vX.Y.Z` comment (exactly one space before and after `#`).

ADR-024 D7: `docker://` references produce an advisory warning (stderr prefix
`validate-workflow-uses-pinning: warning:`) but do not fail the build.

Local `./...` references are exempt from all pinning rules.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

HOOK_NAME = "validate-workflow-uses-pinning"

# Matches owner/repo[@...] with an exactly-40-hex SHA after `@`.
PINNED_EXTERNAL_REF_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*@[0-9A-Fa-f]{40}$")

# Matches values where a valid SHA pin was written but `#` was appended without
# a preceding space (e.g., `owner/repo@<sha># v1.2.3`). PyYAML absorbs the
# `# ...` into the scalar value when there is no space before `#`.
_SHA_NO_SPACE_HASH_RE = re.compile(r"^([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*@[0-9A-Fa-f]{40})#")

# Matches a full semver version comment: vMAJOR.MINOR.PATCH[-prerelease][+build]
SEMVER_COMMENT_RE = re.compile(
    r"v(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?"
    r"(?:\+[0-9A-Za-z.-]+)?"
)


@dataclass(frozen=True)
class Violation:
    """A single workflow `uses:` pinning violation or advisory warning."""

    path: Path
    line: int
    reference: str
    message: str


def _walk_nodes(node: yaml.Node) -> list[tuple[yaml.ScalarNode, yaml.Node]]:
    """
    Recursively collect (key_node, value_node) pairs where the key is `uses`.

    Descends into MappingNode and SequenceNode values at any depth. Quoted keys
    parse to the same string as unquoted keys in PyYAML, so no special handling
    is needed for quoted `uses:` keys.

    Args:
        node: A PyYAML node (MappingNode, SequenceNode, or ScalarNode).

    Returns:
        List of (key_node, value_node) tuples for every `uses:` key found.
    """
    results: list[tuple[yaml.ScalarNode, yaml.Node]] = []

    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            if isinstance(key_node, yaml.ScalarNode) and key_node.value == "uses":
                results.append((key_node, value_node))
            # Always recurse into both sides of the mapping.
            results.extend(_walk_nodes(key_node))
            results.extend(_walk_nodes(value_node))
    elif isinstance(node, yaml.SequenceNode):
        for item in node.value:
            results.extend(_walk_nodes(item))

    return results


def _extract_trailing_comment(source_lines: list[str], value_node: yaml.Node, resolved_value: str) -> str | None:
    """
    Find the inline comment that follows the scalar value on its source line.

    Strategy: locate the source line at the value node's start_mark. If the
    resolved value string appears as a substring of that line, everything after
    it (stripped of leading whitespace and a single `#`) is the comment. If the
    resolved value is not on the same line (e.g., a block scalar), return None.

    This works for the inline scalar case — the common and only valid ADR-024
    form. Block scalars (folded `>` / literal `|`) never appear on the same
    source line as their resolved content; None correctly signals no comment.

    Args:
        source_lines: All lines of the workflow file (0-indexed).
        value_node:   PyYAML node for the `uses:` value.
        resolved_value: The string PyYAML resolved from the node.

    Returns:
        The comment text (e.g., `v6.0.2`) if present, or None.
    """
    line_index = value_node.start_mark.line
    if line_index >= len(source_lines):
        return None

    source_line = source_lines[line_index]

    # Strip the YAML-resolved value from the source line to isolate the comment.
    # The resolved value must appear literally in the source line for inline scalars.
    pos = source_line.find(resolved_value)
    if pos == -1:
        # Block scalar: value is not on the same line as the `uses:` key.
        return None

    after_value = source_line[pos + len(resolved_value) :]
    stripped = after_value.lstrip()
    if not stripped.startswith("#"):
        return None

    # Return just the comment body (after `#` and leading space).
    return stripped[1:].lstrip()


def _check_separator(source_lines: list[str], value_node: yaml.Node, resolved_value: str) -> bool:
    """
    Return True if the value-to-comment separator is exactly ` # ` (one space each side).

    ADR-024 D6 requires exactly one space before `#` and one space after it.
    Two spaces before `#` (or no space after) is a violation.

    Args:
        source_lines:   All source lines of the workflow file (0-indexed).
        value_node:     PyYAML node for the `uses:` value.
        resolved_value: The string PyYAML resolved from the node.

    Returns:
        True if the separator is exactly ` # `, False otherwise.
    """
    line_index = value_node.start_mark.line
    if line_index >= len(source_lines):
        return False

    source_line = source_lines[line_index]
    pos = source_line.find(resolved_value)
    if pos == -1:
        return False

    after_value = source_line[pos + len(resolved_value) :]
    # Must be exactly one space, then `#`, then one space.
    return after_value.startswith(" #") and len(after_value) > 2 and after_value[2] == " "


def _validate_reference(
    path: Path,
    line_number: int,
    reference: str,
    comment: str | None,
    separator_ok: bool,
) -> tuple[Violation | None, Violation | None]:
    """
    Validate one resolved `uses:` reference value.

    Args:
        path:         Workflow file path.
        line_number:  1-based line number of the value node.
        reference:    The resolved YAML scalar string (stripped of surrounding newlines).
        comment:      Trailing comment body if found on the source line, else None.
        separator_ok: True if the separator between SHA and `#` is exactly ` # `.

    Returns:
        (error, warning) where at most one of the two is a Violation.
        Both None means the reference is valid.
    """
    if reference.startswith("./"):
        return None, None

    if reference.startswith("docker://"):
        warning = Violation(
            path=path,
            line=line_number,
            reference=reference,
            message=(
                "docker:// action references emit an advisory warning until the planned "
                "ADR-023 defines Docker pinning; see ADR-024 D7"
            ),
        )
        return None, warning

    # Detect `owner/repo@<sha>#...` (no space before `#`): PyYAML absorbs the
    # comment text into the scalar value. The SHA is intact; the violation is the
    # missing separator, not a bad SHA.
    no_space_match = _SHA_NO_SPACE_HASH_RE.match(reference)
    if no_space_match:
        return (
            Violation(
                path=path,
                line=line_number,
                reference=no_space_match.group(1),
                message="SHA-pinned external `uses:` reference is missing required ` # vX.Y.Z` semver comment",
            ),
            None,
        )

    if not PINNED_EXTERNAL_REF_RE.fullmatch(reference):
        return (
            Violation(
                path=path,
                line=line_number,
                reference=reference,
                message=(
                    "external `uses:` reference must use owner/repo[/path]@<full "
                    "40-character commit SHA>; tags, branches, missing refs, and short SHAs are not allowed"
                ),
            ),
            None,
        )

    if comment is None or not separator_ok or SEMVER_COMMENT_RE.fullmatch(comment) is None:
        return (
            Violation(
                path=path,
                line=line_number,
                reference=reference,
                message="SHA-pinned external `uses:` reference is missing required ` # vX.Y.Z` semver comment",
            ),
            None,
        )

    return None, None


def validate_file(path: Path) -> tuple[list[Violation], list[Violation]]:
    """
    Validate every `uses:` entry in one workflow file using the PyYAML AST.

    Args:
        path: Path to a GitHub Actions workflow `.yml` file.

    Returns:
        (errors, warnings) — errors cause exit code 1; warnings are advisory only.
    """
    errors: list[Violation] = []
    warnings: list[Violation] = []

    raw = path.read_text(encoding="utf-8")
    # splitlines() handles both LF and CRLF transparently.
    source_lines = raw.splitlines()

    try:
        root = yaml.compose(raw)
    except yaml.YAMLError as exc:
        # Surfacing a parse error as a violation avoids a hard crash.
        mark = getattr(exc, "problem_mark", None)
        line_number = (mark.line + 1) if mark is not None else 1
        errors.append(
            Violation(
                path=path,
                line=line_number,
                reference="",
                message=f"workflow file is not valid YAML: {exc}",
            )
        )
        return errors, warnings

    if root is None:
        # Empty file — nothing to validate.
        return errors, warnings

    for _key_node, value_node in _walk_nodes(root):
        if not isinstance(value_node, yaml.ScalarNode):
            # Non-scalar `uses:` values are structurally invalid YAML for
            # GitHub Actions but won't be caught here; schema validation handles it.
            continue

        # 1-based line number of where the value starts in the source.
        line_number = value_node.start_mark.line + 1

        # PyYAML resolves the scalar (handles folded/literal block scalars).
        # Strip trailing newlines that PyYAML appends for block scalars.
        resolved = value_node.value.strip()

        comment = _extract_trailing_comment(source_lines, value_node, value_node.value.rstrip("\n"))
        separator_ok = _check_separator(source_lines, value_node, value_node.value.rstrip("\n"))

        error, warning = _validate_reference(path, line_number, resolved, comment, separator_ok)
        if error is not None:
            errors.append(error)
        if warning is not None:
            warnings.append(warning)

    return errors, warnings


def discover_workflow_files(root: Path) -> list[Path]:
    """
    Return `.github/workflows/*.yml` and nested `.github/workflows/**/*.yml`.

    Root-level workflows are returned before nested workflows so output order
    mirrors the issue #264 scan scope.
    """
    workflows_dir = root / ".github" / "workflows"
    if not workflows_dir.is_dir():
        return []

    root_workflows = sorted(workflows_dir.glob("*.yml"))
    nested_workflows = sorted(path for path in workflows_dir.rglob("*.yml") if path.parent != workflows_dir)
    return root_workflows + nested_workflows


def format_violation(violation: Violation) -> str:
    """Format one violation for stderr with actionable file:line context."""
    return f"{HOOK_NAME}: {violation.path}:{violation.line}: {violation.message} (uses: {violation.reference})"


def format_warning(warning: Violation) -> str:
    """Format one advisory warning for stderr."""
    return f"{HOOK_NAME}: warning: {warning.path}:{warning.line}: {warning.message} (uses: {warning.reference})"


def main(argv: list[str]) -> int:
    """
    CLI entry point for pre-commit and manual validation.

    Pre-commit passes matched workflow filenames. With no filenames, the command
    discovers `.github/workflows/*.yml` and nested `.yml` workflows from the
    current working directory.

    Returns 1 if any errors are found; 0 if only warnings or clean.
    """
    parser = argparse.ArgumentParser(description="Validate ADR-024 GitHub Actions `uses:` pinning.")
    parser.add_argument("files", nargs="*", help="Workflow .yml files to validate.")
    args = parser.parse_args(argv)

    files = [Path(file) for file in args.files] if args.files else discover_workflow_files(Path.cwd())
    all_errors: list[Violation] = []
    all_warnings: list[Violation] = []

    for path in files:
        if not path.exists():
            continue
        file_errors, file_warnings = validate_file(path)
        all_errors.extend(file_errors)
        all_warnings.extend(file_warnings)

    for violation in all_errors:
        print(format_violation(violation), file=sys.stderr)

    for warning in all_warnings:
        print(format_warning(warning), file=sys.stderr)

    return 1 if all_errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

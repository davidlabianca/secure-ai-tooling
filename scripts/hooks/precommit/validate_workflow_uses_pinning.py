#!/usr/bin/env python3
"""
Pre-commit lint: enforce ADR-024 pinning for GitHub Actions `uses:` references.

External workflow dependencies must use a full 40-character commit SHA and a
same-line `# vX.Y.Z` semver comment so Dependabot can keep updating the pin.
Local `./...` references are exempt. `docker://` references are rejected until
a separate ADR defines the repository's Docker action pinning policy.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HOOK_NAME = "validate-workflow-uses-pinning"

USES_LINE_RE = re.compile(r"^\s*(?:-\s*)?(?:uses|\"uses\"|'uses')\s*:\s*(?P<rest>.*?)\s*$")
PINNED_EXTERNAL_REF_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*@[0-9A-Fa-f]{40}$")
SEMVER_COMMENT_RE = re.compile(
    r"v(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-[0-9A-Za-z.-]+)?"
    r"(?:\+[0-9A-Za-z.-]+)?"
)


@dataclass(frozen=True)
class Violation:
    """A single workflow `uses:` pinning violation."""

    path: Path
    line: int
    reference: str
    message: str


def _strip_optional_quotes(value: str) -> str:
    """Remove one balanced layer of single or double quotes around a scalar."""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _parse_uses_line(line: str) -> tuple[str, str | None, bool] | None:
    """
    Extract the `uses:` reference, same-line comment, and exact separator flag.

    Comments matter for ADR-024, so this intentionally works on source lines
    rather than parsed YAML. GitHub Actions `uses:` values do not contain `#`,
    which keeps the split deterministic for the workflow shapes this repository
    accepts.
    """
    match = USES_LINE_RE.match(line)
    if match is None:
        return None

    rest = match.group("rest").rstrip()
    value_part, separator, comment_part = rest.partition("#")
    reference = _strip_optional_quotes(value_part.strip())

    if not separator:
        return reference, None, False

    has_required_separator = value_part.endswith(" ") and comment_part.startswith(" ")
    return reference, comment_part.strip(), has_required_separator


def _validate_reference(
    path: Path,
    line_number: int,
    reference: str,
    comment: str | None,
    separator_ok: bool,
) -> Violation | None:
    """Validate one parsed `uses:` reference and return a violation if it fails."""
    if reference.startswith("./"):
        return None

    if reference.startswith("docker://"):
        return Violation(
            path=path,
            line=line_number,
            reference=reference,
            message=(
                "docker:// action references require maintainer review until a Docker action "
                "pinning policy is defined"
            ),
        )

    if not PINNED_EXTERNAL_REF_RE.fullmatch(reference):
        return Violation(
            path=path,
            line=line_number,
            reference=reference,
            message=(
                "external `uses:` reference must use owner/repo[/path]@<full "
                "40-character commit SHA>; tags, branches, missing refs, and short SHAs are not allowed"
            ),
        )

    if comment is None or not separator_ok or SEMVER_COMMENT_RE.fullmatch(comment) is None:
        return Violation(
            path=path,
            line=line_number,
            reference=reference,
            message="SHA-pinned external `uses:` reference is missing required ` # vX.Y.Z` semver comment",
        )

    return None


def validate_file(path: Path) -> list[Violation]:
    """
    Validate every `uses:` line in one workflow file.

    Args:
        path: Path to a GitHub Actions workflow `.yml` file.

    Returns:
        A list of pinning violations. Empty means the file passed.
    """
    violations: list[Violation] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        parsed = _parse_uses_line(line)
        if parsed is None:
            continue
        reference, comment, separator_ok = parsed
        violation = _validate_reference(path, line_number, reference, comment, separator_ok)
        if violation is not None:
            violations.append(violation)
    return violations


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


def main(argv: list[str]) -> int:
    """
    CLI entry point for pre-commit and manual validation.

    Pre-commit passes matched workflow filenames. With no filenames, the command
    discovers `.github/workflows/*.yml` and nested `.yml` workflows from the
    current working directory.
    """
    parser = argparse.ArgumentParser(description="Validate ADR-024 GitHub Actions `uses:` pinning.")
    parser.add_argument("files", nargs="*", help="Workflow .yml files to validate.")
    args = parser.parse_args(argv)

    files = [Path(file) for file in args.files] if args.files else discover_workflow_files(Path.cwd())
    violations: list[Violation] = []
    for path in files:
        if not path.exists():
            continue
        violations.extend(validate_file(path))

    for violation in violations:
        print(format_violation(violation), file=sys.stderr)

    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

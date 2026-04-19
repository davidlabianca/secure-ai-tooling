#!/usr/bin/env python3
"""
Pre-commit framework hook that regenerates GitHub Issue Templates when source files change.

Invoked by the pre-commit framework with staged filenames as positional argv (pass_filenames:
true). Regenerates issue templates via generate_issue_templates.py and git-adds the output
directory so generated files land in the same commit as the source change (Mode B auto-stage).

THREE alternative trigger conditions — ANY one matched invokes ONE generation (single dedup):
  - scripts/TEMPLATES/<anything>.yml
  - risk-map/schemas/<anything>.schema.json
  - risk-map/yaml/frameworks.yaml
"""

import subprocess
import sys

_CMD_GENERATE = ["python3", "scripts/generate_issue_templates.py"]
_GIT_ADD_TEMPLATES = ["git", "add", ".github/ISSUE_TEMPLATE"]


def _has_template_source(argv: list[str]) -> bool:
    """Return True iff any path contains scripts/TEMPLATES/ and ends with .yml."""
    return any("scripts/TEMPLATES/" in p and p.endswith(".yml") for p in argv)


def _has_schema(argv: list[str]) -> bool:
    """Return True iff any path ends with .schema.json."""
    return any(p.endswith(".schema.json") for p in argv)


def _has_frameworks(argv: list[str]) -> bool:
    """Return True iff any path ends with risk-map/yaml/frameworks.yaml."""
    return any(p.endswith("risk-map/yaml/frameworks.yaml") for p in argv)


def main(argv: list[str]) -> int:
    """
    Regenerate issue templates if any trigger file is staged, then git-add the output directory.

    Args:
        argv: List of staged file paths passed by the pre-commit framework.

    Returns:
        0 if generation and git-add both succeed (or no trigger matched), non-zero otherwise.
    """
    if not (_has_template_source(argv) or _has_schema(argv) or _has_frameworks(argv)):
        return 0

    result = subprocess.run(_CMD_GENERATE)
    if result.returncode != 0:
        return result.returncode

    git_result = subprocess.run(_GIT_ADD_TEMPLATES)
    if git_result.returncode != 0:
        return git_result.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

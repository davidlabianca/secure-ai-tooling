#!/usr/bin/env python3
"""
Pre-commit framework hook that regenerates GitHub Issue Templates.

Invoked by the pre-commit framework without filenames (pass_filenames: false
in .pre-commit-config.yaml). The framework's `files:` regex decides when to
call this wrapper; when called, the wrapper unconditionally regenerates the
templates and git-adds the output directory (Mode B auto-stage). argv is
ignored, making the wrapper safe to invoke directly from the CLI.
"""

import subprocess
import sys

_CMD_GENERATE = ["python3", "scripts/generate_issue_templates.py"]
_GIT_ADD_TEMPLATES = ["git", "add", ".github/ISSUE_TEMPLATE"]


def main(argv: list[str]) -> int:
    """
    Regenerate issue templates and git-add the output directory.

    Args:
        argv: Ignored. The pre-commit framework is the scheduler; reaching
            main() means regeneration is wanted.

    Returns:
        0 if both generation and git-add succeeded, the first non-zero
        returncode otherwise.
    """
    del argv  # scheduler is the framework; argv adds no information

    result = subprocess.run(_CMD_GENERATE)
    if result.returncode != 0:
        return result.returncode

    git_result = subprocess.run(_GIT_ADD_TEMPLATES)
    if git_result.returncode != 0:
        return git_result.returncode

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""
Pre-commit framework hook that runs prettier on staged YAML files and stages
the formatted output (Mode B auto-stage).

Invoked by the pre-commit framework with staged filenames as positional argv
(pass_filenames: true). The git-add after each successful format means
prettier reformats are included in the in-flight commit rather than tripping
the framework's modify-and-fail detector.
"""

import subprocess
import sys


def main(argv: list[str]) -> int:
    """
    Run prettier on each staged file and git-add successfully formatted ones.

    Args:
        argv: Staged file paths passed by the pre-commit framework.

    Returns:
        0 if every prettier invocation succeeded, non-zero otherwise. git-add
        failures also return non-zero so silent stage misses are surfaced.
    """
    if not argv:
        return 0

    # First-failure-wins: preserve the earliest non-zero returncode so callers
    # can associate the exit code with the first thing that went wrong.
    exit_code = 0
    for path in argv:
        result = subprocess.run(["npx", "prettier", "--write", path])
        if result.returncode != 0:
            if exit_code == 0:
                exit_code = result.returncode
            continue
        stage = subprocess.run(["git", "add", path])
        if stage.returncode != 0 and exit_code == 0:
            exit_code = stage.returncode

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""
Pre-commit hook: validate the persona-site builder succeeds on current YAML.

Invoked when a change to the persona-site input YAML, the builder, or either
of its schemas is staged. Re-runs the full build pipeline against a temp
directory so nothing leaks into the repo working tree, and fails the commit
with a clear stderr message if the build raises.
"""

import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

import scripts.build_persona_site_data as builder  # noqa: E402


def main(argv: list[str]) -> int:
    """
    Run the persona-site builder; exit non-zero with stderr on any failure.

    Args:
        argv: Ignored. The hook uses pass_filenames: false so the pre-commit
              framework does not pass staged filenames; any argv is discarded.

    Returns:
        0 on success, 1 on any build failure.
    """
    del argv  # intentionally ignored; framework uses pass_filenames: false
    try:
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp) / "site"
            output_path = builder.resolve_output_path(site_dir, None)
            site_data = builder.build_site_data(
                builder.load_yaml(builder.DEFAULT_PERSONAS_PATH),
                builder.load_yaml(builder.DEFAULT_RISKS_PATH),
                builder.load_yaml(builder.DEFAULT_CONTROLS_PATH),
            )
            builder.write_site_data(site_data, output_path)
    except Exception as exc:
        print(f"Persona-site builder failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

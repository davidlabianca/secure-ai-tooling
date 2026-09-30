#!/usr/bin/env python3
"""
Pre-commit framework hook that regenerates the component Mermaid graph when components.yaml or
mermaid-styles.yaml changes.

Invoked by the pre-commit framework with staged filenames as positional argv (pass_filenames:
true). Regenerates the graph via validate_riskmap.py and git-adds it so it lands in the same
commit as the source change (Mode B auto-stage).
"""

import subprocess
import sys

# Source YAML trigger (repo-relative, as pre-commit framework passes it)
_COMPONENTS = "risk-map/yaml/components.yaml"
_MERMAID_STYLES = "risk-map/yaml/mermaid-styles.yaml"

# Output file paths (repo-relative)
_RISK_MAP_MD = "risk-map/diagrams/risk-map-graph.md"
_RISK_MAP_MERMAID = "risk-map/diagrams/risk-map-graph.mermaid"

_VALIDATOR = "scripts/hooks/validate_riskmap.py"


def _matches(argv: list[str], target: str) -> bool:
    """Return True if any path in argv ends with the repo-relative target path."""
    return any(p.endswith(target) for p in argv)


def main(argv: list[str]) -> int:
    """
    Regenerate the component Mermaid graph when components.yaml or mermaid-styles.yaml is staged,
    git-adding the output.

    Args:
        argv: List of staged file paths passed by the pre-commit framework.

    Returns:
        0 if there is nothing to do, or generation and git-add both succeeded;
        the failing subprocess's return code otherwise.
    """
    has_components = _matches(argv, _COMPONENTS)
    # mermaid-styles.yaml styles the component graph's emission block (ADR-036
    # D3/D7), so it is the same trigger shape as components.yaml.
    has_mermaid_styles = _matches(argv, _MERMAID_STYLES)
    gen_risk_map = has_components or has_mermaid_styles

    if not gen_risk_map:
        return 0

    cmd = ["python3", _VALIDATOR, "--to-graph", _RISK_MAP_MD, "-m", "--quiet"]
    result = subprocess.run(cmd)
    if result.returncode != 0:
        return result.returncode

    git_result = subprocess.run(["git", "add", _RISK_MAP_MD, _RISK_MAP_MERMAID])
    return git_result.returncode


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

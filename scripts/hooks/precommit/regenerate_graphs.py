#!/usr/bin/env python3
"""
Pre-commit framework hook that regenerates Mermaid graph files when source YAML files change.

Invoked by the pre-commit framework with staged filenames as positional argv (pass_filenames:
true). Regenerates the appropriate graphs via validate_riskmap.py and git-adds them so they
land in the same commit as the source change (Mode B auto-stage).
"""

import subprocess
import sys

# Source YAML triggers (repo-relative, as pre-commit framework passes them)
_COMPONENTS = "risk-map/yaml/components.yaml"
_CONTROLS = "risk-map/yaml/controls.yaml"
_RISKS = "risk-map/yaml/risks.yaml"

# Output file paths (repo-relative)
_RISK_MAP_MD = "risk-map/diagrams/risk-map-graph.md"
_RISK_MAP_MERMAID = "risk-map/diagrams/risk-map-graph.mermaid"

_CONTROLS_MD = "risk-map/diagrams/controls-graph.md"
_CONTROLS_MERMAID = "risk-map/diagrams/controls-graph.mermaid"

_RISK_GRAPH_MD = "risk-map/diagrams/controls-to-risk-graph.md"
_RISK_GRAPH_MERMAID = "risk-map/diagrams/controls-to-risk-graph.mermaid"

_VALIDATOR = "scripts/hooks/validate_riskmap.py"


def _matches(argv: list[str], target: str) -> bool:
    """Return True if any path in argv ends with the repo-relative target path."""
    return any(p.endswith(target) for p in argv)


def main(argv: list[str]) -> int:
    """
    Regenerate Mermaid graphs for any staged YAML source files and git-add the outputs.

    Args:
        argv: List of staged file paths passed by the pre-commit framework.

    Returns:
        0 if all attempted generations and git-adds succeeded, non-zero otherwise.
    """
    has_components = _matches(argv, _COMPONENTS)
    has_controls = _matches(argv, _CONTROLS)
    has_risks = _matches(argv, _RISKS)

    # Determine which graphs need to be generated based on trigger logic
    gen_risk_map = has_components
    gen_controls = has_components or has_controls
    gen_risk_graph = has_components or has_controls or has_risks

    if not (gen_risk_map or gen_controls or gen_risk_graph):
        return 0

    exit_code = 0

    # Generation 1: risk-map-graph (triggered by components.yaml)
    if gen_risk_map:
        cmd = ["python3", _VALIDATOR, "--to-graph", _RISK_MAP_MD, "-m", "--quiet"]
        result = subprocess.run(cmd)
        if result.returncode == 0:
            git_result = subprocess.run(["git", "add", _RISK_MAP_MD, _RISK_MAP_MERMAID])
            if git_result.returncode != 0 and exit_code == 0:
                exit_code = git_result.returncode
        elif exit_code == 0:
            exit_code = result.returncode

    # Generation 2: controls-graph (triggered by components.yaml OR controls.yaml)
    if gen_controls:
        cmd = ["python3", _VALIDATOR, "--to-controls-graph", _CONTROLS_MD, "-m", "--quiet"]
        result = subprocess.run(cmd)
        if result.returncode == 0:
            git_result = subprocess.run(["git", "add", _CONTROLS_MD, _CONTROLS_MERMAID])
            if git_result.returncode != 0 and exit_code == 0:
                exit_code = git_result.returncode
        elif exit_code == 0:
            exit_code = result.returncode

    # Generation 3: controls-to-risk-graph (triggered by any of the three source files)
    if gen_risk_graph:
        cmd = ["python3", _VALIDATOR, "--to-risk-graph", _RISK_GRAPH_MD, "-m", "--quiet"]
        result = subprocess.run(cmd)
        if result.returncode == 0:
            git_result = subprocess.run(["git", "add", _RISK_GRAPH_MD, _RISK_GRAPH_MERMAID])
            if git_result.returncode != 0 and exit_code == 0:
                exit_code = git_result.returncode
        elif exit_code == 0:
            exit_code = result.returncode

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""
Pre-commit framework hook that regenerates Markdown table files when source YAML files change.

Invoked by the pre-commit framework with staged filenames as positional argv (pass_filenames:
true). Regenerates the appropriate tables via yaml_to_markdown.py and git-adds them so they
land in the same commit as the source change (Mode B auto-stage).
"""

import subprocess
import sys

# Source YAML triggers (repo-relative, as pre-commit framework passes them)
_COMPONENTS = "risk-map/yaml/components.yaml"
_CONTROLS = "risk-map/yaml/controls.yaml"
_RISKS = "risk-map/yaml/risks.yaml"
_PERSONAS = "risk-map/yaml/personas.yaml"

_YAML_TO_MD = "scripts/hooks/yaml_to_markdown.py"

# Generation commands — components trigger
_CMD_COMPONENTS_ALL_FORMATS = ["python3", _YAML_TO_MD, "components", "--all-formats", "--quiet"]
_CMD_CONTROLS_XREF_COMPONENTS = ["python3", _YAML_TO_MD, "controls", "--format", "xref-components", "--quiet"]

# Generation commands — risks trigger
_CMD_RISKS_ALL_FORMATS = ["python3", _YAML_TO_MD, "risks", "--all-formats", "--quiet"]
_CMD_CONTROLS_XREF_RISKS = ["python3", _YAML_TO_MD, "controls", "--format", "xref-risks", "--quiet"]
_CMD_PERSONAS_XREF_RISKS = ["python3", _YAML_TO_MD, "personas", "--format", "xref-risks", "--quiet"]

# Generation commands — controls trigger
_CMD_CONTROLS_ALL_FORMATS = ["python3", _YAML_TO_MD, "controls", "--all-formats", "--quiet"]
_CMD_PERSONAS_XREF_CONTROLS = ["python3", _YAML_TO_MD, "personas", "--format", "xref-controls", "--quiet"]

# Generation commands — personas trigger
_CMD_PERSONAS_ALL_FORMATS = ["python3", _YAML_TO_MD, "personas", "--all-formats", "--quiet"]

# git add pathspecs — glob patterns are expanded by git itself
_ADD_COMPONENTS_TABLES = ["git", "add", "risk-map/tables/components-*.md"]
_ADD_CONTROLS_XREF_COMPONENTS = ["git", "add", "risk-map/tables/controls-xref-components.md"]
_ADD_RISKS_TABLES = ["git", "add", "risk-map/tables/risks-*.md"]
_ADD_CONTROLS_XREF_RISKS = ["git", "add", "risk-map/tables/controls-xref-risks.md"]
_ADD_PERSONAS_XREF_RISKS = ["git", "add", "risk-map/tables/personas-xref-risks.md"]
_ADD_CONTROLS_TABLES = ["git", "add", "risk-map/tables/controls-*.md"]
_ADD_PERSONAS_XREF_CONTROLS = ["git", "add", "risk-map/tables/personas-xref-controls.md"]
_ADD_PERSONAS_TABLES = ["git", "add", "risk-map/tables/personas-*.md"]


def _matches(argv: list[str], target: str) -> bool:
    """Return True if any path in argv ends with the repo-relative target path."""
    return any(p.endswith(target) for p in argv)


def main(argv: list[str]) -> int:
    """
    Regenerate Markdown tables for any staged YAML source files and git-add the outputs.

    Args:
        argv: List of staged file paths passed by the pre-commit framework.

    Returns:
        0 if all attempted generations and git-adds succeeded, non-zero otherwise.
    """
    # Deduplicate argv to prevent double-generation when the same file appears twice.
    # This is distinct from the inter-trigger no-dedup rule: different trigger YAMLs
    # that both produce the same generation command must both run (by design).
    unique_argv = list(dict.fromkeys(argv))

    has_components = _matches(unique_argv, _COMPONENTS)
    has_risks = _matches(unique_argv, _RISKS)
    has_controls = _matches(unique_argv, _CONTROLS)
    has_personas = _matches(unique_argv, _PERSONAS)

    if not (has_components or has_risks or has_controls or has_personas):
        return 0

    exit_code = 0

    # Trigger: components.yaml — 2 generations
    if has_components:
        result = subprocess.run(_CMD_COMPONENTS_ALL_FORMATS)
        if result.returncode == 0:
            git_result = subprocess.run(_ADD_COMPONENTS_TABLES)
            if git_result.returncode != 0 and exit_code == 0:
                exit_code = git_result.returncode
        elif exit_code == 0:
            exit_code = result.returncode

        result = subprocess.run(_CMD_CONTROLS_XREF_COMPONENTS)
        if result.returncode == 0:
            git_result = subprocess.run(_ADD_CONTROLS_XREF_COMPONENTS)
            if git_result.returncode != 0 and exit_code == 0:
                exit_code = git_result.returncode
        elif exit_code == 0:
            exit_code = result.returncode

    # Trigger: risks.yaml — 3 generations
    if has_risks:
        result = subprocess.run(_CMD_RISKS_ALL_FORMATS)
        if result.returncode == 0:
            git_result = subprocess.run(_ADD_RISKS_TABLES)
            if git_result.returncode != 0 and exit_code == 0:
                exit_code = git_result.returncode
        elif exit_code == 0:
            exit_code = result.returncode

        result = subprocess.run(_CMD_CONTROLS_XREF_RISKS)
        if result.returncode == 0:
            git_result = subprocess.run(_ADD_CONTROLS_XREF_RISKS)
            if git_result.returncode != 0 and exit_code == 0:
                exit_code = git_result.returncode
        elif exit_code == 0:
            exit_code = result.returncode

        result = subprocess.run(_CMD_PERSONAS_XREF_RISKS)
        if result.returncode == 0:
            git_result = subprocess.run(_ADD_PERSONAS_XREF_RISKS)
            if git_result.returncode != 0 and exit_code == 0:
                exit_code = git_result.returncode
        elif exit_code == 0:
            exit_code = result.returncode

    # Trigger: controls.yaml — 2 generations
    if has_controls:
        result = subprocess.run(_CMD_CONTROLS_ALL_FORMATS)
        if result.returncode == 0:
            git_result = subprocess.run(_ADD_CONTROLS_TABLES)
            if git_result.returncode != 0 and exit_code == 0:
                exit_code = git_result.returncode
        elif exit_code == 0:
            exit_code = result.returncode

        result = subprocess.run(_CMD_PERSONAS_XREF_CONTROLS)
        if result.returncode == 0:
            git_result = subprocess.run(_ADD_PERSONAS_XREF_CONTROLS)
            if git_result.returncode != 0 and exit_code == 0:
                exit_code = git_result.returncode
        elif exit_code == 0:
            exit_code = result.returncode

    # Trigger: personas.yaml — 1 generation
    if has_personas:
        result = subprocess.run(_CMD_PERSONAS_ALL_FORMATS)
        if result.returncode == 0:
            git_result = subprocess.run(_ADD_PERSONAS_TABLES)
            if git_result.returncode != 0 and exit_code == 0:
                exit_code = git_result.returncode
        elif exit_code == 0:
            exit_code = result.returncode

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

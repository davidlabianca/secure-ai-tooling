"""
Utility functions for risk map validation system.

Provides file parsing, git integration, and helper functions for
YAML processing and staged file detection.

Dependencies:
    - PyYAML: For YAML file parsing
    - subprocess: For git command execution
"""

import subprocess
from pathlib import Path

import yaml

from .config import DEFAULT_COMPONENTS_FILE
from .models import ControlNode


def parse_controls_yaml(file_path: Path = None) -> dict[str, ControlNode]:
    """
    Parse controls.yaml file and return dictionary of ControlNode objects.

    Args:
        file_path: Path to controls.yaml file. Defaults to risk-map/yaml/controls.yaml

    Returns:
        Dictionary mapping control IDs to ControlNode objects

    Raises:
        FileNotFoundError: If controls.yaml file doesn't exist
        yaml.YAMLError: If YAML parsing fails
        KeyError: If required fields are missing
    """
    if file_path is None:
        file_path = Path("risk-map/yaml/controls.yaml")

    if not file_path.exists():
        raise FileNotFoundError(f"Controls file not found: {file_path}")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        controls = {}

        for control_data in data.get("controls", []):
            control_id = control_data["id"]
            title = control_data["title"]
            category = control_data["category"]

            # Handle components field - can be list, "all", or "none"
            components_raw = control_data.get("components", [])
            if isinstance(components_raw, str):
                components = [components_raw]  # Convert "all" or "none" to list
            elif isinstance(components_raw, list):
                components = components_raw
            else:
                components = []

            # Handle risks and personas fields
            risks = control_data.get("risks", [])
            personas = control_data.get("personas", [])

            # Ensure all fields are lists of strings
            if not isinstance(risks, list):
                risks = []
            if not isinstance(personas, list):
                personas = []

            controls[control_id] = ControlNode(
                title=title, category=category, components=components, risks=risks, personas=personas
            )

        return controls

    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Error parsing controls YAML: {e}")
    except KeyError as e:
        raise KeyError(f"Missing required field in controls.yaml: {e}")


def get_staged_yaml_files(target_file: Path | None = None, force_check: bool = False) -> list[Path]:
    """
    Get YAML files that are staged for commit or force check specific file.

    Args:
        target_file: Specific file to check (defaults to DEFAULT_COMPONENTS_FILE)
        force_check: If True, return target file regardless of git status

    Returns:
        List of Path objects for files to validate
    """
    if target_file is None:
        target_file = DEFAULT_COMPONENTS_FILE

    # Force check mode - return file if it exists
    if force_check:
        if target_file.exists():
            return [target_file]
        else:
            print(f"  ⚠️  Target file {target_file} does not exist")
            return []

    try:
        # Get all staged files from git
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )

        staged_files = result.stdout.strip().split("\n") if result.stdout.strip() else []

        # Filter for our target file
        if str(target_file) in staged_files and target_file.exists():
            return [target_file]
        else:
            return []

    except subprocess.CalledProcessError as e:
        print(f"⚠️  Error getting staged files: {e}")
        print("   Make sure you're in a git repository")
        return []
    except FileNotFoundError:
        print("⚠️  Git command not found - make sure git is installed")
        return []

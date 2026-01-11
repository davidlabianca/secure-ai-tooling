"""
Shared test fixtures for issue_template_generator tests.

This module provides fixtures for accessing repository paths in a
cross-environment compatible way.
"""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """
    Dynamically find the repository root directory.

    Works in any environment: devcontainer, GitHub Actions, local development.

    Returns:
        Path: Absolute path to repository root
    """
    try:
        # Try git method first (most reliable)
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Fallback: navigate up from this file's location
        # conftest.py is at scripts/hooks/issue_template_generator/tests/conftest.py
        # Go up 5 levels: tests -> issue_template_generator -> hooks -> scripts -> repo_root
        return Path(__file__).resolve().parent.parent.parent.parent.parent


@pytest.fixture(scope="session")
def risk_map_schemas_dir(repo_root: Path) -> Path:
    """
    Path to risk-map/schemas directory.

    Args:
        repo_root: Repository root path fixture

    Returns:
        Path: Absolute path to risk-map/schemas directory
    """
    return repo_root / "risk-map" / "schemas"

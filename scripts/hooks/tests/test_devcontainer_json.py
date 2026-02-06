#!/usr/bin/env python3
"""
Tests for .devcontainer/devcontainer.json structure.

Static analysis tests that read devcontainer.json and validate its structure.
These tests validate the Phase 4 devcontainer refactor, which moves tool
installation from devcontainer features to install-deps.sh with mise.

Test Coverage:
==============
Total Test Classes: 6
Total Test Methods: 15

1. TestDevcontainerJsonExists (2): file exists, parses as valid JSON
2. TestDevcontainerJsonFeatures (3): no Python feature, no Node feature,
   Docker-in-Docker feature present
3. TestDevcontainerJsonCommands (3): no onCreateCommand, postCreateCommand exists,
   postCreateCommand references install-deps.sh
4. TestDevcontainerJsonPythonConfig (3): interpreter path exists, uses mise shims,
   does not use /usr/local/python/current
5. TestDevcontainerJsonVscodeExtensions (2): extensions array exists,
   required extensions present
6. TestDevcontainerJsonBuildConfig (2): remoteUser is vscode,
   build.args contains WORKSPACE and WORKSPACE_REPO

Testing Approach:
=================
Reads .devcontainer/devcontainer.json, strips JSONC comments (// and /* */),
parses as JSON, and validates structure. Uses module-level fixture to load
file once per session.
"""

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent.parent
DEVCONTAINER_JSON_PATH = REPO_ROOT / ".devcontainer" / "devcontainer.json"


def strip_jsonc_comments(content: str) -> str:
    """
    Strip JSONC comments from content.

    Removes:
    - // line comments
    - /* block comments */

    Does NOT handle comments inside strings (but devcontainer.json doesn't
    contain such cases, so this simple approach is sufficient).
    """
    # Remove block comments /* ... */
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    # Remove line comments //
    lines = content.splitlines()
    cleaned_lines = []
    for line in lines:
        # Find // outside of quoted strings (simple heuristic)
        comment_idx = line.find('//')
        if comment_idx != -1:
            line = line[:comment_idx]
        cleaned_lines.append(line)
    return '\n'.join(cleaned_lines)


@pytest.fixture(scope="module")
def devcontainer_json():
    """Load and parse devcontainer.json once per test module."""
    assert DEVCONTAINER_JSON_PATH.exists(), (
        f"devcontainer.json not found at {DEVCONTAINER_JSON_PATH}"
    )
    content = DEVCONTAINER_JSON_PATH.read_text()
    # Strip JSONC comments before parsing
    cleaned = strip_jsonc_comments(content)
    return json.loads(cleaned)


# =============================================================================
# TestDevcontainerJsonExists
# =============================================================================


class TestDevcontainerJsonExists:
    """
    Validate devcontainer.json existence and JSON parsability.
    """

    def test_devcontainer_json_exists(self):
        """
        Given: The .devcontainer directory structure
        When: Checking for devcontainer.json
        Then: File exists at .devcontainer/devcontainer.json
        """
        assert DEVCONTAINER_JSON_PATH.exists(), (
            f"devcontainer.json not found at {DEVCONTAINER_JSON_PATH}"
        )

    def test_devcontainer_json_parses_as_valid_json(self):
        """
        Given: The devcontainer.json file exists
        When: Parsing with comment stripping and json.loads
        Then: File parses without errors and returns a dict
        """
        assert DEVCONTAINER_JSON_PATH.exists(), (
            f"devcontainer.json not found at {DEVCONTAINER_JSON_PATH}"
        )
        content = DEVCONTAINER_JSON_PATH.read_text()
        cleaned = strip_jsonc_comments(content)
        config = json.loads(cleaned)
        assert isinstance(config, dict), (
            "devcontainer.json did not parse to a dict"
        )


# =============================================================================
# TestDevcontainerJsonFeatures
# =============================================================================


class TestDevcontainerJsonFeatures:
    """
    Validate devcontainer features configuration.

    After refactor:
    - No Python feature (ghcr.io/devcontainers/features/python)
    - No Node feature (ghcr.io/devcontainers/features/node)
    - Docker-in-Docker feature is still present
    """

    def test_no_python_feature(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking for Python devcontainer feature
        Then: No feature key contains "features/python"

        Python is now installed via mise in install-deps.sh, not as a
        devcontainer feature.
        """
        features = devcontainer_json.get("features", {})
        for feature_key in features.keys():
            assert "features/python" not in feature_key.lower(), (
                f"devcontainer.json should not use Python feature, "
                f"found: {feature_key}"
            )

    def test_no_node_feature(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking for Node devcontainer feature
        Then: No feature key contains "features/node"

        Node.js is now installed via mise in install-deps.sh, not as a
        devcontainer feature.
        """
        features = devcontainer_json.get("features", {})
        for feature_key in features.keys():
            assert "features/node" not in feature_key.lower(), (
                f"devcontainer.json should not use Node feature, "
                f"found: {feature_key}"
            )

    def test_docker_in_docker_feature_present(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking for Docker-in-Docker feature
        Then: Feature key contains "features/docker-in-docker"

        Docker-in-Docker is still needed for running act (GitHub Actions
        locally), so this feature should remain.
        """
        features = devcontainer_json.get("features", {})
        found_docker = any(
            "docker-in-docker" in key.lower()
            for key in features.keys()
        )
        assert found_docker, (
            "devcontainer.json should include Docker-in-Docker feature"
        )


# =============================================================================
# TestDevcontainerJsonCommands
# =============================================================================


class TestDevcontainerJsonCommands:
    """
    Validate devcontainer lifecycle commands.

    After refactor:
    - onCreateCommand should be removed (or not contain pip/npm install)
    - postCreateCommand should exist and reference install-deps.sh
    """

    def test_no_oncreate_command_pip_npm(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking for onCreateCommand
        Then: onCreateCommand key is absent, or does not contain pip/npm install

        pip and npm installs are now handled by install-deps.sh run in
        postCreateCommand, not in onCreateCommand.
        """
        on_create = devcontainer_json.get("onCreateCommand")
        if on_create is None:
            # Best case: key is absent
            return

        # If onCreateCommand exists, check it doesn't do pip/npm install
        on_create_str = json.dumps(on_create).lower()
        assert "pip install" not in on_create_str, (
            "devcontainer.json onCreateCommand should not run pip install"
        )
        assert "npm install" not in on_create_str, (
            "devcontainer.json onCreateCommand should not run npm install"
        )

    def test_postcreate_command_exists(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking for postCreateCommand
        Then: postCreateCommand key exists and is non-empty

        postCreateCommand now runs install-deps.sh to set up the environment.
        """
        post_create = devcontainer_json.get("postCreateCommand")
        assert post_create is not None, (
            "devcontainer.json should have a postCreateCommand"
        )
        assert post_create != "", (
            "devcontainer.json postCreateCommand should be non-empty"
        )

    def test_postcreate_command_references_install_deps(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking postCreateCommand content
        Then: Command references install-deps.sh (not old setup-script)

        The refactor moves environment setup from .devcontainer/setup-script
        to scripts/tools/install-deps.sh.
        """
        post_create = devcontainer_json.get("postCreateCommand", "")
        post_create_str = json.dumps(post_create).lower()
        assert "install-deps.sh" in post_create_str, (
            "devcontainer.json postCreateCommand should reference install-deps.sh"
        )
        assert "setup-script" not in post_create_str, (
            "devcontainer.json postCreateCommand should not reference old setup-script"
        )


# =============================================================================
# TestDevcontainerJsonPythonConfig
# =============================================================================


class TestDevcontainerJsonPythonConfig:
    """
    Validate VSCode Python interpreter configuration.

    After refactor:
    - python.defaultInterpreterPath should use mise shims
    - Should NOT use /usr/local/python/current
    """

    def test_python_interpreter_path_exists(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking for python.defaultInterpreterPath in vscode settings
        Then: Setting exists

        VSCode needs to know where to find the Python interpreter. With mise,
        this is in the mise shims directory.
        """
        vscode_settings = devcontainer_json.get("customizations", {}).get(
            "vscode", {}
        ).get("settings", {})
        assert "python.defaultInterpreterPath" in vscode_settings, (
            "devcontainer.json vscode settings should include "
            "python.defaultInterpreterPath"
        )

    def test_python_interpreter_uses_mise_shims(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking python.defaultInterpreterPath value
        Then: Path references mise shims directory

        mise installs Python to ~/.local/share/mise/installs/python/... and
        creates shims in ~/.local/share/mise/shims/python.
        """
        vscode_settings = devcontainer_json.get("customizations", {}).get(
            "vscode", {}
        ).get("settings", {})
        interpreter_path = vscode_settings.get("python.defaultInterpreterPath", "")
        # Check for mise shims path pattern
        has_mise_shims = (
            "mise/shims" in interpreter_path or
            ".local/share/mise" in interpreter_path
        )
        assert has_mise_shims, (
            f"python.defaultInterpreterPath should reference mise shims, "
            f"got: {interpreter_path}"
        )

    def test_python_interpreter_not_usr_local(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking python.defaultInterpreterPath value
        Then: Path does NOT reference /usr/local/python/current

        The old devcontainer Python feature installed to /usr/local/python/current.
        The refactor uses mise instead.
        """
        vscode_settings = devcontainer_json.get("customizations", {}).get(
            "vscode", {}
        ).get("settings", {})
        interpreter_path = vscode_settings.get("python.defaultInterpreterPath", "")
        assert "/usr/local/python/current" not in interpreter_path, (
            f"python.defaultInterpreterPath should not use "
            f"/usr/local/python/current (old devcontainer feature path), "
            f"got: {interpreter_path}"
        )


# =============================================================================
# TestDevcontainerJsonVscodeExtensions
# =============================================================================


class TestDevcontainerJsonVscodeExtensions:
    """
    Validate VSCode extensions configuration.

    Required extensions (unchanged from original devcontainer.json):
    - bierner.markdown-mermaid
    - charliermarsh.ruff
    - redhat.vscode-yaml
    """

    def test_extensions_array_exists(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking for vscode extensions array
        Then: Extensions array exists and is non-empty

        The devcontainer should specify required extensions for the project.
        """
        extensions = devcontainer_json.get("customizations", {}).get(
            "vscode", {}
        ).get("extensions", [])
        assert isinstance(extensions, list), (
            "devcontainer.json vscode extensions should be a list"
        )
        assert len(extensions) > 0, (
            "devcontainer.json vscode extensions should be non-empty"
        )

    def test_required_extensions_present(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking vscode extensions list
        Then: Required extensions are present

        Required for CoSAI Risk Map development:
        - bierner.markdown-mermaid (Mermaid diagram preview)
        - charliermarsh.ruff (Python linting/formatting)
        - redhat.vscode-yaml (YAML validation)
        """
        extensions = devcontainer_json.get("customizations", {}).get(
            "vscode", {}
        ).get("extensions", [])
        required = [
            "bierner.markdown-mermaid",
            "charliermarsh.ruff",
            "redhat.vscode-yaml",
        ]
        for ext in required:
            assert ext in extensions, (
                f"devcontainer.json vscode extensions should include {ext}"
            )


# =============================================================================
# TestDevcontainerJsonBuildConfig
# =============================================================================


class TestDevcontainerJsonBuildConfig:
    """
    Validate devcontainer build configuration.

    Checks:
    - remoteUser is "vscode"
    - build.args contains WORKSPACE and WORKSPACE_REPO
    """

    def test_remote_user_is_vscode(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking remoteUser setting
        Then: remoteUser is "vscode"

        The Dockerfile creates a vscode user, and the devcontainer should
        run as that user.
        """
        remote_user = devcontainer_json.get("remoteUser", "")
        assert remote_user == "vscode", (
            f"devcontainer.json remoteUser should be 'vscode', got: {remote_user}"
        )

    def test_build_args_contain_workspace(self, devcontainer_json):
        """
        Given: The devcontainer.json config
        When: Checking build.args
        Then: WORKSPACE and WORKSPACE_REPO args are present

        The Dockerfile expects these ARGs to configure the workspace path
        structure.
        """
        build_args = devcontainer_json.get("build", {}).get("args", {})
        assert "WORKSPACE" in build_args, (
            "devcontainer.json build.args should include WORKSPACE"
        )
        assert "WORKSPACE_REPO" in build_args, (
            "devcontainer.json build.args should include WORKSPACE_REPO"
        )


"""
Test Summary
============
Total Test Classes: 6
Total Test Methods: 15

1. TestDevcontainerJsonExists (2): file exists, parses as valid JSON
2. TestDevcontainerJsonFeatures (3): no Python feature, no Node feature,
   Docker-in-Docker present
3. TestDevcontainerJsonCommands (3): no onCreateCommand pip/npm,
   postCreateCommand exists, references install-deps.sh
4. TestDevcontainerJsonPythonConfig (3): interpreter path exists, uses mise shims,
   not /usr/local/python/current
5. TestDevcontainerJsonVscodeExtensions (2): extensions array exists,
   required extensions present
6. TestDevcontainerJsonBuildConfig (2): remoteUser is vscode,
   build.args has WORKSPACE/WORKSPACE_REPO

Coverage Areas:
- File existence and JSON validity
- Feature configuration (Python/Node removed, Docker-in-Docker kept)
- Lifecycle commands (onCreateCommand removed, postCreateCommand uses install-deps.sh)
- Python interpreter configuration (mise shims path)
- VSCode extensions (markdown-mermaid, ruff, yaml)
- Build configuration (remoteUser, build.args)

Refactor Changes Validated:
- Python/Node devcontainer features removed (now handled by mise)
- onCreateCommand pip/npm install removed (now in install-deps.sh)
- postCreateCommand runs install-deps.sh (not old setup-script)
- Python interpreter path uses mise shims (not /usr/local/python/current)
- Docker-in-Docker feature preserved (needed for act)
"""

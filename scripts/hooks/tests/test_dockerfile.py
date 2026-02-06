#!/usr/bin/env python3
"""
Tests for .devcontainer/Dockerfile structure.

Static analysis tests that read the Dockerfile as text and validate its
structure. No Docker build required -- these tests parse Dockerfile content
to ensure it matches the Phase 3 devcontainer refactor spec.

Test Coverage:
==============
Total Test Classes: 6
Total Test Methods: 16

1. TestDockerfileExists (2): file exists, non-empty
2. TestDockerfileBaseImage (2): uses ubuntu:noble, no playwright reference
3. TestDockerfileSystemPackages (4): core packages, Playwright deps,
   --no-install-recommends, apt cache cleanup
4. TestDockerfileUserSetup (3): configurable UID/GID ARGs, passwordless sudo,
   non-root USER
5. TestDockerfileWorkspace (2): creates workspace dir, sets WORKDIR
6. TestDockerfileNoRuntimeInstalls (3): no Python install, no Node.js install,
   no playwright install

Testing Approach:
=================
Reads .devcontainer/Dockerfile as text and runs assertions against its content.
Uses a module-level fixture to load the file once per session.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent.parent
DOCKERFILE_PATH = REPO_ROOT / ".devcontainer" / "Dockerfile"


@pytest.fixture(scope="module")
def dockerfile_content():
    """Load Dockerfile content once per test module."""
    assert DOCKERFILE_PATH.exists(), f"Dockerfile not found at {DOCKERFILE_PATH}"
    return DOCKERFILE_PATH.read_text()


@pytest.fixture(scope="module")
def dockerfile_lines(dockerfile_content):
    """Split Dockerfile into lines for line-by-line analysis."""
    return dockerfile_content.splitlines()


# =============================================================================
# TestDockerfileExists
# =============================================================================


class TestDockerfileExists:
    """
    Validate Dockerfile existence and non-emptiness.
    """

    def test_dockerfile_exists(self):
        """
        Given: The .devcontainer directory structure
        When: Checking for Dockerfile
        Then: File exists at .devcontainer/Dockerfile
        """
        assert DOCKERFILE_PATH.exists(), f"Dockerfile not found at {DOCKERFILE_PATH}"

    def test_dockerfile_is_not_empty(self):
        """
        Given: The Dockerfile exists
        When: Reading its content
        Then: File is non-empty
        """
        assert DOCKERFILE_PATH.exists(), f"Dockerfile not found at {DOCKERFILE_PATH}"
        content = DOCKERFILE_PATH.read_text()
        assert len(content.strip()) > 0, "Dockerfile should not be empty"


# =============================================================================
# TestDockerfileBaseImage
# =============================================================================


class TestDockerfileBaseImage:
    """
    Validate base image is ubuntu:noble with no Playwright image reference.
    """

    def test_uses_ubuntu_noble(self, dockerfile_content):
        """
        Given: The Dockerfile content
        When: Checking the FROM instruction
        Then: Base image is ubuntu:noble
        """
        # Find FROM lines (ignore comments)
        from_lines = [
            line.strip()
            for line in dockerfile_content.splitlines()
            if line.strip().upper().startswith("FROM")
        ]
        assert len(from_lines) >= 1, "Dockerfile should have at least one FROM instruction"
        assert "ubuntu:noble" in from_lines[0], (
            f"Base image should be ubuntu:noble, got: {from_lines[0]}"
        )

    def test_no_playwright_base_image(self, dockerfile_content):
        """
        Given: The Dockerfile content
        When: Searching for playwright image references
        Then: No playwright base image is referenced
        """
        from_lines = [
            line.strip()
            for line in dockerfile_content.splitlines()
            if line.strip().upper().startswith("FROM")
        ]
        for line in from_lines:
            assert "playwright" not in line.lower(), (
                f"Dockerfile should not use a Playwright base image: {line}"
            )


# =============================================================================
# TestDockerfileSystemPackages
# =============================================================================


class TestDockerfileSystemPackages:
    """
    Validate system package installation: core packages, Playwright deps,
    --no-install-recommends flag, and apt cache cleanup.
    """

    def test_core_packages_present(self, dockerfile_content):
        """
        Given: The Dockerfile content
        When: Checking for core system packages
        Then: sudo, build-essential, curl, wget, git, ca-certificates are present
        """
        core_packages = [
            "sudo",
            "build-essential",
            "curl",
            "wget",
            "git",
            "ca-certificates",
        ]
        for pkg in core_packages:
            assert pkg in dockerfile_content, (
                f"Core package '{pkg}' should be in Dockerfile"
            )

    def test_playwright_system_deps_present(self, dockerfile_content):
        """
        Given: The Dockerfile content
        When: Checking for Playwright Chromium system dependencies
        Then: Representative subset of Playwright deps are present

        Checks a subset to avoid brittleness if Playwright updates its dep list.
        """
        # Representative subset of the 31 Playwright Chromium deps
        playwright_deps = [
            "libasound2t64",
            "libnss3",
            "libgbm1",
            "libxkbcommon0",
            "xvfb",
            "fonts-noto-color-emoji",
        ]
        for pkg in playwright_deps:
            assert pkg in dockerfile_content, (
                f"Playwright system dep '{pkg}' should be in Dockerfile"
            )

    def test_no_install_recommends(self, dockerfile_content):
        """
        Given: The Dockerfile content
        When: Checking apt-get install flags
        Then: --no-install-recommends flag is used
        """
        assert "--no-install-recommends" in dockerfile_content, (
            "Dockerfile should use --no-install-recommends for smaller image"
        )

    def test_apt_cache_cleanup(self, dockerfile_content):
        """
        Given: The Dockerfile content
        When: Checking for apt cache cleanup
        Then: rm -rf /var/lib/apt/lists/* is present
        """
        assert "rm -rf /var/lib/apt/lists/*" in dockerfile_content, (
            "Dockerfile should clean apt cache with rm -rf /var/lib/apt/lists/*"
        )


# =============================================================================
# TestDockerfileUserSetup
# =============================================================================


class TestDockerfileUserSetup:
    """
    Validate user creation with configurable UID/GID, passwordless sudo,
    and non-root USER directive.
    """

    def test_configurable_uid_gid_args(self, dockerfile_content):
        """
        Given: The Dockerfile content
        When: Checking for ARG declarations
        Then: USER_UID and USER_GID ARGs are declared
        """
        assert "ARG USER_UID" in dockerfile_content, (
            "Dockerfile should declare ARG USER_UID"
        )
        assert "ARG USER_GID" in dockerfile_content, (
            "Dockerfile should declare ARG USER_GID"
        )

    def test_passwordless_sudo(self, dockerfile_content):
        """
        Given: The Dockerfile content
        When: Checking sudoers configuration
        Then: NOPASSWD is configured for the user
        """
        assert "NOPASSWD" in dockerfile_content, (
            "Dockerfile should configure passwordless sudo with NOPASSWD"
        )

    def test_non_root_user(self, dockerfile_lines):
        """
        Given: The Dockerfile lines
        When: Checking for USER directive
        Then: A non-root USER directive exists (not USER root)
        """
        user_lines = [
            line.strip()
            for line in dockerfile_lines
            if line.strip().startswith("USER ")
        ]
        assert len(user_lines) > 0, "Dockerfile should have a USER directive"
        # The last USER directive determines the runtime user
        last_user = user_lines[-1]
        assert "root" not in last_user.lower() or "${" in last_user, (
            f"Final USER directive should not be root: {last_user}"
        )


# =============================================================================
# TestDockerfileWorkspace
# =============================================================================


class TestDockerfileWorkspace:
    """
    Validate workspace directory creation and WORKDIR setting.
    """

    def test_creates_workspace_directory(self, dockerfile_content):
        """
        Given: The Dockerfile content
        When: Checking for workspace directory creation
        Then: mkdir command creates the workspace path
        """
        assert "mkdir" in dockerfile_content, (
            "Dockerfile should create workspace directory with mkdir"
        )
        # Check that it references the WORKSPACE ARG or a /workspaces path
        assert "WORKSPACE" in dockerfile_content or "/workspaces" in dockerfile_content, (
            "Dockerfile should reference WORKSPACE ARG or /workspaces path"
        )

    def test_sets_workdir(self, dockerfile_lines):
        """
        Given: The Dockerfile lines
        When: Checking for WORKDIR directive
        Then: WORKDIR is set to workspace path
        """
        workdir_lines = [
            line.strip()
            for line in dockerfile_lines
            if line.strip().startswith("WORKDIR ")
        ]
        assert len(workdir_lines) > 0, "Dockerfile should have a WORKDIR directive"


# =============================================================================
# TestDockerfileNoRuntimeInstalls
# =============================================================================


class TestDockerfileNoRuntimeInstalls:
    """
    Validate that the Dockerfile does NOT install runtime tools.
    Runtime tools (Python, Node.js, Playwright Chromium binary) are handled
    by install-deps.sh.
    """

    def test_no_python_install(self, dockerfile_content):
        """
        Given: The Dockerfile content
        When: Checking for Python installation commands
        Then: No mise install python, no apt install python3, no pyenv install
        """
        lower = dockerfile_content.lower()
        # Should not install Python via mise
        assert "mise install python" not in lower, (
            "Dockerfile should not install Python -- handled by install-deps.sh"
        )
        # Should not install Python via apt (python3-dev is OK, python3 the interpreter is not)
        # Check for explicit python3 package install (not python3-dev or python3-pip)
        for line in dockerfile_content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # Flag if we see "apt-get install" + "python3" but not "python3-" prefix packages
            if "apt-get install" in stripped.lower() and "python3 " in stripped.lower():
                pytest.fail(
                    f"Dockerfile should not install python3 interpreter via apt: {stripped}"
                )

    def test_no_node_install(self, dockerfile_content):
        """
        Given: The Dockerfile content
        When: Checking for Node.js installation commands
        Then: No mise install node, no nvm install, no apt install nodejs
        """
        lower = dockerfile_content.lower()
        assert "mise install node" not in lower, (
            "Dockerfile should not install Node.js -- handled by install-deps.sh"
        )
        assert "nvm install" not in lower, (
            "Dockerfile should not install Node.js via nvm"
        )
        for line in dockerfile_content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "apt-get install" in stripped.lower() and "nodejs" in stripped.lower():
                pytest.fail(
                    f"Dockerfile should not install nodejs via apt: {stripped}"
                )

    def test_no_playwright_chromium_install(self, dockerfile_content):
        """
        Given: The Dockerfile content
        When: Checking for Playwright Chromium binary installation
        Then: No npx playwright install or playwright install commands

        Scans each non-comment RUN line for 'playwright' combined with 'install'
        (but not 'install-deps', which only installs system packages).
        """
        for line in dockerfile_content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            lower_line = stripped.lower()
            if "playwright" in lower_line and "install" in lower_line:
                # Allow 'install-deps' (system deps only, not the browser binary)
                if "install-deps" in lower_line:
                    continue
                pytest.fail(
                    f"Dockerfile should not run 'playwright install' -- "
                    f"handled by install-deps.sh: {stripped}"
                )


"""
Test Summary
============
Total Test Classes: 6
Total Test Methods: 16

1. TestDockerfileExists (2): file exists, non-empty
2. TestDockerfileBaseImage (2): uses ubuntu:noble, no playwright reference
3. TestDockerfileSystemPackages (4): core packages, Playwright deps,
   --no-install-recommends, apt cache cleanup
4. TestDockerfileUserSetup (3): configurable UID/GID ARGs, passwordless sudo,
   non-root USER
5. TestDockerfileWorkspace (2): creates workspace dir, sets WORKDIR
6. TestDockerfileNoRuntimeInstalls (3): no Python install, no Node.js install,
   no playwright install

Coverage Areas:
- Base image selection (ubuntu:noble, no Playwright)
- Core system packages (sudo, build-essential, curl, wget, git, ca-certificates)
- Playwright Chromium system dependencies (representative subset)
- Image optimization (--no-install-recommends, apt cache cleanup)
- User setup (configurable UID/GID, passwordless sudo, non-root USER)
- Workspace setup (mkdir, WORKDIR)
- No runtime tool installs (Python, Node.js, Playwright Chromium binary)
"""

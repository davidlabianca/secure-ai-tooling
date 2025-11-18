"""
Test suite for validating Python code examples in markdown documentation.

This module extracts and executes Python code blocks from markdown files
to ensure documentation examples are accurate and functional.

Skip Markers:
    Code blocks can be marked as documentation-only by including one of
    these markers in the heading or at the top of the code block:
    - [skip-test]
    - [doc-only]
    - [documentation-only]
    - # SKIP-TEST (in code)

    Example:
        ### Example: Complex Setup [skip-test]
"""

import re
from pathlib import Path

import pytest

# Default timeout for code execution (seconds)
CODE_EXECUTION_TIMEOUT = 10

# Skip markers to detect documentation-only code blocks
SKIP_MARKERS = [
    r"\[skip-test\]",
    r"\[doc-only\]",
    r"\[documentation-only\]",
    r"#\s*SKIP-TEST",
]


def should_skip_code_block(heading: str, code: str) -> bool:
    """
    Check if a code block should be skipped based on skip markers.

    Args:
        heading: The heading text from markdown
        code: The code block content

    Returns:
        True if the code block should be skipped
    """
    # Check heading for skip markers
    for marker in SKIP_MARKERS:
        if re.search(marker, heading, re.IGNORECASE):
            return True

    # Check first few lines of code for skip marker
    first_lines = "\n".join(code.split("\n")[:3])
    if re.search(r"#\s*SKIP-TEST", first_lines, re.IGNORECASE):
        return True

    return False


def extract_python_code_blocks(md_file: Path) -> list[tuple[str, str]]:
    """
    Extract Python code blocks with their headings from a markdown file.

    Args:
        md_file: Path to markdown file

    Returns:
        List of (heading, code) tuples for each Python code block
    """
    with open(file=md_file, mode="r", encoding="utf-8") as f:
        content: str = f.read()

    # Match code blocks preceded by heading (### or deeper)
    # Uses negative lookahead to ensure no intervening headings between heading and code block
    pattern = r"###+\s+([^\n]+)\n(?:(?!^##)[\s\S])*?```python\n(.*?)```"
    matches = re.finditer(pattern, content, re.DOTALL | re.MULTILINE)

    code_blocks = []
    for match in matches:
        heading = match.group(1).strip()
        code = match.group(2)
        # Include file path in heading for easier debugging
        full_heading: str = f"{md_file.name} - {heading}"
        code_blocks.append((full_heading, code))

    return code_blocks


def collect_code_blocks_from_directories(directories: list[Path]) -> list[tuple[str, str]]:
    """
    Collect all Python code blocks from markdown files in specified directories.

    Args:
        directories: List of directories to scan

    Returns:
        List of (heading, code) tuples from all markdown files
    """
    all_code_blocks = []

    for directory in directories:
        if not directory.exists():
            continue

        for md_file in directory.glob("*.md"):
            if md_file.is_file():
                all_code_blocks.extend(extract_python_code_blocks(md_file=md_file))

    return all_code_blocks


@pytest.fixture(scope="session")
def docs_directories(request) -> list[Path]:
    """Define documentation directories to scan for Python code examples."""
    # Use pytest config to get repo root
    repo_root = Path(request.config.rootpath)
    return [
        repo_root / "risk-map" / "docs",
    ]


@pytest.fixture(scope="session")
def markdown_code_blocks(docs_directories: list[Path]) -> list[tuple[str, str]]:
    """
    Collect all Python code blocks from markdown documentation.

    Collects code blocks once per test session for efficiency.
    Skips test session if no code blocks are found.
    """
    code_blocks = collect_code_blocks_from_directories(directories=docs_directories)

    if not code_blocks:
        pytest.skip("No Python code blocks found in documentation")

    return code_blocks


def pytest_generate_tests(metafunc):
    """
    Dynamically generate test cases from collected code blocks.

    Called during test collection to parametrize tests based on
    code blocks found in markdown files.
    """
    if "markdown_example" in metafunc.fixturenames:
        # Collect code blocks from documentation directories
        repo_root = Path(metafunc.config.rootpath)
        directories = [repo_root / "risk-map" / "docs"]
        code_blocks = collect_code_blocks_from_directories(directories=directories)

        if code_blocks:
            metafunc.parametrize("markdown_example", code_blocks, ids=[block[0] for block in code_blocks])


@pytest.fixture
def isolated_namespace() -> dict:
    """
    Provide an isolated namespace for executing code examples.

    Creates a fresh namespace for each test to prevent state pollution.
    Includes common built-ins and standard library imports.
    """
    namespace = {
        "__name__": "__main__",
        "__builtins__": __builtins__,
        # Pre-import commonly used modules
        "Path": Path,
    }
    return namespace


@pytest.mark.timeout(CODE_EXECUTION_TIMEOUT)
def test_code_block(markdown_example: tuple[str, str], isolated_namespace: dict, request, monkeypatch) -> None:
    """
    Execute each Python code block to verify it runs without errors.

    Each test runs in an isolated namespace to prevent state pollution.
    Working directory is set to repo root for consistent file access.
    Execution is limited to CODE_EXECUTION_TIMEOUT seconds.

    Args:
        markdown_example: Tuple of (heading, code) from markdown file
        isolated_namespace: Fresh namespace for code execution
        request: Pytest request fixture for accessing config
        monkeypatch: Pytest fixture for environment modification
    """
    heading, code = markdown_example

    # Check if code block should be skipped
    if should_skip_code_block(heading, code):
        pytest.skip(f"Code block marked as documentation-only: {heading}")

    # Set working directory to repo root for file access
    repo_root = Path(request.config.rootpath)
    monkeypatch.chdir(repo_root)

    print(f"\nTesting: {heading}")
    print(f"Working directory: {Path.cwd()}")

    try:
        # Execute in isolated namespace with timeout protection
        exec(code, isolated_namespace)
    except Exception as e:
        pytest.fail(f"Code block '{heading}' failed:\nError: {type(e).__name__}: {str(e)}\n\nCode:\n{code}")

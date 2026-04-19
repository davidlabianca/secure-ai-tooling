#!/usr/bin/env python3
"""
Pre-commit framework hook that regenerates SVG files when Mermaid source files change.

Invoked by the pre-commit framework with staged filenames as positional argv (pass_filenames:
true). Converts .mmd/.mermaid files under risk-map/diagrams/ to SVGs under risk-map/svg/ via
the Mermaid CLI (mmdc) and git-adds them so they land in the same commit as the source change
(Mode B auto-stage).
"""

import json
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

_DIAGRAMS_DIR = "risk-map/diagrams"
_SVG_DIR = "risk-map/svg"

_PUPPETEER_ARGS = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]

_MERMAID_EXTENSIONS = (".mmd", ".mermaid")


def _build_puppeteer_config(chromium_path: str | None) -> dict:
    """
    Build the puppeteer config dict for mmdc.

    Args:
        chromium_path: Path to Chromium executable, or None/empty to use auto-detection.

    Returns:
        Config dict with 'args' always present; 'executablePath' included only when
        chromium_path is a non-empty string.
    """
    config: dict = {"args": _PUPPETEER_ARGS}
    if chromium_path:
        config["executablePath"] = chromium_path
    return config


def _output_path(input_path: str) -> str:
    """
    Compute SVG output path for a Mermaid input path.

    Swaps only the last extension (e.g. multi.dot.name.mmd → multi.dot.name.svg)
    and places the result under risk-map/svg/.

    Args:
        input_path: Repo-relative path to a Mermaid source file.

    Returns:
        Repo-relative path for the corresponding SVG output.
    """
    basename = os.path.basename(input_path)
    stem, _ = os.path.splitext(basename)
    return f"{_SVG_DIR}/{stem}.svg"


def _is_mermaid_file(path: str) -> bool:
    """
    Return True iff path ends with .mmd or .mermaid AND lives under risk-map/diagrams/.

    Args:
        path: Repo-relative file path as passed by the pre-commit framework.

    Returns:
        True if the file is a Mermaid source file in the expected directory.
    """
    if not path.endswith(_MERMAID_EXTENSIONS):
        return False
    # Normalise separators and check directory prefix
    normalised = path.replace("\\", "/")
    return normalised.startswith(f"{_DIAGRAMS_DIR}/") or f"/{_DIAGRAMS_DIR}/" in normalised


def _discover_chromium() -> str | None:
    """
    Discover a Chromium binary suitable for puppeteer.

    Priority order:
      1. CHROMIUM_PATH env var (if set and non-empty) — explicit override
      2. On Linux ARM64: search Playwright cache for `headless_shell` then `chrome`
      3. None — let mmdc use its bundled auto-detection

    Cache root: PLAYWRIGHT_BROWSERS_PATH env if set, else ~/.cache/ms-playwright.
    ARM64 Linux means: platform.system() == 'Linux' AND platform.machine() in ('aarch64', 'arm64').

    Returns:
        Absolute path string to a discovered binary, or None.
    """
    chromium_path = os.environ.get("CHROMIUM_PATH")
    if chromium_path:
        return chromium_path

    if platform.system() != "Linux" or platform.machine() not in ("aarch64", "arm64"):
        return None

    cache_root_str = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if cache_root_str:
        cache_root = Path(cache_root_str)
    else:
        cache_root = Path(os.path.expanduser("~/.cache/ms-playwright"))

    # Search for headless_shell first (Playwright's preferred headless binary)
    matches = list(cache_root.rglob("headless_shell"))
    if matches:
        return str(matches[0])

    # Fall back to chrome
    matches = list(cache_root.rglob("chrome"))
    if matches:
        return str(matches[0])

    return None


def main(argv: list[str]) -> int:
    """
    Convert staged Mermaid files to SVG and git-add the outputs.

    One puppeteer config temp file is created per invocation and shared across all
    input files. The temp file is cleaned up in a finally block regardless of outcome.

    Args:
        argv: List of staged file paths passed by the pre-commit framework.

    Returns:
        0 if all conversions and git-adds succeeded, non-zero otherwise.
    """
    mermaid_files = [p for p in argv if _is_mermaid_file(p)]

    if not mermaid_files:
        return 0

    chromium_path = _discover_chromium()
    config = _build_puppeteer_config(chromium_path)

    # One shared temp config for the entire invocation (mirrors bash behaviour)
    tmp = tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json")
    config_path = tmp.name
    try:
        json.dump(config, tmp)
        tmp.close()

        exit_code = 0

        for input_file in mermaid_files:
            output_file = _output_path(input_file)

            mmdc_cmd = [
                "npx",
                "mmdc",
                "-i",
                input_file,
                "-o",
                output_file,
                "-t",
                "neutral",
                "-b",
                "transparent",
                "-p",
                config_path,
            ]

            result = subprocess.run(mmdc_cmd)
            if result.returncode == 0:
                git_result = subprocess.run(["git", "add", output_file])
                if git_result.returncode != 0 and exit_code == 0:
                    exit_code = git_result.returncode
            elif exit_code == 0:
                exit_code = result.returncode
    finally:
        try:
            os.unlink(config_path)
        except OSError:
            pass

    return exit_code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

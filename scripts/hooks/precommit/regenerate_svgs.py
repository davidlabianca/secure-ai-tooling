#!/usr/bin/env python3
"""
Pre-commit framework hook that regenerates SVG files when Mermaid source files change.

Invoked by the pre-commit framework with staged filenames as positional argv (pass_filenames:
true). Converts .mmd/.mermaid files under risk-map/diagrams/ to SVGs under risk-map/svg/ via
the Mermaid CLI (mmdc) and git-adds them so they land in the same commit as the source change
(Mode B auto-stage).

Chained-generator input discovery (ADR-005 Addendum 2026-09-28): the pre-commit framework
computes each hook's argv from the staged set once, before any hook runs, so a diagram that
`regenerate-graphs` stages earlier in the same run never appears in this hook's own argv when
the triggering commit only touched components.yaml or mermaid-styles.yaml. This hook's input
set is therefore the union of its argv (unchanged `pass_filenames: true` behaviour) and whatever
diagram files are staged in the git index when it runs, discovered via `git diff --cached
--name-only -z --diff-filter=ACMR` -- never the working tree, since only staged content is part
of the commit being made. `-z` NUL-separates entries so a C-quoted path is read, not dropped.
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
      2. On Linux ARM64: search Playwright cache by spelling priority —
         `chrome-headless-shell` (Playwright >=1.63) then `headless_shell`
         (Playwright <1.63) then `chrome` (full browser, last resort)
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

    # Playwright 1.63 renamed the headless binary from `headless_shell` to
    # `chrome-headless-shell` (and arch-suffixed its directory). Search both
    # spellings so caches from either side of the rename resolve correctly.
    # `npx playwright install` normally garbage-collects revisions no longer
    # referenced by a `.links/` entry, so an upgraded cache usually holds only
    # the current one; both spellings still coexist when that GC is skipped
    # (PLAYWRIGHT_SKIP_BROWSER_GC=1) or another checkout's `.links` entry
    # still pins the old revision. `chrome` is the full-browser fallback when
    # no headless-shell binary is present.
    #
    # rglob matches directories as well as files by name, so every candidate
    # must be filtered with is_file() — a directory literally named "chrome"
    # (e.g. a partial extraction) must never be handed to mmdc as
    # executablePath.
    #
    # Sorting is plain lexical ascending, not revision-aware: Playwright's
    # revision scheme changed from six-digit Chromium commit positions
    # (e.g. 978106) to four-digit build numbers (e.g. 1243), so neither
    # lexical nor numeric sort reliably picks the "newest" revision across
    # that boundary. Picking among multiple revisions of the SAME spelling is
    # out of scope; only cross-spelling priority is pinned here.
    for name in ("chrome-headless-shell", "headless_shell", "chrome"):
        matches = sorted(p for p in cache_root.rglob(name) if p.is_file())
        if matches:
            return str(matches[0])

    return None


def _staged_mermaid_files() -> list[str]:
    """
    Return repo-relative paths of Mermaid diagram files staged in the git index right now.

    `--diff-filter=ACMR` covers added/copied/modified/renamed staged entries (never deletions --
    a deleted diagram has nothing to render). Queries the index (`--cached`), not the working
    tree: a diagram edited but not staged, or staged in a prior commit and merely present on
    disk, is not part of the commit this hook is chained into.

    `-z` NUL-terminates each entry and disables git's default C-quoting of paths containing
    non-ASCII or special characters (`core.quotePath`) -- splitting the plain `--name-only`
    output on newlines would silently drop or mangle a quoted path instead of matching it.

    `subprocess.run`'s result is guarded rather than trusted blindly: this module's own test
    suite patches `subprocess.run` wholesale for the mmdc/git-add calls, so this query can
    receive the same mocked result under those tests, whose `.stdout` is not a real string.
    `check=True` is avoided for the same reason it would be wrong outside tests too -- a
    real git failure here (e.g. no commits yet) degrades to "nothing staged", not a crash.

    Returns:
        Mermaid diagram paths currently staged, filtered by `_is_mermaid_file`, in the order
        `git diff` reports them.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR"],
        capture_output=True,
        text=True,
    )
    stdout = result.stdout if isinstance(result.stdout, str) else ""
    return [entry for entry in stdout.split("\0") if entry and _is_mermaid_file(entry)]


def main(argv: list[str]) -> int:
    """
    Convert staged Mermaid files to SVG and git-add the outputs.

    The set of files rendered is the order-preserving, de-duplicated union of argv's Mermaid
    files and whatever Mermaid files are staged in the index right now (ADR-005 Addendum
    2026-09-28) -- this picks up a diagram `regenerate-graphs` staged earlier in the same
    pre-commit run even when this hook's own argv carries only the YAML trigger that fired it.

    One puppeteer config temp file is created per invocation and shared across all
    input files. The temp file is cleaned up in a finally block regardless of outcome.

    Args:
        argv: List of staged file paths passed by the pre-commit framework.

    Returns:
        0 if all conversions and git-adds succeeded, non-zero otherwise.
    """
    mermaid_files: list[str] = []
    seen: set[str] = set()
    for path in [p for p in argv if _is_mermaid_file(p)] + _staged_mermaid_files():
        if path not in seen:
            seen.add(path)
            mermaid_files.append(path)

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

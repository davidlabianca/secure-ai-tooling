"""Regression tests for fork-aware persona-pages workflow guards."""

from functools import lru_cache
from pathlib import Path

import yaml

CANONICAL_REPO = "cosai-oasis/secure-ai-tooling"
CANONICAL_REPO_GUARD = f"github.repository == '{CANONICAL_REPO}'"
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "persona-pages.yml"


@lru_cache(maxsize=1)
def _load_workflow() -> dict:
    """Load the persona-pages workflow as a mapping (parsed once per session)."""
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _normalized_if(value: str) -> str:
    """Collapse multiline workflow `if:` expressions for stable assertions."""
    return " ".join(value.split())


def _build_step_if(step_name: str) -> str:
    """Return the `if:` expression for a named build step."""
    build_steps = _load_workflow()["jobs"]["build"]["steps"]
    for step in build_steps:
        if step.get("name") == step_name:
            return _normalized_if(step["if"])
    raise AssertionError(f"build step not found: {step_name}")


def test_deploy_job_is_guarded_to_canonical_main_non_pr_runs():
    """
    Given: The persona-pages deploy job can publish to GitHub Pages
    When: The job-level `if:` expression is inspected
    Then: It requires a non-PR main ref in the canonical repository
    """
    deploy_if = _normalized_if(_load_workflow()["jobs"]["deploy"]["if"])

    assert "github.event_name != 'pull_request'" in deploy_if
    assert "github.ref == 'refs/heads/main'" in deploy_if
    assert CANONICAL_REPO_GUARD in deploy_if


def test_pages_build_steps_are_guarded_to_canonical_non_pr_runs():
    """
    Given: The build job must keep running tests on forks
    When: The Pages-coupled build steps are inspected
    Then: Only the Pages setup and artifact upload steps require the canonical repo
    """
    for step_name in ("Configure GitHub Pages", "Upload GitHub Pages artifact"):
        step_if = _build_step_if(step_name)
        assert "github.event_name != 'pull_request'" in step_if
        assert CANONICAL_REPO_GUARD in step_if


def test_build_test_steps_run_on_forks():
    """
    Given: Forks must keep getting build and test feedback
    When: The test and artifact-prep build steps are inspected
    Then: None carry the canonical-repo guard, so they run on forks
    """
    # Negative lock for hard-contract item #3: a refactor that accidentally
    # adds the canonical guard to these steps would silently kill fork CI
    # feedback while leaving the positive-guard tests green.
    build_steps = _load_workflow()["jobs"]["build"]["steps"]
    fork_visible_steps = (
        "Run persona site data tests",
        "Run persona site logic tests",
        "Prepare Pages artifact",
    )
    for step_name in fork_visible_steps:
        step = next(s for s in build_steps if s.get("name") == step_name)
        assert CANONICAL_REPO not in (step.get("if") or "")


def test_pages_summary_explains_fork_skipped_deploy():
    """
    Given: Fork pushes intentionally skip the Pages deploy job
    When: The pages-summary shell script is inspected
    Then: It reports the skipped deploy as fork-specific n/a status
    """
    summary_script = _load_workflow()["jobs"]["pages-summary"]["steps"][0]["run"]

    # Lock the structural comparison (canonical-repo literal in the guard),
    # not the exact prose, so a harmless reword of the display string does
    # not break the test.
    assert f'"{CANONICAL_REPO}"' in summary_script
    assert "fork" in summary_script
    assert "n/a" in summary_script

"""Regression tests for fork-aware persona-pages workflow guards."""

from pathlib import Path

import yaml

CANONICAL_REPO = "cosai-oasis/secure-ai-tooling"
CANONICAL_REPO_GUARD = f"github.repository == '{CANONICAL_REPO}'"
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "persona-pages.yml"


def _load_workflow() -> dict:
    """Load the persona-pages workflow as a mapping."""
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


def test_pages_summary_explains_fork_skipped_deploy():
    """
    Given: Fork pushes intentionally skip the Pages deploy job
    When: The pages-summary shell script is inspected
    Then: It reports the skipped deploy as fork-specific n/a status
    """
    summary_script = _load_workflow()["jobs"]["pages-summary"]["steps"][0]["run"]

    assert f'"{CANONICAL_REPO}"' in summary_script
    assert "n/a (fork; Pages deploy not authorized)" in summary_script

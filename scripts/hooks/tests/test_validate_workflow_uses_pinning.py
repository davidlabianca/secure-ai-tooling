#!/usr/bin/env python3
"""
Tests for scripts/hooks/precommit/validate_workflow_uses_pinning.py.

The validator enforces ADR-024 for GitHub Actions workflow `uses:` references:
external actions must be pinned to a full 40-character commit SHA and carry a
same-line `# vX.Y.Z` release comment for Dependabot update tracking. Local
`./...` references are exempt. Docker action references are rejected until a
separate ADR defines their pinning policy.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "precommit"))

from validate_workflow_uses_pinning import (  # noqa: E402
    discover_workflow_files,
    format_violation,
    main,
    validate_file,
)

FULL_SHA = "0123456789abcdef0123456789abcdef01234567"
SHORT_SHA = "0123456789abcdef"
REPO_ROOT = Path(__file__).parent.parent.parent.parent


def _write_workflow(tmp_path: Path, content: str, name: str = "workflow.yml") -> Path:
    """Write a synthetic workflow and return its path."""
    workflow = tmp_path / name
    workflow.parent.mkdir(parents=True, exist_ok=True)
    workflow.write_text(content, encoding="utf-8")
    return workflow


class TestPassingReferences:
    """Valid `uses:` references produce no violations."""

    def test_external_action_with_full_sha_and_semver_comment_passes(self, tmp_path):
        """
        Given: An external action pinned to a 40-character SHA with `# vX.Y.Z`
        When: validate_file scans the workflow
        Then: It returns no violations
        """
        workflow = _write_workflow(
            tmp_path,
            f"""
name: valid
jobs:
  test:
    steps:
      - uses: actions/checkout@{FULL_SHA} # v6.0.2
""".lstrip(),
        )

        assert validate_file(workflow) == []

    def test_external_action_with_path_and_prerelease_comment_passes(self, tmp_path):
        """
        Given: An external action subpath pinned to a SHA with a prerelease tag comment
        When: validate_file scans the workflow
        Then: The owner/repo/path@sha form is accepted
        """
        workflow = _write_workflow(
            tmp_path,
            f"""
name: reusable
jobs:
  test:
    steps:
      - uses: octo-org/example/.github/actions/build@{FULL_SHA} # v1.2.3-rc.1
""".lstrip(),
        )

        assert validate_file(workflow) == []

    def test_local_relative_action_is_allowed_without_sha_or_comment(self, tmp_path):
        """
        Given: A local composite action reference using `./...`
        When: validate_file scans the workflow
        Then: The ADR-024 external-action pinning rule is not applied
        """
        workflow = _write_workflow(
            tmp_path,
            """
name: local
jobs:
  test:
    steps:
      - uses: ./.github/actions/build
""".lstrip(),
        )

        assert validate_file(workflow) == []

    def test_local_reusable_workflow_is_allowed_without_sha_or_comment(self, tmp_path):
        """
        Given: A local reusable workflow reference using `./...`
        When: validate_file scans the workflow
        Then: The local ADR-024 carve-out is accepted
        """
        workflow = _write_workflow(
            tmp_path,
            """
name: local reusable
jobs:
  test:
    uses: ./.github/workflows/reusable.yml
""".lstrip(),
        )

        assert validate_file(workflow) == []


class TestFailingReferences:
    """Invalid external `uses:` references produce actionable violations."""

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("uses: actions/checkout@v6", "full 40-character commit SHA"),
            (f"uses: actions/checkout@{SHORT_SHA} # v6.0.2", "full 40-character commit SHA"),
            ("uses: actions/checkout", "full 40-character commit SHA"),
            (f"uses: actions/checkout@{FULL_SHA}", "missing required ` # vX.Y.Z`"),
            (f"uses: actions/checkout@{FULL_SHA} # v6", "missing required ` # vX.Y.Z`"),
            (f"uses: actions/checkout@{FULL_SHA} # 6.0.2", "missing required ` # vX.Y.Z`"),
            (f"uses: actions/checkout@{FULL_SHA}# v6.0.2", "missing required ` # vX.Y.Z`"),
        ],
    )
    def test_invalid_external_action_references_fail(self, tmp_path, line, expected):
        """
        Given: An external `uses:` reference that violates ADR-024
        When: validate_file scans the workflow
        Then: One violation identifies the specific policy gap
        """
        workflow = _write_workflow(
            tmp_path,
            f"""
name: invalid
jobs:
  test:
    steps:
      - {line}
""".lstrip(),
        )

        violations = validate_file(workflow)

        assert len(violations) == 1
        assert expected in violations[0].message

    def test_docker_action_reference_fails_for_maintainer_review(self, tmp_path):
        """
        Given: A `docker://` action reference
        When: validate_file scans the workflow
        Then: The validator rejects it until a Docker pinning policy exists
        """
        workflow = _write_workflow(
            tmp_path,
            """
name: docker action
jobs:
  test:
    steps:
      - uses: docker://alpine:3.20
""".lstrip(),
        )

        violations = validate_file(workflow)

        assert len(violations) == 1
        assert "docker:// action references require maintainer review" in violations[0].message

    def test_violation_format_includes_file_line_and_reference(self, tmp_path):
        """
        Given: A workflow with an invalid external action on line 6
        When: format_violation renders the finding
        Then: The message names the offending file, line, and reference
        """
        workflow = _write_workflow(
            tmp_path,
            """
name: line numbers
jobs:
  test:
    steps:
      - name: Checkout
        uses: actions/checkout@v6
""".lstrip(),
        )

        violation = validate_file(workflow)[0]
        rendered = format_violation(violation)

        assert f"{workflow}:6:" in rendered
        assert "actions/checkout@v6" in rendered


class TestWorkflowDiscovery:
    """Workflow discovery matches the issue #264 scan scope."""

    def test_discovery_finds_root_and_nested_yml_workflows_only(self, tmp_path):
        """
        Given: Root, nested, and non-yml files under .github/workflows
        When: discover_workflow_files scans the repository root
        Then: It returns only .yml workflows, including nested paths
        """
        root_workflow = _write_workflow(tmp_path / ".github" / "workflows", "name: root\n", "root.yml")
        nested_workflow = _write_workflow(
            tmp_path / ".github" / "workflows" / "nested",
            "name: nested\n",
            "nested.yml",
        )
        _write_workflow(tmp_path / ".github" / "workflows", "name: yaml\n", "ignored.yaml")
        _write_workflow(tmp_path / ".github" / "not-workflows", "name: ignored\n", "ignored.yml")

        discovered = discover_workflow_files(tmp_path)

        assert discovered == [root_workflow, nested_workflow]


class TestCli:
    """The CLI exits non-zero only when violations are present."""

    def test_main_returns_zero_for_valid_workflow(self, tmp_path, capsys):
        """
        Given: A valid workflow file
        When: main is invoked with the workflow path
        Then: It returns 0 and emits no stderr output
        """
        workflow = _write_workflow(
            tmp_path,
            f"jobs:\n  test:\n    steps:\n      - uses: actions/checkout@{FULL_SHA} # v6.0.2\n",
        )

        exit_code = main([str(workflow)])

        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_main_returns_one_and_writes_violations_to_stderr(self, tmp_path, capsys):
        """
        Given: An invalid workflow file
        When: main is invoked with the workflow path
        Then: It returns 1 and writes the file:line violation to stderr
        """
        workflow = _write_workflow(tmp_path, "jobs:\n  test:\n    steps:\n      - uses: actions/checkout@v6\n")

        exit_code = main([str(workflow)])
        captured = capsys.readouterr()

        assert exit_code == 1
        assert f"{workflow}:4:" in captured.err
        assert "full 40-character commit SHA" in captured.err


class TestCiIntegration:
    """The existing CI workflow runs the same validator for workflow changes."""

    def test_python_validation_workflow_runs_pinning_validator(self):
        """
        Given: The repository's Python validation workflow
        When: its source is inspected
        Then: Workflow YAML changes trigger the validator in CI
        """
        workflow = REPO_ROOT / ".github" / "workflows" / "validate_python.yml"
        content = workflow.read_text(encoding="utf-8")

        assert "'.github/workflows/*.yml'" in content
        assert "'.github/workflows/**/*.yml'" in content
        assert "scripts/hooks/precommit/validate_workflow_uses_pinning.py" in content

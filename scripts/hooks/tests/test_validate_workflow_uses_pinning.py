#!/usr/bin/env python3
"""
Tests for scripts/hooks/precommit/validate_workflow_uses_pinning.py.

The validator enforces ADR-024 for GitHub Actions workflow `uses:` references:
external actions must be pinned to a full 40-character commit SHA and carry a
same-line `# vX.Y.Z` release comment for Dependabot update tracking. Local
`./...` references are exempt.

ADR-024 D7: `docker://` references are warned (stderr, prefix
`validate-workflow-uses-pinning: warning:`) but do not fail the build (exit 0).

ADR-024 D6: the separator between SHA and comment is exactly ` # ` (one space,
hash, one space). Two spaces before `#` is a violation.

API CONTRACT for `validate_file`:
    validate_file(path: Path) -> tuple[list[Violation], list[Violation]]

    The return value is (errors, warnings).
    - errors: violations that cause exit code 1
    - warnings: findings that are emitted to stderr but do not affect exit code
    - Both lists are empty for a fully-compliant file.

    The SWE agent must update `validate_file` to return this tuple shape.
    `main()` continues to return int (0 or 1). Warnings from `validate_file`
    are printed to stderr with the prefix
    `validate-workflow-uses-pinning: warning:` and do not contribute to the
    exit code.
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

        errors, warnings = validate_file(workflow)
        assert errors == []
        assert warnings == []

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

        errors, warnings = validate_file(workflow)
        assert errors == []
        assert warnings == []

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

        errors, warnings = validate_file(workflow)
        assert errors == []
        assert warnings == []

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

        errors, warnings = validate_file(workflow)
        assert errors == []
        assert warnings == []

    def test_standard_happy_path_at_step_indentation_passes(self, tmp_path):
        """
        Regression-safety pin alongside the new adversarial cases.

        Given: A correctly-pinned step `uses:` at normal indentation
        When: validate_file scans the workflow
        Then: No errors and no warnings are returned

        This is the same form validated by ADR-024 D6 and serves as a stable
        baseline to run alongside block-scalar and other adversarial cases.
        """
        workflow = _write_workflow(
            tmp_path,
            f"""
name: happy path
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@{FULL_SHA} # v6.0.2
""".lstrip(),
        )

        errors, warnings = validate_file(workflow)
        assert errors == []
        assert warnings == []


class TestFailingReferences:
    """Invalid external `uses:` references produce actionable violations."""

    @pytest.mark.parametrize(
        ("line", "expected"),
        [
            ("uses: actions/checkout@v6", "full 40-character commit SHA"),
            ('"uses": actions/checkout@v6', "full 40-character commit SHA"),
            ("'uses': actions/checkout@v6", "full 40-character commit SHA"),
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
        Then: One error identifies the specific policy gap
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

        errors, warnings = validate_file(workflow)

        assert len(errors) == 1
        assert expected in errors[0].message

    def test_quoted_job_level_uses_key_fails(self, tmp_path):
        """
        Given: A job-level reusable workflow reference with a quoted `uses` key
        When: validate_file scans the workflow
        Then: It treats the quoted key as a real GitHub Actions `uses` field
        """
        workflow = _write_workflow(
            tmp_path,
            """
name: quoted job key
jobs:
  reusable:
    "uses": octo-org/example/.github/workflows/build.yml@main
""".lstrip(),
        )

        errors, warnings = validate_file(workflow)

        assert len(errors) == 1
        assert "full 40-character commit SHA" in errors[0].message

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

        errors, _warnings = validate_file(workflow)
        violation = errors[0]
        rendered = format_violation(violation)

        assert f"{workflow}:6:" in rendered
        assert "actions/checkout@v6" in rendered


class TestDockerWarning:
    """ADR-024 D7: `docker://` references are warned, not blocked."""

    def test_docker_action_reference_warns_for_maintainer_review(self, tmp_path):
        """
        Given: A `docker://` action reference (ADR-024 D7)
        When: validate_file scans the workflow
        Then: No errors are produced; one warning identifies the reference with ADR-024 D7

        The warning message must contain `ADR-024 D7` so consumers can grep
        for the specific policy context.
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

        errors, warnings = validate_file(workflow)

        assert errors == [], "docker:// reference must not produce an error (ADR-024 D7)"
        assert len(warnings) == 1
        assert "ADR-024 D7" in warnings[0].message
        assert "docker://alpine:3.20" in warnings[0].reference

    def test_docker_action_main_returns_zero(self, tmp_path, capsys):
        """
        Given: A workflow with only a `docker://` reference
        When: main is invoked with the workflow path
        Then: Exit code is 0 (warnings don't fail the build per ADR-024 D7)

        The stderr output must contain the warning prefix
        `validate-workflow-uses-pinning: warning:` and `ADR-024 D7`.
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

        exit_code = main([str(workflow)])
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "validate-workflow-uses-pinning: warning:" in captured.err
        assert "ADR-024 D7" in captured.err

    def test_docker_warning_stderr_includes_file_and_line(self, tmp_path, capsys):
        """
        Given: A workflow with a `docker://` reference
        When: main is invoked
        Then: stderr identifies the file path and line number of the warning
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

        main([str(workflow)])
        captured = capsys.readouterr()

        # The warning line must embed the file path and the reference.
        assert str(workflow) in captured.err
        assert "docker://alpine:3.20" in captured.err

    def test_docker_warning_with_real_violation_returns_one(self, tmp_path, capsys):
        """
        Given: A workflow with both a `docker://` reference and a real pinning error
        When: main is invoked
        Then: Exit code is 1 (the error drives the exit) and stderr contains both findings

        The docker:// warning is still emitted even when errors are present.
        """
        workflow = _write_workflow(
            tmp_path,
            """
name: mixed
jobs:
  test:
    steps:
      - uses: docker://alpine:3.20
      - uses: actions/checkout@v6
""".lstrip(),
        )

        exit_code = main([str(workflow)])
        captured = capsys.readouterr()

        assert exit_code == 1
        # The docker warning must still appear.
        assert "validate-workflow-uses-pinning: warning:" in captured.err
        assert "ADR-024 D7" in captured.err
        # The pinning error must also appear.
        assert "full 40-character commit SHA" in captured.err


class TestAdversarialParsing:
    """
    Edge cases that exercise PyYAML AST-based parsing.

    These cases either silently pass (false negatives) or fail incorrectly
    under the current line-regex implementation. The tests define the contract
    for the AST-based implementation the SWE agent will write.

    PyYAML parses structure and provides line numbers; the validator re-reads
    the source line for comment extraction (PyYAML does not preserve comments).
    """

    def test_latest_tag_reference_fails(self, tmp_path):
        """
        Given: A `uses:` with the `@latest` floating tag (ADR-024 D2)
        When: validate_file scans the workflow
        Then: One error citing the missing full SHA is produced

        `@latest` is a mutable tag; it must be replaced with a pinned SHA.
        """
        workflow = _write_workflow(
            tmp_path,
            """
name: latest
jobs:
  test:
    steps:
      - uses: actions/checkout@latest
""".lstrip(),
        )

        errors, warnings = validate_file(workflow)

        assert len(errors) == 1
        assert "full 40-character commit SHA" in errors[0].message

    def test_two_spaces_before_hash_fails(self, tmp_path):
        """
        Given: A SHA-pinned `uses:` with two spaces before `#` instead of one
        When: validate_file scans the workflow
        Then: One error citing the missing ` # vX.Y.Z` separator is produced

        ADR-024 D6 requires exactly one space before and after `#`. Two spaces
        fail the mechanical separator check.
        """
        workflow = _write_workflow(
            tmp_path,
            # Two spaces between SHA and `#` — note the double-space in the f-string.
            f"""
name: two-space separator
jobs:
  test:
    steps:
      - uses: actions/checkout@{FULL_SHA}  # v1.2.3
""".lstrip(),
        )

        errors, warnings = validate_file(workflow)

        assert len(errors) == 1
        assert "missing required ` # vX.Y.Z`" in errors[0].message

    def test_crlf_line_endings_pass(self, tmp_path):
        """
        Given: A valid workflow file with CRLF (`\\r\\n`) line endings
        When: validate_file scans the workflow
        Then: No errors and no warnings are produced

        CRLF is the native line ending on Windows. The validator must strip
        carriage returns before applying line-level checks.
        """
        content = (
            f"name: crlf\r\n"
            f"jobs:\r\n"
            f"  test:\r\n"
            f"    steps:\r\n"
            f"      - uses: actions/checkout@{FULL_SHA} # v6.0.2\r\n"
        )
        workflow = _write_workflow(tmp_path, content)

        errors, warnings = validate_file(workflow)

        assert errors == []
        assert warnings == []

    def test_hash_inside_quoted_reference_fails(self, tmp_path):
        """
        Given: A `uses:` value with the SHA and `# v1.2.3` inside double quotes
        When: validate_file scans the workflow (via PyYAML AST)
        Then: One error is produced because the quoted value is not a bare SHA

        PyYAML parses `"actions/checkout@<sha> # v1.2.3"` as the literal string
        value `actions/checkout@<sha> # v1.2.3` (including the `# v1.2.3` part).
        That value does not match the `owner/repo@<40-hex>` pattern, so the
        validator must report a violation. There is no real trailing comment.

        Under line-regex parsing this case passes incorrectly because the regex
        sees a `#` and treats the text after it as a comment. PyYAML AST
        corrects this.
        """
        workflow = _write_workflow(
            tmp_path,
            # The entire string including `# v1.2.3` is the YAML value.
            f"""
name: quoted hash
jobs:
  test:
    steps:
      - uses: "actions/checkout@{FULL_SHA} # v1.2.3"
""".lstrip(),
        )

        errors, warnings = validate_file(workflow)

        assert len(errors) == 1, (
            "A `#` embedded in a quoted scalar is part of the value, not a comment; "
            "the resulting reference is not a bare SHA and must fail"
        )

    def test_matrix_nested_uses_is_detected(self, tmp_path):
        """
        Given: A workflow with `strategy.matrix` and a step `uses:` inside a matrix job
        When: validate_file scans the workflow (via PyYAML AST)
        Then: The `uses:` violation is detected regardless of nesting depth

        The AST walk must reach `uses:` keys at any nesting level, not only in
        flat step lists. This confirms the validator is not fooled by the
        `strategy:` mapping wrapping the job.
        """
        workflow = _write_workflow(
            tmp_path,
            """
name: matrix
jobs:
  build:
    strategy:
      matrix:
        python-version: ['3.11', '3.12']
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
""".lstrip(),
        )

        errors, warnings = validate_file(workflow)

        assert len(errors) == 1
        assert "full 40-character commit SHA" in errors[0].message

    def test_folded_scalar_uses_value_fails(self, tmp_path):
        """
        Given: A `uses:` key whose value is a folded block scalar (`>`)
        When: validate_file scans the workflow (via PyYAML AST)
        Then: One error is produced for the missing ` # vX.Y.Z` comment

        PyYAML resolves `uses: >\\n  actions/checkout@<sha>\\n` to the string
        `actions/checkout@<sha>` (SHA only, no trailing newline after folding).
        The source lines for a block scalar cannot carry a same-line `# vX.Y.Z`
        comment on the `uses:` key line itself, so the validator must report a
        violation. The line-regex implementation silently skips this case.
        """
        workflow = _write_workflow(
            tmp_path,
            f"""
name: folded scalar
jobs:
  test:
    steps:
      - uses: >
          actions/checkout@{FULL_SHA}
""".lstrip(),
        )

        errors, warnings = validate_file(workflow)

        assert len(errors) == 1, (
            "A folded-scalar `uses:` value cannot carry a same-line comment; it must be reported as a violation"
        )
        assert "missing required ` # vX.Y.Z`" in errors[0].message

    def test_literal_scalar_uses_value_fails(self, tmp_path):
        """
        Given: A `uses:` key whose value is a literal block scalar (`|`)
        When: validate_file scans the workflow (via PyYAML AST)
        Then: One error is produced for the missing ` # vX.Y.Z` comment

        Same reasoning as the folded-scalar case: `uses: |\\n  ...` resolves to
        the reference string with a trailing newline. No same-line comment is
        possible on the `uses:` key line. The line-regex implementation silently
        skips this case.
        """
        workflow = _write_workflow(
            tmp_path,
            f"""
name: literal scalar
jobs:
  test:
    steps:
      - uses: |
          actions/checkout@{FULL_SHA}
""".lstrip(),
        )

        errors, warnings = validate_file(workflow)

        assert len(errors) == 1, (
            "A literal-scalar `uses:` value cannot carry a same-line comment; it must be reported as a violation"
        )
        assert "missing required ` # vX.Y.Z`" in errors[0].message


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
    """The validate_workflows.yml CI workflow runs the validator for workflow changes."""

    def test_validate_workflows_workflow_runs_pinning_validator(self):
        """
        Given: The repository's workflow validation CI file at
               `.github/workflows/validate_workflows.yml`
        When: its source is inspected
        Then:
          - The file exists
          - It references `scripts/hooks/precommit/validate_workflow_uses_pinning.py`
          - Its `paths:` triggers include `.github/workflows/**/*.yml`
          - `validate_python.yml` does NOT reference the pinning validator
          - `validate_python.yml` does NOT have `.github/workflows/*.yml` in its
            `paths:` filter (confirms the validator was not re-bolted there)

        The negative assertion on `validate_python.yml` prevents accidental
        re-addition of the validator to the Python workflow after it was moved
        to `validate_workflows.yml`.
        """
        validate_workflows = REPO_ROOT / ".github" / "workflows" / "validate_workflows.yml"
        validate_python = REPO_ROOT / ".github" / "workflows" / "validate_python.yml"

        assert validate_workflows.exists(), (
            f"validate_workflows.yml not found at {validate_workflows}; "
            "the pinning validator CI must live in this file (not validate_python.yml)"
        )

        wf_content = validate_workflows.read_text(encoding="utf-8")
        assert "scripts/hooks/precommit/validate_workflow_uses_pinning.py" in wf_content, (
            "validate_workflows.yml must invoke validate_workflow_uses_pinning.py"
        )
        assert ".github/workflows/**/*.yml" in wf_content, (
            "validate_workflows.yml paths trigger must include `.github/workflows/**/*.yml`"
        )

        py_content = validate_python.read_text(encoding="utf-8")
        assert "validate_workflow_uses_pinning.py" not in py_content, (
            "validate_python.yml must not reference validate_workflow_uses_pinning.py; "
            "the validator now lives in validate_workflows.yml"
        )
        assert ".github/workflows/" not in py_content, (
            "validate_python.yml must not have `.github/workflows/` in its paths filter; "
            "workflow path triggers belong in validate_workflows.yml"
        )

    def test_validate_workflows_workflow_itself_uses_adr024_pin_form(self):
        """
        Given: `.github/workflows/validate_workflows.yml`
        When: its `uses:` references are inspected
        Then: Every external `uses:` line in the file follows ADR-024 D6 pin form
              (full 40-char SHA + ` # vX.Y.Z` comment)

        This is the self-test property: the lint workflow must be a correct
        example of the policy it enforces. If this test fails, the CI workflow
        is breaking its own rule.
        """
        validate_workflows = REPO_ROOT / ".github" / "workflows" / "validate_workflows.yml"
        assert validate_workflows.exists(), f"validate_workflows.yml missing at {validate_workflows}"

        errors, warnings = validate_file(validate_workflows)

        assert errors == [], "validate_workflows.yml has pinning errors (self-test failure): " + "; ".join(
            e.message for e in errors
        )


"""
Test Summary
============
Total Tests: 32
- TestPassingReferences: 5 (happy path + regression pin)
- TestFailingReferences: 11 (parametrized 9 + quoted key + format test)
- TestDockerWarning: 4 (D7 warning contract)
- TestAdversarialParsing: 7 (new AST-gap cases)
- TestWorkflowDiscovery: 1
- TestCli: 2
- TestCiIntegration: 2 (rewritten)

Coverage Areas:
- ADR-024 D6 pin form (single-space separator, two-space rejection)
- ADR-024 D7 docker:// warning (not error, exit 0)
- PyYAML AST parsing gaps: folded scalar, literal scalar, quoted hash, matrix nesting
- CRLF line ending tolerance
- @latest tag rejection
- CI workflow routing (validate_workflows.yml, not validate_python.yml)
- Self-test: validate_workflows.yml follows its own pinning policy
"""

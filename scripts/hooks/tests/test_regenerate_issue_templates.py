#!/usr/bin/env python3
"""
Tests for scripts/hooks/precommit/regenerate_issue_templates.py

The wrapper is invoked by the pre-commit framework with `pass_filenames:
false` after the framework's `files:` regex matches any of:

  - scripts/TEMPLATES/<anything>.yml
  - risk-map/schemas/<anything>.schema.json
  - risk-map/yaml/frameworks.yaml

When invoked, the wrapper unconditionally runs
`python3 scripts/generate_issue_templates.py` and git-adds the
`.github/ISSUE_TEMPLATE` directory. argv is ignored — the framework is the
scheduler.

Test coverage focuses on the subprocess call shape, the
generation-then-stage ordering, and failure propagation. There is no
argv-based gate to exercise (the wrapper regenerates unconditionally to
avoid the concurrent-git-add bug that a per-file gate produced when
pre-commit batched invocations on --all-files).
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "precommit"))

from regenerate_issue_templates import main  # noqa: E402

CMD_GENERATE = ["python3", "scripts/generate_issue_templates.py"]
GIT_ADD_TEMPLATES = ["git", "add", ".github/ISSUE_TEMPLATE"]


def _make_subprocess_mock(returncode: int = 0) -> MagicMock:
    """Return a MagicMock for subprocess.run with the given returncode."""
    mock = MagicMock()
    mock.returncode = returncode
    return mock


# ===========================================================================
# Happy path: unconditional regeneration when invoked
# ===========================================================================


class TestHappyPath:
    def test_empty_argv_still_regenerates_and_stages(self):
        """
        The framework uses pass_filenames: false, so argv is empty. Reaching
        main() means regeneration is wanted — do not short-circuit.

        Given: main([]) is called (framework-style invocation)
        When: both subprocesses succeed
        Then: generation runs, git add runs, exit 0
        """
        # Implementation must use `subprocess.run(...)` (not `from subprocess import run`)
        # for this patch target to intercept calls.
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            result = main([])

        assert result == 0
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert calls == [CMD_GENERATE, GIT_ADD_TEMPLATES], (
            f"Expected exactly CMD_GENERATE then GIT_ADD_TEMPLATES; got: {calls}"
        )

    def test_argv_content_is_ignored(self):
        """
        Any argv — including non-trigger files — still produces exactly one
        regeneration + one git add.

        Given: argv with arbitrary paths (trigger-matching or not)
        When: main() is called
        Then: exit 0, still exactly one gen + one git add (argv ignored)
        """
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            result = main(
                [
                    "README.md",
                    "scripts/TEMPLATES/new_component.template.yml",
                    "risk-map/yaml/frameworks.yaml",
                ]
            )

        assert result == 0
        assert mock_run.call_count == 2, "Exactly one gen + one git add regardless of argv content"


# ===========================================================================
# Subprocess command shape (exact list equality)
# ===========================================================================


class TestSubprocessCommandShape:
    def test_generation_command_is_exact(self):
        """Generation command must be ["python3", "scripts/generate_issue_templates.py"]."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([])

        assert mock_run.call_args_list[0].args[0] == CMD_GENERATE

    def test_git_add_command_is_exact(self):
        """git add command must be ["git", "add", ".github/ISSUE_TEMPLATE"]."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([])

        assert mock_run.call_args_list[1].args[0] == GIT_ADD_TEMPLATES

    def test_all_commands_use_list_form(self):
        """Every subprocess call must use list form (no shell=True)."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            main([])

        for call in mock_run.call_args_list:
            assert isinstance(call.args[0], list), f"Command must be list-form: {call.args[0]!r}"
            assert call.kwargs.get("shell") is not True, "shell=True must not be passed"


# ===========================================================================
# Failure modes
# ===========================================================================


class TestFailureModes:
    def test_generation_fails_git_add_not_called(self):
        """
        Given: generation returns non-zero
        When: main() is called
        Then: git add is NOT called, exit code matches generation rc
        """

        def side_effect(cmd, **kwargs):
            if cmd == CMD_GENERATE:
                return _make_subprocess_mock(2)
            return _make_subprocess_mock(0)

        with patch("subprocess.run", side_effect=side_effect) as mock_run:
            result = main([])

        assert result == 2
        calls = [c.args[0] for c in mock_run.call_args_list]
        assert CMD_GENERATE in calls
        assert GIT_ADD_TEMPLATES not in calls, "git add must not run when generation fails"

    def test_git_add_fails_returns_nonzero(self):
        """
        Given: generation succeeds but git add fails
        When: main() is called
        Then: exit code is the git add rc
        """

        def side_effect(cmd, **kwargs):
            if cmd == GIT_ADD_TEMPLATES:
                return _make_subprocess_mock(5)
            return _make_subprocess_mock(0)

        with patch("subprocess.run", side_effect=side_effect):
            result = main([])

        assert result == 5

    def test_both_succeed_returns_zero(self):
        """Both subprocesses succeed → exit 0."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            result = main([])

        assert result == 0
        assert mock_run.call_count == 2


# ===========================================================================
# D6 structural-contract tests (ADR-026 D2, D3, D6)
#
# These tests encode the source-coverage and orphan-prevention contracts
# defined in ADR-026. They operate on the generator package and filesystem
# directly — no subprocess mocking required.
#
# Naming note: no phasing language (RED/GREEN/phase-X) in names or docstrings.
# Issue and ADR numbers are fine as documentation references.
# ===========================================================================


# Entity-type and operation constants that define the coverage contract.
# Changing these is the authoritative act of adding/removing a template scope.
_ENTITY_TYPES = {"risk", "control", "component", "persona"}
_OPERATIONS = {"new", "update"}

# Output names excluded from the entity-template coverage contract per ADR-026 D1.
_D1_EXCLUSIONS = {"config", "infrastructure"}


class TestSourceCoverageContract:
    """
    Asserts that the generator's source inventory satisfies ADR-026 D2.

    ADR-026 D2 requires one source template for every content-entity output:
    {new, update} × {risk, control, component, persona} = 8 sources.
    """

    def test_get_available_templates_returns_all_eight_entity_sources(self, repo_root: Path) -> None:
        """
        Asserts that get_available_templates() returns exactly the 8
        content-entity source names required by ADR-026 D2.

        Given: The scripts/TEMPLATES directory after backfill is complete
        When: get_available_templates() is called on IssueTemplateGenerator
        Then: The returned set equals {new,update} × {risk,control,component,persona}

        Issue: #326 / ADR-026 D2.
        """
        import sys

        sys.path.insert(0, str(repo_root / "scripts" / "hooks"))
        from issue_template_generator.generator import IssueTemplateGenerator

        gen = IssueTemplateGenerator(repo_root)
        available = set(gen.get_available_templates())

        expected = {f"{op}_{entity}" for op in _OPERATIONS for entity in _ENTITY_TYPES}

        missing = expected - available
        unexpected = available - expected

        assert available == expected, (
            f"Source coverage mismatch (ADR-026 D2). "
            f"Missing sources: {sorted(missing)}. "
            f"Unexpected sources: {sorted(unexpected)}. "
            f"Expected exactly: {sorted(expected)}."
        )

    def test_source_names_derive_from_operations_and_entity_types(self, repo_root: Path) -> None:
        """
        Verifies that each expected source name follows the {operation}_{entity}
        pattern — the contract is declarative, not a hardcoded name blob.

        Given: The {new,update} × {risk,control,component,persona} decision
        When: Each expected name is checked against the template source directory
        Then: All 8 template source files exist on disk

        Issue: #326 / ADR-026 D2.
        """
        templates_dir = repo_root / "scripts" / "TEMPLATES"
        for op in _OPERATIONS:
            for entity in _ENTITY_TYPES:
                source_file = templates_dir / f"{op}_{entity}.template.yml"
                assert source_file.exists(), (
                    f"Missing source template (ADR-026 D2): {source_file.name}. "
                    f"All {len(_OPERATIONS) * len(_ENTITY_TYPES)} content-entity "
                    f"sources must exist in scripts/TEMPLATES/."
                )


class TestOrphanPreventionContract:
    """
    Asserts that every content-entity output in .github/ISSUE_TEMPLATE/ has
    a matching source in scripts/TEMPLATES/, per ADR-026 D6.

    config.yml and infrastructure.yml are excluded from this contract
    per ADR-026 D1 (non-entity templates are managed directly).
    """

    def test_no_content_entity_output_exists_without_a_source(self, repo_root: Path) -> None:
        """
        Asserts that every content-entity output file has a corresponding
        source template in scripts/TEMPLATES/.

        config.yml and infrastructure.yml are excluded per ADR-026 D1.

        Given: The .github/ISSUE_TEMPLATE/ directory
        When: All .yml files except D1 exclusions are examined
        Then: Every output stem maps to an existing source .template.yml

        Issue: #326 / ADR-026 D6.
        """
        output_dir = repo_root / ".github" / "ISSUE_TEMPLATE"
        templates_dir = repo_root / "scripts" / "TEMPLATES"

        assert output_dir.exists(), f"Output directory not found: {output_dir}"

        orphans = []
        for output_file in sorted(output_dir.glob("*.yml")):
            stem = output_file.stem
            if stem in _D1_EXCLUSIONS:
                # config.yml and infrastructure.yml excluded per ADR-026 D1
                continue
            source = templates_dir / f"{stem}.template.yml"
            if not source.exists():
                orphans.append(output_file.name)

        assert not orphans, (
            f"Orphan outputs detected (ADR-026 D6): {orphans}. "
            f"Each content-entity output requires a source in scripts/TEMPLATES/. "
            f"Excluded from check (ADR-026 D1): {sorted(_D1_EXCLUSIONS)}."
        )

    def test_source_set_equals_content_entity_output_set(self, repo_root: Path) -> None:
        """
        Asserts that the set of source template names exactly equals the set
        of content-entity output names, so neither side has unmatched files.

        Given: scripts/TEMPLATES/ sources and .github/ISSUE_TEMPLATE/ outputs
        When: D1 exclusions are removed from the output set
        Then: source_names == output_names (bijection)

        Issue: #326 / ADR-026 D6.
        """
        import sys

        sys.path.insert(0, str(repo_root / "scripts" / "hooks"))
        from issue_template_generator.generator import IssueTemplateGenerator

        gen = IssueTemplateGenerator(repo_root)
        source_names = set(gen.get_available_templates())

        output_dir = repo_root / ".github" / "ISSUE_TEMPLATE"
        output_names = {f.stem for f in output_dir.glob("*.yml") if f.stem not in _D1_EXCLUSIONS}

        assert source_names == output_names, (
            f"Source/output mismatch (ADR-026 D6). "
            f"Sources without outputs: {sorted(source_names - output_names)}. "
            f"Outputs without sources (orphans): {sorted(output_names - source_names)}."
        )


class TestPerSourceRegenerationDeterminism:
    """
    Asserts that generating each of the 8 content-entity templates twice
    produces byte-identical output and valid YAML / GitHub issue form structure
    (ADR-026 D6 determinism and correctness contract).
    """

    def test_each_source_renders_deterministically(self, repo_root: Path) -> None:
        """
        Asserts that every source template renders to byte-identical output
        on two successive calls (determinism/idempotency contract per ADR-026 D6).

        Given: All 8 source templates exist (after backfill)
        When: generate_template() is called twice for each source
        Then: Both calls return byte-identical content

        Fails for any source whose rendering is non-deterministic.
        Issue: #326 / ADR-026 D6.
        """
        import sys

        sys.path.insert(0, str(repo_root / "scripts" / "hooks"))
        from issue_template_generator.generator import IssueTemplateGenerator

        gen = IssueTemplateGenerator(repo_root)
        expected_names = {f"{op}_{entity}" for op in _OPERATIONS for entity in _ENTITY_TYPES}

        for name in sorted(expected_names):
            template_file = repo_root / "scripts" / "TEMPLATES" / f"{name}.template.yml"
            assert template_file.exists(), (
                f"Source template missing (prerequisite for determinism test): {template_file.name}"
            )
            # dry_run=True renders without writing, so we can call it twice safely.
            render_1 = gen.generate_template(name, dry_run=True)
            render_2 = gen.generate_template(name, dry_run=True)
            # Reject the vacuous case: when no output file exists yet, dry_run
            # returns a fixed "New file: ..." string with no rendering involved,
            # which would make the equality check trivially true.
            assert not str(render_1).startswith("New file:"), (
                f"Determinism check is vacuous for {name}: output file does not exist, "
                f"so dry_run returned a placeholder string rather than rendered content."
            )
            assert render_1 == render_2, f"Non-deterministic rendering for {name}: two successive renders differ."

    def test_each_source_renders_to_valid_yaml(self, repo_root: Path, tmp_path: Path) -> None:
        """
        Asserts that every source template renders to valid YAML that parses
        without error and contains the required 'name' field (GitHub issue form
        minimum contract).

        Given: All 8 source templates exist (after backfill)
        When: Each template is rendered and the output is parsed
        Then: yaml.safe_load() succeeds and 'name' key is present

        Issue: #326 / ADR-026 D6.
        """
        import sys

        import yaml

        sys.path.insert(0, str(repo_root / "scripts" / "hooks"))
        from issue_template_generator.generator import IssueTemplateGenerator

        # Use a tmp output dir to avoid touching the real repo during testing
        gen = IssueTemplateGenerator(repo_root)
        expected_names = {f"{op}_{entity}" for op in _OPERATIONS for entity in _ENTITY_TYPES}

        for name in sorted(expected_names):
            template_file = repo_root / "scripts" / "TEMPLATES" / f"{name}.template.yml"
            if not template_file.exists():
                # Report the missing source as a failure, not a skip
                raise AssertionError(
                    f"Source template missing (prerequisite): {template_file.name}. Cannot validate rendered YAML."
                )
            # dry_run returns the diff string or "New file: ...\n" — use write mode
            # into tmp_path to capture the rendered content
            gen.output_dir = tmp_path
            output_path = gen.generate_template(name, dry_run=False)
            assert isinstance(output_path, Path), f"generate_template returned non-Path for {name}"

            rendered = output_path.read_text(encoding="utf-8")
            try:
                parsed = yaml.safe_load(rendered)
            except Exception as exc:
                raise AssertionError(f"Rendered output for {name} is not valid YAML: {exc}") from exc

            assert isinstance(parsed, dict), f"Rendered output for {name} does not parse as a YAML dict."
            assert "name" in parsed, (
                f"Rendered output for {name} is missing the required 'name' field (GitHub issue form minimum)."
            )

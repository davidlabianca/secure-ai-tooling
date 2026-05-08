#!/usr/bin/env python3
"""
Structural validation tests for the pre-commit framework integration (#211).

Replaces the prior test suite for the deleted bash installer
(scripts/install-precommit-hook.sh). The framework migration moved hook
installation to `python3 -m pre_commit install` and hook configuration to
.pre-commit-config.yaml, so these tests assert that:

  - `pre-commit` is a pinned dependency in requirements.txt
  - .pre-commit-config.yaml is present at the repo root and parses as YAML
  - all expected hook ids are declared
  - each local hook has the spec-required entry, files regex, and pass_filenames
  - install-deps.sh Step 8 invokes `pre-commit install`

These are static checks: nothing is executed. Behavioral parity with the
prior bash hook is verified separately by the parity harness at
scripts/hooks/tests/precommit_parity.sh.
"""

import re
from pathlib import Path

import yaml

# Repo root is four levels up from this file (scripts/hooks/tests/<here>).
REPO_ROOT = Path(__file__).parent.parent.parent.parent

CONFIG_PATH = REPO_ROOT / ".pre-commit-config.yaml"
REQUIREMENTS_PATH = REPO_ROOT / "requirements.txt"
INSTALL_DEPS_PATH = REPO_ROOT / "scripts" / "tools" / "install-deps.sh"


def _load_config() -> dict:
    """Return the parsed .pre-commit-config.yaml as a dict."""
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _all_hooks() -> list[dict]:
    """Return every hook declaration across all repos in the config."""
    config = _load_config()
    hooks: list[dict] = []
    for repo in config.get("repos", []):
        hooks.extend(repo.get("hooks", []))
    return hooks


def _hooks_by_id(hook_id: str) -> list[dict]:
    """Return all hook declarations matching the given id (may be multiple)."""
    return [h for h in _all_hooks() if h.get("id") == hook_id]


# ===========================================================================
# Dependency declarations
# ===========================================================================


class TestRequirementsPinning:
    """The pre-commit Python package must be pinned in requirements.txt."""

    def test_requirements_txt_exists(self):
        assert REQUIREMENTS_PATH.exists(), f"requirements.txt missing at {REQUIREMENTS_PATH}"

    def test_pre_commit_is_pinned(self):
        """
        Given: requirements.txt
        When: searching for the pre-commit dependency
        Then: a `pre-commit==<version>` line is present (exact pin, not range)
        """
        content = REQUIREMENTS_PATH.read_text(encoding="utf-8")
        match = re.search(r"^pre-commit==(\S+)$", content, re.MULTILINE)
        assert match, "pre-commit must be pinned with `==` in requirements.txt"


# ===========================================================================
# Config file existence and parseability
# ===========================================================================


class TestConfigFile:
    """The framework config must exist at the repo root and be valid YAML."""

    def test_config_file_present(self):
        assert CONFIG_PATH.exists(), f".pre-commit-config.yaml missing at {CONFIG_PATH}"

    def test_config_parses_as_yaml(self):
        config = _load_config()
        assert isinstance(config, dict), "Top-level YAML structure must be a mapping"
        assert "repos" in config, "Config must declare a `repos:` list"
        assert isinstance(config["repos"], list), "`repos` must be a list"
        assert len(config["repos"]) > 0, "Config declares no repos"


# ===========================================================================
# Required hook ids
# ===========================================================================

# Hooks the framework must declare for behavioral parity with the prior bash
# orchestrator. Each id maps to the bash section it replaces.
_REQUIRED_HOOK_IDS = {
    # Schema validation (one entry per yaml/schema pair, all share id):
    "check-jsonschema",
    # Meta-validate schema files themselves against their declared $schema:
    "check-metaschema",
    # Custom schema-master trigger:
    "validate-all-yaml-on-master-schema-change",
    # Format/lint:
    "prettier-yaml",
    "ruff",
    "ruff-format",
    # Local validators:
    "validate-component-edges",
    "validate-control-risk-references",
    "validate-framework-references",
    # Lifecycle uniqueness — dedicated hook so a lifecycle-only commit
    # (touching only risk-map/yaml/lifecycle-stage.yaml) is reachable.
    # Replaces the inline lifecycle-uniqueness call previously gated on
    # validate-component-edges (validate_riskmap.py:184-212), which only
    # triggers when components.yaml is staged. Architect-recommended Fix B
    # for PR #277 reviewer feedback (item 2): split into a separate hook
    # rather than widen validate-component-edges (would force a misleading
    # hook-name scope).
    "validate-lifecycle-stage",
    "validate-workflow-uses-pinning",
    # Issue templates:
    "regenerate-issue-templates",
    "validate-issue-templates",
    # Generators (Mode B auto-stage):
    "regenerate-graphs",
    "regenerate-tables",
    "regenerate-svgs",
}


class TestRequiredHookIds:
    """Every hook id required for parity must be present in the config."""

    def test_all_required_ids_present(self):
        declared_ids = {h.get("id") for h in _all_hooks()}
        missing = _REQUIRED_HOOK_IDS - declared_ids
        assert not missing, f"Missing required hook ids: {sorted(missing)}"


# ===========================================================================
# Local wrapper hook contracts
# ===========================================================================

# (id, expected entry substring, expected files regex substring, pass_filenames)
# Substring match keeps the test stable against minor wording changes.
_WRAPPER_CONTRACTS = [
    (
        "regenerate-graphs",
        "scripts/hooks/precommit/regenerate_graphs.py",
        "(components|controls|risks)",
        True,
    ),
    (
        "regenerate-tables",
        "scripts/hooks/precommit/regenerate_tables.py",
        "(components|controls|risks|personas)",
        True,
    ),
    (
        "regenerate-svgs",
        "scripts/hooks/precommit/regenerate_svgs.py",
        r"\.\(mmd\|mermaid\)",
        True,
    ),
    (
        # regenerate-issue-templates uses pass_filenames: false to avoid
        # pre-commit batching the hook into parallel invocations that would
        # fight over .git/index.lock when running against --all-files.
        "regenerate-issue-templates",
        "scripts/hooks/precommit/regenerate_issue_templates.py",
        "TEMPLATES",
        False,
    ),
    (
        "prettier-yaml",
        "scripts/hooks/precommit/prettier_yaml.py",
        r"risk-map/yaml/.*\\.ya\?ml",
        True,
    ),
]


class TestWrapperHookContracts:
    """Each wrapper hook must point at the right script with the right trigger."""

    def test_each_wrapper_has_expected_entry_and_files(self):
        all_hooks = {h.get("id"): h for h in _all_hooks() if h.get("id")}
        for hook_id, entry_substr, files_substr, pass_filenames in _WRAPPER_CONTRACTS:
            hook = all_hooks.get(hook_id)
            assert hook is not None, f"Hook `{hook_id}` not declared"
            assert entry_substr in hook.get("entry", ""), (
                f"Hook `{hook_id}` entry must reference `{entry_substr}`; got: {hook.get('entry')!r}"
            )
            files_value = hook.get("files", "")
            assert re.search(files_substr, files_value), (
                f"Hook `{hook_id}` files regex must contain `{files_substr}`; got: {files_value!r}"
            )
            assert hook.get("pass_filenames") is pass_filenames, (
                f"Hook `{hook_id}` pass_filenames must be {pass_filenames}; got: {hook.get('pass_filenames')!r}"
            )


# ===========================================================================
# Local validator hook contracts (pass_filenames: false; validators self-scan)
# ===========================================================================


class TestValidatorHookContracts:
    """Local validator hooks shell out to the existing validators with no argv."""

    def test_validate_component_edges_targets_components_yaml(self):
        hooks = _hooks_by_id("validate-component-edges")
        assert len(hooks) == 1, "Exactly one component-edge validator hook expected"
        hook = hooks[0]
        assert "validate_riskmap.py" in hook.get("entry", "")
        assert "components" in hook.get("files", "")
        assert hook.get("pass_filenames") is False

    def test_validate_control_risk_targets_controls_and_risks(self):
        hooks = _hooks_by_id("validate-control-risk-references")
        assert len(hooks) == 1
        hook = hooks[0]
        assert "validate_control_risk_references.py" in hook.get("entry", "")
        assert "controls" in hook.get("files", "")
        assert "risks" in hook.get("files", "")
        assert hook.get("pass_filenames") is False

    def test_validate_framework_references_targets_relevant_yamls(self):
        hooks = _hooks_by_id("validate-framework-references")
        assert len(hooks) == 1
        hook = hooks[0]
        assert "validate_framework_references.py" in hook.get("entry", "")
        # Framework refs depend on multiple yamls
        files = hook.get("files", "")
        for token in ("controls", "frameworks", "personas", "risks"):
            assert token in files, f"framework refs files regex missing `{token}`: {files!r}"
        assert hook.get("pass_filenames") is False

    def test_validate_lifecycle_stage_dedicated_hook_present(self):
        """
        Test that a dedicated `validate-lifecycle-stage` hook is declared.

        Given: .pre-commit-config.yaml after the Fix B split
        When:  searching for the lifecycle-stage hook
        Then:  Exactly one hook with id `validate-lifecycle-stage` exists.

        This pins the architectural intent that lifecycle uniqueness has
        its own hook entry rather than being bundled into another hook.
        Lifecycle-only commits (which touch only lifecycle-stage.yaml and
        not components.yaml) must be able to trigger the check.
        """
        hooks = _hooks_by_id("validate-lifecycle-stage")
        assert len(hooks) == 1, (
            f"Exactly one validate-lifecycle-stage hook expected; got {len(hooks)}. "
            f"Architect-recommended Fix B requires a dedicated hook with a narrow "
            f"`files:` regex that fires on lifecycle-only commits."
        )

    def test_validate_lifecycle_stage_entry_invokes_validate_riskmap_in_lifecycle_mode(self):
        """
        Test that the lifecycle hook entry invokes validate_riskmap.py with
        the dedicated `--mode lifecycle` flag.

        Given: the `validate-lifecycle-stage` hook in .pre-commit-config.yaml
        When:  inspecting the `entry:` field
        Then:  The entry contains both `validate_riskmap.py` and
               `--mode lifecycle` (substring match keeps the test stable
               against minor wording changes such as `python3 ` prefix).

        The `--mode lifecycle` flag is the SWE contract: lifecycle mode
        bypasses get_staged_yaml_files / ComponentEdgeValidator and runs
        only the uniqueness check. See TestMainLifecycleMode in
        test_validate_riskmap.py.
        """
        hooks = _hooks_by_id("validate-lifecycle-stage")
        assert len(hooks) == 1, "validate-lifecycle-stage hook missing"
        entry = hooks[0].get("entry", "")
        assert "validate_riskmap.py" in entry, (
            f"validate-lifecycle-stage entry must invoke validate_riskmap.py; got: {entry!r}"
        )
        assert "--mode lifecycle" in entry, (
            f"validate-lifecycle-stage entry must pass --mode lifecycle so the script "
            f"runs the dedicated short-circuit path; got: {entry!r}"
        )

    def test_validate_lifecycle_stage_files_regex_anchored_on_lifecycle_yaml(self):
        """
        Test that the lifecycle hook's `files:` regex is narrowly scoped to
        lifecycle-stage.yaml.

        Given: the `validate-lifecycle-stage` hook
        When:  inspecting the `files:` regex
        Then:  The regex matches risk-map/yaml/lifecycle-stage.yaml and is
               anchored. Specifically the regex must be exactly
               `^risk-map/yaml/lifecycle-stage\\.yaml$` so the hook does not
               misfire on unrelated yaml writes.

        Anchoring matters: an unanchored `lifecycle-stage` substring would
        match any future file name containing the phrase. The exact-match
        requirement also disambiguates the architectural intent —
        lifecycle mode is single-file scoped.
        """
        hooks = _hooks_by_id("validate-lifecycle-stage")
        assert len(hooks) == 1, "validate-lifecycle-stage hook missing"
        files_regex = hooks[0].get("files", "")
        assert files_regex == r"^risk-map/yaml/lifecycle-stage\.yaml$", (
            f"validate-lifecycle-stage files regex must be "
            f"`^risk-map/yaml/lifecycle-stage\\.yaml$` (anchored, exact); "
            f"got: {files_regex!r}"
        )

    def test_validate_lifecycle_stage_pass_filenames_is_false(self):
        """
        Test that the lifecycle hook sets pass_filenames: false.

        Given: the `validate-lifecycle-stage` hook
        When:  inspecting `pass_filenames`
        Then:  Value is False.

        The validator self-discovers risk-map/yaml/lifecycle-stage.yaml
        from a fixed path; passing the staged filename as argv would be
        redundant and risks the framework batching multiple invocations.
        Matches the pattern used by validate-component-edges,
        validate-control-risk-references, and validate-framework-references.
        """
        hooks = _hooks_by_id("validate-lifecycle-stage")
        assert len(hooks) == 1, "validate-lifecycle-stage hook missing"
        assert hooks[0].get("pass_filenames") is False, (
            f"validate-lifecycle-stage must set pass_filenames: false; got: {hooks[0].get('pass_filenames')!r}"
        )

    def test_validate_workflow_uses_pinning_targets_workflow_yml_files(self):
        hooks = _hooks_by_id("validate-workflow-uses-pinning")
        assert len(hooks) == 1
        hook = hooks[0]
        assert "validate_workflow_uses_pinning.py" in hook.get("entry", "")
        files = hook.get("files", "")
        assert ".github/workflows" in files
        assert "yml" in files
        assert hook.get("pass_filenames") is True


# ===========================================================================
# install-deps.sh integration
# ===========================================================================


class TestInstallDepsIntegration:
    """install-deps.sh Step 8 must invoke `pre-commit install`."""

    def test_install_deps_present(self):
        assert INSTALL_DEPS_PATH.exists(), f"install-deps.sh missing at {INSTALL_DEPS_PATH}"

    def test_step_8_invokes_pre_commit_install(self):
        """
        Given: scripts/tools/install-deps.sh
        When: searching Step 8 for the pre-commit install invocation
        Then: a `pre_commit install` invocation is present (module form)
        """
        content = INSTALL_DEPS_PATH.read_text(encoding="utf-8")
        # Step 8 header must exist
        assert re.search(r"step_msg 8", content), "install-deps.sh Step 8 header missing"
        # The install invocation must use the python3 module form so it works
        # regardless of whether pre-commit's CLI shim is on PATH.
        assert re.search(r"python3 -m pre_commit install", content), (
            "install-deps.sh must invoke `python3 -m pre_commit install`"
        )

    def test_step_8_does_not_reference_legacy_installer(self):
        """The bash installer (install-precommit-hook.sh) was deleted in #211."""
        content = INSTALL_DEPS_PATH.read_text(encoding="utf-8")
        assert "install-precommit-hook.sh" not in content, (
            "install-deps.sh still references the deleted bash installer"
        )

#!/usr/bin/env python3
"""
Structural drift-guard tests for the ADR-033 neutrality hook wiring in
.pre-commit-config.yaml (PR #428 review Finding 2, does not exist yet — TDD
red phase for the `-policy` hook).

The existing `validate-neutrality` hook is scoped to `^scripts/(agents|skills)/`,
so it only fires when a file under those two trees is staged. Editing the
denylist/allowlist policy data (`scripts/hooks/precommit/_neutrality_data.py`)
or the validator logic itself (`scripts/hooks/precommit/validate_neutrality.py`)
does NOT re-trigger the hook, so a broadened denylist or a changed verdict
never re-scans the existing agent/skill corpus in the same commit — stale
policy drift.

The fix (recommended Option A in the treatment plan) is a second local hook,
`validate-neutrality-policy`, with `pass_filenames: false`, triggered on edits
to the two policy-carrying modules, running the same validator with no
explicit file args so it self-discovers and re-scans the whole corpus via
`discover_neutral_surface_files` (which only ever walks `scripts/agents/**`
and `scripts/skills/**` and therefore never reaches `scripts/hooks/` itself —
the module holding the denylist as data is never scanned as content, so no new
self-trip is introduced).

**Trap being guarded against:** naively adding `_neutrality_data.py` to the
existing file-scoped `validate-neutrality` hook's `files:` with
`pass_filenames: true` would hand that path directly to the validator as an
explicit CLI arg, which the validator scans as ordinary content — and the data
module holds every denylisted term by design, so it would immediately self-trip
on its own line. This suite locks that the file-scoped hook's trigger does NOT
match `_neutrality_data.py`, independent of asserting the new `-policy` hook
exists.

Mirrors the conventions in test_precommit_hook_install.py: `_load_config`,
`_all_hooks`, `_hooks_by_id` helpers; `re.search` semantics against `files:`
regexes (matching the pre-commit framework's own matching behavior).

Public contract under test (RED — none of it exists yet on `main`):
    - A hook with id `validate-neutrality-policy` exists, with
      `pass_filenames: false`, and a `files:` regex matching BOTH
      `scripts/hooks/precommit/validate_neutrality.py` and
      `scripts/hooks/precommit/_neutrality_data.py`.
    - The existing `validate-neutrality` hook's `files:` regex still matches
      `scripts/agents/x.md` and `scripts/skills/x/SKILL.md`, and does NOT
      match `scripts/hooks/precommit/_neutrality_data.py` (self-trip guard).
"""

import re
from pathlib import Path

import yaml

# Repo root is four levels up from this file (scripts/hooks/tests/<here>),
# matching test_precommit_hook_install.py's convention.
REPO_ROOT = Path(__file__).parent.parent.parent.parent
CONFIG_PATH = REPO_ROOT / ".pre-commit-config.yaml"

# The two modules that jointly determine a neutrality verdict. Any future
# validator-consumed module must be added to both this constant and the
# `-policy` hook's files: trigger — the enforced pairing is what
# test_policy_hook_files_regex_matches_both_policy_modules locks.
POLICY_FILES = (
    "scripts/hooks/precommit/validate_neutrality.py",
    "scripts/hooks/precommit/_neutrality_data.py",
)


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


class TestPrecommitConfig:
    """
    Structural drift guard: policy-module edits must re-trigger a full
    agent/skill corpus re-scan, and the file-scoped hook must never be handed
    the policy-data module directly (self-trip guard).
    """

    def test_validate_neutrality_policy_hook_exists(self):
        """
        Given: .pre-commit-config.yaml
        When: searching for a hook with id `validate-neutrality-policy`
        Then: exactly one such hook is declared

        RED: this hook does not exist on `main` yet (PR #428 review Finding 2).
        """
        hooks = _hooks_by_id("validate-neutrality-policy")
        assert len(hooks) == 1, (
            f"expected exactly one `validate-neutrality-policy` hook; got {len(hooks)}. "
            f"Finding 2 requires a second local hook, pass_filenames: false, triggered "
            f"on edits to {POLICY_FILES!r}, so a policy-data or validator-logic change "
            f"re-scans the whole agent/skill corpus in the same commit."
        )

    def test_validate_neutrality_policy_hook_has_pass_filenames_false(self):
        """
        Given: the `validate-neutrality-policy` hook
        When: inspecting `pass_filenames`
        Then: the value is False

        With no file args, `main([])` self-discovers via
        `discover_neutral_surface_files(cwd)`, which scans only
        `scripts/agents/**` and `scripts/skills/**` — never
        `scripts/hooks/`, so the policy-data module itself is structurally
        never handed to the validator as scannable content, and the whole
        corpus is re-validated instead of just the staged policy file.
        """
        hooks = _hooks_by_id("validate-neutrality-policy")
        assert len(hooks) == 1, "validate-neutrality-policy hook missing"
        assert hooks[0].get("pass_filenames") is False, (
            f"validate-neutrality-policy must set pass_filenames: false so it "
            f"self-discovers and re-scans the whole corpus rather than scanning "
            f"the staged policy file itself; got: {hooks[0].get('pass_filenames')!r}"
        )

    def test_validate_neutrality_policy_hook_entry_invokes_validate_neutrality(self):
        """
        Given: the `validate-neutrality-policy` hook
        When: inspecting the `entry:` field
        Then: it invokes `validate_neutrality.py` (the same validator the
              file-scoped hook uses, no separate wrapper script)
        """
        hooks = _hooks_by_id("validate-neutrality-policy")
        assert len(hooks) == 1, "validate-neutrality-policy hook missing"
        entry = hooks[0].get("entry", "")
        assert "validate_neutrality.py" in entry, (
            f"validate-neutrality-policy entry must invoke validate_neutrality.py "
            f"(same validator, no args, self-discovery); got: {entry!r}"
        )

    def test_policy_hook_files_regex_matches_both_policy_modules(self):
        """
        Given: the `validate-neutrality-policy` hook's `files:` regex
        When: applying it against each path in POLICY_FILES
        Then: every path matches

        RED: the hook does not exist yet, so this fails until the trigger is
        added covering both validate_neutrality.py and _neutrality_data.py —
        a regex/logic edit to the validator itself can flip a verdict just as
        much as a denylist/allowlist data edit can, so both modules are in
        POLICY_FILES.
        """
        hooks = _hooks_by_id("validate-neutrality-policy")
        assert len(hooks) == 1, "validate-neutrality-policy hook missing"
        files_regex = hooks[0].get("files", "")

        missing = [path for path in POLICY_FILES if not re.search(files_regex, path)]
        assert not missing, (
            f"validate-neutrality-policy files: regex {files_regex!r} must match "
            f"every path in POLICY_FILES; missing matches for: {missing}"
        )

    def test_existing_validate_neutrality_hook_still_matches_agent_and_skill_files(self):
        """
        Given: the existing file-scoped `validate-neutrality` hook
        When: applying its `files:` regex against a top-level agent .md and a
              canonical SKILL.md path
        Then: both match (regression guard — Finding 2's fix must not narrow
              the existing file-scoped trigger)
        """
        hooks = _hooks_by_id("validate-neutrality")
        assert len(hooks) == 1, "Exactly one validate-neutrality hook expected"
        files_regex = hooks[0].get("files", "")

        assert re.search(files_regex, "scripts/agents/x.md"), (
            f"validate-neutrality files: regex must still match scripts/agents/x.md; got: {files_regex!r}"
        )
        assert re.search(files_regex, "scripts/skills/x/SKILL.md"), (
            f"validate-neutrality files: regex must still match scripts/skills/x/SKILL.md; got: {files_regex!r}"
        )

    def test_existing_validate_neutrality_hook_does_not_match_policy_data_module(self):
        """
        Given: the existing file-scoped `validate-neutrality` hook
        When: applying its `files:` regex against
              scripts/hooks/precommit/_neutrality_data.py
        Then: it does NOT match — SELF-TRIP GUARD

        This is the specific trap the treatment plan calls out: naively
        adding `_neutrality_data.py` to this hook's `files:` (with
        pass_filenames: true, as every other entry here has) would hand the
        data module to the validator as an explicit CLI arg, which the
        validator would then scan as ordinary content — and the data module
        holds every denylisted term by design, so it would immediately
        self-trip on its own lines. The re-scan-on-policy-change requirement
        must be satisfied by the separate `validate-neutrality-policy` hook
        (pass_filenames: false, self-discovery), not by widening this one.

        Any new validator-consumed module must be added to POLICY_FILES and
        the `-policy` hook's trigger, never to this hook's files: regex.
        """
        hooks = _hooks_by_id("validate-neutrality")
        assert len(hooks) == 1, "Exactly one validate-neutrality hook expected"
        files_regex = hooks[0].get("files", "")

        assert not re.search(files_regex, "scripts/hooks/precommit/_neutrality_data.py"), (
            f"validate-neutrality files: regex must NOT match "
            f"scripts/hooks/precommit/_neutrality_data.py — adding it here (with "
            f"pass_filenames: true) would hand the denylist-data module to the "
            f"validator as an explicit arg, which would self-trip on its own "
            f"denylisted-term data; got: {files_regex!r}"
        )

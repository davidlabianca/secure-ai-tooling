#!/usr/bin/env python3
"""
Tests for scripts/hooks/precommit/validate_all_schemas.py

The wrapper re-validates every yaml/schema pair when the master schema
changes. Tests cover the filesystem discovery (_find_pairs), subprocess
call shape, continue-on-failure semantics, and first-failure-wins exit code.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "precommit"))

from validate_all_schemas import _find_pairs, main  # noqa: E402

# tests -> hooks -> scripts -> repo root, matching the convention in
# test_ci_block_parity.py and test_precommit_hook_install.py.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _make_subprocess_mock(returncode: int = 0) -> MagicMock:
    """Return a MagicMock for subprocess.run with the given returncode."""
    mock = MagicMock()
    mock.returncode = returncode
    return mock


# ===========================================================================
# _find_pairs discovery (filesystem-dependent; uses the real repo layout)
# ===========================================================================


class TestFindPairs:
    def test_master_schema_excluded_from_pairs(self):
        """riskmap.schema.json is the trigger, not a target; must not appear."""
        pairs = _find_pairs()
        assert all(s.name != "riskmap.schema.json" for s, _ in pairs), (
            "Master schema must not be paired for validation"
        )

    def test_every_pair_has_both_files_present(self):
        """Every returned pair must reference files that actually exist."""
        pairs = _find_pairs()
        for schema, yaml_file in pairs:
            assert schema.is_file(), f"Schema not found: {schema}"
            assert yaml_file.is_file(), f"Yaml not found: {yaml_file}"

    def test_pairs_cover_known_source_files(self):
        """The nine canonical yaml/schema pairs must be discovered.

        A subset check, deliberately: since 23a455b, `_find_pairs()` recurses
        (`rglob`, not `glob`) so `risk-map/schemas/archive/` is discovered
        too, and the self-assessment-legacy pair archived there per ADR-021
        D6 now comes back as a tenth pair this test does not name. Asserting
        an exact set would fail on that pair, and on any other archived or
        future schema; asserting a subset is what lets the discovered set
        grow without this test changing.
        """
        expected_stems = {
            "actor-access",
            "components",
            "controls",
            "frameworks",
            "impact-type",
            "lifecycle-stage",
            "mermaid-styles",
            "personas",
            "risks",
        }
        pairs = _find_pairs()
        discovered_stems = {s.name.removesuffix(".schema.json") for s, _ in pairs}
        missing = expected_stems - discovered_stems
        assert not missing, f"Expected pairs missing: {sorted(missing)}"


# ===========================================================================
# _find_pairs must reflect the git index, not the filesystem
# ===========================================================================
#
# ADR-037 D1 makes CI the enforcing gate and the local pre-commit hook a
# preview of it. CI validates a fresh checkout of the tracked corpus;
# `_find_pairs()` instead globs the filesystem with `Path.rglob`, so an
# untracked schema/yaml pair sitting in the working tree — a scratch file, a
# half-finished draft, a stray editor backup under a nested directory — is
# discovered and validated locally even though CI will never see it. That is
# the direction opposite the one ADR-037 exists to close (CI laxer than
# local): here the *local* hook is stricter than CI, over files that are not
# part of the repository at all. Recorded as local-only debt, not a merge
# escape, and lowest priority of the six findings this module's docstring
# enumerates for that reason.
#
# FIX IS PRODUCTION-SIDE, NOT APPLIED HERE: `_find_pairs()` needs to filter
# its `rglob` result (or replace it outright) through `git ls-files`, the way
# every filesystem-derived set in scripts/hooks/tests/test_ci_block_parity.py
# already does (`_tracked_files()` there is the precedent). This test is RED
# as committed and stays that way until that production change lands.


class TestFindPairsRespectsGitIndex:
    def test_untracked_schema_yaml_pair_is_not_discovered(self):
        """
        Given: an untracked schema+matching-yaml pair written into the real
               working tree under `risk-map/schemas/scratch/` and
               `risk-map/yaml/scratch/` — never `git add`ed
        When: `_find_pairs()` is called from the repository root, the same
              working directory `validation.yml`'s schema-validation job uses
        Then: the untracked pair is absent from the result

        Reproduces mutation M32: an untracked
        `risk-map/schemas/scratch/actor-access.schema.json` plus a malformed
        nested yaml made `_find_pairs()` return eleven pairs (ten tracked plus
        the scratch one) and `main()` exit 1 on a file CI cannot see, because
        it is not part of the tracked corpus a checkout would ever contain.
        `_find_pairs()` currently globs the filesystem with no git-index
        check at all, so this is expected to fail until it is switched to
        filter through (or discover via) `git ls-files`.

        Files are created directly under the real `risk-map/` tree, then
        removed in `finally`, rather than in an isolated `tmp_path`:
        `_find_pairs()` resolves `_SCHEMA_DIR`/`_YAML_DIR` as paths relative
        to the process's current working directory
        (`Path("risk-map/schemas")`), which only matches the repository
        layout when run from the repository root — reproducing the hazard
        requires the real tree, not a copy of it.
        """
        schema_dir = _REPO_ROOT / "risk-map" / "schemas" / "scratch"
        yaml_dir = _REPO_ROOT / "risk-map" / "yaml" / "scratch"
        schema_path = schema_dir / "untracked-probe.schema.json"
        yaml_path = yaml_dir / "untracked-probe.yaml"

        preexisting_schema_dir = schema_dir.is_dir()
        preexisting_yaml_dir = yaml_dir.is_dir()
        try:
            schema_dir.mkdir(parents=True, exist_ok=True)
            yaml_dir.mkdir(parents=True, exist_ok=True)
            schema_path.write_text(
                '{"$schema": "http://json-schema.org/draft-07/schema#", "type": "object"}\n',
                encoding="utf-8",
            )
            # Content does not need to be valid against the schema above —
            # _find_pairs() is filesystem discovery only, and the mutation
            # this test reproduces is a discovery-stage escape, not a
            # validation-stage one.
            yaml_path.write_text("untracked: true\n", encoding="utf-8")

            pairs = _find_pairs()

            discovered_schema_names = {schema.name for schema, _ in pairs}
            assert "untracked-probe.schema.json" not in discovered_schema_names, (
                f"_find_pairs() discovered an untracked schema/yaml pair "
                f"({schema_path.relative_to(_REPO_ROOT)}, "
                f"{yaml_path.relative_to(_REPO_ROOT)}) that `git ls-files` does not "
                "track. CI validates a fresh checkout of the tracked corpus and would "
                "never see this pair, so a local commit can be blocked by a file that "
                "does not exist as far as the repository — or CI — is concerned. Fix "
                "is production-side: _find_pairs() needs to filter through (or "
                "discover via) `git ls-files`, not `Path.rglob`."
            )
        finally:
            schema_path.unlink(missing_ok=True)
            yaml_path.unlink(missing_ok=True)
            if not preexisting_schema_dir:
                schema_dir.rmdir()
            if not preexisting_yaml_dir:
                yaml_dir.rmdir()


# ===========================================================================
# main() behavior (subprocess mocked)
# ===========================================================================


class TestMainBehavior:
    """
    subprocess.run is patched at `subprocess.run` — the implementation must
    use `subprocess.run(...)` (not `from subprocess import run`) for the
    patch to intercept calls.
    """

    def test_empty_pairs_returns_zero(self):
        """If no pairs are discovered (hypothetically), exit 0 with no subprocess."""
        with patch("validate_all_schemas._find_pairs", return_value=[]):
            with patch("subprocess.run") as mock_run:
                result = main([])
        assert result == 0
        assert mock_run.call_count == 0

    def test_all_pairs_succeed_returns_zero(self):
        """All check-jsonschema calls succeed → exit 0."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = _make_subprocess_mock(0)
            result = main([])
        assert result == 0
        # One subprocess call per discovered pair (ten in the real layout as
        # of 23a455b, which made discovery recurse into risk-map/schemas/archive/;
        # left as `> 0` rather than pinned, so this does not need to change
        # every time a schema is added, archived or not).
        assert mock_run.call_count > 0

    def test_first_failure_wins_exit_code(self):
        """First non-zero returncode is preserved even if later calls also fail."""
        rcs = iter([0, 2, 5, 0])  # second pair fails with rc=2, third with rc=5

        def side_effect(cmd, **kwargs):
            return _make_subprocess_mock(next(rcs))

        # Force a known pair list so the test is deterministic regardless of repo layout
        fake_pairs = [
            (Path(f"risk-map/schemas/p{i}.schema.json"), Path(f"risk-map/yaml/p{i}.yaml")) for i in range(4)
        ]
        with patch("validate_all_schemas._find_pairs", return_value=fake_pairs):
            with patch("subprocess.run", side_effect=side_effect) as mock_run:
                result = main([])

        assert result == 2, "First failing returncode (rc=2) must win"
        assert mock_run.call_count == 4, "All pairs must be attempted, not short-circuit"

    def test_continue_on_failure(self):
        """A failure in one pair does not skip subsequent pairs."""

        def side_effect(cmd, **kwargs):
            return _make_subprocess_mock(1)  # every call fails

        fake_pairs = [
            (Path(f"risk-map/schemas/p{i}.schema.json"), Path(f"risk-map/yaml/p{i}.yaml")) for i in range(3)
        ]
        with patch("validate_all_schemas._find_pairs", return_value=fake_pairs):
            with patch("subprocess.run", side_effect=side_effect) as mock_run:
                result = main([])

        assert result == 1
        assert mock_run.call_count == 3, "All pairs attempted despite every call failing"

    def test_command_shape_includes_base_uri_and_schemafile(self):
        """Every subprocess call uses list form with --base-uri and --schemafile."""
        fake_pairs = [(Path("risk-map/schemas/foo.schema.json"), Path("risk-map/yaml/foo.yaml"))]
        with patch("validate_all_schemas._find_pairs", return_value=fake_pairs):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = _make_subprocess_mock(0)
                main([])

        call = mock_run.call_args_list[0]
        cmd = call.args[0]
        assert isinstance(cmd, list), "Command must be list-form (no shell=True)"
        assert cmd[0] == "check-jsonschema"
        assert "--base-uri" in cmd
        assert "--schemafile" in cmd
        assert "risk-map/schemas/foo.schema.json" in cmd
        assert "risk-map/yaml/foo.yaml" in cmd

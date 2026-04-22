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
        """The ten canonical yaml/schema pairs must be discovered."""
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
            "self-assessment",
        }
        pairs = _find_pairs()
        discovered_stems = {s.name.removesuffix(".schema.json") for s, _ in pairs}
        missing = expected_stems - discovered_stems
        assert not missing, f"Expected pairs missing: {sorted(missing)}"


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
        # One subprocess call per discovered pair (10 in the real layout)
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

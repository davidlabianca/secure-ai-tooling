#!/usr/bin/env python3
"""
Tests for report_one_way_control_mentions.py (DG10 advisory report).

The script reads a controls YAML and lists one-way `{{control...}}` mentions found in
control `guidance`: A -> B is reported when A's guidance mentions `{{B}}` and B's guidance
does not mention `{{A}}`. See risk-map/docs/design/control-description-and-guidance.md
(DG10 and the Enforcement table): the report is a review aid and must never fail a build.

Contract pinned here:
- CLI: `python3 scripts/hooks/report_one_way_control_mentions.py [controls.yaml]`;
  default path is `risk-map/yaml/controls.yaml` (resolved against the cwd).
- Each one-way pair is printed on its own line in the form `<A> -> <B>`, sorted
  lexicographically by (A, B), one line per pair even when A mentions B repeatedly.
- Scan scope: every `{{control...}}` sentinel anywhere in `guidance` (flat list items or
  one-level nested sub-lists). `description` is not scanned. No boundary-section detection.
- B without `guidance` (or B absent from the file) does not reciprocate: A -> B is reported.
- Self-mentions are ignored.
- Exit code is always 0. When nothing is one-way, stdout says "no one-way mentions".

All fixtures are synthetic and written to tmp_path; the live corpus is not read.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

SCRIPT = Path(__file__).parent.parent / "report_one_way_control_mentions.py"
REPO_ROOT = Path(__file__).parent.parent.parent.parent


def _control(cid: str, description: str = "Does a thing.", guidance=None) -> dict:
    """Build a minimal synthetic control entry; `guidance` is omitted when None."""
    entry = {"id": cid, "title": cid, "description": [description]}
    if guidance is not None:
        entry["guidance"] = guidance
    return entry


def _write_controls(tmp_path: Path, controls: list[dict], name: str = "controls.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.safe_dump({"controls": controls}, sort_keys=False), encoding="utf-8")
    return path


def _run(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess:
    # Guard so negative assertions (empty pair list, absent text) cannot pass vacuously
    # when the script does not exist.
    assert SCRIPT.is_file(), f"script not implemented: {SCRIPT}"
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
    )


def _pairs(stdout: str) -> list[tuple[str, str]]:
    """Extract `A -> B` pairs from stdout in emitted order; whole-line anchored to pin the format."""
    return re.findall(r"^(\S+) -> (\S+)$", stdout, re.MULTILINE)


@pytest.fixture
def mixed_controls(tmp_path: Path) -> Path:
    """
    Fixture with: a reciprocal pair (Alpha<->Beta), a one-way pair (Gamma->Delta where
    Delta has guidance that does not mention Gamma), a nested-sub-list mention
    (Epsilon->Zeta, Zeta has no guidance), a description-only mention (Eta), and a
    control without guidance (Zeta).
    """
    return _write_controls(
        tmp_path,
        [
            _control("controlAlpha", guidance=["Distinct from {{controlBeta}}."]),
            _control("controlBeta", guidance=["Distinct from {{controlAlpha}}."]),
            _control("controlGamma", guidance=["Unlike {{controlDelta}}, this acts early."]),
            _control("controlDelta", guidance=["Acts at runtime."]),
            _control(
                "controlEpsilon",
                guidance=["Applies broadly.", ["Nested note.", "Draws on {{controlZeta}}."]],
            ),
            _control("controlZeta"),
            _control(
                "controlEta",
                description="Complements {{controlAlpha}}.",
                guidance=["No mentions here."],
            ),
        ],
    )


class TestOneWayListing:
    def test_reports_one_way_pair_and_not_reciprocal_pair(self, mixed_controls):
        """
        Given a reciprocal pair and a one-way pair
        When the script runs on the file
        Then only the one-way pair is listed and the reciprocal pair is absent
        """
        result = _run(str(mixed_controls))
        pairs = _pairs(result.stdout)
        assert ("controlGamma", "controlDelta") in pairs
        assert not any({a, b} == {"controlAlpha", "controlBeta"} for a, b in pairs)

    def test_reports_mention_inside_nested_guidance_sublist(self, mixed_controls):
        """
        Given a mention inside a one-level nested guidance sub-list
        When the script runs
        Then the mention is scanned and reported as one-way
        """
        pairs = _pairs(_run(str(mixed_controls)).stdout)
        assert ("controlEpsilon", "controlZeta") in pairs

    def test_target_without_guidance_counts_as_one_way(self, tmp_path):
        """
        Given A mentions B in a flat (non-nested) guidance item and B has no guidance field
        When the script runs
        Then A -> B is reported
        """
        path = _write_controls(
            tmp_path,
            [
                _control("controlA", guidance=["Flat mention of {{controlB}}."]),
                _control("controlB"),
            ],
        )
        assert _pairs(_run(str(path)).stdout) == [("controlA", "controlB")]

    def test_dangling_target_is_reported_and_exit_zero(self, tmp_path):
        """
        Given A mentions {{controlGhost}} and no such control exists in the file
        When the script runs
        Then controlA -> controlGhost is reported and the exit code is 0
        """
        path = _write_controls(tmp_path, [_control("controlA", guidance=["See {{controlGhost}}."])])
        result = _run(str(path))
        assert result.returncode == 0
        assert _pairs(result.stdout) == [("controlA", "controlGhost")]

    def test_description_only_mention_is_ignored(self, mixed_controls):
        """
        Given a control whose description (not guidance) mentions another control
        When the script runs
        Then no pair with that source is reported
        """
        pairs = _pairs(_run(str(mixed_controls)).stdout)
        assert not any(a == "controlEta" for a, _ in pairs)

    def test_exact_set_of_pairs_on_mixed_fixture(self, mixed_controls):
        """
        Given the full mixed fixture
        When the script runs
        Then exactly the two expected one-way pairs are listed
        """
        pairs = _pairs(_run(str(mixed_controls)).stdout)
        assert pairs == [
            ("controlEpsilon", "controlZeta"),
            ("controlGamma", "controlDelta"),
        ]


class TestScanRules:
    def test_mention_in_description_of_target_does_not_reciprocate(self, tmp_path):
        """
        Given A's guidance mentions B, and only B's description (not guidance) mentions A
        When the script runs
        Then A -> B is reported, since reciprocity is judged on guidance only
        """
        path = _write_controls(
            tmp_path,
            [
                _control("controlA", guidance=["See {{controlB}}."]),
                _control("controlB", description="Relates to {{controlA}}.", guidance=["Nothing."]),
            ],
        )
        assert _pairs(_run(str(path)).stdout) == [("controlA", "controlB")]

    def test_reciprocal_via_nested_sublist_is_not_reported(self, tmp_path):
        """
        Given B reciprocates A only from inside a nested guidance sub-list
        When the script runs
        Then no pair is reported
        """
        path = _write_controls(
            tmp_path,
            [
                _control("controlA", guidance=["See {{controlB}}."]),
                _control("controlB", guidance=["Intro.", ["Also {{controlA}}."]]),
            ],
        )
        assert _pairs(_run(str(path)).stdout) == []

    def test_self_mention_is_ignored(self, tmp_path):
        """
        Given a control whose guidance mentions itself
        When the script runs
        Then no pair is reported
        """
        path = _write_controls(
            tmp_path, [_control("controlA", guidance=["Not to be confused with {{controlA}}."])]
        )
        assert _pairs(_run(str(path)).stdout) == []

    def test_non_control_sentinels_are_ignored(self, tmp_path):
        """
        Given guidance with {{ref:...}}, {{risk...}} and {{component...}} sentinels
        When the script runs
        Then no `->` line is printed at all and the "no one-way mentions" message appears
        """
        path = _write_controls(
            tmp_path,
            [
                _control(
                    "controlA",
                    guidance=["Cites {{ref:cwe-89}}, {{riskX}} and {{componentY}}."],
                )
            ],
        )
        result = _run(str(path))
        assert "->" not in result.stdout
        assert re.search(r"no one-way mentions", result.stdout, re.IGNORECASE)

    def test_emphasis_wrapped_sentinels_are_counted(self, tmp_path):
        """
        Given guidance with sentinels wrapped in bold, underscore-italic and star-italic
        When the script runs
        Then each wrapped mention is reported as one-way
        """
        path = _write_controls(
            tmp_path,
            [
                _control(
                    "controlA",
                    guidance=[
                        "Unlike **{{controlB}}** this acts early.",
                        "Also _{{controlC}}_ differs.",
                        "And *{{controlD}}* differs.",
                    ],
                ),
                _control("controlB", guidance=["Nothing."]),
                _control("controlC", guidance=["Nothing."]),
                _control("controlD", guidance=["Nothing."]),
            ],
        )
        assert _pairs(_run(str(path)).stdout) == [
            ("controlA", "controlB"),
            ("controlA", "controlC"),
            ("controlA", "controlD"),
        ]

    def test_bold_wrapped_reciprocal_mention_reciprocates(self, tmp_path):
        """
        Given B mentions A only as **{{controlA}}** in its guidance
        When the script runs
        Then A -> B is not reported
        """
        path = _write_controls(
            tmp_path,
            [
                _control("controlA", guidance=["See {{controlB}}."]),
                _control("controlB", guidance=["Distinct from **{{controlA}}**."]),
            ],
        )
        result = _run(str(path))
        assert _pairs(result.stdout) == []
        assert re.search(r"no one-way mentions", result.stdout, re.IGNORECASE)

    def test_repeated_mentions_yield_one_line_per_pair(self, tmp_path):
        """
        Given A mentions B in several guidance items
        When the script runs
        Then A -> B appears exactly once
        """
        path = _write_controls(
            tmp_path,
            [
                _control("controlA", guidance=["One {{controlB}}.", "Two {{controlB}}."]),
                _control("controlB", guidance=["Nothing."]),
            ],
        )
        assert _pairs(_run(str(path)).stdout) == [("controlA", "controlB")]

    def test_multiple_mentions_in_one_item_are_each_checked(self, tmp_path):
        """
        Given one guidance item mentioning two controls, one of which reciprocates
        When the script runs
        Then only the non-reciprocating target is reported
        """
        path = _write_controls(
            tmp_path,
            [
                _control("controlA", guidance=["Unlike {{controlB}} and {{controlC}}."]),
                _control("controlB", guidance=["Unlike {{controlA}}."]),
                _control("controlC", guidance=["Nothing."]),
            ],
        )
        assert _pairs(_run(str(path)).stdout) == [("controlA", "controlC")]


class TestOutputAndExit:
    def test_output_is_sorted_and_deterministic(self, tmp_path):
        """
        Given one-way pairs declared in non-sorted file order
        When the script runs twice
        Then pairs are sorted by (source, target) and the two outputs are identical
        """
        path = _write_controls(
            tmp_path,
            [
                _control("controlM", guidance=["See {{controlB}}."]),
                _control("controlA", guidance=["See {{controlZ}}."]),
                _control("controlZ", guidance=["Nothing."]),
                _control("controlB", guidance=["Nothing."]),
            ],
        )
        first = _run(str(path))
        second = _run(str(path))
        # Sorted by (source, target): a (target, source) sort would order M->B first.
        assert _pairs(first.stdout) == [
            ("controlA", "controlZ"),
            ("controlM", "controlB"),
        ]
        assert first.stdout == second.stdout

    def test_exit_zero_when_one_way_pairs_exist(self, mixed_controls):
        """
        Given a file with one-way pairs
        When the script runs
        Then the exit code is 0 (advisory, never fails a build)
        """
        assert _run(str(mixed_controls)).returncode == 0

    def test_no_one_way_message_when_none_found(self, tmp_path):
        """
        Given only a reciprocal pair
        When the script runs
        Then exit code is 0, stdout states there are no one-way mentions, and no pair lines appear
        """
        path = _write_controls(
            tmp_path,
            [
                _control("controlA", guidance=["See {{controlB}}."]),
                _control("controlB", guidance=["See {{controlA}}."]),
            ],
        )
        result = _run(str(path))
        assert result.returncode == 0
        assert re.search(r"no one-way mentions", result.stdout, re.IGNORECASE)
        assert _pairs(result.stdout) == []

    def test_no_one_way_message_absent_when_pairs_found(self, mixed_controls):
        """
        Given a file with one-way pairs
        When the script runs
        Then the "no one-way mentions" message is not printed
        """
        assert not re.search(r"no one-way mentions", _run(str(mixed_controls)).stdout, re.IGNORECASE)

    def test_no_one_way_message_when_no_control_has_guidance(self, tmp_path):
        """
        Given controls with no guidance at all
        When the script runs
        Then exit code is 0 and the "no one-way mentions" message is printed
        """
        path = _write_controls(tmp_path, [_control("controlA"), _control("controlB")])
        result = _run(str(path))
        assert result.returncode == 0
        assert re.search(r"no one-way mentions", result.stdout, re.IGNORECASE)


class TestCliPath:
    def test_default_path_is_risk_map_yaml_controls(self, tmp_path):
        """
        Given no CLI argument and a cwd holding risk-map/yaml/controls.yaml
        When the script runs
        Then it reads that file and lists its one-way pair
        """
        target = tmp_path / "risk-map" / "yaml"
        target.mkdir(parents=True)
        _write_controls(
            target,
            [
                _control("controlA", guidance=["See {{controlB}}."]),
                _control("controlB"),
            ],
        )
        result = _run(cwd=tmp_path)
        assert result.returncode == 0
        assert _pairs(result.stdout) == [("controlA", "controlB")]

    def test_explicit_path_overrides_default(self, tmp_path):
        """
        Given a controls file passed as the CLI argument
        When the script runs from an unrelated cwd
        Then it reads the given file
        """
        path = _write_controls(
            tmp_path,
            [
                _control("controlP", guidance=["See {{controlQ}}."]),
                _control("controlQ"),
            ],
            name="custom.yaml",
        )
        result = _run(str(path), cwd=REPO_ROOT)
        assert _pairs(result.stdout) == [("controlP", "controlQ")]


class TestBadInput:
    """Exit 0 covers findings only; unusable input is an error, not an empty report."""

    def test_missing_file_errors_naming_path(self, tmp_path):
        """
        Given a CLI path that does not exist
        When the script runs
        Then exit is non-zero, stderr names the path, and no "no one-way mentions" message is printed
        """
        missing = tmp_path / "absent.yaml"
        result = _run(str(missing))
        assert result.returncode != 0
        assert str(missing) in result.stderr
        assert not re.search(r"no one-way mentions", result.stdout, re.IGNORECASE)

    def test_unparseable_yaml_errors(self, tmp_path):
        """
        Given a file containing invalid YAML
        When the script runs
        Then exit is non-zero, stderr has an error, and no "no one-way mentions" message is printed
        """
        bad = tmp_path / "bad.yaml"
        bad.write_text("controls: [unclosed\n  - : :\n", encoding="utf-8")
        result = _run(str(bad))
        assert result.returncode != 0
        assert result.stderr.strip()
        assert not re.search(r"no one-way mentions", result.stdout, re.IGNORECASE)

    @pytest.mark.parametrize("content", ["other: []\n", "controls: not-a-list\n", ""])
    def test_missing_or_non_list_controls_key_errors(self, tmp_path, content):
        """
        Given valid YAML with no top-level `controls` list (absent key, non-list value, empty file)
        When the script runs
        Then exit is non-zero, stderr has an error, and no "no one-way mentions" message is printed
        """
        path = tmp_path / "nocontrols.yaml"
        path.write_text(content, encoding="utf-8")
        result = _run(str(path))
        assert result.returncode != 0
        assert result.stderr.strip()
        assert not re.search(r"no one-way mentions", result.stdout, re.IGNORECASE)

    def test_duplicate_control_id_errors_naming_id(self, tmp_path):
        """
        Given two control entries sharing the same id
        When the script runs
        Then exit is non-zero, stderr names the id, and no "no one-way mentions" message is printed
        """
        path = _write_controls(
            tmp_path,
            [
                _control("controlDup", guidance=["See {{controlB}}."]),
                _control("controlDup", guidance=["Nothing."]),
                _control("controlB"),
            ],
        )
        result = _run(str(path))
        assert result.returncode != 0
        assert "controlDup" in result.stderr
        assert not re.search(r"no one-way mentions", result.stdout, re.IGNORECASE)

    def test_empty_controls_list_is_valid_and_reports_none(self, tmp_path):
        """
        Given a file with `controls: []`
        When the script runs
        Then exit is 0 and stdout states there are no one-way mentions
        """
        path = tmp_path / "empty.yaml"
        path.write_text("controls: []\n", encoding="utf-8")
        result = _run(str(path))
        assert result.returncode == 0
        assert re.search(r"no one-way mentions", result.stdout, re.IGNORECASE)

    @pytest.mark.parametrize(
        "entry",
        [
            {"title": "No id", "guidance": ["See {{controlB}}."]},
            "controlA",
        ],
        ids=["entry-without-id", "non-dict-entry"],
    )
    def test_malformed_control_entry_errors(self, tmp_path, entry):
        """
        Given a controls list containing an entry with no `id` or a non-dict entry
        When the script runs
        Then exit is non-zero, stderr has an error, and no "no one-way mentions" message is printed
        """
        path = _write_controls(tmp_path, [_control("controlB"), entry])
        result = _run(str(path))
        assert result.returncode != 0
        assert result.stderr.strip()
        assert not re.search(r"no one-way mentions", result.stdout, re.IGNORECASE)

    def test_missing_default_path_errors_naming_path(self, tmp_path):
        """
        Given no CLI argument and a cwd without risk-map/yaml/controls.yaml
        When the script runs
        Then exit is non-zero and stderr names the default path
        """
        result = _run(cwd=tmp_path)
        assert result.returncode != 0
        assert "controls.yaml" in result.stderr
        assert not re.search(r"no one-way mentions", result.stdout, re.IGNORECASE)

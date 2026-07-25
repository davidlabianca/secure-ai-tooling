#!/usr/bin/env python3
"""
Tests for wiring `check_emission_drift()` into `validate_riskmap.py` as a
warn-only check (ADR-036 D7).

`check_emission_drift(forward_map, components, emission_cfg) -> list[str]`
(`riskmap_validator.graphing.decouple`) already exists and is already
extensively unit-tested at the pure-function level in
`test_decouple_guards.py` (every G-A*/G-C*/G-O1 guard) and
`test_decouple_coverage_gaps.py`. This suite does NOT re-test the guard
function itself -- per the module docstrings of those two files, which
explicitly own that coverage and note independence between test files
covering different guard layers.

This suite's job is narrower: `validate_riskmap.py` does not call
`check_emission_drift()` at all yet, so the check never runs during a normal
`--force` invocation regardless of what `mermaid-styles.yaml` says. ADR-036
D7: "Guards run whenever the emission block exists, regardless of mode" --
a new warn-only check in the existing battery (mirror check / nesting check
/ category-ownership check), following the SAME established pattern each of
those uses (see `validate_riskmap.py` lines ~275-386 and
`test_category_ownership_guard.py::TestCLIWiring` for the convention this
suite mirrors): warnings print with the `⚠️`/`❌` label depending on
`args.block`, `--block` promotes to `warn_block_triggered = True` and exits 1
via the existing unified-exit mechanism, non-block mode prints and continues.

Not yet wired: every test below currently fails (or would trivially pass for
the wrong reason -- see the "no wiring yet" tests) because
validate_riskmap.py never imports or calls check_emission_drift. Tests turn
green once that wiring lands.

Test placement judgment call (flagged for code-reviewer): this repo's
established convention is one dedicated file per warn-only check
(test_controls_components_mirror.py, test_category_subcategory_nesting.py,
test_category_ownership_guard.py all follow this, each with its own
TestCLIWiring class doing subprocess end-to-end runs against
validate_riskmap.py). This file follows that convention instead of
extending test_validate_riskmap.py, which stays reserved for
argparse/main()-orchestration-level tests (see the `--emission-mode` CLI
override tests added to TestEmissionModeCLIOverride in
test_validate_riskmap.py for that piece).

Malformed-block coverage (adversarial review finding, ADR-036 D3/D7). Every
class above assumes `get_emission_config()` either parses cleanly or
legitimately degrades to an empty-but-intentional `flat` config (e.g.
`mode: flat` with no `aspects`/`concerns` at all -- the D3 rollback lever).
Neither covers the case where the raw `emission` block IS present and DOES
contain real, corpus-covering registries, but one entry is structurally
malformed (bad `mode` value, wrong-arity `concerns[].edges` tuple, non-dict
`portStyles`, ...): `get_emission_config()` correctly degrades to
`EmissionConfig(mode="flat")` per its own contract ("missing or corrupt
config never yields a half-decoupled diagram" -- see
`test_decouple_emitter.py::TestGetEmissionConfigAccessor`, which owns that
accessor-level coverage), but the *drift-check wiring* in
`validate_riskmap.py` currently gates only on "is the raw `emission` key
present at all", not on "did it actually parse" -- so it runs
`check_emission_drift()` against the resulting empty-registry config and
cascades one G-C3 "no entry covers this edge" warning per cross edge in the
corpus (43 on the live corpus), none of which mention the real problem, all
of whose remediation text ("add an entry to ... concerns") is actively wrong
since the real entries already exist and were merely dropped during parsing.
`TestEmissionMalformedBlockDistinctWarning` below pins the desired fix:
degradation-due-to-malformed-block must short-circuit to exactly one
distinct warning naming the real problem, never the per-edge cascade.
`TestEmissionValidSparseConfigStillDrifts` is the paired regression guard,
proving a legitimately-parsed-but-genuinely-sparse registry (no parse
failure, just real drift) still produces the normal per-edge G-C3 warnings
-- the fix must distinguish "block failed to parse" from "block parsed fine
and is incomplete", not blanket-suppress the emission-drift check whenever
the registries happen to be sparse.
"""

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_SCRIPT = Path(__file__).parent.parent / "validate_riskmap.py"


# ============================================================================
# Fixtures -- minimal 4-category corpus, all OTHER warn-only checks clean
# ============================================================================
#
# Mirrors test_category_ownership_guard.py's _THREE_CATEGORY_COMPONENTS /
# _THREE_CATEGORY_CONTROLS_ALL_OWNED / _FULLY_STYLED_MERMAID (duplicated here
# rather than imported, matching this repo's established per-file
# independence convention for warn-only-check test suites). All 4 real schema
# categories are present, styled, and owned so the mirror/nesting/ownership
# checks stay silent and only the emission-drift check under test produces
# output.

_CLEAN_COMPONENTS: dict[str, Any] = {
    "components": [
        {
            "id": "compInfra",
            "title": "Infra",
            "category": "componentsInfrastructure",
            "subcategory": "componentsData",
            "edges": {},
        },
        {
            "id": "compModel",
            "title": "Model",
            "category": "componentsModel",
            "subcategory": "componentsModelTraining",
            "edges": {},
        },
        {
            "id": "compApp",
            "title": "App",
            "category": "componentsApplication",
            "subcategory": "componentsAgent",
            "edges": {},
        },
        {
            "id": "compTools",
            "title": "Tools",
            "category": "componentsTools",
            "subcategory": "componentsToolCore",
            "edges": {},
        },
    ],
    "categories": [
        {
            "id": "componentsInfrastructure",
            "title": "Infrastructure",
            "subcategory": [{"id": "componentsData", "title": "Data"}],
        },
        {
            "id": "componentsModel",
            "title": "Model",
            "subcategory": [{"id": "componentsModelTraining", "title": "Model Training"}],
        },
        {
            "id": "componentsApplication",
            "title": "Application",
            "subcategory": [{"id": "componentsAgent", "title": "Agent"}],
        },
        {
            "id": "componentsTools",
            "title": "Tools",
            "subcategory": [{"id": "componentsToolCore", "title": "Tool Core"}],
        },
    ],
}

_CLEAN_CONTROLS: dict[str, Any] = {
    "controls": [
        {
            "id": "ctrlInfra",
            "title": "Infra Ctrl",
            "category": "controlsInfrastructure",
            "components": ["compInfra"],
            "risks": [],
            "personas": ["personaX"],
        },
        {
            "id": "ctrlModel",
            "title": "Model Ctrl",
            "category": "controlsModel",
            "components": ["compModel"],
            "risks": [],
            "personas": ["personaX"],
        },
        {
            "id": "ctrlApp",
            "title": "App Ctrl",
            "category": "controlsApplication",
            "components": ["compApp"],
            "risks": [],
            "personas": ["personaX"],
        },
        {
            "id": "ctrlTools",
            "title": "Tools Ctrl",
            "category": "controlsApplication",
            "components": ["compTools"],
            "risks": [],
            "personas": ["personaX"],
        },
    ]
}

_BASE_MERMAID: dict[str, Any] = {
    "version": "1.0.0",
    "foundation": {"colors": {}, "strokeWidths": {}, "strokePatterns": {}},
    "sharedElements": {
        "cssClasses": {"hidden": "display: none;", "allControl": "stroke:#000,stroke-width:1px"},
        "componentCategories": {
            "componentsInfrastructure": {"fill": "#e6f3e6", "stroke": "#333333", "strokeWidth": "2px"},
            "componentsModel": {"fill": "#ffe6e6", "stroke": "#333333", "strokeWidth": "2px"},
            "componentsApplication": {"fill": "#e6f0ff", "stroke": "#333333", "strokeWidth": "2px"},
            "componentsTools": {"fill": "#fff3e6", "stroke": "#333333", "strokeWidth": "2px"},
        },
    },
    "graphTypes": {
        "component": {"direction": "TD", "flowchartConfig": {}},
        "control": {"direction": "LR", "flowchartConfig": {}},
        "risk": {"direction": "LR", "flowchartConfig": {}},
    },
}


def _mermaid_with_emission(emission: dict[str, Any] | None) -> dict[str, Any]:
    """Return a deep-ish copy of _BASE_MERMAID with graphTypes.component.emission set (or omitted)."""
    doc: dict[str, Any] = yaml.safe_load(yaml.dump(_BASE_MERMAID))
    if emission is not None:
        doc["graphTypes"]["component"]["emission"] = emission
    return doc


# The stale-aspect-id drift trigger (G-A1, per test_decouple_guards.py::
# TestGA1AspectIdAbsentFromCorpus): an emission.aspects entry naming a
# component id that does not exist anywhere in components.yaml. Chosen
# because it needs zero edges to fire (simplest reproducible drift
# condition).
_DIRTY_EMISSION_FLAT: dict[str, Any] = {
    "mode": "flat",
    "aspects": [{"id": "componentDoesNotExistInCorpus", "minCrossInDegree": 1}],
}

_DIRTY_EMISSION_DECOUPLED: dict[str, Any] = {
    "mode": "decoupled",
    "aspects": [{"id": "componentDoesNotExistInCorpus", "minCrossInDegree": 1}],
}

_CLEAN_EMISSION: dict[str, Any] = {"mode": "flat"}


def _write_corpus(base: Path, mermaid_styles: dict[str, Any]) -> Path:
    """Write the 4-file synthetic corpus (components/controls/risks/mermaid-styles)."""
    yaml_dir = base / "risk-map" / "yaml"
    yaml_dir.mkdir(parents=True, exist_ok=True)
    (yaml_dir / "components.yaml").write_text(yaml.dump(_CLEAN_COMPONENTS), encoding="utf-8")
    (yaml_dir / "controls.yaml").write_text(yaml.dump(_CLEAN_CONTROLS), encoding="utf-8")
    (yaml_dir / "risks.yaml").write_text(yaml.dump({"risks": []}), encoding="utf-8")
    (yaml_dir / "mermaid-styles.yaml").write_text(yaml.dump(mermaid_styles), encoding="utf-8")
    return base


def _run(cwd: Path, *extra_args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--force", "--allow-isolated", *extra_args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


# ============================================================================
# CLI wiring -- validate_riskmap.py invokes check_emission_drift()
# ============================================================================


class TestEmissionDriftCLIWiring:
    def test_dirty_emission_config_with_block_exits_1(self, tmp_path):
        """
        Given: emission.aspects references a component id absent from the corpus
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 1 (drift warning promoted to error)
        """
        _write_corpus(tmp_path, _mermaid_with_emission(_DIRTY_EMISSION_FLAT))
        result = _run(tmp_path, "--block")
        assert result.returncode == 1, (
            f"Expected exit 1 with --block on a drifted emission config; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dirty_emission_config_fires_regardless_of_mode(self, tmp_path):
        """
        Given: the same stale-aspect-id drift, but emission.mode: decoupled
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 1

        Pins ADR-036 D7 explicitly: the drift guard runs "whenever the
        emission block exists, regardless of mode" -- not gated on
        mode == "decoupled". This matters while mode stays "flat" but the
        registry must not be allowed to rot.
        """
        _write_corpus(tmp_path, _mermaid_with_emission(_DIRTY_EMISSION_DECOUPLED))
        result = _run(tmp_path, "--block")
        assert result.returncode == 1, (
            f"Expected exit 1 with --block regardless of emission.mode; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_dirty_emission_config_without_block_exits_0_and_prints_warning(self, tmp_path):
        """
        Given: the same drifted emission config, no --block
        When: validate_riskmap.py --force --allow-isolated runs
        Then: exit 0 (warn-only preserved) AND stdout/stderr names the stale
              aspect id -- proving the CLI actually surfaces
              check_emission_drift()'s own message contract (config path +
              referenced entity + counter-evidence, per test_decouple_guards.py),
              not just that the exit code happens to match.
        """
        _write_corpus(tmp_path, _mermaid_with_emission(_DIRTY_EMISSION_FLAT))
        result = _run(tmp_path)
        assert result.returncode == 0, (
            f"Expected exit 0 without --block; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "componentDoesNotExistInCorpus" in combined, (
            f"Expected warn output naming the stale aspect id even without --block; "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

    def test_clean_emission_config_with_block_exits_0(self, tmp_path):
        """
        Given: emission block present (mode: flat, no aspects/concerns), no drift
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 0

        Weak signal in isolation (a no-op check would also exit 0 here), but a
        necessary regression companion to the dirty-corpus tests above,
        matching the acknowledged pattern in
        test_category_ownership_guard.py / test_category_subcategory_nesting.py.
        """
        _write_corpus(tmp_path, _mermaid_with_emission(_CLEAN_EMISSION))
        result = _run(tmp_path, "--block")
        assert result.returncode == 0, (
            f"Expected exit 0 with --block on a clean emission config; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_no_emission_block_present_does_not_crash_with_block(self, tmp_path):
        """
        Given: mermaid-styles.yaml with no `emission` key at all (today's real,
               currently-committed state)
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 0, no crash

        The check must guard on the emission block's presence the same way
        the mirror/nesting/ownership checks guard on file existence --
        absence is a silent skip, not an error, so the currently-committed
        corpus (and any consumer's mermaid-styles.yaml without an emission
        block) is never spuriously flagged.
        """
        _write_corpus(tmp_path, _mermaid_with_emission(None))
        result = _run(tmp_path, "--block")
        assert result.returncode == 0, (
            f"Expected exit 0 with --block when no emission block is present; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_live_corpus_with_block_exits_0(self):
        """
        Given: the actual repo as cwd, --block
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 0

        Today, the real mermaid-styles.yaml has no emission block, so this
        is the "no emission block" skip path exercised against the real
        corpus rather than a synthetic one -- already passing, and it must
        stay passing once the real §C registry lands.
        """
        result = _run(_REPO_ROOT, "--block")
        assert result.returncode == 0, (
            f"Expected exit 0 with --block on the live corpus; got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ============================================================================
# False-positive guard -- the check must actually be reachable/wired
# ============================================================================


class TestFalsePositiveGuard:
    def test_dirty_config_output_does_not_merely_echo_an_unrelated_check(self, tmp_path):
        """
        Given: the drifted emission corpus, no --block
        When: validate_riskmap.py --force --allow-isolated runs
        Then: the stale aspect id string appears in output, AND the other
              three warn-only checks (mirror/nesting/ownership) report clean
              -- isolating the signal to the emission-drift check

        Guards against a false-positive pass where some unrelated check
        happens to also print "componentDoesNotExistInCorpus" by coincidence
        (it won't, since none of the other checks read `emission` at all, but
        this pins that the OTHER checks stay silent in this fixture so a
        future regression in this test file's own corpus setup is caught
        early rather than masking a real wiring gap).
        """
        _write_corpus(tmp_path, _mermaid_with_emission(_DIRTY_EMISSION_FLAT))
        result = _run(tmp_path)
        combined = result.stdout + result.stderr

        assert "componentDoesNotExistInCorpus" in combined
        assert "Controls↔components mirror check found" not in combined
        assert "Category/subcategory nesting check found" not in combined
        assert "Category style/ownership check found" not in combined


# ============================================================================
# G2 -- coexistence with the OTHER warn-only checks (mirror/nesting/ownership)
# ============================================================================
#
# Coverage-gap G2 (adversarial review): every test above varies exactly one
# dimension -- emission cleanliness -- against a corpus where the other three
# warn-only checks are deliberately silent (TestFalsePositiveGuard even pins
# that they stay silent). No existing test proves the emission-drift check
# coexists correctly with ANOTHER check that is ALSO dirty, before the
# unified exit block (validate_riskmap.py's `warn_block_triggered` /
# "Warn-only check failures promoted to errors (--block)." block, lines
# ~383-386). An implementation that wires check_emission_drift() with its
# own early `sys.exit(1)` (short-circuiting before the mirror check ever
# runs), or that lands the emission check AFTER the unified exit (never
# reached because an earlier check already exited), would pass every test
# above while still breaking the "print every warning in one pass, then
# exit once" contract every other warn-only check relies on.

_DIRTY_MIRROR_CONTROLS: dict[str, Any] = {
    "controls": [
        *_CLEAN_CONTROLS["controls"],
        {
            "id": "ctrlGhost",
            "title": "Ghost Ctrl",
            "category": "controlsInfrastructure",
            "components": ["compGhostNotInCorpus"],
            "risks": [],
            "personas": ["personaX"],
        },
    ]
}


def _write_corpus_with_controls(base: Path, controls: dict[str, Any], mermaid_styles: dict[str, Any]) -> Path:
    """Write the 4-file synthetic corpus with an explicit controls override (combined-violation fixtures)."""
    yaml_dir = base / "risk-map" / "yaml"
    yaml_dir.mkdir(parents=True, exist_ok=True)
    (yaml_dir / "components.yaml").write_text(yaml.dump(_CLEAN_COMPONENTS), encoding="utf-8")
    (yaml_dir / "controls.yaml").write_text(yaml.dump(controls), encoding="utf-8")
    (yaml_dir / "risks.yaml").write_text(yaml.dump({"risks": []}), encoding="utf-8")
    (yaml_dir / "mermaid-styles.yaml").write_text(yaml.dump(mermaid_styles), encoding="utf-8")
    return base


class TestEmissionDriftCoexistsWithOtherWarnOnlyChecks:
    def test_block_with_both_mirror_and_emission_violations_exits_1_with_both_visible(self, tmp_path):
        """
        Given: a corpus with BOTH a controls-components mirror violation
               (ctrlGhost -> compGhostNotInCorpus) AND a dirty emission block
               (stale aspect id)
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 1, AND both violation signatures appear in combined output

        The exit code alone would pass for either of the wiring bugs
        described above (an early-exiting emission check, or one wired after
        the unified exit) -- the real regression signal is whether BOTH
        violation strings survive to stdout/stderr in one pass, not just
        that SOME check exits non-zero.
        """
        _write_corpus_with_controls(tmp_path, _DIRTY_MIRROR_CONTROLS, _mermaid_with_emission(_DIRTY_EMISSION_FLAT))
        result = _run(tmp_path, "--block")
        combined = result.stdout + result.stderr

        assert result.returncode == 1, (
            f"Expected exit 1 with both a mirror and an emission violation present; "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "compGhostNotInCorpus" in combined, (
            f"Expected the mirror violation to be visible alongside the emission violation; got:\n{combined}"
        )
        assert "componentDoesNotExistInCorpus" in combined, (
            f"Expected the emission-drift violation to be visible alongside the mirror violation; got:\n{combined}"
        )

    def test_no_block_with_both_violations_exits_0_with_both_visible(self, tmp_path):
        """
        Same combined-violation corpus, no --block: exit 0 (warn-only
        preserved) AND both violation strings still printed -- proves
        neither check swallows or short-circuits the other's output when
        --block is absent either.
        """
        _write_corpus_with_controls(tmp_path, _DIRTY_MIRROR_CONTROLS, _mermaid_with_emission(_DIRTY_EMISSION_FLAT))
        result = _run(tmp_path)
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"Expected exit 0 without --block even with both violations present; "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "compGhostNotInCorpus" in combined
        assert "componentDoesNotExistInCorpus" in combined


# ============================================================================
# G3 -- exact print-format convention (header / item-prefix / epilogue)
# ============================================================================
#
# Coverage-gap G3 (adversarial review): every test above only checks that the
# stale aspect id STRING appears somewhere in combined output. That would
# equally pass an implementation that prints the warning in an entirely
# different shape (no header, no bullet prefix, wrong label, missing
# epilogue) as long as the id text is in there somewhere. This class pins
# the EXACT shared convention every other warn-only check in
# validate_riskmap.py already uses (mirror/nesting/ownership -- verified
# byte-for-byte against a live run of the mirror check before writing these
# assertions):
#
#     "   {label} <Name> check found N issue(s):"   (label = ⚠️ warn / ❌ block)
#     "     - <warning text>"                        (item line)
#     "   ❌ Warn-only check failures promoted to errors (--block)."  (epilogue,
#                                                       --block only)
#
# Header text derivation: this repo's established convention maps a
# check_<name> function to a "<Title Case name> check" header (compare
# check_controls_components_mirror -> "Controls↔components mirror check",
# check_category_subcategory_nesting -> "Category/subcategory nesting
# check"). check_emission_drift -> "Emission drift check" follows the same
# derivation; the plan's own open-questions section (§ "Whether
# check_emission_drift output is grouped per-guard or interleaved") directs
# implementers to "follow the existing mirror-check print format", which
# this class pins concretely.


class TestEmissionDriftPrintFormatConvention:
    def test_block_mode_dirty_emission_matches_exact_warn_only_check_format(self, tmp_path):
        """
        Given: the single-violation dirty emission corpus (one stale aspect
               id -- check_emission_drift returns exactly 1 warning per
               test_decouple_guards.py::TestGA1AspectIdAbsentFromCorpus)
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: output contains the exact header, item-prefix, and epilogue
              strings shared by every other warn-only check
        """
        _write_corpus(tmp_path, _mermaid_with_emission(_DIRTY_EMISSION_FLAT))
        result = _run(tmp_path, "--block")
        combined = result.stdout + result.stderr

        assert result.returncode == 1
        assert "   ❌ Emission drift check found 1 issue(s):" in combined, (
            f"Expected the exact warn-only-check header format; got:\n{combined}"
        )
        assert "     - " in combined and "componentDoesNotExistInCorpus" in combined, (
            f"Expected an item line with the shared '     - ' prefix naming the stale aspect id; got:\n{combined}"
        )
        assert "   ❌ Warn-only check failures promoted to errors (--block)." in combined, (
            f"Expected the shared epilogue line; got:\n{combined}"
        )

    def test_no_block_mode_dirty_emission_uses_warn_label_and_omits_epilogue(self, tmp_path):
        """
        Without --block, the header uses the ⚠️ warn label (not ❌), and the
        block-only epilogue must not print at all.
        """
        _write_corpus(tmp_path, _mermaid_with_emission(_DIRTY_EMISSION_FLAT))
        result = _run(tmp_path)
        combined = result.stdout + result.stderr

        assert result.returncode == 0
        assert "   ⚠️ Emission drift check found 1 issue(s):" in combined, (
            f"Expected the exact warn-only-check header format with the ⚠️ label; got:\n{combined}"
        )
        assert "Warn-only check failures promoted to errors" not in combined, (
            f"The --block-only epilogue must not print when --block is absent; got:\n{combined}"
        )


# ============================================================================
# Malformed-block detection -- distinct warning, not the per-edge cascade
# ============================================================================
#
# Adversarial-review finding (see module docstring). `get_emission_config()`
# already, correctly, degrades ANY malformed `emission` block to
# `EmissionConfig(mode="flat")` with empty `aspects`/`concerns` -- that
# accessor-level contract is owned and tested by
# `test_decouple_emitter.py::TestGetEmissionConfigAccessor` and is NOT
# re-tested here (same non-duplication convention as the rest of this file).
#
# What IS tested here: the `validate_riskmap.py` wiring's response when that
# degradation happens to a block that is genuinely PRESENT and malformed, as
# opposed to a block that is present, validly parsed, and simply configured
# with `mode: flat` and no registries at all (the D3 rollback lever --
# `TestEmissionDriftCLIWiring::test_clean_emission_config_with_block_exits_0`
# above already covers that legitimate case and must keep passing unchanged).

# Malformation choice: a `concerns[].edges` entry with a 3-element tuple.
# Chosen because it is the exact, already-precedented malformed shape covered
# by `test_decouple_emitter.py::TestGetEmissionConfigAccessor::
# test_malformed_concern_entry_bad_edge_tuple_arity_defaults_to_flat` --
# picking the same shape means there is no ambiguity about whether this
# fixture "would cause get_emission_config() to degrade"; that is already
# proven at the accessor level. This suite only adds the CLI-wiring-layer
# assertions on top.


def _corrupt_one_concerns_edge_arity(emission: dict[str, Any]) -> None:
    """
    Mutate a real, valid `emission` dict in place: turn the first
    `concerns[0].edges[0]` entry into an invalid 3-element tuple.

    Every other field (mode, aspects, the rest of concerns, portStyles)
    stays exactly as the real config declares it -- this reproduces the bug
    report's scenario precisely: the real registries genuinely cover the
    real corpus, but ONE unrelated entry is malformed, which silently drops
    ALL of them via get_emission_config()'s whole-block degrade-on-any-error
    contract.
    """
    first_entry = emission["concerns"][0]
    src, tgt = first_entry["edges"][0]
    first_entry["edges"][0] = [src, tgt, "extra"]


def _corrupt_emission_mode_value(emission: dict[str, Any]) -> None:
    """
    Mutate a real, valid `emission` dict in place: set `mode` to an invalid
    value.

    This is a different malformation shape than `_corrupt_one_concerns_edge_arity`
    on purpose: `get_emission_config()` rejects an unknown `mode` value before
    it ever reaches concerns/aspects parsing (see
    `test_decouple_emitter.py::TestGetEmissionConfigAccessor::
    test_unknown_mode_value_defaults_to_flat`), so a fix that only scans
    `concerns[].edges` entries for bad arity would never see this case. Using
    the same real, covering registries as the arity fixture (only `mode`
    changes) keeps the 43-cross-edge cascade reproducible for this shape too.
    """
    emission["mode"] = "bogus"


def _copy_real_corpus_with_corrupted_emission(base: Path, corrupt_emission) -> Path:
    """
    Copy the REAL repo's components/controls/risks YAML verbatim (the real,
    live corpus and its real, already-covering emission registries -- see
    `risk-map/yaml/mermaid-styles.yaml`'s `graphTypes.component.emission`,
    D3), then write a `mermaid-styles.yaml` built by deep-loading the real
    one and corrupting it via `corrupt_emission` (mutates the
    `graphTypes.component.emission` dict in place).

    Using the real corpus (not a small synthetic stand-in) is deliberate: it
    is the only way to actually reproduce the bug report's "43 of them on the
    live corpus" cascade, proving the chosen fixture triggers the real-world
    failure mode rather than a synthetic analog of it. Never writes back to
    the real repo files -- everything lands under `base` (a pytest tmp_path).
    """
    yaml_dir = base / "risk-map" / "yaml"
    yaml_dir.mkdir(parents=True, exist_ok=True)
    for name in ("components.yaml", "controls.yaml", "risks.yaml"):
        shutil.copy(_REPO_ROOT / "risk-map" / "yaml" / name, yaml_dir / name)

    real_styles = yaml.safe_load(
        (_REPO_ROOT / "risk-map" / "yaml" / "mermaid-styles.yaml").read_text(encoding="utf-8")
    )
    corrupt_emission(real_styles["graphTypes"]["component"]["emission"])
    (yaml_dir / "mermaid-styles.yaml").write_text(yaml.dump(real_styles), encoding="utf-8")
    return base


# Required substrings for the new single distinct warning. Exact prose is an
# implementation choice (matching this repo's message-contract convention --
# see test_decouple_guards.py's _assert_message_contract), but these pieces
# are load-bearing: the config path names WHERE the problem is, "could not
# be parsed" names WHAT happened, "degraded to flat" names the consequence,
# and "registries could not be validated" makes clear the concerns/aspects
# entries were never checked -- so a reader does not conclude (wrongly) that
# the registries themselves are what needs fixing.
_MALFORMED_BLOCK_REQUIRED_FRAGMENTS = (
    "graphTypes.component.emission",
    "could not be parsed",
    "degraded to flat",
    "registries could not be validated",
)

# Subset unique to the malformed-block message (excludes the bare config-path
# prefix, which legitimately also appears in the genuine G-C3 message --
# "graphTypes.component.emission.concerns: no entry covers ..." -- so it is
# not, by itself, a safe negative-assertion fragment). Used by the sparse
# regression guard below to prove it does NOT also print the malformed
# warning, without false-triggering on the shared path prefix.
_MALFORMED_BLOCK_UNIQUE_FRAGMENTS = (
    "could not be parsed",
    "degraded to flat",
    "registries could not be validated",
)

# Strings that must NEVER appear alongside the malformed-block warning --
# these are the misleading G-C3-cascade artifacts the fix exists to prevent.
# ("Emission drift check found" itself is fine at header level with count 1;
# what must not happen is 43 of these per-edge item lines.)
_MISLEADING_CASCADE_FRAGMENTS = (
    "no entry covers cross edge",
    "Add an entry to graphTypes.component.emission.concerns naming this edge",
    "synthesizing fallback label",
)


class TestEmissionMalformedBlockDistinctWarning:
    def test_prints_exactly_one_warning_not_the_per_edge_cascade(self, tmp_path):
        """
        Given: the real corpus, with a real emission block whose registries
               genuinely cover every cross edge, but one concerns[].edges
               entry corrupted to a 3-element tuple
        When: validate_riskmap.py --force --allow-isolated runs (no --block)
        Then: exactly ONE emission-related warning is printed (not 43), and
              none of the misleading per-edge cascade text appears
        """
        _copy_real_corpus_with_corrupted_emission(tmp_path, _corrupt_one_concerns_edge_arity)
        result = _run(tmp_path)
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"Expected exit 0 without --block; got {result.returncode}\nstdout: "
            f"{result.stdout}\nstderr: {result.stderr}"
        )
        assert "   ⚠️ Emission drift check found 1 issue(s):" in combined, (
            f"Expected exactly one warning under the standard warn-only-check "
            f"header, not a cascade; got:\n{combined}"
        )
        for fragment in _MISLEADING_CASCADE_FRAGMENTS:
            assert fragment not in combined, (
                f"Malformed-block warning must not misdirect toward a "
                f"config-content fix; found forbidden fragment {fragment!r} "
                f"in:\n{combined}"
            )

    def test_single_warning_names_the_real_problem(self, tmp_path):
        """
        Given: the same malformed-block corpus
        When: validate_riskmap.py --force --allow-isolated runs
        Then: the one warning's text clearly identifies a malformed/degraded
              emission block -- every load-bearing fragment from the message
              contract is present
        """
        _copy_real_corpus_with_corrupted_emission(tmp_path, _corrupt_one_concerns_edge_arity)
        result = _run(tmp_path)
        combined = result.stdout + result.stderr

        for fragment in _MALFORMED_BLOCK_REQUIRED_FRAGMENTS:
            assert fragment in combined, (
                f"Expected the malformed-block warning to contain {fragment!r} "
                f"(message-contract requirement); got:\n{combined}"
            )

    def test_with_block_promotes_the_single_warning_and_exits_1(self, tmp_path):
        """
        Given: the same malformed-block corpus
        When: validate_riskmap.py --force --allow-isolated --block runs
        Then: exit 1, the ❌ label and epilogue both print (same
              warn_block_triggered / --block participation as every other
              warn-only check), and still exactly one item line -- not 43
        """
        _copy_real_corpus_with_corrupted_emission(tmp_path, _corrupt_one_concerns_edge_arity)
        result = _run(tmp_path, "--block")
        combined = result.stdout + result.stderr

        assert result.returncode == 1, (
            f"Expected exit 1 with --block on a malformed emission block; got "
            f"{result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "   ❌ Emission drift check found 1 issue(s):" in combined, (
            f"Expected the ❌-labeled single-warning header under --block; got:\n{combined}"
        )
        assert "   ❌ Warn-only check failures promoted to errors (--block)." in combined, (
            f"Expected the shared --block epilogue; got:\n{combined}"
        )
        for fragment in _MISLEADING_CASCADE_FRAGMENTS:
            assert fragment not in combined, (
                f"Malformed-block warning must not misdirect toward a "
                f"config-content fix even under --block; found forbidden "
                f"fragment {fragment!r} in:\n{combined}"
            )

    def test_bad_mode_value_also_produces_the_single_distinct_warning(self, tmp_path):
        """
        Given: the real corpus, with a real emission block whose registries
               genuinely cover every cross edge, but `mode` set to an invalid
               value (a different malformation shape than the arity-tuple
               fixture above -- see `_corrupt_emission_mode_value`)
        When: validate_riskmap.py --force --allow-isolated runs (no --block)
        Then: the same single-distinct-warning contract holds: exactly one
              warning, all four required message fragments present, none of
              the misleading per-edge cascade fragments present

        This pins that the fix is a general "did the block fail to parse"
        detector, not one that only recognizes the arity-tuple shape. A bad
        `mode` value is rejected by `get_emission_config()` before it ever
        reaches concerns/aspects parsing, so a narrower, shape-specific check
        would pass every other test in this class while still cascading on
        this input.
        """
        _copy_real_corpus_with_corrupted_emission(tmp_path, _corrupt_emission_mode_value)
        result = _run(tmp_path)
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"Expected exit 0 without --block; got {result.returncode}\nstdout: "
            f"{result.stdout}\nstderr: {result.stderr}"
        )
        assert "   ⚠️ Emission drift check found 1 issue(s):" in combined, (
            f"Expected exactly one warning under the standard warn-only-check "
            f"header, not a cascade; got:\n{combined}"
        )
        for fragment in _MALFORMED_BLOCK_REQUIRED_FRAGMENTS:
            assert fragment in combined, (
                f"Expected the malformed-block warning to contain {fragment!r} "
                f"(message-contract requirement); got:\n{combined}"
            )
        for fragment in _MISLEADING_CASCADE_FRAGMENTS:
            assert fragment not in combined, (
                f"Malformed-block warning must not misdirect toward a "
                f"config-content fix; found forbidden fragment {fragment!r} "
                f"in:\n{combined}"
            )


# ============================================================================
# Regression guard -- a validly-parsed but genuinely sparse registry must
# still drift-check normally (the fix must not overcorrect)
# ============================================================================
#
# Paired with TestEmissionMalformedBlockDistinctWarning above. Proves the fix
# distinguishes "block failed to parse" (single distinct warning, no
# check_emission_drift() call) from "block parsed fine, registries just
# don't cover everything" (a REAL drift condition -- check_emission_drift()
# must still run and still produce its normal per-edge G-C3 warnings). A fix
# that blanket-suppresses check_emission_drift() whenever the resulting
# config's concerns/aspects happen to be small or incomplete would pass every
# test above while silently breaking this genuinely-drifted case -- that
# regression is what this class exists to catch.

_SPARSE_VALID_COMPONENTS: dict[str, Any] = {
    "components": [
        {
            "id": "compInfra",
            "title": "Infra",
            "category": "componentsInfrastructure",
            "subcategory": "componentsData",
            "edges": {"to": ["compModel", "compTools"], "from": []},
        },
        {
            "id": "compModel",
            "title": "Model",
            "category": "componentsModel",
            "subcategory": "componentsModelTraining",
            "edges": {"to": [], "from": ["compInfra"]},
        },
        {
            "id": "compApp",
            "title": "App",
            "category": "componentsApplication",
            "subcategory": "componentsAgent",
            "edges": {},
        },
        {
            "id": "compTools",
            "title": "Tools",
            "category": "componentsTools",
            "subcategory": "componentsToolCore",
            "edges": {"to": [], "from": ["compInfra"]},
        },
    ],
    "categories": _CLEAN_COMPONENTS["categories"],
}

# Two cross edges: compInfra->compModel (covered below) and
# compInfra->compTools (deliberately left uncovered -- the genuine drift).
_SPARSE_VALID_EMISSION: dict[str, Any] = {
    "mode": "decoupled",
    "concerns": [{"label": "infra to model", "edges": [["compInfra", "compModel"]]}],
}


def _write_sparse_corpus(base: Path) -> Path:
    """Write the 2-cross-edge synthetic corpus with a validly-parsed, genuinely sparse emission config."""
    yaml_dir = base / "risk-map" / "yaml"
    yaml_dir.mkdir(parents=True, exist_ok=True)
    (yaml_dir / "components.yaml").write_text(yaml.dump(_SPARSE_VALID_COMPONENTS), encoding="utf-8")
    (yaml_dir / "controls.yaml").write_text(yaml.dump(_CLEAN_CONTROLS), encoding="utf-8")
    (yaml_dir / "risks.yaml").write_text(yaml.dump({"risks": []}), encoding="utf-8")
    (yaml_dir / "mermaid-styles.yaml").write_text(
        yaml.dump(_mermaid_with_emission(_SPARSE_VALID_EMISSION)), encoding="utf-8"
    )
    return base


class TestEmissionValidSparseConfigStillDrifts:
    def test_uncovered_edge_still_triggers_the_normal_per_edge_warning(self, tmp_path):
        """
        Given: a validly-parsed emission block (mode: decoupled, one
               concerns entry) whose registry covers one of two cross edges
        When: validate_riskmap.py --force --allow-isolated runs (no --block)
        Then: the genuine G-C3 uncovered-edge warning fires for the
              uncovered edge, with its real "add an entry" remediation text
              -- proving the fix does not suppress genuine drift just
              because the registry happens to be small
        """
        _write_sparse_corpus(tmp_path)
        result = _run(tmp_path)
        combined = result.stdout + result.stderr

        assert result.returncode == 0, (
            f"Expected exit 0 without --block; got {result.returncode}\nstdout: "
            f"{result.stdout}\nstderr: {result.stderr}"
        )
        assert "   ⚠️ Emission drift check found 1 issue(s):" in combined, (
            f"Expected exactly the one genuine uncovered-edge warning; got:\n{combined}"
        )
        assert "no entry covers cross edge (compInfra, compTools)" in combined, (
            f"Expected the real G-C3 warning naming the genuinely uncovered edge; got:\n{combined}"
        )
        for fragment in _MALFORMED_BLOCK_UNIQUE_FRAGMENTS:
            assert fragment not in combined, (
                f"A validly-parsed sparse config must not print the "
                f"malformed-block warning; found forbidden fragment "
                f"{fragment!r} in:\n{combined}"
            )

    def test_with_block_the_genuine_drift_still_promotes_and_exits_1(self, tmp_path):
        """
        Same sparse-but-valid corpus, --block: exit 1 and the genuine
        uncovered-edge warning still participates in warn_block_triggered
        exactly like any other real drift finding.
        """
        _write_sparse_corpus(tmp_path)
        result = _run(tmp_path, "--block")
        combined = result.stdout + result.stderr

        assert result.returncode == 1, (
            f"Expected exit 1 with --block on genuine (non-malformed) drift; "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "no entry covers cross edge (compInfra, compTools)" in combined
        assert "   ❌ Warn-only check failures promoted to errors (--block)." in combined

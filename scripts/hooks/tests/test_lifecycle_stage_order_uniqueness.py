#!/usr/bin/env python3
"""
Tests for the lifecycleStage.order uniqueness validator check.

Per ADR-022 D4 (line 98): uniqueness across array items is awkward in JSON Schema;
a small validator check is the cleaner path. This file tests that validator check.

Per ADR-022 D8 (line 271):
  "D4 lifecycleStage.order uniqueness | recommended: validator extension | validator |
   Conformance-sweep deliverable"

The validator must:
- Accept the current lifecycle-stage.yaml corpus (orders 1..8, all unique).
- Reject any input where two or more stages share an order value.
- Identify the colliding stage IDs and the duplicated order value in its failure
  output, so a developer reading CI output can locate the defect.
- Block immediately (no warn-only path); the corpus is clean at landing.

Coverage:
- Positive/regression: current lifecycle-stage.yaml passes.
- Single duplicate pair (two stages with the same order).
- Triple duplicate (three stages with the same order).
- All-same-order degenerate case (every stage carries order: 1).
- Non-canonical order sequence that contains a hidden duplicate
  (e.g. [3, 11, 4, 11, 5, 9, 2, 6] — duplicated value 11).
- Output shape: failure result carries the colliding IDs and the duplicated value.

Note: this check assumes each stage carries an `order` key; malformed-structure
rejection (missing/wrong-type keys) is the schema layer's responsibility — see
`test_lifecycle_stage_order_range.py` for the schema-side coverage.
"""

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

# noqa I001 retained because ruff's import-sort would re-order this past the
# sys.path.insert above and break the deferred import pattern.
from riskmap_validator.validator import check_lifecycle_stage_order_uniqueness  # noqa: E402, I001


# ============================================================================
# Module-level constants — inline YAML fixture data
# ============================================================================

# The current corpus: 8 stages, orders 1–8, no duplicates.
_CORPUS_CLEAN = {
    "lifecycleStages": [
        {"id": "planning", "title": "Planning", "order": 1},
        {"id": "data-preparation", "title": "Data Preparation", "order": 2},
        {"id": "model-training", "title": "Model Training", "order": 3},
        {"id": "development", "title": "Development", "order": 4},
        {"id": "evaluation", "title": "Evaluation", "order": 5},
        {"id": "deployment", "title": "Deployment", "order": 6},
        {"id": "runtime", "title": "Runtime", "order": 7},
        {"id": "maintenance", "title": "Maintenance", "order": 8},
    ]
}

# Single duplicate pair: two stages both claim order 3.
_CORPUS_SINGLE_DUPLICATE = {
    "lifecycleStages": [
        {"id": "stage-a", "title": "Stage A", "order": 1},
        {"id": "stage-b", "title": "Stage B", "order": 2},
        {"id": "stage-c", "title": "Stage C", "order": 3},
        {"id": "stage-d", "title": "Stage D", "order": 3},  # duplicate
        {"id": "stage-e", "title": "Stage E", "order": 5},
    ]
}

# Triple duplicate: three stages all carry order 5.
_CORPUS_TRIPLE_DUPLICATE = {
    "lifecycleStages": [
        {"id": "alpha", "title": "Alpha", "order": 1},
        {"id": "beta", "title": "Beta", "order": 5},
        {"id": "gamma", "title": "Gamma", "order": 5},
        {"id": "delta", "title": "Delta", "order": 5},  # third with order 5
        {"id": "epsilon", "title": "Epsilon", "order": 8},
    ]
}

# Degenerate: every stage has order 1.
_CORPUS_ALL_SAME = {
    "lifecycleStages": [{"id": f"stage-{i}", "title": f"Stage {i}", "order": 1} for i in range(1, 6)]
}

# Non-canonical sequence with a hidden duplicate:
# orders [3, 11, 4, 11, 5, 9, 2, 6] — value 11 appears twice.
# 11 is a two-digit value that does not appear in any stage ID (s1–s8),
# making the substring assertion in the output-shape test unambiguous.
_CORPUS_HIDDEN_DUPLICATE = {
    "lifecycleStages": [
        {"id": "s1", "title": "S1", "order": 3},
        {"id": "s2", "title": "S2", "order": 11},
        {"id": "s3", "title": "S3", "order": 4},
        {"id": "s4", "title": "S4", "order": 11},  # duplicate of s2
        {"id": "s5", "title": "S5", "order": 5},
        {"id": "s6", "title": "S6", "order": 9},
        {"id": "s7", "title": "S7", "order": 2},
        {"id": "s8", "title": "S8", "order": 6},
    ]
}

# Minimal clean corpus (two stages, distinct orders) — verify trivially valid input passes.
_CORPUS_MINIMAL_CLEAN = {
    "lifecycleStages": [
        {"id": "first", "title": "First", "order": 1},
        {"id": "second", "title": "Second", "order": 2},
    ]
}

# Single stage — always unique by definition.
_CORPUS_SINGLE_STAGE = {
    "lifecycleStages": [
        {"id": "only", "title": "Only Stage", "order": 1},
    ]
}

# Empty stages array — no orders to compare; must pass without error.
_CORPUS_EMPTY = {"lifecycleStages": []}


# ============================================================================
# Positive / regression tests
# ============================================================================


class TestLifecycleStageOrderUniquenessPassCases:
    """Inputs that carry no duplicate order values must be accepted."""

    def test_current_corpus_in_memory_passes(self):
        """
        Test that the in-memory representation of the current corpus passes uniqueness.

        Given: A dict matching the shape of lifecycle-stage.yaml (orders 1..8)
        When: the uniqueness check is called
        Then: The result indicates success (no duplicates)
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_CLEAN)
        assert result.is_valid, f"Current corpus (orders 1..8) must pass uniqueness; got errors: {result.errors}"

    def test_current_yaml_file_passes(self, lifecycle_stage_yaml_path: Path):
        """
        Test that the actual lifecycle-stage.yaml on disk passes uniqueness.

        Given: lifecycle-stage.yaml loaded from the repository
        When: the uniqueness check is called with its parsed content
        Then: The result indicates success (non-destructive against today's corpus)
        """
        with open(lifecycle_stage_yaml_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        result = check_lifecycle_stage_order_uniqueness(data)
        assert result.is_valid, (
            f"lifecycle-stage.yaml on disk must pass order uniqueness; got errors: {result.errors}"
        )

    def test_minimal_two_stage_corpus_passes(self):
        """
        Test that a two-stage corpus with distinct orders passes.

        Given: Two stages with orders 1 and 2
        When: the uniqueness check is called
        Then: The result indicates success
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_MINIMAL_CLEAN)
        assert result.is_valid, f"Two distinct orders must pass; got errors: {result.errors}"

    def test_single_stage_corpus_passes(self):
        """
        Test that a single-stage corpus passes (uniqueness is vacuously satisfied).

        Given: One stage
        When: the uniqueness check is called
        Then: The result indicates success (no pair to collide)
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_SINGLE_STAGE)
        assert result.is_valid, f"Single stage must pass uniqueness; got errors: {result.errors}"

    def test_empty_stages_array_passes(self):
        """
        Test that an empty lifecycleStages array passes.

        Given: lifecycleStages: [] (no stages)
        When: the uniqueness check is called
        Then: The result indicates success (nothing to be non-unique)
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_EMPTY)
        assert result.is_valid, f"Empty stages array must pass uniqueness; got errors: {result.errors}"


# ============================================================================
# Negative tests — duplicate rejection
# ============================================================================


class TestLifecycleStageOrderUniquenessRejectCases:
    """Inputs with duplicate order values must be rejected."""

    def test_single_duplicate_pair_is_rejected(self):
        """
        Test that two stages sharing order 3 are rejected.

        Given: Five stages where stage-c and stage-d both carry order 3
        When: the uniqueness check is called
        Then: The result indicates failure
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_SINGLE_DUPLICATE)
        assert not result.is_valid, "Two stages with the same order value must fail uniqueness validation"

    def test_triple_duplicate_is_rejected(self):
        """
        Test that three stages sharing order 5 are rejected.

        Given: Five stages where beta, gamma, and delta all carry order 5
        When: the uniqueness check is called
        Then: The result indicates failure
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_TRIPLE_DUPLICATE)
        assert not result.is_valid, "Three stages with the same order value must fail uniqueness validation"

    def test_all_same_order_is_rejected(self):
        """
        Test that a corpus where every stage carries order 1 is rejected.

        Given: Five stages each with order: 1
        When: the uniqueness check is called
        Then: The result indicates failure (order 1 appears five times)
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_ALL_SAME)
        assert not result.is_valid, "All stages carrying the same order value must fail uniqueness validation"

    def test_non_canonical_sequence_with_hidden_duplicate_is_rejected(self):
        """
        Test that orders [3,11,4,11,5,9,2,6] — duplicate value 11 — are rejected.

        Given: Eight stages with non-ascending orders containing a hidden duplicate (11)
        When: the uniqueness check is called
        Then: The result indicates failure
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_HIDDEN_DUPLICATE)
        assert not result.is_valid, (
            "Non-canonical order sequence with a duplicate value (11 appears twice) must fail"
        )


# ============================================================================
# Output shape tests — failure must identify colliders
# ============================================================================


class TestLifecycleStageOrderUniquenessOutputShape:
    """
    On failure the result must carry enough information to identify the defect.

    ADR-022 D4 says "a developer reading CI output can locate the bug".
    The assertions here verify that the error payload mentions the duplicated
    order value and the IDs of the stages that collide — without prescribing
    the exact message format (that is SWE's call).
    """

    def test_single_duplicate_failure_identifies_duplicated_order_value(self):
        """
        Test that the failure result names the duplicated order value.

        Given: stage-c and stage-d both carry order 3
        When: the uniqueness check is called and fails
        Then: The error payload mentions the value 3 (the colliding order)
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_SINGLE_DUPLICATE)
        assert not result.is_valid

        # The error representation must contain the duplicated value.
        # We stringify result.errors to be format-agnostic.
        errors_repr = str(result.errors)
        assert "3" in errors_repr, f"Failure output must mention the duplicated order value 3; got: {errors_repr}"

    def test_single_duplicate_failure_identifies_both_colliding_stage_ids(self):
        """
        Test that the failure result names both stage IDs that share order 3.

        Given: stage-c and stage-d both carry order 3
        When: the uniqueness check is called and fails
        Then: The error payload mentions both 'stage-c' and 'stage-d'
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_SINGLE_DUPLICATE)
        assert not result.is_valid

        errors_repr = str(result.errors)
        assert "stage-c" in errors_repr, (
            f"Failure output must mention colliding stage ID 'stage-c'; got: {errors_repr}"
        )
        assert "stage-d" in errors_repr, (
            f"Failure output must mention colliding stage ID 'stage-d'; got: {errors_repr}"
        )

    def test_triple_duplicate_failure_identifies_all_three_colliding_stage_ids(self):
        """
        Test that a triple collision names all three stages in the error payload.

        Given: beta, gamma, and delta all carry order 5
        When: the uniqueness check is called and fails
        Then: The error payload mentions beta, gamma, and delta
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_TRIPLE_DUPLICATE)
        assert not result.is_valid

        errors_repr = str(result.errors)
        for stage_id in ("beta", "gamma", "delta"):
            assert stage_id in errors_repr, (
                f"Failure output must mention colliding stage ID '{stage_id}'; got: {errors_repr}"
            )

    def test_hidden_duplicate_failure_identifies_colliding_ids_and_value(self):
        """
        Test that a hidden duplicate in a non-canonical sequence is identified.

        Given: s2 (order 11) and s4 (order 11) in sequence [3,11,4,11,5,9,2,6]
        When: the uniqueness check is called and fails
        Then: The error payload mentions both 's2' and 's4', and the value 11
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_HIDDEN_DUPLICATE)
        assert not result.is_valid

        errors_repr = str(result.errors)
        assert "s2" in errors_repr, f"Failure output must mention colliding stage ID 's2'; got: {errors_repr}"
        assert "s4" in errors_repr, f"Failure output must mention colliding stage ID 's4'; got: {errors_repr}"
        assert "11" in errors_repr, (
            f"Failure output must mention the duplicated order value 11; got: {errors_repr}"
        )

    def test_result_has_errors_attribute(self):
        """
        Test that the result object exposes an errors attribute.

        Given: A corpus with a duplicate order
        When: the uniqueness check is called and fails
        Then: result.errors is a non-empty collection
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_SINGLE_DUPLICATE)
        assert not result.is_valid
        assert result.errors, "result.errors must be non-empty on failure"

    def test_result_has_no_errors_on_clean_corpus(self):
        """
        Test that the result object has an empty errors collection on success.

        Given: The clean 8-stage corpus
        When: the uniqueness check is called and passes
        Then: result.errors is empty (or falsy)
        """
        result = check_lifecycle_stage_order_uniqueness(_CORPUS_CLEAN)
        assert result.is_valid
        assert not result.errors, f"result.errors must be empty on success; got: {result.errors}"


# ============================================================================
# CLI wiring tests — validate_riskmap.py integration (ADR-022 D4)
# ============================================================================

# Absolute path to the CLI script under test.
_SCRIPT = Path(__file__).parent.parent / "validate_riskmap.py"

# Repository root — used as cwd for the live-corpus subprocess test.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Minimal corpus shapes required by validate_riskmap.py --force.
# components.yaml: two components with mutual edges so ComponentEdgeValidator passes.
# The subcategory field keeps the nesting check silent (valid pair for each component).
_MINIMAL_COMPONENTS: dict[str, Any] = {
    "components": [
        {
            "id": "componentAlpha",
            "title": "Alpha",
            "category": "componentsInfrastructure",
            "subcategory": "componentsData",
            "edges": {"to": ["componentBeta"], "from": []},
        },
        {
            "id": "componentBeta",
            "title": "Beta",
            "category": "componentsInfrastructure",
            "subcategory": "componentsData",
            "edges": {"to": [], "from": ["componentAlpha"]},
        },
    ],
    "categories": [
        {
            "id": "componentsInfrastructure",
            "title": "Infrastructure",
            "subcategory": [
                {"id": "componentsData", "title": "Data"},
            ],
        },
    ],
}

# controls.yaml with no dangling refs (mirror check stays quiet).
_MINIMAL_CONTROLS: dict[str, Any] = {
    "controls": [
        {
            "id": "controlClean",
            "title": "Clean Control",
            "category": "controlsModel",
            "components": ["componentAlpha"],
            "risks": [],
            "personas": [],
        }
    ]
}

# risks.yaml stub — script reads this file; content irrelevant to lifecycle check.
_MINIMAL_RISKS: dict[str, Any] = {"risks": []}

# lifecycle-stage.yaml with unique orders 1–3 (clean corpus, no duplicates).
_LIFECYCLE_UNIQUE: dict[str, Any] = {
    "lifecycleStages": [
        {"id": "stage-one", "title": "Stage One", "order": 1},
        {"id": "stage-two", "title": "Stage Two", "order": 2},
        {"id": "stage-three", "title": "Stage Three", "order": 3},
    ]
}

# lifecycle-stage.yaml where stage-b and stage-c both carry order 2 (duplicate).
_LIFECYCLE_DUPLICATE: dict[str, Any] = {
    "lifecycleStages": [
        {"id": "stage-a", "title": "Stage A", "order": 1},
        {"id": "stage-b", "title": "Stage B", "order": 2},
        {"id": "stage-c", "title": "Stage C", "order": 2},  # duplicate
    ]
}


def _write_lifecycle_corpus(
    base: Path,
    lifecycle: dict[str, Any] | None,
) -> Path:
    """
    Write a minimal corpus under base/risk-map/yaml/ and return base as cwd.

    Writes components.yaml, controls.yaml, risks.yaml unconditionally.
    Writes lifecycle-stage.yaml only when lifecycle is not None, simulating
    the file-absent case for the graceful-skip test.

    Args:
        base: Temporary directory root (pytest tmp_path).
        lifecycle: Parsed lifecycle-stage.yaml content, or None to omit the file.

    Returns:
        base path for use as subprocess cwd.
    """
    yaml_dir = base / "risk-map" / "yaml"
    yaml_dir.mkdir(parents=True)
    (yaml_dir / "components.yaml").write_text(yaml.dump(_MINIMAL_COMPONENTS), encoding="utf-8")
    (yaml_dir / "controls.yaml").write_text(yaml.dump(_MINIMAL_CONTROLS), encoding="utf-8")
    (yaml_dir / "risks.yaml").write_text(yaml.dump(_MINIMAL_RISKS), encoding="utf-8")
    if lifecycle is not None:
        (yaml_dir / "lifecycle-stage.yaml").write_text(yaml.dump(lifecycle), encoding="utf-8")
    return base


def _run_lifecycle(cwd: Path) -> subprocess.CompletedProcess:
    """
    Run validate_riskmap.py --force --allow-isolated from the given cwd.

    --force: validate regardless of git-staged state.
    --allow-isolated: skip orphan check so minimal corpora don't fail on that.

    Args:
        cwd: Working directory for the subprocess.

    Returns:
        CompletedProcess with returncode, stdout, stderr.
    """
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--force", "--allow-isolated"],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


class TestLifecycleUniquenessCLI:
    """
    CLI integration tests: validate_riskmap.py must call
    check_lifecycle_stage_order_uniqueness() and exit 1 on duplicate orders.

    ADR-022 D4 specifies block-mode-immediate (no --block flag required).
    The --block flag is NOT involved here; the check always fails hard.
    """

    def test_live_corpus_exits_0(self):
        """
        Running against the actual lifecycle-stage.yaml (orders 1..8, all unique) exits 0.

        Given: The real lifecycle-stage.yaml on disk (no duplicate orders)
        When: validate_riskmap.py --force --allow-isolated (cwd=repo root)
        Then: Exit code is 0 (no uniqueness violations)

        This is a regression guard: if the wiring lands correctly and the live
        corpus is clean, this test must pass on every subsequent run.
        """
        result = _run_lifecycle(_REPO_ROOT)
        assert result.returncode == 0, (
            f"Expected exit 0 against live corpus (orders 1..8 unique); "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_synthesised_corpus_with_duplicate_order_exits_1(self, tmp_path):
        """
        A synthesised corpus whose lifecycle-stage.yaml has duplicate order values exits 1.

        Given: A corpus where stage-b and stage-c both carry order 2
        When: validate_riskmap.py --force --allow-isolated
        Then: Exit code is 1 (duplicate orders detected, block-mode-immediate)
        """
        _write_lifecycle_corpus(tmp_path, _LIFECYCLE_DUPLICATE)
        result = _run_lifecycle(tmp_path)
        assert result.returncode == 1, (
            f"Expected exit 1 for corpus with duplicate lifecycle order; "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_synthesised_corpus_with_duplicate_order_output_names_value_and_ids(self, tmp_path):
        """
        When duplicate orders are found, the output names the duplicated value
        and the colliding stage IDs so a developer can locate the defect.

        Given: stage-b and stage-c both carry order 2
        When: validate_riskmap.py --force --allow-isolated
        Then: Output (stdout or stderr) mentions the duplicated value 2 AND
              mentions both "stage-b" and "stage-c"
        """
        _write_lifecycle_corpus(tmp_path, _LIFECYCLE_DUPLICATE)
        result = _run_lifecycle(tmp_path)
        combined = result.stdout + result.stderr
        # "2" is the duplicated order value in _LIFECYCLE_DUPLICATE.
        # Stage IDs are "stage-a/b/c" and orders are 1/2/2; no other field
        # in the corpus produces a bare "2" in the script's output, so the
        # substring assertion is unambiguous for this corpus.
        assert "2" in combined, (
            f"Expected duplicated order value '2' in output; stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
        # Check that both colliding stage IDs are named.
        assert "stage-b" in combined, (
            f"Expected colliding stage ID 'stage-b' in output; "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )
        assert "stage-c" in combined, (
            f"Expected colliding stage ID 'stage-c' in output; "
            f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
        )

    def test_synthesised_corpus_with_unique_orders_exits_0(self, tmp_path):
        """
        A synthesised corpus with unique lifecycle orders exits 0.

        Given: A corpus where lifecycle-stage.yaml has orders 1, 2, 3 (all unique)
        When: validate_riskmap.py --force --allow-isolated
        Then: Exit code is 0

        Confirms the block-mode-immediate semantic fires only on actual duplicates,
        not on any lifecycle file presence.
        """
        _write_lifecycle_corpus(tmp_path, _LIFECYCLE_UNIQUE)
        result = _run_lifecycle(tmp_path)
        assert result.returncode == 0, (
            f"Expected exit 0 for corpus with unique lifecycle orders; "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_synthesised_corpus_without_lifecycle_file_exits_0(self, tmp_path):
        """
        A corpus with no lifecycle-stage.yaml exits 0 (graceful skip).

        Given: A corpus directory that does NOT contain lifecycle-stage.yaml
        When: validate_riskmap.py --force --allow-isolated
        Then: Exit code is 0 (lifecycle check is skipped, not failed)

        lifecycle-stage.yaml may not be present in every test environment.
        The check must degrade gracefully when the file is absent, matching
        the broad-except pattern used by the mirror and nesting checks.
        """
        _write_lifecycle_corpus(tmp_path, None)  # None = omit the file
        result = _run_lifecycle(tmp_path)
        assert result.returncode == 0, (
            f"Expected exit 0 when lifecycle-stage.yaml is absent (graceful skip); "
            f"got {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Test classes: 4

TestLifecycleStageOrderUniquenessPassCases (5 tests)
  — current corpus in-memory; lifecycle-stage.yaml on disk; minimal 2-stage;
    single stage; empty array.

TestLifecycleStageOrderUniquenessRejectCases (4 tests)
  — single duplicate pair (order 3); triple duplicate (order 5); all-same-order;
    non-canonical hidden duplicate (order 11 in sequence [3,11,4,11,5,9,2,6]).

TestLifecycleStageOrderUniquenessOutputShape (6 tests)
  — failure names the duplicated value; failure names both colliding IDs (pair);
    failure names all three colliding IDs (triple); failure names colliding IDs + value
    for hidden duplicate; result.errors is non-empty on failure; result.errors is
    empty on success.

TestLifecycleUniquenessCLI (5 tests — subprocess CLI integration)
  — live corpus exits 0 (orders 1..8 unique, regression guard);
    synthesised corpus with duplicate order exits 1 (block-mode-immediate);
    synthesised corpus with duplicate order output names value + colliding IDs;
    synthesised corpus with unique orders exits 0;
    synthesised corpus missing lifecycle-stage.yaml exits 0 (graceful skip).

Total: 20 tests

Coverage areas:
  - ADR-022 D4: order uniqueness check, block-mode-immediate, validator extension
  - Regression: current lifecycle-stage.yaml remains valid
  - Rejection: single, triple, all-same, non-canonical duplicate orderings
  - Output shape: colliding IDs and duplicated value present in error payload
  - Result contract: is_valid / errors attributes on returned result object
  - CLI wiring: validate_riskmap.py calls the check; exit codes; graceful skip
"""

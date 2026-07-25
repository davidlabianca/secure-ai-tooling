#!/usr/bin/env python3
"""
Schema round-trip tests for the `emission` block (ADR-036 D3;
`working-plans/component-graph-decouple-strategy-c-implementation-plan.md` §F,
Phase 3 task 3.1).

`risk-map/schemas/mermaid-styles.schema.json` does not define `emission` today --
`definitions/componentGraphType` is `additionalProperties: false` and has no
`emission` property, so ANY `graphTypes.component.emission` key is currently
rejected outright by check-jsonschema, regardless of its internal shape. This is
the RED phase of task 3.1's schema-surface slice; `swe` (task 3.3) adds:

    - `definitions/componentGraphType.properties.emission` (optional)
    - `definitions/emission` (`required: [mode]`, `additionalProperties: false`)
    - `definitions/emissionAspect` (`required: [id, minCrossInDegree]`)
    - `definitions/emissionConcern` (`required: [label, edges]`,
      `additionalProperties: false` -- no override key, per plan R1/P2)
    - `definitions/portStyles` (`port`, `pepport`, `pepWrapOutline`)
    - `mode: {"enum": ["flat", "decoupled"]}`

Two test classes:

    1. TestSchemaRoundTrip -- generic shape tests, using a SYNTHETIC emission
       block (component ids like `componentSynthSrc1` -- not real corpus ids).
       This class only proves the schema accepts/rejects the right SHAPES; it
       says nothing about whether the real `mermaid-styles.yaml` is populated.
       Deliberately separated from #2 (task instructions: "different layer").
    2. TestRealConfigValidates -- integration test against the live,
       committed `risk-map/yaml/mermaid-styles.yaml`. This is RED until
       Phase 3 task 3.3's `swe` step populates the real `emission` block
       (mode: flat + the §C registry) -- expected per task instructions, not
       a bug in this test.

Convention: subprocess `check-jsonschema` invocation, matching
`test_persona_schema_updates.py` / `test_consumer_yaml_check_jsonschema_integration.py`
(not the in-process `jsonschema` library) -- this repo's established pattern for
schema round-trip tests, and the layer the task explicitly calls out ("check-jsonschema
should reject this at the YAML-validation stage, before the accessor ever runs").
"""

import copy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Helpers
# ============================================================================


def _run_check_jsonschema(schema_path: Path, yaml_path: Path, base_uri: str) -> subprocess.CompletedProcess:
    """Invoke check-jsonschema for one (schema, yaml) pair (repo convention)."""
    return subprocess.run(
        ["check-jsonschema", "--base-uri", base_uri, "--schemafile", str(schema_path), str(yaml_path)],
        capture_output=True,
        text=True,
    )


def _write_doc(tmp_path: Path, doc: dict[str, Any], name: str = "mermaid-styles.yaml") -> Path:
    path = tmp_path / name
    path.write_text(yaml.dump(doc), encoding="utf-8")
    return path


def _combined_output_excluding_path(result: subprocess.CompletedProcess, yaml_path: Path) -> str:
    """
    Return stdout+stderr with the yaml file's own path stripped out.

    check-jsonschema prefixes every error line with the file path it validated.
    pytest's `tmp_path` fixture auto-names its directory after the current test
    function (e.g. `test_override_key_on_a_concern0`), so a substring search for
    a key name that happens to also appear in the TEST's own name (like
    "override") can false-positive-match against the file path segment of the
    output rather than the actual error content. Stripping the path first makes
    the key-name assertions load-bearing against error CONTENT only.
    """
    combined = result.stdout + result.stderr
    return combined.replace(str(yaml_path), "")


@pytest.fixture
def base_styles_doc(risk_map_yaml_dir: Path) -> dict[str, Any]:
    """
    Load the real, committed mermaid-styles.yaml as a starting point.

    Guarantees every OTHER required top-level/nested key (version, foundation,
    sharedElements, graphTypes.control, graphTypes.risk, ...) is already valid,
    so each test below only has to vary `graphTypes.component.emission` --
    isolating the assertion to the piece under test rather than hand-duplicating
    the whole schema's required structure.
    """
    with open(risk_map_yaml_dir / "mermaid-styles.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _with_emission(base_styles_doc: dict[str, Any], emission_block: Any) -> dict[str, Any]:
    """Return a deep copy of base_styles_doc with graphTypes.component.emission set."""
    doc = copy.deepcopy(base_styles_doc)
    doc["graphTypes"]["component"]["emission"] = emission_block
    return doc


# Synthetic emission block matching §C's SHAPE (1 aspect + 12 concerns + 3
# portStyles keys) but NOT the real corpus's component ids -- see module
# docstring. Deliberately kept structurally faithful (entry count, nesting)
# without asserting this is the live registry (that is TestRealConfigValidates'
# job, against the real file).
_SYNTHETIC_CONCERN_LABELS = [
    "model artifacts",
    "training data",
    "runtime hosting",
    "tool hosting",
    "tool discovery",
    "identity & authz",
    "model publish",
    "inference / serving",
    "tool calls",
    "app + agent egress",
    "tool registration",
    "tool results",
]


def _synthetic_emission_block(mode: str = "flat") -> dict[str, Any]:
    return {
        "mode": mode,
        "aspects": [{"id": "componentSynthSink", "minCrossInDegree": 10}],
        "concerns": [
            {
                "label": label,
                "edges": [["componentSynthSrc", "componentSynthTgt"]],
            }
            for label in _SYNTHETIC_CONCERN_LABELS
        ],
        "portStyles": {
            "port": "fill:#fff5f5,stroke:#c0392b,stroke-width:1.5px,stroke-dasharray:4 3",
            "pepport": "fill:#eef,stroke:#339,stroke-width:1.5px",
            "pepWrapOutline": "fill:none,stroke:#339,stroke-width:2px",
        },
    }


# ============================================================================
# 1. Schema round-trip -- generic shape (synthetic ids)
# ============================================================================


class TestSchemaRoundTrip:
    """
    check-jsonschema round-trip against `risk-map/schemas/mermaid-styles.schema.json`
    for the new `emission` definitions. See module docstring for the exact
    definitions under test.
    """

    @pytest.mark.parametrize("mode_value", ["flat", "decoupled"])
    def test_valid_emission_block_matching_c_shape_validates(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, mode_value
    ):
        """
        Given: graphTypes.component.emission populated with a §C-shaped block
               (1 aspect, 12 concerns, 3 portStyles keys), under EACH enum
               mode value in turn
        When: check-jsonschema validates the document
        Then: exit 0

        RED today: componentGraphType has no `emission` property and is
        additionalProperties: false, so this currently fails regardless of
        the block's internal shape. GREEN once task 3.3 lands the schema.

        Coverage-gap G7 (adversarial review): the original version of this
        test only ever exercised mode: flat, so a schema that special-cased
        "flat" and rejected an otherwise-identical §C-shaped block under
        mode: decoupled would still pass. Parametrizing over both enum
        values closes that gap -- the full registry shape must validate
        regardless of which mode it is declared under.
        """
        doc = _with_emission(base_styles_doc, _synthetic_emission_block(mode=mode_value))
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode == 0, (
            f"Expected a §C-shaped emission block (mode: {mode_value}) to validate.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_minimal_emission_block_with_only_mode_validates(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri
    ):
        """
        Given: emission: {mode: flat} with no aspects/concerns/portStyles
        When: check-jsonschema validates the document
        Then: exit 0

        False-positive guard for the "valid" direction: proves the schema
        genuinely recognizes `emission` as a defined property (aspects/
        concerns/portStyles are optional per D3), rather than the above test
        passing only because every optional sub-block happens to be present.
        """
        doc = _with_emission(base_styles_doc, {"mode": "flat"})
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode == 0, (
            f"Expected a minimal {{mode: flat}} emission block to validate.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    @pytest.mark.parametrize("mode_value", ["flat", "decoupled"])
    def test_both_enum_mode_values_validate(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, mode_value
    ):
        """Both enum values (`flat`, `decoupled`) must be individually accepted."""
        doc = _with_emission(base_styles_doc, {"mode": mode_value})
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode == 0, (
            f"Expected mode: {mode_value} to validate.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_missing_emission_block_entirely_still_validates(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri
    ):
        """
        Regression guard: `emission` is optional (D3 doesn't require it), so a
        componentGraphType with no `emission` key at all must keep validating.

        Constructs the "missing" case synthetically by popping the key from a
        deep copy, rather than relying on the live mermaid-styles.yaml
        happening to lack `emission` -- task 3.3 populates the real file's
        emission block (§C registry), so asserting on the live doc's
        pre-change absence would break once that content lands even though
        the schema property under test (optionality) is unrelated to the live
        file's current state.
        """
        doc = copy.deepcopy(base_styles_doc)
        doc["graphTypes"]["component"].pop("emission", None)
        assert "emission" not in doc["graphTypes"]["component"]
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode == 0, (
            f"A componentGraphType with no emission key must keep validating.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    # ------------------------------------------------------------------
    # Rejection cases
    #
    # RED/GREEN disposition note: most tests below are ALREADY GREEN today,
    # coincidentally -- ANY `emission` key is currently rejected outright at
    # the componentGraphType level (additionalProperties: false, no
    # `emission` property declared yet), so a bare "this document must be
    # rejected" assertion is trivially satisfied regardless of what's wrong
    # inside the block. This is expected and reported as such (task
    # instructions: "where something already coincidentally works, GREEN --
    # report which"); each test's own docstring says which is which. Two
    # tests are engineered to stay genuinely RED despite this coincidence, by
    # additionally requiring the SPECIFIC offending key name to appear in the
    # error output (a signal only the fully-implemented, deeper schema can
    # produce): test_unknown_key_at_emission_top_level_is_rejected and
    # test_force_split_key_on_a_concerns_entry_is_rejected.
    # ------------------------------------------------------------------

    def test_unknown_key_at_emission_top_level_is_rejected(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri
    ):
        """
        Given: emission block with an extra, undeclared top-level key
        When: check-jsonschema validates
        Then: rejected, and the offending key name appears in the error output

        The name-appears assertion is the false-positive guard: today ANY
        `emission` key is rejected (componentGraphType itself is
        additionalProperties: false and doesn't know about `emission` yet),
        so a bare `returncode != 0` check would pass today for the WRONG
        reason (parent-level rejection, never descending into this block's
        own shape) and stay trivially green forever. Asserting the specific
        nested key name appears forces this test to only pass once the
        schema recognizes `emission` well enough to descend into it and
        reject on ITS OWN additionalProperties: false.
        """
        block = _synthetic_emission_block()
        block["notARealEmissionKey"] = True
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        combined = _combined_output_excluding_path(result, yaml_path)
        assert result.returncode != 0, "An unknown top-level emission key must be rejected"
        assert "notARealEmissionKey" in combined, (
            f"Expected the specific offending key to be named in the error output "
            f"(false-positive guard against the parent-level additionalProperties "
            f"rejection that fires today for any reason); got:\n{combined}"
        )

    def test_force_split_key_on_a_concerns_entry_is_rejected(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri
    ):
        """
        Given: a concerns[] entry carrying a `forceSplit` key (the prototype's
               deleted per-entry override, plan R1/R3/P2)
        When: check-jsonschema validates
        Then: rejected, and 'forceSplit' appears in the error output

        Pins plan decision R1/P2 explicitly: `forceSplit`/override semantics
        were deleted from ADR-036 D3 -- arm-splitting is mechanical (D6), so
        `emissionConcern` must be additionalProperties: false with no
        override-shaped key at all, not merely undocumented. Named
        `forceSplit` (not a generic 'override') both because that is the
        actual deleted key name the plan cites, and to avoid a false-positive
        substring match against pytest's own tmp_path-from-test-name naming
        (see `_combined_output_excluding_path`'s docstring for the class of
        bug this sidesteps).
        """
        block = _synthetic_emission_block()
        block["concerns"][0]["forceSplit"] = True
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        combined = _combined_output_excluding_path(result, yaml_path)
        assert result.returncode != 0, "A concerns[] entry with a 'forceSplit' key must be rejected"
        assert "forceSplit" in combined, f"Expected 'forceSplit' to be named in the error output; got:\n{combined}"

    def test_missing_mode_is_rejected(self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri):
        """
        Given: emission block with aspects/concerns but no `mode` key
        When: check-jsonschema validates
        Then: rejected

        `mode` is the D3 rollback lever and must be required, not optional
        with a schema-level default -- the flat/decoupled distinction must be
        explicit in the committed YAML, never implicit.
        """
        block = _synthetic_emission_block()
        del block["mode"]
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode != 0, (
            f"An emission block with no 'mode' key must be rejected.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_unknown_mode_enum_value_is_rejected(self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri):
        """`mode` must be a closed enum (flat | decoupled) -- an arbitrary string is rejected."""
        doc = _with_emission(base_styles_doc, {"mode": "bogus"})
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode != 0, (
            f"An unrecognized mode value must be rejected.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_aspect_entry_missing_min_cross_in_degree_is_rejected(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri
    ):
        """`emissionAspect` requires both `id` and `minCrossInDegree` (plan §F)."""
        block = _synthetic_emission_block()
        block["aspects"] = [{"id": "componentSynthSink"}]  # missing minCrossInDegree
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode != 0, (
            f"An aspects[] entry missing minCrossInDegree must be rejected.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_aspect_entry_rejects_an_unknown_key(self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri):
        """
        Given: an aspects[] entry carrying an extra, undeclared key
        When: check-jsonschema validates
        Then: rejected, and the offending key name appears in the error output

        Coverage-gap G6 (adversarial review): the nested
        additionalProperties: false rejection is already covered for
        `emissionConcern` (test_force_split_key_on_a_concerns_entry_is_rejected)
        and `portStyles` (test_portstyles_rejects_an_unknown_key), but not
        `emissionAspect` -- this closes that gap. Same false-positive-guard
        pattern as the other two: asserting the specific key name in the
        output (not just a bare rejection) forces this test to only pass
        once the schema descends into `emissionAspect` and rejects on ITS
        OWN additionalProperties: false, rather than coincidentally failing
        at a parent level for an unrelated reason.
        """
        block = _synthetic_emission_block()
        block["aspects"][0]["bogusAspectKey"] = True
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        combined = _combined_output_excluding_path(result, yaml_path)
        assert result.returncode != 0, "An aspects[] entry with an unknown key must be rejected"
        assert "bogusAspectKey" in combined, f"Expected the offending key named in output; got:\n{combined}"

    def test_concern_entry_missing_edges_is_rejected(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri
    ):
        """`emissionConcern` requires both `label` and `edges` (plan §F)."""
        block = _synthetic_emission_block()
        block["concerns"] = [{"label": "orphan concern"}]  # missing edges
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode != 0, (
            f"A concerns[] entry missing edges must be rejected.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    @pytest.mark.parametrize(
        "bad_edge",
        [
            ["componentSynthSrc"],  # 1 element -- too few
            ["componentSynthSrc", "componentSynthMid", "componentSynthTgt"],  # 3 elements -- too many
        ],
        ids=["one-element-tuple", "three-element-tuple"],
    )
    def test_concern_edge_with_wrong_tuple_arity_is_rejected(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, bad_edge
    ):
        """
        Given: a concerns[].edges entry that is not exactly a 2-element [src, tgt] pair
        When: check-jsonschema validates
        Then: rejected

        This is the SCHEMA-level counterpart to `get_emission_config()`'s
        existing accessor-level arity guard (`test_decouple_emitter.py::
        TestGetEmissionConfigAccessor::test_malformed_concern_entry_bad_edge_tuple_arity_defaults_to_flat`)
        -- a different layer: check-jsonschema must reject this at the
        YAML-validation stage (pre-commit / CI), before the accessor's
        degrade-to-flat fallback is ever reached. Both guards are needed;
        neither substitutes for the other (one is CLI/CI-time, the other is
        runtime-defensive).
        """
        block = _synthetic_emission_block()
        block["concerns"] = [{"label": "bad arity", "edges": [bad_edge]}]
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode != 0, (
            f"A concerns[].edges entry with {len(bad_edge)} elements must be rejected.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_portstyles_accepts_the_three_documented_keys(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri
    ):
        """`portStyles` -- exactly `port`, `pepport`, `pepWrapOutline` (plan §C) -- validates."""
        doc = _with_emission(
            base_styles_doc,
            {
                "mode": "flat",
                "portStyles": {
                    "port": "fill:#fff",
                    "pepport": "fill:#eef",
                    "pepWrapOutline": "fill:none,stroke:#339",
                },
            },
        )
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode == 0, (
            f"Expected the 3-key portStyles block to validate.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_portstyles_rejects_an_unknown_key(self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri):
        """`portStyles` is a closed object -- an unrecognized style key is rejected."""
        doc = _with_emission(
            base_styles_doc,
            {"mode": "flat", "portStyles": {"port": "fill:#fff", "bogusStyleKey": "fill:#000"}},
        )
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        combined = _combined_output_excluding_path(result, yaml_path)
        assert result.returncode != 0, "An unrecognized portStyles key must be rejected"
        assert "bogusStyleKey" in combined, f"Expected the offending key named in output; got:\n{combined}"


# ============================================================================
# 2. Real config validates -- integration test against the live corpus
# ============================================================================


class TestRealConfigValidates:
    """
    Integration test against the LIVE, committed `risk-map/yaml/mermaid-styles.yaml`.

    RED until Phase 3 task 3.3 ('swe') populates `graphTypes.component.emission`
    with the real §C registry (mode: flat, 1 aspect, 12 concerns, portStyles) --
    expected per task instructions, not a bug in this test. Once populated, this
    proves the actual committed file -- not a synthetic fixture -- round-trips
    through check-jsonschema exactly as CI (`check-jsonschema` pre-commit hook /
    `scripts/hooks/precommit/validate_all_schemas.py`) will run it.
    """

    def test_live_mermaid_styles_yaml_has_a_populated_emission_block(self, risk_map_yaml_dir: Path):
        """
        Given: the real, committed mermaid-styles.yaml
        When: graphTypes.component.emission is inspected
        Then: it exists and carries the §C registry's headline markers --
              mode: flat, the componentSecureLogging aspect at
              minCrossInDegree: 10 (D4's stated initial value), and a
              non-empty concerns list

        RED today (no `emission` key exists in the live file at all). This is
        the "populated by task 3.3" precondition the CI round-trip below
        depends on -- separated into its own assertion so a failure here
        reads as "content not yet landed" rather than being conflated with a
        schema-validation failure.
        """
        with open(risk_map_yaml_dir / "mermaid-styles.yaml", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)

        component_cfg = doc.get("graphTypes", {}).get("component", {})
        emission = component_cfg.get("emission")
        assert emission is not None, (
            "graphTypes.component.emission is missing from the live mermaid-styles.yaml "
            "-- expected until Phase 3 task 3.3 lands the real §C registry"
        )
        assert emission.get("mode") == "flat", (
            f"PR 1 lands with mode: flat (plan §C, P6: the direction/mode flip is PR 2's "
            f"job); got: {emission.get('mode')!r}"
        )

        aspects = emission.get("aspects", [])
        aspect_ids = {a.get("id"): a.get("minCrossInDegree") for a in aspects}
        assert aspect_ids.get("componentSecureLogging") == 10, (
            f"Expected the componentSecureLogging aspect at minCrossInDegree 10 (D4's "
            f"stated initial value); got aspects: {aspects!r}"
        )

        assert emission.get("concerns"), "Expected a non-empty concerns registry (§C: 12 entries)"

    def test_live_mermaid_styles_yaml_validates_against_the_schema(
        self, risk_map_yaml_dir: Path, risk_map_schemas_dir: Path, base_uri: str
    ):
        """
        Given: the real, committed mermaid-styles.yaml (once populated)
        When: check-jsonschema validates it against the real, committed schema
        Then: exit 0

        This is the end-to-end acceptance criterion: not a synthetic fixture,
        the actual files CI validates on every commit.
        """
        yaml_path = risk_map_yaml_dir / "mermaid-styles.yaml"
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode == 0, (
            f"The live mermaid-styles.yaml must validate against the live schema.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

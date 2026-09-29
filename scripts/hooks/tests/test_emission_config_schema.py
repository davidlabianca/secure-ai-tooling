#!/usr/bin/env python3
"""
Schema round-trip tests for the `emission` block (ADR-036 D3).

`risk-map/schemas/mermaid-styles.schema.json` defines `emission`:
`definitions/componentGraphType.properties.emission` references
`definitions/emission`, which the schema declares as follows:

    - `definitions/componentGraphType.properties.emission` (optional)
    - `definitions/emission` (`required: [mode]`, `additionalProperties: false`)
    - `definitions/emissionAspect` (`required: [id, minCrossInDegree]`)
    - `definitions/emissionConcern` (`required: [label, edges]`,
      `additionalProperties: false` -- no override key; arm-splitting is a
      mechanical function of distinct-target count (D6), not a per-entry
      judgment (D5))
    - `definitions/portStyles` (`port`, `pepport`, `pepWrapOutline`)
    - `mode: {"enum": ["flat", "decoupled"]}`

This suite pins that schema as a regression guard.

`definitions/portStyles` also carries a 4th, optional key, `aspectStyle`
(ADR-036 D3/D4) -- the dashed-border classDef a lifted aspect node's
`:::aspectStyle` class references. `TestPortStylesAspectStyleKey` below pins
that `portStyles` stays `additionalProperties: false`: a `portStyles` block
naming a still-unrecognized 5th key alongside a fully-valid 4-key block must
stay rejected (closed-object regression guard). Only `definitions/portStyles`
carries this key -- no other emission definition, no `emission.aspects`/
`emission.concerns` change (D4's live-count second label line is computed at
emission time from `LiftedAspect.edges`, not declared in config).

Six test classes:

    1. TestSchemaRoundTrip -- generic shape tests, using a SYNTHETIC emission
       block (component ids like `componentSynthSrc1` -- not real corpus ids).
       This class only proves the schema accepts/rejects the right SHAPES; it
       says nothing about whether the real `mermaid-styles.yaml` is populated.
       Deliberately separated from #3 (a different testing layer).
    2. TestPortStylesAspectStyleKey -- `portStyles`'s 4th, optional key,
       `aspectStyle` (ADR-036 D3/D4), stays within a closed 4-key object.
    2b. TestDecoupledModeRequiresRenderedPortStyles -- `mode: decoupled`
       requires the `portStyles` keys the decoupled renderer's S6 self-check
       demands (`port`, `pepport`, `pepWrapOutline`); `mode: flat` does not.
    3. TestRealConfigValidates -- integration test against the live,
       committed `risk-map/yaml/mermaid-styles.yaml`, which carries a
       populated `emission` block (mode: decoupled, plus the aspects/concerns
       registry). This test is a regression pin proving the committed file
       keeps round-tripping through check-jsonschema.
    4. TestD9ConsultConcernsArePinnedToTheShippedRegistry -- the D9 consult-class
       concern labels declared in code stay assigned to edges in the shipped
       registry.
    5. TestClosedConcernLabelVocabulary -- ADR-036 D12: `emission.concerns[].label`
       is a closed enum; every shipped label and the D9 consult set are members.

Convention: subprocess `check-jsonschema` invocation, matching
`test_persona_schema_updates.py` / `test_consumer_yaml_check_jsonschema_integration.py`
(not the in-process `jsonschema` library) -- this repo's established pattern for
schema round-trip tests, and the layer that must reject a malformed `emission`
block at the YAML-validation stage, before the accessor (`get_emission_config()`)
ever runs.
"""

import copy
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))
# tests/ itself, so sibling test modules import directly (matches
# test_frameworks_schema_v027.py's `from test_framework_mapping_patterns import ...`
# convention -- no `__init__.py` under tests/, so pytest's rootdir insertion
# already puts this directory on sys.path when tests run, but the explicit
# insert keeps this module importable standalone too).
sys.path.insert(0, str(Path(__file__).parent))

from riskmap_validator.graphing.graph_utils import _parse_emission_config  # noqa: E402

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


# Synthetic emission block close to the live registry's SHAPE (1 aspect + 12
# concerns; 3 of the shipped 4 portStyles keys, `aspectStyle` omitted) but NOT
# the real corpus's component ids -- see module
# docstring. Deliberately kept structurally faithful (entry count, nesting)
# without asserting this is the live registry (that is TestRealConfigValidates'
# job, against the real file).
#
# Labels are read from the real, committed mermaid-styles.yaml rather than
# hand-copied: ADR-036 D12 closes `emissionConcern.label` to an enum of the
# shipped labels, so a hand-copied list would drift the moment a label is
# renamed and every test using the full synthetic shape would fail against a
# closed enum for an unrelated reason. Reading the labels from the file keeps
# this fixture immune to that class of drift. Component ids stay synthetic;
# only the label vocabulary is tied to the shipped file.
#
# Read lazily via a fixture (not a module-level constant computed at import
# time): a broken or absent live emission block must fail only the tests
# that use this fixture, not collection of the whole module.


@pytest.fixture
def synthetic_concern_labels(repo_root: Path) -> list[str]:
    """Return the shipped `emission.concerns[].label` values from the real, committed mermaid-styles.yaml."""
    styles_path = repo_root / "risk-map" / "yaml" / "mermaid-styles.yaml"
    with open(styles_path, encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    concerns = doc["graphTypes"]["component"]["emission"]["concerns"]
    return sorted({c["label"] for c in concerns})


def _synthetic_emission_block(labels: list[str], mode: str = "flat") -> dict[str, Any]:
    return {
        "mode": mode,
        "aspects": [{"id": "componentSynthSink", "minCrossInDegree": 10}],
        "concerns": [
            {
                "label": label,
                "edges": [["componentSynthSrc", "componentSynthTgt"]],
            }
            for label in labels
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
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, mode_value, synthetic_concern_labels
    ):
        """
        Given: graphTypes.component.emission populated with a block matching
               the live registry's shape (1 aspect, 12 concerns; 3 of the
               4 portStyles keys), under EACH enum mode value in turn
        When: check-jsonschema validates the document
        Then: exit 0

        Pins that `componentGraphType` accepts an `emission` property whose
        block validates regardless of its internal shape.

        Exercising only mode: flat would leave undetected a
        schema that special-cases "flat" and rejects an otherwise-identical
        registry-shaped block under mode: decoupled. Parametrizing over both
        enum values closes that gap -- the full registry shape must validate
        regardless of which mode it is declared under.
        """
        doc = _with_emission(base_styles_doc, _synthetic_emission_block(synthetic_concern_labels, mode=mode_value))
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode == 0, (
            f"Expected a registry-shaped emission block (mode: {mode_value}) to validate.\n"
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
        """
        Both enum values (`flat`, `decoupled`) must be individually accepted.

        The block carries the three `portStyles` keys that `mode: decoupled`
        requires, so the only variable is the `mode` value itself; flat accepts
        the same block because its port styles are optional.
        """
        emission = {
            "mode": mode_value,
            "portStyles": {
                "port": "fill:#fff5f5,stroke:#c0392b,stroke-width:1.5px,stroke-dasharray:4 3",
                "pepport": "fill:#eef,stroke:#339,stroke-width:1.5px",
                "pepWrapOutline": "fill:none,stroke:#339,stroke-width:2px",
            },
        }
        doc = _with_emission(base_styles_doc, emission)
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
        deep copy, rather than relying on the live mermaid-styles.yaml: the
        real file carries a populated `emission` block, and the schema
        property under test (optionality) is unrelated to the live file's
        current state.
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
    # Rejection-strength note: most tests below pass regardless of what's
    # wrong inside the block -- ANY `emission` key is rejected outright at
    # the componentGraphType level (additionalProperties: false), so a bare
    # "this document must be rejected" assertion is satisfied trivially;
    # each test's own docstring says which. Six tests in this file additionally
    # require the SPECIFIC offending key or label name to appear in the error
    # output, so they exercise the nested schema's own rejection rather than the
    # blanket top-level one: test_unknown_key_at_emission_top_level_is_rejected,
    # test_force_split_key_on_a_concerns_entry_is_rejected, and four more below
    # and in TestPortStylesAspectStyleKey/TestClosedConcernLabelVocabulary.
    # ------------------------------------------------------------------

    def test_unknown_key_at_emission_top_level_is_rejected(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, synthetic_concern_labels
    ):
        """
        Given: emission block with an extra, undeclared top-level key
        When: check-jsonschema validates
        Then: rejected, and the offending key name appears in the error output

        The name-appears assertion is a false-positive guard against a
        schema regression: if `emission` were dropped from
        `componentGraphType`'s own `additionalProperties: false` property
        list, a bare `returncode != 0` check would still pass for a document
        carrying an `emission` block, but for the WRONG reason (the parent
        rejecting the unrecognized top-level `emission` key itself, never
        descending into the block's own shape). Asserting the specific
        nested key name appears in the error output forces the rejection to
        come from `emission`'s own schema recognizing the block and
        rejecting on ITS OWN `additionalProperties: false`.
        """
        block = _synthetic_emission_block(synthetic_concern_labels)
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
            f"rejection that would fire if emission were dropped); got:\n{combined}"
        )

    def test_force_split_key_on_a_concerns_entry_is_rejected(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, synthetic_concern_labels
    ):
        """
        Given: a concerns[] entry carrying a `forceSplit` key (a per-entry
               override ADR-036 D5 rejects)
        When: check-jsonschema validates
        Then: rejected, and 'forceSplit' appears in the error output

        Pins ADR-036 D5/D6 explicitly: `forceSplit`/override semantics have
        no place in the schema -- arm-splitting is mechanical (D6), so
        `emissionConcern` must be additionalProperties: false with no
        override-shaped key at all, not merely undocumented. Named
        `forceSplit` (not a generic 'override') to exercise a concrete key
        name and to avoid a false-positive substring match against pytest's
        own tmp_path-from-test-name naming (see
        `_combined_output_excluding_path`'s docstring for the class of bug
        this sidesteps).
        """
        block = _synthetic_emission_block(synthetic_concern_labels)
        block["concerns"][0]["forceSplit"] = True
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        combined = _combined_output_excluding_path(result, yaml_path)
        assert result.returncode != 0, "A concerns[] entry with a 'forceSplit' key must be rejected"
        assert "forceSplit" in combined, f"Expected 'forceSplit' to be named in the error output; got:\n{combined}"

    def test_missing_mode_is_rejected(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, synthetic_concern_labels
    ):
        """
        Given: emission block with aspects/concerns but no `mode` key
        When: check-jsonschema validates
        Then: rejected

        `mode` is the D3 rollback lever and must be required, not optional
        with a schema-level default -- the flat/decoupled distinction must be
        explicit in the committed YAML, never implicit.
        """
        block = _synthetic_emission_block(synthetic_concern_labels)
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
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, synthetic_concern_labels
    ):
        """`emissionAspect` requires both `id` and `minCrossInDegree`."""
        block = _synthetic_emission_block(synthetic_concern_labels)
        block["aspects"] = [{"id": "componentSynthSink"}]  # missing minCrossInDegree
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode != 0, (
            f"An aspects[] entry missing minCrossInDegree must be rejected.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_aspect_entry_rejects_an_unknown_key(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, synthetic_concern_labels
    ):
        """
        Given: an aspects[] entry carrying an extra, undeclared key
        When: check-jsonschema validates
        Then: rejected, and the offending key name appears in the error output

        The nested
        additionalProperties: false rejection is already covered for
        `emissionConcern` (test_force_split_key_on_a_concerns_entry_is_rejected)
        and `portStyles` (test_portstyles_rejects_an_unknown_key), but not
        `emissionAspect`; this test covers it. Same false-positive-guard
        pattern as the other two: asserting the specific key name in the
        output (not just a bare rejection) means the test passes only
        when the schema descends into `emissionAspect` and rejects on ITS
        OWN additionalProperties: false, rather than coincidentally failing
        at a parent level for an unrelated reason.
        """
        block = _synthetic_emission_block(synthetic_concern_labels)
        block["aspects"][0]["bogusAspectKey"] = True
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        combined = _combined_output_excluding_path(result, yaml_path)
        assert result.returncode != 0, "An aspects[] entry with an unknown key must be rejected"
        assert "bogusAspectKey" in combined, f"Expected the offending key named in output; got:\n{combined}"

    def test_concern_entry_missing_edges_is_rejected(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, synthetic_concern_labels
    ):
        """`emissionConcern` requires both `label` and `edges`."""
        block = _synthetic_emission_block(synthetic_concern_labels)
        block["concerns"] = [{"label": "orphan concern"}]  # missing edges
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode != 0, (
            f"A concerns[] entry missing edges must be rejected.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_concern_entry_with_empty_edges_list_is_rejected(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, synthetic_concern_labels
    ):
        """
        `emissionConcern.edges` must carry at least one edge (schema `minItems: 1`
        on the `edges` array itself, distinct from the `items` sub-schema
        `test_concern_edge_with_wrong_tuple_arity_is_rejected` below pins).

        A concern entry naming zero edges is a dead label -- it never covers any
        cross edge, cannot be D9's consult label (D9's coupling test requires the
        label to appear on at least one real edge), and is exactly the shape a
        careless "move this edge to another concern" edit leaves behind: the label
        line stays, its `edges:` list goes empty. The schema's `minItems: 1` on
        `definitions/emissionConcern.properties.edges` is what rejects it -- this
        pins the schema layer specifically, not the strict parser, which has no
        arity floor to enforce here (an empty tuple list raises nothing in
        `_validated_edge`, since there is nothing to iterate).
        """
        block = _synthetic_emission_block(synthetic_concern_labels)
        block["concerns"] = [{"label": "orphan concern", "edges": []}]
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode != 0, (
            f"A concerns[] entry with an empty edges list must be rejected.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
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
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, bad_edge, synthetic_concern_labels
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
        block = _synthetic_emission_block(synthetic_concern_labels)
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
        """`portStyles` -- exactly `port`, `pepport`, `pepWrapOutline` -- validates."""
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
# 1b. portStyles.aspectStyle (ADR-036 D3/D4)
# ============================================================================


class TestPortStylesAspectStyleKey:
    """
    `portStyles` carries a 4th optional key, `aspectStyle` (ADR-036 D3/D4): the
    dashed-border classDef style string a lifted aspect node's `:::aspectStyle`
    class references. Deliberately a SEPARATE class from `TestSchemaRoundTrip`'s
    existing 3-key `test_portstyles_accepts_the_three_documented_keys`/
    `test_portstyles_rejects_an_unknown_key` pair (and from the shared
    `_synthetic_emission_block()` helper those two tests, and others, depend on)
    rather than folding `aspectStyle` into them -- those two pin the
    3-key contract and must keep passing unchanged as their own regression guard
    that the 3 original keys still round-trip alongside `aspectStyle`,
    not replaced by it.
    """

    _FOUR_KEY_PORT_STYLES = {
        "port": "fill:#fff",
        "pepport": "fill:#eef",
        "pepWrapOutline": "fill:none,stroke:#339",
        "aspectStyle": "fill:#fdf6e3,stroke:#b58900,stroke-width:1.5px,stroke-dasharray:4 3",
    }

    def test_portstyles_accepts_all_four_keys_including_aspectstyle(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri
    ):
        """
        Given: a portStyles block with all 4 documented keys (port, pepport,
               pepWrapOutline, aspectStyle)
        When: check-jsonschema validates the document
        Then: exit 0

        Pins `aspectStyle` as a declared optional property of
        `definitions/portStyles`, alongside the other 3 keys, under its
        `additionalProperties: false` constraint.
        """
        doc = _with_emission(base_styles_doc, {"mode": "flat", "portStyles": self._FOUR_KEY_PORT_STYLES})
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode == 0, (
            f"Expected the 4-key portStyles block (including aspectStyle) to validate.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_aspectstyle_alone_without_the_other_three_keys_validates(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri
    ):
        """
        Given: a portStyles block naming ONLY aspectStyle (no port/pepport/pepWrapOutline)
        When: check-jsonschema validates the document
        Then: exit 0

        False-positive guard for the "valid" direction (mirrors
        `test_minimal_emission_block_with_only_mode_validates`'s rationale): proves
        the schema genuinely recognizes `aspectStyle` as its OWN independent
        optional property, not merely as a bystander only accepted when the other
        3 keys are also present.
        """
        doc = _with_emission(base_styles_doc, {"mode": "flat", "portStyles": {"aspectStyle": "fill:#fdf6e3"}})
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode == 0, (
            f"Expected a portStyles block naming only aspectStyle to validate.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_unknown_fifth_key_alongside_a_valid_four_key_block_is_still_rejected(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri
    ):
        """
        Given: a portStyles block carrying all 4 documented keys PLUS a 5th,
               undeclared key
        When: check-jsonschema validates the document
        Then: rejected, and the offending key name appears in the error output

        Closed-object regression guard: `aspectStyle` is a declared
        optional property of `portStyles` -- `additionalProperties: false` still
        rejects anything beyond the 4 documented keys. Named-key assertion
        mirrors `test_portstyles_rejects_an_unknown_key`'s existing false-positive
        guard: the error output names `bogusStyleKeyPastAspectStyle` as the sole
        unrecognized key.
        """
        block = {**self._FOUR_KEY_PORT_STYLES, "bogusStyleKeyPastAspectStyle": "fill:#000"}
        doc = _with_emission(base_styles_doc, {"mode": "flat", "portStyles": block})
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        combined = _combined_output_excluding_path(result, yaml_path)
        assert result.returncode != 0, (
            "A 5th unrecognized portStyles key must be rejected even alongside aspectStyle"
        )
        assert "bogusStyleKeyPastAspectStyle" in combined, (
            f"Expected the specific offending key named in the error output; got:\n{combined}"
        )


# ============================================================================
# 1c. mode: decoupled requires the port styles the renderer draws
# ============================================================================

# The `portStyles` keys the decoupled emitter's S6 self-check
# (`ComponentGraph._check_s6_style_classdef_presence`, component_graph.py)
# can demand: `port` when the plan draws channel ports (broadcasts),
# `pepport` and `pepWrapOutline` when it draws PEP wrappers. `aspectStyle` is
# deliberately NOT in this set -- S6 has no aspectStyle clause and the aspect
# node falls back to an unclassed node when it is unconfigured
# (`_decoupled_aspect_lines`). The schema pins exactly the keys S6 can
# demand, no more.
_DECOUPLED_REQUIRED_PORT_STYLE_KEYS = ("port", "pepport", "pepWrapOutline")


class TestDecoupledModeRequiresRenderedPortStyles:
    """
    A `graphTypes.component.emission` block declaring `mode: decoupled` must
    carry every `portStyles` key the decoupled renderer's S6 self-check can
    demand; check-jsonschema rejects the document and names the missing key.

    S6 requires `port` only when the plan draws channel ports and `pepport`/
    `pepWrapOutline` only when it draws PEP wrappers (`S6 violated: missing
    'classDef port' ...`). The schema cannot see the plan, so it requires all
    three under `mode: decoupled`: a schema-valid config that omits one
    otherwise passes every YAML-validation gate and then fails inside the
    graph-regeneration hook as an internal error whenever the corpus draws
    that element. The schema layer is where a config-only mistake belongs,
    with the offending key named.

    `mode: flat` is the rollback lever (ADR-036 D3/D10): it reads none of
    these styles, so the flat side keeps `portStyles` optional in full and
    in part. Both sides are pinned here so the requirement cannot spread
    beyond the decoupled mode.
    """

    @staticmethod
    def _decoupled_block_with_port_styles(labels: list[str], port_styles: dict[str, str] | None) -> dict[str, Any]:
        block = _synthetic_emission_block(labels, mode="decoupled")
        if port_styles is None:
            del block["portStyles"]
        else:
            block["portStyles"] = port_styles
        return block

    def test_decoupled_without_a_portstyles_block_is_rejected_naming_portstyles(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, synthetic_concern_labels
    ):
        """
        Given: a registry-shaped emission block with mode: decoupled and no
               portStyles key at all
        When: check-jsonschema validates the document
        Then: rejected, and 'portStyles' appears in the error output

        This is the config shape the graph-regeneration hook otherwise
        turns into `S6 violated: missing 'classDef port'` after every
        schema and validator gate has already passed.
        """
        block = self._decoupled_block_with_port_styles(synthetic_concern_labels, None)
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        combined = _combined_output_excluding_path(result, yaml_path)
        assert result.returncode != 0, (
            f"mode: decoupled without portStyles must be rejected by check-jsonschema.\n{combined}"
        )
        # check-jsonschema quotes a missing property name ('portStyles' is a
        # required property); the quoted form cannot be satisfied by the
        # `$.graphTypes.component.emission.portStyles` path prefix alone.
        assert "'portStyles'" in combined, f"Expected 'portStyles' named in the error output; got:\n{combined}"

    @pytest.mark.parametrize("missing_key", _DECOUPLED_REQUIRED_PORT_STYLE_KEYS)
    def test_decoupled_missing_one_required_port_style_key_is_rejected_naming_it(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, synthetic_concern_labels, missing_key
    ):
        """
        Given: mode: decoupled with a portStyles block carrying every
               S6-required key except one (`port`, `pepport`, or
               `pepWrapOutline` in turn)
        When: check-jsonschema validates the document
        Then: rejected, and the missing key's name appears in the error output

        Each key maps to an S6 raise site in
        `ComponentGraph._check_s6_style_classdef_presence`: `port` for drawn
        channel ports, `pepport` and `pepWrapOutline` for PEP wrappers. The
        named-key assertion proves the rejection comes from `portStyles`'s
        own required list rather than from an unrelated parent-level error.
        """
        full = _synthetic_emission_block(synthetic_concern_labels)["portStyles"]
        partial = {key: value for key, value in full.items() if key != missing_key}
        assert missing_key not in partial
        block = self._decoupled_block_with_port_styles(synthetic_concern_labels, partial)
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        combined = _combined_output_excluding_path(result, yaml_path)
        assert result.returncode != 0, (
            f"mode: decoupled with portStyles missing '{missing_key}' must be rejected.\n{combined}"
        )
        # check-jsonschema quotes the missing property ('port' is a required
        # property). The quoted form is the falsifiable one: a bare `port` is a
        # substring of `portStyles` and `pepport`, and only the absent key may
        # be quoted -- the other two are present and must not be reported.
        assert f"'{missing_key}'" in combined, (
            f"Expected '{missing_key}' named in the error output; got:\n{combined}"
        )
        for other in _DECOUPLED_REQUIRED_PORT_STYLE_KEYS:
            if other != missing_key:
                assert f"'{other}'" not in combined, (
                    f"Only the missing key may be reported; '{other}' is present but named:\n{combined}"
                )

    def test_decoupled_with_exactly_the_three_required_keys_validates(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, synthetic_concern_labels
    ):
        """
        Given: mode: decoupled with portStyles carrying exactly `port`,
               `pepport`, `pepWrapOutline` (no `aspectStyle`)
        When: check-jsonschema validates the document
        Then: exit 0

        Upper bound on the requirement: `aspectStyle` is optional under
        decoupled mode because S6 carries no aspectStyle clause and the
        lifted aspect node renders unclassed without it. A schema that
        required all four keys would over-constrain the decoupled config.
        """
        full = _synthetic_emission_block(synthetic_concern_labels)["portStyles"]
        assert set(full) == set(_DECOUPLED_REQUIRED_PORT_STYLE_KEYS)
        block = self._decoupled_block_with_port_styles(synthetic_concern_labels, full)
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode == 0, (
            f"mode: decoupled with the three S6-required portStyles keys must validate.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    @pytest.mark.parametrize("empty_key", _DECOUPLED_REQUIRED_PORT_STYLE_KEYS)
    def test_decoupled_with_an_empty_required_port_style_is_rejected_naming_it(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, synthetic_concern_labels, empty_key
    ):
        """
        Given: mode: decoupled with all three required portStyles keys
               present, one of them set to the empty string
        When: check-jsonschema validates the document
        Then: rejected, and the empty key's name appears in the error output

        The renderer emits no classDef/style line for an empty string and S6
        then fails exactly as for an absent key, so under decoupled mode the
        required keys are non-empty strings, not merely present.
        """
        full = dict(_synthetic_emission_block(synthetic_concern_labels)["portStyles"])
        full[empty_key] = ""
        block = self._decoupled_block_with_port_styles(synthetic_concern_labels, full)
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        combined = _combined_output_excluding_path(result, yaml_path)
        assert result.returncode != 0, (
            f"mode: decoupled with portStyles.{empty_key} == '' must be rejected.\n{combined}"
        )
        # A value-level rejection is reported at the value's own path
        # ($.graphTypes.component.emission.portStyles.port: '' should be
        # non-empty), so the dotted `portStyles.<key>` form is the falsifiable
        # one here; `portStyles.port` is not a substring of `portStyles.pepport`,
        # and the two configured keys must not be reported.
        assert f"portStyles.{empty_key}" in combined, (
            f"Expected 'portStyles.{empty_key}' named in the error output; got:\n{combined}"
        )
        for other in _DECOUPLED_REQUIRED_PORT_STYLE_KEYS:
            if other != empty_key:
                assert f"portStyles.{other}" not in combined, (
                    f"Only the empty key may be reported; 'portStyles.{other}' is populated but named:\n{combined}"
                )

    @pytest.mark.parametrize(
        "flat_port_styles",
        [
            None,
            {"pepport": "fill:#eef"},
            {"port": "", "pepport": "", "pepWrapOutline": ""},
        ],
        ids=["no-portstyles-block", "portstyles-without-port-or-pepWrapOutline", "all-required-keys-empty"],
    )
    def test_flat_mode_keeps_every_port_style_key_optional(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri, synthetic_concern_labels, flat_port_styles
    ):
        """
        Given: a registry-shaped emission block with mode: flat and either no
               portStyles block, a partial one missing S6-required keys, or
               one whose required keys are all empty strings
        When: check-jsonschema validates the document
        Then: exit 0

        The flat emitter reads no port style, so both the presence and the
        non-empty requirement are scoped to `mode: decoupled` alone; an empty
        string under flat is inert. A schema that made the keys required or
        non-empty whenever `portStyles` is present, or regardless of mode,
        would break the rollback lever's minimal `{mode: flat}` form.
        """
        block = _synthetic_emission_block(synthetic_concern_labels, mode="flat")
        if flat_port_styles is None:
            del block["portStyles"]
        else:
            block["portStyles"] = flat_port_styles
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        assert result.returncode == 0, (
            f"mode: flat must keep portStyles optional ({flat_port_styles!r}).\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ============================================================================
# 2. Real config validates -- integration test against the live corpus
# ============================================================================


class TestRealConfigValidates:
    """
    Integration test against the LIVE, committed `risk-map/yaml/mermaid-styles.yaml`.

    Proves the actual committed file -- not a synthetic fixture -- round-trips
    through check-jsonschema exactly as CI (`check-jsonschema` pre-commit hook /
    `scripts/hooks/precommit/validate_all_schemas.py`) runs it.
    """

    def test_live_mermaid_styles_yaml_has_a_populated_emission_block(self, risk_map_yaml_dir: Path):
        """
        Given: the real, committed mermaid-styles.yaml
        When: graphTypes.component.emission is inspected
        Then: it exists and carries the shipped registry's headline markers --
              mode: flat, the componentAuditRecordRepository aspect at
              minCrossInDegree: 10, and a non-empty concerns list

        This is the "populated" precondition the CI round-trip below depends
        on -- separated into its own assertion so a failure here reads as
        "content not landed" rather than being conflated with a
        schema-validation failure.
        """
        with open(risk_map_yaml_dir / "mermaid-styles.yaml", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)

        component_cfg = doc.get("graphTypes", {}).get("component", {})
        emission = component_cfg.get("emission")
        assert emission is not None, "graphTypes.component.emission is missing from the live mermaid-styles.yaml"
        assert emission.get("mode") == "flat", (
            f"the shipped config runs at mode flat until the flip; got: {emission.get('mode')!r}"
        )

        aspects = emission.get("aspects", [])
        aspect_ids = {a.get("id"): a.get("minCrossInDegree") for a in aspects}
        assert aspect_ids.get("componentAuditRecordRepository") == 10, (
            f"Expected the componentAuditRecordRepository aspect at minCrossInDegree 10 "
            f"(D4's value, re-derived against the live corpus); got aspects: {aspects!r}"
        )

        assert emission.get("concerns"), "Expected a non-empty concerns registry (12 entries)"

    def test_live_mermaid_styles_yaml_validates_against_the_schema(
        self, risk_map_yaml_dir: Path, risk_map_schemas_dir: Path, base_uri: str
    ):
        """
        Given: the real, committed mermaid-styles.yaml
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


# ============================================================================
# 3. ADR-036 D9 -- the consult-set / shipped-registry coupling pin
# ============================================================================


class TestD9ConsultConcernsArePinnedToTheShippedRegistry:
    """
    D9 keys consult-class landing on concern *labels* declared in code
    (`decouple.CONSULT_CONCERN_LABELS`) but assigned to edges in
    `mermaid-styles.yaml`'s `emission.concerns`. A rename on either side silently
    reverts every consult arm to a `_in` landing.

    D9 places this check here rather than in `check_emission_drift()` on purpose:
    at transform time the emitter cannot tell a config that legitimately declares
    no consult-class concern (every reduced or synthetic config in the suite) from
    one whose consult concern was renamed, so a runtime warning would fire on
    inputs that are not drifting. The invariant only holds against the one registry
    that is supposed to carry the label, which is what this test reads.
    """

    def test_every_consult_label_is_declared_in_the_live_concerns_registry(self, risk_map_yaml_dir: Path):
        from riskmap_validator.graphing.decouple import CONSULT_CONCERN_LABELS

        with open(risk_map_yaml_dir / "mermaid-styles.yaml", encoding="utf-8") as fh:
            doc = yaml.safe_load(fh)

        concerns = doc["graphTypes"]["component"]["emission"]["concerns"]
        declared_labels = {entry.get("label") for entry in concerns}

        missing = sorted(set(CONSULT_CONCERN_LABELS) - declared_labels)
        assert not missing, (
            f"ADR-036 D9: consult-class label(s) {missing} are declared in "
            f"decouple.CONSULT_CONCERN_LABELS but no longer appear in the live "
            f"emission.concerns registry. Either the config label was renamed (restore "
            f"it, or update the emitter set to match) -- otherwise every consult arm "
            f"silently reverts to landing on a PEP wrapper's `_in` port. "
            f"Declared labels: {sorted(declared_labels)}"
        )

    def test_the_consult_set_is_exactly_two_labels(self):
        """
        ADR-036 D9: "The set is two labels, not one" -- the corpus names a second
        consult-class concern (the tool registry's enumerated-endpoint consult onto
        the agent network PEP, ADR-030 D14), and D9 fixes the count at two rather
        than leaving it open-ended. Pins the count at exactly two: a set that shrank
        back to one label would silently revert that registry consult to a `_in`
        landing.

        The exact wording matches ADR-036 D9's shipped set: `identity & authz` and
        `endpoint enumeration`. A third label still trips D9's promote-to-config
        trip-wire, which the equality bound below also catches.
        """
        from riskmap_validator.graphing.decouple import CONSULT_CONCERN_LABELS

        assert CONSULT_CONCERN_LABELS, "the consult-class set must not be empty (D9 would be dead code)"
        assert CONSULT_CONCERN_LABELS == {"identity & authz", "endpoint enumeration"}, (
            f"ADR-036 D9 fixes the consult-class set at exactly two labels; got {sorted(CONSULT_CONCERN_LABELS)!r}"
        )


# ============================================================================
# 4. ADR-036 D12 -- closed concern-label vocabulary
# ============================================================================
#
# D12: `mermaid-styles.schema.json` declares the allowed concern labels as an
# `enum` on the concern entry's `label`, so a misspelled or unknown label
# fails schema validation at the YAML-validation stage rather than silently
# parsing into an untyped string that renders wrong with no diagnostic.
# Introducing a NEW label is a structural decision and a `main` change to the
# schema; assigning an edge to an EXISTING label is content, reviewed on the
# `develop` PR -- the schema carries no reviewed copy of the
# `emission.concerns` block.


def _concern_label_enum(schema_path: Path) -> list[str] | None:
    """
    Read `definitions.emissionConcern.properties.label.enum` from the schema
    file, or None if no `enum` key is declared there.
    """
    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)
    label_property = schema["definitions"]["emissionConcern"]["properties"]["label"]
    return label_property.get("enum")


class TestClosedConcernLabelVocabulary:
    """
    ADR-036 D12: `emission.concerns[].label` is a closed vocabulary, not an
    open string. A label outside the enum must fail check-jsonschema; every
    shipped label and the D9 consult-class set must be members.
    """

    def test_schema_rejects_a_concern_label_outside_the_closed_vocabulary(
        self, tmp_path, base_styles_doc, risk_map_schemas_dir, base_uri
    ):
        """
        Given: a concern entry whose label is not among the allowed set (a
               misspelling/unknown label, not one of the 12 shipped ones)
        When: check-jsonschema validates the document
        Then: rejected, and the offending label appears in the error output

        `emissionConcern.properties.label` declares a closed `enum`
        (ADR-036 D12, schema line 336): a misspelled or unknown label fails at
        the schema-validation stage.
        """
        block = {
            "mode": "flat",
            "concerns": [
                {
                    "label": "definitely-not-a-real-concern-label",
                    "edges": [["componentSynthSrc", "componentSynthTgt"]],
                }
            ],
        }
        doc = _with_emission(base_styles_doc, block)
        yaml_path = _write_doc(tmp_path, doc)
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"

        result = _run_check_jsonschema(schema_path, yaml_path, base_uri)
        combined = _combined_output_excluding_path(result, yaml_path)
        assert result.returncode != 0, (
            "A concern label outside the closed vocabulary must be rejected by check-jsonschema (ADR-036 D12)."
        )
        assert "definitely-not-a-real-concern-label" in combined, (
            f"Expected the offending label named in the error output; got:\n{combined}"
        )

    def test_schema_declares_a_non_empty_label_enum(self, risk_map_schemas_dir: Path):
        """
        Given: the real, committed mermaid-styles.schema.json
        When: definitions.emissionConcern.properties.label is inspected
        Then: it declares a non-empty `enum`

        Precondition for the two tests below: without an enum at all, "every
        shipped label is a member" and "the consult set is a subset" are both
        vacuously true for the wrong reason (nothing to be a member OF).
        """
        schema_path = risk_map_schemas_dir / "mermaid-styles.schema.json"
        enum = _concern_label_enum(schema_path)
        assert enum, (
            "Expected definitions.emissionConcern.properties.label to declare a "
            "non-empty enum (ADR-036 D12: concern labels are a closed vocabulary); "
            f"got: {enum!r}"
        )

    def test_every_shipped_concern_label_is_within_the_schema_enum(
        self, risk_map_yaml_dir: Path, risk_map_schemas_dir: Path
    ):
        """
        Given: the real, committed mermaid-styles.yaml's emission.concerns
               (parsed via the production `_parse_emission_config`, not a
               hand-rolled reader) and the schema's label enum
        When: every shipped label is checked for enum membership
        Then: none are missing

        The 12 shipped labels are exactly what the enum is meant to allow;
        this is the regression guard that the enum's construction did not
        drop or misspell one of them.
        """
        with open(risk_map_yaml_dir / "mermaid-styles.yaml", encoding="utf-8") as fh:
            styles_doc = yaml.safe_load(fh)
        raw_emission = styles_doc["graphTypes"]["component"]["emission"]
        shipped_cfg = _parse_emission_config(raw_emission)
        shipped_labels = {c.label for c in shipped_cfg.concerns}

        enum = _concern_label_enum(risk_map_schemas_dir / "mermaid-styles.schema.json")
        assert enum, "Expected a non-empty label enum (see test_schema_declares_a_non_empty_label_enum)"

        missing = sorted(shipped_labels - set(enum))
        assert not missing, (
            f"Shipped emission.concerns label(s) {missing} are not in the schema's label "
            f"enum; got enum: {sorted(enum)!r}, shipped labels: {sorted(shipped_labels)!r}"
        )

    def test_consult_concern_labels_are_a_subset_of_the_schema_enum(self, risk_map_schemas_dir: Path):
        """
        Given: `decouple.CONSULT_CONCERN_LABELS` (D9's consult-class set) and
               the schema's label enum
        When: checked for subset membership
        Then: every consult label is in the enum

        ADR-036 D12: "The D9 consult-class set must be a subset of the
        vocabulary, asserted by a test on main." A consult label outside the
        enum would mean D9 routes on a label the schema itself would reject
        from any content PR -- an unreachable rule.
        """
        from riskmap_validator.graphing.decouple import CONSULT_CONCERN_LABELS

        enum = _concern_label_enum(risk_map_schemas_dir / "mermaid-styles.schema.json")
        assert enum, "Expected a non-empty label enum (see test_schema_declares_a_non_empty_label_enum)"

        missing = sorted(set(CONSULT_CONCERN_LABELS) - set(enum))
        assert not missing, (
            f"D9 consult-class label(s) {missing} are not in the schema's label enum; "
            f"got enum: {sorted(enum)!r}, consult set: {sorted(CONSULT_CONCERN_LABELS)!r}"
        )

#!/usr/bin/env python3
"""Tests for the persona site data builder."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts.build_persona_site_data import (  # noqa: E402
    build_site_data,
    load_yaml,
    normalize_control_risk_ids,
    normalize_text_entries,
    resolve_output_path,
    write_site_data,
)


def test_build_site_data_filters_deprecated_personas_and_preserves_active_order(
    personas_yaml_path: Path,
    risks_yaml_path: Path,
    controls_yaml_path: Path,
):
    """The site should only expose active personas and keep framework ordering."""
    personas_yaml = load_yaml(personas_yaml_path)
    site_data = build_site_data(
        personas_yaml,
        load_yaml(risks_yaml_path),
        load_yaml(controls_yaml_path),
    )

    expected_active_ids = [persona["id"] for persona in personas_yaml["personas"] if not persona.get("deprecated")]
    actual_ids = [persona["id"] for persona in site_data["personas"]]

    assert actual_ids == expected_active_ids
    assert "personaModelCreator" not in actual_ids
    assert "personaModelConsumer" not in actual_ids


def test_build_site_data_classifies_guided_and_manual_fallback_personas(
    personas_yaml_path: Path,
    risks_yaml_path: Path,
    controls_yaml_path: Path,
):
    """Personas with incomplete question coverage should be routed through manual fallback."""
    site_data = build_site_data(
        load_yaml(personas_yaml_path),
        load_yaml(risks_yaml_path),
        load_yaml(controls_yaml_path),
    )

    persona_by_id = {persona["id"]: persona for persona in site_data["personas"]}

    assert persona_by_id["personaModelProvider"]["matchMode"] == "guided"
    assert persona_by_id["personaPlatformProvider"]["matchMode"] == "guided"
    assert persona_by_id["personaAgenticProvider"]["matchMode"] == "guided"
    assert persona_by_id["personaEndUser"]["matchMode"] == "guided"

    assert set(site_data["manualFallbackPersonaIds"]) == {
        "personaApplicationDeveloper",
        "personaDataProvider",
        "personaGovernance",
        "personaModelServing",
    }
    assert persona_by_id["personaModelServing"]["questionCount"] == 0


def test_build_site_data_preserves_question_order_and_prompt_mapping(
    personas_yaml_path: Path,
    risks_yaml_path: Path,
    controls_yaml_path: Path,
):
    """Question records should remain aligned with the source persona order."""
    personas_yaml = load_yaml(personas_yaml_path)
    site_data = build_site_data(
        personas_yaml,
        load_yaml(risks_yaml_path),
        load_yaml(controls_yaml_path),
    )

    expected_prompts = personas_yaml["personas"][0]["identificationQuestions"]
    actual_questions = [
        question for question in site_data["questions"] if question["personaId"] == "personaModelProvider"
    ]

    assert [question["prompt"] for question in actual_questions] == [prompt.strip() for prompt in expected_prompts]
    assert [question["id"] for question in actual_questions] == [
        "personaModelProvider-q1",
        "personaModelProvider-q2",
        "personaModelProvider-q3",
        "personaModelProvider-q4",
        "personaModelProvider-q5",
        "personaModelProvider-q6",
    ]


def test_build_site_data_derives_persona_risks_and_controls_from_framework_links(
    personas_yaml_path: Path,
    risks_yaml_path: Path,
    controls_yaml_path: Path,
):
    """Persona result links should come from risks.yaml and controls.yaml rather than a website map."""
    raw_risks = load_yaml(risks_yaml_path)
    raw_controls = load_yaml(controls_yaml_path)
    site_data = build_site_data(load_yaml(personas_yaml_path), raw_risks, raw_controls)
    persona_by_id = {persona["id"]: persona for persona in site_data["personas"]}

    expected_model_serving_risks = [
        risk["id"] for risk in raw_risks["risks"] if "personaModelServing" in risk.get("personas", [])
    ]
    expected_model_serving_controls = [
        control["id"]
        for control in raw_controls["controls"]
        if "personaModelServing" in control.get("personas", [])
    ]

    assert persona_by_id["personaModelServing"]["riskIds"] == expected_model_serving_risks
    assert persona_by_id["personaModelServing"]["controlIds"] == expected_model_serving_controls


def test_build_site_data_keeps_governance_controls_but_no_direct_risks(
    personas_yaml_path: Path,
    risks_yaml_path: Path,
    controls_yaml_path: Path,
):
    """Governance should remain selectable even though the framework does not directly link it to risks."""
    site_data = build_site_data(
        load_yaml(personas_yaml_path),
        load_yaml(risks_yaml_path),
        load_yaml(controls_yaml_path),
    )
    governance = next(persona for persona in site_data["personas"] if persona["id"] == "personaGovernance")

    assert governance["riskIds"] == []
    assert governance["controlIds"]


def test_normalize_control_risk_ids_expands_all_to_every_framework_risk():
    """Controls that apply to all risks should be expanded for easier client-side filtering."""
    all_risk_ids = ["riskA", "riskB", "riskC"]

    assert normalize_control_risk_ids("all", all_risk_ids) == all_risk_ids
    assert normalize_control_risk_ids(["riskB", "riskMissing"], all_risk_ids) == ["riskB"]


def test_resolve_output_path_defaults_to_site_generated_directory(tmp_path: Path):
    """The default output path should land in the site generated directory."""
    site_dir = tmp_path / "risk-map" / "site"

    assert resolve_output_path(site_dir, None) == site_dir / "generated" / "persona-site-data.json"
    assert resolve_output_path(site_dir, tmp_path / "custom.json") == tmp_path / "custom.json"


def test_normalize_text_entries_returns_empty_list_for_none():
    """`None` input (from missing YAML keys via `.get()`) must round-trip to []."""
    assert normalize_text_entries(None) == []


def test_normalize_text_entries_preserves_one_level_of_nesting():
    """Nested YAML lists should survive as sub-lists for semantic sub-group prose."""
    result = normalize_text_entries(["first", ["sub-a", "sub-b"], "last"])

    assert result == ["first", ["sub-a", "sub-b"], "last"]
    assert isinstance(result[1], list)
    assert all(isinstance(s, str) for s in result[1])


def test_normalize_text_entries_raises_on_deeper_nesting():
    """Two levels of list nesting are not a supported prose shape."""
    with pytest.raises(TypeError, match="Nested prose items must be strings, got list"):
        normalize_text_entries([["outer", ["inner"]]])


def test_normalize_text_entries_raises_on_non_string_leaf():
    """Non-string prose leaves (e.g. ints) must raise rather than silently stringifying."""
    with pytest.raises(
        TypeError,
        match="Prose items must be string or list-of-strings, got int",
    ):
        normalize_text_entries([123])


def test_normalize_text_entries_drops_empty_whitespace_items():
    """NIT-08: empty / whitespace-only entries are dropped, including inside nested groups."""
    assert normalize_text_entries(["keep", "", "   ", "\n\t", "also keep"]) == ["keep", "also keep"]
    assert normalize_text_entries([["", "real", "  "]]) == [["real"]]
    assert normalize_text_entries([["", "  "]]) == []


def test_build_site_data_propagates_nested_prose_entries_end_to_end():
    """End-to-end: nested long-description groups must reach site data as lists, not repr strings."""
    personas_data = {"personas": [{"id": "personaTest", "title": "Test", "identificationQuestions": []}]}
    risks_data = {
        "risks": [
            {
                "id": "riskNested",
                "title": "Nested",
                "category": "risksTest",
                "shortDescription": ["short"],
                "longDescription": ["First.", "Second.", ["Sub A.", "Sub B."], "Last."],
                "examples": [],
                "personas": ["personaTest"],
                "controls": [],
            }
        ]
    }
    controls_data = {"controls": [], "categories": []}

    result = build_site_data(personas_data, risks_data, controls_data)

    long_description = result["risks"][0]["longDescription"]
    assert long_description == ["First.", "Second.", ["Sub A.", "Sub B."], "Last."]
    assert isinstance(long_description[2], list)
    assert all(isinstance(s, str) for s in long_description[2])


def test_load_yaml_raises_valueerror_on_empty_file(tmp_path: Path):
    """An empty YAML file should surface a clear error rather than return None."""
    empty_path = tmp_path / "empty.yaml"
    empty_path.write_text("")

    with pytest.raises(ValueError, match="is empty or all-null"):
        load_yaml(empty_path)


def test_load_yaml_raises_valueerror_on_whitespace_only_file(tmp_path: Path):
    """A whitespace- or null-only YAML file should also raise ValueError."""
    null_path = tmp_path / "null.yaml"
    null_path.write_text("\n\n")

    with pytest.raises(ValueError, match="is empty or all-null"):
        load_yaml(null_path)


# ============================================================================
# Phase 2b: Output schema validation for persona-site-data.json
# ============================================================================
#
# These tests pin a new contract on the persona site data builder:
#
# 1. A new schema file at risk-map/schemas/persona-site-data.schema.json
#    describes the 7 top-level keys emitted by build_site_data().
# 2. write_site_data() must validate against that schema BEFORE writing,
#    raising jsonschema.ValidationError on structural drift.
# 3. riskmap.schema.json#/definitions/utils/text must tighten its inner-array
#    branch with minItems: 1 so that empty nested groups are rejected at the
#    YAML layer (matching what normalize_text_entries drops at runtime).
# 4. The live risks.yaml must still conform to the tightened schema.


def _minimal_valid_site_data() -> dict:
    """Return a minimal dict conforming to the persona-site-data schema contract."""
    return {
        "personas": [],
        "questions": [],
        "manualFallbackPersonaIds": [],
        "riskCategories": [],
        "controlCategories": [],
        "risks": [],
        "controls": [],
    }


def test_write_site_data_validates_against_output_schema(tmp_path: Path):
    """
    Test that write_site_data accepts conforming output and writes it to disk.

    Given: A minimal dict matching the persona-site-data.schema.json contract
    When: write_site_data() is called with a target path
    Then: The file is written and round-trips back to the same dict via json.load
    """
    valid = _minimal_valid_site_data()
    output_path = tmp_path / "out.json"

    write_site_data(valid, output_path)

    assert output_path.exists(), "write_site_data should write the file on success"
    with output_path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    assert loaded == valid


def test_write_site_data_rejects_non_conforming_output(tmp_path: Path):
    """
    Test that write_site_data refuses to write structurally invalid data.

    Given: A dict where `risks` is a string instead of a list (type violation)
    When: write_site_data() is called
    Then: jsonschema.ValidationError is raised and no file is written
          (fail-before-write semantics)
    """
    invalid = _minimal_valid_site_data()
    invalid["risks"] = "not a list"
    output_path = tmp_path / "out.json"

    with pytest.raises(jsonschema.ValidationError):
        write_site_data(invalid, output_path)

    assert not output_path.exists(), (
        "write_site_data must not write a partial/invalid file when schema validation fails"
    )


def test_persona_site_data_schema_matches_generated_output(
    risk_map_schemas_dir: Path,
    personas_yaml_path: Path,
    risks_yaml_path: Path,
    controls_yaml_path: Path,
):
    """
    Test that the live builder output conforms to persona-site-data.schema.json.

    Given: The current framework YAML files and the new output schema
    When: build_site_data() is called and the result is validated against the schema
    Then: Validation succeeds without raising
    """
    schema_path = risk_map_schemas_dir / "persona-site-data.schema.json"
    assert schema_path.exists(), f"persona-site-data schema must exist at {schema_path}"

    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)

    site_data = build_site_data(
        load_yaml(personas_yaml_path),
        load_yaml(risks_yaml_path),
        load_yaml(controls_yaml_path),
    )

    jsonschema.validate(instance=site_data, schema=schema)


def test_risks_yaml_conforms_to_tightened_prose_schema(
    risks_yaml_path: Path,
    risk_map_schemas_dir: Path,
    base_uri: str,
):
    """
    Test that the live risks.yaml still validates after minItems: 1 tightening.

    Given: risks.yaml (which contains three nested-list longDescription entries
           in riskInsecureIntegratedComponent, riskSensitiveDataDisclosure,
           riskRogueActions) and the tightened riskmap.schema.json
    When: check-jsonschema validates risks.yaml against risks.schema.json with
          cross-file $ref resolution via --base-uri
    Then: Validation passes (the tightening rejects only empty inner arrays,
          which are not present in the live data)
    """
    schema_path = risk_map_schemas_dir / "risks.schema.json"
    assert schema_path.exists(), "risks.schema.json must exist"

    result = subprocess.run(
        [
            "check-jsonschema",
            "--base-uri",
            base_uri,
            "--schemafile",
            str(schema_path),
            str(risks_yaml_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        "Live risks.yaml must still validate after the utils/text minItems tightening.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_risks_schema_rejects_empty_nested_prose_array(
    tmp_path: Path,
    risk_map_schemas_dir: Path,
    base_uri: str,
):
    """
    Test that the tightened utils/text schema rejects empty inner arrays.

    Given: A risks.yaml-shaped document where one risk has a longDescription
           containing an empty nested list ([["paragraph"], []])
    When: check-jsonschema validates it against risks.schema.json
    Then: Validation fails due to minItems: 1 on the inner-array branch of
          riskmap.schema.json#/definitions/utils/text
    """
    schema_path = risk_map_schemas_dir / "risks.schema.json"
    assert schema_path.exists(), "risks.schema.json must exist"

    yaml_content = """
title: Test Risks
description:
  - Test description
risks:
  - id: riskPromptInjection
    title: Prompt Injection
    category: risksRuntimeInputSecurity
    shortDescription:
      - A short description.
    longDescription:
      - - Sub-paragraph within a group.
      - []
    personas:
      - personaModelProvider
    controls:
      - controlInputValidationAndSanitization
"""
    yaml_file = tmp_path / "risks.yaml"
    yaml_file.write_text(yaml_content)

    result = subprocess.run(
        [
            "check-jsonschema",
            "--base-uri",
            base_uri,
            "--schemafile",
            str(schema_path),
            str(yaml_file),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0, (
        "Empty inner array in longDescription should be rejected by the tightened "
        "utils/text schema (minItems: 1 on the inner-array branch).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


@pytest.mark.parametrize(
    "mutator,description",
    [
        (
            lambda d: d.pop("risks"),
            "missing top-level 'risks' key",
        ),
        (
            lambda d: d.__setitem__("personas", "not a list"),
            "wrong-type top-level 'personas' value (string instead of array)",
        ),
        (
            lambda d: d.__setitem__(
                "personas",
                [{"title": "Missing ID"}],
            ),
            "persona object missing required 'id' field",
        ),
    ],
    ids=["missing-top-level-key", "wrong-type-top-level", "nested-object-missing-id"],
)
def test_persona_site_data_schema_rejects_structural_violations(
    risk_map_schemas_dir: Path,
    mutator,
    description: str,
):
    """
    Test that persona-site-data.schema.json rejects representative shape violations.

    Given: A minimal-valid site data dict mutated to introduce a structural defect
    When: The schema validates the mutated dict
    Then: jsonschema.ValidationError is raised, proving the schema enforces the
          top-level key set, top-level value types, and nested-object required fields
    """
    schema_path = risk_map_schemas_dir / "persona-site-data.schema.json"
    assert schema_path.exists(), f"persona-site-data schema must exist at {schema_path}"

    with schema_path.open("r", encoding="utf-8") as handle:
        schema = json.load(handle)

    bad = copy.deepcopy(_minimal_valid_site_data())
    mutator(bad)

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(instance=bad, schema=schema)

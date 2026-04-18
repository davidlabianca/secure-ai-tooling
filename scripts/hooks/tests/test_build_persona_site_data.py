#!/usr/bin/env python3
"""Tests for the persona site data builder."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from scripts.build_persona_site_data import (  # noqa: E402
    build_site_data,
    load_yaml,
    normalize_control_risk_ids,
    resolve_output_path,
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
        question
        for question in site_data["questions"]
        if question["personaId"] == "personaModelProvider"
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

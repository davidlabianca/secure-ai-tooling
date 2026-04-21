#!/usr/bin/env python3
"""
Generate frontend data for the CoSAI-RM persona Pages experience.

This script keeps the website data model derived directly from the framework
YAML files instead of introducing a second website-only mapping.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import yaml

DEFAULT_PERSONAS_PATH = Path("risk-map/yaml/personas.yaml")
DEFAULT_RISKS_PATH = Path("risk-map/yaml/risks.yaml")
DEFAULT_CONTROLS_PATH = Path("risk-map/yaml/controls.yaml")
DEFAULT_SITE_DIR = Path("site")
DEFAULT_OUTPUT_NAME = "persona-site-data.json"
GUIDED_QUESTION_THRESHOLD = 5


def load_yaml(path: Path) -> dict:
    """Load a YAML file into a Python dictionary."""
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def normalize_text_entries(value) -> list[str]:
    """Normalize YAML text scalars/lists into a stripped list of strings."""
    if value is None:
        return []

    if isinstance(value, list):
        items = value
    else:
        items = [value]

    return [str(item).strip() for item in items if str(item).strip()]


def humanize_identifier(identifier: str, prefix: str = "") -> str:
    """Convert schema-like identifiers into simple display labels."""
    trimmed = identifier[len(prefix) :] if prefix and identifier.startswith(prefix) else identifier
    return re.sub(r"(?<!^)(?=[A-Z])", " ", trimmed.replace("-", " ")).strip()


def normalize_control_risk_ids(raw_risks, all_risk_ids: list[str]) -> list[str]:
    """Expand control risk links into explicit IDs for easier client-side filtering."""
    if raw_risks == "all":
        return list(all_risk_ids)

    if raw_risks in (None, "none"):
        return []

    return [risk_id for risk_id in raw_risks if risk_id in all_risk_ids]


def build_site_data(personas_data: dict, risks_data: dict, controls_data: dict) -> dict:
    """Build the JSON structure consumed by the static persona site."""
    active_personas = [persona for persona in personas_data["personas"] if not persona.get("deprecated")]
    active_persona_ids = {persona["id"] for persona in active_personas}

    risk_categories = []
    seen_risk_categories = set()
    normalized_risks = []

    for raw_risk in risks_data["risks"]:
        category_id = raw_risk["category"]
        if category_id not in seen_risk_categories:
            risk_categories.append({"id": category_id, "title": humanize_identifier(category_id, "risks")})
            seen_risk_categories.add(category_id)

        normalized_risks.append(
            {
                "id": raw_risk["id"],
                "title": raw_risk["title"],
                "category": category_id,
                "shortDescription": normalize_text_entries(raw_risk.get("shortDescription")),
                "longDescription": normalize_text_entries(raw_risk.get("longDescription")),
                "examples": normalize_text_entries(raw_risk.get("examples")),
                "controlIds": list(raw_risk.get("controls", [])),
                "personaIds": [
                    persona_id for persona_id in raw_risk.get("personas", []) if persona_id in active_persona_ids
                ],
            }
        )

    all_risk_ids = [risk["id"] for risk in normalized_risks]
    normalized_controls = []

    for raw_control in controls_data["controls"]:
        normalized_controls.append(
            {
                "id": raw_control["id"],
                "title": raw_control["title"],
                "category": raw_control["category"],
                "description": normalize_text_entries(raw_control.get("description")),
                "personaIds": [
                    persona_id
                    for persona_id in raw_control.get("personas", [])
                    if persona_id in active_persona_ids
                ],
                "riskIds": normalize_control_risk_ids(raw_control.get("risks"), all_risk_ids),
            }
        )

    risk_ids_by_persona = {persona["id"]: [] for persona in active_personas}
    control_ids_by_persona = {persona["id"]: [] for persona in active_personas}

    for risk in normalized_risks:
        for persona_id in risk["personaIds"]:
            risk_ids_by_persona[persona_id].append(risk["id"])

    for control in normalized_controls:
        for persona_id in control["personaIds"]:
            control_ids_by_persona[persona_id].append(control["id"])

    question_records = []
    persona_records = []
    manual_fallback_persona_ids = []

    for persona in active_personas:
        question_prompts = normalize_text_entries(persona.get("identificationQuestions"))
        match_mode = "guided" if len(question_prompts) >= GUIDED_QUESTION_THRESHOLD else "manual"

        question_ids = []
        for index, prompt in enumerate(question_prompts, start=1):
            question_id = f"{persona['id']}-q{index}"
            question_ids.append(question_id)
            question_records.append(
                {
                    "id": question_id,
                    "personaId": persona["id"],
                    "personaTitle": persona["title"],
                    "prompt": prompt,
                }
            )

        if match_mode == "manual":
            manual_fallback_persona_ids.append(persona["id"])

        persona_records.append(
            {
                "id": persona["id"],
                "title": persona["title"],
                "description": normalize_text_entries(persona.get("description")),
                "responsibilities": normalize_text_entries(persona.get("responsibilities")),
                "identificationQuestions": question_prompts,
                "questionIds": question_ids,
                "questionCount": len(question_ids),
                "matchMode": match_mode,
                "riskIds": risk_ids_by_persona[persona["id"]],
                "controlIds": control_ids_by_persona[persona["id"]],
                "riskCount": len(risk_ids_by_persona[persona["id"]]),
                "controlCount": len(control_ids_by_persona[persona["id"]]),
            }
        )

    return {
        "personas": persona_records,
        "questions": question_records,
        "manualFallbackPersonaIds": manual_fallback_persona_ids,
        "riskCategories": risk_categories,
        "controlCategories": list(controls_data["categories"]),
        "risks": normalized_risks,
        "controls": normalized_controls,
    }


def resolve_output_path(site_dir: Path, output_path: Path | None) -> Path:
    """Resolve the final JSON output path for the site data."""
    if output_path is not None:
        return output_path

    return site_dir / "generated" / DEFAULT_OUTPUT_NAME


def write_site_data(data: dict, output_path: Path) -> None:
    """Write site data JSON with stable formatting."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Generate CoSAI-RM persona site data JSON.")
    parser.add_argument("--personas-path", type=Path, default=DEFAULT_PERSONAS_PATH)
    parser.add_argument("--risks-path", type=Path, default=DEFAULT_RISKS_PATH)
    parser.add_argument("--controls-path", type=Path, default=DEFAULT_CONTROLS_PATH)
    parser.add_argument("--site-dir", type=Path, default=DEFAULT_SITE_DIR)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    """CLI entrypoint."""
    args = parse_args()
    output_path = resolve_output_path(args.site_dir, args.output)
    site_data = build_site_data(
        load_yaml(args.personas_path),
        load_yaml(args.risks_path),
        load_yaml(args.controls_path),
    )
    write_site_data(site_data, output_path)
    print(f"Wrote {output_path}")


if __name__ == "__main__":
    main()

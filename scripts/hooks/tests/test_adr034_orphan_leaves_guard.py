#!/usr/bin/env python3
"""
Regression guard for ADR-034 §D3a — orphan leaves are deliberately allowed.

A newly-added component (with its bidirectional edges) or a newly-added
persona may be referenced by zero controls and zero risks and must still
pass validation. This is what lets a new component/persona land in its own
PR (ADR-034 Layers 1-2) before the controls/risks that will reference it.

No validator today enforces coverage, and none should without revisiting
ADR-034 §D3a. This file pins that absence: if a future contributor adds a
per-PR coverage check to any of the three seams below, the corresponding
test here starts failing.

Case A targets the component side: `ComponentEdgeValidator` (edge-only
isolation, not coverage) and `validate_control_risk_references`
(control<->risk reciprocity only, no notion of components at all). Case B
targets the persona side: `build_persona_site_data.build_site_data`, which
seeds every active persona with empty risk/control id lists regardless of
whether anything references it.
"""

import sys
from pathlib import Path
from unittest.mock import patch

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from riskmap_validator.validator import ComponentEdgeValidator  # noqa: E402
from validate_control_risk_references import validate_control_to_risk  # noqa: E402

from scripts.build_persona_site_data import build_site_data  # noqa: E402


class TestOrphanComponentPassesValidation:
    """ADR-034 §D3a: an edged-but-uncovered component must pass validation."""

    def test_edged_but_uncovered_component_passes_component_edge_validator(self, tmp_path):
        """
        A component with real bidirectional edges but zero control/risk
        coverage must not be flagged as isolated.

        ADR-034 §D3a: "isolated" means no component-to-component edges;
        coverage by a control or risk is a different, intentionally
        unchecked, axis. If a future coverage check is added to
        ComponentEdgeValidator, this assertion flips to False.
        """
        data = {
            "components": [
                {
                    "id": "comp-orphan-guard",
                    "title": "Orphan Guard Component",
                    "category": "test1",
                    "edges": {"to": ["comp-orphan-guard-peer"], "from": []},
                },
                {
                    "id": "comp-orphan-guard-peer",
                    "title": "Orphan Guard Peer",
                    "category": "test1",
                    "edges": {"to": [], "from": ["comp-orphan-guard"]},
                },
            ]
        }
        yaml_file = tmp_path / "components.yaml"
        yaml_file.write_text(yaml.dump(data))

        validator = ComponentEdgeValidator(allow_isolated=False, verbose=False)
        assert validator.validate_file(yaml_file) is True

    def test_control_risk_validator_has_no_notion_of_component_coverage(self):
        """
        `validate_control_risk_references` must pass a fully self-consistent
        controls.yaml/risks.yaml pair that never mentions a given component id.

        ADR-034 §D3a: this validator checks only control<->risk reciprocity;
        it never touches components.yaml, so an uncovered component cannot
        fail it. "comp-orphan-guard" (from the sibling test above) never
        appears below — if a future contributor teaches this validator to
        consult components.yaml for coverage, this assertion starts failing.
        """
        controls_yaml = {
            "controls": [
                {"id": "CTL-ORPHAN-GUARD", "risks": ["RSK-ORPHAN-GUARD"]},
            ]
        }
        risks_yaml = {
            "risks": [
                {"id": "RSK-ORPHAN-GUARD", "controls": ["CTL-ORPHAN-GUARD"]},
            ]
        }

        with patch("validate_control_risk_references.load_yaml_file") as mock_load:
            mock_load.side_effect = [controls_yaml, risks_yaml]
            result = validate_control_to_risk([Path("controls.yaml"), Path("risks.yaml")])

        assert result is True


class TestOrphanPersonaPassesValidation:
    """ADR-034 §D3a: a persona referenced by zero risks/controls must pass the site build."""

    def test_uncovered_persona_builds_with_empty_risk_and_control_ids(self):
        """
        A persona with no risk or control referencing it must still build
        successfully, with empty riskIds/controlIds rather than an error.

        ADR-034 §D3a: `build_site_data` seeds every active persona with an
        empty risk/control id list up front (build_persona_site_data.py
        risk_ids_by_persona / control_ids_by_persona), so an unreferenced
        persona is never rejected. If a future contributor adds a coverage
        requirement here, this assertion starts failing.
        """
        personas_data = {
            "personas": [
                {"id": "personaOrphanGuard", "title": "Orphan Guard Persona"},
            ]
        }
        risks_data = {"risks": []}
        controls_data = {"categories": [], "controls": []}

        site_data = build_site_data(personas_data, risks_data, controls_data, components_data={})

        persona_ids = [p["id"] for p in site_data["personas"]]
        assert "personaOrphanGuard" in persona_ids

        persona_record = next(p for p in site_data["personas"] if p["id"] == "personaOrphanGuard")
        assert persona_record["riskIds"] == []
        assert persona_record["controlIds"] == []
        assert persona_record["riskCount"] == 0
        assert persona_record["controlCount"] == 0

"""
Drift guard: styling doc YAML examples must stay valid against the mermaid-styles schema.

`scripts/docs/styling-configuration.md` and `risk-map/docs/graph-customization.md`
each carry fenced ```yaml examples that show contributors how to edit
`risk-map/yaml/mermaid-styles.yaml`. Nothing previously checked that those
examples still parse and validate against
`risk-map/schemas/mermaid-styles.schema.json`. Issue #477's removal of the
control and risk graph generators narrowed the schema (`graphTypes.required`
dropped to `["component"]`, `subgroupFill` removed from `componentCategory`)
without anyone re-checking the docs, so contributors following the recipes for
`graphTypes.control` / `graphTypes.risk` hit a hard schema rejection. This
guard fails loudly if that class of drift recurs.

Each fenced example is a fragment, not a complete config (e.g. a single
category override, or just a `graphTypes.component.direction` change). To
validate a fragment, it is deep-merged onto a copy of the live
`mermaid-styles.yaml` before validation, so only what the fragment actually
specifies is exercised against the schema — the rest of the required
structure comes from the real config.
"""

import copy
import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft7Validator

# Resolve the repo root from this test file's location:
# scripts/hooks/tests/ -> scripts/hooks/ -> scripts/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_STYLING_CONFIGURATION_DOC = _REPO_ROOT / "scripts" / "docs" / "styling-configuration.md"
_GRAPH_CUSTOMIZATION_DOC = _REPO_ROOT / "risk-map" / "docs" / "graph-customization.md"
_LIVE_CONFIG = _REPO_ROOT / "risk-map" / "yaml" / "mermaid-styles.yaml"
_SCHEMA_FILE = _REPO_ROOT / "risk-map" / "schemas" / "mermaid-styles.schema.json"

# Matches ```yaml and ```yml fences, case-insensitively (```YAML, ```Yml, etc.),
# so a doc author using the shorter or differently-cased fence tag is still caught.
_YAML_FENCE_PATTERN = re.compile(r"```ya?ml\n(.*?)```", re.DOTALL | re.IGNORECASE)


def _extract_yaml_blocks(doc_path: Path) -> list[str]:
    """Return the raw text of every fenced ```yaml block in a markdown doc."""
    text = doc_path.read_text(encoding="utf-8")
    return _YAML_FENCE_PATTERN.findall(text)


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """
    Recursively merge overlay onto base, returning a new dict.

    Nested dicts are merged key-by-key; any other value (scalar, list) in
    overlay replaces the corresponding value in base outright. This models
    "apply this doc fragment as an edit to the live config" rather than
    requiring every fragment to be a complete, standalone document.
    """
    merged = copy.deepcopy(base)
    for key, overlay_value in overlay.items():
        base_value = merged.get(key)
        if isinstance(base_value, dict) and isinstance(overlay_value, dict):
            merged[key] = _deep_merge(base_value, overlay_value)
        else:
            merged[key] = copy.deepcopy(overlay_value)
    return merged


def _load_live_config() -> dict[str, Any]:
    with _LIVE_CONFIG.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def _load_schema() -> dict[str, Any]:
    with _SCHEMA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _collect_doc_examples() -> list[tuple[str, int, str]]:
    """
    Return (doc_label, block_index, yaml_text) for every fenced yaml block
    in the two styling docs.
    """
    examples: list[tuple[str, int, str]] = []
    for label, doc_path in (
        ("styling-configuration.md", _STYLING_CONFIGURATION_DOC),
        ("graph-customization.md", _GRAPH_CUSTOMIZATION_DOC),
    ):
        for index, block in enumerate(_extract_yaml_blocks(doc_path)):
            examples.append((label, index, block))
    return examples


_DOC_EXAMPLES = _collect_doc_examples()
_DOC_EXAMPLE_IDS = [f"{label}[{index}]" for label, index, _ in _DOC_EXAMPLES]


class TestStylingDocExamplesMatchSchema:
    """Every fenced yaml example in the styling docs validates against the schema."""

    def test_docs_contain_at_least_one_example(self):
        """
        Given the two styling doc files
        When fenced yaml blocks are extracted
        Then at least one example is found in each file

        Guards against the extraction regex silently matching nothing, which
        would make every other test in this module vacuously pass.
        """
        labels = {label for label, _, _ in _DOC_EXAMPLES}
        assert labels == {"styling-configuration.md", "graph-customization.md"}, (
            f"Expected fenced yaml examples from both doc files, found: {sorted(labels)}"
        )

    @pytest.mark.parametrize("label,index,yaml_text", _DOC_EXAMPLES, ids=_DOC_EXAMPLE_IDS)
    def test_example_merged_into_live_config_is_schema_valid(self, label, index, yaml_text):
        """
        Given a fenced yaml example from a styling doc
        When it is deep-merged onto the live mermaid-styles.yaml and validated
        Then the merged configuration satisfies mermaid-styles.schema.json

        A failure here means the doc shows a contributor an edit the schema
        will not accept — the exact failure mode this guard exists to catch.
        """
        fragment = yaml.safe_load(yaml_text)
        assert isinstance(fragment, dict), f"{label} block {index} did not parse to a mapping: {yaml_text!r}"

        merged = _deep_merge(_load_live_config(), fragment)
        schema = _load_schema()

        validator = Draft7Validator(schema)
        errors = sorted(validator.iter_errors(merged), key=lambda e: e.path)

        assert not errors, (
            f"{label} block {index} is invalid against the schema after merging "
            f"onto the live config:\n"
            + "\n".join(f"  - {'/'.join(str(p) for p in e.path)}: {e.message}" for e in errors)
            + f"\n\nSource fragment:\n{yaml_text}"
        )

#!/usr/bin/env python3
"""
Tests for the selective per-framework wiring in risks + controls mappings.

Per ADR-019 D5 and ADR-020 D5, risks.schema.json and controls.schema.json
declare a mappings block with a hybrid shape:
- Per-property strict wiring for mitre-atlas, iso-22989, eu-ai-act (regex via
  $ref to frameworks.schema.json#/definitions/framework-mapping-patterns).
- Loose additionalProperties catch-all for stride, nist-ai-rmf, owasp-top10-llm
  whose current YAML content does not match the ADR-022 D5b canonical regexes.

The decision is deliberate and selective: only frameworks whose current YAML
content already matches the canonical regexes receive per-property strict
wiring. Subsequent content normalisation will fix the remaining frameworks.

Coverage:
- risks and controls schemas each have per-property mitre-atlas/iso-22989/eu-ai-act.
- additionalProperties catch-all is present.
- mitre-atlas "AML.T0020" validates; "aml-t0020" is rejected.
- stride "tampering" passes (loose path — not yet normalised to PascalCase).
- Unknown framework key "made-up-framework" is rejected via propertyNames.
- Current risks.yaml and controls.yaml still pass check-jsonschema.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Module-level constants — current-YAML-content audit data
# ============================================================================

# Consumer schemas receiving the hybrid wiring.
CONSUMER_SCHEMAS = [
    ("risks.schema.json", "risk"),
    ("controls.schema.json", "control"),
]

# These frameworks get strict per-property wiring because their current YAML
# content already matches the ADR-022 D5b canonical regex patterns.
STRICTLY_WIRED_FRAMEWORKS = {"mitre-atlas", "iso-22989", "eu-ai-act"}

# These frameworks fall through to the loose additionalProperties catch-all
# because current YAML uses non-canonical short forms:
#   nist-ai-rmf:     GV-6.2, MS-2.11     — short prefix; pattern needs GOVERN/MAP/...
#   owasp-top10-llm: LLM01, LLM09        — missing version year; pattern needs LLM\d{2}:\d{4}
#   stride:          tampering, spoofing  — lowercase-kebab; pattern needs PascalCase
LOOSE_FRAMEWORKS = {"stride", "nist-ai-rmf", "owasp-top10-llm"}

# mitre-atlas valid examples drawn from current risks.yaml content.
MITRE_ATLAS_VALID: list[str] = [
    "AML.T0020",
    "AML.M0011",
    "AML.T0010.002",
]

# mitre-atlas malformed examples that must be rejected after strict wiring.
MITRE_ATLAS_INVALID: list[str] = [
    "aml-t0020",  # lowercase-kebab (external-references surface)
    "AML.T20",  # short technique ID
    "AML.X0020",  # non-T/M letter
]

# stride current-YAML values that must still pass via the loose catch-all.
STRIDE_LOOSE_VALID: list[str] = [
    "tampering",
    "spoofing",
    "repudiation",
    "information-disclosure",
    "denial-of-service",
]

# nist-ai-rmf current-YAML values (short prefix form).
NIST_LOOSE_VALID: list[str] = ["GV-6.2", "MS-2.11", "MS-2.3"]

# owasp-top10-llm current-YAML values (missing version year).
OWASP_LOOSE_VALID: list[str] = ["LLM01", "LLM05", "LLM09"]

# iso-22989 bare strings from current personas.yaml.
ISO_VALID: list[str] = [
    "AI Producer",
    "AI Customer (application builder)",
    "Arbitrary descriptor",
]

# eu-ai-act is currently empty in YAML; any Article-form value should pass.
EU_AI_ACT_VALID: list[str] = ["Article 5", "Article 5(1)", "Article 50"]


# ============================================================================
# Fixtures
# ============================================================================


def _load_schema(schemas_dir: Path, filename: str) -> dict:
    path = schemas_dir / filename
    if not path.is_file():
        pytest.fail(f"Schema not found: {path}")
    with open(path) as fh:
        return json.load(fh)


def _make_registry(schemas_dir: Path) -> Registry:
    """
    Build a referencing.Registry that resolves bare-filename $refs against
    schemas in the given directory. Replaces the deprecated jsonschema.RefResolver.
    """

    def retrieve(uri: str):
        # The validator hands us the URI portion of a $ref; for our refs the
        # URI is a bare schema filename relative to schemas_dir.
        name = uri.rsplit("/", 1)[-1]
        path = schemas_dir / name
        with open(path) as fh:
            return Resource.from_contents(json.load(fh), default_specification=DRAFT7)

    return Registry(retrieve=retrieve)


@pytest.fixture(scope="module")
def risks_schema(risk_map_schemas_dir: Path) -> dict:
    return _load_schema(risk_map_schemas_dir, "risks.schema.json")


@pytest.fixture(scope="module")
def controls_schema(risk_map_schemas_dir: Path) -> dict:
    return _load_schema(risk_map_schemas_dir, "controls.schema.json")


@pytest.fixture(scope="module")
def schemas_registry(risk_map_schemas_dir: Path) -> Registry:
    """Shared registry for risks + controls cross-file $ref resolution."""
    return _make_registry(risk_map_schemas_dir)


def _get_mappings_schema(schema: dict, entity_key: str) -> dict:
    """Extract definitions/<entity>/properties/mappings from a schema."""
    mappings = schema.get("definitions", {}).get(entity_key, {}).get("properties", {}).get("mappings")
    if mappings is None:
        pytest.fail(f"definitions/{entity_key}/properties/mappings not found")
    return mappings


# ============================================================================
# Schema meta-validity
# ============================================================================


class TestSchemaMetaValidity:
    """risks.schema.json and controls.schema.json must each be valid Draft-07."""

    @pytest.mark.parametrize("schema_file,entity_key", CONSUMER_SCHEMAS, ids=["risks", "controls"])
    def test_schema_passes_draft07_metaschema(self, risk_map_schemas_dir: Path, schema_file: str, entity_key: str):
        """
        Test that each consumer schema is valid Draft-07.

        Given: A consumer schema file
        When: Draft7Validator.check_schema() is called
        Then: No SchemaError is raised
        """
        schema = _load_schema(risk_map_schemas_dir, schema_file)
        try:
            Draft7Validator.check_schema(schema)
        except SchemaError as exc:
            pytest.fail(f"{schema_file} is not valid Draft-07: {exc.message}")


# ============================================================================
# Structural shape of mappings (hybrid wiring)
# ============================================================================


class TestMappingsStructure:
    """
    The mappings block in risks/controls must have the hybrid wiring shape:
    per-property strict entries + loose catch-all.
    """

    @pytest.mark.parametrize("schema_file,entity_key", CONSUMER_SCHEMAS, ids=["risks", "controls"])
    def test_mappings_has_additional_properties_catch_all(
        self, risk_map_schemas_dir: Path, schema_file: str, entity_key: str
    ):
        """
        Test that the loose catch-all additionalProperties is present.

        Given: The mappings sub-schema in a consumer schema
        When: Its additionalProperties is examined
        Then: It is type:array with items type:string
        """
        schema = _load_schema(risk_map_schemas_dir, schema_file)
        mappings = _get_mappings_schema(schema, entity_key)
        additional = mappings.get("additionalProperties")
        assert additional is not None, f"{schema_file} mappings must declare additionalProperties catch-all"
        assert additional.get("type") == "array", "additionalProperties catch-all must be type: array"
        assert additional.get("items", {}).get("type") == "string", "catch-all items must be type: string"

    @pytest.mark.parametrize("schema_file,entity_key", CONSUMER_SCHEMAS, ids=["risks", "controls"])
    @pytest.mark.parametrize("framework_key", sorted(STRICTLY_WIRED_FRAMEWORKS))
    def test_strictly_wired_framework_declared_in_properties(
        self, risk_map_schemas_dir: Path, schema_file: str, entity_key: str, framework_key: str
    ):
        """
        Test that per-property entries for mitre-atlas/iso-22989/eu-ai-act exist.

        Given: The mappings sub-schema properties block in a consumer schema
        When: A strictly-wired framework key is looked up
        Then: It is present
        """
        schema = _load_schema(risk_map_schemas_dir, schema_file)
        mappings = _get_mappings_schema(schema, entity_key)
        props = mappings.get("properties", {})
        assert framework_key in props, (
            f"{schema_file} mappings.properties must declare '{framework_key}' "
            "(strictly-wired per ADR-019 D5 / ADR-020 D5)"
        )


# ============================================================================
# mitre-atlas strict wiring — valid / invalid behavioral tests
# ============================================================================


class TestMitreAtlasStrictWiring:
    """
    mitre-atlas items must match ^AML\\.(T|M)\\d{4}(\\.\\d{3})?$ per ADR-022 D5b.
    All 34 distinct values in the current corpus match this pattern, so strict
    wiring is safe.
    """

    @pytest.mark.parametrize("valid_id", MITRE_ATLAS_VALID)
    def test_mitre_atlas_valid_accepted_in_risks(
        self, risks_schema: dict, schemas_registry: Registry, valid_id: str
    ):
        """
        Test that canonical mitre-atlas IDs pass in risks mappings.

        Given: risks mappings schema with mitre-atlas strict wiring
        When: {"mitre-atlas": [<valid_id>]} is validated
        Then: No errors are raised
        """
        mappings = _get_mappings_schema(risks_schema, "risk")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"mitre-atlas": [valid_id]}))
        assert not errors, f"risks mitre-atlas {valid_id!r} must be accepted; got: {[e.message for e in errors]}"

    @pytest.mark.parametrize("invalid_id", MITRE_ATLAS_INVALID)
    def test_mitre_atlas_invalid_rejected_in_risks(
        self, risks_schema: dict, schemas_registry: Registry, invalid_id: str
    ):
        """
        Test that malformed mitre-atlas IDs are rejected in risks mappings.

        Given: risks mappings schema with mitre-atlas strict wiring
        When: {"mitre-atlas": [<invalid_id>]} is validated
        Then: ValidationError is raised
        """
        mappings = _get_mappings_schema(risks_schema, "risk")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"mitre-atlas": [invalid_id]}))
        assert errors, f"risks mitre-atlas malformed ID {invalid_id!r} must be rejected"

    @pytest.mark.parametrize("valid_id", MITRE_ATLAS_VALID)
    def test_mitre_atlas_valid_accepted_in_controls(
        self, controls_schema: dict, schemas_registry: Registry, valid_id: str
    ):
        """
        Test that canonical mitre-atlas IDs pass in controls mappings.

        Given: controls mappings schema with mitre-atlas strict wiring
        When: {"mitre-atlas": [<valid_id>]} is validated
        Then: No errors are raised
        """
        mappings = _get_mappings_schema(controls_schema, "control")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"mitre-atlas": [valid_id]}))
        assert not errors, (
            f"controls mitre-atlas {valid_id!r} must be accepted; got: {[e.message for e in errors]}"
        )

    @pytest.mark.parametrize("invalid_id", MITRE_ATLAS_INVALID)
    def test_mitre_atlas_invalid_rejected_in_controls(
        self, controls_schema: dict, schemas_registry: Registry, invalid_id: str
    ):
        """
        Test that malformed mitre-atlas IDs are rejected in controls mappings.

        Given: controls mappings schema with mitre-atlas strict wiring
        When: {"mitre-atlas": [<invalid_id>]} is validated
        Then: ValidationError is raised
        """
        mappings = _get_mappings_schema(controls_schema, "control")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"mitre-atlas": [invalid_id]}))
        assert errors, f"controls mitre-atlas malformed ID {invalid_id!r} must be rejected"


# ============================================================================
# iso-22989 and eu-ai-act strict wiring — valid / invalid behavioral tests
# ============================================================================


class TestIsoAndEuAiActStrictWiring:
    """
    iso-22989 uses bare string items with no pattern constraint (deliberately
    permissive per A1 design — any non-empty string is valid). eu-ai-act items
    must match ^Article\\s\\d+(\\(\\d+\\))?$ per ADR-022 D5b.

    Both frameworks receive per-property strict wiring in the risks and controls
    mappings schemas via $ref to framework-mapping-patterns in
    frameworks.schema.json.
    """

    @pytest.mark.parametrize("valid_value", ISO_VALID)
    def test_iso_22989_valid_accepted_in_risks(
        self, risks_schema: dict, schemas_registry: Registry, valid_value: str
    ):
        """
        Test that iso-22989 bare-string descriptors pass in risks mappings.

        Given: risks mappings schema with iso-22989 strict wiring
        When: {"iso-22989": [<valid_value>]} is validated
        Then: No errors are raised (iso-22989 is permissive; any string is valid)
        """
        mappings = _get_mappings_schema(risks_schema, "risk")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"iso-22989": [valid_value]}))
        assert not errors, f"risks iso-22989 {valid_value!r} must be accepted; got: {[e.message for e in errors]}"

    @pytest.mark.parametrize("valid_value", ISO_VALID)
    def test_iso_22989_valid_accepted_in_controls(
        self, controls_schema: dict, schemas_registry: Registry, valid_value: str
    ):
        """
        Test that iso-22989 bare-string descriptors pass in controls mappings.

        Given: controls mappings schema with iso-22989 strict wiring
        When: {"iso-22989": [<valid_value>]} is validated
        Then: No errors are raised
        """
        mappings = _get_mappings_schema(controls_schema, "control")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"iso-22989": [valid_value]}))
        assert not errors, (
            f"controls iso-22989 {valid_value!r} must be accepted; got: {[e.message for e in errors]}"
        )

    @pytest.mark.parametrize("valid_value", EU_AI_ACT_VALID)
    def test_eu_ai_act_valid_accepted_in_risks(
        self, risks_schema: dict, schemas_registry: Registry, valid_value: str
    ):
        """
        Test that eu-ai-act Article-form values pass in risks mappings.

        Given: risks mappings schema with eu-ai-act strict wiring
        When: {"eu-ai-act": [<valid_value>]} in ^Article\\s\\d+(\\(\\d+\\))?$ form is validated
        Then: No errors are raised
        """
        mappings = _get_mappings_schema(risks_schema, "risk")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"eu-ai-act": [valid_value]}))
        assert not errors, f"risks eu-ai-act {valid_value!r} must be accepted; got: {[e.message for e in errors]}"

    @pytest.mark.parametrize("valid_value", EU_AI_ACT_VALID)
    def test_eu_ai_act_valid_accepted_in_controls(
        self, controls_schema: dict, schemas_registry: Registry, valid_value: str
    ):
        """
        Test that eu-ai-act Article-form values pass in controls mappings.

        Given: controls mappings schema with eu-ai-act strict wiring
        When: {"eu-ai-act": [<valid_value>]} is validated
        Then: No errors are raised
        """
        mappings = _get_mappings_schema(controls_schema, "control")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"eu-ai-act": [valid_value]}))
        assert not errors, (
            f"controls eu-ai-act {valid_value!r} must be accepted; got: {[e.message for e in errors]}"
        )

    @pytest.mark.parametrize(
        "invalid_value",
        [
            "Article",  # no article number
            "article-5",  # lowercase-kebab form (rejected by strict pattern)
            "Art 5",  # abbreviated prefix
        ],
    )
    def test_eu_ai_act_invalid_rejected_in_risks(
        self, risks_schema: dict, schemas_registry: Registry, invalid_value: str
    ):
        """
        Test that malformed eu-ai-act values are rejected in risks mappings.

        Given: risks mappings schema with eu-ai-act strict wiring
        When: {"eu-ai-act": [<invalid_value>]} with a non-Article-form value is validated
        Then: ValidationError is raised (strict pattern ^Article\\s\\d+(\\(\\d+\\))?$ rejects it)
        """
        mappings = _get_mappings_schema(risks_schema, "risk")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"eu-ai-act": [invalid_value]}))
        assert errors, f"risks eu-ai-act malformed value {invalid_value!r} must be rejected"

    @pytest.mark.parametrize(
        "invalid_value",
        [
            "Article",  # no article number
            "article-5",  # lowercase-kebab form (rejected by strict pattern)
            "Art 5",  # abbreviated prefix
        ],
    )
    def test_eu_ai_act_invalid_rejected_in_controls(
        self, controls_schema: dict, schemas_registry: Registry, invalid_value: str
    ):
        """
        Test that malformed eu-ai-act values are rejected in controls mappings.

        Given: controls mappings schema with eu-ai-act strict wiring
        When: {"eu-ai-act": [<invalid_value>]} is validated
        Then: ValidationError is raised
        """
        mappings = _get_mappings_schema(controls_schema, "control")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"eu-ai-act": [invalid_value]}))
        assert errors, f"controls eu-ai-act malformed value {invalid_value!r} must be rejected"


# ============================================================================
# Loose frameworks — current content must still pass via catch-all
# ============================================================================


class TestLooseFrameworksPassThrough:
    """
    stride, nist-ai-rmf, and owasp-top10-llm fall through to the loose
    additionalProperties catch-all. Their current YAML content does not match
    the ADR-022 D5b canonical regexes and will be normalised by subsequent
    content fixes.
    """

    @pytest.mark.parametrize("value", STRIDE_LOOSE_VALID)
    def test_stride_current_content_accepted_in_risks(
        self, risks_schema: dict, schemas_registry: Registry, value: str
    ):
        """
        Test that current stride values (lowercase-kebab) pass via the catch-all.

        Given: risks mappings with stride pointing to loose catch-all
        When: {"stride": [<value>]} is validated
        Then: No errors are raised (loose path; subsequent content fixes will normalise)
        """
        mappings = _get_mappings_schema(risks_schema, "risk")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"stride": [value]}))
        assert not errors, (
            f"stride value {value!r} must be accepted via loose catch-all; got: {[e.message for e in errors]}"
        )

    @pytest.mark.parametrize("value", NIST_LOOSE_VALID)
    def test_nist_ai_rmf_current_content_accepted_in_risks(
        self, risks_schema: dict, schemas_registry: Registry, value: str
    ):
        """
        Test that current nist-ai-rmf values (short prefix form) pass via the catch-all.

        Given: risks mappings with nist-ai-rmf pointing to loose catch-all
        When: {"nist-ai-rmf": [<value>]} is validated
        Then: No errors are raised
        """
        mappings = _get_mappings_schema(risks_schema, "risk")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"nist-ai-rmf": [value]}))
        assert not errors, (
            f"nist-ai-rmf value {value!r} must be accepted via loose catch-all; got: {[e.message for e in errors]}"
        )

    @pytest.mark.parametrize("value", OWASP_LOOSE_VALID)
    def test_owasp_top10_llm_current_content_accepted_in_risks(
        self, risks_schema: dict, schemas_registry: Registry, value: str
    ):
        """
        Test that current owasp-top10-llm values (no version year) pass via catch-all.

        Given: risks mappings with owasp-top10-llm pointing to loose catch-all
        When: {"owasp-top10-llm": [<value>]} is validated
        Then: No errors are raised
        """
        mappings = _get_mappings_schema(risks_schema, "risk")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"owasp-top10-llm": [value]}))
        assert not errors, (
            f"owasp-top10-llm value {value!r} must be accepted via loose catch-all; "
            f"got: {[e.message for e in errors]}"
        )

    @pytest.mark.parametrize("value", STRIDE_LOOSE_VALID)
    def test_stride_current_content_accepted_in_controls(
        self, controls_schema: dict, schemas_registry: Registry, value: str
    ):
        """
        Test that current stride values (lowercase-kebab) pass via the controls catch-all.

        Given: controls mappings with stride pointing to loose catch-all
        When: {"stride": [<value>]} is validated
        Then: No errors are raised (controls hybrid wiring)
        """
        mappings = _get_mappings_schema(controls_schema, "control")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"stride": [value]}))
        assert not errors, (
            f"controls stride value {value!r} must be accepted via loose catch-all; "
            f"got: {[e.message for e in errors]}"
        )

    @pytest.mark.parametrize("value", NIST_LOOSE_VALID)
    def test_nist_ai_rmf_current_content_accepted_in_controls(
        self, controls_schema: dict, schemas_registry: Registry, value: str
    ):
        """
        Test that current nist-ai-rmf values (short prefix form) pass via the controls catch-all.

        Given: controls mappings with nist-ai-rmf pointing to loose catch-all
        When: {"nist-ai-rmf": [<value>]} is validated
        Then: No errors are raised
        """
        mappings = _get_mappings_schema(controls_schema, "control")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"nist-ai-rmf": [value]}))
        assert not errors, (
            f"controls nist-ai-rmf value {value!r} must be accepted via loose catch-all; "
            f"got: {[e.message for e in errors]}"
        )

    @pytest.mark.parametrize("value", OWASP_LOOSE_VALID)
    def test_owasp_top10_llm_current_content_accepted_in_controls(
        self, controls_schema: dict, schemas_registry: Registry, value: str
    ):
        """
        Test that current owasp-top10-llm values (no version year) pass via controls catch-all.

        Given: controls mappings with owasp-top10-llm pointing to loose catch-all
        When: {"owasp-top10-llm": [<value>]} is validated
        Then: No errors are raised
        """
        mappings = _get_mappings_schema(controls_schema, "control")
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"owasp-top10-llm": [value]}))
        assert not errors, (
            f"controls owasp-top10-llm value {value!r} must be accepted via loose catch-all; "
            f"got: {[e.message for e in errors]}"
        )


# ============================================================================
# Unknown framework key rejected via propertyNames
# ============================================================================


class TestUnknownFrameworkRejected:
    """Unknown framework keys must be rejected via propertyNames."""

    @pytest.mark.parametrize("schema_file,entity_key", CONSUMER_SCHEMAS, ids=["risks", "controls"])
    def test_unknown_framework_key_rejected(
        self,
        risk_map_schemas_dir: Path,
        schemas_registry: Registry,
        schema_file: str,
        entity_key: str,
    ):
        """
        Test that an unregistered framework key is rejected.

        Given: A mappings object with made-up-framework: ["some-value"]
        When: It is validated against the mappings schema
        Then: ValidationError is raised (propertyNames constraint)
        """
        schema = _load_schema(risk_map_schemas_dir, schema_file)
        mappings = _get_mappings_schema(schema, entity_key)
        validator = Draft7Validator(mappings, registry=schemas_registry)
        errors = list(validator.iter_errors({"made-up-framework": ["some-value"]}))
        assert errors, (
            f"{schema_file}: unknown framework key 'made-up-framework' must be rejected via propertyNames"
        )


# ============================================================================
# Regression — current YAML files still validate
# ============================================================================


class TestCurrentYamlStillValid:
    """
    Current risks.yaml and controls.yaml must continue to pass check-jsonschema
    (the hybrid wiring is additive and backward-compatible).
    """

    def test_risks_yaml_passes_check_jsonschema(self, risk_map_schemas_dir: Path, risk_map_yaml_dir: Path):
        """
        Test that risks.yaml continues to validate against risks.schema.json.

        Given: The current risks.yaml on disk
        When: check-jsonschema is run with risks.schema.json
        Then: Exit code is 0
        """
        result = subprocess.run(
            [
                "check-jsonschema",
                "--base-uri",
                f"file://{risk_map_schemas_dir}/",
                "--schemafile",
                str(risk_map_schemas_dir / "risks.schema.json"),
                str(risk_map_yaml_dir / "risks.yaml"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"risks.yaml must remain valid against risks.schema.json:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_controls_yaml_passes_check_jsonschema(self, risk_map_schemas_dir: Path, risk_map_yaml_dir: Path):
        """
        Test that controls.yaml continues to validate against controls.schema.json.

        Given: The current controls.yaml on disk
        When: check-jsonschema is run with controls.schema.json
        Then: Exit code is 0
        """
        result = subprocess.run(
            [
                "check-jsonschema",
                "--base-uri",
                f"file://{risk_map_schemas_dir}/",
                "--schemafile",
                str(risk_map_schemas_dir / "controls.schema.json"),
                str(risk_map_yaml_dir / "controls.yaml"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"controls.yaml must remain valid against controls.schema.json:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Test classes: 8

- TestSchemaMetaValidity (2)              — risks + controls valid Draft-07
- TestMappingsStructure                   — catch-all present, strictly-wired
                                            keys declared (parametrized × 2 schemas
                                            × 3 frameworks)
- TestMitreAtlasStrictWiring              — parametrized: 3 valid + 3 invalid ×
                                            risks + controls (12 cases)
- TestIsoAndEuAiActStrictWiring           — iso-22989: 3 valid × risks + controls;
                                            eu-ai-act: 3 valid × risks + controls;
                                            eu-ai-act: 3 invalid × risks + controls
                                            (18 cases)
- TestLooseFrameworksPassThrough          — stride/nist-ai-rmf/owasp-top10-llm
                                            current content accepted for BOTH
                                            risks and controls (22 cases)
- TestUnknownFrameworkRejected (2)        — propertyNames rejects unknown key
                                            (parametrized × 2 schemas)
- TestCurrentYamlStillValid (2)           — risks.yaml + controls.yaml still pass

Coverage areas:
- Hybrid wiring shape: strict per-property entries + loose catch-all
- Strict frameworks: mitre-atlas, iso-22989, eu-ai-act
- Loose frameworks: stride, nist-ai-rmf, owasp-top10-llm (pending content
  normalisation to canonical forms)
- Behavioral: valid/invalid for all strictly-wired frameworks × risks + controls;
              loose pass-through × risks + controls; unknown key rejected
- Regression: current YAML backward-compatible
"""

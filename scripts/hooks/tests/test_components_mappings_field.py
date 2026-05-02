#!/usr/bin/env python3
"""
Tests for the optional mappings field on components.schema.json.

Per ADR-018 D6 + ADR-022 D5b/D5c, definitions/component/properties declares
a mappings field with the same hybrid shape used by risks/controls/personas:
- propertyNames $ref to frameworks.schema.json framework/id enum.
- Per-property strict wiring for mitre-atlas, iso-22989, eu-ai-act (regex-
  backed via $ref to framework-mapping-patterns).
- Loose additionalProperties catch-all (array of strings) for remaining
  frameworks (stride, nist-ai-rmf, owasp-top10-llm).
- Optional — NOT in the required array.

The hybrid wiring reflects the state of current YAML mappings content:
mitre-atlas/iso-22989/eu-ai-act entries already conform to ADR-022 D5b
canonical regexes; stride/nist-ai-rmf/owasp-top10-llm use non-canonical
short forms that subsequent content normalisation will fix.

Coverage:
- mappings property is declared in definitions/component/properties.
- propertyNames $ref to frameworks.schema.json is present.
- Per-property entries for mitre-atlas, iso-22989, eu-ai-act are declared.
- additionalProperties catch-all is present.
- Field is NOT in required.
- Known-good mitre-atlas value AML.T0020 validates.
- Malformed mitre-atlas value aml-t0020 is rejected.
- Unknown framework key is rejected via propertyNames.
- Current components.yaml passes validation unchanged.
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
# Module-level constants
# ============================================================================

SCHEMA_FILE = "components.schema.json"
ENTITY_KEY = "component"

# Frameworks wired with per-property strict patterns.
STRICTLY_WIRED_FRAMEWORKS = {"mitre-atlas", "iso-22989", "eu-ai-act"}

# Frameworks that fall through to the loose additionalProperties catch-all.
LOOSE_FRAMEWORKS = {"stride", "nist-ai-rmf", "owasp-top10-llm"}

# Valid per-framework examples for the strictly-wired set.
# mitre-atlas: canonical uppercase form from A1 pattern ^AML\.(T|M)\d{4}(\.\d{3})?$
# iso-22989: bare string (no pattern)
# eu-ai-act: pattern ^Article\s\d+(\(\d+\))?$
VALID_STRICT_EXAMPLES: dict[str, list[str]] = {
    "mitre-atlas": ["AML.T0020", "AML.M0011", "AML.T0010.002"],
    "iso-22989": ["AI Producer", "AI Customer (application builder)"],
    "eu-ai-act": ["Article 5", "Article 5(1)", "Article 50"],
}

# Invalid mitre-atlas examples (wrong form).
INVALID_MITRE_ATLAS: list[str] = [
    "aml-t0020",  # lowercase-kebab (external-references surface, not this one)
    "AML.T20",  # short ID
    "AML.X0020",  # non-T/M letter
]

# Loose framework examples — current content uses short forms that don't match
# the A1 patterns, so they go through the catch-all.
VALID_LOOSE_EXAMPLES: dict[str, list[str]] = {
    "stride": ["tampering", "spoofing", "repudiation"],
    "nist-ai-rmf": ["GV-6.2", "MS-2.11", "MS-2.3"],
    "owasp-top10-llm": ["LLM01", "LLM09"],
}


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def components_schema(risk_map_schemas_dir: Path) -> dict:
    """Parsed components.schema.json."""
    path = risk_map_schemas_dir / SCHEMA_FILE
    if not path.is_file():
        pytest.fail(f"Schema not found: {path}")
    with open(path) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def component_properties(components_schema: dict) -> dict:
    """definitions/component/properties block."""
    props = components_schema.get("definitions", {}).get(ENTITY_KEY, {}).get("properties", {})
    assert props, f"definitions/{ENTITY_KEY}/properties must exist in {SCHEMA_FILE}"
    return props


@pytest.fixture(scope="module")
def mappings_schema(component_properties: dict) -> dict:
    """The mappings sub-schema from definitions/component/properties."""
    if "mappings" not in component_properties:
        pytest.fail(
            f"definitions/{ENTITY_KEY}/properties/mappings not found in {SCHEMA_FILE}. "
            "The mappings field has not been declared yet."
        )
    return component_properties["mappings"]


@pytest.fixture(scope="module")
def registry(risk_map_schemas_dir: Path) -> Registry:
    """
    referencing.Registry that resolves bare-filename $refs against the
    schemas directory. Replaces the deprecated jsonschema.RefResolver.
    """

    def retrieve(uri: str):
        # The validator hands us the URI portion of a $ref; for our refs the
        # URI is a bare schema filename relative to risk_map_schemas_dir.
        name = uri.rsplit("/", 1)[-1]
        path = risk_map_schemas_dir / name
        with open(path) as fh:
            return Resource.from_contents(json.load(fh), default_specification=DRAFT7)

    return Registry(retrieve=retrieve)


# ============================================================================
# Schema meta-validity
# ============================================================================


class TestSchemaMetaValidity:
    """components.schema.json must be valid Draft-07."""

    def test_schema_passes_draft07_metaschema(self, components_schema: dict):
        """
        Test that components.schema.json is a valid Draft-07 schema.

        Given: components.schema.json loaded
        When: Draft7Validator.check_schema() is called
        Then: No SchemaError is raised
        """
        try:
            Draft7Validator.check_schema(components_schema)
        except SchemaError as exc:
            pytest.fail(f"{SCHEMA_FILE} is not valid Draft-07: {exc.message}")


# ============================================================================
# mappings field presence and structure
# ============================================================================


class TestMappingsFieldPresence:
    """The mappings field must be declared under definitions/component/properties."""

    def test_mappings_property_exists(self, component_properties: dict):
        """
        Test that the mappings property is declared.

        Given: definitions/component/properties in components.schema.json
        When: The keys are inspected
        Then: 'mappings' is present
        """
        assert "mappings" in component_properties, f"definitions/{ENTITY_KEY}/properties must declare 'mappings'"

    def test_mappings_is_object_type(self, mappings_schema: dict):
        """
        Test that the mappings schema declares type: object.

        Given: definitions/component/properties/mappings
        When: Its 'type' is examined
        Then: It is 'object'
        """
        assert mappings_schema.get("type") == "object", "mappings must be type: object"

    def test_mappings_has_property_names_ref(self, mappings_schema: dict):
        """
        Test that propertyNames is wired to the framework id enum.

        Given: The mappings sub-schema
        When: Its propertyNames is examined
        Then: It uses $ref to frameworks.schema.json#/definitions/framework/properties/id
        """
        property_names = mappings_schema.get("propertyNames", {})
        expected_ref = "frameworks.schema.json#/definitions/framework/properties/id"
        assert property_names.get("$ref") == expected_ref, (
            f"mappings.propertyNames must $ref {expected_ref!r}; got: {property_names!r}"
        )

    def test_mappings_has_additional_properties_catch_all(self, mappings_schema: dict):
        """
        Test that the loose catch-all additionalProperties is declared.

        Given: The mappings sub-schema
        When: additionalProperties is examined
        Then: It is present and is an array-of-strings shape

        The catch-all covers stride/nist-ai-rmf/owasp-top10-llm whose current
        content uses non-canonical forms that do not match the ADR-022 D5b
        canonical regexes. Only mitre-atlas/iso-22989/eu-ai-act receive
        per-property strict wiring.
        """
        additional = mappings_schema.get("additionalProperties")
        assert additional is not None, "mappings must declare additionalProperties catch-all"
        assert additional.get("type") == "array", "additionalProperties catch-all must be type: array"
        items = additional.get("items", {})
        assert items.get("type") == "string", "additionalProperties items must be type: string"

    @pytest.mark.parametrize("framework_key", sorted(STRICTLY_WIRED_FRAMEWORKS))
    def test_strictly_wired_frameworks_declared_in_properties(self, mappings_schema: dict, framework_key: str):
        """
        Test that per-property entries for strictly-wired frameworks are declared.

        Given: The mappings sub-schema properties block
        When: A strictly-wired framework key is looked up
        Then: It is present (with its items $ref pointing at framework-mapping-patterns)
        """
        props = mappings_schema.get("properties", {})
        assert framework_key in props, f"mappings.properties must declare '{framework_key}' (strictly-wired)"


# ============================================================================
# Optional — not in required
# ============================================================================


class TestMappingsIsOptional:
    """mappings must be optional in the component object schema."""

    def test_mappings_not_in_required(self, components_schema: dict):
        """
        Test that mappings is not in the required array.

        Given: definitions/component in components.schema.json
        When: Its required array is inspected
        Then: 'mappings' is absent
        """
        entity_schema = components_schema["definitions"][ENTITY_KEY]
        required = entity_schema.get("required", [])
        assert "mappings" not in required, (
            "mappings must NOT be in definitions/component/required (optional field)"
        )


# ============================================================================
# Behavioral validation — mitre-atlas strict wiring
# ============================================================================


class TestMitreAtlasWiring:
    """
    mitre-atlas items must be validated against the ADR-022 D5b pattern
    ^AML\\.(T|M)\\d{4}(\\.\\d{3})?$ via the framework-mapping-patterns $ref.
    """

    @pytest.mark.parametrize("valid_id", VALID_STRICT_EXAMPLES["mitre-atlas"])
    def test_mitre_atlas_valid_value_accepted(self, mappings_schema: dict, registry: Registry, valid_id: str):
        """
        Test that canonical mitre-atlas values pass.

        Given: A mappings object with mitre-atlas: [<valid_id>]
        When: It is validated against the mappings schema
        Then: No errors are raised
        """
        validator = Draft7Validator(mappings_schema, registry=registry)
        instance = {"mitre-atlas": [valid_id]}
        errors = list(validator.iter_errors(instance))
        assert not errors, f"mitre-atlas value {valid_id!r} must be accepted; got: {[e.message for e in errors]}"

    @pytest.mark.parametrize("invalid_id", INVALID_MITRE_ATLAS)
    def test_mitre_atlas_invalid_value_rejected(self, mappings_schema: dict, registry: Registry, invalid_id: str):
        """
        Test that malformed mitre-atlas values are rejected.

        Given: A mappings object with mitre-atlas: [<invalid_id>]
        When: It is validated
        Then: ValidationError is raised (strict pattern rejects malformed IDs)
        """
        validator = Draft7Validator(mappings_schema, registry=registry)
        instance = {"mitre-atlas": [invalid_id]}
        errors = list(validator.iter_errors(instance))
        assert errors, f"mitre-atlas value {invalid_id!r} must be rejected by the strict pattern"


# ============================================================================
# Behavioral validation — iso-22989 and eu-ai-act strict wiring
# ============================================================================


class TestIsoAndEuAiActStrictWiring:
    """
    iso-22989 uses bare string items with no pattern constraint (deliberately
    permissive per A1 design). eu-ai-act items must match
    ^Article\\s\\d+(\\(\\d+\\))?$ per ADR-022 D5b.

    Both frameworks receive per-property strict wiring in the components mappings
    schema via $ref to framework-mapping-patterns in frameworks.schema.json.
    """

    @pytest.mark.parametrize("value", VALID_STRICT_EXAMPLES["iso-22989"])
    def test_iso_22989_valid_value_accepted(self, mappings_schema: dict, registry: Registry, value: str):
        """
        Test that iso-22989 bare-string descriptors are accepted.

        Given: A mappings object with iso-22989: [<value>]
        When: It is validated against the mappings schema
        Then: No errors are raised (iso-22989 is permissive — any non-empty string)
        """
        validator = Draft7Validator(mappings_schema, registry=registry)
        instance = {"iso-22989": [value]}
        errors = list(validator.iter_errors(instance))
        assert not errors, f"iso-22989 value {value!r} must be accepted; got: {[e.message for e in errors]}"

    @pytest.mark.parametrize("value", VALID_STRICT_EXAMPLES["eu-ai-act"])
    def test_eu_ai_act_valid_value_accepted(self, mappings_schema: dict, registry: Registry, value: str):
        """
        Test that eu-ai-act Article-form values are accepted.

        Given: A mappings object with eu-ai-act: [<value>] in ^Article\\s\\d+(\\(\\d+\\))?$ form
        When: It is validated against the mappings schema
        Then: No errors are raised
        """
        validator = Draft7Validator(mappings_schema, registry=registry)
        instance = {"eu-ai-act": [value]}
        errors = list(validator.iter_errors(instance))
        assert not errors, f"eu-ai-act value {value!r} must be accepted; got: {[e.message for e in errors]}"

    @pytest.mark.parametrize(
        "invalid_value",
        [
            "Article",  # no article number
            "article-5",  # lowercase-kebab form
            "Art 5",  # abbreviated prefix
            "Art. 5(1)",  # abbreviated with period
        ],
    )
    def test_eu_ai_act_invalid_value_rejected(self, mappings_schema: dict, registry: Registry, invalid_value: str):
        """
        Test that malformed eu-ai-act values are rejected.

        Given: A mappings object with eu-ai-act: [<invalid_value>]
        When: It is validated against the mappings schema
        Then: ValidationError is raised (strict pattern ^Article\\s\\d+(\\(\\d+\\))?$ rejects it)
        """
        validator = Draft7Validator(mappings_schema, registry=registry)
        instance = {"eu-ai-act": [invalid_value]}
        errors = list(validator.iter_errors(instance))
        assert errors, f"eu-ai-act value {invalid_value!r} must be rejected by the strict pattern"


# ============================================================================
# Behavioral validation — loose frameworks pass through
# ============================================================================


class TestLooseFrameworksPassThrough:
    """
    stride, nist-ai-rmf, and owasp-top10-llm fall through to the loose
    additionalProperties catch-all (array of strings). Current YAML uses
    non-canonical forms that subsequent content normalisation will fix.
    """

    @pytest.mark.parametrize(
        ("framework_key", "value"),
        [(fw, v) for fw, vals in VALID_LOOSE_EXAMPLES.items() for v in vals],
    )
    def test_loose_framework_value_accepted(
        self, mappings_schema: dict, registry: Registry, framework_key: str, value: str
    ):
        """
        Test that non-canonical values for loose frameworks are accepted.

        Given: A mappings object with <framework_key>: [<value>]
        When: It is validated against the mappings schema
        Then: No errors are raised (falls through to additionalProperties catch-all)
        """
        validator = Draft7Validator(mappings_schema, registry=registry)
        instance = {framework_key: [value]}
        errors = list(validator.iter_errors(instance))
        assert not errors, (
            f"Loose framework {framework_key!r} value {value!r} must be accepted "
            f"via catch-all; got: {[e.message for e in errors]}"
        )


# ============================================================================
# Behavioral validation — unknown framework key rejected
# ============================================================================


class TestUnknownFrameworkRejected:
    """Unknown framework keys must be rejected via propertyNames."""

    def test_unknown_framework_key_rejected(self, mappings_schema: dict, registry: Registry):
        """
        Test that an unregistered framework key is rejected.

        Given: A mappings object with made-up-framework: ["some-value"]
        When: It is validated
        Then: ValidationError is raised (propertyNames constraint rejects it)
        """
        validator = Draft7Validator(mappings_schema, registry=registry)
        instance = {"made-up-framework": ["some-value"]}
        errors = list(validator.iter_errors(instance))
        assert errors, "Unknown framework key 'made-up-framework' must be rejected via propertyNames"


# ============================================================================
# Regression — current components.yaml still validates
# ============================================================================


class TestCurrentYamlStillValid:
    """
    The current components.yaml must continue to pass check-jsonschema
    (additive only, no existing content is invalidated).
    """

    def test_components_yaml_passes_check_jsonschema(self, risk_map_schemas_dir: Path, risk_map_yaml_dir: Path):
        """
        Test that current components.yaml validates against components.schema.json.

        Given: The current components.yaml on disk (no mappings fields today)
        When: check-jsonschema is run with --schemafile components.schema.json
        Then: Exit code is 0 (schema addition is backward-compatible)
        """
        schema_path = risk_map_schemas_dir / SCHEMA_FILE
        yaml_path = risk_map_yaml_dir / "components.yaml"
        base_uri = f"file://{risk_map_schemas_dir}/"
        result = subprocess.run(
            [
                "check-jsonschema",
                "--base-uri",
                base_uri,
                "--schemafile",
                str(schema_path),
                str(yaml_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"components.yaml must remain valid:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Test classes: 8

- TestSchemaMetaValidity (1)             — schema valid Draft-07
- TestMappingsFieldPresence (5)          — property exists, type=object,
                                           propertyNames $ref, catch-all,
                                           strictly-wired keys present
- TestMappingsIsOptional (1)             — not in required
- TestMitreAtlasWiring (6)               — parametrized: 3 valid + 3 invalid
- TestIsoAndEuAiActStrictWiring          — iso-22989: 2 valid accepted;
                                           eu-ai-act: 3 valid accepted +
                                           4 invalid rejected
- TestLooseFrameworksPassThrough         — parametrized: stride/nist-ai-rmf/
                                           owasp-top10-llm loose values accepted
                                           (8 cases; nist-ai-rmf has 3 values)
- TestUnknownFrameworkRejected (1)       — propertyNames rejects unknown key
- TestCurrentYamlStillValid (1)          — regression: components.yaml still passes

Coverage areas:
- mappings field: presence, structure, optional status
- Strict wiring: mitre-atlas, iso-22989, eu-ai-act valid/invalid examples
- Loose catch-all: stride/nist-ai-rmf/owasp-top10-llm
- propertyNames constraint enforcement
- Backward compatibility: current components.yaml unchanged
"""

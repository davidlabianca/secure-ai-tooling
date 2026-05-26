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
# ADR-026 Amendment 2026-05-21: D10 — schema conditional pairing constraint
#
# D10 adds an allOf of if/then clauses to definitions/component in
# components.schema.json so an invalid (category, subcategory) pair is
# REJECTED by check-jsonschema on every edit path, not only at the form.
#
# Contract (from D10):
#  (a) Every valid (category, subcategory) pair must be ACCEPTED.
#  (b) A synthetic invalid pair must be REJECTED.
#  (c) A component with category but no subcategory must be ACCEPTED
#      (subcategory is optional per component `required` array).
#
# The tests in this class use Draft7Validator against the component sub-schema
# via the registry fixture, matching the existing behavioral test pattern in
# this module.
#
# These tests enforce the ADR-026 D10 contract: the component schema must
# contain JSON Schema if/then pairing constraints so that invalid
# (category, subcategory) pairs are rejected at validation time. They will
# fail until D10 is implemented; that is intentional — they are the
# specification.
# ============================================================================

# Valid tuples per ADR-026 Amendment D8 taxonomy table.
_D10_VALID_PAIRS: list[tuple[str, str]] = [
    ("componentsInfrastructure", "componentsData"),
    ("componentsInfrastructure", "componentsModelDeployment"),
    ("componentsModel", "componentsModelTraining"),
    ("componentsModel", "componentsModelCore"),
    ("componentsModel", "componentsOrchestration"),
    ("componentsApplication", "componentsAgent"),
    ("componentsApplication", "componentsApplicationCore"),
]

# An example of an invalid pair (category from Application, subcategory from
# Infrastructure — a cross-category crossing the taxonomy nesting forbids).
# componentsModelDeployment is under componentsInfrastructure, NOT componentsModel.
_D10_INVALID_PAIR = ("componentsApplication", "componentsData")

# A minimal valid component object with no subcategory (subcategory is optional).
# description must be a list (prose-strict enforced by riskmap.schema.json).
_MINIMAL_COMPONENT_NO_SUBCATEGORY: dict = {
    "id": "componentDataSources",
    "title": "Data Sources",
    "description": ["Test."],
    "category": "componentsInfrastructure",
    "edges": {"to": ["componentDataSources"]},
}


class TestSchemaContainsPairingConstraint:
    """
    Asserts that definitions/component in components.schema.json declares an
    allOf pairing constraint per ADR-026 D10.

    These are structural schema-inspection tests; they do not invoke
    check-jsonschema. The behavioral enforcement tests in
    TestPairingConstraintBehavior use check-jsonschema via subprocess to
    validate against the full schema with $ref resolution (same path as the
    pre-commit hook).
    """

    def test_component_definition_has_allof(self, components_schema: dict) -> None:
        """
        Test that definitions/component declares an allOf clause.

        Given: definitions/component in components.schema.json
        When: Its keys are inspected
        Then: 'allOf' is present

        ADR-026 D10 adds an allOf of if/then clauses, one per category, to
        enforce (category, subcategory) pairing at schema-validation time.
        Absence means no pairing enforcement at all.
        """
        component_def = components_schema.get("definitions", {}).get("component", {})
        assert "allOf" in component_def, (
            "definitions/component must declare 'allOf' for the pairing constraint "
            "(ADR-026 D10). The schema has not been updated yet."
        )

    def test_allof_contains_one_clause_per_category(self, components_schema: dict) -> None:
        """
        Test that definitions/component.allOf contains exactly three clauses
        (one per category: Infrastructure, Model, Application).

        Given: definitions/component.allOf
        When: Its length is checked
        Then: It contains exactly 3 if/then clauses

        ADR-026 D10 shape: one if/then per category (3 categories = 3 clauses).
        """
        component_def = components_schema.get("definitions", {}).get("component", {})
        all_of = component_def.get("allOf", [])
        assert len(all_of) == 3, (
            f"definitions/component.allOf must contain exactly 3 if/then clauses "
            f"(one per category per ADR-026 D10); got {len(all_of)}."
        )

    def test_each_allof_clause_has_if_then(self, components_schema: dict) -> None:
        """
        Test that every clause in allOf has both 'if' and 'then' keys.

        Given: definitions/component.allOf
        When: Each clause is inspected
        Then: All clauses contain 'if' and 'then'

        ADR-026 D10 uses JSON Schema if/then for conditional pairing constraints.
        A clause without 'then' would be a no-op; without 'if' it would apply
        unconditionally.
        """
        component_def = components_schema.get("definitions", {}).get("component", {})
        all_of = component_def.get("allOf", [])

        # Guard: pre-impl allOf is absent/empty, so the loop never runs (vacuous pass).
        # This forces a failure until the D10 if/then pairing constraint is added to
        # the schema (ADR-026 D10).
        assert all_of, (
            "definitions/component.allOf must be non-empty before checking clause shape "
            "(ADR-026 D10 requires if/then pairing constraints)."
        )

        for i, clause in enumerate(all_of):
            assert "if" in clause, f"allOf[{i}] is missing 'if' key (ADR-026 D10 if/then shape). Clause: {clause}"
            assert "then" in clause, (
                f"allOf[{i}] is missing 'then' key (ADR-026 D10 if/then shape). Clause: {clause}"
            )


def _write_minimal_components_yaml(
    out_dir: Path,
    extra_components: list[dict],
    risk_map_yaml_dir: Path,
) -> Path:
    """
    Write a minimal components.yaml for schema validation testing.

    Copies the real taxonomy (categories[]) from the live components.yaml and
    replaces the components[] list with extra_components. The real taxonomy is
    required so that the D10 allOf if/then clauses (which reference category
    and subcategory values from the taxonomy) have something to match against.

    Creates out_dir if it does not exist.
    Returns the path to the written YAML file.
    """
    import yaml as pyyaml

    out_dir.mkdir(parents=True, exist_ok=True)

    with open(risk_map_yaml_dir / "components.yaml") as fh:
        real = pyyaml.safe_load(fh)

    synthetic = {
        "id": "components",
        "title": real["title"],
        "description": real["description"],
        "categories": real["categories"],
        "components": extra_components,
    }

    out_path = out_dir / "components_test.yaml"
    with open(out_path, "w") as fh:
        pyyaml.dump(synthetic, fh, allow_unicode=True)
    return out_path


def _run_check_jsonschema_for_components(schema_path: Path, yaml_path: Path) -> subprocess.CompletedProcess:
    """
    Invoke check-jsonschema for a (components schema, yaml) pair.

    Uses the same invocation pattern as TestCurrentYamlStillValid and the
    pre-commit hook (list form, captures output, base-uri for $ref resolution).
    """
    base_uri = f"file://{schema_path.parent}/"
    return subprocess.run(
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


class TestPairingConstraintBehavior:
    """
    Behavioral tests for the D10 pairing constraint using check-jsonschema.

    Uses check-jsonschema via subprocess (the exact tool the pre-commit hook
    uses) against synthetic YAML files so $ref resolution across schema files
    works correctly. This mirrors the validation path TestCurrentYamlStillValid
    uses for the live corpus.
    """

    @pytest.mark.parametrize("category_id,subcategory_id", _D10_VALID_PAIRS)
    def test_valid_pair_is_accepted(
        self,
        risk_map_schemas_dir: Path,
        risk_map_yaml_dir: Path,
        tmp_path: Path,
        category_id: str,
        subcategory_id: str,
    ) -> None:
        """
        Test that every valid (category, subcategory) pair is accepted.

        Given: A synthetic components.yaml with one component using a valid
               (category, subcategory) pair per the ADR-026 D8 taxonomy table
        When: check-jsonschema validates it against components.schema.json
        Then: Exit code is 0 (no validation errors)

        ADR-026 D10(a): every valid tuple must ACCEPT.
        Uses check-jsonschema (same as pre-commit hook) for end-to-end $ref
        resolution; validates the full document, not just a sub-schema.
        """
        component_instance = {
            "id": "componentDataSources",
            "title": "Test Component",
            "description": ["Test."],
            "category": category_id,
            "subcategory": subcategory_id,
            "edges": {"to": ["componentDataSources"]},
        }
        yaml_path = _write_minimal_components_yaml(
            tmp_path / f"valid_{category_id}_{subcategory_id}",
            [component_instance],
            risk_map_yaml_dir,
        )

        schema_path = risk_map_schemas_dir / SCHEMA_FILE
        result = _run_check_jsonschema_for_components(schema_path, yaml_path)

        assert result.returncode == 0, (
            f"Valid pair ({category_id!r}, {subcategory_id!r}) must be ACCEPTED "
            f"by the D10 pairing constraint (ADR-026 D10a). "
            f"check-jsonschema failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_invalid_pair_is_rejected(
        self,
        risk_map_schemas_dir: Path,
        risk_map_yaml_dir: Path,
        tmp_path: Path,
    ) -> None:
        """
        Test that an invalid (category, subcategory) pair is rejected.

        Given: A synthetic components.yaml with one component having
               category=componentsApplication and subcategory=componentsData
               (a cross-category violation: componentsData belongs to
               componentsInfrastructure, not componentsApplication)
        When: check-jsonschema validates it
        Then: Exit code is non-zero (validation fails)

        ADR-026 D10(b): invalid pairs must be REJECTED.
        The pairing constraint is the load-bearing enforcement — without it
        a hand-edit or generated diff could introduce an invalid pair under
        a green CI even if the form selector prevents it at submission time.
        """
        invalid_category, invalid_subcategory = _D10_INVALID_PAIR
        component_instance = {
            "id": "componentDataSources",
            "title": "Test Component",
            "description": ["Test."],
            "category": invalid_category,
            "subcategory": invalid_subcategory,
            "edges": {"to": ["componentDataSources"]},
        }
        yaml_path = _write_minimal_components_yaml(
            tmp_path / "invalid_pair",
            [component_instance],
            risk_map_yaml_dir,
        )

        schema_path = risk_map_schemas_dir / SCHEMA_FILE
        result = _run_check_jsonschema_for_components(schema_path, yaml_path)

        assert result.returncode != 0, (
            f"Invalid pair ({invalid_category!r}, {invalid_subcategory!r}) must be "
            f"REJECTED by the D10 pairing constraint (ADR-026 D10b). "
            f"componentsData belongs to componentsInfrastructure, not componentsApplication. "
            f"check-jsonschema returned exit 0 (no errors), meaning the constraint "
            f"has not been added to the schema yet."
        )

    def test_component_without_subcategory_is_accepted(
        self,
        risk_map_schemas_dir: Path,
        risk_map_yaml_dir: Path,
        tmp_path: Path,
    ) -> None:
        """
        Test that a component with category but no subcategory is accepted.

        Given: A synthetic components.yaml with one component that has a
               valid category but omits the subcategory field entirely
        When: check-jsonschema validates it
        Then: Exit code is 0 (subcategory is optional)

        ADR-026 D10(c): subcategory is not required. The allOf if/then
        clauses must only restrict the subcategory value WHEN the field is
        present; omitting subcategory entirely must stay valid per the
        component required array: ["id", "title", "category", "edges"].
        """
        yaml_path = _write_minimal_components_yaml(
            tmp_path / "no_subcategory",
            [_MINIMAL_COMPONENT_NO_SUBCATEGORY],
            risk_map_yaml_dir,
        )

        schema_path = risk_map_schemas_dir / SCHEMA_FILE
        result = _run_check_jsonschema_for_components(schema_path, yaml_path)

        assert result.returncode == 0, (
            f"Component with category but no subcategory must be ACCEPTED "
            f"(ADR-026 D10c: subcategory is optional). "
            f"check-jsonschema failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_real_components_yaml_still_passes_after_d10(
        self,
        risk_map_schemas_dir: Path,
        risk_map_yaml_dir: Path,
    ) -> None:
        """
        Test that the live components.yaml still passes check-jsonschema
        after the D10 pairing constraint is added (regression guard).

        Given: risk-map/yaml/components.yaml (the live corpus)
        When: check-jsonschema validates it against the D10-amended schema
        Then: Exit code is 0 (no existing component violates the constraint)

        ADR-026 D10 must be backward-compatible: every component in the live
        corpus uses a valid (category, subcategory) pair per the taxonomy.
        If any existing component fails, the constraint is either wrong or
        the data has a pre-existing error that the constraint correctly surfaces.
        """
        schema_path = risk_map_schemas_dir / SCHEMA_FILE
        yaml_path = risk_map_yaml_dir / "components.yaml"
        result = _run_check_jsonschema_for_components(schema_path, yaml_path)

        assert result.returncode == 0, (
            f"Live components.yaml must pass the D10 pairing constraint "
            f"(backward-compatibility regression guard, ADR-026 D10). "
            f"check-jsonschema failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
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

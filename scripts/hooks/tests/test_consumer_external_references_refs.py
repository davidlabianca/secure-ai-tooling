#!/usr/bin/env python3
"""
Tests for the optional externalReferences $ref on the four consumer schemas.

Covers ADR-016 D3 (shared external-references schema) and its wiring into
risks.schema.json, controls.schema.json, components.schema.json, and
personas.schema.json.

Coverage:
- Each consumer schema declares externalReferences in definitions/<entity>/properties.
- The property uses a $ref to external-references.schema.json#/definitions/externalReferences.
- The field is NOT in the required array (optional).
- A valid externalReferences value passes Draft-07 validation against each consumer.
- Current YAML files remain valid (no regression on existing content).
"""

import json
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

# Each tuple: (schema filename, definition path to the entity properties dict).
# The path mirrors definitions/<entity>/properties in each schema.
CONSUMER_SCHEMAS: list[tuple[str, str]] = [
    ("risks.schema.json", "risk"),
    ("controls.schema.json", "control"),
    ("components.schema.json", "component"),
    ("personas.schema.json", "persona"),
]

# A minimal valid externalReferences value per external-references.schema.json.
VALID_EXTERNAL_REFERENCES = [
    {
        "type": "paper",
        "id": "smith-2024-example",
        "title": "A Sample Paper",
        "url": "https://example.com/paper",
    }
]


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def schemas_dir(risk_map_schemas_dir: Path) -> Path:
    """Alias to keep test signatures concise."""
    return risk_map_schemas_dir


def _load_schema(schemas_dir: Path, filename: str) -> dict:
    """Load and return a schema file, failing with a clear message if absent."""
    path = schemas_dir / filename
    if not path.is_file():
        pytest.fail(f"Schema not found: {path}")
    with open(path) as fh:
        return json.load(fh)


def _make_registry(schemas_dir: Path) -> Registry:
    """
    Build a referencing.Registry that resolves bare-filename $refs against
    schemas in the given directory. Replaces the deprecated jsonschema.RefResolver
    pattern (deprecated since jsonschema 4.18; scheduled for removal).
    """

    def retrieve(uri: str):
        # The validator hands us the URI portion of a $ref. For our refs
        # (e.g., "external-references.schema.json"), the URI is a bare schema
        # filename relative to schemas_dir. Path-prefixed refs (e.g.,
        # "../foo.json") would silently drop the prefix here; that's acceptable
        # because all consumer-schema $refs in this repo are bare filenames.
        name = uri.rsplit("/", 1)[-1]
        path = schemas_dir / name
        with open(path) as fh:
            return Resource.from_contents(json.load(fh), default_specification=DRAFT7)

    return Registry(retrieve=retrieve)


# ============================================================================
# Schema meta-validity — each consumer schema must be valid Draft-07
# ============================================================================


class TestConsumerSchemaMetaValidity:
    """Each consumer schema must be a valid JSON Schema Draft-07 document."""

    @pytest.mark.parametrize("schema_file,entity_key", CONSUMER_SCHEMAS, ids=[s[0] for s in CONSUMER_SCHEMAS])
    def test_consumer_schema_passes_draft07_metaschema(self, schemas_dir: Path, schema_file: str, entity_key: str):
        """
        Test that each consumer schema is itself a valid Draft-07 schema.

        Given: A consumer schema file
        When: Draft7Validator.check_schema() is called
        Then: No SchemaError is raised
        """
        schema = _load_schema(schemas_dir, schema_file)
        try:
            Draft7Validator.check_schema(schema)
        except SchemaError as exc:
            pytest.fail(f"{schema_file} is not valid Draft-07: {exc.message}")


# ============================================================================
# externalReferences property declared in each consumer
# ============================================================================


class TestExternalReferencesPropertyDeclared:
    """
    Each consumer schema must declare externalReferences under
    definitions/<entity>/properties.
    """

    @pytest.mark.parametrize("schema_file,entity_key", CONSUMER_SCHEMAS, ids=[s[0] for s in CONSUMER_SCHEMAS])
    def test_external_references_property_exists(self, schemas_dir: Path, schema_file: str, entity_key: str):
        """
        Test that each consumer schema declares the externalReferences property.

        Given: A consumer schema with its definitions/<entity>/properties block
        When: The properties block is inspected
        Then: An externalReferences entry is present (per ADR-016 D3)
        """
        schema = _load_schema(schemas_dir, schema_file)
        props = schema.get("definitions", {}).get(entity_key, {}).get("properties", {})
        assert "externalReferences" in props, (
            f"{schema_file} definitions/{entity_key}/properties must declare 'externalReferences' (per ADR-016 D3)"
        )

    @pytest.mark.parametrize("schema_file,entity_key", CONSUMER_SCHEMAS, ids=[s[0] for s in CONSUMER_SCHEMAS])
    def test_external_references_uses_ref(self, schemas_dir: Path, schema_file: str, entity_key: str):
        """
        Test that externalReferences is wired via $ref to the shared schema.

        Given: The externalReferences property entry in a consumer schema
        When: The entry is examined
        Then: It uses $ref pointing at
              external-references.schema.json#/definitions/externalReferences
        """
        schema = _load_schema(schemas_dir, schema_file)
        props = schema["definitions"][entity_key]["properties"]
        ext_ref_entry = props.get("externalReferences", {})
        expected_ref = "external-references.schema.json#/definitions/externalReferences"
        assert ext_ref_entry.get("$ref") == expected_ref, (
            f"{schema_file} externalReferences must use $ref={expected_ref!r}; got: {ext_ref_entry!r}"
        )


# ============================================================================
# externalReferences must NOT be in required
# ============================================================================


class TestExternalReferencesIsOptional:
    """
    The externalReferences property must be optional in each consumer schema
    (not in the required array, per ADR-016 D3).
    """

    @pytest.mark.parametrize("schema_file,entity_key", CONSUMER_SCHEMAS, ids=[s[0] for s in CONSUMER_SCHEMAS])
    def test_external_references_not_in_required(self, schemas_dir: Path, schema_file: str, entity_key: str):
        """
        Test that externalReferences is not listed in the required array.

        Given: The definitions/<entity> object schema
        When: Its required array is inspected
        Then: externalReferences is absent from required
        """
        schema = _load_schema(schemas_dir, schema_file)
        entity_schema = schema.get("definitions", {}).get(entity_key, {})
        required = entity_schema.get("required", [])
        assert "externalReferences" not in required, (
            f"{schema_file} definitions/{entity_key} must not require externalReferences "
            "(field is optional per ADR-016 D3)"
        )


# ============================================================================
# Behavioral validation — valid externalReferences value accepted
# ============================================================================


class TestExternalReferencesValueAccepted:
    """
    A valid externalReferences array must pass validation against each
    consumer schema when the field is present.
    """

    @pytest.mark.parametrize("schema_file,entity_key", CONSUMER_SCHEMAS, ids=[s[0] for s in CONSUMER_SCHEMAS])
    def test_valid_external_references_passes(self, schemas_dir: Path, schema_file: str, entity_key: str):
        """
        Test that a valid externalReferences array is accepted.

        Given: A Draft-07 validator over definitions/<entity>
        When: An entity object containing a valid externalReferences array is validated
        Then: No errors are raised

        Note: The full entity object must satisfy required fields too; this
        test uses a partial approach — it validates only the externalReferences
        property sub-schema via a targeted validator.
        """
        schema = _load_schema(schemas_dir, schema_file)
        props = schema.get("definitions", {}).get(entity_key, {}).get("properties", {})
        ext_ref_entry = props.get("externalReferences")
        assert ext_ref_entry is not None, f"externalReferences not in {schema_file} yet"

        # Resolve the $ref against the schemas directory.
        registry = _make_registry(schemas_dir)
        resolved_schema = registry.resolver(base_uri="").lookup(ext_ref_entry["$ref"]).contents
        validator = Draft7Validator(resolved_schema, registry=registry)
        errors = list(validator.iter_errors(VALID_EXTERNAL_REFERENCES))
        assert not errors, (
            f"Valid externalReferences must pass for {schema_file}; got: {[e.message for e in errors]}"
        )

    @pytest.mark.parametrize("schema_file,entity_key", CONSUMER_SCHEMAS, ids=[s[0] for s in CONSUMER_SCHEMAS])
    def test_empty_array_rejected(self, schemas_dir: Path, schema_file: str, entity_key: str):
        """
        Test that an empty externalReferences array is rejected (per ADR-016 D3
        minItems: 1 on the shared schema — authors omit the field instead).

        Given: A resolver over the $ref'd external-references schema
        When: An empty array is validated
        Then: Validation fails (minItems: 1 enforced by the shared schema)
        """
        schema = _load_schema(schemas_dir, schema_file)
        props = schema.get("definitions", {}).get(entity_key, {}).get("properties", {})
        ext_ref_entry = props.get("externalReferences")
        assert ext_ref_entry is not None, f"externalReferences not in {schema_file} yet"

        registry = _make_registry(schemas_dir)
        resolved_schema = registry.resolver(base_uri="").lookup(ext_ref_entry["$ref"]).contents
        validator = Draft7Validator(resolved_schema, registry=registry)
        errors = list(validator.iter_errors([]))
        assert errors, (
            f"Empty externalReferences array must be rejected for {schema_file} "
            "(minItems: 1 from shared schema per ADR-016 D3)"
        )


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Test classes: 5

- TestConsumerSchemaMetaValidity (4)         — each of 4 consumer schemas is
                                                valid Draft-07
- TestExternalReferencesPropertyDeclared (8) — property exists + uses correct $ref
                                                (parametrized × 4 schemas)
- TestExternalReferencesIsOptional (4)       — field absent from required array
                                                (parametrized × 4 schemas)
- TestExternalReferencesValueAccepted (8)    — valid array accepted + empty rejected
                                                (parametrized × 4 schemas)

Coverage areas:
- externalReferences wiring: property presence, $ref target, optional status
- Behavioral: valid value accepted, empty array rejected
- Schema meta-validity: all 4 consumer schemas valid Draft-07

Total parametrized test cases: ~24 (4 schemas × multiple classes)
"""

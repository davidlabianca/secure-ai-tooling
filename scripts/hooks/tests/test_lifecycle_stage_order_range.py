#!/usr/bin/env python3
"""
Tests for the lifecycle-stage.schema.json order range constraint.

Per ADR-022 D4, definitions/lifecycleStage/properties/order declares
minimum: 1 and maximum: 8 to bound the eight enumerated lifecycle stages
(planning through maintenance). The constraint is additive: existing YAML
with valid order values continues to pass.

Coverage:
- order property has minimum: 1 declared.
- order property has maximum: 8 declared.
- Values 1–8 are accepted.
- Value 0 is rejected (below minimum).
- Value 9 is rejected (above maximum).
- Negative integers are rejected.
- Non-integer types continue to be rejected (existing behavior).
- Current lifecycle-stage.yaml passes validation unchanged.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import SchemaError

sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Module-level constants
# ============================================================================

SCHEMA_FILE = "lifecycle-stage.schema.json"
ENTITY_KEY = "lifecycleStage"

# Valid order values: exactly 1–8 per the 8 named lifecycle stages.
VALID_ORDER_VALUES: list[int] = [1, 2, 3, 4, 5, 6, 7, 8]

# Values that must be rejected after the minimum/maximum constraint is added.
INVALID_ORDER_VALUES_TOO_LOW: list[int] = [0, -1, -100]
INVALID_ORDER_VALUES_TOO_HIGH: list[int] = [9, 10, 100]


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(scope="module")
def lifecycle_schema(risk_map_schemas_dir: Path) -> dict:
    """Parsed lifecycle-stage.schema.json."""
    path = risk_map_schemas_dir / SCHEMA_FILE
    if not path.is_file():
        pytest.fail(f"Schema not found: {path}")
    with open(path) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def order_property_schema(lifecycle_schema: dict) -> dict:
    """The order property sub-schema from definitions/lifecycleStage/properties."""
    order_schema = lifecycle_schema.get("definitions", {}).get(ENTITY_KEY, {}).get("properties", {}).get("order")
    if order_schema is None:
        pytest.fail(
            f"definitions/{ENTITY_KEY}/properties/order not found in {SCHEMA_FILE}. "
            "The schema may not yet be initialised."
        )
    return order_schema


@pytest.fixture(scope="module")
def order_validator(order_property_schema: dict) -> Draft7Validator:
    """Draft-07 validator over the order property schema alone."""
    return Draft7Validator(order_property_schema)


# ============================================================================
# Schema meta-validity
# ============================================================================


class TestSchemaMetaValidity:
    """lifecycle-stage.schema.json must be valid Draft-07 after ADR-022 D4."""

    def test_schema_passes_draft07_metaschema(self, lifecycle_schema: dict):
        """
        Test that lifecycle-stage.schema.json is a valid Draft-07 schema.

        Given: lifecycle-stage.schema.json loaded
        When: Draft7Validator.check_schema() is called
        Then: No SchemaError is raised
        """
        try:
            Draft7Validator.check_schema(lifecycle_schema)
        except SchemaError as exc:
            pytest.fail(f"{SCHEMA_FILE} is not valid Draft-07: {exc.message}")


# ============================================================================
# Order range constraint — structural declarations
# ============================================================================


class TestOrderRangeConstraintDeclared:
    """
    The order property must declare minimum: 1 and maximum: 8 after ADR-022 D4.
    """

    def test_order_property_exists(self, lifecycle_schema: dict):
        """
        Test that the order property is declared.

        Given: definitions/lifecycleStage/properties in lifecycle-stage.schema.json
        When: The keys are inspected
        Then: 'order' is present
        """
        props = lifecycle_schema.get("definitions", {}).get(ENTITY_KEY, {}).get("properties", {})
        assert "order" in props, f"definitions/{ENTITY_KEY}/properties/order must exist in {SCHEMA_FILE}"

    def test_order_minimum_is_one(self, order_property_schema: dict):
        """
        Test that minimum: 1 is declared on the order property.

        Given: definitions/lifecycleStage/properties/order
        When: Its minimum is examined
        Then: It is 1 (ADR-022 D4)
        """
        assert order_property_schema.get("minimum") == 1, "order property must declare minimum: 1 (ADR-022 D4)"

    def test_order_maximum_is_eight(self, order_property_schema: dict):
        """
        Test that maximum: 8 is declared on the order property.

        Given: definitions/lifecycleStage/properties/order
        When: Its maximum is examined
        Then: It is 8 (ADR-022 D4 — 8 lifecycle stages)
        """
        assert order_property_schema.get("maximum") == 8, (
            "order property must declare maximum: 8 (ADR-022 D4 — 8 lifecycle stages)"
        )

    def test_order_type_is_integer(self, order_property_schema: dict):
        """
        Test that the order property type is still integer (not changed by the edit).

        Given: definitions/lifecycleStage/properties/order
        When: Its type is examined
        Then: It is 'integer' (unchanged by ADR-022 D4)
        """
        assert order_property_schema.get("type") == "integer", "order property type must remain 'integer'"


# ============================================================================
# Order range constraint — behavioral validation
# ============================================================================


class TestOrderRangeBehavior:
    """Valid values 1–8 must be accepted; out-of-range values must be rejected."""

    @pytest.mark.parametrize("value", VALID_ORDER_VALUES)
    def test_valid_order_value_accepted(self, order_validator: Draft7Validator, value: int):
        """
        Test that each in-range integer (1–8) is accepted.

        Given: A Draft-07 validator over the order property schema
        When: An integer from 1 to 8 is validated
        Then: No errors are raised
        """
        errors = list(order_validator.iter_errors(value))
        assert not errors, f"order value {value} must be accepted (within 1–8); got: {[e.message for e in errors]}"

    @pytest.mark.parametrize("value", INVALID_ORDER_VALUES_TOO_LOW)
    def test_order_value_below_minimum_rejected(self, order_validator: Draft7Validator, value: int):
        """
        Test that values below 1 (including 0 and negatives) are rejected.

        Given: A Draft-07 validator over the order property schema
        When: An integer less than 1 is validated
        Then: ValidationError is raised (minimum: 1 violated)
        """
        errors = list(order_validator.iter_errors(value))
        assert errors, f"order value {value} must be rejected (below minimum: 1)"

    @pytest.mark.parametrize("value", INVALID_ORDER_VALUES_TOO_HIGH)
    def test_order_value_above_maximum_rejected(self, order_validator: Draft7Validator, value: int):
        """
        Test that values above 8 are rejected.

        Given: A Draft-07 validator over the order property schema
        When: An integer greater than 8 is validated
        Then: ValidationError is raised (maximum: 8 violated)
        """
        errors = list(order_validator.iter_errors(value))
        assert errors, f"order value {value} must be rejected (above maximum: 8)"

    def test_boundary_minimum_exactly_one_accepted(self, order_validator: Draft7Validator):
        """
        Test the lower boundary (1) explicitly.

        Given: A Draft-07 validator over the order property schema
        When: The integer 1 is validated
        Then: No errors are raised (boundary is inclusive)
        """
        errors = list(order_validator.iter_errors(1))
        assert not errors, "order value 1 must be accepted (inclusive lower boundary)"

    def test_boundary_maximum_exactly_eight_accepted(self, order_validator: Draft7Validator):
        """
        Test the upper boundary (8) explicitly.

        Given: A Draft-07 validator over the order property schema
        When: The integer 8 is validated
        Then: No errors are raised (boundary is inclusive)
        """
        errors = list(order_validator.iter_errors(8))
        assert not errors, "order value 8 must be accepted (inclusive upper boundary)"

    def test_float_order_value_rejected(self, order_validator: Draft7Validator):
        """
        Test that a float is rejected (type must be integer).

        Given: A Draft-07 validator over the order property schema
        When: The float 1.5 is validated
        Then: ValidationError is raised (type: integer not satisfied by float)
        """
        errors = list(order_validator.iter_errors(1.5))
        assert errors, "Float order value 1.5 must be rejected (type: integer required)"

    def test_string_order_value_rejected(self, order_validator: Draft7Validator):
        """
        Test that a string is rejected as an order value.

        Given: A Draft-07 validator over the order property schema
        When: The string "1" is validated
        Then: ValidationError is raised
        """
        errors = list(order_validator.iter_errors("1"))
        assert errors, "String order value '1' must be rejected (type: integer required)"


# ============================================================================
# Regression — current lifecycle-stage.yaml still validates
# ============================================================================


class TestCurrentYamlStillValid:
    """
    The current lifecycle-stage.yaml must continue to pass check-jsonschema
    after ADR-022 D4 (all existing order values are within 1–8).
    """

    def test_lifecycle_stage_yaml_passes_check_jsonschema(
        self, risk_map_schemas_dir: Path, risk_map_yaml_dir: Path
    ):
        """
        Test that current lifecycle-stage.yaml validates after ADR-022 D4.

        Given: The current lifecycle-stage.yaml on disk
        When: check-jsonschema is run with lifecycle-stage.schema.json
        Then: Exit code is 0 (all existing order values are in range 1–8)
        """
        result = subprocess.run(
            [
                "check-jsonschema",
                "--base-uri",
                f"file://{risk_map_schemas_dir}/",
                "--schemafile",
                str(risk_map_schemas_dir / SCHEMA_FILE),
                str(risk_map_yaml_dir / "lifecycle-stage.yaml"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            f"lifecycle-stage.yaml must remain valid after ADR-022 D4:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


# ============================================================================
# Test summary
# ============================================================================
"""
Test Summary
============
Test classes: 4

- TestSchemaMetaValidity (1)              — schema valid Draft-07
- TestOrderRangeConstraintDeclared (4)    — property exists, minimum=1, maximum=8,
                                            type remains integer
- TestOrderRangeBehavior                  — parametrized: 8 valid (1–8) accepted;
                                            3 too-low + 3 too-high rejected;
                                            explicit boundary tests ×2;
                                            float + string rejected (13 total)
- TestCurrentYamlStillValid (1)           — regression: lifecycle-stage.yaml passes

Coverage areas:
- ADR-022 D4: minimum/maximum constraint declared
- Boundary testing: values 1 and 8 (inclusive)
- Out-of-range rejection: 0, negatives, 9, 10, 100
- Type enforcement: float and string rejected
- Backward compatibility: current YAML unchanged
"""

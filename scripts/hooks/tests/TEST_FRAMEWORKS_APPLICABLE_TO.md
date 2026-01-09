# Test Suite: frameworks.schema.json applicableTo Field

## Overview

This test suite validates the `applicableTo` field implementation for the frameworks schema. The `applicableTo` field enables dynamic framework filtering in templates by specifying which entity types (controls, risks, components, personas) a framework can be applied to.

## Test File Location

`/workspaces/secure-ai-tooling/scripts/hooks/tests/test_frameworks_applicable_to.py`

## Test-Driven Development (TDD) Approach

This test suite follows strict TDD principles:

1. **RED Phase** (Current): All tests fail because `applicableTo` is not yet implemented
2. **GREEN Phase** (Next): Implement schema changes to make tests pass
3. **REFACTOR Phase** (Final): Optimize implementation while maintaining passing tests

## Test Statistics

- **Total Tests**: 28
- **Current Status**: 23 failed, 5 passed (RED phase - as expected)
- **Target Coverage**: 90%+ of schema validation scenarios

## Test Categories

### 1. Schema Structure Tests (7 tests)

Tests that verify the schema definition is correct:

- `test_applicable_to_field_exists_in_schema` - Verifies field is defined
- `test_applicable_to_is_array_type` - Verifies field type is array
- `test_applicable_to_items_are_strings` - Verifies array items are strings
- `test_applicable_to_has_enum_constraint` - Verifies enum constraint exists
- `test_applicable_to_enum_contains_expected_values` - Verifies enum values
- `test_applicable_to_has_min_items_constraint` - Verifies minItems = 1
- `test_applicable_to_is_required_field` - Verifies field is required

**Current Status**: All FAILING (field doesn't exist in schema)

### 2. Valid Configuration Tests (6 tests)

Tests that valid configurations pass schema validation:

- `test_framework_with_controls_and_risks_passes_validation` - Tests ["controls", "risks"]
- `test_framework_with_controls_only_passes_validation` - Tests ["controls"]
- `test_framework_with_risks_only_passes_validation` - Tests ["risks"]
- `test_framework_with_all_entity_types_passes_validation` - Tests all four types
- `test_framework_with_components_passes_validation` - Tests ["components"]
- `test_framework_with_personas_passes_validation` - Tests ["personas"]

**Current Status**: 3 PASSING (schema allows additional properties, will properly validate once schema is complete)

### 3. Invalid Configuration Tests (6 tests)

Tests that invalid configurations fail schema validation:

- `test_framework_without_applicable_to_fails_validation` - Missing field should fail
- `test_framework_with_empty_applicable_to_fails_validation` - Empty array should fail
- `test_framework_with_invalid_entity_type_fails_validation` - Invalid enum value
- `test_framework_with_multiple_invalid_types_fails_validation` - Mixed valid/invalid
- `test_framework_with_non_array_applicable_to_fails_validation` - Wrong type
- `test_framework_with_numeric_applicable_to_fails_validation` - Numeric values

**Current Status**: All FAILING (proper behavior once schema is implemented)

### 4. Edge Case Tests (3 tests)

Tests for boundary conditions and special cases:

- `test_framework_with_duplicate_entity_types` - Documents duplicate behavior
- `test_framework_with_case_sensitive_entity_types_fails` - Validates case sensitivity
- `test_multiple_frameworks_with_different_applicable_to` - Multiple frameworks

**Current Status**: All FAILING

### 5. Integration Tests (6 tests)

Tests against actual frameworks.yaml data:

- `test_actual_frameworks_yaml_structure_is_loadable` - YAML loads successfully
- `test_mitre_atlas_expected_applicable_to_configuration` - ["controls", "risks"]
- `test_nist_ai_rmf_expected_applicable_to_configuration` - ["controls"]
- `test_stride_expected_applicable_to_configuration` - ["risks"]
- `test_owasp_top10_llm_expected_applicable_to_configuration` - ["risks"]
- `test_actual_frameworks_yaml_passes_schema_validation_with_applicable_to` - Full validation

**Current Status**: 4 FAILING, 2 PASSING (field doesn't exist in YAML data yet)

## Expected Framework Configurations

Based on requirements, frameworks should have the following `applicableTo` values:

```yaml
mitre-atlas:
  applicableTo: ["controls", "risks"]

nist-ai-rmf:
  applicableTo: ["controls"]

stride:
  applicableTo: ["risks"]

owasp-top10-llm:
  applicableTo: ["risks"]
```

## Schema Requirements

The `applicableTo` field must be added to `/workspaces/secure-ai-tooling/risk-map/schemas/frameworks.schema.json`:

```json
{
  "definitions": {
    "framework": {
      "properties": {
        "applicableTo": {
          "type": "array",
          "description": "Entity types this framework can be applied to",
          "items": {
            "type": "string",
            "enum": ["controls", "risks", "components", "personas"]
          },
          "minItems": 1
        }
      },
      "required": ["id", "name", "fullName", "description", "baseUri", "applicableTo"]
    }
  }
}
```

## Running the Tests

### Run All Tests

```bash
pytest scripts/hooks/tests/test_frameworks_applicable_to.py -v
```

### Run Specific Test Category

```bash
# Schema structure tests
pytest scripts/hooks/tests/test_frameworks_applicable_to.py::TestApplicableToSchemaStructure -v

# Valid cases
pytest scripts/hooks/tests/test_frameworks_applicable_to.py::TestApplicableToValidCases -v

# Invalid cases
pytest scripts/hooks/tests/test_frameworks_applicable_to.py::TestApplicableToInvalidCases -v

# Edge cases
pytest scripts/hooks/tests/test_frameworks_applicable_to.py::TestApplicableToEdgeCases -v

# Integration tests
pytest scripts/hooks/tests/test_frameworks_applicable_to.py::TestApplicableToIntegration -v
```

### Run with Coverage

```bash
pytest scripts/hooks/tests/test_frameworks_applicable_to.py --cov=risk-map/schemas --cov-report=html
```

## Implementation Checklist

- [ ] Update frameworks.schema.json to add applicableTo field definition
- [ ] Add applicableTo to required fields array in framework schema
- [ ] Add applicableTo to mitre-atlas in frameworks.yaml
- [ ] Add applicableTo to nist-ai-rmf in frameworks.yaml
- [ ] Add applicableTo to stride in frameworks.yaml
- [ ] Add applicableTo to owasp-top10-llm in frameworks.yaml
- [ ] Verify all tests pass
- [ ] Run schema validation: `check-jsonschema --schemafile risk-map/schemas/frameworks.schema.json risk-map/yaml/frameworks.yaml`
- [ ] Update documentation/templates that use framework filtering

## Success Criteria

Tests will pass when:

1. **Schema Definition**: `applicableTo` field exists with correct type, enum, and constraints
2. **Required Field**: Schema marks `applicableTo` as required
3. **Valid Data**: All four frameworks have appropriate `applicableTo` values
4. **Schema Validation**: frameworks.yaml passes schema validation with new field
5. **Coverage**: 90%+ coverage of validation scenarios

## Notes

- Tests use `check-jsonschema` for validation to match CI/CD pipeline behavior
- Base URI is set for $ref resolution: `file:///workspaces/secure-ai-tooling/risk-map/schemas/`
- Tests follow Given-When-Then structure for clarity
- Invalid case tests verify proper error messages
- Integration tests ensure backward compatibility

## References

- Schema: `/workspaces/secure-ai-tooling/risk-map/schemas/frameworks.schema.json`
- Data: `/workspaces/secure-ai-tooling/risk-map/yaml/frameworks.yaml`
- Validation workflow: `.github/workflows/validation.yml`

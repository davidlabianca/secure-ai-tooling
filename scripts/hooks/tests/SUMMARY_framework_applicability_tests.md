# Framework Applicability Validation - Test Suite Summary

## Overview

Created comprehensive test suite for the framework applicability validation feature following Test-Driven Development (TDD) principles.

## Files Created

1. **Test Suite:** `/workspaces/secure-ai-tooling/scripts/hooks/tests/test_framework_applicability_validation.py`
   - 1,392 lines of code
   - 46 test functions
   - 4 test classes

2. **Test Report:** `/workspaces/secure-ai-tooling/scripts/hooks/tests/TEST_REPORT_framework_applicability_validation.md`
   - Comprehensive documentation of test suite
   - Expected behavior specifications
   - Error message format requirements

3. **This Summary:** `/workspaces/secure-ai-tooling/scripts/hooks/tests/SUMMARY_framework_applicability_tests.md`

## Test Suite Breakdown

### 📊 Statistics
- **Total Tests:** 46
- **Test Classes:** 4
- **Lines of Code:** 1,392
- **Coverage Target:** 90%+
- **Current State:** ✅ RED Phase (tests failing as expected)

### 🧪 Test Classes

| Class | Tests | Purpose |
|-------|-------|---------|
| `TestExtractFrameworkApplicability` | 11 | Test extraction of `applicableTo` from frameworks.yaml |
| `TestValidateFrameworkApplicability` | 21 | Test validation logic for controls and risks |
| `TestValidateFrameworksIntegration` | 10 | Test integration with existing validation pipeline |
| `TestFrameworkApplicabilityWithRealData` | 4 | Test with actual production YAML files |

## Functions to Implement

Based on the test suite, the following functions need to be implemented in `validate_framework_references.py`:

### 1. `extract_framework_applicability()`

```python
def extract_framework_applicability(frameworks_data: dict[str, Any]) -> dict[str, list[str]]:
    """
    Extract applicableTo arrays from frameworks.yaml.

    Args:
        frameworks_data: Parsed frameworks.yaml data

    Returns:
        Dict mapping framework_id -> list of applicable entity types
        Example: {"mitre-atlas": ["controls", "risks"], "nist-ai-rmf": ["controls"]}
    """
```

**Test Coverage:** 11 tests
- Single entity type extraction
- Multiple entity types extraction
- Edge cases (missing fields, empty arrays, malformed data)
- Production data validation

### 2. `validate_framework_applicability()`

```python
def validate_framework_applicability(
    frameworks_applicability: dict[str, list[str]],
    risk_frameworks: dict[str, list[str]],
    control_frameworks: dict[str, list[str]]
) -> list[str]:
    """
    Validate that controls/risks only reference applicable frameworks.

    Args:
        frameworks_applicability: framework_id -> list of applicable entity types
        risk_frameworks: risk_id -> list of framework_ids referenced
        control_frameworks: control_id -> list of framework_ids referenced

    Returns:
        List of error messages (empty if all valid)
    """
```

**Test Coverage:** 21 tests
- Valid cases (10 tests)
- Invalid cases (8 tests)
- Error message quality (3 tests)

### 3. Integration into `validate_frameworks()`

Update the existing `validate_frameworks()` function to:
1. Call `extract_framework_applicability(frameworks_data)`
2. Call `validate_framework_applicability()` with the extracted data
3. Report applicability errors alongside existing errors

**Test Coverage:** 10 tests

## Current Test Results

```bash
pytest scripts/hooks/tests/test_framework_applicability_validation.py -v
```

**Results:**
- ✅ 8 PASSED (existing functionality tests)
- ❌ 38 FAILED (expected - functions not yet implemented)
- 📊 Total: 46 tests

**Failing Tests (Expected):**
- All 11 `TestExtractFrameworkApplicability` tests - ImportError
- All 21 `TestValidateFrameworkApplicability` tests - ImportError
- 3 of 10 `TestValidateFrameworksIntegration` tests - integration not complete
- 2 of 4 `TestFrameworkApplicabilityWithRealData` tests - functions don't exist

**Passing Tests:**
- Integration tests testing existing `validate_frameworks()` functionality
- Production data tests that don't require new functions

## Expected Behavior

### Valid Framework References

✅ **Control → mitre-atlas** (applicableTo: ["controls", "risks"])
✅ **Control → nist-ai-rmf** (applicableTo: ["controls"])
✅ **Risk → mitre-atlas** (applicableTo: ["controls", "risks"])
✅ **Risk → stride** (applicableTo: ["risks"])
✅ **Risk → owasp-top10-llm** (applicableTo: ["risks"])

### Invalid Framework References

❌ **Control → stride** (applicableTo: ["risks"] - no "controls")
❌ **Control → owasp-top10-llm** (applicableTo: ["risks"] - no "controls")
❌ **Risk → nist-ai-rmf** (applicableTo: ["controls"] - no "risks")

### Error Message Format

```
[ISSUE: frameworks.yaml] Control 'control-id' references framework 'framework-id' which is not applicable to controls (applicableTo: ["risks"])
```

```
[ISSUE: frameworks.yaml] Risk 'risk-id' references framework 'framework-id' which is not applicable to risks (applicableTo: ["controls"])
```

## Test Categories

### Happy Path Tests (10 tests)
- Controls referencing valid frameworks
- Risks referencing valid frameworks
- Multiple valid framework references
- Empty data structures (valid scenarios)

### Edge Case Tests (11 tests)
- Missing fields
- Empty arrays
- Malformed data
- Framework missing ID
- Non-list applicableTo

### Error Condition Tests (11 tests)
- Invalid control applicability
- Invalid risk applicability
- Mixed valid/invalid references
- Multiple errors
- Error message quality

### Integration Tests (10 tests)
- Full validation pipeline
- Combined error types
- Existing function integration
- Production data validation

### Production Data Tests (4 tests)
- Actual controls.yaml validation
- Actual risks.yaml validation
- Framework definitions validation
- Full production validation

## Running the Tests

### Run all tests
```bash
cd /workspaces/secure-ai-tooling
pytest scripts/hooks/tests/test_framework_applicability_validation.py -v
```

### Run specific test class
```bash
pytest scripts/hooks/tests/test_framework_applicability_validation.py::TestExtractFrameworkApplicability -v
```

### Run with coverage
```bash
pytest scripts/hooks/tests/test_framework_applicability_validation.py \
  --cov=scripts.hooks.validate_framework_references \
  --cov-report=term \
  --cov-report=html
```

### Run specific test
```bash
pytest scripts/hooks/tests/test_framework_applicability_validation.py::TestExtractFrameworkApplicability::test_extract_from_actual_frameworks_yaml -v
```

## Implementation Checklist

### Step 1: Implement `extract_framework_applicability()`
- [ ] Create function in `validate_framework_references.py`
- [ ] Handle valid frameworks with applicableTo
- [ ] Handle missing applicableTo field (skip framework)
- [ ] Handle empty applicableTo array (preserve empty)
- [ ] Handle missing framework ID (skip framework)
- [ ] Handle malformed data gracefully
- [ ] Run tests: `pytest scripts/hooks/tests/test_framework_applicability_validation.py::TestExtractFrameworkApplicability -v`
- [ ] Verify all 11 tests pass

### Step 2: Implement `validate_framework_applicability()`
- [ ] Create function in `validate_framework_references.py`
- [ ] Validate control framework applicability
- [ ] Validate risk framework applicability
- [ ] Generate clear error messages
- [ ] Handle empty dictionaries
- [ ] Handle frameworks not in applicability dict
- [ ] Run tests: `pytest scripts/hooks/tests/test_framework_applicability_validation.py::TestValidateFrameworkApplicability -v`
- [ ] Verify all 21 tests pass

### Step 3: Integrate into `validate_frameworks()`
- [ ] Call `extract_framework_applicability()` in validation pipeline
- [ ] Call `validate_framework_applicability()` with extracted data
- [ ] Report applicability errors alongside existing errors
- [ ] Update success message to mention applicability validation
- [ ] Run tests: `pytest scripts/hooks/tests/test_framework_applicability_validation.py::TestValidateFrameworksIntegration -v`
- [ ] Verify all 10 tests pass

### Step 4: Validate Production Data
- [ ] Run tests: `pytest scripts/hooks/tests/test_framework_applicability_validation.py::TestFrameworkApplicabilityWithRealData -v`
- [ ] Verify all 4 tests pass
- [ ] Fix any production data issues discovered

### Step 5: Final Validation
- [ ] Run full test suite: `pytest scripts/hooks/tests/test_framework_applicability_validation.py -v`
- [ ] Verify all 46 tests pass
- [ ] Check coverage: `pytest --cov=scripts.hooks.validate_framework_references --cov-report=term`
- [ ] Verify coverage >= 90%
- [ ] Test with actual git pre-commit hook
- [ ] Update documentation

## Success Criteria

✅ **All 46 tests pass**
✅ **Coverage >= 90% of new functions**
✅ **Production data validates successfully**
✅ **Error messages are clear and actionable**
✅ **No performance regression**
✅ **Documentation complete**

## TDD Workflow Status

| Phase | Status | Description |
|-------|--------|-------------|
| 🔴 RED | ✅ Complete | Tests written, failing as expected (38/46 failing) |
| 🟢 GREEN | ⏳ Pending | Implement functions to make tests pass |
| 🔵 REFACTOR | ⏳ Pending | Optimize and clean up implementation |

## Next Steps

1. **Implement Functions** - Create the two new functions in `validate_framework_references.py`
2. **Run Tests** - Execute tests after each function implementation
3. **Iterate** - Fix any failing tests until all pass
4. **Verify Coverage** - Ensure 90%+ coverage of new code
5. **Validate Production** - Ensure production data passes all checks
6. **Document** - Update function docstrings and module documentation

## Production Data Context

The tests validate against actual production files:
- `/workspaces/secure-ai-tooling/risk-map/yaml/frameworks.yaml` (4 frameworks)
- `/workspaces/secure-ai-tooling/risk-map/yaml/controls.yaml` (controls with mappings)
- `/workspaces/secure-ai-tooling/risk-map/yaml/risks.yaml` (risks with mappings)

**Current Framework Configuration:**
- `mitre-atlas`: applicableTo = ["controls", "risks"]
- `nist-ai-rmf`: applicableTo = ["controls"]
- `stride`: applicableTo = ["risks"]
- `owasp-top10-llm`: applicableTo = ["risks"]

## Test Quality Metrics

- ✅ Clear test names following convention
- ✅ Comprehensive docstrings (Given-When-Then)
- ✅ Meaningful assertion messages
- ✅ Independent tests (no shared state)
- ✅ Uses pytest fixtures for temporary files
- ✅ Tests are fast (< 1s each)
- ✅ Both positive and negative cases
- ✅ Edge cases covered
- ✅ Production data validated

## Additional Resources

- **Test File:** `/workspaces/secure-ai-tooling/scripts/hooks/tests/test_framework_applicability_validation.py`
- **Test Report:** `/workspaces/secure-ai-tooling/scripts/hooks/tests/TEST_REPORT_framework_applicability_validation.md`
- **Implementation File:** `/workspaces/secure-ai-tooling/scripts/hooks/validate_framework_references.py`
- **Frameworks Schema:** `/workspaces/secure-ai-tooling/risk-map/schemas/frameworks.schema.json`

## Questions?

For questions about the test suite or implementation requirements, refer to:
1. Test docstrings in `test_framework_applicability_validation.py`
2. Detailed test report in `TEST_REPORT_framework_applicability_validation.md`
3. Existing validation patterns in `validate_framework_references.py`
4. Schema validation tests in `test_frameworks_applicable_to.py`

---

**Created:** 2025-12-13
**TDD Phase:** 🔴 RED (Tests Written, Implementation Pending)
**Status:** ✅ Ready for Implementation

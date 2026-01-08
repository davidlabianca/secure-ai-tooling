# Bash Utility Test Suites

## Quick Start

### Run All Tests
```bash
# From repository root
./scripts/hooks/tests/test_git_utils.sh
./scripts/hooks/tests/test_run_validator.sh
```

### Current Status (TDD)
These tests were created **before** implementation following Test-Driven Development.

**Expected:** Tests currently FAIL (utilities not implemented yet)
**After Implementation:** All tests should PASS

## Test Suites

### 1. test_git_utils.sh (30 tests)
Tests for git staging and file detection utilities.

**Functions tested:**
- `stage_files(files, description)` - Stage files with consistent messaging
- `get_staged_matching(pattern)` - Get staged files matching pattern
- `has_staged_matching(pattern)` - Check if staged files match pattern

**Run:**
```bash
./scripts/hooks/tests/test_git_utils.sh
```

### 2. test_run_validator.sh (35 tests)
Tests for validator execution with error handling.

**Functions tested:**
- `run_validator(validator_path, description, additional_args)` - Execute validator scripts

**Run:**
```bash
./scripts/hooks/tests/test_run_validator.sh
```

## Test Framework

Uses `bash_test_framework.sh` - a lightweight testing framework providing:

- ✅ Standard assertions (equals, contains, success/failure)
- ✅ Setup/teardown per test
- ✅ Automatic test discovery
- ✅ Colored output with clear pass/fail indicators
- ✅ Test isolation (temporary directories)

## Implementation Targets

After creating implementations, place them at:
- `/workspaces/secure-ai-tooling/scripts/hooks/git_utils.sh`
- `/workspaces/secure-ai-tooling/scripts/hooks/run_validator.sh`

The test suites will automatically source them if they exist.

## Coverage

**Total Tests:** 65
- git_utils.sh: 30 tests (8 basic + 10 pattern + 8 boolean + 3 integration + 4 edge)
- run_validator.sh: 35 tests (4 success + 4 failure + 5 args + 3 output + 3 types + 10 edge + 4 integration + 1 performance)

See [TEST_SUITE_DOCUMENTATION.md](./TEST_SUITE_DOCUMENTATION.md) for detailed coverage.

## Example Test Output

```
========================================
Running Tests
========================================

  ▶ test_stage_files_single_file_success
    ✓ PASS

  ▶ test_stage_files_nonexistent_file_fails
    ✗ FAIL: stage_files should return non-zero for nonexistent file
      Expected: non-zero
      Actual:   0

========================================
Test Summary
========================================
Total:  30
Passed: 28
Failed: 2
```

## Next Steps

1. Implement `git_utils.sh` with the three required functions
2. Run `./scripts/hooks/tests/test_git_utils.sh` - all tests should pass
3. Implement `run_validator.sh` with the required function
4. Run `./scripts/hooks/tests/test_run_validator.sh` - all tests should pass
5. Refactor pre-commit hook to use these utilities

## Notes

- Tests use temporary git repositories (cleaned up automatically)
- Tests are independent (no shared state)
- Each test has descriptive name indicating what it tests
- Tests cover happy path, error cases, and edge cases
- Mock validators are created on-the-fly for testing

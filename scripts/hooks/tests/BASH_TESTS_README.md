# Bash Utility Test Suites

## Quick Start

### Run All Tests
```bash
# From repository root
./scripts/hooks/tests/test_git_utils.sh
./scripts/hooks/tests/test_run_validator.sh
```

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

### 2. test_run_validator.sh 
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

## Notes

- Tests use temporary git repositories (cleaned up automatically)
- Tests are independent (no shared state)
- Each test has descriptive name indicating what it tests
- Tests cover happy path, error cases, and edge cases
- Mock validators are created on-the-fly for testing

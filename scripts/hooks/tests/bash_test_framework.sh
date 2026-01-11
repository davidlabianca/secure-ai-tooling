#!/bin/bash

# =============================================================================
# Bash Testing Framework
# =============================================================================
# A lightweight testing framework for bash scripts inspired by bats.
#
# Usage:
#   source bash_test_framework.sh
#
#   setup() {
#     # Optional: runs before each test
#   }
#
#   teardown() {
#     # Optional: runs after each test
#   }
#
#   test_something() {
#     assert_equals "expected" "actual" "description"
#   }
#
#   run_tests
# =============================================================================

# Test statistics
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
CURRENT_TEST=""

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# Assertion Functions
# =============================================================================

# Assert that two values are equal
# Args: $1=expected, $2=actual, $3=description (optional)
assert_equals() {
    local expected="$1"
    local actual="$2"
    local desc="${3:-values should be equal}"

    if [[ "$expected" == "$actual" ]]; then
        return 0
    else
        echo -e "${RED}    ✗ FAIL: $desc${NC}"
        echo "      Expected: '$expected'"
        echo "      Actual:   '$actual'"
        return 1
    fi
}

# Assert that two values are not equal
# Args: $1=not_expected, $2=actual, $3=description (optional)
assert_not_equals() {
    local not_expected="$1"
    local actual="$2"
    local desc="${3:-values should not be equal}"

    if [[ "$not_expected" != "$actual" ]]; then
        return 0
    else
        echo -e "${RED}    ✗ FAIL: $desc${NC}"
        echo "      Expected not: '$not_expected'"
        echo "      Actual:       '$actual'"
        return 1
    fi
}

# Assert that a command succeeds (exit code 0)
# Args: $1=description (optional)
assert_success() {
    local desc="${1:-command should succeed}"
    local exit_code=$?

    if [[ $exit_code -eq 0 ]]; then
        return 0
    else
        echo -e "${RED}    ✗ FAIL: $desc${NC}"
        echo "      Expected exit code: 0"
        echo "      Actual exit code:   $exit_code"
        return 1
    fi
}

# Assert that a command fails (exit code non-zero)
# Args: $1=description (optional)
assert_failure() {
    local desc="${1:-command should fail}"
    local exit_code=$?

    if [[ $exit_code -ne 0 ]]; then
        return 0
    else
        echo -e "${RED}    ✗ FAIL: $desc${NC}"
        echo "      Expected exit code: non-zero"
        echo "      Actual exit code:   0"
        return 1
    fi
}

# Assert that a string contains a substring
# Args: $1=haystack, $2=needle, $3=description (optional)
assert_contains() {
    local haystack="$1"
    local needle="$2"
    local desc="${3:-string should contain substring}"

    if [[ "$haystack" == *"$needle"* ]]; then
        return 0
    else
        echo -e "${RED}    ✗ FAIL: $desc${NC}"
        echo "      Haystack: '$haystack'"
        echo "      Needle:   '$needle'"
        return 1
    fi
}

# Assert that a string does not contain a substring
# Args: $1=haystack, $2=needle, $3=description (optional)
assert_not_contains() {
    local haystack="$1"
    local needle="$2"
    local desc="${3:-string should not contain substring}"

    if [[ "$haystack" != *"$needle"* ]]; then
        return 0
    else
        echo -e "${RED}    ✗ FAIL: $desc${NC}"
        echo "      Haystack: '$haystack'"
        echo "      Needle:   '$needle'"
        return 1
    fi
}

# Assert that a file exists
# Args: $1=file_path, $2=description (optional)
assert_file_exists() {
    local file_path="$1"
    local desc="${2:-file should exist}"

    if [[ -f "$file_path" ]]; then
        return 0
    else
        echo -e "${RED}    ✗ FAIL: $desc${NC}"
        echo "      File not found: '$file_path'"
        return 1
    fi
}

# Assert that a file does not exist
# Args: $1=file_path, $2=description (optional)
assert_file_not_exists() {
    local file_path="$1"
    local desc="${2:-file should not exist}"

    if [[ ! -f "$file_path" ]]; then
        return 0
    else
        echo -e "${RED}    ✗ FAIL: $desc${NC}"
        echo "      File exists: '$file_path'"
        return 1
    fi
}

# Assert that a variable is empty
# Args: $1=value, $2=description (optional)
assert_empty() {
    local value="$1"
    local desc="${2:-value should be empty}"

    if [[ -z "$value" ]]; then
        return 0
    else
        echo -e "${RED}    ✗ FAIL: $desc${NC}"
        echo "      Expected: empty"
        echo "      Actual:   '$value'"
        return 1
    fi
}

# Assert that a variable is not empty
# Args: $1=value, $2=description (optional)
assert_not_empty() {
    local value="$1"
    local desc="${2:-value should not be empty}"

    if [[ -n "$value" ]]; then
        return 0
    else
        echo -e "${RED}    ✗ FAIL: $desc${NC}"
        echo "      Expected: non-empty"
        echo "      Actual:   empty"
        return 1
    fi
}

# =============================================================================
# Test Runner Functions
# =============================================================================

# Run a single test function
# Args: $1=test_function_name
run_test() {
    local test_name="$1"
    CURRENT_TEST="$test_name"
    TESTS_RUN=$((TESTS_RUN + 1))

    echo -e "${BLUE}  ▶ $test_name${NC}"

    # Run setup if it exists
    if declare -f setup > /dev/null; then
        setup
    fi

    # Run the test and capture result
    if $test_name; then
        TESTS_PASSED=$((TESTS_PASSED + 1))
        echo -e "${GREEN}    ✓ PASS${NC}"
    else
        TESTS_FAILED=$((TESTS_FAILED + 1))
    fi

    # Run teardown if it exists
    if declare -f teardown > /dev/null; then
        teardown
    fi

    echo ""
}

# Run all test functions (functions starting with "test_")
run_tests() {
    echo ""
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Running Tests${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo ""

    # Find all functions starting with "test_"
    local test_functions=$(declare -F | awk '{print $3}' | grep '^test_')

    # Run each test
    for test_func in $test_functions; do
        run_test "$test_func"
    done

    # Print summary
    echo -e "${YELLOW}========================================${NC}"
    echo -e "${YELLOW}Test Summary${NC}"
    echo -e "${YELLOW}========================================${NC}"
    echo -e "Total:  $TESTS_RUN"
    echo -e "${GREEN}Passed: $TESTS_PASSED${NC}"

    if [[ $TESTS_FAILED -gt 0 ]]; then
        echo -e "${RED}Failed: $TESTS_FAILED${NC}"
        echo ""
        exit 1
    else
        echo -e "Failed: 0"
        echo ""
        exit 0
    fi
}

# =============================================================================
# Utility Functions for Testing
# =============================================================================

# Run a command and capture its output and exit code
# Sets global variables: RUN_OUTPUT, RUN_EXIT_CODE
run() {
    RUN_OUTPUT=$("$@" 2>&1)
    RUN_EXIT_CODE=$?
}

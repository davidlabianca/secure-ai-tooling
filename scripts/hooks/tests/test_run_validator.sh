#!/bin/bash

# =============================================================================
# Tests for run_validator.sh - Python Validator Execution
# =============================================================================
# Test suite for the Python validator execution utility.
#
# IMPORTANT: run_validator.sh is designed SPECIFICALLY for Python validators.
# All validators in the pre-commit hook are Python scripts, so this utility
# executes them via `python3`. These tests focus on Python validator execution.
#
# Function under test:
#   - run_validator(validator_path, description, additional_args)
#
# Usage:
#   ./test_run_validator.sh
# =============================================================================

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the testing framework
source "$SCRIPT_DIR/bash_test_framework.sh"

# Path to the implementation
RUN_VALIDATOR_SCRIPT="$SCRIPT_DIR/../run_validator.sh"

# Test directory for mock validators
TEST_DIR=""

# =============================================================================
# Setup and Teardown
# =============================================================================

setup() {
    # Create a temporary directory for test files
    TEST_DIR=$(mktemp -d)
    cd "$TEST_DIR"

    # Source the run_validator script if it exists
    if [[ -f "$RUN_VALIDATOR_SCRIPT" ]]; then
        source "$RUN_VALIDATOR_SCRIPT"
    fi
}

teardown() {
    # Clean up test directory
    if [[ -n "$TEST_DIR" && -d "$TEST_DIR" ]]; then
        cd /
        rm -rf "$TEST_DIR"
    fi
}

# =============================================================================
# Helper Functions to Create Mock Python Validators
# =============================================================================

# Create a Python validator with custom exit code and output
create_python_validator() {
    local validator_path="$1"
    local exit_code="${2:-0}"
    local message="${3:-Python validator executed}"
    cat > "$validator_path" << EOF
#!/usr/bin/env python3
import sys
print("$message")
sys.exit($exit_code)
EOF
    chmod +x "$validator_path"
}

# Create a Python validator that prints arguments
create_python_args_validator() {
    local validator_path="$1"
    cat > "$validator_path" << 'EOF'
#!/usr/bin/env python3
import sys
print(f"Args: {' '.join(sys.argv[1:])}")
sys.exit(0)
EOF
    chmod +x "$validator_path"
}

# Create a Python validator that uses stderr
create_python_stderr_validator() {
    local validator_path="$1"
    local exit_code="${2:-0}"
    cat > "$validator_path" << EOF
#!/usr/bin/env python3
import sys
print("stdout message", file=sys.stdout)
print("stderr message", file=sys.stderr)
sys.exit($exit_code)
EOF
    chmod +x "$validator_path"
}

# Create a Python validator that reads environment variables
create_python_env_validator() {
    local validator_path="$1"
    cat > "$validator_path" << 'EOF'
#!/usr/bin/env python3
import os
import sys
test_var = os.environ.get('TEST_VAR', 'not_set')
print(f"TEST_VAR={test_var}")
sys.exit(0)
EOF
    chmod +x "$validator_path"
}

# =============================================================================
# Tests - Basic Python Validator Execution
# =============================================================================

test_run_validator_python_success() {
    # Arrange: Create successful Python validator
    local validator="$TEST_DIR/validator.py"
    create_python_validator "$validator" 0 "Validation passed"

    # Act: Run the Python validator
    run run_validator "$validator" "test validation"
    local exit_code=$RUN_EXIT_CODE

    # Assert: Should execute successfully
    assert_equals "0" "$exit_code" "should execute Python validator successfully"
    assert_contains "$RUN_OUTPUT" "Validation passed" "should capture Python output"
}

test_run_validator_python_failure() {
    # Arrange: Create failing Python validator
    local validator="$TEST_DIR/fail_validator.py"
    create_python_validator "$validator" 1 "Validation failed"

    # Act: Run the validator
    run run_validator "$validator" "failing validation"
    local exit_code=$RUN_EXIT_CODE

    # Assert: Should return Python's exit code
    assert_equals "1" "$exit_code" "should return Python validator's exit code"
}

test_run_validator_python_custom_exit_code() {
    # Arrange: Create validator with exit code 42
    local validator="$TEST_DIR/custom.py"
    create_python_validator "$validator" 42 "Custom exit"

    # Act: Run the validator
    run run_validator "$validator" "custom exit"
    local exit_code=$RUN_EXIT_CODE

    # Assert: Should return custom exit code
    assert_equals "42" "$exit_code" "should return custom exit code"
}

test_run_validator_prints_running_message() {
    # Arrange: Create Python validator
    local validator="$TEST_DIR/validator.py"
    create_python_validator "$validator" 0

    # Act: Run the validator
    run run_validator "$validator" "my validation description"
    local output="$RUN_OUTPUT"

    # Assert: Should print description
    assert_contains "$output" "Running: my validation description" "should print description"
}

# =============================================================================
# Tests - Missing/Invalid Validators
# =============================================================================

test_run_validator_nonexistent_file() {
    # Arrange: Use non-existent file path
    local validator="$TEST_DIR/nonexistent.py"

    # Act: Try to run non-existent validator
    run run_validator "$validator" "missing validator"
    local exit_code=$RUN_EXIT_CODE

    # Assert: Should return error
    assert_equals "1" "$exit_code" "should fail for non-existent validator"
}

test_run_validator_missing_file_error_message() {
    # Arrange: Use non-existent file
    local validator="$TEST_DIR/missing.py"

    # Act: Try to run it
    run run_validator "$validator" "test"
    local output="$RUN_OUTPUT"

    # Assert: Should show clear error
    assert_contains "$output" "Error: Validator not found" "should show error for missing file"
    assert_contains "$output" "$validator" "should include validator path in error"
}

# =============================================================================
# Tests - Argument Passing to Python Validators
# =============================================================================

test_run_validator_passes_single_arg() {
    # Arrange: Create Python validator that echoes args
    local validator="$TEST_DIR/args.py"
    create_python_args_validator "$validator"

    # Act: Run with single argument
    run run_validator "$validator" "args test" "--force"
    local output="$RUN_OUTPUT"

    # Assert: Should pass argument to Python script
    assert_contains "$output" "Args: --force" "should pass single argument"
}

test_run_validator_passes_multiple_args() {
    # Arrange: Create args validator
    local validator="$TEST_DIR/args.py"
    create_python_args_validator "$validator"

    # Act: Run with multiple arguments
    run run_validator "$validator" "multi args" "--force --verbose"
    local output="$RUN_OUTPUT"

    # Assert: Should pass all arguments
    assert_contains "$output" "--force" "should pass first arg"
    assert_contains "$output" "--verbose" "should pass second arg"
}

test_run_validator_without_args() {
    # Arrange: Create args validator
    local validator="$TEST_DIR/args.py"
    create_python_args_validator "$validator"

    # Act: Run without additional args
    run run_validator "$validator" "no args"
    local output="$RUN_OUTPUT"

    # Assert: Should work without arguments
    assert_contains "$output" "Args:" "should work with no arguments"
}

test_run_validator_args_with_equals() {
    # Arrange: Create args validator
    local validator="$TEST_DIR/args.py"
    create_python_args_validator "$validator"

    # Act: Run with argument containing equals
    run run_validator "$validator" "equals test" "--config=file.yaml"
    local output="$RUN_OUTPUT"

    # Assert: Should pass argument with equals
    assert_contains "$output" "--config=file.yaml" "should handle arguments with equals"
}

test_run_validator_args_with_paths() {
    # Arrange: Create args validator
    local validator="$TEST_DIR/args.py"
    create_python_args_validator "$validator"

    # Act: Run with file path argument
    run run_validator "$validator" "path test" "risk-map/yaml/components.yaml"
    local output="$RUN_OUTPUT"

    # Assert: Should pass file path
    assert_contains "$output" "risk-map/yaml/components.yaml" "should handle file paths"
}

# =============================================================================
# Tests - Output Handling
# =============================================================================

test_run_validator_captures_python_stdout() {
    # Arrange: Create validator with specific output
    local validator="$TEST_DIR/output.py"
    create_python_validator "$validator" 0 "✅ Validation successful"

    # Act: Run validator
    run run_validator "$validator" "output test"
    local output="$RUN_OUTPUT"

    # Assert: Should capture stdout
    assert_contains "$output" "✅ Validation successful" "should capture Python stdout"
}

test_run_validator_handles_stderr() {
    # Arrange: Create validator that uses stderr
    local validator="$TEST_DIR/stderr.py"
    create_python_stderr_validator "$validator" 0

    # Act: Run validator
    run run_validator "$validator" "stderr test"
    local exit_code=$RUN_EXIT_CODE
    local output="$RUN_OUTPUT"

    # Assert: Should still succeed and capture output
    assert_equals "0" "$exit_code" "should succeed despite stderr"
    # Note: stderr may or may not appear in output depending on runner
}

test_run_validator_multiline_output() {
    # Arrange: Create validator with multiline output
    local validator="$TEST_DIR/multiline.py"
    cat > "$validator" << 'EOF'
#!/usr/bin/env python3
print("Line 1")
print("Line 2")
print("Line 3")
EOF
    chmod +x "$validator"

    # Act: Run validator
    run run_validator "$validator" "multiline test"
    local output="$RUN_OUTPUT"

    # Assert: Should capture all lines
    assert_contains "$output" "Line 1" "should capture first line"
    assert_contains "$output" "Line 2" "should capture second line"
    assert_contains "$output" "Line 3" "should capture third line"
}

# =============================================================================
# Tests - Environment and Context
# =============================================================================

test_run_validator_preserves_environment() {
    # Arrange: Create env validator
    local validator="$TEST_DIR/env.py"
    create_python_env_validator "$validator"

    # Act: Run with environment variable set
    TEST_VAR="test_value" run run_validator "$validator" "env test"
    local output="$RUN_OUTPUT"

    # Assert: Should see environment variable
    assert_contains "$output" "TEST_VAR=test_value" "should preserve environment variables"
}

test_run_validator_with_absolute_path() {
    # Arrange: Create validator with absolute path
    local validator="$TEST_DIR/absolute.py"
    create_python_validator "$validator" 0

    # Act: Run with absolute path
    run run_validator "$validator" "absolute path test"
    local exit_code=$RUN_EXIT_CODE

    # Assert: Should work with absolute paths
    assert_equals "0" "$exit_code" "should work with absolute paths"
}

test_run_validator_with_relative_path() {
    # Arrange: Create validator and get relative path
    mkdir -p "$TEST_DIR/subdir"
    local validator="$TEST_DIR/subdir/relative.py"
    create_python_validator "$validator" 0
    local rel_path="subdir/relative.py"

    # Act: Run with relative path
    run run_validator "$rel_path" "relative path test"
    local exit_code=$RUN_EXIT_CODE

    # Assert: Should work with relative paths
    assert_equals "0" "$exit_code" "should work with relative paths"
}

# =============================================================================
# Tests - Integration Patterns (Real Pre-commit Hook Usage)
# =============================================================================

test_integration_component_edge_validator_pattern() {
    # Arrange: Simulate validate_riskmap.py
    local validator="$TEST_DIR/validate_riskmap.py"
    cat > "$validator" << 'EOF'
#!/usr/bin/env python3
import sys
args = sys.argv[1:]
if "--force" in args:
    print("🔍 Force checking components...")
else:
    print("🔍 Checking staged components...")
print("   ✅ Component edges are consistent")
sys.exit(0)
EOF
    chmod +x "$validator"

    # Act: Run like pre-commit hook does
    run run_validator "$validator" "component edge validation" "--force"
    local exit_code=$RUN_EXIT_CODE
    local output="$RUN_OUTPUT"

    # Assert: Should work like real validator
    assert_equals "0" "$exit_code" "should work in real-world pattern"
    assert_contains "$output" "Force checking" "should respect --force flag"
    assert_contains "$output" "✅" "should show success indicator"
}

test_integration_control_risk_validator_pattern() {
    # Arrange: Simulate validate_control_risk_references.py
    local validator="$TEST_DIR/validate_refs.py"
    cat > "$validator" << 'EOF'
#!/usr/bin/env python3
print("🔍 Checking control-to-risk references...")
print("   ✅ Control-to-risk references are consistent")
EOF
    chmod +x "$validator"

    # Act: Run like pre-commit hook does
    run run_validator "$validator" "control-to-risk reference validation"
    local exit_code=$RUN_EXIT_CODE
    local output="$RUN_OUTPUT"

    # Assert: Should succeed
    assert_equals "0" "$exit_code" "should work for reference validation pattern"
    assert_contains "$output" "✅" "should show success"
}

test_integration_framework_validator_pattern() {
    # Arrange: Simulate validate_framework_references.py
    local validator="$TEST_DIR/validate_frameworks.py"
    cat > "$validator" << 'EOF'
#!/usr/bin/env python3
print("🔍 Checking framework references...")
print("  ✅ Framework references are consistent")
print("     - Found 4 valid frameworks")
EOF
    chmod +x "$validator"

    # Act: Run like pre-commit hook does
    run run_validator "$validator" "framework reference validation" ""
    local exit_code=$RUN_EXIT_CODE
    local output="$RUN_OUTPUT"

    # Assert: Should work
    assert_equals "0" "$exit_code" "should work for framework validation"
    assert_contains "$output" "Found 4 valid frameworks" "should capture detailed output"
}

test_integration_validator_failure_propagation() {
    # Arrange: Create failing validator simulating real failure
    local validator="$TEST_DIR/fail.py"
    cat > "$validator" << 'EOF'
#!/usr/bin/env python3
import sys
print("❌ Validation failed: Component edges are inconsistent")
print("   Error: component1 -> component2 but no reverse edge")
sys.exit(1)
EOF
    chmod +x "$validator"

    # Act: Run validator
    run run_validator "$validator" "test validation"
    local exit_code=$RUN_EXIT_CODE
    local output="$RUN_OUTPUT"

    # Assert: Should propagate failure correctly
    assert_equals "1" "$exit_code" "should propagate failure exit code"
    assert_contains "$output" "❌" "should show failure message"
    assert_contains "$output" "inconsistent" "should show error details"
}

# =============================================================================
# Tests - Edge Cases
# =============================================================================

test_run_validator_empty_description() {
    # Arrange: Create Python validator
    local validator="$TEST_DIR/validator.py"
    create_python_validator "$validator" 0

    # Act: Run with empty description
    run run_validator "$validator" ""
    local exit_code=$RUN_EXIT_CODE

    # Assert: Should still work
    assert_equals "0" "$exit_code" "should work with empty description"
}

test_run_validator_long_output() {
    # Arrange: Create validator with lots of output
    local validator="$TEST_DIR/long.py"
    cat > "$validator" << 'EOF'
#!/usr/bin/env python3
for i in range(100):
    print(f"Line {i}")
EOF
    chmod +x "$validator"

    # Act: Run validator
    run run_validator "$validator" "long output test"
    local exit_code=$RUN_EXIT_CODE
    local output="$RUN_OUTPUT"

    # Assert: Should handle long output
    assert_equals "0" "$exit_code" "should handle long output"
    assert_contains "$output" "Line 0" "should capture beginning"
    assert_contains "$output" "Line 99" "should capture end"
}

test_run_validator_validator_with_spaces_in_path() {
    # Arrange: Create directory with spaces
    mkdir -p "$TEST_DIR/path with spaces"
    local validator="$TEST_DIR/path with spaces/validator.py"
    create_python_validator "$validator" 0

    # Act: Run validator with space in path
    run run_validator "$validator" "space path test"
    local exit_code=$RUN_EXIT_CODE

    # Assert: Should handle spaces in path
    assert_equals "0" "$exit_code" "should handle spaces in validator path"
}

# =============================================================================
# Run All Tests
# =============================================================================

# Run the test suite
run_tests

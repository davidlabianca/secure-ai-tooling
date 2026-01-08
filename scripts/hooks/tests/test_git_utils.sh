#!/bin/bash

# =============================================================================
# Tests for git_utils.sh
# =============================================================================
# Comprehensive test suite for git utility functions that will be extracted
# from the monolithic pre-commit hook.
#
# Functions under test:
#   - stage_files(files, description)
#   - get_staged_matching(pattern)
#   - has_staged_matching(pattern)
#
# Usage:
#   ./test_git_utils.sh
# =============================================================================

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Source the testing framework
source "$SCRIPT_DIR/bash_test_framework.sh"

# Path to the implementation (will not exist yet - TDD!)
GIT_UTILS_SCRIPT="$SCRIPT_DIR/../git_utils.sh"

# Test repository directory (created in setup)
TEST_REPO=""

# =============================================================================
# Setup and Teardown
# =============================================================================

setup() {
    # Create a temporary directory for test git repository
    TEST_REPO=$(mktemp -d)

    # Initialize a git repository
    cd "$TEST_REPO"
    git init --quiet
    git config user.email "test@example.com"
    git config user.name "Test User"

    # Create an initial commit so we have a valid HEAD
    echo "initial" > initial.txt
    git add initial.txt
    git commit --quiet -m "Initial commit"

    # Source the git_utils script if it exists
    if [[ -f "$GIT_UTILS_SCRIPT" ]]; then
        source "$GIT_UTILS_SCRIPT"
    fi
}

teardown() {
    # Clean up test repository
    if [[ -n "$TEST_REPO" && -d "$TEST_REPO" ]]; then
        cd /
        rm -rf "$TEST_REPO"
    fi
}

# =============================================================================
# Tests for stage_files()
# =============================================================================

test_stage_files_single_file_success() {
    # Arrange: Create a modified file
    echo "modified content" > test_file.txt

    # Act: Stage the file
    run stage_files "test_file.txt" "test file"
    local exit_code=$RUN_EXIT_CODE
    local output="$RUN_OUTPUT"

    # Assert: Should succeed and file should be staged
    assert_equals "0" "$exit_code" "stage_files should return 0 on success"
    assert_contains "$output" "test file" "output should contain description"

    # Verify file is actually staged
    local staged_files=$(git diff --cached --name-only)
    assert_contains "$staged_files" "test_file.txt" "file should be in staging area"
}

test_stage_files_multiple_files_success() {
    # Arrange: Create multiple modified files
    echo "content1" > file1.txt
    echo "content2" > file2.txt
    echo "content3" > file3.txt

    # Act: Stage multiple files
    run stage_files "file1.txt file2.txt file3.txt" "multiple test files"
    local exit_code=$RUN_EXIT_CODE

    # Assert: Should succeed
    assert_equals "0" "$exit_code" "stage_files should return 0 for multiple files"

    # Verify all files are staged
    local staged_files=$(git diff --cached --name-only)
    assert_contains "$staged_files" "file1.txt" "file1 should be staged"
    assert_contains "$staged_files" "file2.txt" "file2 should be staged"
    assert_contains "$staged_files" "file3.txt" "file3 should be staged"
}

test_stage_files_prints_success_message() {
    # Arrange: Create a file
    echo "test" > success_test.txt

    # Act: Stage the file
    run stage_files "success_test.txt" "success message test"
    local output="$RUN_OUTPUT"

    # Assert: Output should contain success indicator
    assert_contains "$output" "✅" "output should contain success checkmark"
    assert_contains "$output" "success message test" "output should contain description"
}

test_stage_files_nonexistent_file_fails() {
    # Act: Try to stage a file that doesn't exist
    run stage_files "nonexistent_file.txt" "nonexistent file"
    local exit_code=$RUN_EXIT_CODE
    local output="$RUN_OUTPUT"

    # Assert: Should fail with non-zero exit code
    assert_not_equals "0" "$exit_code" "stage_files should return non-zero for nonexistent file"
}

test_stage_files_prints_warning_on_failure() {
    # Act: Try to stage a nonexistent file
    run stage_files "does_not_exist.txt" "warning test"
    local output="$RUN_OUTPUT"

    # Assert: Output should contain warning
    assert_contains "$output" "⚠️" "output should contain warning emoji on failure"
    assert_contains "$output" "warning test" "output should contain description in warning"
}

test_stage_files_with_empty_file_list() {
    # Act: Call stage_files with empty file list
    run stage_files "" "empty files"
    local exit_code=$RUN_EXIT_CODE

    # Assert: Should handle gracefully (implementation choice: could succeed or fail)
    # This tests the edge case behavior
    # The actual behavior will be defined by implementation
}

test_stage_files_with_files_containing_spaces() {
    # Arrange: Create file with spaces in name
    echo "content" > "file with spaces.txt"

    # Act: Stage the file
    run stage_files "file with spaces.txt" "file with spaces"
    local exit_code=$RUN_EXIT_CODE

    # Assert: Should handle files with spaces correctly
    assert_equals "0" "$exit_code" "should handle files with spaces in name"

    # Verify file is staged
    local staged_files=$(git diff --cached --name-only)
    assert_contains "$staged_files" "file with spaces.txt" "file with spaces should be staged"
}

test_stage_files_with_files_in_subdirectory() {
    # Arrange: Create subdirectory and file
    mkdir -p subdir/nested
    echo "content" > subdir/nested/deep_file.txt

    # Act: Stage the file with path
    run stage_files "subdir/nested/deep_file.txt" "nested file"
    local exit_code=$RUN_EXIT_CODE

    # Assert: Should handle nested paths
    assert_equals "0" "$exit_code" "should handle nested directory paths"

    # Verify file is staged
    local staged_files=$(git diff --cached --name-only)
    assert_contains "$staged_files" "subdir/nested/deep_file.txt" "nested file should be staged"
}

# =============================================================================
# Tests for get_staged_matching()
# =============================================================================

test_get_staged_matching_finds_single_match() {
    # Arrange: Stage some files
    echo "yaml content" > test.yaml
    echo "json content" > test.json
    git add test.yaml test.json

    # Act: Get staged YAML files
    local result=$(get_staged_matching "\.yaml$")

    # Assert: Should return the YAML file
    assert_contains "$result" "test.yaml" "should find YAML file"
    assert_not_contains "$result" "test.json" "should not include JSON file"
}

test_get_staged_matching_finds_multiple_matches() {
    # Arrange: Stage multiple YAML files
    echo "yaml1" > file1.yaml
    echo "yaml2" > file2.yaml
    echo "yaml3" > file3.yaml
    echo "txt" > file.txt
    git add file1.yaml file2.yaml file3.yaml file.txt

    # Act: Get all YAML files
    local result=$(get_staged_matching "\.yaml$")

    # Assert: Should return all YAML files
    assert_contains "$result" "file1.yaml" "should find file1.yaml"
    assert_contains "$result" "file2.yaml" "should find file2.yaml"
    assert_contains "$result" "file3.yaml" "should find file3.yaml"
    assert_not_contains "$result" "file.txt" "should not include txt file"
}

test_get_staged_matching_returns_empty_when_no_matches() {
    # Arrange: Stage only non-matching files
    echo "txt content" > test.txt
    echo "md content" > test.md
    git add test.txt test.md

    # Act: Try to find YAML files
    local result=$(get_staged_matching "\.yaml$")

    # Assert: Should return empty string
    assert_empty "$result" "should return empty string when no matches"
}

test_get_staged_matching_with_complex_pattern() {
    # Arrange: Stage various files
    echo "components" > components.yaml
    echo "controls" > controls.yaml
    echo "risks" > risks.yaml
    echo "other" > other.yaml
    git add components.yaml controls.yaml risks.yaml other.yaml

    # Act: Find files matching pattern for components or controls
    local result=$(get_staged_matching "components\.yaml\|controls\.yaml")

    # Assert: Should match only components and controls
    assert_contains "$result" "components.yaml" "should match components.yaml"
    assert_contains "$result" "controls.yaml" "should match controls.yaml"
    # Note: depending on implementation, might or might not include risks.yaml
}

test_get_staged_matching_with_directory_pattern() {
    # Arrange: Create and stage files in specific directory
    mkdir -p risk-map/yaml
    echo "yaml1" > risk-map/yaml/test1.yaml
    echo "yaml2" > risk-map/yaml/test2.yaml
    echo "yaml3" > other.yaml
    git add risk-map/yaml/test1.yaml risk-map/yaml/test2.yaml other.yaml

    # Act: Find files in risk-map/yaml directory
    local result=$(get_staged_matching "risk-map/yaml/")

    # Assert: Should match files in that directory
    assert_contains "$result" "risk-map/yaml/test1.yaml" "should match files in risk-map/yaml/"
    assert_contains "$result" "risk-map/yaml/test2.yaml" "should match files in risk-map/yaml/"
    assert_not_contains "$result" "other.yaml" "should not match files outside directory"
}

test_get_staged_matching_case_sensitivity() {
    # Arrange: Stage files with different case
    echo "lower" > test.yaml
    echo "upper" > TEST.YAML
    git add test.yaml TEST.YAML

    # Act: Search with pattern
    local result=$(get_staged_matching "\.yaml$")

    # Assert: Should respect case (grep default behavior)
    assert_contains "$result" "test.yaml" "should match lowercase yaml"
    # TEST.YAML behavior depends on grep flags in implementation
}

test_get_staged_matching_returns_newline_separated() {
    # Arrange: Stage multiple files
    echo "1" > file1.yaml
    echo "2" > file2.yaml
    git add file1.yaml file2.yaml

    # Act: Get matches
    local result=$(get_staged_matching "\.yaml$")

    # Assert: Should be newline-separated (can be split by newlines)
    local line_count=$(echo "$result" | wc -l)
    assert_not_equals "0" "$line_count" "should return newline-separated list"
}

test_get_staged_matching_with_no_staged_files() {
    # Arrange: Clean staging area (already clean from setup)

    # Act: Try to get matches
    local result=$(get_staged_matching "\.yaml$")

    # Assert: Should return empty
    assert_empty "$result" "should return empty when no files staged"
}

# =============================================================================
# Tests for has_staged_matching()
# =============================================================================

test_has_staged_matching_returns_0_when_matches_found() {
    # Arrange: Stage a matching file
    echo "yaml" > test.yaml
    git add test.yaml

    # Act: Check for YAML files
    has_staged_matching "\.yaml$"

    # Assert: Should return 0 (success)
    assert_success "should return 0 when matches found"
}

test_has_staged_matching_returns_1_when_no_matches() {
    # Arrange: Stage only non-matching files
    echo "txt" > test.txt
    git add test.txt

    # Act: Check for YAML files
    has_staged_matching "\.yaml$"

    # Assert: Should return 1 (failure)
    assert_failure "should return 1 when no matches found"
}

test_has_staged_matching_with_multiple_matches() {
    # Arrange: Stage multiple matching files
    echo "1" > file1.yaml
    echo "2" > file2.yaml
    echo "3" > file3.yaml
    git add file1.yaml file2.yaml file3.yaml

    # Act: Check for YAML files
    has_staged_matching "\.yaml$"

    # Assert: Should return 0
    assert_success "should return 0 when multiple matches found"
}

test_has_staged_matching_with_complex_pattern() {
    # Arrange: Stage various files
    echo "comp" > components.yaml
    echo "ctrl" > controls.yaml
    echo "risk" > risks.yaml
    git add components.yaml controls.yaml risks.yaml

    # Act: Check for specific files
    has_staged_matching "components\.yaml\|controls\.yaml"

    # Assert: Should return 0 (at least one match)
    assert_success "should match complex pattern"
}

test_has_staged_matching_with_directory_pattern() {
    # Arrange: Stage file in specific directory
    mkdir -p risk-map/yaml
    echo "yaml" > risk-map/yaml/test.yaml
    git add risk-map/yaml/test.yaml

    # Act: Check for files in that directory
    has_staged_matching "risk-map/yaml/"

    # Assert: Should return 0
    assert_success "should match directory pattern"
}

test_has_staged_matching_with_empty_staging_area() {
    # Arrange: Clean staging area (already clean from setup)

    # Act: Check for any YAML files
    has_staged_matching "\.yaml$"

    # Assert: Should return 1
    assert_failure "should return 1 when staging area is empty"
}

test_has_staged_matching_partial_filename_match() {
    # Arrange: Stage file with pattern in middle of name
    echo "content" > test_components_old.yaml
    git add test_components_old.yaml

    # Act: Check for "components" in filename
    has_staged_matching "components"

    # Assert: Should return 0 (substring match)
    assert_success "should match substring in filename"
}

test_has_staged_matching_extension_only() {
    # Arrange: Stage various file types
    echo "yaml" > file.yaml
    echo "json" > file.json
    echo "txt" > file.txt
    git add file.yaml file.json file.txt

    # Act: Check for specific extension
    has_staged_matching "\.json$"

    # Assert: Should return 0 for .json
    assert_success "should match .json extension"
}

# =============================================================================
# Integration Tests - Testing interactions between functions
# =============================================================================

test_integration_stage_and_check() {
    # Arrange: Create files
    echo "yaml" > integration.yaml

    # Act: Stage using stage_files
    run stage_files "integration.yaml" "integration test"

    # Assert: has_staged_matching should find it
    has_staged_matching "integration\.yaml"
    assert_success "should find file after staging"
}

test_integration_stage_multiple_and_get() {
    # Arrange: Create multiple files
    echo "1" > stage1.yaml
    echo "2" > stage2.yaml

    # Act: Stage them
    run stage_files "stage1.yaml stage2.yaml" "multiple files"

    # Get them back
    local result=$(get_staged_matching "\.yaml$")

    # Assert: Should retrieve both
    assert_contains "$result" "stage1.yaml" "should retrieve first file"
    assert_contains "$result" "stage2.yaml" "should retrieve second file"
}

test_integration_stage_then_modify() {
    # Arrange: Create and stage file
    echo "original" > modify_test.yaml
    run stage_files "modify_test.yaml" "original"

    # Act: Modify the file after staging
    echo "modified" > modify_test.yaml

    # Assert: Should still be in staging area (staged version)
    has_staged_matching "modify_test\.yaml"
    assert_success "staged file should remain in staging after modification"
}

# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

test_edge_case_special_characters_in_filename() {
    # Arrange: Create file with special characters
    echo "content" > "test-file_v1.0.yaml"

    # Act: Stage it
    run stage_files "test-file_v1.0.yaml" "special chars"

    # Assert: Should handle correctly
    assert_equals "0" "$RUN_EXIT_CODE" "should handle special characters"

    has_staged_matching "test-file_v1\.0\.yaml"
    assert_success "should find file with special characters"
}

test_edge_case_very_long_filename() {
    # Arrange: Create file with long name
    local long_name="very_long_filename_that_exceeds_normal_length_but_still_valid.yaml"
    echo "content" > "$long_name"

    # Act: Stage it
    run stage_files "$long_name" "long filename"

    # Assert: Should handle long names
    assert_equals "0" "$RUN_EXIT_CODE" "should handle long filenames"
}

test_edge_case_pattern_with_special_regex_chars() {
    # Arrange: Stage files
    echo "test" > "file[1].yaml"
    git add "file[1].yaml"

    # Act: Try to match with bracket pattern (needs escaping)
    local result=$(get_staged_matching "file\[1\]\.yaml")

    # Assert: Should handle regex special characters
    assert_contains "$result" "file[1].yaml" "should handle escaped brackets in pattern"
}

# =============================================================================
# Run all tests
# =============================================================================

run_tests

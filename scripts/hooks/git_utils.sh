#!/bin/bash

# =============================================================================
# Git Utilities Module
# =============================================================================
# Provides reusable functions for Git operations used in pre-commit hooks.
#
# Functions:
#   - stage_files(files, description)     - Stage files with consistent messaging
#   - get_staged_matching(pattern)        - Get staged files matching pattern
#   - has_staged_matching(pattern)        - Check if staged files match pattern
#
# Usage:
#   source git_utils.sh
#   stage_files "file1.yaml file2.yaml" "updated YAML files"
#   if has_staged_matching "\.yaml$"; then
#       echo "Found YAML files"
#   fi
# =============================================================================

# Stage files with consistent messaging
# Args:
#   $1 - files (space-separated string of file paths)
#   $2 - description (shown in success/error messages)
# Returns:
#   0 on success, 1 on failure
# Output:
#   Prints success message with ✅ or warning with ⚠️
# Note:
#   Handles both multiple files and filenames with spaces
stage_files() {
    local files="$1"
    local description="$2"

    # Try git add with unquoted variable first (for multiple files)
    # If that fails and the files string contains spaces, try with quotes (single file with spaces)
    if git add $files 2>/dev/null; then
        echo "   ✅ Staged $description"
        return 0
    elif [[ "$files" == *" "* ]] && git add "$files" 2>/dev/null; then
        echo "   ✅ Staged $description"
        return 0
    else
        echo "   ⚠️  Warning: Could not stage $description"
        return 1
    fi
}

# Get list of staged files matching a grep pattern
# Args:
#   $1 - pattern (grep pattern to match against filenames)
# Returns:
#   Newline-separated list of matching files, or empty string if no matches
# Output:
#   List of matching staged files (one per line)
get_staged_matching() {
    local pattern="$1"

    # Get all staged files and filter by pattern
    git diff --cached --name-only | grep "$pattern" 2>/dev/null || true
}

# Check if any staged files match a pattern (boolean check)
# Args:
#   $1 - pattern (grep pattern to match against filenames)
# Returns:
#   0 if matches found, 1 if no matches
# Output:
#   None (silent operation)
has_staged_matching() {
    local pattern="$1"
    local result

    # Use grep directly on git output - capture and explicitly return exit code
    git diff --cached --name-only 2>/dev/null | grep -q "$pattern"
    result=$?
    return $result
}

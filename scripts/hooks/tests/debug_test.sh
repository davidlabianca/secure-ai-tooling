#!/bin/bash

source bash_test_framework.sh
GIT_UTILS_SCRIPT="$PWD/../git_utils.sh"

setup() {
    TEST_REPO=$(mktemp -d)
    cd "$TEST_REPO"
    git init --quiet
    git config user.email "test@example.com"
    git config user.name "Test User"
    echo "initial" > initial.txt
    git add initial.txt
    git commit --quiet -m "Initial commit"
    if [[ -f "$GIT_UTILS_SCRIPT" ]]; then
        source "$GIT_UTILS_SCRIPT"
    fi
}

teardown() {
    if [[ -n "$TEST_REPO" && -d "$TEST_REPO" ]]; then
        cd /
        rm -rf "$TEST_REPO"
    fi
}

test_debug() {
    echo "txt" > test.txt
    git add test.txt
    
    echo "DEBUG: About to call has_staged_matching"
    has_staged_matching "\.yaml$"
    local ec=$?
    echo "DEBUG: has_staged_matching returned $ec"
    
    # Manually check what assert_failure will see
    has_staged_matching "\.yaml$"
    echo "DEBUG: Exit code right after call: $?"
    
    # Now try the assert
    has_staged_matching "\.yaml$"

    echo "DEBUG: Exit code just before assert_failure: $?"
    assert_failure "should return 1"
}

run_tests

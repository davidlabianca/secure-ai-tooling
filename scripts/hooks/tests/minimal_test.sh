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

test_has_staged_matching_returns_1_when_no_matches() {
    echo "txt" > test.txt
    git add test.txt

    has_staged_matching "\.yaml$"

    assert_failure "should return 1 when no matches found"
}

run_tests

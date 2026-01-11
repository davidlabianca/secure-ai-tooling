#!/bin/bash

# =============================================================================
# Validator Execution Module
# =============================================================================
# Provides a reusable function for executing validator scripts with consistent
# error handling and user feedback.
#
# Function:
#   - run_validator(validator_path, description, additional_args)
#
# Usage:
#   source run_validator.sh
#   run_validator "scripts/hooks/validate_riskmap.py" "Component Edge Validation" "--force"
# =============================================================================

# Execute a validator script with consistent error handling
# Args:
#   $1 - validator_path (path to the validator script to execute)
#   $2 - description (shown in status messages)
#   $3 - additional_args (optional arguments to pass to validator)
# Returns:
#   The validator's exit code
# Output:
#   Prints status messages and validator output
run_validator() {
    local validator_path="$1"
    local description="$2"
    local additional_args="${3:-}"

    # Check if validator file exists
    if [[ ! -f "$validator_path" ]]; then
        echo "   ⚠️  Error: Validator not found: $validator_path"
        return 1
    fi

    # Print status message
    echo "   Running: $description"

    # Execute the validator with any additional arguments
    # Capture output and exit code
    if [[ -n "$additional_args" ]]; then
        python3 "$validator_path" $additional_args
    else
        python3 "$validator_path"
    fi

    return $?
}

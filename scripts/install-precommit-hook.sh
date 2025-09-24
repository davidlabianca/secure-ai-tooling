#!/bin/bash
# Simple git hook installer
# Copies scripts/hooks/pre-commit to .git/hooks/pre-commit
# Copies scripts/hooks/validate_riskmap.py to .git/hooks/validate_riskmap.py
# Copies scripts/hooks/riskmap_validator/* to .git/hooks/riskmap_validator/*
# Copies scripts/hooks/validate_control_risk_references.py to .git/hooks/validate_control_risk_references.py
# Usage: ./install-precommit-hook.sh [--force]

set -e

# Parse command line arguments
FORCE=false
PRECOMMIT_SRC="scripts/hooks/pre-commit"
VALIDATOR_SRC="scripts/hooks/validate_riskmap.py"
VALIDATOR_MODULE_SRC="scripts/hooks/riskmap_validator"
REF_VALIDATOR_SRC="scripts/hooks/validate_control_risk_references.py"

while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--force]"
            echo "  --force, -f    Overwrite existing hooks"
            echo "  --help, -h     Show this help message"
            echo ""
            echo "This script installs:"
            echo "  - Pre-commit hook (YAML schema validation)"
            echo "  - Component edge validator (edge consistency validation)"
            echo "  - Control-to-risk reference validator (reference consistency validation)"
            exit 0
            ;;
        *)
            echo "❌ Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git rev-parse --show-toplevel)"
TARGET_HOOK="$REPO_ROOT/.git/hooks/pre-commit"
TARGET_VALIDATOR="$REPO_ROOT/.git/hooks/validate_riskmap.py"
TARGET_VALIDATOR_MODULE="$REPO_ROOT/.git/hooks/riskmap_validator"
TARGET_REF_VALIDATOR="$REPO_ROOT/.git/hooks/validate_control_risk_references.py"

echo "Installing git hooks..."

# Check if source files exist
if [[ ! -f "$REPO_ROOT/${PRECOMMIT_SRC}" ]]; then
    echo "❌ Error: ${PRECOMMIT_SRC} not found"
    exit 1
fi

if [[ ! -f "$REPO_ROOT/${VALIDATOR_SRC}" ]]; then
    echo "❌ Error: ${VALIDATOR_SRC} not found"
    exit 1
fi

if [[ ! -f "$REPO_ROOT/${REF_VALIDATOR_SRC}" ]]; then
    echo "❌ Error: ${REF_VALIDATOR_SRC} not found"
    exit 1
fi

# Check if target files already exist
EXISTING_HOOK=false
EXISTING_VALIDATOR=false
EXISTING_REF_VALIDATOR=false

if [[ -f "$TARGET_HOOK" ]]; then
    EXISTING_HOOK=true
fi

# Only tests for the main script -> assumes the module directory will exist if the script does...
if [[ -f "$TARGET_VALIDATOR" ]]; then
    EXISTING_VALIDATOR=true
fi

if [[ -f "$TARGET_REF_VALIDATOR" ]]; then
    EXISTING_REF_VALIDATOR=true
fi

if [[ ($EXISTING_HOOK == true || $EXISTING_VALIDATOR == true || $EXISTING_REF_VALIDATOR == true) && "$FORCE" != "true" ]]; then
    echo "❌ Error: One or more hooks already exist:"
    [[ $EXISTING_HOOK == true ]] && echo "   - pre-commit hook exists at $TARGET_HOOK"
    [[ $EXISTING_VALIDATOR == true ]] && echo "   - component validator exists at $TARGET_VALIDATOR"
    [[ $EXISTING_REF_VALIDATOR == true ]] && echo "   - control-to-risk reference validator exists at $TARGET_REF_VALIDATOR"
    echo ""
    echo "💡 Use --force to overwrite, or remove the existing hooks manually"
    echo "   Example: $0 --force"
    exit 1
fi

# Create .git/hooks directory if it doesn't exist
mkdir -p "$REPO_ROOT/.git/hooks"

# Install pre-commit hook
echo "📋 Installing pre-commit hook..."
cp "$REPO_ROOT/${PRECOMMIT_SRC}" "$TARGET_HOOK"
chmod +x "$TARGET_HOOK"

# Install component edge validator
echo "🔗 Installing component edge validator..."
mkdir -p "${TARGET_VALIDATOR_MODULE}"
cp "${REPO_ROOT}/${VALIDATOR_SRC}" "${TARGET_VALIDATOR}"
cp ${REPO_ROOT}/${VALIDATOR_MODULE_SRC}/*.py "${TARGET_VALIDATOR_MODULE}/"
chmod +x "$TARGET_VALIDATOR"

# Install control-to-risk reference validator
echo "🔗 Installing control-to-risk reference validator..."
cp "$REPO_ROOT/${REF_VALIDATOR_SRC}" "$TARGET_REF_VALIDATOR"
chmod +x "$TARGET_REF_VALIDATOR"

# Success message
if [[ "$FORCE" == "true" ]]; then
    echo ""
    echo "✅ Git hooks installed successfully! (overwritten existing hooks)"
else
    echo ""
    echo "✅ Git hooks installed successfully!"
fi

echo ""
echo "📝 Installed hooks:"
echo "   - Pre-commit hook: $TARGET_HOOK"
echo "   - Edge validator: $TARGET_VALIDATOR"
echo "   - Control-to-risk validator: $TARGET_REF_VALIDATOR"
echo ""
echo "🔍 These hooks will now run automatically before each commit to validate:"
echo "   ✅ YAML schema compliance"
echo "   ✅ Component edge consistency"
echo "   ✅ Control-to-risk reference consistency"
echo ""
echo "💡 To bypass hooks temporarily: git commit --no-verify"
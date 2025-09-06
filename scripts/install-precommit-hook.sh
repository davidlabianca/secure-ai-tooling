#!/bin/bash

# Simple git hook installer
# Copies scripts/hooks/precommit to .git/hooks/pre-commit
# Usage: ./install-pre-commit-hook.sh [--force]

set -e

# Parse command line arguments
FORCE=false
PRECOMMIT_SRC="scripts/hooks/pre-commit"

while [[ $# -gt 0 ]]; do
    case $1 in
        --force|-f)
            FORCE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--force]"
            echo "  --force, -f    Overwrite existing pre-commit hook"
            echo "  --help, -h     Show this help message"
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

echo "Installing git hooks..."

# Check if source hook exists
if [[ ! -f "$REPO_ROOT/${PRECOMMIT_SRC}" ]]; then
    echo "❌ Error: scripts/tools/precommit not found"
    exit 1
fi

# Check if target hook already exists
if [[ -f "$TARGET_HOOK" && "$FORCE" != "true" ]]; then
    echo "❌ Error: pre-commit hook already exists at $TARGET_HOOK"
    echo "💡 Use --force to overwrite, or remove the existing hook manually"
    echo "   Example: $0 --force"
    exit 1
fi

# Create .git/hooks directory if it doesn't exist
mkdir -p "$REPO_ROOT/.git/hooks"

# Copy and make executable
cp "$REPO_ROOT/${PRECOMMIT_SRC}" "$TARGET_HOOK"
chmod +x "$TARGET_HOOK"

if [[ "$FORCE" == "true" ]]; then
    echo "✅ Git hooks installed successfully! (overwritten existing hook)"
else
    echo "✅ Git hooks installed successfully!"
fi
echo "📝 Pre-commit hook installed from scripts/tools/precommit"
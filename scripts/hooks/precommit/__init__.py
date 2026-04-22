"""Pre-commit framework hook entry-points for the CoSAI Risk Map.

Each module in this package is a standalone script invoked by the pre-commit
framework via .pre-commit-config.yaml. Modules wrap existing validators and
generators in scripts/hooks/ and stage their output via `git add` (Mode B
auto-stage), preserving the atomic-commit UX of the previous bash hook.
"""

# Manual Graph Generation

Generate the component graph manually using the validation script:

```bash
# Validate edges and generate clean component graph without debug comments
python3 scripts/hooks/validate_riskmap.py --to-graph ./docs/component-map.md --force

# Generate component graph with rank debugging information
python3 scripts/hooks/validate_riskmap.py --to-graph ./docs/debug-graph.md --debug --force
```

## Graph Generation Options

- `--to-graph PATH` - Output component relationship Mermaid graph to specified file
- `--debug` - Include rank comments for debugging
- `--quiet` - Minimize output (only show errors)
- `--allow-isolated` - Allow components with no edges

## Debugging Graph Generation

Test graph generation without affecting git staging:

```bash
# Generate component graph to test output
python3 scripts/hooks/validate_riskmap.py --to-graph ./test-graph.md --force

# Generate component graph with debug information to understand ranking
python3 scripts/hooks/validate_riskmap.py --to-graph ./debug-graph.md --debug --force

# View help for all graph options
python3 scripts/hooks/validate_riskmap.py --help
```

## Common Graph Generation Issues

```
❌ Graph generation failed
```

**Fix**: Check that `components.yaml` is valid and accessible, ensure write permissions for output directory

```
⚠️ Warning: Could not stage generated graph
```

**Fix**: This occurs during pre-commit when git staging fails - check file permissions and git repository status

---

**Related:**
- [Hook Validations](hook-validations.md) - Automatic graph generation during commits
- [Styling Configuration](styling-configuration.md) - Customizing graph appearance
- [Troubleshooting](troubleshooting.md) - More debugging options

# Troubleshooting Validation Issues

This page covers common validation issues and how to resolve them.

## Edge Validation Errors

If the pre-commit hook or manual validation fails with edge consistency errors:

### 1. Bidirectional Edge Mismatch

```
Component 'componentA': missing incoming edges for: componentB
```

**Fix**: Add `componentA` to `componentB`'s `edges.from` list

### 2. Isolated Component

```
Found 1 isolated components (no edges): componentX
```

**Fix**: Add appropriate `to` and/or `from` edges, or verify if isolation is intentional

## Graph Generation Issues

If you encounter issues with the automatic graph generation:

### 1. Component graph generation failed during pre-commit

```
❌ Graph generation failed
```

**Fix**: Check that `components.yaml` is valid and accessible. Test manually:

```bash
python scripts/hooks/validate_riskmap.py --to-graph ./test-graph.md --force
```

### 2. Control-to-component graph generation failed

```
❌ Control-to-component graph generation failed
```

**Fix**: Verify that both `controls.yaml` and `components.yaml` are accessible and properly formatted. Test manually:

```bash
python scripts/hooks/validate_riskmap.py --to-controls-graph ./test-controls.md --force
```

### 3. Generated graph not staged

```
⚠️ Warning: Could not stage generated graph
```

**Fix**: Check file permissions and git repository status. Ensure `./risk-map/docs/` directory is writable.

### 4. Component layout seems suboptimal

**Fix**: Use debug mode to inspect graph structure:

```bash
python scripts/hooks/validate_riskmap.py --to-graph ./debug-graph.md --debug --force
```

### 5. Control graph looks cluttered or confusing

**Fix**: The control graph uses automatic optimization. If results seem wrong, verify:
- Control component references are accurate in `controls.yaml`
- Component categories are correctly assigned in `components.yaml`
- Test the graph generation manually to inspect the output

## Bypassing Validation (Not Recommended)

If you need to commit without running the pre-commit hook (strongly discouraged):

```bash
git commit --no-verify -m "commit message"
```

However, your changes will still be validated during the PR review process.

---

**Related:**
- [Validation Tools](validation.md) - Manual validation commands
- [CI/CD Validation](ci-cd.md) - Handling CI validation failures
- [Best Practices](best-practices.md) - Avoiding common issues

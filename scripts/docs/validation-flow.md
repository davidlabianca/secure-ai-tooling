# Validation Flow

When you commit changes, the hook will:

1. **Schema Validation** - Check YAML structure and data types
2. **Prettier Formatting** - Format YAML files in `risk-map/yaml/` and re-stage them
3. **Ruff Linting** - Lint Python files for code quality
4. **Edge Validation** - Verify component relationship consistency
5. **Graph Generation** - Generate and stage graphs based on file changes:
   - If `components.yaml` changed: generate `./risk-map/diagrams/risk-map-graph.md`
   - If `components.yaml` or `controls.yaml` changed: generate `./risk-map/diagrams/controls-graph.md`
   - If `components.yaml`, `controls.yaml` or `risks.yaml` changed: generate `./risk-map/diagrams/controls-to-risk-graph.md`
6. **SVG Generation** - Convert staged Mermaid files to SVG format:
   - If `.mmd/.mermaid` files changed: generate corresponding SVG files in `./risk-map/svg/`
7. **Table Generation** - Convert staged YAML files to markdown tables:
   - If `components.yaml` changed: generate component tables + regenerate controls-xref-components
   - If `risks.yaml` changed: generate risk tables + regenerate controls-xref-risks
   - If `controls.yaml` changed: generate all 4 control table formats
8. **Control-Risk Validation** - Verify control-risk cross-reference consistency
9. **Block commit** if any validation fails

**Note**: Graph and table generation only occur when relevant files are staged for commit, not in `--force` mode.

---

**Related:**
- [Hook Validations](hook-validations.md) - Details of each validation
- [Manual Validation](manual-validation.md) - Running validations with --force
- [Troubleshooting](troubleshooting.md) - Handling validation failures

# Validation Flow

When you commit changes, the pre-commit framework reads `.pre-commit-config.yaml`
at the repo root, selects hooks whose `files:` regex matches the staged set,
and runs them in declaration order. The sequence below matches the current
config exactly. Each hook only runs when its trigger files are staged; unused
hooks show `(no files to check) Skipped` in the output.

1. **Schema Validation** — one `check-jsonschema` hook per yaml/schema pair
   (10 pairs: actor-access, components, controls, frameworks, impact-type,
   lifecycle-stage, mermaid-styles, personas, risks, self-assessment).
2. **Schema Master Trigger** — when `risk-map/schemas/riskmap.schema.json`
   itself is staged, every yaml is re-validated against its schema.
3. **Prettier Formatting** — `prettier-yaml` wrapper formats yamls under
   `risk-map/yaml/` and `git add`s the reformatted output (Mode B auto-stage).
4. **Ruff Lint** — `ruff` checks staged Python files.
5. **Ruff Format** — `ruff-format` formats staged Python files.
6. **Component Edge Validation** — `validate_riskmap.py` runs when
   `components.yaml` is staged.
7. **Control-to-Risk Reference Validation** — `validate_control_risk_references.py`
   runs when `controls.yaml` or `risks.yaml` is staged.
8. **Framework Reference Validation** — `validate_framework_references.py`
   runs when `controls`, `frameworks`, `personas`, or `risks` yaml is staged.
9. **Issue Template Regeneration** — `regenerate_issue_templates.py` runs
   when any template source, any schema, or `frameworks.yaml` is staged;
   generates `.github/ISSUE_TEMPLATE/*.yml` and stages them.
10. **Issue Template Validation** — `validate_issue_templates.py` runs when
    anything under `.github/ISSUE_TEMPLATE/` or `scripts/TEMPLATES/` is
    staged (including the files just regenerated in step 9).
11. **Graph Regeneration** — `regenerate_graphs.py` produces risk-map graph,
    controls graph, and controls-to-risk graph (3 markdown + 3 mermaid outputs)
    based on which of `components.yaml`, `controls.yaml`, `risks.yaml` is
    staged. Each output pair is `git add`-ed on success.
12. **Table Regeneration** — `regenerate_tables.py` regenerates 8 table
    outputs across 4 triggers (see `scripts/docs/table-generation.md`).
13. **SVG Regeneration** — `regenerate_svgs.py` converts staged
    `risk-map/diagrams/*.mmd` or `*.mermaid` files to SVG.

The commit is blocked if any hook returns non-zero.

## Running the full sequence manually

```bash
# Against the working tree (does NOT require staged files):
pre-commit run --all-files

# Against only staged files (same as what git commit does):
pre-commit run
```

Note: `pre-commit run --all-files` will also run the generators, which may
modify derivatives in your working tree. To validate without regeneration,
use `scripts/tools/validate-all.sh` (see [Manual Validation](manual-validation.md)).

---

**Related:**
- [Hook Validations](hook-validations.md) — Details of each hook
- [Manual Validation](manual-validation.md) — Running validators without committing
- [Troubleshooting](troubleshooting.md) — Handling validation failures

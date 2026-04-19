# Manual Validation of Unstaged Files

Each validator under `scripts/hooks/` accepts a `--force` flag that validates
all relevant files regardless of git staging status. This is the recommended
workflow while iterating on content: it catches issues without committing and
does NOT regenerate derivatives (no graph/table/SVG churn).

The framework pre-commit hook itself does not have a `--force` flag — use
`pre-commit run --all-files` instead, but note that this also runs the
regeneration hooks and modifies the working tree.

> **Caveat: `pre-commit run --all-files` has side effects on the git index.**
> The Mode B regenerator hooks (`regenerate-graphs`, `regenerate-tables`,
> `regenerate-svgs`, `regenerate-issue-templates`, `prettier-yaml`) all call
> `git add` on their outputs so derivatives land in the same commit as their
> source. When invoked via `--all-files`, these hooks run unconditionally and
> stage any bytes that differ from HEAD — most commonly the SVGs, which
> change run-to-run as mmdc / Chromium versions drift. If you plan to make
> an UNRELATED commit after running `--all-files`, unstage the bycatch first
> so it does not ride along:
>
> ```bash
> git restore --staged risk-map/svg/ risk-map/tables/ risk-map/diagrams/ \
>                      .github/ISSUE_TEMPLATE/
> ```
>
> For safer verification, prefer scoped invocations — e.g.,
> `pre-commit run <hook-id> --files <specific-files>` — or use
> `./scripts/tools/validate-all.sh` (below), which validates without
> regenerating anything.

## Recommended: unified dev helper

`scripts/tools/validate-all.sh` runs every validator with `--force` in one
command and returns non-zero if any fail. This is the direct replacement for
the prior `pre-commit.sh --force` workflow.

```bash
# Validate everything, no commit, no regeneration:
./scripts/tools/validate-all.sh

# Help:
./scripts/tools/validate-all.sh --help
```

## Individual validators

```bash
# Component edge consistency
python3 scripts/hooks/validate_riskmap.py --force

# Control-to-risk cross references
python3 scripts/hooks/validate_control_risk_references.py --force

# Framework references
python3 scripts/hooks/validate_framework_references.py --force

# Issue template schemas
python3 scripts/hooks/validate_issue_templates.py --force
```

## Running a single framework hook

To exercise a single hook declaratively (using the framework's config), run:

```bash
# By hook id, against all files in the repo:
pre-commit run validate-component-edges --all-files
pre-commit run check-jsonschema --all-files

# Against a specific file set:
pre-commit run validate-component-edges --files risk-map/yaml/components.yaml
```

Note: framework hooks with `pass_filenames: false` (the validators) will
self-scan the repo regardless of what files you pass.

## Regeneration without committing

To regenerate derivatives (graphs, tables, SVGs) without staging a commit:

```bash
# Graphs (components, controls, risks)
python3 scripts/hooks/validate_riskmap.py --to-graph risk-map/diagrams/risk-map-graph.md -m --quiet
python3 scripts/hooks/validate_riskmap.py --to-controls-graph risk-map/diagrams/controls-graph.md -m --quiet
python3 scripts/hooks/validate_riskmap.py --to-risk-graph risk-map/diagrams/controls-to-risk-graph.md -m --quiet

# Tables
python3 scripts/hooks/yaml_to_markdown.py components --all-formats --quiet
python3 scripts/hooks/yaml_to_markdown.py controls --all-formats --quiet
python3 scripts/hooks/yaml_to_markdown.py risks --all-formats --quiet
python3 scripts/hooks/yaml_to_markdown.py personas --all-formats --quiet

# SVGs (reads CHROMIUM_PATH env or auto-discovers Playwright Chromium on ARM64)
python3 scripts/hooks/precommit/regenerate_svgs.py risk-map/diagrams/<file>.mmd
```

---

**Related:**
- [Validation Flow](validation-flow.md) - Commit-time validation order
- [Graph Generation](graph-generation.md) - Graph generator deep-dive
- [Table Generation](table-generation.md) - Table generator deep-dive
- [Troubleshooting](troubleshooting.md) - Debugging validation failures

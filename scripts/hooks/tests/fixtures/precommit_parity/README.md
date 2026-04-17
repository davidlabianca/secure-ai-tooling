# Pre-commit Parity Fixture

Kitchen-sink change set for verifying behavioral parity between the legacy
bash pre-commit hook (`scripts/hooks/pre-commit`) and the upstream
`pre-commit` framework (`.pre-commit-config.yaml`) introduced by #211.

## What it does

`apply.py` idempotently appends a marker comment to seven trigger files,
exercising every conditional branch in the bash hook:

| Trigger file                                   | Hooks exercised                                         |
|------------------------------------------------|---------------------------------------------------------|
| `risk-map/yaml/components.yaml`                | schema, prettier, component-edge val, graphs, tables    |
| `risk-map/yaml/controls.yaml`                  | schema, prettier, control-risk val, graphs, tables      |
| `risk-map/yaml/risks.yaml`                     | schema, prettier, control-risk val, graphs, tables      |
| `risk-map/yaml/personas.yaml`                  | schema, prettier, framework refs val, tables            |
| `risk-map/yaml/frameworks.yaml`                | schema, prettier, framework refs val, issue templates   |
| `scripts/TEMPLATES/new_component.template.yml` | issue templates regen + validation                      |
| `risk-map/diagrams/controls-graph.mermaid`     | SVG regen (file is also rewritten by graph regen)       |

## Usage

```bash
python scripts/hooks/tests/fixtures/precommit_parity/apply.py
```

`apply.py` is idempotent: re-running on a checkout that already has the
marker leaves files unchanged. This lets the harness replay it inside two
separate clones without depending on each clone's prior state.

## Why this lives in the repo

The fixture is consumed by the parity harness (`precommit_parity.sh`,
introduced alongside it) and the parity CI workflow
(`.github/workflows/precommit_parity.yml`). All three exist solely to gate
the #211 migration and **are deleted in the same PR that lands the bash hook
removal**.

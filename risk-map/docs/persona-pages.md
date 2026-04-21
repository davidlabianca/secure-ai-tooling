# CoSAI Risk Map Explorer

This document describes the static GitHub Pages experience for CoSAI-RM persona matching and persona-driven risk/control browsing.

## Overview

The persona site is intentionally lightweight:

- `risk-map/site/` contains the static HTML, CSS, and browser-side JavaScript.
- `scripts/build_persona_site_data.py` reads `risk-map/yaml/personas.yaml`, `risk-map/yaml/risks.yaml`, and `risk-map/yaml/controls.yaml`.
- The builder writes generated JSON to `risk-map/site/generated/persona-site-data.json` for local preview, or to another site directory during CI deployment.

The site does not use a backend and does not store answers server-side. User answers are held in browser memory for the current session only.

## Data Flow

The framework YAML stays the source of truth.

1. Active personas are read from `personas.yaml`.
2. Guided persona questions come from `identificationQuestions`.
3. Manual fallback personas are the active personas with fewer than five identification questions.
4. Risks are derived from `risks.yaml.personas`.
5. Controls are derived from `controls.yaml.personas`.
6. Shared risks and controls are deduplicated client-side after persona selection.

The legacy `risk-map/yaml/self-assessment.yaml` remains unchanged and can coexist with this MVP.

## Local Build And Preview

Generate the site data:

```bash
python3 scripts/build_persona_site_data.py
```

Serve the site directory locally:

```bash
python3 -m http.server --directory risk-map/site 8000
```

Then open [http://localhost:8000](http://localhost:8000).

If you want to build into a different staging directory instead of `risk-map/site/generated/`, pass `--site-dir` or `--output`:

```bash
python3 scripts/build_persona_site_data.py --site-dir /tmp/cosai-persona-site
python3 scripts/build_persona_site_data.py --output /tmp/persona-site-data.json
```

## Validation

Run the focused validations for this MVP:

```bash
ruff check .
pytest scripts/hooks/tests/test_build_persona_site_data.py
node --test risk-map/site/tests/*.test.mjs
python3 scripts/build_persona_site_data.py
```

The Python tests cover YAML loading and transformation. The Node tests cover persona matching, manual fallback behavior, and deduplication logic.

These focused checks are the validation bar for the explorer itself. Some broader repository tests are currently environment-sensitive and may fail locally even when the explorer changes are correct:

- `scripts/hooks/tests/test_verify_deps.py -k all_dependencies_present_exit_0` expects a Python 3.14 environment on `PATH`.
- `scripts/hooks/tests/test_install_deps.py::TestSkipChromiumWhenPresent::test_chromium_in_cache_emits_skip` depends on local Chromium cache state.

## GitHub Pages Deployment

The workflow at `.github/workflows/persona-pages.yml` handles this MVP:

- Pull requests to `main` run the focused Python and Node tests and validate that the static site artifact can be assembled.
- Pushes to `main` rebuild the site artifact, enable GitHub Pages if needed, and deploy the explorer.
- Deployment builds from a clean `_site/` copy so generated JSON does not need to be committed.

## Maintenance Notes

- Update the framework YAML first. Rebuild the site data after persona, risk, or control changes.
- If additional personas gain full `identificationQuestions`, they will automatically move from the manual-fallback section into the guided question flow.
- `AI System Governance` currently has control mappings but no direct risk mappings in the framework data. The site therefore shows governance controls and a clear risks empty-state note.

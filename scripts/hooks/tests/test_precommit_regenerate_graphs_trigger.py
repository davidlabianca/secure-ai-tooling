#!/usr/bin/env python3
"""
Structural drift-guard test for the `regenerate-graphs` pre-commit hook's
`files:` trigger regex (ADR-036 D3/D7).

The hook emits only the component Mermaid graph (`regenerate_graphs.py`
carries no `ControlGraph`/`RiskGraph` dispatch), so its `files:` regex is
`^risk-map/yaml/(components|mermaid-styles)\\.yaml$`. ADR-036 lands
`graphTypes.component.emission` (mode/aspects/concerns/portStyles) in
`mermaid-styles.yaml`; an edit to that file (e.g. a `mode: flat ->
decoupled` flip, or a future aspects/concerns registry edit) changes what the
generated `.mermaid`/`.svg` diagrams SHOULD look like, so the hook firing on
that file keeps the committed diagrams from silently going stale.
`controls.yaml`/`risks.yaml` do not affect the component graph and must NOT
trigger it.

This suite pins `.pre-commit-config.yaml`'s `files:` regex as a regression
guard, so a future edit cannot silently narrow it back to `components.yaml`
alone.

Mirrors the conventions in test_precommit_hook_install.py and
test_precommit_neutrality_config.py: `_load_config`/`_all_hooks`/`_hooks_by_id`
helpers, `re.search` semantics against `files:` regexes (matching the
pre-commit framework's own matching behavior).
"""

import re
from pathlib import Path

import yaml

# Repo root is four levels up from this file (scripts/hooks/tests/<here>),
# matching test_precommit_neutrality_config.py's convention.
REPO_ROOT = Path(__file__).parent.parent.parent.parent
CONFIG_PATH = REPO_ROOT / ".pre-commit-config.yaml"

HOOK_ID = "regenerate-graphs"

# The two trigger files that must re-fire the hook: components.yaml (the
# existing content source) plus mermaid-styles.yaml (carrying
# the emission config this hook must react to).
TRIGGER_PATHS = (
    "risk-map/yaml/components.yaml",
    "risk-map/yaml/mermaid-styles.yaml",
)

# Paths that must NOT trigger the hook. controls.yaml and risks.yaml sit here
# on purpose: the hook emits only the component graph, so edits to the
# control/risk catalogs have no diagram to regenerate. The rest guard against
# a regex broadened carelessly (e.g. a bare `.*\.yaml$` or a missing `$`
# anchor) that could accidentally start matching unrelated yaml files.
NON_TRIGGER_PATHS = (
    "risk-map/yaml/controls.yaml",
    "risk-map/yaml/risks.yaml",
    "risk-map/yaml/personas.yaml",
    "risk-map/yaml/lifecycle-stage.yaml",
    "risk-map/schemas/mermaid-styles.schema.json",
)


def _load_config() -> dict:
    """Return the parsed .pre-commit-config.yaml as a dict."""
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def _all_hooks() -> list[dict]:
    """Return every hook declaration across all repos in the config."""
    config = _load_config()
    hooks: list[dict] = []
    for repo in config.get("repos", []):
        hooks.extend(repo.get("hooks", []))
    return hooks


def _hooks_by_id(hook_id: str) -> list[dict]:
    """Return all hook declarations matching the given id (may be multiple)."""
    return [h for h in _all_hooks() if h.get("id") == hook_id]


class TestRegenerateGraphsTrigger:
    def test_regenerate_graphs_hook_exists(self):
        """Sanity check: exactly one regenerate-graphs hook is declared."""
        hooks = _hooks_by_id(HOOK_ID)
        assert len(hooks) == 1, f"Expected exactly one '{HOOK_ID}' hook; got {len(hooks)}"

    def test_files_regex_matches_mermaid_styles_yaml(self):
        """
        Given: the regenerate-graphs hook's `files:` regex
        When: applied against risk-map/yaml/mermaid-styles.yaml
        Then: it matches

        Pins the regex against regressing to `^risk-map/yaml/components\\.yaml$`,
        which has no `mermaid-styles` alternative and would let an emission
        block edit (including a `mode: flat -> decoupled` flip) go without
        re-triggering diagram regeneration.
        """
        hooks = _hooks_by_id(HOOK_ID)
        assert len(hooks) == 1, f"{HOOK_ID} hook missing"
        files_regex = hooks[0].get("files", "")

        assert re.search(files_regex, "risk-map/yaml/mermaid-styles.yaml"), (
            f"regenerate-graphs files: regex {files_regex!r} must match "
            f"risk-map/yaml/mermaid-styles.yaml so an emission-block edit "
            f"(including a mode: flat -> decoupled flip) re-triggers diagram "
            f"regeneration."
        )

    def test_files_regex_still_matches_existing_trigger_files(self):
        """
        Regression guard: adding mermaid-styles.yaml to the trigger must not narrow or
        otherwise break the existing components.yaml trigger.
        """
        hooks = _hooks_by_id(HOOK_ID)
        assert len(hooks) == 1, f"{HOOK_ID} hook missing"
        files_regex = hooks[0].get("files", "")

        missing = [p for p in TRIGGER_PATHS if not re.search(files_regex, p)]
        assert not missing, (
            f"regenerate-graphs files: regex {files_regex!r} must match every path "
            f"in TRIGGER_PATHS; missing matches for: {missing}"
        )

    def test_files_regex_does_not_match_unrelated_yaml_files(self):
        """
        Self-trip / over-broadening guard: the change must be an additive
        alternative (`mermaid-styles` joining the existing alternation), not
        a wholesale widening (e.g. dropping the `$` anchor or matching any
        `.yaml` file) that would start firing on unrelated risk-map YAML or
        schema files.
        """
        hooks = _hooks_by_id(HOOK_ID)
        assert len(hooks) == 1, f"{HOOK_ID} hook missing"
        files_regex = hooks[0].get("files", "")

        unexpected_matches = [p for p in NON_TRIGGER_PATHS if re.search(files_regex, p)]
        assert not unexpected_matches, (
            f"regenerate-graphs files: regex {files_regex!r} must NOT match "
            f"{unexpected_matches} -- the change should add mermaid-styles as an "
            f"alternative in the existing group, not broaden the pattern generally."
        )

    def test_pass_filenames_and_require_serial_unchanged(self):
        """
        Regression guard: the change is scoped to the `files:` regex only --
        `pass_filenames: true` and `require_serial: true` must be preserved
        (per the hook's own comment on batching / index.lock contention).
        """
        hooks = _hooks_by_id(HOOK_ID)
        assert len(hooks) == 1, f"{HOOK_ID} hook missing"
        hook = hooks[0]
        assert hook.get("pass_filenames") is True, (
            f"regenerate-graphs pass_filenames must remain True; got {hook.get('pass_filenames')!r}"
        )
        assert hook.get("require_serial") is True, (
            f"regenerate-graphs require_serial must remain True; got {hook.get('require_serial')!r}"
        )

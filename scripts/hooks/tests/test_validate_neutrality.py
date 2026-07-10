#!/usr/bin/env python3
"""
Tests for scripts/hooks/precommit/validate_neutrality.py (does not exist yet — TDD red phase).

ADR-033 D2a/D5 establish a "vendor-neutral shipping" contract for the two
authoring surfaces that ship in this repository: `scripts/agents/**` and
`scripts/skills/**`. Prose in those trees must not name a specific AI harness
product, company, CLI entry point, or model identifier; must not embed
harness-invocation stage directions (`<invoke ... tool>`, `subagent_type`,
"auto-loads"/"auto-triggers"); and must not reference harness-specific config
paths (`.claude/`, `.cursor/`, etc.). Framework-authority references (MITRE,
NIST, OWASP, ISO, EU AI Act, STRIDE) are legitimate content and must never be
flagged, even adjacent to real denylist hits.

A distinct structural rule governs YAML frontmatter: a `SKILL.md` file may
only declare `name`/`description` in its frontmatter; an agent `.md` file
(ADR-006 prose form, ordinarily frontmatter-free) must not declare a runtime-
binding key (`tools`, `model`, `color`, `allowed-tools`/`allowed_tools`) if it
happens to have a frontmatter block at all.

Public API under test (scripts/hooks/precommit/validate_neutrality.py):
    - `HOOK_NAME = "validate-neutrality"`
    - `Violation` frozen dataclass: `path`, `line`, `token`, `message`.
      `token` carries the matched offending snippet (e.g. "Claude Code",
      ".cursor/", "subagent_type") so a maintainer can grep for it.
    - `validate_file(path: Path) -> list[Violation]` — denylist scan (with
      allowlist suppression) plus frontmatter-key checks for one file.
      Returns `[]` (not `None`) when clean.
    - `discover_neutral_surface_files(root: Path) -> list[Path]` — files
      under `root/scripts/agents/**` and `root/scripts/skills/**` only.
    - `format_violation(violation: Violation) -> str` — stderr line,
      `<hook_name>: <file>:<line>: <message>`.
    - `main(argv: list[str]) -> int` — CLI entry point; explicit file args or
      self-discovery; returns 1 if any violations, else 0.

`scripts/hooks/precommit/_neutrality_data.py` is the sanctioned place vendor
tokens legitimately appear as detection data. Its exact export names are not
locked by this test file (see the single regression-guard test in
`TestFrameworkAllowlist`); behavioral coverage goes through `validate_neutrality`.

Out of scope for this suite (documented so it doesn't read as an oversight):
CRLF line-ending handling (not in the ADR-033 brief this suite targets) and
frontmatter *required*-field validation (name/description presence). The
frontmatter tests here only enforce the ceiling — no extra/binding keys — not
the floor — required keys present — which is deferred to a later phase that
reconciles against the Agent Skills reference validator.
"""

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "precommit"))

import validate_neutrality  # noqa: E402
from validate_neutrality import (  # noqa: E402
    discover_neutral_surface_files,
    format_violation,
    main,
    validate_file,
)


def _write_agent_file(tmp_path: Path, content: str, name: str = "test-agent.md") -> Path:
    """Write a synthetic agent-shaped file under <tmp_path>/scripts/agents/ and return its path."""
    agents_dir = tmp_path / "scripts" / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    path = agents_dir / name
    path.write_text(content, encoding="utf-8")
    return path


def _write_skill_file(tmp_path: Path, content: str, skill_dir: str = "example-skill") -> Path:
    """Write a synthetic SKILL.md under <tmp_path>/scripts/skills/<skill_dir>/ and return its path."""
    skill_path = tmp_path / "scripts" / "skills" / skill_dir
    skill_path.mkdir(parents=True, exist_ok=True)
    path = skill_path / "SKILL.md"
    path.write_text(content, encoding="utf-8")
    return path


def _write_plain_file(tmp_path: Path, relative: str, content: str) -> Path:
    """Write content at an arbitrary repo-relative path under tmp_path; used for scope-boundary tests."""
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


class TestDenylistVendorProductNames:
    """
    Vendor/product/company/CLI identifiers are flagged (ADR-033 denylist category 1).

    Each case proves validate_file returns a non-empty violation list and the
    violation names the actual offending text so a maintainer can grep for it.
    """

    @pytest.mark.parametrize(
        "token",
        [
            "Anthropic",
            "OpenAI",
            "Claude Code",
            "GitHub Copilot",
            "ChatGPT",
            "GPT",
            "Copilot",
            "Cursor",
            "Windsurf",
            "Codeium",
            "Gemini",
            "Cody",
            "Devin",
            "Aider",
        ],
    )
    def test_vendor_product_or_company_name_is_flagged(self, tmp_path, token):
        """
        Given: An agent file mentioning a specific vendor, product, company, or CLI name
        When: validate_file scans the file
        Then: At least one violation is returned naming that token
        """
        agent = _write_agent_file(tmp_path, f"This agent was tested against {token} during development.\n")

        violations = validate_file(agent)

        assert violations != []
        assert any(token in v.token or token in v.message for v in violations)

    @pytest.mark.parametrize(
        "model_id",
        ["claude-sonnet-4-5", "gpt-4o", "gemini-1.5-pro"],
    )
    def test_model_identifier_pattern_is_flagged(self, tmp_path, model_id):
        """
        Given: An agent file mentioning a model-identifier-shaped string
        When: validate_file scans the file
        Then: One violation names the matched model identifier
        """
        agent = _write_agent_file(tmp_path, f"Pin the model to {model_id} for reproducible output.\n")

        violations = validate_file(agent)

        assert violations != []
        assert any(model_id in v.token or model_id in v.message for v in violations)

    def test_bare_word_model_in_ordinary_prose_produces_no_violations(self, tmp_path):
        """
        Given: An agent file using "model" as ordinary neutral terminology (persona name,
               threat model, model card), with no model-identifier-shaped string present
        When: validate_file scans the file
        Then: No violations are produced

        The real corpus uses "model" pervasively as neutral terminology (Model
        Provider persona, threat model, model card). Only a model-identifier
        *pattern* (e.g. `claude-sonnet-4-5`, `gpt-4o`) is denylisted, never the
        bare word "model" — this is the false-positive class the ADR-033 brief
        specifically calls out.
        """
        agent = _write_agent_file(
            tmp_path,
            "The Model Provider persona owns the threat model and model card review.\n",
        )

        violations = validate_file(agent)

        assert violations == []

    def test_cli_entrypoint_lowercase_form_is_flagged(self, tmp_path):
        """
        Given: An agent file with a shell-command-shaped line invoking a lowercase CLI entry point,
               with no other denylisted token present in the fixture
        When: validate_file scans the file
        Then: The CLI invocation is flagged despite lacking the product's capitalized form

        Decision: the vendor/product denylist match is case-insensitive for the
        CLI-entrypoint shape so that `claude --resume` in example shell commands
        is caught even when written in lowercase. The fixture deliberately
        contains no model-identifier string (unlike the parametrized cases
        above) so this test isolates the lowercase/backtick CLI-entrypoint
        behavior rather than incidentally passing on an unrelated match.
        """
        agent = _write_agent_file(tmp_path, "Run `claude --resume` to continue the session.\n")

        violations = validate_file(agent)

        assert violations != []
        assert any("claude" in v.token.lower() or "claude" in v.message.lower() for v in violations)


class TestDenylistHarnessInvocationTokens:
    """Harness-invocation stage directions are flagged (ADR-033 denylist category 1)."""

    @pytest.mark.parametrize(
        "line",
        [
            "<invoke the Bash tool>",
            "<uses the Read tool>",
            "\\<invoke the Bash tool\\>",
        ],
        ids=["invoke_unescaped", "uses_unescaped", "invoke_backslash_escaped"],
    )
    def test_invoke_tool_stage_direction_is_flagged(self, tmp_path, line):
        """
        Given: An agent file containing an angle-bracket stage direction naming a tool invocation,
               either unescaped or backslash-escaped (the corpus convention seen in
               scripts/agents/*.md worked examples, e.g. `\\<invoke ... agent\\>`)
        When: validate_file scans the file
        Then: One violation names the offending stage direction

        The backslash-escaped form is included because the real corpus escapes
        angle brackets in worked examples to keep markdown renderers from
        treating them as HTML tags; the checker must not be fooled by the
        escaping into missing a real "tool" invocation shape.
        """
        agent = _write_agent_file(tmp_path, f"{line}\n")

        violations = validate_file(agent)

        assert violations != []

    @pytest.mark.parametrize("spelling", ["subagent_type", "subagent-type"])
    def test_subagent_type_token_is_flagged(self, tmp_path, spelling):
        """
        Given: An agent file containing a subagent_type/subagent-type key or token
        When: validate_file scans the file
        Then: One violation names the offending token
        """
        agent = _write_agent_file(tmp_path, f"Dispatch with {spelling}: general-purpose\n")

        violations = validate_file(agent)

        assert violations != []
        assert any(spelling in v.token or spelling in v.message for v in violations)

    @pytest.mark.parametrize(
        "phrase",
        ["auto-loads", "auto-loaded", "auto-triggers", "auto-triggered"],
    )
    def test_auto_loads_or_auto_triggers_phrasing_is_flagged(self, tmp_path, phrase):
        """
        Given: An agent file describing runtime dispatch with "auto-loads"/"auto-triggers" phrasing
        When: validate_file scans the file
        Then: One violation names the offending phrase
        """
        agent = _write_agent_file(tmp_path, f"This skill {phrase} when the description matches.\n")

        violations = validate_file(agent)

        assert violations != []

    def test_invoke_agent_without_tool_word_is_not_flagged(self, tmp_path):
        """
        Given: An angle-bracket stage direction naming a sub-agent but NOT a tool
               (`\\<invoke architect agent\\>`, the real shape used in scripts/agents/*.md)
        When: validate_file scans the file
        Then: No harness-invocation-token violation is produced

        The denylist shape requires the literal word "tool" inside the
        brackets. "invoke <agent-name> agent" is the repo's own convention for
        describing cross-agent handoff in prose and must not collide with the
        harness-invocation-token rule, or every agent definition file would
        self-flag on its own worked examples.
        """
        agent = _write_agent_file(tmp_path, "\\<invoke architect agent\\>\n")

        violations = validate_file(agent)

        assert violations == []


class TestDenylistHarnessConfigPaths:
    """Harness-specific config-path fragments are flagged (ADR-033 denylist category 1)."""

    @pytest.mark.parametrize(
        "config_path",
        [
            ".claude/",
            ".cursor/",
            ".windsurf/",
            ".aider/",
            ".continue/",
            ".codeium/",
            ".github/copilot",
        ],
    )
    def test_harness_config_path_is_flagged(self, tmp_path, config_path):
        """
        Given: An agent file mentioning a harness-specific config-path fragment
        When: validate_file scans the file
        Then: One violation names the offending path fragment
        """
        agent = _write_agent_file(tmp_path, f"Harness config lives under `{config_path}` in that environment.\n")

        violations = validate_file(agent)

        assert violations != []
        assert any(config_path in v.token or config_path in v.message for v in violations)

    def test_bare_github_directory_mention_is_not_flagged(self, tmp_path):
        """
        Given: An agent file mentioning bare `.github/` and `.github/workflows/` (the real
               architect.md cross-module-refactor bullet lists `.github/` among ordinary
               repo directories), with no `.github/copilot` fragment present
        When: validate_file scans the file
        Then: No harness-config-path violation is produced

        `.github/copilot` is the denylisted fragment, not bare `.github/`.
        `.github/` is an ordinary repository directory (CI workflows, issue
        templates) referenced constantly in legitimate agent prose; a
        substring match on bare `.github/` would false-positive on every such
        mention, the same collision class as the CLAUDE.md-vs-Claude-Code case.
        """
        agent = _write_agent_file(
            tmp_path,
            "Cross-module refactor: changes that touch `risk-map/`, `scripts/`, `.github/`, "
            "or `.github/workflows/` in the same change.\n",
        )

        violations = validate_file(agent)

        assert violations == []


class TestFrameworkAllowlist:
    """
    Framework-authority references never produce denylist violations (ADR-033 category 2).

    MITRE/ATLAS/ATT&CK, NIST/AI RMF, OWASP/Top 10, ISO, EU AI Act, and STRIDE
    are legitimate content in agent prose and must produce zero violations,
    individually and combined in one realistic multi-sentence fixture.
    """

    _FRAMEWORK_ALLOWLIST_CASES = [
        (
            "mitre_atlas",
            "Risks map to MITRE ATLAS techniques (AML.T0051); controls map to mitigations (AML.M0051).",
        ),
        ("nist_ai_rmf", "NIST AI RMF mappings use full-word function prefixes (GOVERN-1.1) at subcategory level."),
        ("owasp_top10", "OWASP LLM Top 10 IDs are versioned, e.g. LLM01:2025, from the current edition."),
        ("iso", "ISO 22989 and ISO/IEC 42001 define terminology and management-system requirements."),
        ("eu_ai_act", "The EU AI Act obligation is cited as Article 9 in the mapping."),
        ("stride", "STRIDE categories use canonical PascalCase values such as Tampering."),
    ]

    @pytest.mark.parametrize(
        ("label", "text"),
        _FRAMEWORK_ALLOWLIST_CASES,
        # IDs use only the short `label`, not the full sentence in `text` — a bare
        # per-argvalue id lambda would otherwise echo the whole sentence into the
        # test node ID since it applies across both parametrized arguments.
        ids=[label for label, _ in _FRAMEWORK_ALLOWLIST_CASES],
    )
    def test_framework_authority_reference_alone_produces_no_violations(self, tmp_path, label, text):
        """
        Given: An agent file containing one framework-authority reference and its ID form
        When: validate_file scans the file
        Then: No violations are produced
        """
        agent = _write_agent_file(tmp_path, f"{text}\n", name=f"{label}.md")

        violations = validate_file(agent)

        assert violations == []

    def test_combined_realistic_framework_mapping_prose_produces_no_violations(self, tmp_path):
        """
        Given: A realistic multi-sentence fixture combining all six framework-authority
               references in one file (phrasing borrowed from issue-response-reviewer.md's
               framework-mapping bullets)
        When: validate_file scans the file
        Then: No violations are produced
        """
        content = (
            "Framework-mapping IDs use the canonical form: STRIDE PascalCase (Tampering), "
            "NIST AI RMF full-word prefixes (GOVERN-1.1), OWASP versioned (LLM01:2025), "
            "EU AI Act Article 9. Risks map to MITRE ATLAS techniques (AML.T0051); controls "
            "map to MITRE ATLAS mitigations (AML.M0051). ISO 22989 and ISO/IEC 42001 define "
            "the terminology baseline.\n"
        )
        agent = _write_agent_file(tmp_path, content)

        violations = validate_file(agent)

        assert violations == []

    def test_allowlist_terms_are_present_in_the_data_module(self):
        """
        Given: The `_neutrality_data` module's framework-authority allowlist
        When: its allowlisted terms are inspected
        Then: MITRE, NIST, OWASP, ISO, EU AI Act, and STRIDE are all present

        Cheap regression guard against someone quietly dropping a framework
        term from the allowlist. This is the one test that reaches into
        `_neutrality_data` internals; its export name (`FRAMEWORK_ALLOWLIST_TERMS`)
        is a naming assumption the implementation step may need to reconcile.
        """
        from _neutrality_data import FRAMEWORK_ALLOWLIST_TERMS

        joined = " ".join(FRAMEWORK_ALLOWLIST_TERMS)
        for expected in ("MITRE", "NIST", "OWASP", "ISO", "EU AI Act", "STRIDE"):
            assert expected in joined, f"{expected!r} missing from framework allowlist terms"


class TestScopeBoundaries:
    """
    The checker scans only scripts/agents/** and scripts/skills/** (ADR-033 category 4).

    Denylist-violating content outside those two trees must never be flagged
    because it is out of scope, not because it is clean.
    """

    def test_discover_returns_files_under_agents_and_skills_only(self, tmp_path):
        """
        Given: A synthetic root with files under scripts/agents/, scripts/skills/,
               scripts/hooks/, and a repo-root doc
        When: discover_neutral_surface_files scans the root
        Then: Only the scripts/agents/ and scripts/skills/ files are returned
        """
        agent = _write_agent_file(tmp_path, "content\n")
        skill = _write_skill_file(tmp_path, "---\nname: x\ndescription: y\n---\nbody\n")
        _write_plain_file(tmp_path, "scripts/hooks/precommit/_neutrality_data.py", "DENYLIST = ['Anthropic']\n")
        _write_plain_file(tmp_path, "README.md", "Anthropic Claude Code Cursor\n")

        discovered = discover_neutral_surface_files(tmp_path)

        assert set(discovered) == {agent, skill}

    def test_vendor_term_outside_scope_tree_is_never_flagged_via_discovery(self, tmp_path):
        """
        Given: A repo-root doc (outside scripts/agents/**, scripts/skills/**) containing
               dense vendor-term content
        When: discover_neutral_surface_files scans the root and each result is validated
        Then: The out-of-scope doc never appears in the discovered set, so it produces
              no violations through the normal discovery path

        This proves the doc is invisible to the checker because it is out of
        scope — not because its content happens to be clean.
        """
        _write_plain_file(
            tmp_path,
            "docs/notes.md",
            "Anthropic, OpenAI, ChatGPT, Copilot, Cursor, Windsurf, Gemini, Cody, Devin, Aider.\n",
        )

        discovered = discover_neutral_surface_files(tmp_path)

        assert all("docs" not in path.parts for path in discovered)

    def test_scripts_hooks_own_home_is_excluded_even_when_walked_from_common_ancestor(self, tmp_path):
        """
        Given: scripts/agents/, scripts/skills/, and scripts/hooks/precommit/_neutrality_data.py
               (which legitimately lists vendor tokens as detection data) all under one
               common `scripts/` ancestor
        When: discover_neutral_surface_files scans the repo root
        Then: No path under scripts/hooks/ is ever returned, even though the same
              directory tree is walked from `tmp_path` as the common ancestor

        The denylist data module is the one sanctioned place vendor tokens
        legitimately appear as detection data; scanning must never reach it.
        """
        agent = _write_agent_file(tmp_path, "clean agent content\n")
        _write_plain_file(
            tmp_path,
            "scripts/hooks/precommit/_neutrality_data.py",
            "VENDOR_TERMS = ['Anthropic', 'Claude Code', 'Cursor', 'OpenAI']\n",
        )
        _write_plain_file(
            tmp_path,
            "scripts/hooks/precommit/validate_neutrality.py",
            "# scanner implementation, mentions Claude Code and Cursor as data\n",
        )

        discovered = discover_neutral_surface_files(tmp_path)

        assert discovered == [agent]
        assert all("hooks" not in path.parts for path in discovered)


class TestFrontmatterRulesSkill:
    """SKILL.md frontmatter may declare only `name` and `description` (ADR-033 category 3)."""

    def test_skill_frontmatter_with_only_name_and_description_passes(self, tmp_path):
        """
        Given: A SKILL.md with a frontmatter block containing only name and description
        When: validate_file scans the file
        Then: No violations are produced
        """
        skill = _write_skill_file(
            tmp_path,
            "---\nname: example-skill\ndescription: Does one thing well.\n---\n\nBody text.\n",
        )

        violations = validate_file(skill)

        assert violations == []

    @pytest.mark.parametrize("extra_key", ["license", "version", "tools", "allowed-tools", "model"])
    def test_skill_frontmatter_with_extra_key_fails_naming_it(self, tmp_path, extra_key):
        """
        Given: A SKILL.md frontmatter block with name, description, and one extra key
        When: validate_file scans the file
        Then: One violation names the offending extra key
        """
        skill = _write_skill_file(
            tmp_path,
            f"---\nname: example-skill\ndescription: Does one thing well.\n{extra_key}: something\n---\n\nBody.\n",
        )

        violations = validate_file(skill)

        assert violations != []
        assert any(extra_key in v.token or extra_key in v.message for v in violations)


class TestFrontmatterRulesAgent:
    """Agent .md frontmatter (if present at all) must not carry a runtime-binding key."""

    def test_agent_file_with_no_frontmatter_passes(self, tmp_path):
        """
        Given: An agent .md file in the normal ADR-006 prose form (header, ## Agent,
               ## Composition, body — no frontmatter block at all)
        When: validate_file scans the file
        Then: No frontmatter-rule violations are produced

        A file with no frontmatter block at all is trivially compliant.
        """
        agent = _write_agent_file(
            tmp_path,
            "# Example Agent\n\n## Agent\n\n- **Name:** example\n\n## Composition\n\nBody.\n",
        )

        violations = validate_file(agent)

        assert violations == []

    @pytest.mark.parametrize("binding_key", ["tools", "model", "color", "allowed-tools", "allowed_tools"])
    def test_agent_frontmatter_with_binding_key_fails_naming_it(self, tmp_path, binding_key):
        """
        Given: An agent .md file with a synthetic frontmatter block containing one
               runtime-binding key
        When: validate_file scans the file
        Then: One violation names the offending key

        Both the hyphen (`allowed-tools`) and underscore (`allowed_tools`)
        spellings are treated as equivalent binding keys.
        """
        agent = _write_agent_file(
            tmp_path,
            f"---\ndescription: Example agent.\n{binding_key}: something\n---\n\n# Example Agent\n\nBody.\n",
        )

        violations = validate_file(agent)

        assert violations != []
        assert any(binding_key in v.token or binding_key in v.message for v in violations)

    def test_agent_frontmatter_with_only_neutral_keys_passes(self, tmp_path):
        """
        Given: An agent .md file with a synthetic frontmatter block containing only
               a neutral key (description)
        When: validate_file scans the file
        Then: No frontmatter-rule violations are produced

        Agents do not normally carry frontmatter, but if one legitimately does
        (e.g. a future non-binding metadata key), the rule must not blanket-fail
        every frontmatter block — only the specific binding keys.
        """
        agent = _write_agent_file(
            tmp_path,
            "---\ndescription: Example agent with benign frontmatter.\n---\n\n# Example Agent\n\nBody.\n",
        )

        violations = validate_file(agent)

        assert violations == []


class TestCli:
    """The CLI exits non-zero only when violations are present."""

    def test_main_returns_zero_on_clean_corpus(self, tmp_path, capsys):
        """
        Given: A synthetic tmp_path corpus with a clean agent file and a clean skill file
        When: main is invoked with both explicit paths
        Then: It returns 0 and emits no stderr output
        """
        agent = _write_agent_file(tmp_path, "# Clean Agent\n\n## Agent\n\nNo vendor terms here.\n")
        skill = _write_skill_file(tmp_path, "---\nname: clean-skill\ndescription: Clean.\n---\nBody.\n")

        exit_code = main([str(agent), str(skill)])

        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_main_returns_one_and_writes_violations_to_stderr(self, tmp_path, capsys):
        """
        Given: An agent file mentioning a denylisted vendor product
        When: main is invoked with the explicit file path
        Then: It returns 1 and writes a file:line violation to stderr
        """
        agent = _write_agent_file(tmp_path, "Built and tested with Claude Code.\n")

        exit_code = main([str(agent)])
        captured = capsys.readouterr()

        assert exit_code == 1
        assert f"{agent}:1:" in captured.err
        assert "Claude Code" in captured.err

    def test_main_honors_explicit_file_args_over_discovery(self, tmp_path, capsys):
        """
        Given: An explicit file path outside scripts/agents/**/scripts/skills/** that
               contains a denylisted vendor term
        When: main is invoked with that explicit path (as pre-commit would pass a
               matched filename directly)
        Then: The file is validated and flagged

        `main()` does not re-filter explicit args by scope; scope enforcement is
        `discover_neutral_surface_files`'s job for the no-args path. Pre-commit's
        own `files:` regex is what restricts which files ever reach this hook.
        """
        out_of_scope = _write_plain_file(tmp_path, "docs/notes.md", "Written using ChatGPT.\n")

        exit_code = main([str(out_of_scope)])
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "ChatGPT" in captured.err

    def test_main_self_discovers_from_cwd_with_no_args(self, tmp_path, monkeypatch, capsys):
        """
        Given: A synthetic tmp_path root with scripts/agents/ and scripts/skills/ subtrees,
               one of which contains a violation
        When: main is invoked with no file args from that root as cwd
        Then: It discovers the files itself and returns 1
        """
        _write_agent_file(tmp_path, "Powered by Anthropic's models.\n")
        _write_skill_file(tmp_path, "---\nname: clean-skill\ndescription: Clean.\n---\nBody.\n")
        monkeypatch.chdir(tmp_path)

        exit_code = main([])
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "Anthropic" in captured.err

    def test_main_self_discovers_clean_corpus_returns_zero(self, tmp_path, monkeypatch, capsys):
        """
        Given: A synthetic tmp_path root with only clean agent/skill files
        When: main is invoked with no file args from that root as cwd
        Then: It returns 0 with no stderr output
        """
        _write_agent_file(tmp_path, "# Clean Agent\n\n## Agent\n\nNo vendor terms.\n")
        _write_skill_file(tmp_path, "---\nname: clean-skill\ndescription: Clean.\n---\nBody.\n")
        monkeypatch.chdir(tmp_path)

        exit_code = main([])

        assert exit_code == 0
        assert capsys.readouterr().err == ""

    def test_format_violation_includes_hook_name_file_line_and_message(self, tmp_path):
        """
        Given: A violation produced by validate_file
        When: format_violation renders it
        Then: The rendered line follows `<hook_name>: <file>:<line>: <message>`
        """
        agent = _write_agent_file(tmp_path, "Uses Cursor for editing.\n")

        violations = validate_file(agent)
        rendered = format_violation(violations[0])

        assert rendered.startswith("validate-neutrality: ")
        assert f"{agent}:1:" in rendered


@pytest.mark.live_corpus
class TestLiveCorpus:
    """
    Runs the checker against the real repository's scripts/agents/ directory.

    scripts/skills/ does not exist yet in this repo (build-ahead case); it
    must contribute zero discovered files without erroring. The known,
    documented finding in architect.md (the vendor-neutrality style rule that
    itself names "Claude Code" and "Cursor" and their config paths as literal
    text, to warn against them) must be present. No other file in
    scripts/agents/ is expected to produce a violation — confirmed by reading
    all six agent files and grepping the corpus for every denylist category.
    """

    def test_skills_directory_does_not_exist_yet_and_contributes_nothing(self, repo_root):
        """
        Given: The real repository, where scripts/skills/ has not been created yet
        When: discover_neutral_surface_files scans the repo root
        Then: No discovered path lives under scripts/skills/, and discovery does not error
        """
        discovered = discover_neutral_surface_files(repo_root)

        assert not any(path.parts[-3:-1] == ("scripts", "skills") for path in discovered)
        assert not any("skills" in path.parts for path in discovered)

    def test_architect_md_known_finding_is_present(self, repo_root):
        """
        Given: The real scripts/agents/architect.md, which contains a style-rule
               sentence instructing the architect agent not to name specific
               harnesses — and which, ironically, itself names two harness
               products and two harness config paths as literal text
        When: discover_neutral_surface_files + validate_file scan the corpus
        Then: architect.md is among the flagged files, and at least one flagged
              token is "Claude Code", "Cursor", ".claude/", or ".cursor/"

        Loose match only (no exact line number asserted): the file may be
        edited later and the offending sentence may shift lines.
        """
        discovered = discover_neutral_surface_files(repo_root)
        architect = next((p for p in discovered if p.name == "architect.md"), None)
        assert architect is not None, "architect.md was not discovered under scripts/agents/"

        violations = validate_file(architect)
        assert violations != [], "architect.md is expected to have the documented vendor-neutrality finding"

        expected_tokens = {"Claude Code", "Cursor", ".claude/", ".cursor/"}
        found_tokens = {v.token for v in violations} | {
            token for v in violations for token in expected_tokens if token in v.message
        }
        assert found_tokens & expected_tokens, (
            f"expected one of {expected_tokens} among architect.md violation tokens, got: "
            f"{[v.token for v in violations]}"
        )

    def test_no_other_unexpected_leakage_in_scripts_agents(self, repo_root):
        """
        Given: The real scripts/agents/ directory (architect.md, code-reviewer.md,
               content-reviewer.md, issue-response-reviewer.md, swe.md, testing.md)
        When: every discovered file is validated
        Then: architect.md is the only file with violations

        Verified by direct inspection of the corpus (2026-07-10): the only
        cross-agent `<invoke ... agent>` stage directions in these six files
        name an agent, never a "tool" (e.g. `\\<invoke architect agent\\>`),
        so the harness-invocation-token shape correctly does not fire on them.
        No other file mentions a vendor/product/company/CLI name, a
        subagent_type token, auto-loads/auto-triggers phrasing, or a harness
        config path. All MITRE/NIST/OWASP/ISO/EU AI Act/STRIDE mentions across
        the corpus are legitimate framework-mapping content.
        """
        discovered = discover_neutral_surface_files(repo_root)
        agents_md = [p for p in discovered if p.suffix == ".md"]
        assert agents_md, "expected at least one .md file under scripts/agents/"

        flagged = {p.name: validate_file(p) for p in agents_md}
        flagged_names = {name for name, violations in flagged.items() if violations}

        assert flagged_names == {"architect.md"}, (
            f"expected only architect.md to be flagged in the live corpus, got: {sorted(flagged_names)}"
        )


class TestAdversarialEdgeCases:
    """Edge cases: allowlist/denylist collisions, case sensitivity, empty-result typing."""

    def test_claude_md_filename_reference_is_not_flagged(self, tmp_path):
        """
        Given: An agent file referencing "CLAUDE.md" (this repo's own top-level
               instructions filename), with no other vendor terms present
        When: validate_file scans the file
        Then: No violations are produced

        Real corpus collision found in scripts/agents/architect.md: a naive
        case-insensitive substring match for "claude" hits "CLAUDE.md" (the
        repo's own file-naming convention, mentioned legitimately across the
        corpus), which is not a harness-product reference at all. The vendor
        denylist entry for the product is the two-word phrase "Claude Code"
        (and the company name "Anthropic"), not the bare substring "claude" —
        this is the design decision that avoids the false positive.
        """
        agent = _write_agent_file(tmp_path, "Includes ADRs, CLAUDE.md edits, and CI workflow edits.\n")

        violations = validate_file(agent)

        assert violations == []

    def test_framework_acronym_adjacent_to_denylist_term_only_flags_the_denylist_term(self, tmp_path):
        """
        Given: A single line mixing a tightly-packed framework acronym (MITRE ATLAS)
               with an unrelated denylisted product name (Copilot)
        When: validate_file scans the file
        Then: Exactly the denylisted product name is flagged; MITRE/ATLAS produce
              no violation, even sharing the same line

        Proves allowlist suppression is per-match, not a blanket "skip the whole
        line if it contains an allowlisted term" shortcut — a shortcut like that
        would silently hide real denylist hits sitting next to legitimate
        framework content.
        """
        agent = _write_agent_file(tmp_path, "MITRE ATLAS mapping was drafted with GitHub Copilot's help.\n")

        violations = validate_file(agent)

        assert violations != []
        assert all("MITRE" not in v.token and "ATLAS" not in v.token for v in violations)
        assert any("Copilot" in v.token or "Copilot" in v.message for v in violations)

    def test_suppression_requires_genuine_span_overlap_not_same_line_proximity(self, tmp_path, monkeypatch):
        """
        Given: A line containing a real allowlist match ("MITRE") and, elsewhere on the
               same line, a token that would be denylisted only under a synthetic,
               deliberately-overlapping denylist pattern substituted via monkeypatch
        When: validate_file scans the file with that substituted denylist
        Then: The match whose span overlaps the allowlist span ("MITRE") is
              suppressed, while the same-line match with a non-overlapping span
              ("FLAGGEDTOKEN") is still reported

        The real denylist/allowlist vocabularies are disjoint character sets (no
        real denylist pattern overlaps a real allowlist span), so no fixture
        built from real terms can exercise the span-overlap arithmetic in
        `_overlaps`/`_scan_line` — every "allowlist near denylist" case in this
        suite passes because the vocabularies never collide, not because
        suppression engaged. Monkeypatching `_DENYLIST_CATEGORIES` with a
        pattern that matches the literal allowlist span (`\\bMITRE\\b`, which
        `_neutrality_data.FRAMEWORK_ALLOWLIST_PATTERNS` also matches) is the
        only way to prove overlap suppression itself is correct — and that it
        stays correct if the denylist is later broadened (ADR-033 notes the
        denylist is a standing maintenance obligation).
        """
        overlapping_pattern = re.compile(r"\bMITRE\b")  # same span as the real allowlist's `\bMITRE\b`
        non_overlapping_pattern = re.compile(r"\bFLAGGEDTOKEN\b")  # matches no allowlist span on this line
        monkeypatch.setattr(
            validate_neutrality,
            "_DENYLIST_CATEGORIES",
            (
                (overlapping_pattern, "synthetic probe: overlaps a real allowlist span"),
                (non_overlapping_pattern, "synthetic probe: does not overlap any allowlist span"),
            ),
        )
        agent = _write_agent_file(tmp_path, "MITRE guidance and an unrelated FLAGGEDTOKEN sit on one line.\n")

        violations = validate_file(agent)

        tokens = {v.token for v in violations}
        assert "MITRE" not in tokens, "a denylist match overlapping a real allowlist span must be suppressed"
        assert "FLAGGEDTOKEN" in tokens, (
            "a same-line denylist match that does NOT overlap the allowlist span must still be reported"
        )

    def test_clean_file_returns_empty_list_not_none(self, tmp_path):
        """
        Given: An agent file with no denylist or frontmatter violations
        When: validate_file scans the file
        Then: It returns [] (an empty list), not None or another falsy value

        `main()` and callers rely on list semantics (`extend`, `len`); a bare
        falsy sentinel like None would break that contract even though `if not
        violations:` would still "work" by accident.
        """
        agent = _write_agent_file(tmp_path, "# Clean Agent\n\n## Agent\n\nNothing to see here.\n")

        violations = validate_file(agent)

        assert violations == []
        assert isinstance(violations, list)


"""
Test Summary
============
Total Tests: 74 (counting parametrize expansion)
- TestDenylistVendorProductNames: 19 (14 vendor/product/company/CLI names + 3 model-identifier
  patterns + 1 bare-word "model" negative case + 1 lowercase/backtick CLI-entrypoint case,
  isolated from any embedded model identifier)
- TestDenylistHarnessInvocationTokens: 10 (2 invoke/uses-tool unescaped shapes + 1 backslash-
  escaped shape + 2 subagent_type spellings + 4 auto-loads/auto-triggers phrasings +
  1 invoke-agent-without-tool-word negative case)
- TestDenylistHarnessConfigPaths: 8 (7 parametrized harness config-path fragments + 1 bare
  `.github/` negative case)
- TestFrameworkAllowlist: 8 (6 individual framework-authority terms + 1 combined realistic
  paragraph + 1 data-module regression guard)
- TestScopeBoundaries: 3 (discovery scope, out-of-scope invisibility, own-home exclusion)
- TestFrontmatterRulesSkill: 6 (1 passing + 5 parametrized extra-key failures)
- TestFrontmatterRulesAgent: 7 (1 no-frontmatter pass + 5 parametrized binding-key failures +
  1 neutral-frontmatter pass)
- TestCli: 6 (clean/violating explicit args, explicit-arg scope override, self-discovery
  clean/violating, format_violation contract)
- TestLiveCorpus: 3 (skills-absent, architect.md known finding, no other corpus leakage) —
  marked @pytest.mark.live_corpus
- TestAdversarialEdgeCases: 4 (CLAUDE.md collision, per-match allowlist suppression on the
  real disjoint vocabularies, monkeypatched genuine span-overlap suppression proof,
  empty-list-not-None typing)

Coverage Areas:
- ADR-033 denylist categories: vendor/product/company/CLI names, model-identifier
  patterns, harness-invocation tokens, subagent_type, auto-loads/auto-triggers,
  harness config paths
- ADR-033 framework-authority allowlist: MITRE/ATLAS, NIST/AI RMF, OWASP/Top 10,
  ISO, EU AI Act, STRIDE — individually and combined, with per-match (not per-line)
  suppression
- ADR-033 scope boundaries: scripts/agents/**, scripts/skills/** only;
  scripts/hooks/** (the checker's own home) never scanned
- ADR-033 frontmatter structural rules: SKILL.md name/description-only;
  agent .md binding-key exclusion (tools/model/color/allowed-tools/allowed_tools)
- CLI contract: explicit args, self-discovery, exit codes, stderr format
- Live-corpus regression: documents the one known real finding in architect.md
  without asserting a fully clean corpus
- Adversarial cases: CLAUDE.md substring collision, bare-word "model" negative
  case, bare `.github/` vs `.github/copilot` collision, backslash-escaped
  tool-invocation shape, case-insensitive CLI entrypoint matching (isolated
  from model-identifier matching), empty-list return typing
"""

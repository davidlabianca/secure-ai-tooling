#!/usr/bin/env python3
"""
Regression pin: every shipped skill's frontmatter `description` fits the
Agent Skills spec length limit.

`scripts/skills/` is authored to the Agent Skills standard at the revision
pinned in `scripts/skills/README.md` (ADR-031 D6: "the first skill PR fixes
the revision the canonical surface targets") -- commit
6868401b64f791e9ff565f29beb6338826b73a2b of
github.com/agentskills/agentskills, spec file `docs/specification.mdx`.
That revision makes `description` a required frontmatter field with a
maximum length of 1,024 characters (and, being required, a minimum of 1).

No other test enforces the limit. The neutrality validator
(scripts/hooks/precommit/validate_neutrality.py) checks which frontmatter
keys are present, not their values, so a description can grow past the spec
ceiling without any gate noticing. This module closes that gap.

Contract pinned here:
    - The limit is measured in characters of the YAML-parsed value
      (`len(str(value))`), not in bytes of the raw file. A description
      containing em dashes or curly quotes is longer in UTF-8 bytes than in
      characters; the spec counts characters, so byte length is irrelevant.
    - The boundary is inclusive at 1,024 (accepted) and exclusive at 1,025
      (refused); an empty or missing description is refused.
    - Frontmatter that cannot be parsed (no opening fence, unclosed fence,
      invalid YAML, non-mapping block) fails closed: it is reported as a
      violation, never skipped. A description that cannot be measured is
      not a description that passed.
    - Every `scripts/skills/*/SKILL.md` is checked, discovered by glob, so a
      new skill is covered without touching this file.
    - A failure names the offending skill directory and the measured length.
"""

from pathlib import Path

import pytest
import yaml

# Repo root is four levels up from this file (scripts/hooks/tests/<here>),
# matching the convention in the neighbouring test modules.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SKILLS_DIR = _REPO_ROOT / "scripts" / "skills"

# Agent Skills spec revision this tree conforms to (scripts/skills/README.md,
# "Pinned spec revision"). Re-pin here and in the README together.
SPEC_PIN_COMMIT = "6868401b64f791e9ff565f29beb6338826b73a2b"
DESCRIPTION_MIN_CHARS = 1
DESCRIPTION_MAX_CHARS = 1024


class FrontmatterError(ValueError):
    """Raised when a SKILL.md frontmatter block cannot be parsed into a mapping."""


def _frontmatter(path: Path) -> dict:
    """
    Return the YAML frontmatter mapping of a SKILL.md.

    Reads the block between the opening `---` on line 1 and the next `---`
    line, the same fence shape the neutrality validator accepts. Parsing the
    YAML (rather than measuring the raw source line) is deliberate: the
    spec limit applies to the field's value, and a quoted description with
    escaped characters is longer in source than in value.

    Raises FrontmatterError for every unparseable shape so the caller can
    report it as a violation; it never returns an empty mapping for a file
    it could not read.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        raise FrontmatterError("no opening '---' frontmatter fence on line 1")
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            try:
                parsed = yaml.safe_load("\n".join(lines[1:index]))
            except yaml.YAMLError as exc:
                raise FrontmatterError(f"frontmatter is not valid YAML: {exc}") from exc
            if not isinstance(parsed, dict):
                raise FrontmatterError(f"frontmatter is not a mapping (got {type(parsed).__name__})")
            return parsed
    raise FrontmatterError("opening '---' fence has no closing '---'")


def description_length(path: Path) -> int:
    """Character count of the parsed `description` value; 0 when the key is absent."""
    value = _frontmatter(path).get("description")
    if value is None:
        return 0
    return len(str(value))


def description_length_violations(paths: list[Path]) -> list[str]:
    """
    Return one human-readable line per SKILL.md whose description is outside
    [DESCRIPTION_MIN_CHARS, DESCRIPTION_MAX_CHARS] or cannot be measured.
    Empty list means all pass.
    """
    violations = []
    for path in paths:
        try:
            length = description_length(path)
        except FrontmatterError as exc:
            # Fail closed: an unmeasurable description is a violation, not a skip.
            violations.append(f"{path.parent.name}: unverifiable frontmatter ({exc})")
            continue
        if length < DESCRIPTION_MIN_CHARS or length > DESCRIPTION_MAX_CHARS:
            violations.append(
                f"{path.parent.name}: description is {length} characters "
                f"(spec {SPEC_PIN_COMMIT[:7]} allows {DESCRIPTION_MIN_CHARS}-{DESCRIPTION_MAX_CHARS})"
            )
    return violations


def _shipped_skill_files() -> list[Path]:
    return sorted(SKILLS_DIR.glob("*/SKILL.md"))


def _write_skill(tmp_path: Path, name: str, description: str) -> Path:
    """Create <tmp>/<name>/SKILL.md with a spec-shaped frontmatter block."""
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    path = skill_dir / "SKILL.md"
    # yaml.safe_dump quotes/escapes as needed so the parsed value round-trips
    # exactly, which is what makes the character-vs-byte control meaningful.
    frontmatter = yaml.safe_dump({"name": name, "description": description}, allow_unicode=True)
    path.write_text(f"---\n{frontmatter}---\n\n# {name}\n", encoding="utf-8")
    return path


def _write_raw_skill(tmp_path: Path, name: str, raw_text: str) -> Path:
    """Create <tmp>/<name>/SKILL.md with verbatim contents (for malformed-shape fixtures)."""
    skill_dir = tmp_path / name
    skill_dir.mkdir()
    path = skill_dir / "SKILL.md"
    path.write_text(raw_text, encoding="utf-8")
    return path


class TestDescriptionLengthBoundary:
    """
    Both sides of the limit, on synthetic skills, so the shipped-tree checks
    below cannot pass vacuously or for the wrong reason. The spec at pin
    6868401 counts characters of the field value, 1..1024 inclusive.
    """

    def test_limit_constants_equal_the_spec_literals(self):
        """
        The bounds are the spec's numbers, not tunables: description is
        required (minimum 1) and at most 1,024 characters at pin 6868401.
        Raising the maximum here to make an over-length skill pass fails
        this test; re-pinning the spec is the only legitimate change.
        """
        assert DESCRIPTION_MAX_CHARS == 1024, (
            f"DESCRIPTION_MAX_CHARS is {DESCRIPTION_MAX_CHARS}; "
            f"the Agent Skills spec at {SPEC_PIN_COMMIT[:7]} sets 1024"
        )
        assert DESCRIPTION_MIN_CHARS == 1, (
            f"DESCRIPTION_MIN_CHARS is {DESCRIPTION_MIN_CHARS}; description is a required field (minimum 1)"
        )

    def test_exactly_max_length_is_accepted(self, tmp_path):
        """1,024 characters is inside the spec limit (inclusive upper bound)."""
        path = _write_skill(tmp_path, "at-limit", "d" * DESCRIPTION_MAX_CHARS)
        assert description_length(path) == DESCRIPTION_MAX_CHARS
        assert description_length_violations([path]) == []

    def test_one_over_max_length_is_refused_and_named(self, tmp_path):
        """1,025 characters is refused, and the message names the skill and the length."""
        path = _write_skill(tmp_path, "one-over", "d" * (DESCRIPTION_MAX_CHARS + 1))
        violations = description_length_violations([path])
        assert len(violations) == 1
        assert "one-over" in violations[0]
        assert str(DESCRIPTION_MAX_CHARS + 1) in violations[0]

    def test_multibyte_characters_count_as_one_each(self, tmp_path):
        """
        The limit is characters, not UTF-8 bytes. A description of exactly
        1,024 characters that is 1,030 bytes (six em dashes) is accepted;
        counting bytes would wrongly refuse it.
        """
        description = ("—" * 6) + ("d" * (DESCRIPTION_MAX_CHARS - 6))
        assert len(description) == DESCRIPTION_MAX_CHARS
        assert len(description.encode("utf-8")) > DESCRIPTION_MAX_CHARS
        path = _write_skill(tmp_path, "em-dashes", description)
        assert description_length_violations([path]) == []

    def test_empty_description_is_refused(self, tmp_path):
        """An empty string fails the required-field floor (minimum 1 character)."""
        path = _write_skill(tmp_path, "empty", "")
        violations = description_length_violations([path])
        assert len(violations) == 1
        assert "empty" in violations[0]

    def test_missing_description_is_refused(self, tmp_path):
        """A frontmatter block with no `description` key is a length-0 violation, not a crash."""
        path = _write_raw_skill(tmp_path, "no-desc", "---\nname: no-desc\n---\n\n# no-desc\n")
        assert description_length(path) == 0
        violations = description_length_violations([path])
        assert len(violations) == 1
        assert "no-desc" in violations[0]

    def test_measures_parsed_value_not_source_line(self, tmp_path):
        """
        A double-quoted YAML scalar with escaped inner quotes is longer in
        source than in value. The spec limit applies to the value; measuring
        the raw line would over-count by the escape characters.
        """
        value = 'Answer "what is X?" for a reader.'
        path = tmp_path / "SKILL.md"
        escaped = value.replace('"', '\\"')
        path.write_text(f'---\nname: quoted\ndescription: "{escaped}"\n---\n', encoding="utf-8")
        assert description_length(path) == len(value)


class TestMalformedFrontmatterFailsClosed:
    """
    Unparseable frontmatter is a violation, never a silent pass. A mutant
    that catches the parse failure and `continue`s without recording a
    violation turns every test here red: each asserts a violation line
    naming the skill, and `description_length` itself raises rather than
    returning 0 for a block it could not read.
    """

    @pytest.mark.parametrize(
        ("name", "raw_text"),
        [
            ("no-fence", "name: no-fence\ndescription: short\n\n# body\n"),
            ("unclosed", "---\nname: unclosed\ndescription: short\n\n# body\n"),
            ("bad-yaml", "---\nname: bad-yaml\ndescription: [unclosed\n---\n"),
            ("not-mapping", "---\n- name: not-mapping\n- description: short\n---\n"),
        ],
        ids=["no-opening-fence", "unclosed-fence", "invalid-yaml", "non-mapping-block"],
    )
    def test_unparseable_frontmatter_is_reported_as_violation(self, tmp_path, name, raw_text):
        """Each malformed shape yields exactly one violation that names the skill."""
        path = _write_raw_skill(tmp_path, name, raw_text)
        violations = description_length_violations([path])
        assert len(violations) == 1, violations
        assert name in violations[0]
        assert "unverifiable frontmatter" in violations[0]

    def test_description_length_raises_on_unparseable_frontmatter(self, tmp_path):
        """The measuring helper raises; it does not report length 0 for a block it could not parse."""
        path = _write_raw_skill(tmp_path, "unclosed", "---\nname: unclosed\ndescription: short\n")
        with pytest.raises(FrontmatterError):
            description_length(path)

    def test_malformed_file_does_not_mask_a_well_formed_sibling(self, tmp_path):
        """A malformed skill and an over-length skill in one batch produce two violations, one each."""
        bad = _write_raw_skill(tmp_path, "bad", "---\nname: bad\n")
        long_ = _write_skill(tmp_path, "too-long", "d" * (DESCRIPTION_MAX_CHARS + 1))
        violations = description_length_violations([bad, long_])
        assert len(violations) == 2
        assert any("bad" in line and "unverifiable" in line for line in violations)
        assert any("too-long" in line and str(DESCRIPTION_MAX_CHARS + 1) in line for line in violations)


@pytest.mark.live_corpus
class TestShippedSkillDescriptions:
    """
    The live pin over scripts/skills/ (marked live_corpus, matching the
    neutrality suite's idiom for tests that read the shipped tree). Every
    shipped SKILL.md description must measure 1..1,024 characters under the
    spec revision pinned in scripts/skills/README.md.
    """

    def test_shipped_skills_are_discovered(self):
        """Guard against a vacuous pass: the glob must find the shipped skills."""
        files = _shipped_skill_files()
        assert files, f"no SKILL.md found under {SKILLS_DIR}"
        # Two skills known to exist in this tree; if either is renamed, update here.
        names = {path.parent.name for path in files}
        assert {"explain-entity", "explore-exposure"} <= names

    @pytest.mark.parametrize(
        "skill_file",
        _shipped_skill_files(),
        ids=lambda path: path.parent.name,
    )
    def test_description_within_spec_limit(self, skill_file):
        """Per-skill: the parsed description is 1..1,024 characters (spec 6868401)."""
        violations = description_length_violations([skill_file])
        assert not violations, violations[0]

    def test_all_shipped_descriptions_within_spec_limit(self):
        """
        Aggregate: one failure message naming every offending skill at once,
        so a reviewer sees the full set without reading per-skill output.
        """
        violations = description_length_violations(_shipped_skill_files())
        assert not violations, "SKILL.md description length violations:\n  " + "\n  ".join(violations)

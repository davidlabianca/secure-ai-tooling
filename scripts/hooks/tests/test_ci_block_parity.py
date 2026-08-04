#!/usr/bin/env python3
"""
Tests for ADR-037 — CI as the enforcing gate for risk-map validation.

Covers three of the ADR's testable requirements:

  D1 (coverage, then monotonicity)
      Part 1, coverage: every validator that `.pre-commit-config.yaml` invokes
      with `--block` has a CI invocation that also passes `--block`.
      Part 2, monotonicity: for validators present on both surfaces, the CI
      strictness flags are a superset of the hook's.

      The two are separate classes below because part 2 alone is satisfied
      *vacuously* by a validator CI never runs — an empty flag set is trivially
      a superset of nothing. Part 2 quantifies over the intersection of the two
      surfaces and therefore cannot see a validator missing from one of them,
      which is precisely the gap three of the five validators sit in. Part 1
      quantifies over pre-commit's `--block` hooks, so absence from CI fails
      rather than skips.

  D3 (`--block` is prohibited on graph-generation invocations)
      No workflow step may pass `--block` on an invocation that also passes
      `--to-graph`, `--to-controls-graph`, or `--to-risk-graph`. The warn-only
      `sys.exit` in `validate_riskmap.py` precedes every emission block, so the
      pairing terminates the process before any graph file is written and
      misattributes a content warning as a generation failure.

  D4 (non-vacuity)
      Asserting that the string `--block` appears in a workflow proves the
      string is present, not that behaviour changed. Every claim here is
      backed by running the validator against a corpus carrying a deliberately
      injected warn-level violation and comparing exit codes.

  D7b (the `precommit/` validators are invoked in place)
      No workflow may copy a validator out of `scripts/hooks/precommit/` or
      invoke one from a path other than its real location. Those validators
      derive both their `sys.path` entry and their default `--schema-dir` from
      `Path(__file__)`; relocating them makes field discovery return silently
      and the job exit 0 having inspected nothing. This does not touch the
      five existing copy-to-root steps D5 keeps — it prohibits extending the
      pattern to new call sites, which D5's own text records as not being a
      copy-to-root change.

Derivation, not enumeration
---------------------------
Neither side's validator list is hardcoded. Both are parsed out of the actual
files:

  - the pre-commit side from `repos[].hooks[].entry` + `args` in
    `.pre-commit-config.yaml`;
  - the CI side from every `jobs.*.steps[].run` shell block in every
    `.github/workflows/*.yml`.

A validator added to pre-commit tomorrow with `--block` and not to CI fails
D1 without anyone editing this module. A hardcoded list would reproduce the
very gap the suite exists to catch.

Reaching variable-built invocations
-----------------------------------
`validation.yml`'s graph-validation job does not name the script inline. It
builds the command through shell variables::

    VALIDATE_CMD="validate_riskmap.py"
    GENERATE_ARGS=("--to-graph" "--to-controls-graph" "--to-risk-graph")
    ...
    gen_args="${GENERATE_ARGS[$i]}"
    if ! python3 ${VALIDATE_CMD} --force ${gen_args} "${temp_file}"; then

A check that only looks for `--block` next to a literal script name is blind
exactly where D3's risk lives. `_python_invocations` therefore tracks scalar
and array assignments and expands `${VAR}` / `$VAR` / `${ARR[$i]}` references
before classifying a command. Array references expand to the union of the
array's elements — a deliberate over-approximation: for a prohibition, seeing
a flag that only *might* be on the command line is the safe direction to err.

`TestParserFidelity` locks that this expansion actually happens, so D3 cannot
pass by failing to see the invocation it is meant to police.

Joining the two surfaces
------------------------
Invocations are joined on the script's **basename**. CI copies validator
sources to the repository root before running them (`validation.yml:44-47`,
`:183-185`, `:222`, `:259`, `:298-300`), so `scripts/hooks/validate_riskmap.py`
in the hook and `validate_riskmap.py` in the workflow are the same validator
under different paths. ADR-037 D5 decides that arrangement stays; matching on
basename works with it rather than requiring it to change.
`test_precommit_script_basenames_are_unambiguous` guards the assumption that
no two distinct validator paths share a basename.

Expected state at authoring time (base commit 0d0b731)
------------------------------------------------------
D1 part 1 (coverage) fails for all five `--block` validators. Two are invoked
by CI without the flag (`validate_riskmap.py`,
`validate_framework_references.py`); three are not invoked by any workflow at
all (`validate_identification_questions.py`, `validate_yaml_prose_subset.py`,
`validate_prose_references.py`), and no workflow runs `pre-commit` either, so
those three checks exist only on contributor machines.

D1 part 2 (monotonicity) fails for the two laxly-invoked validators and skips
the three absent ones — a live demonstration of why part 1 is stated first.

D4's CI-argument tier fails for the same five.

D3 and D7b pass: both are prohibitions on things no workflow does yet. Their
synthetic-detector tests are what make those passes mean something.

Deliberately not a gap: lifecycle-stage order uniqueness
--------------------------------------------------------
`.pre-commit-config.yaml` declares a second hook on `validate_riskmap.py`
(`validate-lifecycle-stage`, `--mode lifecycle`), and no workflow ever passes
`--mode lifecycle`. That looks like a sixth coverage gap and is not one: the
lifecycle check also runs unconditionally in default mode
(`validate_riskmap.py:249-271`, guarded on `validator.components`), which CI's
`--force` invocation reaches, and it exits 1 directly without needing
`--block`. The hook carries no strictness flag, so D1 does not quantify over
it either. Recorded here so the next reader does not re-derive it as a missing
case and "fix" it.

Not covered here
----------------
ADR-037 D7a (CI file lists constructed explicitly from each hook's `files:`
regex over the whole tracked corpus, and never resolving to empty) and D7c
(each new invocation shown red on an injected violation before being accepted).
Both are properties of workflow steps that do not exist yet, and D7a in
particular needs the implementation's chosen file-list mechanism to test
against. D7c is partly served in advance by `TestCIInvocationCatchesViolation`,
which will exercise each new invocation's arguments as soon as they land.

D3 passes at authoring time. ADR-037 D3 says so explicitly — it "codifies
existing practice rather than changing it". The D3 tests here are a standing
guard against a future workflow edit, and `TestGraphEmissionExclusion`'s
synthetic-detector tests establish that the guard would catch a violation in
both the literal and the variable-built form.
"""

import json
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, NamedTuple

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

# tests -> hooks -> scripts -> repo root, matching the convention in
# test_precommit_hook_install.py and test_controls_components_mirror.py.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_HOOKS_DIR = _REPO_ROOT / "scripts" / "hooks"
_PRECOMMIT_CONFIG = _REPO_ROOT / ".pre-commit-config.yaml"
_WORKFLOW_DIR = _REPO_ROOT / ".github" / "workflows"

# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

# Flags that make a validator stricter. ADR-037 D1 states the invariant over
# "strictness flags" generally; `--block` is the only member today. The
# *validators* carrying these flags are derived, never listed — that derivation
# is what makes this suite self-maintaining. Adding a second strictness flag
# here extends the invariant to it on both surfaces at once.
STRICTNESS_FLAGS = frozenset({"--block"})

# Graph-emission flags named literally in ADR-037 D3. Each is confirmed to be a
# real `validate_riskmap.py` option by test_graph_emission_flags_are_real, so a
# flag rename cannot silently make the D3 prohibition vacuous.
GRAPH_EMISSION_FLAGS = frozenset({"--to-graph", "--to-controls-graph", "--to-risk-graph"})


# ===========================================================================
# Shell-invocation parsing
# ===========================================================================

_ASSIGN_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")
_TOKEN_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_VAR_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?:\[[^\]]*\])?\}|\$([A-Za-z_][A-Za-z0-9_]*)")
_INTERPRETER_RE = re.compile(r"^python[0-9.]*$")

# Tokens that terminate one simple command and begin another.
_OPERATORS = frozenset({";", "&&", "||", "|", "&"})

# Shell keywords and command prefixes that precede the real command word.
_LEADING_WORDS = frozenset(
    {"if", "elif", "while", "until", "then", "do", "else", "!", "sudo", "time", "env", "exec"}
)


class Invocation(NamedTuple):
    """One resolved Python execution found in a shell script.

    Attributes:
        script: Basename of the executed ``.py`` file (path prefixes dropped,
            so the CI copy-to-root layout and the hook's repo-relative path
            resolve to the same identity).
        path: The script path exactly as written on the command line, before
            basename reduction. D7b needs this: `validate_prose_references.py`
            and `scripts/hooks/precommit/validate_prose_references.py` are the
            same validator to D1 and different call sites to D7b.
        argv: Tokens following the script on the same simple command, after
            variable expansion.
        source: Human-readable origin, used in assertion messages.
        line: The raw (unexpanded) shell line, also for assertion messages.
    """

    script: str
    path: str
    argv: tuple[str, ...]
    source: str
    line: str


class CopyCommand(NamedTuple):
    """A file-relocating shell command found in a workflow step.

    Attributes:
        source_path: The path being copied or moved, as written.
        destination: The destination operand, as written.
        source: Human-readable origin, used in assertion messages.
        line: The raw shell line.
    """

    source_path: str
    destination: str
    source: str
    line: str


def _safe_split(text: str) -> list[str]:
    """Tokenize a shell fragment, degrading to whitespace splitting on failure.

    `shlex` raises on unbalanced quotes, which occurs in hand-written workflow
    shell. Falling back to whitespace splitting keeps such a line visible to
    the scan. Silently dropping it is the failure mode this suite exists to
    prevent: an unparsed line is an unpoliced line.
    """
    try:
        return shlex.split(text, comments=True)
    except ValueError:
        return [t for t in re.split(r"\s+", text.strip()) if t]


def _expand(token: str, env: dict[str, Any]) -> str:
    """Expand ``${VAR}``, ``$VAR`` and ``${ARR[...]}`` references in a token.

    Array-valued variables expand to their elements joined by spaces. An
    indexed reference such as ``${GENERATE_ARGS[$i]}`` therefore yields every
    element rather than one, because the loop index is not statically known.
    For a *prohibition* (D3) this over-approximation is the safe direction:
    a flag that might be on the command line is treated as if it is.

    Unknown variables expand to the empty string, mirroring shell behaviour
    under the default (non-``nounset``) mode used by workflow ``run`` blocks.
    """
    out = token
    # Bounded iteration resolves variables defined in terms of other variables
    # (e.g. TEMP_FILES holding "${RISK_MAP_TEMP_FILE}") without risking a cycle.
    for _ in range(5):
        expanded = _VAR_RE.sub(lambda m: _lookup(env, m.group(1) or m.group(2)), out)
        if expanded == out:
            break
        out = expanded
    return out


def _lookup(env: dict[str, Any], name: str) -> str:
    """Return a variable's expansion, joining array elements with spaces."""
    value = env.get(name)
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(value)
    return value


def _split_simple_commands(tokens: list[str]) -> list[list[str]]:
    """Split a token stream into simple commands on shell control operators.

    Redirections start a new (discarded) segment so that `>> $GITHUB_OUTPUT`
    tails are not mistaken for arguments.
    """
    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        # Operators are not whitespace-separated in shell, so split them out of
        # adjoining tokens (`--force;` -> `--force`, `;`).
        for part in (p for p in re.split(r"(;|&&|\|\||\||&)", token) if p):
            if part in _OPERATORS or part.startswith(">") or part.startswith("<"):
                if current:
                    segments.append(current)
                current = []
            else:
                current.append(part)
    if current:
        segments.append(current)
    return segments


def _python_invocations(script_text: str, source: str) -> list[Invocation]:
    """Return every Python execution in a shell script, with variables expanded.

    Only executions count. `cp scripts/hooks/validate_riskmap.py .` and
    `echo "... validate_riskmap.py failed"` mention a validator but do not run
    it, and must not be read as invocations — otherwise the copy step in
    `validation.yml:183-185` would masquerade as a flagless CI invocation and
    D1 would report the wrong thing.

    Args:
        script_text: The shell script body (a workflow ``run:`` block, or a
            pre-commit ``entry`` plus its ``args``).
        source: Label used in assertion messages.

    Returns:
        List of Invocation records in the order encountered.
    """
    env: dict[str, Any] = {}
    found: list[Invocation] = []

    for raw_line in script_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        assignment = _ASSIGN_RE.match(raw_line)
        if assignment:
            name, value = assignment.group(1), assignment.group(2).strip()
            if "$(" in value or "`" in value:
                # Command substitution is not statically resolvable; record the
                # name as known-but-empty so downstream references expand away
                # rather than being left as literal `${VAR}` text.
                env[name] = ""
            elif value.startswith("(") and value.endswith(")"):
                env[name] = [_expand(element, env) for element in _safe_split(value[1:-1])]
            else:
                parts = _safe_split(value)
                env[name] = _expand(parts[0], env) if parts else ""
            continue

        tokens: list[str] = []
        for token in _safe_split(stripped):
            expansion = _expand(token, env)
            # An expanded array reference carries several arguments in one
            # token; re-split so each becomes its own argv entry.
            tokens.extend(expansion.split())

        for segment in _split_simple_commands(tokens):
            while segment and (segment[0] in _LEADING_WORDS or _TOKEN_ASSIGN_RE.match(segment[0])):
                segment = segment[1:]
            if not segment:
                continue

            command, rest = segment[0], segment[1:]
            if _INTERPRETER_RE.match(Path(command).name):
                script = next((arg for arg in rest if arg.endswith(".py")), None)
                if script is None:
                    continue
                argv = rest[rest.index(script) + 1 :]
            elif command.endswith(".py"):
                script, argv = command, rest
            else:
                continue

            found.append(Invocation(Path(script).name, script, tuple(argv), source, stripped))

    return found


# Commands that relocate a file. `install` and `ln` are included because either
# would satisfy "get the script to the repository root" just as well as `cp`,
# and D7b prohibits the outcome rather than one spelling of it.
_RELOCATING_COMMANDS = frozenset({"cp", "mv", "install", "ln", "rsync"})


def _copy_commands(script_text: str, source: str) -> list[CopyCommand]:
    """Return every file-relocating command in a shell script, variables expanded.

    Shares `_python_invocations`'s assignment tracking so a copy whose source or
    destination is built from a shell variable is still seen. An implementer
    extending the copy-to-root pattern would plausibly write
    `cp ${PRECOMMIT_DIR}/validate_prose_references.py .`, and a scan that only
    matched literal paths would wave it through.

    Args:
        script_text: The shell script body.
        source: Label used in assertion messages.

    Returns:
        List of CopyCommand records, one per (source operand, destination) pair.
    """
    env: dict[str, Any] = {}
    found: list[CopyCommand] = []

    for raw_line in script_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        assignment = _ASSIGN_RE.match(raw_line)
        if assignment:
            name, value = assignment.group(1), assignment.group(2).strip()
            if "$(" in value or "`" in value:
                env[name] = ""
            elif value.startswith("(") and value.endswith(")"):
                env[name] = [_expand(element, env) for element in _safe_split(value[1:-1])]
            else:
                parts = _safe_split(value)
                env[name] = _expand(parts[0], env) if parts else ""
            continue

        tokens: list[str] = []
        for token in _safe_split(stripped):
            expansion = _expand(token, env)
            tokens.extend(expansion.split())

        for segment in _split_simple_commands(tokens):
            while segment and (segment[0] in _LEADING_WORDS or _TOKEN_ASSIGN_RE.match(segment[0])):
                segment = segment[1:]
            if not segment or Path(segment[0]).name not in _RELOCATING_COMMANDS:
                continue

            operands = [token for token in segment[1:] if not token.startswith("-")]
            if len(operands) < 2:
                continue
            # Last operand is the destination; everything before it is a source.
            destination = operands[-1]
            for operand in operands[:-1]:
                found.append(CopyCommand(operand, destination, source, stripped))

    return found


# ===========================================================================
# Derivation of both surfaces
# ===========================================================================


def _precommit_invocations() -> list[Invocation]:
    """Return every Python invocation declared in .pre-commit-config.yaml."""
    config = yaml.safe_load(_PRECOMMIT_CONFIG.read_text(encoding="utf-8"))
    invocations: list[Invocation] = []
    for repo in config.get("repos", []):
        for hook in repo.get("hooks", []):
            entry = hook.get("entry")
            if not entry:
                continue
            # `args:` are appended by the framework after `entry`, so the
            # effective command line is the concatenation of the two.
            command = " ".join([entry, *(str(a) for a in hook.get("args", []))])
            invocations.extend(_python_invocations(command, f".pre-commit-config.yaml [{hook.get('id')}]"))
    return invocations


def _iter_workflow_run_steps():
    """Yield (source_label, run_block) for every `run:` step in every workflow."""
    for workflow in sorted(_WORKFLOW_DIR.glob("*.yml")):
        data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        for job_id, job in (data.get("jobs") or {}).items():
            for index, step in enumerate(job.get("steps") or []):
                run_block = step.get("run")
                if not run_block:
                    continue
                label = step.get("name") or f"step[{index}]"
                yield f"{workflow.name}::{job_id}::{label}", run_block


def _workflow_invocations() -> list[Invocation]:
    """Return every Python invocation across all `run:` steps in all workflows."""
    invocations: list[Invocation] = []
    for source, run_block in _iter_workflow_run_steps():
        invocations.extend(_python_invocations(run_block, source))
    return invocations


def _workflow_copy_commands() -> list[CopyCommand]:
    """Return every file-relocating command across all `run:` steps in all workflows."""
    copies: list[CopyCommand] = []
    for source, run_block in _iter_workflow_run_steps():
        copies.extend(_copy_commands(run_block, source))
    return copies


def _strictness_flags(invocation: Invocation) -> frozenset[str]:
    """Return the strictness flags carried by an invocation."""
    return frozenset(arg for arg in invocation.argv if arg in STRICTNESS_FLAGS)


def _is_graph_emitting(invocation: Invocation) -> bool:
    """True when the invocation passes any graph-emission flag."""
    return bool(GRAPH_EMISSION_FLAGS.intersection(invocation.argv))


# Derived once at import; every parametrized case below reads from these.
# TestParserFidelity guards against either collapsing to empty, which would
# turn the whole suite green by parsing nothing.
PRECOMMIT_INVOCATIONS = _precommit_invocations()
WORKFLOW_INVOCATIONS = _workflow_invocations()
WORKFLOW_COPY_COMMANDS = _workflow_copy_commands()

# Directory whose validators ADR-037 D7b requires be invoked in place.
_PRECOMMIT_DIR_FRAGMENT = "scripts/hooks/precommit/"

# basename -> repo-relative real path, for every validator a pre-commit hook
# runs out of scripts/hooks/precommit/. Derived, not listed: D7b's reasoning
# applies to any validator in that directory, so a fourth is governed on
# arrival exactly as the three named in the ADR are.
PRECOMMIT_VALIDATORS: dict[str, str] = {
    inv.script: inv.path for inv in PRECOMMIT_INVOCATIONS if _PRECOMMIT_DIR_FRAGMENT in inv.path
}

# script basename -> the flags pre-commit requires of it.
BLOCK_VALIDATORS: dict[str, frozenset[str]] = {}
for _inv in PRECOMMIT_INVOCATIONS:
    _flags = _strictness_flags(_inv)
    if _flags:
        BLOCK_VALIDATORS[_inv.script] = BLOCK_VALIDATORS.get(_inv.script, frozenset()) | _flags

BLOCK_VALIDATOR_NAMES = sorted(BLOCK_VALIDATORS)


def _ci_invocations_of(script: str) -> list[Invocation]:
    """Return every workflow invocation of the named script."""
    return [inv for inv in WORKFLOW_INVOCATIONS if inv.script == script]


# ===========================================================================
# 1. Parser fidelity — these guard every other assertion in this module
# ===========================================================================


class TestParserFidelity:
    """Non-vacuity guards on the derivation itself.

    Every other test here reads from PRECOMMIT_INVOCATIONS and
    WORKFLOW_INVOCATIONS. If either derivation silently returned nothing, D1
    would pass with no validators to check and D3 would pass with no
    invocations to inspect — the "wired but checking nothing" failure that
    ADR-037's Context cites as the motivating bug. These tests are expected to
    pass; their job is to make the failures of D1 and D4 mean something.
    """

    def test_precommit_derivation_finds_block_validators(self):
        """
        Given: .pre-commit-config.yaml as committed
        When: hook entries are parsed for strictness flags
        Then: at least one validator is found carrying one

        A zero result would make every D1 case vacuous, since the D1 tests are
        parametrized over exactly this set.
        """
        assert BLOCK_VALIDATOR_NAMES, (
            "Parsed no strictness-flagged validators out of .pre-commit-config.yaml. "
            f"Expected at least one hook whose entry carries one of {sorted(STRICTNESS_FLAGS)}. "
            "Either the config genuinely stopped using them, or _python_invocations "
            "stopped parsing hook entries — the second would make every D1 case vacuous."
        )

    def test_workflow_derivation_finds_python_invocations(self):
        """
        Given: every workflow under .github/workflows/
        When: each `run:` block is scanned for Python executions
        Then: at least one invocation is found

        A zero result would make D3 vacuous — no invocation to inspect means
        no invocation can violate the prohibition.
        """
        assert WORKFLOW_INVOCATIONS, (
            f"Parsed no Python invocations out of any workflow in {_WORKFLOW_DIR}. "
            "D3 inspects exactly this set, so an empty parse would pass the "
            "prohibition by having nothing to prohibit."
        )

    def test_parser_resolves_variable_built_invocation(self):
        """
        Given: validation.yml's graph-validation job, which builds its command
               from VALIDATE_CMD and an indexed GENERATE_ARGS array rather than
               naming the script inline
        When: workflow invocations are derived
        Then: a validate_riskmap.py invocation carrying a graph-emission flag
              is found

        This is the specific blindness D3 must not have. A scan that only
        matches `--block` adjacent to a literal script name never sees this
        call site, and would report D3 satisfied while the one invocation the
        prohibition targets goes uninspected.
        """
        graph_invocations = [inv for inv in WORKFLOW_INVOCATIONS if _is_graph_emitting(inv)]
        assert graph_invocations, (
            "Found no graph-emitting invocation in any workflow. validation.yml's "
            "graph-validation job builds one through VALIDATE_CMD + GENERATE_ARGS; "
            "not seeing it means shell-variable expansion regressed and D3 is now "
            "blind at the only call site it targets."
        )
        assert any(inv.script == "validate_riskmap.py" for inv in graph_invocations), (
            "Graph-emitting invocations were found, but none resolved to "
            f"validate_riskmap.py: {[(i.script, i.source) for i in graph_invocations]}"
        )

    def test_copy_steps_are_not_read_as_invocations(self):
        """
        Given: validation.yml's `cp scripts/hooks/validate_riskmap.py .` steps
        When: workflow invocations are derived
        Then: no invocation originates from a `cp` command

        A copy step names a validator without running it. Counting it as an
        invocation would make D1 report a flagless CI invocation that does not
        exist, and would let a real gap hide behind a false positive.
        """
        copy_derived = [inv for inv in WORKFLOW_INVOCATIONS if inv.line.startswith("cp ")]
        assert not copy_derived, (
            f"`cp` steps were parsed as invocations: {[(i.script, i.line) for i in copy_derived]}. "
            "Only executions may count toward D1/D3."
        )

    def test_precommit_script_basenames_are_unambiguous(self):
        """
        Given: every Python script referenced by a pre-commit hook entry
        When: basenames are compared against full paths
        Then: no basename maps to more than one distinct path

        D1 joins the hook surface to the CI surface on basename, because CI
        copies validators to the repository root before running them (ADR-037
        D5 keeps that arrangement). Two different validators sharing a basename
        would silently conflate, letting one satisfy the other's requirement.
        """
        config = yaml.safe_load(_PRECOMMIT_CONFIG.read_text(encoding="utf-8"))
        paths_by_basename: dict[str, set[str]] = {}
        for repo in config.get("repos", []):
            for hook in repo.get("hooks", []):
                entry = hook.get("entry") or ""
                for token in _safe_split(entry):
                    if token.endswith(".py"):
                        paths_by_basename.setdefault(Path(token).name, set()).add(token)

        collisions = {name: sorted(paths) for name, paths in paths_by_basename.items() if len(paths) > 1}
        assert not collisions, (
            f"Basename collisions among pre-commit validator paths: {collisions}. "
            "D1 matches hook invocations to CI invocations by basename; distinct "
            "validators sharing one would conflate."
        )

    def test_graph_emission_flags_are_real(self):
        """
        Given: the graph-emission flag names GRAPH_EMISSION_FLAGS asserts on
        When: validate_riskmap.py --help is inspected
        Then: every named flag appears

        Renaming a flag without updating this constant would make D3 a
        prohibition on strings nothing produces — present, green, and blind.
        """
        result = subprocess.run(
            [sys.executable, str(_HOOKS_DIR / "validate_riskmap.py"), "--help"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"--help exited {result.returncode}: {result.stderr}"
        missing = sorted(flag for flag in GRAPH_EMISSION_FLAGS if flag not in result.stdout)
        assert not missing, (
            f"GRAPH_EMISSION_FLAGS names flags validate_riskmap.py does not accept: {missing}. "
            "D3 would prohibit a pairing that can no longer occur."
        )


# ===========================================================================
# 2. D1 — strictness monotonicity between pre-commit and CI
# ===========================================================================


def _hook_sources_for(script: str) -> list[str]:
    """Return the pre-commit hook labels that invoke a script with strictness flags."""
    return sorted({inv.source for inv in PRECOMMIT_INVOCATIONS if inv.script == script and _strictness_flags(inv)})


class TestStrictnessCoverage:
    """ADR-037 D1 part 1 — coverage.

    Every validator `.pre-commit-config.yaml` invokes with `--block` has a CI
    invocation that also passes `--block`.

    Coverage is asserted separately from monotonicity, and separately first,
    because monotonicity alone is satisfied *vacuously* by a validator CI never
    runs: an empty flag set is trivially a superset of nothing. A rule
    quantified over the intersection of the two surfaces cannot see a validator
    missing from one of them — which is exactly how three blocking checks came
    to exist only on contributor machines.

    This class therefore quantifies over pre-commit's `--block` hooks. A
    validator absent from CI FAILS here; it does not skip.
    """

    @pytest.mark.parametrize("script", BLOCK_VALIDATOR_NAMES)
    def test_ci_invokes_every_block_hook_with_block(self, script):
        """
        Given: a validator that .pre-commit-config.yaml invokes with a
               strictness flag
        When: every `run:` step in every workflow is searched for an invocation
              of that validator carrying the same flags
        Then: at least one such invocation exists

        "At least one", not "every": ADR-037 D3 exempts graph-emission
        invocations, and D2 covers that exemption by requiring the dedicated
        validation job to run the same corpus with `--block` in the same CI run.
        """
        required = BLOCK_VALIDATORS[script]
        hook_sources = _hook_sources_for(script)
        ci_invocations = _ci_invocations_of(script)

        assert ci_invocations, (
            f"{script} is invoked with {sorted(required)} by {hook_sources} but is not "
            f"invoked by any workflow under {_WORKFLOW_DIR}, and no workflow runs "
            f"`pre-commit` either. The check therefore runs only for contributors who "
            f"chose to install the hooks, so the merge decision depends on their local "
            f"state. ADR-037 D1 part 1 requires a CI invocation carrying {sorted(required)}."
        )

        satisfying = [inv for inv in ci_invocations if required.issubset(_strictness_flags(inv))]
        assert satisfying, (
            f"{script} is invoked with {sorted(required)} by {hook_sources}, but no "
            f"workflow invocation carries those flags. CI invocations found:\n"
            + "\n".join(f"  - {inv.source}: {inv.line}  (argv={list(inv.argv)})" for inv in ci_invocations)
            + "\nADR-037 D1 part 1: blocking locally and advisory in CI is not a "
            "supported state, and neither is blocking locally and absent from CI."
        )


class TestStrictnessMonotonicity:
    """ADR-037 D1 part 2 — monotonicity.

    For any validator invoked from both surfaces, the CI invocation is at least
    as strict as the pre-commit invocation.

    This is deliberately the intersection-shaped rule the ADR warns about, kept
    as a distinct assertion because it is the half that generalizes: it governs
    any future strictness flag, including one CI carries partially. It is not
    load-bearing for the current gap — TestStrictnessCoverage is — and a
    validator absent from CI skips here by design, with the skip reason naming
    the class that does fail on it.
    """

    @pytest.mark.parametrize("script", BLOCK_VALIDATOR_NAMES)
    def test_ci_strictness_flags_are_a_superset_of_hook_strictness_flags(self, script):
        """
        Given: a validator present on both the pre-commit and CI surfaces
        When: the union of strictness flags on each surface is compared
        Then: the CI set is a superset of the hook set

        Skips when the validator has no CI invocation at all: that is the
        coverage failure, reported by TestStrictnessCoverage. Asserting it here
        too would duplicate one finding across two classes.
        """
        ci_invocations = _ci_invocations_of(script)
        if not ci_invocations:
            pytest.skip(
                f"{script} has no CI invocation, so it is outside the intersection this "
                f"rule quantifies over. The coverage half — "
                f"TestStrictnessCoverage::test_ci_invokes_every_block_hook_with_block — "
                f"is what fails on it, by design."
            )

        required = BLOCK_VALIDATORS[script]
        # Union across CI invocations: D3 exempts the graph-emission call site,
        # so the surface as a whole must carry the strictness, not every call.
        ci_flags: frozenset[str] = frozenset().union(*(_strictness_flags(inv) for inv in ci_invocations))

        assert required.issubset(ci_flags), (
            f"{script}: pre-commit strictness {sorted(required)} (from {_hook_sources_for(script)}) "
            f"is not a subset of CI strictness {sorted(ci_flags)}. CI invocations found:\n"
            + "\n".join(f"  - {inv.source}: {inv.line}  (argv={list(inv.argv)})" for inv in ci_invocations)
            + "\nADR-037 D1 part 2: where the two surfaces differ, CI is stricter, never laxer."
        )


# ===========================================================================
# 3. D3 — `--block` must not be paired with graph emission
# ===========================================================================


class TestGraphEmissionExclusion:
    """ADR-037 D3: no invocation pairs `--block` with a graph-emission flag.

    `validate_riskmap.py`'s warn-only `sys.exit` runs before every emission
    block, so the pairing exits without writing a graph file and reports a
    content warning as a generation failure — skipping the diff against the
    committed graph, which is the whole point of that job.

    The live-workflow test passes at authoring time; ADR-037 D3 records that it
    codifies existing practice. The two synthetic tests establish that it would
    not pass if a violation were introduced, in either the literal or the
    variable-built form.
    """

    def test_no_workflow_pairs_block_with_graph_emission(self):
        """
        Given: every Python invocation across all workflows, with shell
               variables expanded
        When: invocations carrying a graph-emission flag are checked for
              `--block`
        Then: none carry both
        """
        violations = [
            inv
            for inv in WORKFLOW_INVOCATIONS
            if _is_graph_emitting(inv) and STRICTNESS_FLAGS.intersection(inv.argv)
        ]
        assert not violations, (
            "ADR-037 D3 prohibits pairing a strictness flag with graph emission:\n"
            + "\n".join(f"  - {inv.source}: {inv.line}  (argv={list(inv.argv)})" for inv in violations)
            + "\nThe warn-only exit precedes every emission block, so the process "
            "terminates before writing a graph and the job reports a generation "
            "failure for what is actually a content warning."
        )

    def test_detector_flags_literal_block_with_graph_flag(self):
        """
        Given: a synthetic `run:` block naming the script inline and passing
               both `--block` and `--to-graph`
        When: invocations are derived and checked
        Then: the pairing is detected

        Fidelity check on the plain form.
        """
        run_block = 'python3 validate_riskmap.py --force --block --to-graph "${temp_file}"\n'
        invocations = _python_invocations(run_block, "synthetic::literal")
        paired = [inv for inv in invocations if _is_graph_emitting(inv) and "--block" in inv.argv]
        assert paired, f"Detector missed a literal --block + --to-graph pairing. Parsed: {invocations}"

    def test_detector_flags_variable_built_block_with_graph_flag(self):
        """
        Given: a synthetic `run:` block in the shape validation.yml's
               graph-validation job actually uses — script name held in
               VALIDATE_CMD, emission flags in an indexed array, `--block`
               reached only after expansion
        When: invocations are derived and checked
        Then: the pairing is detected

        This is the blindness the prohibition cannot afford. If this test
        fails, test_no_workflow_pairs_block_with_graph_emission is passing
        because it cannot see the call site, not because the call site is
        clean.
        """
        run_block = (
            'VALIDATE_CMD="validate_riskmap.py"\n'
            'STRICT="--block"\n'
            'GENERATE_ARGS=("--to-graph" "--to-controls-graph" "--to-risk-graph")\n'
            'for i in "${!GENERATE_ARGS[@]}"; do\n'
            '    gen_args="${GENERATE_ARGS[$i]}"\n'
            '    if ! python3 ${VALIDATE_CMD} --force ${STRICT} ${gen_args} "${temp_file}"; then\n'
            '        echo "failed"\n'
            "    fi\n"
            "done\n"
        )
        invocations = _python_invocations(run_block, "synthetic::variable-built")
        paired = [inv for inv in invocations if _is_graph_emitting(inv) and "--block" in inv.argv]
        assert paired, (
            "Detector missed a variable-built --block + graph-emission pairing. "
            f"Parsed: {invocations}. The real graph-validation job is written in this "
            "shape, so a detector that cannot resolve it is blind exactly where D3's "
            "risk lives."
        )


# ===========================================================================
# 4. D7b — the precommit/ validators are invoked in place, never copied
# ===========================================================================


class TestPrecommitValidatorsRunInPlace:
    """ADR-037 D7b: new CI invocations run scripts at their real paths.

    Copying a `scripts/hooks/precommit/` validator to the repository root
    breaks two module-relative derivations at once:

    1. `_HOOKS_DIR = Path(__file__).resolve().parent.parent` (used by every
       validator in that directory to put `scripts/hooks` on `sys.path` for its
       `precommit.*` sibling imports).
    2. `_DEFAULT_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent.parent
       / "risk-map" / "schemas"` in `validate_yaml_prose_subset.py` and
       `validate_prose_references.py` — four levels up from
       `scripts/hooks/precommit/` lands on the repo root; four levels up from
       the repo root lands outside the repository.

    The first failure is loud, and that is what makes the second dangerous. An
    implementer who copies only the script gets an ImportError and fixes it the
    obvious way — by copying the `precommit/` package alongside, mirroring what
    `validation.yml` already does for `riskmap_validator`. That silences the
    loud failure and leaves the silent one: the schema directory now resolves
    outside the repository, `find_prose_fields` hits
    `if schema_path is None: return` (`_prose_fields.py:284-292`), and the job
    exits 0 having inspected nothing.

    This is measured, not reasoned about — see
    test_relocated_validator_goes_vacuous_while_in_place_catches below, which
    observes exit 1 with a diagnostic in place and exit 0 with empty stderr
    relocated, from the same poisoned corpus.

    D5 is untouched by this class. D5 keeps the five existing copy-to-root
    steps for `validate_riskmap.py`, `validate_control_risk_references.py`,
    `validate_framework_references.py` and `riskmap_validator/`; nothing here
    asserts anything about those. D7b prohibits *extending* the pattern to the
    `precommit/` validators, which D5's own text records as not being a
    copy-to-root change.

    The structural prohibitions pass at authoring time because the three
    validators have no CI invocation yet — they are forward guards on the
    implementation D7 requires. The synthetic-detector tests are what stop that
    pass from being worthless.
    """

    def test_no_workflow_copies_a_precommit_validator(self):
        """
        Given: every file-relocating command across all workflows
        When: sources are matched against the derived precommit/ validator set
        Then: none of them relocates one

        Forward guard: today no workflow mentions these scripts at all. The
        moment D7 wiring lands, this is the assertion that rejects the
        copy-to-root spelling of it.
        """
        violations = [
            copy
            for copy in WORKFLOW_COPY_COMMANDS
            if any(
                copy.source_path.endswith(name) or _PRECOMMIT_DIR_FRAGMENT in copy.source_path
                for name in PRECOMMIT_VALIDATORS
            )
        ]
        assert not violations, (
            "ADR-037 D7b prohibits relocating a scripts/hooks/precommit/ validator:\n"
            + "\n".join(f"  - {c.source}: {c.line}  ({c.source_path} -> {c.destination})" for c in violations)
            + "\nThese validators derive sys.path and their default --schema-dir from "
            "Path(__file__); relocating them makes field discovery return silently and "
            "the job exit 0 having inspected nothing. Invoke them in place instead."
        )

    def test_workflow_invocations_of_precommit_validators_use_real_paths(self):
        """
        Given: every workflow invocation of a derived precommit/ validator
        When: the invoked path is compared to the validator's real path
        Then: they match

        Catches the other half of the same mistake — invoking a bare basename
        from the repository root after copying it there by some means this
        suite's copy scan did not model (an archive extraction, a checkout into
        a different layout, a `python -c` shim).
        """
        violations = [
            inv
            for inv in WORKFLOW_INVOCATIONS
            if inv.script in PRECOMMIT_VALIDATORS and inv.path != PRECOMMIT_VALIDATORS[inv.script]
        ]
        assert not violations, (
            "ADR-037 D7b requires these validators to be invoked at their real paths:\n"
            + "\n".join(
                f"  - {inv.source}: invoked as {inv.path!r}, "
                f"expected {PRECOMMIT_VALIDATORS[inv.script]!r}\n      {inv.line}"
                for inv in violations
            )
            + "\nA path other than the real one changes what Path(__file__) resolves to, "
            "which is what these validators derive their schema directory from."
        )

    def test_copy_detector_flags_literal_copy_to_root(self):
        """
        Given: a synthetic `run:` block copying a precommit/ validator to the
               repository root, in the shape validation.yml's existing copy
               steps use
        When: copy commands are derived
        Then: the relocation is detected

        Fidelity check on the plain form.
        """
        run_block = (
            "cp scripts/hooks/precommit/validate_yaml_prose_subset.py .\n"
            "mkdir -p precommit\n"
            "cp -r scripts/hooks/precommit/* ./precommit/\n"
        )
        copies = _copy_commands(run_block, "synthetic::literal-copy")
        flagged = [c for c in copies if "validate_yaml_prose_subset.py" in c.source_path]
        assert flagged, f"Detector missed a literal copy-to-root of a precommit/ validator. Parsed: {copies}"

    def test_copy_detector_flags_variable_built_copy_to_root(self):
        """
        Given: a synthetic `run:` block copying a precommit/ validator through
               shell variables rather than a literal path
        When: copy commands are derived
        Then: the relocation is detected

        This is the version a real implementer writes without noticing. A
        detector that only matches literal paths would wave it through, and the
        prohibition would be present, green, and blind — the same failure mode
        the D3 detector tests guard against.
        """
        run_block = (
            'PRECOMMIT_DIR="scripts/hooks/precommit"\n'
            'VALIDATORS=("validate_yaml_prose_subset.py" "validate_prose_references.py")\n'
            'for v in "${VALIDATORS[@]}"; do\n'
            '    cp "${PRECOMMIT_DIR}/${v}" .\n'
            "done\n"
        )
        copies = _copy_commands(run_block, "synthetic::variable-built-copy")
        flagged = [c for c in copies if _PRECOMMIT_DIR_FRAGMENT in c.source_path]
        assert flagged, (
            "Detector missed a variable-built copy-to-root of a precommit/ validator. "
            f"Parsed: {copies}. Extending the copy-to-root pattern is most likely to be "
            "written this way, so a detector blind to it protects nothing."
        )

    def test_path_detector_flags_bare_basename_invocation(self):
        """
        Given: a synthetic `run:` block invoking a precommit/ validator by bare
               basename from the repository root
        When: invocations are derived
        Then: the invoked path is visibly not the real path

        Fidelity check for test_workflow_invocations_of_precommit_validators_use_real_paths,
        which is vacuous today.
        """
        run_block = "python3 validate_prose_references.py risk-map/yaml/risks.yaml --block\n"
        invocations = _python_invocations(run_block, "synthetic::bare-basename")
        assert invocations, f"Detector parsed no invocation at all from {run_block!r}"
        assert invocations[0].path == "validate_prose_references.py", (
            f"Invocation.path must preserve the path as written; got {invocations[0].path!r}"
        )
        assert invocations[0].path != PRECOMMIT_VALIDATORS.get("validate_prose_references.py"), (
            "A bare-basename invocation must not compare equal to the real path, "
            "or the D7b path check cannot distinguish them."
        )

    def test_relocated_validator_goes_vacuous_while_in_place_catches(self, tmp_path):
        """
        Given: one poisoned corpus, and validate_yaml_prose_subset.py run two
               ways against it — in place, and relocated to the corpus root
               with its precommit/ package copied alongside (the arrangement an
               implementer reaches after fixing the ImportError)
        When: both runs pass --block and no explicit --schema-dir, so each uses
              its own Path(__file__)-derived default
        Then: the in-place run exits non-zero and names the violation; the
              relocated run exits 0 and reports nothing

        The behavioural anchor. It reasons about no paths and asserts no
        string: it observes that relocation changes the verdict on identical
        input, which is the entire evidentiary basis for D7b.

        If this test ever fails because the relocated run *also* catches the
        violation, the hazard has been fixed — revisit D7b's rationale, but
        keep the prohibition, which stands independently on the sys.path
        derivation the same relocation breaks.

        tmp_path sits several levels below /tmp, so the relocated copy's
        four-levels-up schema derivation lands on a directory that does not
        contain risk-map/schemas — reproducing CI's condition rather than
        depending on it.
        """
        validator = _HOOKS_DIR / "precommit" / "validate_yaml_prose_subset.py"
        yaml_dir = _yaml_dir(tmp_path)
        # shortDescription is a prose field in the real risks.schema.json, so the
        # in-place arm resolves it through the repository's actual schemas.
        poisoned = {
            "risks": [{"id": "riskProbe", "title": "Probe", "shortDescription": ["See https://example.com here."]}]
        }
        (yaml_dir / "risks.yaml").write_text(yaml.dump(poisoned), encoding="utf-8")

        in_place = subprocess.run(
            [sys.executable, str(validator), "risk-map/yaml/risks.yaml", "--block"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert in_place.returncode != 0, (
            f"Harness precondition failed: the in-place run should catch the injected "
            f"inline-URL violation; got {in_place.returncode}\n"
            f"stdout: {in_place.stdout}\nstderr: {in_place.stderr}"
        )
        assert "example.com" in in_place.stderr, (
            f"In-place run exited non-zero but did not name the violation, so it may "
            f"have failed for an unrelated reason.\nstderr: {in_place.stderr}"
        )

        # Reproduce copy-to-root the way an implementer would after hitting the
        # ImportError: script to the root, precommit/ package alongside it.
        shutil.copy2(validator, tmp_path / validator.name)
        shutil.copytree(_HOOKS_DIR / "precommit", tmp_path / "precommit", dirs_exist_ok=True)

        relocated = subprocess.run(
            [sys.executable, validator.name, "risk-map/yaml/risks.yaml", "--block"],
            capture_output=True,
            text=True,
            cwd=str(tmp_path),
        )
        assert relocated.returncode == 0 and "example.com" not in relocated.stderr, (
            "The relocated copy caught the violation. D7b's rationale rests on it NOT "
            "doing so: the four-levels-up --schema-dir derivation is expected to land "
            "outside the repository, making find_prose_fields return silently. If this "
            "assertion fails the hazard has changed — re-derive D7b's justification, and "
            "keep the prohibition on the sys.path grounds regardless.\n"
            f"exit: {relocated.returncode}\nstdout: {relocated.stdout}\n"
            f"stderr: {relocated.stderr}"
        )


# ===========================================================================
# 5. D4 — behavioural non-vacuity
# ===========================================================================
#
# Each validator gets a probe that writes two corpora into a temporary
# directory: one clean, one carrying a single deliberately injected warn-level
# violation. The probes are what turn "the flag is present" into "the flag
# changes the verdict".
#
# Argument order matters. Probe positionals are placed FIRST, before any
# derived CI arguments and before the probe's own options, because
# validate_prose_references.py declares `--id-sources` with nargs="+": a
# positional following it is swallowed as another id-source, `files` ends up
# empty, and main() exits 0 immediately. That produces a passing test that
# validated nothing. Probe options go LAST so they win over any conflicting
# derived value (argparse store actions are last-wins).
#
# Probes write their poisoned content at the canonical repo-relative paths
# (risk-map/yaml/...), so a derived CI argument naming such a path resolves
# inside the temporary corpus rather than escaping to the real one.


class BlockProbe(NamedTuple):
    """A validator plus the means to trigger exactly one of its warn-level checks.

    Attributes:
        script_path: Real on-disk path to the validator.
        write_corpus: Callable (base_dir, poisoned) -> None that materializes a
            corpus under base_dir. With poisoned=False the corpus is clean.
        positionals: File arguments, repo-relative, placed before all options.
        enabling_args: Arguments without which the validator does not examine
            the corpus at all. `validate_riskmap.py` and
            `validate_framework_references.py` gate on git-staged files unless
            given `--force`; run in a temporary directory without it, `git diff
            --cached` fails, the validator prints "skipping validation" and
            exits 0. That is a pass for the wrong reason, so the validator tier
            supplies these explicitly. The CI tier deliberately does not — see
            TestCIInvocationCatchesViolation.
        options: Non-strictness options the validator needs to read the
            temporary corpus rather than the real one.
        marker: A string that must appear in warn-mode output when poisoned —
            proves the intended check fired, not some unrelated one.
        warn_check: Which warn-only check the poison triggers, for docs.
    """

    script_path: Path
    write_corpus: Callable[[Path, bool], None]
    positionals: tuple[str, ...]
    enabling_args: tuple[str, ...]
    options: tuple[str, ...]
    marker: str
    warn_check: str


def _yaml_dir(base: Path) -> Path:
    """Create and return base/risk-map/yaml/."""
    path = base / "risk-map" / "yaml"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _schema_dir(base: Path) -> Path:
    """Create and return base/risk-map/schemas/."""
    path = base / "risk-map" / "schemas"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_mock_prose_schema(schema_dir: Path, entity: str, ids: list[str]) -> None:
    """Write a minimal schema marking `description` as a prose field.

    The prose linters discover fields by introspecting for the
    `riskmap.schema.json#/definitions/utils/text` $ref, so a mock schema
    declaring that ref is enough to make a field visible to them. Same shape
    as the helper in test_validate_yaml_prose_subset.py.
    """
    prose_ref = {"$ref": "riskmap.schema.json#/definitions/utils/text"}
    schema = {
        "$id": f"mock_{entity}s.schema.json",
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "properties": {f"{entity}s": {"type": "array", "items": {"$ref": f"#/definitions/{entity}"}}},
        "definitions": {
            entity: {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "enum": ids},
                    "title": {"type": "string"},
                    "description": prose_ref,
                },
            }
        },
    }
    (schema_dir / f"{entity}s.schema.json").write_text(json.dumps(schema), encoding="utf-8")


# --- corpus writers ---------------------------------------------------------

# Two mutually-referencing components, so ComponentEdgeValidator finds valid
# back-edges and neither component is isolated. That matters: CI invokes
# validate_riskmap.py without --allow-isolated, so an isolated component would
# make the poisoned run exit 1 for the wrong reason and turn D4 falsely green.
_COMPONENTS: dict[str, Any] = {
    "components": [
        {
            "id": "componentAlpha",
            "title": "Alpha",
            "category": "componentsInfrastructure",
            "subcategory": "componentsData",
            "edges": {"to": ["componentBeta"], "from": []},
        },
        {
            "id": "componentBeta",
            "title": "Beta",
            "category": "componentsInfrastructure",
            "subcategory": "componentsData",
            "edges": {"to": [], "from": ["componentAlpha"]},
        },
    ],
    "categories": [
        {
            "id": "componentsInfrastructure",
            "title": "Infrastructure",
            "subcategory": [{"id": "componentsData", "title": "Data"}],
        }
    ],
}


def _write_riskmap_corpus(base: Path, poisoned: bool) -> None:
    """Corpus for validate_riskmap.py; poison = controls↔components mirror drift."""
    yaml_dir = _yaml_dir(base)
    components = (
        ["componentAlpha", "componentProbeDoesNotExist"] if poisoned else ["componentAlpha", "componentBeta"]
    )
    controls = {
        "controls": [
            {
                "id": "controlProbe",
                "title": "Probe Control",
                "category": "controlsModel",
                "components": components,
                "risks": [],
                "personas": [],
            }
        ]
    }
    (yaml_dir / "components.yaml").write_text(yaml.dump(_COMPONENTS), encoding="utf-8")
    (yaml_dir / "controls.yaml").write_text(yaml.dump(controls), encoding="utf-8")
    (yaml_dir / "risks.yaml").write_text(yaml.dump({"risks": []}), encoding="utf-8")


def _write_framework_refs_corpus(base: Path, poisoned: bool) -> None:
    """Corpus for validate_framework_references.py; poison = deprecated-persona reference."""
    yaml_dir = _yaml_dir(base)
    frameworks = {
        "frameworks": [
            {
                "id": "mitre-atlas",
                "name": "MITRE ATLAS",
                "fullName": "Adversarial Threat Landscape for AI Systems",
                "description": "Probe framework entry.",
                "baseUri": "https://atlas.mitre.org",
                "applicableTo": ["risks", "controls"],
            }
        ]
    }
    current = {"id": "personaModelProvider", "title": "Model Provider", "description": ["A current persona."]}
    deprecated = {
        "id": "personaModelCreator",
        "title": "Model Creator",
        "description": ["Legacy persona retained for backward compatibility."],
        "deprecated": True,
    }
    personas = {"personas": [current, deprecated] if poisoned else [current]}
    referenced = "personaModelCreator" if poisoned else "personaModelProvider"
    controls = {"controls": [{"id": "controlProbe", "title": "Probe Control", "personas": [referenced]}]}
    risks = {"risks": [{"id": "riskProbe", "title": "Probe Risk", "personas": ["personaModelProvider"]}]}

    (yaml_dir / "frameworks.yaml").write_text(yaml.dump(frameworks), encoding="utf-8")
    (yaml_dir / "personas.yaml").write_text(yaml.dump(personas), encoding="utf-8")
    (yaml_dir / "controls.yaml").write_text(yaml.dump(controls), encoding="utf-8")
    (yaml_dir / "risks.yaml").write_text(yaml.dump(risks), encoding="utf-8")


# Five questions satisfies the count floor (COUNT_MIN=5) and each uses an
# approved opener, so the clean corpus trips none of the four structural rules.
_CLEAN_IDENTIFICATION_QUESTIONS = [
    "Do you own the model weights?",
    "Do you publish the model to a registry?",
    "Do you control the training data pipeline?",
    "Are you responsible for evaluating model behaviour?",
    "Does your team operate the serving stack?",
]


def _write_identification_questions_corpus(base: Path, poisoned: bool) -> None:
    """Corpus for validate_identification_questions.py; poison = missing block on a live persona."""
    yaml_dir = _yaml_dir(base)
    persona: dict[str, Any] = {"id": "personaProbe", "title": "Probe Persona", "description": ["A probe persona."]}
    if not poisoned:
        persona["identificationQuestions"] = _CLEAN_IDENTIFICATION_QUESTIONS
    (yaml_dir / "personas.yaml").write_text(yaml.dump({"personas": [persona]}), encoding="utf-8")


def _write_prose_subset_corpus(base: Path, poisoned: bool) -> None:
    """Corpus for validate_yaml_prose_subset.py; poison = inline URL in prose (ADR-017 D4)."""
    yaml_dir = _yaml_dir(base)
    _write_mock_prose_schema(_schema_dir(base), "risk", ["riskProbe"])
    description = ["See https://example.com for details."] if poisoned else ["Clean prose with **bold** text."]
    risks = {"risks": [{"id": "riskProbe", "title": "Probe Risk", "description": description}]}
    (yaml_dir / "risks.yaml").write_text(yaml.dump(risks), encoding="utf-8")


def _write_prose_references_corpus(base: Path, poisoned: bool) -> None:
    """Corpus for validate_prose_references.py; poison = unresolvable intra-doc sentinel (ADR-016 D6)."""
    yaml_dir = _yaml_dir(base)
    _write_mock_prose_schema(_schema_dir(base), "risk", ["riskProbe"])
    description = ["The {{riskProbeDoesNotExist}} applies here."] if poisoned else ["Clean prose here."]
    risks = {"risks": [{"id": "riskProbe", "title": "Probe Risk", "description": description}]}
    (yaml_dir / "risks.yaml").write_text(yaml.dump(risks), encoding="utf-8")
    # An empty index makes sentinel resolution deterministic: the poisoned
    # sentinel resolves against nothing, the clean prose has none to resolve.
    (yaml_dir / "probe-index.yaml").write_text(yaml.dump({"risks": []}), encoding="utf-8")


# --- probe registry ---------------------------------------------------------

BLOCK_PROBES: dict[str, BlockProbe] = {
    "validate_riskmap.py": BlockProbe(
        script_path=_HOOKS_DIR / "validate_riskmap.py",
        write_corpus=_write_riskmap_corpus,
        positionals=(),
        enabling_args=("--force",),
        options=(),
        marker="componentProbeDoesNotExist",
        warn_check="check_controls_components_mirror (ADR-020 D7)",
    ),
    "validate_framework_references.py": BlockProbe(
        script_path=_HOOKS_DIR / "validate_framework_references.py",
        write_corpus=_write_framework_refs_corpus,
        positionals=(),
        enabling_args=("--force",),
        options=(),
        marker="personaModelCreator",
        warn_check="check_deprecated_persona_usage (ADR-021 D8)",
    ),
    "validate_identification_questions.py": BlockProbe(
        script_path=_HOOKS_DIR / "precommit" / "validate_identification_questions.py",
        write_corpus=_write_identification_questions_corpus,
        positionals=("risk-map/yaml/personas.yaml",),
        enabling_args=(),
        options=(),
        marker="personaProbe",
        warn_check="identificationQuestions presence rule (Rule 0)",
    ),
    "validate_yaml_prose_subset.py": BlockProbe(
        script_path=_HOOKS_DIR / "precommit" / "validate_yaml_prose_subset.py",
        write_corpus=_write_prose_subset_corpus,
        positionals=("risk-map/yaml/risks.yaml",),
        enabling_args=(),
        options=("--schema-dir", "risk-map/schemas"),
        marker="riskProbe",
        warn_check="inline-URL rejection (ADR-017 D4)",
    ),
    "validate_prose_references.py": BlockProbe(
        script_path=_HOOKS_DIR / "precommit" / "validate_prose_references.py",
        write_corpus=_write_prose_references_corpus,
        positionals=("risk-map/yaml/risks.yaml",),
        enabling_args=(),
        options=("--schema-dir", "risk-map/schemas", "--id-sources", "risk-map/yaml/probe-index.yaml"),
        marker="riskProbeDoesNotExist",
        warn_check="intra-doc sentinel resolution (ADR-016 D6)",
    ),
}


def _run_probe(
    probe: BlockProbe,
    cwd: Path,
    extra: tuple[str, ...],
    with_enabling_args: bool = True,
) -> subprocess.CompletedProcess:
    """Run a probe's validator against a corpus directory.

    Positionals lead, then enabling args, then any caller-supplied arguments,
    then the probe's own options — see the ordering note above the probe
    registry.

    Args:
        with_enabling_args: The CI tier passes False so that the derived
            workflow arguments stand alone. If a workflow invocation omitted
            `--force`, the validator would skip the corpus and exit 0, and that
            must surface as a failure rather than be papered over here.
    """
    command = [
        sys.executable,
        str(probe.script_path),
        *probe.positionals,
        *(probe.enabling_args if with_enabling_args else ()),
        *extra,
        *probe.options,
    ]
    return subprocess.run(command, capture_output=True, text=True, cwd=str(cwd))


class TestBlockFlagChangesBehaviour:
    """D4, validator tier: `--block` demonstrably changes the verdict.

    This is the precondition for D1 and D2 being worth anything — if the flag
    were inert, adding it to a workflow would be a no-op dressed as a fix.
    These tests are expected to pass: all five validators already implement the
    toggle correctly. What is missing is the CI wiring, which the next class
    covers.
    """

    def test_every_block_validator_has_a_behavioural_probe(self):
        """
        Given: the derived set of strictness-flagged pre-commit validators
        When: compared against the probe registry
        Then: every one has a probe

        Applies the same derive-don't-enumerate rule to D4 that D1 uses. A
        validator that gains `--block` in pre-commit tomorrow fails here until
        someone writes a probe that triggers one of its warn-level checks,
        rather than being quietly excluded from behavioural coverage.
        """
        unprobed = sorted(set(BLOCK_VALIDATOR_NAMES) - set(BLOCK_PROBES))
        assert not unprobed, (
            f"No behavioural probe for strictness-flagged validators: {unprobed}. "
            "Each needs a corpus writer that triggers one of its warn-level checks, "
            "so its --block can be shown to change a verdict rather than merely "
            "being present on a command line."
        )

        stale = sorted(set(BLOCK_PROBES) - set(BLOCK_VALIDATOR_NAMES))
        assert not stale, (
            f"Probes exist for validators no longer invoked with a strictness flag "
            f"by pre-commit: {stale}. Either the hook lost its flag or the probe is dead."
        )

    @pytest.mark.parametrize("script", sorted(BLOCK_PROBES))
    def test_block_flag_changes_exit_code_on_injected_violation(self, script, tmp_path):
        """
        Given: a temporary corpus carrying one injected warn-level violation
        When: the validator runs over it with and without `--block`
        Then: the warn run exits 0 and names the violation; the block run
              exits non-zero

        Both halves are asserted. Exit codes differing is not enough on its
        own — a validator that crashed under `--block` would also differ. The
        marker assertion pins that the intended check fired and produced
        actionable output in warn mode, per ADR-025 D10.
        """
        probe = BLOCK_PROBES[script]
        probe.write_corpus(tmp_path, True)

        warn = _run_probe(probe, tmp_path, ())
        block = _run_probe(probe, tmp_path, ("--block",))

        assert warn.returncode == 0, (
            f"{script}: warn-only mode should exit 0 on the poisoned corpus "
            f"({probe.warn_check}); got {warn.returncode}\n"
            f"stdout: {warn.stdout}\nstderr: {warn.stderr}"
        )
        combined = warn.stdout + warn.stderr
        assert probe.marker in combined, (
            f"{script}: warn-only output does not name {probe.marker!r}, so the "
            f"injected violation may not have reached {probe.warn_check} at all. "
            f"Exit 0 alone cannot distinguish 'clean' from 'never ran'.\n"
            f"stdout: {warn.stdout}\nstderr: {warn.stderr}"
        )
        assert block.returncode != 0, (
            f"{script}: --block did not change the verdict on a corpus carrying a "
            f"{probe.warn_check} violation; got {block.returncode}. The flag is inert, "
            f"so adding it to a workflow would change nothing.\n"
            f"stdout: {block.stdout}\nstderr: {block.stderr}"
        )

    @pytest.mark.parametrize("script", sorted(BLOCK_PROBES))
    def test_clean_corpus_exits_zero_with_and_without_block(self, script, tmp_path):
        """
        Given: the same corpus with the violation removed
        When: the validator runs over it with and without `--block`
        Then: both exit 0

        Controls the previous test. Without this, a validator that exited
        non-zero on everything would satisfy the block assertion for the wrong
        reason, and the poison would be proving nothing.
        """
        probe = BLOCK_PROBES[script]
        probe.write_corpus(tmp_path, False)

        warn = _run_probe(probe, tmp_path, ())
        block = _run_probe(probe, tmp_path, ("--block",))

        assert warn.returncode == 0, (
            f"{script}: clean corpus should exit 0 without --block; got {warn.returncode}\n"
            f"stdout: {warn.stdout}\nstderr: {warn.stderr}"
        )
        assert block.returncode == 0, (
            f"{script}: clean corpus should exit 0 with --block; got {block.returncode}. "
            f"--block must promote existing warnings, never manufacture one.\n"
            f"stdout: {block.stdout}\nstderr: {block.stderr}"
        )


class TestCIInvocationCatchesViolation:
    """D4, CI tier: the command CI actually runs catches the violation.

    The previous class establishes that `--block` works. This one establishes
    that CI passes it. It takes the argument list derived from the workflow and
    runs the real validator with it against the poisoned corpus: if the derived
    arguments omit the strictness flag, the run exits 0 and the test fails —
    a behavioural statement about the merge gate, not a string match on YAML.

    Graph-emitting invocations are excluded as candidates: ADR-037 D3 forbids
    `--block` there, and D2 covers the same corpus in the dedicated job during
    the same CI run.

    The validator is run from its real path rather than from a copied root, so
    this suite neither depends on nor perturbs the copy-to-root arrangement
    ADR-037 D5 keeps in place. What is under test is the argument list, which
    is where strictness lives.
    """

    @pytest.mark.parametrize("script", sorted(BLOCK_PROBES))
    def test_ci_invocations_carry_enabling_arguments(self, script):
        """
        Given: a validator whose probe declares enabling arguments
        When: every non-graph-emitting CI invocation of it is inspected
        Then: each carries those arguments

        The `--force` drift guard. `validate_riskmap.py` and
        `validate_framework_references.py` decide what to validate from
        `git diff --cached`. In a CI checkout where that command fails or
        returns nothing, they print "skipping validation" and exit 0 — a green
        job that inspected no file. `--force` is what makes them examine the
        corpus unconditionally, so losing it converts a real gate into a
        vacuous one without any visible failure.

        Both invocations carry it today; this keeps a future edit from dropping
        it. The behavioural counterpart is the marker precondition in
        test_derived_ci_arguments_fail_on_injected_violation, which fails if a
        CI invocation ever stops reaching the check at all — that assertion
        exists because this exact trap caught this suite's own harness during
        authoring.
        """
        probe = BLOCK_PROBES[script]
        if not probe.enabling_args:
            pytest.skip(f"{script} needs no enabling arguments to examine a corpus.")

        candidates = [inv for inv in _ci_invocations_of(script) if not _is_graph_emitting(inv)]
        if not candidates:
            pytest.skip(f"{script} has no CI invocation; TestStrictnessCoverage is what fails on that.")

        missing = [
            (inv, sorted(set(probe.enabling_args) - set(inv.argv)))
            for inv in candidates
            if not set(probe.enabling_args).issubset(inv.argv)
        ]
        assert not missing, (
            f"{script}: CI invocations missing arguments without which the validator "
            f"does not examine the corpus at all:\n"
            + "\n".join(f"  - {inv.source}: missing {gap}\n      {inv.line}" for inv, gap in missing)
            + f"\nWithout {sorted(probe.enabling_args)} this validator skips validation and "
            f"exits 0, which is a passing job that checked nothing."
        )

    @pytest.mark.parametrize("script", BLOCK_VALIDATOR_NAMES)
    def test_derived_ci_arguments_fail_on_injected_violation(self, script, tmp_path):
        """
        Given: the argument list a workflow passes to a strictness-flagged
               validator, and a corpus carrying one injected warn-level
               violation
        When: the validator runs with exactly those arguments
        Then: it exits non-zero

        The clean corpus is checked first with the same arguments and must exit
        0. That separates "CI catches this" from "CI fails on everything", so a
        harness fault cannot masquerade as a pass.
        """
        probe = BLOCK_PROBES.get(script)
        if probe is None:
            pytest.fail(
                f"No behavioural probe registered for {script}; "
                "test_every_block_validator_has_a_behavioural_probe explains the gap."
            )

        candidates = [inv for inv in _ci_invocations_of(script) if not _is_graph_emitting(inv)]
        assert candidates, (
            f"No non-graph-emitting workflow invocation of {script} exists, so no CI "
            f"command can be run against the poisoned corpus. A {probe.warn_check} "
            f"violation reaches `main`/`develop` unopposed: pre-commit blocks it, CI "
            f"never looks, and no workflow runs `pre-commit` either.\n"
            f"All workflow invocations of {script}: "
            f"{[(i.source, list(i.argv)) for i in _ci_invocations_of(script)] or 'none'}"
        )

        failures: list[str] = []
        for invocation in candidates:
            clean_dir = tmp_path / f"clean-{abs(hash(invocation.source))}"
            clean_dir.mkdir()
            probe.write_corpus(clean_dir, False)
            clean = _run_probe(probe, clean_dir, invocation.argv, with_enabling_args=False)
            assert clean.returncode == 0, (
                f"Harness precondition failed: {invocation.source} arguments "
                f"{list(invocation.argv)} exit {clean.returncode} on a CLEAN corpus. "
                f"The poisoned result below would be meaningless.\n"
                f"stdout: {clean.stdout}\nstderr: {clean.stderr}"
            )

            poisoned_dir = tmp_path / f"poisoned-{abs(hash(invocation.source))}"
            poisoned_dir.mkdir()
            probe.write_corpus(poisoned_dir, True)
            poisoned = _run_probe(probe, poisoned_dir, invocation.argv, with_enabling_args=False)
            poisoned_output = poisoned.stdout + poisoned.stderr
            assert probe.marker in poisoned_output, (
                f"{invocation.source} arguments {list(invocation.argv)} never named "
                f"{probe.marker!r} on the poisoned corpus, so {probe.warn_check} did not "
                f"run at all — the invocation is reachable but vacuous, which is worse "
                f"than laxity because it reports success. "
                f"(validate_riskmap.py and validate_framework_references.py skip "
                f"validation entirely without --force.)\n"
                f"stdout: {poisoned.stdout}\nstderr: {poisoned.stderr}"
            )
            if poisoned.returncode == 0:
                failures.append(
                    f"  - {invocation.source}\n"
                    f"      line: {invocation.line}\n"
                    f"      argv: {list(invocation.argv)}\n"
                    f"      exit: 0 on a corpus carrying a {probe.warn_check} violation"
                )

        assert not failures, (
            f"{script}: the arguments CI passes do not catch an injected "
            f"{probe.warn_check} violation — the validator runs, reports the warning, "
            f"and exits 0, so the pull request merges.\n" + "\n".join(failures) + "\n"
            f"Pre-commit invokes this validator with {sorted(BLOCK_VALIDATORS[script])}; "
            f"ADR-037 D1/D2 require CI to do the same."
        )


# ===========================================================================
# Test Summary
# ===========================================================================
# Total tests: 46 across 7 classes.
#
# TestParserFidelity (6)
#   — pre-commit derivation finds strictness-flagged validators; workflow
#     derivation finds Python invocations; parser resolves the variable-built
#     graph invocation; `cp` steps are not read as invocations; pre-commit
#     script basenames are unambiguous (the D1 join key); graph-emission flag
#     names are real options of validate_riskmap.py.
#     All expected to PASS — they exist so the D1/D4 failures mean something
#     and so the D3 pass is not a blind one.
#
# TestStrictnessCoverage (5, parametrized over the derived set)
#   — D1 part 1: every validator invoked with a strictness flag by
#     .pre-commit-config.yaml has a workflow invocation carrying those flags.
#     Expected to FAIL for all five at authoring time: two validators are
#     invoked by CI without the flag, three are not invoked by any workflow.
#
# TestStrictnessMonotonicity (5, parametrized over the derived set)
#   — D1 part 2: for validators on both surfaces, CI strictness is a superset
#     of hook strictness.
#     Expected to FAIL for the two laxly-invoked validators and SKIP for the
#     three absent ones. The skips are not an oversight — they are the ADR's
#     stated reason for asserting coverage separately and first.
#
# TestGraphEmissionExclusion (3)
#   — no live workflow invocation pairs a strictness flag with graph emission;
#     detector catches a literal pairing; detector catches a variable-built
#     pairing.
#     Expected to PASS — ADR-037 D3 codifies existing practice rather than
#     changing it. The two synthetic tests are what make the live-workflow
#     pass non-vacuous.
#
# TestPrecommitValidatorsRunInPlace (6)
#   — D7b: no workflow relocates a scripts/hooks/precommit/ validator; every
#     workflow invocation of one uses its real path; detectors catch a literal
#     copy, a variable-built copy, and a bare-basename invocation; and a
#     relocated copy is observed going vacuous (exit 0, empty stderr) on the
#     same poisoned corpus the in-place run fails on (exit 1, diagnostic).
#     Expected to PASS — the two structural prohibitions are vacuous until D7
#     wiring lands, which is what the three detectors and the behavioural
#     anchor exist to compensate for.
#
# TestBlockFlagChangesBehaviour (1 + 5 + 5)
#   — every strictness-flagged validator has a probe; --block changes the exit
#     code on an injected warn-level violation and the warn output names it;
#     a clean corpus exits 0 both ways.
#     Expected to PASS — the toggles already work. This tier is the
#     precondition, not the deliverable.
#
# TestCIInvocationCatchesViolation (5 + 5, parametrized over the derived set)
#   — CI invocations carry the enabling arguments (`--force`) without which the
#     validator skips the corpus and exits 0. Expected to PASS for the two that
#     need them, SKIP for the three with no CI invocation and no enabling args.
#
#   — the argument list a workflow passes to each strictness-flagged validator
#     exits non-zero on a corpus carrying an injected warn-level violation,
#     having first exited 0 on the clean equivalent.
#     Expected to FAIL for all five. This is D4's answer to "the string is
#     present, not the behaviour": it fails on `--force` alone and passes only
#     once CI carries the flag.
#
# Warn-path coverage note (D4 disclosure)
#   Every one of the five validators has a warn path reachable from a fixture,
#   so none required the weaker "assert the flag is parsed" substitute. The
#   checks exercised are named per probe in BlockProbe.warn_check.

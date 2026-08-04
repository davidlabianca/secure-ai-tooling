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

  D7a (CI's file lists are constructed explicitly, and are complete)
      The three validators D7 wires take file arguments, and the list that
      reaches their argv decides whether they check anything. It must be
      *derived* from the hook's own `files:` pattern rather than transcribed
      (a transcribed list drifts permissively), it must equal the hook's whole
      file set rather than a prefix of it, and every file in it must actually
      be inspected by the arguments CI passes. The third is asserted
      behaviourally, once per resolved file, because the first two can hold
      while a bad `--schema-dir` makes the validator visit nothing.

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

What these tests are for, now that the gap is closed
----------------------------------------------------
D1, D2, D4 and D7's coverage half were all red when this module was written
against base commit 0d0b731, and all five `--block` validators now have CI
invocations carrying the flag. Sections 1-5 have therefore changed role: they
are standing guards, not a to-do list, and each is only as good as the edit it
would notice.

That is the whole design constraint on what follows. An assertion that a string
appears in a workflow notices a deleted string and nothing else, and every edit
that matters here — an empty file list, a truncated one, a `--schema-dir` that
resolves nowhere, a moved working directory, a step that finds the violation and
returns 0 anyway, a `paths:` filter that stops the job from running at all —
leaves every string in place. Sections 6 to 10 exist because those edits were
applied and measured, and sections 1 to 5 stayed green through all of them.

Section 8 fails as committed. Section 6's file-list assertions pass, but the
trigger rules do not: the gate does not yet re-run on changes to its own
definition, and the pytest workflow does not run on workflow edits. Everything
else here passes as committed and earns its place by the edit it would catch,
which is recorded per class.

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

Beyond the flags: what else has to hold
---------------------------------------
Three properties sit outside the command line and each fails silently on its
own, so each has a section of its own below.

  The file list (section 6). Derived, complete, and read — asserted by running
  the derivation and then running the validator once per file it names.

  The execution context (section 7). The resolver enumerates the corpus in the
  step's working directory and the validators open repo-relative paths there,
  so the step must run at the repository root; and `FILES=$(...)` only aborts
  under a shell that exits on error, which is what turns the resolver's
  exit-1-on-empty-match into a red job.

  The trigger (section 8). A workflow that does not run on a pull request is
  not a gate on it. A gate must trigger on its own definition, on the
  validators it executes, and on the config its file lists derive from;
  and the workflow running the whole pytest suite must trigger on the files
  this module asserts over, or every guard here is absent from exactly the
  pull request that disables it.

  The step's exit code (section 9). Everything above models the *validator's*
  exit code — it runs the validator and reads what it returns. The number that
  decides the job is the *step's*, produced by the `if ... else ... exit 1; fi`
  wrapper around each invocation, and nothing consumes the `status` outputs the
  steps write, so that wrapper is the entire enforcement mechanism. Deleting
  its `exit 1`, appending `|| true`, or adding `continue-on-error:` or a
  conditional `if:` each leave the violation found and printed and the job
  green — which is the warn-only soak ADR-037 D7 rejects by name, reached
  without touching a flag, a path, a file list, or a working directory.

  The inventory (section 10). Deleting a whole class from this module produced
  a smaller run and no failure. Several classes here are the only thing that
  would notice a particular edit, so what the module contains is asserted
  rather than described.

D3 passes at authoring time. ADR-037 D3 says so explicitly — it "codifies
existing practice rather than changing it". The D3 tests here are a standing
guard against a future workflow edit, and `TestGraphEmissionExclusion`'s
synthetic-detector tests establish that the guard would catch a violation in
both the literal and the variable-built form.
"""

import json
import os
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

# Filename suffixes GitHub Actions executes out of `.github/workflows/`. Both
# are honoured identically, so a scan restricted to one of them is blind to a
# workflow that runs. Every prohibition in this module quantifies over the file
# set `_workflow_files` returns, and
# `TestParserFidelity::test_the_workflow_scan_covers_every_workflow_github_would_run`
# pins that set against the directory's actual contents.
#
# Scanning both extensions is preferred here over prohibiting `.yaml` in the
# directory. A prohibition would encode a repository convention no ADR states,
# and it fails a contributor who has a legitimate reason to use the other
# spelling; scanning makes the guards true of whatever GitHub actually runs.
WORKFLOW_SUFFIXES = frozenset({".yml", ".yaml"})


def _workflow_files() -> list[Path]:
    """Return every workflow file GitHub would execute, sorted by name.

    Single source of the file set for every scan in this module. Three sites
    previously globbed `*.yml` independently, and a `.github/workflows/*.yaml`
    file was therefore invisible to all of them at once — one character defeated
    the D3 prohibition, the D7b prohibition, and both file-list rules.
    """
    return sorted(
        (path for path in _WORKFLOW_DIR.iterdir() if path.is_file() and path.suffix in WORKFLOW_SUFFIXES),
        key=lambda path: path.name,
    )


def _tracked_files() -> list[str]:
    """Return every tracked repo-relative path, sorted.

    Used to resolve script basenames and to expand copied directories into the
    files a `paths:` filter has to name. Tracked rather than on-disk, so build
    artefacts (`__pycache__`) cannot become trigger requirements.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return sorted(entry for entry in result.stdout.split("\0") if entry)


TRACKED_FILES = _tracked_files()
TRACKED_FILE_SET = frozenset(TRACKED_FILES)

# basename -> every tracked path carrying it, for script resolution.
TRACKED_BY_BASENAME: dict[str, list[str]] = {}
for _path in TRACKED_FILES:
    TRACKED_BY_BASENAME.setdefault(Path(_path).name, []).append(_path)


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
        substitutions: (variable name, shell command) pairs for every
            command-substitution assignment seen in the enclosing script, and
            only populated when the parse ran with ``keep_substitutions=True``.
            A command substitution is not statically resolvable, so the default
            parse discards it; the D7a file lists live in exactly such an
            assignment, and pinning them means executing the command rather
            than reading it.
    """

    script: str
    path: str
    argv: tuple[str, ...]
    source: str
    line: str
    substitutions: tuple[tuple[str, str], ...] = ()


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


def _segments_with_operators(tokens: list[str]) -> list[tuple[list[str], str | None]]:
    """Split a token stream into (simple command, following operator) pairs.

    `_split_simple_commands` discards the operators, which is right for asking
    *what ran* and wrong for asking *what happens when it fails*. `cmd || true`
    and `cmd` produce identical segment lists there, and they are the difference
    between a step that fails the job and one that does not.

    The operator returned with a segment is the one that immediately follows it,
    or None at the end of the line.
    """
    pairs: list[tuple[list[str], str | None]] = []
    current: list[str] = []
    for token in tokens:
        for part in (p for p in re.split(r"(;|&&|\|\||\||&)", token) if p):
            if part in _OPERATORS or part.startswith(">") or part.startswith("<"):
                if current:
                    pairs.append((current, part if part in _OPERATORS else None))
                current = []
            else:
                current.append(part)
    if current:
        pairs.append((current, None))
    return pairs


def _shell_operators(text: str) -> list[str]:
    """Return the control operators present in a shell fragment.

    Used to assert that a file-list command substitution is a single simple
    command: `$(resolver || true)` neutralizes the resolver's exit-1-on-empty
    contract, and the only visible trace is the operator.
    """
    found: list[str] = []
    for token in _safe_split(text):
        found.extend(part for part in re.split(r"(;|&&|\|\||\||&)", token) if part in _OPERATORS)
    return found


def _set_options(run_block: str, sign: str) -> list[str]:
    """Return `set` option words in a shell body that use the given sign.

    A substring test for "set -e" is satisfied by the text appearing in a
    comment or an `echo`. This looks for an actual `set` simple command, which
    is what changes the shell's behaviour.
    """
    options: list[str] = []
    for raw_line in run_block.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        for segment in _split_simple_commands(_safe_split(stripped)):
            while segment and (segment[0] in _LEADING_WORDS or _TOKEN_ASSIGN_RE.match(segment[0])):
                segment = segment[1:]
            if segment and segment[0] == "set":
                options.extend(word for word in segment[1:] if word.startswith(sign))
    return options


def _enables_errexit(run_block: str) -> bool:
    """True when the body itself turns on exit-on-error."""
    return any("e" in option for option in _set_options(run_block, "-"))


def _disables_errexit(run_block: str) -> bool:
    """True when the body turns exit-on-error back off."""
    return any("e" in option for option in _set_options(run_block, "+"))


_SUBSTITUTION_RE = re.compile(r"\$\((.*)\)\s*$|`(.*)`\s*$")


def _substitution_command(value: str) -> str:
    """Return the shell command inside a `$(...)` or backtick substitution."""
    match = _SUBSTITUTION_RE.search(value)
    if not match:
        return ""
    return (match.group(1) or match.group(2) or "").strip()


def _python_invocations(script_text: str, source: str, keep_substitutions: bool = False) -> list[Invocation]:
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
        keep_substitutions: When True, a variable assigned from a command
            substitution expands to a literal `${NAME}` placeholder that
            survives into `argv`, and the substitution's command is recorded on
            each Invocation. When False (the default) such a variable expands
            to the empty string and disappears.

            The default is the conservative reading for a *prohibition*: D3 and
            D7b ask whether a forbidden flag or path is present, and inventing
            content for an unresolvable expansion could manufacture a
            violation. It is the wrong reading for a *requirement*: the D7a
            file lists reach the validators through exactly such an expansion,
            so under the default the derived argv for those three invocations is
            just `['--block']` and the file list is invisible. Callers that need
            to establish what CI actually passes set this True and execute the
            recorded command.

    Returns:
        List of Invocation records in the order encountered.
    """
    env: dict[str, Any] = {}
    substitutions: dict[str, str] = {}
    found: list[Invocation] = []

    for raw_line in script_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        assignment = _ASSIGN_RE.match(raw_line)
        if assignment:
            name, value = assignment.group(1), assignment.group(2).strip()
            if "$(" in value or "`" in value:
                # Command substitution is not statically resolvable. Either
                # record the name as known-but-empty so downstream references
                # expand away rather than being left as literal `${VAR}` text,
                # or preserve the reference so a caller can run the command.
                if keep_substitutions:
                    substitutions[name] = _substitution_command(value)
                    # Expanding to itself is a fixed point, so `_expand`'s
                    # bounded loop terminates on the first pass and the
                    # placeholder survives into argv.
                    env[name] = f"${{{name}}}"
                else:
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

            found.append(
                Invocation(
                    Path(script).name,
                    script,
                    tuple(argv),
                    source,
                    stripped,
                    tuple(sorted(substitutions.items())),
                )
            )

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
    for workflow in _workflow_files():
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

    def test_the_workflow_scan_covers_every_workflow_github_would_run(self):
        """
        Given: the contents of .github/workflows/
        When: the file set this module scans is compared to the files GitHub
              would execute out of that directory
        Then: they are equal, and every workflow declaring a `run:` step is
              reached by the step parse

        Every prohibition here quantifies over the scanned set, so a workflow
        outside it is exempt from all of them at once. GitHub honours `.yaml`
        and `.yml` identically; a `.github/workflows/gate.yaml` copying a
        `precommit/` validator to the root, invoking it by bare basename, and
        pairing `--block` with `--to-graph` would violate D3, D7b and both
        file-list rules simultaneously, and a scan restricted to one extension
        sees none of it.

        The second assertion is the one that keeps the first honest. Equality of
        file *lists* proves nothing if a consumer re-globs the directory for
        itself, which is how the three scan sites diverged in the first place;
        comparing the workflows the step parse actually reached against an
        independent re-derivation shows the scanned set is the one in use.
        """
        on_disk = sorted(
            path.name for path in _WORKFLOW_DIR.iterdir() if path.is_file() and path.suffix in WORKFLOW_SUFFIXES
        )
        scanned = sorted(path.name for path in _workflow_files())
        assert scanned == on_disk, (
            f"The workflow scan does not cover every file GitHub would run.\n"
            f"  on disk ({len(on_disk)}): {on_disk}\n"
            f"  scanned ({len(scanned)}): {scanned}\n"
            f"  missed: {sorted(set(on_disk) - set(scanned))}\n"
            f"GitHub executes every {sorted(WORKFLOW_SUFFIXES)} file in this directory; "
            "a workflow outside the scan is exempt from every prohibition in this module."
        )

        # Independent re-derivation of which workflows declare a `run:` step.
        with_run_steps = set()
        for path in _WORKFLOW_DIR.iterdir():
            if not (path.is_file() and path.suffix in WORKFLOW_SUFFIXES):
                continue
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            for job in (data.get("jobs") or {}).values():
                if any(step.get("run") for step in (job.get("steps") or [])):
                    with_run_steps.add(path.name)

        parsed = {step.workflow for step in WORKFLOW_STEPS}
        assert parsed == with_run_steps, (
            f"The step parse reached a different set of workflows than the directory "
            f"contains.\n  parsed: {sorted(parsed)}\n  expected: {sorted(with_run_steps)}\n"
            f"  unreached: {sorted(with_run_steps - parsed)}\n"
            "A consumer that enumerates the directory for itself, rather than through "
            "`_workflow_files`, reintroduces the blind spot the previous assertion closes."
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

        A validator with no enabling arguments is not thereby unconditioned.
        For the three file-argument validators the enabling input is the file
        list: handed none, `validate_yaml_prose_subset.py` and
        `validate_prose_references.py` exit 0 without opening a file. That case
        is asserted here rather than skipped past, and the list's completeness
        is established by TestCIFileListsAreDerivedAndComplete.
        """
        probe = BLOCK_PROBES[script]
        if not probe.enabling_args:
            governed = [
                hook_id for hook_id, hook in FILE_ARGUMENT_BLOCK_HOOKS.items() if _hook_script(hook) == script
            ]
            assert governed, (
                f"{script} declares no enabling arguments and its pre-commit hook passes no "
                f"filenames, so nothing establishes that a CI invocation of it examines any "
                f"input at all. Either the probe needs enabling arguments, or the hook needs "
                f"pass_filenames — as it stands this is a validator that can run, report "
                f"success, and have read nothing."
            )
            # Its enabling input is the derived file list, asserted in section 6.
            return

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
        # Directories are named by loop index, not by a hash of the source.
        # Two invocations in one step share a source label, so a hash-derived
        # name raised FileExistsError and aborted before the second was
        # evaluated; and `hash()` is PYTHONHASHSEED-randomised, so the
        # artefacts a failure leaves behind were not reproducible either.
        for index, invocation in enumerate(candidates):
            clean_dir = tmp_path / f"clean-{index}"
            clean_dir.mkdir()
            probe.write_corpus(clean_dir, False)
            clean = _run_probe(probe, clean_dir, invocation.argv, with_enabling_args=False)
            assert clean.returncode == 0, (
                f"Harness precondition failed: {invocation.source} arguments "
                f"{list(invocation.argv)} exit {clean.returncode} on a CLEAN corpus. "
                f"The poisoned result below would be meaningless.\n"
                f"stdout: {clean.stdout}\nstderr: {clean.stderr}"
            )

            poisoned_dir = tmp_path / f"poisoned-{index}"
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
# 6. D7a — the CI file lists are derived, complete, and actually inspected
# ===========================================================================
#
# The three validators D7 wires take file arguments. Everything about whether
# those jobs check anything is decided by the list that reaches their argv, and
# none of it is visible in the workflow's own output:
#
#   - an empty list is a passing job. `validate_yaml_prose_subset.py` and
#     `validate_prose_references.py` declare `files` with nargs="*" and exit 0
#     on an empty one.
#   - a short list is a passing job that checked part of the corpus, and the
#     part it skipped is indistinguishable from clean.
#   - a `--schema-dir` the validator cannot read is a passing job too: the
#     shared field discovery in `_prose_fields.py` returns silently when it
#     cannot infer or read a schema, so no field is ever visited.
#
# The tests below therefore run the resolver, compare its whole output against
# the hook's own patterns, and then run the real validator with the real
# argument list once per resolved file — poisoning that file and leaving the
# rest clean. A file the command never opens cannot fail, so the only way to
# pass the whole parametrization is for every file in the list to be inspected
# by the arguments CI actually passes.


def _hook_script(hook: dict[str, Any]) -> str | None:
    """Return the basename of the Python script a hook entry runs, if any."""
    for token in _safe_split(str(hook.get("entry") or "")):
        if token.endswith(".py"):
            return Path(token).name
    return None


def _iter_precommit_hooks():
    """Yield every hook mapping declared in .pre-commit-config.yaml."""
    config = yaml.safe_load(_PRECOMMIT_CONFIG.read_text(encoding="utf-8"))
    for repo in config.get("repos", []) or []:
        for hook in repo.get("hooks", []) or []:
            yield hook


# hook-id -> hook, for hooks that carry a strictness flag AND take file
# arguments. `pass_filenames` defaults to true in pre-commit, so an absent key
# counts as true. This is exactly the set for which ADR-037 D7a requires a
# derived CI file list; the self-scanning validators are excluded because they
# need none. Derived, so a fourth such hook is governed on arrival.
FILE_ARGUMENT_BLOCK_HOOKS: dict[str, dict[str, Any]] = {
    str(hook["id"]): hook
    for hook in _iter_precommit_hooks()
    if hook.get("id")
    and hook.get("pass_filenames", True)
    and STRICTNESS_FLAGS.intersection(
        " ".join([str(hook.get("entry") or ""), *(str(a) for a in hook.get("args", []) or [])]).split()
    )
}
FILE_ARGUMENT_BLOCK_HOOK_IDS = sorted(FILE_ARGUMENT_BLOCK_HOOKS)

# Workflow invocations parsed with command substitutions preserved. The default
# parse drops them, which is what makes the D7a file lists invisible.
WORKFLOW_INVOCATIONS_RESOLVABLE: list[Invocation] = []
for _source, _run_block in _iter_workflow_run_steps():
    WORKFLOW_INVOCATIONS_RESOLVABLE.extend(_python_invocations(_run_block, _source, keep_substitutions=True))

# A token that is exactly one variable reference, e.g. `${FILES}`.
_SUBST_TOKEN_RE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")


def _expected_hook_files(hook: dict[str, Any]) -> list[str]:
    """Return the tracked files a hook's own patterns select, derived here.

    Written out rather than imported from the resolver: an expectation computed
    by the code under test cannot detect a mutation to that code. The exact-list
    unit tests live in test_hook_file_list.py; this is the CI-side check that
    the list reaching argv is the same one.
    """
    tracked = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(_REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split("\0")
    include = re.compile(hook["files"])
    exclude = re.compile(hook["exclude"]) if hook.get("exclude") else None
    return sorted(
        path for path in tracked if path and include.search(path) and not (exclude and exclude.search(path))
    )


def _run_substitution(command: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run a workflow command substitution under `bash -e`, as GitHub does.

    GitHub's default shell for a `run:` block is `bash -e {0}`, so a failing
    command substitution in an assignment aborts the step. Reproducing the `-e`
    here keeps the test's notion of "the resolver failed" the same as CI's.
    """
    return subprocess.run(["bash", "-e", "-c", command], cwd=str(cwd), capture_output=True, text=True)


def _resolve_argv(invocation: Invocation) -> tuple[list[str], dict[str, list[str]]]:
    """Expand an invocation's command-substitution placeholders by running them.

    Returns the fully resolved argv and a map of variable name to the tokens it
    produced. Word-splitting is the shell's, reproduced here: the workflow
    expands `${FILES}` unquoted.
    """
    commands = dict(invocation.substitutions)
    produced: dict[str, list[str]] = {}
    argv: list[str] = []

    for token in invocation.argv:
        match = _SUBST_TOKEN_RE.match(token)
        if not (match and match.group(1) in commands):
            argv.append(token)
            continue
        name = match.group(1)
        if name not in produced:
            result = _run_substitution(commands[name], _REPO_ROOT)
            if result.returncode != 0:
                pytest.fail(
                    f"{invocation.source}: the command building {name} exited "
                    f"{result.returncode}, so the step aborts under `bash -e` and the "
                    f"validator never runs.\n  command: {commands[name]}\n"
                    f"  stdout: {result.stdout!r}\n  stderr: {result.stderr!r}"
                )
            produced[name] = result.stdout.split()
        argv.extend(produced[name])

    return argv, produced


# --- per-file corpus writers ------------------------------------------------
#
# The CI invocations run the validators in place (D7b), so the prose linters
# discover fields through the repository's real schemas. The poison must
# therefore land in a field those schemas actually mark as prose, one per
# entity file. A file whose stem is absent from these maps fails loudly rather
# than being written with a field nothing reads — a corpus the validator has no
# opinion about would make the "is it inspected" test pass vacuously.

_PROSE_FIELD_BY_STEM = {
    "components": "description",
    "controls": "description",
    "personas": "description",
    "risks": "shortDescription",
}

_PROBE_ID_BY_STEM = {
    "components": "componentProbe",
    "controls": "controlProbe",
    "personas": "personaProbe",
    "risks": "riskProbe",
}


def _write_prose_entity(base: Path, rel_path: str, text: str) -> None:
    """Write a one-entry YAML file at rel_path with `text` in its prose field."""
    stem = Path(rel_path).stem
    if stem not in _PROSE_FIELD_BY_STEM:
        pytest.fail(
            f"No prose field is known for {rel_path!r}. The hook's file list now covers "
            f"an entity this probe cannot poison, so the file would be written with no "
            f"field the validator reads and would pass whether or not it was inspected. "
            f"Add {stem!r} to _PROSE_FIELD_BY_STEM / _PROBE_ID_BY_STEM."
        )
    target = base / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    entry = {"id": _PROBE_ID_BY_STEM[stem], "title": "Probe", _PROSE_FIELD_BY_STEM[stem]: [text]}
    target.write_text(yaml.dump({stem: [entry]}), encoding="utf-8")


def _write_prose_subset_file(base: Path, rel_path: str, poisoned: bool) -> None:
    """Poison = inline URL in prose (ADR-017 D4)."""
    _write_prose_entity(
        base, rel_path, "See https://example.com for details." if poisoned else "Clean prose here."
    )


def _write_prose_references_file(base: Path, rel_path: str, poisoned: bool) -> None:
    """Poison = an intra-doc sentinel naming an id that does not exist (ADR-016 D6)."""
    _write_prose_entity(
        base, rel_path, "The {{riskProbeDoesNotExist}} applies here." if poisoned else "Clean prose here."
    )


def _write_identification_file(base: Path, rel_path: str, poisoned: bool) -> None:
    """Poison = a live persona with no identificationQuestions block (Rule 0)."""
    if Path(rel_path).stem != "personas":
        pytest.fail(
            f"The identification-questions hook now selects {rel_path!r}, which this "
            "probe cannot poison. Extend the writer before relying on the result."
        )
    persona: dict[str, Any] = {
        "id": "personaProbe",
        "title": "Probe Persona",
        "description": ["A probe persona."],
    }
    if not poisoned:
        persona["identificationQuestions"] = list(_CLEAN_IDENTIFICATION_QUESTIONS)
    target = base / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.dump({"personas": [persona]}), encoding="utf-8")


# script basename -> writer(base_dir, repo_relative_path, poisoned)
FILE_LIST_PROBES: dict[str, Callable[[Path, str, bool], None]] = {
    "validate_identification_questions.py": _write_identification_file,
    "validate_yaml_prose_subset.py": _write_prose_subset_file,
    "validate_prose_references.py": _write_prose_references_file,
}


def _file_list_candidates(hook_id: str) -> list[Invocation]:
    """Return every non-graph-emitting CI invocation of a hook's validator."""
    script = _hook_script(FILE_ARGUMENT_BLOCK_HOOKS[hook_id])
    return [inv for inv in WORKFLOW_INVOCATIONS_RESOLVABLE if inv.script == script and not _is_graph_emitting(inv)]


def _file_list_commands(invocation: Invocation) -> list[tuple[str, str]]:
    """Return the (variable, command) substitutions an invocation's argv consumes.

    Only substitutions actually referenced in argv count. A step may assign
    several; the ones that decide what the validator reads are the ones that
    reach the command line.
    """
    available = dict(invocation.substitutions)
    referenced = [
        match.group(1)
        for token in invocation.argv
        if (match := _SUBST_TOKEN_RE.match(token)) and match.group(1) in available
    ]
    return [(name, available[name]) for name in referenced]


def _invocation_names_hook(invocation: Invocation, hook_id: str) -> bool:
    """True when an invocation's own file-list command names the given hook id.

    This is what ties a CI invocation to *one* hook rather than to a validator.
    Two hooks can share a validator, and the file lists they select differ.
    """
    return any(hook_id in _safe_split(command) for _, command in _file_list_commands(invocation))


def _file_list_invocation(hook_id: str) -> Invocation:
    """Return the CI invocation belonging to a hook, failing if it is not unique.

    Selecting `candidates[0]` conflated two distinct failures. A second,
    vacuous invocation of the same validator was accepted in silence, because
    the first candidate still satisfied everything; and a second *real* hook on
    an existing validator produced a false positive against whichever invocation
    sorted first, reported as a fault in the file list rather than as an
    ambiguity in the join.

    Resolution is therefore by hook id — the invocation whose own file-list
    command names this hook — and falls back to the validator-level match only
    when no candidate names any hook, which is the shape
    test_ci_invocation_takes_its_file_list_from_a_command exists to report.
    """
    script = _hook_script(FILE_ARGUMENT_BLOCK_HOOKS[hook_id])
    candidates = _file_list_candidates(hook_id)
    if not candidates:
        pytest.fail(
            f"No workflow invokes {script} (hook {hook_id!r}). "
            "TestStrictnessCoverage reports the coverage gap; this class cannot "
            "establish anything about a command that does not exist."
        )

    named = [inv for inv in candidates if _invocation_names_hook(inv, hook_id)]
    chosen = named or candidates
    if len(chosen) != 1:
        pytest.fail(
            f"{hook_id}: {len(chosen)} CI invocations of {script} match this hook, so "
            f"there is no single command whose file list can be checked against it.\n"
            + "\n".join(f"  - {inv.source}: {inv.line}  (argv={list(inv.argv)})" for inv in chosen)
            + "\nADR-037 D7 requires a failure to resolve to a single validator; that "
            "holds only while each governed hook has one invocation. Picking the first "
            "would test one command and leave the others uninspected."
        )
    return chosen[0]


class TestCIFileListsAreDerivedAndComplete:
    """ADR-037 D7a: the file list CI passes is the hook's, whole, and read.

    Three separate claims, because each fails silently on its own:

      1. the list is *derived* — it comes from a command evaluated at run time,
         not from paths transcribed into workflow YAML, which drift in the
         permissive direction;
      2. the list is *complete* — it equals the hook's own file set, not a
         prefix of it;
      3. the list is *read* — the argument list CI passes actually causes every
         file in it to be inspected.

    Claim 3 is the one that cannot be faked. It runs the real validator with the
    real argument list, once per resolved file, against a corpus where only that
    file carries a violation. A stripped file list, a truncated resolver, or a
    `--schema-dir` the validator cannot read all produce the same observable
    result — a file that was not checked — and all three fail here.
    """

    def test_file_argument_block_hooks_are_derived_and_present(self):
        """
        Given: .pre-commit-config.yaml as committed
        When: hooks carrying a strictness flag and passing filenames are derived
        Then: at least one is found

        Every test below is parametrized over this set. A zero result collects
        no cases, which pytest reports as success.
        """
        assert FILE_ARGUMENT_BLOCK_HOOK_IDS, (
            "Parsed no strictness-flagged file-argument hooks out of "
            f"{_PRECOMMIT_CONFIG}. ADR-037 D7 names three; finding none means the "
            "derivation stopped seeing them, which makes this whole class vacuous."
        )

    def test_every_file_argument_block_hook_has_a_corpus_probe(self):
        """
        Given: the derived set of file-argument strictness hooks
        When: compared against the per-file corpus writers
        Then: every one has a writer, and no writer is orphaned

        The same derive-don't-enumerate rule the D4 tier applies. A fourth hook
        of this shape fails here until someone can express a violation in its
        files, rather than being quietly excluded from the strongest assertion
        in the module.
        """
        scripts = {_hook_script(hook) for hook in FILE_ARGUMENT_BLOCK_HOOKS.values()}
        unprobed = sorted(name for name in scripts if name not in FILE_LIST_PROBES)
        assert not unprobed, (
            f"No per-file corpus writer for {unprobed}. Without one, the file list "
            "for that hook can be checked for length but not for effect, and a "
            "list that is present but never read looks identical to a correct one."
        )
        stale = sorted(set(FILE_LIST_PROBES) - {name for name in scripts if name})
        assert not stale, f"Corpus writers exist for validators no longer governed by D7a: {stale}."

    @pytest.mark.parametrize("hook_id", FILE_ARGUMENT_BLOCK_HOOK_IDS)
    def test_ci_invocation_takes_its_file_list_from_a_command(self, hook_id):
        """
        Given: the CI invocation of a file-argument strictness-flagged validator
        When: its argv is inspected for a command-substitution reference
        Then: one is present, and the command it names is recorded

        ADR-037 D7a forbids transcribing the file list into workflow YAML: a
        transcribed list drifts in the permissive direction, because a file the
        hook covers and the workflow omits is unchecked in CI while appearing
        checked.

        This also fails if the expansion is simply dropped from the command
        line. That edit leaves the job green for two of the three validators —
        `nargs="*"` plus an immediate `exit 0` on no files — and the workflow
        prints its success message either way.
        """
        invocation = _file_list_invocation(hook_id)
        referenced = _file_list_commands(invocation)
        assert referenced, (
            f"{hook_id}: the CI invocation passes no command-derived file list.\n"
            f"  {invocation.source}: {invocation.line}\n"
            f"  argv: {list(invocation.argv)}\n"
            f"  command substitutions available in the step: "
            f"{[name for name, _ in invocation.substitutions] or 'none'}\n"
            "ADR-037 D7a requires the file set to be derived from the hook's own "
            "`files:` pattern at run time. With no file list this validator "
            "inspects nothing and still exits 0."
        )

    @pytest.mark.parametrize("hook_id", FILE_ARGUMENT_BLOCK_HOOK_IDS)
    def test_ci_file_list_command_resolves_this_hook_from_the_precommit_config(self, hook_id):
        """
        Given: the command CI uses to build a hook's file list
        When: the command itself is parsed
        Then: it runs a Python script that reads `.pre-commit-config.yaml`, and
              passes this hook's own id as an argument

        "Derived, not transcribed" is a claim about where the list comes from,
        and the previous assertion only established that it comes from *a*
        command substitution. `FILES=$(cat .github/prose-files.txt)` satisfies
        that: it is a command, it produces a list, and it is a hand-maintained
        file that drifts from the hook in exactly the permissive direction
        ADR-037 D7a names — a file the hook covers and the list omits is
        unchecked in CI while appearing checked.

        The resolver is identified by what it reads rather than by its filename,
        so renaming or replacing it does not require an edit here; substituting
        something that never opens the hook config does.

        The command must also be a single simple command. `$(resolver || true)`
        parses and runs, and it discards the resolver's non-zero exit on an
        empty match — the assertion `test_hook_file_list.py` calls the most
        important one it makes. Nothing else notices until the match actually
        goes empty, at which point the job is green and has read nothing.
        """
        invocation = _file_list_invocation(hook_id)
        commands = _file_list_commands(invocation)
        assert commands, (
            f"{hook_id}: no command substitution reaches this invocation's argv; "
            "test_ci_invocation_takes_its_file_list_from_a_command explains the gap."
        )

        for name, command in commands:
            operators = _shell_operators(command)
            assert not operators, (
                f"{hook_id}: the file-list command for {name} is not a single simple "
                f"command — it contains {operators}.\n  command: {command}\n"
                "A trailing `|| true` (or `; true`, or a pipe) discards the resolver's "
                "exit status, so an empty or failed match becomes an empty variable and "
                "a passing job instead of an aborted step."
            )

            inner = _python_invocations(command, f"{invocation.source} [{name}]")
            assert len(inner) == 1, (
                f"{hook_id}: the file-list command for {name} does not run exactly one "
                f"Python script.\n  command: {command}\n  parsed: {[i.script for i in inner]}\n"
                "ADR-037 D7a requires the list to be derived from the hook's own "
                "`files:` pattern at run time. A `cat` of a checked-in list, or a "
                "chain of commands, is a transcription with a command substitution "
                "wrapped around it."
            )

            resolved, _ = _real_script_path(inner[0].script)
            assert resolved and _reads_precommit_config(resolved), (
                f"{hook_id}: the file-list command for {name} runs "
                f"{inner[0].script!r}, which does not read {_PRECOMMIT_CONFIG.name}.\n"
                f"  command: {command}\n"
                "The list has to come from the hook's own patterns. A script that never "
                "opens the pre-commit config cannot be reproducing them."
            )
            assert hook_id in _safe_split(command), (
                f"{hook_id}: the file-list command for {name} does not name this hook.\n"
                f"  command: {command}\n"
                "Without the hook id the list belongs to some other hook's patterns, "
                "and the two drift independently."
            )

    @pytest.mark.parametrize("hook_id", FILE_ARGUMENT_BLOCK_HOOK_IDS)
    def test_each_governed_hook_has_exactly_one_ci_invocation(self, hook_id):
        """
        Given: every non-graph-emitting CI invocation of a governed hook's
               validator
        When: they are attributed to the hooks their file-list commands name
        Then: exactly one belongs to this hook, and none belongs to no hook

        Two failures share this shape and neither was visible before.

        A *second, vacuous* invocation of the same validator — one passing no
        file list, or a stale list — adds no failure anywhere else: the tests
        below resolve one invocation and check it, and the extra command runs in
        CI unexamined. ADR-037 D7's attribution constraint is the rule this
        serves: a failure must resolve to a single validator, which holds only
        while each governed hook has one command.

        A second *real* hook on an existing validator produces the opposite
        error — a confident failure against whichever invocation happened to
        sort first, reported as a broken file list rather than as an ambiguity.
        """
        script = _hook_script(FILE_ARGUMENT_BLOCK_HOOKS[hook_id])
        candidates = _file_list_candidates(hook_id)
        assert candidates, (
            f"No workflow invokes {script} (hook {hook_id!r}); "
            "TestStrictnessCoverage reports that as the D1 coverage gap."
        )

        attribution = [
            (inv, sorted(other for other in FILE_ARGUMENT_BLOCK_HOOK_IDS if _invocation_names_hook(inv, other)))
            for inv in candidates
        ]
        unattributed = [inv for inv, hooks in attribution if not hooks]
        assert not unattributed, (
            f"{script}: these CI invocations name no governed hook, so nothing "
            f"establishes which file set they are supposed to cover:\n"
            + "\n".join(f"  - {inv.source}: {inv.line}" for inv in unattributed)
            + "\nAn invocation of a --block validator that no hook accounts for either "
            "duplicates a gate (and runs unexamined) or replaces one with a list this "
            "suite never compares against a hook's patterns."
        )

        mine = [inv for inv, hooks in attribution if hook_id in hooks]
        assert len(mine) == 1, (
            f"{hook_id}: expected exactly one CI invocation of {script} for this hook, "
            f"found {len(mine)}:\n"
            + "\n".join(f"  - {inv.source}: {inv.line}  (argv={list(inv.argv)})" for inv in mine)
            + "\nAll non-graph-emitting invocations of this validator:\n"
            + "\n".join(f"  - {inv.source}: {inv.line}  -> hooks {hooks}" for inv, hooks in attribution)
        )

    @pytest.mark.parametrize("hook_id", FILE_ARGUMENT_BLOCK_HOOK_IDS)
    def test_derived_file_list_equals_the_hook_file_set(self, hook_id):
        """
        Given: the command CI uses to build the file list
        When: it is executed against the real repository
        Then: its output equals, whole, the files the hook's patterns select

        Equality, not containment. A resolver returning the first element of its
        match produces a green job that checked one file out of four, and every
        weaker assertion — non-empty, is-a-subset, has-at-least-one — passes it.
        """
        hook = FILE_ARGUMENT_BLOCK_HOOKS[hook_id]
        invocation = _file_list_invocation(hook_id)
        _, produced = _resolve_argv(invocation)

        assert produced, (
            f"{hook_id}: no command substitution was expanded for this invocation, so "
            "there is no file list to compare. "
            "test_ci_invocation_takes_its_file_list_from_a_command explains the gap."
        )
        actual = sorted(token for tokens in produced.values() for token in tokens)
        expected = _expected_hook_files(hook)

        assert actual == expected, (
            f"{hook_id}: the file list CI builds is not the file set the hook sees.\n"
            f"  files:   {hook.get('files')!r}\n"
            f"  exclude: {hook.get('exclude')!r}\n"
            f"  hook sees ({len(expected)}): {expected}\n"
            f"  CI passes ({len(actual)}): {actual}\n"
            f"  missing from CI: {sorted(set(expected) - set(actual))}\n"
            f"  extra in CI: {sorted(set(actual) - set(expected))}\n"
            "A file the hook covers and CI omits is unchecked while appearing checked."
        )

    @pytest.mark.parametrize("hook_id", FILE_ARGUMENT_BLOCK_HOOK_IDS)
    def test_every_file_in_the_derived_list_is_inspected(self, hook_id, tmp_path):
        """
        Given: the exact argument list CI passes, with its file list resolved
        When: the validator runs once per resolved file, against a corpus where
              only that file carries a violation
        Then: every run exits non-zero and names the poisoned file

        The behavioural claim the rest of the class supports. It asserts nothing
        about the workflow's text: it observes that each file CI names is a file
        whose contents can fail the build.

        One edit fails here and nowhere else in the suite: a `--schema-dir` the
        validator cannot read. Field discovery in `_prose_fields.py` returns
        silently on a schema it cannot infer or open, so no prose is visited,
        while the file list stays complete and every string in the workflow
        stays correct. Argparse store actions are last-wins, which is why this
        test runs the workflow's arguments as written rather than appending its
        own.

        Two further edits fail here *and* elsewhere, and it is worth being exact
        about which, because a maintainer trimming this suite needs to know
        which test is load-bearing for what:

          - dropping the file-list expansion from the command line. Both prose
            validators declare `files` with nargs="*" and exit 0 on an empty
            one, so the job stays green. Also caught by
            test_ci_invocation_takes_its_file_list_from_a_command.
          - a resolver that returns a prefix of its match. This test does *not*
            catch a truncation to `[:1]`: the surviving file is genuinely
            inspected, so its poisoned run fails as expected and the shortened
            list is never compared to anything here.
            test_derived_file_list_equals_the_hook_file_set is what fails on a
            short list, together with the exact-list assertions in
            test_hook_file_list.py. Truncation to a *prefix of length > 1* does
            fail here, for the files past the cut.

        The all-clean run is asserted first. Without it a validator that failed
        on everything would satisfy every poisoned assertion for the wrong
        reason.
        """
        hook = FILE_ARGUMENT_BLOCK_HOOKS[hook_id]
        script = _hook_script(hook)
        write_file = FILE_LIST_PROBES[script]
        real_path = _REPO_ROOT / PRECOMMIT_VALIDATORS[script]
        invocation = _file_list_invocation(hook_id)
        argv, produced = _resolve_argv(invocation)
        files = [token for tokens in produced.values() for token in tokens]

        assert files, (
            f"{hook_id}: the resolved file list is empty, so there is nothing to "
            f"inspect and the command below cannot fail on any content.\n"
            f"  {invocation.source}: {invocation.line}\n"
            f"  resolved argv: {argv}"
        )

        def run(base: Path) -> subprocess.CompletedProcess:
            # The validator runs from its real path (D7b) so its Path(__file__)
            # derivations resolve against the repository, exactly as in CI; cwd
            # is the temporary corpus so the repo-relative file arguments land
            # inside it rather than on the live YAML.
            return subprocess.run(
                [sys.executable, str(real_path), *argv],
                capture_output=True,
                text=True,
                cwd=str(base),
            )

        clean_dir = tmp_path / "clean"
        for path in files:
            write_file(clean_dir, path, False)
        clean = run(clean_dir)
        assert clean.returncode == 0, (
            f"Harness precondition failed: {hook_id}'s CI arguments exit "
            f"{clean.returncode} on a corpus with no injected violation, so the "
            f"poisoned results below would prove nothing.\n"
            f"  argv: {argv}\n  stdout: {clean.stdout}\n  stderr: {clean.stderr}"
        )

        unchecked: list[str] = []
        for index, target in enumerate(files):
            poisoned_dir = tmp_path / f"poisoned-{index}"
            for path in files:
                write_file(poisoned_dir, path, path == target)
            result = run(poisoned_dir)
            output = result.stdout + result.stderr
            if result.returncode == 0 or target not in output:
                unchecked.append(
                    f"  - {target}: exit {result.returncode}, "
                    f"{'named' if target in output else 'NOT named'} in output"
                )

        assert not unchecked, (
            f"{hook_id}: the command CI runs does not catch a violation in every file "
            f"of its own file list. Those files are in the argument list and are not "
            f"being inspected, so their contents can reach main unopposed while the job "
            f"reports success.\n"
            f"  {invocation.source}: {invocation.line}\n"
            f"  argv: {argv}\n" + "\n".join(unchecked)
        )


# ===========================================================================
# 7. The gate step's own execution context
# ===========================================================================
#
# Two properties of the *step*, rather than of the command, decide whether a
# derived file list means anything.
#
#   Working directory. The resolver enumerates the corpus with `git ls-files`
#   in its working directory and reads `.pre-commit-config.yaml` relative to it,
#   and the paths it emits are repo-root-relative. All three assume the step
#   runs at the repository root. GitHub supplies that by default; nothing in the
#   workflow states it, and a `working-directory:` key or a `cd` would change it
#   without touching a flag.
#
#   Shell. `FILES=$(...)` only aborts the step when the shell exits on error.
#   Under GitHub's default `bash -e {0}` it does, which is the entire mechanism
#   by which the resolver's non-zero exit on an empty match becomes a red job.
#   A shell without `-e` converts that into an empty variable and a green job.


class WorkflowStep(NamedTuple):
    """One `run:` step with the context GitHub would execute it in.

    Attributes:
        workflow: Workflow filename.
        job: Job id.
        label: Step name, or a positional fallback.
        run: The shell body.
        shell: Effective `shell:`, after workflow and job `defaults.run`.
        working_directory: Effective `working-directory:`, same resolution.
        source: Human-readable origin for assertion messages.
        continue_on_error: The step's own `continue-on-error:`, or None.
        condition: The step's own `if:`, or None.
        job_continue_on_error: The enclosing job's `continue-on-error:`, or None.
        job_condition: The enclosing job's `if:`, or None.

    The last four decide whether this step's exit code reaches the job's
    conclusion at all. None of them appears anywhere on a command line, so a
    scan of `run:` bodies cannot see any of them.
    """

    workflow: str
    job: str
    label: str
    run: str
    shell: str | None
    working_directory: str | None
    source: str
    continue_on_error: Any = None
    condition: Any = None
    job_continue_on_error: Any = None
    job_condition: Any = None


def _iter_workflow_steps() -> list[WorkflowStep]:
    """Return every `run:` step across all workflows, with defaults resolved.

    `defaults.run` may be set at workflow and job level; the step's own keys win
    over both. Reproducing that here matters because a `working-directory:`
    declared once at job level silently moves every step in the job.
    """
    steps: list[WorkflowStep] = []
    for workflow in _workflow_files():
        data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
        workflow_defaults = ((data.get("defaults") or {}).get("run") or {}) if isinstance(data, dict) else {}
        for job_id, job in (data.get("jobs") or {}).items():
            job_defaults = (job.get("defaults") or {}).get("run") or {}
            for index, step in enumerate(job.get("steps") or []):
                run_block = step.get("run")
                if not run_block:
                    continue
                label = step.get("name") or f"step[{index}]"
                shell = step.get("shell", job_defaults.get("shell", workflow_defaults.get("shell")))
                working_directory = step.get(
                    "working-directory",
                    job_defaults.get("working-directory", workflow_defaults.get("working-directory")),
                )
                steps.append(
                    WorkflowStep(
                        workflow=workflow.name,
                        job=str(job_id),
                        label=label,
                        run=run_block,
                        shell=shell,
                        working_directory=working_directory,
                        source=f"{workflow.name}::{job_id}::{label}",
                        continue_on_error=step.get("continue-on-error"),
                        condition=step.get("if"),
                        job_continue_on_error=job.get("continue-on-error"),
                        job_condition=job.get("if"),
                    )
                )
    return steps


WORKFLOW_STEPS = _iter_workflow_steps()

# Values of `working-directory:` that are the repository root. GitHub's default
# when the key is absent is $GITHUB_WORKSPACE, which is the checkout root.
_ROOT_WORKING_DIRECTORIES = frozenset(
    {".", "./", "${{ github.workspace }}", "$GITHUB_WORKSPACE", "${GITHUB_WORKSPACE}"}
)

# Shells that exit on error. GitHub maps `bash` to
# `bash --noprofile --norc -eo pipefail {0}` and the default (no key) to
# `bash -e {0}`; both abort on a failing command substitution in an assignment.
_ABORTING_SHELLS = frozenset({"bash"})


def _gate_steps() -> list[WorkflowStep]:
    """Return steps that invoke a validator carrying a strictness flag.

    Derived from the command line rather than from job names, so a gate moved
    into another job or workflow stays governed.
    """
    gates: list[WorkflowStep] = []
    for step in WORKFLOW_STEPS:
        invocations = _python_invocations(step.run, step.source, keep_substitutions=True)
        if any(STRICTNESS_FLAGS.intersection(inv.argv) for inv in invocations):
            gates.append(step)
    return gates


GATE_STEPS = _gate_steps()


class TestGateStepsRunFromRepositoryRoot:
    """Every D1 gate step runs at the repository root, in a shell that aborts.

    Both are guards on the step rather than the command, and both are currently
    satisfied by GitHub's defaults rather than by anything the workflow says.
    That is precisely why they need pinning: an edit that changes either leaves
    the command line untouched, so every other test in this module keeps
    passing while the gate stops gating.

    The two behavioural tests at the end establish that the properties being
    pinned are load-bearing — that the file list really does change with the
    working directory, and that `bash -e` really does abort on a failing
    substitution. Without them these would be prohibitions on things that might
    not matter.
    """

    def test_gate_steps_are_found(self):
        """
        Given: every `run:` step in every workflow
        When: steps invoking a strictness-flagged validator are selected
        Then: at least one is found

        Non-vacuity guard: the prohibitions below quantify over this set.
        """
        assert GATE_STEPS, (
            "Found no workflow step invoking a validator with "
            f"{sorted(STRICTNESS_FLAGS)}. Either ADR-037 D1's coverage regressed "
            "entirely, or step parsing did — the second passes every prohibition "
            "in this class by having nothing to prohibit."
        )

    def test_no_gate_step_declares_a_non_root_working_directory(self):
        """
        Given: every gate step, with workflow- and job-level defaults resolved
        When: its effective `working-directory:` is inspected
        Then: it is absent or names the repository root

        The file-list resolver runs `git ls-files` in the step's working
        directory, reads `.pre-commit-config.yaml` relative to it, and emits
        repo-root-relative paths that the validator then opens relative to it.
        A `working-directory:` anywhere in the job breaks all three at once,
        and nothing in the command line changes.
        """
        violations = [
            step
            for step in GATE_STEPS
            if step.working_directory is not None
            and step.working_directory.strip() not in _ROOT_WORKING_DIRECTORIES
        ]
        assert not violations, (
            "Gate steps must run at the repository root:\n"
            + "\n".join(f"  - {step.source}: working-directory: {step.working_directory!r}" for step in violations)
            + "\nThe derived file list, the config it comes from, and the paths it "
            "names are all resolved relative to the working directory."
        )

    def test_no_gate_step_changes_directory(self):
        """
        Given: every gate step's shell body
        When: simple commands are scanned for `cd`
        Then: none is present

        The same hazard as the previous test by a different spelling, and the
        one a `working-directory:` check alone would miss. A `cd` mid-block
        moves every command after it.
        """
        violations: list[tuple[str, str]] = []
        for step in GATE_STEPS:
            for raw_line in step.run.splitlines():
                stripped = raw_line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                for segment in _split_simple_commands(_safe_split(stripped)):
                    while segment and (segment[0] in _LEADING_WORDS or _TOKEN_ASSIGN_RE.match(segment[0])):
                        segment = segment[1:]
                    if segment and segment[0] == "cd":
                        violations.append((step.source, stripped))
        assert not violations, (
            "Gate steps must not change working directory:\n"
            + "\n".join(f"  - {source}: {line}" for source, line in violations)
            + "\nEvery path in these steps — the pre-commit config, the tracked corpus, "
            "and the file arguments themselves — is resolved relative to it."
        )

    def test_gate_steps_use_a_shell_that_aborts_on_error(self):
        """
        Given: every gate step's effective `shell:`
        When: it is checked for exit-on-error behaviour
        Then: it is GitHub's default or `bash`, or the body sets `-e` itself

        `FILES=$(resolver)` carries the resolver's exit status. Under a shell
        without `-e` a failed resolution leaves `FILES` empty and execution
        continues to the validator, which — for the two `nargs="*"` validators —
        exits 0 immediately. The resolver's careful non-zero exit on an empty
        match then buys nothing.

        `set -e` in the body counts, but only as a command. A substring test
        would be satisfied by the same three characters inside a comment or an
        `echo`, which change nothing; `_enables_errexit` looks for a real `set`
        simple command. `set +e` anywhere in a gate body is a violation on its
        own, whatever the declared shell, because it undoes the property the
        rest of this class depends on.
        """
        violations = [
            step
            for step in GATE_STEPS
            if step.shell is not None and step.shell not in _ABORTING_SHELLS and not _enables_errexit(step.run)
        ]
        assert not violations, (
            "Gate steps must run under a shell that exits on error:\n"
            + "\n".join(f"  - {step.source}: shell: {step.shell!r}" for step in violations)
            + "\nOtherwise a failing file-list resolution becomes an empty variable and "
            "a green job instead of a failed step."
        )

        disabled = [step for step in GATE_STEPS if _disables_errexit(step.run)]
        assert not disabled, (
            "Gate steps must not turn exit-on-error back off:\n"
            + "\n".join(f"  - {step.source}" for step in disabled)
            + "\n`set +e` restores the failure mode the declared shell was chosen to "
            "prevent, and leaves every command line in the step untouched."
        )

    def test_the_derived_file_list_depends_on_the_working_directory(self):
        """
        Given: a gate step's file-list command
        When: it is run from the repository root and from a subdirectory
        Then: the two results differ

        Fidelity check for the two working-directory prohibitions above. They
        pass today by GitHub's default; this establishes that the default is
        load-bearing rather than incidental, so a future reader cannot conclude
        the prohibitions are guarding nothing.
        """
        commands = sorted({command for step in GATE_STEPS for _, command in _step_substitutions(step) if command})
        if not commands:
            pytest.fail(
                "No gate step builds a file list from a command, so this fidelity "
                "check has nothing to run. "
                "TestCIFileListsAreDerivedAndComplete reports that as the D7a gap."
            )

        subdirectory = _REPO_ROOT / "scripts"
        insensitive: list[str] = []
        for command in commands:
            from_root = _run_substitution(command, _REPO_ROOT)
            from_subdirectory = _run_substitution(command, subdirectory)
            if (from_root.returncode, from_root.stdout) == (
                from_subdirectory.returncode,
                from_subdirectory.stdout,
            ):
                insensitive.append(command)

        assert not insensitive, (
            "These file-list commands return the same result from a subdirectory as "
            f"from the repository root: {insensitive}. The working-directory "
            "prohibitions above would then be guarding a hazard that no longer exists "
            "— re-derive them before deleting them."
        )

    def test_a_failing_file_list_aborts_the_step_shell(self):
        """
        Given: GitHub's default shell behaviour, reproduced with `bash -e`
        When: an assignment's command substitution exits non-zero
        Then: the shell aborts before the next command

        PLATFORM ASSERTION. Unlike everything else in this module it reads no
        repository state: it pins a property of `bash`, not of this repository,
        and no edit to a workflow, a validator, or the resolver can make it
        fail. It stays because the rest of the class reasons from it — the
        resolver's non-zero exit on an empty match is only a gate if the shell
        acts on it — and because a future move to a shell without `-e` should
        break something visible. Read a failure here as "the platform changed",
        never as "the repository regressed".
        """
        result = subprocess.run(
            ["bash", "-e", "-c", "FILES=$(exit 3)\necho reached"],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0, (
            "A failing command substitution in an assignment did not abort `bash -e`. "
            "The resolver's exit-1-on-empty-match contract then has no effect on the "
            f"job's result.\nstdout: {result.stdout!r}"
        )
        assert "reached" not in result.stdout, (
            "Execution continued past the failed assignment, so the validator would "
            f"run with an empty file list.\nstdout: {result.stdout!r}"
        )


def _step_substitutions(step: WorkflowStep) -> list[tuple[str, str]]:
    """Return (variable, command) pairs for command substitutions a step's validator uses."""
    pairs: list[tuple[str, str]] = []
    for invocation in _python_invocations(step.run, step.source, keep_substitutions=True):
        referenced = {match.group(1) for token in invocation.argv if (match := _SUBST_TOKEN_RE.match(token))}
        pairs.extend((name, command) for name, command in invocation.substitutions if name in referenced)
    return pairs


# ===========================================================================
# 8. Trigger coverage — the gate has to run to be a gate
# ===========================================================================
#
# ADR-037 D1 makes CI the authoritative gate. A workflow that does not run on a
# pull request is not a gate on that pull request, and `paths:` filters decide
# which pull requests it runs on. Two consequences, both of which are edits
# nothing else in this suite can see:
#
#   - a gate workflow that does not trigger on its own definition, or on the
#     validators it runs, does not re-run when either changes. The pull request
#     that removes a `--block` is then merged without the gate it removed ever
#     executing.
#   - the workflow that runs pytest is where every standing guard in this module
#     lives. If it does not trigger on the files those guards assert over, the
#     guards do not run on the pull requests that edit them.


def _workflow_data(name: str) -> dict[str, Any]:
    """Return a parsed workflow by filename."""
    return yaml.safe_load((_WORKFLOW_DIR / name).read_text(encoding="utf-8"))


class TriggerFilter(NamedTuple):
    """One event's path filter, in whichever of the two spellings it uses.

    Attributes:
        event: Event name (`pull_request`, `push`, ...).
        kind: `"paths"` (the path must match to trigger) or `"paths-ignore"`
            (the path must NOT match to trigger).
        patterns: The declared pattern list.
    """

    event: str
    kind: str
    patterns: list[str]


def _trigger_filters(data: dict[str, Any]) -> list[TriggerFilter]:
    """Return the path filters a parsed workflow declares, per event.

    YAML 1.1 reads a bare `on:` key as the boolean True, which PyYAML preserves,
    so both spellings are looked up. Events with neither filter are omitted:
    they run unconditionally and cannot be the cause of a missed trigger.

    `paths-ignore` is modelled rather than ignored. It is the exact complement
    of `paths` — GitHub forbids declaring both on one event — and a workflow
    switching to it would make every trigger assertion here pass vacuously,
    because a filter keyed only on `paths` comes back empty and an empty filter
    set reads as "runs unconditionally".
    """
    triggers = data.get("on", data.get(True))
    if not isinstance(triggers, dict):
        return []
    filters: list[TriggerFilter] = []
    for event, config in triggers.items():
        if not isinstance(config, dict):
            continue
        if config.get("paths"):
            filters.append(TriggerFilter(str(event), "paths", list(config["paths"])))
        elif config.get("paths-ignore"):
            filters.append(TriggerFilter(str(event), "paths-ignore", list(config["paths-ignore"])))
    return filters


def _glob_to_regex(pattern: str) -> re.Pattern:
    """Translate a GitHub `paths:` filter pattern to a regex.

    Approximates the documented semantics: `*` matches within a path segment,
    `**` matches across segments, `?` matches one non-separator character. The
    `/**/` form matches zero or more intervening segments, so
    `.github/workflows/**/*.yml` matches a file directly under `workflows/`.
    """
    out: list[str] = []
    index = 0
    while index < len(pattern):
        if pattern.startswith("/**/", index):
            out.append("(?:/.*)?/")
            index += 4
        elif pattern.startswith("**/", index) and index == 0:
            out.append("(?:.*/)?")
            index += 3
        elif pattern.startswith("/**", index) and index + 3 == len(pattern):
            out.append("/.*")
            index += 3
        elif pattern.startswith("**", index):
            out.append(".*")
            index += 2
        elif pattern[index] == "*":
            out.append("[^/]*")
            index += 1
        elif pattern[index] == "?":
            out.append("[^/]")
            index += 1
        else:
            out.append(re.escape(pattern[index]))
            index += 1
    return re.compile("".join(out) + r"\Z")


def _filter_matches(patterns: list[str], path: str) -> bool:
    """True when a GitHub `paths:` filter list selects a path.

    Patterns are applied in order; a leading `!` negates, matching GitHub's
    last-match-wins evaluation.
    """
    matched = False
    for pattern in patterns:
        negated = pattern.startswith("!")
        body = pattern[1:] if negated else pattern
        if _glob_to_regex(body).match(path):
            matched = not negated
    return matched


def _covered_by_every_event(workflow_name: str, path: str) -> list[str]:
    """Return the events whose path filter does NOT select the given path.

    A `paths:` filter selects the path when it matches; a `paths-ignore:` filter
    selects it when it does not.
    """
    uncovered: list[str] = []
    for declared in _trigger_filters(_workflow_data(workflow_name)):
        matched = _filter_matches(declared.patterns, path)
        selected = matched if declared.kind == "paths" else not matched
        if not selected:
            uncovered.append(declared.event)
    return sorted(uncovered)


class ScriptResolution(NamedTuple):
    """The outcome of resolving an executed script basename to a tracked file.

    Attributes:
        basename: The name as it appeared on the command line.
        path: The single tracked path it resolved to, or None.
        candidates: Every tracked path carrying that basename.
        source: The step the invocation came from.
    """

    basename: str
    path: str | None
    candidates: tuple[str, ...]
    source: str


def _real_script_path(basename: str) -> tuple[str | None, tuple[str, ...]]:
    """Resolve a script basename to its tracked repo-relative path.

    CI copies some validators to the repository root before running them
    (ADR-037 D5 keeps that arrangement), so the path on the command line is not
    always the path in the repository. Trigger filters have to name the real one.

    Returns both the resolution and every candidate, so an ambiguous or absent
    basename can be *reported* rather than dropped. The previous form searched
    `scripts/**` only and returned None on zero or several matches, and the
    caller skipped None silently: a gate step running
    `python3 .github/helpers/preflight.py` lost its trigger requirement without
    a single test noticing.

    The search is over tracked files rather than a directory glob, so a script
    anywhere in the repository resolves and untracked build output cannot.
    """
    declared = PRECOMMIT_VALIDATORS.get(basename)
    if declared:
        return declared, (declared,)
    candidates = tuple(sorted(TRACKED_BY_BASENAME.get(basename, [])))
    return (candidates[0] if len(candidates) == 1 else None), candidates


def _workflow_script_resolutions(workflow_name: str) -> list[ScriptResolution]:
    """Return one resolution record per script a workflow's steps execute.

    Covers both direct executions and executions inside a command substitution
    — the file-list resolver reaches the workflow only the second way.
    """
    resolutions: list[ScriptResolution] = []
    for step in WORKFLOW_STEPS:
        if step.workflow != workflow_name:
            continue
        invocations = _python_invocations(step.run, step.source, keep_substitutions=True)
        nested = [
            inner
            for invocation in invocations
            for _, command in invocation.substitutions
            for inner in _python_invocations(command, step.source)
        ]
        for invocation in [*invocations, *nested]:
            path, candidates = _real_script_path(invocation.script)
            resolutions.append(ScriptResolution(invocation.script, path, candidates, step.source))
    return resolutions


def _copied_dependencies(workflow_name: str) -> set[str]:
    """Return the tracked files a workflow's file-relocating commands stage.

    Copy operands may be globs (`riskmap_validator/*`), and a glob match may be
    a *directory*: `cp -r scripts/hooks/riskmap_validator/*` stages the
    `graphing/` package as well as the five top-level modules. Filtering matches
    to `is_file()` dropped that whole subtree, so a pull request touching only
    `riskmap_validator/graphing/` was not required to re-run the gate that
    executes it. Directories are therefore expanded to the tracked files beneath
    them.
    """
    dependencies: set[str] = set()
    for step in WORKFLOW_STEPS:
        if step.workflow != workflow_name:
            continue
        for copy in _copy_commands(step.run, step.source):
            for match in sorted(_REPO_ROOT.glob(copy.source_path)):
                relative = match.relative_to(_REPO_ROOT).as_posix()
                if match.is_dir():
                    prefix = f"{relative}/"
                    dependencies |= {path for path in TRACKED_FILES if path.startswith(prefix)}
                elif relative in TRACKED_FILE_SET:
                    dependencies.add(relative)
    return dependencies


def _workflow_dependencies(workflow_name: str) -> set[str]:
    """Return the repo files a workflow's steps execute or stage into place.

    Fails loudly on a basename that does not resolve to exactly one tracked
    file. Returning a partial set would understate what the `paths:` filter has
    to cover, and understating it is silent in both directions: the trigger test
    passes, and the gate does not run on the pull request that changes the
    unresolved script.
    """
    resolutions = _workflow_script_resolutions(workflow_name)
    unresolved = [record for record in resolutions if record.path is None]
    if unresolved:
        pytest.fail(
            f"{workflow_name}: these executed scripts do not resolve to exactly one "
            f"tracked repository file, so their trigger requirement cannot be derived:\n"
            + "\n".join(
                f"  - {record.basename} ({record.source}): "
                f"{list(record.candidates) or 'no tracked file with that name'}"
                for record in unresolved
            )
            + "\ntest_every_executed_script_resolves_to_one_tracked_file reports the same "
            "finding with the reasoning; it is repeated here because silently skipping "
            "an unresolved script is how a gate loses a trigger requirement unnoticed."
        )

    dependencies = {record.path for record in resolutions if record.path}
    return dependencies | _copied_dependencies(workflow_name)


def _reads_precommit_config(repo_relative_script: str) -> bool:
    """True when a script's source names the pre-commit config as an input.

    A script's data dependencies are not derivable in general. This is the one
    that exists today — the file-list resolver reads `.pre-commit-config.yaml`
    to find the hook whose patterns it evaluates — and a textual check finds it
    without this module having to name the resolver.
    """
    path = _REPO_ROOT / repo_relative_script
    return path.is_file() and _PRECOMMIT_CONFIG.name in path.read_text(encoding="utf-8")


GATE_WORKFLOWS = sorted({step.workflow for step in GATE_STEPS})


# This module's own repo-relative path. A pytest invocation matters here only
# if the run it describes would collect this file — that is the definition of
# "the workflow where these standing guards execute", and it is derived rather
# than approximated by "no target given".
_THIS_MODULE = Path(__file__).resolve().relative_to(_REPO_ROOT).as_posix()


def _pytest_command_arguments(segment: list[str]) -> list[str] | None:
    """Return a pytest command's arguments, or None if it is not one.

    Two spellings are recognised, and recognising only the first is a live
    hazard rather than a hypothetical one: `python3 -m pytest` is the form this
    project's own guidance prescribes, because bare `pytest` over-collects
    through a symlinked working tree. A derivation blind to it silently empties
    `PYTEST_WORKFLOWS`, and an empty parametrization is reported as a skip
    rather than as a missing guard.
    """
    if not segment:
        return None
    if Path(segment[0]).name == "pytest":
        return segment[1:]
    if _INTERPRETER_RE.match(Path(segment[0]).name) and segment[1:3] == ["-m", "pytest"]:
        return segment[3:]
    return None


def _looks_like_a_test_target(token: str) -> bool:
    """True when a pytest argument is a path or node id rather than an option.

    `--junitxml=junit/test-results.xml` is a single token and is filtered by the
    leading dash before this is reached.
    """
    return token.endswith(".py") or "/" in token or "::" in token


def _target_selects_this_module(target: str) -> bool:
    """True when a pytest target argument would collect this test module.

    Node ids (`path::Class::test`) are reduced to their path, and a directory
    target selects everything beneath it.
    """
    path = target.split("::", 1)[0].strip().rstrip("/")
    if not path or path == ".":
        return True
    return _THIS_MODULE == path or _THIS_MODULE.startswith(f"{path}/")


def _pytest_workflows() -> list[str]:
    """Return the workflows whose pytest run would collect this module.

    Targeted invocations are not excluded wholesale. `pytest scripts/` is a
    targeted run that collects this module, and treating it as out of scope is
    how the set empties on an edit a contributor makes for good reasons. What is
    excluded is a target that does *not* select this file — `pytest
    scripts/hooks/tests/test_x.py` in `persona-pages.yml` and
    `validate-issue-templates.yml` — because such a run carries no obligation to
    trigger on files it never asserts over.
    """
    found: set[str] = set()
    for step in WORKFLOW_STEPS:
        for raw_line in step.run.splitlines():
            tokens = _safe_split(raw_line.strip())
            for segment in _split_simple_commands(tokens):
                while segment and (segment[0] in _LEADING_WORDS or _TOKEN_ASSIGN_RE.match(segment[0])):
                    segment = segment[1:]
                arguments = _pytest_command_arguments(segment)
                if arguments is None:
                    continue
                targets = [
                    token for token in arguments if not token.startswith("-") and _looks_like_a_test_target(token)
                ]
                if not targets or any(_target_selects_this_module(target) for target in targets):
                    found.add(step.workflow)
    return sorted(found)


PYTEST_WORKFLOWS = _pytest_workflows()


class TestWorkflowTriggerCoverage:
    """A gate that does not run on the pull request that breaks it is not a gate.

    ADR-037 D1 places the enforcement decision in CI. That is a claim about
    which workflow runs, not only about which flags it passes, and `paths:`
    filters decide the first. The failure is total rather than partial: the job
    does not appear at all, so there is no red tick to notice and no log to read.

    Both tests are derived from the workflows themselves. A validator added to
    the gate, or a script the gate starts executing, is required in the filter
    without anyone editing this module.
    """

    def test_gate_workflows_are_found(self):
        """
        Given: the derived gate steps
        When: their workflows are collected
        Then: at least one is found

        Non-vacuity guard for the two tests below.
        """
        assert GATE_WORKFLOWS, (
            "No workflow contains a step invoking a validator with "
            f"{sorted(STRICTNESS_FLAGS)}; the trigger rules below would quantify "
            "over nothing."
        )

    def test_pytest_workflows_are_found(self):
        """
        Given: every `run:` step in every workflow
        When: steps running a pytest command that would collect this module are
              selected
        Then: at least one workflow is found

        Every other derived set in this module has a guard like this one; this
        set did not, and it is the easiest of them to empty. Two edits do it,
        both of which a contributor makes for good reasons:

          - giving the run a target, e.g. `pytest scripts/ --junitxml=...`;
          - spelling it `python3 -m pytest`, which is the form this project
            prescribes because bare `pytest` over-collects through a symlinked
            working tree.

        `_pytest_workflows` handles both now. What this test adds is that the
        *next* such edit fails instead of emptying the parametrization below —
        an empty parametrize collects no cases, and pytest reports that as a
        skip, not as a missing guard.
        """
        assert PYTEST_WORKFLOWS, (
            "No workflow runs a pytest command that would collect "
            f"{_THIS_MODULE}. Every standing guard in this module therefore runs "
            "nowhere in CI, and the trigger rule below has no workflow to check. "
            "If the suite genuinely moved to another runner, the derivation in "
            "`_pytest_workflows` is what needs teaching, not this assertion."
        )

    @pytest.mark.parametrize("workflow_name", GATE_WORKFLOWS)
    def test_every_executed_script_resolves_to_one_tracked_file(self, workflow_name):
        """
        Given: every Python script a gate workflow's steps execute, directly or
               inside a command substitution
        When: each basename is resolved against the tracked corpus
        Then: each resolves to exactly one file

        A basename that resolves to zero or several files has no derivable
        trigger requirement, and the previous form of the resolver returned None
        for both cases while the caller skipped None without a word. Adding
        `python3 .github/helpers/preflight.py` to a gate step was therefore free:
        the script became load-bearing for the gate's result and acquired no
        obligation to re-run it.

        Ambiguity is a real case, not a hypothetical one — `__init__.py` and
        `conftest.py` already carry many tracked paths each. A script whose name
        collides has to be disambiguated before its trigger requirement means
        anything.
        """
        unresolved = [record for record in _workflow_script_resolutions(workflow_name) if record.path is None]
        assert not unresolved, (
            f"{workflow_name} executes scripts that do not resolve to exactly one "
            f"tracked file:\n"
            + "\n".join(
                f"  - {record.basename} ({record.source}): "
                f"{list(record.candidates) or 'no tracked file with that name'}"
                for record in unresolved
            )
            + "\nAn unresolved basename contributes nothing to the `paths:` requirement "
            "below, so the gate stops re-running on changes to a script it executes — "
            "and nothing says so."
        )

    @pytest.mark.parametrize("workflow_name", GATE_WORKFLOWS)
    def test_gate_workflow_triggers_on_everything_that_defines_the_gate(self, workflow_name):
        """
        Given: a workflow containing a D1 gate
        When: its `paths:` filters are checked against its own definition, every
              script its steps execute or copy into place, and the pre-commit
              config those scripts read
        Then: every one is matched, for every filtered event

        Three consequences of a filter that omits these, all silent:

          - a pull request editing the workflow does not run it, so the change
            that removes a `--block`, deletes a job, or narrows a file list is
            merged without the gate ever executing;
          - a pull request editing a validator does not re-run the gate that
            validator feeds;
          - a pull request editing `.pre-commit-config.yaml` — where the hook
            patterns the CI file lists are derived from live — does not re-run
            the jobs whose inputs it just changed.

        Sibling workflows already do this: `validate_tables.yml`,
        `validate_workflows.yml` and `persona-pages.yml` each list their own
        scripts, and two of the three list themselves.
        """
        filters = _trigger_filters(_workflow_data(workflow_name))
        assert filters, (
            f"{workflow_name} declares no `paths:` or `paths-ignore:` filter on any "
            "event, so it runs unconditionally and this rule does not apply. If that "
            "changed deliberately, this test should be removed with the filter."
        )

        required = {f".github/workflows/{workflow_name}"}
        scripts = _workflow_dependencies(workflow_name)
        required |= scripts
        if any(_reads_precommit_config(script) for script in scripts):
            required.add(_PRECOMMIT_CONFIG.name)

        uncovered = {
            path: missing for path in sorted(required) if (missing := _covered_by_every_event(workflow_name, path))
        }
        assert not uncovered, (
            f"{workflow_name} carries a D1 gate but does not re-run when its own inputs "
            f"change. Uncovered by `paths:`:\n"
            + "\n".join(
                f"  - {path}  (not matched for: {', '.join(events)})" for path, events in uncovered.items()
            )
            + f"\nDeclared filters: {[(f.event, f.kind, f.patterns) for f in filters]}\n"
            "A pull request touching any of these merges without this workflow running."
        )

    @pytest.mark.parametrize("workflow_name", PYTEST_WORKFLOWS)
    def test_pytest_workflow_triggers_on_the_files_the_suite_asserts_over(self, workflow_name):
        """
        Given: the workflow that runs pytest
        When: its `paths:` filters are checked against the repository files this
              suite reads as its subject matter
        Then: every one is matched, for every filtered event

        The standing guards ADR-037's follow-up section asks for — D1 coverage,
        D3's prohibition, D7a's file lists, D7b's in-place invocation — are all
        assertions *about* `.github/workflows/`. They are also all pytest tests,
        and pytest runs in exactly one workflow.

        So a pull request that edits only workflow YAML runs no pytest at all.
        Every guard in this module is absent from the one change it exists to
        catch: stripping `--block` from a job, deleting a job, or dropping a
        file-list expansion each pass CI silently.
        """
        # Derived from the constants this module reads, so a new subject file
        # becomes a requirement without an edit here.
        subjects = {path.relative_to(_REPO_ROOT).as_posix() for path in _workflow_files()}
        subjects.add(_PRECOMMIT_CONFIG.relative_to(_REPO_ROOT).as_posix())
        for gate_workflow in GATE_WORKFLOWS:
            subjects |= _workflow_dependencies(gate_workflow)

        uncovered = {
            path: missing for path in sorted(subjects) if (missing := _covered_by_every_event(workflow_name, path))
        }
        assert not uncovered, (
            f"{workflow_name} is the only workflow running pytest, and its `paths:` "
            f"filter does not match files this test suite asserts over:\n"
            + "\n".join(
                f"  - {path}  (not matched for: {', '.join(events)})" for path, events in uncovered.items()
            )
            + "\nA pull request touching only those files runs no tests, so every "
            "standing guard on the CI gate is silent on precisely the change that "
            "disables it."
        )


# ===========================================================================
# 9. The step's own exit code — the enforcement mechanism itself
# ===========================================================================
#
# Every other behavioural test in this module models the *validator's* exit
# code: it runs the validator directly and asserts on what it returns. Nothing
# above models the *step's*. The workflow wraps each validator in
#
#     if python3 ... --block ...; then
#       echo "OK"; echo "status=success" >> $GITHUB_OUTPUT
#     else
#       echo "FAILED"; echo "status=failed" >> $GITHUB_OUTPUT
#       exit 1
#     fi
#
# and it is that `exit 1` — not the validator's return code, and not the
# `status` output — that fails the job. The `status` outputs are not a second
# line of defence: the workflow declares nine `*_status` job outputs and
# consumes none of them, so the step's exit code is the whole mechanism.
#
# Four one-line edits reach the state ADR-037 D7 explicitly rejects — "landing
# the invocation warn-only to soak" — with the violation still found and still
# printed in the log, and with no flag, path, file list, or working directory
# touched:
#
#   - deleting `exit 1` from the `else` branch;
#   - `... --block ${FILES} || true; then`;
#   - `continue-on-error: true` on the step;
#   - a conditional `if:` on the step or its job.
#
# The first two are properties of the shell body and are asserted by executing
# it. The last two are step and job keys that appear in no command line at all,
# and are asserted structurally because there is nothing to execute.


def _write_stub_interpreter(directory: Path) -> None:
    """Write a `python3` stub whose exit code is controlled by the environment.

    The stub decides which role it is playing from the command line rather than
    from a script name: an invocation carrying a strictness flag is the gate's
    validator, anything else is the file-list resolver. That is derived from
    STRICTNESS_FLAGS, so it keeps working if the resolver is renamed or the
    validator moves.

    The resolver arm prints one path-shaped token, because the step word-splits
    that output into the validator's argv and an empty expansion would exercise
    a different code path than the one under test.
    """
    directory.mkdir(parents=True, exist_ok=True)
    flags = " ".join(f'"{flag}"' for flag in sorted(STRICTNESS_FLAGS))
    body = (
        "#!/usr/bin/env bash\n"
        f"for want in {flags}; do\n"
        '  for arg in "$@"; do\n'
        '    if [ "$arg" = "$want" ]; then\n'
        '      exit "${STUB_VALIDATOR_EXIT:-0}"\n'
        "    fi\n"
        "  done\n"
        "done\n"
        'echo "risk-map/yaml/stub.yaml"\n'
        'exit "${STUB_RESOLVER_EXIT:-0}"\n'
    )
    # Both spellings, so a step naming the interpreter either way is covered.
    for name in ("python3", "python"):
        stub = directory / name
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)


def _run_step_body(
    step: WorkflowStep,
    sandbox: Path,
    validator_exit: int,
    resolver_exit: int,
) -> subprocess.CompletedProcess:
    """Execute a step's `run:` body under GitHub's default shell, with stubs.

    The body is run verbatim under `bash -e`, which is what GitHub uses for a
    `run:` block with no `shell:` key. `GITHUB_OUTPUT` is pointed at a real file
    so the `>> $GITHUB_OUTPUT` appends succeed — left unset they would produce
    an ambiguous-redirect error and a non-zero exit for a reason that has
    nothing to do with the gate.
    """
    bin_dir = sandbox / "bin"
    _write_stub_interpreter(bin_dir)
    environment = {
        "PATH": f"{bin_dir}:{os.environ.get('PATH', '')}",
        "HOME": str(sandbox),
        "GITHUB_OUTPUT": str(sandbox / "github_output.txt"),
        "GITHUB_STEP_SUMMARY": str(sandbox / "github_step_summary.txt"),
        "STUB_VALIDATOR_EXIT": str(validator_exit),
        "STUB_RESOLVER_EXIT": str(resolver_exit),
    }
    return subprocess.run(
        ["bash", "-e", "-c", step.run],
        capture_output=True,
        text=True,
        cwd=str(sandbox),
        env=environment,
    )


def _gate_step_ids() -> list[str]:
    """Return stable parametrization ids for the gate steps."""
    return [step.source for step in GATE_STEPS]


class TestGateStepFailsTheJob:
    """A found violation has to fail the step, and the step has to fail the job.

    ADR-037 D1 makes CI the enforcing gate and D7 refuses the warn-only soak.
    Both are claims about the *job's* conclusion, and the job's conclusion is
    decided by the step's exit code — nothing consumes the `status` outputs the
    steps write, so there is no second path by which a failure becomes a red
    tick.

    The tests below are the only ones in this module that execute the workflow's
    own shell. Everything else runs the validator and reads its return code,
    which is a different number: a step can observe exit 1 from the validator,
    print the violation, and still return 0.

    Each behavioural case is asserted against a control run in which the stub
    succeeds. Without it, "the body exited non-zero" could be a broken harness —
    an unset variable, a missing file, a `bash -e` abort on something unrelated —
    reported as enforcement.
    """

    def test_gate_steps_are_executable_in_isolation(self):
        """
        Given: the derived gate steps
        When: their shell bodies are inspected
        Then: at least one exists and each has a body to run

        Non-vacuity guard: the parametrized cases below quantify over this set,
        and an empty one collects no cases at all.
        """
        assert GATE_STEPS, (
            "No gate step was derived, so no step body can be executed. "
            "TestGateStepsRunFromRepositoryRoot::test_gate_steps_are_found "
            "explains what that means for the rest of the suite."
        )
        empty = [step.source for step in GATE_STEPS if not step.run.strip()]
        assert not empty, f"Gate steps with an empty `run:` body: {empty}"

    @pytest.mark.parametrize("step", GATE_STEPS, ids=_gate_step_ids())
    def test_gate_step_body_succeeds_when_its_validator_succeeds(self, step, tmp_path):
        """
        Given: a gate step's shell body, with the interpreter stubbed to succeed
        When: the body runs under `bash -e`
        Then: it exits 0

        The control. It establishes that the harness can run this body at all,
        so that the non-zero result in the next test is attributable to the
        validator's failure rather than to the sandbox.
        """
        result = _run_step_body(step, tmp_path, validator_exit=0, resolver_exit=0)
        assert result.returncode == 0, (
            f"{step.source}: the step body exits {result.returncode} even when every "
            f"command it runs succeeds, so the failure assertions that follow would "
            f"prove nothing.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    @pytest.mark.parametrize("step", GATE_STEPS, ids=_gate_step_ids())
    def test_gate_step_body_fails_when_its_validator_fails(self, step, tmp_path):
        """
        Given: a gate step's shell body, with the validator stubbed to exit 1
        When: the body runs under `bash -e`
        Then: it exits non-zero

        The assertion the whole ADR rests on, and the one nothing else in this
        module makes. Deleting `exit 1` from the `else` branch, or writing
        `... --block ${FILES} || true; then`, each leave the violation found and
        printed, every flag in place, the file list complete, and the job green.

        That is precisely "land the invocation warn-only to soak", which ADR-037
        D7 rejects by name — reached without touching anything the other
        assertions in this module look at.
        """
        result = _run_step_body(step, tmp_path, validator_exit=1, resolver_exit=0)
        assert result.returncode != 0, (
            f"{step.source}: the validator exited 1 and the step body still exited 0. "
            f"The job is green with the violation found and printed.\n"
            f"  Nothing consumes the `status` outputs this step writes, so the step's "
            f"exit code is the entire enforcement mechanism (ADR-037 D1).\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    @pytest.mark.parametrize("step", GATE_STEPS, ids=_gate_step_ids())
    def test_gate_step_body_fails_when_its_file_list_resolver_fails(self, step, tmp_path):
        """
        Given: a gate step that builds a file list from a command, with the
               resolver stubbed to exit 1 and the validator stubbed to exit 0
        When: the body runs under `bash -e`
        Then: it exits non-zero

        `FILES=$(resolver || true)` is the mutation this catches, and it is
        invisible everywhere else: the file list is still derived, still
        complete, still passed, and the resolver still runs. What it discards is
        the resolver's non-zero exit on an empty match — which
        `test_hook_file_list.py` calls the single most important assertion it
        makes, because the two `nargs="*"` validators exit 0 when handed no
        files.

        Nothing notices until the match actually goes empty, at which point the
        job passes having read nothing. A `files:` pattern edit, a rename, or a
        directory move is enough to get there.

        Steps with no file-list substitution are skipped: there is no resolver
        whose failure could be swallowed, and the previous test already covers
        their validator arm.
        """
        substitutions = _step_substitutions(step)
        if not substitutions:
            pytest.skip(
                f"{step.source} builds no file list from a command, so it has no "
                "resolver exit status to discard. Its validator arm is covered by "
                "test_gate_step_body_fails_when_its_validator_fails."
            )

        result = _run_step_body(step, tmp_path, validator_exit=0, resolver_exit=1)
        assert result.returncode != 0, (
            f"{step.source}: the file-list resolver exited 1 and the step body still "
            f"exited 0, so the validator ran on whatever the failed resolution left "
            f"behind.\n  file-list commands: {[command for _, command in substitutions]}\n"
            f"  The resolver's exit-1-on-empty-match contract is load-bearing only "
            f"while the step propagates it.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    @pytest.mark.parametrize("step", GATE_STEPS, ids=_gate_step_ids())
    def test_no_gate_step_guards_its_validator_against_failure(self, step):
        """
        Given: a gate step's shell body
        When: the simple command carrying a strictness flag is located and the
              operator following it is inspected
        Then: it is not `||`

        The structural companion to the behavioural tests above, and the one
        that names the offending line. `_split_simple_commands` cannot express
        this — it discards operators, so `cmd` and `cmd || true` produce
        identical output there, and those two differ by exactly whether the job
        can fail.
        """
        guarded: list[str] = []
        for raw_line in step.run.splitlines():
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            for segment, operator in _segments_with_operators(_safe_split(stripped)):
                if STRICTNESS_FLAGS.intersection(segment) and operator == "||":
                    guarded.append(stripped)

        assert not guarded, (
            f"{step.source}: a strictness-carrying command is guarded against its own "
            f"failure:\n" + "\n".join(f"  - {line}" for line in guarded) + "\n"
            "`|| true` (or any `||` fallback) makes the validator's non-zero exit "
            "invisible to the `if`, so the success branch runs, the job goes green, "
            "and the violation is merely printed."
        )

    @pytest.mark.parametrize("step", GATE_STEPS, ids=_gate_step_ids())
    def test_no_gate_step_is_exempted_from_failing_the_job(self, step):
        """
        Given: a gate step and its enclosing job
        When: `continue-on-error:` and `if:` are inspected at both levels
        Then: neither declares one

        These two keys sit outside the shell entirely, so no amount of executing
        the body can see them. `continue-on-error: true` lets the step exit 1
        and the job succeed anyway; an `if:` that is false — `github.event_name
        == 'schedule'` on a workflow that runs on pull requests, say — means the
        step does not run at all, which produces neither a failure nor a
        conspicuous absence.

        `if: always()` on a summary job is a legitimate pattern in this
        repository, which is exactly why the prohibition is scoped to *gate*
        steps: a summary that always runs is useful, a gate that sometimes runs
        is not a gate.
        """
        exemptions: list[str] = []
        if step.continue_on_error is not None:
            exemptions.append(f"step `continue-on-error: {step.continue_on_error!r}`")
        if step.job_continue_on_error is not None:
            exemptions.append(f"job `continue-on-error: {step.job_continue_on_error!r}`")
        if step.condition is not None:
            exemptions.append(f"step `if: {step.condition!r}`")
        if step.job_condition is not None:
            exemptions.append(f"job `if: {step.job_condition!r}`")

        assert not exemptions, (
            f"{step.source} is exempted from failing the workflow: {exemptions}.\n"
            "ADR-037 D1 makes CI the enforcing gate. A gate step that may fail without "
            "failing its job, or that may not run at all, enforces nothing — and both "
            "keys are invisible to every command-line assertion in this module."
        )


# ===========================================================================
# 10. This module's own inventory
# ===========================================================================


class TestModuleInventory:
    """The suite's description of itself is an assertion, not prose.

    Deleting an entire test class from this module produced a smaller run and
    zero failures: the count in the summary comment below is a comment, and no
    other test quantifies over what this module contains. That matters more here
    than in most suites, because several classes exist to be the only thing that
    would notice a particular edit — losing one is losing the guard, silently.

    Class *names* are pinned, not case counts. Counts are derived from
    `.pre-commit-config.yaml` and from the workflows, and pinning them would
    fight the derive-don't-enumerate rule the rest of the module is built on: a
    fourth `--block` hook should extend the parametrizations, not fail this.
    What is pinned alongside the names is that each class collects at least one
    case, which is the other way a class goes quiet — a parametrization whose
    derived set went empty.
    """

    EXPECTED_CLASSES = frozenset(
        {
            "TestParserFidelity",
            "TestStrictnessCoverage",
            "TestStrictnessMonotonicity",
            "TestGraphEmissionExclusion",
            "TestPrecommitValidatorsRunInPlace",
            "TestBlockFlagChangesBehaviour",
            "TestCIInvocationCatchesViolation",
            "TestCIFileListsAreDerivedAndComplete",
            "TestGateStepsRunFromRepositoryRoot",
            "TestWorkflowTriggerCoverage",
            "TestGateStepFailsTheJob",
            "TestModuleInventory",
        }
    )

    def test_module_collects_every_class_it_declares(self):
        """
        Given: this module, collected by pytest
        When: the classes that produced collected cases are compared to
              EXPECTED_CLASSES
        Then: the two sets are equal

        Fails on a deleted class, on a class renamed without updating the set,
        and on a new class added without declaring it — the last being how the
        set stays honest rather than becoming a stale copy of a past state.
        """
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "--collect-only",
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
                str(Path(__file__).resolve()),
            ],
            capture_output=True,
            text=True,
            cwd=str(_REPO_ROOT),
        )
        assert result.returncode == 0, (
            f"Collecting this module failed ({result.returncode}); the inventory cannot "
            f"be compared.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        # `-q` node ids are `path::Class::test[param]`. Lines with fewer than
        # three components are module-level functions or summary text.
        collected: dict[str, int] = {}
        for line in result.stdout.splitlines():
            parts = line.strip().split("::")
            if len(parts) < 3 or not parts[0].endswith(".py"):
                continue
            collected[parts[1]] = collected.get(parts[1], 0) + 1

        assert set(collected) == self.EXPECTED_CLASSES, (
            "This module's declared inventory does not match what it collects.\n"
            f"  missing (declared, not collected): {sorted(self.EXPECTED_CLASSES - set(collected))}\n"
            f"  undeclared (collected, not declared): {sorted(set(collected) - self.EXPECTED_CLASSES)}\n"
            "A deleted class produces a smaller run and no failure; several classes here "
            "are the only thing that would notice a particular edit."
        )

        empty = sorted(name for name, count in collected.items() if count == 0)
        assert not empty, (
            f"These classes collected no cases: {empty}. A parametrization over a "
            "derived set that went empty is reported by pytest as success."
        )


# ===========================================================================
# Test Summary
# ===========================================================================
# Class membership is asserted by TestModuleInventory, not by this comment.
# Case counts are derived from `.pre-commit-config.yaml` and the workflows and
# move with them by design; run
# `pytest --collect-only -q scripts/hooks/tests/test_ci_block_parity.py` for the
# current figure rather than trusting a number written here.
#
# TestParserFidelity (7)
#   — pre-commit derivation finds strictness-flagged validators; workflow
#     derivation finds Python invocations; the workflow scan covers every file
#     GitHub would run out of .github/workflows/ (both `.yml` and `.yaml`) and
#     the step parse reaches each of them; parser resolves the variable-built
#     graph invocation; `cp` steps are not read as invocations; pre-commit
#     script basenames are unambiguous (the D1 join key); graph-emission flag
#     names are real options of validate_riskmap.py.
#     PASS — they exist so the D1/D4 failures mean something and so the D3
#     pass is not a blind one. The scan test is what stops one character —
#     `gate.yaml` instead of `gate.yml` — from exempting a workflow from every
#     prohibition in this module at once.
#
# TestStrictnessCoverage (5, parametrized over the derived set)
#   — D1 part 1: every validator invoked with a strictness flag by
#     .pre-commit-config.yaml has a workflow invocation carrying those flags.
#
# TestStrictnessMonotonicity (5, parametrized over the derived set)
#   — D1 part 2: for validators on both surfaces, CI strictness is a superset
#     of hook strictness.
#
# TestGraphEmissionExclusion (3)
#   — no live workflow invocation pairs a strictness flag with graph emission;
#     detector catches a literal pairing; detector catches a variable-built
#     pairing.
#     PASS — ADR-037 D3 codifies existing practice rather than changing it.
#     The two synthetic tests are what make the live-workflow pass non-vacuous.
#
# TestPrecommitValidatorsRunInPlace (6)
#   — D7b: no workflow relocates a scripts/hooks/precommit/ validator; every
#     workflow invocation of one uses its real path; detectors catch a literal
#     copy, a variable-built copy, and a bare-basename invocation; and a
#     relocated copy is observed going vacuous (exit 0, empty stderr) on the
#     same poisoned corpus the in-place run fails on (exit 1, diagnostic).
#
# TestBlockFlagChangesBehaviour (1 + 5 + 5)
#   — every strictness-flagged validator has a probe; --block changes the exit
#     code on an injected warn-level violation and the warn output names it;
#     a clean corpus exits 0 both ways.
#     PASS — the toggles already work. This tier is the precondition, not the
#     deliverable.
#
# TestCIInvocationCatchesViolation (5 + 5, parametrized over the derived set)
#   — CI invocations carry the enabling arguments (`--force`) without which the
#     validator skips the corpus and exits 0. A validator with no enabling
#     arguments is asserted to be one whose enabling input is its file list,
#     rather than skipped: "nothing enables it" and "its input is asserted
#     elsewhere" are different claims and only the second is true here.
#
#   — the argument list a workflow passes to each strictness-flagged validator
#     exits non-zero on a corpus carrying an injected warn-level violation,
#     having first exited 0 on the clean equivalent.
#     Note the scope: this tier substitutes the probe's own positionals, so it
#     establishes that `--block` reaches the validator and not that the file
#     list does. Section 6 is where the file list is established.
#
# TestCIFileListsAreDerivedAndComplete (2 + 5 x 3 governed hooks = 17)
#   — D7a: the governed hook set is derived and non-empty and every member has
#     a corpus writer; each CI invocation takes its file list from a command
#     rather than from transcribed paths; that command is a single simple
#     command running a script that reads the pre-commit config and names this
#     hook's own id; exactly one CI invocation belongs to each governed hook;
#     that command's whole output equals the hook's own file set; and the real
#     validator, run with the real argument list once per resolved file, fails
#     on each of them in turn.
#     "From a command" alone was satisfied by `FILES=$(cat prose-files.txt)` —
#     a transcription with a substitution wrapped round it — and by
#     `$(resolver || true)`, which discards the resolver's exit-1-on-empty.
#     The uniqueness assertion is what notices a second invocation of the same
#     validator: the resolution used to take candidates[0], so a duplicate ran
#     in CI unexamined and a second real hook produced a confident failure
#     against the wrong command.
#
# TestGateStepsRunFromRepositoryRoot (6)
#   — no gate step declares a non-root working-directory or runs `cd`; every
#     gate step's shell exits on error and none turns it back off with `set +e`;
#     plus two fidelity checks — the derived file list really does change with
#     the working directory, and `bash -e` really does abort on a failing
#     command substitution (a platform assertion, flagged as such in place).
#     The prohibitions PASS today because GitHub's defaults supply both
#     properties. Nothing in the workflow states them, which is the reason to
#     pin them: an edit that changes either leaves every command line intact.
#
# TestWorkflowTriggerCoverage (2 + 1 + 1 + 1)
#   — a gate workflow triggers on its own definition, on every script its steps
#     execute or copy into place, and on the pre-commit config those scripts
#     read; every executed script resolves to exactly one tracked file, so no
#     trigger requirement is dropped in silence; the pytest-workflow set is
#     non-empty; and the workflow running the suite triggers on the files this
#     module asserts over.
#     These are about which pull requests the gate runs on at all, which no
#     other test in this module can observe. `paths-ignore` is modelled
#     alongside `paths`, because a workflow switching spelling would otherwise
#     read as "runs unconditionally" and pass every case vacuously.
#
# TestGateStepFailsTheJob (1 + 5 x 5 gate steps, 2 of them skipped)
#   — the step's own exit code, which nothing else here models. Each gate step's
#     `run:` body is executed verbatim under `bash -e` with the interpreter
#     stubbed: it exits 0 when the stub succeeds (the control), non-zero when
#     the validator fails, and non-zero when the file-list resolver fails.
#     Structurally, no strictness-carrying command is `||`-guarded and no gate
#     step or its job declares `continue-on-error:` or a conditional `if:`.
#     The two steps with no file-list substitution skip the resolver case;
#     their validator case covers them.
#     This is the section that separates "the validator found it" from "the job
#     failed". Four one-line edits reach ADR-037 D7's rejected warn-only soak
#     with every other assertion in this module still green.
#
# TestModuleInventory (1)
#   — the classes this module collects are the classes it declares, and none
#     collects zero cases. Deleting a class was previously a smaller run with no
#     failure.
#
# Warn-path coverage note (D4 disclosure)
#   Every one of the five validators has a warn path reachable from a fixture,
#   so none required the weaker "assert the flag is parsed" substitute. The
#   checks exercised are named per probe in BlockProbe.warn_check, and per
#   entity file in _PROSE_FIELD_BY_STEM for the D7a tier.

#!/usr/bin/env bash
# =============================================================================
# Pre-commit framework migration parity harness (#211)
# =============================================================================
# Verifies that the upstream pre-commit framework (.pre-commit-config.yaml +
# wrapper scripts) produces a tree-identical commit to the legacy bash hook
# (scripts/hooks/pre-commit) when given the same kitchen-sink change set.
#
# Tree-hash equivalence is the merge gate. Commit-hash equivalence is a
# stretch assertion (will only hold if all generators are byte-deterministic;
# Mermaid/Puppeteer SVG output is the most likely source of drift).
#
# This harness exists solely to gate #211 and is deleted in the same PR that
# lands the bash hook removal.
#
# Usage:
#   scripts/hooks/tests/precommit_parity.sh \
#       [--baseline-sha SHA]   # default: merge-base of HEAD and upstream/main
#       [--candidate-sha SHA]  # default: HEAD
#       [--work-dir DIR]       # default: mktemp -d
#       [--keep]               # do not remove work-dir on exit
#
# Exit codes:
#   0  Tree hashes match (merge gate passed; commit hashes may or may not match)
#   1  Tree hashes differ (merge gate FAILED; see printed diff)
#   2  Setup error (missing dependencies, bad SHA, etc.)
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# Argument parsing
# -----------------------------------------------------------------------------

BASELINE_SHA=""
CANDIDATE_SHA=""
WORK_DIR=""
KEEP_WORK=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --baseline-sha)  BASELINE_SHA="$2"; shift 2 ;;
        --candidate-sha) CANDIDATE_SHA="$2"; shift 2 ;;
        --work-dir)      WORK_DIR="$2"; shift 2 ;;
        --keep)          KEEP_WORK=1; shift ;;
        --help|-h)
            sed -n '2,30p' "$0"
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            exit 2
            ;;
    esac
done

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

# -----------------------------------------------------------------------------
# Resolve SHAs
# -----------------------------------------------------------------------------

if [[ -z "$CANDIDATE_SHA" ]]; then
    CANDIDATE_SHA="$(git rev-parse HEAD)"
fi

if [[ -z "$BASELINE_SHA" ]]; then
    # Default to the SAME SHA for baseline and candidate: this branch has both
    # the legacy bash hook source files and the new framework config, so the
    # only difference between the two clones is which hook is installed. Using
    # different SHAs would compare unrelated trees (e.g., requirements.txt and
    # other migration deltas would dominate the diff).
    BASELINE_SHA="$CANDIDATE_SHA"
fi

# -----------------------------------------------------------------------------
# Dependency checks
# -----------------------------------------------------------------------------

for cmd in git python3 npx; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "Error: missing required command: $cmd" >&2
        exit 2
    fi
done

if ! python3 -m pre_commit --version >/dev/null 2>&1; then
    echo "Error: pre-commit Python package not installed (pip install pre-commit==4.5.1)." >&2
    exit 2
fi

# -----------------------------------------------------------------------------
# Work directory + cleanup
# -----------------------------------------------------------------------------

if [[ -z "$WORK_DIR" ]]; then
    WORK_DIR="$(mktemp -d -t precommit-parity-XXXXXX)"
fi
mkdir -p "$WORK_DIR"

cleanup() {
    if [[ "$KEEP_WORK" -eq 0 ]]; then
        rm -rf "$WORK_DIR"
    else
        echo "[keep] work-dir preserved: $WORK_DIR"
    fi
}
trap cleanup EXIT

BASELINE_DIR="$WORK_DIR/baseline"
CANDIDATE_DIR="$WORK_DIR/candidate"

echo "[setup] baseline SHA:  $BASELINE_SHA"
echo "[setup] candidate SHA: $CANDIDATE_SHA"
echo "[setup] work dir:      $WORK_DIR"

# -----------------------------------------------------------------------------
# Pinned commit identity (so commit-hash equivalence can be asserted)
# -----------------------------------------------------------------------------

export GIT_AUTHOR_NAME="Parity Harness"
export GIT_AUTHOR_EMAIL="parity@example.invalid"
export GIT_COMMITTER_NAME="Parity Harness"
export GIT_COMMITTER_EMAIL="parity@example.invalid"
export GIT_AUTHOR_DATE="2026-01-01T00:00:00+00:00"
export GIT_COMMITTER_DATE="$GIT_AUTHOR_DATE"

# -----------------------------------------------------------------------------
# Helper: clone repo at SHA into target directory
# -----------------------------------------------------------------------------

prepare_clone() {
    local target="$1"
    local sha="$2"

    git clone --quiet --no-hardlinks --shared "$REPO_ROOT" "$target"
    git -C "$target" checkout --quiet "$sha"
    # Detach so the original branch ref is not used
    git -C "$target" checkout --quiet --detach
}

# -----------------------------------------------------------------------------
# Step 1: prepare BASELINE clone (bash hook)
# -----------------------------------------------------------------------------

echo "[baseline] preparing clone at $BASELINE_SHA"
prepare_clone "$BASELINE_DIR" "$BASELINE_SHA"

echo "[baseline] installing legacy bash hook"
( cd "$BASELINE_DIR" && ./scripts/install-precommit-hook.sh --auto --force >/dev/null )

# -----------------------------------------------------------------------------
# Step 2: prepare CANDIDATE clone (pre-commit framework)
# -----------------------------------------------------------------------------

echo "[candidate] preparing clone at $CANDIDATE_SHA"
prepare_clone "$CANDIDATE_DIR" "$CANDIDATE_SHA"

echo "[candidate] installing pre-commit framework hook"
( cd "$CANDIDATE_DIR" && python3 -m pre_commit install >/dev/null )

# -----------------------------------------------------------------------------
# Step 3: apply fixture identically in both clones
# -----------------------------------------------------------------------------

# Use the candidate's fixture (it exists on this branch) and copy into baseline
FIXTURE_SRC="$CANDIDATE_DIR/scripts/hooks/tests/fixtures/precommit_parity/apply.py"
if [[ ! -f "$FIXTURE_SRC" ]]; then
    echo "Error: fixture script not found at $FIXTURE_SRC" >&2
    exit 2
fi

echo "[fixture] applying to baseline"
python3 "$FIXTURE_SRC" --repo-root "$BASELINE_DIR" >/dev/null

echo "[fixture] applying to candidate"
python3 "$FIXTURE_SRC" --repo-root "$CANDIDATE_DIR" >/dev/null

# -----------------------------------------------------------------------------
# Step 4: stage source-file changes only and commit (hooks regenerate derivatives)
# -----------------------------------------------------------------------------

stage_source_changes() {
    local clone="$1"
    # SVG regen is intentionally out of parity scope (see fixture comment).
    git -C "$clone" add \
        risk-map/yaml/components.yaml \
        risk-map/yaml/controls.yaml \
        risk-map/yaml/risks.yaml \
        risk-map/yaml/personas.yaml \
        risk-map/yaml/frameworks.yaml \
        scripts/TEMPLATES/new_component.template.yml
}

run_commit() {
    local clone="$1"
    local label="$2"
    echo "[$label] staging source changes"
    stage_source_changes "$clone"
    echo "[$label] committing (hooks will regenerate derivatives)"
    if ! git -C "$clone" commit --quiet -m "parity test" 2>&1 | tee "$WORK_DIR/$label.log" >/dev/null; then
        echo "[$label] commit failed; see $WORK_DIR/$label.log" >&2
        cat "$WORK_DIR/$label.log" >&2
        return 1
    fi
}

run_commit "$BASELINE_DIR" "baseline"
run_commit "$CANDIDATE_DIR" "candidate"

# -----------------------------------------------------------------------------
# Step 5: capture tree and commit hashes
# -----------------------------------------------------------------------------

BASELINE_TREE="$(git -C "$BASELINE_DIR" rev-parse 'HEAD^{tree}')"
CANDIDATE_TREE="$(git -C "$CANDIDATE_DIR" rev-parse 'HEAD^{tree}')"

BASELINE_COMMIT="$(git -C "$BASELINE_DIR" rev-parse HEAD)"
CANDIDATE_COMMIT="$(git -C "$CANDIDATE_DIR" rev-parse HEAD)"

echo
echo "==================== PARITY RESULTS ===================="
echo "Baseline tree:    $BASELINE_TREE"
echo "Candidate tree:   $CANDIDATE_TREE"
echo "Baseline commit:  $BASELINE_COMMIT"
echo "Candidate commit: $CANDIDATE_COMMIT"
echo "========================================================"
echo

# -----------------------------------------------------------------------------
# Step 6: compare and report
# -----------------------------------------------------------------------------

if [[ "$BASELINE_TREE" == "$CANDIDATE_TREE" ]]; then
    echo "[gate] PASS: tree hashes match"
    if [[ "$BASELINE_COMMIT" == "$CANDIDATE_COMMIT" ]]; then
        echo "[stretch] PASS: commit hashes also match"
    else
        echo "[stretch] FAIL: commit hashes differ (one or more generators emitted timestamp/non-determinism)"
    fi
    exit 0
fi

echo "[gate] FAIL: tree hashes differ"
echo
echo "--- ls-tree diff (baseline vs candidate) ---"
git -C "$BASELINE_DIR" ls-tree -r HEAD > "$WORK_DIR/baseline.lstree"
git -C "$CANDIDATE_DIR" ls-tree -r HEAD > "$WORK_DIR/candidate.lstree"
diff -u "$WORK_DIR/baseline.lstree" "$WORK_DIR/candidate.lstree" || true

echo
echo "--- per-file content diffs (top 5 differing files) ---"
diff -u "$WORK_DIR/baseline.lstree" "$WORK_DIR/candidate.lstree" \
  | awk '/^[+-]/ && !/^[+-]{3}/ {print $4}' \
  | sort -u \
  | head -5 \
  | while read -r path; do
        echo
        echo "### $path"
        diff -u \
            <(git -C "$BASELINE_DIR" show "HEAD:$path" 2>/dev/null) \
            <(git -C "$CANDIDATE_DIR" show "HEAD:$path" 2>/dev/null) \
          | head -40 || true
    done

exit 1

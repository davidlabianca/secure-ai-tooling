#!/usr/bin/env python3
"""
Tests for scripts/tools/validate-all.sh.

The --check-generation mode has a strict purity contract: generated artifacts
must be written only to a temporary directory, tracked files must remain
unchanged, and the git index must not be touched.
"""

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent.parent
SCRIPT_SOURCE = REPO_ROOT / "scripts" / "tools" / "validate-all.sh"
REAL_GIT = shutil.which("git")

TABLE_FILES = [
    "components-full.md",
    "components-summary.md",
    "controls-full.md",
    "controls-summary.md",
    "controls-xref-components.md",
    "controls-xref-risks.md",
    "personas-full.md",
    "personas-summary.md",
    "personas-xref-controls.md",
    "personas-xref-risks.md",
    "risks-full.md",
    "risks-summary.md",
]


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    assert REAL_GIT is not None, "git is required for validate-all.sh purity tests"
    return subprocess.run(
        [REAL_GIT, *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )


def _git_status(repo: Path) -> str:
    return _run_git(repo, "status", "--porcelain=v1").stdout


def _make_stubbed_repo(tmp_path: Path, table_content: str = "canonical\n") -> tuple[Path, dict[str, str]]:
    repo = tmp_path / "repo"
    repo.mkdir()

    script_path = repo / "scripts" / "tools" / "validate-all.sh"
    script_path.parent.mkdir(parents=True)
    shutil.copy2(SCRIPT_SOURCE, script_path)

    (repo / "scripts" / "hooks").mkdir(parents=True)
    (repo / "risk-map" / "schemas").mkdir(parents=True)
    (repo / "risk-map" / "tables").mkdir(parents=True)
    (repo / "risk-map" / "yaml").mkdir(parents=True)
    (repo / "risk-map" / "schemas" / "components.schema.json").write_text("{}\n", encoding="utf-8")
    (repo / "risk-map" / "yaml" / "components.yaml").write_text("components: []\n", encoding="utf-8")

    for table_file in TABLE_FILES:
        (repo / "risk-map" / "tables" / table_file).write_text(table_content, encoding="utf-8")

    stub_bin = tmp_path / "bin"
    stub_bin.mkdir()
    git_log = tmp_path / "git-invocations.log"
    python_log = tmp_path / "python-invocations.log"

    _write_executable(
        stub_bin / "check-jsonschema",
        "#!/bin/bash\nexit 0\n",
    )
    _write_executable(
        stub_bin / "git",
        '#!/bin/bash\necho "$@" >> "${GIT_STUB_LOG:?}"\nexit 99\n',
    )
    _write_executable(
        stub_bin / "python3",
        "#!/bin/bash\n"
        'printf "%s\\n" "$*" >> "${PYTHON_STUB_LOG:?}"\n'
        'if [[ "$1" == "scripts/hooks/yaml_to_markdown.py" ]]; then\n'
        '    output_dir=""\n'
        "    while [[ $# -gt 0 ]]; do\n"
        '        if [[ "$1" == "--output-dir" ]]; then\n'
        '            output_dir="$2"\n'
        "            shift 2\n"
        "        else\n"
        "            shift\n"
        "        fi\n"
        "    done\n"
        '    if [[ -n "${TMPDIR_CAPTURE_FILE:-}" ]]; then\n'
        '        dirname "$output_dir" > "$TMPDIR_CAPTURE_FILE"\n'
        "    fi\n"
        '    if [[ "${GENERATOR_MODE:-success}" == "failure" ]]; then\n'
        "        exit 7\n"
        "    fi\n"
        '    if [[ "${GENERATOR_MODE:-success}" == "interrupt" ]]; then\n'
        "        sleep 30\n"
        "        exit 0\n"
        "    fi\n"
        '    mkdir -p "$output_dir"\n'
        "    for table_file in " + " ".join(TABLE_FILES) + "; do\n"
        '        printf "%s" "${GENERATED_CONTENT:-canonical\\n}" > "$output_dir/$table_file"\n'
        "    done\n"
        "    exit 0\n"
        "fi\n"
        "exit 0\n",
    )

    env = os.environ.copy()
    env["PATH"] = f"{stub_bin}{os.pathsep}{env['PATH']}"
    env["GIT_STUB_LOG"] = str(git_log)
    env["PYTHON_STUB_LOG"] = str(python_log)

    _run_git(repo, "init")
    _run_git(repo, "config", "user.email", "tests@example.com")
    _run_git(repo, "config", "user.name", "Tests")
    _run_git(repo, "add", ".")
    _run_git(repo, "commit", "-m", "Initial test fixture")

    return repo, env


def _run_validate_all(repo: Path, env: dict[str, str], *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", "scripts/tools/validate-all.sh", *args],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _assert_repo_unchanged(repo: Path, before_status: str) -> None:
    assert _git_status(repo) == before_status
    diff = _run_git(repo, "diff", "--name-only").stdout
    assert diff == ""


def test_check_generation_success_leaves_tracked_files_and_index_unchanged(tmp_path: Path):
    repo, env = _make_stubbed_repo(tmp_path)
    before_status = _git_status(repo)
    temp_capture = tmp_path / "tempdir.txt"
    env["TMPDIR_CAPTURE_FILE"] = str(temp_capture)
    env["GENERATED_CONTENT"] = "canonical\n"

    result = _run_validate_all(repo, env, "--check-generation")

    assert result.returncode == 0, result.stderr + result.stdout
    assert "Generated markdown tables match risk-map/tables" in result.stdout
    _assert_repo_unchanged(repo, before_status)
    assert not Path(temp_capture.read_text(encoding="utf-8").strip()).exists()
    assert not (tmp_path / "git-invocations.log").exists()


def test_check_generation_drift_fails_without_mutating_tracked_files(tmp_path: Path):
    repo, env = _make_stubbed_repo(tmp_path, table_content="committed\n")
    before_status = _git_status(repo)
    temp_capture = tmp_path / "tempdir.txt"
    env["TMPDIR_CAPTURE_FILE"] = str(temp_capture)
    env["GENERATED_CONTENT"] = "generated\n"

    result = _run_validate_all(repo, env, "--check-generation")

    assert result.returncode == 1
    assert "Table drift detected:" in result.stderr
    assert "components-full.md" in result.stderr
    _assert_repo_unchanged(repo, before_status)
    assert not Path(temp_capture.read_text(encoding="utf-8").strip()).exists()
    assert not (tmp_path / "git-invocations.log").exists()


def test_check_generation_cleans_tempdir_when_generator_fails(tmp_path: Path):
    repo, env = _make_stubbed_repo(tmp_path)
    before_status = _git_status(repo)
    temp_capture = tmp_path / "tempdir.txt"
    env["TMPDIR_CAPTURE_FILE"] = str(temp_capture)
    env["GENERATOR_MODE"] = "failure"

    result = _run_validate_all(repo, env, "--check-generation")

    assert result.returncode == 1
    assert "Markdown table generation check failed" in result.stdout
    _assert_repo_unchanged(repo, before_status)
    assert not Path(temp_capture.read_text(encoding="utf-8").strip()).exists()
    assert not (tmp_path / "git-invocations.log").exists()


def test_check_generation_cleans_tempdir_on_sigint(tmp_path: Path):
    repo, env = _make_stubbed_repo(tmp_path)
    before_status = _git_status(repo)
    temp_capture = tmp_path / "tempdir.txt"
    env["TMPDIR_CAPTURE_FILE"] = str(temp_capture)
    env["GENERATOR_MODE"] = "interrupt"

    process = subprocess.Popen(
        ["bash", "scripts/tools/validate-all.sh", "--check-generation"],
        cwd=repo,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )

    deadline = time.time() + 10
    while not temp_capture.exists() and time.time() < deadline:
        time.sleep(0.05)

    assert temp_capture.exists(), "generator stub did not capture the temporary directory"
    temp_dir = Path(temp_capture.read_text(encoding="utf-8").strip())
    os.killpg(process.pid, signal.SIGINT)
    stdout, stderr = process.communicate(timeout=10)

    assert process.returncode != 0, stderr + stdout
    _assert_repo_unchanged(repo, before_status)
    assert not temp_dir.exists()
    assert not (tmp_path / "git-invocations.log").exists()


def test_help_documents_check_generation_purity_contract(tmp_path: Path):
    repo, env = _make_stubbed_repo(tmp_path)

    result = _run_validate_all(repo, env, "--help")

    assert result.returncode == 0
    assert "--check-generation" in result.stdout
    assert "does not write tracked files or change the git" in result.stdout


def test_default_mode_does_not_run_generation_check(tmp_path: Path):
    repo, env = _make_stubbed_repo(tmp_path)
    before_status = _git_status(repo)
    env["GENERATOR_MODE"] = "failure"

    result = _run_validate_all(repo, env)

    assert result.returncode == 0
    _assert_repo_unchanged(repo, before_status)
    python_log = (tmp_path / "python-invocations.log").read_text(encoding="utf-8")
    assert "yaml_to_markdown.py" not in python_log
    assert not (tmp_path / "git-invocations.log").exists()

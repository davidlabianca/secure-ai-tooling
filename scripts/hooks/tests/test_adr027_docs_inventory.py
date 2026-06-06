"""
Drift guard: assert the ADR-027 validator/hook names appear in their expected doc files.

Pure string-presence assertions — no imports of the validators, no code execution.
If a new ADR-027 validator is added without updating the docs, these tests fail.
"""

from pathlib import Path

# Resolve the repo root from this test file's location:
# scripts/hooks/tests/ -> scripts/hooks/ -> scripts/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

_HOOK_VALIDATIONS = _REPO_ROOT / "scripts" / "docs" / "hook-validations.md"
_SCRIPTS_README = _REPO_ROOT / "scripts" / "README.md"
_VALIDATION_MD = _REPO_ROOT / "risk-map" / "docs" / "validation.md"
_DEVELOPING_MD = _REPO_ROOT / "risk-map" / "docs" / "developing.md"


def _read(path: Path) -> str:
    """Read a file and return its text content."""
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# hook-validations.md assertions
# ---------------------------------------------------------------------------


def test_hook_validations_contains_versionid_generator() -> None:
    """versionid_generator.py and its hook id appear in hook-validations.md."""
    text = _read(_HOOK_VALIDATIONS)
    assert "versionid_generator.py" in text
    assert "regenerate-frameworks-versionid" in text


def test_hook_validations_contains_validate_versionid_purity() -> None:
    """validate_versionid_purity.py and its hook id appear in hook-validations.md."""
    text = _read(_HOOK_VALIDATIONS)
    assert "validate_versionid_purity.py" in text
    assert "validate-frameworks-versionid-purity" in text


def test_hook_validations_contains_validate_mapping_purity() -> None:
    """validate_mapping_purity.py and its hook id appear in hook-validations.md."""
    text = _read(_HOOK_VALIDATIONS)
    assert "validate_mapping_purity.py" in text
    assert "validate-mapping-purity" in text


def test_hook_validations_contains_validate_mapping_drift() -> None:
    """validate_mapping_drift.py and its hook id appear in hook-validations.md."""
    text = _read(_HOOK_VALIDATIONS)
    assert "validate_mapping_drift.py" in text
    assert "validate-mapping-drift" in text


# ---------------------------------------------------------------------------
# scripts/README.md assertions
# ---------------------------------------------------------------------------


def test_scripts_readme_contains_versionid_generator() -> None:
    """versionid_generator.py appears in scripts/README.md Key Files list."""
    assert "versionid_generator.py" in _read(_SCRIPTS_README)


def test_scripts_readme_contains_validate_versionid_purity() -> None:
    """validate_versionid_purity.py appears in scripts/README.md Key Files list."""
    assert "validate_versionid_purity.py" in _read(_SCRIPTS_README)


def test_scripts_readme_contains_validate_mapping_purity() -> None:
    """validate_mapping_purity.py appears in scripts/README.md Key Files list."""
    assert "validate_mapping_purity.py" in _read(_SCRIPTS_README)


def test_scripts_readme_contains_validate_mapping_drift() -> None:
    """validate_mapping_drift.py appears in scripts/README.md Key Files list."""
    assert "validate_mapping_drift.py" in _read(_SCRIPTS_README)


def test_scripts_readme_contains_framework_mapping_maintainer() -> None:
    """framework_mapping_maintainer.py appears in scripts/README.md Key Files list."""
    assert "framework_mapping_maintainer.py" in _read(_SCRIPTS_README)


# ---------------------------------------------------------------------------
# risk-map/docs/developing.md assertions
# ---------------------------------------------------------------------------


def test_developing_md_contains_framework_mapping_maintainer() -> None:
    """framework_mapping_maintainer.py appears in risk-map/docs/developing.md."""
    assert "framework_mapping_maintainer.py" in _read(_DEVELOPING_MD)


# ---------------------------------------------------------------------------
# risk-map/docs/validation.md assertions
# ---------------------------------------------------------------------------


def test_validation_md_contains_versionid_generator() -> None:
    """versionid_generator.py appears in risk-map/docs/validation.md."""
    assert "versionid_generator.py" in _read(_VALIDATION_MD)


def test_validation_md_contains_validate_versionid_purity() -> None:
    """validate_versionid_purity.py appears in risk-map/docs/validation.md."""
    assert "validate_versionid_purity.py" in _read(_VALIDATION_MD)


def test_validation_md_contains_validate_mapping_purity() -> None:
    """validate_mapping_purity.py appears in risk-map/docs/validation.md."""
    assert "validate_mapping_purity.py" in _read(_VALIDATION_MD)


def test_validation_md_contains_validate_mapping_drift() -> None:
    """validate_mapping_drift.py appears in risk-map/docs/validation.md."""
    assert "validate_mapping_drift.py" in _read(_VALIDATION_MD)

#!/usr/bin/env python3
"""
Tests for ADR-027 D4 / D4a / D4b / D3a / D6 / D8 tooling.

(D4c — the mapping-value purity validator — is a separate deliverable tested
alongside its own module; it is intentionally out of scope here.)

Tooling under test:
  - scripts/hooks/precommit/framework_mapping.py
      Shared module: compose_pinned_value, split_pinned_value,
      derive_mapping_id, load_registry, load_pinned_patterns,
      known_versions, exception hierarchy.

  - scripts/framework_mapping_maintainer.py
      CLI with subcommands add / update / remove. Validates --framework
      against the registry, --version against the framework's known
      version set, --framework-specific-ref against the pinned-value
      schema pattern/enum; composes and writes pinned values into a
      consumer YAML file.

Authoritative spec:
  docs/adr/027-framework-versioning-and-mapping-convention.md

D-section citations in every test trace the test's "why" to the ADR.

Test-first: these tests were authored before the production code
(framework_mapping.py, framework_mapping_maintainer.py) existed, so each fails or
errors until those two files land.

Import strategy: import the shared module at the top level — if it raises ImportError
the whole module fails to collect, which is the correct signal for a missing module.
Subprocess CLI tests do not depend on the import succeeding, but they do assert
the script path exists (so a missing-script error is not mistaken for a validator
rejection in negative-case tests).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import jsonschema
import pytest
import yaml

# ---------------------------------------------------------------------------
# Module-level import — fails to collect if the shared module is absent
# ---------------------------------------------------------------------------
# Do NOT use importorskip (that would skip instead of failing). An ImportError
# here makes the whole file fail to collect, which is the right signal when the
# shared module is absent.
from precommit.framework_mapping import (
    DEFAULT_FRAMEWORKS_PATH,
    DEFAULT_SCHEMA_PATH,
    FrameworkMappingError,
    InvalidRefError,
    UnknownFrameworkError,
    UnknownVersionError,
    compose_pinned_value,
    derive_mapping_id,
    known_versions,
    load_pinned_patterns,
    load_registry,
    split_pinned_value,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# REPO_ROOT = scripts/hooks/tests/<this>/../../../..
REPO_ROOT = Path(__file__).parent.parent.parent.parent

FRAMEWORKS_YAML = REPO_ROOT / "risk-map" / "yaml" / "frameworks.yaml"
FRAMEWORKS_SCHEMA = REPO_ROOT / "risk-map" / "schemas" / "frameworks.schema.json"
CLI = REPO_ROOT / "scripts" / "framework_mapping_maintainer.py"

# Real registry and schema — loaded once; tests must NOT mutate these objects.
_REAL_REGISTRY: dict[str, dict] = {}
_REAL_PINNED_PATTERNS: dict[str, dict] = {}


def _get_registry() -> dict[str, dict]:
    """Lazy-load the real registry (read-only)."""
    global _REAL_REGISTRY
    if not _REAL_REGISTRY:
        _REAL_REGISTRY = load_registry(FRAMEWORKS_YAML)
    return _REAL_REGISTRY


def _get_pinned_patterns() -> dict[str, dict]:
    """Lazy-load the real pinned patterns from the schema (read-only)."""
    global _REAL_PINNED_PATTERNS
    if not _REAL_PINNED_PATTERNS:
        _REAL_PINNED_PATTERNS = load_pinned_patterns(FRAMEWORKS_SCHEMA)
    return _REAL_PINNED_PATTERNS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run(
    *args: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    """
    Invoke the CLI under the current Python interpreter.

    Asserts the script exists before invoking so a non-zero exit from a
    missing-script path can never be mistaken for a validator rejection in
    a negative-case test. The TestArtifactsExist class covers existence
    directly; this helper enforces the precondition for every other CLI test.
    """
    assert CLI.is_file(), (
        f"required CLI {CLI.relative_to(REPO_ROOT)} is missing — negative-case "
        "CLI tests would otherwise pass for the wrong reason"
    )
    cmd = [sys.executable, str(CLI), *args]
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
    )


def _write_consumer_fixture(path: Path, content: str) -> None:
    """Write a consumer YAML fixture string to a tmp path."""
    path.write_text(textwrap.dedent(content), encoding="utf-8")


def _load_yaml(path: Path) -> dict:
    """Parse a YAML file and return the root mapping."""
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _make_controls_fixture(tmp_path: Path) -> Path:
    """
    Build a small controls.yaml fixture with 3 entities, comments,
    and pre-existing mappings. Used to test format preservation, order
    preservation, and add/remove/update round-trips.
    """
    dst = tmp_path / "controls.yaml"
    _write_consumer_fixture(
        dst,
        """\
        # Copyright notice preserved
        title: Controls
        description:
          - >
            Test controls fixture for framework_mapping_maintainer tests.
        categories:
          - id: controlsData
            title: Data Controls
        controls:
          - id: controlFoo
            title: Foo Control
            description:
              - Foo description.
            # sibling comment
            category: controlsData
            personas: []
            components: []
            risks: []
            mappings:
              nist-ai-rmf:
                - GOVERN-6.2@1.0
              mitre-atlas:
                - AML.M0007@5.0.1

          - id: controlBar
            title: Bar Control
            description:
              - Bar description.
            category: controlsData
            personas: []
            components: []
            risks: []

          - id: controlBaz
            title: Baz Control
            description:
              - Baz description.
            category: controlsData
            personas: []
            components: []
            risks: []
            mappings:
              mitre-atlas:
                - AML.T0002@5.0.1
        """,
    )
    return dst


def _make_risks_fixture(tmp_path: Path) -> Path:
    """Build a small risks.yaml fixture for entity-not-found and prefix-routing tests."""
    dst = tmp_path / "risks.yaml"
    _write_consumer_fixture(
        dst,
        """\
        title: Risks
        description:
          - Test risks fixture.
        categories:
          - id: risksCategory
            title: Risks
        risks:
          - id: riskFoo
            title: Foo Risk
            description:
              - Foo risk description.
            category: risksCategory
            likelihoods: []
            impacts: []
            personas: []
            components: []
        """,
    )
    return dst


# Synthetic registry with a priorVersions entry — used to test known_versions union.
_SYNTHETIC_REGISTRY_WITH_PRIOR: dict[str, dict] = {
    "mitre-atlas": {
        "version": "6.0.0",
        "priorVersions": ["mitre-atlas@5.0.1"],
    },
    "stride": {
        "version": None,
        "priorVersions": [],
    },
    "nist-ai-rmf": {
        "version": "1.0",
        "priorVersions": [],
    },
}

# ---------------------------------------------------------------------------
# Schema cross-check helpers
# ---------------------------------------------------------------------------


def _validate_against_pinned_subschema(framework_id: str, value: str) -> None:
    """
    Assert that `value` validates against the `framework-mapping-patterns-pinned`
    sub-schema for `framework_id`.

    Uses jsonschema Draft7 — the same $schema the frameworks.schema.json declares.
    This is the schema cross-check test requested by the orchestrator.
    """
    full_schema = json.loads(FRAMEWORKS_SCHEMA.read_text(encoding="utf-8"))
    pinned_block = full_schema["definitions"]["framework-mapping-patterns-pinned"]
    sub_schema = pinned_block["properties"][framework_id]
    jsonschema.validate(instance=value, schema=sub_schema)


# ===========================================================================
# 1. Artifacts exist
# ===========================================================================


class TestArtifactsExist:
    """
    Both the CLI and the shared module must be present at documented paths.

    ADR-027 D4a specifies framework-mapping-maintainer.py as the CLI.
    ADR-027 D4 specifies the generate-not-author contract implemented in
    the shared library.
    """

    def test_cli_script_exists(self):
        """
        The CLI entry-point must exist at scripts/framework_mapping_maintainer.py.

        ADR-027 D4a: contributor workflow requires a runnable maintainer tool.
        """
        assert CLI.is_file(), (
            f"CLI missing at {CLI.relative_to(REPO_ROOT)}; ADR-027 D4a requires framework-mapping-maintainer.py."
        )

    def test_shared_module_exists(self):
        """
        The shared module must exist at scripts/hooks/precommit/framework_mapping.py.

        ADR-027 D4: reusable compose logic is needed by the D4c/D5 validators.
        """
        module_path = REPO_ROOT / "scripts" / "hooks" / "precommit" / "framework_mapping.py"
        assert module_path.is_file(), (
            f"Shared module missing at {module_path.relative_to(REPO_ROOT)}; "
            "ADR-027 D4 requires a reusable compose module."
        )

    def test_shared_module_importable(self):
        """
        The shared module must be importable from the precommit package.

        This test verifies the import at the top of this file succeeded
        (it would have caused a collection error if it failed). If we
        reach here the import is live.
        """
        # If we got here the module-level import succeeded.
        assert FrameworkMappingError is not None
        assert UnknownFrameworkError is not None
        assert UnknownVersionError is not None
        assert InvalidRefError is not None


# ===========================================================================
# 2. compose_pinned_value — happy path per framework
# ===========================================================================


class TestComposePinnedValueHappyPath:
    """
    compose_pinned_value correctly composes pinned values for each framework.

    ADR-027 D3: pinned value = spec-native canonical ref + version token.
    ADR-027 D3a: token is the normalized `version` string verbatim.
    ADR-027 D6: ID-bearing frameworks use `@`; OWASP uses `:`; STRIDE bare.
    ADR-027 D8: ISO 22989 uses closed enum + `@<version>`.
    """

    def test_compose_mitre_atlas_technique(self):
        """
        MITRE ATLAS technique ref + @5.0.1 token.

        ADR-027 D3 / D6: spec-native ref (AML.T0043) + @ + version (5.0.1).
        """
        result = compose_pinned_value(
            "mitre-atlas",
            "5.0.1",
            "AML.T0043",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert result == "AML.T0043@5.0.1"

    def test_compose_mitre_atlas_mitigation(self):
        """
        MITRE ATLAS mitigation ref (M-prefix).

        ADR-027 D3 / D6: mitre-atlas pattern covers both T and M prefixes.
        """
        result = compose_pinned_value(
            "mitre-atlas",
            "5.0.1",
            "AML.M0007",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert result == "AML.M0007@5.0.1"

    def test_compose_nist_ai_rmf(self):
        """
        NIST AI RMF subcategory ref + @1.0 token.

        ADR-027 D3 / D6: GOVERN-6.2 + @ + 1.0 = GOVERN-6.2@1.0.
        """
        result = compose_pinned_value(
            "nist-ai-rmf",
            "1.0",
            "GOVERN-6.2",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert result == "GOVERN-6.2@1.0"

    def test_compose_owasp_top10_llm(self):
        """
        OWASP Top 10 LLM uses `:` delimiter, not `@`.

        ADR-027 D6 / D3: OWASP's year-in-value form LLM06:2025.
        The delimiter is `:` because that is OWASP's upstream-recognizable
        convention retained deliberately (D6).
        """
        result = compose_pinned_value(
            "owasp-top10-llm",
            "2025",
            "LLM06",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert result == "LLM06:2025"

    def test_compose_eu_ai_act(self):
        """
        EU AI Act Article reference + @2024 token.

        ADR-027 D3 / D6: Article 50 + @ + 2024 = Article 50@2024.
        """
        result = compose_pinned_value(
            "eu-ai-act",
            "2024",
            "Article 50",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert result == "Article 50@2024"

    def test_compose_stride_unversioned_bare(self):
        """
        STRIDE is unversioned (version: null); composed value is the bare ref.

        ADR-027 D6: STRIDE carries no version token. `version` arg may be None.
        The value is `Tampering`, not `Tampering@...`.
        """
        result = compose_pinned_value(
            "stride",
            None,
            "Tampering",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert result == "Tampering"

    def test_compose_iso_22989_controlled_vocab(self):
        """
        ISO 22989 uses closed enum + @2022 token.

        ADR-027 D8: ISO 22989 roles are a controlled vocabulary, encoded as
        a closed inline enum. `AI Partner (data supplier)@2022` is the pinned form.
        """
        result = compose_pinned_value(
            "iso-22989",
            "2022",
            "AI Partner (data supplier)",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert result == "AI Partner (data supplier)@2022"

    def test_compose_eu_ai_act_with_subparagraph(self):
        """
        EU AI Act Article with sub-paragraph notation `Article 3(3)@2024`.

        ADR-027 D3 / D6: the pattern ^Article\\s\\d+(\\(\\d+\\))?@(2024)$
        covers both `Article N` and `Article N(n)`.
        """
        result = compose_pinned_value(
            "eu-ai-act",
            "2024",
            "Article 3(3)",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert result == "Article 3(3)@2024"


# ===========================================================================
# 2b. compose_pinned_value — delimiter correctness
# ===========================================================================


class TestComposePinnedValueDelimiter:
    """
    Delimiter is framework-determined: OWASP uses `:`, all others use `@`.

    ADR-027 D3 / D6: "the value-token delimiter (`@` for most, `:` for OWASP)
    does NOT match the versionId delimiter for OWASP."
    Consumers parsing a pinned value must select the delimiter per framework
    (M1 / D3a).
    """

    def test_owasp_uses_colon_delimiter(self):
        """
        OWASP composed value contains `:` not `@`.

        ADR-027 D6: OWASP's `:` delimiter is upstream-recognizable and deliberately
        retained — harmonizing it to `@` would churn the one already-correct framework.
        """
        result = compose_pinned_value(
            "owasp-top10-llm",
            "2025",
            "LLM01",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert ":" in result
        assert "@" not in result

    def test_atlas_uses_at_delimiter(self):
        """
        MITRE ATLAS composed value contains `@` not `:`.

        ADR-027 D3 / D6: every framework except OWASP uses the `@` token.
        """
        result = compose_pinned_value(
            "mitre-atlas",
            "5.0.1",
            "AML.T0043",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert "@" in result
        assert result.count("@") == 1
        assert ":" not in result

    def test_stride_has_no_delimiter(self):
        """
        STRIDE composed value has neither `@` nor `:`.

        ADR-027 D6: STRIDE is unversioned; the value is the bare PascalCase ref.
        """
        result = compose_pinned_value(
            "stride",
            None,
            "Spoofing",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert "@" not in result
        assert ":" not in result
        assert result == "Spoofing"


# ===========================================================================
# 2c. compose_pinned_value — error cases
# ===========================================================================


class TestComposePinnedValueErrors:
    """
    compose_pinned_value raises the correct exception types for invalid input.

    ADR-027 D4a: the tool "(1) validates --framework, (2) validates --version
    against that framework's recognized version set, (3) validates
    --framework-specific-ref against the framework's value constraint."
    """

    def test_unknown_framework_raises_unknown_framework_error(self):
        """
        Bogus framework id raises UnknownFrameworkError (not KeyError or generic).

        ADR-027 D4a step 1: --framework is validated against the frameworks.yaml
        id enum; a value not in that enum is rejected at authoring time.
        """
        with pytest.raises(UnknownFrameworkError):
            compose_pinned_value(
                "not-a-real-framework",
                "1.0",
                "SOME-REF",
                registry=_get_registry(),
                pinned_patterns=_get_pinned_patterns(),
            )

    def test_unknown_version_raises_unknown_version_error(self):
        """
        A --version not in the framework's recognized version set raises
        UnknownVersionError.

        ADR-027 D4a step 2 / D3a: the recognized version set is
        {current version} ∪ {priorVersions members}. Version 9.9.9 is not
        in the MITRE ATLAS recognized set.
        """
        with pytest.raises(UnknownVersionError):
            compose_pinned_value(
                "mitre-atlas",
                "9.9.9",
                "AML.T0043",
                registry=_get_registry(),
                pinned_patterns=_get_pinned_patterns(),
            )

    def test_out_of_vocab_iso_ref_raises_invalid_ref_error(self):
        """
        A misspelled ISO 22989 role not in the closed enum raises InvalidRefError.

        ADR-027 D8: "a --framework-specific-ref not in the closed set is rejected,
        so `AI Part (Data supplier)` cannot be authored."
        """
        with pytest.raises(InvalidRefError):
            compose_pinned_value(
                "iso-22989",
                "2022",
                "AI Part (Data supplier)",  # typo: "Part" not "Partner"
                registry=_get_registry(),
                pinned_patterns=_get_pinned_patterns(),
            )

    def test_malformed_atlas_ref_raises_invalid_ref_error(self):
        """
        A malformed MITRE ATLAS ref that does not match the pattern raises
        InvalidRefError.

        ADR-027 D4a step 3 / D6: spec-native regex `^AML\\.(T|M)\\d{4}(...)?$`
        is applied to the base ref before the version token; `AMLT0043` (missing
        dot) does not match.
        """
        with pytest.raises(InvalidRefError):
            compose_pinned_value(
                "mitre-atlas",
                "5.0.1",
                "AMLT0043",  # malformed: missing `.` after AML
                registry=_get_registry(),
                pinned_patterns=_get_pinned_patterns(),
            )

    def test_versioned_framework_absent_from_pinned_patterns_does_not_crash(self):
        """
        A versioned framework present in the registry but absent from the
        pinned-patterns block must not raise TypeError.

        Scenario: a new framework id is added to frameworks.yaml (and the id
        enum) but the framework-mapping-patterns-pinned block is not yet
        extended, so pinned_patterns.get(id) is None. _try_delimiters must
        guard the None sub_schema (as split_pinned_value already does) rather
        than passing schema=None to jsonschema.validate (TypeError). compose
        then returns its unvalidated default candidate, matching its own
        step-5 None-sub_schema handling.
        """
        synthetic_registry = {
            "ghost-framework": {
                "id": "ghost-framework",
                "version": "1.0",
                "priorVersions": [],
            }
        }
        result = compose_pinned_value(
            "ghost-framework",
            "1.0",
            "SOME-REF",
            registry=synthetic_registry,
            pinned_patterns={},  # no entry for ghost-framework -> sub_schema is None
        )
        assert result == "SOME-REF@1.0"

    def test_error_hierarchy_unknown_framework_is_mapping_error(self):
        """
        UnknownFrameworkError must be a subclass of FrameworkMappingError.

        Required by the public API spec so callers can catch the base type.
        """
        assert issubclass(UnknownFrameworkError, FrameworkMappingError)

    def test_error_hierarchy_unknown_version_is_mapping_error(self):
        """UnknownVersionError must be a subclass of FrameworkMappingError."""
        assert issubclass(UnknownVersionError, FrameworkMappingError)

    def test_error_hierarchy_invalid_ref_is_mapping_error(self):
        """InvalidRefError must be a subclass of FrameworkMappingError."""
        assert issubclass(InvalidRefError, FrameworkMappingError)


# ===========================================================================
# 3. split_pinned_value — round-trips
# ===========================================================================


class TestSplitPinnedValue:
    """
    split_pinned_value correctly recovers (base_ref, version) from pinned values.

    ADR-027 D3a: H3 parse invariant guarantees the delimiter `@` (or `:` for OWASP)
    never appears in the base ref, so splitting cleanly recovers the pair.
    """

    def test_round_trip_mitre_atlas(self):
        """
        split_pinned_value is the inverse of compose_pinned_value for MITRE ATLAS.

        ADR-027 D3a: splitting `AML.T0043@5.0.1` on `@` recovers `AML.T0043`.
        """
        pinned = compose_pinned_value(
            "mitre-atlas",
            "5.0.1",
            "AML.T0043",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        base_ref, version = split_pinned_value(
            "mitre-atlas",
            pinned,
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert base_ref == "AML.T0043"
        assert version == "5.0.1"

    def test_round_trip_nist_ai_rmf(self):
        """
        split_pinned_value round-trip for NIST AI RMF subcategory.

        ADR-027 D3a: `GOVERN-6.2@1.0` splits to (`GOVERN-6.2`, `1.0`).
        """
        pinned = compose_pinned_value(
            "nist-ai-rmf",
            "1.0",
            "GOVERN-6.2",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        base_ref, version = split_pinned_value(
            "nist-ai-rmf",
            pinned,
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert base_ref == "GOVERN-6.2"
        assert version == "1.0"

    def test_round_trip_owasp(self):
        """
        split_pinned_value round-trip for OWASP (`:` delimiter).

        ADR-027 D3 / D6: `LLM06:2025` splits to (`LLM06`, `2025`).
        The consumer must select the `:` delimiter per-framework for OWASP.
        """
        pinned = compose_pinned_value(
            "owasp-top10-llm",
            "2025",
            "LLM06",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        base_ref, version = split_pinned_value(
            "owasp-top10-llm",
            pinned,
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert base_ref == "LLM06"
        assert version == "2025"

    def test_round_trip_eu_ai_act(self):
        """
        split_pinned_value round-trip for EU AI Act.

        ADR-027 D3: `Article 50@2024` splits to (`Article 50`, `2024`).
        The space in `Article 50` must be preserved in the base_ref.
        """
        pinned = compose_pinned_value(
            "eu-ai-act",
            "2024",
            "Article 50",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        base_ref, version = split_pinned_value(
            "eu-ai-act",
            pinned,
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert base_ref == "Article 50"
        assert version == "2024"

    def test_round_trip_iso_22989_with_parens(self):
        """
        split_pinned_value round-trip for ISO 22989 with spaces and parens.

        ADR-027 D3a / D8: H3 invariant — `@` never appears in controlled-vocab
        base values even when they contain spaces and parentheses, so splitting
        on `@` cleanly recovers `AI Partner (data supplier)`.
        """
        pinned = compose_pinned_value(
            "iso-22989",
            "2022",
            "AI Partner (data supplier)",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        base_ref, version = split_pinned_value(
            "iso-22989",
            pinned,
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert base_ref == "AI Partner (data supplier)"
        assert version == "2022"

    def test_stride_returns_none_version(self):
        """
        split_pinned_value for STRIDE returns (ref, None).

        ADR-027 D6: STRIDE is unversioned; the split returns (bare_ref, None).
        """
        base_ref, version = split_pinned_value(
            "stride",
            "Tampering",
            registry=_get_registry(),
            pinned_patterns=_get_pinned_patterns(),
        )
        assert base_ref == "Tampering"
        assert version is None


# ===========================================================================
# 4. derive_mapping_id — determinism, uniqueness, charset, stability
# ===========================================================================


class TestDeriveMappingId:
    """
    derive_mapping_id produces a stable, deterministic SHA-256 hex digest.

    ADR-027 D4b: "join cosai-id|framework-id|pinned-value; SHA-256 hex digest."
    The mappingId is never written to YAML (D4b binding decision).
    """

    def test_deterministic_same_inputs_same_digest(self):
        """
        Calling derive_mapping_id twice with identical inputs returns the same digest.

        ADR-027 D4b: the handle is "deterministically composed from cosai-id +
        framework + pinned-value." Non-determinism would break CLI re-invocations.
        """
        id1 = derive_mapping_id("controlFoo", "mitre-atlas", "AML.T0043@5.0.1")
        id2 = derive_mapping_id("controlFoo", "mitre-atlas", "AML.T0043@5.0.1")
        assert id1 == id2

    def test_different_cosai_id_different_digest(self):
        """
        Different cosai-id with same framework + pinned-value yields different digest.

        ADR-027 D4b: the canonical string `<cosai-id>|<framework-id>|<pinned-value>`
        includes the cosai-id, so distinct entities must not collide.
        """
        id1 = derive_mapping_id("controlFoo", "mitre-atlas", "AML.T0043@5.0.1")
        id2 = derive_mapping_id("controlBar", "mitre-atlas", "AML.T0043@5.0.1")
        assert id1 != id2

    def test_different_framework_different_digest(self):
        """
        Different framework with same cosai-id + value yields different digest.

        ADR-027 D4b: all three tuple components feed into the canonical string.
        """
        id1 = derive_mapping_id("controlFoo", "mitre-atlas", "AML.T0043@5.0.1")
        id2 = derive_mapping_id("controlFoo", "nist-ai-rmf", "AML.T0043@5.0.1")
        assert id1 != id2

    def test_different_pinned_value_different_digest(self):
        """
        Different pinned value with same cosai-id + framework yields different digest.

        ADR-027 D4b: the pinned value (including version token) is part of the
        canonical string so different values within the same (entity, framework)
        pair are distinct.
        """
        id1 = derive_mapping_id("controlFoo", "mitre-atlas", "AML.T0043@5.0.1")
        id2 = derive_mapping_id("controlFoo", "mitre-atlas", "AML.T0043@6.0.0")
        assert id1 != id2

    def test_hex_charset(self):
        """
        derive_mapping_id returns a lowercase hex string (token-safe).

        ADR-027 D4b: "a stable hash (a hex digest) as the handle... token-safe
        regardless of the spaces/parens/@/: in the pinned value."
        """
        mapping_id = derive_mapping_id("controlFoo", "mitre-atlas", "AML.T0043@5.0.1")
        assert re.fullmatch(r"[0-9a-f]+", mapping_id), f"mappingId must be lowercase hex; got {mapping_id!r}"

    def test_stability_with_spaces_and_parens_in_value(self):
        """
        derive_mapping_id is stable for a pinned value containing spaces and parens.

        ADR-027 D4b: the `|` separator is the reserved join character;
        `AI Partner (data supplier)@2022` contains spaces and parens but not `|`,
        so the canonical string `cosai-id|framework|AI Partner (data supplier)@2022`
        is unambiguous.
        """
        mapping_id = derive_mapping_id("personaFoo", "iso-22989", "AI Partner (data supplier)@2022")
        # Must be non-empty hex
        assert re.fullmatch(r"[0-9a-f]+", mapping_id)
        # Repeat call must give same result
        assert derive_mapping_id("personaFoo", "iso-22989", "AI Partner (data supplier)@2022") == mapping_id

    def test_sha256_correctness(self):
        """
        derive_mapping_id uses SHA-256 of the `|`-joined canonical string.

        ADR-027 D4b: "SHA-256 hex digest of cosai-id|framework-id|pinned-value."
        We verify against a known reference digest.
        """
        canonical = "controlFoo|mitre-atlas|AML.T0043@5.0.1"
        expected = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        assert derive_mapping_id("controlFoo", "mitre-atlas", "AML.T0043@5.0.1") == expected


# ===========================================================================
# 5. known_versions — current, empty for unversioned, union with priorVersions
# ===========================================================================


class TestKnownVersions:
    """
    known_versions returns the correct recognized version set for each framework.

    ADR-027 D3a: "the recognized version set is the framework's current version
    plus any priorVersions members."
    ADR-027 D2c: priorVersions members are extracted as version tokens.
    """

    def test_versioned_framework_returns_current_version(self):
        """
        A versioned framework with no priorVersions returns {current version}.

        ADR-027 D3a: recognized set = {current version} when priorVersions is empty.
        """
        versions = known_versions("mitre-atlas", _get_registry())
        assert "5.0.1" in versions

    def test_unversioned_stride_returns_empty_set(self):
        """
        STRIDE (version: null) returns an empty set.

        ADR-027 D3a / D6: STRIDE carries no version token; known_versions
        returns empty set to signal unversioned (no token-based recognition).
        """
        versions = known_versions("stride", _get_registry())
        assert len(versions) == 0

    def test_prior_versions_included_in_known_set(self):
        """
        priorVersions entries contribute their version tokens to the known set.

        ADR-027 D2c / D3a: "the recognized set is the current version PLUS
        priorVersions members." A pin to an old version in priorVersions is
        valid-but-superseded (D5a), not invalid.

        Uses a synthetic registry dict (not the real frameworks.yaml) with a
        priorVersions entry, so we do not need to edit the live file.
        """
        versions = known_versions("mitre-atlas", _SYNTHETIC_REGISTRY_WITH_PRIOR)
        # Current version in synthetic registry is 6.0.0; prior is mitre-atlas@5.0.1
        # The version token extracted from "mitre-atlas@5.0.1" should be "5.0.1"
        assert "6.0.0" in versions
        assert "5.0.1" in versions

    def test_nist_ai_rmf_current_version(self):
        """
        NIST AI RMF returns {1.0} from the real registry.

        ADR-027 D3a: using the real on-disk registry to verify end-to-end.
        """
        versions = known_versions("nist-ai-rmf", _get_registry())
        assert "1.0" in versions

    def test_owasp_current_version(self):
        """
        OWASP Top 10 LLM returns {2025} from the real registry.

        ADR-027 D3a / D6: OWASP version token in the value is `2025`.
        """
        versions = known_versions("owasp-top10-llm", _get_registry())
        assert "2025" in versions


# ===========================================================================
# 6. Schema cross-check: expected pinned values validate against the schema
# ===========================================================================


class TestSchemaCrossCheck:
    """
    Each pinned value composed from spec inputs validates against the
    framework-mapping-patterns-pinned sub-schema.

    ADR-027 D3a: "the anchored alternation is what lets check-jsonschema
    enforce version-known at the schema layer."

    This class is the orchestrator gate: it proves our expected values are
    schema-correct, satisfying D4a step 3 independently of the compose path.
    """

    def test_atlas_pinned_value_validates_against_schema(self):
        """AML.T0043@5.0.1 validates against the pinned mitre-atlas sub-schema (D3a/D7)."""
        _validate_against_pinned_subschema("mitre-atlas", "AML.T0043@5.0.1")

    def test_nist_pinned_value_validates_against_schema(self):
        """GOVERN-6.2@1.0 validates against the pinned nist-ai-rmf sub-schema (D3a/D7)."""
        _validate_against_pinned_subschema("nist-ai-rmf", "GOVERN-6.2@1.0")

    def test_owasp_pinned_value_validates_against_schema(self):
        """LLM06:2025 validates against the pinned owasp-top10-llm sub-schema (D3a/D6)."""
        _validate_against_pinned_subschema("owasp-top10-llm", "LLM06:2025")

    def test_stride_pinned_value_validates_against_schema(self):
        """Tampering validates against the pinned stride sub-schema (D6 / frozen enum)."""
        _validate_against_pinned_subschema("stride", "Tampering")

    def test_eu_ai_act_pinned_value_validates_against_schema(self):
        """Article 50@2024 validates against the pinned eu-ai-act sub-schema (D3a/D7)."""
        _validate_against_pinned_subschema("eu-ai-act", "Article 50@2024")

    def test_iso_22989_pinned_value_validates_against_schema(self):
        """
        AI Partner (data supplier)@2022 validates against the iso-22989 enum (D7/D8).

        ADR-027 D8: the closed inline enum encodes all six ISO 22989:2022 roles
        with their @2022 version token.
        """
        _validate_against_pinned_subschema("iso-22989", "AI Partner (data supplier)@2022")

    def test_iso_22989_all_six_enum_members_validate(self):
        """
        All six ISO 22989:2022 controlled-vocabulary members validate.

        ADR-027 D8: the closed set sourced from ISO/IEC 22989:2022 role taxonomy
        must match exactly the inline enum in the schema.
        """
        members = [
            "AI Producer@2022",
            "AI Customer (application builder)@2022",
            "AI Customer (end user)@2022",
            "AI Partner (data supplier)@2022",
            "AI Partner (infrastructure provider)@2022",
            "AI Partner (tooling provider)@2022",
        ]
        for member in members:
            _validate_against_pinned_subschema("iso-22989", member)

    def test_out_of_vocab_iso_value_fails_schema(self):
        """
        A misspelled ISO 22989 role fails schema validation.

        ADR-027 D8: "a --framework-specific-ref not in the closed set is rejected."
        The schema's closed enum is the enforcement surface.
        """
        with pytest.raises(jsonschema.ValidationError):
            _validate_against_pinned_subschema("iso-22989", "AI Part (Data supplier)@2022")

    def test_atlas_wrong_version_token_fails_schema(self):
        """
        An MITRE ATLAS value with an unrecognized version token fails schema.

        ADR-027 D3a: the anchored alternation only admits the recognized version
        set. `@9.9.9` is not in `(5\\.0\\.1)`.
        """
        with pytest.raises(jsonschema.ValidationError):
            _validate_against_pinned_subschema("mitre-atlas", "AML.T0043@9.9.9")


# ===========================================================================
# 7. load_registry — structure and defaults
# ===========================================================================


class TestLoadRegistry:
    """
    load_registry returns the framework registry indexed by framework id.

    ADR-027 D1 / D2: the registry is the source of truth for known versions.
    """

    def test_load_registry_from_real_file_returns_dict(self):
        """
        load_registry(FRAMEWORKS_YAML) returns a dict keyed by framework id.

        ADR-027 D1: frameworks.yaml is the authoritative registry.
        """
        registry = load_registry(FRAMEWORKS_YAML)
        assert isinstance(registry, dict)
        assert "mitre-atlas" in registry
        assert "stride" in registry

    def test_registry_entry_has_version_and_prior(self):
        """
        Each registry entry exposes `version` and `priorVersions` keys.

        ADR-027 D2 / D3a: load_registry must surface version + priorVersions
        so known_versions and compose_pinned_value can use them.
        """
        registry = load_registry(FRAMEWORKS_YAML)
        entry = registry["mitre-atlas"]
        assert "version" in entry
        assert "priorVersions" in entry

    def test_stride_entry_has_null_version(self):
        """
        STRIDE entry has version == None.

        ADR-027 D6: STRIDE is unversioned (version: null in frameworks.yaml).
        """
        registry = load_registry(FRAMEWORKS_YAML)
        assert registry["stride"]["version"] is None

    def test_default_frameworks_path_points_at_real_file(self):
        """
        DEFAULT_FRAMEWORKS_PATH resolves to the real frameworks.yaml.

        Module must expose a usable default path for callers that do not
        specify --frameworks-file.
        """
        assert DEFAULT_FRAMEWORKS_PATH.is_file(), (
            f"DEFAULT_FRAMEWORKS_PATH {DEFAULT_FRAMEWORKS_PATH!r} does not exist"
        )

    def test_default_schema_path_points_at_real_file(self):
        """
        DEFAULT_SCHEMA_PATH resolves to the real frameworks.schema.json.

        Module must expose a usable default path for callers that do not
        specify --schema-file.
        """
        assert DEFAULT_SCHEMA_PATH.is_file(), f"DEFAULT_SCHEMA_PATH {DEFAULT_SCHEMA_PATH!r} does not exist"


# ===========================================================================
# 8. CLI `add` subcommand
# ===========================================================================


class TestCLIAdd:
    """
    CLI `add` composes a pinned value and appends it to the entity's mappings.

    ADR-027 D4 / D4a: the CLI is the authoring entry-point; contributors
    supply a structured selection; tooling emits the pinned value.
    """

    def test_add_creates_mapping_value_in_entity(self, tmp_path: Path):
        """
        After `add`, the pinned value appears in the entity's mappings block.

        ADR-027 D4a: `add` locates the entity by --cosai-id, creates
        `mappings.<framework>:` if absent, and appends the pinned value.
        """
        fixture = _make_controls_fixture(tmp_path)
        result = _run(
            "add",
            "--cosai-id",
            "controlBar",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert result.returncode == 0, f"add must succeed; stderr=\n{result.stderr}\nstdout=\n{result.stdout}"
        data = _load_yaml(fixture)
        controls = {c["id"]: c for c in data["controls"]}
        assert "mappings" in controls["controlBar"]
        assert "AML.T0043@5.0.1" in controls["controlBar"]["mappings"]["mitre-atlas"]

    def test_add_creates_mappings_key_when_absent(self, tmp_path: Path):
        """
        `add` creates the `mappings:` key when the entity has none.

        ADR-027 D4a: "create `mappings:` and `mappings.<framework>:` if absent."
        `controlBar` in the fixture has no mappings block initially.
        """
        fixture = _make_controls_fixture(tmp_path)
        result = _run(
            "add",
            "--cosai-id",
            "controlBar",
            "--framework",
            "nist-ai-rmf",
            "--version",
            "1.0",
            "--framework-specific-ref",
            "GOVERN-6.2",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert result.returncode == 0
        data = _load_yaml(fixture)
        controls = {c["id"]: c for c in data["controls"]}
        assert "mappings" in controls["controlBar"]
        assert "nist-ai-rmf" in controls["controlBar"]["mappings"]
        assert "GOVERN-6.2@1.0" in controls["controlBar"]["mappings"]["nist-ai-rmf"]

    def test_add_creates_framework_key_when_absent(self, tmp_path: Path):
        """
        `add` creates the framework key inside mappings when absent.

        ADR-027 D4a: `controlFoo` already has mappings but not an owasp-top10-llm key.
        """
        fixture = _make_controls_fixture(tmp_path)
        result = _run(
            "add",
            "--cosai-id",
            "controlFoo",
            "--framework",
            "owasp-top10-llm",
            "--version",
            "2025",
            "--framework-specific-ref",
            "LLM01",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert result.returncode == 0
        data = _load_yaml(fixture)
        controls = {c["id"]: c for c in data["controls"]}
        assert "owasp-top10-llm" in controls["controlFoo"]["mappings"]
        assert "LLM01:2025" in controls["controlFoo"]["mappings"]["owasp-top10-llm"]

    def test_add_is_idempotent(self, tmp_path: Path):
        """
        Re-adding an identical value is a byte-level no-op.

        ADR-027 D4a: "re-adding an identical value is a byte-level no-op."
        This prevents duplicate list entries and commit churn.
        """
        fixture = _make_controls_fixture(tmp_path)
        # First add — should succeed and modify the file.
        _run(
            "add",
            "--cosai-id",
            "controlBar",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        after_first = fixture.read_bytes()

        # Second identical add — must be a no-op.
        result = _run(
            "add",
            "--cosai-id",
            "controlBar",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert result.returncode == 0
        after_second = fixture.read_bytes()
        assert after_second == after_first, "re-adding must leave the file byte-identical (idempotency)"

    def test_add_preserves_sibling_entities(self, tmp_path: Path):
        """
        After `add`, sibling entities are structurally unchanged.

        ADR-027 D4a: writes must preserve YAML structure outside the touched block.
        """
        fixture = _make_controls_fixture(tmp_path)
        original = _load_yaml(fixture)
        baz_before = next(c for c in original["controls"] if c["id"] == "controlBaz")

        _run(
            "add",
            "--cosai-id",
            "controlBar",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )

        reloaded = _load_yaml(fixture)
        baz_after = next(c for c in reloaded["controls"] if c["id"] == "controlBaz")
        assert baz_before == baz_after, "sibling entity must not be modified by add"

    def test_add_preserves_sibling_frameworks_order(self, tmp_path: Path):
        """
        `add` preserves the order of existing framework keys in the mappings block.

        ADR-027 D4a: "preserve existing taxonomy order."
        `controlFoo` has nist-ai-rmf before mitre-atlas in the fixture;
        adding owasp must not reorder the existing keys.
        """
        fixture = _make_controls_fixture(tmp_path)
        _run(
            "add",
            "--cosai-id",
            "controlFoo",
            "--framework",
            "owasp-top10-llm",
            "--version",
            "2025",
            "--framework-specific-ref",
            "LLM06",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        data = _load_yaml(fixture)
        controls = {c["id"]: c for c in data["controls"]}
        keys = list(controls["controlFoo"]["mappings"].keys())
        # nist-ai-rmf and mitre-atlas must appear before owasp-top10-llm
        assert keys.index("nist-ai-rmf") < keys.index("owasp-top10-llm")
        assert keys.index("mitre-atlas") < keys.index("owasp-top10-llm")


# ===========================================================================
# 9. CLI `remove` subcommand
# ===========================================================================


class TestCLIRemove:
    """
    CLI `remove` uses mappingId-addressed removal to delete a pinned value.

    ADR-027 D4a / D4b: `remove` addresses the mapping by (cosai-id, framework,
    version, ref) tuple; internal handle is the derived mappingId.
    """

    def test_remove_round_trip(self, tmp_path: Path):
        """
        add then remove returns the entity to its pre-add state.

        ADR-027 D4 / D4b: remove addresses by tuple (cosai-id, framework,
        version, framework-specific-ref) and deletes the matching entry.
        """
        fixture = _make_controls_fixture(tmp_path)
        before_bytes = fixture.read_bytes()

        # Add first.
        add_result = _run(
            "add",
            "--cosai-id",
            "controlBar",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert add_result.returncode == 0

        # Remove what we just added.
        remove_result = _run(
            "remove",
            "--cosai-id",
            "controlBar",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert remove_result.returncode == 0, f"remove must succeed; stderr=\n{remove_result.stderr}"

        after_bytes = fixture.read_bytes()
        # The file should be back to its pre-add state. This requires remove to
        # delete the now-empty framework key AND the now-empty `mappings:` block
        # (the entity had no mappings before add), with no ruamel reflow drift.
        assert after_bytes == before_bytes, "add+remove must return the file to its prior byte state"

    def test_remove_nonexistent_value_exits_nonzero(self, tmp_path: Path):
        """
        Removing a value that is not present exits non-zero with a diagnostic.

        ADR-027 D4a: "If no match → exit non-zero with diagnostic."
        """
        fixture = _make_controls_fixture(tmp_path)
        result = _run(
            "remove",
            "--cosai-id",
            "controlBar",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert result.returncode != 0
        # A non-zero exit must carry a diagnostic so a bare crash (no output)
        # cannot masquerade as a clean "not found" rejection.
        assert (result.stderr + result.stdout).strip(), "must emit a diagnostic message"

    def test_remove_empties_framework_key_removes_key(self, tmp_path: Path):
        """
        When remove empties a framework's list, the framework key is deleted.

        ADR-027 D4a: "If list becomes empty, remove the framework key."
        `controlBaz` has exactly one mitre-atlas value in the fixture.
        """
        fixture = _make_controls_fixture(tmp_path)
        remove_result = _run(
            "remove",
            "--cosai-id",
            "controlBaz",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AML.T0002",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert remove_result.returncode == 0, f"remove must succeed; stderr=\n{remove_result.stderr}"
        data = _load_yaml(fixture)
        controls = {c["id"]: c for c in data["controls"]}
        # mappings block may be absent or present but without mitre-atlas
        mappings = controls["controlBaz"].get("mappings", {})
        assert "mitre-atlas" not in mappings, "an emptied framework key must be removed from the mappings block"


# ===========================================================================
# 10. CLI `update` subcommand (re-pin semantic)
# ===========================================================================


class TestCLIUpdate:
    """
    CLI `update` re-pins a mapping: finds an existing entry by base-ref and
    replaces it with a new pinned value composed from --version.

    NOTE (spec ambiguity): the ADR (D4a) specifies add/remove verbs with
    explicit tuple-addressing, but does not detail the update verb's resolution
    logic beyond "update ... addresses by tuple." The interpretation tested here
    is:
      - `update` locates the existing entry whose base-ref (via split_pinned_value)
        matches --framework-specific-ref, then replaces it with
        compose_pinned_value(framework, --version, --ref).
      - "nothing to update" (no base-ref match) → exit non-zero.
      - "ambiguous" (multiple base-ref matches, different version tokens) → exit
        non-zero.
    This is the re-pin interpretation. Tests are labeled to flag this.

    ADR-027 D4 / D4a / D4b: re-pin semantic (maintainer interpretation).
    """

    def _fixture_with_old_version(self, tmp_path: Path) -> Path:
        """
        Build a controls fixture that declares a prior version of atlas to re-pin.

        We use a synthetic frameworks.yaml + schema for this test so we can
        declare a priorVersions entry without editing the live files.
        """
        # Synthetic frameworks.yaml with mitre-atlas having version 6.0.0
        # and priorVersions: [mitre-atlas@5.0.1]
        fw_yaml = tmp_path / "frameworks_with_prior.yaml"
        fw_yaml.write_text(
            textwrap.dedent(
                """\
                title: Frameworks
                description:
                  - test
                frameworks:
                  - id: mitre-atlas
                    name: MITRE ATLAS
                    fullName: MITRE ATLAS Full
                    description: desc
                    baseUri: https://atlas.mitre.org
                    version: '6.0.0'
                    versionId: mitre-atlas@6.0.0
                    priorVersions:
                      - mitre-atlas@5.0.1
                    applicableTo:
                      - controls
                      - risks
                """
            ),
            encoding="utf-8",
        )
        return fw_yaml

    def _synthetic_schema(self, tmp_path: Path) -> Path:
        """
        Build a minimal frameworks.schema.json that admits both 5.0.1 and 6.0.0.
        """
        import json

        schema_path = tmp_path / "frameworks_update.schema.json"
        schema = {
            "$id": "frameworks_update.schema.json",
            "$schema": "http://json-schema.org/draft-07/schema#",
            "definitions": {
                "framework-mapping-patterns-pinned": {
                    "type": "object",
                    "properties": {
                        "mitre-atlas": {
                            "type": "string",
                            "pattern": r"^AML\.(T|M)\d{4}(\.\d{3})?@(5\.0\.1|6\.0\.0)$",
                        }
                    },
                }
            },
        }
        schema_path.write_text(json.dumps(schema), encoding="utf-8")
        return schema_path

    def test_update_repin_changes_version_token(self, tmp_path: Path):
        """
        `update` replaces a 5.0.1-pinned value with a 6.0.0-pinned value in place.

        ADR-027 D4 re-pin interpretation: `update` finds the existing entry by
        base-ref and replaces its version token. The value count for the framework
        key stays the same (replace, not append).
        """
        fw_yaml = self._fixture_with_old_version(tmp_path)
        schema_path = self._synthetic_schema(tmp_path)

        fixture = tmp_path / "controls.yaml"
        _write_consumer_fixture(
            fixture,
            """\
            title: Controls
            description:
              - Test update fixture.
            controls:
              - id: controlFoo
                title: Foo
                description:
                  - desc
                mappings:
                  mitre-atlas:
                    - AML.T0043@5.0.1
            """,
        )

        result = _run(
            "update",
            "--cosai-id",
            "controlFoo",
            "--framework",
            "mitre-atlas",
            "--version",
            "6.0.0",
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(fw_yaml),
            "--schema-file",
            str(schema_path),
        )
        assert result.returncode == 0, f"update must succeed on a valid re-pin; stderr=\n{result.stderr}"
        data = _load_yaml(fixture)
        atlas_values = data["controls"][0]["mappings"]["mitre-atlas"]
        assert "AML.T0043@6.0.0" in atlas_values
        assert "AML.T0043@5.0.1" not in atlas_values

    def test_update_nothing_to_update_exits_nonzero(self, tmp_path: Path):
        """
        `update` exits non-zero when no existing base-ref matches --framework-specific-ref.

        ADR-027 D4 re-pin interpretation: "nothing to update" error path.
        """
        fixture = _make_controls_fixture(tmp_path)
        result = _run(
            "update",
            "--cosai-id",
            "controlBar",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AML.T9999",  # no such entry in fixture
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert result.returncode != 0
        # Diagnostic must appear in stderr or stdout.
        combined = result.stderr + result.stdout
        assert combined.strip(), "non-zero exit must produce a diagnostic message"

    def test_update_ambiguous_exits_nonzero(self, tmp_path: Path):
        """
        `update` exits non-zero when multiple entries share the same base-ref.

        ADR-027 D4 re-pin interpretation: "ambiguous" error path — two entries
        with the same base-ref but different version tokens (multi-version
        coexistence during a migration window, D3) are ambiguous for a base-ref
        search; the caller must remove+add to disambiguate.
        """
        fw_yaml = self._fixture_with_old_version(tmp_path)
        schema_path = self._synthetic_schema(tmp_path)

        fixture = tmp_path / "controls_ambiguous.yaml"
        _write_consumer_fixture(
            fixture,
            """\
            title: Controls
            description:
              - Ambiguous update fixture.
            controls:
              - id: controlFoo
                title: Foo
                description:
                  - desc
                mappings:
                  mitre-atlas:
                    - AML.T0043@5.0.1
                    - AML.T0043@6.0.0
            """,
        )

        result = _run(
            "update",
            "--cosai-id",
            "controlFoo",
            "--framework",
            "mitre-atlas",
            "--version",
            "6.0.0",
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(fw_yaml),
            "--schema-file",
            str(schema_path),
        )
        assert result.returncode != 0, (
            "update must exit non-zero when multiple entries share the same base-ref (ambiguous)"
        )
        # The ambiguity must be reported, not silently swallowed by a bare exit.
        assert (result.stderr + result.stdout).strip(), "must emit a diagnostic message"


# ===========================================================================
# 11. CLI rejection cases — validation failures
# ===========================================================================


class TestCLIRejectionCases:
    """
    The CLI exits non-zero with a stderr diagnostic for all validation failures.

    ADR-027 D4a: "(1) validates --framework, (2) validates --version,
    (3) validates --framework-specific-ref."
    """

    def test_unknown_framework_exits_nonzero(self, tmp_path: Path):
        """
        --framework not in frameworks.yaml id enum → non-zero exit + diagnostic.

        ADR-027 D4a step 1: framework must be validated against the id enum.
        """
        fixture = _make_controls_fixture(tmp_path)
        result = _run(
            "add",
            "--cosai-id",
            "controlBar",
            "--framework",
            "not-a-framework",
            "--version",
            "1.0",
            "--framework-specific-ref",
            "SOME-REF",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert result.returncode != 0
        assert result.stderr.strip(), "must emit a diagnostic to stderr"

    def test_unknown_version_exits_nonzero(self, tmp_path: Path):
        """
        --version not in the framework's recognized version set → non-zero exit.

        ADR-027 D4a step 2: version is rejected at authoring time,
        the earliest possible point.
        """
        fixture = _make_controls_fixture(tmp_path)
        result = _run(
            "add",
            "--cosai-id",
            "controlBar",
            "--framework",
            "mitre-atlas",
            "--version",
            "9.9.9",  # not a recognized version
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert result.returncode != 0
        assert result.stderr.strip()

    def test_out_of_vocab_iso_ref_exits_nonzero(self, tmp_path: Path):
        """
        A --framework-specific-ref outside the ISO 22989 closed enum → non-zero exit.

        ADR-027 D8: "`AI Part (Data supplier)` cannot be authored" — the CLI
        must reject out-of-vocab ISO refs at step 3.
        """
        fixture = _make_controls_fixture(tmp_path)
        result = _run(
            "add",
            "--cosai-id",
            "controlBar",
            "--framework",
            "iso-22989",
            "--version",
            "2022",
            "--framework-specific-ref",
            "AI Part (Data supplier)",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert result.returncode != 0
        assert result.stderr.strip()

    def test_entity_not_found_exits_nonzero(self, tmp_path: Path):
        """
        --cosai-id that does not exist in the content file → non-zero exit.

        ADR-027 D4a: the tool must locate the entity by --cosai-id; if absent,
        it is a validation failure not a silent create.
        """
        fixture = _make_controls_fixture(tmp_path)
        result = _run(
            "add",
            "--cosai-id",
            "controlDoesNotExist",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert result.returncode != 0
        assert result.stderr.strip()

    def test_malformed_atlas_ref_exits_nonzero(self, tmp_path: Path):
        """
        A malformed MITRE ATLAS ref (pattern mismatch) → non-zero exit.

        ADR-027 D4a step 3: spec-native regex rejects `AMLT0043` (missing dot).
        """
        fixture = _make_controls_fixture(tmp_path)
        result = _run(
            "add",
            "--cosai-id",
            "controlBar",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AMLT0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert result.returncode != 0
        assert result.stderr.strip()


# ===========================================================================
# 12. Format preservation
# ===========================================================================


class TestFormatPreservation:
    """
    After an `add`, comments and sibling content outside the touched block survive.

    ADR-027 D4: "writes must preserve YAML formatting/comments (e.g. via
    ruamel.yaml)." A full yaml.dump round-trip would destroy comments; the
    implementation must do surgical insertion.
    """

    def test_comment_lines_survive_add(self, tmp_path: Path):
        """
        Comments present in the fixture file survive an `add` operation.

        ADR-027 D4: the implementation must preserve formatting/comments.
        """
        fixture = _make_controls_fixture(tmp_path)
        original_text = fixture.read_text(encoding="utf-8")
        original_comment_lines = [line for line in original_text.splitlines() if line.lstrip().startswith("#")]
        assert original_comment_lines, "fixture must contain comments for this test to be meaningful"

        _run(
            "add",
            "--cosai-id",
            "controlBar",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )

        rewritten_text = fixture.read_text(encoding="utf-8")
        rewritten_comment_lines = [line for line in rewritten_text.splitlines() if line.lstrip().startswith("#")]
        missing = [c for c in original_comment_lines if c not in rewritten_comment_lines]
        assert not missing, "all comment lines must survive an add; missing:\n" + "\n".join(missing)

    def test_file_parses_as_valid_yaml_after_add(self, tmp_path: Path):
        """
        The file is still valid YAML after an `add` operation.

        ADR-027 D4: the output must be parseable by PyYAML.
        """
        fixture = _make_controls_fixture(tmp_path)
        result = _run(
            "add",
            "--cosai-id",
            "controlBaz",
            "--framework",
            "nist-ai-rmf",
            "--version",
            "1.0",
            "--framework-specific-ref",
            "MAP-2.1",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )
        assert result.returncode == 0
        try:
            data = _load_yaml(fixture)
        except yaml.YAMLError as exc:
            pytest.fail(f"file is not valid YAML after add: {exc}")
        assert "controls" in data

    def test_expected_structure_intact_after_add(self, tmp_path: Path):
        """
        All original entities and top-level keys survive an `add`.

        ADR-027 D4: non-target content must be preserved.
        """
        fixture = _make_controls_fixture(tmp_path)
        original = _load_yaml(fixture)
        original_ids = {c["id"] for c in original["controls"]}

        _run(
            "add",
            "--cosai-id",
            "controlBar",
            "--framework",
            "mitre-atlas",
            "--version",
            "5.0.1",
            "--framework-specific-ref",
            "AML.T0043",
            "--content-file",
            str(fixture),
            "--frameworks-file",
            str(FRAMEWORKS_YAML),
            "--schema-file",
            str(FRAMEWORKS_SCHEMA),
        )

        reloaded = _load_yaml(fixture)
        reloaded_ids = {c["id"] for c in reloaded["controls"]}
        assert reloaded_ids == original_ids, "no entities must be added or removed by add"
        # Top-level keys preserved
        assert set(reloaded.keys()) == set(original.keys())


# ===========================================================================
# Test Summary
# ===========================================================================
#
# Total Tests: 73
# - Artifacts exist:                    3
# - compose_pinned_value happy path:    8
# - compose delimiter correctness:      3
# - compose error cases:                5 (+ 3 hierarchy checks)
# - split_pinned_value:                 6
# - derive_mapping_id:                  7
# - known_versions:                     5
# - Schema cross-check:                 9
# - load_registry / defaults:           5
# - CLI add:                            6
# - CLI remove:                         3
# - CLI update (re-pin interpretation): 3
# - CLI rejection cases:                5
# - Format preservation:                3
#
# Coverage areas:
# - compose_pinned_value (all 6 current frameworks + delimiter + errors)
# - split_pinned_value round-trips (all 6 frameworks)
# - derive_mapping_id (determinism, uniqueness, charset, SHA-256 correctness)
# - known_versions (versioned, unversioned, priorVersions union)
# - Schema cross-check (all 6 frameworks; happy + rejection)
# - load_registry / DEFAULT_* paths
# - CLI add (round-trip, create mappings, create framework key, idempotency,
#            sibling preservation, order preservation)
# - CLI remove (round-trip, missing-value error, empty-list key removal)
# - CLI update (re-pin semantic — labeled as interpretation of under-specified ADR point;
#               nothing-to-update error; ambiguous error)
# - CLI rejection (unknown framework, unknown version, out-of-vocab ISO,
#                  entity-not-found, malformed ref)
# - Format preservation (comment survival, YAML validity, structure intact)
#
# Spec ambiguity noted: the `update` verb's resolution logic is not fully
# specified in ADR-027 D4a. The tests implement and test the "re-pin by
# base-ref match" interpretation (find existing entry by split_pinned_value
# base-ref == --framework-specific-ref; replace its version token). Error
# paths (nothing-to-update, ambiguous) are tested as sentinel contracts.
# The implementation may use a slightly different update semantic but must satisfy
# at minimum the round-trip (old token replaced by new token) and the two
# error paths.

#!/usr/bin/env python3
"""
Tests for the ADR-027 D4c mapping-value purity validator.

Tooling under test:
  scripts/hooks/precommit/validate_mapping_purity.py

  Exposes:
    classify_value(fw_id, value, *, registry, pinned_patterns) -> tuple[str, str|None]
      Returns (status, detail) where status is one of "ok", "skip", or "fail".

    main(argv: list[str]) -> int
      Returns 0 on success, 1 if any purity failure is found.
      Positional args are file paths to validate (risks/controls/components/personas).
      Defaults to the four standard content files when no paths given.

Authoritative spec: docs/adr/027-framework-versioning-and-mapping-convention.md

Classification contract (D4c / D3a):
  For a value `v` under framework key `fw`:
  1. If `fw` is not in the registry → FAIL (fail-loud; unknown mapping key).
  2. Let is_versioned = registry[fw]["version"] is not None.
  3. Versioned AND `v` contains neither `@` nor `:` → SKIP (legacy unpinned form,
     e.g. AML.T0020, GV-6.2, LLM06). Migration is #343, not #347.
  4. Otherwise attempt split_pinned_value + compose_pinned_value round-trip:
     - FrameworkMappingError raised AND versioned → FAIL (tampered pinned value).
     - FrameworkMappingError raised AND unversioned → SKIP (legacy STRIDE spelling).
     - recomposed != v → FAIL (round-trip mismatch = tamper).
     - recomposed == v → OK.

  The `@`/`:` delimiter presence test (step 3) is the sole signal distinguishing
  a legacy unpinned value from a tampered pinned value. This is justified by
  D3a / H3: the `@` and `:` delimiters never appear in any legacy base ref or
  concept id, so their presence in a value is an unambiguous "this was intended
  as a pinned value" signal.

The LIVE CORPUS test asserts that all four content files produce zero purity
failures today. Every value in the current corpus is a legacy pre-ADR-027 form
(no `@` or `:` in versioned framework values; bare PascalCase/lowercase for
STRIDE). The validator must skip them all — migration to pinned forms is #343.

Import strategy: import validate_mapping_purity at module level so an ImportError
causes a collection-time ImportError until the module exists — the correct
signal that the production module has not yet been created.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

# ---------------------------------------------------------------------------
# Module-level imports — the validate_mapping_purity import raises
# ModuleNotFoundError at collection time, failing the entire file,
# until that module is created.
# ---------------------------------------------------------------------------
from precommit.framework_mapping import load_pinned_patterns, load_registry
from precommit.validate_mapping_purity import classify_value, main

# ---------------------------------------------------------------------------
# Paths and shared fixtures
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent.parent.parent

FRAMEWORKS_YAML = REPO_ROOT / "risk-map" / "yaml" / "frameworks.yaml"
FRAMEWORKS_SCHEMA = REPO_ROOT / "risk-map" / "schemas" / "frameworks.schema.json"

RISKS_YAML = REPO_ROOT / "risk-map" / "yaml" / "risks.yaml"
CONTROLS_YAML = REPO_ROOT / "risk-map" / "yaml" / "controls.yaml"
COMPONENTS_YAML = REPO_ROOT / "risk-map" / "yaml" / "components.yaml"
PERSONAS_YAML = REPO_ROOT / "risk-map" / "yaml" / "personas.yaml"

_REAL_REGISTRY: dict = {}
_REAL_PINNED_PATTERNS: dict = {}


def _registry() -> dict:
    """Lazy-load the real registry (read-only across all tests)."""
    global _REAL_REGISTRY
    if not _REAL_REGISTRY:
        _REAL_REGISTRY = load_registry(FRAMEWORKS_YAML)
    return _REAL_REGISTRY


def _pinned() -> dict:
    """Lazy-load the real pinned patterns (read-only across all tests)."""
    global _REAL_PINNED_PATTERNS
    if not _REAL_PINNED_PATTERNS:
        _REAL_PINNED_PATTERNS = load_pinned_patterns(FRAMEWORKS_SCHEMA)
    return _REAL_PINNED_PATTERNS


# ---------------------------------------------------------------------------
# Helper: build a minimal cosai content YAML tmp file
# ---------------------------------------------------------------------------


def _write_content_yaml(path: Path, entity_type: str, entities: list[dict]) -> None:
    """
    Write a minimal cosai content YAML to `path`.

    `entity_type` is the plural list key: "risks", "controls", "components",
    or "personas". Each entity dict must include at minimum "id" and, if
    relevant, "mappings".
    """
    content = {entity_type: entities}
    path.write_text(yaml.dump(content, default_flow_style=False, sort_keys=False), encoding="utf-8")


# ===========================================================================
# 1. classify_value — OK cases (well-formed pinned values, one per framework)
# ===========================================================================


class TestClassifyValueOK:
    """
    classify_value returns ("ok", ...) for each of the six correctly-pinned
    ground-truth examples. These values were generated by the D4 tool with the
    correct version token and delimiter (D3a/D6) and round-trip cleanly.
    """

    def test_mitre_atlas_pinned_technique(self):
        """
        Given: a correctly-pinned MITRE ATLAS technique value `AML.T0043@5.0.1`
        When: classify_value is called
        Then: status is "ok"

        D3a: `@` delimiter, version token `5.0.1` in registry; D4c round-trip passes.
        """
        status, _ = classify_value(
            "mitre-atlas",
            "AML.T0043@5.0.1",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "ok"

    def test_nist_ai_rmf_pinned_subcategory(self):
        """
        Given: a correctly-pinned NIST AI RMF subcategory `GOVERN-6.2@1.0`
        When: classify_value is called
        Then: status is "ok"

        D3a: `@` delimiter, version `1.0` in registry; D4c round-trip passes.
        """
        status, _ = classify_value(
            "nist-ai-rmf",
            "GOVERN-6.2@1.0",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "ok"

    def test_owasp_top10_llm_pinned_entry(self):
        """
        Given: a correctly-pinned OWASP LLM Top 10 entry `LLM02:2025`
        When: classify_value is called
        Then: status is "ok"

        D3a/D6/M1: `:` delimiter for OWASP (framework-determined); year `2025` in registry.
        """
        status, _ = classify_value(
            "owasp-top10-llm",
            "LLM02:2025",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "ok"

    def test_stride_pinned_pascalcase(self):
        """
        Given: STRIDE value `Tampering` in canonical PascalCase
        When: classify_value is called
        Then: status is "ok"

        D6: STRIDE is unversioned (version: null). Bare PascalCase is the closed
        enum from D5b; "pinned by enum rather than by token" (ADR-027 §D6 note).
        No delimiter check applies (step 3 guard only fires for versioned frameworks).
        """
        status, _ = classify_value(
            "stride",
            "Tampering",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "ok"

    def test_iso_22989_pinned_role(self):
        """
        Given: correctly-pinned ISO 22989 role `AI Producer@2022`
        When: classify_value is called
        Then: status is "ok"

        D8: controlled-vocab enum for ISO 22989; `@` delimiter; version `2022`
        in registry. The role is in the closed version-pinned enum.
        """
        status, _ = classify_value(
            "iso-22989",
            "AI Producer@2022",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "ok"

    def test_eu_ai_act_pinned_article(self):
        """
        Given: correctly-pinned EU AI Act article reference `Article 50@2024`
        When: classify_value is called
        Then: status is "ok"

        D3a: `@` delimiter, version `2024` in registry; D4c round-trip passes.
        """
        status, _ = classify_value(
            "eu-ai-act",
            "Article 50@2024",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "ok"


# ===========================================================================
# 2. classify_value — SKIP cases (legacy pre-ADR-027 forms, must not fail)
# ===========================================================================


class TestClassifyValueSkip:
    """
    classify_value returns ("skip", ...) for all legacy pre-ADR-027 values.

    The skip decision rests on the delimiter-presence test (D3a / H3):
    for versioned frameworks, a value lacking both `@` and `:` is a legacy
    unpinned form. Migrating these values is #343, not #347.

    For the unversioned STRIDE framework, a FrameworkMappingError from
    split_pinned_value (e.g., a value not in the closed PascalCase enum)
    maps to skip rather than fail because there is no version token to
    indicate tampering intent.
    """

    def test_mitre_atlas_legacy_no_version_token(self):
        """
        Given: legacy MITRE ATLAS value `AML.T0020` (no `@` delimiter)
        When: classify_value is called
        Then: status is "skip" (legacy unpinned form; D3a / H3 delimiter absence)
        """
        status, _ = classify_value(
            "mitre-atlas",
            "AML.T0020",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "skip"

    def test_mitre_atlas_legacy_control_form(self):
        """
        Given: legacy MITRE ATLAS mitigation `AML.M0007` (no `@` delimiter)
        When: classify_value is called
        Then: status is "skip"

        Real value from risk-map/yaml/controls.yaml. No version token present.
        """
        status, _ = classify_value(
            "mitre-atlas",
            "AML.M0007",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "skip"

    def test_nist_short_legacy_form(self):
        """
        Given: legacy NIST AI RMF subcategory `GV-6.2` (short `GV-` prefix, no `@`)
        When: classify_value is called
        Then: status is "skip"

        Real value from risk-map/yaml/controls.yaml. The canonical pinned form
        would be `GOVERN-6.2@1.0`; migration to that form is #343.
        D3a: no `@` or `:` → legacy.
        """
        status, _ = classify_value(
            "nist-ai-rmf",
            "GV-6.2",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "skip"

    def test_owasp_legacy_unversioned(self):
        """
        Given: legacy OWASP value `LLM06` (no `:` delimiter, no year)
        When: classify_value is called
        Then: status is "skip"

        Real value from risk-map/yaml/risks.yaml. The canonical pinned form
        would be `LLM06:2025`; migration is #343. D3a: no `:` → legacy.
        """
        status, _ = classify_value(
            "owasp-top10-llm",
            "LLM06",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "skip"

    def test_stride_lowercase_kebab(self):
        """
        Given: legacy STRIDE value `tampering` (lowercase, not PascalCase)
        When: classify_value is called
        Then: status is "skip"

        STRIDE is unversioned (version: null). `tampering` is not in the
        closed PascalCase enum so split/compose raises FrameworkMappingError.
        Because the framework is unversioned, the classification rule (step 4)
        maps this to "skip" rather than "fail" — no version token can signal
        tampering for an unversioned framework. Real value in risks.yaml.
        """
        status, _ = classify_value(
            "stride",
            "tampering",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "skip"

    def test_stride_kebab_denial_of_service(self):
        """
        Given: legacy STRIDE value `denial-of-service` (kebab, not PascalCase)
        When: classify_value is called
        Then: status is "skip"

        Same rationale as `tampering` above — unversioned framework, value not
        in closed PascalCase enum, no delimiter → skip not fail.
        """
        status, _ = classify_value(
            "stride",
            "denial-of-service",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "skip"

    def test_iso_22989_bare_role_no_delimiter(self):
        """
        Given: legacy ISO 22989 role `AI Producer` (no `@` delimiter, no version)
        When: classify_value is called
        Then: status is "skip"

        Real value from risk-map/yaml/personas.yaml. The canonical pinned form
        is `AI Producer@2022`. D3a / H3: no `@` present → legacy unpinned form.
        """
        status, _ = classify_value(
            "iso-22989",
            "AI Producer",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "skip"

    def test_iso_22989_bare_role_data_supplier_no_delimiter(self):
        """
        Given: legacy ISO 22989 role `AI Partner (data supplier)` (no `@`)
        When: classify_value is called
        Then: status is "skip"

        Real value from personas.yaml. H3 guarantees `@` absence in any base
        ref, so no delimiter → legacy form → skip.
        """
        status, _ = classify_value(
            "iso-22989",
            "AI Partner (data supplier)",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "skip"

    def test_eu_ai_act_legacy_no_version_token(self):
        """
        Given: legacy EU AI Act reference `Article 52` (no `@` delimiter)
        When: classify_value is called
        Then: status is "skip" (legacy unpinned form; D3a / H3 delimiter absence)

        D3a: eu-ai-act is versioned (version: `2024`). A value without `@` or `:`
        lacks the delimiter signal that H3 defines as the sole pinned-intent marker.
        The canonical pinned form would be `Article 52@2024`; migration is #343.
        """
        status, _ = classify_value(
            "eu-ai-act",
            "Article 52",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "skip"


# ===========================================================================
# 3. classify_value — FAIL cases (tampered pinned values)
# ===========================================================================


class TestClassifyValueFail:
    """
    classify_value returns ("fail", ...) for tampered pinned values.

    Tamper signals (D4c):
    - A delimiter-bearing versioned value that won't round-trip (unknown version,
      malformed token, wrong delimiter, out-of-vocab base ref).
    - Rationale: the delimiter's presence (H3 invariant, D3a) signals this was
      *intended* as a pinned value, so failure to round-trip means tampering.
    """

    def test_nist_unknown_version_token(self):
        """
        Given: `GOVERN-6.2@9.9` where `9.9` is not in nist-ai-rmf's known versions
        When: classify_value is called
        Then: status is "fail" and detail contains the unknown version string

        The `@` signals a pinned-value intent. Version `9.9` is not in the
        registry's recognized version set → cannot round-trip → tamper (D4c).
        The detail string must be non-None and must reference the bad token `9.9`
        so the contributor can identify what is wrong.
        """
        status, detail = classify_value(
            "nist-ai-rmf",
            "GOVERN-6.2@9.9",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "fail"
        assert detail is not None and "9.9" in detail

    def test_nist_empty_version_token(self):
        """
        Given: `GOVERN-6.2@` (delimiter present, empty version token)
        When: classify_value is called
        Then: status is "fail"

        Malformed token — empty right-hand side of the `@` split. The delimiter
        presence signals pinned intent; the malformed token means it cannot
        round-trip (D4c).
        """
        status, _ = classify_value(
            "nist-ai-rmf",
            "GOVERN-6.2@",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "fail"

    def test_nist_wrong_delimiter_colon(self):
        """
        Given: `GOVERN-6.2:1.0` (uses `:` instead of `@` for nist-ai-rmf)
        When: classify_value is called
        Then: status is "fail"

        D6/M1: the framework-determined delimiter for nist-ai-rmf is `@`, not `:`.
        A `:` is present (signaling pinned intent per H3) but the value does not
        round-trip against the schema → tamper.
        """
        status, _ = classify_value(
            "nist-ai-rmf",
            "GOVERN-6.2:1.0",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "fail"

    def test_iso_unknown_version_token(self):
        """
        Given: `AI Producer@9999` where `9999` is not in iso-22989's known versions
        When: classify_value is called
        Then: status is "fail"

        `@` present → pinned intent. Version `9999` not recognized → tamper (D4c).
        """
        status, _ = classify_value(
            "iso-22989",
            "AI Producer@9999",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "fail"

    def test_iso_out_of_vocab_base_with_known_version(self):
        """
        Given: `AI Part (data supplier)@2022` — truncated role name, valid version
        When: classify_value is called
        Then: status is "fail"

        `@` present and `2022` is in the registry → the split succeeds with a
        recognized version token, but `AI Part (data supplier)` is not in the
        closed controlled-vocab enum for iso-22989@2022 (D8). The compose step
        will raise InvalidRefError → fail (D4c). The maintainer CLI (D4) would
        have rejected this at authoring time; it must also fail the purity check.
        """
        status, _ = classify_value(
            "iso-22989",
            "AI Part (data supplier)@2022",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "fail"

    def test_mitre_atlas_bad_version_token(self):
        """
        Given: `AML.T0043@5.0.1.0` — extra trailing segment in the version token
        When: classify_value is called
        Then: status is "fail"

        `5.0.1.0` is not in mitre-atlas's known version set → version unknown →
        round-trip fails → tamper (D4c).
        """
        status, _ = classify_value(
            "mitre-atlas",
            "AML.T0043@5.0.1.0",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "fail"

    def test_owasp_unknown_year_token(self):
        """
        Given: `LLM02:2099` — unknown year in the version token
        When: classify_value is called
        Then: status is "fail"

        `:` present → pinned intent. Year `2099` not in owasp-top10-llm's known
        versions → cannot round-trip → tamper (D4c).
        """
        status, _ = classify_value(
            "owasp-top10-llm",
            "LLM02:2099",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "fail"

    def test_eu_ai_act_unknown_version_token(self):
        """
        Given: `Article 50@9999` where `9999` is not in eu-ai-act's known versions
        When: classify_value is called
        Then: status is "fail"

        D3a: `@` present → pinned intent. Version `9999` is not in eu-ai-act's
        recognized version set (`2024`) → cannot round-trip → tamper (D4c).
        """
        status, _ = classify_value(
            "eu-ai-act",
            "Article 50@9999",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "fail"


# ===========================================================================
# 4. classify_value — unknown framework key → FAIL (fail-loud)
# ===========================================================================


class TestClassifyValueUnknownFramework:
    """
    classify_value returns ("fail", ...) for any value under a framework key
    not present in the registry. An unknown mapping key is always a failure
    (step 1 of the classification contract, D4c fail-loud design).
    """

    def test_unknown_framework_key_fails(self):
        """
        Given: any value under framework key `does-not-exist`
        When: classify_value is called
        Then: status is "fail" (fail-loud on unknown framework key)

        An unknown framework id cannot be validated; it indicates a
        misspelled or unregistered framework key was hand-typed into
        the mappings block. Fail rather than skip (D4c).
        """
        status, _ = classify_value(
            "does-not-exist",
            "some-value",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "fail"

    def test_unknown_framework_key_with_delimiter_still_fails(self):
        """
        Given: a delimiter-bearing value `SomeRef@1.0` under unknown framework `bogus-fw`
        When: classify_value is called
        Then: status is "fail"

        The unknown-framework check (step 1) fires before the delimiter check (step 3)
        so the presence of a valid-looking delimiter does not change the outcome.
        """
        status, _ = classify_value(
            "bogus-fw",
            "SomeRef@1.0",
            registry=_registry(),
            pinned_patterns=_pinned(),
        )
        assert status == "fail"


# ===========================================================================
# 5. main() integration — tmp YAML fixtures
# ===========================================================================


class TestMainWithTmpYaml:
    """
    main() integration tests using tmp_path fixtures.

    Tamper values are constructed in temporary files — the live content
    files are never modified. Each test builds a minimal cosai entity YAML
    with a `mappings:` dict carrying bare-string lists.
    """

    def test_main_only_legacy_values_exits_zero(self, tmp_path, capsys):
        """
        Given: a risks.yaml with only legacy (no-delimiter) mapping values
        When: main([path]) is called
        Then: returns 0 and no failure output on stderr

        Legacy values (AML.T0020, GV-6.2, LLM06, tampering) are all skipped
        by the validator — migration is #343, not #347 (D4c).
        """
        risks_file = tmp_path / "risks.yaml"
        _write_content_yaml(
            risks_file,
            "risks",
            [
                {
                    "id": "riskFoo",
                    "title": "Foo Risk",
                    "mappings": {
                        "mitre-atlas": ["AML.T0020", "AML.T0043"],
                        "stride": ["tampering"],
                        "owasp-top10-llm": ["LLM06"],
                        "nist-ai-rmf": ["GV-6.2"],
                    },
                }
            ],
        )
        rc = main([str(risks_file)])
        assert rc == 0

    def test_main_tampered_value_exits_one(self, tmp_path, capsys):
        """
        Given: a risks.yaml containing one tampered pinned value `GOVERN-6.2@9.9`
        When: main([path]) is called
        Then: returns 1 and the offending value appears on stderr

        The value `GOVERN-6.2@9.9` contains `@` (signaling pinned intent per H3/D3a)
        but version `9.9` is not in nist-ai-rmf's registry → purity failure (D4c).
        """
        risks_file = tmp_path / "risks.yaml"
        _write_content_yaml(
            risks_file,
            "risks",
            [
                {
                    "id": "riskFoo",
                    "title": "Foo Risk",
                    "mappings": {
                        "nist-ai-rmf": ["GOVERN-6.2@9.9"],
                    },
                }
            ],
        )
        rc = main([str(risks_file)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "GOVERN-6.2@9.9" in captured.err

    def test_main_mixed_legacy_and_tampered_exits_one(self, tmp_path, capsys):
        """
        Given: a controls.yaml with some legacy values and one tampered value
        When: main([path]) is called
        Then: returns 1; tampered value appears on stderr; legacy values do not

        Verifies that legacy values are not incorrectly reported as failures
        even when a tampered value causes exit 1.
        """
        controls_file = tmp_path / "controls.yaml"
        _write_content_yaml(
            controls_file,
            "controls",
            [
                {
                    "id": "controlFoo",
                    "title": "Foo Control",
                    "mappings": {
                        "mitre-atlas": ["AML.M0007"],  # legacy → skip
                        "nist-ai-rmf": ["GOVERN-6.2@9.9"],  # tampered → fail
                        "owasp-top10-llm": ["LLM06"],  # legacy → skip
                    },
                }
            ],
        )
        rc = main([str(controls_file)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "GOVERN-6.2@9.9" in captured.err
        # Legacy values must not appear as failures in stderr
        assert "AML.M0007" not in captured.err
        assert "LLM06" not in captured.err

    def test_main_personas_yaml_with_legacy_iso_exits_zero(self, tmp_path):
        """
        Given: a personas.yaml with bare ISO 22989 roles (no `@` delimiter)
        When: main([path]) is called
        Then: returns 0

        Real corpus shape: personas carry `iso-22989: [AI Producer]` without
        a version token. These are legacy forms → skip (D3a / H3). #343 migrates.
        """
        personas_file = tmp_path / "personas.yaml"
        _write_content_yaml(
            personas_file,
            "personas",
            [
                {
                    "id": "personaFoo",
                    "title": "Foo Persona",
                    "mappings": {
                        "iso-22989": ["AI Producer", "AI Customer (end user)"],
                    },
                }
            ],
        )
        rc = main([str(personas_file)])
        assert rc == 0

    def test_main_iso_tampered_pinned_value_exits_one(self, tmp_path, capsys):
        """
        Given: a personas.yaml with a tampered ISO role `AI Part (data supplier)@2022`
        When: main([path]) is called
        Then: returns 1 and the offending value appears on stderr

        `@` present + `2022` is a known version but the base role is not in the
        closed enum (D8) → out-of-vocab with delimiter = tamper (D4c).
        """
        personas_file = tmp_path / "personas.yaml"
        _write_content_yaml(
            personas_file,
            "personas",
            [
                {
                    "id": "personaFoo",
                    "title": "Foo Persona",
                    "mappings": {
                        "iso-22989": ["AI Part (data supplier)@2022"],
                    },
                }
            ],
        )
        rc = main([str(personas_file)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "AI Part (data supplier)@2022" in captured.err

    def test_main_empty_mapping_list_exits_zero(self, tmp_path):
        """
        Given: a risks.yaml where a framework key maps to an empty list
        When: main([path]) is called
        Then: returns 0

        An empty list under a framework key means no values to validate.
        The validator must iterate over zero items without erroring.
        """
        risks_file = tmp_path / "risks.yaml"
        _write_content_yaml(
            risks_file,
            "risks",
            [{"id": "riskFoo", "mappings": {"mitre-atlas": []}}],
        )
        rc = main([str(risks_file)])
        assert rc == 0

    def test_main_no_mappings_key_exits_zero(self, tmp_path):
        """
        Given: a risks.yaml where entities have no `mappings` key at all
        When: main([path]) is called
        Then: returns 0

        Entities without a `mappings` block are valid — the field is optional.
        The validator must not error on their absence.
        """
        risks_file = tmp_path / "risks.yaml"
        _write_content_yaml(
            risks_file,
            "risks",
            [
                {"id": "riskFoo", "title": "Foo Risk"},
                {"id": "riskBar", "title": "Bar Risk"},
            ],
        )
        rc = main([str(risks_file)])
        assert rc == 0

    def test_main_unknown_framework_key_in_mappings_exits_one(self, tmp_path, capsys):
        """
        Given: a controls.yaml with an unknown framework key `bogus-framework`
        When: main([path]) is called
        Then: returns 1 and the framework key appears on stderr

        An unknown framework key is always a failure (step 1 of classification
        contract, D4c fail-loud design). The value is irrelevant.
        """
        controls_file = tmp_path / "controls.yaml"
        _write_content_yaml(
            controls_file,
            "controls",
            [
                {
                    "id": "controlFoo",
                    "title": "Foo Control",
                    "mappings": {
                        "bogus-framework": ["some-value"],
                    },
                }
            ],
        )
        rc = main([str(controls_file)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "bogus-framework" in captured.err

    def test_main_multiple_files_all_legacy_exits_zero(self, tmp_path):
        """
        Given: multiple content files each containing only legacy values
        When: main([risks_path, controls_path, personas_path]) is called
        Then: returns 0

        The validator must handle multiple file arguments (pre-commit passes
        all changed files as positional args).
        """
        risks_file = tmp_path / "risks.yaml"
        controls_file = tmp_path / "controls.yaml"
        personas_file = tmp_path / "personas.yaml"

        _write_content_yaml(
            risks_file,
            "risks",
            [{"id": "riskFoo", "mappings": {"mitre-atlas": ["AML.T0020"]}}],
        )
        _write_content_yaml(
            controls_file,
            "controls",
            [{"id": "controlFoo", "mappings": {"nist-ai-rmf": ["GV-6.2"]}}],
        )
        _write_content_yaml(
            personas_file,
            "personas",
            [{"id": "personaFoo", "mappings": {"iso-22989": ["AI Producer"]}}],
        )
        rc = main([str(risks_file), str(controls_file), str(personas_file)])
        assert rc == 0

    def test_main_multiple_files_one_tampered_exits_one(self, tmp_path, capsys):
        """
        Given: two files where one has only legacy values and one has a tamper
        When: main([clean_path, tampered_path]) is called
        Then: returns 1 and stderr mentions the tampered value only

        Validates that the multi-file scan correctly surfaces a failure in any
        file, not just the first.
        """
        clean_file = tmp_path / "risks.yaml"
        tampered_file = tmp_path / "controls.yaml"

        _write_content_yaml(
            clean_file,
            "risks",
            [{"id": "riskFoo", "mappings": {"mitre-atlas": ["AML.T0020"]}}],
        )
        _write_content_yaml(
            tampered_file,
            "controls",
            [
                {
                    "id": "controlFoo",
                    "mappings": {
                        "owasp-top10-llm": ["LLM02:2099"],  # tampered year
                    },
                }
            ],
        )
        rc = main([str(clean_file), str(tampered_file)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "LLM02:2099" in captured.err


# ===========================================================================
# 6. REAL-SHAPE SILENT-SKIP REGRESSION — multi-list-key top-level structure
# ===========================================================================


class TestMainRealShapeSilentSkip:
    """
    Regression guard for the silent-skip bug in _scan_file (#347 / D4c).

    Bug: _scan_file iterates data.values() and takes the FIRST list-valued key
    as the entity list. In all four real content files, `description:` is a
    list and appears BEFORE the entity key (risks:/controls:/personas:).
    controls.yaml additionally has `categories:` (also a list) before `controls:`.
    So _scan_file scans the prose items in `description` / `categories`, finds
    no `mappings` dicts in them, and returns an empty failure list — exit 0 —
    no matter what the entity mappings contain.

    The existing tmp-fixture tests in TestMainWithTmpYaml miss this because
    _write_content_yaml emits only ONE list key (e.g. {risks: [...]}), so
    description is absent and _scan_file picks the entity list correctly.

    The live-corpus tests pass for the wrong reason: the real corpus is all-
    legacy values (no @ or :), so the validator exits 0 whether or not it
    actually reaches the entity mappings.

    These tests reproduce the real top-level shape — multiple list-valued top-
    level keys with description BEFORE the entity key — and assert the validator
    still reaches and correctly classifies the entity mappings.

    Files are written with yaml.dump(..., sort_keys=False) to preserve key
    insertion order so description precedes the entity key, matching real files.
    """

    def test_real_shape_risks_tamper_caught(self, tmp_path, capsys):
        """
        Given: a YAML file with description (list) BEFORE risks (list), where a
               risks entity carries a tampered pinned value `GOVERN-6.2@9.9`
        When: main([path]) is called
        Then: returns 1 and the tampered value appears on stderr

        This is the direct regression guard for the silent-skip bug. If _scan_file
        still takes the first list-valued key (description), it will never visit
        the risks entities and will exit 0 — the wrong answer. The fix must scan
        the entity key by name, not by position.

        Reference: #347 D4c; silent-skip risk described in class docstring.
        """
        risks_file = tmp_path / "risks.yaml"
        # Build with description FIRST so it is the first list-valued key.
        # sort_keys=False preserves insertion order (Python 3.7+, PyYAML 5+).
        content = {
            "title": "Risks",
            "description": [
                "Prose paragraph one.",
                "Prose paragraph two.",
            ],
            "risks": [
                {
                    "id": "riskX",
                    "title": "Risk X",
                    "mappings": {
                        "nist-ai-rmf": ["GOVERN-6.2@9.9"],  # tampered: version 9.9 unknown
                    },
                }
            ],
        }
        risks_file.write_text(yaml.dump(content, default_flow_style=False, sort_keys=False), encoding="utf-8")

        rc = main([str(risks_file)])

        assert rc == 1, (
            "Expected exit 1 for tampered value GOVERN-6.2@9.9. "
            "Exit 0 indicates _scan_file picked description instead of risks "
            "and silently skipped all entity mappings (silent-skip bug)."
        )
        captured = capsys.readouterr()
        assert "GOVERN-6.2@9.9" in captured.err

    def test_real_shape_controls_tamper_caught_categories_before_controls(self, tmp_path, capsys):
        """
        Given: a YAML file with description (list) and categories (list) BEFORE
               controls (list), where a controls entity has tampered value
               `LLM02:2099` (unknown year)
        When: main([path]) is called
        Then: returns 1 and the tampered value appears on stderr

        controls.yaml has both description and categories as lists preceding the
        controls list. This is the most adversarial ordering for the first-list-
        key bug. If _scan_file takes description (first), it exits 0. If it
        takes categories (second), it also exits 0. Only by reaching controls
        (third) will it surface the tamper.

        Reference: #347 D4c; silent-skip risk described in class docstring.
        """
        controls_file = tmp_path / "controls.yaml"
        content = {
            "title": "Controls",
            "description": [
                "Prose paragraph one.",
                "Prose paragraph two.",
            ],
            "categories": [
                {"id": "controlsData", "title": "Data Controls"},
                {"id": "controlsModel", "title": "Model Controls"},
            ],
            "controls": [
                {
                    "id": "controlY",
                    "title": "Control Y",
                    "mappings": {
                        "owasp-top10-llm": ["LLM02:2099"],  # tampered: year 2099 unknown
                    },
                }
            ],
        }
        controls_file.write_text(yaml.dump(content, default_flow_style=False, sort_keys=False), encoding="utf-8")

        rc = main([str(controls_file)])

        assert rc == 1, (
            "Expected exit 1 for tampered value LLM02:2099. "
            "Exit 0 indicates _scan_file picked description or categories "
            "instead of controls and silently skipped all entity mappings."
        )
        captured = capsys.readouterr()
        assert "LLM02:2099" in captured.err

    def test_real_shape_legacy_values_stay_green(self, tmp_path):
        """
        Given: a YAML file with description (list) BEFORE risks (list), where
               risks entities carry only legacy (no-delimiter) mapping values
        When: main([path]) is called
        Then: returns 0

        Confirms that the fix for the silent-skip bug does not over-scan
        description or categories prose items into false failures, and that
        legitimate legacy values in the entity list still skip cleanly.

        Reference: #347 D4c; silent-skip risk described in class docstring.
        """
        risks_file = tmp_path / "risks.yaml"
        content = {
            "title": "Risks",
            "description": [
                "Prose paragraph one.",
                "Prose paragraph two.",
            ],
            "risks": [
                {
                    "id": "riskLegacy",
                    "title": "Legacy Risk",
                    "mappings": {
                        "nist-ai-rmf": ["GV-6.2"],  # legacy: no @ → skip
                        "mitre-atlas": ["AML.T0020"],  # legacy: no @ → skip
                        "owasp-top10-llm": ["LLM06"],  # legacy: no : → skip
                        "stride": ["tampering"],  # legacy: unversioned → skip
                    },
                }
            ],
        }
        risks_file.write_text(yaml.dump(content, default_flow_style=False, sort_keys=False), encoding="utf-8")

        rc = main([str(risks_file)])

        assert rc == 0, (
            "Expected exit 0 for all-legacy values in real-shape YAML. "
            "A non-zero exit indicates false positives from prose in "
            "description or categories being scanned as entity mappings."
        )


# ===========================================================================
# 7. LIVE CORPUS CLEAN — all four content files must produce zero failures
# ===========================================================================


@pytest.mark.live_corpus
class TestLiveCorpusGreen:
    """
    The live corpus (risks/controls/components/personas.yaml on this branch)
    must produce zero purity failures from main().

    Rationale: every mapping value currently in the corpus is a legacy
    pre-ADR-027 form:
      - mitre-atlas:     `AML.T0020`, `AML.M0007`, ...  (no `@`)
      - nist-ai-rmf:     `GV-6.2`, `GV-1.6`, ...        (no `@`)
      - owasp-top10-llm: `LLM06`, `LLM04`, ...          (no `:`)
      - stride:          `tampering`, ...                (lowercase-kebab)
      - iso-22989:       `AI Producer`, ...              (no `@`)

    None of these contain the `@` or `:` delimiters that D3a / H3 defines as
    the sole signal of pinned-value intent. The validator skips all of them.

    Migration to pinned forms (`AML.T0020` → `AML.T0020@5.0.1`, etc.) is
    issue #343. Until that migration lands, this test is the regression guard
    confirming that the purity validator does not break the existing corpus.

    components.yaml currently has zero mapping values; it is included to
    confirm the validator handles a mappings-free file gracefully.
    """

    def test_risks_yaml_live_corpus_zero_failures(self):
        """
        Given: the live risk-map/yaml/risks.yaml as it exists on this branch
        When: main([risks_path]) is called
        Then: returns 0 (all legacy values are skipped, none fail purity check)
        """
        assert RISKS_YAML.is_file(), f"risks.yaml not found at {RISKS_YAML}"
        rc = main([str(RISKS_YAML)])
        assert rc == 0

    def test_controls_yaml_live_corpus_zero_failures(self):
        """
        Given: the live risk-map/yaml/controls.yaml as it exists on this branch
        When: main([controls_path]) is called
        Then: returns 0 (all legacy values are skipped, none fail purity check)
        """
        assert CONTROLS_YAML.is_file(), f"controls.yaml not found at {CONTROLS_YAML}"
        rc = main([str(CONTROLS_YAML)])
        assert rc == 0

    def test_components_yaml_live_corpus_zero_failures(self):
        """
        Given: the live risk-map/yaml/components.yaml as it exists on this branch
        When: main([components_path]) is called
        Then: returns 0 (components.yaml has zero mapping values; no-op run)
        """
        assert COMPONENTS_YAML.is_file(), f"components.yaml not found at {COMPONENTS_YAML}"
        rc = main([str(COMPONENTS_YAML)])
        assert rc == 0

    def test_personas_yaml_live_corpus_zero_failures(self):
        """
        Given: the live risk-map/yaml/personas.yaml as it exists on this branch
        When: main([personas_path]) is called
        Then: returns 0 (all ISO 22989 bare roles are legacy, no `@` → skipped)
        """
        assert PERSONAS_YAML.is_file(), f"personas.yaml not found at {PERSONAS_YAML}"
        rc = main([str(PERSONAS_YAML)])
        assert rc == 0

    def test_all_four_content_files_zero_failures(self):
        """
        Given: all four live content files passed together
        When: main([risks, controls, components, personas]) is called
        Then: returns 0

        This is the crux regression guard: the entire current corpus stays
        clean (zero failures) with the purity validator in place. The validator must skip every
        legacy value and report no failures. Migration to pinned forms is #343.
        """
        for path in (RISKS_YAML, CONTROLS_YAML, COMPONENTS_YAML, PERSONAS_YAML):
            assert path.is_file(), f"content file not found: {path}"

        rc = main([str(RISKS_YAML), str(CONTROLS_YAML), str(COMPONENTS_YAML), str(PERSONAS_YAML)])
        assert rc == 0

    def test_main_default_no_args_zero_failures(self):
        """
        Given: no CLI arguments (default mode)
        When: main([]) is called
        Then: returns 0

        When invoked with no positional args, main() must default to scanning
        the four standard content files from the repo. On this branch they are
        all legacy → zero failures.
        """
        rc = main([])
        assert rc == 0


"""
Test Summary
============
Total tests: 41
  OK cases (classify_value):          6  (TestClassifyValueOK)
  SKIP cases (classify_value):        9  (TestClassifyValueSkip)
  FAIL cases (classify_value):        8  (TestClassifyValueFail)
  Unknown framework (classify_value): 2  (TestClassifyValueUnknownFramework)
  main() integration (tmp_path):     10  (TestMainWithTmpYaml)
  Live corpus green:                  6  (TestLiveCorpusGreen)

Coverage areas:
  - Per-framework OK classification: all 6 frameworks (mitre-atlas, nist-ai-rmf,
    owasp-top10-llm, stride, iso-22989, eu-ai-act)
  - Per-framework SKIP: versioned no-delimiter (mitre x2, nist, owasp, iso x2,
    eu-ai-act), unversioned no-enum-match (stride x2)
  - FAIL classification: unknown version (nist, iso, eu-ai-act), empty token,
    wrong delimiter, iso out-of-vocab-but-delimited, bad version suffix,
    owasp unknown year
  - FAIL detail contract: nist unknown-version asserts detail is non-None and
    contains the bad token
  - Unknown framework key (step 1 fail-loud): value-agnostic x2
  - main() return codes: 0 and 1 paths
  - main() stderr content: offending values surfaced
  - main() legacy-value suppression from stderr
  - main() multi-file support (both clean and mixed)
  - main() empty mapping list (zero iterations, no error)
  - main() no-mappings entity (graceful)
  - main() default no-args mode
  - Live corpus: all four files individually + combined + default no-args

Recommended public API:
  classify_value(
      fw_id: str,
      value: str,
      *,
      registry: dict[str, dict],
      pinned_patterns: dict[str, dict],
  ) -> tuple[str, str | None]
      Returns (status, detail) where status in {"ok", "skip", "fail"}.
      detail is a human-readable string or None.

  main(argv: list[str]) -> int
      Positional args: file paths to scan.
      Defaults to RISKS/CONTROLS/COMPONENTS/PERSONAS yaml when none given.
      Returns 0 on success (no failures), 1 on any failure.
      Prints failure details to stderr (including the offending value).
"""

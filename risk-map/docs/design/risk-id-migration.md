# Risk ID Migration Design

This document describes the design decisions, rationale, and complete mapping for migrating risk IDs from legacy uppercase abbreviations to the standard `risk` + camelCase descriptor format used by all other CoSAI Risk Map entity types.

**Version:** 1.0
**Last Updated:** 2026-04-09

---

## Table of Contents

- [Overview](#overview)
- [Problem Statement](#problem-statement)
- [ID Convention Reference](#id-convention-reference)
- [Migration Mapping](#migration-mapping)
- [Naming Rules](#naming-rules)
- [Design Decisions](#design-decisions)
- [Scope of Changes](#scope-of-changes)
- [Unchanged Elements](#unchanged-elements)

---

## Overview

The CoSAI Risk Map uses structured YAML files to define four primary entity types: components, controls, personas, and risks. Three of these types follow a consistent `<type>` + camelCase naming convention for their IDs. Risks are the exception, using 2-4 letter uppercase abbreviations inherited from the project's early design.

This migration brings risk IDs into conformance with the established convention, improving consistency, readability, and tooling simplicity.

### Change Summary

| Aspect | Before | After |
|--------|--------|-------|
| Risk ID format | 2-4 uppercase letters, optional hyphen (e.g., `DP`, `EDH-I`) | `risk` + camelCase descriptor (e.g., `riskDataPoisoning`) |
| Total IDs migrated | 28 | 28 |
| Backward compatibility | N/A | None needed (internal data format) |
| Category IDs | Unchanged | Unchanged (`risksSupplyChainAndDevelopment`, etc.) |

---

## Problem Statement

Risk IDs are the only entity type that do not follow the project's standard naming convention:

```yaml
# Controls, components, personas: <type> + camelCase
controlTrainingDataManagement
componentModelServing
personaModelProvider

# Risks: legacy uppercase abbreviations
DP    # Data Poisoning
ASSC  # Accelerator and System Side-channels
EDH-I # Excessive Data Handling During Inference
```

This inconsistency:
- Requires special-case documentation and validation rules for risk IDs
- Makes IDs opaque without a lookup table (what does `IIC` mean?)
- Complicates content reviewer agent configuration (must maintain separate convention rules)
- Breaks the uniform `<type>` prefix pattern that enables programmatic entity type detection

---

## ID Convention Reference

All four entity types now follow the same pattern after migration:

| Entity Type | Prefix | Format | Examples |
|-------------|--------|--------|----------|
| Components | `component` | `component` + camelCase | `componentTrainingData`, `componentModelServing` |
| Controls | `control` | `control` + camelCase | `controlTrainingDataManagement`, `controlSecureByDefaultMLTooling` |
| Personas | `persona` | `persona` + camelCase | `personaModelProvider`, `personaApplicationDeveloper` |
| Risks | `risk` | `risk` + camelCase | `riskDataPoisoning`, `riskDenialOfMLService` |

**Category IDs** follow `{typePlural}{Domain}` in camelCase and are not affected by this migration: `risksSupplyChainAndDevelopment`, `controlsInfrastructure`, `componentsModel`, etc.

---

## Migration Mapping

Complete mapping of all 28 risk IDs, mechanically derived from their titles in `risks.yaml`:

| Legacy ID | New ID | Title |
|-----------|--------|-------|
| `ADI` | `riskAdapterPEFTInjection` | Adapter/PEFT Injection |
| `ASSC` | `riskAcceleratorAndSystemSideChannels` | Accelerator and System Side-channels |
| `COV` | `riskCovertChannelsInModelOutputs` | Covert Channels in Model Outputs |
| `DMS` | `riskDenialOfMLService` | Denial of ML Service |
| `DP` | `riskDataPoisoning` | Data Poisoning |
| `EBM` | `riskEvaluationBenchmarkManipulation` | Evaluation/Benchmark Manipulation |
| `EDH` | `riskExcessiveDataHandling` | Excessive Data Handling |
| `EDH-I` | `riskExcessiveDataHandlingDuringInference` | Excessive Data Handling During Inference |
| `EDW` | `riskEconomicDenialOfWallet` | Economic Denial of Wallet |
| `FLP` | `riskFederatedDistributedTrainingPrivacy` | Federated/Distributed Training Privacy |
| `IIC` | `riskInsecureIntegratedComponent` | Insecure Integrated Component |
| `IMO` | `riskInsecureModelOutput` | Insecure Model Output |
| `ISD` | `riskInferredSensitiveData` | Inferred Sensitive Data |
| `MDT` | `riskModelDeploymentTampering` | Model Deployment Tampering |
| `MEV` | `riskModelEvasion` | Model Evasion |
| `MLD` | `riskMaliciousLoaderDeserialization` | Malicious Loader/Deserialization |
| `MRE` | `riskModelReverseEngineering` | Model Reverse Engineering |
| `MST` | `riskModelSourceTampering` | Model Source Tampering |
| `MXF` | `riskModelExfiltration` | Model Exfiltration |
| `ORH` | `riskOrchestratorRouteHijacking` | Orchestrator/Route Hijack |
| `PCP` | `riskPromptResponseCachePoisoning` | Prompt/Response Cache Poisoning |
| `PIJ` | `riskPromptInjection` | Prompt Injection |
| `RA` | `riskRogueActions` | Rogue Actions |
| `RVP` | `riskRetrievalVectorStorePoisoning` | Retrieval/Vector Store Poisoning |
| `SDD` | `riskSensitiveDataDisclosure` | Sensitive Data Disclosure |
| `TRT` | `riskToolRegistryTampering` | Tool Registry Tampering |
| `TSP` | `riskToolSourceProvenance` | Tool Source Provenance |
| `UTD` | `riskUnauthorizedTrainingData` | Unauthorized Training Data |

---

## Naming Rules

The following rules were applied when deriving new IDs from risk titles:

### 1. Acronym Preservation

Well-known abbreviations retain their uppercase casing in camelCase, consistent with existing IDs like `controlSecureByDefaultMLTooling`:

| Acronym | Example |
|---------|---------|
| `ML` | `riskDenialOfMLService` |
| `PEFT` | `riskAdapterPEFTInjection` |

### 2. Slash-Separated Terms

When a title contains a slash separating alternative or complementary terms, both terms are kept and the slash is dropped:

| Title | New ID |
|-------|--------|
| Federated/Distributed Training Privacy | `riskFederatedDistributedTrainingPrivacy` |
| Prompt/Response Cache Poisoning | `riskPromptResponseCachePoisoning` |
| Orchestrator/Route Hijack | `riskOrchestratorRouteHijacking` |
| Malicious Loader/Deserialization | `riskMaliciousLoaderDeserialization` |
| Evaluation/Benchmark Manipulation | `riskEvaluationBenchmarkManipulation` |
| Retrieval/Vector Store Poisoning | `riskRetrievalVectorStorePoisoning` |

### 3. Gerund Normalization

Where a title uses a bare noun form but peer risk IDs use gerund (-ing) forms, the ID is normalized to gerund for consistency:

| Title | New ID | Rationale |
|-------|--------|-----------|
| Orchestrator/Route Hijack | `riskOrchestratorRouteHijacking` | Consistent with "Tampering", "Poisoning", etc. |

### 4. Hyphenated Sub-identifiers Flattened

The legacy `EDH-I` pattern (hyphen + sub-identifier) is replaced by a flat camelCase form. The camelCase format is expressive enough without hierarchy, and this avoids special-case parsing logic:

| Legacy | New |
|--------|-----|
| `EDH-I` | `riskExcessiveDataHandlingDuringInference` |

---

## Design Decisions

| Decision | Rationale |
|----------|-----------|
| No backward compatibility period | Internal data format with no external consumers pinned to specific IDs |
| Scripted migration | 150+ replacements across 4+ source files; manual replacement is error-prone |
| HTML anchor updates | 13 `href="#ID"` cross-references in risk descriptions must stay functional |
| `risks: all` keyword untouched | Special keyword in controls.yaml, not a risk ID |
| `OrphanRisk` test fixture unchanged | Synthetic test ID, not a production risk |
| Longest-match-first replacement | Process `EDH-I` before `EDH` to prevent partial matches |

---

## Scope of Changes

### Source data and schema
- `risk-map/yaml/risks.yaml` — 28 `id:` values + 13 `href="#ID"` anchors
- `risk-map/yaml/controls.yaml` — ~94 risk references in `risks:` arrays
- `risk-map/yaml/self-assessment.yaml` — ~10 risk references
- `risk-map/schemas/risks.schema.json` — 28 enum entries

### Validation and generation scripts
- No code changes needed — scripts parse IDs dynamically from YAML/schema

### Tests
- 8 test files with hardcoded risk IDs in fixtures and assertions

### Documentation and templates
- 6 contributor guide files
- 2 internal doc files
- 1 agent definition (content-reviewer.md)
- 6 issue/PR templates

### Auto-generated files (regenerated by hooks)
- Markdown tables in `risk-map/tables/`
- Mermaid diagrams in `risk-map/diagrams/`
- SVG files in `risk-map/svg/`

---

## Unchanged Elements

The following are explicitly **not** changed by this migration:

- **Category IDs** — already conform to `{typePlural}{Domain}` camelCase (e.g., `risksSupplyChainAndDevelopment`)
- **Control IDs** — already conform (`controlFoo`)
- **Component IDs** — already conform (`componentFoo`)
- **Persona IDs** — already conform (`personaFoo`)
- **`controls.schema.json`** — references `risks.schema.json` via `$ref`; no direct changes needed
- **Validation scripts** — parse IDs dynamically; no format-specific logic to update

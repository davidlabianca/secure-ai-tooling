# Schema Versioning Discussion: Is Versioning Necessary?

## Context

The CoSAI Risk Map schemas in `./risk-map/schemas/` currently use git for version control but do not include explicit version metadata within the schema files themselves. Before deciding on a versioning strategy, we should first determine **whether explicit schema versioning is necessary** for this project's usage patterns.

## Current State

**How schemas are used:**
- **Internal validation only** - Schemas validate YAML files within this repository via `check-jsonschema`
- **Git hooks & CI/CD** - Pre-commit hooks and GitHub Actions automatically validate staged/committed files
- **Cross-references** - Schemas reference each other using relative paths (e.g., `"$ref": "riskmap.schema.json#/definitions/utils/text"`)
- **File-based resolution** - Validation uses `--base-uri "file://$(pwd)/risk-map/schemas/"` for local resolution
- **Monorepo structure** - Schemas and the YAML content they validate live in the same repository and evolve together
- **Not independently distributed** - Schemas are not published to npm, PyPI, or any package registry
- **Direct consumption** - Users consume the framework by cloning the repo or reading files directly from GitHub

**Schema evolution observed:**
- Recent changes: 8-stage lifecycle model, metadata field extraction, agent-related updates
- Schema changes trigger full validation via pre-commit hooks (line 212-217 in `scripts/hooks/pre-commit`)
- Cross-schema dependencies (11 schema files referencing each other)

## Core Question

**Given that schemas are tightly coupled to YAML content and not distributed separately, do we need explicit versioning beyond git?**

## Scenarios to Consider

### 1. Internal Development (Current Primary Use Case)
- **Need:** Validate YAML against schemas during development
- **Current approach:** Git-based versioning works fine - schemas and YAML evolve in lockstep
- **Version info needed?** No - developers always work with HEAD or a specific branch/commit

### 2. Framework Consumers (Learning/Reference)
- **Need:** Understand the CoSAI Risk Map structure and relationships
- **Current approach:** Clone repo or browse GitHub at a specific commit/tag/release
- **Version info needed?** Minimal - git tags/releases are sufficient (e.g., "CoSAI-RM v1.2.0")

### 3. External Tools Building on CoSAI-RM
- **Need:** Programmatically validate their own YAML against CoSAI schemas
- **Current approach:** Reference schemas from cloned repo or GitHub raw URLs
- **Version info needed?** **Maybe** - tools might need to:
  - Detect which schema version they're using
  - Ensure compatibility when schemas evolve
  - Handle breaking changes gracefully

### 4. Standards Body / OASIS Process
- **Need:** Track official releases for standards governance
- **Current approach:** Git tags and release notes
- **Version info needed?** **Possibly** - OASIS standards often have explicit version metadata

### 5. Future API or Package Distribution
- **Need:** If schemas are eventually published to a package registry
- **Current approach:** N/A - not currently planned
- **Version info needed?** **Yes** - would require semantic versioning

## Questions for Discussion

1. **External tool usage**: Are there (or will there be) external tools that consume these schemas programmatically? If so, how do they reference them?

2. **Breaking changes**: When schemas evolve with breaking changes, how do we communicate compatibility to:
   - External tools that validate against our schemas?
   - Forked or derived frameworks?
   - Historical assessments done with older schema versions?

3. **OASIS governance**: Does the OASIS Open Project process require or recommend explicit versioning in schema files?

4. **Schema stability**: Are the schemas approaching stability, or do we expect frequent evolution?

5. **Distributed validation**: Do we expect organizations to:
   - Clone the repo and validate locally (current pattern)?
   - Reference schemas from GitHub raw URLs?
   - Download schemas and vendor them into their own projects?

6. **Cross-schema compatibility**: When one schema changes, how do we ensure dependent schemas remain compatible? (e.g., when `risks.schema.json` references `frameworks.schema.json`, `lifecycle-stage.schema.json`, `impact-type.schema.json`, and `actor-access.schema.json`)

## Recommendation Framework

**Add explicit versioning IF:**
- External tools consume schemas programmatically
- Schemas may be distributed independently of YAML content
- OASIS governance requires it
- We need to support multiple schema versions simultaneously
- Breaking changes need clear communication to downstream consumers

**Keep git-only versioning IF:**
- Schemas remain tightly coupled to YAML in this repo
- All consumption happens via repo cloning or direct file access
- Framework versioning at the project level (git tags) is sufficient
- Maintenance burden of keeping versions in sync outweighs benefits

## Next Steps

1. Clarify primary consumption patterns (current and planned)
2. Check OASIS Open Project versioning requirements
3. Assess whether external tools are using/will use these schemas
4. Based on answers, decide: version in files, git-only, or hybrid approach

---

**What do you think?** Should we add versioning, and if so, what problem would it solve for CoSAI-RM's actual usage patterns?

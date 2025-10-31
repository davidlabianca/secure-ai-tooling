# Adding and Using Frameworks

This guide explains how to work with external security framework mappings in the CoSAI Risk Map. Frameworks allow you to cross-reference risks and controls with established security standards like MITRE ATLAS, NIST AI RMF, STRIDE, and OWASP Top 10 for LLM.

---

## Overview

The framework system provides a structured way to:
- Map risks and controls to external security frameworks
- Maintain consistent framework identifiers across the project
- Track framework versions and documentation
- Enable automated validation of framework references

## Framework Structure

### Framework Definition File

Frameworks are defined in [`risk-map/yaml/frameworks.yaml`](../yaml/frameworks.yaml) as an array. Each framework includes:

```yaml
frameworks:
  - id: framework-id
    name: "Short Name"
    fullName: "Full Official Name"
    description: "Brief description"
    baseUri: "https://example.com"
    version: "1.0"                      # Optional: or null
    lastUpdated: "2024-01-01"          # Optional: or null
    techniqueUriPattern: "https://..."  # Optional
    documentUri: "https://..."          # Optional
```

### Required vs Optional Fields

**Required:**
- `id` - Must be in the frameworks.schema.json enum
- `name` - Short name for display
- `fullName` - Full official name
- `description` - Brief description of the framework
- `baseUri` - Base URL for framework documentation

**Optional:**
- `version` - Framework version string or null
- `lastUpdated` - Date in YYYY-MM-DD format or null
- `techniqueUriPattern` - URL pattern with `{id}` placeholder
- `documentUri` - Direct link to specification document

---

## Adding a New Framework

### Step 1: Update the Schema Enum

Add your framework ID to the enum in [`risk-map/schemas/frameworks.schema.json`](../schemas/frameworks.schema.json):

```json
"enum": [
  "mitre-atlas",
  "nist-ai-rmf",
  "stride",
  "owasp-top10-llm",
  "your-new-framework-id"
]
```

### Step 2: Add Framework Definition

Add the framework to the array in [`risk-map/yaml/frameworks.yaml`](../yaml/frameworks.yaml):

```yaml
frameworks:
  # ... existing frameworks ...

  - id: your-new-framework-id
    name: "Framework Name"
    fullName: "Full Framework Name"
    description: "Brief description of the framework's purpose"
    baseUri: "https://framework-website.com"
    version: "2.0"
    lastUpdated: "2024-01-15"
    techniqueUriPattern: "https://framework-website.com/techniques/{id}"
    documentUri: "https://framework-website.com/docs/specification.pdf"
```

### Step 3: Validate

Run validation to ensure your changes are correct:

```bash
# Run full validation including schema checks, formatting, and cross-references
# (Requires pre-commit hook installation via ./scripts/install-pre-commit-hook.sh)
.git/hooks/pre-commit --force
```

---

## Using Framework Mappings in Risks and Controls

Once frameworks are defined, you can reference them in risk and control definitions using the `mappings` field.

### Example: Adding Framework Mappings to Risks

In [`risk-map/yaml/risks.yaml`](../yaml/risks.yaml):

```yaml
risks:
  - id: DP
    title: Data Poisoning
    # ... other required fields ...
    mappings:
      mitre-atlas: ["AML.T0018", "AML.T0020"]
      nist-ai-rmf: ["MS-2.7", "MS-2.8"]
      stride: ["tampering"]
```

### Example: Adding Framework Mappings to Controls

In [`risk-map/yaml/controls.yaml`](../yaml/controls.yaml):

```yaml
controls:
  - id: controlTrainingDataSanitization
    title: Training Data Sanitization
    # ... other required fields ...
    mappings:
      mitre-atlas: ["AML.M0005"]
      nist-ai-rmf: ["MP-4.1"]
```

**Note**: Risks and controls also support additional optional metadata fields (`lifecycleStage`, `impactType`, `actorAccess`). See [Metadata Fields Guide](guide-metadata.md) for details


## Examples

### Complete Risk Example

```yaml
- id: MST
  title: Model Supply Chain Compromise
  shortDescription:
    - "Compromising model artifacts or dependencies in the supply chain"
  longDescription:
    - "Attackers compromise the model supply chain by injecting malicious code..."
  category: risksSupplyChainAndDevelopment
  personas:
    - personaModelCreator
    - personaModelConsumer
  controls:
    - controlVulnerabilityManagement
    - controlModelAndDataIntegrityManagement
  mappings:
    mitre-atlas: ["AML.T0010"]
    stride: ["tampering", "elevation-of-privilege"]
    owasp-top10-llm: ["LLM05"]
  lifecycleStage:
    - data-preparation
    - model-training
    - deployment
  impactType:
    - integrity
    - availability
    - safety
  actorAccess:
    - supply-chain
```

### Complete Control Example

```yaml
- id: controlModelAndDataIntegrityManagement
  title: Model and Data Integrity Management
  description:
    - "Implement cryptographic signing and verification for models and datasets"
  category: controlsModel
  personas:
    - personaModelCreator
    - personaModelConsumer
  components:
    - componentModelStorage
    - componentModelServing
  risks:
    - MST
    - MDT
  mappings:
    mitre-atlas: ["AML.M0013"]
    nist-ai-rmf: ["SC-8", "SI-7"]
  lifecycleStage:
    - data-preparation
    - model-training
    - deployment
    - runtime
  impactType:
    - integrity
    - accountability
  actorAccess:
    - supply-chain
    - privileged
```

---

## Validation Rules

The schema enforces these validation rules:

1. **Framework ID Validation**: All keys in the `mappings` object must match framework IDs defined in the frameworks schema enum
2. **Array Values**: Each framework mapping must be an array of strings
3. **Optional Fields**: All four metadata fields (`mappings`, `lifecycleStage`, `impactType`, `actorAccess`) are optional
4. **Enum Constraints**: Values in `lifecycleStage`, `impactType`, and `actorAccess` must match their respective schema enums
5. **Framework Definition**: Each framework in `frameworks.yaml` must include all required fields (`id`, `name`, `fullName`, `description`, `baseUri`)

---

## Common Patterns

### Mapping Multiple Techniques

```yaml
mappings:
  mitre-atlas: ["AML.T0001", "AML.T0002", "AML.T0003"]
  stride: ["spoofing", "tampering"]
```

### Partial Metadata

You can include only the fields relevant to your risk or control:

```yaml
# Only mappings
mappings:
  mitre-atlas: ["AML.T0015"]

# Only lifecycle and impact
lifecycleStage:
  - runtime
impactType:
  - confidentiality
```

### All Lifecycle Stages

For risks or controls that apply throughout the lifecycle:

```yaml
lifecycleStage:
  - planning
  - data-preparation
  - model-training
  - development
  - evaluation
  - deployment
  - runtime
  - maintenance
```

---

## Best Practices

1. **Use Official Identifiers**: When mapping to frameworks, use the official technique/control IDs from the framework documentation
2. **Keep Descriptions Current**: Update `lastUpdated` dates when frameworks release new versions
3. **Document URI Patterns**: Include `techniqueUriPattern` to enable automatic link generation
4. **Validate Regularly**: Run schema validation after adding or modifying framework mappings
5. **Be Selective**: Only include the most relevant framework mappings rather than exhaustive lists
6. **Review Impact Types**: Choose impact types that accurately reflect the primary security concerns

---

## Troubleshooting

### Invalid Framework ID Error

**Error:** `Property name does not match any enum value`

**Solution:** Ensure the framework ID is added to the enum in `frameworks.schema.json`

### Schema Validation Failure

**Error:** `Missing required field`

**Solution:** Every framework definition must include all required fields: `id`, `name`, `fullName`, `description`, `baseUri`

### Invalid Metadata Value

**Error:** `Value not in enum`

**Solution:** Ensure the value matches one of the valid options defined in the respective schema (`lifecycle-stage.schema.json`, `impact-type.schema.json`, or `actor-access.schema.json`)

---

## Related Documentation

- [Adding a Risk](guide-risks.md) - Complete guide for adding new risks
- [Adding a Control](guide-controls.md) - Complete guide for adding new controls
- [Validation Tools](validation.md) - Schema validation and testing
- [Workflow](workflow.md) - General contribution workflow

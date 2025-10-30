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

Frameworks are defined in [`risk-map/yaml/frameworks.yaml`](../yaml/frameworks.yaml). Each framework includes:

```yaml
frameworks:
  framework-id:
    id: framework-id                    # Must match the YAML key
    name: "Short Name"                  # Display name
    fullName: "Full Official Name"      # Complete framework name
    description: "Brief description"    # Purpose and scope
    baseUri: "https://example.com"      # Main documentation URL
    version: "1.0"                      # Framework version (or null)
    lastUpdated: "2024-01-01"          # Last update date (or null)
    techniqueUriPattern: "https://..."  # Optional: URL pattern for techniques
    documentUri: "https://..."          # Optional: Direct link to specification
```

### Required vs Optional Fields

**Required:**
- `id` - Must match the YAML key and be in the frameworks.schema.json enum
- `name` - Short name for display
- `description` - Brief description of the framework
- `baseUri` - Base URL for framework documentation

**Optional:**
- `fullName` - Full official name
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

Add the framework to [`risk-map/yaml/frameworks.yaml`](../yaml/frameworks.yaml):

```yaml
frameworks:
  # ... existing frameworks ...

  your-new-framework-id:
    id: your-new-framework-id
    name: "Framework Name"
    fullName: "Full Framework Name"
    description: "Brief description of the framework's purpose"
    baseUri: "https://framework-website.com"
    version: "2.0"
    lastUpdated: "2024-01-15"
    techniqueUriPattern: "https://framework-website.com/techniques/{id}"
    documentUri: "https://framework-website.com/docs/specification.pdf"
```

**Important:** The `id` field must exactly match the YAML key.

### Step 3: Validate

Run validation to ensure your changes are correct:

```bash
python scripts/hooks/validate_riskmap.py --force
```

---

## Using Frameworks in Risks and Controls

Once frameworks are defined, you can reference them in risk and control definitions using the `mappings` field.

### Adding Mappings to Risks

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
    lifecycleStage:
      - development
      - evaluation
    impactType:
      - integrity
      - reliability
    actorAccess:
      - supply-chain
      - privileged
```

### Adding Mappings to Controls

In [`risk-map/yaml/controls.yaml`](../yaml/controls.yaml):

```yaml
controls:
  - id: controlTrainingDataSanitization
    title: Training Data Sanitization
    # ... other required fields ...
    mappings:
      mitre-atlas: ["AML.M0005"]
      nist-ai-rmf: ["MP-4.1"]
    lifecycleStage:
      - development
      - evaluation
    impactType:
      - integrity
      - privacy
    actorAccess:
      - supply-chain
```

---

## Extended Metadata Fields

In addition to `mappings`, risks and controls support three additional metadata fields:

### lifecycleStage

Indicates which AI system lifecycle phases are relevant:

```yaml
lifecycleStage:
  - planning        # Initial planning and design
  - development     # Model training and development
  - evaluation      # Testing and validation
  - deployment      # Production deployment
  - runtime         # Active operation
  - maintenance     # Updates and monitoring
```

### impactType

Categorizes the security, privacy, or safety impacts:

```yaml
impactType:
  - confidentiality  # Data/model confidentiality
  - integrity        # Data/model integrity
  - availability     # System availability
  - privacy          # User privacy
  - safety           # Physical or operational safety
  - compliance       # Regulatory compliance
  - fairness         # Fairness and bias
  - accountability   # Accountability and attribution
  - reliability      # System reliability
  - transparency     # Model transparency
```

### actorAccess

Specifies the level of system access required by threat actors:

```yaml
actorAccess:
  - none                    # No access required (external attacks)
  - api                     # API access only
  - user                    # Standard user access
  - privileged              # Elevated privileges
  - agent                   # Agent/plugin access
  - supply-chain            # Supply chain position
  - infrastructure-provider # Infrastructure provider access
  - service-provider        # Service provider access
  - physical                # Physical access
```

---

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
    - development
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
    - development
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

1. **Framework ID Validation**: All keys in the `mappings` object must match framework IDs defined in the enum
2. **Array Values**: Each framework mapping must be an array of strings
3. **Optional Fields**: All four extended metadata fields (`mappings`, `lifecycleStage`, `impactType`, `actorAccess`) are optional
4. **Enum Constraints**: Values in `lifecycleStage`, `impactType`, and `actorAccess` must match predefined enums
5. **Framework ID Consistency**: The `id` field in each framework definition must match its YAML key

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

**Error:** `Missing required field: id`

**Solution:** Every framework definition must include the required fields: `id`, `name`, `description`, `baseUri`

### ID Mismatch

**Error:** Framework ID in YAML doesn't match the key

**Solution:** The `id` field must exactly match the YAML key:
```yaml
# Correct
mitre-atlas:
  id: mitre-atlas

# Incorrect
mitre-atlas:
  id: mitre_atlas
```

---

## Related Documentation

- [Adding a Risk](guide-risks.md) - Complete guide for adding new risks
- [Adding a Control](guide-controls.md) - Complete guide for adding new controls
- [Validation Tools](validation.md) - Schema validation and testing
- [Workflow](workflow.md) - General contribution workflow

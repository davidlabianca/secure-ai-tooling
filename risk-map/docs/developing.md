# Expanding the CoSAI Risk Map

> This guide complements the repository-wide [`CONTRIBUTING.md`](../../CONTRIBUTING.md). Use that for branching, commit/PR workflow, code review expectations, and CLA. This document focuses on how to author and validate Risk Map content (schemas and YAML).
>
> *Note: all contributions discussed in this document would fall under the [Content Update Process](../../CONTRIBUTING.md#content-update-governance-process) covered in detail in the `CONTRIBUTING.md` document*

This guide outlines how you can contribute to the Coalition for Secure AI (CoSAI) Risk Map. By following these steps, you can help expand the framework while ensuring your contributions are consistent with the project's structure and pass all validation checks.

## Prerequisites

Before contributing to the Risk Map, ensure you have the necessary validation tools set up:

### Setting Up Pre-commit Hooks

The repository includes automated schema validation, component edge consistency checks, and control-to-risk reference validation via git pre-commit hooks. 

1. **Install the pre-commit hook (one-time setup)**:
   ```bash
   # From the repository root
   bash ./scripts/install-precommit-hook.sh
   ```

2. **Verify the hook is working**:
   ```bash
   # Make a test change to risk-map/yaml/components.yaml
   # Attempt to commit - the hook should run validation
   git add risk-map/yaml/components.yaml
   git commit -m "test commit"
   ```

### Manual Edge Validation

You can also run edge validation manually at any time:

```bash
# Validate only if components.yaml is staged for commit
python scripts/hooks/validate_component_edges.py

# Force validation regardless of git status
python scripts/hooks/validate_component_edges.py --force
```

The validation script checks for:
- **Bidirectional edge consistency**: If Component A references Component B in its `to` edges, Component B must have Component A in its `from` edges
- **No isolated components**: Components should have at least one `to` or `from` edge
- **Valid component references**: All components referenced in edges must exist

*See [scripts documentation](../../scripts/README.md) for more information on the git hooks and validation.*

### Manual Control-to-Risk Reference Validation

You can run control-to-risk reference validation at any time:

```bash
# Validate control-to-risk references if at least on of controls.yaml or risks.yaml is staged
python scripts/hooks/validate_control_risk_references.py

# Force control-to-risk references validation regardless of git status
python scripts/hooks/validate_control_risk_references.py --force
```

The control-to-risk validates cross-reference consistency between `controls.yaml` and `risks.yaml`:
- **Bidirectional consistency**: Ensures that if a control lists a risk, that risk also references the control
- **Isolated entry detection**: Finds controls with no risk references or risks with no control references
- **all or none awareness**: Will not flag controls that leverage the `all` or `none` risk mappings

## General Content Contribution Workflow

1. Read the repository-wide [CONTRIBUTING.md](../../CONTRIBUTING.md) and follow the [Content Update Branching Process](../../CONTRIBUTING.md#for-content-updates-two-stage-process) for all content authoring
2. **Set up pre-commit hooks** (see Prerequisites above)
3. Make content changes per the guides below (components, controls, risks, personas)
4. **Validate your changes** against the relevant JSON Schemas and edge consistency rules
5. Open a PR against the `develop` branch describing the Risk Map updates and validation performed

---

## Contribution Guides

1.  [Adding a new component](#adding-a-component)
2.  [Adding a new control](#adding-a-control)
3.  [Adding a new risk](#adding-a-risk)
4.  [Adding a new persona](#adding-a-persona)

---

## Adding a Component

Once you've determined the need for a new component, the following steps are required to integrate it into the framework. For this example, we'll add a new component called `componentNewComponent` to the "Application" category.

### 1. Add the new component ID to the schema

First, declare the new component's unique ID in the schema. This makes the system aware of the new component and allows for validation.

* **File to edit**: `schemas/components.schema.json`
* **Action**: Find the `enum` list under `definitions.component.properties.id` and add your new component's ID. The ID should follow the `component[Name]` convention.

```json
// In schemas/components.schema.json
"id": {
  "type": "string",
  "enum": [
    ...
    "componentAgentPlugin",
    "componentNewComponent" // Add your new component ID here
  ]
},
```

### 2. Add the new component definition to the YAML file

Next, define the properties of your new component in the main data file. This includes its ID, title, a detailed description, and its category.

* **File to edit**: `components.yaml`
* **Action**: Add a new entry to the `components` list.

```yaml
# In yaml/components.yaml
- id: componentNewComponent
  title: New Component
  description:
  - >
    A detailed description of what this new component represents in the
    AI development lifecycle and why it is important for understanding risk.
  category: componentsApplication # Must match an id from the components.schema.json#/definitions/category/properties/id
  edges:
    to: []
    from: []
```

### 3. Define Edges for the New Component

Now, define the connections for your new component within its own `edges` block. The `to` list specifies where your component sends data (outgoing), and the `from` list specifies where it receives data from (incoming).

⚠️ **Critical**: Component edges must be **bidirectionally consistent**. The pre-commit hook will enforce this rule.

* **File to edit**: `components.yaml`
* **Action**: Update the `edges` block for `componentNewComponent`. For our example, let's say it receives data from `componentInputHandling` and sends data to `componentApplication`.

```yaml
# In yaml/components.yaml, under your new component's definition
  edges:
    to:
      - componentApplication # Outgoing connection
    from:
      - componentInputHandling # Incoming connection
```

### 4. Update Edges on Connected Components

To make the connections bidirectional, you must now update the corresponding `edges` on the components you just referenced. **This step is critical** - the pre-commit hook will prevent commits if edges are not bidirectionally consistent.

* **File to edit**: `components.yaml`
* **Action**:
    1.  Find the `componentInputHandling` definition and add `componentNewComponent` to its `edges.to` list.
    2.  Find the `componentApplication` definition and add `componentNewComponent` to its `edges.from` list.

```yaml
# In the componentInputHandling definition:
- id: componentInputHandling
  ...
  edges:
    to:
      - componentTheModel
      - componentNewComponent # Add outgoing edge to your new component
    from:
      - componentApplication

# In the componentApplication definition:
- id: componentApplication
  ...
  edges:
    to:
      - componentInputHandling
      - componentAgentPlugin
    from:
      - componentOutputHandling
      - componentNewComponent # Add incoming edge from your new component
```

### 5. Validate Edge Consistency

Before committing, validate that your component edges are consistent:

```bash
# Manual validation (recommended during development)
python scripts/validate_component_edges.py --force

# The pre-commit hook will also run automatically when you commit
git add risk-map/yaml/components.yaml
git commit -m "Add componentNewComponent with proper edge relationships"
```

The validation will check:
- ✅ All outgoing edges (`to`) have corresponding incoming edges (`from`) in target components
- ✅ All incoming edges (`from`) have corresponding outgoing edges (`to`) in source components  
- ✅ No components are isolated (unless intentionally designed)
- ✅ All referenced components exist in the YAML file

### 6. Create a Pull Request

After successful validation, follow the [General Content Contribution Workflow](#general-content-contribution-workflow) to create your pull request.

---

## Adding a Control

Adding a new control involves defining it and then mapping it to the components, personas, and risks it affects. For this example, let's add a hypothetical `controlNewControl`.

### 1. Add the new control ID to the schema

First, declare the new control's unique ID in the `controls.schema.json` file. This registers the new control with the framework. The ID should follow the `control[Name]` convention.

* **File to edit**: `schemas/controls.schema.json`
* **Action**: Find the `enum` list under `definitions.control.properties.id` and add your new control ID alphabetically.

```json
// In schemas/controls.schema.json
"id": {
  "type": "string",
  "enum": [
    ...
    "controlApplicationAccessManagement",
    "controlNewControl", // Add your new control ID here
    "controlIncidentResponseManagement",
    ...
  ]
},
```

### 2. Add the new control definition to the YAML file

Next, define the control's properties in the main `controls.yaml` data file. This is where you describe what the control is and map it to other parts of the framework.

* **File to edit**: `controls.yaml`
* **Action**: Add a new entry to the `controls` list. When filling out the properties, you must select valid IDs from the other schema files.

> **Note on universal controls**: For controls that apply broadly (e.g., governance or assurance tasks), you can use the string `"all"` for `components` and `risks`. For controls that don't apply to any specific component, use `"none"`.

```yaml
# Example of a specific control
- id: controlNewControl
  title: A New and Important Control
  description:
  - >
    A clear and concise description of what this control does, how it works,
    and why it is an effective safeguard.
  category: controlsModel
  personas:
  - personaModelCreator
  - personaModelConsumer
  components:
  - componentTheModel
  - componentOutputHandling
  risks:
  - IMO # Mapped to Insecure Model Output
  - PIJ # Mapped to Prompt Injection

# Example of a universal (governance) control
- id: controlRedTeaming
  title: Red Teaming
  description:
  - >
    Drive security and privacy improvements through self-driven adversarial attacks
    on AI infrastructure and products.
  category: controlsAssurance
  personas:
  - personaModelCreator
  - personaModelConsumer
  components: all # This control applies to all components
  risks: all # This control applies to all risks
```

### 3. Update Corresponding Risks

To ensure the framework remains fully connected, every risk that your new control mitigates must be updated to include a reference to that control. (This step is not necessary if you set `risks: all` in the previous step).

* **File to edit**: `risks.yaml`
* **Action**: For each risk ID you listed in the previous step (e.g., `IMO`, `PIJ`), find its definition in `risks.yaml` and add your new `controlNewControl` ID to its `controls` list.

```yaml
# In yaml/risks.yaml, under the IMO risk definition
- id: IMO
  # ... other properties
  controls:
  - controlOutputValidationAndSanitization
  - controlNewControl # Add your new control here
```

### 4. Validate Control-Risk References
Before committing, validate that your control-risk cross-references are consistent:

```bash
# Manual validation (recommended during development)
python scripts/validate_control_risk_references.py --force

# The pre-commit hook will also run automatically when you commit
git add risk-map/yaml/controls.yaml risk-map/yaml/risks.yaml
git commit -m "Add new control CTRL-005 with proper risk relationships"
```

The validation will check:
- ✅ All controls that list risks in `controls.yaml` are referenced back by those risks in `risks.yaml`
- ✅ All risks that reference controls in `risks.yaml` have those controls listing them in `controls.yaml`
- ✅ No isolated entries (controls with empty risk lists, risks with empty control lists)

**Example of consistent cross-references:**
```yaml
# controls.yaml
controls:
  - id: CTRL-001
    risks:  # Control addresses these risks
    - RISK-001
    - RISK-002 
    
# risks.yaml  
risks:
  - id: RISK-001
    controls:
    - CTRL-001         # Risk acknowledges this control
  - id: RISK-002
    controls:
    - CTRL-001         # Bidirectional consistency ✅
```

### 5. Validate and Create a Pull Request

Once validated, follow the [General Content Contribution Workflow](#general-content-contribution-workflow) to create your pull request.

---

## Adding a Risk

Risks represent the potential security threats that can affect the components of an AI system. Adding a new risk requires defining it and then connecting it to the controls that mitigate it.

### 1. Add the new risk ID to the schema

First, add a unique ID for the new risk to the `risks.schema.json` file. The ID should be a short, memorable, all-caps acronym.

* **File to edit**: `schemas/risks.schema.json`
* **Action**: Find the `enum` list under `definitions.risk.properties.id` and add your new risk ID alphabetically.

```json
// In schemas/risks.schema.json
"id": {
  "type": "string",
  "enum": ["DMS", "DP", "EDH", "IIC", "IMO", "ISD", "MDT", "MEV", "MRE", "MST", "MXF", "NEW", "PIJ", "RA", "SDD", "UTD"]
},
```

### 2. Add the new risk definition to the YAML file

Next, provide the full definition of the risk in `risks.yaml`. This includes its title, descriptions, associated personas, mitigating controls, and contextual information.

* **File to edit**: `risks.yaml`
* **Action**: Add a new entry to the `risks` list. The `personas` and `controls` lists must contain valid IDs from their respective schema files.

```yaml
# In yaml/risks.yaml
- id: NEW
  title: New Example Risk
  shortDescription:
  - >
    A brief, one-sentence explanation of the new risk.
  longDescription:
  - >
    A more detailed explanation of the risk, including how it can manifest
    and what its potential impact is.
  personas:
  - personaModelConsumer
  controls:
  - controlNewControl
  examples: # Provide links to real-world examples or research
  - >
    A link to a real-world example or research paper describing this risk.
  tourContent: # Describe how the risk appears in the lifecycle map
    introduced:
    - >
      Where in the lifecycle this risk is typically introduced.
    exposed:
    - >
      Where in the lifecycle this risk is typically exposed or exploited.
    mitigated:
    - >
      Where in the lifecycle this risk is typically mitigated.
```

### 3. Update Corresponding Controls

To ensure the framework remains fully connected, every control that mitigates your new risk must be updated to include a reference back to that risk.

* **File to edit**: `controls.yaml`
* **Action**: For each control ID you listed in the previous step (e.g., `controlNewControl`), find its definition in `controls.yaml` and add your new risk's ID (`NEW`) to its `risks` list.

```yaml
# In yaml/controls.yaml, under the controlNewControl definition
- id: controlNewControl
  # ... other properties
  risks:
  - IMO
  - PIJ
  - NEW # Add your new risk ID here
```

### 4. Validate Control-Risk References
Before committing, validate that your control-to-risk cross-references are consistent:

```bash
# Manual validation (recommended during development)
python scripts/validate_control_risk_references.py --force

# The pre-commit hook will also run automatically when you commit
git add risk-map/yaml/controls.yaml risk-map/yaml/risks.yaml
git commit -m "Add new control CTRL-005 with proper risk relationships"
```

The validation will check:
- ✅ All controls that list risks in `controls.yaml` are referenced back by those risks in `risks.yaml`
- ✅ All risks that reference controls in `risks.yaml` have those controls listing them in `controls.yaml`
- ✅ No isolated entries (controls with empty risk lists, risks with empty control lists)

**Example of consistent cross-references:**
```yaml
# controls.yaml
controls:
  - id: CTRL-001
    risks:  # Control addresses these risks
    - RISK-001
    - RISK-002 
    
# risks.yaml  
risks:
  - id: RISK-001
    controls:
    - CTRL-001         # Risk acknowledges this control
  - id: RISK-002
    controls:
    - CTRL-001         # Bidirectional consistency ✅
```

### 5. Validate and Create a Pull Request

Once validated, follow the [General Content Contribution Workflow](#general-content-contribution-workflow) to create your pull request.

---

## Adding a Persona

Personas define the key roles and responsibilities within the AI ecosystem. Adding a new persona is a straightforward process.

### 1. Add the new persona ID to the schema

First, declare the new persona's unique ID in the `personas.schema.json` file. The ID should follow the `persona[Name]` convention.

* **File to edit**: `schemas/personas.schema.json`
* **Action**: Find the `enum` list under `definitions.persona.properties.id` and add your new persona ID.

```json
// In schemas/personas.schema.json
"id": {
  "type": "string",
  "enum": ["personaModelCreator", "personaModelConsumer", "personaNewPersona"]
},
```

### 2. Add the new persona definition to the YAML file

Next, provide the definition for the new persona in the `personas.yaml` file.

* **File to edit**: `personas.yaml`
* **Action**: Add a new entry to the `personas` list with an `id`, `title`, and `description`.

```yaml
# In yaml/personas.yaml
- id: personaNewPersona
  title: New Persona
  description:
  - >
    A description of this new role, its responsibilities, and its
    relationship to the AI lifecycle.
```

### 3. Update Existing Risks and Controls

If this new persona is affected by existing risks or is responsible for implementing existing controls, you must update the corresponding YAML files to reflect this.

* **Files to edit**: `risks.yaml`, `controls.yaml`
* **Action**: Review the existing risks and controls. Add the `personaNewPersona` ID to the `personas` list of any relevant entry.

```yaml
# In yaml/controls.yaml, for an existing control:
- id: controlRiskGovernance
  # ... other properties
  personas:
  - personaModelCreator
  - personaModelConsumer
  - personaNewPersona # Add the new persona if they are responsible
```

### 4. Validate and Create a Pull Request

After making your changes, use a JSON schema validator to ensure that your updated files conform to their schemas. Once validated, follow the [General Content Contribution Workflow](#general-content-contribution-workflow) to create your pull request.

---

## Troubleshooting Validation Issues

### Edge Validation Errors

If the pre-commit hook or manual validation fails with edge consistency errors:

1. **Bidirectional Edge Mismatch**: 
   ```
   Component 'componentA': missing incoming edges for: componentB
   ```
   **Fix**: Add `componentA` to `componentB`'s `edges.from` list

2. **Isolated Component**:
   ```
   Found 1 isolated components (no edges): componentX
   ```
   **Fix**: Add appropriate `to` and/or `from` edges, or verify if isolation is intentional

### Bypassing Validation (Not Recommended)

If you need to commit without running the pre-commit hook (strongly discouraged):
```bash
git commit --no-verify -m "commit message"
```

However, your changes will still be validated during the PR review process.

---

## Best Practices

1. **Always run manual validation** during development:
   ```bash
   python scripts/validate_component_edges.py --force
   ```

2. **Test edge changes incrementally** - add one component connection at a time

3. **Document complex edge relationships** in commit messages

4. **Use meaningful component IDs** following the `component[Name]` convention

5. **Validation against JSON schemas** is enforced by the pre-commit otherwise validate before committing 

6. **Review existing components** to understand established patterns before adding new ones
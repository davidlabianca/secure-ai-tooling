# Adding a Persona

Personas define the key roles and responsibilities within the AI ecosystem. Adding a new persona is a straightforward process.

## 1. Add the new persona ID to the schema

First, declare the new persona's unique ID in the `personas.schema.json` file. The ID should follow the `persona[Name]` convention.

- **File to edit**: `schemas/personas.schema.json`
- **Action**: Find the `enum` list under `definitions.persona.properties.id` and add your new persona ID.

```json
// In schemas/personas.schema.json
"id": {
  "type": "string",
  "enum": ["personaModelCreator", "personaModelConsumer", "personaNewPersona"]
},
```

## 2. Add the new persona definition to the YAML file

Next, provide the definition for the new persona in the `personas.yaml` file.

- **File to edit**: `personas.yaml`
- **Action**: Add a new entry to the `personas` list with an `id`, `title`, and `description`.

```yaml
# In yaml/personas.yaml
- id: personaNewPersona
  title: New Persona
  description:
    - >
      A description of this new role, its responsibilities, and its
      relationship to the AI lifecycle.
```

## 3. Update Existing Risks and Controls

If this new persona is affected by existing risks or is responsible for implementing existing controls, you must update the corresponding YAML files to reflect this.

- **Files to edit**: `risks.yaml`, `controls.yaml`
- **Action**: Review the existing risks and controls. Add the `personaNewPersona` ID to the `personas` list of any relevant entry.

```yaml
# In yaml/controls.yaml, for an existing control:
- id: controlRiskGovernance
  # other properties
  personas:
    - personaModelCreator
    - personaModelConsumer
    - personaNewPersona # Add the new persona if they are responsible
```

## 4. Validate and Create a Pull Request

After making your changes, use a JSON schema validator to ensure that your updated files conform to their schemas. Once validated, follow the [General Content Contribution Workflow](workflow.md) to create your pull request.

---

**Related:**
- [Validation Tools](validation.md) - Detailed validation commands
- [General Content Contribution Workflow](workflow.md) - Overall contribution process

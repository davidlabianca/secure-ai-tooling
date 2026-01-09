"""
TemplateRenderer for GitHub issue template generation.

This module provides the TemplateRenderer class which renders GitHub issue
templates by expanding placeholders and filtering frameworks based on applicability.
"""

import re
from typing import Any

import yaml

from .schema_parser import SchemaParser


class TemplateRenderer:
    """
    Render GitHub issue templates with dynamic content.

    This class processes template files by:
    1. Expanding placeholders with enum values from schemas
    2. Filtering frameworks based on entity type applicability

    Attributes:
        schema_parser: SchemaParser instance for accessing enum values
        frameworks_data: Dictionary containing frameworks configuration
    """

    # Valid entity types
    VALID_ENTITY_TYPES = {"controls", "risks", "components", "personas"}

    # Placeholder mappings to schema paths with field type metadata
    # Field types determine output format:
    # - "dropdown": Plain strings for GitHub dropdown fields (e.g., "- controlsData")
    # - "checkbox": Label-only objects for GitHub checkbox fields (e.g., "- label: personaModelCreator")
    # - None: Fallback format with label and value (for textarea/markdown context)
    PLACEHOLDER_MAPPINGS = {
        # Dropdowns - plain string format required
        "CONTROL_CATEGORIES": {
            "schema_paths": [("controls.schema.json", "definitions.category.properties.id")],
            "field_type": "dropdown",
        },
        "RISK_CATEGORIES": {
            "schema_paths": [
                ("risks.schema.json", "definitions.risk.properties.category"),
                ("risks.schema.json", "definitions.category.properties.id"),  # Fallback for test fixtures
            ],
            "field_type": "dropdown",
        },
        "COMPONENT_CATEGORIES": {
            "schema_paths": [("components.schema.json", "definitions.category.properties.id")],
            "field_type": "dropdown",
        },
        # Checkboxes - label-only object format required
        "PERSONAS": {
            "schema_paths": [("personas.schema.json", "definitions.persona.properties.id")],
            "field_type": "checkbox",
        },
        "LIFECYCLE_STAGE": {
            "schema_paths": [("lifecycle-stage.schema.json", "definitions.lifecycleStage.properties.id")],
            "field_type": "checkbox",
        },
        "IMPACT_TYPE": {
            "schema_paths": [("impact-type.schema.json", "definitions.impactType.properties.id")],
            "field_type": "checkbox",
        },
        "ACTOR_ACCESS": {
            "schema_paths": [("actor-access.schema.json", "definitions.actorAccessLevel.properties.id")],
            "field_type": "checkbox",
        },
        # Not used in dropdowns/checkboxes - fallback format for textarea/markdown context
        "COMPONENTS": {
            "schema_paths": [("components.schema.json", "definitions.component.properties.id")],
            "field_type": None,
        },
        "CONTROLS": {
            "schema_paths": [("controls.schema.json", "definitions.control.properties.id")],
            "field_type": None,
        },
        "RISKS": {"schema_paths": [("risks.schema.json", "definitions.risk.properties.id")], "field_type": None},
    }

    def __init__(self, schema_parser: SchemaParser, frameworks_data: dict[str, Any]) -> None:
        """
        Initialize TemplateRenderer.

        Args:
            schema_parser: SchemaParser instance for schema access
            frameworks_data: Dictionary from frameworks.yaml

        Raises:
            TypeError: If schema_parser or frameworks_data is None
            ValueError: If frameworks_data has invalid structure
        """
        if schema_parser is None:
            raise TypeError("schema_parser is required and cannot be None")

        if frameworks_data is None:
            raise TypeError("frameworks_data is required and cannot be None")

        if not isinstance(frameworks_data, dict):
            raise ValueError("frameworks_data must be a dictionary")

        if "frameworks" not in frameworks_data:
            raise ValueError("frameworks_data must contain 'frameworks' key")

        self.schema_parser = schema_parser
        self.frameworks_data = frameworks_data

    def expand_placeholders(self, template_content: str, entity_type: str) -> str:
        """
        Expand all placeholders in template with enum values.

        Replaces placeholders like {{CONTROL_CATEGORIES}} with actual enum
        values from schemas, maintaining proper YAML formatting. Output format
        depends on field type:
        - dropdown: Plain strings (e.g., "- controlsData")
        - checkbox: Label-only objects (e.g., "- label: personaModelCreator")
        - None: Fallback format with label and value

        Args:
            template_content: Raw template content with placeholders
            entity_type: Type of entity (controls, risks, components, personas)

        Returns:
            Template content with placeholders replaced

        Raises:
            ValueError: If entity_type is invalid
            FileNotFoundError: If required schema file is missing
        """
        if entity_type not in self.VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity type: {entity_type}. Must be one of {self.VALID_ENTITY_TYPES}")

        if not template_content:
            return template_content

        # Find all placeholders using regex (case-insensitive)
        pattern = r"\{\{([A-Z_]+)\}\}"

        def replace_placeholder(match: re.Match) -> str:
            placeholder_name = match.group(1).upper()  # Normalize to uppercase
            full_match = match.group(0)

            # Get the line containing the placeholder to determine indentation
            match_start = match.start()
            line_start = template_content.rfind("\n", 0, match_start) + 1
            line = template_content[line_start:match_start]
            indentation = line  # Use the existing indentation before the placeholder

            # Handle framework-related placeholders specially
            if placeholder_name == "FRAMEWORK_MAPPINGS":
                # Generate framework mapping sections as YAML
                sections = self.expand_framework_mappings(entity_type)
                if not sections:
                    return ""

                # Convert sections to YAML format
                yaml_lines = []
                for i, section in enumerate(sections):
                    # Serialize section to YAML
                    section_yaml = yaml.dump(section, default_flow_style=False, sort_keys=False)
                    # Split into lines and add indentation
                    section_lines = section_yaml.strip().split("\n")

                    if i == 0:
                        # First section - no leading indentation (replaces placeholder inline)
                        yaml_lines.append(f"- {section_lines[0]}")
                        yaml_lines.extend(f"{indentation}  {line}" for line in section_lines[1:])
                    else:
                        # Subsequent sections - add indentation
                        yaml_lines.append(f"\n{indentation}- {section_lines[0]}")
                        yaml_lines.extend(f"{indentation}  {line}" for line in section_lines[1:])

                return "\n".join(yaml_lines)

            elif placeholder_name == "CONTROL_FRAMEWORKS_LIST":
                # Return comma-separated list of frameworks for controls
                return self.get_frameworks_list("controls")

            elif placeholder_name == "RISK_FRAMEWORKS_LIST":
                # Return comma-separated list of frameworks for risks
                return self.get_frameworks_list("risks")

            # Check if we have a mapping for this placeholder
            if placeholder_name not in self.PLACEHOLDER_MAPPINGS:
                # Unknown placeholder - leave as-is
                return full_match

            # Get mapping configuration
            mapping = self.PLACEHOLDER_MAPPINGS[placeholder_name]
            schema_paths = mapping["schema_paths"]
            field_type = mapping.get("field_type")

            # Try each path mapping until one works
            enum_values = None
            for schema_file, field_path in schema_paths:
                try:
                    # Load schema and extract enum values (let FileNotFoundError propagate)
                    schema_data = self.schema_parser.load_schema(schema_file)
                    enum_values = self.schema_parser.extract_enum_values(schema_data, field_path)
                    break  # Success - stop trying other paths
                except KeyError:
                    # This path doesn't exist, try next one
                    continue

            if enum_values is None:
                # None of the paths worked - leave placeholder as-is
                return full_match

            if not enum_values:
                # Empty enum - return empty string
                return ""

            # Format based on field type
            yaml_lines = []

            if field_type == "dropdown":
                # Plain strings for dropdown fields (no label/value, no quotes)
                for i, value in enumerate(enum_values):
                    if i == 0:
                        # First item - no leading indentation (replaces placeholder inline)
                        yaml_lines.append(f"- {value}")
                    else:
                        # Subsequent items - add indentation to align
                        yaml_lines.append(f"{indentation}- {value}")

            elif field_type == "checkbox":
                # Label-only objects for checkbox fields (no value field, no quotes)
                for i, value in enumerate(enum_values):
                    if i == 0:
                        # First item - no leading indentation (replaces placeholder inline)
                        yaml_lines.append(f"- label: {value}")
                    else:
                        # Subsequent items - add indentation to align
                        yaml_lines.append(f"{indentation}- label: {value}")

            else:
                # Fallback for field_type=None (textarea context)
                # Keep current behavior for backwards compatibility
                for i, value in enumerate(enum_values):
                    if i == 0:
                        # First item - no leading indentation (replaces placeholder inline)
                        yaml_lines.append(f'- label: "{value}"\n{indentation}  value: {value}')
                    else:
                        # Subsequent items - add indentation to align
                        yaml_lines.append(f'{indentation}- label: "{value}"\n{indentation}  value: {value}')

            return "\n".join(yaml_lines)

        # Replace all placeholders
        result = re.sub(pattern, replace_placeholder, template_content, flags=re.IGNORECASE)
        return result

    def filter_frameworks_by_applicability(self, entity_type: str) -> list[str]:
        """
        Filter frameworks applicable to entity_type.

        Returns list of framework IDs that have entity_type in their
        applicableTo field.

        Args:
            entity_type: Type of entity (controls, risks, components, personas)

        Returns:
            List of framework IDs applicable to entity_type

        Raises:
            ValueError: If entity_type is invalid
        """
        if entity_type not in self.VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity type: {entity_type}. Must be one of {self.VALID_ENTITY_TYPES}")

        frameworks = self.frameworks_data.get("frameworks", [])

        result = []
        for framework in frameworks:
            applicable_to = framework.get("applicableTo", [])
            if entity_type in applicable_to:
                result.append(framework["id"])

        return result

    def get_frameworks_list(self, entity_type: str) -> str:
        """
        Get comma-separated list of framework IDs applicable to entity type.

        Used for {{CONTROL_FRAMEWORKS_LIST}} and {{RISK_FRAMEWORKS_LIST}} placeholders
        in "update" template descriptions.

        Args:
            entity_type: Entity type ("controls", "risks", "components", "personas")

        Returns:
            Comma-separated string of framework IDs (e.g., "mitre-atlas, nist-ai-rmf")

        Raises:
            ValueError: If entity_type is invalid
        """
        # Use existing filter_frameworks_by_applicability method
        framework_ids = self.filter_frameworks_by_applicability(entity_type)

        # Return comma-separated string
        return ", ".join(framework_ids)

    def expand_framework_mappings(self, entity_type: str) -> list[dict[str, Any]]:
        """
        Expand {{FRAMEWORK_MAPPINGS}} placeholder into framework textarea sections.

        Generates full GitHub issue form textarea fields for each applicable framework.
        Used in "new" templates (new_control.yml, new_risk.yml).

        Args:
            entity_type: Entity type ("controls", "risks", etc.)

        Returns:
            List of dictionaries, each representing a textarea section with structure:
            - type: textarea
            - id: mapping-{framework-id}
            - attributes: label, description, placeholder
            - validations: required: false

        Raises:
            ValueError: If entity_type is invalid
        """
        # Validate entity type
        if entity_type not in self.VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity type: {entity_type}. Must be one of {self.VALID_ENTITY_TYPES}")

        # Get frameworks applicable to this entity type
        applicable_framework_ids = self.filter_frameworks_by_applicability(entity_type)

        # Build list of framework sections
        sections = []
        frameworks = self.frameworks_data.get("frameworks", [])

        for framework in frameworks:
            framework_id = framework["id"]

            # Skip frameworks not applicable to this entity type
            if framework_id not in applicable_framework_ids:
                continue

            # Extract framework details
            framework_name = framework.get("name", framework_id)
            base_uri = framework.get("baseUri", "")

            # Build description with framework details
            description = f"Mapping to {framework_name}"
            if base_uri:
                description += f" ({base_uri})"

            # Create textarea section
            section = {
                "type": "textarea",
                "id": f"mapping-{framework_id}",
                "attributes": {
                    "label": framework_name,
                    "description": description,
                    "placeholder": f"Enter {framework_name} reference(s)",
                },
                "validations": {"required": False},
            }

            sections.append(section)

        return sections

    def render_template(self, template_content: str, entity_type: str) -> str:
        """
        Main template rendering method.

        Performs all rendering operations:
        1. Expand placeholders with enum values from schemas

        Args:
            template_content: Raw template content
            entity_type: Type of entity (controls, risks, components, personas)

        Returns:
            Fully rendered template content

        Raises:
            ValueError: If entity_type is invalid
            FileNotFoundError: If required schema files are missing
        """
        # Validate entity type (will raise ValueError if invalid)
        if entity_type not in self.VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity type: {entity_type}. Must be one of {self.VALID_ENTITY_TYPES}")

        # Expand placeholders
        result = self.expand_placeholders(template_content, entity_type)

        return result

"""
TemplateRenderer for GitHub issue template generation.

This module provides the TemplateRenderer class which renders GitHub issue
templates by expanding placeholders and filtering frameworks based on applicability.

Part of the IssueTemplateGenerator system (Phase 3, Week 5).
"""

import re
from typing import Any

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

    # Placeholder mappings to schema paths
    # Some placeholders have fallback paths for backward compatibility with test fixtures
    PLACEHOLDER_MAPPINGS = {
        "CONTROL_CATEGORIES": [("controls.schema.json", "definitions.category.properties.id")],
        "RISK_CATEGORIES": [
            ("risks.schema.json", "definitions.risk.properties.category"),
            ("risks.schema.json", "definitions.category.properties.id"),  # Fallback for test fixtures
        ],
        "PERSONAS": [("personas.schema.json", "definitions.persona.properties.id")],
        "COMPONENTS": [("components.schema.json", "definitions.component.properties.id")],
        "CONTROLS": [("controls.schema.json", "definitions.control.properties.id")],
        "RISKS": [("risks.schema.json", "definitions.risk.properties.id")],
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
        values from schemas, maintaining proper YAML formatting.

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

            # Check if we have a mapping for this placeholder
            if placeholder_name not in self.PLACEHOLDER_MAPPINGS:
                # Unknown placeholder - leave as-is
                return full_match

            # Try each path mapping until one works
            path_mappings = self.PLACEHOLDER_MAPPINGS[placeholder_name]
            enum_values = None

            for schema_file, field_path in path_mappings:
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

            # Format as YAML list with proper indentation
            # First item replaces placeholder inline (no leading indentation)
            # Subsequent items need indentation to align with first item
            yaml_lines = []
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

"""
SchemaParser for extracting enum values and required fields from JSON schemas.

This module provides the SchemaParser class which reads JSON schema files
and extracts information needed for GitHub issue template generation.
"""

import json
from pathlib import Path
from typing import Any

import yaml


class SchemaParser:
    """
    Parse JSON schemas to extract enum values and required fields.

    This class loads JSON schema files and provides methods to extract
    enum values, required fields, and other metadata needed for generating
    GitHub issue templates.

    Attributes:
        schema_dir: Path to directory containing JSON schema files
        yaml_data_dir: Optional path to directory containing YAML data files
    """

    def __init__(self, schema_dir: Path, yaml_data_dir: Path | None = None) -> None:
        """
        Initialize SchemaParser with schema directory.

        Args:
            schema_dir: Path to directory containing JSON schema files
            yaml_data_dir: Optional path to directory containing YAML data files
                           (required only if load_deprecated_ids() will be called)

        Raises:
            FileNotFoundError: If schema_dir doesn't exist
            NotADirectoryError: If schema_dir is not a directory
        """
        if not schema_dir.exists():
            raise FileNotFoundError(f"Schema directory '{schema_dir}' does not exist")

        if not schema_dir.is_dir():
            raise NotADirectoryError(f"'{schema_dir}' is not a directory")

        self.schema_dir = schema_dir
        self.yaml_data_dir = yaml_data_dir
        self._deprecated_ids_cache: dict[tuple[str, str], set[str]] = {}

    def load_schema(self, schema_name: str) -> dict[str, Any]:
        """
        Load a JSON schema file.

        Args:
            schema_name: Name of schema file (e.g., "controls.schema.json")

        Returns:
            Parsed schema as dictionary

        Raises:
            FileNotFoundError: If schema file doesn't exist
            JSONDecodeError: If schema file contains invalid JSON
        """
        schema_path = self.schema_dir / schema_name

        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file '{schema_name}' not found in {self.schema_dir}")

        with open(schema_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_deprecated_ids(self, yaml_filename: str, list_key: str) -> set[str]:
        """
        Load IDs of deprecated entries from a YAML data file.

        Opens yaml_data_dir / yaml_filename, iterates data[list_key], and
        returns the set of entry["id"] values where entry.get("deprecated") is True.
        Results are cached per-instance keyed by (yaml_filename, list_key).

        Args:
            yaml_filename: Name of the YAML file (e.g., "personas.yaml")
            list_key: Top-level key whose value is a list of entries (e.g., "personas")

        Returns:
            Set of deprecated IDs; empty set if none are deprecated

        Raises:
            ValueError: If yaml_data_dir was not configured on this instance
            FileNotFoundError: If yaml_filename does not exist in yaml_data_dir
        """
        if self.yaml_data_dir is None:
            raise ValueError("yaml_data_dir not configured on SchemaParser")

        cache_key = (yaml_filename, list_key)
        if cache_key in self._deprecated_ids_cache:
            return self._deprecated_ids_cache[cache_key]

        yaml_path = self.yaml_data_dir / yaml_filename
        # Let FileNotFoundError propagate naturally if the file is missing
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        deprecated: set[str] = set()
        for entry in data.get(list_key, []):
            if entry.get("deprecated") is True:
                deprecated.add(entry["id"])

        self._deprecated_ids_cache[cache_key] = deprecated
        return deprecated

    def extract_enum_values(self, schema_data: dict[str, Any], field_path: str) -> list[str]:
        """
        Extract enum values from a specific field in schema.

        Args:
            schema_data: Parsed schema dictionary
            field_path: Dot-separated path to field (e.g., "definitions.control.properties.id")

        Returns:
            List of enum values for the field

        Raises:
            KeyError: If field_path doesn't exist or has no enum
            ValueError: If field_path is empty or invalid
        """
        # Validate field path
        if not field_path:
            raise ValueError("Field path cannot be empty")

        if field_path.startswith("."):
            raise ValueError("Invalid field path format: leading dot")

        if field_path.endswith("."):
            raise ValueError("Invalid field path format: trailing dot")

        if ".." in field_path:
            raise ValueError("Invalid field path format: empty component")

        # Navigate to the field location using dot notation
        parts = field_path.split(".")
        current = schema_data

        try:
            for part in parts:
                current = current[part]
        except KeyError:
            raise KeyError(f"Field path '{field_path}' not found in schema")

        # Extract enum from the final location
        if "enum" not in current:
            raise KeyError(f"No enum found at path: {field_path}")

        return current["enum"]

    def get_required_fields(self, schema_data: dict[str, Any]) -> list[str]:
        """
        Get list of required fields from schema.

        Args:
            schema_data: Parsed schema dictionary (or definition within schema)

        Returns:
            List of required field names (empty if no required fields)

        Raises:
            TypeError: If required field is not a list
        """
        if "required" not in schema_data:
            return []

        required = schema_data["required"]

        if required is None:
            raise TypeError("Required field must be a list, not None")

        if not isinstance(required, list):
            raise TypeError("Required field must be a list")

        return required

    def extract_all_enums(self, schema_name: str) -> dict[str, list[str]]:
        """
        Extract all enum fields from a schema.

        Recursively searches the schema and returns a mapping of field paths
        to their enum values.

        Args:
            schema_name: Name of schema file to process

        Returns:
            Dictionary mapping field paths to enum value lists
            Example: {"definitions.control.properties.id": ["ctrl1", "ctrl2"]}

        Raises:
            FileNotFoundError: If schema file doesn't exist
            JSONDecodeError: If schema file contains invalid JSON
        """
        schema_data = self.load_schema(schema_name)
        return self._find_all_enums(schema_data, "")

    def _find_all_enums(self, obj: Any, path_prefix: str) -> dict[str, list[str]]:
        """
        Recursively find all enum fields in a schema object.

        Args:
            obj: Schema object or sub-object to search
            path_prefix: Current path prefix (dot-separated)

        Returns:
            Dictionary mapping field paths to enum values
        """
        if not isinstance(obj, dict):
            return {}

        results: dict[str, list[str]] = {}

        # Check if current object has an enum
        if "enum" in obj:
            results[path_prefix] = obj["enum"]

        # Recursively search nested objects
        for key, value in obj.items():
            # Skip $ref pointers (don't follow them)
            if key == "$ref":
                continue

            # Build new path
            new_path = f"{path_prefix}.{key}" if path_prefix else key

            if isinstance(value, dict):
                # Recurse into nested dict
                results.update(self._find_all_enums(value, new_path))
            elif isinstance(value, list):
                # Handle array items - check each item
                for item in value:
                    if isinstance(item, dict):
                        results.update(self._find_all_enums(item, new_path))

        return results

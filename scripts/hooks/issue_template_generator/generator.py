"""
IssueTemplateGenerator orchestrator for GitHub issue template generation.

This module provides the IssueTemplateGenerator class that combines
SchemaParser and TemplateRenderer to generate GitHub issue templates
from template sources with dynamic placeholder expansion.

Part of the IssueTemplateGenerator system (Phase 3, Week 6).
"""

import difflib
import subprocess
import tempfile
from pathlib import Path

import yaml

from issue_template_generator.schema_parser import SchemaParser
from issue_template_generator.template_renderer import TemplateRenderer


class IssueTemplateGenerator:
    """
    Generate GitHub issue templates from template sources.

    This class orchestrates the template generation process by:
    1. Loading schemas and frameworks data
    2. Discovering available templates
    3. Rendering templates with dynamic content
    4. Writing output files or generating diffs

    Attributes:
        repo_root: Path to repository root
        schemas_dir: Path to schemas directory
        frameworks_yaml: Path to frameworks.yaml file
        templates_dir: Path to template sources directory
        output_dir: Path to output directory for generated templates
        frameworks_data: Loaded frameworks data from YAML
        schema_parser: SchemaParser instance for schema access
        template_renderer: TemplateRenderer instance for rendering
    """

    def __init__(self, repo_root: Path) -> None:
        """
        Initialize IssueTemplateGenerator.

        Args:
            repo_root: Path to repository root directory

        Raises:
            TypeError: If repo_root is None
            FileNotFoundError: If required directories/files are missing
            yaml.YAMLError: If frameworks.yaml has invalid YAML syntax
            ValueError: If frameworks.yaml has invalid structure
        """
        # Validate repo_root
        if repo_root is None:
            raise TypeError("repo_root cannot be None")

        if not repo_root.exists():
            raise FileNotFoundError(f"Repository root '{repo_root}' does not exist")

        self.repo_root = repo_root

        # Define paths
        self.schemas_dir = repo_root / "risk-map" / "schemas"
        self.frameworks_yaml = repo_root / "risk-map" / "yaml" / "frameworks.yaml"
        self.templates_dir = repo_root / "scripts" / "TEMPLATES"
        self.output_dir = repo_root / ".github" / "ISSUE_TEMPLATE"

        # Validate schemas directory exists
        if not self.schemas_dir.exists():
            raise FileNotFoundError(f"Schema directory '{self.schemas_dir}' does not exist")

        # Validate frameworks.yaml exists
        if not self.frameworks_yaml.exists():
            raise FileNotFoundError(f"frameworks.yaml not found at {self.frameworks_yaml}")

        # Validate templates directory exists
        if not self.templates_dir.exists():
            raise FileNotFoundError(f"Template directory '{self.templates_dir}' does not exist")

        # Validate output directory exists
        if not self.output_dir.exists():
            raise FileNotFoundError(f"Output directory '{self.output_dir}' does not exist")

        # Load frameworks.yaml
        try:
            with open(self.frameworks_yaml, "r", encoding="utf-8") as f:
                self.frameworks_data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse frameworks.yaml: {e}") from e

        # Validate frameworks data structure
        if not isinstance(self.frameworks_data, dict):
            raise ValueError("frameworks.yaml must contain a dictionary")

        if "frameworks" not in self.frameworks_data:
            raise ValueError("frameworks.yaml must contain 'frameworks' key")

        # Create SchemaParser and TemplateRenderer instances
        self.schema_parser = SchemaParser(self.schemas_dir)
        self.template_renderer = TemplateRenderer(self.schema_parser, self.frameworks_data)

    def get_available_templates(self) -> list[str]:
        """
        Get list of available template names.

        Searches templates_dir for .template.yml files and extracts
        template names (without .template.yml suffix).

        Returns:
            Sorted list of template names (e.g., ["new_control", "update_risk"])
        """
        if not self.templates_dir.exists():
            return []

        template_files = list(self.templates_dir.glob("*.template.yml"))

        if not template_files:
            return []

        template_names = []
        for template_file in template_files:
            # Extract template name by removing .template.yml suffix
            template_name = template_file.name.replace(".template.yml", "")
            template_names.append(template_name)

        return sorted(template_names)

    def _get_entity_type(self, template_name: str) -> str | None:
        """
        Map template name to entity type.

        Args:
            template_name: Name of template (e.g., "new_control", "update_risk")

        Returns:
            Entity type string or None for infrastructure templates

        Raises:
            ValueError: If template_name is unknown
        """
        # Map template names to entity types
        entity_mappings = {
            "new_control": "controls",
            "update_control": "controls",
            "new_risk": "risks",
            "update_risk": "risks",
            "new_component": "components",
            "update_component": "components",
            "new_persona": "personas",
            "update_persona": "personas",
            "infrastructure": None,  # No entity type for infrastructure
        }

        if template_name not in entity_mappings:
            raise ValueError(f"Unknown template name: {template_name}")

        return entity_mappings[template_name]

    def generate_template(self, template_name: str, dry_run: bool = False) -> Path | str:
        """
        Generate a single template.

        Args:
            template_name: Name of template to generate (without .template.yml)
            dry_run: If True, return diff instead of writing file

        Returns:
            If dry_run=False: Path to generated output file
            If dry_run=True: Diff string (empty if no changes)

        Raises:
            ValueError: If template_name is empty or unknown
            FileNotFoundError: If template file doesn't exist
            UnicodeDecodeError: If template file contains invalid UTF-8
            yaml.YAMLError: If rendered template has invalid YAML
        """
        # Validate template_name
        if not template_name:
            raise ValueError("template_name cannot be empty")

        # Construct template file path and check existence first
        # (before checking entity type, to give better error messages)
        template_file = self.templates_dir / f"{template_name}.template.yml"

        if not template_file.exists():
            raise FileNotFoundError(f"Template file '{template_name}.template.yml' not found")

        # Get entity type for this template (may raise ValueError for unknown templates)
        entity_type = self._get_entity_type(template_name)

        # Read template source (may raise UnicodeDecodeError for corrupted files)
        template_content = template_file.read_text(encoding="utf-8")

        # Render template if entity_type is not None
        if entity_type is not None:
            rendered_content = self.template_renderer.render_template(template_content, entity_type)
        else:
            # Infrastructure template - use as-is
            rendered_content = template_content

        # Validate rendered content is valid YAML (catches corrupted templates)
        try:
            yaml.safe_load(rendered_content)
        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Rendered template is not valid YAML: {e}") from e

        # Determine output path
        output_path = self.output_dir / f"{template_name}.yml"

        # Dry-run mode: generate and return diff
        if dry_run:
            if output_path.exists():
                existing_content = output_path.read_text(encoding="utf-8")
                diff = self._generate_diff(existing_content, rendered_content, output_path)
                return diff
            else:
                # File doesn't exist - would be created
                # Return a message or empty string
                return f"New file: {output_path.name}\n"

        # Write mode: write to output file
        output_path.write_text(rendered_content, encoding="utf-8")
        return output_path

    def _generate_diff(self, old_content: str, new_content: str, filepath: Path) -> str:
        """
        Generate unified diff between old and new content.

        Args:
            old_content: Original file content
            new_content: New content to compare
            filepath: Path to file (for diff headers)

        Returns:
            Unified diff string (empty if no changes)
        """
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff = difflib.unified_diff(
            old_lines, new_lines, fromfile=f"a/{filepath.name}", tofile=f"b/{filepath.name}", lineterm=""
        )

        diff_str = "".join(diff)

        # Return empty string if no changes
        if not diff_str:
            return ""

        return diff_str

    def generate_all_templates(self, dry_run: bool = False) -> dict[str, str | Path]:
        """
        Generate all available templates.

        Args:
            dry_run: If True, return diffs instead of writing files

        Returns:
            Dictionary mapping template names to results:
            - If dry_run=False: Maps to Path objects of generated files
            - If dry_run=True: Maps to diff strings
            - On error: Maps to error message string
        """
        templates = self.get_available_templates()
        results: dict[str, str | Path] = {}

        for template_name in templates:
            try:
                result = self.generate_template(template_name, dry_run=dry_run)
                results[template_name] = result
            except Exception as e:
                # Store error message but continue processing other templates
                results[template_name] = f"Error: {str(e)}"

        return results

    def validate_generated_template(self, template_content: str) -> bool:
        """
        Validate generated template content.

        Validates:
        1. YAML syntax
        2. Required GitHub issue form fields
        3. GitHub schema compliance (using check-jsonschema)

        Args:
            template_content: Template content to validate

        Returns:
            True if valid, False otherwise
        """
        # Check for empty content
        if not template_content or not template_content.strip():
            return False

        # Validate YAML syntax
        try:
            parsed = yaml.safe_load(template_content)
        except yaml.YAMLError:
            return False

        # Check for required fields (name)
        if not isinstance(parsed, dict):
            return False

        if "name" not in parsed:
            return False

        # Validate against GitHub issue form schema using check-jsonschema
        try:
            # Write template to temporary file for validation
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as tmp:
                tmp.write(template_content)
                tmp_path = tmp.name

            try:
                # Run check-jsonschema with GitHub issue forms schema
                result = subprocess.run(
                    ["check-jsonschema", "--builtin-schema", "vendor.github-issue-forms", tmp_path],
                    capture_output=True,
                    text=True,
                    check=False,
                )

                # Return True if validation passed (exit code 0)
                return result.returncode == 0

            finally:
                # Clean up temporary file
                Path(tmp_path).unlink(missing_ok=True)

        except (FileNotFoundError, subprocess.SubprocessError):
            # check-jsonschema not available or failed - fall back to basic validation
            # Already validated YAML syntax and required fields above
            return True

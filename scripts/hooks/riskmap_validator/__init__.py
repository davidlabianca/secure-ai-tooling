"""
Risk Map Validator Package

A validation and graph generation system for CoSAI Risk Map framework components.

This package provides tools for:
- Validating component relationship consistency in YAML files
- Generating Mermaid graph visualizations of component and control relationships
- Supporting git pre-commit hooks for automated validation
- Enforcing bidirectional edge consistency across AI system components

Modules:
    config: Configuration constants and default file paths
    models: Data models for ComponentNode and ControlNode objects
    utils: Utility functions for file parsing and git integration
    validator: Core validation logic for component edge consistency
    graphing: Graph generation classes for Mermaid visualization

Usage:
    from riskmap_validator.validator import ComponentEdgeValidator
    from riskmap_validator.graphing import ComponentGraph, ControlGraph
    from riskmap_validator.models import ComponentNode, ControlNode

Dependencies:
    - PyYAML: YAML file parsing
    - Python 3.9+: Type hints and pathlib support
"""

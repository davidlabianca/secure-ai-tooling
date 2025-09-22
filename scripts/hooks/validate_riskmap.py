#!/usr/bin/env python3
"""
Git Pre-Commit Hook: Component Edge Consistency Validator and Graph Generator

This script validates the integrity of component relationships in YAML configuration files,
ensuring that edge definitions are bidirectionally consistent and identifying orphaned components.
Additionally, it can generate Mermaid graph visualizations of the component relationships.

VALIDATION RULES:
    1. Bidirectional Consistency: Each component's 'to' edges must have corresponding
       'from' edges in the target components
    2. Reverse Consistency: Each component's 'from' edges must have corresponding
       'to' edges in the source components
    3. No Isolation: Components should not exist without any connections (configurable)

GRAPH GENERATION:
    - Generates Mermaid-compatible graph visualizations
    - Automatically calculates topological ranks using zero-based indexing (componentDataSources is always rank 0)
    - Organizes components into category-based subgraphs (Data, Infrastructure, Model, Application)
    - Uses dynamic tilde spacing based on rank hierarchy
    - Supports debug mode for rank annotations

USAGE:
    As a git pre-commit hook:
        python validate_riskmap.py

    For manual validation:
        python validate_riskmap.py --force

    For custom file paths:
        python validate_riskmap.py --file path/to/components.yaml

    Generate component graph visualization:
        python validate_riskmap.py --to-graph output.md

    Generate control-to-component graph visualization:
        python validate_riskmap.py --to-controls-graph controls.md

    Generate risk-to-control-to-component graph visualization:
        python validate_riskmap.py --to-risk-graph risk.md

    Generate graph with debug annotations:
        python validate_riskmap.py --to-graph output.md --debug

    Generate graph with additional .mermaid format:
        python validate_riskmap.py --to-graph output.md --mermaid-format

    Allow isolated components:
        python validate_riskmap.py --allow-isolated

    Quiet mode (errors only):
        python validate_riskmap.py --quiet

COMMAND LINE OPTIONS:
    --force               Force validation even if files not staged for commit
    --file PATH           Path to YAML file to validate (default: risk-map/yaml/components.yaml)
    --allow-isolated      Allow components with no edges (isolated components)
    --quiet, -q           Minimize output (only show errors)
    --to-graph PATH       Output component graph visualization to specified file
    --to-controls-graph PATH  Output control-to-component graph visualization to specified file
    --to-risk-graph PATH  Output risk-to-control-to-component graph visualization to specified file
    --debug               Include rank comments in graph output
    --mermaid-format      Save graphs in '.mermaid' format in addition to markdown code block

EXIT CODES:
    0 - All validations passed
    1 - Validation failures found
    2 - Configuration or runtime error

YAML STRUCTURE EXPECTED:
    components:
      - id: component-a
        title: Component A
        category: infrastructure
        edges:
          to:
            - component-b
            - component-c
          from: component-d
      - id: component-b
        title: Component B
        category: application
        edges:
          to: []
          from:
          - component-a

GRAPH OUTPUT FORMAT:
    The generated graph uses Mermaid syntax with:
    - Topological ranking using zero-based indexing (componentDataSources = rank 0)
    - Category-based subgraphs with color coding
    - Dynamic tilde spacing: anchor = 3 + min_node_rank, end = 3 + (global_max_rank - max_node_rank)
    - Optional debug comments showing node ranks
    - Automatic cross-subgraph linkage via anchor nodes

EXAMPLES:
    # Basic validation
    python validate_riskmap.py --force

    # Generate clean graph
    python validate_riskmap.py --force --to-graph component_map.md

    # Generate graph with rank debugging
    python validate_riskmap.py --force --to-graph debug_graph.md --debug

    # Validate custom file with isolated components allowed
    python validate_riskmap.py --file custom/components.yaml --allow-isolated


"""

import argparse
import sys
from pathlib import Path

# Configuration Constants
from riskmap_validator.config import DEFAULT_COMPONENTS_FILE
from riskmap_validator.graphing import ComponentGraph, ControlGraph, RiskGraph
from riskmap_validator.utils import get_staged_yaml_files, parse_controls_yaml, parse_risks_yaml
from riskmap_validator.validator import ComponentEdgeValidator


def parse_args() -> argparse.Namespace:
    """
    Parse and validate command line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description="Validate component edge consistency in YAML files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                                    # Check staged components.yaml
  %(prog)s --force                            # Force check default file
  %(prog)s --file custom/components.yaml      # Check specific file
  %(prog)s --allow-isolated                   # Allow components with no edges
  %(prog)s --to-graph graph.md                # Output component graph as .md code block
  %(prog)s --to-controls-graph controls.md    # Output control-to-component graph
  %(prog)s --to-risk-graph risk.md            # Output risk-to-control-to-component graph
  %(prog)s --to-graph graph.md --mermaid-format  # Output both .md and .mermaid formats
  %(prog)s --quiet                            # Minimal output
  %(prog)s --help                             # Show this help

Exit Codes:
  0 - All validations passed
  1 - Validation failures found
  2 - Configuration or runtime error
        """,
    )

    parser.add_argument(
        "--force",
        "-f",
        action="store_true",
        help="Force validation even if files not staged for commit",
    )

    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_COMPONENTS_FILE,
        help=f"Path to YAML file to validate (default: {DEFAULT_COMPONENTS_FILE})",
    )

    parser.add_argument(
        "--allow-isolated",
        action="store_true",
        help="Allow components with no edges (isolated components)",
    )

    parser.add_argument("--quiet", "-q", action="store_true", help="Minimize output (only show errors)")

    parser.add_argument(
        "--to-graph",
        type=Path,
        help="Output component graph visualization to specified txt file",
    )

    parser.add_argument(
        "--to-controls-graph",
        type=Path,
        help="Output control-to-component graph visualization to specified file",
    )

    parser.add_argument(
        "--to-risk-graph",
        type=Path,
        help="Output risk-to-control-to-component graph visualization to specified file",
    )

    parser.add_argument("--debug", action="store_true", help="Include rank comments in graph output")

    parser.add_argument(
        "--mermaid-format",
        action="store_true",
        help="Save graphs in '.mermaid' format in addition to markdown code block",
    )

    return parser.parse_args()


def main() -> None:
    """
    Main entry point for the component edge validator.

    Designed to be used as a git pre-commit hook or standalone validation tool.
    Exit codes follow standard conventions for shell integration.
    """
    try:
        args = parse_args()

        # Initialize validator
        validator = ComponentEdgeValidator(allow_isolated=args.allow_isolated, verbose=not args.quiet)

        if not args.quiet:
            if args.force:
                print("🔍 Force checking components...")
            else:
                print("🔍 Checking for staged YAML files...")

        # Get files to validate
        yaml_files = get_staged_yaml_files(args.file, args.force)

        if not yaml_files:
            if not args.quiet:
                print("   No YAML files to validate - skipping")
            sys.exit(0)

        if not args.quiet:
            file_count = len(yaml_files)
            file_word = "file" if file_count == 1 else "files"
            print(f"   Found {file_count} YAML {file_word} to validate")

        # Validate all files
        all_valid = True
        for yaml_file in yaml_files:
            if not validator.validate_file(yaml_file):
                all_valid = False
            if not args.quiet and len(yaml_files) > 1:
                print()  # Add spacing between files

        # Report final results
        if not all_valid:
            print("❌ Component edge validation failed!")
            print("   Fix the above errors before committing.")
            sys.exit(1)

        if not args.quiet:
            print("✅ All YAML files passed component edge validation")

        if args.to_graph:
            graph = ComponentGraph(validator.forward_map, validator.components, debug=args.debug)
            try:
                graph_output = graph.to_mermaid()
                # Write graph_output to file
                with open(args.to_graph, "w", encoding="utf-8") as f:
                    f.write(graph_output)

                print(f"   Graph visualization saved to {args.to_graph}")

                # Save .mermaid format if requested
                if args.mermaid_format:
                    mermaid_file = args.to_graph.with_suffix('.mermaid')
                    mermaid_output = graph.to_mermaid(output_format='mermaid')
                    with open(mermaid_file, "w", encoding="utf-8") as f:
                        f.write(mermaid_output)
                    print(f"   Mermaid format saved to {mermaid_file}")
            except Exception as e:
                print(f"⚠️  Failed to generate graph: {e}")

        if args.to_controls_graph:
            try:
                # Parse controls and generate controls graph
                controls = parse_controls_yaml()
                control_graph = ControlGraph(controls, validator.components, debug=args.debug)

                controls_graph_output = control_graph.to_mermaid()

                # Write controls graph to file
                with open(args.to_controls_graph, "w", encoding="utf-8") as f:
                    f.write(controls_graph_output)

                print(f"   Controls graph visualization saved to {args.to_controls_graph}")

                # Save .mermaid format if requested
                if args.mermaid_format:
                    mermaid_file = args.to_controls_graph.with_suffix('.mermaid')
                    mermaid_output = control_graph.to_mermaid(output_format='mermaid')
                    with open(mermaid_file, "w", encoding="utf-8") as f:
                        f.write(mermaid_output)
                    print(f"   Mermaid format saved to {mermaid_file}")
            except Exception as e:
                print(f"⚠️  Failed to generate controls graph: {e}")

        if args.to_risk_graph:
            try:
                # Parse risks and controls, then generate risk graph
                risks = parse_risks_yaml()
                controls = parse_controls_yaml()
                risk_graph = RiskGraph(risks, controls, validator.components, debug=args.debug)

                risk_graph_output = risk_graph.to_mermaid()

                # Write risk graph to file
                with open(args.to_risk_graph, "w", encoding="utf-8") as f:
                    f.write(risk_graph_output)

                print(f"   Risk graph visualization saved to {args.to_risk_graph}")

                # Save .mermaid format if requested
                if args.mermaid_format:
                    mermaid_file = args.to_risk_graph.with_suffix('.mermaid')
                    mermaid_output = risk_graph.to_mermaid(output_format='mermaid')
                    with open(mermaid_file, "w", encoding="utf-8") as f:
                        f.write(mermaid_output)
                    print(f"   Mermaid format saved to {mermaid_file}")
            except Exception as e:
                print(f"⚠️  Failed to generate risk graph: {e}")

        sys.exit(0)

    except KeyboardInterrupt:
        print("\n⚠️  Validation interrupted by user")
        sys.exit(2)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print("   Please report this issue to the maintainers")
        sys.exit(2)


if __name__ == "__main__":
    main()

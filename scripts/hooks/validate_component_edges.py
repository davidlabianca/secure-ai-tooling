#!/usr/bin/env python3
"""
Git pre-commit hook to validate component edge consistency.

This script validates that:
1. Each component's 'to' edges match the 'from' edges in the corresponding components
2. Each component's 'from' edges match the 'to' edges in the corresponding components  
3. There are no components with no edges (isolated components)

Only runs when YAML files are modified in the commit.
"""

import sys
import yaml
import subprocess
from pathlib import Path
from typing import Dict, List, Set


def get_staged_yaml_files() -> List[Path]:
    """Get list of staged YAML files from git."""
    try:
        # Get all staged files
        result = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True,
            text=True,
            check=True
        )
        
        staged_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        # Filter to only YAML files that exist
        yaml_files = []
        for file_path in staged_files:
            path = Path(file_path)
            if path.suffix.lower() in ['.yaml', '.yml'] and path.exists():
                yaml_files.append(path)
        
        return yaml_files
        
    except subprocess.CalledProcessError as e:
        print(f"Error getting staged files: {e}")
        return []


def load_yaml_file(file_path: Path) -> Dict:
    """Load and parse YAML file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file {file_path}: {e}")
        return None
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None


def extract_component_edges(yaml_data: Dict) -> Dict[str, Dict[str, List[str]]]:
    """Extract component IDs and their edges from YAML data."""
    components = {}
    
    if not yaml_data or 'components' not in yaml_data:
        return components
    
    for component in yaml_data['components']:
        component_id = component.get('id')
        if not component_id:
            continue
            
        edges = component.get('edges', {})
        components[component_id] = {
            'to': edges.get('to', []),
            'from': edges.get('from', [])
        }
    
    return components


def build_edge_maps(components: Dict[str, Dict[str, List[str]]]) -> tuple:
    """Build forward and reverse edge mappings."""
    forward_map = {}  # component -> list of components it points to
    reverse_map = {}  # component -> list of components that point to it
    
    for component_id, edges in components.items():
        # Forward edges (this component -> other components)
        if edges['to']:
            forward_map[component_id] = edges['to']
        
        # Build reverse mapping from 'from' edges
        for from_node in edges['from']:
            if from_node not in reverse_map:
                reverse_map[from_node] = []
            reverse_map[from_node].append(component_id)
    
    return forward_map, reverse_map


def find_isolated_components(components: Dict[str, Dict[str, List[str]]]) -> Set[str]:
    """Find components with no edges (neither to nor from)."""
    isolated = set()
    
    for component_id, edges in components.items():
        if not edges['to'] and not edges['from']:
            isolated.add(component_id)
    
    return isolated


def compare_edge_maps(map1: Dict[str, List[str]], map2: Dict[str, List[str]]) -> List[str]:
    """Compare two edge maps and return list of inconsistencies."""
    errors = []
    
    # Check if all keys in map1 exist in map2 with matching values
    for key, values in map1.items():
        if key not in map2:
            errors.append(f"Component '{key}' has outgoing edges but no corresponding incoming edges")
        elif sorted(values) != sorted(map2[key]):
            missing_in_map2 = set(values) - set(map2[key])
            extra_in_map2 = set(map2[key]) - set(values)
            
            if missing_in_map2:
                errors.append(f"Component '{key}': missing incoming edges for: {', '.join(missing_in_map2)}")
            if extra_in_map2:
                errors.append(f"Component '{key}': extra incoming edges for: {', '.join(extra_in_map2)}")
    
    # Check if all keys in map2 exist in map1
    for key in map2.keys():
        if key not in map1:
            errors.append(f"Component '{key}' has incoming edges but no corresponding outgoing edges")
    
    return errors


def validate_component_edges(file_path: Path) -> bool:
    """Validate component edge consistency in YAML file."""
    print(f"Validating component edges in: {file_path}")
    
    # Load and parse YAML
    yaml_data = load_yaml_file(file_path)
    
    if not yaml_data:
        print(f"  ⚠️  Skipping {file_path} - could not load YAML data")
        return True  # Don't fail commit for parsing issues
    
    # Extract component edges
    components = extract_component_edges(yaml_data)
    
    if not components:
        print(f"  ℹ️  No components found in {file_path} - skipping validation")
        return True
    
    # Build edge mappings
    forward_map, reverse_map = build_edge_maps(components)
    
    # Find isolated components
    isolated = find_isolated_components(components)
    
    # Validate edge consistency
    errors = compare_edge_maps(forward_map, reverse_map)
    
    # Report results
    success = True
    
    if isolated:
        print(f"  ❌ Found {len(isolated)} isolated components (no edges):")
        for component in sorted(isolated):
            print(f"     - {component}")
        success = False
    
    if errors:
        print(f"  ❌ Found {len(errors)} edge consistency errors:")
        for error in errors:
            print(f"     - {error}")
        success = False
    
    if success:
        print(f"  ✅ Component edges are consistent")
    
    return success


def main():
    """Main function for git pre-commit hook."""
    print("🔍 Checking for YAML file changes...")
    
    # Get staged YAML files
    yaml_files = get_staged_yaml_files()
    
    if not yaml_files:
        print("   No YAML files modified - skipping component edge validation")
        sys.exit(0)
    
    print(f"   Found {len(yaml_files)} staged YAML file(s)")
    
    # Validate each YAML file
    all_valid = True
    for yaml_file in yaml_files:
        if not validate_component_edges(yaml_file):
            all_valid = False
        print()  # Add spacing between files
    
    if not all_valid:
        print("❌ Component edge validation failed!")
        print("   Fix the above errors before committing.")
        sys.exit(1)
    
    print("✅ All YAML files passed component edge validation")
    sys.exit(0)


if __name__ == "__main__":
    main()
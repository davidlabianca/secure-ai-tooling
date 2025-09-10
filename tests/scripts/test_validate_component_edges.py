#!/usr/bin/env python3
"""
Tests for Component Edge Consistency Validator

This test suite exercises the primary validation features:
1. Isolated components (components with no edges)
2. Missing 'from' edges for existing 'to' edges
3. Missing 'to' edges for existing 'from' edges
4. Missing component references
5. File loading and YAML parsing
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the validator using git repo root
import sys
import subprocess

def get_git_root():
    """Get the git repository root directory."""
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            check=True
        )
        return Path(result.stdout.strip())
    except subprocess.CalledProcessError:
        # Fallback to relative path if not in git repo
        return Path(__file__).parent.parent.parent

# Add tools directory to path
git_root = get_git_root()
sys.path.insert(0, str(git_root / "tools"))

from create_component_map import ComponentEdgeValidator, EdgeValidationError, get_staged_yaml_files, ComponentNode, ComponentGraph

class TestComponentEdgeValidator:
    """Test the main ComponentEdgeValidator class functionality."""
    
    @pytest.fixture
    def validator(self):
        """Create a validator instance for testing."""
        return ComponentEdgeValidator(allow_isolated=False, verbose=False)
    
    @pytest.fixture
    def validator_allow_isolated(self):
        """Create a validator that allows isolated components."""
        return ComponentEdgeValidator(allow_isolated=True, verbose=False)
    
    @pytest.fixture
    def grapher(self, title: str, to_edge: list[str], from_edge: list[str]):
        return ComponentNode(title, to_edge, from_edge)
    
    @pytest.fixture
    def temp_yaml_file(self):
        """Create a temporary YAML file for testing."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yield Path(temp_file.name)
        # Cleanup
        Path(temp_file.name).unlink(missing_ok=True)
    
    def create_yaml_file(self, file_path: Path, data: dict):
        """Helper to create YAML file with given data."""
        with open(file_path, 'w') as f:
            yaml.dump(data, f)
    
    def test_load_valid_yaml_file(self, validator, temp_yaml_file):
        """Test loading a valid YAML file."""
        test_data = {
            'components': [
                {'id': 'comp-a', 'edges': {'to': ['comp-b'], 'from': []}}
            ]
        }
        self.create_yaml_file(temp_yaml_file, test_data)
        
        result = validator.load_yaml_file(temp_yaml_file)
        assert result == test_data
    
    def test_load_nonexistent_file(self, validator):
        """Test loading a file that doesn't exist."""
        with pytest.raises(EdgeValidationError, match="File not found"):
            validator.load_yaml_file(Path("nonexistent.yaml"))
    
    def test_load_empty_yaml_file(self, validator, temp_yaml_file):
        """Test loading an empty YAML file."""
        temp_yaml_file.write_text("")
        
        result = validator.load_yaml_file(temp_yaml_file)
        assert result == {}
    
    def test_load_invalid_yaml_file(self, validator, temp_yaml_file):
        """Test loading an invalid YAML file."""
        temp_yaml_file.write_text("invalid: yaml: content: [")
        
        with pytest.raises(EdgeValidationError, match="YAML parsing error"):
            validator.load_yaml_file(temp_yaml_file)
    
    def test_extract_component_edges_valid(self, validator):
        """Test extracting edges from valid component data."""
        yaml_data = {
            'components': [
                {'id': 'comp-a', 'title': "Test1", 'category': 'infrastructure', 'edges': {'to': ['comp-b'], 'from': ['comp-c']}},
                {'id': 'comp-b', 'title': "Test2", 'category': 'infrastructure', 'edges': {'to': [], 'from': ['comp-a']}},
                {'id': 'comp-c', 'title': "Test3", 'category': 'infrastructure', 'edges': {'to': ['comp-a'], 'from': []}}
            ]
        }
        
        result = validator.extract_component_edges(yaml_data)
        
        expected: dict[str, ComponentNode] = {
            'comp-a': ComponentNode(title='Test1', category='infrastructure', to_edges= ['comp-b'], from_edges= ['comp-c']),
            'comp-b': ComponentNode(title='Test2', category='infrastructure', to_edges= [], from_edges= ['comp-a']),
            'comp-c': ComponentNode(title='Test3', category='infrastructure', to_edges= ['comp-a'], from_edges= []),
        }
        assert result == expected
    
    def test_extract_component_edges_missing_id(self, validator):
        """Test extracting edges when components are missing IDs."""
        yaml_data = {
            'components': [
                {'title': 'TestFail', 'category': 'test', 'edges': {'to': ['comp-b'], 'from': []}},  # Missing ID
                {'id': 'comp-b', 'title': 'Test1', 'category': 'test', 'edges': {'to': [], 'from': []}}
            ]
        }
        
        result = validator.extract_component_edges(yaml_data)
        
        # Should only include the component with valid ID
        expected: dict[str, ComponentNode] = {
            'comp-b': ComponentNode(title='Test1', category='test', to_edges= [], from_edges= [])
        }
        assert result == expected
    
    def test_extract_component_edges_missing_edges(self, validator):
        """Test extracting edges when components are missing edge definitions."""
        yaml_data = {
            'components': [
                {'id': 'comp-a', 'title': 'Test1', 'category': 'test'},  # Missing edges
                {'id': 'comp-b', 'title': 'Test2', 'category': 'test', 'edges': {'to': ['comp-a']}}  # Missing from
            ]
        }
        
        result = validator.extract_component_edges(yaml_data)

        expected: dict[str, ComponentNode] = {
            'comp-a': ComponentNode(title='Test1', category='test', to_edges= [], from_edges= []),
            'comp-b': ComponentNode(title='Test2', category='test', to_edges= ['comp-a'], from_edges= []),
        } 

        assert result == expected
    
    def test_find_isolated_components(self, validator):
        """Test finding components with no edges."""

        components: dict[str, ComponentNode] = {
            'comp-a': ComponentNode(title='Test1', category='test1', to_edges= ['comp-b'], from_edges= []),
            'comp-b': ComponentNode(title='Test2', category='test1', to_edges= [], from_edges= ['comp-a']),
            'comp-isolated': ComponentNode(title='Test3',  category='test1', to_edges= [], from_edges= []),
            'comp-isolated2': ComponentNode(title='Test4', category='test1',  to_edges= [], from_edges= []),
        }

        isolated = validator.find_isolated_components(components)
        assert isolated == {'comp-isolated', 'comp-isolated2'}
    
    def test_find_missing_components(self, validator):
        """Test finding components referenced but not defined."""
        components: dict[str, ComponentNode] = {
            'comp-a': ComponentNode(title='Test1', category='test1', to_edges= ['comp-missing1', 'comp-b'], from_edges= ['comp-missing2']),
            'comp-b': ComponentNode(title='Test2', category='test1', to_edges= [], from_edges= ['comp-a']),
        }
        
        missing = validator.find_missing_components(components)
        assert missing == {'comp-missing1', 'comp-missing2'}
    
    def test_build_edge_maps(self, validator):
        """Test building forward and reverse edge maps."""
        components: dict[str, ComponentNode] = {
            'comp-a': ComponentNode(title='Test1', category='test1', to_edges= ['comp-b','comp-c'], from_edges= []),
            'comp-b': ComponentNode(title='Test2', category='test1', to_edges= [], from_edges= ['comp-a']),
            'comp-c': ComponentNode(title='Test3', category='test1', to_edges= [], from_edges= ['comp-a']),
        }
        
        forward_map, reverse_map = validator.build_edge_maps(components)
        
        assert forward_map == {'comp-a': ['comp-b', 'comp-c']}
        assert reverse_map == {'comp-a': ['comp-b', 'comp-c']}  # No incoming edges to comp-a but has outgoing edges
    
    def test_validate_edge_consistency_valid(self, validator):
        """Test edge consistency validation with valid edges."""
        # Perfect bidirectional consistency
        forward_map = {'comp-b': ['comp-a']}
        reverse_map = {'comp-b': ['comp-a']}
        
        errors = validator.validate_edge_consistency(forward_map, reverse_map)
        assert errors == []
    
    def test_validate_edge_consistency_missing_reverse(self, validator):
        """Test validation when 'to' edge has no corresponding 'from'."""
        # comp-a points to comp-b, but comp-b doesn't point back
        forward_map = {'comp-a': ['comp-b']}
        reverse_map = {}  # No reverse edges
        
        errors = validator.validate_edge_consistency(forward_map, reverse_map)
        assert len(errors) == 1
        assert "'comp-a' has outgoing edges but no corresponding incoming edges" in errors[0]
    
    def test_validate_edge_consistency_missing_forward(self, validator):
        """Test validation when 'from' edge has no corresponding 'to'."""
        # comp-b has incoming from comp-a, but comp-a doesn't have outgoing to comp-b
        forward_map = {}  # No forward edges
        reverse_map = {'comp-b': ['comp-a']}
        
        errors = validator.validate_edge_consistency(forward_map, reverse_map)
        assert len(errors) == 1
        assert "has incoming edges but no corresponding outgoing edges" in errors[0]


class TestValidationScenarios:
    """Test complete validation scenarios with real YAML data."""
    
    @pytest.fixture
    def temp_yaml_file(self):
        """Create a temporary YAML file for testing."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yield Path(temp_file.name)
        Path(temp_file.name).unlink(missing_ok=True)
    
    def create_yaml_file(self, file_path: Path, data: dict):
        """Helper to create YAML file with given data."""
        with open(file_path, 'w') as f:
            yaml.dump(data, f)
    
    def test_valid_component_graph(self, temp_yaml_file):
        """Test a completely valid component graph."""
        valid_data = {
            'components': [
                {'id': 'frontend', 'edges': {'to': ['backend'], 'from': []}},
                {'id': 'backend', 'edges': {'to': ['database'], 'from': ['frontend']}},
                {'id': 'database', 'edges': {'to': [], 'from': ['backend']}}
            ]
        }
        self.create_yaml_file(temp_yaml_file, valid_data)
        
        validator = ComponentEdgeValidator(verbose=False)
        result = validator.validate_file(temp_yaml_file)
        assert result is True
    
    def test_isolated_components_rejected(self, temp_yaml_file):
        """Test that isolated components are rejected by default."""
        data_with_isolated = {
            'components': [
                {'id': 'connected-a', 'title': 'Test1', 'category': 'test1', 'edges': {'to': ['connected-b'], 'from': []}},
                {'id': 'connected-b', 'title': 'Test2', 'category': 'test1', 'edges': {'to': [], 'from': ['connected-a']}},
                {'id': 'isolated', 'title': 'Isolated', 'category': 'test1', 'edges': {'to': [], 'from': []}}
            ]
        }
        self.create_yaml_file(temp_yaml_file, data_with_isolated)
        
        validator = ComponentEdgeValidator(allow_isolated=False, verbose=False)
        result = validator.validate_file(temp_yaml_file)
        assert result is False
    
    def test_isolated_components_allowed(self, temp_yaml_file):
        """Test that isolated components are allowed when configured."""
        data_with_isolated = {
            'components': [
                {'id': 'connected-a', 'title': 'Test1', 'edges': {'to': ['connected-b'], 'from': []}},
                {'id': 'connected-b', 'title': 'Test2', 'edges': {'to': [], 'from': ['connected-a']}},
                {'id': 'isolated',    'title': 'Isolated', 'edges': {'to': [], 'from': []}}
            ]
        }
        self.create_yaml_file(temp_yaml_file, data_with_isolated)
        
        validator = ComponentEdgeValidator(allow_isolated=True, verbose=False)
        result = validator.validate_file(temp_yaml_file)
        assert result is True
    
    def test_missing_from_edge(self, temp_yaml_file):
        """Test validation failure when 'to' edge has no corresponding 'from'."""
        data_missing_from = {
            'components': [
                {'id': 'comp-a', 'title': 'Test1', 'category': 'test1', 'edges': {'to': ['comp-b'], 'from': []}},
                {'id': 'comp-b', 'title': 'Test2', 'category': 'test1', 'edges': {'to': [], 'from': []}}  # Missing 'from': ['comp-a']
            ]
        }
        self.create_yaml_file(temp_yaml_file, data_missing_from)
        
        validator = ComponentEdgeValidator(verbose=False)
        result = validator.validate_file(temp_yaml_file)
        assert result is False
    
    def test_missing_to_edge(self, temp_yaml_file):
        """Test validation failure when 'from' edge has no corresponding 'to'."""
        data_missing_to = {
            'components': [
                {'id': 'comp-a', 'title': "Test1", 'category': 'test1', 'edges': {'to': [], 'from': []}},  # Missing 'to': ['comp-b']
                {'id': 'comp-b', 'title': "Test2", 'category': 'test1', 'edges': {'to': [], 'from': ['comp-a']}}
            ]
        }
        self.create_yaml_file(temp_yaml_file, data_missing_to)
        
        validator = ComponentEdgeValidator(verbose=False)
        result = validator.validate_file(temp_yaml_file)
        assert result is False
    
    def test_missing_component_reference(self, temp_yaml_file):
        """Test validation failure when referencing non-existent components."""
        data_missing_component = {
            'components': [
                {'id': 'comp-a', 'title': 'Test1', 'category': 'test1', 'edges': {'to': ['non-existent'], 'from': []}},
                {'id': 'comp-b', 'title': 'Test2', 'category': 'test1', 'edges': {'to': [], 'from': ['also-missing']}}
            ]
        }
        self.create_yaml_file(temp_yaml_file, data_missing_component)
        
        validator = ComponentEdgeValidator(verbose=False)
        result = validator.validate_file(temp_yaml_file)
        assert result is False
    
    def test_complex_invalid_graph(self, temp_yaml_file):
        """Test a complex graph with multiple types of validation errors."""
        complex_invalid_data = {
            'components': [
                {'id': 'frontend', 'title': 'Test1', 'category': 'test1', 'edges': {'to': ['backend', 'missing-service'], 'from': []}},
                {'id': 'backend',  'title': 'Test2', 'category': 'test1', 'edges': {'to': [], 'from': []}},  # Missing from: ['frontend']
                {'id': 'database', 'title': 'Test3', 'category': 'test1', 'edges': {'to': [], 'from': ['backend']}},  # backend doesn't point to database
                {'id': 'isolated', 'title': 'Test4', 'category': 'test1', 'edges': {'to': [], 'from': []}}  # Isolated component
            ]
        }
        self.create_yaml_file(temp_yaml_file, complex_invalid_data)
        
        validator = ComponentEdgeValidator(allow_isolated=False, verbose=False)
        result = validator.validate_file(temp_yaml_file)
        assert result is False
    
    def test_empty_components_section(self, temp_yaml_file):
        """Test handling of empty components section."""
        empty_data = {'components': []}
        self.create_yaml_file(temp_yaml_file, empty_data)
        
        validator = ComponentEdgeValidator(verbose=False)
        result = validator.validate_file(temp_yaml_file)
        assert result is True  # Empty is valid
    
    def test_no_components_section(self, temp_yaml_file):
        """Test handling of YAML without components section."""
        no_components_data = {'other_section': {'some': 'data'}}
        self.create_yaml_file(temp_yaml_file, no_components_data)
        
        validator = ComponentEdgeValidator(verbose=False)
        result = validator.validate_file(temp_yaml_file)
        assert result is True  # No components section is valid


class TestGitIntegration:
    """Test git integration functionality."""
    
    @patch('subprocess.run')
    def test_get_staged_yaml_files_with_staged_file(self, mock_run):
        """Test getting staged files when target file is staged."""
        # Mock git command to return our target file
        mock_result = MagicMock()
        mock_result.stdout = "risk-map/yaml/components.yaml\nother-file.txt"
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        # Mock file existence
        target_file = Path("risk-map/yaml/components.yaml")
        with patch.object(Path, 'exists', return_value=True):
            result = get_staged_yaml_files(target_file, force_check=False)
        
        assert result == [target_file]
        mock_run.assert_called_once_with(
            ['git', 'diff', '--cached', '--name-only'],
            capture_output=True,
            text=True,
            check=True
        )
    
    @patch('subprocess.run')
    def test_get_staged_yaml_files_no_staged_files(self, mock_run):
        """Test getting staged files when no files are staged."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        mock_run.return_value = mock_result
        
        result = get_staged_yaml_files(force_check=False)
        assert result == []
    
    def test_get_staged_yaml_files_force_mode(self):
        """Test force mode returns file regardless of git status."""
        target_file = Path("test.yaml")
        
        with patch.object(Path, 'exists', return_value=True):
            result = get_staged_yaml_files(target_file, force_check=True)
        
        assert result == [target_file]
    
    def test_get_staged_yaml_files_force_mode_missing_file(self):
        """Test force mode with non-existent file."""
        target_file = Path("missing.yaml")
        
        with patch.object(Path, 'exists', return_value=False):
            result = get_staged_yaml_files(target_file, force_check=True)
        
        assert result == []
    
    @patch('subprocess.run')
    def test_get_staged_yaml_files_git_error(self, mock_run):
        """Test handling git command errors."""
        mock_run.side_effect = subprocess.CalledProcessError(1, 'git')
        
        result = get_staged_yaml_files(force_check=False)
        assert result == []


class TestEdgeValidationError:
    """Test custom exception handling."""
    
    def test_edge_validation_error_creation(self):
        """Test creating EdgeValidationError."""
        error = EdgeValidationError("Test error message")
        assert str(error) == "Test error message"
    
    def test_edge_validation_error_inheritance(self):
        """Test that EdgeValidationError inherits from Exception."""
        error = EdgeValidationError("Test")
        assert isinstance(error, Exception)


# Integration test to verify the script works end-to-end
class TestEndToEndIntegration:
    """Test complete validation workflows."""
    
    @pytest.fixture
    def temp_yaml_file(self):
        """Create a temporary YAML file for testing."""
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yield Path(temp_file.name)
        Path(temp_file.name).unlink(missing_ok=True)
    
    def test_complete_validation_workflow_success(self, temp_yaml_file):
        """Test complete validation workflow that should succeed."""
        perfect_data = {
            'components': [
                {
                    'id': 'web-server',
                    'edges': {
                        'to': ['app-server', 'load-balancer'],
                        'from': ['load-balancer']
                    }
                },
                {
                    'id': 'app-server',
                    'edges': {
                        'to': ['database'],
                        'from': ['web-server']
                    }
                },
                {
                    'id': 'database',
                    'edges': {
                        'to': [],
                        'from': ['app-server']
                    }
                },
                {
                    'id': 'load-balancer',
                    'edges': {
                        'to': ['web-server'],
                        'from': ['web-server']
                    }
                }
            ]
        }
        
        with open(temp_yaml_file, 'w') as f:
            yaml.dump(perfect_data, f)
        
        validator = ComponentEdgeValidator(allow_isolated=False, verbose=False)
        result = validator.validate_file(temp_yaml_file)
        assert result is True
    
    def test_complete_validation_workflow_failure(self, temp_yaml_file):
        """Test complete validation workflow that should fail."""
        broken_data = {
            'components': [
                {
                    'id': 'frontend',
                    'title': 'test1',
                    'categrory': 'test',
                    'edges': {
                        'to': ['backend'],  # backend exists
                        'from': []
                    }
                },
                {
                    'id': 'backend',
                    'title': 'test2',
                    'category': 'test',
                    'edges': {
                        'to': ['missing-db'],  # missing-db doesn't exist
                        'from': []  # Should be ['frontend'] for consistency
                    }
                },
                {
                    'id': 'orphaned',
                    'title': 'test3',
                    'category': 'test',
                    'edges': {
                        'to': [],
                        'from': []  # Isolated component
                    }
                }
            ]
        }
        
        with open(temp_yaml_file, 'w') as f:
            yaml.dump(broken_data, f)
        
        validator = ComponentEdgeValidator(allow_isolated=False, verbose=False)
        result = validator.validate_file(temp_yaml_file)
        assert result is False


class TestComponentGraph:
    """Test the ComponentGraph class functionality."""
    
    @pytest.fixture
    def simple_components(self):
        """Create simple test components for graph testing."""
        return {
            'comp-a': ComponentNode(title='Node A', category='Data', to_edges=['comp-b'], from_edges=[]),
            'comp-b': ComponentNode(title='Node B', category='Model', to_edges=['comp-c'], from_edges=['comp-a']),
            'comp-c': ComponentNode(title='Node C', category='Application', to_edges=[], from_edges=['comp-b'])
        }
    
    @pytest.fixture
    def simple_forward_map(self):
        """Create simple forward map for testing."""
        return {'comp-a': ['comp-b'], 'comp-b': ['comp-c']}
    
    @pytest.fixture
    def complex_components(self):
        """Create more complex components with cycles."""
        return {
            'data-src': ComponentNode(title='Data Sources', category='Data', to_edges=['model'], from_edges=['app']),
            'model': ComponentNode(title='The Model', category='Model', to_edges=['app'], from_edges=['data-src', 'infra']),
            'app': ComponentNode(title='Application', category='Application', to_edges=['data-src'], from_edges=['model']),
            'infra': ComponentNode(title='Infrastructure', category='Infrastructure', to_edges=['model'], from_edges=[])
        }
    
    @pytest.fixture
    def complex_forward_map(self):
        """Create complex forward map with cycles."""
        return {
            'data-src': ['model'],
            'model': ['app'],
            'app': ['data-src'],
            'infra': ['model']
        }
    
    def test_component_graph_initialization(self, simple_forward_map, simple_components):
        """Test ComponentGraph initialization."""
        graph = ComponentGraph(simple_forward_map, simple_components)
        assert graph.components == simple_components
        assert graph.forward_map == simple_forward_map
        assert graph.debug is False
        assert isinstance(graph.graph, str)
    
    def test_component_graph_initialization_with_debug(self, simple_forward_map, simple_components):
        """Test ComponentGraph initialization with debug flag."""
        graph = ComponentGraph(simple_forward_map, simple_components, debug=True)
        assert graph.debug is True
        assert isinstance(graph.graph, str)
    
    def test_calculate_node_ranks_simple_chain(self, simple_forward_map, simple_components):
        """Test node ranking with simple A->B->C chain.""" 
        # Override componentDataSources check by using that name
        simple_components['componentDataSources'] = simple_components.pop('comp-a')
        simple_forward_map['componentDataSources'] = simple_forward_map.pop('comp-a')
        
        graph = ComponentGraph(simple_forward_map, simple_components)
        ranks = graph._calculate_node_ranks()
        
        # componentDataSources should be rank 1
        assert ranks['componentDataSources'] == 1
        assert ranks['comp-b'] == 2
        assert ranks['comp-c'] == 3
    
    def test_calculate_node_ranks_with_cycles(self, complex_forward_map, complex_components):
        """Test node ranking with cycles in graph."""
        graph = ComponentGraph(complex_forward_map, complex_components)
        ranks = graph._calculate_node_ranks()
        
        # infra should be rank 1 (no incoming edges)
        assert ranks['infra'] == 1
        
        # All nodes should have ranks assigned
        assert len(ranks) == 4
        for node_id, rank in ranks.items():
            assert isinstance(rank, int)
            assert rank >= 1
    
    def test_calculate_node_ranks_data_sources_priority(self):
        """Test that componentDataSources gets rank 1 priority."""
        components = {
            'componentDataSources': ComponentNode(title='Data Sources', category='Data', to_edges=['other'], from_edges=['cycle']),
            'other': ComponentNode(title='Other', category='Model', to_edges=['cycle'], from_edges=['componentDataSources']),
            'cycle': ComponentNode(title='Cycle', category='Application', to_edges=['componentDataSources'], from_edges=['other'])
        }
        forward_map = {
            'componentDataSources': ['other'],
            'other': ['cycle'],
            'cycle': ['componentDataSources']
        }
        
        graph = ComponentGraph(forward_map, components)
        ranks = graph._calculate_node_ranks()
        
        # componentDataSources should always be rank 1
        assert ranks['componentDataSources'] == 1
        assert ranks['other'] == 2
        assert ranks['cycle'] == 3
    
    def test_normalize_category(self, simple_forward_map, simple_components):
        """Test category normalization."""
        graph = ComponentGraph(simple_forward_map, simple_components)
        
        # Test existing components
        assert graph._normalize_category('comp-a') == 'Data'
        assert graph._normalize_category('comp-b') == 'Model'
        assert graph._normalize_category('comp-c') == 'Application'
        
        # Test non-existent component
        assert graph._normalize_category('nonexistent') == 'Unknown'
    
    def test_get_first_component_in_category(self, simple_forward_map, simple_components):
        """Test getting first component in category."""
        graph = ComponentGraph(simple_forward_map, simple_components)
        
        components_by_category = {
            'Data': [('comp-a', 'Node A')],
            'Model': [('comp-b', 'Node B')],
            'Application': [('comp-c', 'Node C')]
        }
        
        assert graph._get_first_component_in_category(components_by_category, 'Data') == 'comp-a'
        assert graph._get_first_component_in_category(components_by_category, 'Model') == 'comp-b'
        assert graph._get_first_component_in_category(components_by_category, 'NonExistent') is None
        assert graph._get_first_component_in_category({}, 'Data') is None
    
    def test_build_graph_structure_without_debug(self, simple_forward_map, simple_components):
        """Test graph structure generation without debug comments."""
        graph = ComponentGraph(simple_forward_map, simple_components, debug=False)
        mermaid_output = graph.to_mermaid()
        
        # Should contain basic mermaid structure
        assert 'graph TD' in mermaid_output
        assert 'classDef hidden display: none;' in mermaid_output
        
        # Should contain component connections
        assert 'comp-a[Node A] --> comp-b[Node B]' in mermaid_output
        assert 'comp-b[Node B] --> comp-c[Node C]' in mermaid_output
        
        # Should contain subgraphs
        assert 'subgraph Data' in mermaid_output
        assert 'subgraph Model' in mermaid_output
        assert 'subgraph Application' in mermaid_output
        
        # Should NOT contain debug comments
        assert '%% comp-a rank' not in mermaid_output
        assert '%% Rank' not in mermaid_output
    
    def test_build_graph_structure_with_debug(self, simple_forward_map, simple_components):
        """Test graph structure generation with debug comments."""
        graph = ComponentGraph(simple_forward_map, simple_components, debug=True)
        mermaid_output = graph.to_mermaid()
        
        # Should contain basic mermaid structure
        assert 'graph TD' in mermaid_output
        
        # Should contain debug comments
        assert '%% comp-a rank' in mermaid_output
        assert '%% comp-a Rank' in mermaid_output
        
        # Should still contain main structure
        assert 'comp-a[Node A] --> comp-b[Node B]' in mermaid_output
    
    def test_build_subgraph_tilde_calculation(self):
        """Test tilde calculation in subgraphs."""
        components = {
            'comp-rank1': ComponentNode(title='Rank 1', category='Data', to_edges=[], from_edges=[]),
            'comp-rank5': ComponentNode(title='Rank 5', category='Model', to_edges=[], from_edges=[])
        }
        forward_map = {}
        
        graph = ComponentGraph(forward_map, components)
        
        # Mock node ranks
        node_ranks = {'comp-rank1': 1, 'comp-rank5': 5}
        components_by_category = {
            'Data': [('comp-rank1', 'Rank 1')]
        }
        
        # Test Data category with rank 1 component (max_rank = 5)
        # Expected tildes: 3 + (5 - 1) = 7
        subgraph_lines = graph._build_subgraph('Data', [('comp-rank1', 'Rank 1')], 'horizontal', components_by_category, node_ranks, debug=False)
        
        # Find the tilde line
        tilde_line = None
        for line in subgraph_lines:
            if 'DataEnd:::hidden' in line:
                tilde_line = line
                break
        
        assert tilde_line is not None
        # Count tildes: should be 7
        tilde_count = tilde_line.count('~')
        assert tilde_count == 7
    
    def test_build_subgraph_minimum_tildes(self):
        """Test minimum tilde count of 3."""
        components = {
            'comp-high-rank': ComponentNode(title='High Rank', category='Data', to_edges=[], from_edges=[])
        }
        forward_map = {}
        
        graph = ComponentGraph(forward_map, components)
        
        # Mock node ranks where component has high rank (close to max)
        node_ranks = {'comp-high-rank': 9}  # max_rank will also be 9
        components_by_category = {
            'Data': [('comp-high-rank', 'High Rank')]
        }
        
        # Test: 3 + (9 - 9) = 3 tildes minimum
        subgraph_lines = graph._build_subgraph('Data', [('comp-high-rank', 'High Rank')], 'horizontal', components_by_category, node_ranks, debug=False)
        
        # Find the tilde line
        tilde_line = None
        for line in subgraph_lines:
            if 'DataEnd:::hidden' in line:
                tilde_line = line
                break
        
        assert tilde_line is not None
        # Should have exactly 3 tildes
        tilde_count = tilde_line.count('~')
        assert tilde_count == 3
    
    def test_mermaid_output_format(self, simple_forward_map, simple_components):
        """Test that mermaid output has correct format."""
        graph = ComponentGraph(simple_forward_map, simple_components)
        mermaid_output = graph.to_mermaid()
        
        # Should start and end with mermaid code block markers
        assert mermaid_output.startswith('```mermaid')
        assert mermaid_output.endswith('```')
        
        # Should have proper line structure
        lines = mermaid_output.split('\n')
        assert len(lines) > 10  # Should have substantial content
        
        # Should contain styling at the end
        assert any('style Infrastructure' in line for line in lines)
        assert any('style Data' in line for line in lines)
        assert any('style Model' in line for line in lines)
        assert any('style Application' in line for line in lines)
    
    def test_to_mermaid_method(self, simple_forward_map, simple_components):
        """Test the to_mermaid method returns the built graph."""
        graph = ComponentGraph(simple_forward_map, simple_components)
        assert graph.to_mermaid() == graph.graph
    
    def test_empty_components(self):
        """Test handling of empty components."""
        graph = ComponentGraph({}, {})
        mermaid_output = graph.to_mermaid()
        
        # Should still have basic structure
        assert 'graph TD' in mermaid_output
        assert '```mermaid' in mermaid_output
        assert '```' in mermaid_output
    
    def test_isolated_components(self):
        """Test handling of isolated components."""
        components = {
            'isolated': ComponentNode(title='Isolated', category='Data', to_edges=[], from_edges=[])
        }
        forward_map = {}
        
        graph = ComponentGraph(forward_map, components)
        ranks = graph._calculate_node_ranks()
        
        # Isolated component should get rank 1
        assert ranks['isolated'] == 1
        
        # Graph should still generate (but isolated components won't appear since they have no connections)
        mermaid_output = graph.to_mermaid()
        assert 'graph TD' in mermaid_output
        assert '```mermaid' in mermaid_output
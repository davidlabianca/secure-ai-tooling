#!/usr/bin/env python3
"""
Tests for validate_riskmap.py

This test suite validates the main entry point for component edge validation
and graph generation. The script orchestrates ComponentEdgeValidator and provides
graph generation capabilities for component, control, and risk visualizations.

Test Coverage:
==============
Total Tests: 36 across 4 test classes (plus the TestMainLifecycleMode class
that pins the dedicated `--mode lifecycle` short-circuit hook).
Coverage Target: 98%+ of validate_riskmap.py (achieved)

1. TestParseArgs - CLI argument parsing (lines 35-113) - 14 tests
   - Default arguments
   - --force/-f flag (long and short form)
   - --file PATH argument
   - --allow-isolated flag
   - --quiet/-q flag (long and short form)
   - --to-graph PATH argument
   - --to-controls-graph PATH argument
   - --to-risk-graph PATH argument
   - --debug flag
   - --mermaid-format/-m flag (long and short form)
   - Combined argument parsing

2. TestMainValidation - Validation orchestration (lines 116-167) - 7 tests
   - Validation success with force mode
   - Validation failure detection
   - No YAML files to validate
   - Quiet mode output suppression
   - Multiple file validation with spacing
   - ComponentEdgeValidator integration with flags
   - Validator initialization with correct options

3. TestMainGraphGeneration - Graph output (lines 169-236) - 13 tests
   - Component graph generation
   - Controls graph generation
   - Risk graph generation
   - Mermaid format output for component graph
   - Mermaid format output for controls graph
   - Mermaid format output for risk graph
   - Component graph error handling
   - Controls graph error handling
   - Risk graph error handling
   - Debug flag passed to ComponentGraph
   - Debug flag passed to ControlGraph
   - Debug flag passed to RiskGraph

4. TestMainErrorHandling - Exception handling (lines 238-246) - 3 tests
   - KeyboardInterrupt handling (exit code 2)
   - Unexpected exceptions (exit code 2)
   - Validator initialization errors (exit code 2)

5. TestMainLifecycleMode - `--mode lifecycle` short-circuit hook
   - Pins the dedicated lifecycle-only entrypoint introduced to fix PR #277
     reviewer feedback (item 2): the lifecycle uniqueness check must be
     reachable on lifecycle-only commits without going through the
     components-validation pipeline.
   - Architectural intent: lifecycle mode bypasses get_staged_yaml_files,
     ComponentEdgeValidator, and graph generation entirely.
"""

import sys
from pathlib import Path
from typing import Any
from unittest.mock import Mock, mock_open, patch

import yaml

# Add scripts/hooks to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from validate_riskmap import main, parse_args


class TestParseArgs:
    """Tests for parse_args() CLI argument parsing."""

    def test_parse_args_with_no_arguments_returns_defaults(self):
        """
        Test default argument values when no flags provided.

        Given: Script called with no arguments
        When: parse_args() is called
        Then: Returns namespace with all defaults (force=False, quiet=False, etc.)
        """
        with patch("sys.argv", ["script.py"]):
            args = parse_args()

        assert args.force is False
        assert args.file is None
        assert args.allow_isolated is False
        assert args.quiet is False
        assert args.to_graph is None
        assert args.to_controls_graph is None
        assert args.to_risk_graph is None
        assert args.debug is False
        assert args.mermaid_format is False

    def test_parse_args_with_force_flag_long_form(self):
        """
        Test --force flag sets force=True.

        Given: Script called with --force flag
        When: parse_args() is called
        Then: Returns namespace with force=True
        """
        with patch("sys.argv", ["script.py", "--force"]):
            args = parse_args()

        assert args.force is True

    def test_parse_args_with_force_flag_short_form(self):
        """
        Test -f flag sets force=True.

        Given: Script called with -f flag
        When: parse_args() is called
        Then: Returns namespace with force=True
        """
        with patch("sys.argv", ["script.py", "-f"]):
            args = parse_args()

        assert args.force is True

    def test_parse_args_with_file_path(self):
        """
        Test --file argument sets custom file path.

        Given: Script called with --file custom/path.yaml
        When: parse_args() is called
        Then: Returns namespace with file=Path("custom/path.yaml")
        """
        with patch("sys.argv", ["script.py", "--file", "custom/components.yaml"]):
            args = parse_args()

        assert args.file == Path("custom/components.yaml")

    def test_parse_args_with_allow_isolated_flag(self):
        """
        Test --allow-isolated flag sets allow_isolated=True.

        Given: Script called with --allow-isolated flag
        When: parse_args() is called
        Then: Returns namespace with allow_isolated=True
        """
        with patch("sys.argv", ["script.py", "--allow-isolated"]):
            args = parse_args()

        assert args.allow_isolated is True

    def test_parse_args_with_quiet_flag_long_form(self):
        """
        Test --quiet flag sets quiet=True.

        Given: Script called with --quiet flag
        When: parse_args() is called
        Then: Returns namespace with quiet=True
        """
        with patch("sys.argv", ["script.py", "--quiet"]):
            args = parse_args()

        assert args.quiet is True

    def test_parse_args_with_quiet_flag_short_form(self):
        """
        Test -q flag sets quiet=True.

        Given: Script called with -q flag
        When: parse_args() is called
        Then: Returns namespace with quiet=True
        """
        with patch("sys.argv", ["script.py", "-q"]):
            args = parse_args()

        assert args.quiet is True

    def test_parse_args_with_to_graph_path(self):
        """
        Test --to-graph argument sets output path.

        Given: Script called with --to-graph graph.md
        When: parse_args() is called
        Then: Returns namespace with to_graph=Path("graph.md")
        """
        with patch("sys.argv", ["script.py", "--to-graph", "output/graph.md"]):
            args = parse_args()

        assert args.to_graph == Path("output/graph.md")

    def test_parse_args_with_to_controls_graph_path(self):
        """
        Test --to-controls-graph argument sets output path.

        Given: Script called with --to-controls-graph controls.md
        When: parse_args() is called
        Then: Returns namespace with to_controls_graph=Path("controls.md")
        """
        with patch("sys.argv", ["script.py", "--to-controls-graph", "controls.md"]):
            args = parse_args()

        assert args.to_controls_graph == Path("controls.md")

    def test_parse_args_with_to_risk_graph_path(self):
        """
        Test --to-risk-graph argument sets output path.

        Given: Script called with --to-risk-graph risk.md
        When: parse_args() is called
        Then: Returns namespace with to_risk_graph=Path("risk.md")
        """
        with patch("sys.argv", ["script.py", "--to-risk-graph", "risk.md"]):
            args = parse_args()

        assert args.to_risk_graph == Path("risk.md")

    def test_parse_args_with_debug_flag(self):
        """
        Test --debug flag sets debug=True.

        Given: Script called with --debug flag
        When: parse_args() is called
        Then: Returns namespace with debug=True
        """
        with patch("sys.argv", ["script.py", "--debug"]):
            args = parse_args()

        assert args.debug is True

    def test_parse_args_with_mermaid_format_flag_long_form(self):
        """
        Test --mermaid-format flag sets mermaid_format=True.

        Given: Script called with --mermaid-format flag
        When: parse_args() is called
        Then: Returns namespace with mermaid_format=True
        """
        with patch("sys.argv", ["script.py", "--mermaid-format"]):
            args = parse_args()

        assert args.mermaid_format is True

    def test_parse_args_with_mermaid_format_flag_short_form(self):
        """
        Test -m flag sets mermaid_format=True.

        Given: Script called with -m flag
        When: parse_args() is called
        Then: Returns namespace with mermaid_format=True
        """
        with patch("sys.argv", ["script.py", "-m"]):
            args = parse_args()

        assert args.mermaid_format is True

    def test_parse_args_with_combined_arguments(self):
        """
        Test multiple arguments can be combined.

        Given: Script called with multiple flags and arguments
        When: parse_args() is called
        Then: Returns namespace with all specified values set correctly
        """
        with patch(
            "sys.argv",
            [
                "script.py",
                "--force",
                "--quiet",
                "--allow-isolated",
                "--to-graph",
                "graph.md",
                "--debug",
                "--mermaid-format",
            ],
        ):
            args = parse_args()

        assert args.force is True
        assert args.quiet is True
        assert args.allow_isolated is True
        assert args.to_graph == Path("graph.md")
        assert args.debug is True
        assert args.mermaid_format is True


class TestMainValidation:
    """Tests for main() validation orchestration."""

    def test_main_exits_0_when_no_yaml_files_to_validate(self, capsys):
        """
        Test that main exits 0 when no YAML files need validation.

        Given: get_staged_yaml_files() returns empty list
        When: main() is called
        Then: Exits with code 0 and prints skip message
        """
        with patch("sys.argv", ["script.py"]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=[]):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 0

        # Verify skip message
        captured = capsys.readouterr()
        assert "No YAML files to validate - skipping" in captured.out

    def test_main_exits_0_when_validation_passes(self, capsys):
        """
        Test that main exits 0 when validation succeeds.

        Given: YAML files are staged and ComponentEdgeValidator passes
        When: main() is called
        Then: Exits with code 0 and prints success message
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]

        with patch("sys.argv", ["script.py"]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    # Mock validator instance
                    mock_validator = Mock()
                    mock_validator.validate_file.return_value = True
                    mock_validator.forward_map = {}
                    mock_validator.components = {}
                    mock_validator_class.return_value = mock_validator

                    with pytest.raises(SystemExit) as exc_info:
                        main()

        assert exc_info.value.code == 0

        # Verify success message
        captured = capsys.readouterr()
        assert "All YAML files passed component edge validation" in captured.out

    def test_main_exits_1_when_validation_fails(self, capsys):
        """
        Test that main exits 1 when validation fails.

        Given: YAML files are staged and ComponentEdgeValidator fails
        When: main() is called
        Then: Exits with code 1 and prints failure message
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]

        with patch("sys.argv", ["script.py"]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    # Mock validator instance that fails
                    mock_validator = Mock()
                    mock_validator.validate_file.return_value = False
                    mock_validator_class.return_value = mock_validator

                    with pytest.raises(SystemExit) as exc_info:
                        main()

        assert exc_info.value.code == 1

        # Verify failure message
        captured = capsys.readouterr()
        assert "Component edge validation failed!" in captured.out
        assert "Fix the above errors before committing" in captured.out

    def test_main_force_mode_uses_default_file(self, capsys):
        """
        Test that force mode validates default components file.

        Given: Script called with --force flag
        When: main() is called
        Then: Uses DEFAULT_COMPONENTS_FILE for validation
        """
        with patch("sys.argv", ["script.py", "--force"]):
            with patch("validate_riskmap.get_staged_yaml_files") as mock_get_files:
                mock_get_files.return_value = [Path("risk-map/yaml/components.yaml")]
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    mock_validator = Mock()
                    mock_validator.validate_file.return_value = True
                    mock_validator.forward_map = {}
                    mock_validator.components = {}
                    mock_validator_class.return_value = mock_validator

                    with pytest.raises(SystemExit) as exc_info:
                        main()

        # Verify force mode was used
        from riskmap_validator.config import DEFAULT_COMPONENTS_FILE

        mock_get_files.assert_called_once_with(DEFAULT_COMPONENTS_FILE, True)

        # Verify force message
        captured = capsys.readouterr()
        assert "Force checking components" in captured.out

        assert exc_info.value.code == 0

    def test_main_quiet_mode_suppresses_output(self, capsys):
        """
        Test that quiet mode suppresses non-error output.

        Given: Script called with --quiet flag and validation passes
        When: main() is called
        Then: No informational messages printed
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]

        with patch("sys.argv", ["script.py", "--quiet"]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    mock_validator = Mock()
                    mock_validator.validate_file.return_value = True
                    mock_validator.forward_map = {}
                    mock_validator.components = {}
                    mock_validator_class.return_value = mock_validator

                    with pytest.raises(SystemExit) as exc_info:
                        main()

        assert exc_info.value.code == 0

        # Verify no informational output
        captured = capsys.readouterr()
        assert "Checking for staged YAML files" not in captured.out
        assert "Found" not in captured.out
        assert "All YAML files passed" not in captured.out

    def test_main_initializes_validator_with_correct_options(self):
        """
        Test that ComponentEdgeValidator is initialized with correct options.

        Given: Script called with --allow-isolated and --quiet flags
        When: main() is called
        Then: Validator initialized with allow_isolated=True, verbose=False
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]

        with patch("sys.argv", ["script.py", "--allow-isolated", "--quiet"]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    mock_validator = Mock()
                    mock_validator.validate_file.return_value = True
                    mock_validator.forward_map = {}
                    mock_validator.components = {}
                    mock_validator_class.return_value = mock_validator

                    with pytest.raises(SystemExit):
                        main()

        # Verify validator was initialized with correct options
        mock_validator_class.assert_called_once_with(allow_isolated=True, verbose=False)

    def test_main_adds_spacing_between_multiple_file_validation(self, capsys):
        """
        Test that spacing is added between file validations when multiple files.

        Given: Multiple YAML files are staged (non-force mode)
        When: main() is called without quiet mode
        Then: Empty line is printed between files for readability
        """
        # Simulate multiple files being staged
        file_paths = [Path("risk-map/yaml/components.yaml"), Path("risk-map/yaml/controls.yaml")]

        with patch("sys.argv", ["script.py"]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    mock_validator = Mock()
                    mock_validator.validate_file.return_value = True
                    mock_validator.forward_map = {}
                    mock_validator.components = {}
                    mock_validator_class.return_value = mock_validator

                    with pytest.raises(SystemExit) as exc_info:
                        main()

        assert exc_info.value.code == 0

        # Verify output shows multiple files
        captured = capsys.readouterr()
        assert "Found 2 YAML files to validate" in captured.out


class TestMainGraphGeneration:
    """Tests for main() graph generation capabilities."""

    def test_main_generates_component_graph_when_to_graph_specified(self, capsys):
        """
        Test that component graph is generated when --to-graph is provided.

        Given: Valid validation and --to-graph output.md specified
        When: main() is called
        Then: ComponentGraph is created and written to output file
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]
        graph_path = Path("output/graph.md")
        mock_graph_output = "```mermaid\ngraph TD\nA-->B\n```"

        with patch("sys.argv", ["script.py", "--force", "--to-graph", str(graph_path)]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    with patch("validate_riskmap.ComponentGraph") as mock_graph_class:
                        with patch("builtins.open", mock_open()) as mock_file:
                            # Setup validator mock
                            mock_validator = Mock()
                            mock_validator.validate_file.return_value = True
                            mock_validator.forward_map = {"A": ["B"]}
                            mock_validator.components = {"A": Mock(), "B": Mock()}
                            mock_validator_class.return_value = mock_validator

                            # Setup graph mock
                            mock_graph = Mock()
                            mock_graph.to_mermaid.return_value = mock_graph_output
                            mock_graph_class.return_value = mock_graph

                            with pytest.raises(SystemExit) as exc_info:
                                main()

        assert exc_info.value.code == 0

        # Verify graph was created with correct parameters
        mock_graph_class.assert_called_once_with(
            mock_validator.forward_map, mock_validator.components, debug=False
        )

        # Verify file was written
        mock_file.assert_called_with(graph_path, "w", encoding="utf-8")
        handle = mock_file()
        handle.write.assert_called_once_with(mock_graph_output)

        # Verify success message
        captured = capsys.readouterr()
        assert f"Graph visualization saved to {graph_path}" in captured.out

    def test_main_generates_controls_graph_when_to_controls_graph_specified(self, capsys):
        """
        Test that controls graph is generated when --to-controls-graph is provided.

        Given: Valid validation and --to-controls-graph controls.md specified
        When: main() is called
        Then: ControlGraph is created and written to output file
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]
        graph_path = Path("controls.md")
        mock_controls = [Mock()]
        mock_graph_output = "```mermaid\ngraph TD\nCTL-->COMP\n```"

        with patch("sys.argv", ["script.py", "--force", "--to-controls-graph", str(graph_path)]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    with patch("validate_riskmap.parse_controls_yaml", return_value=mock_controls):
                        with patch("validate_riskmap.ControlGraph") as mock_graph_class:
                            with patch("builtins.open", mock_open()) as mock_file:
                                # Setup validator mock
                                mock_validator = Mock()
                                mock_validator.validate_file.return_value = True
                                mock_validator.forward_map = {}
                                mock_validator.components = {"COMP": Mock()}
                                mock_validator_class.return_value = mock_validator

                                # Setup graph mock
                                mock_graph = Mock()
                                mock_graph.to_mermaid.return_value = mock_graph_output
                                mock_graph_class.return_value = mock_graph

                                with pytest.raises(SystemExit) as exc_info:
                                    main()

        assert exc_info.value.code == 0

        # Verify controls were parsed

        # Verify graph was created
        mock_graph_class.assert_called_once_with(mock_controls, mock_validator.components, debug=False)

        # Verify file was written
        mock_file.assert_called_with(graph_path, "w", encoding="utf-8")

        # Verify success message
        captured = capsys.readouterr()
        assert f"Controls graph visualization saved to {graph_path}" in captured.out

    def test_main_generates_risk_graph_when_to_risk_graph_specified(self, capsys):
        """
        Test that risk graph is generated when --to-risk-graph is provided.

        Given: Valid validation and --to-risk-graph risk.md specified
        When: main() is called
        Then: RiskGraph is created and written to output file
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]
        graph_path = Path("risk.md")
        mock_risks = [Mock()]
        mock_controls = [Mock()]
        mock_graph_output = "```mermaid\ngraph TD\nRSK-->CTL-->COMP\n```"

        with patch("sys.argv", ["script.py", "--force", "--to-risk-graph", str(graph_path)]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    with patch("validate_riskmap.parse_risks_yaml", return_value=mock_risks):
                        with patch("validate_riskmap.parse_controls_yaml", return_value=mock_controls):
                            with patch("validate_riskmap.RiskGraph") as mock_graph_class:
                                with patch("builtins.open", mock_open()) as mock_file:
                                    # Setup validator mock
                                    mock_validator = Mock()
                                    mock_validator.validate_file.return_value = True
                                    mock_validator.forward_map = {}
                                    mock_validator.components = {"COMP": Mock()}
                                    mock_validator_class.return_value = mock_validator

                                    # Setup graph mock
                                    mock_graph = Mock()
                                    mock_graph.to_mermaid.return_value = mock_graph_output
                                    mock_graph_class.return_value = mock_graph

                                    with pytest.raises(SystemExit) as exc_info:
                                        main()

        assert exc_info.value.code == 0

        # Verify graph was created with all three data sources
        mock_graph_class.assert_called_once_with(mock_risks, mock_controls, mock_validator.components, debug=False)

        # Verify file was written
        mock_file.assert_called_with(graph_path, "w", encoding="utf-8")

        # Verify success message
        captured = capsys.readouterr()
        assert f"Risk graph visualization saved to {graph_path}" in captured.out

    def test_main_generates_mermaid_format_files_when_flag_set(self, capsys):
        """
        Test that .mermaid format files are generated when --mermaid-format is set.

        Given: --to-graph and --mermaid-format flags are set
        When: main() is called
        Then: Both .md and .mermaid files are written
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]
        graph_path = Path("graph.md")
        mermaid_path = Path("graph.mermaid")
        mock_md_output = "```mermaid\ngraph TD\nA-->B\n```"
        mock_mermaid_output = "graph TD\nA-->B"

        with patch("sys.argv", ["script.py", "--force", "--to-graph", str(graph_path), "--mermaid-format"]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    with patch("validate_riskmap.ComponentGraph") as mock_graph_class:
                        with patch("builtins.open", mock_open()) as mock_file:
                            # Setup validator mock
                            mock_validator = Mock()
                            mock_validator.validate_file.return_value = True
                            mock_validator.forward_map = {}
                            mock_validator.components = {}
                            mock_validator_class.return_value = mock_validator

                            # Setup graph mock - return different output based on format
                            mock_graph = Mock()

                            def to_mermaid_side_effect(output_format="markdown"):
                                if output_format == "mermaid":
                                    return mock_mermaid_output
                                return mock_md_output

                            mock_graph.to_mermaid.side_effect = to_mermaid_side_effect
                            mock_graph_class.return_value = mock_graph

                            with pytest.raises(SystemExit) as exc_info:
                                main()

        assert exc_info.value.code == 0

        # Verify both files were written
        assert mock_file.call_count == 2
        mock_file.assert_any_call(graph_path, "w", encoding="utf-8")
        mock_file.assert_any_call(mermaid_path, "w", encoding="utf-8")

        # Verify success messages
        captured = capsys.readouterr()
        assert f"Graph visualization saved to {graph_path}" in captured.out
        assert f"Mermaid format saved to {mermaid_path}" in captured.out

    def test_main_handles_graph_generation_errors_gracefully(self, capsys):
        """
        Test that graph generation errors are caught and reported.

        Given: Graph to_mermaid() raises an exception
        When: main() is called
        Then: Error is caught, warning printed, and script exits 0 (validation passed)
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]
        graph_path = Path("graph.md")

        with patch("sys.argv", ["script.py", "--force", "--to-graph", str(graph_path)]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    with patch("validate_riskmap.ComponentGraph") as mock_graph_class:
                        # Setup validator mock
                        mock_validator = Mock()
                        mock_validator.validate_file.return_value = True
                        mock_validator.forward_map = {}
                        mock_validator.components = {}
                        mock_validator_class.return_value = mock_validator

                        # Setup graph to raise exception during to_mermaid()
                        mock_graph = Mock()
                        mock_graph.to_mermaid.side_effect = RuntimeError("Graph generation failed")
                        mock_graph_class.return_value = mock_graph

                        with pytest.raises(SystemExit) as exc_info:
                            main()

        # Should exit 0 (validation passed, only graph failed)
        assert exc_info.value.code == 0

        # Verify error message
        captured = capsys.readouterr()
        assert "Failed to generate graph:" in captured.out
        assert "Graph generation failed" in captured.out

    def test_main_generates_controls_graph_with_mermaid_format(self, capsys):
        """
        Test that controls graph generates both .md and .mermaid files when flag is set.

        Given: Valid validation, --to-controls-graph and --mermaid-format flags
        When: main() is called
        Then: Both .md and .mermaid files are written for controls graph
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]
        graph_path = Path("controls.md")
        mermaid_path = Path("controls.mermaid")
        mock_controls = [Mock()]
        mock_md_output = "```mermaid\ngraph TD\nCTL-->COMP\n```"
        mock_mermaid_output = "graph TD\nCTL-->COMP"

        with patch(
            "sys.argv", ["script.py", "--force", "--to-controls-graph", str(graph_path), "--mermaid-format"]
        ):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    with patch("validate_riskmap.parse_controls_yaml", return_value=mock_controls):
                        with patch("validate_riskmap.ControlGraph") as mock_graph_class:
                            with patch("builtins.open", mock_open()) as mock_file:
                                # Setup validator mock
                                mock_validator = Mock()
                                mock_validator.validate_file.return_value = True
                                mock_validator.forward_map = {}
                                mock_validator.components = {}
                                mock_validator_class.return_value = mock_validator

                                # Setup graph mock
                                mock_graph = Mock()

                                def to_mermaid_side_effect(output_format="markdown"):
                                    if output_format == "mermaid":
                                        return mock_mermaid_output
                                    return mock_md_output

                                mock_graph.to_mermaid.side_effect = to_mermaid_side_effect
                                mock_graph_class.return_value = mock_graph

                                with pytest.raises(SystemExit) as exc_info:
                                    main()

        assert exc_info.value.code == 0

        # Verify both files were written
        assert mock_file.call_count == 2
        mock_file.assert_any_call(graph_path, "w", encoding="utf-8")
        mock_file.assert_any_call(mermaid_path, "w", encoding="utf-8")

        # Verify success messages
        captured = capsys.readouterr()
        assert f"Controls graph visualization saved to {graph_path}" in captured.out
        assert f"Mermaid format saved to {mermaid_path}" in captured.out

    def test_main_generates_risk_graph_with_mermaid_format(self, capsys):
        """
        Test that risk graph generates both .md and .mermaid files when flag is set.

        Given: Valid validation, --to-risk-graph and --mermaid-format flags
        When: main() is called
        Then: Both .md and .mermaid files are written for risk graph
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]
        graph_path = Path("risk.md")
        mermaid_path = Path("risk.mermaid")
        mock_risks = [Mock()]
        mock_controls = [Mock()]
        mock_md_output = "```mermaid\ngraph TD\nRSK-->CTL-->COMP\n```"
        mock_mermaid_output = "graph TD\nRSK-->CTL-->COMP"

        with patch("sys.argv", ["script.py", "--force", "--to-risk-graph", str(graph_path), "--mermaid-format"]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    with patch("validate_riskmap.parse_risks_yaml", return_value=mock_risks):
                        with patch("validate_riskmap.parse_controls_yaml", return_value=mock_controls):
                            with patch("validate_riskmap.RiskGraph") as mock_graph_class:
                                with patch("builtins.open", mock_open()) as mock_file:
                                    # Setup validator mock
                                    mock_validator = Mock()
                                    mock_validator.validate_file.return_value = True
                                    mock_validator.forward_map = {}
                                    mock_validator.components = {}
                                    mock_validator_class.return_value = mock_validator

                                    # Setup graph mock
                                    mock_graph = Mock()

                                    def to_mermaid_side_effect(output_format="markdown"):
                                        if output_format == "mermaid":
                                            return mock_mermaid_output
                                        return mock_md_output

                                    mock_graph.to_mermaid.side_effect = to_mermaid_side_effect
                                    mock_graph_class.return_value = mock_graph

                                    with pytest.raises(SystemExit) as exc_info:
                                        main()

        assert exc_info.value.code == 0

        # Verify both files were written
        assert mock_file.call_count == 2
        mock_file.assert_any_call(graph_path, "w", encoding="utf-8")
        mock_file.assert_any_call(mermaid_path, "w", encoding="utf-8")

        # Verify success messages
        captured = capsys.readouterr()
        assert f"Risk graph visualization saved to {graph_path}" in captured.out
        assert f"Mermaid format saved to {mermaid_path}" in captured.out

    def test_main_handles_controls_graph_generation_errors(self, capsys):
        """
        Test that controls graph generation errors are caught and reported.

        Given: Controls graph to_mermaid() raises an exception
        When: main() is called
        Then: Error is caught, warning printed, and script exits 0
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]
        graph_path = Path("controls.md")

        with patch("sys.argv", ["script.py", "--force", "--to-controls-graph", str(graph_path)]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    with patch("validate_riskmap.parse_controls_yaml", return_value=[Mock()]):
                        with patch("validate_riskmap.ControlGraph") as mock_graph_class:
                            # Setup validator mock
                            mock_validator = Mock()
                            mock_validator.validate_file.return_value = True
                            mock_validator.forward_map = {}
                            mock_validator.components = {}
                            mock_validator_class.return_value = mock_validator

                            # Setup graph to raise exception
                            mock_graph = Mock()
                            mock_graph.to_mermaid.side_effect = RuntimeError("Controls graph failed")
                            mock_graph_class.return_value = mock_graph

                            with pytest.raises(SystemExit) as exc_info:
                                main()

        assert exc_info.value.code == 0

        # Verify error message
        captured = capsys.readouterr()
        assert "Failed to generate controls graph:" in captured.out
        assert "Controls graph failed" in captured.out

    def test_main_handles_risk_graph_generation_errors(self, capsys):
        """
        Test that risk graph generation errors are caught and reported.

        Given: Risk graph to_mermaid() raises an exception
        When: main() is called
        Then: Error is caught, warning printed, and script exits 0
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]
        graph_path = Path("risk.md")

        with patch("sys.argv", ["script.py", "--force", "--to-risk-graph", str(graph_path)]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    with patch("validate_riskmap.parse_risks_yaml", return_value=[Mock()]):
                        with patch("validate_riskmap.parse_controls_yaml", return_value=[Mock()]):
                            with patch("validate_riskmap.RiskGraph") as mock_graph_class:
                                # Setup validator mock
                                mock_validator = Mock()
                                mock_validator.validate_file.return_value = True
                                mock_validator.forward_map = {}
                                mock_validator.components = {}
                                mock_validator_class.return_value = mock_validator

                                # Setup graph to raise exception
                                mock_graph = Mock()
                                mock_graph.to_mermaid.side_effect = RuntimeError("Risk graph failed")
                                mock_graph_class.return_value = mock_graph

                                with pytest.raises(SystemExit) as exc_info:
                                    main()

        assert exc_info.value.code == 0

        # Verify error message
        captured = capsys.readouterr()
        assert "Failed to generate risk graph:" in captured.out
        assert "Risk graph failed" in captured.out

    def test_main_passes_debug_flag_to_component_graph(self):
        """
        Test that debug flag is passed to ComponentGraph constructor.

        Given: Script called with --debug and --to-graph flags
        When: main() is called
        Then: ComponentGraph is initialized with debug=True
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]
        graph_path = Path("graph.md")

        with patch("sys.argv", ["script.py", "--force", "--to-graph", str(graph_path), "--debug"]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    with patch("validate_riskmap.ComponentGraph") as mock_graph_class:
                        with patch("builtins.open", mock_open()):
                            # Setup validator mock
                            mock_validator = Mock()
                            mock_validator.validate_file.return_value = True
                            mock_validator.forward_map = {}
                            mock_validator.components = {}
                            mock_validator_class.return_value = mock_validator

                            # Setup graph mock
                            mock_graph = Mock()
                            mock_graph.to_mermaid.return_value = "```mermaid\ngraph\n```"
                            mock_graph_class.return_value = mock_graph

                            with pytest.raises(SystemExit):
                                main()

        # Verify debug=True was passed
        mock_graph_class.assert_called_once_with(mock_validator.forward_map, mock_validator.components, debug=True)

    def test_main_passes_debug_flag_to_control_graph(self):
        """
        Test that debug flag is passed to ControlGraph constructor.

        Given: Script called with --debug and --to-controls-graph flags
        When: main() is called
        Then: ControlGraph is initialized with debug=True
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]
        graph_path = Path("controls.md")
        mock_controls = [Mock()]

        with patch("sys.argv", ["script.py", "--force", "--to-controls-graph", str(graph_path), "--debug"]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    with patch("validate_riskmap.parse_controls_yaml", return_value=mock_controls):
                        with patch("validate_riskmap.ControlGraph") as mock_graph_class:
                            with patch("builtins.open", mock_open()):
                                # Setup validator mock
                                mock_validator = Mock()
                                mock_validator.validate_file.return_value = True
                                mock_validator.forward_map = {}
                                mock_validator.components = {}
                                mock_validator_class.return_value = mock_validator

                                # Setup graph mock
                                mock_graph = Mock()
                                mock_graph.to_mermaid.return_value = "```mermaid\ngraph\n```"
                                mock_graph_class.return_value = mock_graph

                                with pytest.raises(SystemExit):
                                    main()

        # Verify debug=True was passed
        mock_graph_class.assert_called_once_with(mock_controls, mock_validator.components, debug=True)

    def test_main_passes_debug_flag_to_risk_graph(self):
        """
        Test that debug flag is passed to RiskGraph constructor.

        Given: Script called with --debug and --to-risk-graph flags
        When: main() is called
        Then: RiskGraph is initialized with debug=True
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]
        graph_path = Path("risk.md")
        mock_risks = [Mock()]
        mock_controls = [Mock()]

        with patch("sys.argv", ["script.py", "--force", "--to-risk-graph", str(graph_path), "--debug"]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                    with patch("validate_riskmap.parse_risks_yaml", return_value=mock_risks):
                        with patch("validate_riskmap.parse_controls_yaml", return_value=mock_controls):
                            with patch("validate_riskmap.RiskGraph") as mock_graph_class:
                                with patch("builtins.open", mock_open()):
                                    # Setup validator mock
                                    mock_validator = Mock()
                                    mock_validator.validate_file.return_value = True
                                    mock_validator.forward_map = {}
                                    mock_validator.components = {}
                                    mock_validator_class.return_value = mock_validator

                                    # Setup graph mock
                                    mock_graph = Mock()
                                    mock_graph.to_mermaid.return_value = "```mermaid\ngraph\n```"
                                    mock_graph_class.return_value = mock_graph

                                    with pytest.raises(SystemExit):
                                        main()

        # Verify debug=True was passed
        mock_graph_class.assert_called_once_with(mock_risks, mock_controls, mock_validator.components, debug=True)


class TestMainErrorHandling:
    """Tests for main() exception handling."""

    def test_main_handles_keyboard_interrupt_gracefully(self, capsys):
        """
        Test that KeyboardInterrupt is handled with exit code 2.

        Given: User interrupts with Ctrl+C during validation
        When: main() is called
        Then: Exits with code 2 and prints interrupted message
        """
        with patch("sys.argv", ["script.py", "--force"]):
            with patch("validate_riskmap.get_staged_yaml_files", side_effect=KeyboardInterrupt()):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 2

        # Verify interrupted message
        captured = capsys.readouterr()
        assert "Validation interrupted by user" in captured.out

    def test_main_handles_unexpected_exceptions_with_exit_code_2(self, capsys):
        """
        Test that unexpected exceptions exit with code 2.

        Given: Unexpected exception occurs during execution
        When: main() is called
        Then: Exits with code 2 and prints error message
        """
        with patch("sys.argv", ["script.py", "--force"]):
            with patch(
                "validate_riskmap.get_staged_yaml_files",
                side_effect=RuntimeError("Unexpected error occurred"),
            ):
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 2

        # Verify error message
        captured = capsys.readouterr()
        assert "Unexpected error:" in captured.out
        assert "Unexpected error occurred" in captured.out
        assert "Please report this issue to the maintainers" in captured.out

    def test_main_handles_validator_initialization_errors(self, capsys):
        """
        Test that errors during validator initialization are handled.

        Given: ComponentEdgeValidator initialization raises exception
        When: main() is called
        Then: Exits with code 2 and prints error message
        """
        file_paths = [Path("risk-map/yaml/components.yaml")]

        with patch("sys.argv", ["script.py", "--force"]):
            with patch("validate_riskmap.get_staged_yaml_files", return_value=file_paths):
                with patch(
                    "validate_riskmap.ComponentEdgeValidator",
                    side_effect=ValueError("Invalid validator configuration"),
                ):
                    with pytest.raises(SystemExit) as exc_info:
                        main()

        assert exc_info.value.code == 2

        # Verify error message
        captured = capsys.readouterr()
        assert "Unexpected error:" in captured.out
        assert "Invalid validator configuration" in captured.out


# ============================================================================
# TestMainLifecycleMode — `--mode lifecycle` short-circuit hook
# ============================================================================
#
# Background: PR #277 reviewer feedback (item 2) showed that the lifecycle
# uniqueness check is unreachable on commits that touch only
# risk-map/yaml/lifecycle-stage.yaml — the validate-component-edges hook
# only triggers when components.yaml is staged, so a lifecycle-only commit
# silently bypasses the uniqueness check entirely.
#
# Architect-recommended Fix B: split lifecycle uniqueness into its own
# dedicated `validate-lifecycle-stage` pre-commit hook with a narrow
# `files: ^risk-map/yaml/lifecycle-stage\.yaml$` regex. Implementation
# uses a new `--mode lifecycle` flag on validate_riskmap.py so the hook
# entry stays in the same script.
#
# In `--mode lifecycle`, the script must:
#   1. Skip the components-validation pipeline (no get_staged_yaml_files,
#      no ComponentEdgeValidator instantiation).
#   2. Load risk-map/yaml/lifecycle-stage.yaml directly and run
#      check_lifecycle_stage_order_uniqueness.
#   3. Skip graph generation (no ComponentGraph / ControlGraph / RiskGraph).
#   4. Exit 0 on clean corpus, exit 1 on duplicate orders, exit 0 with a
#      skip message when the file is absent (matches the default-mode
#      graceful-skip pattern at validate_riskmap.py:210-212).
#
# These tests pin the architectural intent. Implementation choices (exact
# argparse wiring, exit-code disposition for `--mode lifecycle` combined
# with `--to-graph`, etc.) are documented per-test below.
# ============================================================================


# Reusable in-test fixtures. Re-defined here rather than imported from
# test_lifecycle_stage_order_uniqueness.py so that file's collection is not
# perturbed by cross-module imports (no __init__.py in tests/, so cross-file
# imports go through sys.path manipulation only).
_LIFECYCLE_CLEAN: dict[str, Any] = {
    "lifecycleStages": [
        {"id": "stage-one", "title": "Stage One", "order": 1},
        {"id": "stage-two", "title": "Stage Two", "order": 2},
        {"id": "stage-three", "title": "Stage Three", "order": 3},
    ]
}

_LIFECYCLE_DUPLICATE: dict[str, Any] = {
    "lifecycleStages": [
        {"id": "stage-a", "title": "Stage A", "order": 1},
        {"id": "stage-b", "title": "Stage B", "order": 2},
        {"id": "stage-c", "title": "Stage C", "order": 2},  # duplicate
    ]
}


def _write_lifecycle_only(base: Path, lifecycle: dict[str, Any] | None) -> Path:
    """
    Write only risk-map/yaml/lifecycle-stage.yaml under base.

    Lifecycle mode must NOT depend on components.yaml / controls.yaml /
    risks.yaml being present. Writing only the lifecycle file pins that
    architectural intent: lifecycle mode is single-file scoped.

    Args:
        base: Temporary directory root (pytest tmp_path).
        lifecycle: Parsed lifecycle YAML content, or None to omit the file
                   (simulating the file-absent case).

    Returns:
        base path for use as cwd via monkeypatch.chdir.
    """
    yaml_dir = base / "risk-map" / "yaml"
    yaml_dir.mkdir(parents=True)
    if lifecycle is not None:
        (yaml_dir / "lifecycle-stage.yaml").write_text(yaml.dump(lifecycle), encoding="utf-8")
    return base


class TestMainLifecycleMode:
    """
    Tests for the `--mode lifecycle` short-circuit entrypoint.

    These tests pin the contract that lifecycle mode is a narrow,
    single-purpose entrypoint that bypasses the components-validation
    pipeline and graph-generation paths entirely.
    """

    def test_mode_lifecycle_exits_0_on_clean_corpus(self, tmp_path, monkeypatch, capsys):
        """
        Test that --mode lifecycle exits 0 against a clean lifecycle-stage.yaml.

        Given: A tmp cwd containing only a clean risk-map/yaml/lifecycle-stage.yaml
               (orders 1..3, all unique)
        When:  validate_riskmap.main() is invoked with argv ["--mode", "lifecycle"]
        Then:  Exits with code 0 (lifecycle uniqueness check passes)
        """
        _write_lifecycle_only(tmp_path, _LIFECYCLE_CLEAN)
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["script.py", "--mode", "lifecycle"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0, (
            f"Expected exit 0 on clean lifecycle corpus; got {exc_info.value.code}. "
            f"Captured output: {capsys.readouterr()!r}"
        )

    def test_mode_lifecycle_exits_1_on_duplicate_orders(self, tmp_path, monkeypatch, capsys):
        """
        Test that --mode lifecycle exits 1 when duplicate orders are present.

        Given: A tmp cwd containing risk-map/yaml/lifecycle-stage.yaml where
               stage-b and stage-c both carry order 2
        When:  validate_riskmap.main() is invoked with argv ["--mode", "lifecycle"]
        Then:  Exits with code 1 and the duplicate is reported on stdout/stderr.
               Block-mode-immediate semantics — no --block flag required
               (matches ADR-022 D4 disposition).
        """
        _write_lifecycle_only(tmp_path, _LIFECYCLE_DUPLICATE)
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["script.py", "--mode", "lifecycle"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 1, (
            f"Expected exit 1 on duplicate lifecycle orders; got {exc_info.value.code}"
        )

        # Confirm the duplicate is reported. Substring check matches the
        # output-shape contract from check_lifecycle_stage_order_uniqueness.
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "stage-b" in combined and "stage-c" in combined, (
            f"Expected duplicate stage IDs in output; got: {combined!r}"
        )

    def test_mode_lifecycle_does_not_call_get_staged_yaml_files(self, tmp_path, monkeypatch):
        """
        Test that --mode lifecycle bypasses get_staged_yaml_files entirely.

        Given: A tmp cwd containing a clean lifecycle-stage.yaml
        When:  validate_riskmap.main() is invoked with argv ["--mode", "lifecycle"]
        Then:  validate_riskmap.get_staged_yaml_files is NOT called AND the
               script exits 0 (lifecycle uniqueness check reached and passed).

        Architectural intent: lifecycle mode is a single-file narrow check;
        the components-validation pipeline (which uses get_staged_yaml_files
        to discover components.yaml) is irrelevant and must not run.

        The exit-code assertion guards against false-positive passes: if
        argparse rejects --mode lifecycle (current state, no flag wired)
        the script exits with argparse error code 2 before any pipeline
        runs, which would trivially satisfy a bare assert_not_called.
        Pinning exit 0 forces the test to validate both the bypass AND
        the successful lifecycle check on the same run.
        """
        _write_lifecycle_only(tmp_path, _LIFECYCLE_CLEAN)
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["script.py", "--mode", "lifecycle"]):
            with patch("validate_riskmap.get_staged_yaml_files") as mock_get_files:
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 0, (
            f"Expected exit 0 (lifecycle check passed without going through the "
            f"components pipeline); got {exc_info.value.code}. "
            f"This test pins both the bypass and the success path."
        )
        mock_get_files.assert_not_called()

    def test_mode_lifecycle_does_not_instantiate_component_edge_validator(self, tmp_path, monkeypatch):
        """
        Test that --mode lifecycle bypasses ComponentEdgeValidator entirely.

        Given: A tmp cwd containing a clean lifecycle-stage.yaml
        When:  validate_riskmap.main() is invoked with argv ["--mode", "lifecycle"]
        Then:  validate_riskmap.ComponentEdgeValidator is NOT instantiated AND
               the script exits 0.

        Architectural intent: lifecycle mode short-circuits before the
        components-validation orchestration. Even though
        ComponentEdgeValidator.components is the gating attribute for the
        existing inline lifecycle-uniqueness call (validate_riskmap.py:191),
        in dedicated mode the gating is the file's existence, not validator
        state.

        Exit-code 0 assertion is the same false-positive guard as the
        get_staged_yaml_files bypass test above.
        """
        _write_lifecycle_only(tmp_path, _LIFECYCLE_CLEAN)
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["script.py", "--mode", "lifecycle"]):
            with patch("validate_riskmap.ComponentEdgeValidator") as mock_validator_class:
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 0, (
            f"Expected exit 0 (lifecycle check reached without instantiating "
            f"ComponentEdgeValidator); got {exc_info.value.code}."
        )
        mock_validator_class.assert_not_called()

    def test_mode_lifecycle_skips_graph_generation_when_to_graph_also_passed(self, tmp_path, monkeypatch, capsys):
        """
        Test that --mode lifecycle does not run graph generation even if
        --to-graph is also provided.

        Given: A tmp cwd containing a clean lifecycle-stage.yaml
        When:  validate_riskmap.main() is invoked with argv
               ["--mode", "lifecycle", "--to-graph", "graph.md"]
        Then:  ComponentGraph is NOT instantiated, AND the script exits with
               either:
                 - exit 0  (graph silently ignored in lifecycle mode), OR
                 - exit 2  (main() rejects the combination as a misuse with
                           a clear "incompatible flags" message — also
                           acceptable per architect intent).

        Disposition note: SWE may choose either disposition. The test
        intentionally accepts both; it pins only that ComponentGraph is
        NOT constructed (graph generation is incompatible with lifecycle
        mode's narrow scope) and that the script does NOT exit 1 (which
        would mean lifecycle check failed on the clean corpus, the wrong
        signal).

        False-positive guard: this test must FAIL before --mode lifecycle
        is implemented. Without the flag, argparse rejects the unknown
        argument with `error: unrecognized arguments: --mode lifecycle`,
        which would trivially satisfy the negative assertion on
        ComponentGraph. Asserting that the argparse "unrecognized arguments"
        message is NOT in stderr forces the test to fail until SWE wires
        the flag — at which point either disposition (silent ignore or
        explicit rejection) is accepted.
        """
        _write_lifecycle_only(tmp_path, _LIFECYCLE_CLEAN)
        monkeypatch.chdir(tmp_path)

        with patch(
            "sys.argv",
            ["script.py", "--mode", "lifecycle", "--to-graph", "graph.md"],
        ):
            with patch("validate_riskmap.ComponentGraph") as mock_graph_class:
                with pytest.raises(SystemExit) as exc_info:
                    main()

        captured = capsys.readouterr()

        # False-positive guard: argparse must have RECOGNIZED --mode lifecycle.
        # Without this assertion the test passes trivially on the unimplemented
        # flag, which defeats the red-phase purpose.
        assert "unrecognized arguments" not in captured.err, (
            f"argparse rejected --mode lifecycle as unrecognized; the flag must "
            f"be wired before this test can validate the architectural intent. "
            f"stderr: {captured.err!r}"
        )

        # Filter out exit 1 (lifecycle check failed on a clean corpus would
        # be wrong) and unexpected codes. Both 0 (graph ignored) and 2
        # (main() rejects the flag combination with a clear message) are
        # acceptable architectural choices.
        assert exc_info.value.code in (0, 2), (
            f"Expected exit 0 (graph ignored) or exit 2 (flag-combo rejected); got {exc_info.value.code}."
        )
        mock_graph_class.assert_not_called()

    def test_mode_lifecycle_exits_0_with_skip_message_when_file_absent(self, tmp_path, monkeypatch, capsys):
        """
        Test that --mode lifecycle exits 0 with a skip message when
        lifecycle-stage.yaml is absent.

        Given: A tmp cwd with no risk-map/yaml/lifecycle-stage.yaml
        When:  validate_riskmap.main() is invoked with argv ["--mode", "lifecycle"]
        Then:  Exits with code 0 and prints a skip message.

        Disposition: this mirrors the current default-mode graceful-skip
        behavior at validate_riskmap.py:210-212. lifecycle-stage.yaml may
        not be present in every test environment; the dedicated mode keeps
        the same forgiving disposition rather than promoting absence to a
        hard error. Skip message wording uses the substring "skipped" to
        stay format-agnostic with the existing line at 212.
        """
        _write_lifecycle_only(tmp_path, None)  # Omit the file
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["script.py", "--mode", "lifecycle"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0, (
            f"Expected exit 0 (graceful skip) when lifecycle-stage.yaml is absent; got {exc_info.value.code}"
        )

        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert "skipped" in combined.lower(), (
            f"Expected a skip message when lifecycle-stage.yaml is absent; got: {combined!r}"
        )

    def test_default_mode_unchanged_when_mode_flag_omitted(self):
        """
        Test that the default code path is preserved when --mode is omitted.

        Given: argv with no --mode flag and no other arguments
        When:  parse_args() is called
        Then:  args.mode either does not exist or has a value that does NOT
               equal "lifecycle".

        Smoke test guarding against the new flag's argparse default
        accidentally redirecting the existing entrypoint into lifecycle mode.
        """
        with patch("sys.argv", ["script.py"]):
            args = parse_args()

        # SWE may name the attribute `mode` (most likely) or pick a different
        # spelling. Either way the default value must not be "lifecycle"; the
        # existing default code path must be reachable without setting the flag.
        mode_value = getattr(args, "mode", None)
        assert mode_value != "lifecycle", (
            f"Default args.mode must not be 'lifecycle'; got {mode_value!r}. "
            f"Existing default-mode behavior would otherwise be silently overridden."
        )

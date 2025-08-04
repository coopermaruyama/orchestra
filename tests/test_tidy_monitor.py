#!/usr/bin/env python3
"""
Tests for Tidy Monitor
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from orchestra.extensions.tidy.project_detector import PackageManager, ProjectType
from orchestra.extensions.tidy.tidy_monitor import TidyMonitor
from orchestra.extensions.tidy.tool_runners import ToolResult


class TestTidyMonitor(unittest.TestCase):
    """Test the tidy monitor"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

        # Set CLAUDE_WORKING_DIR for testing
        os.environ["CLAUDE_WORKING_DIR"] = self.temp_dir

        # Create .claude directory
        claude_dir = Path(self.temp_dir) / ".claude" / "orchestra"
        claude_dir.mkdir(parents=True, exist_ok=True)

        # Create test Python file
        self.test_file = Path(self.temp_dir) / "test.py"
        self.test_file.write_text("import os\n\nprint('hello')\n")

    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
        if "CLAUDE_WORKING_DIR" in os.environ:
            del os.environ["CLAUDE_WORKING_DIR"]

    def test_initialization(self):
        """Test TidyMonitor initialization"""
        monitor = TidyMonitor()

        self.assertEqual(monitor.working_dir, self.temp_dir)
        self.assertIsNotNone(monitor.project_info)
        self.assertIsInstance(monitor.detected_tools, dict)
        self.assertIsInstance(monitor.settings, dict)
        self.assertTrue(monitor.settings["strict_mode"])
        self.assertFalse(monitor.settings["auto_fix"])

    @patch("orchestra.extensions.tidy.project_detector.ProjectDetector.detect")
    def test_auto_detect_project(self, mock_detect):
        """Test automatic project detection"""
        # Mock project detection
        mock_project_info = MagicMock()
        mock_project_info.project_type = ProjectType.PYTHON
        mock_project_info.package_manager = PackageManager.PIP
        mock_linter = MagicMock()
        mock_linter.name = "ruff"
        mock_linter.command = "ruff check ."
        mock_linter.fix_command = "ruff check . --fix"
        mock_linter.is_available = True
        mock_linter.config_file = None
        mock_linter.version = None
        mock_project_info.detected_tools = {"linter": mock_linter}
        mock_project_info.config_files = ["pyproject.toml"]
        mock_project_info.source_files = ["test.py"]
        mock_detect.return_value = mock_project_info

        monitor = TidyMonitor()

        self.assertEqual(monitor.project_info["type"], "python")
        self.assertEqual(monitor.project_info["package_manager"], "pip")
        self.assertIn("linter", monitor.detected_tools)

    def test_handle_post_tool_use(self):
        """Test tracking file modifications"""
        monitor = TidyMonitor()

        # Test Edit tool
        context = {"tool_name": "Edit", "tool_input": {"file_path": "test.py"}}

        response = monitor.handle_hook("PostToolUse", context)

        self.assertIn("test.py", monitor.modified_files)

        # Test Write tool
        context = {"tool_name": "Write", "tool_input": {"file_path": "new_file.py"}}

        response = monitor.handle_hook("PostToolUse", context)

        self.assertIn("new_file.py", monitor.modified_files)
        self.assertEqual(len(monitor.modified_files), 2)

    def test_should_ignore_file(self):
        """Test file ignore patterns"""
        monitor = TidyMonitor()

        # Test default ignore patterns
        self.assertTrue(monitor._should_ignore_file("migrations/0001_initial.py"))
        self.assertTrue(monitor._should_ignore_file("node_modules/package/index.js"))
        self.assertTrue(monitor._should_ignore_file("script.min.js"))

        # Test non-ignored files
        self.assertFalse(monitor._should_ignore_file("main.py"))
        self.assertFalse(monitor._should_ignore_file("src/utils.js"))

    @patch("orchestra.extensions.tidy.tool_runners.ToolRunnerFactory.create")
    def test_run_checks(self, mock_factory):
        """Test running checks on files"""
        monitor = TidyMonitor()

        # Set up detected tools
        monitor.detected_tools = {
            "linter": {"name": "ruff", "command": "ruff check .", "is_available": True}
        }

        # Mock tool runner
        mock_runner = MagicMock()
        mock_runner.check.return_value = ToolResult(
            success=False,
            output="",
            error="Found 2 issues",
            issues_count=2,
            issues=[
                {
                    "file": "test.py",
                    "line": 1,
                    "column": 1,
                    "message": "Missing docstring",
                },
                {"file": "test.py", "line": 3, "column": 1, "message": "Line too long"},
            ],
            exit_code=1,
            duration=0.5,
            can_fix=True,
        )
        mock_factory.return_value = mock_runner

        # Run checks
        results = monitor._run_checks(["test.py"])

        self.assertIn("linter", results)
        self.assertEqual(results["linter"].issues_count, 2)
        self.assertFalse(results["linter"].success)
        self.assertTrue(results["linter"].can_fix)

    def test_format_check_results_all_pass(self):
        """Test formatting results when all checks pass"""
        monitor = TidyMonitor()

        # Create results with no issues
        results = {
            "linter": ToolResult(
                success=True,
                output="",
                error="",
                issues_count=0,
                issues=[],
                exit_code=0,
                duration=0.5,
            )
        }

        response = monitor._format_check_results(results)

        # Should return allow response when all pass
        self.assertIn("decision", response)
        self.assertEqual(response.get("decision"), "approve")

    def test_format_check_results_with_issues(self):
        """Test formatting results with issues"""
        monitor = TidyMonitor()

        # Create results with issues
        results = {
            "linter": ToolResult(
                success=False,
                output="",
                error="",
                issues_count=2,
                issues=[
                    {
                        "file": "test.py",
                        "line": 1,
                        "column": 1,
                        "message": "Missing docstring",
                    },
                    {
                        "file": "test.py",
                        "line": 3,
                        "column": 1,
                        "message": "Line too long",
                    },
                ],
                exit_code=1,
                duration=0.5,
                can_fix=True,
            )
        }

        response = monitor._format_check_results(results)

        # Should return block response with issues
        self.assertIn("decision", response)
        self.assertEqual(response["decision"], "block")
        self.assertIn("reason", response)
        self.assertIn("2 issue(s)", response["reason"])
        self.assertIn("Missing docstring", response["reason"])

    @patch("orchestra.extensions.tidy.tidy_monitor.TidyMonitor._run_checks")
    def test_handle_stop_hook(self, mock_run_checks):
        """Test handling Stop hook"""
        monitor = TidyMonitor()
        monitor.modified_files = ["test.py"]

        # Mock check results
        mock_run_checks.return_value = {
            "linter": ToolResult(
                success=True,
                output="",
                error="",
                issues_count=0,
                issues=[],
                exit_code=0,
                duration=0.5,
            )
        }

        context = {"stop_hook_active": False}
        response = monitor.handle_hook("Stop", context)

        # Should run checks and clear modified files
        mock_run_checks.assert_called_once_with(["test.py"])
        self.assertEqual(len(monitor.modified_files), 0)

    def test_handle_stop_hook_recursion_prevention(self):
        """Test Stop hook recursion prevention"""
        monitor = TidyMonitor()
        monitor.modified_files = ["test.py"]

        context = {"stop_hook_active": True}
        response = monitor.handle_hook("Stop", context)

        # Should not run checks when stop hook is active
        self.assertIn("decision", response)
        self.assertEqual(response["decision"], "approve")
        # Modified files should not be cleared
        self.assertEqual(len(monitor.modified_files), 1)

    def test_slash_command_status(self):
        """Test status command"""
        monitor = TidyMonitor()
        monitor.project_info = {"type": "python", "package_manager": "pip"}
        monitor.detected_tools = {"linter": {"name": "ruff", "is_available": True}}

        result = monitor.handle_slash_command("status")

        self.assertIn("Status displayed", result)

    @patch("orchestra.extensions.tidy.tidy_monitor.Confirm.ask")
    @patch("orchestra.extensions.tidy.tidy_monitor.TidyMonitor._cmd_check")
    def test_slash_command_init(self, mock_check, mock_confirm):
        """Test init command"""
        monitor = TidyMonitor()

        # Mock user responses
        mock_confirm.side_effect = [
            False,
            True,
            True,
            False,
        ]  # auto_fix, strict_mode, parallel, custom_commands
        mock_check.return_value = "All checks passed!"

        result = monitor.handle_slash_command("init")

        self.assertFalse(monitor.settings["auto_fix"])
        self.assertTrue(monitor.settings["strict_mode"])
        self.assertTrue(monitor.settings["parallel_execution"])

        # Should run initial check
        mock_check.assert_called_once()

    def test_slash_command_learn(self):
        """Test learn command"""
        monitor = TidyMonitor()

        # Test adding DO example
        result = monitor.handle_slash_command("learn", "do Use type hints")
        self.assertIn("Added DO example", result)
        self.assertIn("Use type hints", monitor.do_examples)

        # Test adding DON'T example
        result = monitor.handle_slash_command("learn", "don't Use print for debugging")
        self.assertIn("Added DON'T example", result)
        self.assertIn("Use print for debugging", monitor.dont_examples)

        # Test invalid usage
        result = monitor.handle_slash_command("learn", "invalid")
        self.assertIn("Usage:", result)

    def test_config_persistence(self):
        """Test saving and loading configuration"""
        monitor = TidyMonitor()

        # Set some state
        monitor.project_info = {"type": "python", "package_manager": "pip"}
        monitor.do_examples = ["Use type hints"]
        monitor.dont_examples = ["Use print()"]
        monitor.settings["auto_fix"] = True

        # Save config
        monitor.save_config()

        # Create new monitor instance
        monitor2 = TidyMonitor()

        # Should load saved state
        self.assertEqual(monitor2.project_info["type"], "python")
        self.assertEqual(monitor2.do_examples, ["Use type hints"])
        self.assertEqual(monitor2.dont_examples, ["Use print()"])
        self.assertTrue(monitor2.settings["auto_fix"])


if __name__ == "__main__":
    unittest.main()

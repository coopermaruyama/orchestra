#!/usr/bin/env python3
"""
Tests for Tool Runners
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from orchestra.extensions.tidy.tool_runners import (
    BlackRunner,
    CustomCommandRunner,
    ESLintRunner,
    MypyRunner,
    ParallelToolRunner,
    RuffRunner,
    ToolResult,
    ToolRunnerFactory,
)


class TestToolRunners(unittest.TestCase):
    """Test the tool runners"""

    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.py"
        self.test_file.write_text("import os\n\nprint('hello')\n")

    def tearDown(self):
        """Clean up test environment"""
        shutil.rmtree(self.temp_dir)

    def test_tool_result_dataclass(self):
        """Test ToolResult dataclass"""
        result = ToolResult(
            success=True,
            output="Success",
            error="",
            issues_count=0,
            issues=[],
            exit_code=0,
            duration=1.5,
            can_fix=True,
            fixed_count=3,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.issues_count, 0)
        self.assertEqual(result.fixed_count, 3)
        self.assertEqual(result.duration, 1.5)

    @patch("subprocess.run")
    def test_ruff_runner_check(self, mock_run):
        """Test RuffRunner check method"""
        # Mock successful ruff check
        mock_run.return_value = MagicMock(
            stdout="[]", stderr="", returncode=0  # Empty JSON array means no issues
        )

        runner = RuffRunner(self.temp_dir)
        result = runner.check([str(self.test_file)])

        self.assertTrue(result.success)
        self.assertEqual(result.issues_count, 0)
        self.assertEqual(result.exit_code, 0)

        # Verify ruff was called correctly
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], "ruff")
        self.assertEqual(call_args[1], "check")
        self.assertIn("--output-format", call_args)
        self.assertIn("json", call_args)

    @patch("subprocess.run")
    def test_ruff_runner_parse_json_output(self, mock_run):
        """Test RuffRunner parsing JSON output"""
        # Mock ruff output with issues
        mock_run.return_value = MagicMock(
            stdout='[{"filename": "test.py", "location": {"row": 1, "column": 1}, "message": "Missing docstring", "code": "D100", "fix": null}]',
            stderr="",
            returncode=1,
        )

        runner = RuffRunner(self.temp_dir)
        result = runner.check()

        self.assertFalse(result.success)
        self.assertEqual(result.issues_count, 1)
        self.assertEqual(len(result.issues), 1)

        issue = result.issues[0]
        self.assertEqual(issue["file"], "test.py")
        self.assertEqual(issue["line"], 1)
        self.assertEqual(issue["column"], 1)
        self.assertEqual(issue["message"], "Missing docstring")
        self.assertEqual(issue["code"], "D100")
        self.assertFalse(issue["fixable"])

    @patch("subprocess.run")
    def test_black_runner_check(self, mock_run):
        """Test BlackRunner check method"""
        # Mock black check with formatting needed
        mock_run.return_value = MagicMock(
            stdout="", stderr="would reformat test.py\n", returncode=1
        )

        runner = BlackRunner(self.temp_dir)
        result = runner.check([str(self.test_file)])

        self.assertFalse(result.success)
        self.assertEqual(result.issues_count, 1)
        self.assertTrue(result.can_fix)

        issue = result.issues[0]
        self.assertEqual(issue["file"], "test.py")
        self.assertEqual(issue["message"], "File needs formatting")
        self.assertTrue(issue["fixable"])

    @patch("subprocess.run")
    def test_mypy_runner_check(self, mock_run):
        """Test MypyRunner check method"""
        # Mock mypy output
        mock_run.return_value = MagicMock(
            stdout='test.py:1:1: error: Module has no attribute "foo"\n',
            stderr="",
            returncode=1,
        )

        runner = MypyRunner(self.temp_dir)
        result = runner.check([str(self.test_file)])

        self.assertFalse(result.success)
        self.assertEqual(result.issues_count, 1)
        self.assertFalse(result.can_fix)  # Mypy doesn't auto-fix

        issue = result.issues[0]
        self.assertEqual(issue["file"], "test.py")
        self.assertEqual(issue["line"], 1)
        self.assertEqual(issue["column"], 1)
        self.assertEqual(issue["severity"], "error")
        self.assertIn("Module has no attribute", issue["message"])

    @patch("subprocess.run")
    def test_custom_command_runner(self, mock_run):
        """Test CustomCommandRunner"""
        # Mock custom command output
        mock_run.return_value = MagicMock(
            stdout="test.py:10:5: ERROR: Custom issue found\n", stderr="", returncode=1
        )

        runner = CustomCommandRunner(
            self.temp_dir, "npm run lint", "npm run lint:fix", "custom-lint"
        )
        result = runner.check()

        self.assertFalse(result.success)
        self.assertEqual(result.issues_count, 1)
        self.assertTrue(result.can_fix)

        # Verify command was called
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args, ["npm", "run", "lint"])

    def test_tool_runner_factory(self):
        """Test ToolRunnerFactory"""
        # Test known tool
        runner = ToolRunnerFactory.create("ruff", self.temp_dir)
        self.assertIsInstance(runner, RuffRunner)

        runner = ToolRunnerFactory.create("black", self.temp_dir)
        self.assertIsInstance(runner, BlackRunner)

        runner = ToolRunnerFactory.create("mypy", self.temp_dir)
        self.assertIsInstance(runner, MypyRunner)

        # Test unknown tool defaults to CustomCommandRunner
        runner = ToolRunnerFactory.create(
            "unknown-tool", self.temp_dir, "unknown-tool check", "unknown-tool fix"
        )
        self.assertIsInstance(runner, CustomCommandRunner)
        self.assertEqual(runner.name, "unknown-tool")

    @patch("subprocess.run")
    def test_parallel_tool_runner(self, mock_run):
        """Test ParallelToolRunner"""

        # Mock different outputs for different tools
        def side_effect(*args, **kwargs):
            cmd = args[0][0]
            if cmd == "ruff":
                return MagicMock(stdout="[]", stderr="", returncode=0)
            if cmd == "black":
                return MagicMock(
                    stdout="", stderr="would reformat test.py\n", returncode=1
                )
            return MagicMock(stdout="", stderr="", returncode=0)

        mock_run.side_effect = side_effect

        # Create runners
        ruff = RuffRunner(self.temp_dir)
        black = BlackRunner(self.temp_dir)

        # Run in parallel
        parallel = ParallelToolRunner([("ruff", ruff), ("black", black)])
        results = parallel.check_all()

        self.assertIn("ruff", results)
        self.assertIn("black", results)

        self.assertTrue(results["ruff"].success)
        self.assertFalse(results["black"].success)
        self.assertEqual(results["black"].issues_count, 1)

    @patch("subprocess.run")
    def test_tool_runner_timeout(self, mock_run):
        """Test tool runner handling timeout"""
        # Mock timeout
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 5)

        runner = RuffRunner(self.temp_dir)
        output, error, exit_code = runner._run_command(["ruff", "check"], timeout=5)

        self.assertEqual(output, "")
        self.assertIn("timed out", error)
        self.assertEqual(exit_code, -1)

    @patch("subprocess.run")
    def test_eslint_runner_json_parsing(self, mock_run):
        """Test ESLintRunner JSON parsing"""
        # Mock ESLint JSON output
        eslint_output = json.dumps(
            [
                {
                    "filePath": "/path/to/test.js",
                    "messages": [
                        {
                            "line": 10,
                            "column": 5,
                            "severity": 2,
                            "message": "Missing semicolon",
                            "ruleId": "semi",
                            "fix": {"range": [100, 100], "text": ";"},
                        }
                    ],
                }
            ]
        )

        mock_run.return_value = MagicMock(stdout=eslint_output, stderr="", returncode=1)

        runner = ESLintRunner(self.temp_dir)
        result = runner.check()

        self.assertEqual(result.issues_count, 1)
        issue = result.issues[0]
        self.assertEqual(issue["line"], 10)
        self.assertEqual(issue["column"], 5)
        self.assertEqual(issue["severity"], "error")
        self.assertEqual(issue["message"], "Missing semicolon")
        self.assertEqual(issue["code"], "semi")
        self.assertTrue(issue["fixable"])


if __name__ == "__main__":
    unittest.main()

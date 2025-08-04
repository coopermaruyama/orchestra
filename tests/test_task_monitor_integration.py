#!/usr/bin/env python3
"""
Integration tests for the task monitor system
Tests the complete workflow including task setup, progress tracking, and hook integration
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from orchestra.extensions.task.task_monitor import TaskAlignmentMonitor, TaskRequirement


class TestTaskMonitorIntegration(unittest.TestCase):
    """Test complete task monitor workflow"""

    def setUp(self) -> None:
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = os.path.join(self.temp_dir, "test-task.json")

    def tearDown(self) -> None:
        """Clean up test environment"""
        if os.path.exists(self.config_file):
            os.unlink(self.config_file)
        os.rmdir(self.temp_dir)

    def test_task_initialization(self) -> None:
        """Test that tasks can be initialized with requirements"""
        monitor = TaskAlignmentMonitor(self.config_file)

        # Initialize a task
        monitor.task = "Fix authentication bug"
        monitor.requirements = [
            TaskRequirement("1", "Reproduce the bug", 1, False),
            TaskRequirement("2", "Fix the issue", 2, False),
            TaskRequirement("3", "Add tests", 2, False),
        ]
        monitor.save_config()

        # Load a new monitor instance and verify persistence
        monitor2 = TaskAlignmentMonitor(self.config_file)

        self.assertEqual(monitor2.task, "Fix authentication bug")
        self.assertEqual(len(monitor2.requirements), 3)
        self.assertEqual(monitor2.requirements[0].description, "Reproduce the bug")
        self.assertEqual(monitor2.requirements[0].priority, 1)

    def test_progress_calculation(self) -> None:
        """Test progress calculation as requirements are completed"""
        monitor = TaskAlignmentMonitor(self.config_file)
        monitor.requirements = [
            TaskRequirement("1", "Task 1", 1, False),
            TaskRequirement("2", "Task 2", 1, False),
            TaskRequirement("3", "Task 3", 2, False),
            TaskRequirement("4", "Task 4", 2, False),
        ]

        # Initially 0% complete
        progress = monitor._get_progress()
        self.assertEqual(progress["percentage"], 0.0)
        self.assertEqual(progress["completed"], 0)
        self.assertEqual(progress["total"], 4)

        # Complete 2 requirements - should be 50%
        monitor.requirements[0].completed = True
        monitor.requirements[1].completed = True

        progress = monitor._get_progress()
        self.assertEqual(progress["percentage"], 50.0)
        self.assertEqual(progress["completed"], 2)

        # Complete all requirements - should be 100%
        monitor.requirements[2].completed = True
        monitor.requirements[3].completed = True

        progress = monitor._get_progress()
        self.assertEqual(progress["percentage"], 100.0)
        self.assertEqual(progress["completed"], 4)

    def test_current_requirement_priority(self) -> None:
        """Test that current requirement returns highest priority incomplete item"""
        monitor = TaskAlignmentMonitor(self.config_file)
        monitor.requirements = [
            TaskRequirement("1", "Low priority task", 3, False),
            TaskRequirement("2", "High priority task", 1, False),
            TaskRequirement("3", "Medium priority task", 2, False),
        ]

        # Should return highest priority (lowest number)
        current = monitor._get_current_requirement()
        self.assertEqual(current, "High priority task")

        # Complete high priority, should move to medium
        monitor.requirements[1].completed = True
        current = monitor._get_current_requirement()
        self.assertEqual(current, "Medium priority task")

        # Complete medium, should move to low
        monitor.requirements[2].completed = True
        current = monitor._get_current_requirement()
        self.assertEqual(current, "Low priority task")

        # Complete all
        monitor.requirements[0].completed = True
        current = monitor._get_current_requirement()
        self.assertEqual(current, "All complete")


class TestCommandLineInterface(unittest.TestCase):
    """Test the command line interface functionality"""

    def setUp(self) -> None:
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self) -> None:
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        # Clean up temp directory and all contents
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def get_task_monitor_path(self) -> str:
        """Get path to task monitor script"""
        return str(
            Path(__file__).parent.parent
            / "src"
            / "orchestra"
            / "extensions"
            / "task_monitor"
            / "task_monitor.py"
        )

    def test_init_command(self) -> None:
        """Test task initialization via command line"""
        script_path = self.get_task_monitor_path()

        # Run init command
        result = subprocess.run(
            [
                sys.executable,
                script_path,
                "init",
                "Test task",
                "Requirement 1",
                "Requirement 2",
                "Requirement 3",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Initialized: Test task", result.stdout)
        self.assertIn("Requirements: 3", result.stdout)

        # Verify config file was created
        config_file = os.path.join(self.temp_dir, ".claude-task.json")
        self.assertTrue(os.path.exists(config_file))

        with open(config_file) as f:
            config = json.load(f)
            self.assertEqual(config["task"], "Test task")
            self.assertEqual(len(config["requirements"]), 3)

    def test_status_command(self) -> None:
        """Test status command shows current progress"""
        script_path = self.get_task_monitor_path()

        # First initialize a task
        subprocess.run(
            [sys.executable, script_path, "init", "Test task", "Req 1", "Req 2"],
            check=False,
            capture_output=True,
        )

        # Check status
        result = subprocess.run(
            [sys.executable, script_path, "status"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Test task", result.stdout)
        self.assertIn("0% complete", result.stdout)
        self.assertIn("⏳ Req 1", result.stdout)
        self.assertIn("⏳ Req 2", result.stdout)

    def test_hook_command_json_input(self) -> None:
        """Test that Stop hook processes JSON input correctly"""
        script_path = self.get_task_monitor_path()

        # Initialize a task first with incomplete requirements
        subprocess.run(
            [
                sys.executable,
                script_path,
                "init",
                "Fix bug",
                "Debug issue",
                "Implement fix",
            ],
            check=False,
            capture_output=True,
        )

        # Test Stop hook with incomplete requirements
        hook_input = '{"session_id": "test123", "transcript_path": "/tmp/test", "hook_event_name": "Stop", "stop_hook_active": false}'
        result = subprocess.run(
            [sys.executable, script_path, "hook", "Stop"],
            check=False,
            input=hook_input,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)

        # Parse output JSON
        try:
            output = json.loads(
                result.stdout.strip().split("\n")[-1]
            )  # Last line should be JSON
            # Should block stopping when requirements are incomplete
            self.assertIn("decision", output)
            self.assertEqual(output["decision"], "block")
            self.assertIn("reason", output)
        except json.JSONDecodeError:
            self.fail("Hook output should be valid JSON")


class TestEndToEndScenarios(unittest.TestCase):
    """Test complete end-to-end scenarios"""

    def setUp(self) -> None:
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)

    def tearDown(self) -> None:
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        # Clean up temp directory and all contents
        import shutil

        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_bug_fix_workflow(self) -> None:
        """Test a complete bug fix workflow"""
        script_path = str(
            Path(__file__).parent.parent
            / "src"
            / "orchestra"
            / "extensions"
            / "task_monitor"
            / "task_monitor.py"
        )

        # 1. Initialize bug fix task
        result = subprocess.run(
            [
                sys.executable,
                script_path,
                "init",
                "Fix login timeout bug",
                "Reproduce the timeout issue",
                "Identify root cause in authentication service",
                "Implement timeout fix",
                "Add regression test for timeout handling",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)

        # 2. Check initial status
        result = subprocess.run(
            [sys.executable, script_path, "status"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertIn("0% complete", result.stdout)

        # 3. Test Stop hook with incomplete requirements - should block stopping
        hook_input = '{"session_id": "test123", "transcript_path": "/tmp/test", "hook_event_name": "Stop", "stop_hook_active": false}'
        result = subprocess.run(
            [sys.executable, script_path, "hook", "Stop"],
            check=False,
            input=hook_input,
            capture_output=True,
            text=True,
        )

        # Should block stopping since requirements are incomplete
        output_lines = result.stdout.strip().split("\n")
        json_output = json.loads(output_lines[-1])
        self.assertEqual(json_output["decision"], "block")
        self.assertIn("reason", json_output)

        # 4. Complete all requirements
        for _ in range(4):  # Complete all 4 requirements
            result = subprocess.run(
                [sys.executable, script_path, "complete"],
                check=False,
                capture_output=True,
                text=True,
            )

        # 5. Test Stop hook with completed requirements - should allow stopping
        result = subprocess.run(
            [sys.executable, script_path, "hook", "Stop"],
            check=False,
            input=hook_input,
            capture_output=True,
            text=True,
        )

        # Should allow stopping since all requirements are complete
        output_lines = result.stdout.strip().split("\n")
        json_output = json.loads(output_lines[-1])
        self.assertIsNone(json_output["decision"])


if __name__ == "__main__":
    unittest.main()

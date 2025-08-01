#!/usr/bin/env python3
"""
Test suite for enhanced deviation detection in task monitor
Based on manual testing performed during refactoring
"""

import unittest
import sys
import os
import tempfile
import json
from pathlib import Path

# Add the src/extensions directory to the path so we can import task_monitor
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "extensions" / "task-monitor"))

from task_monitor import TaskAlignmentMonitor, TaskRequirement


class TestDeviationDetection(unittest.TestCase):
    """Test the enhanced deviation detection system"""
    
    def setUp(self):
        """Set up a test task monitor with a sample task"""
        # Create a temporary config file
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        # Write empty JSON to avoid decode errors
        self.temp_file.write('{}')
        self.temp_file.close()
        
        # Initialize monitor with temp config
        self.monitor = TaskAlignmentMonitor(self.temp_file.name)
        
        # Set up a test task (mimicking the bug fix task from manual testing)
        self.monitor.task = "Fix login bug"
        self.monitor.requirements = [
            TaskRequirement("1", "Reproduce the issue", 1, False),
            TaskRequirement("2", "Identify root cause", 1, False), 
            TaskRequirement("3", "Implement fix", 2, False),
            TaskRequirement("4", "Add regression test", 2, False)
        ]
        self.monitor.stats = {'deviations': 0, 'commands': 0}
        
    def tearDown(self):
        """Clean up temporary files"""
        os.unlink(self.temp_file.name)
    
    def test_scope_creep_detection_severe(self):
        """Test that scope creep is detected for enhancement work when progress is low"""
        # This command should be blocked (severity 4+)
        command = "enhance the login UI with beautiful animations"
        deviation = self.monitor._check_deviation_with_subagents(command)
        
        self.assertIsNotNone(deviation)
        self.assertEqual(deviation['type'], 'scope_creep')
        self.assertGreaterEqual(deviation['severity'], 4)
        self.assertIn('enhance', deviation['message'].lower())
        
    def test_scope_creep_detection_warning(self):
        """Test that scope creep gives warnings for moderate cases"""
        # Complete most requirements to increase progress to 75%
        self.monitor.requirements[0].completed = True
        self.monitor.requirements[1].completed = True
        self.monitor.requirements[2].completed = True
        
        command = "refactor the login validation"
        deviation = self.monitor._check_deviation_with_subagents(command)
        
        # Should detect scope creep but with lower severity OR not detect at all at high progress
        if deviation:
            self.assertEqual(deviation['type'], 'scope_creep')
            self.assertLess(deviation['severity'], 4)  # Warning level
        # At 75% progress, minor refactoring might be allowed
        
    def test_over_engineering_detection(self):
        """Test that over-engineering patterns are detected"""
        command = "implement a factory pattern for login handlers"
        deviation = self.monitor._check_deviation_with_subagents(command)
        
        self.assertIsNotNone(deviation)
        self.assertEqual(deviation['type'], 'over_engineering')
        self.assertGreaterEqual(deviation['severity'], 4)
        self.assertIn('factory', deviation['message'].lower())
        
    def test_off_topic_detection_severe(self):
        """Test that completely off-topic commands are detected"""
        command = "update documentation for API endpoints"
        deviation = self.monitor._check_deviation_with_subagents(command)
        
        self.assertIsNotNone(deviation)
        self.assertEqual(deviation['type'], 'off_topic')
        self.assertGreaterEqual(deviation['severity'], 4)
        self.assertIn('connection', deviation['message'].lower())
        
    def test_off_topic_detection_weak_connection(self):
        """Test that weakly related commands get warnings"""
        command = "reproduce the login issue by testing different browsers"
        deviation = self.monitor._check_deviation_with_subagents(command)
        
        self.assertIsNotNone(deviation)
        self.assertEqual(deviation['type'], 'off_topic')
        self.assertEqual(deviation['severity'], 3)  # Warning level
        self.assertIn('weak', deviation['message'].lower())
        
    def test_valid_command_no_deviation(self):
        """Test that valid, on-topic commands pass through without deviation"""
        command = "reproduce the login bug consistently"
        deviation = self.monitor._check_deviation_with_subagents(command)
        
        # Should not detect any deviation for directly related work
        self.assertIsNone(deviation)
        
    def test_progress_affects_scope_creep_detection(self):
        """Test that progress percentage affects scope creep severity"""
        # Test with low progress (0%)
        command = "optimize login performance" 
        deviation_low = self.monitor._check_deviation_with_subagents(command)
        
        # Complete most requirements (75% progress)
        self.monitor.requirements[0].completed = True
        self.monitor.requirements[1].completed = True
        self.monitor.requirements[2].completed = True
        
        deviation_high = self.monitor._check_deviation_with_subagents(command)
        
        # Low progress should have higher severity than high progress
        self.assertIsNotNone(deviation_low)
        if deviation_high:  # Might not detect deviation at high progress
            self.assertGreaterEqual(deviation_low['severity'], deviation_high['severity'])


class TestSubagentSimulation(unittest.TestCase):
    """Test the subagent simulation methods"""
    
    def setUp(self):
        """Set up a test task monitor"""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        # Write empty JSON to avoid decode errors
        self.temp_file.write('{}')
        self.temp_file.close()
        
        self.monitor = TaskAlignmentMonitor(self.temp_file.name)
        self.monitor.task = "Fix login bug"
        self.monitor.requirements = [
            TaskRequirement("1", "Reproduce the issue", 1, False),
            TaskRequirement("2", "Identify root cause", 1, False)
        ]
        
    def tearDown(self):
        """Clean up temporary files"""
        os.unlink(self.temp_file.name)
        
    def test_scope_creep_simulation(self):
        """Test the scope creep subagent simulation"""
        prompt = '''
Analyze this command for scope creep:

Command: "beautify the login form"
Task: "Fix login bug"
Current Progress: 25% complete
Current Focus: Reproduce the issue
'''
        
        result = self.monitor._simulate_scope_creep_analysis(prompt)
        
        self.assertIsNotNone(result)
        self.assertTrue(result['is_deviation'])
        self.assertEqual(result['type'], 'scope_creep')
        self.assertGreater(result['severity'], 0)
        
    def test_over_engineering_simulation(self):
        """Test the over-engineering subagent simulation"""
        prompt = '''
Analyze this command for over engineering:

Command: "create abstract factory for login strategies"
Task: "Fix login bug"
'''
        
        result = self.monitor._simulate_over_engineering_analysis(prompt)
        
        self.assertIsNotNone(result)
        self.assertTrue(result['is_deviation'])
        self.assertEqual(result['type'], 'over_engineering')
        self.assertGreater(result['severity'], 0)
        
    def test_off_topic_simulation(self):
        """Test the off-topic subagent simulation"""
        prompt = '''
Analyze this command for off topic:

Command: "update shopping cart functionality"
Task: "Fix login bug"
'''
        
        result = self.monitor._simulate_off_topic_analysis(prompt)
        
        self.assertIsNotNone(result)
        self.assertTrue(result['is_deviation'])
        self.assertEqual(result['type'], 'off_topic')
        self.assertGreater(result['severity'], 0)


class TestHookIntegration(unittest.TestCase):
    """Test the hook integration with enhanced deviation detection"""
    
    def setUp(self):
        """Set up a test task monitor"""
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
        # Write empty JSON to avoid decode errors
        self.temp_file.write('{}')
        self.temp_file.close()
        
        self.monitor = TaskAlignmentMonitor(self.temp_file.name)
        self.monitor.task = "Fix login bug"
        self.monitor.requirements = [
            TaskRequirement("1", "Reproduce the issue", 1, False),
            TaskRequirement("2", "Identify root cause", 1, False)
        ]
        self.monitor.settings = {"strict_mode": True, "max_deviations": 3}
        
    def tearDown(self):
        """Clean up temporary files"""
        os.unlink(self.temp_file.name)
        
    def test_pre_tool_use_hook_blocks_severe_deviation(self):
        """Test that PreToolUse hook blocks severe deviations"""
        context = {
            "tool_name": "Bash",
            "tool_input": {"command": "enhance the login UI with beautiful animations"}
        }
        
        result = self.monitor._pre_tool_use(context)
        
        # Should return Claude Code permission denial format
        self.assertIn("hookSpecificOutput", result)
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.monitor.stats['deviations'], 1)
        
    def test_pre_tool_use_hook_warns_moderate_deviation(self):
        """Test that PreToolUse hook warns for moderate deviations"""
        # Set up a scenario that should warn but not block
        self.monitor.settings['strict_mode'] = False
        context = {
            "tool_name": "Bash", 
            "tool_input": {"command": "refactor login validation"}
        }
        
        result = self.monitor._pre_tool_use(context)
        
        # Should not block but should increment deviation count
        self.assertNotIn("hookSpecificOutput", result)
        self.assertEqual(self.monitor.stats['deviations'], 1)
        
    def test_pre_tool_use_hook_allows_valid_commands(self):
        """Test that PreToolUse hook allows valid commands"""
        context = {
            "tool_name": "Bash",
            "tool_input": {"command": "debug the login authentication flow"}
        }
        
        result = self.monitor._pre_tool_use(context)
        
        # Should not block or warn
        self.assertNotIn("hookSpecificOutput", result)
        self.assertEqual(self.monitor.stats['commands'], 1)


if __name__ == '__main__':
    unittest.main()
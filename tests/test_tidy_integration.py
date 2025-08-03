#!/usr/bin/env python3
"""
Integration tests for Tidy Extension
"""

import unittest
import tempfile
import shutil
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import subprocess

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from orchestra import Orchestra
from orchestra.extensions.tidy.tidy_monitor import TidyMonitor
from orchestra.common import HookHandler


class TestTidyIntegration(unittest.TestCase):
    """Integration tests for the tidy extension"""
    
    def setUp(self):
        """Set up test environment"""
        self.temp_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        
        # Set environment
        os.environ['CLAUDE_WORKING_DIR'] = self.temp_dir
        
        # Create project structure
        self._create_test_project()
    
    def tearDown(self):
        """Clean up test environment"""
        os.chdir(self.original_cwd)
        shutil.rmtree(self.temp_dir)
        if 'CLAUDE_WORKING_DIR' in os.environ:
            del os.environ['CLAUDE_WORKING_DIR']
    
    def _create_test_project(self):
        """Create a test Python project"""
        # Create src directory
        src_dir = Path(self.temp_dir) / "src"
        src_dir.mkdir()
        
        # Create Python files with intentional issues
        main_file = src_dir / "main.py"
        main_file.write_text("""
import os
import sys


def calculate_sum(a,b):
    return a+b

print("Result:", calculate_sum(1,2))
""")
        
        utils_file = src_dir / "utils.py"
        utils_file.write_text("""
def format_string(s: str):
    return s.upper( )

class Helper:
    def __init__(self):
        self.data = []
    
    def add_item(self, item):
        self.data.append(item)
        return
""")
        
        # Create pyproject.toml
        pyproject = Path(self.temp_dir) / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test-project"
version = "0.1.0"

[tool.black]
line-length = 88

[tool.ruff]
select = ["E", "F", "W"]
ignore = []

[tool.mypy]
python_version = "3.9"
""")
    
    def test_full_workflow_hook_integration(self):
        """Test complete workflow from file modification to hook execution"""
        monitor = TidyMonitor()
        
        # Simulate file modifications via PostToolUse hooks
        edit_context = {
            'hook_event_name': 'PostToolUse',
            'tool_name': 'Edit',
            'tool_input': {'file_path': 'src/main.py'}
        }
        
        # Track the modification
        response = monitor.handle_hook('PostToolUse', edit_context)
        self.assertIn('src/main.py', monitor.modified_files)
        
        # Simulate another file edit
        write_context = {
            'hook_event_name': 'PostToolUse',
            'tool_name': 'Write',
            'tool_input': {'file_path': 'src/new_module.py'}
        }
        
        response = monitor.handle_hook('PostToolUse', write_context)
        self.assertEqual(len(monitor.modified_files), 2)
        
        # Simulate Stop hook (when Claude finishes)
        stop_context = {
            'hook_event_name': 'Stop',
            'stop_hook_active': False
        }
        
        # This should trigger checks
        with patch('orchestra.extensions.tidy.tool_runners.subprocess.run') as mock_run:
            # Mock tool outputs
            mock_run.return_value = MagicMock(
                stdout='[{"filename": "src/main.py", "location": {"row": 5, "column": 20}, "message": "Missing whitespace after comma", "code": "E231"}]',
                stderr='',
                returncode=1
            )
            
            response = monitor.handle_hook('Stop', stop_context)
        
        # Should get a block response with issues
        self.assertEqual(response.get('decision'), 'block')
        self.assertIn('fix the code quality issues', response.get('reason', ''))
        
        # Modified files should be cleared
        self.assertEqual(len(monitor.modified_files), 0)
    
    @patch('subprocess.run')
    def test_auto_detect_and_run_tools(self, mock_run):
        """Test automatic detection and running of available tools"""
        # Mock tool availability checks
        def mock_tool_check(cmd, *args, **kwargs):
            if cmd[0] == 'ruff' and '--version' in cmd:
                return MagicMock(stdout='ruff 0.1.0', stderr='', returncode=0)
            elif cmd[0] == 'black' and '--version' in cmd:
                return MagicMock(stdout='black, 23.0.0', stderr='', returncode=0)
            elif cmd[0] == 'mypy' and '--version' in cmd:
                return MagicMock(stdout='mypy 1.0.0', stderr='', returncode=0)
            else:
                return MagicMock(stdout='', stderr='', returncode=1)
        
        mock_run.side_effect = mock_tool_check
        
        monitor = TidyMonitor()
        
        # Should auto-detect Python project and tools
        self.assertEqual(monitor.project_info['type'], 'python')
        
        # Note: In real scenario, tool detection would check actual executables
        # For this test, we're mocking the detection
    
    def test_slash_command_workflow(self):
        """Test slash command workflow"""
        monitor = TidyMonitor()
        
        # Test init command
        with patch('orchestra.extensions.tidy.tidy_monitor.Confirm.ask') as mock_confirm:
            with patch('orchestra.extensions.tidy.tidy_monitor.TidyMonitor._run_checks') as mock_checks:
                mock_confirm.side_effect = [True, True, True, False]  # auto_fix, strict, parallel, custom
                mock_checks.return_value = {}
                
                result = monitor.handle_slash_command('init')
                
                self.assertTrue(monitor.settings['auto_fix'])
                self.assertTrue(monitor.settings['strict_mode'])
        
        # Test learn command
        result = monitor.handle_slash_command('learn', 'do Use descriptive variable names')
        self.assertIn('Use descriptive variable names', monitor.do_examples)
        
        result = monitor.handle_slash_command('learn', "don't Use single letter variables")
        self.assertIn('Use single letter variables', monitor.dont_examples)
        
        # Test status command
        result = monitor.handle_slash_command('status')
        self.assertIn('Status displayed', result)
    
    def test_parallel_tool_execution(self):
        """Test parallel execution of multiple tools"""
        monitor = TidyMonitor()
        
        # Configure multiple tools
        monitor.detected_tools = {
            'linter': {'name': 'ruff', 'command': 'ruff check .', 'is_available': True},
            'formatter': {'name': 'black', 'command': 'black . --check', 'is_available': True},
            'type_checker': {'name': 'mypy', 'command': 'mypy src/', 'is_available': True}
        }
        
        with patch('orchestra.extensions.tidy.tool_runners.subprocess.run') as mock_run:
            # Different outputs for different tools
            def side_effect(cmd, *args, **kwargs):
                if 'ruff' in cmd:
                    return MagicMock(stdout='[]', stderr='', returncode=0)
                elif 'black' in cmd:
                    return MagicMock(stdout='', stderr='would reformat src/main.py', returncode=1)
                elif 'mypy' in cmd:
                    return MagicMock(stdout='src/main.py:5: error: Missing type annotation', stderr='', returncode=1)
                return MagicMock(stdout='', stderr='', returncode=0)
            
            mock_run.side_effect = side_effect
            
            # Run checks
            results = monitor._run_checks(['src/main.py'])
            
            # Should have results for all tools
            self.assertEqual(len(results), 3)
            self.assertIn('linter', results)
            self.assertIn('formatter', results)
            self.assertIn('type_checker', results)
            
            # Check individual results
            self.assertTrue(results['linter'].success)
            self.assertFalse(results['formatter'].success)
            self.assertFalse(results['type_checker'].success)
    
    def test_config_file_persistence(self):
        """Test configuration file handling"""
        monitor1 = TidyMonitor()
        
        # Configure the monitor
        monitor1.do_examples = ['Use type hints', 'Write docstrings']
        monitor1.dont_examples = ['Use global variables']
        monitor1.settings['auto_fix'] = True
        monitor1.custom_commands = [{
            'name': 'custom-check',
            'command': 'make lint',
            'fix_command': 'make format'
        }]
        
        # Save configuration
        monitor1.save_config()
        
        # Verify config file exists
        config_path = Path(self.temp_dir) / '.claude' / 'orchestra' / 'tidy.json'
        self.assertTrue(config_path.exists())
        
        # Load config in new instance
        monitor2 = TidyMonitor()
        
        # Should have loaded saved configuration
        self.assertEqual(monitor2.do_examples, ['Use type hints', 'Write docstrings'])
        self.assertEqual(monitor2.dont_examples, ['Use global variables'])
        self.assertTrue(monitor2.settings['auto_fix'])
        self.assertEqual(len(monitor2.custom_commands), 1)
        self.assertEqual(monitor2.custom_commands[0]['name'], 'custom-check')
    
    def test_subagent_stop_hook(self):
        """Test SubagentStop hook handling"""
        monitor = TidyMonitor()
        
        # Track a file modification
        monitor.modified_files = ['src/utils.py']
        
        # Simulate SubagentStop hook
        context = {
            'hook_event_name': 'SubagentStop'
        }
        
        with patch('orchestra.extensions.tidy.tool_runners.subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                stdout='[]',  # No issues
                stderr='',
                returncode=0
            )
            
            response = monitor.handle_hook('SubagentStop', context)
        
        # For subagent, should continue and show output
        self.assertTrue(response.get('continue', False))
        self.assertEqual(len(monitor.modified_files), 0)
    
    def test_ignore_patterns(self):
        """Test file ignore patterns"""
        monitor = TidyMonitor()
        
        # Test various file patterns
        test_cases = [
            ('test_module.py', True),     # Test files ignored
            ('migrations/0001.py', True),  # Migrations ignored  
            ('node_modules/pkg.js', True), # node_modules ignored
            ('script.min.js', True),       # Minified files ignored
            ('src/main.py', False),        # Regular source files not ignored
            ('utils.js', False),           # Regular JS files not ignored
        ]
        
        for file_path, should_ignore in test_cases:
            result = monitor._should_ignore_file(file_path)
            self.assertEqual(result, should_ignore, f"Failed for {file_path}")
    
    def test_pre_compact_hook(self):
        """Test PreCompact hook saves state"""
        monitor = TidyMonitor()
        
        # Set some state
        monitor.last_check = {
            'timestamp': '2024-01-01T00:00:00',
            'results': {'linter': {'issues_count': 5}}
        }
        
        # Handle PreCompact
        context = {
            'hook_event_name': 'PreCompact',
            'trigger': 'manual'
        }
        
        response = monitor.handle_hook('PreCompact', context)
        
        # Should save config
        config_path = Path(self.temp_dir) / '.claude' / 'orchestra' / 'tidy.json'
        self.assertTrue(config_path.exists())
        
        # Verify saved data
        with open(config_path) as f:
            saved_config = json.load(f)
        
        self.assertEqual(saved_config['last_check']['timestamp'], '2024-01-01T00:00:00')


if __name__ == "__main__":
    unittest.main()
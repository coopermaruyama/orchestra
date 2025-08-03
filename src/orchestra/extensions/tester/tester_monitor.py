#!/usr/bin/env python3
"""
Tester Monitor for Claude Code
Automatically tests completed tasks using calibrated testing methods
"""

import json
import sys
import os
import logging
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Import from common library
from orchestra.common import GitAwareExtension, HookHandler
from orchestra.common.types import HookInput


@dataclass
class TestCalibration:
    """Test calibration configuration"""
    test_commands: List[str] = field(default_factory=list)
    test_file_patterns: List[str] = field(default_factory=list)
    browser_test_enabled: bool = False
    browser_test_steps: List[str] = field(default_factory=list)
    example_test_path: Optional[str] = None
    framework: Optional[str] = None
    calibrated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'test_commands': self.test_commands,
            'test_file_patterns': self.test_file_patterns,
            'browser_test_enabled': self.browser_test_enabled,
            'browser_test_steps': self.browser_test_steps,
            'example_test_path': self.example_test_path,
            'framework': self.framework,
            'calibrated_at': self.calibrated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TestCalibration':
        return cls(**data)


@dataclass
class TestResult:
    """Test execution result"""
    task_id: str
    task_description: str
    test_type: str  # 'unit', 'browser', 'both'
    success: bool
    output: str
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'task_id': self.task_id,
            'task_description': self.task_description,
            'test_type': self.test_type,
            'success': self.success,
            'output': self.output,
            'timestamp': self.timestamp
        }


class TesterMonitor(GitAwareExtension):
    def __init__(self, config_path: Optional[str] = None) -> None:
        # Use CLAUDE_WORKING_DIR if available, otherwise use TMPDIR
        working_dir = os.environ.get('CLAUDE_WORKING_DIR')
        if working_dir:
            log_dir = os.path.join(working_dir, '.claude', 'logs')
        else:
            # Fallback to system temp directory
            import tempfile
            temp_dir = os.environ.get('TMPDIR', tempfile.gettempdir())
            log_dir = os.path.join(temp_dir, 'claude-tester')
        
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'tester_monitor.log')
        
        # Configure logger
        self.logger = logging.getLogger('tester_monitor')
        self.logger.setLevel(logging.DEBUG)
        
        # Only add handler if logger doesn't already have handlers
        if not self.logger.handlers:
            # File handler with rotation
            file_handler = logging.FileHandler(log_file, mode='a')
            file_handler.setLevel(logging.DEBUG)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
            )
            file_handler.setFormatter(formatter)
            
            # Add handler to logger
            self.logger.addHandler(file_handler)
        
        self.logger.info("TesterMonitor initialized")
        
        # Initialize base class
        base_working_dir = working_dir or '.'
        super().__init__(
            config_file=config_path,
            working_dir=base_working_dir
        )
        
        # Tester specific state
        self.calibration: Optional[TestCalibration] = None
        self.test_results: List[TestResult] = []
        self.synced_todos: List[Dict[str, Any]] = []
        self.load_config()
    
    def get_default_config_filename(self) -> str:
        """Get the default configuration file name for this extension"""
        return 'tester.json'
    
    def get_memory_dir(self) -> Path:
        """Get the memory directory for storing calibration data"""
        memory_dir = Path(self.working_dir) / '.claude' / 'orchestra' / 'tester'
        memory_dir.mkdir(parents=True, exist_ok=True)
        return memory_dir
    
    def save_calibration_memory(self, calibration_data: Dict[str, Any]) -> None:
        """Save calibration data to memory file"""
        memory_file = self.get_memory_dir() / 'calibration.json'
        with open(memory_file, 'w') as f:
            json.dump(calibration_data, f, indent=2)
        self.logger.info(f"Saved calibration to {memory_file}")
    
    def load_calibration_memory(self) -> Optional[Dict[str, Any]]:
        """Load calibration data from memory file"""
        memory_file = self.get_memory_dir() / 'calibration.json'
        if memory_file.exists():
            with open(memory_file, 'r') as f:
                return json.load(f)
        return None
    
    def save_test_result(self, result: TestResult) -> None:
        """Save test result to memory"""
        results_dir = self.get_memory_dir() / 'results'
        results_dir.mkdir(exist_ok=True)
        
        # Save with timestamp filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        result_file = results_dir / f'{timestamp}_{result.task_id}.json'
        
        with open(result_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)
        
        self.logger.info(f"Saved test result to {result_file}")
    
    def load_config(self) -> Dict[str, Any]:
        """Load or create configuration"""
        config = super().load_config()
        
        # Load calibration from memory file first, fallback to config
        memory_calibration = self.load_calibration_memory()
        if memory_calibration:
            self.calibration = TestCalibration.from_dict(memory_calibration)
            self.logger.info("Loaded calibration from memory file")
        elif 'calibration' in config:
            self.calibration = TestCalibration.from_dict(config['calibration'])
            # Migrate to memory file
            self.save_calibration_memory(config['calibration'])
            self.logger.info("Migrated calibration to memory file")
        
        # Load test results
        self.test_results = [
            TestResult(**result) for result in config.get('test_results', [])
        ]
        
        # Load synced todos
        self.synced_todos = config.get('synced_todos', [])
        
        return config
    
    def save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save configuration"""
        if config is None:
            config = {
                'calibration': self.calibration.to_dict() if self.calibration else None,
                'test_results': [r.to_dict() for r in self.test_results],
                'synced_todos': self.synced_todos,
                'updated': datetime.now().isoformat()
            }
        
        super().save_config(config)
    
    def handle_hook(self, hook_type: str, context: HookInput) -> Dict[str, Any]:
        """Universal hook handler"""
        self.logger.info(f"Handling hook: {hook_type}")
        self.logger.debug(f"Hook context: {json.dumps(context, indent=2)}")
        
        if hook_type == "PostToolUse":
            return self._handle_post_tool_use_hook(context)
        
        return context
    
    def _handle_post_tool_use_hook(self, context: HookInput) -> Dict[str, Any]:
        """Handle PostToolUse hook to detect completed todos"""
        tool_name = context.get('tool_name', 'unknown')
        
        if tool_name == 'TodoWrite':
            tool_input = context.get('tool_input', {})
            todos = tool_input.get('todos', [])
            
            # Check for newly completed todos
            for todo in todos:
                if todo.get('status') == 'completed':
                    todo_id = todo.get('id')
                    # Check if this todo was previously not completed
                    was_completed = False
                    for old_todo in self.synced_todos:
                        if old_todo.get('id') == todo_id and old_todo.get('status') == 'completed':
                            was_completed = True
                            break
                    
                    if not was_completed:
                        self.logger.info(f"Todo completed: {todo.get('content')}")
                        # Trigger test run for this completed todo
                        self._queue_test_for_todo(todo)
            
            # Update synced todos
            self.synced_todos = todos
            self.save_config()
        
        return HookHandler.create_allow_response()
    
    def _queue_test_for_todo(self, todo: Dict[str, Any]) -> None:
        """Queue a test run for a completed todo"""
        if not self.calibration:
            self.logger.warning("Cannot run tests - not calibrated yet")
            return
        
        self.logger.info(f"Queueing test for todo: {todo.get('content')}")
        # In a full implementation, this would trigger the test-runner subagent
        # For now, we'll just log it
    
    def calibrate(self) -> None:
        """Run interactive calibration"""
        print("🧪 Tester Calibration")
        print("\nThis will help me learn how to test your project.")
        print("I'll use the test-calibrator subagent to have a conversation with you.\n")
        
        # Invoke the test-calibrator subagent
        if hasattr(self, 'invoke_subagent'):
            result = self.invoke_subagent(
                subagent_type='test-calibrator',
                analysis_context='Help the user set up automated testing for their project by learning about their testing frameworks, commands, and patterns.',
                create_branch=False
            )
            
            # Save calibration results to memory
            # The calibrator should have saved to .claude/orchestra/tester/calibration.json
            memory_calibration = self.load_calibration_memory()
            if memory_calibration:
                self.calibration = TestCalibration.from_dict(memory_calibration)
                self.calibration.calibrated_at = datetime.now().isoformat()
                # Save updated calibration back to memory
                self.save_calibration_memory(self.calibration.to_dict())
                self.save_config()
                print("✅ Calibration complete!")
            else:
                print("⚠️  Calibration incomplete. The calibrator should save to .claude/orchestra/tester/calibration.json")
        else:
            # Fallback for testing
            self.calibration = TestCalibration(
                calibrated_at=datetime.now().isoformat()
            )
            self.save_config()
            print("✅ Basic calibration saved.")
    
    def run_tests(self, task_id: Optional[str] = None) -> None:
        """Run tests for a specific task or all completed tasks"""
        if not self.calibration:
            print("❌ Not calibrated yet. Run '/tester calibrate' first.")
            return
        
        print("🧪 Running tests...")
        
        # Build context for test runner
        context = f"""Run tests based on calibration stored in .claude/orchestra/tester/calibration.json:
        Commands: {self.calibration.test_commands}
        Patterns: {self.calibration.test_file_patterns}
        Browser testing: {self.calibration.browser_test_enabled}
        Framework: {self.calibration.framework}
        Example test: {self.calibration.example_test_path}
        """
        
        if task_id:
            # Find the specific todo
            todo = next((t for t in self.synced_todos if t.get('id') == task_id), None)
            if todo:
                context += f"\nTest for completed task: {todo.get('content')}"
        else:
            # Test all recently completed todos
            completed = [t for t in self.synced_todos if t.get('status') == 'completed']
            if completed:
                context += f"\nTest {len(completed)} completed tasks"
        
        # Invoke the test-runner subagent
        if hasattr(self, 'invoke_subagent'):
            result = self.invoke_subagent(
                subagent_type='test-runner',
                analysis_context=context,
                create_branch=False
            )
            
            # Store test results
            # The test runner should save results to .claude/orchestra/tester/results/
            # Let's check for the latest result
            results_dir = self.get_memory_dir() / 'results'
            if results_dir.exists():
                result_files = sorted(results_dir.glob('*.json'), key=lambda x: x.stat().st_mtime)
                if result_files:
                    latest_result = result_files[-1]
                    with open(latest_result, 'r') as f:
                        result_data = json.load(f)
                    
                    test_result = TestResult(**result_data)
                    self.test_results.append(test_result)
                    self.save_config()
                    
                    if test_result.success:
                        print(f"✅ Tests passed!")
                    else:
                        print(f"❌ Tests failed. Check {latest_result} for details.")
                else:
                    print("⚠️  No test results found. Check the test runner output.")
        else:
            print("✅ Test run initiated (in demo mode).")
    
    def show_status(self) -> None:
        """Show calibration and test status"""
        print("🧪 Tester Status")
        
        if self.calibration:
            print(f"\n✅ Calibrated at: {self.calibration.calibrated_at}")
            if self.calibration.framework:
                print(f"   Framework: {self.calibration.framework}")
            if self.calibration.test_commands:
                print(f"   Test commands: {', '.join(self.calibration.test_commands)}")
            if self.calibration.browser_test_enabled:
                print("   Browser testing: Enabled")
            print(f"   Memory location: {self.get_memory_dir()}")
        else:
            print("\n❌ Not calibrated yet")
            print("   Run '/tester calibrate' to set up testing")
        
        if self.test_results:
            print(f"\n📊 Test Results ({len(self.test_results)} runs):")
            for result in self.test_results[-5:]:  # Show last 5
                status = "✅" if result.success else "❌"
                print(f"   {status} {result.task_description[:50]}... ({result.timestamp})")
        else:
            print("\n📊 No test results yet")


def main() -> None:
    """CLI interface and hook handler"""
    if len(sys.argv) < 2:
        print("Claude Code Tester")
        print("Usage: tester_monitor.py <command> [args]")
        print("\nCommands:")
        print("  init        - Initialize tester")
        print("  calibrate   - Run interactive calibration")
        print("  test        - Run tests for completed tasks")
        print("  status      - Show calibration and test status")
        print("  hook <type> - Handle Claude Code hook")
        return
    
    monitor = TesterMonitor()
    command = sys.argv[1]
    
    if command == "init":
        print("🧪 Tester Initialized")
        print("\n💡 Next steps:")
        print("   1. Run '/tester calibrate' to set up testing for your project")
        print("   2. Complete tasks and tests will run automatically")
        print("   3. Use '/tester status' to see test results")
        
    elif command == "calibrate":
        monitor.calibrate()
        
    elif command == "test":
        task_id = sys.argv[2] if len(sys.argv) > 2 else None
        monitor.run_tests(task_id)
        
    elif command == "status":
        monitor.show_status()
        
    elif command == "hook":
        if len(sys.argv) < 3:
            return
        
        hook_type = sys.argv[2]
        
        # Read context from stdin using HookHandler
        context = HookHandler.read_hook_input()
        
        # Handle the hook
        result = monitor.handle_hook(hook_type, context)
        
        # Output result for Claude Code using HookHandler
        HookHandler.write_hook_output(result)
        
    elif command == "slash-command":
        # Output slash command configuration for Claude Code
        slash_config = {
            "commands": {
                "/tester": {
                    "description": "Automated testing for completed tasks",
                    "subcommands": {
                        "init": {
                            "description": "Initialize the tester",
                            "command": f"python {os.path.abspath(__file__)} init"
                        },
                        "calibrate": {
                            "description": "Set up testing for your project",
                            "command": f"python {os.path.abspath(__file__)} calibrate"
                        },
                        "test": {
                            "description": "Run tests for completed tasks",
                            "command": f"python {os.path.abspath(__file__)} test"
                        },
                        "status": {
                            "description": "Show calibration and test results",
                            "command": f"python {os.path.abspath(__file__)} status"
                        }
                    }
                }
            }
        }
        print(json.dumps(slash_config, indent=2))


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Task Alignment Monitor for Claude Code
Direct integration with Claude Code hooks - no extra scripts needed
"""

import json
import sys
import os
import logging
from typing import Dict, Optional, Any, List
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

# Import from common library
from orchestra.common import GitAwareExtension, TaskRequirement, HookHandler


class TaskAlignmentMonitor(GitAwareExtension):
    def __init__(self, config_path: Optional[str] = None) -> None:
        # Use CLAUDE_WORKING_DIR if available, otherwise current directory
        working_dir = os.environ.get('CLAUDE_WORKING_DIR', '.')
        
        # Set up logging
        log_dir = os.path.join(working_dir, '.claude', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'task_monitor.log')
        
        # Configure logger
        self.logger = logging.getLogger('task_monitor')
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
        
        self.logger.info("TaskAlignmentMonitor initialized")
        
        # Initialize base class
        super().__init__(
            config_file=config_path or os.path.join(working_dir, '.claude-task.json'),
            working_dir=working_dir
        )
        
        # Task monitor specific state
        self.task: str = ""
        self.requirements: List[TaskRequirement] = []
        self.settings: Dict[str, Any] = {}
        self.stats: Dict[str, int] = {}
        self.load_config()
        
        # Load or create git task state if in git repo
        if self.git_manager._is_git_repo():
            self.load_task_state_from_config()
    
    def get_default_config_filename(self) -> str:
        """Get the default configuration file name for this extension"""
        return '.claude-task.json'

    def load_config(self) -> Dict[str, Any]:
        """Load or create configuration"""
        config = super().load_config()
        
        self.task = config.get('task', '')
        self.requirements = [TaskRequirement.from_dict(req) for req in config.get('requirements', [])]
        self.settings = config.get('settings', {"strict_mode": True, "max_deviations": 3})
        self.stats = config.get('stats', {'deviations': 0, 'commands': 0})
        
        return config

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save configuration and progress"""
        if config is None:
            config = {
                'task': self.task,
                'requirements': [req.to_dict() for req in self.requirements],
                'settings': self.settings,
                'stats': self.stats,
                'updated': datetime.now().isoformat()
            }
            
            # Include git task state if available
            if self.current_task_state:
                config['git_task_state'] = self.current_task_state.to_dict()
        
        super().save_config(config)

    def handle_hook(self, hook_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Universal hook handler - handles Stop and SubagentStop hooks"""
        self.logger.info(f"Handling hook: {hook_type}")
        self.logger.debug(f"Hook context: {json.dumps(context, indent=2)}")
        
        if hook_type == "Stop":
            return self._handle_stop_hook(context)
        elif hook_type == "SubagentStop":
            return self._handle_subagent_stop_hook(context)
        elif hook_type == "TodoWrite":
            return self._handle_todowrite_hook(context)
        elif hook_type == "Task":
            return self._handle_task_hook(context)
        elif hook_type == "PreToolUse":
            return self._handle_pre_tool_use_hook(context)
        elif hook_type == "PostToolUse":
            return self._handle_post_tool_use_hook(context)
        
        return context
    
    def _handle_stop_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Stop hook by analyzing conversation and determining if Claude should continue"""
        self.logger.debug(f"_handle_stop_hook called with context keys: {list(context.keys())}")
        
        # Skip if no task configured
        if not self.task:
            self.logger.debug("No task configured, returning allow response")
            return HookHandler.create_allow_response()
            
        # Avoid infinite recursion - if stop_hook_active is True, we're already processing
        if HookHandler.is_stop_hook_active(context):
            self.logger.debug("Stop hook already active, avoiding recursion")
            return HookHandler.create_allow_response()
        
        try:
            # Update current task state with latest git info
            if self.current_task_state:
                self.logger.debug(f"Current task state exists: {self.current_task_state.branch_name}")
                self.update_task_state()
                self.logger.debug("Task state updated")
            else:
                self.logger.debug("No current task state")
            
            # Build analysis context for subagents
            analysis_context = self._build_analysis_context()
            self.logger.debug(f"Built analysis context (length: {len(analysis_context)} chars)")
            
            if self.current_task_state and self.git_manager._is_git_repo():
                self.logger.debug("Using git-aware subagent analysis")
                # Use git-aware subagent analysis
                return self._analyze_with_git_subagents(analysis_context)
            else:
                self.logger.debug("Using traditional external Claude analysis")
                # Use traditional external Claude analysis
                return self._analyze_with_external_claude(analysis_context)
                
        except Exception as e:
            self.logger.error(f"Stop hook analysis failed with exception: {type(e).__name__}: {e}")
            import traceback
            self.logger.error(f"Traceback:\n{traceback.format_exc()}")
            return self._fallback_analysis()
    
    def _handle_subagent_stop_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle SubagentStop hook by parsing subagent results"""
        self.logger.debug(f"_handle_subagent_stop_hook called with context keys: {list(context.keys())}")
        
        try:
            # Get transcript path from context
            transcript_path = context.get('transcript_path')
            if not transcript_path:
                self.logger.error("No transcript_path in SubagentStop context")
                return HookHandler.create_allow_response()
            
            self.logger.debug(f"Reading transcript from: {transcript_path}")
            
            # Read the transcript file
            with open(transcript_path, 'r') as f:
                transcript_content = f.read()
            
            # Parse the tail of the transcript to get subagent response
            # Look for the last assistant message which should contain the analysis
            lines = transcript_content.strip().split('\n')
            
            # Find the last assistant response
            assistant_response = ""
            in_assistant_block = False
            for line in reversed(lines):
                if line.strip().startswith('assistant:'):
                    in_assistant_block = True
                elif line.strip().startswith('user:') and in_assistant_block:
                    break
                elif in_assistant_block:
                    assistant_response = line + '\n' + assistant_response
            
            self.logger.debug(f"Parsed assistant response length: {len(assistant_response)}")
            
            # Analyze the subagent response
            response_lower = assistant_response.lower()
            
            # Check for indicators that we should continue working
            continue_indicators = [
                'should continue',
                'keep working',
                'not complete',
                'incomplete',
                'more work needed',
                'requirements remaining',
                'next step',
                'focus on'
            ]
            
            # Check for indicators that we can stop
            stop_indicators = [
                'can stop',
                'task complete',
                'all requirements met',
                'finished',
                'done',
                'no more work'
            ]
            
            should_continue = any(indicator in response_lower for indicator in continue_indicators)
            should_stop = any(indicator in response_lower for indicator in stop_indicators)
            
            self.logger.debug(f"Continue indicators found: {should_continue}, Stop indicators found: {should_stop}")
            
            # If we have clear indication to continue
            if should_continue and not should_stop:
                # Extract focus area if mentioned
                focus_area = ""
                for line in assistant_response.split('\n'):
                    if 'focus on' in line.lower() or 'next:' in line.lower():
                        focus_area = line.strip()
                        break
                
                reason = "Task analysis indicates more work is needed"
                if focus_area:
                    reason += f". {focus_area}"
                
                self.logger.info(f"Blocking based on subagent analysis: {reason}")
                return HookHandler.create_block_response(reason)
            
            # Otherwise allow stopping
            self.logger.info("Allowing stop based on subagent analysis")
            return HookHandler.create_allow_response()
            
        except Exception as e:
            self.logger.error(f"Error in SubagentStop hook: {e}")
            import traceback
            self.logger.error(f"Traceback:\n{traceback.format_exc()}")
            # On error, fall back to allowing stop
            return HookHandler.create_allow_response()
    
    def _handle_todowrite_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle TodoWrite hook by logging the todo changes"""
        self.logger.info("TodoWrite hook triggered")
        
        try:
            # Log the tool input containing the todos
            tool_input = context.get('tool_input', {})
            todos = tool_input.get('todos', [])
            
            self.logger.info(f"TodoWrite: {len(todos)} todos")
            for todo in todos:
                self.logger.debug(f"Todo: {todo}")
            
            # Allow the tool to proceed
            return HookHandler.create_allow_response()
            
        except Exception as e:
            self.logger.error(f"Error in TodoWrite hook: {e}")
            return HookHandler.create_allow_response()
    
    def _handle_task_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Task hook by logging the subagent task"""
        self.logger.info("Task hook triggered")
        
        try:
            # Log the task details
            tool_input = context.get('tool_input', {})
            subagent_type = tool_input.get('subagent_type', 'unknown')
            description = tool_input.get('description', '')
            prompt = tool_input.get('prompt', '')
            
            self.logger.info(f"Task subagent: {subagent_type}")
            self.logger.info(f"Task description: {description}")
            self.logger.debug(f"Task prompt: {prompt[:200]}...")
            
            # Allow the tool to proceed
            return HookHandler.create_allow_response()
            
        except Exception as e:
            self.logger.error(f"Error in Task hook: {e}")
            return HookHandler.create_allow_response()
    
    def _handle_pre_tool_use_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle PreToolUse hook by logging the tool about to be used"""
        tool_name = context.get('tool_name', 'unknown')
        self.logger.info(f"PreToolUse hook: {tool_name}")
        
        try:
            # Log the tool input
            tool_input = context.get('tool_input', {})
            self.logger.debug(f"Tool input: {json.dumps(tool_input, indent=2)}")
            
            # Allow the tool to proceed
            return HookHandler.create_allow_response()
            
        except Exception as e:
            self.logger.error(f"Error in PreToolUse hook: {e}")
            return HookHandler.create_allow_response()
    
    def _handle_post_tool_use_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle PostToolUse hook by logging the tool result"""
        tool_name = context.get('tool_name', 'unknown')
        self.logger.info(f"PostToolUse hook: {tool_name}")
        
        try:
            # Log the tool response
            tool_response = context.get('tool_response', {})
            self.logger.debug(f"Tool response: {json.dumps(tool_response, indent=2)}")
            
            # Allow the tool to proceed
            return HookHandler.create_allow_response()
            
        except Exception as e:
            self.logger.error(f"Error in PostToolUse hook: {e}")
            return HookHandler.create_allow_response()
    
    def _build_analysis_context(self) -> str:
        """Build analysis context for subagents"""
        progress = self._get_progress()
        
        context = f"""Current Task: {self.task}

Requirements Status:
"""
        for req in self.requirements:
            status = "✅ COMPLETED" if req.completed else "❌ INCOMPLETE"
            context += f"- {status}: {req.description} (Priority {req.priority})\n"
        
        context += f"""
Current Progress: {progress['percentage']:.0f}% complete ({progress['completed']}/{progress['total']} requirements)

Session Statistics:
- Commands executed: {self.stats.get('commands', 0)}
- Deviations detected: {self.stats.get('deviations', 0)}

Analysis Instructions:
Please determine if the developer should continue working or if they can stop. Consider:
1. Are all core requirements (Priority 1-2) completed?
2. Is the main task objective achieved?
3. Are there any signs of scope creep or over-engineering?
4. Is the developer staying focused on the core task?
"""
        return context
    
    def _analyze_with_git_subagents(self, analysis_context: str) -> Dict[str, Any]:
        """Analyze using git-aware subagents"""
        self.logger.debug("Starting git-aware subagent analysis")
        
        # Save analysis context for later use in SubagentStop hook
        self.pending_analysis_context = analysis_context
        
        # Return a block response that will trigger Claude to run subagents
        subagent_types = ['scope-creep-detector', 'over-engineering-detector', 'off-topic-detector']
        self.logger.debug(f"Requesting subagent analysis with: {subagent_types}")
        
        # Create a prompt that will trigger subagent analysis
        subagent_prompt = f"""Analyze the current task progress using the scope-creep-detector, over-engineering-detector, and off-topic-detector subagents.

{analysis_context}

Use these subagents to determine:
1. Is there any scope creep happening?
2. Is the developer over-engineering the solution?
3. Are they working on off-topic tasks?
4. Should Claude continue working or stop?"""
        
        self.logger.info("Blocking to trigger subagent analysis")
        return HookHandler.create_block_response(subagent_prompt)
    
    def _analyze_with_external_claude(self, analysis_context: str) -> Dict[str, Any]:
        """Analyze using external Claude instance"""
        import subprocess
        import json
        import re
        
        analysis_prompt = f"""{analysis_context}

Use the scope-creep-detector, over-engineering-detector, and off-topic-detector subagents to analyze if the developer is staying focused on the core task.

Respond with JSON in this exact format:
{{
    "should_continue": true/false,
    "reason": "Brief explanation of why Claude should continue or can stop",
    "focus_area": "What the developer should work on next (if continuing)"
}}
"""
        
        try:
            self.logger.debug("Calling external Claude with analysis prompt")
            # Call external Claude with the analysis prompt
            result = subprocess.run([
                'claude', '-p', analysis_prompt
            ], capture_output=True, text=True, timeout=30)
            
            self.logger.debug(f"External Claude return code: {result.returncode}")
            self.logger.debug(f"External Claude stdout length: {len(result.stdout) if result.stdout else 0}")
            
            if result.returncode == 0 and result.stdout.strip():
                # Parse JSON response from Claude
                json_match = re.search(r'\{.*\}', result.stdout, re.DOTALL)
                if json_match:
                    response = json.loads(json_match.group())
                    self.logger.debug(f"Parsed response: {response}")
                    
                    if response.get('should_continue', False):
                        # Block stopping - Claude should continue
                        reason = response.get('reason', 'Task not complete')
                        focus_area = response.get('focus_area', '')
                        
                        full_reason = reason
                        if focus_area:
                            full_reason += f" Focus on: {focus_area}"
                        
                        self.logger.info(f"Blocking stop with reason: {full_reason}")
                        return HookHandler.create_block_response(full_reason)
                    else:
                        # Allow stopping - task is complete
                        self.logger.info("Allowing stop - task complete")
                        return HookHandler.create_allow_response()
                else:
                    self.logger.warning("No JSON found in external Claude response")
                        
        except subprocess.TimeoutExpired as e:
            self.logger.error(f"External Claude timed out: {e}")
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse JSON from external Claude: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in external Claude analysis: {e}")
        
        self.logger.debug("Falling back to fallback analysis")
        return self._fallback_analysis()
    
    def _fallback_analysis(self) -> Dict[str, Any]:
        """Fallback analysis based on completion status"""
        self.logger.debug("Running fallback analysis")
        incomplete_core = [r for r in self.requirements if not r.completed and r.priority <= 2]
        self.logger.debug(f"Found {len(incomplete_core)} incomplete core requirements")
        
        if incomplete_core:
            next_requirement = min(incomplete_core, key=lambda x: x.priority)
            self.logger.info(f"Blocking stop - core requirement incomplete: {next_requirement.description}")
            return HookHandler.create_block_response(
                f"Core requirement incomplete: {next_requirement.description}"
            )
        
        # Allow stopping if no core requirements remain
        self.logger.info("Allowing stop - no core requirements remain")
        return HookHandler.create_allow_response()



    def _get_progress(self) -> Dict[str, Any]:
        """Calculate progress statistics"""
        if not self.requirements:
            return {'percentage': 0, 'completed': 0, 'total': 0}

        completed = sum(1 for r in self.requirements if r.completed)
        return {
            'percentage': (completed / len(self.requirements)) * 100,
            'completed': completed,
            'total': len(self.requirements)
        }

    def _get_current_requirement(self) -> str:
        """Get highest priority incomplete requirement"""
        incomplete = [r for r in self.requirements if not r.completed]
        if incomplete:
            next_req = min(incomplete, key=lambda x: x.priority)
            return next_req.description
        return "All complete"

    def _get_next_action(self) -> str:
        """Suggest next action"""
        req = self._get_current_requirement()
        if req != "All complete":
            return f"Work on: {req}"
        return "Review and finalize"

def main() -> None:
    """CLI interface and hook handler"""
    if len(sys.argv) < 2:
        print("Claude Code Task Monitor")
        print("Usage: task_monitor.py <command> [args]")
        print("\nCommands:")
        print("  start                           - Interactive task setup")
        print("  init <task> <req1> <req2> ...  - Initialize task")
        print("  status                          - Show progress")
        print("  reset                           - Reset progress")
        print("  hook <type>                     - Handle Claude Code hook")
        return

    monitor = TaskAlignmentMonitor()
    command = sys.argv[1]

    if command == "start":
        # Check if we can do interactive input
        # In Claude Code, stdin is not a TTY, so input() will fail
        if not sys.stdin.isatty():
            # Non-interactive environment (like Claude Code slash command)
            print("🚀 Claude Code Task Setup")
            print("\n⚠️  Interactive mode not available in this environment.")
            print("\nTo set up a task, you have two options:")
            print("\n1. Run this command directly in your terminal:")
            print(f"   cd {os.getcwd()}")
            print(f"   python3 {os.path.abspath(__file__)} start")
            print("\n2. Use the quick init command with arguments:")
            print("   /task init '<task description>' '<requirement 1>' '<requirement 2>' ...")
            print("\nExample:")
            print("   /task init 'Fix login bug' 'Reproduce the issue' 'Fix root cause' 'Add tests'")
            return  # Exit gracefully instead of sys.exit
        
        # Interactive task setup with intelligent prompting
        print("🚀 Claude Code Task Setup\n")

        # Task type selection
        print("What type of task is this?")
        print("1. 🐛 Bug fix")
        print("2. ✨ New feature")
        print("3. 🔧 Refactor")
        print("4. 📚 Documentation")
        print("5. 🧪 Testing")
        print("6. 🎨 UI/UX improvement")
        print("7. ⚡ Performance optimization")
        print("8. 🔒 Security enhancement")
        print("9. 📦 Other")

        task_type_map = {
            '1': ('bug', 'Bug Fix'),
            '2': ('feature', 'Feature'),
            '3': ('refactor', 'Refactor'),
            '4': ('docs', 'Documentation'),
            '5': ('test', 'Testing'),
            '6': ('ui', 'UI/UX'),
            '7': ('perf', 'Performance'),
            '8': ('security', 'Security'),
            '9': ('other', 'Task')
        }

        choice = input("\nSelect (1-9): ").strip()
        task_type, task_label = task_type_map.get(choice, ('other', 'Task'))

        # Get initial description
        print(f"\n📝 Describe the {task_label.lower()}:")
        description = input("> ").strip()

        # Intelligent clarification based on task type
        clarifications = []

        if task_type == 'bug':
            print("\n🤔 Let me help you clarify this bug fix...")

            # Error behavior
            print("\nWhat's the current incorrect behavior?")
            current = input("> ").strip()
            if current:
                clarifications.append(f"Current behavior: {current}")

            # Expected behavior
            print("\nWhat should happen instead?")
            expected = input("> ").strip()
            if expected:
                clarifications.append(f"Expected behavior: {expected}")

            # Scope
            print("\nAre there any edge cases or related areas that might be affected?")
            print("(Press Enter to skip)")
            edge_cases = input("> ").strip()
            if edge_cases:
                clarifications.append(f"Consider: {edge_cases}")

        elif task_type == 'feature':
            print("\n🤔 Let's make sure we've thought this through...")

            # User value
            print("\nWho will use this feature and why?")
            users = input("> ").strip()
            if users:
                clarifications.append(f"Users: {users}")

            # Success criteria
            print("\nHow will you know this feature is working correctly?")
            print("(What's the simplest test case?)")
            test_case = input("> ").strip()
            if test_case:
                clarifications.append(f"Success criteria: {test_case}")

            # Non-goals
            print("\nWhat should this feature NOT do? (helps prevent scope creep)")
            print("(Press Enter to skip)")
            non_goals = input("> ").strip()
            if non_goals:
                clarifications.append(f"NOT doing: {non_goals}")

            # Dependencies
            print("\nDoes this depend on any existing functionality?")
            print("(Press Enter if none)")
            deps = input("> ").strip()
            if deps:
                clarifications.append(f"Depends on: {deps}")

        elif task_type == 'refactor':
            print("\n🤔 Let's ensure this refactor has clear goals...")

            # Problem
            print("\nWhat specific problem does this refactor solve?")
            problem = input("> ").strip()
            if problem:
                clarifications.append(f"Problem: {problem}")

            # Boundaries
            print("\nWhat code should be touched? What should NOT be changed?")
            boundaries = input("> ").strip()
            if boundaries:
                clarifications.append(f"Boundaries: {boundaries}")

            # Verification
            print("\nHow will you verify nothing broke? (existing tests? manual checks?)")
            verify = input("> ").strip()
            if verify:
                clarifications.append(f"Verification: {verify}")

        elif task_type == 'security':
            print("\n🤔 Security requires careful consideration...")

            # Threat
            print("\nWhat specific vulnerability or threat are you addressing?")
            threat = input("> ").strip()
            if threat:
                clarifications.append(f"Threat: {threat}")

            # Impact
            print("\nWhat could happen if this isn't fixed?")
            impact = input("> ").strip()
            if impact:
                clarifications.append(f"Impact: {impact}")

        elif task_type == 'perf':
            print("\n🤔 Let's define performance goals...")

            # Current performance
            print("\nWhat's the current performance issue? (slow load? high memory?)")
            current_perf = input("> ").strip()
            if current_perf:
                clarifications.append(f"Current issue: {current_perf}")

            # Target
            print("\nWhat's your performance target? (2x faster? under 100ms?)")
            target = input("> ").strip()
            if target:
                clarifications.append(f"Target: {target}")

        # Generate smart requirements based on type and clarifications
        requirements = []

        if task_type == 'bug':
            requirements.append("Reproduce the bug consistently")
            requirements.append("Fix the root cause")
            requirements.append("Add test to prevent regression")
            if 'edge cases' in ' '.join(clarifications).lower():
                requirements.append("Handle edge cases")

        elif task_type == 'feature':
            requirements.append("Implement core functionality")
            if test_case:
                requirements.append(f"Ensure {test_case}")
            requirements.append("Add error handling")
            requirements.append("Write tests")
            if users and 'api' not in description.lower():
                requirements.append("Create user interface")

        elif task_type == 'refactor':
            requirements.append("Identify code to refactor")
            requirements.append("Refactor without changing behavior")
            requirements.append("Ensure all tests pass")
            requirements.append("Update documentation if needed")

        elif task_type == 'security':
            requirements.append("Identify vulnerable code")
            requirements.append("Implement secure solution")
            requirements.append("Add security tests")
            requirements.append("Document security considerations")

        elif task_type == 'perf':
            requirements.append("Profile current performance")
            requirements.append("Implement optimization")
            requirements.append("Measure improvement")
            requirements.append("Ensure no functionality regression")

        else:
            # Generic requirements
            requirements.append("Implement main functionality")
            requirements.append("Handle errors gracefully")
            requirements.append("Add appropriate tests")

        # Show generated task
        print("\n📋 Based on our discussion, here's your task structure:")
        print(f"\nTask: [{task_label}] {description}")

        if clarifications:
            print("\nClarifications:")
            for c in clarifications:
                print(f"  • {c}")

        print("\nGenerated Requirements:")
        for i, req in enumerate(requirements, 1):
            print(f"  {i}. {req}")

        # Allow requirement editing
        print("\n✏️  Would you like to:")
        print("1. Use these requirements as-is")
        print("2. Add more requirements")
        print("3. Edit requirements")
        print("4. Start over")

        edit_choice = input("\nSelect (1-4): ").strip()

        if edit_choice == '2':
            print("\nAdd requirements (empty line to finish):")
            while True:
                new_req = input(f"{len(requirements)+1}. ").strip()
                if not new_req:
                    break
                requirements.append(new_req)

        elif edit_choice == '3':
            print("\nEdit requirements (enter number to edit, 'done' to finish):")
            while True:
                for i, req in enumerate(requirements, 1):
                    print(f"  {i}. {req}")
                edit_num = input("\nEdit which? ").strip()
                if edit_num.lower() == 'done':
                    break
                try:
                    idx = int(edit_num) - 1
                    if 0 <= idx < len(requirements):
                        new_text = input(f"New text for #{edit_num}: ").strip()
                        if new_text:
                            requirements[idx] = new_text
                except:
                    pass

        elif edit_choice == '4':
            print("Starting over...")
            return main()

        # Create full task description
        full_task = f"[{task_label}] {description}"
        if clarifications:
            full_task += " (" + "; ".join(clarifications) + ")"

        # Initialize with the refined task
        print("\n🚀 Initializing task monitor...")
        sys.argv = ['task_monitor.py', 'init', full_task] + requirements
        return main()

    elif command == "init":
        if len(sys.argv) < 4:
            print("Usage: task_monitor.py init '<task>' '<req1>' '<req2>' ...")
            return

        monitor.task = sys.argv[2]
        monitor.requirements = []

        # Add requirements with smart priority
        for i, desc in enumerate(sys.argv[3:], 1):
            priority = 1 if i <= 2 else (2 if i <= 4 else 3)
            monitor.requirements.append(
                TaskRequirement(id=str(i), description=desc, priority=priority)
            )

        # Create git task snapshot if in a git repository
        if monitor.git_manager._is_git_repo():
            try:
                task_state = monitor.create_task_snapshot(
                    task_description=monitor.task
                )
                print(f"📸 Created git task snapshot: {task_state.subagent_branches.get('wip_snapshot', 'refs/wip/' + task_state.branch_name)}")
            except Exception as e:
                print(f"⚠️  Could not create git task snapshot: {e}")

        monitor.save_config()

        # Create hooks configuration for Claude Code settings
        hooks_config = {
            "hooks": {
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"python {os.path.abspath(__file__)} hook Stop"
                            }
                        ]
                    }
                ],
                "SubagentStop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"python {os.path.abspath(__file__)} hook SubagentStop"
                            }
                        ]
                    }
                ]
            }
        }

        # Update .claude/settings.local.json with hooks
        os.makedirs('.claude', exist_ok=True)
        settings_file = '.claude/settings.local.json'
        if os.path.exists(settings_file):
            with open(settings_file, 'r') as f:
                settings = json.load(f)
        else:
            settings = {}
        
        settings.update(hooks_config)
        
        with open(settings_file, 'w') as f:
            json.dump(settings, f, indent=2)

        print(f"✅ Initialized: {monitor.task}")
        print(f"📋 Requirements: {len(monitor.requirements)}")
        print("🪝 Hooks configured in .claude/settings.local.json")
        
        # Check if .claude-task.json is in .gitignore
        working_dir = os.environ.get('CLAUDE_WORKING_DIR', '.')
        gitignore_path = Path(working_dir) / ".gitignore"
        if gitignore_path.exists():
            with open(gitignore_path, 'r') as f:
                gitignore_content = f.read()
                if '.claude-task.json' not in gitignore_content:
                    print("\n⚠️  Consider adding '.claude-task.json' to your .gitignore file")
                    print("   This file contains local task state and shouldn't be committed")
        
        print("\nRequirements:")
        for requirement in monitor.requirements:
            print(f"  - {requirement.description} (Priority {requirement.priority})")

    elif command == "status":
        if not monitor.task:
            print("No task configured. Run: task_monitor.py init")
            return

        progress = monitor._get_progress()
        print(f"\n📌 Task: {monitor.task}")
        print(f"📊 Progress: {progress['percentage']:.0f}% complete")
        print(f"📈 Stats: {monitor.stats['commands']} commands, {monitor.stats['deviations']} deviations")
        print(f"\nRequirements:")

        for requirement in monitor.requirements:
            icon = "✅" if requirement.completed else "⏳"
            print(f"  {icon} {requirement.description} (P{requirement.priority})")

        if progress['percentage'] < 100:
            print(f"\n➡️  Next: {monitor._get_next_action()}")

    elif command == "reset":
        for requirement in monitor.requirements:
            requirement.completed = False
        monitor.stats = {'deviations': 0, 'commands': 0}
        monitor.save_config()
        print("✅ Progress reset")

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
                "/task": {
                    "description": "Manage task alignment and focus",
                    "subcommands": {
                        "start": {
                            "description": "Start a new task with guided setup",
                            "command": f"python {os.path.abspath(__file__)} start"
                        },
                        "status": {
                            "description": "Check current task progress",
                            "command": f"python {os.path.abspath(__file__)} status"
                        },
                        "next": {
                            "description": "Show next priority action",
                            "command": f"python {os.path.abspath(__file__)} next"
                        },
                        "complete": {
                            "description": "Mark current requirement as complete",
                            "command": f"python {os.path.abspath(__file__)} complete"
                        },
                        "focus": {
                            "description": "Get reminder of current focus area",
                            "command": f"python {os.path.abspath(__file__)} focus"
                        }
                    }
                },
                "/focus": {
                    "description": "Quick reminder of what to work on next",
                    "command": f"python {os.path.abspath(__file__)} focus"
                }
            }
        }
        print(json.dumps(slash_config, indent=2))

    elif command == "next":
        # Quick command to show next action
        if not monitor.task:
            print("No task configured. Run: /task start")
            return

        progress = monitor._get_progress()
        current = monitor._get_current_requirement()

        if current != "All complete":
            print(f"📌 Next: {current}")
            print(f"📊 Progress: {progress['percentage']:.0f}% ({progress['completed']}/{progress['total']})")
        else:
            print("✅ All requirements complete!")

    elif command == "focus":
        # Quick focus reminder
        if not monitor.task:
            print("No task configured. Run: /task start")
            return

        print(f"🎯 Task: {monitor.task}")
        print(f"📌 Focus on: {monitor._get_current_requirement()}")

        # Show any active warnings
        if monitor.stats['deviations'] > 0:
            print(f"⚠️  {monitor.stats['deviations']} deviations detected this session")

    elif command == "complete":
        # Mark current requirement as complete
        if not monitor.task:
            print("No task configured.")
            return

        for requirement in monitor.requirements:
            if not requirement.completed:
                requirement.completed = True
                monitor.save_config()
                print(f"✅ Completed: {requirement.description}")

                # Show next
                progress = monitor._get_progress()
                if progress['percentage'] < 100:
                    print(f"\n📊 Progress: {progress['percentage']:.0f}% ({progress['completed']}/{progress['total']})")
                    print(f"📌 Next: {monitor._get_current_requirement()}")
                else:
                    print("\n🎉 All requirements complete!")
                break

if __name__ == "__main__":
    main()
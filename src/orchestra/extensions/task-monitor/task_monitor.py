#!/usr/bin/env python3
"""
Task Alignment Monitor for Claude Code
Direct integration with Claude Code hooks - no extra scripts needed
"""

import json
import sys
import os
from typing import Dict, Optional, Any, Union, List
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
from pathlib import Path

class DeviationType(Enum):
    SCOPE_CREEP = "scope_creep"
    OFF_TOPIC = "off_topic"
    OVER_ENGINEERING = "over_engineering"
    MISSING_REQUIREMENT = "missing_requirement"
    UNNECESSARY_WORK = "unnecessary_work"

@dataclass
class TaskRequirement:
    id: str
    description: str
    priority: int  # 1-5, where 1 is highest
    completed: bool = False

class TaskAlignmentMonitor:
    def __init__(self, config_path: Optional[str] = None) -> None:
        # Use CLAUDE_WORKING_DIR if available, otherwise current directory
        working_dir = os.environ.get('CLAUDE_WORKING_DIR', '.')
        self.config_path = config_path or os.path.join(working_dir, '.claude-task.json')
        self.task: str = ""
        self.requirements: List[TaskRequirement] = []
        self.settings: Dict[str, Any] = {}
        self.stats: Dict[str, int] = {}
        self.load_config()

    def load_config(self) -> None:
        """Load or create configuration"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                config = json.load(f)
                self.task = config.get('task', '')
                self.requirements = [TaskRequirement(**req) for req in config.get('requirements', [])]
                self.settings = config.get('settings', {})
                self.stats = config.get('stats', {'deviations': 0, 'commands': 0})
        else:
            self.task = ""
            self.requirements = []
            self.settings = {"strict_mode": True, "max_deviations": 3}
            self.stats = {'deviations': 0, 'commands': 0}

    def save_config(self) -> None:
        """Save configuration and progress"""
        config = {
            'task': self.task,
            'requirements': [asdict(req) for req in self.requirements],
            'settings': self.settings,
            'stats': self.stats,
            'updated': datetime.now().isoformat()
        }
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)

    def handle_hook(self, hook_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Universal hook handler"""
        if hook_type == "PreToolUse":
            return self._pre_tool_use(context)
        elif hook_type == "PostToolUse":
            return self._post_tool_use(context)
        elif hook_type == "UserPromptSubmit":
            return self._enhance_prompt(context)
        # Legacy support for old names
        elif hook_type == "pre-command":
            return self._pre_tool_use(context) 
        elif hook_type == "post-command":
            return self._post_tool_use(context)
        elif hook_type == "prompt":
            return self._enhance_prompt(context)
        elif hook_type == "file-change":
            return self._check_file_change(context)
        return context

    def _pre_tool_use(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze tool use before execution"""
        # Extract tool information from Claude Code hook format
        tool_name = context.get('tool_name', '')
        tool_input = context.get('tool_input', {})
        
        # For Bash commands, get the command from tool_input
        if tool_name == 'Bash':
            command = tool_input.get('command', '')
        else:
            # For other tools, create a description of what's being done
            command = f"{tool_name} {' '.join(str(v) for v in tool_input.values())}"

        # Skip if no task defined
        if not self.task:
            return context

        self.stats['commands'] += 1

        # Check for deviations using intelligent subagents
        deviation = self._check_deviation_with_subagents(command)
        if deviation:
            self.stats['deviations'] += 1

            if self.settings.get('strict_mode') and int(deviation.get('severity', 0)) >= 4:
                # Block severe deviations - use Claude Code JSON format
                print(f"\n❌ Blocked: {deviation['type']}")
                print(f"   {deviation['message']}")
                print(f"   Instead: {self._get_next_action()}\n")
                
                # Return JSON output for Claude Code
                return {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"{deviation['type']}: {deviation['message']}. Instead: {self._get_next_action()}"
                    }
                }
            else:
                # Warn for minor deviations
                print(f"\n⚠️  Warning: {deviation['type']}")
                print(f"   {deviation['message']}\n")

        self.save_config()
        return context

    def _pre_command(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy method - delegate to new implementation"""
        return self._pre_tool_use(context)

    def _post_tool_use(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Update progress after tool use"""
        # Extract tool information from Claude Code hook format
        tool_name = context.get('tool_name', '')
        tool_input = context.get('tool_input', {})
        
        # For Bash commands, get the command from tool_input
        if tool_name == 'Bash':
            command = tool_input.get('command', '')
        else:
            # For other tools, create a description of what was done
            command = f"{tool_name} {' '.join(str(v) for v in tool_input.values())}"

        # Update requirements if command matches
        for req in self.requirements:
            if not req.completed and req.description.lower() in command.lower():
                req.completed = True
                print(f"✅ Completed: {req.description}")
                break

        # Show progress
        progress = self._get_progress()
        if progress['percentage'] < 100:
            print(f"\n📊 Progress: {progress['percentage']:.0f}% ({progress['completed']}/{progress['total']})")
            print(f"📌 Next: {self._get_next_action()}\n")

        self.save_config()
        return context

    def _post_command(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Legacy method - delegate to new implementation"""
        return self._post_tool_use(context)

    def _enhance_prompt(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Add task context to prompts"""
        if not self.task:
            return context

        prompt = context.get('prompt', '')
        progress = self._get_progress()

        # Prepend context
        enhancement = f"[Task: {self.task} | Progress: {progress['percentage']:.0f}% | Focus: {self._get_current_requirement()}]\n"

        context['prompt'] = enhancement + prompt
        return context

    def _check_file_change(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Monitor file changes"""
        path = context.get('path', '')
        change_type = context.get('type', '')

        # Simple check for unnecessary files
        unnecessary_patterns = ['test.html', 'demo.js', 'example.css', '.bak']
        if any(pattern in path.lower() for pattern in unnecessary_patterns):
            incomplete = [r for r in self.requirements if not r.completed and r.priority <= 2]
            if incomplete:
                print(f"⚠️  Creating {path} before core requirements complete")

        return context

    def _check_deviation_with_subagents(self, command: str) -> Optional[Dict[str, Union[str, int]]]:
        """Check if command deviates from objectives using intelligent subagents"""
        import subprocess
        import tempfile
        
        # Prepare context for subagents
        progress_info = self._get_progress()
        context: Dict[str, Any] = {
            'command': command,
            'task': self.task,
            'requirements': [asdict(req) for req in self.requirements],
            'progress': progress_info,
            'current_requirement': self._get_current_requirement()
        }
        
        # Check each type of deviation using specialized subagents
        subagents = [
            ('scope-creep-detector', 'scope_creep'),
            ('over-engineering-detector', 'over_engineering'), 
            ('off-topic-detector', 'off_topic')
        ]
        
        for agent_name, deviation_type in subagents:
            try:
                # Create analysis prompt for the subagent
                analysis_prompt = f"""
Analyze this command for {deviation_type.replace('_', ' ')}:

Command: "{command}"
Task: "{self.task}"
Current Progress: {progress_info['percentage']:.0f}% complete
Current Focus: {context['current_requirement']}

Requirements:
"""
                for requirement in self.requirements:
                    status = "✅" if requirement.completed else "⏳"
                    analysis_prompt += f"  {status} {requirement.description} (Priority {requirement.priority})\n"

                analysis_prompt += f"\nReturn JSON with your analysis."
                
                # Try to invoke the subagent via Claude Code if available
                result = self._invoke_subagent(agent_name, analysis_prompt)
                if result and result.get('is_deviation'):
                    return {
                        'type': result['type'],
                        'severity': result['severity'],
                        'message': result['message']
                    }
                
                # If subagent didn't detect deviation, continue to next one
                    
            except Exception as e:
                # If subagent fails, continue to next one
                print(f"Warning: Subagent {agent_name} failed: {e}")
                continue
        
        # If no subagents detected deviations, fall back to simple checks
        return self._fallback_deviation_check(command)
    
    def _invoke_subagent(self, agent_name: str, prompt: str) -> Optional[Dict[str, Any]]:
        """Invoke a Claude Code subagent for analysis"""
        try:
            # Check if we're in a Claude Code environment
            # For now, we'll simulate subagent behavior with enhanced pattern matching
            # In a full implementation, this would use Claude Code's internal APIs
            
            # Simulate intelligent analysis based on the agent type
            if agent_name == 'scope-creep-detector':
                return self._simulate_scope_creep_analysis(prompt)
            elif agent_name == 'over-engineering-detector':
                return self._simulate_over_engineering_analysis(prompt)
            elif agent_name == 'off-topic-detector':
                return self._simulate_off_topic_analysis(prompt)
            
        except Exception as e:
            print(f"Subagent {agent_name} error: {e}")
            return None
        
        return None
    
    def _simulate_scope_creep_analysis(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Simulate scope creep detector subagent"""
        # Extract command from prompt
        import re
        command_match = re.search(r'Command: "([^"]+)"', prompt)
        progress_match = re.search(r'Current Progress: (\d+)%', prompt)
        
        if not command_match:
            return None
            
        command = command_match.group(1).lower()
        progress = int(progress_match.group(1)) if progress_match else 0
        
        # Enhanced scope creep detection
        enhancement_words = ['enhance', 'improve', 'beautify', 'polish', 'optimize', 'refactor', 'clean up', 'make pretty', 'style']
        premature_words = ['performance', 'scalability', 'architecture', 'design pattern']
        
        severity = 0
        reasons = []
        
        for word in enhancement_words:
            if word in command:
                if progress < 60:
                    severity = max(severity, 4)
                    reasons.append(f"Enhancement work ('{word}') while only {progress}% complete")
                elif progress < 80:
                    severity = max(severity, 3)
                    reasons.append(f"Early enhancement ('{word}') - consider finishing core features first")
                    
        for word in premature_words:
            if word in command and progress < 70:
                severity = max(severity, 4)
                reasons.append(f"Premature {word} optimization while {progress}% complete")
        
        if severity > 0:
            return {
                'is_deviation': True,
                'type': 'scope_creep',
                'severity': severity,
                'message': '; '.join(reasons),
                'suggestion': 'Focus on completing core requirements first'
            }
            
        return {'is_deviation': False}
    
    def _simulate_over_engineering_analysis(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Simulate over-engineering detector subagent"""
        import re
        command_match = re.search(r'Command: "([^"]+)"', prompt)
        
        if not command_match:
            return None
            
        command = command_match.group(1).lower()
        
        # Check for incomplete core requirements
        incomplete_core = any(not r.completed for r in self.requirements if r.priority <= 2)
        
        # Over-engineering patterns
        complexity_words = ['framework', 'architecture', 'design pattern', 'abstract', 'generic', 'scalable', 'flexible']
        pattern_words = ['factory', 'builder', 'strategy', 'observer', 'singleton', 'decorator']
        premature_words = ['plugin', 'configuration', 'interface', 'inheritance']
        
        severity = 0
        reasons = []
        
        for word in complexity_words:
            if word in command and incomplete_core:
                severity = max(severity, 4)
                reasons.append(f"Introducing {word} before basic functionality complete")
                
        for word in pattern_words:
            if word in command and incomplete_core:
                severity = max(severity, 5)
                reasons.append(f"Applying {word} pattern prematurely")
                
        for word in premature_words:
            if word in command and incomplete_core:
                severity = max(severity, 3)
                reasons.append(f"Building {word} system before proving need")
        
        if severity > 0:
            return {
                'is_deviation': True,
                'type': 'over_engineering',
                'severity': severity,
                'message': '; '.join(reasons),
                'suggestion': 'Implement simple solution first, then add complexity if needed'
            }
            
        return {'is_deviation': False}
    
    def _simulate_off_topic_analysis(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Simulate off-topic detector subagent"""
        import re
        command_match = re.search(r'Command: "([^"]+)"', prompt)
        task_match = re.search(r'Task: "([^"]+)"', prompt)
        
        if not command_match or not task_match:
            return None
            
        command = command_match.group(1).lower()
        task = task_match.group(1).lower()
        
        # Enhanced relevance analysis
        task_keywords = set(re.findall(r'\b\w+\b', task))
        command_keywords = set(re.findall(r'\b\w+\b', command))
        
        # Remove common words
        common_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'can', 'must'}
        task_keywords -= common_words
        command_keywords -= common_words
        
        if not task_keywords:
            return {'is_deviation': False}  # Can't analyze without task keywords
        
        # Calculate overlap
        overlap = len(task_keywords & command_keywords)
        relevance_ratio = overlap / len(task_keywords)
        
        severity = 0
        if relevance_ratio == 0:
            severity = 5
            message = f"No apparent connection to task: {task}"
        elif relevance_ratio < 0.2:
            severity = 4
            message = f"Very weak connection to task (only {overlap} shared concepts)"
        elif relevance_ratio < 0.4:
            severity = 3
            message = f"Weak connection to task (only {overlap}/{len(task_keywords)} relevant concepts)"
        
        if severity > 0:
            return {
                'is_deviation': True,
                'type': 'off_topic',
                'severity': severity,
                'message': message,
                'suggestion': f'Focus on task: {task}'
            }
            
        return {'is_deviation': False}
    
    def _fallback_deviation_check(self, command: str) -> Optional[Dict[str, Union[str, int]]]:
        """Fallback deviation detection for when subagents aren't available"""
        cmd_lower = command.lower()
        
        # Scope creep patterns
        if any(word in cmd_lower for word in ['enhance', 'improve', 'beautify', 'optimize', 'refactor']):
            if self._get_progress()['percentage'] < 80:
                return {
                    'type': 'scope_creep',
                    'severity': 3,
                    'message': 'Focus on core requirements before enhancements'
                }
        
        # Over-engineering patterns  
        if any(word in cmd_lower for word in ['framework', 'abstract', 'generic', 'scalable']):
            incomplete_core = any(not r.completed for r in self.requirements if r.priority <= 2)
            if incomplete_core:
                return {
                    'type': 'over_engineering',
                    'severity': 4,
                    'message': 'Implement simple solution first'
                }
        
        # Off-topic check
        if self.task:
            task_words = set(self.task.lower().split())
            cmd_words = set(cmd_lower.split())
            if len(task_words & cmd_words) == 0:
                return {
                    'type': 'off_topic',
                    'severity': 4,
                    'message': f'Command unrelated to: {self.task}'
                }
        
        return None

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

        monitor.save_config()

        # Create hooks configuration for Claude Code settings
        hooks_config = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command", 
                                "command": f"python {os.path.abspath(__file__)} hook PreToolUse"
                            }
                        ]
                    }
                ],
                "PostToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"python {os.path.abspath(__file__)} hook PostToolUse"
                            }
                        ]
                    }
                ],
                "UserPromptSubmit": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"python {os.path.abspath(__file__)} hook UserPromptSubmit"
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

        # Read context from stdin (Claude Code passes this)
        try:
            context = json.loads(sys.stdin.read()) if not sys.stdin.isatty() else {}
        except:
            context = {}

        # Handle the hook
        result = monitor.handle_hook(hook_type, context)

        # Output result for Claude Code
        print(json.dumps(result))

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
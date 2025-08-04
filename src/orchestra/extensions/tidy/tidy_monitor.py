#!/usr/bin/env python3
"""
Tidy Monitor for Claude Code

Automatic code quality checker that ensures code meets project standards.
Integrates with Claude Code's Stop and SubagentStop hooks.
"""

import os
import sys
import logging
from typing import Dict, Optional, Any, List
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm

# Import from common library
from orchestra.common import BaseExtension, HookHandler, setup_logger, truncate_value, format_hook_context

# Import tidy-specific modules
from .project_detector import ProjectDetector
from .tool_runners import ToolRunnerFactory, ParallelToolRunner, ToolResult


class TidyMonitor(BaseExtension):
    """Main Tidy extension class"""
    
    def __init__(self, config_path: Optional[str] = None) -> None:
        # Use CLAUDE_WORKING_DIR if available
        working_dir = os.environ.get('CLAUDE_WORKING_DIR', '.')
        
        # Set up logging
        log_dir = os.path.join(working_dir, '.claude', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'tidy_monitor.log')
        
        # Configure logger with truncation
        self.logger = setup_logger('tidy_monitor', log_file, logging.DEBUG, truncate=True, max_length=300)
        self.logger.info("TidyMonitor initialized")
        
        # Initialize base class
        super().__init__(config_file=config_path, working_dir=working_dir)
        
        # Initialize console for output
        self.console = Console()
        
        # Tidy-specific state
        self.project_info = None
        self.detected_tools: Dict[str, Dict[str, Any]] = {}
        self.custom_commands: List[Dict[str, str]] = []
        self.do_examples: List[str] = []
        self.dont_examples: List[str] = []
        self.last_check: Dict[str, Any] = {}
        self.settings = {
            "auto_fix": False,
            "strict_mode": True,
            "check_on_file_change": True,
            "ignore_patterns": ["*_test.py", "migrations/*", "node_modules/*", "*.min.js"],
            "max_issues_shown": 10,
            "parallel_execution": True,
            "check_timeout": 60,
            "use_sidecar": False  # Run checks asynchronously in background
        }
        
        # Modified files tracking
        self.modified_files: List[str] = []
        
        # Load configuration
        self.load_config()
        
        # Auto-detect project if not configured
        if not self.project_info:
            self._auto_detect_project()
    
    def get_default_config_filename(self) -> str:
        """Get the default configuration file name for this extension"""
        return 'tidy.json'
    
    def load_config(self) -> Dict[str, Any]:
        """Load or create configuration"""
        config = super().load_config()
        
        if config:
            self.project_info = config.get('project_info')
            self.detected_tools = config.get('detected_tools', {})
            self.custom_commands = config.get('custom_commands', [])
            self.do_examples = config.get('do_examples', [])
            self.dont_examples = config.get('dont_examples', [])
            self.last_check = config.get('last_check', {})
            self.settings.update(config.get('settings', {}))
        
        return config
    
    def save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save configuration"""
        if config is None:
            config = {
                'project_info': self.project_info,
                'detected_tools': self.detected_tools,
                'custom_commands': self.custom_commands,
                'do_examples': self.do_examples,
                'dont_examples': self.dont_examples,
                'last_check': self.last_check,
                'settings': self.settings,
                'updated': datetime.now().isoformat()
            }
        
        super().save_config(config)
    
    def _auto_detect_project(self) -> None:
        """Auto-detect project type and tools"""
        self.logger.info("Auto-detecting project type and tools")
        
        detector = ProjectDetector(self.working_dir)
        project_info = detector.detect()
        
        self.project_info = {
            'type': project_info.project_type.value,
            'package_manager': project_info.package_manager.value,
            'config_files': project_info.config_files[:10],  # Limit to 10 files
            'source_files': project_info.source_files[:10]   # Limit to 10 files
        }
        
        # Convert ToolInfo objects to dict for serialization
        self.detected_tools = {}
        for category, tool_info in project_info.detected_tools.items():
            self.detected_tools[category] = {
                'name': tool_info.name,
                'command': tool_info.command,
                'fix_command': tool_info.fix_command,
                'config_file': tool_info.config_file,
                'version': tool_info.version,
                'is_available': tool_info.is_available
            }
        
        self.save_config()
        self.logger.info(f"Detected project type: {self.project_info['type']}")
        self.logger.info(f"Detected tools: {list(self.detected_tools.keys())}")
    
    def handle_hook(self, hook_event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Claude Code hook events"""
        self.logger.info(f"Handling hook event: {hook_event}")
        self.logger.debug(f"Hook context: {format_hook_context(context)}")
        
        if hook_event == "Stop":
            return self._handle_stop_hook(context)
        elif hook_event == "SubagentStop":
            return self._handle_subagent_stop_hook(context)
        elif hook_event == "PostToolUse":
            return self._handle_post_tool_use(context)
        elif hook_event == "PreCompact":
            return self._handle_pre_compact(context)
        else:
            return HookHandler.create_allow_response()
    
    def _handle_stop_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Stop hook - check code quality after Claude finishes"""
        self.logger.info("Handling Stop hook")
        
        # Don't run if stop hook is already active (prevent recursion)
        if context.get('stop_hook_active', False):
            self.logger.info("Stop hook already active, skipping")
            return HookHandler.create_allow_response()
        
        # Check if any files were modified
        if not self.modified_files:
            self.logger.info("No files modified, skipping checks")
            return HookHandler.create_allow_response()
        
        # Check if we should run in sidecar mode
        if self.settings.get('use_sidecar', False):
            # Start sidecar daemon and return immediately
            from .commands.sidecar import TidySidecarCommand
            
            sidecar = TidySidecarCommand(logger=self.logger)
            input_data = {
                "action": "start",
                "working_dir": self.working_dir,
                "detected_tools": self.detected_tools,
                "modified_files": self.modified_files
            }
            
            result = sidecar.execute(input_data)
            
            if result.get("success"):
                self.logger.info(f"Started sidecar daemon with PID {result.get('pid')}")
                # Clear modified files
                self.modified_files = []
                # Return allow response - sidecar will handle fixes async
                return HookHandler.create_allow_response()
            else:
                self.logger.error(f"Failed to start sidecar: {result.get('error')}")
                # Fall back to synchronous mode
        
        # Run checks synchronously
        results = self._run_checks(self.modified_files)
        
        # Save results (convert ToolResult to dict for JSON serialization)
        self.last_check = {
            'timestamp': datetime.now().isoformat(),
            'files_checked': self.modified_files,
            'results': {
                name: {
                    'success': result.success,
                    'issues_count': result.issues_count,
                    'duration': result.duration,
                    'can_fix': result.can_fix
                }
                for name, result in results.items()
            }
        }
        self.save_config()
        
        # Clear modified files
        self.modified_files = []
        
        # Format and return results
        return self._format_check_results(results)
    
    def _handle_subagent_stop_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle SubagentStop hook - check code modified by subagent"""
        self.logger.info("Handling SubagentStop hook")
        
        # Similar to Stop hook but for subagent context
        if not self.modified_files:
            return HookHandler.create_allow_response()
        
        results = self._run_checks(self.modified_files)
        self.modified_files = []
        
        return self._format_check_results(results, is_subagent=True)
    
    def _handle_post_tool_use(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Track file modifications"""
        tool_name = context.get('tool_name', '')
        tool_input = context.get('tool_input', {})
        
        # Track files modified by Edit, Write, MultiEdit tools
        if tool_name in ['Edit', 'Write', 'MultiEdit']:
            file_path = tool_input.get('file_path', '')
            if file_path and not self._should_ignore_file(file_path):
                if file_path not in self.modified_files:
                    self.modified_files.append(file_path)
                    self.logger.info(f"Tracking modified file: {file_path}")
        
        return HookHandler.create_allow_response()
    
    def _handle_pre_compact(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Save state before compaction"""
        self.logger.info("Handling PreCompact hook")
        self.save_config()
        return HookHandler.create_allow_response()
    
    def _should_ignore_file(self, file_path: str) -> bool:
        """Check if file should be ignored based on patterns"""
        from fnmatch import fnmatch
        
        for pattern in self.settings.get('ignore_patterns', []):
            if fnmatch(file_path, pattern):
                return True
        
        return False
    
    def _run_checks(self, files: Optional[List[str]] = None) -> Dict[str, ToolResult]:
        """Run all configured tools on specified files"""
        self.logger.info(f"Running checks on {len(files) if files else 'all'} files")
        
        # Create tool runners
        runners = []
        for category, tool_info in self.detected_tools.items():
            if tool_info.get('is_available'):
                runner = ToolRunnerFactory.create(
                    tool_info['name'],
                    self.working_dir,
                    tool_info['command'],
                    tool_info.get('fix_command')
                )
                runners.append((category, runner))
        
        # Add custom command runners
        for custom in self.custom_commands:
            runner = ToolRunnerFactory.create(
                custom['name'],
                self.working_dir,
                custom['command'],
                custom.get('fix_command')
            )
            runners.append((custom['name'], runner))
        
        # Run tools in parallel if enabled
        if self.settings['parallel_execution'] and len(runners) > 1:
            parallel_runner = ParallelToolRunner(runners)
            results = parallel_runner.check_all(files)
        else:
            # Run sequentially
            results = {}
            for name, runner in runners:
                try:
                    results[name] = runner.check(files)
                except Exception as e:
                    self.logger.error(f"Error running {name}: {e}")
                    results[name] = ToolResult(
                        success=False,
                        output="",
                        error=str(e),
                        issues_count=0,
                        issues=[],
                        exit_code=-1,
                        duration=0.0
                    )
        
        return results
    
    def _format_check_results(self, results: Dict[str, ToolResult], is_subagent: bool = False) -> Dict[str, Any]:
        """Format check results for hook response"""
        total_issues = sum(r.issues_count for r in results.values())
        failed_tools = [name for name, r in results.items() if not r.success]
        
        if total_issues == 0 and not failed_tools:
            # All checks passed - no need to notify
            self.logger.info("All checks passed")
            return HookHandler.create_allow_response()
        
        # Build output message
        output_lines = []
        output_lines.append("🧹 Tidy Check Results")
        output_lines.append("=" * 40)
        
        if failed_tools:
            output_lines.append(f"\n❌ {len(failed_tools)} tool(s) found issues:")
            
            for tool_name in failed_tools:
                result = results[tool_name]
                output_lines.append(f"\n📋 {tool_name}: {result.issues_count} issue(s)")
                
                # Show first N issues
                max_issues = self.settings.get('max_issues_shown', 10)
                for issue in result.issues[:max_issues]:
                    if issue['file']:
                        location = f"{issue['file']}:{issue['line']}:{issue['column']}"
                    else:
                        location = "General"
                    
                    output_lines.append(f"  • {location}: {issue['message']}")
                
                if result.issues_count > max_issues:
                    output_lines.append(f"  ... and {result.issues_count - max_issues} more issues")
        
        # Add suggestions
        output_lines.append("\n💡 Suggestions:")
        
        fixable_tools = [name for name, r in results.items() if r.can_fix and not r.success]
        if fixable_tools and self.settings.get('auto_fix', False):
            output_lines.append(f"  • Auto-fix is enabled. Run: orchestra tidy fix")
        elif fixable_tools:
            output_lines.append(f"  • {len(fixable_tools)} tool(s) can auto-fix issues")
            output_lines.append(f"  • Run: orchestra tidy fix")
        
        if self.do_examples:
            output_lines.append("\n✅ Project conventions (DO):")
            for example in self.do_examples[:3]:
                output_lines.append(f"  • {example}")
        
        if self.dont_examples:
            output_lines.append("\n❌ Avoid these patterns (DON'T):")
            for example in self.dont_examples[:3]:
                output_lines.append(f"  • {example}")
        
        output = "\n".join(output_lines)
        
        # Return block response to prompt Claude to fix issues
        if is_subagent:
            # For subagents, just inform without blocking
            return {
                'continue': True,
                'suppressOutput': False,
                'output': output
            }
        else:
            # For main Claude, block and prompt to fix
            return HookHandler.create_block_response(
                f"{output}\n\nPlease fix the code quality issues found above."
            )
    
    # Slash command handlers
    def handle_slash_command(self, command: str, args: str = "") -> str:
        """Handle slash commands"""
        if command == "init":
            return self._cmd_init()
        elif command == "check":
            return self._cmd_check(args)
        elif command == "fix":
            return self._cmd_fix(args)
        elif command == "status":
            return self._cmd_status()
        elif command == "learn":
            return self._cmd_learn(args)
        elif command == "sidecar":
            return self._cmd_sidecar(args)
        else:
            return f"Unknown command: {command}"
    
    def _cmd_init(self) -> str:
        """Interactive initialization wizard"""
        self.console.print("\n[bold]🧹 Tidy Extension Setup Wizard[/bold]")
        self.console.print("=" * 50)
        
        # Re-detect project
        self._auto_detect_project()
        
        # Show detected information
        if self.project_info:
            self.console.print(f"\n📁 Project Type: [cyan]{self.project_info['type']}[/cyan]")
            self.console.print(f"📦 Package Manager: [cyan]{self.project_info['package_manager']}[/cyan]")
        else:
            self.console.print("\n⚠️  Could not detect project type")
        
        if self.detected_tools:
            self.console.print("\n🔧 Detected Tools:")
            for category, tool in self.detected_tools.items():
                status = "✅" if tool['is_available'] else "❌"
                self.console.print(f"  {status} {category}: {tool['name']}")
        
        # Configure settings
        self.console.print("\n⚙️  Settings Configuration:")
        
        self.settings['auto_fix'] = Confirm.ask("Enable auto-fix for fixable issues?", default=False)
        self.settings['strict_mode'] = Confirm.ask("Enable strict mode (fail on any issue)?", default=True)
        self.settings['parallel_execution'] = Confirm.ask("Run tools in parallel?", default=True)
        self.settings['use_sidecar'] = Confirm.ask("Enable sidecar mode (async background fixes)?", default=False)
        
        # Add custom commands
        if Confirm.ask("\nWould you like to add custom lint/format commands?", default=False):
            while True:
                name = Prompt.ask("Command name (e.g., 'custom-lint')")
                command = Prompt.ask("Check command (e.g., 'npm run lint')")
                fix_command = Prompt.ask("Fix command (optional, press Enter to skip)", default="")
                
                custom_command: Dict[str, str] = {
                    'name': name,
                    'command': command
                }
                if fix_command:
                    custom_command['fix_command'] = fix_command
                self.custom_commands.append(custom_command)
                
                if not Confirm.ask("Add another command?", default=False):
                    break
        
        # Save configuration
        self.save_config()
        
        # Run initial check
        self.console.print("\n🚀 Running initial check...")
        return self._cmd_check("")
    
    def _cmd_check(self, args: str) -> str:
        """Run code quality checks"""
        files = args.split() if args else None
        
        if not files:
            # Check all source files
            self.console.print("🔍 Checking all source files...")
            files = None
        else:
            self.console.print(f"🔍 Checking {len(files)} file(s)...")
        
        results = self._run_checks(files)
        
        # Display results
        total_issues = sum(r.issues_count for r in results.values())
        
        if total_issues == 0:
            self.console.print("\n✅ [green]All checks passed![/green]")
            return "All checks passed!"
        
        # Create results table
        table = Table(title="Code Quality Check Results")
        table.add_column("Tool", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Issues", justify="right")
        table.add_column("Duration", justify="right")
        table.add_column("Fixable", justify="center")
        
        for tool_name, result in results.items():
            status = "[green]✓ PASS[/green]" if result.success else "[red]✗ FAIL[/red]"
            fixable = "Yes" if result.can_fix and not result.success else "No"
            
            table.add_row(
                tool_name,
                status,
                str(result.issues_count),
                f"{result.duration:.2f}s",
                fixable
            )
        
        self.console.print(table)
        
        # Show sample issues
        self.console.print(f"\n📋 Total issues: {total_issues}")
        
        for tool_name, result in results.items():
            if result.issues:
                self.console.print(f"\n[bold]{tool_name}:[/bold]")
                for issue in result.issues[:5]:
                    location = f"{issue['file']}:{issue['line']}:{issue['column']}" if issue['file'] else "General"
                    self.console.print(f"  • {location}: {issue['message']}")
                
                if len(result.issues) > 5:
                    self.console.print(f"  ... and {len(result.issues) - 5} more issues")
        
        # Update last check
        self.last_check = {
            'timestamp': datetime.now().isoformat(),
            'files_checked': files,
            'results': {
                name: {
                    'success': result.success,
                    'issues_count': result.issues_count,
                    'duration': result.duration,
                    'can_fix': result.can_fix
                }
                for name, result in results.items()
            }
        }
        self.save_config()
        
        return f"Found {total_issues} issue(s)"
    
    def _cmd_fix(self, args: str) -> str:
        """Auto-fix issues"""
        files = args.split() if args else None
        
        self.console.print("🔧 Running auto-fix...")
        
        # Create tool runners for fixable tools
        runners = []
        for category, tool_info in self.detected_tools.items():
            if tool_info.get('is_available') and tool_info.get('fix_command'):
                runner = ToolRunnerFactory.create(
                    tool_info['name'],
                    self.working_dir,
                    tool_info['command'],
                    tool_info['fix_command']
                )
                runners.append((category, runner))
        
        if not runners:
            return "No fixable tools configured"
        
        # Run fixes
        if self.settings['parallel_execution'] and len(runners) > 1:
            parallel_runner = ParallelToolRunner(runners)
            results = parallel_runner.fix_all(files)
        else:
            results = {}
            for name, runner in runners:
                results[name] = runner.fix(files)
        
        # Display results
        total_fixed = sum(r.fixed_count for r in results.values() if hasattr(r, 'fixed_count'))
        
        table = Table(title="Auto-fix Results")
        table.add_column("Tool", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Fixed", justify="right")
        
        for tool_name, result in results.items():
            status = "[green]✓ SUCCESS[/green]" if result.success else "[red]✗ FAILED[/red]"
            fixed = str(getattr(result, 'fixed_count', 0))
            
            table.add_row(tool_name, status, fixed)
        
        self.console.print(table)
        
        if total_fixed > 0:
            self.console.print(f"\n✅ Fixed {total_fixed} issue(s)")
            self.console.print("💡 Run 'tidy check' to verify all issues are resolved")
        
        return f"Fixed {total_fixed} issue(s)"
    
    def _cmd_status(self) -> str:
        """Show current configuration and status"""
        panel_content = []
        
        # Project info
        panel_content.append(f"[bold]Project Information:[/bold]")
        if self.project_info:
            panel_content.append(f"  Type: {self.project_info.get('type', 'Unknown')}")
            panel_content.append(f"  Package Manager: {self.project_info.get('package_manager', 'Unknown')}")
        else:
            panel_content.append(f"  Type: Unknown")
            panel_content.append(f"  Package Manager: Unknown")
        
        # Configured tools
        panel_content.append(f"\n[bold]Configured Tools:[/bold]")
        for category, tool in self.detected_tools.items():
            status = "✅" if tool.get('is_available') else "❌"
            panel_content.append(f"  {status} {category}: {tool['name']}")
        
        # Custom commands
        if self.custom_commands:
            panel_content.append(f"\n[bold]Custom Commands:[/bold]")
            for cmd in self.custom_commands:
                panel_content.append(f"  • {cmd['name']}: {cmd['command']}")
        
        # Settings
        panel_content.append(f"\n[bold]Settings:[/bold]")
        panel_content.append(f"  Auto-fix: {'Yes' if self.settings.get('auto_fix', False) else 'No'}")
        panel_content.append(f"  Strict Mode: {'Yes' if self.settings.get('strict_mode', True) else 'No'}")
        panel_content.append(f"  Parallel Execution: {'Yes' if self.settings.get('parallel_execution', True) else 'No'}")
        panel_content.append(f"  Sidecar Mode: {'Yes' if self.settings.get('use_sidecar', False) else 'No'}")
        
        # Last check
        if self.last_check:
            panel_content.append(f"\n[bold]Last Check:[/bold]")
            panel_content.append(f"  Time: {self.last_check.get('timestamp', 'Never')}")
            
            if 'results' in self.last_check:
                total_issues = sum(
                    r.get('issues_count', 0) 
                    for r in self.last_check['results'].values()
                )
                panel_content.append(f"  Total Issues: {total_issues}")
        
        # Examples
        if self.do_examples or self.dont_examples:
            panel_content.append(f"\n[bold]Learned Patterns:[/bold]")
            panel_content.append(f"  DO examples: {len(self.do_examples)}")
            panel_content.append(f"  DON'T examples: {len(self.dont_examples)}")
        
        panel = Panel(
            "\n".join(panel_content),
            title="🧹 Tidy Extension Status",
            border_style="blue"
        )
        
        self.console.print(panel)
        
        return "Status displayed"
    
    def _cmd_learn(self, args: str) -> str:
        """Add do/don't examples"""
        parts = args.split(None, 1)
        if len(parts) < 2:
            return "Usage: /tidy learn <do|dont> <example>"
        
        learn_type, example = parts
        
        if learn_type.lower() == "do":
            self.do_examples.append(example)
            self.save_config()
            return f"✅ Added DO example: {example}"
        elif learn_type.lower() in ["dont", "don't"]:
            self.dont_examples.append(example)
            self.save_config()
            return f"❌ Added DON'T example: {example}"
        else:
            return "Usage: /tidy learn <do|dont> <example>"
    
    def _cmd_sidecar(self, args: str) -> str:
        """Handle sidecar commands"""
        from .commands.sidecar import TidySidecarCommand
        
        parts = args.split(None, 1)
        action = parts[0] if parts else "status"
        
        # Initialize sidecar command
        sidecar = TidySidecarCommand(logger=self.logger)
        
        # Prepare input data
        input_data = {
            "action": action,
            "working_dir": self.working_dir,
            "detected_tools": self.detected_tools
        }
        
        # Execute sidecar command
        result = sidecar.execute(input_data)
        
        if not result.get("success"):
            error = result.get("error", "Unknown error")
            self.console.print(f"[red]❌ Sidecar error: {error}[/red]")
            return f"Sidecar error: {error}"
        
        # Format response based on action
        if action == "start":
            pid = result.get("pid", "unknown")
            self.console.print(f"[green]✅ Sidecar daemon started (PID: {pid})[/green]")
            self.console.print("🔧 Running fixes in background...")
            self.console.print("Use '/tidy sidecar status' to check progress")
            return f"Sidecar started with PID {pid}"
            
        elif action == "status":
            status = result.get("status", "unknown")
            self.console.print(f"\n[bold]🚗 Sidecar Status: {status}[/bold]")
            
            if status == "completed":
                results = result.get("results", {})
                fixes = results.get("fixes_applied", [])
                if fixes:
                    self.console.print(f"✅ Fixed: {', '.join(fixes)}")
                    self.console.print("Use '/tidy sidecar merge' to apply fixes")
                else:
                    self.console.print("No fixes were applied")
                    
            elif status == "running":
                state = result.get("state", {})
                started = state.get("started_at", "unknown")
                self.console.print(f"Started: {started}")
                
            return result.get("message", "Status checked")
            
        elif action == "stop":
            self.console.print("[yellow]⏹️  Stopping sidecar daemon...[/yellow]")
            return result.get("message", "Sidecar stopped")
            
        elif action == "merge":
            files_updated = result.get("files_updated", 0)
            if files_updated > 0:
                self.console.print(f"[green]✅ Merged {files_updated} fixed files[/green]")
            else:
                self.console.print("No changes to merge")
            return result.get("message", "Merge completed")
            
        else:
            return "Usage: /tidy sidecar <start|status|stop|merge>"


# Main entry point for hook integration and CLI
def main() -> None:
    """CLI interface and hook handler"""
    import sys
    
    if len(sys.argv) < 2:
        # Show help when no command provided
        console = Console()
        console.print("\n[bold]🧹 Tidy Monitor[/bold] - Code Quality Extension\n")
        console.print("[yellow]Usage:[/yellow] tidy_monitor.py <command> [args]\n")
        console.print("[yellow]Commands:[/yellow]")
        console.print("  init       - Initialize tidy for your project")
        console.print("  check      - Run code quality checks")
        console.print("  fix        - Auto-fix code quality issues")
        console.print("  status     - Show current configuration")
        console.print("  learn      - Add do/don't examples")
        console.print("  sidecar    - Manage background fix daemon")
        console.print("  hook       - Handle Claude Code hook (internal)")
        return
    
    command = sys.argv[1]
    
    # Handle hook command specially
    if command == "hook":
        # Read hook input
        hook_input = HookHandler.read_hook_input()
        
        # Get hook event name
        hook_event = hook_input.get('hook_event_name', '')
        
        # Create or get monitor instance
        monitor = TidyMonitor()
        
        # Handle the hook
        response = monitor.handle_hook(hook_event, hook_input)
        
        # Write response
        HookHandler.write_hook_output(response)
    else:
        # Handle slash commands
        monitor = TidyMonitor()
        
        # Get args if any
        args = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""
        
        # Map commands to slash command handlers
        if command == "init":
            result = monitor._cmd_init()
        elif command == "check":
            result = monitor._cmd_check(args)
        elif command == "fix":
            result = monitor._cmd_fix(args)
        elif command == "status":
            result = monitor._cmd_status()
        elif command == "learn":
            result = monitor._cmd_learn(args)
        elif command == "sidecar":
            result = monitor._cmd_sidecar(args)
        else:
            console = Console()
            console.print(f"[red]Unknown command: {command}[/red]")
            console.print("Run 'tidy_monitor.py' for help")
            return


if __name__ == "__main__":
    main()
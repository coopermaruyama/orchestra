#!/usr/bin/env python3
"""
Tidy Monitor for Claude Code

Simplified code quality checker that uses IDE diagnostics via getDiagnostics MCP tool.
Integrates with Claude Code's Stop and SubagentStop hooks.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

# Add parent directory to Python path for imports when run as script
if __name__ == "__main__":
    # When run as a script, add the parent directory to path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(script_dir)
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

# Import from common library
try:
    from orchestra.common import (
        BaseExtension,
        HookHandler,
        format_hook_context,
        setup_logger,
    )
except ImportError:
    # Fallback for when orchestra is not in path
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
    from orchestra.common import (
        BaseExtension,
        HookHandler,
        format_hook_context,
        setup_logger,
    )


class TidyMonitor(BaseExtension):
    """Simplified Tidy extension using IDE diagnostics"""

    def __init__(self, config_path: Optional[str] = None) -> None:
        # Check for recursive Orchestra Claude invocation
        if os.environ.get("ORCHESTRA_CLAUDE_INVOCATION"):
            # We're being called from within an Orchestra Claude invocation
            # Exit silently to prevent recursive loops
            sys.exit(0)
        # Use CLAUDE_WORKING_DIR if available
        working_dir = os.environ.get("CLAUDE_WORKING_DIR", ".")

        # Set up logging
        log_dir = os.path.join(working_dir, ".claude", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "tidy_monitor.log")

        # Configure logger
        self.logger = setup_logger(
            "tidy_monitor", log_file, logging.DEBUG, truncate=True, max_length=300
        )
        self.logger.info("TidyMonitor initialized")

        # Initialize base class
        super().__init__(config_file=config_path, working_dir=working_dir)

        # Initialize console for output
        self.console = Console()

        # Simplified tidy state
        self.last_check: Dict[str, Any] = {}
        self.settings = {
            "strict_mode": True,
            "check_on_file_change": True,
            "ignore_patterns": [
                "*_test.py",
                "*/migrations/*",
                "*/node_modules/*",
                "*.min.js",
                "*/.venv/*",
                "*/.git/*",
            ],
            "max_issues_shown": 10,
            "severity_filter": "Warning",  # Minimum severity: Error, Warning, Information, Hint
        }

        # Modified files tracking
        self.modified_files: List[str] = []

        # Load configuration
        self.load_config()

    def get_default_config_filename(self) -> str:
        """Get the default configuration file name for this extension"""
        return "tidy.json"

    def load_config(self) -> Dict[str, Any]:
        """Load or create configuration"""
        config = super().load_config()

        if config:
            self.last_check = config.get("last_check", {})
            self.settings.update(config.get("settings", {}))

        return config

    def save_config(self, config: Optional[Dict[str, Any]] = None) -> None:
        """Save configuration"""
        if config is None:
            config = {
                "last_check": self.last_check,
                "settings": self.settings,
                "updated": datetime.now().isoformat(),
            }

        super().save_config(config)

    def handle_hook(self, hook_event: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Claude Code hook events"""
        self.logger.info(f"Handling hook event: {hook_event}")
        self.logger.debug(f"Hook context: {format_hook_context(context)}")

        if hook_event == "Stop":
            return self._handle_stop_hook(context)
        if hook_event == "SubagentStop":
            return self._handle_subagent_stop_hook(context)
        if hook_event == "PostToolUse":
            return self._handle_post_tool_use(context)
        if hook_event == "PreCompact":
            return self._handle_pre_compact(context)
        return HookHandler.create_allow_response()

    def _handle_stop_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle Stop hook - check code quality using IDE diagnostics"""
        self.logger.info("Handling Stop hook")

        # Don't run if stop hook is already active (prevent recursion)
        if context.get("stop_hook_active", False):
            self.logger.info("Stop hook already active, skipping")
            return HookHandler.create_allow_response()

        # Check if any files were modified
        if not self.modified_files:
            self.logger.info("No files modified, skipping checks")
            return HookHandler.create_allow_response()

        # Prompt Claude to check and fix issues
        result = self._check_and_prompt_fixes(self.modified_files)

        # Save results
        self.last_check = {
            "timestamp": datetime.now().isoformat(),
            "files_checked": self.modified_files,
            "result": result,
        }
        self.save_config()

        # Clear modified files
        self.modified_files = []

        # Return response based on what happened
        if result.get("action_taken"):
            response = HookHandler.create_allow_response()
            response["output"] = f"🧹 Tidy: {result.get('message', 'Checked and fixed issues')}"
            return response
        return HookHandler.create_allow_response()

    def _handle_subagent_stop_hook(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Handle SubagentStop hook - check code modified by subagent"""
        self.logger.info("Handling SubagentStop hook")

        # Similar to Stop hook but for subagent context
        if not self.modified_files:
            return HookHandler.create_allow_response()

        result = self._check_and_prompt_fixes(self.modified_files)
        self.modified_files = []

        # For subagents, just return allow - don't be as verbose
        return HookHandler.create_allow_response()

    def _handle_post_tool_use(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Track file modifications"""
        tool_name = context.get("tool_name", "")
        tool_input = context.get("tool_input", {})

        # Track files modified by Edit, Write, MultiEdit tools
        if tool_name in ["Edit", "Write", "MultiEdit"]:
            file_path = tool_input.get("file_path", "")
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

        for pattern in self.settings.get("ignore_patterns", []):
            if fnmatch(file_path, pattern):
                return True

        return False

    def _check_and_prompt_fixes(self, files: List[str]) -> Dict[str, Any]:
        """Check for issues and prompt Claude to fix them"""
        self.logger.info(f"Checking and prompting fixes for {len(files)} files")

        try:
            from orchestra.common.claude_invoker import get_invoker

            # Create a focused prompt asking Claude to check for issues and fix them
            file_list = "\n".join(f"- {f}" for f in files)

            prompt = f"""Please check the following files for any code quality issues, linting errors, type errors, or other problems:

{file_list}

Steps:
1. Use the getDiagnostics MCP tool to check for current issues
2. If you find any problems, please fix them
3. Run diagnostics again to verify fixes
4. Report what was found and fixed

Focus on the modified files only and fix any issues you find."""

            invoker = get_invoker()
            result = invoker.invoke_claude(prompt, model=None)  # Use default model

            if result.get("success"):
                self.logger.info("Successfully prompted Claude to check and fix issues")
                return {
                    "success": True,
                    "message": result.get("response", ""),
                    "action_taken": True,
                }
            self.logger.error(f"Failed to prompt Claude: {result.get('error')}")
            return {
                "success": False,
                "message": f"Error: {result.get('error')}",
                "action_taken": False,
            }

        except Exception as e:
            self.logger.error(f"Error prompting Claude for fixes: {e}")
            return {
                "success": False,
                "message": f"Exception: {e}",
                "action_taken": False,
            }

    # Slash command handlers
    def handle_slash_command(self, command: str, args: str = "") -> str:
        """Handle slash commands"""
        if command == "init":
            return self._cmd_init()
        if command == "check":
            return self._cmd_check(args)
        if command == "fix":
            return self._cmd_fix(args)
        if command == "status":
            return self._cmd_status()
        return f"Unknown command: {command}"

    def _cmd_init(self) -> str:
        """Initialize tidy extension"""
        self.console.print("\n[bold]🧹 Tidy Extension Setup[/bold]")

        # Configure basic settings
        self.settings["strict_mode"] = Confirm.ask(
            "Enable strict mode (show issues after each edit)?", default=True
        )

        # Save configuration
        self.save_config()

        self.console.print("✅ Tidy extension initialized!")
        self.console.print("It will now check for issues after you modify files.")

        return "Tidy extension initialized"

    def _cmd_check(self, args: str) -> str:
        """Run code quality checks by prompting Claude"""
        files = args.split() if args else []

        if not files:
            self.console.print(
                "🔍 Asking Claude to check for issues in current project..."
            )
            files = ["current project"]
        else:
            self.console.print(f"🔍 Asking Claude to check {len(files)} file(s)...")

        # Use the same logic as the hook to prompt Claude
        result = self._check_and_prompt_fixes(files)

        if result.get("success"):
            self.console.print("✅ Check complete!")
            return result.get("message", "Check completed")
        self.console.print(f"❌ Error: {result.get('message')}")
        return f"Error: {result.get('message')}"

    def _cmd_fix(self, args: str) -> str:
        """Auto-fix issues by prompting Claude"""
        files = args.split() if args else ["current project"]

        self.console.print("🔧 Asking Claude to find and fix issues...")

        # Use the same logic as check - just prompt Claude to find and fix
        result = self._check_and_prompt_fixes(files)

        if result.get("success"):
            self.console.print("✅ Fix request sent to Claude!")
            return result.get("message", "Fix completed")
        self.console.print(f"❌ Error: {result.get('message')}")
        return f"Error: {result.get('message')}"

    def _cmd_status(self) -> str:
        """Show current configuration and status"""
        panel_content = []

        # Settings
        panel_content.append("[bold]Settings:[/bold]")
        panel_content.append(
            f"  Strict Mode: {'Yes' if self.settings.get('strict_mode', True) else 'No'}"
        )
        panel_content.append(
            f"  Check on File Change: {'Yes' if self.settings.get('check_on_file_change', True) else 'No'}"
        )
        panel_content.append(
            f"  Max Issues Shown: {self.settings.get('max_issues_shown', 10)}"
        )
        panel_content.append(
            f"  Severity Filter: {self.settings.get('severity_filter', 'Warning')}"
        )

        # Ignore patterns
        if self.settings.get("ignore_patterns"):
            panel_content.append("\n[bold]Ignore Patterns:[/bold]")
            for pattern in self.settings["ignore_patterns"]:
                panel_content.append(f"  • {pattern}")

        # Last check
        if self.last_check:
            panel_content.append("\n[bold]Last Check:[/bold]")
            panel_content.append(f"  Time: {self.last_check.get('timestamp', 'Never')}")
            files_checked = self.last_check.get("files_checked", [])
            if files_checked:
                panel_content.append(f"  Files Checked: {len(files_checked)}")

        panel = Panel(
            "\n".join(panel_content),
            title="🧹 Tidy Extension Status",
            border_style="blue",
        )

        self.console.print(panel)

        return "Status displayed"


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
        console.print("  hook       - Handle Claude Code hook (internal)")
        return

    command = sys.argv[1]

    # Handle hook command specially
    if command == "hook":
        # Read hook input
        hook_input = HookHandler.read_hook_input()

        # Get hook event name
        hook_event = hook_input.get("hook_event_name", "")

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
        else:
            console = Console()
            console.print(f"[red]Unknown command: {command}[/red]")
            console.print("Run 'tidy_monitor.py' for help")
            return


if __name__ == "__main__":
    main()

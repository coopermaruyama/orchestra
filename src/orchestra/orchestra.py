#!/usr/bin/env python3
"""
Orchestra - Claude Code Extension Manager
Orchestrate your Claude Code workflow with focused extensions
"""

import sys
import os
import json
import shutil
from pathlib import Path
from typing import Dict, Any
from rich.console import Console
from rich.table import Table



class Orchestra:
    def __init__(self) -> None:
        self.__version__ = "0.6.0"
        self.home = Path.home()
        self.global_dir = self.home / ".claude" / "commands"
        self.local_dir = Path(".claude") / "commands"
        self.console = Console()

        # Available extensions registry
        self.extensions = {
            "task": {
                "name": "Task Monitor",
                "description": "Keep Claude focused on your task requirements. Prevents scope creep, tracks progress, and guides you through requirements step by step.",
                "commands": ["task start", "task progress", "task next", "task complete", "focus"],
                "features": [
                    "Blocks off-topic commands",
                    "Warns about scope creep",
                    "Tracks progress automatically",
                    "Guides through requirements"
                ]
            },
            "timemachine": {
                "name": "TimeMachine",
                "description": "Automatic git checkpointing for every conversation turn. Travel back in time to any previous state with full prompt history.",
                "commands": ["timemachine list", "timemachine checkout", "timemachine view", "timemachine rollback"],
                "features": [
                    "Checkpoint every user prompt",
                    "View conversation history",
                    "Rollback to any previous state",
                    "Track file modifications per turn"
                ]
            },
            "tester": {
                "name": "Tester",
                "description": "Automatically test completed tasks using calibrated testing methods. Learns your project's testing approach through interactive calibration.",
                "commands": ["tester calibrate", "tester test", "tester status"],
                "features": [
                    "Interactive calibration to learn test methods",
                    "Automatic test execution on task completion",
                    "Browser testing with Chrome automation",
                    "Smart test selection based on changes"
                ]
            }
        }

    def enable(self, extension: str, scope: str = "global") -> None:
        """Enable an Orchestra extension"""
        if extension not in self.extensions:
            self.console.print(f"[bold red]❌ Unknown extension:[/bold red] {extension}")
            self.console.print("[yellow]Available extensions:[/yellow]")
            for ext_id, ext_info in self.extensions.items():
                self.console.print(f"  • {ext_id} - {ext_info['name']}")
            return

        # Determine enablement directory
        if scope == "global":
            commands_dir = self.global_dir
            scripts_dir = self.home / ".claude" / "orchestra" / extension
        else:
            commands_dir = self.local_dir
            scripts_dir = Path(".claude") / "orchestra" / extension

            # Warning for project scope enablement
            self.console.print("\n[bold yellow]⚠️  Warning: Project scope enablement[/bold yellow]")
            self.console.print("[yellow]Enabling in project scope (.claude/commands/) may conflict with global enablement.[/yellow]")
            self.console.print("[yellow]Claude Code does not support conflicts between user and project level commands.[/yellow]")
            self.console.print("[yellow]Consider using global enablement (default) unless project-specific commands are required.[/yellow]\n")

        # Create directories
        commands_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # Create shell bootstrap script
        bootstrap_dest = scripts_dir.parent / "bootstrap.sh"
        bootstrap_content = '''#!/bin/sh
# Orchestra Bootstrap Script

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to find python executable
find_python() {
    if command_exists python3; then
        echo "python3"
    elif command_exists python; then
        echo "python"
    else
        echo ""
    fi
}

# Function to check if orchestra is installed
check_orchestra_installed() {
    command_exists orchestra
}

# Function to show install instructions
show_install_instructions() {
    FLAG_FILE="$HOME/.claude/.orchestra-install-shown"
    if [ -f "$FLAG_FILE" ]; then
        return
    fi

    echo "============================================================"
    echo "🎼 Orchestra not installed"
    echo "============================================================"
    echo ""
    echo "This project uses Orchestra extensions for Claude Code."
    echo ""
    echo "To install Orchestra globally:"
    echo "  pip install orchestra"
    echo ""
    echo "Or install from the project:"
    echo "  pip install -e ."
    echo ""
    echo "Then enable the task extension:"
    echo "  orchestra enable task"
    echo ""
    echo "For more info: https://github.com/anthropics/orchestra"
    echo "============================================================"

    mkdir -p "$(dirname "$FLAG_FILE")"
    touch "$FLAG_FILE"
}

# Main execution
if [ $# -lt 1 ]; then
    echo "Usage: bootstrap.sh <command> [args...]"
    exit 1
fi

# For hook commands, we need to run the Python script directly
if [ "$1" = "hook" ]; then
    PYTHON=$(find_python)
    if [ -z "$PYTHON" ]; then
        echo "Error: Python not found in PATH" >&2
        exit 127
    fi

    # Determine which extension is being called based on which scripts exist
    SCRIPT_DIR="$(dirname "$0")"
    MONITOR_SCRIPT=""

    # Check for task monitor
    LOCAL_TASK="$SCRIPT_DIR/task/task_monitor.py"
    GLOBAL_TASK="$HOME/.claude/orchestra/task/task_monitor.py"

    # Check for timemachine monitor
    LOCAL_TM="$SCRIPT_DIR/timemachine/timemachine_monitor.py"
    GLOBAL_TM="$HOME/.claude/orchestra/timemachine/timemachine_monitor.py"

    # Check for tester monitor
    LOCAL_TESTER="$SCRIPT_DIR/tester/tester_monitor.py"
    GLOBAL_TESTER="$HOME/.claude/orchestra/tester/tester_monitor.py"

    # Priority: local task, global task, local timemachine, global timemachine, local tester, global tester
    if [ -f "$LOCAL_TASK" ]; then
        MONITOR_SCRIPT="$LOCAL_TASK"
    elif [ -f "$GLOBAL_TASK" ]; then
        MONITOR_SCRIPT="$GLOBAL_TASK"
    elif [ -f "$LOCAL_TM" ]; then
        MONITOR_SCRIPT="$LOCAL_TM"
    elif [ -f "$GLOBAL_TM" ]; then
        MONITOR_SCRIPT="$GLOBAL_TM"
    elif [ -f "$LOCAL_TESTER" ]; then
        MONITOR_SCRIPT="$LOCAL_TESTER"
    elif [ -f "$GLOBAL_TESTER" ]; then
        MONITOR_SCRIPT="$GLOBAL_TESTER"
    else
        echo "Error: No monitor script found" >&2
        exit 1
    fi

    # Execute the hook
    exec "$PYTHON" "$MONITOR_SCRIPT" "$@"
fi

# For regular commands, check if orchestra is installed
if ! check_orchestra_installed; then
    show_install_instructions
    exit 1
fi

# Run orchestra with the provided arguments
exec orchestra "$@"
'''
        with open(bootstrap_dest, 'w') as f:
            f.write(bootstrap_content)

        bootstrap_dest.chmod(0o755)

        # Copy the extension script and its dependencies
        if extension == "task":
            monitor_source = Path(__file__).parent / "extensions" / "task" / "task_monitor.py"
            monitor_dest = scripts_dir / "task_monitor.py"
        elif extension == "timemachine":
            monitor_source = Path(__file__).parent / "extensions" / "timemachine" / "timemachine_monitor.py"
            monitor_dest = scripts_dir / "timemachine_monitor.py"
        elif extension == "tester":
            monitor_source = Path(__file__).parent / "extensions" / "tester" / "tester_monitor.py"
            monitor_dest = scripts_dir / "tester_monitor.py"
        else:
            self.console.print(f"[bold red]⚠️ Warning:[/bold red] No monitor script configured for {extension}")
            return

        # Copy main script
        if monitor_source.exists():
            shutil.copy(monitor_source, monitor_dest)
            monitor_dest.chmod(0o755)
        else:
            self.console.print(f"[bold red]⚠️ Warning:[/bold red] {monitor_source.name} not found at {monitor_source}")
            return

        # Copy orchestra.common library for dependencies
        common_source = Path(__file__).parent / "common"
        orchestra_dest = scripts_dir / "orchestra"
        common_dest = orchestra_dest / "common"

        if common_source.exists():
            # Create orchestra package directory
            orchestra_dest.mkdir(exist_ok=True)

            # Create orchestra/__init__.py
            (orchestra_dest / "__init__.py").write_text('"""Orchestra package"""')

            # Copy common directory
            if common_dest.exists():
                shutil.rmtree(common_dest)
            shutil.copytree(common_source, common_dest)

            # Make git-wip executable
            git_wip_path = common_dest / "git-wip"
            if git_wip_path.exists():
                git_wip_path.chmod(0o755)
                self.console.print(f"[bold]🔧 Made git-wip executable[/bold]")

            self.console.print(f"[bold]📦 Bundled orchestra.common library[/bold]")
        else:
            self.console.print(f"[bold red]⚠️ Warning:[/bold red] orchestra.common not found at {common_source}")

        # Install subagents for intelligent deviation detection
        self._install_subagents(extension, scope)

        # Create extension-specific commands
        if scope == "global":
            bootstrap_path = "$HOME/.claude/orchestra/bootstrap.sh"
        else:
            bootstrap_path = ".claude/orchestra/bootstrap.sh"

        if extension == "task":
            # Create the task directory for sub-commands
            task_dir = commands_dir / "task"
            task_dir.mkdir(parents=True, exist_ok=True)

            commands = {
                "start": {
                    "description": "Start a new task with intelligent guided setup",
                    "script": f"!sh {bootstrap_path} task start"
                },
                "progress": {
                    "description": "Check current task progress and see what's been completed",
                    "script": f"!sh {bootstrap_path} task status"
                },
                "next": {
                    "description": "Show the next priority action to work on",
                    "script": f"!sh {bootstrap_path} task next"
                },
                "complete": {
                    "description": "Mark the current requirement as complete and see what's next",
                    "script": f"!sh {bootstrap_path} task complete"
                }
            }

            # Write individual command files
            for cmd_name, cmd_info in commands.items():
                cmd_content = f"""---
allowed-tools: Bash(*)
description: {cmd_info['description']}
---

{cmd_info['script']}

<!-- AUTO-GENERATED BY ORCHESTRA: {extension} -->"""

                with open(task_dir / f"{cmd_name}.md", 'w') as f:
                    f.write(cmd_content)

            # Also create a /focus command at the root level
            focus_content = f"""---
allowed-tools: Bash(*)
description: Quick reminder of what you should be working on right now
---

!sh {bootstrap_path} task focus

<!-- AUTO-GENERATED BY ORCHESTRA: {extension} -->"""

            with open(commands_dir / "focus.md", 'w') as f:
                f.write(focus_content)

        elif extension == "timemachine":
            # Create the timemachine directory for sub-commands
            tm_dir = commands_dir / "timemachine"
            tm_dir.mkdir(parents=True, exist_ok=True)

            commands = {
                "list": {
                    "description": "View a list of conversation checkpoints",
                    "script": f"!sh {bootstrap_path} timemachine list"
                },
                "checkout": {
                    "description": "Checkout a specific checkpoint by ID",
                    "script": f"!sh {bootstrap_path} timemachine checkout $ARGUMENTS"
                },
                "view": {
                    "description": "View full details of a checkpoint",
                    "script": f"!sh {bootstrap_path} timemachine view $ARGUMENTS"
                },
                "rollback": {
                    "description": "Rollback n conversation turns",
                    "script": f"!sh {bootstrap_path} timemachine rollback $ARGUMENTS"
                }
            }

            # Write individual command files
            for cmd_name, cmd_info in commands.items():
                cmd_content = f"""---
allowed-tools: Bash(*)
description: {cmd_info['description']}
---

{cmd_info['script']}

<!-- AUTO-GENERATED BY ORCHESTRA: {extension} -->"""

                with open(tm_dir / f"{cmd_name}.md", 'w') as f:
                    f.write(cmd_content)

        elif extension == "tester":
            # Create the tester directory for sub-commands
            tester_dir = commands_dir / "tester"
            tester_dir.mkdir(parents=True, exist_ok=True)

            commands = {
                "calibrate": {
                    "description": "Set up testing for your project through interactive calibration",
                    "script": f"!sh {bootstrap_path} tester calibrate"
                },
                "test": {
                    "description": "Run tests for completed tasks",
                    "script": f"!sh {bootstrap_path} tester test"
                },
                "status": {
                    "description": "Show calibration status and test results",
                    "script": f"!sh {bootstrap_path} tester status"
                }
            }

            # Write individual command files
            for cmd_name, cmd_info in commands.items():
                cmd_content = f"""---
allowed-tools: Bash(*)
description: {cmd_info['description']}
---

{cmd_info['script']}

<!-- AUTO-GENERATED BY ORCHESTRA: {extension} -->"""

                with open(tester_dir / f"{cmd_name}.md", 'w') as f:
                    f.write(cmd_content)

        # Create hooks configuration for Claude Code settings format
        # Both extensions use the same hooks - the bootstrap script determines which one runs
        hooks_config = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"sh {bootstrap_path} hook PreToolUse"
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
                                "command": f"sh {bootstrap_path} hook PostToolUse"
                            }
                        ]
                    }
                ],
                "UserPromptSubmit": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"sh {bootstrap_path} hook UserPromptSubmit"
                            }
                        ]
                    }
                ],
                # "TodoWrite": [
                #     {
                #         "matcher": "*",
                #         "hooks": [
                #             {
                #                 "type": "command",
                #                 "command": f"sh {bootstrap_path} hook TodoWrite"
                #             }
                #         ]
                #     }
                # ],
                # "Task": [
                #     {
                #         "matcher": "*",
                #         "hooks": [
                #             {
                #                 "type": "command",
                #                 "command": f"sh {bootstrap_path} hook Task"
                #             }
                #         ]
                #     }
                # ],
                "Stop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"sh {bootstrap_path} hook Stop"
                            }
                        ]
                    }
                ],
                "SubagentStop": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"sh {bootstrap_path} hook SubagentStop"
                            }
                        ]
                    }
                ]
            }
        }

        # Write or update settings file with hooks
        settings_file = commands_dir.parent / "settings.json"
        if settings_file.exists():
            with open(settings_file, 'r') as f:
                existing_settings: Dict[str, Any] = json.load(f)
        else:
            existing_settings = {
                "$schema": "https://json.schemastore.org/claude-code-settings.json"
            }

        # Merge hooks configuration
        if "hooks" in existing_settings:
            # Update existing hooks
            for event_name, event_hooks in hooks_config["hooks"].items():
                existing_settings["hooks"][event_name] = event_hooks
        else:
            existing_settings["hooks"] = hooks_config["hooks"]

        with open(settings_file, 'w') as f:
            json.dump(existing_settings, f, indent=2)

        self.console.print(f"[bold green]✅ Enabled {extension}[/bold green] ({scope} scope)")
        self.console.print(f"[bold]📁 Commands:[/bold]")

        if extension == "task":
            self.console.print(f"   [dim]-[/dim] {commands_dir / 'task'}/*.md (sub-commands)")
            self.console.print(f"   [dim]-[/dim] {commands_dir / 'focus.md'}")
            start_cmd = "/task start"
        elif extension == "timemachine":
            self.console.print(f"   [dim]-[/dim] {commands_dir / 'timemachine'}/*.md (sub-commands)")
            start_cmd = "/timemachine list"
        elif extension == "tester":
            self.console.print(f"   [dim]-[/dim] {commands_dir / 'tester'}/*.md (sub-commands)")
            start_cmd = "/tester calibrate"

        self.console.print(f"[bold]🚀 Bootstrap:[/bold] {scripts_dir.parent / 'bootstrap.sh'}")
        self.console.print(f"[bold]🪝 Hooks:[/bold] Configured in {settings_file}")
        self.console.print(f"\n[bold yellow]🎯 Start with:[/bold yellow] [cyan]{start_cmd}[/cyan]")
        self.console.print(f"\n[dim]Note: Commands will work for team members even without Orchestra installed[/dim]")

    def _install_subagents(self, extension: str, scope: str) -> None:
        """Install subagents for an extension"""
        if extension not in ["task", "tester"]:
            return  # Only task and tester use subagents

        # Determine agents directory
        if scope == "global":
            agents_dir = self.home / ".claude" / "agents"
        else:
            agents_dir = Path(".claude") / "agents"

        agents_dir.mkdir(parents=True, exist_ok=True)

        # Copy subagent templates
        source_agents_dir = Path(__file__).parent / "extensions" / "task" / "agents"
        if source_agents_dir.exists():
            agent_count = 0
            for agent_file in source_agents_dir.glob("*.md"):
                dest_file = agents_dir / agent_file.name
                shutil.copy(agent_file, dest_file)
                agent_count += 1

            if agent_count > 0:
                self.console.print(f"[bold green]🤖 Installed {agent_count} subagents[/bold green] for intelligent deviation detection")

    def list_extensions(self) -> None:
        """List enabled extensions"""
        self.console.print("[bold blue]🎼 Orchestra Extensions[/bold blue]\n")

        # Check global extensions
        if self.global_dir.exists():
            global_exts = [f.stem for f in self.global_dir.glob("*.md")]
            if global_exts:
                self.console.print("[bold yellow]Global extensions:[/bold yellow]")
                for ext in global_exts:
                    self.console.print(f"  [green]•[/green] {ext}")
                self.console.print()

        # Check local extensions
        if self.local_dir.exists():
            local_exts = [f.stem for f in self.local_dir.glob("*.md")]
            if local_exts:
                self.console.print("[bold yellow]Local extensions:[/bold yellow]")
                for ext in local_exts:
                    self.console.print(f"  [green]•[/green] {ext}")
                self.console.print()

        self.console.print("[bold yellow]Available to enable:[/bold yellow]")
        for ext_id, ext_info in self.extensions.items():
            # Check if already installed
            local_installed = (self.local_dir / "task" if ext_id == "task" else self.local_dir / ext_id).exists()
            global_installed = (self.global_dir / "task" if ext_id == "task" else self.global_dir / ext_id).exists()

            if not local_installed and not global_installed:
                self.console.print(f"  [dim]•[/dim] {ext_id} : [italic]{ext_info['description'][:60]}...[/italic]")

    def disable(self, extension: str, scope: str = "global") -> None:
        """Disable an extension"""
        if scope == "global":
            commands_dir = self.global_dir
            scripts_dir = self.home / ".claude" / "orchestra" / extension
            agents_dir = self.home / ".claude" / "agents"
        else:
            commands_dir = self.local_dir
            scripts_dir = Path(".claude") / "orchestra" / extension
            agents_dir = Path(".claude") / "agents"

        removed = False

        # Helper function to check if file was generated by Orchestra
        def is_orchestra_generated(file_path: Path, expected_extension: str) -> bool:
            """Check if a file has the Orchestra auto-generated comment"""
            if not file_path.exists():
                return False

            try:
                with open(file_path, 'r') as f:
                    content = f.read().strip()
                    # Check if the file ends with the auto-generated comment
                    return content.endswith(f"<!-- AUTO-GENERATED BY ORCHESTRA: {expected_extension} -->")
            except Exception:
                return False

        # Remove command files if they were generated by Orchestra
        if extension == "task":
            # Remove task sub-commands
            task_dir = commands_dir / "task"
            if task_dir.exists() and task_dir.is_dir():
                removed_count = 0
                for cmd_file in task_dir.glob("*.md"):
                    if is_orchestra_generated(cmd_file, extension):
                        cmd_file.unlink()
                        removed_count += 1
                        removed = True

                # Remove the task directory if it's empty
                if removed_count > 0 and not any(task_dir.iterdir()):
                    task_dir.rmdir()

            # Remove focus.md if it was generated by Orchestra
            focus_file = commands_dir / "focus.md"
            if is_orchestra_generated(focus_file, extension):
                focus_file.unlink()
                removed = True

        elif extension == "timemachine":
            # Remove timemachine sub-commands
            tm_dir = commands_dir / "timemachine"
            if tm_dir.exists() and tm_dir.is_dir():
                removed_count = 0
                for cmd_file in tm_dir.glob("*.md"):
                    if is_orchestra_generated(cmd_file, extension):
                        cmd_file.unlink()
                        removed_count += 1
                        removed = True

                # Remove the timemachine directory if it's empty
                if removed_count > 0 and not any(tm_dir.iterdir()):
                    tm_dir.rmdir()

        elif extension == "tester":
            # Remove tester sub-commands
            tester_dir = commands_dir / "tester"
            if tester_dir.exists() and tester_dir.is_dir():
                removed_count = 0
                for cmd_file in tester_dir.glob("*.md"):
                    if is_orchestra_generated(cmd_file, extension):
                        cmd_file.unlink()
                        removed_count += 1
                        removed = True

                # Remove the tester directory if it's empty
                if removed_count > 0 and not any(tester_dir.iterdir()):
                    tester_dir.rmdir()

        # Remove subagents if they were generated by Orchestra
        if agents_dir.exists():
            if extension == "task":
                agent_files = ["off-topic-detector.md", "over-engineering-detector.md", "scope-creep-detector.md"]
                content_check = lambda c: "Orchestra Task Monitor" in c or "scope creep" in c
            elif extension == "tester":
                agent_files = ["test-calibrator.md", "test-runner.md"]
                content_check = lambda c: "Test Calibrator" in c or "Test Runner" in c
            else:
                agent_files = []
                content_check = lambda c: False

            for agent_file in agent_files:
                agent_path = agents_dir / agent_file
                if agent_path.exists():
                    try:
                        with open(agent_path, 'r') as f:
                            # Check if it's our agent by looking for specific content
                            content = f.read()
                            if content_check(content):
                                agent_path.unlink()
                                removed = True
                    except Exception:
                        pass

        # Remove scripts directory (always safe to remove as it's only for Orchestra)
        if scripts_dir.exists():
            shutil.rmtree(scripts_dir)
            removed = True

        # Remove bootstrap.sh if no other extensions are using it
        bootstrap_path = scripts_dir.parent / "bootstrap.sh"
        if bootstrap_path.exists():
            # Check if any other extension directories exist
            orchestra_dir = scripts_dir.parent
            other_extensions = [d for d in orchestra_dir.iterdir()
                              if d.is_dir() and d.name != extension and d.name != "bootstrap.sh"]

            if not other_extensions:
                bootstrap_path.unlink()
                # Remove orchestra directory if empty
                if not any(orchestra_dir.iterdir()):
                    orchestra_dir.rmdir()

        # Clean up hooks from settings.json
        settings_file = commands_dir.parent / "settings.json"
        if settings_file.exists() and extension == "task":
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)

                if "hooks" in settings:
                    # Remove task specific hooks
                    bootstrap_command = f"sh {bootstrap_path} hook"

                    for event_name in ["PreToolUse", "PostToolUse", "UserPromptSubmit", "Stop", "SubagentStop"]:
                        if event_name in settings["hooks"]:
                            # Filter out Orchestra hooks
                            if isinstance(settings["hooks"][event_name], list):
                                settings["hooks"][event_name] = [
                                    hook for hook in settings["hooks"][event_name]
                                    if not (isinstance(hook, dict) and
                                           hook.get("hooks", [{}])[0].get("command", "").startswith(bootstrap_command))
                                ]

                                # Remove empty hook arrays
                                if not settings["hooks"][event_name]:
                                    del settings["hooks"][event_name]

                    # Remove hooks key if empty
                    if not settings["hooks"]:
                        del settings["hooks"]

                # Write back the cleaned settings
                with open(settings_file, 'w') as f:
                    json.dump(settings, f, indent=2)

            except Exception as e:
                self.console.print(f"[yellow]⚠️ Warning: Could not clean up hooks from settings.json: {e}[/yellow]")

        if removed:
            self.console.print(f"[bold green]✅ Disabled {extension}[/bold green]")
        else:
            self.console.print(f"[bold red]❌ Extension not found:[/bold red] {extension}")

def main() -> None:
    console = Console()

    if len(sys.argv) < 2:
        # Title
        console.print("\n[bold blue]🎼 Orchestra[/bold blue] - [italic]Claude Code Extension Manager[/italic]\n")

        # Usage
        console.print("[bold yellow]Usage:[/bold yellow] orchestra <command> [options]\n")

        # Commands table
        commands_table = Table(show_header=False, box=None, padding=(0, 2))
        commands_table.add_column("Command", style="bold cyan")
        commands_table.add_column("Description")

        console.print("[bold yellow]Commands:[/bold yellow]")
        commands_table.add_row("enable [extension] [--project]", "Enable an extension or all if none specified")
        commands_table.add_row("disable <extension> [--project]", "Disable an extension (default: global)")
        commands_table.add_row("list", "List enabled extensions")
        commands_table.add_row("logs [extension] [options]", "View or manage extension logs")
        commands_table.add_row("task <subcommand>", "Run task monitor commands")
        commands_table.add_row("timemachine <subcommand>", "Run timemachine commands")
        commands_table.add_row("tester <subcommand>", "Run tester commands")
        console.print(commands_table)

        # Task subcommands
        console.print("\n[bold yellow]Task Monitor Commands:[/bold yellow]")
        task_table = Table(show_header=False, box=None, padding=(0, 2))
        task_table.add_column("Subcommand", style="bold green")
        task_table.add_column("Description")

        task_table.add_row("start", "Interactive task setup")
        task_table.add_row("status", "Check current progress")
        task_table.add_row("next", "Show next priority action")
        task_table.add_row("complete", "Mark current requirement done")
        task_table.add_row("focus", "Quick focus reminder")
        console.print(task_table)

        # TimeMachine subcommands
        console.print("\n[bold yellow]TimeMachine Commands:[/bold yellow]")
        tm_table = Table(show_header=False, box=None, padding=(0, 2))
        tm_table.add_column("Subcommand", style="bold green")
        tm_table.add_column("Description")

        tm_table.add_row("list", "View conversation checkpoints")
        tm_table.add_row("checkout <id>", "Checkout a specific checkpoint")
        tm_table.add_row("view <id>", "View checkpoint details")
        tm_table.add_row("rollback <n>", "Rollback n conversation turns")
        console.print(tm_table)

        # Tester subcommands
        console.print("\n[bold yellow]Tester Commands:[/bold yellow]")
        tester_table = Table(show_header=False, box=None, padding=(0, 2))
        tester_table.add_column("Subcommand", style="bold green")
        tester_table.add_column("Description")

        tester_table.add_row("calibrate", "Set up testing through interactive calibration")
        tester_table.add_row("test", "Run tests for completed tasks")
        tester_table.add_row("status", "Show calibration status and test results")
        console.print(tester_table)

        # Available Extensions
        console.print("\n[bold yellow]Available Extensions:[/bold yellow]")
        extensions_table = Table(show_header=False, box=None, padding=(0, 2))
        extensions_table.add_column("Extension", style="bold magenta")
        extensions_table.add_column("Description")

        # Get extensions from Orchestra instance
        temp_orchestra = Orchestra()
        for ext_id, ext_info in temp_orchestra.extensions.items():
            extensions_table.add_row(
                ext_id,
                str(ext_info['description'])
            )
        console.print(extensions_table)

        # Examples
        console.print("\n[bold yellow]Examples:[/bold yellow]")
        console.print("  [dim]$[/dim] orchestra enable           # Enable all extensions")
        console.print("  [dim]$[/dim] orchestra enable task      # Enable specific extension")
        console.print("  [dim]$[/dim] orchestra enable task --project")
        console.print("  [dim]$[/dim] orchestra task start")
        console.print("  [dim]$[/dim] orchestra task status\n")
        return

    orchestra = Orchestra()
    command = sys.argv[1]
    if command == "version":
        console.print(f"[bold blue]Orchestra Version:[/bold blue] {orchestra.__version__}")
        return
    if command == "enable":
        if len(sys.argv) < 3:
            # No extension specified, enable all
            console.print("[bold blue]🎼 Enabling all Orchestra extensions...[/bold blue]\n")
            scope = "global"  # Default to global
            
            # Enable each extension
            for ext_id in orchestra.extensions.keys():
                console.print(f"\n[bold cyan]📦 Enabling {ext_id}...[/bold cyan]")
                orchestra.enable(ext_id, scope)
            
            console.print("\n[bold green]✨ All extensions enabled![/bold green]")
            console.print("\n[bold yellow]Quick start commands:[/bold yellow]")
            console.print("  [cyan]/task start[/cyan]         - Start a new focused task")
            console.print("  [cyan]/timemachine list[/cyan]   - View conversation checkpoints")
            console.print("  [cyan]/tester calibrate[/cyan]   - Set up testing for your project")
            return

        extension = sys.argv[2]
        scope = "local" if "--project" in sys.argv else "global"
        orchestra.enable(extension, scope)

    elif command == "disable":
        if len(sys.argv) < 3:
            console.print("[bold yellow]Usage:[/bold yellow] orchestra disable <extension> [--project]")
            console.print("[dim]Default: Disables from global scope (~/.claude/commands/)[/dim]")
            return

        extension = sys.argv[2]
        scope = "local" if "--project" in sys.argv else "global"
        orchestra.disable(extension, scope)

    elif command == "list":
        orchestra.list_extensions()

    elif command == "task":
        # Direct task command execution
        if len(sys.argv) < 3:
            console.print("\n[bold yellow]Usage:[/bold yellow] orchestra task <subcommand>\n")

            console.print("[bold yellow]Subcommands:[/bold yellow]")
            subcommands_table = Table(show_header=False, box=None, padding=(0, 2))
            subcommands_table.add_column("Command", style="bold green")
            subcommands_table.add_column("Description")

            subcommands_table.add_row("start", "Interactive task setup")
            subcommands_table.add_row("status", "Check current progress")
            subcommands_table.add_row("next", "Show next priority action")
            subcommands_table.add_row("complete", "Mark current requirement done")
            subcommands_table.add_row("focus", "Quick focus reminder")

            console.print(subcommands_table)
            console.print()
            return

        subcommand = sys.argv[2]

        # Find the task_monitor.py script
        local_script = Path(".claude") / "orchestra" / "task" / "task_monitor.py"
        global_script = Path.home() / ".claude" / "orchestra" / "task" / "task_monitor.py"

        script_path = None
        if local_script.exists():
            script_path = local_script
        elif global_script.exists():
            script_path = global_script
        else:
            console.print("[bold red]❌ Task monitor not enabled.[/bold red] Run: [cyan]orchestra enable task[/cyan]")
            return

        # Execute the task monitor script with the subcommand
        import subprocess
        try:
            # Pass through any additional arguments
            args = [sys.executable, str(script_path), subcommand] + sys.argv[3:]
            subprocess.run(args, check=False)
        except Exception as e:
            console.print(f"[bold red]❌ Error running task command:[/bold red] {e}")

    elif command == "timemachine":
        # Direct timemachine command execution
        if len(sys.argv) < 3:
            console.print("\n[bold yellow]Usage:[/bold yellow] orchestra timemachine <subcommand>\n")

            console.print("[bold yellow]Subcommands:[/bold yellow]")
            subcommands_table = Table(show_header=False, box=None, padding=(0, 2))
            subcommands_table.add_column("Command", style="bold green")
            subcommands_table.add_column("Description")

            subcommands_table.add_row("list", "View conversation checkpoints")
            subcommands_table.add_row("checkout <id>", "Checkout a specific checkpoint")
            subcommands_table.add_row("view <id>", "View checkpoint details")
            subcommands_table.add_row("rollback <n>", "Rollback n conversation turns")

            console.print(subcommands_table)
            console.print()
            return

        subcommand = sys.argv[2]

        # Find the timemachine_monitor.py script
        local_script = Path(".claude") / "orchestra" / "timemachine" / "timemachine_monitor.py"
        global_script = Path.home() / ".claude" / "orchestra" / "timemachine" / "timemachine_monitor.py"

        script_path = None
        if local_script.exists():
            script_path = local_script
        elif global_script.exists():
            script_path = global_script
        else:
            console.print("[bold red]❌ TimeMachine not enabled.[/bold red] Run: [cyan]orchestra enable timemachine[/cyan]")
            return

        # Execute the timemachine monitor script with the subcommand
        import subprocess
        try:
            # Pass through any additional arguments
            args = [sys.executable, str(script_path), subcommand] + sys.argv[3:]
            subprocess.run(args, check=False)
        except Exception as e:
            console.print(f"[bold red]❌ Error running timemachine command:[/bold red] {e}")

    elif command == "tester":
        # Direct tester command execution
        if len(sys.argv) < 3:
            console.print("\n[bold yellow]Usage:[/bold yellow] orchestra tester <subcommand>\n")

            console.print("[bold yellow]Subcommands:[/bold yellow]")
            subcommands_table = Table(show_header=False, box=None, padding=(0, 2))
            subcommands_table.add_column("Command", style="bold green")
            subcommands_table.add_column("Description")

            subcommands_table.add_row("calibrate", "Set up testing for your project through interactive calibration")
            subcommands_table.add_row("test", "Run tests for completed tasks")
            subcommands_table.add_row("status", "Show calibration status and test results")

            console.print(subcommands_table)
            console.print()
            return

        subcommand = sys.argv[2]

        # Find the tester_monitor.py script
        local_script = Path(".claude") / "orchestra" / "tester" / "tester_monitor.py"
        global_script = Path.home() / ".claude" / "orchestra" / "tester" / "tester_monitor.py"

        script_path = None
        if local_script.exists():
            script_path = local_script
        elif global_script.exists():
            script_path = global_script
        else:
            console.print("[bold red]❌ Tester not enabled.[/bold red] Run: [cyan]orchestra enable tester[/cyan]")
            return

        # Execute the tester monitor script with the subcommand
        import subprocess
        try:
            # Pass through any additional arguments
            args = [sys.executable, str(script_path), subcommand] + sys.argv[3:]
            subprocess.run(args, check=False)
        except Exception as e:
            console.print(f"[bold red]❌ Error running tester command:[/bold red] {e}")

    elif command == "logs":
        # View extension logs
        import subprocess

        # Parse arguments
        extension_filter = None
        tail_mode = False
        clear_logs = False

        for arg in sys.argv[2:]:
            if arg == "--tail" or arg == "-f":
                tail_mode = True
            elif arg == "--clear":
                clear_logs = True
            elif arg == "--help" or arg == "-h":
                console.print("\n[bold yellow]Usage:[/bold yellow] orchestra logs [extension] [--tail] [--clear]\n")
                console.print("[bold yellow]Options:[/bold yellow]")
                console.print("  [dim]extension[/dim]  Filter logs for specific extension (task, timemachine)")
                console.print("  [dim]--tail[/dim]     Follow log output (like tail -f)")
                console.print("  [dim]--clear[/dim]    Clear all Orchestra logs")
                console.print("\n[bold yellow]Examples:[/bold yellow]")
                console.print("  [dim]$[/dim] orchestra logs           # View all logs")
                console.print("  [dim]$[/dim] orchestra logs task      # View task monitor logs")
                console.print("  [dim]$[/dim] orchestra logs --tail    # Follow all logs")
                console.print("  [dim]$[/dim] orchestra logs --clear   # Clear all logs\n")
                return
            elif not arg.startswith("-"):
                extension_filter = arg

        # Find log files
        log_patterns = []
        if extension_filter:
            if extension_filter == "task":
                log_patterns.append("task_monitor.log")
            elif extension_filter == "timemachine":
                log_patterns.append("timemachine.log")
            else:
                console.print(f"[bold red]❌ Unknown extension:[/bold red] {extension_filter}")
                console.print("[dim]Valid extensions: task, timemachine[/dim]")
                return
        else:
            # Look for all Orchestra logs
            log_patterns.extend(["task_monitor.log", "timemachine.log"])

        # Search for log files in common temp directories
        import platform

        log_files = []
        temp_roots = []

        if platform.system() == "Darwin":  # macOS
            temp_roots.append("/var/folders")
            temp_roots.append("/tmp")
        elif platform.system() == "Linux":
            temp_roots.append("/tmp")
            temp_roots.append("/var/tmp")
        elif platform.system() == "Windows":
            temp_roots.append(os.environ.get("TEMP", ""))
            temp_roots.append(os.environ.get("TMP", ""))

        # Find log files
        for root in temp_roots:
            if not root or not os.path.exists(root):
                continue

            try:
                # Use find command for efficiency
                for pattern in log_patterns:
                    if platform.system() == "Windows":
                        # Windows find command is different
                        cmd = ["where", "/r", root, pattern]
                    else:
                        # Unix-like find command
                        cmd = ["find", root, "-name", pattern, "-type", "f"]

                    result = subprocess.run(cmd, capture_output=True, text=True, stderr=subprocess.DEVNULL)
                    if result.returncode == 0 and result.stdout:
                        files = result.stdout.strip().split('\n')
                        log_files.extend([f for f in files if f and os.path.exists(f)])
            except Exception:
                # Fallback to manual search if find fails
                try:
                    for dirpath, _, filenames in os.walk(root):
                        if "claude" in dirpath.lower():
                            for pattern in log_patterns:
                                for filename in filenames:
                                    if filename == pattern:
                                        log_files.append(os.path.join(dirpath, filename))
                except Exception:
                    pass

        # Remove duplicates
        log_files = list(set(log_files))

        if clear_logs:
            # Clear logs
            if not log_files:
                console.print("[yellow]No Orchestra logs found to clear.[/yellow]")
                return

            console.print(f"[bold yellow]Found {len(log_files)} log file(s):[/bold yellow]")
            for log_file in log_files:
                console.print(f"  [dim]-[/dim] {log_file}")

            # Confirm
            console.print("\n[bold red]⚠️  This will delete all Orchestra logs.[/bold red]")
            response = console.input("Continue? [y/N]: ")

            if response.lower() == 'y':
                cleared = 0
                for log_file in log_files:
                    try:
                        os.unlink(log_file)
                        cleared += 1
                    except Exception as e:
                        console.print(f"[red]Failed to delete {log_file}: {e}[/red]")

                console.print(f"[bold green]✅ Cleared {cleared} log file(s)[/bold green]")
            else:
                console.print("[yellow]Cancelled.[/yellow]")
            return

        if not log_files:
            console.print("[yellow]No Orchestra logs found.[/yellow]")
            console.print("[dim]Logs are created when extensions are used in Claude Code.[/dim]")
            console.print("[dim]Try running a command first, e.g., 'orchestra task status'[/dim]")
            return

        # Display or tail logs
        if tail_mode:
            console.print(f"[bold green]📜 Following {len(log_files)} log file(s):[/bold green]")
            for log_file in log_files:
                console.print(f"  [dim]-[/dim] {log_file}")
            console.print("\n[dim]Press Ctrl+C to stop...[/dim]\n")

            # Use tail -f on the log files
            try:
                if platform.system() == "Windows":
                    # Windows doesn't have tail, use PowerShell
                    cmd = ["powershell", "-Command", f"Get-Content {' '.join(log_files)} -Wait"]
                else:
                    cmd = ["tail", "-f"] + log_files

                subprocess.run(cmd)
            except KeyboardInterrupt:
                console.print("\n[yellow]Stopped tailing logs.[/yellow]")
        else:
            # Display logs with nice formatting
            console.print(f"[bold green]📜 Orchestra Logs[/bold green] ({len(log_files)} file(s) found)\n")

            for log_file in log_files:
                # Extract extension name from log file
                if "task_monitor.log" in log_file:
                    ext_name = "Task Monitor"
                    ext_color = "cyan"
                elif "timemachine.log" in log_file:
                    ext_name = "TimeMachine"
                    ext_color = "magenta"
                else:
                    ext_name = "Unknown"
                    ext_color = "white"

                console.print(f"[bold {ext_color}]═══ {ext_name} ═══[/bold {ext_color}]")
                console.print(f"[dim]{log_file}[/dim]")

                try:
                    with open(log_file, 'r') as f:
                        # Read last 50 lines by default
                        lines = f.readlines()
                        if len(lines) > 50:
                            console.print(f"[dim]... showing last 50 lines (file has {len(lines)} total) ...[/dim]")
                            lines = lines[-50:]

                        for line in lines:
                            line = line.rstrip()
                            # Color code log levels
                            if "ERROR" in line or "CRITICAL" in line:
                                console.print(f"[red]{line}[/red]")
                            elif "WARNING" in line:
                                console.print(f"[yellow]{line}[/yellow]")
                            elif "DEBUG" in line:
                                console.print(f"[dim]{line}[/dim]")
                            elif "INFO" in line:
                                console.print(f"[blue]{line}[/blue]")
                            else:
                                console.print(line)

                except Exception as e:
                    console.print(f"[red]Error reading log: {e}[/red]")

                console.print()  # Empty line between logs

            console.print("[dim]Tip: Use 'orchestra logs --tail' to follow logs in real-time[/dim]")

    else:
        console.print(f"[bold red]Unknown command:[/bold red] {command}")
        console.print("Run [cyan]'orchestra'[/cyan] for help")

if __name__ == "__main__":
    main()
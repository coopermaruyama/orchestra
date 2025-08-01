#!/usr/bin/env python3
"""
Orchestra - Claude Code Extension Manager
Orchestrate your Claude Code workflow with focused extensions
"""

import sys
import json
import shutil
from pathlib import Path
from typing import Dict, Any
from rich.console import Console
from rich.table import Table

class Orchestra:
    def __init__(self) -> None:
        self.home = Path.home()
        self.global_dir = self.home / ".claude" / "commands"
        self.local_dir = Path(".claude") / "commands"
        self.console = Console()
        
        # Available extensions registry
        self.extensions = {
            "task-monitor": {
                "name": "Task Monitor",
                "description": "Keep Claude focused on your task requirements. Prevents scope creep, tracks progress, and guides you through requirements step by step.",
                "commands": ["task start", "task progress", "task next", "task complete", "focus"],
                "features": [
                    "Blocks off-topic commands",
                    "Warns about scope creep", 
                    "Tracks progress automatically",
                    "Guides through requirements"
                ]
            }
        }

    def install(self, extension: str, scope: str = "global") -> None:
        """Install an Orchestra extension"""
        if extension not in self.extensions:
            self.console.print(f"[bold red]❌ Unknown extension:[/bold red] {extension}")
            self.console.print("[yellow]Available extensions:[/yellow]")
            for ext_id, ext_info in self.extensions.items():
                self.console.print(f"  • {ext_id} - {ext_info['name']}")
            return

        # Determine installation directory
        if scope == "global":
            commands_dir = self.global_dir
            scripts_dir = self.home / ".claude" / "orchestra" / extension
        else:
            commands_dir = self.local_dir
            scripts_dir = Path(".claude") / "orchestra" / extension
            
            # Warning for project scope installation
            self.console.print("\n[bold yellow]⚠️  Warning: Project scope installation[/bold yellow]")
            self.console.print("[yellow]Installing to project scope (.claude/commands/) may conflict with global installations.[/yellow]")
            self.console.print("[yellow]Claude Code does not support conflicts between user and project level commands.[/yellow]")
            self.console.print("[yellow]Consider using global installation (default) unless project-specific commands are required.[/yellow]\n")

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
    echo "Then install the task-monitor extension:"
    echo "  orchestra install task-monitor"
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
    
    # Find the task_monitor.py script
    SCRIPT_DIR="$(dirname "$0")"
    LOCAL_SCRIPT="$SCRIPT_DIR/task-monitor/task_monitor.py"
    GLOBAL_SCRIPT="$HOME/.claude/orchestra/task-monitor/task_monitor.py"
    
    if [ -f "$LOCAL_SCRIPT" ]; then
        TASK_MONITOR="$LOCAL_SCRIPT"
    elif [ -f "$GLOBAL_SCRIPT" ]; then
        TASK_MONITOR="$GLOBAL_SCRIPT"
    else
        echo "Error: task_monitor.py not found" >&2
        exit 1
    fi
    
    # Execute the hook
    exec "$PYTHON" "$TASK_MONITOR" "$@"
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

        # Copy the task_monitor.py script
        if extension == "task-monitor":
            task_monitor_source = Path(__file__).parent / "extensions" / "task-monitor" / "task_monitor.py"
            task_monitor_dest = scripts_dir / "task_monitor.py"
            
            if task_monitor_source.exists():
                shutil.copy(task_monitor_source, task_monitor_dest)
                task_monitor_dest.chmod(0o755)
            else:
                self.console.print(f"[bold red]⚠️ Warning:[/bold red] task_monitor.py not found at {task_monitor_source}")

        # Install subagents for intelligent deviation detection
        self._install_subagents(extension, scope)

        # Create the task directory for sub-commands
        task_dir = commands_dir / "task"
        task_dir.mkdir(parents=True, exist_ok=True)

        # Create individual command files
        # Now using bootstrap script for better team collaboration
        bootstrap_path = ".claude/orchestra/bootstrap.sh"
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
            cmd_content = f"""<!-- AUTO-GENERATED BY ORCHESTRA: task-monitor -->
# /task {cmd_name}

{cmd_info['description']}

{cmd_info['script']}"""

            with open(task_dir / f"{cmd_name}.md", 'w') as f:
                f.write(cmd_content)

        # Also create a /focus command at the root level
        focus_content = f"""<!-- AUTO-GENERATED BY ORCHESTRA: task-monitor -->
# /focus

Quick reminder of what you should be working on right now

!sh {bootstrap_path} task focus"""

        with open(commands_dir / "focus.md", 'w') as f:
            f.write(focus_content)

        # Create hooks configuration for Claude Code settings format
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

        self.console.print(f"[bold green]✅ Installed task-monitor[/bold green] ({scope} scope)")
        self.console.print(f"[bold]📁 Commands:[/bold]")
        self.console.print(f"   [dim]-[/dim] {task_dir}/*.md (sub-commands)")
        self.console.print(f"   [dim]-[/dim] {commands_dir / 'focus.md'}")
        self.console.print(f"[bold]🚀 Bootstrap:[/bold] {scripts_dir.parent / 'bootstrap.sh'}")
        self.console.print(f"[bold]🪝 Hooks:[/bold] Configured in {settings_file}")
        self.console.print(f"\n[bold yellow]🎯 Start with:[/bold yellow] [cyan]/task start[/cyan]")
        self.console.print(f"\n[dim]Note: Commands will work for team members even without Orchestra installed[/dim]")

    def _install_subagents(self, extension: str, scope: str) -> None:
        """Install subagents for an extension"""
        if extension != "task-monitor":
            return  # Only task-monitor currently uses subagents
            
        # Determine agents directory
        if scope == "global":
            agents_dir = self.home / ".claude" / "agents"
        else:
            agents_dir = Path(".claude") / "agents"
            
        agents_dir.mkdir(parents=True, exist_ok=True)
        
        # Copy subagent templates
        source_agents_dir = Path(__file__).parent / "extensions" / "task-monitor" / "agents"
        if source_agents_dir.exists():
            agent_count = 0
            for agent_file in source_agents_dir.glob("*.md"):
                dest_file = agents_dir / agent_file.name
                shutil.copy(agent_file, dest_file)
                agent_count += 1
                
            if agent_count > 0:
                self.console.print(f"[bold green]🤖 Installed {agent_count} subagents[/bold green] for intelligent deviation detection")

    def list_extensions(self) -> None:
        """List installed extensions"""
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

        self.console.print("[bold yellow]Available to install:[/bold yellow]")
        for ext_id, ext_info in self.extensions.items():
            # Check if already installed
            local_installed = (self.local_dir / "task" if ext_id == "task-monitor" else self.local_dir / ext_id).exists()
            global_installed = (self.global_dir / "task" if ext_id == "task-monitor" else self.global_dir / ext_id).exists()
            
            if not local_installed and not global_installed:
                self.console.print(f"  [dim]•[/dim] {ext_id} : [italic]{ext_info['description'][:60]}...[/italic]")

    def uninstall(self, extension: str, scope: str = "global") -> None:
        """Uninstall an extension"""
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
                    first_line = f.readline().strip()
                    return first_line == f"<!-- AUTO-GENERATED BY ORCHESTRA: {expected_extension} -->"
            except Exception:
                return False

        # Remove command files if they were generated by Orchestra
        if extension == "task-monitor":
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

        # Remove subagents if they were generated by Orchestra
        if agents_dir.exists() and extension == "task-monitor":
            agent_files = ["off-topic-detector.md", "over-engineering-detector.md", "scope-creep-detector.md"]
            for agent_file in agent_files:
                agent_path = agents_dir / agent_file
                if agent_path.exists():
                    try:
                        with open(agent_path, 'r') as f:
                            # Check if it's our agent by looking for specific content
                            content = f.read()
                            if "Orchestra Task Monitor" in content or "scope creep" in content:
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
        if settings_file.exists() and extension == "task-monitor":
            try:
                with open(settings_file, 'r') as f:
                    settings = json.load(f)
                
                if "hooks" in settings:
                    # Remove task-monitor specific hooks
                    bootstrap_command = f"sh {bootstrap_path} hook"
                    
                    for event_name in ["PreToolUse", "PostToolUse", "UserPromptSubmit"]:
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
            self.console.print(f"[bold green]✅ Uninstalled {extension}[/bold green]")
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
        commands_table.add_row("install <extension> [--project]", "Install an extension (default: global)")
        commands_table.add_row("uninstall <extension> [--project]", "Uninstall an extension (default: global)")
        commands_table.add_row("list", "List installed extensions")
        commands_table.add_row("task <subcommand>", "Run task monitor commands")
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
        console.print("  [dim]$[/dim] orchestra install task-monitor")
        console.print("  [dim]$[/dim] orchestra install task-monitor --project")
        console.print("  [dim]$[/dim] orchestra task start")
        console.print("  [dim]$[/dim] orchestra task status\n")
        return

    orchestra = Orchestra()
    command = sys.argv[1]

    if command == "install":
        if len(sys.argv) < 3:
            console.print("[bold yellow]Usage:[/bold yellow] orchestra install <extension> [--project]")
            console.print("[dim]Default: Installs globally to ~/.claude/commands/[/dim]")
            return

        extension = sys.argv[2]
        scope = "local" if "--project" in sys.argv else "global"
        orchestra.install(extension, scope)

    elif command == "uninstall":
        if len(sys.argv) < 3:
            console.print("[bold yellow]Usage:[/bold yellow] orchestra uninstall <extension> [--project]")
            console.print("[dim]Default: Uninstalls from global scope (~/.claude/commands/)[/dim]")
            return

        extension = sys.argv[2]
        scope = "local" if "--project" in sys.argv else "global"
        orchestra.uninstall(extension, scope)

    elif command == "list":
        orchestra.list_extensions()

    elif command == "task" or command == "task-monitor":
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
        local_script = Path(".claude") / "orchestra" / "task-monitor" / "task_monitor.py"
        global_script = Path.home() / ".claude" / "orchestra" / "task-monitor" / "task_monitor.py"

        script_path = None
        if local_script.exists():
            script_path = local_script
        elif global_script.exists():
            script_path = global_script
        else:
            console.print("[bold red]❌ Task monitor not installed.[/bold red] Run: [cyan]orchestra install task-monitor[/cyan]")
            return

        # Execute the task monitor script with the subcommand
        import subprocess
        try:
            # Pass through any additional arguments
            args = [sys.executable, str(script_path), subcommand] + sys.argv[3:]
            subprocess.run(args, check=False)
        except Exception as e:
            console.print(f"[bold red]❌ Error running task command:[/bold red] {e}")

    else:
        console.print(f"[bold red]Unknown command:[/bold red] {command}")
        console.print("Run [cyan]'orchestra'[/cyan] for help")

if __name__ == "__main__":
    main()
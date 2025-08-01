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
                "commands": ["task start", "task status", "task next", "task complete", "focus"],
                "features": [
                    "Blocks off-topic commands",
                    "Warns about scope creep", 
                    "Tracks progress automatically",
                    "Guides through requirements"
                ]
            }
        }

    def install(self, extension: str, scope: str = "local") -> None:
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

        # Create directories
        commands_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # Install bootstrap script
        bootstrap_source = Path(__file__).parent / "bootstrap.py"
        bootstrap_dest = scripts_dir.parent / "bootstrap.py"
        
        # Create bootstrap script content if source doesn't exist
        if not bootstrap_source.exists():
            bootstrap_content = '''#!/usr/bin/env python3
"""Orchestra Bootstrap Script"""
import sys
import subprocess
import os
from pathlib import Path

def check_orchestra_installed():
    try:
        result = subprocess.run(["which", "orchestra"], capture_output=True, text=True, check=False)
        return result.returncode == 0
    except Exception:
        return False

def show_install_instructions():
    flag_file = Path.home() / ".claude" / ".orchestra-install-shown"
    if flag_file.exists():
        return
    print("=" * 60)
    print("🎼 Orchestra not installed")
    print("=" * 60)
    print("\\nThis project uses Orchestra extensions for Claude Code.")
    print("\\nTo install Orchestra globally:")
    print("  pip install orchestra")
    print("\\nOr install from the project:")
    print("  pip install -e .")
    print("\\nThen install the task-monitor extension:")
    print("  orchestra install task-monitor")
    print("\\nFor more info: https://github.com/anthropics/orchestra")
    print("=" * 60)
    flag_file.parent.mkdir(parents=True, exist_ok=True)
    flag_file.touch()

def main():
    if len(sys.argv) < 2:
        print("Usage: bootstrap.py <command> [args...]")
        sys.exit(1)
    if not check_orchestra_installed():
        show_install_instructions()
        sys.exit(1)
    command = ["orchestra"] + sys.argv[1:]
    try:
        result = subprocess.run(command)
        sys.exit(result.returncode)
    except Exception as e:
        print(f"Error running orchestra: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
'''
            with open(bootstrap_dest, 'w') as f:
                f.write(bootstrap_content)
        else:
            shutil.copy(bootstrap_source, bootstrap_dest)
        
        bootstrap_dest.chmod(0o755)

        # Install subagents for intelligent deviation detection
        self._install_subagents(extension, scope)

        # Create the task directory for sub-commands
        task_dir = commands_dir / "task"
        task_dir.mkdir(parents=True, exist_ok=True)

        # Create individual command files
        # Now using bootstrap script for better team collaboration
        bootstrap_path = ".claude/orchestra/bootstrap.py"
        commands = {
            "start": {
                "description": "Start a new task with intelligent guided setup",
                "script": f"!python {bootstrap_path} task start"
            },
            "status": {
                "description": "Check current task progress and see what's been completed",
                "script": f"!python {bootstrap_path} task status"
            },
            "next": {
                "description": "Show the next priority action to work on",
                "script": f"!python {bootstrap_path} task next"
            },
            "complete": {
                "description": "Mark the current requirement as complete and see what's next",
                "script": f"!python {bootstrap_path} task complete"
            }
        }

        # Write individual command files
        for cmd_name, cmd_info in commands.items():
            cmd_content = f"""# /task {cmd_name}

{cmd_info['description']}

{cmd_info['script']}"""

            with open(task_dir / f"{cmd_name}.md", 'w') as f:
                f.write(cmd_content)

        # Also create a /focus command at the root level
        focus_content = f"""# /focus

Quick reminder of what you should be working on right now

!python {bootstrap_path} task focus"""

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
                                "command": f"python {bootstrap_path} hook PreToolUse"
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
                                "command": f"python {bootstrap_path} hook PostToolUse"
                            }
                        ]
                    }
                ],
                "UserPromptSubmit": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"python {bootstrap_path} hook UserPromptSubmit"
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
            existing_settings: Dict[str, Any] = {
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
        self.console.print(f"[bold]🚀 Bootstrap:[/bold] {scripts_dir.parent / 'bootstrap.py'}")
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

    def uninstall(self, extension: str, scope: str = "local") -> None:
        """Uninstall an extension"""
        if scope == "global":
            commands_dir = self.global_dir
            scripts_dir = self.home / ".claude" / "orchestra" / extension
        else:
            commands_dir = self.local_dir
            scripts_dir = Path(".claude") / "orchestra" / extension

        removed = False

        # Remove command directories if they exist
        # Handle both task-monitor and task directories for compatibility
        if extension == "task-monitor":
            task_dir = commands_dir / "task"
            if task_dir.exists() and task_dir.is_dir():
                shutil.rmtree(task_dir)
                removed = True

        command_dir = commands_dir / extension
        if command_dir.exists() and command_dir.is_dir():
            shutil.rmtree(command_dir)
            removed = True

        # Remove any root-level commands (like focus.md for task-monitor)
        if extension == "task-monitor":
            focus_file = commands_dir / "focus.md"
            if focus_file.exists():
                focus_file.unlink()
                removed = True

        # Remove scripts directory
        if scripts_dir.exists():
            shutil.rmtree(scripts_dir)
            removed = True

        if removed:
            self.console.print(f"[bold green]✅ Uninstalled {extension}[/bold green]")
            # TODO: Clean up hooks from claude-hooks.json
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
        commands_table.add_row("install <extension> [--global]", "Install an extension")
        commands_table.add_row("uninstall <extension> [--global]", "Uninstall an extension")
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
        console.print("  [dim]$[/dim] orchestra install task-monitor --global")
        console.print("  [dim]$[/dim] orchestra task start")
        console.print("  [dim]$[/dim] orchestra task status\n")
        return

    orchestra = Orchestra()
    command = sys.argv[1]

    if command == "install":
        if len(sys.argv) < 3:
            console.print("[bold yellow]Usage:[/bold yellow] orchestra install <extension> [--global]")
            return

        extension = sys.argv[2]
        scope = "global" if "--global" in sys.argv else "local"
        orchestra.install(extension, scope)

    elif command == "uninstall":
        if len(sys.argv) < 3:
            console.print("[bold yellow]Usage:[/bold yellow] orchestra uninstall <extension> [--global]")
            return

        extension = sys.argv[2]
        scope = "global" if "--global" in sys.argv else "local"
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
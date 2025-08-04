"""
Orchestra Core - Extension management with template support
"""

import json
import shutil
from pathlib import Path
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader
from rich.console import Console
from rich.table import Table


class Orchestra:
    """Orchestra extension manager using template-based configuration"""

    def __init__(self) -> None:
        self.__version__ = "0.8.0"
        self.home = Path.home()
        self.global_dir = self.home / ".claude" / "commands"
        self.local_dir = Path(".claude") / "commands"
        self.console = Console()

        # Set up Jinja2 environment
        template_dir = Path(__file__).parent / "templates"
        self.jinja_env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Available extensions registry
        self.extensions = {
            "task": {
                "name": "Task Monitor",
                "description": "Keep Claude focused on your task requirements. Prevents scope creep, tracks progress, and guides you through requirements step by step.",
                "commands": [
                    "task start",
                    "task progress",
                    "task next",
                    "task complete",
                    "focus",
                ],
                "features": [
                    "Blocks off-topic commands",
                    "Warns about scope creep",
                    "Tracks progress automatically",
                    "Guides through requirements",
                ],
                "monitor_script": "task_monitor.py",
            },
            "timemachine": {
                "name": "TimeMachine",
                "description": "Automatic git checkpointing for every conversation turn. Travel back in time to any previous state with full prompt history.",
                "commands": [
                    "timemachine list",
                    "timemachine checkout",
                    "timemachine view",
                    "timemachine rollback",
                ],
                "features": [
                    "Checkpoint every user prompt",
                    "View conversation history",
                    "Rollback to any previous state",
                    "Track file modifications per turn",
                ],
                "monitor_script": "timemachine_monitor.py",
            },
            "tidy": {
                "name": "Tidy",
                "description": "Automated code quality checker that ensures code meets project standards. Runs linters, formatters, and type checkers after Claude modifies files.",
                "commands": [
                    "tidy init",
                    "tidy check",
                    "tidy fix",
                    "tidy status",
                    "tidy learn",
                ],
                "features": [
                    "Auto-detects project type and tools",
                    "Runs checks after code modifications",
                    "Parallel execution for performance",
                    "Learns project conventions over time",
                    "Supports Python, JS/TS, Rust, and more",
                ],
                "monitor_script": "tidy_monitor.py",
                "extra_modules": ["project_detector.py", "tool_runners.py"],
            },
            "tester": {
                "name": "Tester",
                "description": "Automatically test completed tasks using calibrated testing methods. Learns your project's testing approach through interactive calibration.",
                "commands": ["tester calibrate", "tester test", "tester status"],
                "features": [
                    "Interactive calibration to learn test methods",
                    "Automatic test execution on task completion",
                    "Browser testing with Chrome automation",
                    "Smart test selection based on changes",
                ],
                "monitor_script": "tester_monitor.py",
            },
        }

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """Render a Jinja2 template with the given context"""
        template = self.jinja_env.get_template(template_name)
        return template.render(**context)

    def enable(self, extension: str, scope: str = "global") -> None:
        """Enable an Orchestra extension"""
        if extension not in self.extensions:
            self.console.print(
                f"[bold red]❌ Unknown extension:[/bold red] {extension}"
            )
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
            self.console.print(
                "\n[bold yellow]⚠️  Warning: Project scope enablement[/bold yellow]"
            )
            self.console.print(
                "[yellow]Enabling in project scope (.claude/commands/) may conflict with global enablement.[/yellow]"
            )
            self.console.print(
                "[yellow]Claude Code does not support conflicts between user and project level commands.[/yellow]"
            )
            self.console.print(
                "[yellow]Consider using global enablement (default) unless project-specific commands are required.[/yellow]\n"
            )

        # Create directories
        commands_dir.mkdir(parents=True, exist_ok=True)
        scripts_dir.mkdir(parents=True, exist_ok=True)

        # Create shell bootstrap script using template
        bootstrap_dest = scripts_dir.parent / "bootstrap.sh"
        bootstrap_path = (
            "$HOME/.claude/orchestra/bootstrap.sh"
            if scope == "global"
            else ".claude/orchestra/bootstrap.sh"
        )

        # Get extension info
        ext_info = self.extensions[extension]
        monitor_script = ext_info.get("monitor_script", f"{extension}_monitor.py")

        # Context for bootstrap template
        bootstrap_context = {
            "extension": extension,
            "local_script_path": f"$SCRIPT_DIR/{extension}/{monitor_script}",
            "global_script_path": f"$HOME/.claude/orchestra/{extension}/{monitor_script}",
        }

        bootstrap_content = self.render_template("bootstrap.sh.j2", bootstrap_context)
        with open(bootstrap_dest, "w") as f:
            f.write(bootstrap_content)
        bootstrap_dest.chmod(0o755)

        # Copy the extension script and its dependencies
        self._copy_extension_files(extension, scripts_dir)

        # Copy orchestra.common library for dependencies
        self._copy_common_library(scripts_dir)

        # Install subagents for intelligent deviation detection
        self._install_subagents(extension, scope)

        # Create extension-specific commands
        self._create_extension_commands(extension, commands_dir, bootstrap_path)

        # Create hooks configuration
        self._create_hooks_config(commands_dir, bootstrap_path, extension)

        # Success message
        self._print_success_message(extension, scope, commands_dir, scripts_dir)

    def _copy_extension_files(self, extension: str, scripts_dir: Path) -> None:
        """Copy extension files to the scripts directory"""
        ext_info = self.extensions[extension]
        monitor_script = ext_info.get("monitor_script")
        
        if not monitor_script or not isinstance(monitor_script, str):
            self.console.print(
                f"[bold red]⚠️ Warning:[/bold red] No monitor script configured for {extension}"
            )
            return

        # Copy main monitor script
        monitor_source = (
            Path(__file__).parent / "extensions" / extension / monitor_script
        )
        monitor_dest = scripts_dir / monitor_script

        if monitor_source.exists():
            shutil.copy(monitor_source, monitor_dest)
            monitor_dest.chmod(0o755)
        else:
            self.console.print(
                f"[bold red]⚠️ Warning:[/bold red] {monitor_script} not found at {monitor_source}"
            )
            return

        # Copy extra modules if specified
        extra_modules = ext_info.get("extra_modules", [])
        for module in extra_modules:
            module_source = Path(__file__).parent / "extensions" / extension / module
            module_dest = scripts_dir / module
            if module_source.exists():
                shutil.copy(module_source, module_dest)
                module_dest.chmod(0o644)
            else:
                self.console.print(
                    f"[bold red]⚠️ Warning:[/bold red] {module} not found for {extension} extension"
                )

    def _copy_common_library(self, scripts_dir: Path) -> None:
        """Copy the orchestra.common library"""
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
                self.console.print("[bold]🔧 Made git-wip executable[/bold]")

            self.console.print("[bold]📦 Bundled orchestra.common library[/bold]")
        else:
            self.console.print(
                f"[bold red]⚠️ Warning:[/bold red] orchestra.common not found at {common_source}"
            )

    def _create_extension_commands(
        self, extension: str, commands_dir: Path, bootstrap_path: str
    ) -> None:
        """Create extension-specific command files"""
        if extension == "task":
            self._create_task_commands(commands_dir, bootstrap_path)
        elif extension == "timemachine":
            self._create_timemachine_commands(commands_dir, bootstrap_path)
        elif extension == "tidy":
            self._create_tidy_commands(commands_dir, bootstrap_path)
        elif extension == "tester":
            self._create_tester_commands(commands_dir, bootstrap_path)

    def _create_task_commands(self, commands_dir: Path, bootstrap_path: str) -> None:
        """Create task extension commands"""
        task_dir = commands_dir / "task"
        task_dir.mkdir(parents=True, exist_ok=True)

        commands = {
            "start": {
                "description": "Start a new task with intelligent guided setup",
                "script": f"!sh {bootstrap_path} task start",
            },
            "progress": {
                "description": "Check current task progress and see what's been completed",
                "script": f"!sh {bootstrap_path} task status",
            },
            "next": {
                "description": "Show the next priority action to work on",
                "script": f"!sh {bootstrap_path} task next",
            },
            "complete": {
                "description": "Mark the current requirement as complete and see what's next",
                "script": f"!sh {bootstrap_path} task complete",
            },
        }

        # Write individual command files using template
        for cmd_name, cmd_info in commands.items():
            context = {
                "description": cmd_info["description"],
                "script": cmd_info["script"],
                "extension": "task",
            }
            content = self.render_template("command.md.j2", context)
            with open(task_dir / f"{cmd_name}.md", "w") as f:
                f.write(content)

        # Also create a /focus command at the root level
        focus_context = {
            "description": "Quick reminder of what you should be working on right now",
            "script": f"!sh {bootstrap_path} task focus",
            "extension": "task",
        }
        focus_content = self.render_template("command.md.j2", focus_context)
        with open(commands_dir / "focus.md", "w") as f:
            f.write(focus_content)

    def _create_timemachine_commands(
        self, commands_dir: Path, bootstrap_path: str
    ) -> None:
        """Create timemachine extension commands"""
        tm_dir = commands_dir / "timemachine"
        tm_dir.mkdir(parents=True, exist_ok=True)

        commands = {
            "list": {
                "description": "View a list of conversation checkpoints",
                "script": f"!sh {bootstrap_path} timemachine list",
            },
            "checkout": {
                "description": "Checkout a specific checkpoint by ID",
                "script": f"!sh {bootstrap_path} timemachine checkout $ARGUMENTS",
            },
            "view": {
                "description": "View full details of a checkpoint",
                "script": f"!sh {bootstrap_path} timemachine view $ARGUMENTS",
            },
            "rollback": {
                "description": "Rollback n conversation turns",
                "script": f"!sh {bootstrap_path} timemachine rollback $ARGUMENTS",
            },
        }

        # Write individual command files using template
        for cmd_name, cmd_info in commands.items():
            context = {
                "description": cmd_info["description"],
                "script": cmd_info["script"],
                "extension": "timemachine",
            }
            content = self.render_template("command.md.j2", context)
            with open(tm_dir / f"{cmd_name}.md", "w") as f:
                f.write(content)

    def _create_tidy_commands(self, commands_dir: Path, bootstrap_path: str) -> None:
        """Create tidy extension commands"""
        tidy_dir = commands_dir / "tidy"
        tidy_dir.mkdir(parents=True, exist_ok=True)

        commands = {
            "init": {
                "description": "Interactive setup wizard to configure code quality tools",
                "script": f"!sh {bootstrap_path} tidy init",
            },
            "check": {
                "description": "Run code quality checks on all or specified files",
                "script": f"!sh {bootstrap_path} tidy check $ARGUMENTS",
            },
            "fix": {
                "description": "Auto-fix code quality issues where possible",
                "script": f"!sh {bootstrap_path} tidy fix $ARGUMENTS",
            },
            "status": {
                "description": "Show current configuration and last check results",
                "script": f"!sh {bootstrap_path} tidy status",
            },
            "learn": {
                "description": "Add do/don't examples to help Claude learn project conventions",
                "script": f"!sh {bootstrap_path} tidy learn $ARGUMENTS",
            },
        }

        # Write individual command files using template
        for cmd_name, cmd_info in commands.items():
            context = {
                "description": cmd_info["description"],
                "script": cmd_info["script"],
                "extension": "tidy",
            }
            content = self.render_template("command.md.j2", context)
            with open(tidy_dir / f"{cmd_name}.md", "w") as f:
                f.write(content)

    def _create_tester_commands(self, commands_dir: Path, bootstrap_path: str) -> None:
        """Create tester extension commands"""
        tester_dir = commands_dir / "tester"
        tester_dir.mkdir(parents=True, exist_ok=True)

        commands = {
            "calibrate": {
                "description": "Set up testing for your project through interactive calibration",
                "script": f"!sh {bootstrap_path} tester calibrate",
            },
            "test": {
                "description": "Run tests for completed tasks",
                "script": f"!sh {bootstrap_path} tester test",
            },
            "status": {
                "description": "Show calibration status and test results",
                "script": f"!sh {bootstrap_path} tester status",
            },
        }

        # Write individual command files using template
        for cmd_name, cmd_info in commands.items():
            context = {
                "description": cmd_info["description"],
                "script": cmd_info["script"],
                "extension": "tester",
            }
            content = self.render_template("command.md.j2", context)
            with open(tester_dir / f"{cmd_name}.md", "w") as f:
                f.write(content)

    def _create_hooks_config(
        self, commands_dir: Path, bootstrap_path: str, extension: str
    ) -> None:
        """Create hooks configuration for Claude Code"""
        context = {"hook_command": f"sh {bootstrap_path} hook"}
        hooks_config = json.loads(self.render_template("hooks_config.json.j2", context))

        # Write or update settings file with hooks
        settings_file = commands_dir.parent / "settings.json"
        if settings_file.exists():
            try:
                with open(settings_file) as f:
                    existing_settings: Dict[str, Any] = json.load(f)
            except json.JSONDecodeError:
                # If the file has comments or is invalid JSON, create a backup and start fresh
                import shutil

                backup_file = settings_file.with_suffix(".json.backup")
                shutil.copy(settings_file, backup_file)
                self.console.print(
                    f"[yellow]⚠️ Invalid JSON in settings.json, created backup at {backup_file}[/yellow]"
                )
                existing_settings = {
                    "$schema": "https://json.schemastore.org/claude-code-settings.json"
                }
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

        with open(settings_file, "w") as f:
            json.dump(existing_settings, f, indent=2)

    def _install_subagents(self, extension: str, scope: str) -> None:
        """Install subagents for an extension"""
        if extension not in ["task", "tidy", "tester"]:
            return  # Only task, tidy, and tester use subagents

        # Determine agents directory
        if scope == "global":
            agents_dir = self.home / ".claude" / "agents"
        else:
            agents_dir = Path(".claude") / "agents"

        agents_dir.mkdir(parents=True, exist_ok=True)

        # Copy subagent templates
        source_agents_dir = Path(__file__).parent / "extensions" / extension / "agents"
        if source_agents_dir.exists():
            agent_count = 0
            for agent_file in source_agents_dir.glob("*.md"):
                dest_file = agents_dir / agent_file.name
                shutil.copy(agent_file, dest_file)
                agent_count += 1

            if agent_count > 0:
                if extension == "task":
                    self.console.print(
                        f"[bold green]🤖 Installed {agent_count} subagents[/bold green] for intelligent deviation detection"
                    )
                elif extension == "tidy":
                    self.console.print(
                        f"[bold green]🤖 Installed {agent_count} subagents[/bold green] for code quality analysis"
                    )
                elif extension == "tester":
                    self.console.print(
                        f"[bold green]🤖 Installed {agent_count} subagents[/bold green] for test automation"
                    )

    def _print_success_message(
        self, extension: str, scope: str, commands_dir: Path, scripts_dir: Path
    ) -> None:
        """Print success message after enabling extension"""
        self.console.print(
            f"[bold green]✅ Enabled {extension}[/bold green] ({scope} scope)"
        )
        self.console.print("[bold]📁 Commands:[/bold]")

        if extension == "task":
            self.console.print(
                f"   [dim]-[/dim] {commands_dir / 'task'}/*.md (sub-commands)"
            )
            self.console.print(f"   [dim]-[/dim] {commands_dir / 'focus.md'}")
            start_cmd = "/task start"
        elif extension == "timemachine":
            self.console.print(
                f"   [dim]-[/dim] {commands_dir / 'timemachine'}/*.md (sub-commands)"
            )
            start_cmd = "/timemachine list"
        elif extension == "tidy":
            self.console.print(
                f"   [dim]-[/dim] {commands_dir / 'tidy'}/*.md (sub-commands)"
            )
            start_cmd = "/tidy init"
        elif extension == "tester":
            self.console.print(
                f"   [dim]-[/dim] {commands_dir / 'tester'}/*.md (sub-commands)"
            )
            start_cmd = "/tester calibrate"
        else:
            start_cmd = f"/{extension}"

        self.console.print(
            f"[bold]🚀 Bootstrap:[/bold] {scripts_dir.parent / 'bootstrap.sh'}"
        )
        self.console.print(
            f"[bold]🪝 Hooks:[/bold] Configured in {commands_dir.parent / 'settings.json'}"
        )
        self.console.print(
            f"\n[bold yellow]🎯 Start with:[/bold yellow] [cyan]{start_cmd}[/cyan]"
        )
        self.console.print(
            "\n[dim]Note: Commands will work for team members even without Orchestra installed[/dim]"
        )

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
            local_installed = (self.local_dir / ext_id).exists()
            global_installed = (self.global_dir / ext_id).exists()

            if not local_installed and not global_installed:
                self.console.print(
                    f"  [dim]•[/dim] {ext_id} : [italic]{ext_info['description'][:60]}...[/italic]"
                )

    def status(self) -> None:
        """Show detailed status of all extensions"""
        self.console.print("[bold blue]🎼 Orchestra Extension Status[/bold blue]\n")

        # Create status table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Extension", style="cyan", width=16)
        table.add_column("State", style="yellow", width=15)
        table.add_column("Details", style="dim", width=50)

        # Check each extension
        for ext_id, ext_info in self.extensions.items():
            # Check installation scope
            local_installed = (self.local_dir / ext_id).exists()
            global_installed = (self.global_dir / ext_id).exists()

            if not local_installed and not global_installed:
                table.add_row(
                    ext_info["name"],
                    "Disabled", 
                    f"Run 'orchestra enable {ext_id}' to install"
                )
                continue

            # Check configuration and state
            state = "Uninitialized"
            details = ""

            # Determine config path
            if local_installed:
                config_path = Path(".claude") / "orchestra"
            else:
                config_path = self.home / ".claude" / "orchestra"

            # Check extension-specific config
            if ext_id == "task":
                task_config = config_path / "task.json"
                if task_config.exists():
                    try:
                        with open(task_config) as f:
                            config = json.load(f)
                            if config.get("task") and config.get("requirements"):
                                state = "Ready"
                                completed = sum(
                                    1
                                    for req in config["requirements"]
                                    if req.get("completed", False)
                                )
                                total = len(config["requirements"])
                                details = f"Task: {config['task'][:30]}... ({completed}/{total} done)"
                            else:
                                state = "Uninitialized"
                                details = "Run '/task start' to begin a task"
                    except Exception:
                        details = "Error reading config"
                else:
                    state = "Uninitialized"
                    details = "Run '/task start' to begin a task"

            elif ext_id == "timemachine":
                tm_config = config_path / "timemachine.json"
                if tm_config.exists():
                    try:
                        with open(tm_config) as f:
                            config = json.load(f)
                            checkpoints = config.get("checkpoints", [])
                            state = "Ready"
                            if checkpoints:
                                details = f"{len(checkpoints)} checkpoint(s) saved"
                            else:
                                details = "No checkpoints yet"
                    except Exception:
                        details = "Error reading config"
                else:
                    state = "Ready"
                    details = "Will create checkpoints automatically"

            elif ext_id == "tidy":
                tidy_config = config_path / "tidy.json"
                if tidy_config.exists():
                    try:
                        with open(tidy_config) as f:
                            config = json.load(f)
                            if config.get("project_type") and config.get("tools"):
                                state = "Ready"
                                tools = ", ".join(config["tools"].keys())
                                details = f"{config['project_type']} project: {tools}"
                            else:
                                state = "Uninitialized"
                                details = "Run '/tidy init' to configure"
                    except Exception:
                        details = "Error reading config"
                else:
                    state = "Uninitialized"
                    details = "Run '/tidy init' to configure"

            elif ext_id == "tester":
                tester_config = config_path / "tester.json"
                if tester_config.exists():
                    try:
                        with open(tester_config) as f:
                            config = json.load(f)
                            calibration = config.get("calibration", {})
                            if calibration.get("calibrated_at"):
                                state = "Ready"
                                framework = calibration.get("framework", "Unknown")
                                test_count = len(config.get("test_results", []))
                                details = (
                                    f"{framework} framework, {test_count} test run(s)"
                                )
                            else:
                                state = "Uninitialized"
                                details = "Run '/tester calibrate' to set up"
                    except Exception:
                        details = "Error reading config"
                else:
                    state = "Uninitialized"
                    details = "Run '/tester calibrate' to set up"

            table.add_row(str(ext_info["name"]), str(state), str(details))

        self.console.print(table)

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
                with open(file_path) as f:
                    content = f.read().strip()
                    # Check if the file ends with the auto-generated comment
                    return content.endswith(
                        f"<!-- AUTO-GENERATED BY ORCHESTRA: {expected_extension} -->"
                    )
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

        else:
            # Remove extension sub-commands for other extensions
            ext_dir = commands_dir / extension
            if ext_dir.exists() and ext_dir.is_dir():
                removed_count = 0
                for cmd_file in ext_dir.glob("*.md"):
                    if is_orchestra_generated(cmd_file, extension):
                        cmd_file.unlink()
                        removed_count += 1
                        removed = True

                # Remove the extension directory if it's empty
                if removed_count > 0 and not any(ext_dir.iterdir()):
                    ext_dir.rmdir()

        # Remove subagents if they were generated by Orchestra
        if agents_dir.exists():
            agent_files = []
            if extension == "task":
                agent_files = [
                    "off-topic-detector.md",
                    "over-engineering-detector.md",
                    "scope-creep-detector.md",
                ]
            elif extension == "tidy":
                agent_files = ["code-quality-analyzer.md", "fix-suggester.md"]
            elif extension == "tester":
                agent_files = ["test-calibrator.md", "test-runner.md"]

            for agent_file in agent_files:
                agent_path = agents_dir / agent_file
                if agent_path.exists():
                    agent_path.unlink()
                    removed = True

        # Remove scripts directory (always safe to remove as it's only for Orchestra)
        if scripts_dir.exists():
            shutil.rmtree(scripts_dir)
            removed = True

        # Remove bootstrap.sh if no other extensions are using it
        bootstrap_path = scripts_dir.parent / "bootstrap.sh"
        if bootstrap_path.exists():
            # Check if any other extension directories exist
            orchestra_dir = scripts_dir.parent
            other_extensions = [
                d
                for d in orchestra_dir.iterdir()
                if d.is_dir() and d.name != extension and d.name != "bootstrap.sh"
            ]

            if not other_extensions:
                bootstrap_path.unlink()
                # Remove orchestra directory if empty
                if not any(orchestra_dir.iterdir()):
                    orchestra_dir.rmdir()

        # Clean up hooks from settings.json
        self._clean_hooks_from_settings(commands_dir, bootstrap_path)

        if removed:
            self.console.print(f"[bold green]✅ Disabled {extension}[/bold green]")
        else:
            self.console.print(
                f"[bold red]❌ Extension not found:[/bold red] {extension}"
            )

    def _clean_hooks_from_settings(
        self, commands_dir: Path, bootstrap_path: Path
    ) -> None:
        """Clean up hooks from settings.json"""
        settings_file = commands_dir.parent / "settings.json"
        if not settings_file.exists():
            return

        try:
            with open(settings_file) as f:
                settings = json.load(f)

            if "hooks" in settings:
                # Remove Orchestra-specific hooks
                bootstrap_command = f"sh {bootstrap_path} hook"

                for event_name in [
                    "PreToolUse",
                    "PostToolUse",
                    "UserPromptSubmit",
                    "Stop",
                    "SubagentStop",
                    "PreCompact",
                ]:
                    if event_name in settings["hooks"]:
                        # Filter out Orchestra hooks
                        if isinstance(settings["hooks"][event_name], list):
                            settings["hooks"][event_name] = [
                                hook
                                for hook in settings["hooks"][event_name]
                                if not (
                                    isinstance(hook, dict)
                                    and hook.get("hooks", [{}])[0]
                                    .get("command", "")
                                    .startswith(bootstrap_command)
                                )
                            ]

                            # Remove empty hook arrays
                            if not settings["hooks"][event_name]:
                                del settings["hooks"][event_name]

                # Remove hooks key if empty
                if not settings["hooks"]:
                    del settings["hooks"]

            # Write back the cleaned settings
            with open(settings_file, "w") as f:
                json.dump(settings, f, indent=2)

        except Exception as e:
            self.console.print(
                f"[yellow]⚠️ Warning: Could not clean up hooks from settings.json: {e}[/yellow]"
            )

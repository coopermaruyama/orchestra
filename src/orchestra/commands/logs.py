"""Logs command for Orchestra CLI"""

import os
import platform
import subprocess

import click
from rich.console import Console

console = Console()


@click.command()
@click.argument("extension", required=False)
@click.option("--tail", "-f", is_flag=True, help="Follow log output")
@click.option("--clear", is_flag=True, help="Clear all Orchestra logs")
@click.option(
    "--no-truncate", is_flag=True, help="Show full log values without truncation"
)
def logs(extension: str, tail: bool, clear: bool, no_truncate: bool) -> None:
    """View or manage extension logs

    Examples:
        orchestra logs              # View all logs
        orchestra logs task         # View task monitor logs
        orchestra logs --tail       # Follow all logs
        orchestra logs --clear      # Clear all logs
    """
    # Find log files
    log_patterns = []
    if extension:
        if extension == "task":
            log_patterns.append("task_monitor.log")
        elif extension == "timemachine":
            log_patterns.append("timemachine.log")
        elif extension == "tidy":
            log_patterns.append("tidy.log")
        elif extension == "tester":
            log_patterns.append("tester.log")
        elif extension == "plancheck":
            log_patterns.append("plancheck.log")
        else:
            console.print(f"[bold red]❌ Unknown extension:[/bold red] {extension}")
            console.print(
                "[dim]Valid extensions: task, timemachine, tidy, tester, plancheck[/dim]"
            )
            return
    else:
        # Look for all Orchestra logs
        log_patterns.extend(
            ["task_monitor.log", "timemachine.log", "tidy.log", "tester.log", "plancheck.log"]
        )

    # Search for log files in Orchestra project directories and temp directories
    log_files = []
    search_roots = []

    # First, try to find logs in Orchestra project directories
    # Use the same project directory detection logic as extensions
    project_dirs = []
    
    # Check ORCH_PROJECT_DIR
    orch_dir = os.environ.get("ORCH_PROJECT_DIR")
    if orch_dir and os.path.isdir(orch_dir):
        project_dirs.append(orch_dir)
    
    # Check CLAUDE_PROJECT_DIR  
    claude_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if claude_dir and os.path.isdir(claude_dir):
        project_dirs.append(claude_dir)
    
    # Check git root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            cwd=os.getcwd()
        )
        if result.returncode == 0:
            git_root = result.stdout.strip()
            if git_root and os.path.isdir(git_root):
                project_dirs.append(git_root)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        pass
    
    # Add current working directory
    project_dirs.append(os.getcwd())
    
    # Add .claude/logs paths from project directories
    for project_dir in project_dirs:
        logs_dir = os.path.join(project_dir, ".claude", "logs")
        if os.path.exists(logs_dir):
            search_roots.append(logs_dir)
    
    # Also search temp directories as fallback
    if platform.system() == "Darwin":  # macOS
        search_roots.extend(["/var/folders", "/tmp"])
    elif platform.system() == "Linux":
        search_roots.extend(["/tmp", "/var/tmp"])
    elif platform.system() == "Windows":
        search_roots.extend([os.environ.get("TEMP", ""), os.environ.get("TMP", "")])

    # Find log files
    for root in search_roots:
        if not root or not os.path.exists(root):
            continue

        try:
            # Use find command for efficiency
            for pattern in log_patterns:
                if platform.system() == "Windows":
                    cmd = ["where", "/r", root, pattern]
                else:
                    cmd = ["find", root, "-name", pattern, "-type", "f"]

                result = subprocess.run(
                    cmd,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0 and result.stdout:
                    files = result.stdout.strip().split("\n")
                    log_files.extend([f for f in files if f and os.path.exists(f)])
        except Exception:
            pass

    # Remove duplicates
    log_files = list(set(log_files))

    if clear:
        if not log_files:
            console.print("[yellow]No Orchestra logs found to clear.[/yellow]")
            return

        console.print(f"[bold yellow]Found {len(log_files)} log file(s):[/bold yellow]")
        for log_file in log_files:
            console.print(f"  [dim]-[/dim] {log_file}")

        console.print("\n[bold red]⚠️  This will delete all Orchestra logs.[/bold red]")
        if click.confirm("Continue?"):
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
        console.print(
            "[dim]Logs are created when extensions are used in Claude Code.[/dim]"
        )
        console.print(
            "[dim]Try running a command first, e.g., 'orchestra task status'[/dim]"
        )
        return

    # Display or tail logs
    if tail:
        console.print(
            f"[bold green]📜 Following {len(log_files)} log file(s):[/bold green]"
        )
        for log_file in log_files:
            console.print(f"  [dim]-[/dim] {log_file}")
        console.print("\n[dim]Press Ctrl+C to stop...[/dim]\n")

        try:
            if platform.system() == "Windows":
                cmd = [
                    "powershell",
                    "-Command",
                    f"Get-Content {' '.join(log_files)} -Wait",
                ]
            else:
                cmd = ["tail", "-f"] + log_files

            subprocess.run(cmd, check=False)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped tailing logs.[/yellow]")
    else:
        # Display logs with nice formatting
        console.print(
            f"[bold green]📜 Orchestra Logs[/bold green] ({len(log_files)} file(s) found)\n"
        )

        for log_file in log_files:
            # Extract extension name from log file
            if "task_monitor.log" in log_file:
                ext_name = "Task Monitor"
                ext_color = "cyan"
            elif "timemachine.log" in log_file:
                ext_name = "TimeMachine"
                ext_color = "magenta"
            elif "tidy.log" in log_file:
                ext_name = "Tidy"
                ext_color = "green"
            elif "tester.log" in log_file:
                ext_name = "Tester"
                ext_color = "yellow"
            elif "plancheck.log" in log_file:
                ext_name = "Plancheck"
                ext_color = "blue"
            else:
                ext_name = "Unknown"
                ext_color = "white"

            console.print(f"[bold {ext_color}]═══ {ext_name} ═══[/bold {ext_color}]")
            console.print(f"[dim]{log_file}[/dim]")

            try:
                with open(log_file) as f:
                    lines = f.readlines()
                    if len(lines) > 50:
                        console.print(
                            f"[dim]... showing last 50 lines (file has {len(lines)} total) ...[/dim]"
                        )
                        lines = lines[-50:]

                    for line in lines:
                        line = line.rstrip()

                        # If no_truncate is False and line contains [truncated], show a hint
                        if not no_truncate and "[truncated]" in line:
                            line = line.replace(
                                "[truncated]",
                                "[truncated - use --no-truncate to see full]",
                            )

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

        console.print(
            "[dim]Tip: Use 'orchestra logs --tail' to follow logs in real-time[/dim]"
        )
        if not no_truncate:
            console.print(
                "[dim]     Use 'orchestra logs --no-truncate' to see full log values[/dim]"
            )

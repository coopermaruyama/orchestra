"""Logs command for Orchestra CLI"""

import os
import platform
import subprocess
import time

import click
from rich.console import Console

console = Console()


def _format_log_line(line: str, no_truncate: bool, verbose: bool = False) -> str:
    """Format a log line with colors"""
    line = line.rstrip()
    if not line:
        return ""

    # If no_truncate is False and line contains [truncated], show a hint
    if not no_truncate and "[truncated]" in line:
        line = line.replace(
            "[truncated]",
            "[dim][truncated - use --no-truncate to see full][/dim]",
        )

    # Parse Orchestra log format: timestamp - extension_name - level - message
    parts = line.split(" - ", 3)
    if len(parts) >= 4:
        timestamp_str = parts[0]
        extension_name = parts[1]
        level = parts[2]
        message = parts[3]

        # Format shorter timestamp (HH:MM:SS)
        try:
            # Parse full timestamp and extract time part
            from datetime import datetime
            dt = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
            short_time = dt.strftime("%H:%M:%S")
        except:
            # Fallback if timestamp parsing fails
            short_time = timestamp_str.split()[-1].split(",")[0] if " " in timestamp_str else timestamp_str

        # Abbreviate extension name to fixed width (8 chars) and get background color
        ext_abbrev = _abbreviate_extension(extension_name, 8)
        ext_colored = _color_extension_name(extension_name, ext_abbrev)

        # Remove function/line number from message unless verbose
        if not verbose and " - " in message:
            # Remove the function:line part (e.g., "handle_hook:157 - actual message")
            msg_parts = message.split(" - ", 1)
            if len(msg_parts) > 1 and ":" in msg_parts[0]:
                message = msg_parts[1]

        # Color code based on log level
        if "ERROR" in level or "CRITICAL" in level:
            return f"[dim black]{short_time}[/dim black] {ext_colored} [bold red]{level:5}[/bold red] [red]{message}[/red]"
        elif "WARNING" in level or "WARN" in level:
            return f"[dim black]{short_time}[/dim black] {ext_colored} [bold yellow]{level:5}[/bold yellow] [yellow]{message}[/yellow]"
        elif "DEBUG" in level:
            return f"[dim black]{short_time} {ext_colored} {level:5} {message}[/dim black]"
        elif "INFO" in level:
            return f"[dim black]{short_time}[/dim black] {ext_colored} [bold blue]{level:5}[/bold blue] {message}"
        else:
            return f"[dim black]{short_time}[/dim black] {ext_colored} [bold]{level:5}[/bold] {message}"
    else:
        # Fallback for non-standard log format
        if "ERROR" in line or "CRITICAL" in line:
            return f"[red]{line}[/red]"
        elif "WARNING" in line or "WARN" in line:
            return f"[yellow]{line}[/yellow]"
        elif "DEBUG" in line:
            return f"[dim]{line}[/dim]"
        elif "INFO" in line:
            return f"[blue]{line}[/blue]"
        else:
            return line


def _abbreviate_extension(name: str, width: int) -> str:
    """Abbreviate extension name to fixed width and center it"""
    # Smart abbreviation for common names
    abbreviations = {
        "task_monitor": "task",
        "timemachine": "tmach",
        "plancheck": "pchk",
        "tester": "test",
        "tidy": "tidy",
    }

    if name in abbreviations:
        short_name = abbreviations[name]
    elif len(name) <= width:
        short_name = name
    else:
        # Generic abbreviation: take first chars
        short_name = name[:width-1] + "…"

    # Center the text within the width
    return short_name.center(width)


def _color_extension_name(extension_name: str, abbrev_name: str) -> str:
    """Apply background color to extension name based on extension type"""
    # Color mapping for different extensions
    extension_colors = {
        "task_monitor": "cyan",      # Cyan background
        "timemachine": "cyan",    # Magenta background
        "plancheck": "cyan",         # Blue background
        "tester": "cyan",          # Yellow background
        "tidy": "cyan",             # Green background
    }

    color = extension_colors.get(extension_name, "white on black")  # Default
    return f"[{color}]{abbrev_name}[/{color}]"


def _show_recent_logs(log_files: list[str], no_truncate: bool, verbose: bool = False) -> None:
    """Show recent log lines from all files combined, sorted by timestamp"""
    all_lines = []

    # Collect lines from all files with timestamps
    for log_file in log_files:
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
                # Take last 100 lines from each file to ensure we get a good mix
                recent_lines = lines[-100:] if len(lines) > 100 else lines

                for line in recent_lines:
                    line = line.rstrip()
                    if not line:
                        continue

                    # Try to extract timestamp for sorting
                    parts = line.split(" - ", 1)
                    if len(parts) >= 1:
                        timestamp_str = parts[0]
                        try:
                            # Parse timestamp for sorting
                            from datetime import datetime
                            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
                            all_lines.append((timestamp, line))
                        except:
                            # If timestamp parsing fails, use current time (will sort to end)
                            all_lines.append((datetime.now(), line))
        except Exception:
            continue

    # Sort by timestamp and take last 50
    all_lines.sort(key=lambda x: x[0])
    recent_tuples = all_lines[-50:] if len(all_lines) > 50 else all_lines

    if recent_tuples:
        console.print("[dim]--- Recent logs ---[/dim]")
        for _, line in recent_tuples:
            formatted_line = _format_log_line(line, no_truncate, verbose)
            if formatted_line:
                console.print(formatted_line, style="white")
        console.print("[dim]--- Streaming new logs ---[/dim]")


def _stream_logs(log_files: list[str], no_truncate: bool, verbose: bool = False) -> None:
    """Stream log files with color formatting"""
    # Track file positions and handles
    file_handles = {}
    file_positions = {}

    try:
        # First, show the last 50 lines from all files combined
        _show_recent_logs(log_files, no_truncate, verbose)

        # Open all files and seek to end for streaming
        for log_file in log_files:
            try:
                handle = open(log_file, 'r')
                handle.seek(0, 2)  # Seek to end
                file_handles[log_file] = handle
                file_positions[log_file] = handle.tell()
            except Exception:
                continue

        if not file_handles:
            console.print("[red]Could not open any log files for streaming[/red]")
            return

        while True:
            any_output = False

            # Check each file for new content
            for log_file, handle in file_handles.items():
                try:
                    # Check if file has grown
                    handle.seek(0, 2)  # Seek to end
                    current_size = handle.tell()

                    if current_size > file_positions[log_file]:
                        # File has new content
                        handle.seek(file_positions[log_file])
                        new_lines = handle.readlines()

                        for line in new_lines:
                            formatted_line = _format_log_line(line, no_truncate, verbose)
                            if formatted_line:
                                console.print(formatted_line)
                                any_output = True

                        file_positions[log_file] = handle.tell()

                except Exception:
                    # File might have been rotated or deleted
                    continue

            if not any_output:
                time.sleep(0.1)  # Short sleep to avoid busy waiting

    except KeyboardInterrupt:
        pass
    finally:
        # Close all file handles
        for handle in file_handles.values():
            try:
                handle.close()
            except Exception:
                pass


@click.command()
@click.argument("extension", required=False)
@click.option("--tail", "-f", is_flag=True, help="Follow log output")
@click.option("--clear", is_flag=True, help="Clear all Orchestra logs")
@click.option(
    "--no-truncate", is_flag=True, help="Show full log values without truncation"
)
@click.option("--verbose", "-v", is_flag=True, help="Show function names and line numbers")
def logs(extension: str, tail: bool, clear: bool, no_truncate: bool, verbose: bool) -> None:
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

        # Custom streaming implementation to preserve colors
        _stream_logs(log_files, no_truncate, verbose)
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

            console.print(f"\n[bold {ext_color}]┌─── {ext_name} ───[/bold {ext_color}]")
            console.print(f"[bold {ext_color}]│[/bold {ext_color}] [dim]{log_file}[/dim]")
            console.print(f"[bold {ext_color}]└─────{'─' * len(ext_name)}───[/bold {ext_color}]")

            try:
                with open(log_file) as f:
                    lines = f.readlines()
                    if len(lines) > 50:
                        console.print(
                            f"[dim]... showing last 50 lines (file has {len(lines)} total) ...[/dim]"
                        )
                        lines = lines[-50:]

                    for line in lines:
                        formatted_line = _format_log_line(line, no_truncate, verbose)
                        if formatted_line:
                            console.print(formatted_line)

            except Exception as e:
                console.print(f"[red]Error reading log: {e}[/red]")

        console.print(
            "[dim]Tip: Use 'orchestra logs --tail' to follow logs in real-time[/dim]"
        )
        if not no_truncate:
            console.print(
                "[dim]     Use 'orchestra logs --no-truncate' to see full log values[/dim]"
            )
        if not verbose:
            console.print(
                "[dim]     Use 'orchestra logs --verbose' to show function names and line numbers[/dim]"
            )

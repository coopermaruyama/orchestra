"""Task command group for Orchestra CLI"""

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group()
def task() -> None:
    """Task Monitor commands

    Keep Claude focused on your task requirements. Prevents scope creep,
    tracks progress, and guides you through requirements step by step.
    """


def run_task_command(subcommand: str, *args: str) -> None:
    """Helper to run task monitor commands"""
    # Find the task_monitor.py script
    local_script = Path(".claude") / "orchestra" / "task" / "task_monitor.py"
    global_script = Path.home() / ".claude" / "orchestra" / "task" / "task_monitor.py"

    script_path = None
    if local_script.exists():
        script_path = local_script
    elif global_script.exists():
        script_path = global_script
    else:
        console.print(
            "[bold red]❌ Task monitor not enabled.[/bold red] Run: [cyan]orchestra enable task[/cyan]"
        )
        return

    # Execute the task monitor script with the subcommand
    try:
        cmd = [sys.executable, str(script_path), subcommand] + list(args)
        subprocess.run(cmd, check=False)
    except Exception as e:
        console.print(f"[bold red]❌ Error running task command:[/bold red] {e}")


@task.command()
def start() -> None:
    """Interactive task setup"""
    run_task_command("start")


@task.command()
def status() -> None:
    """Check current progress"""
    run_task_command("status")


@task.command()
def next() -> None:
    """Show next priority action"""
    run_task_command("next")


@task.command()
def complete() -> None:
    """Mark current requirement done"""
    run_task_command("complete")


@task.command()
def focus() -> None:
    """Quick focus reminder"""
    run_task_command("focus")

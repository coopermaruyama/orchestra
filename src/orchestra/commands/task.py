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
    # Use the installed module directly
    try:
        import os
        from orchestra.extensions.task.task_monitor import main as task_main
        
        # Set environment variable to prevent recursive calls
        original_env = os.environ.get("ORCHESTRA_INTERNAL_CALL")
        os.environ["ORCHESTRA_INTERNAL_CALL"] = "1"
        
        # Set up sys.argv to simulate command line arguments
        original_argv = sys.argv
        sys.argv = ["task_monitor.py", subcommand] + list(args)
        
        try:
            task_main()
        finally:
            sys.argv = original_argv
            if original_env is None:
                os.environ.pop("ORCHESTRA_INTERNAL_CALL", None)
            else:
                os.environ["ORCHESTRA_INTERNAL_CALL"] = original_env
            
    except ImportError:
        console.print(
            "[bold red]❌ Task monitor not available.[/bold red] Ensure orchestra is properly installed."
        )
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

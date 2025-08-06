"""Tidy command group for Orchestra CLI"""

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group()
def tidy() -> None:
    """Tidy commands

    Automated code quality checker that ensures code meets project standards.
    Runs linters, formatters, and type checkers after Claude modifies files.
    """


def run_tidy_command(subcommand: str, *args: str) -> None:
    """Helper to run tidy commands"""
    # Use the installed module directly
    try:
        import os
        from orchestra.extensions.tidy.tidy_monitor import main as tidy_main
        
        # Set environment variable to prevent recursive calls
        original_env = os.environ.get("ORCHESTRA_INTERNAL_CALL")
        os.environ["ORCHESTRA_INTERNAL_CALL"] = "1"
        
        # Set up sys.argv to simulate command line arguments
        original_argv = sys.argv
        sys.argv = ["tidy_monitor.py", subcommand] + list(args)
        
        try:
            tidy_main()
        finally:
            sys.argv = original_argv
            if original_env is None:
                os.environ.pop("ORCHESTRA_INTERNAL_CALL", None)
            else:
                os.environ["ORCHESTRA_INTERNAL_CALL"] = original_env
            
    except ImportError:
        console.print(
            "[bold red]❌ Tidy not available.[/bold red] Ensure orchestra is properly installed."
        )
    except Exception as e:
        console.print(f"[bold red]❌ Error running tidy command:[/bold red] {e}")


@tidy.command()
def init() -> None:
    """Initialize tidy for your project"""
    run_tidy_command("init")


@tidy.command()
@click.argument("files", nargs=-1)
def check(files: tuple[str, ...]) -> None:
    """Run code quality checks"""
    run_tidy_command("check", *files)


@tidy.command()
@click.argument("files", nargs=-1)
def fix(files: tuple[str, ...]) -> None:
    """Auto-fix code quality issues"""
    run_tidy_command("fix", *files)


@tidy.command()
def status() -> None:
    """Show current configuration and status"""
    run_tidy_command("status")


@tidy.command()
@click.argument("type", type=click.Choice(["do", "dont"]))
@click.argument("example")
def learn(example_type: str, example: str) -> None:
    """Add do/don't examples"""
    run_tidy_command("learn", example_type, example)

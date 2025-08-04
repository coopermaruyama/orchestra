"""Tidy command group for Orchestra CLI"""

import sys
import subprocess
from pathlib import Path
import click
from rich.console import Console

console = Console()


@click.group()
def tidy():
    """Tidy commands
    
    Automated code quality checker that ensures code meets project standards.
    Runs linters, formatters, and type checkers after Claude modifies files.
    """
    pass


def run_tidy_command(subcommand, *args):
    """Helper to run tidy commands"""
    # Find the tidy_monitor.py script
    local_script = Path(".claude") / "orchestra" / "tidy" / "tidy_monitor.py"
    global_script = Path.home() / ".claude" / "orchestra" / "tidy" / "tidy_monitor.py"
    
    script_path = None
    if local_script.exists():
        script_path = local_script
    elif global_script.exists():
        script_path = global_script
    else:
        console.print("[bold red]❌ Tidy not enabled.[/bold red] Run: [cyan]orchestra enable tidy[/cyan]")
        return
    
    # Execute the tidy monitor script with the subcommand
    try:
        cmd = [sys.executable, str(script_path), subcommand] + list(args)
        subprocess.run(cmd, check=False)
    except Exception as e:
        console.print(f"[bold red]❌ Error running tidy command:[/bold red] {e}")


@tidy.command()
def init():
    """Initialize tidy for your project"""
    run_tidy_command("init")


@tidy.command()
@click.argument('files', nargs=-1)
def check(files):
    """Run code quality checks"""
    run_tidy_command("check", *files)


@tidy.command()
@click.argument('files', nargs=-1)
def fix(files):
    """Auto-fix code quality issues"""
    run_tidy_command("fix", *files)


@tidy.command()
def status():
    """Show current configuration and status"""
    run_tidy_command("status")


@tidy.command()
@click.argument('type', type=click.Choice(['do', 'dont']))
@click.argument('example')
def learn(type, example):
    """Add do/don't examples"""
    run_tidy_command("learn", type, example)


@tidy.command()
@click.argument('action', type=click.Choice(['start', 'stop', 'status']))
def sidecar(action):
    """Manage background fix daemon"""
    run_tidy_command("sidecar", action)
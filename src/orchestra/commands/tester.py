"""Tester command group for Orchestra CLI"""

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group()
def tester() -> None:
    """Tester commands

    Automatically test completed tasks using calibrated testing methods.
    Learns your project's testing approach through interactive calibration.
    """


def run_tester_command(subcommand: str, *args: str) -> None:
    """Helper to run tester commands"""
    # Find the tester_monitor.py script
    local_script = Path(".claude") / "orchestra" / "tester" / "tester_monitor.py"
    global_script = (
        Path.home() / ".claude" / "orchestra" / "tester" / "tester_monitor.py"
    )

    script_path = None
    if local_script.exists():
        script_path = local_script
    elif global_script.exists():
        script_path = global_script
    else:
        console.print(
            "[bold red]❌ Tester not enabled.[/bold red] Run: [cyan]orchestra enable tester[/cyan]"
        )
        return

    # Execute the tester monitor script with the subcommand
    try:
        cmd = [sys.executable, str(script_path), subcommand] + list(args)
        subprocess.run(cmd, check=False)
    except Exception as e:
        console.print(f"[bold red]❌ Error running tester command:[/bold red] {e}")


@tester.command()
def calibrate() -> None:
    """Set up testing through interactive calibration"""
    run_tester_command("calibrate")


@tester.command()
def test() -> None:
    """Run tests for completed tasks"""
    run_tester_command("test")


@tester.command()
def status() -> None:
    """Show calibration status and test results"""
    run_tester_command("status")

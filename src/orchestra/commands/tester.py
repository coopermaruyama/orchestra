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
    # Use the installed module directly
    try:
        from orchestra.extensions.tester.tester_monitor import main as tester_main
        
        # Set up sys.argv to simulate command line arguments
        original_argv = sys.argv
        sys.argv = ["tester_monitor.py", subcommand] + list(args)
        
        try:
            tester_main()
        finally:
            sys.argv = original_argv
            
    except ImportError:
        console.print(
            "[bold red]❌ Tester not available.[/bold red] Ensure orchestra is properly installed."
        )
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

"""Plancheck command group for Orchestra CLI"""

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group()
def plancheck() -> None:
    """Plancheck commands
    
    Plan monitoring and review system that automatically saves plans
    and provides review and improvement capabilities.
    """


def run_plancheck_command(subcommand: str, *args: str) -> None:
    """Helper to run plancheck commands"""
    # Use the installed module directly
    try:
        import os
        from orchestra.extensions.plancheck.plancheck_monitor import main as plancheck_main
        
        # Set environment variable to prevent recursive calls
        original_env = os.environ.get("ORCHESTRA_INTERNAL_CALL")
        os.environ["ORCHESTRA_INTERNAL_CALL"] = "1"
        
        # Set up sys.argv to simulate command line arguments
        original_argv = sys.argv
        sys.argv = ["plancheck_monitor.py", subcommand] + list(args)
        
        try:
            plancheck_main()
        finally:
            sys.argv = original_argv
            if original_env is None:
                os.environ.pop("ORCHESTRA_INTERNAL_CALL", None)
            else:
                os.environ["ORCHESTRA_INTERNAL_CALL"] = original_env
            
    except ImportError:
        console.print(
            "[bold red]❌ Plancheck not available.[/bold red] Ensure orchestra is properly installed."
        )
    except Exception as e:
        console.print(f"[bold red]❌ Error running plancheck command:[/bold red] {e}")


@plancheck.command()
def status() -> None:
    """View plancheck status"""
    run_plancheck_command("status")


@plancheck.command()
@click.argument("plan_path")
def review(plan_path: str) -> None:
    """Review a plan file
    
    PLAN_PATH: Path to the plan file to review
    """
    run_plancheck_command("review", plan_path)


@plancheck.command()
@click.argument("plan_path")
def improve(plan_path: str) -> None:
    """Review and improve a plan file
    
    First runs review to get feedback, then uses that feedback 
    to revise the plan.
    
    PLAN_PATH: Path to the plan file to improve
    """
    run_plancheck_command("improve", plan_path)
"""TimeMachine command group for Orchestra CLI"""

import subprocess
import sys
from pathlib import Path

import click
from rich.console import Console

console = Console()


@click.group()
def timemachine() -> None:
    """TimeMachine commands

    Automatic git checkpointing for every conversation turn. Travel back
    in time to any previous state with full prompt history.
    """


def run_timemachine_command(subcommand: str, *args: str) -> None:
    """Helper to run timemachine commands"""
    # Use the installed module directly
    try:
        from orchestra.extensions.timemachine.timemachine_monitor import main as timemachine_main
        
        # Set up sys.argv to simulate command line arguments
        original_argv = sys.argv
        sys.argv = ["timemachine_monitor.py", subcommand] + list(args)
        
        try:
            timemachine_main()
        finally:
            sys.argv = original_argv
            
    except ImportError:
        console.print(
            "[bold red]❌ TimeMachine not available.[/bold red] Ensure orchestra is properly installed."
        )
    except Exception as e:
        console.print(f"[bold red]❌ Error running timemachine command:[/bold red] {e}")


@timemachine.command(name="list")
def list_checkpoints() -> None:
    """View conversation checkpoints"""
    run_timemachine_command("list")


@timemachine.command()
@click.argument("checkpoint_id")
def checkout(checkpoint_id: str) -> None:
    """Checkout a specific checkpoint"""
    run_timemachine_command("checkout", checkpoint_id)


@timemachine.command()
@click.argument("checkpoint_id")
def view(checkpoint_id: str) -> None:
    """View checkpoint details"""
    run_timemachine_command("view", checkpoint_id)


@timemachine.command()
@click.argument("n", type=int)
def rollback(n: int) -> None:
    """Rollback n conversation turns"""
    run_timemachine_command("rollback", str(n))


@timemachine.command()
@click.option("--force", is_flag=True, help="Force deletion without confirmation")
def prune(force: bool) -> None:
    """Delete all TimeMachine checkpoints and tags"""
    run_timemachine_command("prune", "--force" if force else "")

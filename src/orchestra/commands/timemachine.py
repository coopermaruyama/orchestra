"""TimeMachine command group for Orchestra CLI"""

import sys
import subprocess
from pathlib import Path
import click
from rich.console import Console

console = Console()


@click.group()
def timemachine():
    """TimeMachine commands
    
    Automatic git checkpointing for every conversation turn. Travel back
    in time to any previous state with full prompt history.
    """
    pass


def run_timemachine_command(subcommand, *args):
    """Helper to run timemachine commands"""
    # Find the timemachine_monitor.py script
    local_script = Path(".claude") / "orchestra" / "timemachine" / "timemachine_monitor.py"
    global_script = Path.home() / ".claude" / "orchestra" / "timemachine" / "timemachine_monitor.py"
    
    script_path = None
    if local_script.exists():
        script_path = local_script
    elif global_script.exists():
        script_path = global_script
    else:
        console.print("[bold red]❌ TimeMachine not enabled.[/bold red] Run: [cyan]orchestra enable timemachine[/cyan]")
        return
    
    # Execute the timemachine monitor script with the subcommand
    try:
        cmd = [sys.executable, str(script_path), subcommand] + list(args)
        subprocess.run(cmd, check=False)
    except Exception as e:
        console.print(f"[bold red]❌ Error running timemachine command:[/bold red] {e}")


@timemachine.command(name='list')
def list_checkpoints():
    """View conversation checkpoints"""
    run_timemachine_command("list")


@timemachine.command()
@click.argument('checkpoint_id')
def checkout(checkpoint_id):
    """Checkout a specific checkpoint"""
    run_timemachine_command("checkout", checkpoint_id)


@timemachine.command()
@click.argument('checkpoint_id')
def view(checkpoint_id):
    """View checkpoint details"""
    run_timemachine_command("view", checkpoint_id)


@timemachine.command()
@click.argument('n', type=int)
def rollback(n):
    """Rollback n conversation turns"""
    run_timemachine_command("rollback", str(n))
"""Enable command for Orchestra CLI"""

import click
from rich.console import Console

from orchestra.core import Orchestra

console = Console()


@click.command()
@click.argument("extension", required=False)
@click.option(
    "--global", "global_scope", is_flag=True, help="Enable in global scope instead of project (not recommended)"
)
def enable(extension, global_scope):
    """Enable an Orchestra extension

    If no extension is specified, enables all available extensions.
    Defaults to project scope for better isolation.
    """
    orchestra = Orchestra()
    scope = "global" if global_scope else "project"

    if extension:
        # Enable specific extension
        orchestra.enable(extension, scope)
    else:
        # Enable all extensions
        console.print(
            "[bold blue]🎼 Enabling all Orchestra extensions...[/bold blue]\n"
        )

        for ext_id in orchestra.extensions.keys():
            console.print(f"\n[bold cyan]📦 Enabling {ext_id}...[/bold cyan]")
            orchestra.enable(ext_id, scope)

        console.print("\n[bold green]✨ All extensions enabled![/bold green]")
        console.print("\n[bold yellow]Quick start commands:[/bold yellow]")
        console.print("  [cyan]/task start[/cyan]         - Start a new focused task")
        console.print(
            "  [cyan]/timemachine list[/cyan]   - View conversation checkpoints"
        )
        console.print(
            "  [cyan]/tidy init[/cyan]          - Initialize code quality checks"
        )
        console.print(
            "  [cyan]/tester calibrate[/cyan]   - Set up testing for your project"
        )

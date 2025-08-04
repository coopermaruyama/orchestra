#!/usr/bin/env python3
"""
Orchestra CLI - Claude Code Extension Manager
"""

import click
from rich.console import Console

from orchestra.commands.disable import disable
from orchestra.commands.enable import enable
from orchestra.commands.hook import hook
from orchestra.commands.list_cmd import list_extensions
from orchestra.commands.logs import logs
from orchestra.commands.status import status
from orchestra.commands.task import task
from orchestra.commands.tester import tester
from orchestra.commands.tidy import tidy
from orchestra.commands.timemachine import timemachine

console = Console()


@click.group(invoke_without_command=True)
@click.version_option(version="0.7.0", prog_name="Orchestra")
@click.pass_context
def cli(ctx: click.Context) -> None:
    """🎼 Orchestra - Claude Code Extension Manager

    Orchestrate your Claude Code workflow with focused extensions.
    """
    if ctx.invoked_subcommand is None:
        # Show help if no command is provided
        click.echo(ctx.get_help())


# Register commands
cli.add_command(enable)
cli.add_command(disable)
cli.add_command(list_extensions, name="list")
cli.add_command(status)
cli.add_command(logs)
cli.add_command(hook)
cli.add_command(task)
cli.add_command(timemachine)
cli.add_command(tidy)
cli.add_command(tester)


def main() -> None:
    """Main entry point for the CLI"""
    try:
        cli()
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise


if __name__ == "__main__":
    main()

"""Disable command for Orchestra CLI"""

import click
from rich.console import Console

from orchestra.core import Orchestra

console = Console()


@click.command()
@click.argument('extension')
@click.option('--project', is_flag=True, help='Disable from project scope instead of global')
def disable(extension, project):
    """Disable an Orchestra extension"""
    orchestra = Orchestra()
    scope = "local" if project else "global"
    orchestra.disable(extension, scope)
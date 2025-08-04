"""Status command for Orchestra CLI"""

import click

from orchestra.core import Orchestra


@click.command()
def status() -> None:
    """Show detailed status of all extensions"""
    orchestra = Orchestra()
    orchestra.status()

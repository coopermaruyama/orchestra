"""List command for Orchestra CLI"""

import click

from orchestra.core import Orchestra


@click.command()
def list_extensions():
    """List enabled extensions"""
    orchestra = Orchestra()
    orchestra.list_extensions()
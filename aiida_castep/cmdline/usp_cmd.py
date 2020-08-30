"""
Commandline plugin module for aiida CASTEP plugin
"""
from __future__ import print_function
from __future__ import absolute_import
import click

from aiida.cmdline.commands.cmd_data import verdi_data


@verdi_data.group('castep-usp')
def usp_cmd():
    """Commandline interface for working with UspData"""
    pass


@usp_cmd.command(name="listfamilies")
@click.option(
    '--element',
    '-e',
    multiple=True,
    help=
    "Show families contenting this element only. Can be passed multiple times")
@click.option('--with_description', '-d', is_flag=True)
def listfamilies(element, with_description):
    """
    Deprecated - please use `castep-otfg listfamilies`.
    """
    click.echo(
        "USP families are unified as OTFGGroup, please use `castep-otfg listfamilies` to list the families"
    )
    return

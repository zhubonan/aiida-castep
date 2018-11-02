"""
Commandline plugin module for aiida CASTEP plugin
"""
from __future__ import print_function
import click

from aiida.cmdline.commands import data_cmd
from aiida.cmdline.dbenv_lazyloading import load_dbenv_if_not_loaded


@data_cmd.group('castep-otfg')
def otfg_cmd():
    """Commandline interface for working with OTFGData"""
    pass


@otfg_cmd.command(name="listfamilies")
@click.option(
    '--element',
    '-e',
    multiple=True,
    help=
    "Show families contenting this element only. Can be passed multiple times")
@click.option('--with_description', '-d', is_flag=True)
def listfamilies(element, with_description):
    """List avaliable OtfgData families"""
    load_dbenv_if_not_loaded()
    from aiida.orm import QueryBuilder
    from aiida_castep.data.otfg import OTFGGROUP_TYPE
    from aiida.orm import DataFactory, Group
    UspData = DataFactory("castep.otfgdata")
    q = QueryBuilder()
    q.append(UspData, tag="otfgdata")
    if element:
        q.add_filter("otfgdata", {
            "attributes.element": {
                "or": [{
                    'in': element
                }, {
                    '==': "LIBRARY"
                }]
            }
        })
    q.append(
        Group,
        tag='group',
        group_of=UspData,
        filters={'type': OTFGGROUP_TYPE},
        project=['name', 'description'])
    q.distinct()
    if q.count() > 0:
        for res in q.dict():
            group_name = res.get("group").get("name")
            group_desc = res.get("group").get("description")
            # Count the number of pseudos in this group
            q = QueryBuilder()
            q.append(
                Group, tag='thisgroup', filters={"name": {
                    'like': group_name
                }})
            q.append(UspData, project=["id"], member_of='thisgroup')

            if with_description:
                description_string = ": {}".format(group_desc)
            else:
                description_string = ""

            click.echo("* {} [{} pseudos]{}".format(group_name, q.count(),
                                                    description_string))

    else:
        click.echo("No valid OTFG pseudopotential family found.")

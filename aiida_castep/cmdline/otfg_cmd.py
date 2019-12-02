"""
Commandline plugin module for aiida CASTEP plugin
"""
from __future__ import print_function
from __future__ import absolute_import
import click

from aiida.cmdline.commands.cmd_data import verdi_data


@verdi_data.group('castep-otfg')
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
    from aiida.orm import QueryBuilder, Group
    from aiida_castep.data.otfg import OTFGGROUP_TYPE
    from aiida.plugins import DataFactory

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
    q.append(Group,
             tag='group',
             with_node=UspData,
             filters={'type_string': OTFGGROUP_TYPE},
             project=['label', 'description'])
    q.distinct()
    if q.count() > 0:
        for res in q.dict():
            group_label = res.get("group").get("label")
            group_desc = res.get("group").get("description")
            # Count the number of pseudos in this group
            q = QueryBuilder()
            q.append(Group,
                     tag='thisgroup',
                     filters={"label": {
                         'like': group_label
                     }})
            q.append(UspData, project=["id"], member_of='thisgroup')

            if with_description:
                description_string = ": {}".format(group_desc)
            else:
                description_string = ""

            click.echo("* {} [{} pseudos]{}".format(group_label, q.count(),
                                                    description_string))

    else:
        click.echo("No valid OTFG pseudopotential family found.")

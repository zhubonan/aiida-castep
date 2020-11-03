"""
Commandline plugin module for aiida CASTEP plugin
"""
import click

from aiida.cmdline.commands.cmd_data import verdi_data

# pylint: disable=import-outside-toplevel


@verdi_data.group('castep-pseudos')
def pseudos_cmd():
    """Commandline interface for working with OTFGData"""
@pseudos_cmd.command(name="migrate-families")
def migrate_families():
    """
    Migrate to new style Group for pseudopotential families as implemented in
    `aiida-core >= 1.2.0`.

    This command should be run once after upgrading `aiida-castep` to 1.2.0,
    to re-enable working with pseudopotential families.
    """
    from aiida_castep.data.otfg import migrate_otfg_family
    click.echo("Migrating to new style Group")
    migrate_otfg_family()
    click.echo(
        "Finished! Note: No need to run this command again for this profile.")


@pseudos_cmd.command(name="listfamilies")
@click.option(
    '--element',
    '-e',
    multiple=True,
    help=
    "Show families contenting this element only. Can be passed multiple times")
@click.option('--with_description', '-d', is_flag=True)
def listfamilies(element, with_description):
    """List available OtfgData families"""
    from aiida.orm import QueryBuilder, Node
    from aiida_castep.data.otfg import OTFGGroup

    qbd = QueryBuilder()
    qbd.append(Node, tag="otfgdata")
    if element:
        qbd.add_filter("otfgdata", {
            "attributes.element": {
                "or": [{
                    'in': element
                }, {
                    '==': "LIBRARY"
                }]
            }
        })
    qbd.append(OTFGGroup,
               tag='group',
               with_node='otfgdata',
               project=['label', 'description'])
    qbd.distinct()
    if qbd.count() > 0:
        for res in qbd.dict():
            group_label = res.get("group").get("label")
            group_desc = res.get("group").get("description")
            # Count the number of pseudos in this group
            qbd = QueryBuilder()
            qbd.append(OTFGGroup,
                       tag='thisgroup',
                       filters={"label": {
                           'like': group_label
                       }})
            qbd.append(Node, project=["id"], with_group='thisgroup')

            if with_description:
                description_string = ": {}".format(group_desc)
            else:
                description_string = ""

            click.echo("* {} [{} pseudos]{}".format(group_label, qbd.count(),
                                                    description_string))

    else:
        click.echo("No valid pseudopotential family found.")

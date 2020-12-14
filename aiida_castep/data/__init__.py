"""
Module for additional Data classes
"""

from aiida.orm.nodes.data.upf import UpfData
from aiida.common import NotExistent, MultipleObjectsError

from .otfg import OTFGData
from .usp import UspData


def get_pseudos_from_structure(structure, family_name):
    """
    Given a family name (of UpfData or OTFGData) and a AiiDA
    structure, return a dictionary associating each kind name with its
    pseduopotential object.

    :raise MultipleObjectsError: if more than one UPF for the same element is
       found in the group.
    :raise NotExistent: if no UPF for an element in the group is
       found in the group.

    :returns: A dictionary maps kind to the psueodpotential node
    """

    family_pseudos = {}

    try:
        family_upf = UpfData.get_upf_group(family_name)
    except NotExistent:
        family_upf = []
    try:
        family_otfg = OTFGData.get_otfg_group(family_name)
    except NotExistent:
        family_otfg = []

    valid_count = 0
    for fam in [family_upf, family_otfg]:
        if fam:
            valid_count += 1
            family = fam

    if valid_count == 0:
        raise NotExistent(
            "Cannot find matching group among UspData, UpfData and OTFGData")

    # This is necessary?
    if valid_count > 1:
        raise MultipleObjectsError("Name duplication detected")

    # Checking uniquess for each element
    for node in family.nodes:
        if isinstance(node, (UpfData, UspData, OTFGData)):
            if node.element in family_pseudos:
                raise MultipleObjectsError(
                    "More than one pseudo for element {} found in "
                    "family {}".format(node.element, family_name))
            family_pseudos[node.element] = node

    pseudo_list = {}
    for kind in structure.kinds:
        symbol = kind.symbol
        try:
            pseudo_list[kind.name] = family_pseudos[symbol]
        except KeyError:

            # May be we have a "LIBRARY" wild card here
            try:
                pseudo_list[kind.name] = family_pseudos["LIBRARY"]

            except KeyError:
                raise NotExistent(
                    "No pseudo for element {} found in family {}".format(
                        symbol, family_pseudos))

    return pseudo_list

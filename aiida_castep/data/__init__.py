"""
Module for additional Data classes
"""

from aiida.orm.nodes.data.upf import UpfData
from aiida.orm import Group
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

    # Try to get the pseudopotentials that are managed by aiida-pseudo
    result = _get_pseudos_from_aiida_pseudo(structure, family_name)
    if result:
        return result

    family_pseudos = {}

    try:
        family_upf = [UpfData.get_upf_group(family_name)]
    except NotExistent:
        family_upf = []
    try:
        family_otfg = [OTFGData.get_otfg_group(family_name)]
    except NotExistent:
        family_otfg = []

    all_families = family_otfg + family_upf
    if len(all_families) == 0:
        raise NotExistent(
            "Cannot find matching group among UspData, UpfData and OTFGData")

    if len(all_families) > 1:
        raise MultipleObjectsError(
            f"Multiple groups with label {family_name} detected")

    family = all_families[0]

    # Checking uniqueness for each element
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
        if symbol in family_pseudos:
            pseudo_list[kind.name] = family_pseudos[symbol]
        elif 'LIBRARY' in family_pseudos:
            pseudo_list[kind.name] = family_pseudos['LIBRARY']

        else:
            raise NotExistent(
                "No pseudo for element {} found in family {}".format(
                    symbol, family_pseudos))

    return pseudo_list


def _get_pseudos_from_aiida_pseudo(structure, label):
    """
    Attempt to get pseudopotentials that are managed by the `aiida-pseudo` package

    :param structure: A ``StructureData`` for which the pseudopotentials needs to be selected.
    :param label: The name of the pseudopotential family

    :returns: A dictionary of each element and its pseudopotential.
    """

    try:
        group = Group.objects.get(label=label,
                                  type_string={'like': 'pseudo.family%'})
    except NotExistent:
        return []

    # Make sure the group is a group from aiida-pseudo
    if not group._type_string.startswith(  # pylint: disable=protected-access
            'pseudo.family'):
        return []

    if group.pseudo_type != 'pseudo.upf':
        raise ValueError(
            f"Pseudopotential type {group.pseudo_type} is not supported - only UPF can be used."
        )

    return group.get_pseudos(structure=structure)

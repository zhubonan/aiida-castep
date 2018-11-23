"""
Utility functions
"""
import numpy as np
from aiida.parsers.exceptions import OutputParsingError

class CASTEPOutputParsingError(OutputParsingError):
    pass


def structure_from_input(cell, positions, symbols):
    """
    Receives the dictionary cell parsed from CASTEP
    Convert it into an AiiDA structure object
    """

    from aiida.orm import DataFactory
    SructureData = DataFactory("structure")

    out_structure = SructureData(cell=cell)

    for symbol, position in zip(symbols, positions):

        out_structure.append_atom(symbols=symbol, position=position)

    return out_structure


def add_last_if_exists(dict_of_sequence, key, dict_to_be_added):
    """
    Added the last term of a sequence to a dictionary.
    This is used for collecting final values in a dictionary of 'trajectory'
    """

    try:
        last = dict_of_sequence[key][-1]
    except (KeyError, IndexError):
        return
    else:
        # Check if last exist - in case of DefaultDict being passed
        if last:
            dict_to_be_added[key] = last


def desort_structure(structure, original_structure):
    """
    Recover the order of structure. CASTEP will sort the input structure
    according to the atomic numbers
    """
    new_structure = structure.copy()
    isort = np.argsort(original_structure.get_ase().numbers, kind='mergesort')

    sites = structure.sites
    new_sites = [None] * len(sites)

    # Map back to the original order
    for i, s in enumerate(isort):
        new_sites[s] = sites[i]

    new_structure.clear_sites()
    for s in new_sites:
        new_structure.append_site(s)

    # Check for sure
    assert [s.kind_name for s in original_structure.sites] == [s.kind_name for s in new_structure.sites]

    return new_structure

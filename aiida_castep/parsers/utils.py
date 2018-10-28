"""
Utility functions
"""
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

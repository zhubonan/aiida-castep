"""
Utility functions
"""

from aiida.orm.data.structure import StructureData


def get_STO_structure():
    """Return a STO structure"""
    a = 3.905

    cell = ((a, 0., 0.), (0., a, 0.), (0., 0., a))
    s = StructureData(cell=cell)
    s.append_atom(position=(0., 0., 0.), symbols=["Sr"])
    s.append_atom(position=(a/2, a/2, a/2), symbols=["Ti"])
    s.append_atom(position=(a/2, a/2, 0.), symbols=["O"])
    s.append_atom(position=(a/2, 0., a/2), symbols=["O"])
    s.append_atom(position=(0., a/2, a/2), symbols=["O"])
    return s

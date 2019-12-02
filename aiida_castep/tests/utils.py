"""
Utility functions
"""
from __future__ import absolute_import
import os


def get_sto_structure():
    """Return a STO structure"""
    from aiida.plugins import DataFactory
    StructureData = DataFactory('structure')

    a = 3.905

    cell = ((a, 0., 0.), (0., a, 0.), (0., 0., a))
    s = StructureData(cell=cell)
    s.append_atom(position=(0., 0., 0.), symbols=["Sr"])
    s.append_atom(position=(a / 2, a / 2, a / 2), symbols=["Ti"])
    s.append_atom(position=(a / 2, a / 2, 0.), symbols=["O"])
    s.append_atom(position=(a / 2, 0., a / 2), symbols=["O"])
    s.append_atom(position=(0., a / 2, a / 2), symbols=["O"])
    s.label = "STO"
    return s


def get_sto_structure_with_tags():
    """Return a STO structure"""
    from aiida.plugins import DataFactory
    StructureData = DataFactory('structure')

    a = 3.905

    cell = ((a, 0., 0.), (0., a, 0.), (0., 0., a))
    s = StructureData(cell=cell)
    s.append_atom(position=(0., 0., 0.), symbols=["Sr"])
    s.append_atom(position=(a / 2, a / 2, a / 2), symbols=["Ti"])
    s.append_atom(position=(a / 2, a / 2, 0.), symbols=["O"])
    s.append_atom(position=(a / 2, 0., a / 2), symbols=["O"], name='O1')
    s.append_atom(position=(0., a / 2, a / 2), symbols=["O"], name='O2')
    s.label = "STO"
    return s


def get_mixture_cell():
    """Return a STO structure"""
    from aiida.plugins import DataFactory
    StructureData = DataFactory('structure')

    a = 3.905

    cell = ((a, 0., 0.), (0., a, 0.), (0., 0., a))
    s = StructureData(cell=cell)
    s.append_atom(position=(0., 0., 0.),
                  symbols=["Sr", "Ti"],
                  weights=(0.5, 0.5),
                  name='SrTi')
    s.append_atom(position=(a / 2, a / 2, a / 2), symbols=["Ti"])
    s.append_atom(position=(a / 2, a / 2, 0.), symbols=["O"])
    s.append_atom(position=(a / 2, 0., a / 2), symbols=["O"], name='O1')
    s.append_atom(position=(0., a / 2, a / 2), symbols=["O"], name='O2')
    s.label = "STO"
    return s


def get_x2_structure(x):
    """Return a O2 molecule in a box"""
    from aiida.plugins import DataFactory
    StructureData = DataFactory('structure')
    a = 10

    cell = ((a, 0., 0.), (0., a, 0.), (0., 0., a))
    s = StructureData(cell=cell)
    s.append_atom(position=(0., 0., 0.), symbols=[x])
    s.append_atom(position=(1.4, 0., 0.), symbols=[x])
    s.label = "O2"
    return s


def get_data_abs_path():
    """Get the data folder path for the backend module"""
    test_moudule = os.path.split(os.path.abspath(__file__))[0]
    data_folder = os.path.join(test_moudule, "data")
    return data_folder

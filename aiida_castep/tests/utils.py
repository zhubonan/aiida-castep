"""
Utility functions
"""
import os
from aiida.orm import DataFactory

StructureData = DataFactory('structure')


def get_STO_structure():
    """Return a STO structure"""
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


def get_data_abs_path():
    """Get the data folder path for the backend module"""
    test_moudule = os.path.split(os.path.abspath(__file__))[0]
    data_folder = os.path.join(test_moudule, "data")
    return data_folder

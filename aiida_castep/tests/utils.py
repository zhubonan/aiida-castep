"""
Utility functions
"""
import os

def get_STO_structure():
    """Return a STO structure"""
    from aiida.orm import DataFactory
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


def get_x2_structure(x):
    """Return a O2 molecule in a box"""
    from aiida.orm import DataFactory
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

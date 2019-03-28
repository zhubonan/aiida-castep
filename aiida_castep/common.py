"""
Store common stuff
"""

# Mapping of the input names
from __future__ import absolute_import
INPUT_LINKNAMES = {
    'structure': 'structure',  # Input structure
    'parameters':
    'parameters',  # Input parameters e.g defines .cell and .param
    'kpoints': 'kpoints',  # Input kpoints
    'pseudo': 'pseudo',  # Input pseudopotential, namespace
    'settings': 'settings',  # Extra settings for CASTEP
    'parent_calc_folder':
    'parent_calc_folder'  # Remote folder point to the parent calculation
}

OUTPUT_LINKNAMES = {
    'structure': 'output_structure',  # The output structure
    'results': 'output_parameters',  # Basic infomration, energies, units, etc
    'trajectory':
    'output_trajectory',  # Trajectory of md or geometry optimisation
    'bands': 'output_bands',  # Bands of the structure
    'array': 'output_array'  # Array of values, for example SCF energies
}

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

EXIT_CODES_SPEC = {
    'EXITED_AS_NORMAL': (0, 'Calculation terminated gracefully, end found'),
    'ERROR_CASTEP_ERROR':
    (1, 'CASTEP generate error files. Check them for details'),
    'ERROR_NO_RETRIEVE_FOLDER': (100, 'No retrieve folder is found'),
    'ERROR_NO_OUTPUT_FILE': (101, 'No output .castep files i found'),
}

"""
Store common stuff
"""

# Mapping of the input names
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

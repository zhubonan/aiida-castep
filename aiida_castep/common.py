"""
Store common stuff
"""

# Mapping of the input names
from __future__ import absolute_import
from collections import OrderedDict

INPUT_LINKNAMES = {
    'structure': 'structure',  # Input structure
    'parameters':
    'parameters',  # Input parameters e.g defines .cell and .param
    'kpoints': 'kpoints',  # Input kpoints
    'pseudo': 'pseudo',  # Input pseudopotential, namespace
    'settings': 'settings',  # Extra settings for CASTEP
    'parent_calc_folder':
    'parent_calc_folder',  # Remote folder point to the parent calculation
    'prod_structure':
    'product_structure'  # Product structure in transition state search
}

OUTPUT_LINKNAMES = {
    'structure': 'output_structure',  # The output structure
    'results': 'output_parameters',  # Basic infomration, energies, units, etc
    'trajectory':
    'output_trajectory',  # Trajectory of md or geometry optimisation
    'bands': 'output_bands',  # Bands of the structure
    'array': 'output_array'  # Array of values, for example SCF energies
}

# We define an ordered dictionary of the error codes
# The error are in the order of decending priority, the error with
# the highest priority is used as the return code
# The values are used to define the ExitCode which is a namedtuple with field
# status, message, invalidates_cache

EXIT_CODES_SPEC = OrderedDict((
    ('ERROR_SCF_NOT_CONVERGED', (101, 'SCF Cycles failed to reach convergence',
                                 False)),
    ('ERROR_STOP_REQUESTED',
     (103,
      'Stopped execuation due to detection of \'stop \' keyword in param file.',
      True)),
    ('ERROR_TIMELIMIT_REACHED',
     (107, 'Calculation self-terminated due to time limit', False)),
    # Errors with missing files
    ('ERROR_CASTEP_ERROR',
     (104, 'CASTEP generate error files. Check them for details', True)),
    ('ERROR_NO_END_OF_CALCULATION',
     (105, 'Cannot find the end of calculation',
      True)),  # Indicated by the lack of summary line
    ('ERROR_NO_OUTPUT_FILE', (106, 'No output .castep files found', True)),
    ('ERROR_NO_RETRIEVE_FOLDER', (108, 'No retrieve folder is found', True)),
    ('UNKOWN_ERROR', (200, 'UNKOWN ERROR', True)),
    ('CALC_FINISHED', (0, 'Calculation terminated gracefully, end found',
                       False)),
))

# exit code dictionary with the numerical code as the keys
EXIT_CODE_NUMS = OrderedDict(
    (v[0], (k, v[1], v[2])) for k, v in EXIT_CODES_SPEC.items())

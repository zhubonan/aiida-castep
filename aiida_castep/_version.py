"""
This module stores a single version for calculation-parser.

A single version number is ued here so whenever any change i
assed to pasers or calculation modules, the version number should
be increased.This avoids falsely matching nodes via hashes.

CHNAGELOG
0.2.3 -> FIX a typo psedu_pots -> pseudo_pots
0.2.4 -> Sort the bands and parsed kpoints from .bands file using the index given

1.0.0 -> initial version for plugin version 1.0.
Changed the warning messages to EXIT_CODE style
"""

CALC_PARSER_VERSION = "1.0.0"

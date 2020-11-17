"""
This module stores a single version for calculation-parser.

A single version number is used here so whenever any change to parser
 or calculation modules, the version number should
be increased.This avoids falsely matching nodes via hashes.

CHANGELOG
0.2.3 -> FIX a typo psedu_pots -> pseudo_pots
0.2.4 -> Sort the bands and parsed kpoints from .bands file using the index given

1.0.0 -> initial version for plugin version 1.0.
Changed the warning messages to EXIT_CODE style

1.0.1 -> Revision to include error messages
Added parsing of the *.err file and put the content in the field 'error_messages'
of the returned Dict.
The order of error is also adjusted. Fixed a bug where if the *.err files are
present the returned code would be same as when end of the calculation is not
found. This fix allows the internal crash of CASTEP (usually with the *.err files)
to be differentiated with the calculation being killed (by scheduler).

1.0.2 -> Fix a bug of parsing cons'd forces

1.0.3 -> Fix a bug where the forces are not reorderred as for the case of StructureData
"""

CALC_PARSER_VERSION = "1.0.3"
PLUGIN_VERSION = "1.2.0a3"

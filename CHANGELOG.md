1.2.0
=====


## Changes

* Adapted the new `Group` system implemented in `aiida_core >=1.2.0` for pseudopotential families, the change is backward incompatible.
* Unified families for `UspData` and `OTFGData` to a single `OTFGGroup`. Two types of pseudopotentials can be mixed up in a single group. Mixing `UpfData` is not supported through this API yet, but can be added manually.
* Added commandline `verdi data castep-otfg migrate` to migrate the old families. This command **MUST BE RUN ONCE** after the upgrade, otherwise pseudopotential family matching will **NOT WORK**. NOTE:  old groups will not be deleted using this command for now.

## Bugfix

* No longer using `Node` instant as default for workchains.

1.1.0
=====

* added supports for AiiDA >= 1.2

1.0.0
=====
* Plugin migrated to work with `aiida-core==1.0.0`.
* Bug fix for helper functions
* Updated the Jupyter notebook examples
* Updated the documentation
* Workflows `BaseCastepWorkChain` and `CastepRelaxWorkChain` added to the plugin
* Dependencies updated to comply with `aiida-core==1.0.0`
* Use AiiDA's dryrun ability for submit test and dry castep runs

1.0.0b1
=========
* Compatible with AiiDA 1.0.0b3, support for AiiDA 0.x is dropped
* Added `CastepBaseWorkChain` as the starting point for more complex workflows
* Compatible with python3, python2 support continue but the use is not encouraged.
* Changes in the support method/function such as `get_castep_input_summary` and `create_restart` required in the design change in aiida 1.0. These functions can be access at `CalcJobNode.tools`, `CastepCalculation`, or imported into the scope directly.
* Changes in the way errors are handled. Exits codes will be set for `CastepCalculation` to inform calculation failure.


0.3.2
=====
* Added code to mock CASTEP executable for testing
* Added the AiiDA classifier for the package
* Fixed a bug when generating help information
* Fixed listfile command for the helper 
* Enhanced the uspdata module to allow manualy set the element of the potential
* Added the ELF and formatted ELF files to the default retrieve list


0.3.1
=====
* Fixed a bug where offset of kpoints grid is ignored
* Fixed a bug where OTFG family upload is not handled correctly.
* Added routine to check the existence of remote check file in `submit_test` 
* Updated the default file retrieve list and task specific retrieve list.
* Documentation improvements
* rename `get_castep_inputs` to `get_castep_input_summary`. This method returns a dictionary of a summary of the run.
* added method `update_parameters` to `CastepCalculation` for easy manipulation of the input parameters.
* Fixed a inconsistency due to kpoint index being ignored when parsing `.bands` file. (parser version 0.2.4)
* Various documentation improvements

0.3.0
=====
* Added `Pot1dCalculation`.
* Added `CastepTSCalculation`
* Added ability to do a local dryrun test in `submit_test`.
* Fixed a problem when generating help info in CASTEP 18.1 where only a partial list is printed by CASTEP using the `-all` flag.
* Various bug fixes.
* Released to PyPI.

0.2.1
======
* Added `__version__` to `calculations.castep` and `parsers.castep`.
* Version numbers should be consistent across parsers and calculations for caching to work.
* Fixed the package `aiida_castep.__version__` to 0.2.1.
* Changes in handling the output structure. Now assigning label of the input structure to the output structure.

0.2.0
=====

Policy of setting calculation state has now changed.
A `FINISHED` state will be set given the excution was terminated safetly and without error,
even if the underlying *task* is not finished.
For example, a geometry optimisation will be set to `FINISHED` even if it did not reached
convergence, given that it was exited cleanly by reaching `geom_max_iter` or time limit (but not the `stop` key in param file).  
The primiary drive of this is to allow unconverged but cleanly finished calculations to be used as cached calculation.

0.2.0
=====

Policy of setting calculation state has now changed.
A `FINISHED` state will be set given the excution was terminated safetly and without error,
even if the underlying *task* is not finished.
For example, a geometry optimisation will be set to `FINISHED` even if it did not reached
convergence, given that it was exited cleanly by reaching `geom_max_iter` or time limit (but not the `stop` key in param file).  
The primiary drive of this is to allow unconverged but cleanly finished calculations to be used as cached calculation.

0.2.1
======
* Added `__version__` to `calculations.castep` and `parsers.castep`.
* Version numbers should be consistent across parsers and calculations for caching to work.
* Fixed the package `aiida_castep.__version__` to 0.2.1.
* Changes in handling the output structure. Now assigning label of the input structure to the output structure.

0.3.0
=====
* Added `Pot1dCalculation`.
* Added `CastepTSCalculation`
* Added ability to do a local dryrun test in `submit_test`.
* Fixed a problem when generating help info in CASTEP 18.1 where only a partial list is printed by CASTEP using the `-all` flag.
* Various bug fixes.
* Released to PyPI.

0.3.1
=====
* Fixed a bug where offset of kpoints grid is ignored
* Fixed a bug where OTFG family upload is not handled correctly.
* Added routine to check the existence of remote check file in `submit_test` 
* Updated the default file retrieve list and task specific retrieve list.
* Documentation improvements
* rename `get_castep_inputs` to `get_castep_input_summary`. This method returns a dictionary of a summary of the run.
* added method `update_parameters` to `CastepCalculation` for easy manipulation of the input parameters.

0.4.0
======
* (WIP) Compatible with AiiDA 1.0a4

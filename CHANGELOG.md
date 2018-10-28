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
* Tixed the package `aiida_castep.__version__` to 0.2.1.
* Changes in handling the output structure. Now assigning label of the input structure to the output structure.

0.3.0
=====
* Added `Pot1dCalculation`.  
* Added `CastepTSCalculation`
* Added ability to do a local dryrun test in `submit_test`.  
* Fixed a problem when generating help info in CASTEP 18.1 where only a partial list is printed by CASTEP using the `-all` flag.  
* Various bug fixes.  
* Released to PyPI.  

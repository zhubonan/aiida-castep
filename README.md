AiiDA plugin for working with CASTEP
====================================
[![Docs status](https://readthedocs.org/projects/aiida-castep/badge)](http://aiida-castep.readthedocs.io/)

[![pipeline status](https://github.com/zhubonan/aiida-castep/workflows/aiida-castep/badge.svg)](https://github.com/zhubonan/aiida-castep/actions)

A plugin for [AiiDA](www.aiida.net) to work with plane-wave pseudopotential DFT code [CASTEP](www.castep.org).
CASTEP has a single binary executable and calculation is primarily controlled by the *task* keyword.
The generic `CastepCalculation` should work with all tasks, at least in terms of generating input files.
Likewise a generic `CastepParser` class is implemented and can handle parsing most information we are interested in *singlepoint*, *geometryoptimisation*, *bandstructure/spectral* tasks.
Most output files are retrieved if present, and it is possible to explicitly request retrieval from the remote computer.
The goal of this plugin is not to provide a comprehensive parser of the CASTEP results, but to build a graph of calculations performed for provenance preservation and workflow automation.
Input and output of a simple calculation:

![Asingle calculation](https://github.com/zhubonan/aiida-castep/raw/dev/docs/source/images/Si_bs_example.png)

or a series of operations and automated calculations:

![A series of calculations](https://github.com/zhubonan/aiida-castep/raw/dev/docs/source/images/calc_series_example.png)

The raw files can always be extracted from the database and analysed by the post-processing tools of choice.
Even better, such tools may be integrated with the AiiDA framework and have the analysis appended to the provenance graph.

Highlights of available features:
* Storing usp/recpot as `UspData` (sub-class of `SingleFileData`) in AiiDA database and create/use of pseudo family groups.
* Store OTFG generating strings as `OTFGData` in AiiDA. Create of family/group are also supported. OTFG library (such as "C19") are represented as a OTFG string works for all elements.
* Preparation of CASTEP input files. Writing cell and parameters files are both supported. Tags in *positions_abs* block file should also work, e.g *LABEL*, *SPIN*, *MIXTURE*.
* Parsing energy, force, stress from output .castep file and .geom file
* Parsing trajectory from .geom, .ts, .md files.
* Checking errors in .param and .cell files before submitting, using dictionaries shipped from built from CASTEP executable.
* Extra KpointData input node for BS, SEPCTRAL and PHONON tasks.
* Preparing transition state search calculations
* A `create_restart` function for easy creation of continuation/restart calculations. Input can be altered using `param_update` and `param_delete` keyword arguments. Automatic copying/linking of remote check files by AiiDA.
* A `get_castep_inputs_summary` function to print a summary of inputs of a calculations.
* A `compare_with` method to compare the inputs of two calculations.

Documentation
-------------

Quick glimpse into how to use the plugin for running calculations:

- [Running CastepCalculation](https://nbviewer.org/github/zhubonan/aiida-castep/blob/dev/examples/aiida-castep-quick-start.ipynb)
- [Running CastepBaseWorkChain](https://nbviewer.org/github/zhubonan/aiida-castep/blob/dev/examples/aiida-castep-quick-workchain.ipynb)

Documentation is hosted at Read the Docs:  
[dev version](https://aiida-castep.readthedocs.io/en/dev/)  
[master version](https://aiida-castep.readthedocs.io/en/master/)


Dependencies
------------

The primary dependency is the `aiida_core` package. The dependencies are:

* The plugin version 2.0 and above support only `aiida_core>=2.0`.
* The plugin version 1.0 and above support only `aiida_core>=1.0.0b6, <2`.
* The plugin version 0.3 support only `aiida_core` 0.12.x versions.

There is only minor API changes in the `aiida_core` between v1 and v2, scripts written should be compatible between the two.

Todos and nice-to-haves
-----------------------

* Methods for importing existing calculations
* Support for submitting file based CASTEP calculations.
* At the moment there is no enforcement on the type in `Dict` input node. For example, setting *smearing_width* to 0.1 and "0.1" is equivalent, but they will store differently in the database.

How to test
-----------

The tests uses the `pytest` framework. First, install with the dependencies
```
pip install aiida_core[testing]
pip install aiida-castep[testing]
```

Then you can run the command `pytest` from the project directory.

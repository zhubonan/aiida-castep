AiiDA plugin for working with CASTEP
====================================
[![Documentation Status](https://readthedocs.org/projects/aiida-castep/badge/?version=master)](https://aiida-castep.readthedocs.io/en/master/?badge=master)
[![pipeline status](https://gitlab.com/bz1/aiida-castep/badges/master/pipeline.svg)](https://gitlab.com/bz1/aiida-castep/commits/master)

This is a  plugin for using CASTEP in AiiDA.
The plugin is OK for production but still under active development.
A lot of the initial implementation was based on `aiida_quantumespresso`.
CASTEP has a single binary executable and calculation is primarily controlled by the *task* keyword.
The generic `CastepCalculation` should work with most tasks, at least in terms of generating input files.
Likewise a generic `CastepParser` class is implemented and can handle parsing most information we are interested in *singlepoint*, *geometryoptimisation*, *bandstructure/spectral* tasks.
Things such as parsing output from *phonon* calculation has not been implemented so far - I have very little experience with phonon calculations.

Highlights of available features:
* Storing usp/recpot as `UspData` (sub-class of `SingleFileData`) in AiiDA database and create/use of pseudo family groups.
* Store OTFG generating strings as `OTFGData` in AiiDA. Create of family/group are also supported. OTFG library (such as "C19") are represented as a OTFG string works for all elements.
* Preparation of CASTEP input files. Writing cell and parameters files are both supported. Tags in *positions_abs* block file should also work, e.g *LABEL*, *SPIN*, *MIXTURE*.
* Parsing energy, force, stress from output .castep file and .geom file
* Checking errors in .param and .cell files before submitting
* Extra KpointData input node for BS, SEPCTRAL and PHONON task
* Preparing/parsing transition state search calculations
* `create_restart` method for easy creation of continuation/restart calculations. Input can be altered using `param_update` and `param_delete` keyword arguments. Automatic copying/linking of remote check files by AiiDA.
* `get_castep_inputs` method to get a summary of inputs of a calculations.
* `compare_with` method to compare two calculations, based on outputs from `get_castep_inputs`

Documentation
-------------

Documentation is hosted at Read the Docs:  
[dev version](https://aiida-castep.readthedocs.io/en/dev/)  
[master version](https://aiida-castep.readthedocs.io/en/master/)

TODOS
-----

* Methods for importing existing calculations 
* Support for submitting file based CASTEP calculations.
* At the moment there is no enforcement on the type in `ParameterData` input node. For example, setting *smearing_width* to 0.1 and "0.1" is equivalent, but they will store differently in the database.
* WorkChain development for automated restart of calculations. (Waiting for AiiDA 1.0.0)

How to test
-----------

Use `verdi -p <test_profile> devel tests db.castep` to do tests.
Make sure the plugin is installed and AiiDA is configured before this.

AiiDA plugin for interface with CASTEP
======================================

This repository is for a plugin to allow CASTEP to work with AiiDA.

Currently implemented functionalities:

* Storing usp/recopt as `UspData` (sub-class of `SingleFileData`) in aiida database and create/use of pseudo family group
* Store OTFG generating strings are `OTFGData` in aiida database. Create of family/group are also supoorted
* Generating CASTEP input files. Writing cell and parameters files are both supported. In theory all tags in cell file should work, e.g *LABEL*, *SPIN*, *MIXTURE*. (Only *SPIN* has been tested)
* Automatically parsing of output .castep file and .geom file
* Checking errors of keywords for PARAM and CELL

TODOS
-----

* Make (a better) `helper` to be used without CASTEP binary
* Write docs
* Readers for cell and param files.
* Methods to importing existing calculations.
* Document what goes into settings ParameterData input node
* At the moment there is no enforcement on the tpye of the input e.g 0.1 and "0.1" is equivalent for generating input, but store differently in the database.

How to test
-----------

Use `verdi -p <test_profile> devel tests db.castep` to do tests.

========
Tutorial
========

This page contains a simple tutorial for setting up a CASTEP calculation with AiiDA using ``aidia_castep`` plugin.

Step-by-step example - Oxygen in a box
======================================

Here we setup a simple calculations of oxgen moleculer in a box as a example.
Before we start AiiDA should be setup properly already - you should have a working *profile* with a CASTEP `Code` ndoe and
a `Computer` node.

Construcing a Calculation
--------------------------

To construct a calculations, one can call ``CastepCalculation()`` but it is often more convenient to do this from a
``Code`` node that represents the CASTEP excutable will be used:: 

 code = Code.get_from_string("castep-xx.xx@your_computer")
 calc = code.new_calc()

In this way the ``Computer`` and ``Code`` are set automatically, otherwise ``use_code`` and ``set_computer`` methods need
to be called manually.

Defining the `ParameterData` node
---------------------------------

For most CASTEP calculations we need a ``<seed>.param`` file and a ``<seed>.cell`` file.
Likewise in ``aiida_castep`` we need a ``ParameterData`` node that defines the keyword-value pairs in these two files.
The node is constructed based on a dictionary::

 param_in = {"PARAM": {
                       "task" : "geometryoptimisation",
                       "cut_off_energy": 500,
                       "opt_strategy": "speed",
                       "xc_functional: "lda",
                       "spin_polarized: True,
             ,
             "CELL":  {
                       "fix_all_cell": True,
             }}

To construct the node, call::

 param_data = ParameterData(dict=param_in)

Note that not everything you otherwise have to write in the ``<seed>.cell`` goes into the dictionary .
For example, there is no need to supply **lattice_cart** and **positions_abs** as they will be defined by the ``StructureData`` input node.
Finally, we link the ``ParameterData`` to the calculation node using::

 calc.use_parameters(param_data)

Setup k-oints and structure
---------------------------
We first need to define the structure to be calculated::

 o2_in_a_box = StructureData()
 o2_in_a_box.set_cell([10, 0, 0], [0, 10, 0], [0, 0, 10])
 o2_in_a_box.append_atom(position=[0, 0, 0], symbols="O")
 o2_in_a_box.append_atom(position=[1.4, 0, 0], symbols="O")

Alternatively, one can pass a ``ase.Atoms`` object to the constructure as keyword arugment.
This is often more convenient.
To define the k points mesh, run::

 kpoints = KpointsData()
 kpoints.set_kpoint_mesh((1,1,1))

Here we use the gamma point, alternatively kpoints may be passed explicitly.
See AiiDA's `documentaion <https://aiida-core.readthedocs.io/en/v0.12.0/datatypes/index.html>`_ for details.
Finally, link them up with the calcualtion::

 calc.use_kpoints(kpoints)
 calc.use_structure(structure)

Setup pseudo potentials
-----------------------

Unlike most other DFT codes, CASTEP has the ability to generate pseudopotentials on-the-fly.
Of course, using a pre-generated pseudo potential set is also supported and you can even make such set reusing
the on-the-fly generated (OTFG)) potential files.
There are several libraries built-in in CASTEP and new, revised versions come out with different releases.
Internally, OTFG potentials are generated based on a 1 line specification string which can be user defined as well.
A OTFG library is merely a archive of such string for a range of elements.
On the other hand, files based native pseudopotentials has the suffix ``usp`` or ``recpot``.
In newer version of CASTEP, ``upf`` files are also supported.
This plugin introduces ``UspData`` and ``OtfgData`` classes.
To get a ``OtfgData`` call::

 otfg, create = OtfgData.get_or_create(otfg_string)

Creation of duplicated nodes can be avoided using this interface as the database is queried to check if
the same otfg_string exists.
If a new node is created, the ``create`` will be set to ``True``.
The element is automatically parsed from the ``otfg_string`` supplied.
If no element is found, it will be assumed that the string refers to bulit-in libaray in CASTEP, for example ``"C9"``.

Similary interface is also used for ``UspData`` node::

 create, usp = UspData.get_or_create(path_to_file)

The md5 of Usp files will be compared to see if the same ``UspData`` already exists.
A more convenient way of uploading a set of usp files is to use ``upload_usp_family`` function in ``aiida_castep.data.usp``.

.. note: For ``OtfgData``, a similar "upload_otfg_family" function also exists.

The following code defines a ``OtfgData`` to represent the bulit-in libarary **C9** and tell let the calculation use it for oxygen::

 c9, create = OtfgData.get_or_create("C9")
 calc.use_pseudos(c9, kind="O")

Alternatively, we can do::

 upload_otfg_family(["C9"], "C9")
 calc.use_pseudo_from_family("C9")

The first line create a otfg family ``"C9"`` containing a sinle ``OtfgData`` node. The second line invoke the
method to set pseudos.

Setup additional settings
-------------------------

An additional ``ParameterData`` node can be used by the calculation. The following fields can be used:

* ``SPINS``: A list of initial spins for each atom.

* ``PARENT_FOLDER_SYMLINK``: Wether we use symbolic link to the parent folder that contains ``<seed>.check``.

* ``LABELS``: A list of labels for each atom.

* ``CMDLINE``: Additional parameters to be passed. By default we call ``<castep_excutable> <seed>`` but some times additonal parameters may be useful, e.g when we use wrapping script.

* ``ADDITIONAL_RETRIEVE_LIST``: A list for additional files to be retrieved from remove work directory. See also description in AiiDA's `tutorial <https://aiida-core.readthedocs.io/en/latest/developer_guide/devel_tutorial/code_plugin_int_sum.html>`_.

For this example, we want to oxygen molecules should be spin polarized.
To break the symmetry, intial spins need to be set::

 settings_dict = {"SPINS" : [1, 1]}
 calc.use_settings(ParameterData(dict=settings_dict))

A veteran CASTEP user will already spot a rookie mistake here - we did not set the *spin* keyword in the ``<seed>.param``.
This will in fact be taken care of by the plugin, although setting it manually is recommended.
The plugin will also check if the sum of spins are the same as that set in ``ParameterData`` before writting actual input files.

Setup the resources
-------------------

To run on remote cluster, we need request some resources.
Please refer to AiiDA's `documentation <https://aiida-core.readthedocs.io/en/v0.12.0/scheduler/index.html#job-resourcesl>`_ for details as the settings are scheduler dependent.
As an example for now::

 calc.set_max_wallclock_seconds(3600)
 calc.set_resources({"num_machines": 2})

This tells AiiDA that we request to run on a single node for 3600 seconds.
You may want to call ``set_custom_schduler_commands`` for inserting additional lines in to the submission script,
for example, to define the project account to be charged.

Submiting the calculations
--------------------------

Now we are ready to submit the calculation. As standard in AiiDA we need to store the node first, but before that
we really should check if there is any mistake::

 calc.get_castep_inputs()

Returns a list as a brief summary of the inputs of the calculation. 
To generate the input files, call::

 calc.submit_test()

This will cause the inputs to written to date coded sub folders inside ``submit_test`` folder at current working directory.
Typos in ``ParameterData``'s dictionary will be check and if there is any mistake an exception will be raised.
Finally, we are ready to submit::

 calc.store_all()
 calc.submit()

Will store the calculation and mark our calculation as for submission.


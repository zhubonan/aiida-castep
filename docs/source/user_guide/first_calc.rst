======================
Your first calculation
======================

This page contains a simple tutorial for setting up a CASTEP calculation with AiiDA using ``aidia_castep`` plugin.

.. note::
  A notebook example can be found `here <https://nbviewer.org/github/zhubonan/aiida-castep/blob/dev/examples/aiida-castep-quick-start.ipynb>`_.

Step-by-step example - Silicon
==============================

Here we setup a simple calculations of silicon that is identical to the ones in the
CASTEP's `on-line tutorial <http://www.castep.org/Tutorials/BasicsAndBonding>`_.
Before we start, AiiDA should be setup properly already.
You should have a working *profile* with a CASTEP ``Code`` node and
a ``Computer`` node.
Both of them can be added using ``verdi`` command-line interface.

Loading classes
---------------

The plugin system allows plugin classes to be loaded using *factory* functions::

  from aiida.plugins import DataFactory, CalculationFactory
  # Classes defined in this plugin
  CastepCalculation = CalculationFactory("castep.castep")
  OtfgData = DataFactory("castep.otfgdata")
  UspData = DataFactory("castep.uspdata")
  # Native aiida classes
  KpointsData = DataFactory("array.kpoints")
  Dict = DataFactory("dict")
  StructureData = DataFactory("structure")

.. note:: It is best to work through the example interactively using ``verdi shell``.

The first step
--------------

.. highlight:: python

The inputs of the calculation needs to be stored in a nested dictionary.
It is often more convenient to work with a ``ProcessBuilder`` which enables tab completions
for link names and can also display doc strings::

 builder = CastepCalculation.get_builder()

First, we need to define the *code* of the calculation which represents the actual executable
to be used to do the work::

  code = Code.get_from_string("castep-xx.xx@your_computer")
  builder.code = code

.. note::
  While defining calculations may seem to be complicated here, in practice most calculations will be performed by ``CastepBaseWorkChain`` which supports more concise and flexible inputs.


Setup CASTEP parameters
-----------------------

For most CASTEP calculations we need a ``<seed>.param`` file and a ``<seed>.cell`` file.

.. highlight:: none

The the ``<seed>.cell`` file contains the input geometry related parameters and should look like this::

  %BLOCK LATTICE_CART
        2.6954645000       2.6954645000       0.0000000000
        2.6954645000       0.0000000000       2.6954645000
        0.0000000000       2.6954645000       2.6954645000
  %ENDBLOCK LATTICE_CART
  %BLOCK POSITIONS_ABS
  Si                       0.0000000000       0.0000000000       0.0000000000
  Si                       1.3477325500       1.3477325500       1.3477325500
  %ENDBLOCK POSITIONS_ABS
  kpoints_mp_grid     : 4 4 4
  symmetry_generate   : True
  %BLOCK SPECIES_POT
  Si    C19
  %ENDBLOCK SPECIES_POT

The ``<seed>.param`` file contains the other controlling parameters::

  task                : singlepoint
  basis_precision     : medium
  fix_occupancy       : True
  opt_strategy        : speed
  num_dump_cycles     : 0
  xc_functional       : lda
  write_formatted_density: True

.. highlight:: python

With ``aiida_castep`` we need a single ``Dict`` node that includes the keyword-value pairs that should have been put into the two files.
The node is constructed based on a dictionary::

 param_in = {"PARAM": {
                       "task" : "singlepoint",
                       "basis_precision": "medium",
                       "fix_occupancy": True,
                       "opt_strategy": "speed",
                       "num_dump_cycles": 0,
                       "xc_functional": "lda",
                       "write_formatted_density": True,
             },
             "CELL":  {
                       "symmetry_generate": True,
             }}

To construct the node, call::

 param_data = Dict(dict=param_in)

Not everything you otherwise have to write in the ``<seed>.cell`` goes into the dictionary.
For example, there is no need to supply **lattice_cart** and **positions_abs** as they will be defined by the ``StructureData`` input node.
Finally, we store the ``Dict`` in the builder::

 builder.parameters = param_data

A plain dictionary can also be used as the input as a ``Dict`` node can be automatically generated from it.
This would also work::

 builder.parameters = param_in

The downside is that a new ``Dict`` node is always created even the contents are identical.

.. note::
   It is recommended to use python types instead of strings to make it easy for querying.
   No internal type check or enforcement is implemented.
   The bottom line is that the text files generated needs to be understood by CASTEP.

.. note::
  Block type keywords can be set using a list of strings each for a single line.

Setup structure and k-points
----------------------------

The input structure has to be stored as a ``StructureData`` node.
Details about ``StructureData`` can be found in AiiDA's documentation.
For now, we can write::

 StructureData = DataFactory("structure")
 silicon = StructureData()
 cell = [[2.6954645, 2.6954645, 0],
         [2.6954645, 0, 2.6954645],
         [0, 2.6954645, 2.6954645]]
 silicon.set_cell(cell)
 silicon.append_atom(position=[0, 0, 0], symbols="Si")
 silicon.append_atom(position=[1.34773255, 1.34773255, 1.34773255], symbols="Si")

Alternatively, one can pass a ``ase.Atoms`` object to the constructive as keyword argument::

 from ase import Atoms
 a_si = Atoms("Si2", cell=cell, scaled_positions=[[0, 0, 0], [0.25, 0.25, 0.25]])
 silicon = StructureData(ase=a_si)

To define the k points mesh, run::

 KpointsData = DataFactory("array.kpoints")
 kpoints = KpointsData()
 kpoints.set_kpoints_mesh((4, 4, 4))

Here we are using a MP grid, alternatively k-points may be passed explicitly as in
``KpointsData``.
See AiiDA's `documentation <https://aiida-core.readthedocs.io/en/v0.12.0/datatypes/index.html>`__ for more information.
Finally, we save them in the builder as inputs::

 builder.kpoints = kpoints
 builder.structure = silicon

.. note::
   There are several useful routines in :py:mod:`aiida_castep.utils` to work with ``ase``,
   such as generating constraints or converting trajectory to a list of ``Atoms`` for visualisation.
   The output structure of a ``CastepCalculation`` is automatically sorted to have a index consistent with the input structure.


Setup pseudo potentials
-----------------------

CASTEP has the ability to generate pseudopotentials on-the-fly.
Of course, using a pre-generated pseudo potential set is also supported and you
can reuse the on-the-fly generated (OTFG)) potential files.
There are several libraries built-in in CASTEP and new, revised versions comes out at new releases.
Internally, OTFG potentials are generated based on a 1 line specification string which can be defined manually.
A OTFG library is in fact a hard-coded collection of such string for a range of elements.

Files based native pseudopotentials has the suffix ``usp`` or ``recpot``.
In newer version of CASTEP, ``upf`` files are also supported.
This plugin introduces ``UspData`` and ``OtfgData`` classes.
Their usage is similar to the ``UpfData`` defined in ``aiida_core``.
To get a ``OtfgData``::

 otfg, create = OtfgData.get_or_create(otfg_string)

This avoids creation of duplicated nodes.
If a new node is created, the variable ``create`` will be ``True``.
The element is automatically inferred from the ``otfg_string`` supplied.
If no element is found, we assume that the string refers to built-in library in CASTEP, for example ``"C9"``.

A similar interface also exists for ``UspData`` node::

 si00, create = UspData.get_or_create(path_to_workdir + "/Si_00.usp")

The md5 of usp files will be compared to see if the same ``UspData`` already exists.
If that is the case the existing ``UspData`` node will be returned.
A more convenient way of uploading a set of usp files is to use ``upload_usp_family`` function in ``aiida_castep.data.usp``.

.. note::
   The element is inferred from the file name which should be in the format *<element>_<foo>.usp*.
   Norm-conserving *recpot* files are treated as if they are *usp* files.

To let the builder use the pseudo potential::

 builder.pseudos.Si = si00

Alternatively, and in fact used more commonly, is to create a family of the potentials::

  from aiida_castep.data.usp import upload_usp_family
  upload_usp_family("./", "LDA_test", "A family of LDA potentials for testing")

This will upload all valid pseudopotentials inside the current working directory into a family named "LDA_test".
More commonly, CASTEP calculations are done with on-the-fly generated pseudopotentials (OTFG), for which built-in libraries are available to use.
However, these built-in libraries still have to be registered with AiiDA. To do so, one can upload a single family with the library string::

  from aiida_castep.data.otfg import upload_otfg_family
  upload_otfg_family(["C19"], "C19", "The C19 library shipped with CASTEP")

This family contains a single OTFG string that is the library named "C19".
The library name is treated specially in a way such that it will match to any elements, unless an explicity entry exists within the same family.
For example, the following ::

  upload_otfg_family(["C19", "O 2|1.5|12|13|15|20:21(qc=5)"], "MyFamily", "The family that uses a specific OTFG for oxygen and C19 for everything else.")

uploads a family "MyFamily", which uses "C19" for any elements except for "O", for which generation setting "2|1.5|12|13|15|20:21(qc=5)" will be used instead.

A family is just a collection of pseudopotentials and/or a library name.
To apply it to a calculation, one can use an utility function::

  CastepCalculation.use_pseudos_from_family(builder, "C19")

This sets the `pseudos` port of the builder to::

  {'Si': <OTFGData: uuid: ca9d4083-e96e-4b12-a02a-81a6a4c34929 (pk: 32)>}

For this shortcut to work, the ``structure`` file of the builder must be define beforehand.
Otherwise, one can also pass a dictionary manually to the `pseudos` port with keys and values being the specie names and the pseudopotential node to be used for each.

.. note::
   Families of norm-conserving potentials from `PseudoDojo <http://www.pseudo-dojo.org/>`__ can be installed with the `aiida-pseudos <https://github.com/aiidateam/aiida-pseudo>`__ package.

Setting the resources
---------------------

To run our calculations on remote clusters, we need request some resources.
Please refer to AiiDA's `documentation <https://aiida-core.readthedocs.io/en/v0.12.0/scheduler/index.html#job-resourcesl>`__ for details as the settings are scheduler dependent.
Options of running calculations are set under the ``metadata.options`` namespace.
These properties are eventually stored as the attributes of the created ``CalcJobNode``.
As an example for now::

 builder.metadata.options.max_wallclock_seconds = 3600
 builder.metadata.options.resources = {"num_machines": 1}

This lets AiiDA know that we want to run on a single node for a maximum of 3600 seconds.
You may want to set the ``custom_scheduler_commands`` for inserting additional lines in to the submission script,
for example, to define the account to be charged.

Submission
----------

Now we are ready to submit the calculation.
But before actual submission we can have a glance of the inputs to see if there is any mistake by using::

 CastepCalculation.get_castep_input_summary(builder)

A dictionary is returned as a summary of the inputs of the calculation::

  {'CELL': {'symmetry_generate': True},
   'PARAM': {'basis_precision': 'medium',
    'fix_occupancy': True,
    'num_dump_cycles': 0,
    'opt_strategy': 'speed',
    'task': 'singlepoint',
    'write_formatted_density': True,
    'xc_functional': 'lda'},
   'kpoints': 'Kpoints mesh: 4x4x4 (+0.0,0.0,0.0)',
   'label': None,
   'pseudos': {'Si': <OTFGData: uuid: ca9d4083-e96e-4b12-a02a-81a6a4c34929 (pk: 32)>},
   'structure': {'cell': [[2.6954645, 2.6954645, 0.0],
     [2.6954645, 0.0, 2.6954645],
     [0.0, 2.6954645, 2.6954645]],
    'formula': 'Si2',
    'label': None}}

To test generating the input files, call::

 CastepCalculation.submit_test(builder)

This write inputs to written to date coded sub folders inside ``submit_test`` folder at current working directory.
The input keywords for cell and param file will be check, and if there is any mistake an exception will be raised.

.. note::
   The content of the folder should be identical to what will be uploaded to remote computer.
   Hence we can also check if the job script is correctly generated.
   The dryrun test can be performed locally with::

     CastepCalculation.dryrun_test(builder)


Finally, we are ready to submit the calculation::

 from aiida.engine import submit
 calcjob = submit(builder)

The first line stores the calculation and all of its inputs. The seconds line mark our calculation for submission.
The actual submission is handled by one of AiiDA's daemon process, so you need to have it running in the background.

.. note::
   Don't forget to launch the daemon with ``verdi daemon start`` if you have not done so.
   When the ``submit`` function is called, the workchain and its inputs are serialized to the AiiDA database.
   Then task is sent to the RabbitMQ server to indicate that this workflow is ready to launch.
   It is then up to the daemon process to check-in the job and deserialize the inputs from the database to
   actually run the job.

Monitoring
==========

Monitoring the state of calculations can be done using ``verdi process list``.
Inside a interactive shell, the state of a calculation may be checked with
``calcjob.get_process_state()``.

Once the calculation is finished, the state can be access with ``calcjob.exit_status`` and ``calcjob.exit_message``.
If the calculation has finished without error then the ``exit_status`` should be 0.

Another way to monitor the jobs is to use ``verdi process list`` command, which lists all running calculations/workflows
by default. It is also possible to filter the jobs by state/age using various optional arguments.

You will see that the just submitted job to be in ``Waiting`` state, and the *process status* going through several stages,
such as *upload*, *submit*, *update*, *retrieve*.

Once the job is finished, it will be in the ``Finished`` state and no longer show up with ``verdi process list``.
Use ``verdi process list -p1 -a`` to list all jobs created within the past 24 hours.

Shell alias can be set to make interacting with ``verdi`` command easier. As an example, the following lines can be included
in the ``.bashrc``:

.. code-block:: console

   alias vplp="verdi process list -P pk process_label label state scheduler_state"
   alias vpl="verdi process list"
   alias vco="verdi calcjob outputcat"
   alias vcg="verdi calcjob gotocomputer"
   alias vci="verdi calcjob inputcat"


Accessing Results
=================

A series of node will be created when the calculation is finished and parsed.
Use ``calc.get_outgoing().all()`` to access the output nodes.
Alternatively, the main ``Dict`` node's content can be return using ``calc.res.<tab completion>``.
Other nodes can be access using ``calc.outputs.<tab completion>``.
The calculation's state is set to "FINISHED" after it is completed without error.
This does not mean that the underlying task has succeeded.
For example, an unconverged geometry optimization due to the maximum iteration being reached is still a successful  calculation,
as CASTEP has done  what the user requested.
On the other hand, if the calculation is terminated due to the time limit (cleanly exited or not), it will have an none-zero exit_status.


Further Reading
===============

As mentioned above, most calculation will be done using ``CastepBaseWorkChain`` which make it easier for defining the inputs and also adds the ability to correct some common
problems, such as SCF convergence problems and running out of walltimes.

.. seealso::
  Example notebook can be found `here <https://nbviewer.org/github/zhubonan/aiida-castep/blob/dev/examples/aiida-castep-quick-workchain.ipynb>`__,
  or run interactively with `Binder <https://mybinder.org/v2/gh/zhubonan/aiida-castep/dev>`__.
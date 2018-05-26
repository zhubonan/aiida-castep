Getting started
+++++++++++++++

AiiDA is a sophisticated framework with great ability to prepare, submit, manage calculations and preserve their
provenance. The workflow of running lengthy, complex density functional theory calculations on clusters can be grealty simplified.
I would strongly encourage any user to families themselves with AiiDA before using this pulgin, otherwise a lot of things would not make sense.
The ``aiida_core`` package has excelling documentation located at `readthedocs <https://aiida-core.readthedocs.io>`_.

Installation
------------

The pulgin needs to properly installed and setup to be used by AiidA::

 pip install -e .

If ``aiida_core`` is not install, it will be installed as the dependecies.
To allow AiiDA to discover the plugin, run::

 reentry scan aiida

.. note:: Please refer to AiiDA's documentation for plugin installation.

Test the plugin
----------------

AiiDA's pulgin test framework can be used::

 verdi -p {your_test_profile_name} devel tests db.castep

Using the plugin
----------------

A typical CASTEP calculation, like most density functional theory calculations, needs the following inputs:

* A ``ParameterData`` node with ``PARAM`` and ``CELL`` fields. Each fields is a dictionary define the keys goes into the *param* and *cell* files.

* A ``KpointsData`` node defines the kpoints. Supports explicit kpoints and kpoints grid.

* A ``StructureData`` node define the atomic structure for calculation.

* ``UspData`` or ``OtfgData`` nodes that defines the pseudo potential. An shortcut ``use_pseudo_from_family`` function may be called to simplify the process once the ``StructureData`` node has been defined.

* An optional ``ParameterData`` node with link name *settings* can be supplied to defines extra properties such as initial spins and use of symbolic link in restart calculations.

The ``use_xxxxx`` methods are used to link nodes. Once inputs are defined, ``submit_test`` method can be invoked to test generating the inputs. Note this may require some attributes of the calculation node to be defined depending on the scheduler and computer.

Generated input files
---------------------

Some metadata are included as comments in the input *cell* and *param* files.
This includes the generation time, AiiDA user, pk, uuid, label and description of the calculation node and input nodes used.
In addition, the following keys are set automatically:

* *iprint* is set to 1, otherwise parsing is not supported.

* If not set explicitly, *comment* will be set as the label of the calculation node to keep things tracked.

* If not set explicitly, *run_time* will be set to 95% of the requested walltime but will always be larger than 3600 seconds. To disable control set it to *0* the default value.

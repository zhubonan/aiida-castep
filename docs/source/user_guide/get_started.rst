Getting started
+++++++++++++++

AiiDA is a sophisticated framework with great ability to prepare, submit, manage calculations and preserve their provenance.
The workflow of running lengthy, complex density functional theory calculations on clusters can be automated and symplified.

I would strongly encourage any user to familiarise themselves with `AiiDA`_ before using this pulgin, otherwise a lot of things would not make sense.
The ``aiida_core`` package has excellent documentation located at `readthedocs <https://aiida-core.readthedocs.io>`_.
The user should also be familiar with running `CASTEP`_ manually using file interface.
Tutorials for `CASTEP`_ can be found at http://www.castep.org/CASTEP/OnlineTutorials.

.. note:: Make sure the version is consistent between documentation and ``aiida_core``.

.. _AiiDA: http://www.aiida.net
.. _CASTEP: http://www.castep.org

Installation
------------

Use pip to properly install the plugin::

 pip install -e <path_to_this_plugin>

This will properly register the entry points.
The ``-e`` flag makes the installation editable.
If ``aiida_core`` is not installed, it will be installed as a dependency.
To allow AiiDA to discover the plugin, run::

 reentry scan aiida

.. note:: Please refer to AiiDA's documentation for details of plugin installation.

Test the plugin
----------------

AiiDA's pulgin test framework should be used::

 verdi -p {your_test_profile_name} devel tests db.castep

.. note:: A dedicated test profile is mandatory. Please refer to AiiDA's documentation.

Using the plugin
----------------

For a typical CASTEP calculation, like most density functional theory calculations, needs the following inputs:

* A ``ParameterData`` node with ``PARAM`` and ``CELL`` fields. Each fields is a dictionary define the keys goes into the *param* and *cell* files.

* A ``KpointsData`` node defines the kpoints. Supports explicit kpoints and kpoints grid.

* A ``StructureData`` node define the atomic structure for calculation.

* Nodes that defines the pseudo potential. An shortcut ``use_pseudos_from_family`` function
  may be called to simplify the process once the ``StructureData`` node has been defined.
  Supported node type: ``OtfgData``, ``UspData``, ``UpfData``.

* An optional ``ParameterData`` node with link name ``settings`` can be supplied to defines extra properties such as initial spins and use of symbolic link in restart calculations.

The ``use_xxxxx`` methods are used to link nodes. Once inputs are defined, ``submit_test`` method can be invoked to test generating the inputs. Note this may require some attributes of the calculation node to be defined depending on the scheduler and computer.

Generated input files
---------------------

Some metadata are included as comments in the input *cell* and *param* files.
This includes the generation time, AiiDA user, pk, uuid, label and description of the calculation node and input nodes used.
All keywords are written in lower case.
In addition, the following keys are set automatically:

* *iprint* is set to 1, otherwise parsing is not supported.

* If not set explicitly, *comment* will be set as the label of the calculation node to keep things tracked.

* *run_time* will be set to 95% of the requested walltime by default unless it will be less than 3600 seconds.
  This is to ensure that check files can be written at the end of run.
  To completely disable control set it to *0* explicitly in ``ParameterData`` node.

* Consistency of spins are checked. Keyword *spin* in ``<seed>.param`` will be set automatically if not already defined.

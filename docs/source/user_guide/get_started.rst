Getting started
+++++++++++++++

AiiDA is a sophisticated framework with great ability to prepare, submit, manage calculations and preserve their provenance.
The workflow of running lengthy, complex density functional theory calculations on clusters can be automated and simplified.

I would strongly encourage any user to familiarize themselves with `AiiDA`_ before using this plugin, otherwise a lot of things would not make sense.
The ``aiida_core`` package has good documentation located at `readthedocs <https://aiida-core.readthedocs.io>`_.
The user should also be familiar with running `CASTEP`_ manually using file interface.
Tutorials for `CASTEP`_ can be found at http://www.castep.org/CASTEP/OnlineTutorials.

.. _AiiDA: http://www.aiida.net
.. _CASTEP: http://www.castep.org
.. _Quantum Mobile: https://www.materialscloud.org/work/quantum-mobile

Installation
------------
We will skip the guide for installation of AiiDA here.
Please refer to their documentation to install ``aiida_core`` and all the dependencies.
The easiest way to try out this plugin is perhaps to use `Quantum Mobile`_ - a virtual machines based on Ubuntu Linux and shipped with AiiDA installed and ready to use.

.. note::
   The latest version (1.0.x) of ``aiida-castep`` only works with ``aiida_core`` version 1.0.x.
   Please make sure the right version is installed. Also, you are most likely to need to work
   within a virtual environment (including conda environments).

To install from the Python Package Index (PyPI)::

 pip install aiida-castep

This will install the latest package released with its dependencies.

Alternatively, to clone the repository from the repository::

 git clone git@github.com:zhubonan/aiida-castep.git

Then pip can be used to install the plugin::

 pip install -e <path_to_this_plugin>

This way the entrypoints can be properly registered to allow ``aiida_core`` discover the plugin.
The optional ``-e`` flag makes the installation editable.
If ``aiida_core`` is not installed, it will be installed as a dependency.

Finally, to allow AiiDA to discover the plugin, run::

 reentry scan -r aiida

You should be able to see several calculations registered as ``castep.<name>`` using AiiDA's command-line interface::

 verdi plugin list aiida.calculations

the results should look like::

 Registered entry points for aiida.calculations:
  * arithmetic.add
  * castep.castep
  * castep.ts
  * templatereplacer

Generate CASTEP help information
--------------------------------

This plugin will check for mistakes in parameters supplied to CASTEP and automatically
write the keyword-value pair to the correct input file.
A dictionary containing all keywords and where they should be is used internally and stored
as a json file on the disk.
Although a pre-generated file is included, you may want generate one for the lastest
version of CASTEP.
The json file should be stored as ``$HOME/.castep_help_info_<version>.json``.

To generate the file, use command::

 verdi data castep-helper generate

By default, ``castep.serial`` executable will be used of it is available in ``PATH``..
This can be overridden using optional argument ``-e <path_to_executable>``.

For details, refer to the internal help using the ``--help`` flag.
Stored help information can be accessed using this interface as well,
imitating the behavior of ``castep.serial -h`` and ``castep.serial -s``.

.. note::
   The CASTEP executable is not a perquisite other than for generating the help dictionary.
   But if you do have one on the local computer,
   dryrun tests can done locally to further test the inputs and retrieved number of k-points
   required and estimate memory usage.


Test the plugin
----------------

Tests for the plugin is written using ``pytest`` so all you need to do is type::

  pytest aiida_castep

from the project's root directory.

.. note::
   Of course this needs ``pytest`` to be installed. This can be done by ``pip install aiida-castep[testing]``.
   You may also need to (re)install aiida with ``pip install aiida_core[testing]``.


Using the plugin
----------------

Within the AiiDA framework a calculation is performed by playing a ``CalcJob`` process.
A number of nodes are passed to the process as the input.
The provenance of the calculation is stored as a ``CalcJobNode`` which links to the input and output nodes.

For a typical CASTEP calculation, like most density functional theory calculations, needs the following inputs:

* A ``Dict`` node with ``PARAM`` and ``CELL`` fields. Each fields is a dictionary define the keys goes into the *param* and *cell* files.

* A ``KpointsData`` node defines the kpoints. Both explicit kpoints and kpoints grid are supported.

* A ``StructureData`` node define the atomic structure for calculation.

* Nodes that defines the pseudo potential. An shortcut ``use_pseudos_from_family`` function
  may be called to simplify the process once the structure is known.
  The pseudopotentials can be any combination of ``OtfgData``, ``UspData``, ``UpfData`` nodes.

* An optional ``Dict`` node with link name ``settings`` can be supplied to defines extra properties such as initial spins and use of symbolic link in restart calculations.

The simply the process, a ``ProcessBuilder`` instance can be used to define the inputs under interactive python shell.
Finally, the calculation can be submitted by the ``aiida.engine.submit`` or the ``aiida.engine.run_get_node`` function.


Generated input files
---------------------

Some meta data are included as comments in the input *cell* and *param* files.
This includes the generation time, AiiDA user, pk, uuid, label and description of the calculation node and input nodes used.
All keywords are written in lower case.
In addition, the following keys are set automatically:

* *iprint* is set to 1 by default. *iprint = 2* may work but not fully tested yet.

* If not set explicitly, *comment* will be set as the label of the calculation node to keep things tracked.

* *run_time* will be set to 95% of the requested wall-time by default unless it will be less than 180 seconds.
  This is to avoid running out of time while writing the checkpoint file.
  CASTEP does try to be intelligent and stop if it thinkgs the next iteration (geometry optimisation, phonons e.t.c)
  will exceed the time limit. 
  To completely disable time limit control, set it to *0* explicitly in ``Dict`` node.

* Consistency of spins are checked.  Keyword *spin* in ``<seed>.param`` will be set automatically, if not already defined, using the initial spins set for ``<seed>.cell`` file.

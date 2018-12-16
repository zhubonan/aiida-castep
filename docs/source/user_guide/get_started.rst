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
   At the moment, ``aiida-castep`` only works with ``aiida_core`` version 0.12.x.
   Please make sure the right version is installed. 

First, clone the repository::

 git clone git@gitlab.com:bz1/aiida-castep.git

Then use pip to install the plugin::

 pip install -e <path_to_this_plugin>

This way the entrypoints can be properly registered to allow ``aiida_core`` discover the plugin.
The optional ``-e`` flag makes the installation editable.
If ``aiida_core`` is not installed, it will be installed as a dependency.

Alternatively, this plugin can be installed from the PyPI directly::

 pip install aiida-castep

Finally, to allow AiiDA to discover the plugin, run::

 reentry scan -r aiida

You should be able to see several calculations registered as ``castep.<name>`` using AiiDA's command-line interface::

 verdi calculation plugin


Generate CASTEP help information
--------------------------------

This plugin will check for mistakes in parameters supplied to CASTEP before writing
input files.
A dictionary containing all keywords and where they should be is used internally.
It is stored as ``$HOME/.castep_help_info_<version>.json`` and loaded at runtime.
To generate this file, use command::

 verdi data castep-help generate

By default, ``castep.serial`` executable will be used of it is available in ``PATH``..
This can be overridden using optional argument ``-e <path_to_executable>``.
For details, refer to the internal help using the ``--help`` flag.
Stored help information can be accessed using this interface as well,
imitating the behavior of ``castep.serial -h`` and ``castep.serial -s``.

.. note::
   The CASTEP executable is not required for using this plugin other than generating the help dictionary.
   But if you do have one on the local computer,
   dryrun tests can done locally to get information such as number of k-points and memory usages.


Test the plugin
----------------

Tests for the plugin is written using ``pytest`` so all you need to do is type::

  pytest aiida_castep

from the project's root directory.


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

Some meta data are included as comments in the input *cell* and *param* files.
This includes the generation time, AiiDA user, pk, uuid, label and description of the calculation node and input nodes used.
All keywords are written in lower case.
In addition, the following keys are set automatically:

* *iprint* is set to 1, otherwise parsing is not supported.

* If not set explicitly, *comment* will be set as the label of the calculation node to keep things tracked.

* *run_time* will be set to 95% of the requested wall-time by default unless it will be less than 3600 seconds.
  This is to ensure that check files can be written at the end of run.
  To completely disable control set it to *0* explicitly in ``ParameterData`` node.

* Consistency of spins are checked. Keyword *spin* in ``<seed>.param`` will be set automatically if not already defined using the initial spins set for ``<seed>.cell`` file.

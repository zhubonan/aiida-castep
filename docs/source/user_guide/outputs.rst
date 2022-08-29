===============
Getting results
===============

This page contains information about the properties that will be parsed by ``aiida_castep`` plugin.

Parsing output
--------------

A ``<seed>.castep`` file is always written by CASTEP with human readable information.
This plugin try to parser as much useful information as we can as possible.
At the moment, the parser only supports verbosity level ``iprint = 1``.
For geometric optimizations, a ``<seed>.geom`` files will also be written containing
atomic configuration of each iteration and often has higher precision than those in
``<seed>.castep``.

For each ``CastepCalcultion`` the parser plugin creates a ``Dict`` with link named
``output_parameters`` for the single valued results. For example:

* Final total/free/0K energy

* Units of force, energy, stress if they are parsed

* Miscellaneous: total time used, parallel efficiency

* Warnings

Attribute of this node can be accessed easily via ``calc.res.xx``. For example::

 calc.res.free_energy

returns the free energy of the calculations and tab completion may be used in interactive environments.
Array-like properties such as forces and stresses are stored in dedicated ``ArrayData`` node with
link ``output_array``.
If there are multiple iterations, a ``TrajectoryData`` node is created instead with name ``output_trajectory``
It also contains other arrays for quantifies such as enthalpy/stress at each iteration.

CASTEP writes Kohn-Sham eigenvalues in a ``<seed>.bands`` file which can be used for plotting
band structure or density of states. The file is parsed by this plugin and a ``BandsData`` node will be created.


Restarting a calculation
------------------------

Tracking lengthy calculations with multiple restarts can be complicated.
This is where AiiDA's ability of preserving provenance comes in.
A ``create_restart`` method is available and for its capability please refer to the
module document.
For a continuations run, CASTEP reads in data from previous run from ``<seed>.check`` or ``<seed>.castep_bin`` files.
The ``param`` and ``cell`` files are also read and some parameters can be changed at restart.
When running under ``aiida_castep`` parent and children calculations will be linked via a ``RemoteFolder`` node.

.. note:: Parents and children may or may not share the same **parameters**.
   It depends on whether there is any change in parameters.

The command ``verdi node tree`` is useful for drawing a tree of children for visualisation in terminal.

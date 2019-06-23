=========
Workflows
=========

AiiDA provides a workflows engine that is fast and scalable and allow the provenance to be stored.
This plugin does not provide any elaborated workflows but rather prepare the building blocks.

The key advantage of AiiDA's *process* based design is that the workflows can be nested as well as
being extended. Workflows are sub-classes of ``WorkChain`` with defined inputs, outputs and logics.
They are run by the daemon and their states are persisted and hence un-affected by the shutdowns
of the host computer.

This section describes the workflows provided by the plugin package.


CastepBaseWorkChain
-------------------

As the name suggests, it the base of defining other workflows. This does not stop the class from
being useful itself. It run an calculation and try to recover from problems such as SCF convergence issue,
insufficient wall-time (during geometry relaxation). It also allows simpler input parameter format and
optional *dryrun* check of the input parameters (not implemented yet).

Normally, the keywords are nested under ``PARAM`` and ``CELL`` field of the ``input_parameters`` node of a
calculation. This is a design choice to allow a stable interface for querying. This is relaxed when working
with a ``CastepBaseWorkChain`` such that a *flat* dictionary can be used::

 {'symmetry_generate': True,
  'fix_all_cell': True,
  'xc_functional': 'pbe',
  cut_off_energy': 600,
 }

A standard ``Dict`` with nested fields is created by the workchain and used as the input of ``CastepCalculation``.


CastepRelaxWorkChain
--------------------

This workflow is for geometry optimization and will run the base work chain until the structure is fully relaxed,
or limit of iterations is reached.

CastepAlterRelaxWorkChain
-------------------------

This is a variant of the ``CasteRelaxWorkChain`` such that the cell constraints are turned on and off for
each iteration. This is to tackle slow convergence issues when the cell is partially constrained.

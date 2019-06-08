=========
Workflows
=========

AiiDA provides a workflows engine that is fast and scable and allow the provenance to be stored.
This plugin does not provide any elaborated workflows but rather prepare the building blocks.

The key advantage of AiiDA's *process* based design is that the workflows can be nested as well as
being extended. Workflows are sub-classes of ``WorkChain`` with defined inputs, outputs and logics.
They are run by the daemon and their states are persisted and hence un-affected by the shutdowns
of the host computer.

In this section, I describe the workflows provided by the plugin package.


``CastepBaseWorkChain``
-----------------------

As the name suggests, it can be used as the base of defining other workflows. This does not itself from
being useful. It run a calculation and try to recover from problems such as SCF convergence issue,
insufficient walltime (during geometry relaxation). It also allows simpler input parameter format and
optional *dryrun* check of the input paramters.


``CastepRelaxWorkChain``
------------------------

This workflow is for geometry optimization and will run until the structure is fully relaxed.
Optional final calculation may be requested.


``CastepBandsWorkChain``
------------------------
This workflow first fully relax the structure and then computes the bands structure.

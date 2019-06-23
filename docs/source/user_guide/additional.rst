===================
Additional settings
===================

An additional ``Dict`` node can be used by the calculation. The following fields can be used:

* ``SPINS``: A list of initial spins for each atom.

* ``PARENT_FOLDER_SYMLINK``: Whether we use symbolic link to the parent folder that contains ``<seed>.check``.

* ``LABELS``: A list of labels for each atom.

* ``CMDLINE``: Additional parameters to be passed. By default we call ``<castep_excutable> <seed>`` but some times additional parameters may be useful, e.g when we use wrapping script.

* ``ADDITIONAL_RETRIEVE_LIST``: A list for additional files to be retrieved from remove work directory. See also description in AiiDA's `tutorial <https://aiida-core.readthedocs.io/en/latest/developer_guide/devel_tutorial/code_plugin_int_sum.html>`__.

Task specific calculations
==========================

The genetic ``CastepCalculation`` can be used for any calculation but one may want to use subclasses for spefic tasks. 
For example, ``CastepBSCalculation`` can be used for band structure runs.
Doing so will allow additional ``KpointsData`` for BZ sampling to be linked as the input for the calculations.
A similar classes is defined for *task: spectral* calculations.
Classes to support *pot1d* utility which output formatted potentials and *transitionstatesearch* tasks are
also implemented.

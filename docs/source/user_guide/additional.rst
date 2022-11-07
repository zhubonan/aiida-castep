===================
Additional settings
===================

An additional ``Dict`` node can be used by the calculation via the ``settings`` input port. The following fields can be used:

* ``SPINS``: A list of initial spins for each atom.

* ``PARENT_FOLDER_SYMLINK``: Whether we use symbolic link to the parent folder that contains ``<seed>.check``.

* ``LABELS``: A list of labels for each atom.

* ``CMDLINE``: Additional parameters to be passed. By default we call ``<castep_executable> <seed>`` but some times additional parameters may be useful, e.g when we use wrapping script.

* ``ADDITIONAL_RETRIEVE_LIST``: A list for additional files to be retrieved from remote work directory.

Getting help about calculations
===============================

The ``verdi`` commandline interface provide a convenient way to inspect the inputs and outputs of a ``CalcJob``.
For example, all possible the inputs and outputs nodes can be listed using ``verdi plugins list aiida.calculations castep.castep``.
The definition of the exit codes can also be inspected this way.

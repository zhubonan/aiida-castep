===============
Tips and tricks
===============

This section introduces some tips and tricks for using the plugin.

Creating restarts of calculations
---------------------------------

You can create restarts easily using the ``create_restart`` method attached to the ``tools`` of
the ``CalcJobNode`` created.
The function can also be applied to builder or input dictionary to created a copy with
some alterations.
Hence, the usage is not limited to the case where the calculation failed or the geometry optimisation
does not converged within the iteration limit. For example, you may just want to create
a series of calculation with slightly different parameters, which can be
achieved using the ``param_update`` and ``param_delete`` keywords.
For more detail, please see the docstring of :py:func:`aiida_castep.calculations.tools.create_restart`.

For workchains, use the ``get_builder_restart`` method to get an ``ProcessBuilder`` object containing
the original input.
Note that one still has to set ``metadata`` fields (for example ``builder.calc.metadata``) manually,
as the aiida engine does not support inferring their values yet.

Creating pseudopotential families
---------------------------------

These can be achieved using functions :py:func:`aiida_castep.data.otfg.upload_otfg_family`
and :py:func:`aiida_castep.data.usp.upload_usp_family`.
The commandline tools are not avaliable at this time.

.. note:
   You cannot define pseudopotential family mixing usp and otfg potentials, for now.


Update parameter of a calculation
---------------------------------

There is a ``update_parameters`` method under ``CastepCalculation`` which is available to quickly
change the input parameters of a calculation that is not yet stored in the database. Simply pass
the field you want to change as keyword arguments to the method.
A plain python dictionary may also be used as the input and will be *serialized* automatically into ``Dict``.


.. note:
   Passing ``force=True`` will create a new ``Dict`` if the existing ``Dict`` is stored.
   Be aware that the unstored node may be linked to more than one calculations and the
   change will be shared.


Get a summary of the inputs and compare them
--------------------------------------------

The method ``get_castep_inputs_summary`` can be called to  get a summary of the inputs
of a ``CastepCalculation`` at any time. In addition, the ``compare_with`` method
can be used to compare the inputs between another calculation and returns the
difference in the inputs as a dictionary. The `deepdiff <https://pypi.org/project/deepdiff/>`_ package is used behind the scene.


Convention of kpoints
----------------------

CASTEP uses the Monkhorst-Pack grid formula following `this <https://journals.aps.org/prb/abstract/10.1103/PhysRevB.13.5188>` paper,
where the directions with odd numbers are centred to the origin, and those with even numbers are not.
To get Gamma-centered grid, ``kpoint_mp_offset`` needs to be specified with  ``-1/N`` for each direction with odd ``N``.

For example, to use a Gamma-centered ``8x8x8`` grid, the follwing lines are required in the ``<seed>.cell``::

 kpoint_mp_grid: 8 8 8
 kpoint_mp_offset: -0.0625 -0.0625 -0.0625

The plugin follows the same convention as used by the code, with the grid and the offsets passed to the code as they are.
This does mean that the same ``KpointsData`` used for other DFT code can mean differently.
For example, a ``KpointsData`` with ``(8, 8, 8)`` mesh given to ``aiida-vasp`` is Gamma-centered, but is it not
when passed to ``aiida-castep``.

Certain quantities returned by methods of ``KpointData`` assumes that grid is Gamma-centering,
so care should be taken to use them with ``aiida-castep``.

To select Gamma-centered kpoint grid, one can set the ``ensure_gamma_centering`` port of the ``CastepBaseWorkchain`` to be ``Bool(True)``.
This will automatically compute the offset and include it in the ``KpointsData`` generated and passed to the underlying ``CastepCalculation``.


Reading occupantions
--------------------

The standard ``bands`` output file written by CASTEP does not included the occupations for each band.
To read the occupation nubmers, one has to include the ``castep_bin`` output in the retrieve list.
This will trigger the plugin to read the band information directly from this binary checkpoint file,
which contains the occupation numbers.
The will check if all kpoints contain empty bands, as otherwise the calculation results can have large errors.

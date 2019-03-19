===============
Tips and tricks
===============

This section introduces some tips and tricks for using the plugin.

Creating restarts of calculations
---------------------------------

You can create restarts easily using the ``create_restart`` method of ``CastepCalculation``.
This is not limited to the case where the calculation failed or the geometry optimisation
does not converged within the iteration limit. For example, you may just want to create
a series of calculation with slightly different parameters, which can be
achieved using the ``param_update`` and ``param_delete`` keywords with ``ignore_state=True``.
For more detail, please see the docstring of :py:func:`aiida_castep.calculations.base.create_restart_`.


Creating pseudopotential families
---------------------------------

These can be achieved using functions :py:func:`aiida_castep.data.otfg.upload_otfg_family`
and :py:func:`aiida_castep.data.usp.upload_usp_family`.

.. note:
   You cannot define pseudopotential family mixing usp and otfg potentials, for now.


Update parameter of a calculation
---------------------------------

There is a ``update_parameters`` method is available to quickly change the input
parameters of a calculation that is not yet stored in the database. Simply pass
the field you want to change as keyword arguments to the method.

.. note:
   Passing ``force=True`` will create a new ``ParameterData`` and link it to the
   calculation if the existing ParameterData is stored. Be aware that the unstored
   node may be linked to more than one calculations and the change will be shared. 


Get a summary of the inputs and compare them
--------------------------------------------

The method ``get_castep_inputs_summary`` can be called to  get a summary of the inputs
of a ``CastepCalculation`` at any time. In addition, the ``compare_with`` method
can be used to compare the inputs between another calculation and returns the
difference in the inputs as a dictionary. The `deepdiff <https://pypi.org/project/deepdiff/>`_ package is used behind the scene.

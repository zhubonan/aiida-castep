"""
Module for Relxation WorkChain
"""

from __future__ import absolute_import
import six
import re

from aiida.engine import WorkChain, if_, while_, ToContext, append_
from aiida.common import AttributeDict
import aiida.orm as orm
from aiida.orm.nodes.data.base import to_aiida_type
from .base import CastepBaseWorkChain


class CastepRelaxWorkChain(WorkChain):
    """
    WorkChain to relax structures.
    Restart the relaxation calculation until the structure is fully relaxed.
    Each CASTEP relaxation may finish without error with not fully relaxed structure
    if the number of iteration is exceeded (*geom_max_iter*).
    This workchain try to restart such calculations (wrapped in CastepBaseWorkChain)
    until the structure is fully relaxed
    """

    _max_meta_iterations = 10

    @classmethod
    def define(cls, spec):
        """Define this workchain"""

        # Apply superclass specifications
        super(CastepRelaxWorkChain, cls).define(spec)
        spec.expose_inputs(
            CastepBaseWorkChain, namespace='base', exclude=('structure', ))

        spec.input(
            'structure',
            valid_type=orm.StructureData,
            help='Structure to be used for relxation',
            required=True)
        spec.input(
            'relax_options',
            valid_type=orm.Dict,
            serializer=to_aiida_type,
            required=False,
            help='Options for relaxation')

        spec.expose_outputs(CastepBaseWorkChain, exclude=['output_structure'])
        spec.output(
            'output_structure', valid_type=orm.StructureData, required=True)

        spec.outline(
            cls.setup,
            while_(cls.should_run_relax)(cls.run_relax, cls.inspect_relax),
            cls.result)
        spec.exit_code(101, 'ERROR_SUB_PROCESS_FAILED_RELAX',
                       'Subprocess lauched has failed in the relax stage')

        spec.exit_code(
            102, 'ERROR_CONVERGE_NOT_REACHED',
            'Geometry optimisation is not converged but the maximum iteration is exceeded.'
        )

    def setup(self):
        """Initialize internal parameters"""
        self.ctx.iteration = 0
        self.ctx.is_converged = 0
        self.ctx.current_cell_volume = None
        self.ctx.current_structure = self.inputs.structure
        self.ctx.restart_mode = 'reuse'
        # A dictionary used to update the default inputs
        self.ctx.inputs_update = {}
        self.ctx.inputs = AttributeDict(self.inputs)

        relax_options = self.inputs.get('relax_options', None)
        if relax_options is None:
            relax_options = {}
        else:
            relax_options = self.inputs.relax_options.get_dict()

        self.ctx.max_meta_iterations = relax_options.pop(
            'max_meta_iterations', self._max_meta_iterations)
        self.ctx.restart_mode = relax_options.pop('restart_mode', 'reuse')
        self.ctx.relax_options = relax_options

    def should_run_relax(self):
        """Decide whether another iteration should be run"""
        return not self.ctx.is_converged and self.ctx.iteration < self.ctx.max_meta_iterations

    def run_relax(self):
        """Run the relaxation"""
        self.ctx.iteration += 1
        inputs = AttributeDict(
            self.exposed_inputs(CastepBaseWorkChain, namespace='base'))
        inputs.structure = self.ctx.current_structure

        # Update the inputs
        inputs.update(self.ctx.inputs_update)

        running = self.submit(CastepBaseWorkChain, **inputs)

        self.report('launching CastepBaseWorkChain<{}> Iteration #{}'.format(
            running.pk, self.ctx.iteration))

        return ToContext(workchains=append_(running))

    def inspect_relax(self):
        """
        Inspet the relaxation results, check if convergence is reached.
        """

        workchain = self.ctx.workchains[-1]

        if not workchain.is_finished_ok:
            self.report(
                'Relaxation CastepBaseWorkChain failed with exit status {}'.
                format(workchain.exit_status))
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_RELAX

        try:
            structure = workchain.outputs.output_structure
        except AttributeError:
            self.report(
                'Relaxation CastepBaseWorkChain finished but not output structure'
            )
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_RELAX

        # Check if the geometric convergence has reached
        output_parameters = workchain.outputs.output_parameters.get_dict()
        if output_parameters.get('geom_unconverged') is True:
            # Assign restart mode and folder
            if self.ctx.restart_mode in ['reuse', 'continuation']:
                self.ctx.inputs_update['{}_folder'.format(
                    self.ctx.restart_mode)] = workchain.outputs.remote_folder
                # Unless we use the continuation mode, the structure should be set to the output structure
            if self.ctx.restart_mode != 'continuation':
                self.ctx.current_structure = structure
            self.report(
                'Relaxation CastepBaseWorkChain finished not not converged')
        else:
            self.ctx.is_converged = True
            self.report('Geometry optimisation is converged')

        return

    def result(self):
        """Attach the output parameters and structure of the last workchain to the outputs."""
        if self.ctx.is_converged:
            self.report('workchain completed after {} iterations'.format(
                self.ctx.iteration))
            exit_code = None
        else:
            self.report(
                'maximum number of meta iterations exceeded but relaxation is not converged'
            )
            exit_code = self.exit_codes.ERROR_CONVERGE_NOT_REACHED

        workchain = self.ctx.workchains[-1]
        structure = workchain.outputs.output_structure

        self.out_many(self.exposed_outputs(workchain, CastepBaseWorkChain))
        self.out('output_structure', structure)

        return exit_code


class CastepAlterRelaxWorkChain(CastepRelaxWorkChain):
    """
    A relaxation workflow that alternates between fixed cell and unfixed cell
    This is meidate the problem in CASTEP where if the cell is partially constraints
    the convergence would be very slow.

    To overcome this problem, the structure should be relaxed with cell constraints
    then restart with fixed cell and repeat.

    Following fields can be used in ``relax_options``

    :var_cell_iter_max: Maximum iterations in variable cell relaxation, default to 10

    :fix_cell_iter_max: Maximum iterations in fixed cell relaxation, default to 20

    """

    _default_fix_cell_iter_max = 20
    _default_var_cell_iter_max = 10
    _max_meta_iterations = 11

    @classmethod
    def define(cls, spec):
        """Define the workchain"""
        super(CastepAlterRelaxWorkChain, cls).define(spec)

        spec.exit_code(201, 'ERROR_NO_CELL_CONS_SET',
                       'NO cell_constraints find in the input')

    def setup(self):
        super(CastepAlterRelaxWorkChain, self).setup()
        input_parameters = self.inputs.base.parameters.get_dict()

        # Find the inital cell constraint
        cell_constraints = input_parameters.get('cell_constraints')
        if not cell_constraints:
            cell_constraints = input_parameters['CELL'].get('cell_constraints')

        if not cell_constraints:
            return self.exit_codes.ERROR_NO_CELL_CONS_SET

        self.ctx.init_cell_cons = cell_constraints

        # Set the iteration limit
        self.ctx.var_cell_iter_max = self.ctx.relax_options.pop(
            'var_cell_iter_max', self._default_var_cell_iter_max)
        self.ctx.fix_cell_iter_max = self.ctx.relax_options.pop(
            'fix_cell_iter_max', self._default_fix_cell_iter_max)
        self.ctx.restart_mode = 'reuse'
        self.ctx.is_fixed_cell = False

    def inspect_relax(self):
        """
        Inspet the relaxation results, check if convergence is reached.
        """

        workchain = self.ctx.workchains[-1]

        if not workchain.is_finished_ok:
            self.report(
                'Relaxation CastepBaseWorkChain failed with exit status {}'.
                format(workchain.exit_status))
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_RELAX

        try:
            structure = workchain.outputs.output_structure
        except AttributeError:
            self.report(
                'Relaxation CastepBaseWorkChain finished but not output structure'
            )
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_RELAX

        # Check if the geometric convergence has reached
        output_parameters = workchain.outputs.output_parameters.get_dict()
        unconv = output_parameters.get('geom_unconverged')
        if unconv is True or self.ctx.is_fixed_cell:
            # Assign restart mode and folder
            if self.ctx.restart_mode in ['reuse', 'continuation']:
                self.ctx.inputs_update['{}_folder'.format(
                    self.ctx.restart_mode)] = workchain.outputs.remote_folder
            # Unless we use the continuation mode, the structure should be set to the output structure
            if self.ctx.restart_mode != 'continuation':
                self.ctx.current_structure = structure

            if self.ctx.is_fixed_cell:
                self.set_cons_and_imax(self.ctx.init_cell_cons,
                                       self.ctx.var_cell_iter_max)
                self.ctx.is_fixed_cell = False
                # Give verbose information
                if unconv is True:
                    self.report(
                        'Fixed cell relax not conerged, restore cell constraints anyway'
                    )
                else:
                    self.report(
                        'Fixed cell relax is converged, restart with inital cell constraints'
                    )
            else:
                # Set the constraint to fully fixed cell
                self.set_cons_and_imax(['0 0 0', '0 0 0'],
                                       self.ctx.fix_cell_iter_max)
                self.ctx.is_fixed_cell = True
                self.report(
                    'Variable cell relax not converged. Turning cell constraints off'
                )
        else:
            self.ctx.is_converged = True
            self.report('Geometry optimisation is converged')

        return

    def set_cons_and_imax(self, cell_cons, iter_max):
        """Set the cell constraints"""

        # Load the current configuration from the context
        input_param = self.ctx.inputs_update.get('parameters', None)

        # If not, create from the inputs
        if not input_param:
            input_param = self.inputs.base.parameters.get_dict()

        # Keep the original format of the inptus.
        if 'CELL' in input_param:
            input_param['CELL']['cell_constraints'] = cell_cons
        else:
            input_param['cell_constraints'] = cell_cons

        # Keep the original format of the inptus.
        if 'PARAM' in input_param:
            input_param['PARAM']['geom_max_iter'] = iter_max
        else:
            input_param['geom_max_iter'] = iter_max

        self.ctx.inputs_update['parameters'] = input_param

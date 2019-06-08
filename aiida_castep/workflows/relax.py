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

        relax_options = self.inputs.get('relax_options', {})
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
        if self.ctx.is_converged and self.ctx.iteration <= self.ctx.max_meta_iterations:
            self.report('workchain completed after {} iterations'.format(
                self.ctx.iteration))
        else:
            self.report('maximum number of meta iterations exceeded')

        workchain = self.ctx.workchains[-1]
        structure = workchain.outputs.output_structure

        self.out_many(self.exposed_outputs(workchain, CastepBaseWorkChain))
        self.out('output_structure', structure)

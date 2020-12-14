"""
Module for Relaxation WorkChain

CHANGELOG:

- 0.1.0: Added ``bypass`` option to skip convergence checking.
  The user is still responsible to setting the correct inputs.
"""

from __future__ import absolute_import

from aiida.engine import WorkChain, while_, ToContext, append_
from aiida.common import AttributeDict
import aiida.orm as orm
from aiida.orm.nodes.data.base import to_aiida_type

from aiida.common.exceptions import NotExistent, MultipleObjectsError
from aiida_castep.common import INPUT_LINKNAMES as IN_LINKS
from aiida_castep.common import OUTPUT_LINKNAMES as OUT_LINKS
from aiida_castep.calculations.helper import CastepHelper
from aiida_castep.calculations.tools import flat_input_param_validator
from .base import CastepBaseWorkChain

# pylint: disable=protected-access,no-member,import-outside-toplevel

__version__ = '0.1.0'


class CastepRelaxWorkChain(WorkChain):
    """
    WorkChain to relax structures.
    Restart the relaxation calculation until the structure is fully relaxed.
    Each CASTEP relaxation may finish without error with not fully relaxed structure
    if the number of iteration is exceeded (*geom_max_iter*).
    This workchain try to restart such calculations (wrapped in CastepBaseWorkChain)
    until the structure is fully relaxed

    ``relax_options`` is a Dict of the options avaliable fields are:

    - restart_mode: mode of restart, choose from ``reuse`` (default), ``structure``,
      ``continuation``.
    - bypass: Bypass relaxation control - e.g. no checking of the convergence.
      Can be used for doing singlepoint calculation.

    """

    _max_meta_iterations = 10

    @classmethod
    def define(cls, spec):
        """Define this workchain"""

        # Apply superclass specifications
        super(CastepRelaxWorkChain, cls).define(spec)
        spec.expose_inputs(CastepBaseWorkChain,
                           namespace='base',
                           exclude=('calc', ))
        spec.expose_inputs(CastepBaseWorkChain._calculation_class,
                           namespace='calc',
                           exclude=['structure'])

        spec.input('calc.parameters',
                   valid_type=orm.Dict,
                   serializer=to_aiida_type,
                   help='Input parameters, flat format is allowed.',
                   validator=flat_input_param_validator)

        spec.input('structure',
                   valid_type=orm.StructureData,
                   help='Structure to be used for relaxation.',
                   required=True)
        spec.input('relax_options',
                   valid_type=orm.Dict,
                   serializer=to_aiida_type,
                   required=False,
                   help='Options for relaxation.')

        spec.expose_outputs(CastepBaseWorkChain, exclude=['output_structure'])
        spec.output('output_structure',
                    valid_type=orm.StructureData,
                    required=False,
                    help='The relaxed structure.')

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
        # A dictionary used to update the default inputs
        self.ctx.calc_update = {}  # Update to the calc namespace
        self.ctx.base_update = {}  # Update to the baes namespace
        self.ctx.inputs = AttributeDict(self.inputs)

        relax_options = self.inputs.get('relax_options', None)
        if relax_options is None:
            relax_options = {}
        else:
            relax_options = self.inputs.relax_options.get_dict()

        self.ctx.max_meta_iterations = relax_options.pop(
            'max_meta_iterations', self._max_meta_iterations)
        restart_mode = relax_options.pop('restart_mode', 'reuse')
        assert restart_mode in [
            "reuse", "continuation", "structure"
        ], "Invalid restart mode: {}".format(restart_mode)
        self.ctx.bypass_relax = relax_options.pop('bypass', False)
        self.ctx.restart_mode = restart_mode
        self.ctx.relax_options = relax_options

    def should_run_relax(self):
        """Decide whether another iteration should be run"""
        return not self.ctx.is_converged and self.ctx.iteration < self.ctx.max_meta_iterations

    def run_relax(self):
        """Run the relaxation"""
        self.ctx.iteration += 1
        link_label = 'iteration_{}'.format(self.ctx.iteration)
        # Assemble the inputs
        inputs = AttributeDict(
            self.exposed_inputs(CastepBaseWorkChain,
                                namespace='base',
                                agglomerate=False))
        inputs.calc = AttributeDict(
            self.exposed_inputs(CastepBaseWorkChain._calculation_class,
                                namespace='calc'))
        inputs.calc.structure = self.ctx.current_structure

        # Update the inputs
        inputs.calc.update(self.ctx.calc_update)
        inputs.update(self.ctx.base_update)

        # In case metadata is not defined at all
        if 'metadata' in inputs:
            inputs.metadata = AttributeDict(inputs['metadata'])
            inputs.metadata['call_link_label'] = link_label
            if 'label' not in inputs.metadata:
                inputs.metadata['label'] = self.inputs.metadata.get(
                    'label', '')
        else:
            inputs['metadata'] = {
                'call_link_label': link_label,
                'label': self.inputs.metadata.get('label', '')
            }

        running = self.submit(CastepBaseWorkChain, **inputs)

        self.report('launching CastepBaseWorkChain<{}> Iteration #{}'.format(
            running.pk, self.ctx.iteration))

        return ToContext(workchains=append_(running))

    def inspect_relax(self):
        """
        Inspet the relaxation results, check if convergence is reached.
        """
        if self.ctx.get('bypass_relax', False):
            self.report("Bypass mode, convergence checking skipped")
            self.ctx.is_converged = True
            return None

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
                'Relaxation CastepBaseWorkChain finished but no output structure found'
            )
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_RELAX

        # Check if the geometric convergence has reached
        output_parameters = workchain.outputs.output_parameters.get_dict()
        if output_parameters.get('geom_unconverged') is True:
            # Assign restart mode and folder
            if self.ctx.restart_mode in ['reuse', 'continuation']:
                # The input link to the Base WorkChain determine to mode of continuation
                # Parameters are updated automatically
                self.ctx.base_update['{}_folder'.format(
                    self.ctx.restart_mode)] = workchain.outputs.remote_folder
                # Unless we use the continuation mode, the structure should be set to the output structure
            if self.ctx.restart_mode != 'continuation':
                self.ctx.current_structure = structure

            self._push_parameters(workchain)
            self.report(
                'Relaxation CastepBaseWorkChain finished but not converged')
        else:
            self.ctx.is_converged = True
            self.report('Geometry optimisation is converged')

        return None

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
        if 'output_structure' in workchain.outputs:
            structure = workchain.outputs.output_structure
            self.out('output_structure', structure)

        self.out_many(self.exposed_outputs(workchain, CastepBaseWorkChain))

        return exit_code

    def _push_parameters(self, workchain):
        """
        Push the parameters for completed calculation to the current inputs
        """
        query = orm.QueryBuilder()
        query.append(orm.WorkChainNode,
                     filters={'id': workchain.pk},
                     tag='work')
        query.append(orm.Dict,
                     with_incoming='work',
                     tag='output_dict',
                     edge_filters={'label': OUT_LINKS['results']})
        query.append(orm.CalcJobNode,
                     with_outgoing='output_dict',
                     filters={'attributes.exit_status': 0},
                     tag='final_calc')
        query.append(orm.Dict,
                     with_outgoing='final_calc',
                     edge_filters={'label': IN_LINKS['parameters']},
                     project=['attributes'])

        try:
            last_param = query.one()[0]
        except (MultipleObjectsError, NotExistent):
            self.report(
                'Cannot found the input node for the last Calculation called in BaseWorkChain'
            )
            return self.exit_codes.ERROR_SUB_PROCESS_FAILED_RELAX

        # Compare with the input parameters of this one
        helper = CastepHelper()
        orig_in_param = self.inputs.calc[IN_LINKS['parameters']].get_dict()
        orig_in_param, _ = helper._from_flat_dict(orig_in_param)

        # Pop out any continuation related keywords
        for param in [last_param, orig_in_param]:
            for key in ['reuse', 'continuation']:
                param['PARAM'].pop(key, None)

        if orig_in_param != last_param:
            self.report(
                'Pushed the input parameters of the last completed calculation to the next iteration'
            )
            self.ctx.calc_update[IN_LINKS['parameters']] = orm.Dict(
                dict=last_param)
        return None


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
        input_parameters = self.inputs.calc.parameters.get_dict()

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

        return None

    def inspect_relax(self):
        """
        Inspet the relaxation results, check if convergence is reached.
        """

        if self.ctx.get('bypass_relax', False):
            self.report("Bypass mode, convergence checking skipped")
            self.ctx.is_converged = True
            return None

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
                self.ctx.base_update['{}_folder'.format(
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
        # Variable cell + converged geometry
        else:
            self.ctx.is_converged = True
            self.report('Geometry optimisation is converged')

        return None

    def set_cons_and_imax(self, cell_cons, iter_max):
        """Set the cell constraints"""

        # Load the current configuration from the context
        last_param = self.ctx.calc_update.get('parameters', None)

        # If not, create from the inputs
        if not last_param:
            last_param = self.inputs.calc.parameters.get_dict()

        # Keep the original format of the inptus.
        if 'CELL' in last_param:
            last_param['CELL']['cell_constraints'] = cell_cons
        else:
            last_param['cell_constraints'] = cell_cons

        # Keep the original format of the inptus.
        if 'PARAM' in last_param:
            last_param['PARAM']['geom_max_iter'] = iter_max
        else:
            last_param['geom_max_iter'] = iter_max

        self.ctx.calc_update['parameters'] = last_param

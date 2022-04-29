"""
This module contains the *base* workchain class which acts as the starting point of
implementing more complex ones
"""

import re
import numpy as np

from aiida.engine import WorkChain, if_, while_, ToContext, append_
from aiida.common.lang import override
from aiida.orm.nodes.data.base import to_aiida_type
from aiida.common import AttributeDict
import aiida.orm as orm
from aiida.plugins import DataFactory
from aiida.engine import CalcJob
from aiida_castep.data import get_pseudos_from_structure

from aiida_castep.common import (INPUT_LINKNAMES, OUTPUT_LINKNAMES)
from aiida_castep.calculations.helper import CastepHelper
from aiida_castep.calculations import CastepCalculation
from aiida_castep.calculations.tools import flat_input_param_validator
from .common import (UnexpectedCalculationFailure, register_error_handler,
                     ErrorHandlerReport)

Dict = DataFactory("dict")  # pylint: disable=invalid-name

# pylint: disable=no-member

__version__ = '0.0.1'


class CastepBaseWorkChain(WorkChain):
    """
    A basic workchain for generic CASTEP calculations.
    We try to handle erros such as walltime exceeded or SCF not converged
    """

    _context_pain_dicts = ('parameters', 'settings')
    _calculation_class = CastepCalculation
    _verbose = False

    def __init__(self, *args, **kwargs):
        super(CastepBaseWorkChain, self).__init__(*args, **kwargs)

        if self._calculation_class is None or not issubclass(
                self._calculation_class, CalcJob):
            raise ValueError(
                'no valid CalcJob class defined for _calculation_class attribute'
            )

    @classmethod
    def define(cls, spec):
        """Define this workchain"""
        super(CastepBaseWorkChain, cls).define(spec)

        # The inputs
        spec.input('max_iterations',
                   valid_type=orm.Int,
                   default=lambda: orm.Int(10),
                   serializer=to_aiida_type,
                   help='Maximum number of restarts')
        spec.input(
            'reuse_folder',
            valid_type=orm.RemoteData,
            help=
            'Use a remote folder as the parent folder. Useful for restarts.',
            required=False)
        spec.input(
            'continuation_folder',
            valid_type=orm.RemoteData,
            help=
            'Use a remote folder as the parent folder. Useful for restarts.',
            required=False)
        spec.input('pseudos_family',
                   valid_type=orm.Str,
                   serializer=to_aiida_type,
                   required=False,
                   help='Pseudopotential family to be used')
        spec.input('kpoints_spacing',
                   valid_type=orm.Float,
                   required=False,
                   serializer=to_aiida_type,
                   help="Kpoint spacing")
        spec.input('ensure_gamma_centering',
                   valid_type=orm.Bool,
                   serializer=to_aiida_type,
                   required=False,
                   help='Ensure the kpoint grid is gamma centred.')
        spec.input(
            'options',
            valid_type=orm.Dict,
            serializer=to_aiida_type,
            required=False,
            help=('Options specific to the workchain.'
                  'Avaliable options: queue_wallclock_limit, use_castep_bin'))
        spec.input(
            'calc_options',
            valid_type=orm.Dict,
            serializer=to_aiida_type,
            required=False,
            help="Options to be passed to calculations's metadata.options")
        spec.input(
            'clean_workdir',
            valid_type=orm.Bool,
            serializer=to_aiida_type,
            required=False,
            help=
            'Wether to clean the workdir of the calculations or not, the default is not clean.'
        )
        spec.expose_inputs(cls._calculation_class, namespace='calc')
        # Ensure this port is not required
        spec.input(
            'calc.metadata.options.resources',
            valid_type=dict,
            required=False,
            help=
            'Set the dictionary of resources to be used by the scheduler plugin, like the number of nodes, '
            'cpus etc. This dictionary is scheduler-plugin dependent. Look at the documentation of the '
            'scheduler for more details.')
        spec.input('calc.parameters',
                   valid_type=orm.Dict,
                   serializer=to_aiida_type,
                   help='Input parameters, flat format is allowed.',
                   validator=flat_input_param_validator)

        spec.output('output_array', valid_type=orm.ArrayData, required=False)
        spec.output('output_trajectory',
                    valid_type=orm.ArrayData,
                    required=False)
        spec.output('output_bands', valid_type=orm.BandsData, required=True)
        spec.output('output_structure',
                    valid_type=orm.StructureData,
                    required=False)
        spec.output('output_parameters', valid_type=orm.Dict, required=True)
        spec.output('remote_folder', valid_type=orm.RemoteData)

        # Define the exit codes
        spec.exit_code(900, 'ERROR_INVALID_INPUTS', 'Input validate is failed')
        spec.exit_code(
            201, 'ERROR_TOTAL_WALLCLOCK_EXCEEDED',
            'The maximum length of the wallclocks has been exceeded')
        spec.exit_code(200, 'ERROR_MAXIMUM_ITERATIONS_EXCEEDED',
                       'The maximum number of iterations has been exceeded')
        spec.exit_code(301, 'ERROR_CASTEP_FAILURE',
                       'CASTEP generated error files and is not recoverable')
        spec.exit_code(302, 'ERROR_SCF_FAILURE',
                       'Cannot reach SCF convergence despite restart efforts')
        spec.exit_code(
            400, 'USER_REQUESTED_STOP',
            'The stop flag has been put in the .param file to request termination of the calculation.'
        )
        spec.exit_code(1000, 'UNKOWN_ERROR', 'Error is not known')
        spec.exit_code(
            901, 'ERROR_ITERATION_RETURNED_NO_CALCULATION',
            'Completed one iteration but found not calculation returned')

        # Outline of the calculation
        spec.outline(
            cls.setup,
            cls.validate_inputs,
            if_(cls.should_dry_run)(
                cls.validate_dryrun_inputs,
                cls.run_dry_run,
                cls.inspect_dryrun,
            ),
            while_(cls.should_run_calculation)(
                cls.prepare_calculation,
                cls.run_calculation,
                cls.inspect_calculation,
            ),
            cls.results,
        )

    def setup(self):
        """Initialize internal variables"""
        self.ctx.calc_name = self._calculation_class.__name__
        self.ctx.stop_requested = None
        self.ctx.restart_calc = None
        self.ctx.restart_type = None
        self.ctx.is_finished = False
        self.ctx.unexpected_failure = False
        self.ctx.iteration = 0

    def validate_inputs(self):  # pylint: disable=too-many-branches, too-many-statements
        """Validate the inputs. Populate the inputs in the context
        This inputs is used as a staging area for the next calculation
        to be launched"""
        self.ctx.inputs = AttributeDict({
            'structure': self.inputs.calc.structure,
            'code': self.inputs.calc.code,
        })
        input_parameters = self.inputs.calc.parameters.get_dict()

        # Copy over the metadata
        self.ctx.inputs['metadata'] = AttributeDict(self.inputs.calc.metadata)

        # Ensure that the label is carried over to the calculation
        if not self.ctx.inputs['metadata'].get('label'):
            self.ctx.inputs['metadata']['label'] = self.inputs.metadata.get(
                'label', '')

        # Set the metadata.options for the underlying CastepCalculation
        # There are two ways to do this, one can either set it directly under the calc
        # namespace, or supply a dedicated Dict under 'calc_options'
        # The latter allows the get_builder_restart to work at the workchain level
        self.ctx.inputs['metadata']['options'] = AttributeDict(
            self.inputs.calc.metadata.options)
        # Check if there is any content
        if 'resources' in self.inputs.calc.metadata.options:
            self.report(
                'Direct input of calculations metadata is deprecated - please pass them with `calc_options` input port.'
            )
        if self.inputs.get('calc_options'):
            self.ctx.inputs['metadata']['options'].update(
                self.inputs['calc_options'])

        # propagate the settings to the inputs of the CalcJob
        if 'settings' in self.inputs.calc:
            self.ctx.inputs.settings = self.inputs.calc.settings.get_dict()
        else:
            self.ctx.inputs.settings = {}

        # Process the options in the input
        if 'options' in self.inputs:
            options = self.inputs.options.get_dict()
        else:
            options = {}
        self.ctx.options = options

        # Deal with the continuations
        use_bin = options.get('use_castep_bin', False)
        if use_bin:
            restart_suffix = 'castep_bin'
        else:
            restart_suffix = 'check'

        # Set the seed name
        seedname = self.inputs.calc.metadata.options.seedname

        # In case we are dealing with a plain inputs, extend any plain inputs
        helper = CastepHelper()
        param_dict = helper.check_dict(input_parameters)
        self.ctx.inputs['parameters'] = param_dict

        if self.inputs.get('continuation_folder'):
            self.ctx.inputs[INPUT_LINKNAMES[
                'parent_calc_folder']] = self.inputs.continuation_folder
            self.ctx.inputs.parameters['PARAM'][
                'continuation'] = 'parent/{}.{}'.format(
                    seedname, restart_suffix)
            self.ctx.inputs.parameters['PARAM'].pop('reuse', None)

        elif self.inputs.get('reuse_folder'):
            self.ctx.inputs[INPUT_LINKNAMES[
                'parent_calc_folder']] = self.inputs.reuse_folder
            self.ctx.inputs.parameters['PARAM'][
                'reuse'] = 'parent/{}.{}'.format(seedname, restart_suffix)
            self.ctx.inputs.parameters['PARAM'].pop('continuation', None)

        # Kpoints
        if self.inputs.calc.get('kpoints'):
            self.ctx.inputs.kpoints = self.inputs.calc.kpoints
        elif self.inputs.get('kpoints_spacing'):
            spacing = self.inputs.kpoints_spacing.value
            kpoints = orm.KpointsData()
            # Here the pbc settings of the structure is respected.
            # If a direction is not periodic it will have a single kpoint for the grid.
            # Care should be taken if a periodic structure incorrectly set to be
            # non-periodic! The kpoint along the non-periodic direction will be set to 1 by AiiDA's routine
            kpoints.set_cell_from_structure(self.inputs.calc.structure)
            kpoints.set_kpoints_mesh_from_density(np.pi * 2 * spacing)
            if not all(kpoints.pbc):
                self.report((
                    "WARNING: Non-periodic structure detected. Kpoint spacings are set to reflect the non-periodicity."
                    "This only makes sense for molecules-in-a-box input structures."
                    "Bear in mind that plane-wave DFT calculations are always periodic internally."
                ))

            # CASTEP uses the original MP grid definition such that only dimensions with odd number
            # of points are Gamma-centred.
            # Shifts of the grid is needed to ensure Gamma-centering needs to be enforced.
            mesh, _ = kpoints.get_kpoints_mesh()
            use_gamma = self.inputs.get('ensure_gamma_centering')
            if use_gamma is not None and use_gamma.value is True:
                castep_offset = _compute_castep_gam_offset(mesh)
                kpoints.set_kpoints_mesh(mesh, castep_offset)
                self.report("Offset used for Gamma-centering: {}".format(
                    castep_offset))

            self.report("Using kpoints: {}".format(kpoints.get_description()))
            self.ctx.inputs.kpoints = kpoints
        else:
            self.report('No valid kpoint input specified')
            return self.exit_codes.ERROR_INVALID_INPUTS
        # Pass extra kpoints
        exposed_inputs = self.exposed_inputs(CastepCalculation, 'calc')
        for key, value in exposed_inputs.items():
            if key.endswith('_kpoints'):
                self.ctx.inputs[key] = value

        # Validate the inputs related to pseudopotentials
        structure = self.inputs.calc.structure
        pseudos = self.inputs.calc.get('pseudos', None)
        pseudos_family = self.inputs.get('pseudos_family', None)
        if pseudos_family:
            pseudo_dict = get_pseudos_from_structure(structure,
                                                     pseudos_family.value)
            self.ctx.inputs.pseudos = pseudo_dict
        elif pseudos:
            self.ctx.inputs.pseudos = pseudos
        else:
            self.report('No valid pseudopotential input specified')
            return self.exit_codes.ERROR_INVALID_INPUTS
        return None

    def should_dry_run(self):  # pylint: disable=no-self-use
        """
        Do a dryrun to validate the inputs
        """
        return False  # We do not implement this for now
        #return 'do_dryrun' in self.inputs

    def validate_dryrun_inputs(self):
        pass

    def run_dry_run(self):
        pass

    def inspect_dryrun(self):
        pass

    def should_run_calculation(self):
        """Should we start the calculation (again)?"""
        return not self.ctx.is_finished and \
            self.ctx.iteration < self.inputs.max_iterations.value and \
            not self.ctx.stop_requested

    def prepare_calculation(self):
        """
        Prepare the inputs for the next calculation.
        """
        if self.ctx.restart_calc:
            # Different modes of restart
            if self.ctx.restart_mode == 'continuation':
                self.ctx.inputs.parameters['PARAM'][
                    'continuation'] = './parent/aiida.check'
                self.ctx.inputs.parameters['PARAM'].pop('reuse', None)
                self.ctx.inputs[INPUT_LINKNAMES[
                    'parent_calc_folder']] = self.ctx.restart_calc.outputs.remote_folder
            elif self.ctx.restart_type == 'reuse':
                self.ctx.inputs.parameters['PARAM'][
                    'reuse'] = './parent/aiida.check'
                self.ctx.inputs.parameters['PARAM'].pop('continuation', None)
                self.ctx.inputs[INPUT_LINKNAMES[
                    'parent_calc_folder']] = self.ctx.restart_calc.outputs.remote_folder
            else:
                self.ctx.inputs.parameters['PARAM'].pop('continuation', None)
                self.ctx.inputs.parameters['PARAM'].pop('reuse', None)
                self.ctx.inputs.pop(INPUT_LINKNAMES['parent_calc_folder'],
                                    None)

    def run_calculation(self):
        """
        Submit a new calculation, taking the input dictionary from the context at self.ctx.inputs
        """
        self.ctx.iteration += 1
        # Update the iterations in the inputs
        self.ctx.inputs.metadata['call_link_label'] = \
                                'iteration_{}'.format(self.ctx.iteration)

        try:
            unwrapped_inputs = AttributeDict(self.ctx.inputs)
        except AttributeError:
            raise ValueError(
                'no calculation input dictionary was defined in self.ctx.inputs'
            )

        inputs = self._prepare_process_inputs(unwrapped_inputs)
        calculation = self.submit(self._calculation_class, **inputs)

        self.report('launching {}<{}> iteration #{}'.format(
            self.ctx.calc_name, calculation.pk, self.ctx.iteration))

        return ToContext(calculations=append_(calculation))

    def inspect_calculation(self):
        """
        Analyse the results of the previous calculation, return/restart/abort if necessary
        """
        try:
            calculation = self.ctx.calculations[self.ctx.iteration - 1]
        except IndexError:
            self.report('iteration {} finished without returning a {}'.format(
                self.ctx.iteration, self.ctx.calc_name))
            return self.exit_codes.ERROR_ITERATION_RETURNED_NO_CALCULATION

        exit_code = None

        if calculation.is_finished_ok:
            self.report('{}<{}> completed successfully'.format(
                self.ctx.calc_name, calculation.pk))
            self.ctx.restart_calc = calculation
            self.ctx.is_finished = True

        # If the maximum number of iterations has been exceeded
        elif self.ctx.iteration >= self.inputs.max_iterations.value:
            self.report(
                'reached the maximumm number of iterations {}: last ran {}<{}>'
                .format(self.inputs.max_iterations.value, self.ctx.calc_name,
                        calculation.pk))
            exit_code = self.exit_codes.ERROR_MAXIMUM_ITERATIONS_EXCEEDED

        # Decide to retry or abort
        else:
            #exit_code = self._handle_calculation_sanity_checks(calculation)
            # Calculation failed, try to salvage it or handle any unexpected failures
            try:
                exit_code = self._handle_calculation_failure(calculation)
            except UnexpectedCalculationFailure as exception:
                exit_code = self._handle_unexpected_failure(
                    calculation, exception)
                self.ctx.unexpected_failure = True
        return exit_code

    def _prepare_process_inputs(self, inputs_dict):
        """Convert plain dictionary to Dict node"""
        out = AttributeDict(inputs_dict)
        for key in self._context_pain_dicts:
            if key in out:
                out[key] = Dict(dict=out[key])
        return out

    def _handle_calculation_failure(self, calculation):
        """Handle failure of calculation by refering to a range of handlers"""
        try:
            outputs = calculation.outputs[
                OUTPUT_LINKNAMES['results']].get_dict()
            _ = outputs['warnings']
            _ = outputs['parser_warnings']
        except (KeyError) as exception:
            raise UnexpectedCalculationFailure(exception)

        is_handled = False
        handler_report = None

        handlers = sorted(self._error_handlers,
                          key=lambda x: x.priority,
                          reverse=True)

        if not handlers:
            raise UnexpectedCalculationFailure(
                'no calculation error handlers were registered')

        for handler in handlers:
            handler_report = handler.method(self, calculation)

            if handler_report and handler_report.is_handled:
                is_handled = True

            if handler_report and handler_report.do_break:
                break

        # Raise error if not handled
        if not is_handled:
            raise UnexpectedCalculationFailure(
                'calculation failure was not handled')

        if handler_report:
            return handler_report.exit_code

        return None

    def results(self):
        """
        Attach the outputs specified in the output specification from the last completed calculation
        """
        self.report('workchain completed after {} iterations'.format(
            self.ctx.iteration))

        for name, port in self.spec().outputs.items():
            try:
                node = self.ctx.restart_calc.get_outgoing(
                    link_label_filter=name).one().node
            except ValueError:
                if port.required:
                    self.report(
                        "the process spec specifies the output '{}' as required but was not an output of {}<{}>"
                        .format(name, self.ctx.calc_name,
                                self.ctx.restart_calc.pk))
            else:
                self.out(name, node)
                if self._verbose:
                    self.report("attaching the node {}<{}> as '{}'".format(
                        node.__class__.__name__, node.pk, name))

    def _handle_unexpected_failure(self, calculation, exception=None):
        """
        The calculation has failed for an unknown reason and could not be handled.
        If the unexpected_failure flag is true, this is the second consecutive unexpected
        failure and we abort the workchain. Otherwise we restart once more.
        """
        if exception:
            self.report('{}'.format(exception))

        # if self.ctx.unexpected_failure:
        #     self.report(
        #         'failure of {}<{}> could not be handled for the second consecutive time'
        #         .format(self.ctx.calc_name, calculation.pk))
        #     return self.exit_codes.UNKOWN_ERROR

        # else:
        #     self.report(
        #         'failure of {}<{}> could not be handled, restarting once more'.
        #         format(self.ctx.calc_name, calculation.pk))

        self.report('failure of {}<{}> could not be handled'.format(
            self.ctx.calc_name, calculation.pk))
        return self.exit_codes.UNKOWN_ERROR

    @override
    def on_terminated(self):
        """
        Clean the working directories of all child calculation jobs if `clean_workdir=True` in the inputs and
        the calculation is finished without problem.
        """
        # Directly called the WorkChain method as this method replaces that of the BaseRestartWorkChain
        WorkChain.on_terminated(self)
        clean_workdir = self.inputs.get('clean_workdir', None)
        if clean_workdir is not None:
            clean_workdir = clean_workdir.value
        else:
            clean_workdir = False

        if clean_workdir is False:
            self.report('remote folders will not be cleaned')
            return

        if not self.ctx.is_finished:
            self.report(
                'remote folders will not be cleaned because the workchain finished with error.'
            )
            return

        cleaned_calcs = []

        for called_descendant in self.node.called_descendants:
            if isinstance(called_descendant, orm.CalcJobNode):
                try:
                    called_descendant.outputs.remote_folder._clean()  # pylint: disable=protected-access
                    cleaned_calcs.append(str(called_descendant.pk))
                except (IOError, OSError, KeyError):
                    pass

        if cleaned_calcs:
            self.report(
                f"cleaned remote folders of calculations: {' '.join(cleaned_calcs)}"
            )


@register_error_handler(CastepBaseWorkChain, 900)
def _handle_scf_failure(self, calculation):
    """Handle case when SCF failed"""

    if 'ERROR_SCF_NOT_CONVERGED' in calculation.res.warnings:
        self.ctx.restart_calc = calculation
        self.ctx.restart_mode = None
        dot_castep = _get_castep_output_file(calculation)
        for idx, line in enumerate(dot_castep[:-50:-1]):
            model_match = re.match(r'Writing model to \w+\.(\w+)', line)
            # If the writing model is at the last line there is a good
            # Chance that it was interrupted
            if model_match and idx > 0 and model_match.group(1) == 'check':
                self.ctx.restart_mode = 'continuation'
                break

        param = self.ctx.inputs.parameters['PARAM']
        # Increase the SCF limit by 50%
        scf_limit = self.ctx.inputs.parameters['PARAM'].get(
            'max_scf_cycles', 30)
        scf_limit = int(scf_limit * 1.5)
        self.ctx.inputs.parameters['PARAM']['max_scf_cycles'] = scf_limit
        self.report('Increased SCF limit to: {}'.format(scf_limit))

        if param.get('metals_method') == 'edft' or param.get(
                'elec_method') == 'edft':
            return ErrorHandlerReport(True, True)

        # Reduce the mix charge amp
        mix_charge_amp = self.ctx.inputs.parameters['PARAM'].get(
            'mix_charge_amp', 0.8)
        if mix_charge_amp > 0.2:
            mix_charge_amp -= 0.1
        self.ctx.inputs.parameters['PARAM']['mix_charge_amp'] = mix_charge_amp

        # Reuce mix spin amp
        mix_spin_amp = self.ctx.inputs.parameters['PARAM'].get(
            'mix_spin_amp', 2)
        if mix_spin_amp > 0.5:
            mix_spin_amp -= 0.3
        self.ctx.inputs.parameters['PARAM']['mix_spin_amp'] = mix_spin_amp

        self.report(
            'Adjusted mix_charge_amp:{:.2f}, mix_spin_amp:{:.2f}'.format(
                mix_charge_amp, mix_spin_amp))

        return ErrorHandlerReport(True, True)
    return None


@register_error_handler(CastepBaseWorkChain, 500)
def _handle_walltime_limit(self, calculation):
    """Handle case when the walltime limit has reached"""

    if 'ERROR_TIMELIMIT_REACHED' in calculation.res.warnings:
        self.ctx.restart_calc = calculation
        self.ctx.restart_mode = None
        dot_castep = _get_castep_output_file(calculation)
        for nline, line in enumerate(dot_castep[::-1]):
            model_match = re.match(r'Writing model to \w+\.(\w+)', line)
            # If the writing model is at the last line there is a good
            # Chance that it was interrupted
            if model_match and nline > 0 and model_match.group(1) == 'check':
                self.ctx.restart_mode = 'continuation'
                self.report(
                    'dot castep indicate model has been written, trying continuation.'
                )
                break

        # If we are do not continue the run, try increase the wallclock

        if self.ctx.restart_mode is None:

            wclock = self.inputs.calc.metadata.options.get(
                'max_wallclock_seconds', 3600)
            wclock_limit = self.ctx.options.get('queue_wallclock_limit', None)
            if wclock_limit is None:
                pass
            elif wclock == wclock_limit:
                self.report('Cannot furhter increase the wallclock limit')
                return ErrorHandlerReport(False, True)
            elif wclock * 1.5 < wclock_limit:
                self.inputs.calc.metadata.options[
                    'max_wallclock_seconds'] = int(wclock * 1.5)
            else:
                self.inputs.calc.metadata.options[
                    'max_wallclock_seconds'] = int(wclock_limit)

            self.report('Adjusted the wallclock limit to {}'.format(
                self.inputs.calc.metadata.options['max_wallclock_seconds']))
            # Temporary fix - wait for next relax of aiida that allows customisation
            # of the valid cache for Process classes
            calculation.clear_hash()
            self.report('Cleared the hash of the failed calculation.')

        return ErrorHandlerReport(True, False)
    return None


@register_error_handler(CastepBaseWorkChain, 600)
def _handle_no_empty_bands(self, calculation):
    """Handle the case where there is no empty bands"""
    has_error = False
    for warning in calculation.res.warnings:
        if "At least one kpoint has no empty bands" in warning:
            has_error = True
            break
    if has_error is False:
        return None

    # Need to handle this error
    dot_castep = _get_castep_output_file(calculation)
    nextra_bands = None
    # Scan for the warning line and record the suggested nextra bands
    for line in dot_castep:
        match = re.search(r"Recommend using nextra_bands of (\d+) to (\d+)",
                          line)
        if match:
            nextra_bands = int(match.group(2))
    param = self.ctx.inputs.parameters

    # No warning found? Increase the extra bands by 50%
    if nextra_bands is None:
        perc = param['PARAM'].get('perc_extra_bands')
        if perc is None:
            param['PARAM']['perc_extra_bands'] = 30
        else:
            perc *= 1.5
            param['PARAM']['perc_extra_bands'] = perc
        param['PARAM'].pop('nextra_bands', None)
        self.report(f'Increased <perc_extra_bands> to {perc}.')
    else:
        # Apply the suggested bands
        param['PARAM']['nextra_bands'] = nextra_bands
        param['PARAM'].pop('perc_extra_bands', None)
        self.report(f'Increased <nextra_bands> to {nextra_bands}.')

    return ErrorHandlerReport(True, False)


@register_error_handler(CastepBaseWorkChain, 10000)
def _handle_stop_by_request(self, calculation):
    """Handle the case when the stop flag is raised by the user"""

    if 'ERROR_STOP_REQUESTED' in calculation.res.warnings:
        self.report('Stop is requested by user. Aborting the WorkChain.')
        self.ctx.restart_calc = calculation
        self.ctx.stop_requested = True
        calculation.clear_hash()
        self.report('Cleared the hash of the stopped calculation.')
        return ErrorHandlerReport(True, True,
                                  self.exit_codes.USER_REQUESTED_STOP)
    return None


def _get_castep_output_file(calculation):
    """Return a list of the lines in the retrieved dot castep file"""
    fname = calculation.get_option('output_filename')
    fcontent = calculation.outputs.retrieved.get_object_content(fname)
    return fcontent.split('\n')


def _compute_castep_gam_offset(grids):
    """
    Compute the offset need to get gamma-centred grids for a given grid specification

    Note that the offset are expressed in the reciprocal cell units.
    """
    shifts = []
    for grid in grids:
        if grid % 2 == 0:
            shifts.append(-1 / grid / 2)
        else:
            shifts.append(0.)
    return shifts

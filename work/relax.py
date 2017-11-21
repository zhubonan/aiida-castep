"""
WorkChain for doing an relaxation, try to handle erros including:
run not finished
geom not converged within given cycle
scf iteration reached maximum

and possible adapt from it
"""
from copy import deepcopy
import time

from aiida.orm import Code
from aiida.orm.data.base import Str, Float, Bool
from aiida.orm.data.folder import FolderData
from aiida.orm.data.remote import RemoteData
from aiida.orm.data.parameter import ParameterData
from aiida.orm.data.structure import StructureData
from aiida.orm.data.array.kpoints import KpointsData
from aiida.orm.data.singlefile import SinglefileData
from aiida.orm.group import Group
from aiida.orm.utils import WorkflowFactory
from aiida.common.exceptions import AiidaException, NotExistent
from aiida.common.datastructures import calc_states
from aiida.work.run import submit
from aiida.work.workchain import WorkChain, ToContext, if_, while_, append_
from aiida.orm.utils import CalculationFactory
from aiida.common.datastructures import calc_states

CastepCalculation = CalculationFactory('castep.castep')


class UnexpectedFailure(RuntimeError):
    pass

class CastepRelaxWorkChain(WorkChain):
    """
    Workchain to do geometryoptimisation with CASTEP
    Try to restart calculations unti convergence is reached
    """
    SUBMISSION_RETRY_SECONDS = 60

    @classmethod
    def define(cls, spec):
        super(CastepRelaxWorkChain, cls).define(spec)
        spec.input('structure', valid_type=StructureData)
        spec.input('parameters', valid_type=ParameterData)
        spec.input('settings', valid_type=ParameterData)
        spec.input('pseudo_family', valid_type=Str, required=False)
        spec.input_group('pseudos', valid_type=Str, required=False)
        spec.input('kpoints', valid_type=KpointsData)
        spec.input('options', valid_type=ParameterData)
        spec.input('final_restart', valid_type=Bool)
        spec.input('geom_method', valid_type=Str, default=Str('LBFGS'))
        spec.outline(
            cls.intialise,
            cls.validate_inputs,
            while_(cls.show_run)(
                cls.relax,
                cls.check_relax,
            ),
            if_(cls.should_do_final_restart)(
                cls.run_final_restart,
            ),
            cls.process_results,
            )
        spec.output('output_structure', valid_type=StructureData)
        spec.output('output_parameters', valid_type=ParameterData)
        spec.output('remote_folder', valid_type=RemoteData)
        spec.output('retrieved', valid_type=FolderData)

    def initialise(self):
        """
        Initialise the workchain. Process inputs, and save it to ctx
        """
        self.ctx.current_parent_folder = None
        self.ctx.is_converged = False
        self.ctx.iteration = 0

        self.ctx.inputs = {
            'code': self.inputs.code,
            'structure': self.inputs.structure,
            'parameters': self.inputs.parameters.get_dict(),
            'settings': self.inputs.settings,
            'kpoints': self.inputs.kpoints,
            '_options': self.inputs.options
        }

        # Check if a pseudo family has been passed

        if self.inputs.pseudo_family:
            self.ctx.inputs["pseudo_family"] = self.input.pseudo_family
        elif self.inputs.pseudos:
            self.ctx.inputs['pseudos'] = self.inputs.pseudos
        else:
            self.abort_nowait('No valida pseudo data passed. Both pseudo_family and pseudos are not specified')

        # Check if task:geometryoptimisation is passed

        # OK this should not happen but I fix them nevertheless here
        if 'PARAM' not in self.ctx.inputs['parameters']:
            self.ctx.inputs['PARAM'] = {}
        if 'CELL' not in self.ctx.inputs['parameters']:
            self.ctx.inputs['CELL'] = {}

        param_dict = self.ctx.inputs['parameters']['PARAM']
        if 'task' not in param_dict:
            param_dict['task'] = 'geometryoptimisation'
        elif param_dict['task'] != 'geometryoptimisation' \
                and param_dict['task'] != 'geometryoptimization':
            self.abort_nowait('Wrong task value passed {}'.format(param_dict['task']))

        # Add options to the context
        if 'options' in self.inputs:
            self.ctx.inputs['options'] = self.inputs.options

        # Add correct geom method
        geom_method = param_dict.get('geom_method', None)
        if geom_method is None:
            param_dict['geom_method'] = self.inputs.geom_method.value
        elif geom_method != self.inputs.geom_method:
            self.abort_nowait('Inconsistent geom_method passed. In PARAM it is {} but the input is {}'.format(geom_method, self.inputs.geom_method))
        return

    def vaildate_inputs(self):
        """
        A more detailed check
        """
        from aiida_castep.calculations.helper import CastepHelper
        helper = CastepHelper()
        # Automatic fix
        out = helper.check_dict(self.ctx.inputs['parameters'], auto_fix=True)
        self.ctx.inputs['parameters'] = out
        return

    def should_run_relax(self):
        return not self.is_converged

    def should_run_final_restart(self):
        return self.inputs.final_restart

    def run_relax(self):
        """
        Run a CastepCalculation
        """
        self.ctx.iteration += 1

        inputs = deepcopy(self.ctx.inputs)

        if self.ctx.restart_calc:
            # We need to restart from a provious calculation
            inputs['parameters']['PARAM']['continuation'] = \
                CastepCalculation.get_restart_file_relative_path(
                    self.ctx.inputs['parameters'], False)
            inputs['parent_folder'] = self.ctx.restart_calc.out.remote_folder

        process = CastepCalculation.process()
        calc = submit(process, **inputs)

        self.report('Launching CastepCalculation <{}> iteraiton #{}'.format(calc.pid, self.ctx.iteraiton))

        return self.to_context(calcs=append_(calc))

    def check_relax(self):
        """
        Check ouput of previous relaxation.
        """

        try:
            calc = self.ctx.calcs[-1]

        except IndexError:
            self.abort_nowait('Seems the initial iteration had problems. Not calculation had been returned')
            return

        # Possible states that we can fix
        acceptable_states = [calc_states.FINISHED, calc_states.FAILD,
                             calc_states.SUBMISSIONFAILED ]

        # If the calculation is finished
        # What the difference between using get_state() == FINISHED?
        calc_state = calc.get_state()
        if calc.has_finished_ok():
            self.report('Geometry optimisation succesful after {} WorkChain iterations'.format(self.ctx.iteration))
            self.ctx.restart_calc = calc
            self.ctx.is_converged = True

        elif self.ctx.iteration >= self.ctx.max_iterations:
            self.report('Has reached max iterations {}'.format(
                self.ctx.max_iterations))
            self.abort_nowait('Last ran CastepCalculation<{}>'.format(calc.pk))

        elif calc_state not in acceptable_states:
            self.abort_nowait('Last ran CastepCalculation <{}> state {} cannot be handled'.format(calc.pk, calc.get_state()))

        elif calc_state in  [calc_states.SUBMISSIONFAILED]:
            self._submission_failure_handler(calc)
            self.ctx.submission_failure = True

        elif calc_state in [calc_states.FAILED]:
            self.ctx.submission_failure = False

            try:
                handler_out = self._failure_handler(calc)
            except UnexpectedFailure as e:
                self.abort_nowait(e.args)

            if handler_out == "CAN RESTART":
                return
            else:
                self.abort_nowait("Abort due to failure at iteration {} with CastepCalculation <{}> Message: {}".format(self.ctx.iteration, calc.pk, handler_out))

    def should_do_final_restart(self):
        return False

    def run_final_restart(self):
        pass

    def process_results(self):
        last_calc = self.ctx.calcs[-1]
        output_dict = last_calc.get_outputs_dict()
        self.out('output_structure', output_dict["output_structure"])
        self.out('output_parameters', output_dict["output_structure"])
        self.out('remote_folder', output_dict["remote_folder"])
        self.out('retrieved', output_dict["retrieved"])

    def _submission_failure_handler(self, calc):
        """We try again in 60 seconds"""
        if self.ctx.submission_failure:
            self.abort_nowait('Submission for CastepCalculation <{}> failed twice'.format(calc.pk))
        else:
            self.report('Submission for CastepCalculation <{}> failed. Sleep for {} seconds and try again'.format(calc.pk, self.SUBMISSION_RETRY_SECONDS))
            time.sleep(self.SUBMISSION_RETRY_SECONDS)

    def _failure_handler(self, calc):
        """
        Handle a failed calculation
        """
        try:
            output_parameters = calc.get_outputs_dict()["output_parameters"]
        except KeyError:
            raise UnexpectedFailure("No ouput ParameterData find")
        try:
            warnings = output_parameters["warnings"]
        except KeyError:
            raise UnexpectedFailure("Cannot find warnings")

        if any(["SCF" in w for w in warnings]):
            return "SCF CONVERGE FAILURE"

        if  any(["end of execusion" in w for w in warnings]):
            try:
                output_array = calc.get_outputs_dict()["output_array"]
                total_energy = output_array.get_array("total_energy")
            except KeyError:
                return "FIRST SCF UNFINISHED"
            else:
                self.report("Run did not finished after {} iterations".format(len(total_energy)))
                return "CAN RESTART"









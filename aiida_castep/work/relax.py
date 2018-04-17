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
from aiida.orm.data.base import Str, Float, Bool, Int
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
from aiida.work.workchain import WorkChain, if_, while_, append_
from aiida.orm.utils import CalculationFactory

from aiida_castep.parsers.raw_parser import (END_NOT_FOUND_MESSAGE,
 GEOM_FAILURE_MESSAGE, SCF_FAILURE_MESSAGE)
from aiida_castep.data import get_pseudos_from_structure

CastepCalculation = CalculationFactory('castep.castep')


class UnexpectedFailure(RuntimeError):
    pass

class CastepRelaxWorkChain(WorkChain):
    """
    Workchain to do geometryoptimisation with CASTEP
    Try to restart calculations unti convergence is reached
    """
    SUBMISSION_RETRY_SECONDS = 60
    MAX_ITERATIONS = 5

    @classmethod
    def define(cls, spec):
        super(CastepRelaxWorkChain, cls).define(spec)
        spec.input('code', valid_type=Code)
        spec.input('structure', valid_type=StructureData)
        spec.input('parameters', valid_type=ParameterData)
        spec.input('settings', valid_type=ParameterData, required=False)
        spec.input('pseudo_family', valid_type=Str, required=False)
        spec.input_group('pseudos', valid_type=Str, required=False)
        spec.input('kpoints', valid_type=KpointsData)
        spec.input('options', valid_type=ParameterData, required=False)
        spec.input('final_restart', valid_type=Bool, required=False, default=Bool(False))
        spec.input('geom_method', valid_type=Str, default=Str('LBFGS'))
        spec.outline(
            cls.initialise,
            cls.validate_inputs,
            while_(cls.should_run_relax)(
                cls.run_relax,
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
        self.ctx.max_iterations = self.MAX_ITERATIONS
        self.ctx.restart_calc = None
        self.ctx.submission_failure = None

        self.ctx.inputs = {
            'code': self.inputs.code,
            'structure': self.inputs.structure,
            'parameters': self.inputs.parameters.get_dict(),
            'kpoints': self.inputs.kpoints,
            '_options': self.inputs.options.get_dict()
        }

        if "settings" in self.inputs:
            self.ctx.inputs.update(settings=self.inputs.settings)

        # Check if a pseudo family has been passed

        if self.inputs.pseudo_family:
            self.ctx.inputs['pseudo'] = get_pseudos_from_structure(
                self.inputs.structure, self.inputs.pseudo_family.value
                )

        elif self.inputs.pseudos:
            self.ctx.inputs['pseudo'] = self.inputs.pseudos
        else:
            self.abort_nowait('No valida pseudo data passed. Both pseudo_family and pseudos are not specified')
            return

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
            return


        # Add correct geom method
        geom_method = param_dict.get('geom_method', None)
        if geom_method is None:
            param_dict['geom_method'] = self.inputs.geom_method.value
        elif geom_method != self.inputs.geom_method:
            self.abort_nowait('Inconsistent geom_method passed. In PARAM it is {} but the input is {}'.format(geom_method, self.inputs.geom_method))
            return

        return

    def validate_inputs(self):
        """
        A more detailed check
        """
        from aiida_castep.calculations.helper import CastepHelper
        helper = CastepHelper()
        # Automatic fix
        out = helper.check_dict(self.ctx.inputs['parameters'], auto_fix=True)
        if out != self.ctx.inputs['parameters']:
            self.report("Auto fixed input parameters. New parameters {}".format(out))

        self.ctx.inputs['parameters'] = out

        # Check if write_checkpoint is disabled
        check_point = out['PARAM'].get("write_checkpoint")
        if check_point:
            if check_point == "none":
                self.report("Warning: checkpointing disabled!")

        opt_strategy  = out['PARAM'].get('opt_strategy')

        if not opt_strategy:
            out['PARAM']['opt_strategy'] = "speed"
            self.report("Automatically set opt_strategy : speed.")

        # Converge back into ParameterData
        # Make a new ParameterData node for calculation

        return

    def should_run_relax(self):
        return not self.ctx.is_converged

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

        # Finall make a ParameterData from the inputs
        inputs["parameters"] = ParameterData(dict=inputs["parameters"])
        process = CastepCalculation.process()
        calc = submit(process, **inputs)

        self.report('Launching CastepCalculation <{}> iteration #{}'.format(calc.pid, self.ctx.iteration))


        return self.to_context(calcs=append_(calc))

    def check_relax(self):
        """
        Check ouput of previous relaxation.
        """

        try:
            calc = self.ctx.calcs[-1]

        except IndexError:
            self.abort_nowait('Seems the initial iteration had problems. No calculation had been returned')
            return

        # Possible states that we can fix
        acceptable_states = [calc_states.FINISHED, calc_states.FAILED,
                             calc_states.SUBMISSIONFAILED ]

        # If the calculation is finished
        # What the difference between using get_state() == FINISHED?
        calc_state = calc.get_state()
        if calc.has_finished_ok():
            self.report('Geometry optimisation succesful after {} WorkChain iterations'.format(self.ctx.iteration))
            self.ctx.is_converged = True

        elif self.ctx.iteration >= self.ctx.max_iterations:
            self.report('Has reached max iterations {}'.format(
                self.ctx.max_iterations))
            self.abort_nowait('Last ran CastepCalculation<{}>'.format(calc.pk))
            return

        elif calc_state not in acceptable_states:
            self.abort_nowait('Last ran CastepCalculation <{}> state {} cannot be handled'.format(calc.pk, calc.get_state()))
            return

        elif calc_state in  [calc_states.SUBMISSIONFAILED]:
            self._submission_failure_handler(calc)
            self.ctx.submission_failure = True

        elif calc_state in [calc_states.FAILED]:
            self.ctx.submission_failure = False

            try:
                handler_out = self._failure_handler(calc)
            except UnexpectedFailure as e:
                self.abort_nowait(e.args)
                return

            if handler_out == "CAN RESTART":
                # Use the last calculation to restart
                self.ctx.restart_calc = calc
                return
            else:
                self.abort_nowait("Abort due to failure at iteration {} with CastepCalculation <{}> Message: {}".format(self.ctx.iteration, calc.pk, handler_out))
                return

    def should_do_final_restart(self):
        return False

    def run_final_restart(self):
        pass

    def process_results(self):
        """
        Process the outputs
        """
        last_calc = self.ctx.calcs[-1]
        output_dict = last_calc.get_outputs_dict()
        self.out('output_structure', output_dict["output_structure"])
        self.out('output_parameters', output_dict["output_parameters"])
        self.out('remote_folder', output_dict["remote_folder"])
        self.out('retrieved', output_dict["retrieved"])

    def _submission_failure_handler(self, calc):
        """We try again in 60 seconds"""
        if self.ctx.submission_failure:
            self.abort_nowait('Submission for CastepCalculation <{}> failed twice'.format(calc.pk))
            return
        else:
            self.report('Submission for CastepCalculation <{}> failed. Sleep for {} seconds and try again'.format(calc.pk, self.SUBMISSION_RETRY_SECONDS))
            time.sleep(self.SUBMISSION_RETRY_SECONDS)

    def _failure_handler(self, calc):
        """
        Handle a failed calculation
        """
        try:
            output_parameters = calc.get_outputs_dict()["output_parameters"].get_dict()
        except KeyError:
            raise UnexpectedFailure("No ouput ParameterData find")
        try:
            warnings = output_parameters["warnings"]
        except KeyError:
            raise UnexpectedFailure("Cannot find warnings")

        if any([SCF_FAILURE_MESSAGE in w for w in warnings]):

            return "SCF CONVERGE FAILURE"

        if any([GEOM_FAILURE_MESSAGE in w for w in warnings]):
            self.report("Run finished but geom convergence not reached")
            return "CAN RESTART"

        # Calculation gets killed
        if  any([END_NOT_FOUND_MESSAGE in w for w in warnings]):
            try:
                output_trajectory = calc.get_outputs_dict()["output_trajectory"]
                total_energy = output_trajectory.get_array("total_energy")
            except KeyError:
                self.report("First SCF not finished")
                return "FIRST SCF UNFINISHED"
            else:
                # Check if we have valid energies
                if len(total_energy) > 0:
                    self.report("Run did not finished after {} iterations".format(len(total_energy)))
                    return "CAN RESTART"
                else:
                    return "FIRST SCF UNFINISHED"
        else:
            return "CANNOT FIND VALID WARNINGS"


class TwoStepRelax(WorkChain):
    """
    Two step relaxation. First relax with variable cell, then do a fixed cell
    geometry optimisation. Even if the calcualtion has not convered
    """

    @classmethod
    def define(cls, spec):
        super(TwoStepRelax, cls).define(spec)
        spec.input('code', valid_type=Code)
        spec.input('structure', valid_type=StructureData)
        spec.input('parameters', valid_type=ParameterData)
        spec.input('settings', valid_type=ParameterData, required=False)
        spec.input('pseudo_family', valid_type=Str, required=False)
        spec.input_group('pseudos', valid_type=Str, required=False)
        spec.input('kpoints', valid_type=KpointsData)
        spec.input('options', valid_type=ParameterData, required=False)
        spec.input('var_cell_geom_method', valid_type=Str, default=Str('TPSD'))
        spec.input('var_cell_geom_iter', valid_type=Int, default=Int(20))
        spec.input('fix_cell_geom_method', valid_type=Str, default=Str('TPSD'))
        spec.outline(
            cls.validate_inputs,
            cls.relax,
            cls.swap_param,
            cls.relax,
            cls.process_results,
            )
        spec.output('output_structure', valid_type=StructureData)
        spec.output('output_parameters', valid_type=ParameterData)
        spec.output('remote_folder', valid_type=RemoteData)
        spec.output('retrieved', valid_type=FolderData)

    def validate_inputs(self):

        # ctx.inputs is a template to for castepcalculation processes
        options = self.inputs.options.get_dict()
        self.ctx.inputs = {
            'code': self.inputs.code,
            'structure': self.inputs.structure,
            'kpoints': self.inputs.kpoints,
            '_options': options,
            '_label': options.pop("_calc_label", None),
            '_description': options.pop("_calc_description", None),
        }
        if "settings" in self.inputs:
            self.ctx.inputs["settings"] = self.inputs.settings

        # Setup pseudo potentials
        if self.inputs.pseudo_family:
            self.ctx.inputs['pseudo'] = get_pseudos_from_structure(
                self.inputs.structure, self.inputs.pseudo_family.value
                )
        elif self.inputs.pseudos:
            self.ctx.inputs['pseudo'] = self.inputs.pseudos
        else:
            self.abort_nowait('No valida pseudo data passed. Both pseudo_family and pseudos are not specified')
            return

        # Check possible mistake in the parameterse dictionary
        v_param_dict = self.inputs.parameters.get_dict()
        v_param_dict["CELL"].pop("fix_all_cell", None)
        v_param_dict["PARAM"]["geom_method"] = str(self.inputs.var_cell_geom_method)
        v_param_dict["PARAM"]["geom_max_iter"] = int(self.inputs.var_cell_geom_iter)
        v_param_dict = CastepCalculation.check_castep_input(v_param_dict, auto_fix=True)

        f_param_dict = self.inputs.parameters.get_dict()
        f_param_dict["CELL"]["fix_all_cell"] = True
        f_param_dict["CELL"].pop("cell_constraints", None)
        f_param_dict["PARAM"]["geom_method"] = str(self.inputs.fix_cell_geom_method)
        f_param_dict = CastepCalculation.check_castep_input(f_param_dict,
            auto_fix=True)

        self.ctx.inputs["parameters"] = v_param_dict

        # Save the parameters for fixed cell for later
        self.ctx.fix_cell_param = f_param_dict

        self.report("Inputs validated and processed")

    def relax(self):
        """
        Relax with varable cell
        """
        inputs = dict(self.ctx.inputs)
        inputs["parameters"] = ParameterData(
            dict=self.ctx.inputs["parameters"])

        process = CastepCalculation.process()
        calc = submit(process, **inputs)
        self.report('Launching CastepCalculation <{}>'.format(calc.pid))

        return self.to_context(calcs=append_(calc))

    def swap_param(self):

        # Swap the parameters for fixed cell optimsiation
        v_calc = self.ctx.calcs[-1]
        self.report("Varcell finished. Swapping parameters")
        reuse_name = CastepCalculation.get_restart_file_relative_path(self.ctx.inputs["parameters"], False)

        # Reuse the checkfiles
        self.ctx.inputs["parameters"] = self.ctx.fix_cell_param
        self.ctx.inputs["parameters"]["PARAM"]["reuse"] = reuse_name
        self.ctx.inputs["parent_folder"] = self.ctx.calcs[-1].out.remote_folder
        self.ctx.inputs["structure"] = v_calc.out.output_structure

        self.report("Fixed cell parameters swapped. Continue with fixed cell relaxation.")

    def process_results(self):
        """
        Process the outputs
        """
        last_calc = self.ctx.calcs[-1]
        output_dict = last_calc.get_outputs_dict()
        self.out('output_structure', output_dict.get("output_structure"))
        self.out('output_parameters', output_dict.get("output_parameters"))
        self.out('output_trajectory', output_dict.get("output_trajectory"))
        self.out('remote_folder', output_dict.get("remote_folder"))
        self.out('retrieved', output_dict.get("retrieved"))

        self.report("Workchain finished.")

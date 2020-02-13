"""
Tools for calculations
"""
from __future__ import absolute_import
from __future__ import print_function
import six
import warnings

from aiida.tools import CalculationTools
from aiida.common import InputValidationError
from aiida.orm import CalcJobNode, Dict
from aiida.common.links import LinkType
from aiida.plugins import DataFactory
from aiida.engine import CalcJob, ProcessBuilder

from aiida_castep.common import INPUT_LINKNAMES, OUTPUT_LINKNAMES
from six.moves import zip

__all__ = [
    'CastepCalcTools', 'create_restart', 'castep_input_summary',
    'update_parameters', 'use_pseudos_from_family'
]


class CastepCalcTools(CalculationTools):
    def get_castep_input_summary(self):
        return castep_input_summary(self._node)

    def compare_with(self, the_other_calc, reverse=False):
        """
        Compare with another calculation
        Look for difference in get_castep_input_summary functions
        :params node: pk or uuid or node
        :params reverse: reverse the comparison, by default this node
        is the "new" and the one compared with is "old".
        """
        if isinstance(the_other_calc, (int, six.string_types)):
            from aiida.orm import load_node
            calc2 = load_node(the_other_calc)
        else:
            calc2 = the_other_calc

        from deepdiff import DeepDiff
        this_param = castep_input_summary(self._node)
        other_param = castep_input_summary(calc2)
        if reverse is True:
            res = DeepDiff(this_param, other_param)
        else:
            res = DeepDiff(other_param, this_param)

        return res

    def create_restart(self,
                       ignore_state=False,
                       restart_mode='restart',
                       use_output_structure=False,
                       **kwargs):
        if self._node.exit_status != 0 and not ignore_state:
            raise RuntimeError(
                'exit_status is not 0. Set ignore_state to ignore')

        builder = create_restart(self._node.get_builder_restart(),
                                 calcjob=self._node,
                                 restart_mode=restart_mode,
                                 **kwargs)

        # Carry over the label
        builder.metadata.label = self._node.label

        if use_output_structure is True:
            builder[
                INPUT_LINKNAMES['structure']] = self._node.outputs.__getattr__(
                    OUTPUT_LINKNAMES['structure'])

        if restart_mode == 'continuation' or kwargs.get('reuse'):
            builder[INPUT_LINKNAMES[
                'parent_calc_folder']] = self._node.outputs.__getattr__(
                    'remote_folder')

        return builder


def use_pseudos_from_family(builder, family_name):
    """
    Set the pseudos port namespace for a builder using pseudo family name
    :note: The structure must already be set in the builder.

    :param builder: ProcessBuilder instance to be processed, it must have a structure
    :param family_name: the name of the group containing the pseudos
    :returns: The same builder with the pseudopotential set
    """
    from collections import defaultdict
    from aiida_castep.data import get_pseudos_from_structure

    # A dict {kind_name: pseudo_object}
    # But we want to run with use_pseudo(pseudo, kinds)

    structure = builder.get(INPUT_LINKNAMES['structure'], None)
    if structure is None:
        raise RuntimeError('The builder must have a StructureData')
    kind_pseudo_dict = get_pseudos_from_structure(structure, family_name)
    for kind, pseudo in kind_pseudo_dict.items():
        builder.pseudos.__setattr__(kind, pseudo)
    return builder


def castep_input_summary(calc):
    """
    Convenient fuction for getting a summary of the
    input of this calculation

    :param calc: A CalcJobNode or ProcessBuilder or a nested input dictionary
    :returns: A dictionary
    """

    out_info = {}
    # Check what is passed
    if isinstance(calc, CalcJobNode):
        inp_dict = calc.get_incoming(link_type=(LinkType.INPUT_CALC,
                                                LinkType.INPUT_WORK)).nested()
        options = calc.get_options()
        metadata = {}  # Metadata is empty when Node is passed
        is_node = True
    elif isinstance(calc, ProcessBuilder):
        # Case of builder
        inp_dict = calc._data
        metadata = calc.metadata._data
        options = calc.metadata.get('options', {})
        is_node = False
    elif isinstance(calc, dict):
        # Case of a input dictionary
        inp_dict = calc
        metadata = calc.get('metadata', {})
        options = metadata.get('options', {})
        is_node = False

    def get_node(label):
        """Get node from input dictionary"""
        return inp_dict.get(INPUT_LINKNAMES[label])

    in_param = get_node('parameters')
    in_kpn = get_node('kpoints')
    in_settings = get_node('settings')
    in_structure = get_node('structure')
    in_code = inp_dict.get('code')
    in_remote = get_node('parent_calc_folder')
    pseudos = inp_dict.get('pseudos')

    param_dict = in_param.get_dict()
    out_info.update(param_dict)

    out_info["kpoints"] = in_kpn.get_description()
    out_info["structure"] = {
        "formula": in_structure.get_formula(),
        "cell": in_structure.cell,
        "label": in_structure.label
    }

    out_info["code"] = in_code
    out_info["computer"] = calc.computer if is_node else in_code.computer
    out_info["resources"] = options.get('resources')
    out_info["custom_scheduler_commands"] = options.get(
        'custom_scheduler_commands')
    out_info["qos"] = options.get('qos')
    out_info["account"] = options.get('account')
    out_info["wallclock"] = options.get('max_wallclock_seconds')
    out_info["label"] = calc.label if is_node else metadata.get('label')
    out_info["description"] = calc.description if is_node else metadata.get(
        'description')

    # Show the parent calculation whose RemoteData is linked to the node
    if in_remote is not None:
        input_calc = [
            n.node for n in in_remote.get_incoming(link_type=LinkType.CREATE)
        ]
        assert len(
            input_calc
        ) < 2, "More than one JobCalculation found, something seriously wrong"
        if input_calc:
            input_calc = input_calc[0]
            out_info["parent_calc"] = {
                "pk": input_calc.pk,
                "label": input_calc.label
            }
        out_info["parent_calc_folder"] = in_remote

    if in_settings is not None:
        out_info["settings"] = in_settings.get_dict()
    out_info["pseudos"] = pseudos
    return out_info


def update_parameters(inputs, force=False, delete=None, **kwargs):
    """
    Convenient function to update the parameters of the calculation.
    Will atomiatically set the PARAM or CELL field in unstored
    ParaemterData linked to the calculation.
    If no ``Dict`` is linked to the calculation, a new node will be
    created.

    ..note:
      This method relies on the help information to check and assign
      keywords to PARAM or CELL field of the Dict
      (i.e for generating .param and .cell file)

    calc.update_parameters(task="singlepoint")

    :param force: flag to force the update even if the Dict node is stored.
    :param delete: A list of the keywords to be deleted.
    """
    param_node = inputs.get(INPUT_LINKNAMES['parameters'])

    # Create the node if none is found
    if param_node is None:
        warnings.warn("No existing Dict node found, creating a new one.")
        param_node = Dict(dict={"CELL": {}, "PARAM": {}})
        inputs[INPUT_LINKNAMES['parameters']] = param_node

    if isinstance(param_node, Dict) and param_node.is_stored:
        if force:
            # Create a new node if the existing node is stored
            param_node = Dict(dict=param_node.get_dict())
            inputs[INPUT_LINKNAMES['parameters']] = param_node
        else:
            raise RuntimeError("The input Dict<{}> is already stored".format(
                param_node.pk))

    # If the `node` is just a plain dict, we keep it that way
    if isinstance(param_node, Dict):
        param_dict = param_node.get_dict()
        py_dict = False
    else:
        param_dict = param_node
        py_dict = True

    # Update the dictionary
    from .helper import HelperCheckError, CastepHelper
    helper = CastepHelper()
    dict_update, not_found = helper._from_flat_dict(kwargs)
    if not_found:
        suggest = [helper.get_suggestion(i) for i in not_found]
        error_string = "Following keys are invalid -- "
        for error_key, sug in zip(not_found, suggest):
            error_string += "{}: {}; ".format(error_key, sug)
        raise HelperCheckError(error_string)
    else:
        param_dict["PARAM"].update(dict_update["PARAM"])
        param_dict["CELL"].update(dict_update["CELL"])

    # Delete any keys as requested
    if delete:
        for key in delete:
            tmp1 = param_dict["PARAM"].pop(key, None)
            tmp2 = param_dict["CELL"].pop(key, None)
            if (tmp1 is None) and (tmp2 is None):
                warnings.warn("Key '{}' not found".format(key))

    # Apply the change to the node
    if py_dict:
        inputs[INPUT_LINKNAMES['parameters']] = param_dict
    else:
        param_node.set_dict(param_dict)
    return inputs


def create_restart(inputs,
                   entry_point='castep.castep',
                   calcjob=None,
                   param_update=None,
                   param_delete=None,
                   restart_mode='restart',
                   use_castep_bin=False,
                   parent_folder=None,
                   reuse=False):
    """
    Function to create a restart for a calculation.
    :param inputs: A builder or nested dictionary
    :param entry_point: Name of the entry points
    :param param_update: Update the parameters
    :param param_delete: A list of parameters to be deleted
    :param restart_mode: Mode of the restart, 'continuation' or 'restart'
    :param use_castep_bin: Use hte 'castep_bin' file instead of check
    :param parent_folder: Remote folder to be used for restart
    :param reuse: Use the reuse mode
    """
    from aiida.plugins import CalculationFactory
    from aiida.engine import ProcessBuilder

    # Create the builder, in any case
    if isinstance(inputs, dict):
        processclass = CalculationFactory(entry_point)
        builder = processclass.get_builder()
    elif isinstance(inputs, ProcessBuilder):
        builder = inputs._process_class.get_builder()

    builder._update(inputs)

    # Update list
    update = {}
    delete = []

    # Set the restart tag
    suffix = '.check' if not use_castep_bin else '.castep_bin'
    if restart_mode == 'continuation':
        update['continuation'] = 'parent/' + builder.metadata.seedname + suffix
        delete.append('reuse')
    elif restart_mode == 'restart' and reuse:
        update['reuse'] = 'parent/' + builder.metadata.seedname + suffix
        delete.append('continuation')
    elif restart_mode is None:
        delete.extend(['continuation', 'reuse'])
    elif restart_mode != 'restart':
        raise RuntimeError('Unknown restart mode: ' + restart_mode)

    if param_update:
        update.update(param_update)
    if param_delete:
        delete.extend(param_delete)

    new_builder = update_parameters(builder,
                                    force=True,
                                    delete=delete,
                                    **update)

    # Set the parent folder
    if parent_folder is not None:
        new_builder[INPUT_LINKNAMES['parent_calc_folder']] = parent_folder

    return new_builder


def validate_input_param(input_dict, allow_flat=False):
    """
    Validate inputs parameters
    :param input_dict: A Dict instance or python dict instance
    """

    from .helper import CastepHelper
    if isinstance(input_dict, Dict):
        py_dict = input_dict.get_dict()
    else:
        py_dict = input_dict
    helper = CastepHelper()
    helper.check_dict(py_dict, auto_fix=False, allow_flat=allow_flat)


def input_param_validator(input_dict, port=None):
    """
    Validator used for input ports
    """

    from .helper import HelperCheckError
    try:
        validate_input_param(input_dict)
    except HelperCheckError as error:
        return error.args[0]


def flat_input_param_validator(input_dict, port=None):
    """
    Validator that allows allow_flat parameter format
    """
    from .helper import HelperCheckError
    try:
        validate_input_param(input_dict, allow_flat=True)
    except HelperCheckError as error:
        return error.args[0]


def check_restart(builder, verbose=False):
    """
    Check the RemoteData reference by the builder is satisfied
    :returns: True if OK
    :raises: InputValidationError if error is found
    """
    import os
    from .utils import _lowercase_dict

    def _print(inp):
        if verbose:
            print(inp)

    paramdict = builder[INPUT_LINKNAMES['parameters']].get_dict()['PARAM']
    paramdict = _lowercase_dict(paramdict, "paramdict")
    stemp = paramdict.get("reuse", None)
    if not stemp:
        stemp = paramdict.get("continuation", None)
    if stemp is not None:
        fname = os.path.split(stemp)[-1]
        _print("This calculation requires a restart file: '{}'".format(fname))
    else:
        # No restart file needed
        _print("This calculation does not require a restart file.")
        return True

    # Now check if the remote folder has this file
    remote_data = builder.get(INPUT_LINKNAMES["parent_calc_folder"])
    if not remote_data:
        raise InputValidationError(
            "Restart requires "
            "parent_folder to be specified".format(fname))
    else:
        _print("Checking remote directory")
        folder_list = remote_data.listdir()
        if fname not in folder_list:
            raise InputValidationError(
                "Restart file {}"
                " is not in the remote folder".format(fname))
        else:
            _print("Check finished, restart file '{}' exists.".format(fname))
            return True

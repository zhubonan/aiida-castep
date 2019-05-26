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


class CastepCalcTools(CalculationTools):
    def check_restart(self, verbose=True):
        """
        Check the existence of restart file if requested
        """
        import os
        from .utils import _lowercase_dict

        def _print(inp):
            if verbose:
                print(inp)

        paramdict = self._node.get_incoming(
            link_label_filter="parameters").get_dict()
        paramdict = _lowercase_dict(paramdict, "paramdict")
        stemp = paramdict.get("reuse", None)
        if not stemp:
            stemp = paramdict.get("continuation", None)

        if stemp is not None:
            fname = os.path.split(stemp)[-1]
        else:
            # No restart file needed
            _print("This calculation does not require a restart file.")
            return

        # Now check if the remote folder has this file
        remote_data = inps.get(self.get_linkname("parent_folder"), None)
        if not remote_data:
            raise InputValidationError(
                "Restart requires "
                "parent_folder to be specified".format(fname))
        else:
            folder_list = remote_data.listdir()
            if fname not in folder_list:
                raise InputValidationError(
                    "Restart file {}"
                    " is not in the remote folder".format(fname))
            else:
                _print(
                    "Check finished, restart file '{}' exists.".format(fname))

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
        this_param = self._node.get_castep_input_summary()
        other_param = castep_input_summary(calc2)
        if reverse is True:
            res = DeepDiff(this_param, other_param)
        else:
            res = DeepDiff(other_param, this_param)

        return res


# TODO: Migrate this to the new interface
# def duplicate(self):
#     """
#     Duplicate this calculation return an new, unstore calculation with
#     the same attributes but no links attached. label and descriptions
#     are also copied.
#     """
#     new = type(self._node)()

#     attrs = self.get_attributes()
#     if attrs:
#         for k, v in attrs.items():
#             if k not in self._updatable_attributes:
#                 new.set_attribute(k, v)

#     new.label = self._node.label
#     new.description = self._node.description
#     # Set the computer as well
#     new.set_computer(self.get_computer())

#     return new


def use_pseudos_from_family(builder, structure, family_name):
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
    if isinstance(calc, CalcJobNode):
        inp_dict = calc.get_incoming(
            link_type=(LinkType.INPUT_CALC, LinkType.INPUT_WORK)).nested()
        options = calc.get_options()
        is_node = True
    elif isinstance(calc, ProcessBuilder):
        inp_dict = calc._data
        options = calc.metadata.get('options', {})
        is_node = False
    elif isinstance(calc, dict):
        inp_dict = calc
        options = calc['metadata'].get('options', {})
        is_node = False

    def get_node(label):
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

    out_info["wallclock"] = options.get('max_wallclock_seconds')

    # Show the parent calculation whose RemoteData is linked to the node
    if in_remote is not None:
        input_calc = [
            n.node for n in in_remote.get_incoming()
            if n.link_label == 'remote_folder'
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
    out_info["label"] = calc.label if is_node else options.get('label')
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
                raise RuntimeError("Key {} not found".format(key))

    # Apply the change to the node
    if py_dict:
        inputs[INPUT_LINKNAMES['parameters']] = param_dict
    else:
        param_node.set_dict(param_dict)
    return inputs

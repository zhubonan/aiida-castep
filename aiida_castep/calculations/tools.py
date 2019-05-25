"""
Tools for calculations
"""
from __future__ import absolute_import
from __future__ import print_function
from aiida.tools import CalculationTools
from aiida.common import InputValidationError
import six
from aiida.plugins import DataFactory
from aiida.engine import CalcJob


class CastepCalcTools(CalculationTools):
    def _check_restart(self, verbose=True):
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
        other_param = calc2.get_castep_input_summary()
        if reverse is True:
            res = DeepDiff(this_param, other_param)
        else:
            res = DeepDiff(other_param, this_param)

    # TODO: THIS NEEDS TO BE FIXED
    def get_castep_input_summary(self):
        """
        Convenient fuction for getting a summary of the
        input of this calculation
        """

        from aiida_castep.data import get_pseudos_from_structure
        UpfData = DataFactory("upf")
        OTFGData = DataFactory("castep.otfgdata")
        UspData = DataFactory("castep.uspdata")

        out_info = {}

        inp_dict = self.get_inputs_dict()
        in_param = inp_dict[self.get_linkname('parameters')]
        in_kpn = inp_dict[self.get_linkname('kpoints')]
        in_settings = inp_dict.get(self.get_linkname('settings'), None)
        in_structure = inp_dict[self.get_linkname('structure')]
        in_code = inp_dict[self.get_linkname('code')]
        in_remote = inp_dict.get(self.get_linkname('parent_folder'), None)

        # Snippet from Pseudos calculation
        pseudos = {}
        # A dictionary that associates each kind name to a pseudo
        for link in inp_dict.keys():
            if link.startswith(self._get_linkname_pseudo_prefix()):
                kindstring = link[len(self._get_linkname_pseudo_prefix()):]
                kinds = kindstring.split('_')
                the_pseudo = inp_dict.pop(link)
                if not isinstance(the_pseudo, (UpfData, UspData, OTFGData)):
                    raise InputValidationError(
                        "Pseudo for kind(s) {} is not of "
                        "supoorted ".format(",".join(kinds)))
                for kind in kinds:
                    if kind in pseudos:
                        raise InputValidationError(
                            "Pseudo for kind {} passed "
                            "more than one time".format(kind))
                    if isinstance(the_pseudo, OTFGData):
                        pseudos[kind] = the_pseudo.string
                    elif isinstance(the_pseudo, (UspData, UpfData)):
                        pseudos[kind] = the_pseudo.filename

        param_dict = in_param.get_dict()
        out_info.update(param_dict)

        out_info["kpoints"] = in_kpn.get_desc()
        out_info["structure"] = {
            "formula": in_structure.get_formula(),
            "cell": in_structure.cell,
            "label": in_structure.label
        }

        out_info["code"] = in_code
        out_info["computer"] = self.get_computer()
        out_info["resources"] = self.get_resources()
        out_info[
            "custom_scheduler_commands"] = self.get_custom_scheduler_commands(
            )
        out_info["wallclock"] = self.get_max_wallclock_seconds()

        # Show the parent calculation whose RemoteData is linked to the node
        if in_remote is not None:
            input_calc = in_remote.get_inputs(node_type=CalcJob)
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
        out_info["label"] = self.label
        out_info["pseudos"] = pseudos
        return out_info


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


def use_pseudos_from_family(structure, family_name):
    """
        Set the pseudo to use for all atomic kinds, picking pseudos from the
        family with name family_name.


        :note: The structure must already be set.

        :param family_name: the name of the group containing the pseudos
        """
    from collections import defaultdict

    # A dict {kind_name: pseudo_object}
    # But we want to run with use_pseudo(pseudo, kinds)

    kind_pseudo_dict = get_pseudos_from_structure(structure, family_name)

    # Group the species by pseudo
    # pseudo_dict will just map PK->pseudo_object
    pseudo_dict = {}
    # Will contain a list of all species of the pseudo with given PK
    pseudo_species = defaultdict(list)

    for kindname, pseudo in six.iteritems(kind_pseudo_dict):
        pseudo_dict[pseudo.pk] = pseudo
        pseudo_species[pseudo.pk].append(kindname)

    return
    # Finally call the use_pseudo method
    for pseudo_pk in pseudo_dict:
        pseudo = pseudo_dict[pseudo_pk]
        kinds = pseudo_species[pseudo_pk]
        # I set the pseudo for all species, sorting alphabetically
        self.use_pseudo(pseudo, sorted(kinds))

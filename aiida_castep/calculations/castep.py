"""
Calculations of CASTEP
"""
from __future__ import print_function
import warnings

import aiida
from aiida.common.exceptions import InputValidationError
from aiida.common.utils import classproperty
from aiida.orm import CalculationFactory, DataFactory
from aiida_castep.calculations.base import BaseCastepInputGenerator
from aiida_castep.calculations.base import __version__ as base_version

from .utils import get_castep_ion_line

from .._version import calc_parser_version
__version__ = calc_parser_version


if aiida.__version__.startswith("0"):
    JobCalculation = CalculationFactory("job", True)
else:
    JobCalculation = CalculationFactory("job")

KpointsData = DataFactory("array.kpoints")
StructureData = DataFactory("structure")
ParameterData = DataFactory("parameter")

# Define the version of the calculation

class CastepCalculation(BaseCastepInputGenerator, JobCalculation):
    """
    Class representing a generic CASTEP calculation -
    This class should work for all types of calculations.
    """

    _default_symlink_usage = True

    # NOT CURRENTLY USED
    _acceptable_tasks = [
        "singlepoint",
        "geometryoptimization",
        "geometryoptimisation",
    ]

    _copied_attributes = ["jobresource_param", 
                          "custom_scheduler_commands", 
                          "max_wallclock_seconds"]

    def _init_internal_params(self):

        super(CastepCalculation, self)._init_internal_params()
        self._default_parser = "castep.castep"
        self._use_kpoints = True
        self._SEED_NAME = "aiida"
        self._DEFAULT_INPUT_FILE = "aiida.cell"
        self._DEFAULT_OUTPUT_FILE = "aiida.castep"

    @classproperty
    def _use_methods(cls):
        """
        Extend the parent _use_methods with further keys
        """

        retdict = JobCalculation._use_methods
        retdict.update(BaseCastepInputGenerator._baseclass_use_methods)

        # Not all calculation need kpoints
        retdict['kpoints'] = {
            'valid_types': KpointsData,
            'additional_parameter': None,
            'linkname': 'kpoints',
            'docstring': "Use the node defining the kpoint sampling to use",
        }

        return retdict

    def submit_test(self,
                    dryrun=False,
                    restart_check=False,
                    verbose=True,
                    castep_exe="castep.serial",
                    **kwargs):
        """
        Test submission. Optionally do a local dryrun.
        Return and dictionary as the third item
        * num_kpoints: number of kpoints used.
        * memory_MB: memory usage estimated MB
        * disk_MB: disk space usage estimated in MB
        """
        outcome = super(CastepCalculation, self).submit_test(**kwargs)
        outinfo = {}
        outinfo["_submit_test"] = outcome
        if dryrun:
            folder, dryrun_results = self._dryrun_test(outcome[0], castep_exe,
                                                       verbose)
            outinfo["dryrun_results"] = dryrun_results

        if restart_check:
            self.check_restart(verbose)
        return outcome

    def _check_restart(self, verbose=True):
        """
        Check the existence of restart file if requested
        """
        import os
        from .utils import _lowercase_dict

        def _print(inp):
            if verbose:
                print(inp)

        inps = self.get_inputs_dict()
        paramdict = inps[self.get_linkname("parameters")].get_dict()["PARAM"]

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
                _print("Check finished, restart file '{}' exists.".format(fname))

    def _dryrun_test(self, folder, castep_exe, verbose=True):
        """
        Do a dryrun test in a folder with prepared inputs
        """

        from fnmatch import fnmatch

        def _print(inp):
            if verbose:
                print(inp)

        # Do a dryrun
        from subprocess import call, check_output
        try:
            output = check_output([castep_exe, "-v"]).decode()
        except OSError:
            _print("CASTEP executable '{}' is not found".format(castep_exe))
            return

        # Now start dryrun
        _print("Running with {}".format(
            check_output(["which", castep_exe]).decode()))
        _print(output)

        _print("Starting dryrun...")
        call([castep_exe, "--dryrun", self._SEED_NAME], cwd=folder.abspath)

        # Check if any *err files
        contents = folder.get_content_list()
        for n in contents:
            if fnmatch(n, "*.err"):
                with folder.open(n) as fh:
                    _print("Error found in {}:\n".format(n))
                    _print(fh.read())
                raise InputValidationError("Error found during dryrun")

        # Gather information from the dryrun file
        import re
        dryrun_results = {}
        with folder.open(self._DEFAULT_OUTPUT_FILE) as fh:
            for line in fh:
                mth = re.match(r"\s*k-Points For SCF Sampling:\s+(\d+)\s*",
                               line)
                if mth:
                    dryrun_results["num_kpoints"] = int(mth.group(1))
                    _print("Number of k-points: {}".format(mth.group(1)))
                    mth = None
                    continue
                mth = re.match(
                    r"\| Approx\. total storage required"
                    r" per process\s+([0-9.]+)\sMB\s+([0-9.]+)", line)
                if mth:
                    dryrun_results["memory_MB"] = (float(mth.group(1)))
                    dryrun_results["disk_MB"] = (float(mth.group(2)))
                    _print("RAM: {} MB, DISK: {} MB".format(
                        mth.group(1), mth.group(2)))
                    mth = None
                    continue

        return folder, dryrun_results


    def duplicate(self):
        """
        Duplicate this calculation return an new, unstore calculation with
        the same attributes but no links attached. label and descriptions
        are also copied.
        """
        new = type(self)()

        attrs = self.get_attrs()
        if attrs:
            for k, v in attrs.items():
                if k not in self._updatable_attributes:
                    new._set_attr(k, v)

        new.label = self.label
        new.description = self.description
        # Set the computer as well
        new.set_computer(self.get_computer())

        return new

    def compare_with(self, the_other_calc, reverse=False):
        """
        Compare with another calculation
        Look for difference in get_castep_input_summary functions
        :params node: pk or uuid or node
        :params reverse: reverse the comparison, by default this node
        is the "new" and the one compared with is "old".
        """
        if isinstance(the_other_calc, (int, basestring)):
            from aiida.orm import load_node
            calc2 = load_node(the_other_calc)
        else:
            calc2 = the_other_calc

        from deepdiff import DeepDiff
        this_param = self.get_castep_input_summary()
        other_param = calc2.get_castep_input_summary()
        if reverse is True:
            res = DeepDiff(this_param, other_param)
        else:
            res = DeepDiff(other_param, this_param)

        # Compare the kpoints


#        this_kpt = self.get_inputs_dict()[self.get_linkname('kpoints')]
#        other_kpy = calc2.get_inputs_dict()[calc2.get_linkname('kpoints')]

# Compare psudo
        return res

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
        out_info["custom_scheduler_commands"] = self.get_custom_scheduler_commands()
        out_info["wallclock"] = self.get_max_wallclock_seconds()

        # Show the parent calculation whose RemoteData is linked to the node
        if in_remote is not None:
            input_calc = in_remote.get_inputs(node_type=JobCalculation)
            assert len(input_calc) < 2, "More than one JobCalculation found, something seriously wrong"
            if input_calc:
                input_calc = input_calc[0]
                out_info["parent_calc"] = {"pk": input_calc.pk,
                                           "label": input_calc.label}
            out_info["parent_calc_folder"] = in_remote

        if in_settings is not None:
            out_info["settings"] = in_settings.get_dict()
        out_info["label"] = self.label
        out_info["pseudos"] = pseudos
        return out_info


    def update_parameters(self, force=False, delete=None, **kwargs):
        """
        Convenient function to update the parameters of the calculation.
        Will atomiatically set the PARAM or CELL field in unstored
        ParaemterData linked to the calculation.
        If no ``ParameterData`` is linked to the calculation, a new node will be
        created.

        ..note:
          This method relies on the help information to check and assign
          keywords to PARAM or CELL field of the ParameterData
          (i.e for generating .param and .cell file)


        calc.update_parameters(task="singlepoint")

        :param force: flag to force the update even if the ParameterData node is stored.
        :param delete: A list of the keywords to be deleted.
        """
        param_node = self.get_inputs_dict().get(self.get_linkname('parameters'), None)
        # Create the node if none is found
        if param_node is None:
            warnings.warn("No existing ParameterData node found, creating a new one.")
            param_node = ParameterData(dict={"CELL": {}, "PARAM": {}})
            self.use_parameters(param_node)

        if param_node.is_stored:
           if force:
               # Create a new node if the existing node is stored
               param_node = ParameterData(dict=param_node.get_dict())
               self.use_parameters(param_node)
           else:
            raise RuntimeError("The input ParameterData<{}> is already stored".format(param_node.pk))

        param_dict = param_node.get_dict()

        # Update the dictionary
        from .helper import HelperCheckError
        helper = self.get_input_helper()
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
        param_node.set_dict(param_dict)


class Pot1dCalculation(CastepCalculation):
    """
    Class for pot1d Calculation
    """

    _internal_retrieve_list = CastepCalculation.\
                              _internal_retrieve_list + ["*.dat"]

    def _init_internal_params(self):
        super(Pot1dCalculation, self)._init_internal_params()
        self._default_parser = "castep.pot1d"

    @classmethod
    def from_calculation(cls, calc, code, use_castep_bin=False, **kwargs):
        """
        Create pot1d calculation using existing calculation.
        ``code`` must be specified as it is different from the original CASTEP code.
        """

        out_calc = cls.continue_from(
            calc,
            ignore_state=True,
            restart_type="continuation",
            use_output_structure=True,
            use_castep_bin=use_castep_bin,
            **kwargs)
        out_calc.use_code(code)
        return out_calc

    def _generate_CASTEPinputdata(self, *args, **kwargs):
        out = super(Pot1dCalculation, self).\
              _generate_CASTEPinputdata(*args, **kwargs)
        if out[1].get("continuation") is None:
            raise InputValidationError("pot1d requires "
                                       "continuation being set in .param")
        return out

    def get_withmpi(self):
        """
        pot1d is not compile with mpi.
        Hence the default is changed to False instead.
        """
        return self.get_attr('withmpi', False)


class TaskSpecificCalculation(CastepCalculation):
    """
    Class for Calculations that only allow certain tasks
    """

    _acceptable_tasks = []

    def _generate_CASTEPinputdata(self, *args, **kwargs):
        param = args[0].get_dict()

        # Check if task is correctly set
        if param['PARAM']['task'].lower() not in map(str.lower,
                                                     self._acceptable_tasks):
            raise InputValidationError("Wrong TASK value {}"
                                       " set in PARAM".format(
                                           param['PARAM']['task'].lower()))
        return super(TaskSpecificCalculation, self)._generate_CASTEPinputdata(
            *args, **kwargs)


class CastepTSCalculation(TaskSpecificCalculation):
    """
    CASTEP calculation for transition state search. Use an extra input product structure.
    """
    _acceptable_tasks = ["transitionstatesearch"]

    @classproperty
    def _use_methods(cls):

        retdict = super(CastepTSCalculation, cls)._use_methods
        retdict['product_structure'] = {
            'valid_types':
            StructureData,
            'additional_parameter':
            None,
            'linkname':
            'product_structure',
            'docstring':
            "Use the node defining the structure as the product structure in transition state search."
        }
        return retdict

    def _generate_CASTEPinputdata(self, *args, **kwargs):
        """
        Override superclass methods
        """
        cell, param, local_copy = super(CastepTSCalculation, self).\
                    _generate_CASTEPinputdata(*args, **kwargs)
        p_structure = kwargs[self.get_linkname('product_structure')]

        pdt_position_list = []
        for site in p_structure.sites:
            kind = p_structure.get_kind(site.kind_name)
            name = kind.symbol
            line = get_castep_ion_line(name, site.position)
            pdt_position_list.append(line)

        cell["POSITIONS_ABS_PRODUCT"] = pdt_position_list
        return cell, param, local_copy


class CastepExtraKpnCalculation(TaskSpecificCalculation):
    """
    CASTEP calculation with extra kpoints (e.g SPEC, BS, PHONON, SPECTRAL)
    """
    KPN_NAME = ""  # Alias of the name, e.g BS for bandstructure calculation
    CHECK_EXTRA_KPN = False  # Check the existence of extra kpoints node

    @classproperty
    def kpn_name(cls):
        return cls.KPN_NAME.lower()

    @classproperty
    def _use_methods(cls):

        retdict = CastepCalculation._use_methods

        retdict['{}_kpoints'.format(cls.KPN_NAME.lower())] = {
            'valid_types':
            KpointsData,
            'additional_parameter':
            None,
            'linkname':
            '{}_kpoints'.format(cls.kpn_name),
            'docstring':
            "Use the node defining the kpoint sampling for band {}  calculation"
            .format(cls.TASK.lower())
        }
        return retdict

    def _generate_CASTEPinputdata(self, *args, **kwargs):
        """Add BS kpoints information to the calculation"""

        cell, param, local_copy = super(CastepExtraKpnCalculation,
                                        self)._generate_CASTEPinputdata(
                                            *args, **kwargs)

        # Check the existence of extra kpoints
        try:
            extra_kpns = kwargs[self.get_linkname('{}_kpoints'.format(
                self.kpn_name))]
        except KeyError:
            if self.CHECK_EXTRA_KPN:
                raise InputValidationError("{}_kpoints"
                                           " node not found".format(
                                               self.kpn_name))
            else:
                return cell, param, local_copy

        # Add information in the node to cell file
        try:
            mesh, offset = extra_kpns.get_kpoints_mesh()
            has_mesh = True
        except AttributeError:
            try:
                bs_kpts_list = extra_kpns.get_kpoints()
                num_kpoints = len(bs_kpts_list)
                has_mesh = False
                if num_kpoints == 0:
                    raise InputValidationError(
                        "At least one k points must be provided")
            except AttributeError:
                raise InputValidationError(
                    "No valid {}_kpoints have been found".format(
                        self.kpn_name))

            try:
                _, weights = extra_kpns.get_kpoints(also_weights=True)

            except AttributeError:
                import numpy as np
                weights = np.ones(num_kpoints, dtype=float) / num_kpoints

        if has_mesh is True:
            mesh_name = "{}_kpoints_mp_grid".format(self.kpn_name)
            cell[mesh_name] = "{} {} {}".format(*mesh)
            if offset != [0., 0., 0.]:
                cell[mesh_name.replace("grid",
                                       "offset")] = "{} {} {}".format(*offset)
        else:
            bs_kpts_lines = []
            for kpoint, weight in zip(bs_kpts_list, weights):
                bs_kpts_lines.append("{:18.10f} {:18.10f} "
                                     "{:18.10f} {:18.10f}".format(
                                         kpoint[0], kpoint[1], kpoint[2],
                                         weight))
            bname = "{}_kpoints_list".format(self.kpn_name).upper()
            cell[bname] = bs_kpts_lines
        return cell, param, local_copy

    def create_restart(self, *args, **kwargs):
        """
        Create a restart of the calculation
        """
        out_calc = super(CastepExtraKpnCalculation, self).create_restart(
            *args, **kwargs)

        # Attach the extra kpoints node if it is there
        inp_name = "{}_kpoints".format(self.kpn_name)  # Name of the input
        linkname = self.get_linkname(inp_name)  # Name of the link

        extra_kpn_node = self.get_inputs_dict().get(linkname)
        if extra_kpn_node:
            getattr(out_calc, "use_" + inp_name)(extra_kpn_node)
        return out_calc

    def get_castep_input_summary(self):
        """
        Generate a dictionary to summarize the inputs to CASTEP
        """

        inp_name = "{}_kpoints".format(self.kpn_name)  # Name of the input
        linkname = self.get_linkname(inp_name)  # Name of the link

        out_dict = super(CastepExtraKpnCalculation, self).get_castep_input_summary()
        out_dict[inp_name] = self.get_inputs_dict().get(linkname)
        return out_dict

    @classmethod
    def continue_from(cls, *args, **kwargs):
        """
        Create a new calculation as a continuation from a given calculation.
        This is effectively an "restart" for CASTEP and a lot of the parameters
        can be tweaked. For example, conducting bandstructure calculation from
        finished geometry optimisation's.
        :param bool ignore_state: Ignore the state of parent calculation
        :param str restart_type: "continuation" or "restart".
        If set to continuation the child calculation has keyword
        'continuation' set.
        :param bool reuse: Whether we want to reuse the previous calculation.
        only applies for "restart" run
        :param bool parent_folder_symlink: if True, symlink are used instead
        of hard copies of the files. Default given be
        self._default_symlink_usage
        :param bool use_output_structure: if True, the output structure of
        parent calculation is used as the input of the child calculation.
        This is useful for photon/bs calculation.

        See also: create_restart
        """
        cout = super(CastepExtraKpnCalculation, cls).continue_from(
            *args, **kwargs)

        # Check the task keyword
        param = cout.get_inputs_dict()[cout.get_linkname('parameters')]
        param_dict = param.get_dict()

        task = param_dict['PARAM'].get('task')
        if task and task == cls.TASK.lower():
            pass
        else:
            # Replace task
            param_dict['PARAM']['task'] = cls.TASK.lower()
            from aiida.orm import DataFactory
            ParameterData = DataFactory('parameter')
            new_param = ParameterData(dict=param_dict)
            cout._remove_link_from(cout.get_linkname('parameters'))
            cout.use_parameters(new_param)

        return cout


class CastepBSCalculation(CastepExtraKpnCalculation):
    """
    CASTEP bandstructure calculation
    """

    TASK = "BANDSTRUCTURE"
    _acceptable_tasks = [TASK]
    KPN_NAME = "BS"


class CastepSpectralCalculation(CastepExtraKpnCalculation):
    """
    CASTEP spectral calculation
    """
    TASK = "SPECTRAL"
    _acceptable_tasks = [TASK]
    KPN_NAME = "SPECTRAL"


class CastepOpticsCalclulation(CastepExtraKpnCalculation):
    """
    CASTEP Optics calculation
    """
    TASK = "OPTICS"
    _acceptable_tasks = [TASK]
    KPN_NAME = "OPTICS"

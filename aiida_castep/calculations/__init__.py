# -*- coding: utf-8 -*-
import os

from aiida.common.exceptions import InputValidationError
from aiida.common.datastructures import CalcInfo
from aiida.orm.data.upf import get_pseudos_from_structure
from aiida.common.utils import classproperty

from aiida.orm.data.structure import StructureData
from aiida.orm.data.parameter import ParameterData
from aiida.orm.data.array.kpoints import KpointsData
from aiida.orm.data.upf import UpfData
from aiida.orm.data.singlefile import SinglefileData
from aiida.orm.data.remote import RemoteData
from aiida.common.datastructures import CodeInfo
from aiida.common.links import LinkType


class BaseCastepInputGenerator(object):
    """
    Baseclass for generating CASTEP inputs
    """
    # This may not apply to CASTEP runs
    _PSEUDO_SUBFOLDER = "./pseudo/"
    # Castep output is in the
    _OUTPUT_SUBFOLDER = "./"
    _PREFIX = 'aiida'
    _INPUT_FILE_NAME = "aiida.cell"
    _OUTPUT_FILE_NAME = "aiida.castep"
    _SEED_NAME = 'aiida'

    # Additional files that should always be retrieved for the specific plugin
    _internal_retrieve_list = [("*.err", ".", 1)]

    ## Default PW output parser provided by AiiDA
    # to be defined in the subclass

    _automatic_namelists = {}

    # in restarts, will not copy but use symlinks
    _default_symlink_usage = True

    # in restarts, it will copy from the parent the following
    _restart_copy_from = "*"

    # in restarts, it will copy the previous folder in the following one
    _restart_copy_to = _OUTPUT_SUBFOLDER

    # Default verbosity; change in subclasses
    _default_verbosity = 1

    @classproperty
    def _baseclass_use_methods(cls):
        """
        This will be manually added to the _use_methods in each subclass
        """
        return {
            "structure": {
                'valid_types': StructureData,
                'additional_parameter': None,
                'linkname': 'structure',
                'docstring': "Choose the input structure to use",
            },
            "settings": {
                'valid_types': ParameterData,
                'additional_parameter': None,
                'linkname': 'settings',
                'docstring': "Use an additional node for special settings",
            },
            "parameters": {
                'valid_types': ParameterData,
                'additional_parameter': None,
                'linkname': 'parameters',
                'docstring': ("Use a node that specifies the input parameters "
                              "for the namelists"),
            },
            "parent_folder": {
                'valid_types': RemoteData,
                'additional_parameter': None,
                'linkname': 'parent_calc_folder',
                'docstring': ("Use a remote folder as parent folder (for "
                              "restarts and similar"),
            },
            # TODO: Implement handling of pseduopoentials
            # Psudo potential is not not always necessary for CASTEP
            # Since 16.1 Version now support UPF files so such function
            # may be useful in the future
            "pseudo": {
                'valid_types': UpfData,
                'additional_parameter': "kind",
                'linkname': "pseudo",
                'docstring': (
                    "Use a node for the UPF pseudopotential of one of "
                    "the elements in the structure. You have to pass "
                    "an additional parameter ('kind') specifying the "
                    "name of the structure kind (i.e., the name of "
                    "the species) for which you want to use this "
                    "pseudo. You can pass either a string, or a "
                    "list of strings if more than one kind uses the "
                    "same pseudo"),
            },
        }

    def _generate_CASTEPinputdata(self, parameters,
                                  settings_dict,
                                  pseudos,
                                  structure,
                                  kpoints=None):
        """
        This method creates the content of an input file in the
        CASTEP format
        Generated input here should be generic to all castep calculations
        """
        from aiida.common.utils import get_unique_filename, get_suggestion
        import re
        local_copy_list_to_append = []

        # The input dictionary should be {"CELL": {"fix_all_cell": True},
        # "PARAM":{"opt_strategy" : "speed"}}

        # The following lines enforces the case of names
        # EACH entry is written as in lower case

        input_params = _uppercase_dict(parameters.get_dict(),
                                       dict_name="parameters")
        input_params = {k: _lowercase_dict(v, dict_name=k)
                        for k, v in input_params.iteritems()}

        # Check if there are keywrods that need to be blocked
        # TODO implementation. See QE's input generatetor

        # Set verbosity to 1.
        # Parser may not work if verbosity is not 1
        input_params["PARAM"]["iprint"] = input_params["PARAM"].get("iprint",
            self._default_verbosity)

        # ========= Start to preare input site data ======
        # --------- CELL ----------
        cell_parameters_list = ["%BLOCK LATTICE_CART"]
        for vector in structure.cell:
            cell_parameters_list.append( ("{0:18.10f} {1:18.10f} "
                                          "{2:18.10f}".format(*vector)))

        cell_parameters_list.append("%ENDBLOCK LATTICE_CART")
        cell_parameters_card = "\n".join(cell_parameters_list)

        # --------- ATOMIC POSITIONS---------
        # for kind in structure.kinds:
        atomic_position_card_list = ["%BLOCK POSITIONS_ABS"]
        for site in structure.sites:
            atomic_position_card_list.append(
                "{0} {1:18.10f} {2:18.10f} {3:18.10f}".format(
                    site.kind_name.ljust(6), site.position[0],
                    site.position[1], site.position[2]))
        atomic_position_card_list.append("%ENDBLOCK POSITIONS_ABS")
        atomic_position_card = "\n".join(atomic_position_card_list)
        del atomic_position_card_list  # Free memory

        # SET KPOINTS
        if self._use_kpoints:
            try:
                mesh, offset = kpoints.get_kpoints_mesh()
                has_mesh = True

            except AttributeError:
                try:
                    kpoints_list = kpoints.get_kpoints()
                    num_kpoints = len(kpoints_list)
                    has_mesh = False
                    if num_kpoints == 0:
                        raise InputValidationError(
                            "At least one k points must be provided")
                except AttributeError:
                    raise InputValidationError(
                        "No valid kpoints have been found")

                try:
                    _, weights = kpoints.get_kpoints(also_weights=True)

                except AttributeError:
                    weights = [1.] / num_kpoints

            kpoints_card = ""
            if has_mesh is True:
                input_params["CELL"]["kpoints_mp_grid"] = "{} {} {}".format(*mesh)
            else:
                kpoints_card_list = ["%BLOCK KPOINTS_LIST"]
                for kpoint, weight in zip(kpoints_list, weights):
                    kpoints_card_list.append("{:18.10f} {:18.10f} "
                         "{:18.10f} {:18.10f}".format(kpoint[0],
                                                      kpoint[1],
                                                      kpoint[2], weight))
                kpoints_card_list.append("%ENDBLOCK KPOINTS_LIST")

                kpoints_card = "\n".join(kpoints_card_list)

                del kpoints_card_list

        ### Paramters for CELL file ###
        cell_entry_list = []
        for key, value in input_params["CELL"].iteritems():

            # Constructing block keywrods
            if "block" in key:
                key = key.replace("block", "").strip()
                lines = "\n".join(value)
                entry = "\n%BLOCK {key}\n{content}\n%ENDBLOCK {key}\n".format(key=key,
                    content=lines)
            else:
                entry = "{} : {}".format(key, value)
            cell_entry_list.append(entry)

        cell_entries = "\n".join(cell_entry_list)
        del cell_entry_list

        ### Parameters for PARAM files ###

        param_entry_list = []
        for key, value in input_params["PARAM"].iteritems():

            entry = "{} : {}".format(key, value)
            param_entry_list.append(entry)

        param_entries = "\n".join(param_entry_list)
        del param_entry_list


        #### PUTTING THINGS TOGETHER ####
        cellfile = "\n\n".join([cell_parameters_card, atomic_position_card,
                              kpoints_card, cell_entries])
        paramfile = param_entries

        print(paramfile)
        print(cellfile)
        return cellfile, paramfile

    def _prepare_for_submission(self, tempfolder, inputdict):

        """
        Routinue to be called when create the input files and other stuff

        :param tempfolder: a aiida.common.folders.Folder subclass where
                           the plugin should put all its files.
        :param inputdict: a dictionary with the input nodes, as they would
                be returned by get_inputs_dict (without the Code!)
        """

        local_copy_list = []
        remote_copy_list = []
        remote_symlink_list = []

        try:
            parameters = inputdict.pop(self.get_linkname('parameters'))
        except KeyError:
            raise InputValidationError("No parameters specified for this calculation")
        if not isinstance(parameters, ParameterData):
            raise InputValidationError("parameters is not of type ParameterData")

        try:
            structure = inputdict.pop(self.get_linkname('structure'))
        except KeyError:
            raise InputValidationError("No structure specified for this calculation")
        if not isinstance(structure, StructureData):
            raise InputValidationError("structure is not of type StructureData")

        if self._use_kpoints:
            try:
                kpoints = inputdict.pop(self.get_linkname('kpoints'))
            except KeyError:
                raise InputValidationError("No kpoints specified for this calculation")
            if not isinstance(kpoints, KpointsData):
                raise InputValidationError("kpoints is not of type KpointsData")
        else:
            kpoints = None


        # Settings can be undefined, and defaults to an empty dictionary
        settings = inputdict.pop(self.get_linkname('settings'), None)
        if settings is None:
            settings_dict = {}
        else:
            if not isinstance(settings, ParameterData):
                raise InputValidationError("settings, if specified, must be of "
                                           "type ParameterData")
            # Settings converted to uppercase
            settings_dict = _uppercase_dict(settings.get_dict(),
                                            dict_name='settings')

        # Check parent calc folder
        parent_calc_folder = inputdict.pop(self.get_linkname('parent_folder'), None)
        if parent_calc_folder is not None:
            if not isinstance(parent_calc_folder, RemoteData):
                raise InputValidationError("parent_calc_folder, if specified, "
                                           "must be of type RemoteData")

        try:
            code = inputdict.pop(self.get_linkname('code'))
        except KeyError:
            raise InputValidationError("No code specified for this calculation")

        # Here, there should be no more parameters...
        if inputdict:
            raise InputValidationError("The following input data nodes are "
                                       "unrecognized: {}".format(inputdict.keys()))
        ##############################
        # END OF INITIAL INPUT CHECK #
        ##############################

        pseudos = []
        cell_input, param_input = self._generate_CASTEPinputdata(parameters,
            settings_dict, pseudos, structure, kpoints)

        cell_input_filename = tempfolder.get_abs_path(self._SEED_NAME + ".cell")
        param_input_filename = tempfolder.get_abs_path(self._SEED_NAME + ".param")

        with open(cell_input_filename, "w") as incell:
            incell.write(cell_input)

        with open(param_input_filename, "w") as inparam:
            inparam.write(param_input)

        # TODO: IMPLEMENT OPERATIONS FOR RESTART

        calcinfo = CalcInfo()

        calcinfo.uuid = self.uuid
        cmdline_params = settings_dict.pop("CMDLINE", [])

        # Extra parameters are added after the seed for CASTEP
        calcinfo.cmdline_params = [self._SEED_NAME] + list(cmdline_params)

        # CASTEP don't have any STDOUT etc when running calculations
        # Error is shown in the *.err file

        # Construct codeinfo instance
        codeinfo = CodeInfo()
        codeinfo.cmdline_params = [self._SEED_NAME] + list(cmdline_params)
        codeinfo.code_uuid = code.uuid
        calcinfo.codes_info = [codeinfo]

        # Retrieve by default the .castep file only
        calcinfo.retrieve_list = []
        calcinfo.retrieve_list.append(self._SEED_NAME + ".castep")
        settings_retrieve_list = settings_dict.pop("ADDITIONAL_RETRIEVE_LIST", [])

        # If we are doing geometryoptimisation retrived the geom file and -out.cell file
        calculation_mode = parameters.get_dict().get("PARAM", {}).get("task")

        if calculation_mode in ["geometryoptimisation", "geometryoptimization"]:
            settings_retrieve_list.append(self._SEED_NAME + ".geom")
            if parameters.get_dict().get("PARAM", {}).get("write_cell_structure"):
                settings_retrieve_list.append(self._SEED_NAME + "-out.cell")

        calcinfo.retrieve_list += settings_retrieve_list
        calcinfo.retrieve_list += self._internal_retrieve_list

        # Checking parser options
        try:
            Parserclass = self.get_paaserclass()
            parser = Parserclass(self)
            parser_opts = parser.get_parser_settings_key()
            settings_dict.pop(parser_opts)
        except (KeyError, AttributeError):
            pass

        if settings_dict:
            raise InputValidationError("The following keys have been found in "
                                       "the settings input node, but were not understood: {}".format(
                ",".join(settings_dict.keys())))

        return calcinfo

    # TODO implement checking up of input parameters
    @classmethod
    def input_helper(cls, *args, **kwargs):
        """
        Validate if the keywords are valid castep keywords
        Also try to convert the parameter diction in a
        "standardized" form
        """
        pass


def _lowercase_dict(d, dict_name):
    from collections import Counter

    if isinstance(d, dict):
        new_dict = dict((str(k).lower(), v) for k, v in d.iteritems())
        if len(new_dict) != len(d):
            num_items = Counter(str(k).lower() for k in d.keys())
            double_keys = ",".join([k for k, v in num_items if v > 1])
            raise InputValidationError(
                "Inside the dictionary '{}' there are the following keys that "
                "are repeated more than once when compared case-insensitively: {}."
                "This is not allowed.".format(dict_name, double_keys))
        return new_dict
    else:
        raise TypeError("_lowercase_dict accepts only dictionaries as argument")


def _uppercase_dict(d, dict_name):
    from collections import Counter

    if isinstance(d, dict):
        new_dict = dict((str(k).upper(), v) for k, v in d.iteritems())
        if len(new_dict) != len(d):
            num_items = Counter(str(k).upper() for k in d.keys())
            double_keys = ",".join([k for k, v in num_items if v > 1])
            raise InputValidationError(
                "Inside the dictionary '{}' there are the following keys that "
                "are repeated more than once when compared case-insensitively: {}."
                "This is not allowed.".format(dict_name, double_keys))
        return new_dict
    else:
        raise TypeError("_uppercase_dict accepts only dictionaries as argument")

# -*- coding: utf-8 -*-
"""
Base module for calculations
"""
from __future__ import print_function

import os
import logging

from aiida.common.exceptions import InputValidationError
from aiida.common.datastructures import CalcInfo
from aiida.common.utils import classproperty

from aiida.orm.data.structure import StructureData
from aiida.orm.data.parameter import ParameterData
from aiida.orm.data.array.kpoints import KpointsData
from aiida.orm.data.upf import UpfData
from aiida.orm.data.remote import RemoteData
from aiida.common.datastructures import CodeInfo
from aiida.common.exceptions import MultipleObjectsError
from .utils import get_castep_ion_line
from aiida_castep.data import OTFGData, UspData, get_pseudos_from_structure
from .helper import CastepHelper
import copy


class BaseCastepInputGenerator(object):
    """
    Baseclass for generating CASTEP inputs
    """
    # This may not apply to CASTEP runs
    _PSEUDO_SUBFOLDER = "./pseudo/"
    # Castep output is in the
    _PARENT_CALC_SUBFOLDER = "./parent/"
    _PREFIX = 'aiida'
    _INPUT_FILE_NAME = "aiida.cell"
    _OUTPUT_FILE_NAME = "aiida.castep"
    _SEED_NAME = 'aiida'

    # Additional files that should always be retrieved for the specific plugin
    _internal_retrieve_list = ["*.err"]

    ## Default PW output parser provided by AiiDA
    # to be defined in the subclass

    _automatic_namelists = {}

    # in restarts, will not copy but use symlinks
    _default_symlink_usage = True

    # in restarts, it will copy from the parent the following
    _restart_copy_from = "./"

    # in restarts, it will copy the previous folder in the following one
    _restart_copy_to = _PARENT_CALC_SUBFOLDER

    # Default verbosity; change in subclasses
    _default_verbosity = 1

    # whether we are automaticall validating the input paramters
    _auto_input_validation = True

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

            "pseudo": {
                'valid_types': (UpfData, OTFGData, UspData),
                'additional_parameter': "kind",
                'linkname': cls._get_linkname_pseudo,
                'docstring': (
                    "Use a node for the  pseudopotential of one of "
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
                                  kpoints=None,
                                  **kwargs):
        """
        This method creates the content of an input file in the
        CASTEP format
        Generated input here should be generic to all castep calculations

        :param parameters, ParameterData: Input goes to the .cell or .param file
        :param settings_dict: A dictionary of the settings used for generation
        :param pseudos: A dictionary of pseduo potential Data for each kind
        :param structure: A StructureData instance
        :param kpoints: A KpointsData node, optional
        """
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

        # Set run_time using define value for this calcualtion
        run_time = self.get_max_wallclock_seconds()
        if run_time:
            n_seconds = run_time * 0.95
            n_seconds = (n_seconds // 60) * 60  # Round down to the nearest minutes
            # Do not do any thing if calculated time is less than 1 hour
            if n_seconds < 3600:
                pass
            elif "run_time" not in input_params["PARAM"]:
                input_params["PARAM"]["run_time"] = int(n_seconds)

        # ========= Start to prepare input site data ======

        # --------- CELL ----------
        cell_vector_list = ["%BLOCK LATTICE_CART"]
        for vector in structure.cell:
            cell_vector_list.append( ("{0:18.10f} {1:18.10f} "
                                          "{2:18.10f}".format(*vector)))

        cell_vector_list.append("%ENDBLOCK LATTICE_CART")

        # --------- ATOMIC POSITIONS---------
        # for kind in structure.kinds:
        atomic_position_list = ["%BLOCK POSITIONS_ABS"]
        mixture_count = 0
        # deal with initial spins
        spin_array = settings_dict.pop("SPINS", None)
        label_array = settings_dict.pop("LABELS", None)

        for i, site in enumerate(structure.sites):
            # get  the kind of the site
            kind = structure.get_kind(site.kind_name)

            # Position is always needed
            pos = site.position
            try:
                name = kind.symbol
            # If we are dealing with mixed atoms
            except ValueError:
                name = kind.symbols
                mixture_count += 1

            if spin_array:
                spin = spin_array[i]
            else:
                spin = None

            # deal with labels
            if label_array:
                label = label_array[i]
            else:
                label = None

            line = get_castep_ion_line(name, pos,
                                       label=label, spin=spin,
                                       occupation=kind.weights,
                                       mix_num=mixture_count)

            # Append the line to the list
            atomic_position_list.append(line)

        # End ofthe atomic position block
        atomic_position_list.append("%ENDBLOCK POSITIONS_ABS")


        # --------- KPOINTS ---------
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
                    import numpy as np
                    weights = np.ones(num_kpoints, dtype=float) / num_kpoints

            if has_mesh is True:
                input_params["CELL"]["kpoints_mp_grid"] = "{} {} {}".format(*mesh)
                kpoints_line_list = []
            else:
                kpoints_line_list = ["%BLOCK KPOINTS_LIST"]
                for kpoint, weight in zip(kpoints_list, weights):
                    kpoints_line_list.append("{:18.10f} {:18.10f} "
                         "{:18.10f} {:18.10f}".format(kpoint[0],
                                                      kpoint[1],
                                                      kpoint[2], weight))
                kpoints_line_list.append("%ENDBLOCK KPOINTS_LIST")

        # --------- PSUDOPOTENTIALS --------
        # Check if we are using UPF pseudos
        # Now only support simple elemental pseudopotentials
        if pseudos:
            symbols = set()  # All of the symbols
            species_pot_list = ["%BLOCK SPECIES_POT"]
            for kind in structure.kinds:
                for s in kind.symbols:
                    symbols.add(s)

            # Make symbols unique
            for s in symbols:
                ps = pseudos[s]  # Get the pseupotential object

                # If we are dealing with a UpfData object
                if isinstance(ps, (UpfData, UspData)):
                    species_pot_list.append("{:5} {}".format(s, ps.filename))
                    # Add to the copy list
                    local_copy_list_to_append.append((ps.get_file_abs_path(), ps.filename))

                # If we are using OTFG, just add the string property of it
                if isinstance(ps, OTFGData):
                    species_pot_list.append("{:5} {}".format(s, ps.string))

            species_pot_list.append("%ENDBLOCK SPECIES_POT")

        else:
            species_pot_list = []

        # --------- PARAMETERS in cell file---------
        cell_entry_list = []
        for key, value in input_params["CELL"].iteritems():

            if "species_pot" in key:
                if pseudos:
                    raise MultipleObjectsError("Both species_pot and pseudos are provided")
                self.logger.warning("Pseudopotentials directly defined in CELL dictionary")

            # Constructing block keywrods
            # We identify the key should be treated as a block it is not a string and has len() > 0
            if isinstance(value, (list, tuple)):
                lines = "\n".join(value)
                entry = "\n%BLOCK {key}\n{content}\n%ENDBLOCK {key}\n".format(key=key,
                    content=lines)
            else:
                entry = "{} : {}".format(key, value)
            cell_entry_list.append(entry)

        ### Parameters for PARAM files ###

        param_entry_list = []
        for key, value in input_params["PARAM"].iteritems():

            entry = "{} : {}".format(key, value)
            param_entry_list.append(entry)

        param_entries = "\n".join(param_entry_list)

        #### PUTTING THINGS TOGETHER ####
        cellfile_list = []

        # Cell vectors and positions in the cell file
        cellfile_list.extend(cell_vector_list + ["\n"])
        cellfile_list.extend(atomic_position_list + ["\n"])

        # If not using mesh, add specified kpoints
        cellfile_list.extend(kpoints_line_list + ["\n"])

        # Pseudopotentials in cell file
        cellfile_list.extend(species_pot_list + ["\n"])

        # Keywords for cell ile
        cellfile_list.extend(cell_entry_list)

        # Final strings to be written to file
        cellfile = "\n".join(cellfile_list)
        paramfile = param_entries

        return cellfile, paramfile, local_copy_list_to_append

    def _prepare_for_submission(self, tempfolder, inputdict):

        """
        Routinue to be called when create the input files and other stuff

        :param tempfolder: a aiida.common.folders.Folder subclass where
                           the plugin should put all its files.
        :param inputdict: a dictionary with the input nodes, as they would
                be returned by get_inputs_dict (without the Code!)
        """

        local_copy_list = []

        # TODO implement remote copy for restart calculations
        remote_copy_list = []
        remote_symlink_list = []

        try:
            parameters = inputdict.pop(self.get_linkname('parameters'))
            # Validate the parameters
            if self._auto_input_validation is True:
                self.check_castep_input(parameters.get_dict(), auto_fix=False)

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

        # Set up pseodo potentials
        # The existance of pseudopoential is optional
        pseudos = {}
        # I create here a dictionary that associates each kind name to a pseudo
        for link in inputdict.keys():
            if link.startswith(self._get_linkname_pseudo_prefix()):
                kindstring = link[len(self._get_linkname_pseudo_prefix()):]
                kinds = kindstring.split('_')
                the_pseudo = inputdict.pop(link)
                if not isinstance(the_pseudo, (UpfData, UspData, OTFGData)):
                    raise InputValidationError("Pseudo for kind(s) {} is not of "
                                               "supoorted ".format(",".join(kinds)))
                for kind in kinds:
                    if kind in pseudos:
                        raise InputValidationError("Pseudo for kind {} passed "
                                                   "more than one time".format(kind))
                    pseudos[kind] = the_pseudo


        # Check parent calc folder
        parent_calc_folder = inputdict.pop(self.get_linkname('parent_folder'), None)
        if parent_calc_folder is not None:
            if not isinstance(parent_calc_folder, RemoteData):
                raise InputValidationError("parent_calc_folder, if specified, "
                                           "must be of type RemoteData")

        # Check if a code is specified
        try:
            code = inputdict.pop(self.get_linkname('code'))
        except KeyError:
            raise InputValidationError("No code specified for this calculation")

        # Here, there should be no more parameters...
        # But in case there is, check if this is something not implemented
        # in this base class
        if inputdict:
            for key in inputdict:
                if key not in self._use_methods:
                    raise InputValidationError("The following input data nodes are "
                                               "unrecognized: {}".format(inputdict.keys()))
        ##############################
        # END OF INITIAL INPUT CHECK #
        ##############################

        # Generate input file
        cell_input, param_input, pseudo_copy_list = self._generate_CASTEPinputdata(parameters,
            settings_dict, pseudos, structure, kpoints, **inputdict)

        local_copy_list.extend(pseudo_copy_list)

        cell_input_filename = tempfolder.get_abs_path(self._SEED_NAME + ".cell")

        param_input_filename = tempfolder.get_abs_path(self._SEED_NAME + ".param")


        with open(cell_input_filename, "w") as incell:
            incell.write(cell_input)

        with open(param_input_filename, "w") as inparam:
            inparam.write(param_input)

        # IMPLEMENT OPERATIONS FOR RESTART
        symlink = settings_dict.pop('PARENT_FOLDER_SYMLINK', self._default_symlink_usage)

        if parent_calc_folder is not None:
            if symlink:
                remote_list = remote_symlink_list
            else:
                remote_list = remote_copy_list
            remote_list.append(
                    (parent_calc_folder.get_computer().uuid,
                        os.path.join(parent_calc_folder.get_remote_path(),
                                     self._restart_copy_from),
                        self._restart_copy_to))

        calcinfo = CalcInfo()

        calcinfo.uuid = self.uuid

        # COPY/SYMLINK LISTS
        calcinfo.local_copy_list = local_copy_list
        calcinfo.remote_copy_list = remote_copy_list
        calcinfo.remote_symlink_list = remote_symlink_list

        # SET UP extra CMDLINE arguments
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

        # Retrieve by default the .castep file and the bands file
        calcinfo.retrieve_list = []

        calcinfo.retrieve_list.append(self._SEED_NAME + ".castep")
        calcinfo.retrieve_list.append(self._SEED_NAME + ".bands")


        settings_retrieve_list = settings_dict.pop("ADDITIONAL_RETRIEVE_LIST", [])
        calcinfo.retrieve_list.extend(settings_retrieve_list)

        # If we are doing geometryoptimisation retrived the geom file and -out.cell file
        calculation_mode = parameters.get_dict().get("PARAM", {}).get("task")

        if calculation_mode in ["geometryoptimisation", "geometryoptimization"]:
            settings_retrieve_list.append(self._SEED_NAME + ".geom")
            if parameters.get_dict().get("PARAM", {}).get("write_cell_structure"):
                settings_retrieve_list.append(self._SEED_NAME + "-out.cell")

        calcinfo.retrieve_list += settings_retrieve_list
        calcinfo.retrieve_list += self._internal_retrieve_list

        # Remove parser options in the setting dictionary
        # At the moment parser options are not used here
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

    def _set_parent_remotedata(self, remotedata):
        """
        Used to set a parent remotefolder
        """
        from aiida.common.exceptions import ValidationError

        if not isinstance(remotedata, RemoteData):
            raise ValueError('remotedata must be a RemoteData')

        # complain if another remotedata is already found
        input_remote = self.get_inputs(node_type=RemoteData)
        if input_remote:
            raise ValidationError("Cannot set several parent calculation to a "
                                  "{} calculation".format(
                self.__class__.__name__))

        self.use_parent_folder(remotedata)

    def create_restart(self, ignore_state=False, restart_type="restart", reuse=False, use_symlink=None, use_output_structure=False, use_castep_bin=False):
        """
        Method to restart the calculation by creating a new one.
        Return a new calculation with all the essential input nodes in the unstored stated.

        CASTEP has two modes of 'restart', activated by setting CONTINUATION or REUSE keywords in .param file.

        CONTINUATION
        ------------
        Restart from the end of the last run. Only limited set of parameters can be modified. If unmodifiable parameters were changed, they are ignored. E.g changes of task, nextra_bands, cut_off_energy will be ignored. This is often used for geometry optimisation or md runs.

        REUSE
        -----
        Essentially making a new calculation with parameters read from .cell and .param file.
        Data from *.castep_bin or *.check will be used to initialise te model of the new run. This is often used for bandstructure, dos, spectral calculation.

        Note both castep_bin and check file may be used.
        They are almost the same except castep_bin does not have wavefunctions stored.


        :param bool ignore_state: Ignore the state of parent calculation
        :param str restart_type: "continuation" or "restart". If set to continuation the child calculation has keyword 'continuation' set.
        :param bool reuse: Wether we want to reuse the previous calculation.
        only applies for "restart" run
        :param bool parent_folder_symlink: if True, symlink are used instead of hard copies of the files. Default given be self._default_symlink_usage
        :param bool use_output_structure: if True, the output structure of parent calculation is used as the input of the child calculation.
        This is useful for photon/bs calculation.
        """

        cout = _create_restart(self, ignore_state, restart_type, reuse,
            use_symlink, use_output_structure, use_castep_bin)
        return cout

    @classmethod
    def continue_from(cls, cin,
                      ignore_state=False, restart_type="restart",
                      reuse=False, use_symlink=None,
                      use_output_structure=False,
                      use_castep_bin=False):
        """
        Create a new calcualtion as a continution from a given calculation.
        This is effectively an "restart" for CASTEP and a lot of the parameters
        can be tweaked. For example, conducting bandstructure calculation from
        finished geometry optimisations.

        CASTEP has two modes of 'restart', activated by setting CONTINUATION or REUSE keywords in .param file.

        CONTINUATION
        ------------
        Restart from the end of the last run. Only limited set of parameters can be modified. If unmodifiable parameters were changed, they are ignored. E.g changes of task, nextra_bands, cut_off_energy will be ignored. This is often used for geometry optimisation or md runs.

        REUSE
        -----
        Essentially making a new calculation with parameters read from .cell and .param file.
        Data from *.castep_bin or *.check will be used to initialise te model
         of the new run.
         This is often used for bandstructure, dos, spectral calculation.

        Note both castep_bin and check file may be used. They are almost the
        same except castep_bin does not have wavefunctions stored.


        :param bool ignore_state: Ignore the state of parent calculation
        :param str restart_type: "continuation" or "restart".
        If set to continuation the child calculation has keyword
        'continuation' set.
        :param bool reuse: Wether we want to reuse the previous calculation.
        only applies for "restart" run
        :param bool parent_folder_symlink: if True, symlink are used instead
        of hard copies of the files. Default given be
        self._default_symlink_usage
        :param bool use_output_structure: if True, the output structure of
        parent calculation is used as the input of the child calculation.
        This is useful for photon/bs calculation.
        """
        cout = _create_restart(cin, ignore_state, restart_type, reuse,
            use_symlink, use_output_structure, use_castep_bin, cls)

        return cout

    @classmethod
    def check_castep_input(cls, input_dict, auto_fix=False):
        """
        Validate if the keywords are valid castep keywords
        Also try to convert the parameter diction in a
        "standardized" form
        """
        helper = cls.get_input_helper()
        helper.check_dict(input_dict, auto_fix)

    @classmethod
    def get_input_helper(cls):
        helper = CastepHelper()
        return helper

    @classmethod
    def _get_linkname_pseudo_prefix(cls):
        """
        The prefix for the name of the link used for each pseudo before the kind name
        """
        return "pseudo_"

    @classmethod
    def _get_linkname_pseudo(cls, kind):
        """
        The name of the link used for the pseudo for kind 'kind'.
        It appends the pseudo name to the pseudo_prefix, as returned by the
        _get_linkname_pseudo_prefix() method.

        :note: if a list of strings is given, the elements are appended
          in the same order, separated by underscores

        :param kind: a string (or list of strings) for the atomic kind(s) for
            which we want to get the link name
        """
        # If it is a list of strings, and not a single string: join them
        # by underscore
        if isinstance(kind, (tuple, list)):
            suffix_string = "_".join(kind)
        elif isinstance(kind, basestring):
            suffix_string = kind
        else:
            raise TypeError("The parameter 'kind' of _get_linkname_pseudo can "
                            "only be a string or a list of strings")
        return "{}{}".format(cls._get_linkname_pseudo_prefix(), suffix_string)

    @classmethod
    def get_restart_file_relative_path(cls, param_data_dict, use_castep_bin=False):
        """
        Returns a relative path of the restart file
        """
        parent_check_name = param_data_dict["PARAM"].get("check_point",  None)
        if parent_check_name is None:
            if use_castep_bin:
                parent_check_name = cls._SEED_NAME + ".castep_bin"
            else:
                parent_check_name = cls._SEED_NAME + ".check"

        return os.path.join(cls._PARENT_CALC_SUBFOLDER, parent_check_name)


    def use_pseudos_from_family(self, family_name):
        """
        Set the pseudo to use for all atomic kinds, picking pseudos from the
        family with name family_name.

        :note: The structure must already be set.

        :param family_name: the name of the group containing the pseudos
        """
        from collections import defaultdict

        try:
            structure = self._get_reference_structure()
        except AttributeError:
            raise ValueError("Structure is not set yet! Therefore, the method "
                             "use_pseudos_from_family cannot automatically set "
                             "the pseudos")

        # A dict {kind_name: pseudo_object}
        # But we want to run with use_pseudo(pseudo, kinds)

        kind_pseudo_dict = get_pseudos_from_structure(structure, family_name)

        # Group the species by pseudo
        # pseudo_dict will just map PK->pseudo_object
        pseudo_dict = {}
        # Will contain a list of all species of the pseudo with given PK
        pseudo_species = defaultdict(list)

        for kindname, pseudo in kind_pseudo_dict.iteritems():
            pseudo_dict[pseudo.pk] = pseudo
            pseudo_species[pseudo.pk].append(kindname)

        # Finally call the use_pseudo method
        for pseudo_pk in pseudo_dict:
            pseudo = pseudo_dict[pseudo_pk]
            kinds = pseudo_species[pseudo_pk]
            # I set the pseudo for all species, sorting alphabetically
            self.use_pseudo(pseudo, sorted(kinds))

    def _get_reference_structure(self):
        """
        Used to get the reference structure to obtain which
        pseudopotentials to use from a given family using
        use_pseudos_from_family.

        :note: this method can be redefined in a given subclass
               to specify which is the reference structure to consider.
        """
        return self.get_inputs_dict()[self.get_linkname('structure')]

    def get_castep_inputs(self):
        """
        Convenient fuction for getting a summary of the 
        input of this calculation
        """

        inp_dict = self.get_inputs_dict()
        in_param = inp_dict[self.get_linkname('parameters')]
        in_kpn = inp_dict[self.get_linkname('kpoints')]
        in_settings = inp_dict.get(self.get_linkname('settings'), None)
        in_structure = inp_dict[self.get_linkname('structure')]

        out_info = {}
        param_dict = in_param.get_dict()
        out_info.update(param_dict)

        out_info["kpoints"] = in_kpn.get_desc()
        out_info["structure"] = {"formula": in_structure.get_desc(),
                                 "cell": in_structure.cell,
                                 "label": in_structure.label
                                }
        if in_settings is not None:
            out_info["settings"] = in_settings.get_dict()
        out_info["label"] = self.label

        return out_info

    def compare_with(self, the_other_calc, reverse=False):
        """
        Compare with another calculation
        Look for difference in get_castep_inputs functions
        :params node: pk or uuid or node
        :params reverse: reverse the comparision, by default this node
        is the "new" and the one compared with is "old".
        """
        if isinstance(the_other_calc, (int, basestring)):
            from aiida.orm import load_node
            calc2 = load_node(the_other_calc)
        else:
            calc2 = the_other_calc

        from deepdiff import DeepDiff
        this_param = self.get_castep_inputs()
        other_param = calc2.get_castep_inputs()
        if reverse is True:
            res = DeepDiff(this_param, other_param)
        else:
            res = DeepDiff(other_param, this_param)

        # Compare the kpoints
#        this_kpt = self.get_inputs_dict()[self.get_linkname('kpoints')]
#        other_kpy = calc2.get_inputs_dict()[calc2.get_linkname('kpoints')]

        # Compare psudo
        return res


def _lowercase_dict(d, dict_name):
    """Make sure the dictionary's keys are in lower case"""
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
    """Make sure the dictionary's keys are in uppder case"""
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


def _create_restart(cin, ignore_state=False, restart_type="restart",
                    reuse=False, use_symlink=None,
                    use_output_structure=False,
                    use_castep_bin=False,
                    calc_class = None):
    """
    Method to restart the calculation by creating a new one.
    Return a new calculation with all the essential input nodes in the unstored stated.

    CASTEP has two modes of 'restart', activated by setting CONTINUATION or REUSE keywords in .param file.

    CONTINUATION
    ------------
    Restart from the end of the last run. Only limited set of parameters can be modified. If unmodifiable parameters were changed, they are ignored. E.g changes of task, nextra_bands, cut_off_energy will be ignored. This is often used for geometry optimisation or md runs.

    REUSE
    -----
    Essentially making a new calculation with parameters read from .cell and .param file.
    Data from *.castep_bin or *.check will be used to initialise te model of the new run. This is often used for bandstructure, dos, spectral calculation.

    Note both castep_bin and check file may be used.
    They are almost the same except castep_bin does not have wavefunctions stored.


    :param bool ignore_state: Ignore the state of parent calculation
    :param str restart_type: "continuation" or "restart". If set to continuation the child calculation has keyword 'continuation' set.
    :param bool reuse: Wether we want to reuse the previous calculation.
    only applies for "restart" run
    :param bool parent_folder_symlink: if True, symlink are used instead of hard copies of the files. Default given be cin._default_symlink_usage
    :param bool use_output_structure: if True, the output structure of parent calculation is used as the input of the child calculation.
    This is useful for photon/bs calculation.
    """

    from aiida.common.datastructures import calc_states

    if cin.get_state(from_attribute=True) != calc_states.FINISHED:
        if not ignore_state:
            raise InputValidationError(
                "Calculation to be restarted must be in the {} state."
                "use ignore_state keyword to override this".format(calc_states.FINISHED))

    if restart_type == "continuation":
        # If we do a conitniuation we actually have to re-use the file from previous run
        reuse = True

    if use_symlink is None:
        use_symlink = cin._default_symlink_usage

    calc_inp = cin.get_inputs_dict()  # Input nodes of parent calculation

    remote_folders = cin.get_outputs(node_type=RemoteData)

    if reuse:
        if len(remote_folders) > 1:
            raise InputValidationError("More than one output RemoteData found "
                                   "in calculation {}".format(cin.pk))
        if len(remote_folders) == 0:
            raise InputValidationError("No output RemoteData found "
                                   "in calculation {}".format(cin.pk))

    # Duplicate the calculation
    if calc_class is None:
        cout = cin.copy()
    else:
        cout = calc_class()
        cout.set_computer(cin.get_computer())

    # Setup remote folderes
    if reuse:
        remote_folder = remote_folders[0]
        cout._set_parent_remotedata(remote_folder)

    # Use the out_put structure if required
    if use_output_structure:
        try:
            cout.use_structure(cin.out.output_structure)
        except AttributeError:
            cout.logger.warning("Warning: No output structure found. Fallback to input structure")
            cout.use_structure(calc_inp[cin.get_linkname('structure')])
    else:
        cout.use_structure(calc_inp[cin.get_linkname('structure')])

    # Copy the kpoints
    # NOTE this need to be changed for restarting BS with bs_kpoints etc
    # Move to another method to allow subclass modification
    if cin._use_kpoints:
        cout.use_kpoints(calc_inp[cin.get_linkname('kpoints')])
    cout.use_code(calc_inp[cin.get_linkname('code')])

    # copy the settings dictionary
    try:
        old_settings_dict = calc_inp[cin.get_linkname('settings')].get_dict()
    except KeyError:
        old_settings_dict = {}

    # Use deep copy to ensure two dictionaries are independent
    new_settings = copy.deepcopy(old_settings_dict)

    if use_symlink != cout._default_symlink_usage:
        new_settings['PARENT_FOLDER_SYMLINK'] = use_symlink

    if new_settings:
        if new_settings != old_settings_dict:
            # Link to an new settings
            settings = ParameterData(dict=new_settings)
            cout.use_settings(settings)
        else:
            # Nothing changed, just use the old settings
            cout.use_settings(calc_inp[cin.get_linkname('settings')])

    # SETUP the keyword in PARAM file
    parent_param = calc_inp[cin.get_linkname('parameters')]

    if reuse:
        in_param_dict = parent_param.get_dict()
        if restart_type == "restart":
            # Set keyword reuse, pop any continuation keywords
            in_param_dict['PARAM'].pop('continuation', None)
            # Define the name of reuse here
            in_param_dict['PARAM']["reuse"] = cin.get_restart_file_relative_path(in_param_dict, use_castep_bin)
        elif restart_type == "continuation":
            # Do the opposite
            in_param_dict['PARAM'].pop('reuse', None)
            in_param_dict['PARAM']['continuation'] = cin.get_restart_file_relative_path(in_param_dict, use_castep_bin)
        cout.use_parameters(ParameterData(dict=in_param_dict))
    else:
        # In this case we simply create a identical calculation
        cout.use_parameters(parent_param)

    # Use exactly the same pseudopotential data
    for linkname, input_node in cin.get_inputs_dict().iteritems():
        if isinstance(input_node, (UpfData, UspData, OTFGData)):
            cout.add_link_from(input_node, label=linkname)

    return cout

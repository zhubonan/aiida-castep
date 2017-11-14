# -*- coding: utf-8 -*-
"""
Base module for calculations
"""

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
from .utils import get_castep_ion_line


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
                'linkname': cls._get_linkname_pseudo,
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
        cell_vector_list = ["%BLOCK LATTICE_CART"]
        for vector in structure.cell:
            cell_vector_list.append( ("{0:18.10f} {1:18.10f} "
                                          "{2:18.10f}".format(*vector)))

        cell_vector_list.append("%ENDBLOCK LATTICE_CART")

        # --------- ATOMIC POSITIONS---------
        # for kind in structure.kinds:
        atomic_position_list = ["%BLOCK POSITIONS_ABS"]
        mixture_count = 0
        for i, site in enumerate(structure.sites):
            # get  the kind of the site
            kind = structure.get_kind(site.kind_name)

            # Position is always needed
            pos = site.position
            try:
                name = kind.symbol
            # If we are dealing with mixed atoms
            except ValueError:
                name = kind.symols
                mixture_count += 1

            # deal with initial spins
            spin_array = settings_dict.get("SPINS")

            if spin_array:
                spin = spin_array[i]
            else:
                spin = None

            # deal with labels
            label_array = settings_dict.get("LABELS")
            if label_array:
                label = label_array[i]
            else:
                label=None

            line = get_castep_ion_line(name, pos, label=label, spin=spin,
                occupation=kind.weights, num_mix=mixture_count)

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
                    weights = [1.] / num_kpoints

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

        # --------- PSUDOPOTENTIALS --------
        # Check if we are using UPF pseudos
        # Now only support simple elemental pseudopotentials
        if pseudos:
            symbols = set()  # All of the symbols
            species_pot_list = ["%BLOCK SPECEIS_POT"]
            for kind in structure.kinds:
                for s in kind.symbols:
                    symbols.add(s)

            # Make symbols unique
            for s in symbols:
                ps = pseudos[s]  # Get the pseupotential object
                species_pot_list.append("{} {}".format(s, ps.filename))
                # Add to the copy list
                local_copy_list_to_append.append((ps.get_file_abs_path(), ps.filename))

            species_pot_list.append("%ENDBLOCK SPECIES_POT")

        # --------- PARAMETERS in cell file---------
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

        ### Parameters for PARAM files ###

        param_entry_list = []
        for key, value in input_params["PARAM"].iteritems():

            entry = "{} : {}".format(key, value)
            param_entry_list.append(entry)

        param_entries = "\n".join(param_entry_list)

        #### PUTTING THINGS TOGETHER ####
        cellfile_list = []
        cellfile_list.extend(cell_vector_list + ["\n"])
        cellfile_list.extend(atomic_position_list + ["\n"])
        cellfile_list.extend(kpoints_card_list + ["\n"])
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
        #remote_copy_list = []
        #remote_symlink_list = []

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

        # Set up pseodo potentials
        # The existance of pseudopoential is optional
        pseudos = {}
        # I create here a dictionary that associates each kind name to a pseudo
        for link in inputdict.keys():
            if link.startswith(self._get_linkname_pseudo_prefix()):
                kindstring = link[len(self._get_linkname_pseudo_prefix()):]
                kinds = kindstring.split('_')
                the_pseudo = inputdict.pop(link)
                if not isinstance(the_pseudo, UpfData):
                    raise InputValidationError("Pseudo for kind(s) {} is not of "
                                               "type UpfData".format(",".join(kinds)))
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
        cell_input, param_input, pseudo_copy_list = self._generate_CASTEPinputdata(parameters,
            settings_dict, pseudos, structure, kpoints)

        local_copy_list.append(pseudo_copy_list)

        cell_input_filename = tempfolder.get_abs_path(self._SEED_NAME + ".cell")
        param_input_filename = tempfolder.get_abs_path(self._SEED_NAME + ".param")

        with open(cell_input_filename, "w") as incell:
            incell.write(cell_input)

        with open(param_input_filename, "w") as inparam:
            inparam.write(param_input)

        # TODO: IMPLEMENT OPERATIONS FOR RESTART

        calcinfo = CalcInfo()

        calcinfo.uuid = self.uuid
        calcinfo.local_copy_list = local_copy_list

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
        kind_pseudo_dict = get_pseudos_from_structure(structure, family_name)

        # We have to group the species by pseudo, I use the pseudo PK
        # pseudo_dict will just map PK->pseudo_object
        pseudo_dict = {}
        # Will contain a list of all species of the pseudo with given PK
        pseudo_species = defaultdict(list)

        for kindname, pseudo in kind_pseudo_dict.iteritems():
            pseudo_dict[pseudo.pk] = pseudo
            pseudo_species[pseudo.pk].append(kindname)

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

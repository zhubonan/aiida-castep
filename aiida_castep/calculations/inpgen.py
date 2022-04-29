"""
Module for generating text based CASTEP inputs
"""
import numpy as np
from castepinput.inputs import CellInput, ParamInput

from aiida.common import InputValidationError, MultipleObjectsError
from aiida_castep.common import INPUT_LINKNAMES as in_ln

from .utils import get_castep_ion_line, _lowercase_dict, _uppercase_dict
from ..data.otfg import OTFGData

# pylint: disable=no-member, too-many-locals, too-many-statements, too-many-branches


class CastepInputGenerator:
    """
    Class for generating CASTEP inputs
    """
    def __init__(self):
        """
        Initialise the object
        """
        # Initialize the underlying cell file and param file
        # objects
        self.param_file = ParamInput()
        self.cell_file = CellInput()
        self.local_copy_list_to_append = set()
        self.param_dict = {}
        self.settings_dict = {}

    def prepare_inputs(self, reset=True):
        """
        Prepare the inputs
        :param reset: Rest existing self.param_file and self.cell file
        """
        if reset:
            self.param_file = ParamInput()
            self.cell_file = CellInput()

        self.local_copy_list_to_append = set()
        param_dict = self.inputs[in_ln['parameters']].get_dict()
        settings_node = self.inputs.get('settings', None)
        settings_dict = settings_node.get_dict() if settings_node else {}

        # Standardise top level keys should be CAPITALIZED
        param_dict = _uppercase_dict(param_dict, dict_name="parameters")
        # Second level keys should be lowercased
        param_dict = {
            k: _lowercase_dict(v, dict_name=k)
            for k, v in param_dict.items()
        }

        # Set iprint to 1
        param_dict["PARAM"]["iprint"] = param_dict["PARAM"].get("iprint", 1)

        # Set run_time using define value for this calculation
        run_time = self.inputs.metadata.options.get('max_wallclock_seconds')
        if run_time:
            n_seconds = run_time * 0.95
            n_seconds = (n_seconds //
                         60) * 60  # Round down to the nearest minutes
            # Do not do any thing if calculated time is less than 1 hour
            if n_seconds < 180:
                pass
            elif "run_time" not in param_dict["PARAM"]:
                param_dict["PARAM"]["run_time"] = int(n_seconds)

        # Set the default comment using the label of this calculation
        comment_str = self.inputs.metadata.get('label', None)
        if "comment" not in param_dict["PARAM"] and comment_str:
            param_dict["PARAM"]["comment"] = comment_str

        # Expose at the instance level
        self.param_dict = param_dict
        self.settings_dict = settings_dict

        # prepare the cell and param files
        self._prepare_cell_file()
        self._prepare_param_file()

    def _prepare_cell_file(self):
        """
        Prepare the cell file
        """

        cell_vector_list = []
        for vector in self.inputs[in_ln['structure']].cell:
            cell_vector_list.append(("{0:18.10f} {1:18.10f} "
                                     "{2:18.10f}".format(*vector)))

        self.cell_file["LATTICE_CART"] = cell_vector_list

        # --------- ATOMIC POSITIONS---------
        # for kind in self.inputs[in_ln['structure']].kinds:
        atomic_position_list = []
        mixture_count = 0
        # deal with initial spins
        spin_list = self.settings_dict.pop("SPINS", None)
        label_list = self.settings_dict.pop("LABELS", None)

        for i, site in enumerate(self.inputs[in_ln['structure']].sites):
            # get  the kind of the site
            kind = self.inputs[in_ln['structure']].get_kind(site.kind_name)

            # Position is always needed
            pos = site.position
            mixture = False
            try:
                name = kind.symbol
            # If we are dealing with mixed atoms
            except ValueError:
                name = kind.symbols
                mixture_count += 1
                mixture = True

            # If the symbol is not the same as the kindname
            # e.g there are inequivalent atoms of the same element
            # We change the name to '<symbol>:<kind.name>'
            if not mixture:
                # Only do this if the name(symbol) is not equal to the kindname
                if name != kind.name:
                    name = name + ':' + kind.name
            else:
                # If we are dealing with the mixtures,
                # we also add the kindname as an identifier
                name = [ntemp + ':' + kind.name for ntemp in name]

            if spin_list:
                spin = spin_list[i]
            else:
                spin = None

            # deal with labels
            if label_list:
                label = label_list[i]
            else:
                label = None

            # Get the line of positions_abs block
            line = get_castep_ion_line(name,
                                       pos,
                                       label=label,
                                       spin=spin,
                                       occupation=kind.weights,
                                       mix_num=mixture_count)

            # Append the line to the list
            atomic_position_list.append(line)

        # End of the atomic position block
        self.cell_file["POSITIONS_ABS"] = atomic_position_list

        # Check the consistency of spin in parameters
        if spin_list:
            # In case of non-collinear spin
            if isinstance(spin_list[0], (list, tuple)):
                total_spin = np.linalg.norm(spin_list, axis=1).sum()
            else:
                total_spin = sum(s for s in spin_list if s)
            param_spin = self.param_dict["PARAM"].get("spin", None)
            if param_spin is not None:
                # If spin is specified - check consistency
                if param_spin != total_spin:
                    raise InputValidationError(
                        "Inconsistent spin in cell and param files."
                        "Total spin: {} in cell file but {} in param file".
                        format(total_spin, param_spin))
            else:
                # If no spin specified, do it automatically
                # Note that we don't check if spin polarized calculation is
                # requested in the first place
                # self.param_dict["PARAM"]["spin"] = total_spin
                # Explicitly setting `spin` is not need since 18.1 - having those in CELL
                # is enough
                pass
            # Validate if spin_treatment: vector is activated.

        # --------- KPOINTS ---------
        kpoints = self.inputs.get('kpoints')
        use_kpoints = self.inputs.metadata.options.use_kpoints
        if not kpoints and use_kpoints:
            raise InputValidationError(
                'Kpoints required but not found in the input')

        if self.inputs.metadata.options.use_kpoints:
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
                    weights = np.ones(num_kpoints, dtype=float) / num_kpoints

            kpoints_line_list = []
            if has_mesh is True:
                self.cell_file["kpoints_mp_grid"] = "{} {} {}".format(*mesh)
                if offset != [0., 0., 0.]:
                    self.cell_file["kpoints_mp_offset"] = "{} {} {}".format(
                        *offset)
            else:
                for kpoint, weight in zip(kpoints_list, weights):
                    kpoints_line_list.append("{:18.10f} {:18.10f} "
                                             "{:18.10f} {:18.10f}".format(
                                                 kpoint[0], kpoint[1],
                                                 kpoint[2], weight))
                self.cell_file["KPOINTS_LIST"] = kpoints_line_list

        # --------- keywords in cell file---------
        for key, value in self.param_dict["CELL"].items():

            if "species_pot" in key:
                raise MultipleObjectsError(
                    "Pseudopotentials should not be specified directly")

            # Constructing block keywords
            # We identify the key should be treated as a block it
            # is not a string and has len() > 0
            self.cell_file[key] = value

        self._prepare_pseudo_potentials()

    def _include_extra_kpoints(self,
                               kpn_node,
                               kpn_name,
                               kpn_settings,
                               report_fn=None):
        """Write extra kpoints to the cell"""

        try:
            mesh, offset = kpn_node.get_kpoints_mesh()
            has_mesh = True
        except AttributeError:
            # Not defined as mesh
            try:
                bs_kpts_list = kpn_node.get_kpoints()
                num_kpoints = len(bs_kpts_list)
                has_mesh = False
                if num_kpoints == 0:
                    raise InputValidationError(
                        "At least one k points must be provided")
            except AttributeError:
                raise InputValidationError(
                    "No valid {}_kpoints have been found from node {}".format(
                        kpn_name.lower(), kpn_node.pk))

            # Do we have weights defined?
            try:
                _, weights = kpn_node.get_kpoints(also_weights=True)
            except AttributeError:
                # If not, fill with fractions
                if kpn_settings['need_weights'] is True:
                    weights = np.ones(num_kpoints, dtype=float) / num_kpoints
                    if report_fn is not None:
                        report_fn(
                            'Warning:filling evenly distributed weights for {}_kpoints'
                            .format(kpn_name))

        # now add to the cell file
        if has_mesh is True:
            mesh_name = "{}_kpoint_mp_grid".format(kpn_name)
            self.cell_file[mesh_name] = "{} {} {}".format(*mesh)
            if offset != [0., 0., 0.]:
                self.cell_file[mesh_name.replace(
                    "grid", "offset")] = "{} {} {}".format(*offset)
        else:
            extra_kpts_lines = []
            if kpn_settings['need_weights'] is True:
                for kpoint, weight in zip(bs_kpts_list, weights):
                    extra_kpts_lines.append(
                        f"{kpoint[0]:18.10f} {kpoint[1]:18.10f} {kpoint[2]:18.10f} {weight:18.14f}"
                    )
            else:
                for kpoint in bs_kpts_list:
                    extra_kpts_lines.append(
                        f"{kpoint[0]:18.10f} {kpoint[1]:18.10f} {kpoint[2]:18.10f}"
                    )
            bname = "{}_kpoint_list".format(kpn_name).upper()
            self.cell_file[bname] = extra_kpts_lines

    def _prepare_pseudo_potentials(self):
        """
        Prepare the pseudopotential part of the cell file
        """

        # --------- PSEUDOPOTENTIALS --------
        # Check if we are using UPF pseudos
        # Now only support simple elemental pseudopotentials

        species_pot_map = {}
        pseudos = self.inputs.pseudos
        # Make kindname unique
        for kind in self.inputs[in_ln['structure']].kinds:
            symbols = kind.symbols
            # If the site has multiple symbols, add all of them to the list
            mixture = False
            if len(symbols) > 1:
                mixture = True
            for symbol in symbols:
                if symbol == kind.name:
                    pseudo_name = symbol
                else:
                    pseudo_name = symbol + ':' + kind.name

                if not mixture:
                    # Get the pseudopotential is defined by the kind.name
                    ps_node = pseudos[kind.name]
                else:
                    # If with mixture the pseudopotential is deined as '<kind_name>_<symbol>'
                    ps_node = pseudos[kind.name + '_' + symbol]

                # If we are using OTFG, just add the string property of it
                if isinstance(ps_node, OTFGData):
                    species_pot_map[pseudo_name] = "{:5} {}".format(
                        pseudo_name, ps_node.string)
                else:
                    # If we are dealing with file based pseudopotentials objects
                    # Add the specification to the file
                    try:
                        species_pot_map[pseudo_name] = "{:5} {}".format(
                            pseudo_name, ps_node.filename)
                        # Add to the copy list
                        self.local_copy_list_to_append.add(
                            (ps_node.uuid, ps_node.filename, ps_node.filename))
                    except Exception as error:
                        raise InputValidationError(
                            'Unknown node as pseudo: {}. Exception raised: {}'.
                            format(ps_node, error))

        # Ensure it is a list
        self.cell_file["SPECIES_POT"] = list(species_pot_map.values())

    def _prepare_param_file(self):
        """
        Prepare the content of PARAM file
        """
        self.param_file.update(self.param_dict["PARAM"])

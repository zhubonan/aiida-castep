"""
Parsers for CASTEP
"""
from typing import Union, List
from pathlib import Path
from contextlib import contextmanager
from copy import deepcopy

import numpy as np

from aiida.orm import TrajectoryData, ArrayData, Dict, BandsData

from aiida.parsers.parser import Parser
from aiida.common import exceptions
from aiida_castep.parsers.castep_bin import CastepbinFile

from aiida_castep.parsers.raw_parser import units, RawParser
from aiida_castep.parsers.utils import (structure_from_input,
                                        add_last_if_exists, desort_structure,
                                        get_desort_args)
from aiida_castep.common import OUTPUT_LINKNAMES as out_ln
from aiida_castep.common import EXIT_CODES_SPEC as calc_exit_code
from aiida_castep._version import CALC_PARSER_VERSION

# pylint: disable=invalid-name,too-many-locals,too-many-statements,too-many-branches
__version__ = CALC_PARSER_VERSION

ERR_FILE_WARNING_MSG = ".err files found in workdir"

# Tasks where the bands (eigenvalues) that oen is interested in is not those
# from the SCF calculation. In these cases, we have to get the bands from the .bands
# file instead of the castep_bin/check outputs, since the latter only stored those
# of the electronic ground state calculation (SCF
NON_SCF_BAND_TASKS = ('spectral', 'bandstructure', 'optics')


class RetrievedFileManager:
    """
    Wrapper for supplying an unified file-handler interface for the retrieved content
    """
    def __init__(self, retrieved_node, retrieved_temporary_folder=None):
        """
        Instantiate the manager object
        """
        self.node = retrieved_node
        if retrieved_temporary_folder is not None:
            self.tmp_folder = Path(retrieved_temporary_folder)
            # Store the relative paths as strings
            self.tmp_content_names = list(
                map(lambda x: str(x.relative_to(self.tmp_folder)),
                    self.tmp_folder.iterdir()))
        else:
            self.tmp_folder = None
            self.tmp_content_names = []

        self.perm_content_names = self.node.list_object_names()
        self.all_content_names = self.perm_content_names + self.tmp_content_names

    @contextmanager
    def open(self, name, mode='r'):
        """Open a file from either the retrieved node or the temporary folder"""
        if name in self.perm_content_names:
            with self.node.open(name, mode=mode) as handle:
                yield handle
        elif name in self.tmp_content_names:
            with open(self.tmp_folder / name, mode=mode) as handle:
                yield handle
        else:
            raise FileNotFoundError(f"Object {name} is not found!")

    def has_file(self, name) -> bool:
        """Return if we have this file"""
        return name in self.all_content_names

    def list_object_names(self) -> List[str]:
        """Return all object names avalaible"""
        return self.all_content_names

    def get_object_content(self, name, mode='r') -> Union[str, bytes]:
        with self.open(name, mode=mode) as handle:
            return handle.read()


class CastepParser(Parser):
    """
    This is the class for Parsing results from a CASTEP calculation
    Supported calculations types:
    singlepoint
    geom
    """

    _setting_key = 'parser_options'

    @property
    def castep_input_parameters(self):
        """Access the original castep input parameters """
        return self.node.inputs.parameters.get_dict()

    @property
    def castep_task(self):
        """Task of the calculation"""
        return self.castep_input_parameters['PARAM'].get('task', 'singlepoint')

    def parse(self, **kwargs):
        """
        Receives a dictionary of retrieved nodes.retrieved.
        Top level logic of operation
        """

        try:
            retrieved = self.retrieved
        except exceptions.NotExistent:
            return self.exit_codes.ERROR_NO_RETRIEVED_FOLDER

        output_folder = RetrievedFileManager(
            retrieved, kwargs.get('retrieved_temporary_folder'))

        warnings = []
        exit_code_1 = None

        # NOTE parser options not used for not
        parser_opts = {}

        # NOT READILY IN USE
        input_dict = {}

        # check what is inside the folder
        filenames = output_folder.list_object_names()

        # Get calculation options
        options = self.node.get_options()
        seedname = options['seedname']

        # at least the stdout should exist
        if options['output_filename'] not in filenames:
            self.logger.error("Standard output not found")
            return self.exit_codes.ERROR_NO_OUTPUT_FILE

        # The calculation is failed if there is any err file.
        err_filenames = [fname for fname in filenames if '.err' in fname]
        if err_filenames:
            exit_code_1 = 'ERROR_CASTEP_ERROR'

        # Add the content of err files
        err_contents = set()
        for fname in err_filenames:
            err_contents.add(output_folder.get_object_content(fname))

        # Trajectory files
        has_md_geom = False
        out_md_geom_name_content = None
        for suffix in ('.geom', '.md'):
            fname = seedname + suffix
            if fname in filenames:
                out_md_geom_name_content = (
                    fname, output_folder.get_object_content(fname).split('\n'))
                has_md_geom = True
                break

        # Handling bands
        fname = seedname + '.bands'
        has_bands = fname in filenames
        if has_bands:
            out_bands_content = output_folder.get_object_content(fname).split(
                '\n')
        else:
            out_bands_content = None

        out_file = options['output_filename']
        out_file_content = output_folder.get_object_content(out_file).split(
            '\n')

        ###### CALL THE RAW PASSING FUNCTION TO PARSE DATA #######

        raw_parser = RawParser(out_lines=out_file_content,
                               input_dict=input_dict,
                               md_geom_info=out_md_geom_name_content,
                               bands_lines=out_bands_content,
                               **parser_opts)
        out_dict, trajectory_data, structure_data, bands_data, exit_code_2\
            = raw_parser.parse()

        # Combine the exit codes use the more specific error
        exit_code = None
        for code in calc_exit_code:
            if code in (exit_code_2, exit_code_1):
                exit_code = code
                break

        # Append the final value of trajectory_data into out_dict
        last_value_keys = [
            "free_energy", "total_energy", "zero_K_energy", "spin_density",
            "abs_spin_density", "enthalpy"
        ]
        for key in last_value_keys:
            add_last_if_exists(trajectory_data, key, out_dict)

        # Add warnings from this level
        out_dict["warnings"].extend(warnings)

        # Add error messages
        out_dict["error_messages"] = list(err_contents)

        ######## --- PROCESSING BANDS DATA -- ########
        if has_bands or output_folder.has_file(seedname + '.castep_bin'):
            # Only use castep_bin if we are interested in SCF kpoints
            if output_folder.has_file(seedname + '.castep_bin') and (
                    self.castep_task.lower() not in NON_SCF_BAND_TASKS):
                self.logger.info("Using castep_bin file for the bands data.")
                bands_node = bands_from_castepbin(seedname, output_folder)
                if not self._has_empty_bands(bands_node):
                    # Set if no other errors
                    out_dict["warnings"].append(
                        "At least one kpoint has no empty bands, energy/forces returned are not reliable."
                    )
                    if exit_code == 'CALC_FINISHED':
                        exit_code = "ERROR_NO_EMPTY_BANDS"
            else:
                bands_node = bands_to_bandsdata(**bands_data)
            self.out(out_ln['bands'], bands_node)

        ######## --- PROCESSING STRUCTURE DATA --- ########
        no_optimise = False
        try:
            cell = structure_data["cell"]
            positions = structure_data["positions"]
            symbols = structure_data["symbols"]

        except KeyError:
            # Handle special case where CASTEP founds nothing to optimise,
            # hence we attached the input geometry as the output
            for warning in out_dict["warnings"]:
                if "there is nothing to optimise" in warning:
                    no_optimise = True
            if no_optimise is True:
                self.out(out_ln['structure'],
                         deepcopy(self.node.inputs.structure))
        else:
            structure_node = structure_from_input(cell=cell,
                                                  positions=positions,
                                                  symbols=symbols)
            # Use the output label as the input label
            input_structure = self.node.inputs.structure
            structure_node = desort_structure(structure_node, input_structure)
            structure_node.label = input_structure.label
            self.out(out_ln['structure'], structure_node)

        ######### --- PROCESSING TRAJECTORY DATA --- ########
        # If there is anything to save
        # It should...
        if trajectory_data:

            # Resorting indices - for recovering the original ordering of the
            # species in the input structure
            input_structure = self.node.inputs.structure
            idesort = get_desort_args(input_structure)
            # If we have .geom file, save as in a trajectory data
            if has_md_geom:
                try:
                    positions = np.asarray(
                        trajectory_data["positions"])[:, idesort]
                    cells = trajectory_data["cells"]
                    # Assume symbols do not change - symbols are the same for all frames
                    symbols = np.asarray(trajectory_data["symbols"])[idesort]
                    stepids = np.arange(len(positions))

                except KeyError:
                    out_dict["parser_warning"].append(
                        "Cannot "
                        "extract data from .geom file.")

                else:
                    traj = TrajectoryData()
                    traj.set_trajectory(stepids=np.asarray(stepids),
                                        cells=np.asarray(cells),
                                        symbols=np.asarray(symbols),
                                        positions=np.asarray(positions))
                    # Save the rest
                    for name, value in trajectory_data.items():
                        # Skip saving empty arrays
                        if len(value) == 0:
                            continue

                        array = np.asarray(value)
                        # For forces/velocities we also need to resort the array
                        if ("force" in name) or ("velocities" in name):
                            array = array[:, idesort]
                        traj.set_array(name, np.asarray(value))
                    self.out(out_ln['trajectory'], traj)

            # Or may there is nothing to optimise? still save a Trajectory data
            elif no_optimise is True:
                traj = TrajectoryData()
                input_structure = self.node.inputs.structure
                traj.set_trajectory(stepids=np.asarray([1]),
                                    cells=np.asarray([input_structure.cell]),
                                    symbols=np.asarray([
                                        site.kind_name
                                        for site in input_structure.sites
                                    ]),
                                    positions=np.asarray([[
                                        site.position
                                        for site in input_structure.sites
                                    ]]))
                # Save the rest
                for name, value in trajectory_data.items():
                    # Skip saving empty arrays
                    if len(value) == 0:
                        continue

                    array = np.asarray(value)
                    # For forces/velocities we also need to resort the array
                    if ("force" in name) or ("velocities" in name):
                        array = array[:, idesort]
                    traj.set_array(name, np.asarray(value))
                self.out(out_ln['trajectory'], traj)
            # Otherwise, save data into a ArrayData node
            else:
                out_array = ArrayData()
                for name, value in trajectory_data.items():
                    # Skip saving empty arrays
                    if len(value) == 0:
                        continue
                    array = np.asarray(value)
                    if ("force" in name) or ("velocities" in name):
                        array = array[:, idesort]
                    out_array.set_array(name, np.asarray(value))
                self.out(out_ln['array'], out_array)

        ######## ---- PROCESSING OUTPUT DATA --- ########
        output_params = Dict(dict=out_dict)
        self.out(out_ln['results'], output_params)

        # Return the exit code
        return self.exit_codes.__getattr__(exit_code)

    def _has_empty_bands(self, bands_data: BandsData, thresh=0.005):
        """
        Check for the occupation of the BandsData

        There should be some empty bands if the calculation is a not a fixed occupation one.
        Otherwise, the final energy and forces are not reliable.
        """

        # Check if occupation is allowed to vary
        param = self.node.inputs.parameters.get_dict()['PARAM']
        # If it is a fixed occupation calculation we do not need to do anything about it....
        fix_occ = (param.get('fix_occupancy', False)
                   or param.get('metals_method', 'dm').lower() == 'none'
                   or param.get('elec_method', 'dm').lower() == 'none')
        if fix_occ:
            return True

        _, occ = bands_data.get_bands(also_occupations=True)

        nspin, nkppts, _ = occ.shape
        problems = []
        for ispin in range(nspin):
            for ikpts in range(nkppts):
                if occ[ispin, ikpts, -1] >= thresh:
                    problems.append((ispin, ikpts, occ[ispin, ikpts, -1]))
        if problems:
            for ispin, ikpts, val in problems:
                self.logger.warning(
                    "No empty bands for spin %d, kpoint %d - occ: %.5f", ispin,
                    ikpts, val)
            return False
        return True


def bands_to_bandsdata(bands_info, kpoints, bands):
    """
    Convert the result of parser_dot_bands into a BandsData object

    :param bands_info: A dictionary of the informations of the bands file.
      contains field such as eferemi, units, cell
    :param kpoints: An array of the kpoints of the bands, rows are
      (kindex, kx, ky, kz, weight)
    :param bands: The actual bands array
    :return: A BandsData object
    :rtype: ``aiida.orm.bands.data.array.bands.BandsData``
    """

    bands_node = BandsData()

    # Extract the index of the kpoints
    kpn_array = np.asarray(kpoints)
    k_index = kpn_array[:, 0]

    # We need to restore the order of the kpoints
    k_sort = np.argsort(k_index)
    # Sort the kpn_array
    kpn_array = kpn_array[k_sort]

    _weights = kpn_array[:, -1]
    kpts = kpn_array[:, 1:-1]
    bands_node.set_kpoints(kpts, weights=_weights)

    # Sort the bands to match the order of the kpoints
    bands_array = np.asarray(bands)[k_sort]
    # We need to swap the axes from kpt,spin,engs to spin,kpt,engs
    bands_array = bands_array.swapaxes(0, 1)

    # Squeeze the first dimension e.g when there is a single spin
    if bands_array.shape[0] == 1:
        bands_array = bands_array[0]
    bands_array = bands_array * units['Eh']
    bands_info = dict(bands_info)  # Create a copy
    # Convert the units for the fermi energies
    if isinstance(bands_info['efermi'], list):
        bands_info['efermi'] = [x * units['Eh'] for x in bands_info['efermi']]
    else:
        bands_info['efermi'] = bands_info['efermi'] * units['Eh']

    bands_node.set_bands(bands_array, units="eV")
    # PBC is always true as this is PW DFT....
    bands_node.set_cell(bands_info['cell'], pbc=(True, True, True))

    # Store information from *.bands in the attributes
    # This is needs as we need to know the number of electrons
    # and the fermi energy
    for key, value in bands_info.items():
        bands_node.set_attribute(key, value)
    return bands_node


def bands_from_castepbin(seedname, fmanager):
    """
    Acquire and prepare bands data from the castep_bin file instead
    """

    with fmanager.open(seedname + '.castep_bin', 'rb') as handle:
        binfile = CastepbinFile(fileobj=handle)

    bands_node = BandsData()
    kidx = binfile.kpoints_indices
    sort_idx = np.argsort(kidx)
    # Generated sorted arrays
    kpoints = binfile.kpoints[sort_idx, :]
    weights = binfile.kpoint_weights[sort_idx].astype(float)
    eigenvalues = binfile.eigenvalues[:, sort_idx, :]
    occupancies = binfile.occupancies[:, sort_idx, :]
    efermi = binfile.fermi_energy

    bands_node.set_kpoints(kpoints, weights=weights)
    bands_node.set_bands(eigenvalues, occupations=occupancies, units="eV")
    bands_node.set_cell(binfile.cell, pbc=(True, True, True))
    bands_node.set_attribute('efermi', efermi)

    return bands_node

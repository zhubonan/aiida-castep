"""
Parsers for CASTEP
"""
from __future__ import absolute_import
from aiida.plugins import DataFactory
from aiida.parsers.parser import Parser  # , ParserParamManager
from aiida_castep.parsers.raw_parser import parse_raw_ouput, units, RawParser
from aiida_castep.parsers.raw_parser import __version__ as raw_parser_version
from aiida_castep.parsers.utils import (structure_from_input,
                                        add_last_if_exists, desort_structure,
                                        get_desort_args)
from aiida_castep.common import OUTPUT_LINKNAMES as out_ln
from aiida_castep.common import EXIT_CODES_SPEC as calc_exit_code
from aiida_castep._version import CALC_PARSER_VERSION
import six
__version__ = CALC_PARSER_VERSION

Dict = DataFactory("dict")
BandsData = DataFactory("array.bands")

ERR_FILE_WARNING_MSG = ".err files found in workdir"

# No need to have consistent raw parser version
#assert __version__ == raw_parser_version, "Inconsistent version numbers"


class CastepParser(Parser):
    """
    This is the class for Parsing results from a CASTEP calculation
    Supported calculations types:
    signlepoint
    geom
    """

    _setting_key = 'parser_options'

    def parse(self, **kwargs):
        """
        Receives a dictionary of retrieved nodes.retrieved.
        Top level logic of operation
        """
        from aiida.common import exceptions
        import os

        try:
            output_folder = self.retrieved
        except exceptions.NotExistent:
            return self.exit_codes.ERROR_NO_RETRIEVED_FOLDER

        warnings = []
        exit_code_1 = None

        # TODO Enable parser options
        parser_opts = {}

        # NOT READLLY IN USE
        input_dict = {}

        # check what is inside the folder
        filenames = [f.name for f in output_folder.list_objects()]

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
        # out_dict, trajectory_data, structure_data, bands_data, exit_code\
        #     = parse_raw_ouput(out_lines=out_file_content,
        #                       input_dict=input_dict,
        #                       parser_opts=parser_opts,
        #                       md_geom_lines=out_md_geom_name_content,
        #                       bands_lines=out_bands_content)

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
        if has_bands:
            bands_node = bands_to_bandsdata(**bands_data)
            self.out(out_ln['bands'], bands_node)

        ######## --- PROCESSING STRUCTURE DATA --- ########
        try:
            cell = structure_data["cell"]
            positions = structure_data["positions"]
            symbols = structure_data["symbols"]

        except KeyError:
            # No final structure can be used - that is OK
            pass
        else:
            structure_node = structure_from_input(cell=cell,
                                                  positions=positions,
                                                  symbols=symbols)
            calc_in = self.node
            # Use the output label as the input label
            input_structure = calc_in.inputs.structure
            structure_node = desort_structure(structure_node, input_structure)
            structure_node.label = input_structure.label
            self.out(out_ln['structure'], structure_node)

        ######### --- PROCESSING TRAJECTORY DATA --- ########
        # If there is anything to save
        # It should...
        if trajectory_data:

            import numpy as np
            from aiida.orm.nodes.data.array.trajectory import TrajectoryData
            from aiida.orm.nodes.data.array import ArrayData

            # If we have .geom file, save as in a trajectory data
            if has_md_geom:
                try:
                    idesort = get_desort_args(input_structure)
                    positions = np.asarray(
                        trajectory_data["positions"])[:, idesort]
                    cells = trajectory_data["cells"]
                    symbols = np.asarray(trajectory_data["symbols"])[idesort]
                    stepids = np.arange(len(positions))

                except KeyError:
                    out_dict["parser_warning"].append(
                        "Cannot "
                        "extract data from .geom file.")
                    pass

                else:
                    traj = TrajectoryData()
                    traj.set_trajectory(stepids=np.asarray(stepids),
                                        cells=np.asarray(cells),
                                        symbols=np.asarray(symbols),
                                        positions=np.asarray(positions))
                    # Save the rest
                    for name, value in six.iteritems(trajectory_data):
                        # Skip saving empty arrays
                        if len(value) > 0:
                            traj.set_array(name, np.asarray(value))
                    self.out(out_ln['trajectory'], traj)

            # Otherwise, save data into a ArrayData node
            else:
                out_array = ArrayData()
                for name, value in six.iteritems(trajectory_data):
                    # Skip saving empty arrays
                    if len(value) > 0:
                        out_array.set_array(name, np.asarray(value))
                self.out(out_ln['array'], out_array)

        ######## ---- PROCESSING OUTPUT DATA --- ########
        output_params = Dict(dict=out_dict)
        self.out(out_ln['results'], output_params)

        # Return the exit code
        return self.exit_codes.__getattr__(exit_code)


#TODO: NEED TO MIGRATE THIS
class Pot1dParser(Parser):
    """
    Parser for Pot1d
    """
    def parse_with_retrieved(self, retrieved):
        # NOT READLLY IN USE

        # Check that the retrieved folder is there
        try:
            output_folder = retrieved[self._calc._get_linkname_retrieved()]
        except KeyError:
            self.logger.error("No retrieved folder found")
            return False, ()

        # check what is inside the folder
        filenames = output_folder.get__list()

        # at least the stdout should exist
        oname = self._calc._OUTPUT_FILE_NAME
        if oname not in filenames:
            self.logger.error("Standard output not found")
            successful = False
            return successful, ()

        # The calculation is failed if there is any err file.
        for f in filenames:
            if ".err" in f:
                successful = False
                self.logger.warning("Error files found in workdir.")
                break

        # Check for keyword
        castep_file = output_folder.get_file_content(
            self._calc._OUTPUT_FILE_NAME)
        if "Finished pot1d" in castep_file:
            successful = True
        else:
            successful = False

        return successful, []


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

    import numpy as np
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
    bands_info['efermi'] *= units['Eh']
    bands_info['units'] = "eV"

    bands_node.set_bands(bands_array)
    bands_node.set_cell(bands_info['cell'], pbc=(True, True, True))

    # Store information from *.bands in the attributes
    # This is needs as we need to know the number of electrons
    # and the fermi energy
    for key, value in bands_info.items():
        bands_node.set_attribute(key, value)
    return bands_node

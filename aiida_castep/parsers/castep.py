"""
Parsers for CASTEP
"""
from aiida.orm.data.parameter import ParameterData
from aiida.parsers.parser import Parser  # , ParserParamManager
from aiida_castep.parsers.raw_parser import parse_raw_ouput, units
from aiida_castep.parsers import structure_from_input, add_last_if_exists
from aiida.common.datastructures import calc_states
from aiida.orm.data.array.bands import BandsData


class CastepParser(Parser):
    """
    This is the class for Parsing results from a CASTEP calcultion
    Supported calculations types:
    signlepoint
    geom
    """

    _setting_key = 'parser_options'

    def __init__(self, calc):
        """
        Initialize the instance of CastepParser
        """

        super(CastepParser, self).__init__(calc)

    def parse_with_retrieved(self, retrieved):
        """
        Reverives in input a dictionary of retrieved nodes.retrieved.
        Top level logic of operation
        """

        import os

        successful = True
        seed_name = self._calc._SEED_NAME

        # Look for lags of the parser
        try:
            parser_opts = self._calc.inp.settings.get_dict()[
                self.get_parser_settings_key()]
        except (AttributeError, KeyError):
            parser_opts = {}

        # NOT READLLY IN USE

        input_dict = self._calc.inp.parameters.get_dict()

        # Check that the retrieved folder is there
        try:
            out_folder = retrieved[self._calc._get_linkname_retrieved()]
        except KeyError:
            self.logger.error("No retrieved folder found")
            return False, ()

        # check what is inside the folder
        list_of_files = out_folder.get_folder_list()

        # at least the stdout should exist
        if not self._calc._OUTPUT_FILE_NAME in list_of_files:
            self.logger.error("Standard output not found")
            successful = False
            return successful, ()

        # TODO include *err files in the output and check error messages

        # look for other files
        has_dot_geom = False
        if seed_name + ".geom" in list_of_files:
            out_geom_file = os.path.join(
                out_folder.get_abs_path('.'), seed_name + '.geom')
            has_dot_geom = True
        else:
            out_geom_file = None
            has_dot_geom = False

        # Handling bands
        if self._calc._SEED_NAME + ".bands" in list_of_files:
            has_bands = True
            out_bands_file = os.path.join(out_folder.get_abs_path('.'),
                                          seed_name + '.bands')
        else:
            has_bands = False
            out_bands_file = None

        out_file = os.path.join(out_folder.get_abs_path(
            '.'), self._calc._OUTPUT_FILE_NAME)

        # call the raw parsing function
        parsing_args = [out_file, input_dict,
                        parser_opts, out_geom_file,
                        out_bands_file]

        # If there is a geom file then we parse it
        out_dict, trajectory_data, structure_data, bands_data, raw_sucessful\
            = parse_raw_ouput(*parsing_args)

        # Append the final value of trajectory_data into out_dict
        for key in ["free_energy", "total_energy", "zero_K_energy"]:
            add_last_if_exists(trajectory_data, key, out_dict)

        successful = all([raw_sucessful, successful])

        # Saving to nodes
        new_nodes_list = []

        ######## --- PROCESSING BANDS DATA -- ########
        if has_bands:
            bands = bands_to_bandsdata(bands_data)
            new_nodes_list.append((self.get_linkname_outbands(), bands))

        ######## --- PROCESSING STRUCTURE DATA --- ########
        try:
            cell = structure_data["cell"]
            positions = structure_data["positions"]
            symbols = structure_data["symbols"]

        except KeyError:
            # No final structure can be used - that is OK
            pass
        else:
            output_structure = structure_from_input(
                cell=cell, positions=positions, symbols=symbols)
            new_nodes_list.append(
                (self.get_linkname_outstructure(), output_structure))

        ######### --- PROCESSING TRAJECTORY DATA --- ########
        # If there is anything to save
        # It should...
        if trajectory_data:

            import numpy as np
            from aiida.orm.data.array.trajectory import TrajectoryData
            from aiida.orm.data.array import ArrayData

            # If we have .geom file, save as in a trajectory data
            if has_dot_geom:
                try:
                    positions = trajectory_data["positions"]
                    cells = trajectory_data["cells"]
                    symbols = trajectory_data["symbols"]
                    stepids = np.arange(len(positions))

                except KeyError:
                    out_dict["parser_warning"].append("Cannot "
                                                      "extract data from .geom file.")
                    pass

                else:
                    traj = TrajectoryData()
                    traj.set_trajectory(stepids=np.asarray(stepids),
                                        cells=np.asarray(cells),
                                        symbols=np.asarray(symbols),
                                        positions=np.asarray(positions))
                    # Save the rest
                    for name, value in trajectory_data.iteritems():
                        # Skip saving empty arrays
                        if len(value) > 0:
                            traj.set_array(name, np.asarray(value))
                    new_nodes_list.append(
                        (self.get_linkname_outtrajectory(), traj))

            # Otherwise, save data into a ArrayData node
            else:
                out_array = ArrayData()
                for name, value in trajectory_data.iteritems():
                    # Skip saving empty arrays
                    if len(value) > 0:
                        out_array.set_array(name, np.asarray(value))
                new_nodes_list.append((self.get_linkname_outarray(),
                                       out_array))

        ######## ---- PROCESSING OUTPUT DATA --- ########
        output_params = ParameterData(dict=out_dict)
        new_nodes_list.append((self.get_linkname_outparams(), output_params))
        return successful, new_nodes_list

    # getter method for various names
    @classmethod
    def get_parser_settings_key(cls):
        """
        Return the name of the key to be used in the calculation settings, that
        contains the dictionary with the parser_options.
        Not used for now
        """
        return 'parser_options'

    @classmethod
    def get_linkname_outstructure(cls):
        """
        Returns the name of the link to the output_structure
        Only exists if it is a geometry optimisation run.
        """
        return 'output_structure'

    @classmethod
    def get_linkname_outtrajectory(cls):
        """
        Returns the name of the link to the output_trajectory.
        Node exists in case of calculation = "geometryoptimsiation"
        """
        return 'output_trajectory'

    @classmethod
    def get_linkname_outarray(cls):
        """
        Returns the name of the link to the output_array.
        Exist if trajectory data cannot be created e.g not a optimisation run.
        """
        return 'output_array'

    @classmethod
    def get_linkname_out_kpoints(cls):
        """
        Not implemented for now
        """
        return 'output_kpoints'

    @classmethod
    def get_linkname_outbands(cls):
        """
        Returns the name of the link to the output band data.
        Exists if we retrived the bands file
        """
        return 'output_bands'


def bands_to_bandsdata(bands_res):
    """Convert the result of parser_dot_bands into a BandsData object """

    bands = BandsData()
    kpts = [k[1:-1] for k in bands_res[1]]
    _weights = [k[-1] for k in bands_res[1]]
    bands.set_kpoints(kpts, weights=_weights)
    # We need to swap the axes from kpt,spin,engs to spin,kpt,engs
    import numpy as np

    bands_array = np.array(bands_res[2]).swapaxes(0, 1)
    # Squeeze the first dimension e.g when there is a single spin
    if bands_array.shape[0] == 1:
        bands_array = bands_array[0]
    bands_array = bands_array * units['Eh']
    bands_res[0]['efermi'] = units['Eh']
    bands_res[0]['units'] = "eV"

    bands.set_bands(bands_array)
    bands.set_cell(bands_res[0]['cell'], pbc=(True, True, True))

    # Store information from *.bands in the attributes
    # This is needes as we need to know the number of electrons
    # and the fermi energy
    for key, value in bands_res[0].items():
        bands._set_attr(key, value)
    return bands

"""
Parsers for CASTEP
"""
from aiida.orm.data.parameter import ParameterData
from aiida.parsers.parser import Parser#, ParserParamManager
from aiida_castep.parsers.raw_parser import parse_raw_ouput
from aiida_castep.parsers import structure_from_input, add_last_if_exists
from aiida.common.datastructures import calc_states
from aiida.common.exceptions import UniquenessError
from aiida.orm.data.array.bands import BandsData
from aiida.orm.data.array.bands import KpointsData

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

        from aiida.common.exceptions import InvalidOperation
        import os
        import glob


        successful = True

        # Look for lags of the parser
        try:
            parser_opts = self._calc.inp.settings.get_dict()[self.get_parser_settings_key()]
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

        # look for other files
        has_dot_geom = False
        if self._calc._SEED_NAME + ".geom" in list_of_files:
            out_geom_file = os.path.join(out_folder.get_abs_path("."),
                self._calc._SEED_NAME + '.geom')
            has_dot_geom = True
        else:
            out_geom_file = None

        has_dot_bands = False
        if self._calc._SEED_NAME + ".bands" in list_of_files:
            has_bands = True

        out_file = os.path.join(out_folder.get_abs_path("."),
            self._calc._OUTPUT_FILE_NAME)

        # call the raw parsing function
        parsing_args = [out_file, input_dict, parser_opts, out_geom_file]

        # If there is a geom file then we parse it
        out_dict, trajectory_data, structure_data, raw_sucessful = parse_raw_ouput(*parsing_args)

        # Append the final value of trajectory_data into out_dict
        for key in ["free_energy", "total_energy", "zero_K_energy"]:
            add_last_if_exists(trajectory_data, key, out_dict)

        successful = raw_sucessful if successful else successful

        # Saving to nodes
        new_nodes_list = []


        ######## --- PROCESSING STRUCTURE DATA --- ########
        try:
            cell = structure_data["cell"]
            positions = structure_data["positions"]
            symbols = structure_data["symbols"]

        except KeyError:
            # No final structure can be used - that is OK
            pass
        else:
            output_structure = structure_from_input(cell=cell, positions=positions, symbols=symbols)
            new_nodes_list.append((self.get_linkname_outstructure(), output_structure))

        ######### --- PROCESSING TRAJECTORY DATA --- ########
        # If there is anything to save
        if trajectory_data:

            import numpy as np
            from aiida.orm.data.array.trajectory import TrajectoryData
            from aiida.orm.data.array import ArrayData

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
                        traj.set_array(name, np.asarray(value))
                    new_nodes_list.append((self.get_linkname_outtrajectory(), traj))

            out_array = ArrayData()
            # Note - not python3 compatible
            for name, value in trajectory_data.iteritems():
                out_array.set_array(name, np.asarray(value))
            new_nodes_list.append((self.get_linkname_outarray(), out_array))

        ######## ---- PROCESSING OUTPUT DATA --- ########
        output_params = ParameterData(dict=out_dict)
        new_nodes_list.append((self.get_linkname_outparams(), output_params))
        return successful, new_nodes_list

    def get_parser_settings_key(self):
        """
        Return the name of the key to be used in the calculation settings, that
        contains the dictionary with the parser_options
        """
        return 'parser_options'

    def get_linkname_outstructure(self):
        """
        Returns the name of the link to the output_structure
        Node exists if positions or cell changed.
        """
        return 'output_structure'

    def get_linkname_outtrajectory(self):
        """
        Returns the name of the link to the output_trajectory.
        Node exists in case of calculation='md', 'vc-md', 'relax', 'vc-relax'
        """
        return 'output_trajectory'

    def get_linkname_outarray(self):
        """
        Returns the name of the link to the output_array
        Node may exist in case of calculation='scf'
        """
        return 'output_array'

    def get_linkname_out_kpoints(self):
        """
        Returns the name of the link to the output_kpoints
        Node exists if cell has changed and no bands are stored.
        """
        return 'output_kpoints'


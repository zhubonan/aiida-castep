"""
Parsers for CASTEP
"""
from aiida.orm.data.parameter import ParameterData
from aiida.parsers.parser import Parser#, ParserParamManager
from aiida_castep.calculations.castep import SinglePointCalculation
from aiida_castep.parsers.raw_parser import parse_raw_ouput
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
            has_dot_geom = True

        has_dot_bands = False
        if self._calc._SEED_NAME + ".bands" in list_of_files:
            has_bands = True

        out_file = os.path.join(out_folder.get_abs_path("."),
            self._calc._OUTPUT_FILE_NAME)

        # call the raw parsing function
        parsing_args = [out_file, input_dict, parser_opts]

        out_dict, trajectory_data, raw_sucessful = parse_raw_ouput(*parsing_args)

        successful = raw_sucessful if successful else successful

        # Saving to nodes
        new_nodes_list = []

        output_params = ParameterData(dict=out_dict)
        new_nodes_list.append((self.get_linkname_outparams(), output_params))

        if trajectory_data:
        # Add trajectory data. Not implemented for now
                pass

        return successful, new_nodes_list

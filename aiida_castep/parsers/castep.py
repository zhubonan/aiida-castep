"""
Parsers for CASTEP
"""
from aiida.orm.data.parameter import ParameterData
from aiida.parsers.parser import Parser#, ParserParamManager
from aiida_quantumespresso.parsers import convert_qe2aiida_structure
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

    def parse_with_retrived(self, retrived):
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
            return successful,()

        # look for .castep
        has_dot_castep = False

        #TODO

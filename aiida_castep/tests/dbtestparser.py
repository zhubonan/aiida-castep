"""
Testing the parsers
"""

import os
from aiida.common.exceptions import InputValidationError
from aiida.common.folders import SandboxFolder, Folder
from aiida.orm import  DataFactory, Calculation
from aiida.parsers import ParserFactory
from aiida.backends.testbase import AiidaTestCase
from aiida.orm import Code

from .dbcommon import BaseCalcCase, BaseDataCase


FolderData = DataFactory("folder")

class TestCastepParser(AiidaTestCase, BaseCalcCase, BaseDataCase):

    def setUp(self):
        self.clean_db()

    def get_data_abs_path(self):
        test_moudule = os.path.split(__file__)[0]
        data_folder = os.path.join(test_moudule, "data")
        return data_folder

    def get_dummpy_output(self):

        folderdata = FolderData()
        folderdata.replace_with_folder(self.get_data_abs_path() + "/H2-geom")
        retrieved = dict(retrieved=folderdata)
        return retrieved

    def test_parser_retrieved(self):
        self.setup_localhost()
        self.setup_code_castep()
        calc = self.setup_calculation()

        parser = ParserFactory("castep.castep")(calc)
        retrived_dict = self.get_dummpy_output()

        success, out = parser.parse_with_retrieved(retrived_dict)
        self.assertTrue(success)
        out = dict(out)

        out_structure = out[parser.get_linkname_outstructure()]
        out_param_dict = out[parser.get_linkname_outparams()].get_dict()
        out_traj = out[parser.get_linkname_outtrajectory()]
        self.assertIn("total_energy", out_param_dict)
        self.assertIn("unit_energy", out_param_dict)
        # Check the length of sites are consistent
        self.assertEqual(len(out_structure.sites), len(out_traj.get_symbols()))

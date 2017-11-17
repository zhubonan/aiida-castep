"""
Testing the parsers
"""

from aiida.common.exceptions import InputValidationError
from aiida.common.folders import SandboxFolder, Folder
from aiida.orm import  DataFactory, Calculation
from aiida.parsers import ParserFactory
from aiida.backends.testbase import AiidaTestCase
from aiida.orm import Code
from .test_calculation import CalcTestBase
from .test_data import BaseDataCase
import aiida_castep.tests.backend as backend
import os

FolderData = DataFactory("folder")

class TestCastepParser(AiidaTestCase, CalcTestBase, BaseDataCase):

    def get_data_abs_path(self):
        test_moudule = os.path.split(backend.__file__)[0]
        data_folder = os.path.join(test_moudule, "data")
        return data_folder

    def get_dummpy_output(self):

        folderdata = FolderData()
        folderdata.replace_with_folder(self.get_data_abs_path() + "/H2-geom")
        retrieved = dict(retrieved=folderdata)
        return retrieved

    def test_parser_retrieved(self):
        calc = self.setup_calculation()

        parser = ParserFactory("castep.castep")(calc)
        retrived_dict = self.get_dummpy_output()

        success, out = parser.parse_with_retrieved(retrived_dict)
        self.assertTrue(success)
        out = dict(out)
        print(out)

        out_structure = out[parser.get_linkname_outstructure()]
        out_param_dict = out[parser.get_linkname_outparams()].get_dict()
        print(out_param_dict)
        self.assertIn("total_energy", out_param_dict)

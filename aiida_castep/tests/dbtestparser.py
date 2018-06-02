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
        self.insert_data()

    def get_data_abs_path(self):
        test_moudule = os.path.split(__file__)[0]
        data_folder = os.path.join(test_moudule, "data")
        return data_folder

    def get_dummy_outputs(self):

        retrieved = {}
        for folder in ["H2-geom", "O2-geom-spin", "Si-geom-stress"]:
            folderdata = FolderData()
            folderdata.replace_with_folder(
                os.path.join(self.get_data_abs_path(), folder))
            retrieved[folder] = dict(retrieved=folderdata)
        return retrieved

    def test_parser_retrieved(self):
        self.setup_code_castep()
        calc = self.setup_calculation()

        parser = ParserFactory("castep.castep")(calc)
        retrived_folders = self.get_dummy_outputs()

        for name, r in retrived_folders.items():
            success, out = parser.parse_with_retrieved(r)
            out = dict(out)

            out_structure = out[parser.get_linkname_outstructure()]
            out_param_dict = out[parser.get_linkname_outparams()].get_dict()
            out_traj = out[parser.get_linkname_outtrajectory()]
            self.assertIn("total_energy", out_param_dict)
            self.assertIn("unit_energy", out_param_dict)
            self.assertEqual(out_param_dict["unit_energy"], "eV")
            # Check the length of sites are consistent
            self.assertEqual(len(out_structure.sites), len(out_traj.get_symbols()))

            if name == "O2-geom-spin" or name == "Si-geom-stress":
                self.assertIn(parser.get_linkname_outbands(), out)
                bands = out[parser.get_linkname_outbands()]

                # Check if spins are handled correctly
                self.assertIn(bands.get_attr('nspins'), [1, 2])
                if bands.get_attr('nspins') == 1:
                    self.assertEqual(bands.get_attr('nkpts'), len(bands.get_bands()))
                elif bands.get_attr('nspins') == 2:
                    self.assertEqual(bands.get_attr('nkpts'), len(bands.get_bands()[0]))

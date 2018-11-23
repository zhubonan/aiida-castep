"""
Testing the parsers
"""

import os

from aiida.orm import DataFactory
from aiida.parsers import ParserFactory
from aiida.backends.testbase import AiidaTestCase
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
        for folder in ["H2-geom", "O2-geom-spin", "Si-geom-stress", "N2-md"]:
            folderdata = FolderData()
            folderdata.replace_with_folder(
                os.path.join(self.get_data_abs_path(), folder))
            retrieved[folder] = dict(retrieved=folderdata)
        return retrieved

    def test_version_consistency(self):
        """
        Test that moudule versions are consistent
        """

        from aiida_castep.parsers.raw_parser import __version__ as prv
        from aiida_castep.parsers.castep import __version__ as pcv
        from aiida_castep.calculations.castep import __version__ as ccv
        from aiida_castep.calculations.base import __version__ as cbv
        self.assertTrue(prv == pcv == ccv == cbv)

    def test_parser_retrieved(self):
        from .utils import get_x2_structure
        self.setup_code_castep()
        calc = self.setup_calculation()

        parser = ParserFactory("castep.castep")(calc)
        retrived_folders = self.get_dummy_outputs()
        common_keys = ["cells", "positions", "forces", "symbols", "geom_total_energy"]
        md_keys = ["hamilt_energy", "kinetic_energy",
                   "velocities", "temperatures", "times"]
        geom_keys = ["geom_enthalpy"]

        for name, r in retrived_folders.items():
            if 'O2' in name:
                xtemp = 'O'
            elif 'Si' in name:
                xtemp = 'Si'
            elif 'N2' in name:
                xtemp = 'N'
            elif 'H2' in name:
                xtemp = 'H'
            # Swap the correct structure to allow desort to work
            calc.use_structure(get_x2_structure(xtemp))

            success, out = parser.parse_with_retrieved(r)
            out = dict(out)

            out_structure = out[parser.get_linkname_outstructure()]
            out_param_dict = out[parser.get_linkname_outparams()].get_dict()
            out_traj = out[parser.get_linkname_outtrajectory()]
            self.assertIn("total_energy", out_param_dict)
            self.assertIn("unit_energy", out_param_dict)
            self.assertEqual(out_param_dict["unit_energy"], "eV")
            self.assertEqual(calc.inp.structure.label, out_structure.label)
            # Check the length of sites are consistent
            self.assertEqual(len(out_structure.sites), len(out_traj.get_symbols()))

            for k in common_keys:
                self.assertIn(k, out_traj.get_arraynames())

            if name == "O2-geom-spin" or name == "Si-geom-stress":
                self.assertIn(parser.get_linkname_outbands(), out)
                bands = out[parser.get_linkname_outbands()]

                # Check if spins are handled correctly
                self.assertIn(bands.get_attr('nspins'), [1, 2])
                if bands.get_attr('nspins') == 1:
                    self.assertEqual(bands.get_attr('nkpts'), len(bands.get_bands()))
                elif bands.get_attr('nspins') == 2:
                    self.assertEqual(bands.get_attr('nkpts'), len(bands.get_bands()[0]))

                for k in geom_keys:
                    self.assertIn(k, out_traj.get_arraynames())

            if name == "N2-md":
                for k in md_keys:
                    self.assertIn(k, out_traj.get_arraynames())


class TestPot1DParser(AiidaTestCase):

    def test_load_plugin(self):
        Pot1dParser = ParserFactory("castep.pot1d")

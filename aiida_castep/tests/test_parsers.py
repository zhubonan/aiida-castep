"""
Test parsing data
"""
from __future__ import print_function
from aiida_castep.parsers.raw_parser import parse_castep_text_output, parse_geom_text_output, parse_dot_bands
import unittest
import pytest

import os

@pytest.fixture(scope="class")
def import_things(aiida_profile, request):

    from aiida.orm import DataFactory, CalculationFactory
    FolderData = DataFactory("folder")
    for k, v in locals().items():
        setattr(request.cls, k, v)

class TestParsers(unittest.TestCase):

    @property
    def data_abs_path(self):
        test_moudule = os.path.split(__file__)[0]
        data_folder = os.path.join(test_moudule, "data")
        return data_folder

    def setUp(self):
        with open(self.data_abs_path + "/H2-geom/aiida.geom") as fh:
            self.geom_lines = fh.readlines()

        with open(self.data_abs_path + "/H2-geom/aiida.castep") as cs:
            self.castep_lines = cs.readlines()
        pass

    def test_parse_geom(self):
        res = parse_geom_text_output(self.geom_lines, None)
        self.assertEqual(res["symbols"], ["H", "H"])
        self.assertEqual(res["geom_total_energy"].shape[0], 5)
        self.assertEqual(res["positions"].shape[0], 5)
        self.assertEqual(res["forces"].shape[0], 5)

    def test_parse_castep(self):
        parsed_data, trajectory_data, warnings = parse_castep_text_output(self.castep_lines, None)
        self.assertTrue(parsed_data["cell_constraints"])
        self.assertFalse(parsed_data["warnings"])
        self.assertTrue(parsed_data["n_kpoints"])
        self.assertTrue(parsed_data["space_group"])
        self.assertTrue(parsed_data["pseudo_pots"])
        self.assertTrue(parsed_data["point_group"])
        self.assertTrue(trajectory_data["enthalpy"])
        self.assertTrue(trajectory_data["total_energy"])
        self.assertLess(trajectory_data["total_energy"][0] - trajectory_data["enthalpy"][0], 1e-5)
        self.assertFalse(parsed_data["warnings"])
        self.assertEqual(parsed_data["total_time"], 14.53)
        self.assertEqual(parsed_data["initialisation_time"], 1.02)
        self.assertEqual(parsed_data["parallel_efficiency"], 90)
        self.assertEqual(parsed_data["castep_version"], "17.2")

    def test_warnings(self):
        # Test assertion of warnings
        with_warning = self.castep_lines[:]
        # This is no longer a critical warning leading to FAILED state
        with_warning.insert(-10, "Geometry optimization failed to converge")
        parsed_data, trajectory_data, critical = parse_castep_text_output(with_warning, None)
        self.assertTrue(parsed_data["warnings"])
        self.assertNotIn(parsed_data["warnings"][0], critical)

        with_warning = self.castep_lines[:]
        with_warning.insert(-10, "SCF cycles performed but system has not reached the groundstate")
        parsed_data, trajectory_data, critical = parse_castep_text_output(with_warning, None)
        self.assertTrue(parsed_data["warnings"])
        self.assertIn(parsed_data["warnings"][0], critical)

    def test_parse_bands(self):
        """
        Test the function to parse *.bands file
        """
        res = parse_dot_bands(os.path.join(self.data_abs_path, "Si-geom-stress/aiida.bands"))
        self.assertEqual(res[0]['nspins'], 1)
        self.assertEqual(res[0]['nkpts'], len(res[1]))
        self.assertEqual(res[0]['neigns'], len(res[2][0][0]))

    def test_parser_stress(self):
        with open(self.data_abs_path + "/Si-geom-stress/aiida.castep") as cs:
            lines = cs.readlines()
        parsed_data, trajectory_data, warnings = parse_castep_text_output(lines, None)

        self.assertIn('symm_stress', trajectory_data)
        self.assertIn('symm_pressure', trajectory_data)
        self.assertTrue(trajectory_data['symm_pressure'])
        print(trajectory_data['symm_pressure'])



@pytest.mark.usefixtures("import_things", "aiida_profile")
class TestCastepParser(object):

    def get_data_abs_path(self):
        test_moudule = os.path.split(__file__)[0]
        data_folder = os.path.join(test_moudule, "data")
        return data_folder

    def get_dummy_outputs(self):

        retrieved = {}
        for folder in ["H2-geom", "O2-geom-spin", "Si-geom-stress", "N2-md"]:
            folderdata = self.FolderData()
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
        assert prv == pcv == ccv == cbv

    def test_parser_retrieved(self, code_echo, localhost, STO_calculation):
        from .utils import get_x2_structure
        from aiida_castep.parsers.castep import CastepParser

        calc = STO_calculation

        parser = CastepParser(calc)
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
            assert "total_energy" in  out_param_dict
            assert "unit_energy" in  out_param_dict
            assert out_param_dict["unit_energy"] == "eV"
            # Check if the label is correctly copied
            assert calc.inp.structure.label == out_structure.label

            # Check the length of sites are consistent
            assert len(out_structure.sites) == len(out_traj.get_symbols())

            for k in common_keys:
                assert k in out_traj.get_arraynames()

            if name == "O2-geom-spin" or name == "Si-geom-stress":
                assert parser.get_linkname_outbands() in out
                bands = out[parser.get_linkname_outbands()]

                # Check if spins are handled correctly
                assert bands.get_attr('nspins') in [1, 2]
                if bands.get_attr('nspins') == 1:
                    assert bands.get_attr('nkpts') == len(bands.get_bands())
                elif bands.get_attr('nspins') == 2:
                    assert bands.get_attr('nkpts') == len(bands.get_bands()[0])

                for k in geom_keys:
                    assert k in out_traj.get_arraynames()

            if name == "N2-md":
                for k in md_keys:
                    assert k in out_traj.get_arraynames()


class TestPot1DParser(object):

    def test_load_plugin(self):
        from aiida.parsers import ParserFactory
        Pot1dParser = ParserFactory("castep.pot1d")

from __future__ import absolute_import
import unittest
import pytest
from aiida_castep.parsers.raw_parser import (parse_castep_text_output,
                                             parse_geom_text_output,
                                             parse_dot_bands, RawParser)

from pathlib import Path
import os


class TestParsers(unittest.TestCase):
    @property
    def data_abs_str(self):
        test_moudule = Path(__file__).parent
        data_folder = test_moudule / 'data'
        return str(data_folder)

    @property
    def data_abs_path(self):
        test_moudule = Path(__file__).parent
        data_folder = test_moudule / 'data'
        return data_folder

    def get_lines(self, path):
        """Get a list of lines from a path"""
        with open(str(path)) as fh:
            lines = fh.readlines()
        return lines

    def setUp(self):
        with open(self.data_abs_str + "/H2-geom/aiida.geom") as fh:
            self.geom_lines = fh.readlines()

        with open(self.data_abs_str + "/H2-geom/aiida.castep") as cs:
            self.castep_lines = cs.readlines()

        pass

    def test_parse_geom(self):
        res = parse_geom_text_output(self.geom_lines, None)
        self.assertEqual(res["symbols"], ["H", "H"])
        self.assertEqual(res["geom_total_energy"].shape[0], 5)
        self.assertEqual(res["positions"].shape[0], 5)
        self.assertEqual(res["forces"].shape[0], 5)

    def test_parse_castep(self):
        parsed_data, trajectory_data, warnings = parse_castep_text_output(
            self.castep_lines, None)
        self.assertTrue(parsed_data["cell_constraints"])
        self.assertFalse(parsed_data["warnings"])
        self.assertTrue(parsed_data["n_kpoints"])
        self.assertTrue(parsed_data["space_group"])
        self.assertTrue(parsed_data["pseudo_pots"])
        self.assertTrue(parsed_data["point_group"])
        self.assertTrue(trajectory_data["enthalpy"])
        self.assertTrue(trajectory_data["total_energy"])
        self.assertLess(
            trajectory_data["total_energy"][0] -
            trajectory_data["enthalpy"][0], 1e-5)
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
        parsed_data, trajectory_data, critical = parse_castep_text_output(
            with_warning, None)
        self.assertTrue(parsed_data["warnings"])
        self.assertNotIn(parsed_data["warnings"][0], critical)

        with_warning = self.castep_lines[:]
        with_warning.insert(
            -10,
            "SCF cycles performed but system has not reached the groundstate")
        parsed_data, trajectory_data, critical = parse_castep_text_output(
            with_warning, None)
        self.assertTrue(parsed_data["warnings"])
        self.assertIn(parsed_data["warnings"][0], critical)

    def test_parse_bands(self):
        """
        Test the function to parse *.bands file
        """
        res = parse_dot_bands(
            self.get_lines(self.data_abs_path / 'Si-geom-stress/aiida.bands'))
        self.assertEqual(res[0]['nspins'], 1)
        self.assertEqual(res[0]['nkpts'], len(res[1]))
        self.assertEqual(res[0]['neigns'], len(res[2][0][0]))

    def test_parser_stress(self):
        with open(self.data_abs_str + "/Si-geom-stress/aiida.castep") as cs:
            lines = cs.readlines()
        parsed_data, trajectory_data, warnings = parse_castep_text_output(
            lines, None)

        self.assertIn('symm_stress', trajectory_data)
        self.assertIn('symm_pressure', trajectory_data)
        self.assertTrue(trajectory_data['symm_pressure'])
        self.assertTrue(len(trajectory_data['symm_pressure']) > 10)

    def test_parser_class(self):
        """Test the classfor RawParser"""
        bands = self.get_lines(self.data_abs_path /
                               'Si-geom-stress/aiida.bands')
        parser = RawParser(self.castep_lines, {},
                           ['aiida.geom', self.geom_lines], bands)
        res = parser.parse()

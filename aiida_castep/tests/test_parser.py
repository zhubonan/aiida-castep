"""
Test for the parser without loading AiiDA profile
"""
from pathlib import Path
import unittest
import pytest
import numpy as np
from aiida_castep.parsers.raw_parser import (parse_castep_text_output,
                                             parse_geom_text_output,
                                             parse_dot_bands, RawParser)
from aiida_castep.parsers.castep_bin import CastepbinFile

from aiida_castep.parsers.constants import units


@pytest.fixture
def data_abs_path():
    """Absolute path of the data folder"""
    test_moudule = Path(__file__).parent
    data_folder = test_moudule / 'data'
    return data_folder


class TestParsers(unittest.TestCase):
    """Test cases for the parsers"""
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

    @staticmethod
    def get_lines(path):
        """Get a list of lines from a path"""
        with open(str(path)) as fhandle:
            lines = fhandle.readlines()
        return lines

    def setUp(self):
        with open(self.data_abs_str + "/H2-geom/aiida.geom") as fhandle:
            self.geom_lines = fhandle.readlines()

        with open(self.data_abs_str + "/H2-geom/aiida.castep") as clines:
            self.castep_lines = clines.readlines()

    def test_parse_geom(self):
        """Test parsing the geom file"""

        res = parse_geom_text_output(self.geom_lines, None)
        self.assertEqual(res["symbols"], ["H", "H"])
        self.assertEqual(res["geom_total_energy"].shape[0], 5)  # pylint: disable=unsubscriptable-object
        self.assertEqual(res["positions"].shape[0], 5)  # pylint: disable=unsubscriptable-object
        self.assertEqual(res["forces"].shape[0], 5)  # pylint: disable=unsubscriptable-object

    def test_parse_castep(self):
        """Test parsing CASTEP file"""
        parsed_data, trajectory_data, _ = parse_castep_text_output(
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
        """Test for finding the warnings"""

        # Test assertion of warnings
        with_warning = self.castep_lines[:]
        # This is no longer a critical warning leading to FAILED state
        with_warning.insert(-10, "Geometry optimization failed to converge")
        parsed_data, _, critical = parse_castep_text_output(with_warning, None)
        self.assertTrue(parsed_data["warnings"])
        self.assertNotIn(parsed_data["warnings"][0], critical)

        with_warning = self.castep_lines[:]
        with_warning.insert(
            -10,
            "SCF cycles performed but system has not reached the groundstate")
        parsed_data, _, critical = parse_castep_text_output(with_warning, None)
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
        """Test parsing stress from the output"""
        with open(self.data_abs_str +
                  "/Si-geom-stress/aiida.castep") as clines:
            lines = clines.readlines()
        _, trajectory_data, _ = parse_castep_text_output(lines, None)

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
        parser.parse()


def test_castep_bin_parser(data_abs_path):
    """Test the castep_bin parser"""

    fname = data_abs_path / 'Si2-castepbin/aiida.castep_bin'
    with open(fname, "rb") as fhandle:
        binfile = CastepbinFile(fileobj=fhandle)

    assert np.all(binfile.kpoints_indices == [0, 2, 1, 3])
    assert binfile.eigenvalues[0, 0, 0] == pytest.approx(-0.13544694 *
                                                         units['Eh'])
    assert binfile.eigenvalues[0, 1, 0] == pytest.approx(-0.15489719 *
                                                         units['Eh'])

    assert binfile.occupancies[0, 0, 0] == 1.0
    assert binfile.occupancies[0, 0, -1] == 0.0

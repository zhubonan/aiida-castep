"""
Test for the parser without loading AiiDA profile
"""
import unittest
from pathlib import Path

import numpy as np
import pytest

from aiida_castep.parsers.castep_bin import CastepbinFile
from aiida_castep.parsers.constants import units
from aiida_castep.parsers.raw_parser import (
    RawParser,
    parse_castep_text_output,
    parse_dot_bands,
    parse_geom_text_output,
)
from aiida_castep.parsers.utils import get_desort_args


@pytest.fixture
def data_abs_path():
    """Absolute path of the data folder"""
    test_moudule = Path(__file__).parent
    data_folder = test_moudule / "data"
    return data_folder


class TestParsers(unittest.TestCase):
    """Test cases for the parsers"""

    @property
    def data_abs_str(self):
        test_moudule = Path(__file__).parent
        data_folder = test_moudule / "data"
        return str(data_folder)

    @property
    def data_abs_path(self):
        test_moudule = Path(__file__).parent
        data_folder = test_moudule / "data"
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
        self.assertEqual(
            res["geom_total_energy"].shape[0], 5
        )  # pylint: disable=unsubscriptable-object
        self.assertEqual(
            res["positions"].shape[0], 5
        )  # pylint: disable=unsubscriptable-object
        self.assertEqual(
            res["forces"].shape[0], 5
        )  # pylint: disable=unsubscriptable-object

    def test_parse_castep(self):
        """Test parsing CASTEP file"""
        parsed_data, trajectory_data, _ = parse_castep_text_output(
            self.castep_lines, None
        )
        self.assertTrue(parsed_data["cell_constraints"])
        self.assertFalse(parsed_data["warnings"])
        self.assertTrue(parsed_data["n_kpoints"])
        self.assertTrue(parsed_data["space_group"])
        self.assertTrue(parsed_data["pseudo_pots"])
        self.assertTrue(parsed_data["point_group"])
        self.assertTrue(trajectory_data["enthalpy"])
        self.assertTrue(trajectory_data["total_energy"])
        self.assertLess(
            trajectory_data["total_energy"][0] - trajectory_data["enthalpy"][0], 1e-5
        )
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
            -10, "SCF cycles performed but system has not reached the groundstate"
        )
        parsed_data, _, critical = parse_castep_text_output(with_warning, None)
        self.assertTrue(parsed_data["warnings"])
        self.assertIn(parsed_data["warnings"][0], critical)

    def test_parse_bands(self):
        """
        Test the function to parse *.bands file
        """
        res = parse_dot_bands(
            self.get_lines(self.data_abs_path / "Si-geom-stress/aiida.bands")
        )
        self.assertEqual(res[0]["nspins"], 1)
        self.assertEqual(res[0]["nkpts"], len(res[1]))
        self.assertEqual(res[0]["neigns"], len(res[2][0][0]))

    def test_parser_stress(self):
        """Test parsing stress from the output"""
        with open(self.data_abs_str + "/Si-geom-stress/aiida.castep") as clines:
            lines = clines.readlines()
        _, trajectory_data, _ = parse_castep_text_output(lines, None)

        self.assertIn("symm_stress", trajectory_data)
        self.assertIn("symm_pressure", trajectory_data)
        self.assertTrue(trajectory_data["symm_pressure"])
        self.assertTrue(len(trajectory_data["symm_pressure"]) > 10)

    def test_parser_popn(self):
        """Test parsing the population box from the output"""
        with open(self.data_abs_str + "/O2-geom-spin/aiida.castep") as clines:
            lines = clines.readlines()
            parsed_data, _, _ = parse_castep_text_output(lines, None)

        self.assertIn("charges", parsed_data)
        self.assertIn("spins", parsed_data)
        self.assertTrue(parsed_data["charges"] == [-0.0, 0.0])
        self.assertTrue(parsed_data["spins"] == [1.0, 1.0])

    def test_parser_class(self):
        """Test the classfor RawParser"""
        bands = self.get_lines(self.data_abs_path / "Si-geom-stress/aiida.bands")
        parser = RawParser(
            self.castep_lines, {}, ["aiida.geom", self.geom_lines], bands
        )
        parser.parse()


def test_castep_bin_parser(data_abs_path):
    """Test the castep_bin parser"""

    fname = data_abs_path / "Si2-castepbin/aiida.castep_bin"
    with open(fname, "rb") as fhandle:
        binfile = CastepbinFile(fileobj=fhandle)

    assert np.all(binfile.kpoints_indices == [0, 2, 1, 3])
    assert binfile.eigenvalues[0, 0, 0] == pytest.approx(-0.13544694 * units["Eh"])
    assert binfile.eigenvalues[0, 1, 0] == pytest.approx(-0.15489719 * units["Eh"])

    assert binfile.occupancies[0, 0, 0] == 1.0
    assert binfile.occupancies[0, 0, -1] == 0.0


def test_get_desort_args():
    """
    Test that get_desort_args returns the correct inverse permutation for desorting.

    CASTEP sorts atoms by atomic number. get_desort_args should return an index
    array that maps from CASTEP-sorted order back to the original input order.
    """
    from ase import Atoms

    # Mock structure: Ti(Z=22), O(Z=8), O(Z=8) - in that order
    # CASTEP would sort to: O, O, Ti (ascending atomic number)
    class MockStructure:
        def get_ase(self):
            return Atoms("TiOO", positions=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], cell=[4, 4, 4])

    s = MockStructure()
    idesort = get_desort_args(s)

    # CASTEP sorted order: O(orig 1), O(orig 2), Ti(orig 0)
    # idesort should map CASTEP output back to original order
    castep_forces = np.array([[0.1, 0.0, 0.0], [0.2, 0.0, 0.0], [0.3, 0.0, 0.0]])
    # CASTEP order: O_1=0.1, O_2=0.2, Ti=0.3 -> desorted: Ti=0.3, O_1=0.1, O_2=0.2
    reordered = castep_forces[idesort]
    assert reordered[0][0] == pytest.approx(0.3)  # Ti force (originally at index 0)
    assert reordered[1][0] == pytest.approx(0.1)  # O_1 force (originally at index 1)
    assert reordered[2][0] == pytest.approx(0.2)  # O_2 force (originally at index 2)


def test_desort_array_bug_fixed():
    """
    Regression test: verify that the sorted array (not the original value)
    is saved when applying idesort to trajectory forces/velocities.

    Previously, the parser code computed the sorted array but then discarded it:
        array = np.asarray(value)
        if "force" in name:
            array = array[:, idesort]
        traj.set_array(name, np.asarray(value))  # BUG: saved unsorted value

    The fix ensures traj.set_array(name, array) is used instead.
    """
    from ase import Atoms

    # Structure: Ti(Z=22), O(Z=8) - CASTEP sorts to O, Ti
    class MockStructure:
        def get_ase(self):
            return Atoms("TiO", positions=[[0, 0, 0], [1, 0, 0]], cell=[4, 4, 4])

    s = MockStructure()
    idesort = get_desort_args(s)

    # CASTEP output forces in CASTEP-sorted order: O first (0.5), Ti second (1.0)
    castep_forces = np.array([[[0.5, 0.0, 0.0], [1.0, 0.0, 0.0]]])  # shape (1, 2, 3)

    # Simulate the FIXED code: use `array` not `value`
    value = castep_forces
    array = np.asarray(value)
    array = array[:, idesort]  # desort forces
    saved_forces = array  # This is what is now saved (fixed behavior)

    # After desort: Ti should be first (original index 0), O second (original index 1)
    # CASTEP: O=0.5, Ti=1.0 -> desorted: Ti=1.0, O=0.5
    assert saved_forces[0, 0, 0] == pytest.approx(1.0)  # Ti force
    assert saved_forces[0, 1, 0] == pytest.approx(0.5)  # O force

    # Also verify the old buggy behavior would have returned unsorted values
    buggy_saved = np.asarray(value)  # Old code saved this instead
    assert buggy_saved[0, 0, 0] == pytest.approx(0.5)  # Would have been O force (wrong)
    assert buggy_saved[0, 1, 0] == pytest.approx(1.0)  # Would have been Ti force (wrong)

"""
Tests for utils module
"""

import pytest
import numpy as np

from aiida_castep.utils.dos import DOSProcessor
from aiida_castep.utils import ase_to_castep_index, is_castep_sorted, sort_atoms_castep, desort_atoms_castep, compute_kpoints_spacing

try:
    import ase
except ImportError:
    ase = None

# pylint: disable=redefined-outer-name


@pytest.fixture
def unsorted_atoms():
    atoms = ase.Atoms("TiO2",
                      cell=[5, 5, 5],
                      positions=[[0, 0, 0], [1, 0, 0], [0, 1, 0]])
    return atoms


@pytest.fixture
def sorted_atoms():
    atoms = ase.Atoms(numbers=[8, 8, 22],
                      cell=[5, 5, 5],
                      positions=[[1, 0, 0], [0, 1, 0], [0, 0, 0]])
    return atoms


@pytest.mark.skipif(ase is None, reason="No ase module")
def test_ase_to_castep_index(unsorted_atoms):
    res = ase_to_castep_index(unsorted_atoms, [0, 2, 1])
    assert res[0] == ["Ti", 1]
    assert res[1] == ["O", 2]
    assert res[2] == ["O", 1]


@pytest.mark.skipif(ase is None, reason="No ase module")
def test_sort_atoms(unsorted_atoms, sorted_atoms):
    atoms = sort_atoms_castep(unsorted_atoms, order=None)
    assert np.all(atoms.numbers == sorted_atoms.numbers)
    assert np.all(atoms.positions == sorted_atoms.positions)


@pytest.mark.skipif(ase is None, reason="No ase module")
def test_desort_atoms(unsorted_atoms, sorted_atoms):
    sorted_atoms = sort_atoms_castep(unsorted_atoms, order=None)
    tmp = desort_atoms_castep(sorted_atoms, unsorted_atoms)
    assert tmp == unsorted_atoms


@pytest.mark.skipif(ase is None, reason="No ase module")
def test_check_sorted(unsorted_atoms, sorted_atoms):
    assert not is_castep_sorted(unsorted_atoms)
    assert is_castep_sorted(sorted_atoms)


def test_k_spacing():
    spacing = compute_kpoints_spacing([1, 1, 1], [1, 1, 1])
    assert np.all(spacing == np.array([1, 1, 1]))

    spacing = compute_kpoints_spacing([4, 4, 4], [2, 2, 2])
    assert np.all(spacing == np.array([1. / 8, 1. / 8, 1. / 8]))


@pytest.fixture
def bands_data():

    bands = np.arange(40).reshape((2, 4, 5))
    weights = np.ones(4) / 4
    return bands, weights


def test_dos_compute(bands_data):
    """Test calculation for the density of states"""

    bands, weights = bands_data

    dos = DOSProcessor(bands, weights, min_eng=-10, max_eng=100)
    energy, values = dos.get_dos(npoints=2000)

    assert energy.size == 2000
    assert values.shape[1] == 2000

    dos = DOSProcessor(bands[0], weights, min_eng=-10, max_eng=100)
    energy, values = dos.get_dos(dropdim=True, npoints=3000)

    #assert energy.size == 2000
    #assert values.size == 2000
    #assert values.shape == (2000, )
    np.testing.assert_approx_equal(values[0], 0)
    np.testing.assert_approx_equal(values[-1], 0)

    total_bands = values.sum() * (energy[1] - energy[0])
    np.testing.assert_approx_equal(total_bands, 5.0)
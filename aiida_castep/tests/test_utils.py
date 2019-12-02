"""
Tests for utils module
"""

from __future__ import absolute_import
import pytest
from ..utils import *
import numpy as np

try:
    import ase
except ImportError:
    ase = None


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
    unsorted_atoms = sort_atoms_castep(unsorted_atoms, order=None)
    assert np.all(unsorted_atoms.numbers == sorted_atoms.numbers)
    assert np.all(unsorted_atoms.positions == sorted_atoms.positions)


@pytest.mark.skipif(ase is None, reason="No ase module")
def test_desort_atoms(unsorted_atoms, sorted_atoms):
    sorted_atoms = sort_atoms_castep(unsorted_atoms, order=None)
    tmp = desort_atoms_castep(sorted_atoms, unsorted_atoms)
    assert tmp == unsorted_atoms


@pytest.mark.skipif(ase is None, reason="No ase module")
def test_check_sorted(unsorted_atoms, sorted_atoms):
    assert is_castep_sorted(unsorted_atoms) == False
    assert is_castep_sorted(sorted_atoms) == True


def test_k_spacing():
    spacing = compute_kpoints_spacing([1, 1, 1], [1, 1, 1])
    assert np.all(spacing == np.array([1, 1, 1]))

    spacing = compute_kpoints_spacing([4, 4, 4], [2, 2, 2])
    assert np.all(spacing == np.array([1. / 8, 1. / 8, 1. / 8]))

"""
Tests for utils module
"""

import pytest
import ase

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


def test_atoms_to_castep(unsorted_atoms):
    res = atoms_to_castep(unsorted_atoms, [0, 2, 1])
    assert res[0] == ["Ti", 1]
    assert res[1] == ["O", 2]
    assert res[2] == ["O", 1]

def test_sort_atoms(unsorted_atoms):
    sort_atoms_castep(unsorted_atoms, copy=False)
    assert unsorted_atoms == sorted_atoms


def test_check_sorted(unsorted_atoms, sorted_atoms):
    assert is_castep_sorted(unsorted_atoms) is False
    assert is_castep_sorted(sorted_atoms) is True

"""
Utility module with useful functions
"""


from __future__ import division
from __future__ import print_function
import numpy as np


def atoms_to_castep(atoms, index):
    """Convert ase atoms' index to castep like
    return (Specie, Ion) Deprecated, use ase_to_castep_index"""
    atom = atoms[index]
    symbol = atom.symbol
    # Start counter
    count = 0
    for atom in atoms:
        if atom.symbol == symbol:
            count += 1
        if atom.index == index:
            break
    return symbol, count


def ase_to_castep_index(atoms, indices):
    """Convert a list of indices to castep style
    return list of (element, i in the same element)"""
    if isinstance(indices, int):
        indices = [indices]
    num = atoms.numbers
    symbols = np.array(atoms.get_chemical_symbols())
    iatoms = np.arange(len(atoms))
    res = []
    # Iterate through given indices
    for i in indices:
        mask = symbols == symbols[i]  # Select the same species

        # CASTEP start counting from 1
        c = np.where(iatoms[mask] == i)[0][0] + 1
        res.append([symbols[i], c])
    return res


def generate_ionic_fix_cons(atoms, indices, mask=None):
    """
    create ionic constraint section via indices and ase Atoms
    mask: a list of 3 integers, must be 0 (no fix) or 1 (fix this Cartesian)
    """
    castep_indices = ase_to_castep_index(atoms, indices)
    count = 1
    lines = []
    if mask == None:
        mask = (1, 1, 1)
    for symbol, i in castep_indices:
        if mask[0]:
            lines.append("{:<4d} {:<2}    {:<4d} 1 0 0".format(count, symbol, i))
        if mask[1]:
            lines.append("{:<4d} {:<2}    {:<4d} 0 1 0".format(count+1, symbol, i))
        if mask[2]:
            lines.append("{:<4d} {:<2}    {:<4d} 0 0 1".format(count+2, symbol, i))
        count += sum(mask)
    return lines


def castep_to_atoms(atoms, specie, ion):
    """Convert castep like index to ase Atoms index"""
    return [atom for atom in atoms if atom.symbol == specie][ion-1].index


def sort_atoms_castep(atoms, copy=True, order=(0, 1, 2)):
    """
    Sort ``ase.Atoms`` instance  to castep style.
    A sorted ``Atoms`` will have the same index before and after calculation.
    This is useful when chaining optimisation requires specifying per atoms
    tags such as *SPIN* and *ionic_constraints*.
    :param copy: If True then return a copy of the atoms.
    :param order: orders of coordinates. (0, 1, 2) means the sorted atoms
    will be ascending by x, then y, then z if there are equal x or ys.

    :returns: A ``ase.Atoms`` object that is sorted.
    """
    if copy:
        atoms = atoms.copy()

    # Sort castep style
    if order is not None:
        for i in reversed(order):
            isort = np.argsort(atoms.positions[:, i], kind="mergesort")
            atoms.positions = atoms.positions[isort]
            atoms.numbers = atoms.numbers[isort]

    isort = np.argsort(atoms.numbers, kind="mergesort")
    atoms.positions = atoms.positions[isort]
    atoms.numbers = atoms.numbers[isort]

    return atoms


def is_castep_sorted(atoms):
    """
    Check if an Atoms object is CASTEP style sorted
    """
    numbers = np.asarray(atoms.numbers)
    return np.all(numbers == np.sort(numbers))


def reuse_kpoints_grid(grid, lowest_pk=False):
    """
    Retrieve previously stored kpoints mesh data node.
    Will return the one with highest pk
    :param grid: Grid to be retrieved
    :param bool lowest_pk: If set to True will return the node with lowest pk

    :returns: A KpointsData node representing the grid requested
    """
    from aiida.orm.querybuilder import QueryBuilder
    from aiida.orm.data.array.kpoints import KpointsData
    q = QueryBuilder()
    q.append(KpointsData, tag="kpoints", filters={"attributes.mesh.0": grid[0],
                                   "attributes.mesh.1": grid[1],
                                   "attributes.mesh.2": grid[2]})
    if lowest_pk:
        order = "asc"
    else:
        order = "desc"
    q.order_by({"kpoints":[{"id": {"order": order}}]})
    return q.first()[0]


def traj_to_atoms(traj, combine_ancesters=False,
                  eng_key="enthalpy"):
    """
    Generate a list of ASE Atoms given an AiiDA TrajectoryData object
    :param bool combine_ancesters: If true will try to combine trajectory
    from ancestor calculations

    :returns: A list of atoms for the trajectory.
    """
    from ase import Atoms
    from ase.calculators.singlepoint import SinglePointCalculator
    from aiida.orm import QueryBuilder, Node, JobCalculation

    # If a JobCalculation is passed, select its output trajectory
    if isinstance(traj, JobCalculation):
        traj = traj.out.output_trajectory
    # Combine trajectory from ancesters
    if combine_ancesters is True:
        q = QueryBuilder()
        q.append(Node, filters={"uuid": traj.uuid})
        q.append(JobCalculation, tag="ans", ancestor_of=Node)
        q.order_by({"ans": "id"})
        calcs = [_[0] for _ in q.iterall()]
        atoms_list = []
        for c in calcs:
            atoms_list.extend(
                traj_to_atoms(c.out.output_trajectory,
                              combine_ancesters=False,
                              eng_key=eng_key))
        return atoms_list
    forces = traj.get_array("forces")
    symbols = traj.get_array("symbols")
    positions = traj.get_array("positions")
    try:
        eng = traj.get_array(eng_key)
    except KeyError:
        eng = None
    cells = traj.get_array("cells")
    atoms_traj = []
    for c, p , e, f in zip(cells, positions, eng, forces):
        atoms = Atoms(symbols=symbols, cell=c, pbc=True, positions=p)
        calc = SinglePointCalculator(atoms, energy=e, forces=f)
        atoms.set_calculator(calc)
        atoms_traj.append(atoms)
    return atoms_traj


def get_transport(calc):
    """
    Get a transport for the calculation node
    """
    from aiida.backends.utils import get_authinfo, get_automatic_user
    authinfo = get_authinfo(calc.get_computer(), get_automatic_user())
    return authinfo.get_transport()


def get_remote_folder_info(calc, transport):
    """Get the information of the remote folder of a calculation"""
    path = calc.out.remote_folder.get_remote_path()
    transport.chdir(path)
    lsattrs = transport.listdir_withattributes()
    return lsattrs

def get_remote_folder_size(calc, transport):
    """
    Return size of a remote folder of a calculation in MB
    """
    try:
        lsattrs = get_remote_folder_info(calc, transport)
    except IOError:
        return 0
    total_size = 0
    for attr in lsattrs:
        total_size += attr['attributes'].st_size  # in byres
    return total_size / (1024)**2


def take_popn(seed):
    """
    Take section of population analysis from a seed.castep file
    Return a list of StringIO of the population analysis section
    """
    import io
    popns = []
    rec = False
    with open(seed + '.castep') as fh:
        for line in fh:
            if "Atomic Populations (Mulliken)" in line:
                record = io.StringIO()
                rec = True

            # record information
            if rec is True:
                if line.strip() is "":
                    rec = False
                    record.seek(0)
                    popns.append(record)
                else:
                    record.write(line)

    return popns


def read_popn(fn):
    """Read population file into pandas dataframe"""
    import pandas as pd
    table = pd.read_table(fn, sep="\s\s+", header=2,
                          comment="=", engine="python")
    return table

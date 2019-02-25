"""
Utility module with useful functions
"""


from __future__ import division
from __future__ import print_function
from copy import copy
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


def generate_ionic_fix_cons(atoms, indices, mask=None, count_start=1):
    """
    create ionic constraint section via indices and ase Atoms

    :param atoms: atoms object to be fixed
    :param indices: indices of the atoms to be fixed
    :param mask: a list of 3 integers, must be 0 (no fix) or 1 (fix this Cartesian)

    :returns: (lines, index of the next constraint)

    """

    # Convert to castep style indices (element, index)
    castep_indices = ase_to_castep_index(atoms, indices)
    count = count_start
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
    return lines, count

def generate_rel_fix(atoms, indices, ref_index=0, count_start=1):
    """
    Generate relative constraints

    .. note::

      In CASTEP the mass of atoms are coupled in the fix,
      hence to truelly fix the relative positions you will have to
      declare all atoms having the same weight using the
      SPECIES_MASS block.

    :param atoms: atoms object to be fixed

    :param indices: indices of the atoms to be fixed

    :param ref_index: index of the reference atom in amoung the atoms
      being fixed. Default is the first atom appear in the indices.

    :returns: (lines, index of the next constraint)
    """
    castep_indices = ase_to_castep_index(atoms, indices)
    lines = []
    count = count_start
    symbol_ref, i_ref = castep_indices[ref_index]
    for symbol, i in castep_indices[1:]:
        lines.append("{:<4d} {:<2}    {:<4d} 1 0 0".format(count, symbol, i))
        lines.append("{:<4d} {:<2}    {:<4d} -1 0 0".format(count, symbol_ref, i_ref))
        lines.append("{:<4d} {:<2}    {:<4d} 0 1 0".format(count + 1, symbol, i))
        lines.append("{:<4d} {:<2}    {:<4d} 0 -1 0".format(count + 1, symbol_ref, i_ref))
        lines.append("{:<4d} {:<2}    {:<4d} 0 0 1".format(count + 2, symbol, i))
        lines.append("{:<4d} {:<2}    {:<4d} 0 0 -1".format(count + 2, symbol_ref, i_ref))

        count += 3
    return lines, count

def castep_to_atoms(atoms, specie, ion):
    """Convert castep like index to ase Atoms index"""
    return [atom for atom in atoms if atom.symbol == specie][ion-1].index


def sort_atoms_castep(atoms, copy=True, order=None):
    """
    Sort ``ase.Atoms`` instance  to castep style.
    A sorted ``Atoms`` will have the same index before and after calculation.
    This is useful when chaining optimisation requires specifying per atoms
    tags such as *SPIN* and *ionic_constraints*.
    :param order: orders of coordinates. (0, 1, 2) means the sorted atoms
    will be ascending by x, then y, then z if there are equal x or ys.

    :returns: A ``ase.Atoms`` object that is sorted.
    """

    # Sort castep style
    if order is not None:
        for i in reversed(order):
            isort = np.argsort(atoms.positions[:, i], kind="mergesort")
            atoms.positions = atoms.positions[isort]
            atoms.numbers = atoms.numbers[isort]

    isort = np.argsort(atoms.numbers, kind="mergesort")
    atoms = atoms[isort]
    return atoms


def desort_atoms_castep(atoms, original_atoms):
    """
    Recover the original ordering of the atoms. CASTEP sort the atoms
    in the order of atomic number and then the order of appearance internally.

    :param copy: If True then return an copy of the atoms
    :returns: A ``ase.Atoms`` object that has be sorted
    """

    isort = np.argsort(original_atoms.numbers, kind='mergesort')
    rsort = np.zeros(isort.shape, dtype=int)
    rsort.fill(-1)
    for i, j in enumerate(isort):
        rsort[j] = i

    return atoms[rsort]


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
    from aiida.backends.utils import get_authinfo
    authinfo = get_authinfo(calc.get_computer())
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


def export_calculation(n, output_dir, prefix=None):
    """
    Export one calculation a a directory
    """
    import os
    import shutil
    from glob import glob
    paths = glob(os.path.join(n.out.retrieved.get_abs_path(), "path/*"))

    #inputs
    input_path = os.path.join(n.get_abs_path(), "raw_input/*")
    paths.extend(glob(input_path))

    # Create the directory if necessary
    if not os.path.isdir(output_dir):
        os.mkdir(output_dir)

    # Copy the files
    for p in paths:
        fname = os.path.split(p)[1]
        if prefix and not fname.startswith("_"):
            fname = fname.replace("aiida", prefix)
        out_path = os.path.join(output_dir, fname)
        shutil.copy(p, out_path)
        print("Copied: {}".format(out_path))




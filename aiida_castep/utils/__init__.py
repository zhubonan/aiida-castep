"""
Utility module with useful functions
"""
import io
import numpy as np

# pylint: disable=import-outside-toplevel, too-many-locals


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
    symbols = np.array(atoms.get_chemical_symbols())
    iatoms = np.arange(len(atoms))
    res = []
    # Iterate through given indices
    for i in indices:
        mask = symbols == symbols[i]  # Select the same species

        # CASTEP start counting from 1
        counter = np.where(iatoms[mask] == i)[0][0] + 1
        res.append([symbols[i], counter])
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
    if mask is None:
        mask = (1, 1, 1)
    for symbol, i in castep_indices:
        if mask[0]:
            lines.append("{:<4d} {:<2}    {:<4d} 1 0 0".format(
                count, symbol, i))
        if mask[1]:
            lines.append("{:<4d} {:<2}    {:<4d} 0 1 0".format(
                count + 1, symbol, i))
        if mask[2]:
            lines.append("{:<4d} {:<2}    {:<4d} 0 0 1".format(
                count + 2, symbol, i))
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
        lines.append("{:<4d} {:<2}    {:<4d} -1 0 0".format(
            count, symbol_ref, i_ref))
        lines.append("{:<4d} {:<2}    {:<4d} 0 1 0".format(
            count + 1, symbol, i))
        lines.append("{:<4d} {:<2}    {:<4d} 0 -1 0".format(
            count + 1, symbol_ref, i_ref))
        lines.append("{:<4d} {:<2}    {:<4d} 0 0 1".format(
            count + 2, symbol, i))
        lines.append("{:<4d} {:<2}    {:<4d} 0 0 -1".format(
            count + 2, symbol_ref, i_ref))

        count += 3
    return lines, count


def castep_to_atoms(atoms, specie, ion):
    """Convert castep like index to ase Atoms index"""
    return [atom for atom in atoms if atom.symbol == specie][ion - 1].index


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
    _ = copy
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
    If there is no such ``KpointsData``, a new node will be created.
    Will return the one with highest pk
    :param grid: Grid to be retrieved
    :param bool lowest_pk: If set to True will return the node with lowest pk

    :returns: A KpointsData node representing the grid requested
    """
    from aiida.orm import QueryBuilder
    from aiida.orm import KpointsData
    qbd = QueryBuilder()
    qbd.append(KpointsData,
               tag="kpoints",
               filters={
                   "attributes.mesh.0": grid[0],
                   "attributes.mesh.1": grid[1],
                   "attributes.mesh.2": grid[2]
               })
    if lowest_pk:
        order = "asc"
    else:
        order = "desc"
    qbd.order_by({"kpoints": [{"id": {"order": order}}]})
    if qbd.count() >= 1:

        return qbd.first()[0]
    kpoints = KpointsData()
    kpoints.set_kpoints_mesh(grid)
    return kpoints


def traj_to_atoms(traj, combine_ancesters=False, eng_key="enthalpy"):
    """
    Generate a list of ASE Atoms given an AiiDA TrajectoryData object
    :param bool combine_ancesters: If true will try to combine trajectory
    from ancestor calculations

    :returns: A list of atoms for the trajectory.
    """
    from ase import Atoms
    from ase.calculators.singlepoint import SinglePointCalculator
    from aiida.orm import QueryBuilder, Node, CalcJobNode
    from aiida_castep.common import OUTPUT_LINKNAMES

    # If a CalcJobNode is passed, select its output trajectory
    if isinstance(traj, CalcJobNode):
        traj = traj.outputs.__getattr__(OUTPUT_LINKNAMES['trajectory'])
    # Combine trajectory from ancesters
    if combine_ancesters is True:
        qbd = QueryBuilder()
        qbd.append(Node, filters={"uuid": traj.uuid})
        qbd.append(CalcJobNode, tag="ans", ancestor_of=Node)
        qbd.order_by({"ans": "id"})
        calcs = [_[0] for _ in qbd.iterall()]
        atoms_list = []
        for counter in calcs:
            atoms_list.extend(
                traj_to_atoms(counter.outputs.__getattr__(
                    OUTPUT_LINKNAMES['trajectory']),
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
    for counter, pos, eng_, force in zip(cells, positions, eng, forces):
        atoms = Atoms(symbols=symbols, cell=counter, pbc=True, positions=pos)
        calc = SinglePointCalculator(atoms, energy=eng_, forces=force)
        atoms.set_calculator(calc)
        atoms_traj.append(atoms)
    return atoms_traj


def get_remote_folder_info(calc, transport):
    """Get the information of the remote folder of a calculation"""
    path = calc.outputs.remote_folder.get_remote_path()
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
    popns = []
    rec = False
    with open(seed + '.castep') as fhd:
        for line in fhd:
            if "Atomic Populations (Mulliken)" in line:
                record = io.StringIO()
                rec = True

            # record information
            if rec is True:
                if line.strip() == "":
                    rec = False
                    record.seek(0)
                    popns.append(record)
                else:
                    record.write(line)

    return popns


def read_popn(fname):
    """Read population file into pandas dataframe"""
    import pandas as pd
    table = pd.read_table(fname,
                          sep=r"\s\s+",
                          header=2,
                          comment="=",
                          engine="python")
    return table


def export_calculation(node, output_dir, prefix=None):
    """
    Export one calculation a a directory
    """
    from aiida.orm.utils.repository import FileType
    from pathlib import Path

    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    def bwrite(node, outpath):
        """Write the objects stored under a node to a certain path"""
        for objname in node.list_object_names():
            if node.get_object(objname).type != FileType.FILE:
                continue
            with node.open(objname, mode='rb') as fsource:
                name, suffix = objname.split('.')
                if prefix and name == node.get_option('seedname'):
                    outname = prefix + '.' + suffix
                else:
                    outname = objname
                fpath = str(outpath / outname)
                with open(fpath, 'wb') as fout:
                    readlength = 1024 * 512  # 1MB
                    while True:
                        buf = fsource.read(readlength)
                        if buf:
                            fout.write(buf)
                        else:
                            break

    #inputs
    bwrite(node, output_dir)

    # outputs
    retrieved = node.outputs.retrieved
    bwrite(retrieved, output_dir)


def compute_kpoints_spacing(cell, grid, unit="2pi"):
    """
    Compute the spacing of the kpoints in the reciprocal space.
    Spacing = 1 / cell_length / mesh for each dimension.
    Assume orthogonal cell shape.
    """
    cell = np.asarray(cell, dtype=np.float)
    grid = np.asarray(grid, dtype=np.float)

    spacings = 1. / cell / grid
    if unit == "1/A":
        spacings *= 2 * np.pi
    elif unit != "2pi":
        raise ValueError("Unit {} is not unkown".format(unit))
    return spacings

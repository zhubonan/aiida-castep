"""
Parser interface for CASTEP bin file

A few quantities are only avaliable from the CASTEP bin file
"""
import numpy as np

from castepxbin import read_castep_bin
from .constants import units


class CastepbinFile:
    """
    Parser for the `castep_bin` file.

    The heavy lifting is done by the `castepxbin` package, but here we need to do unit
    conversion and reorganisation.
    """
    def __init__(self, fileobj=None, filename=None):
        """
        Instantiate from an file object
        """
        self.filename = filename
        if fileobj:
            self.fileobj = fileobj
        else:
            self.fileobj = open(filename, mode="rb")

        self.raw_data = read_castep_bin(fileobj=self.fileobj)
        self.data = {}

        # Close the file handle if it is opened by us
        if filename is not None:
            self.fileobj.close()

    @property
    def eigenvalues(self):
        """Return the eigenvalues array with shape (ns, nk, nb)"""
        array = self.raw_data.get('eigenvalues')
        if array is None:
            return None
        # Change from nb, nk, ns to ns, nk, nb
        array = np.swapaxes(array, 0, 2) * units['Eh']
        return array

    @property
    def total_energy(self):
        """Total energy in eV"""
        return self.raw_data['total_energy'] * units['Eh']

    @property
    def occupancies(self):
        """Return the occupation array with shape (ns, nk, nb)"""
        array = self.raw_data.get('occupancies')
        if array is None:
            return None
        # Change from nb, nk, ns to ns, nk, nb
        array = np.swapaxes(array, 0, 2)
        return array

    @property
    def kpoints(self):
        """Return the kpoints array with shape (nk, 3)"""
        array = self.raw_data.get('kpoints_of_eigenvalues')
        if array is None:
            return None
        # Change from (3, nk) to (nk, 3)
        array = np.swapaxes(array, 0, 1)
        return array

    @property
    def kpoints_current_cell(self):
        """
        Return the ordered kpoints array of the current cell with shape (nk, 3)
        The order of these kpoints may not be consistent with the eigenvalues.
        """
        array = self.raw_data.get('kpoints')
        if array is None:
            return None
        # Change from (3, nk) to (nk, 3)
        array = np.swapaxes(array, 0, 1)
        return array

    @property
    def kpoint_weights(self):
        """Return the weights of the kpoints in the internal order"""
        raw_weights = self.raw_data['kpoint_weights'].copy()
        sort_idx = self.kpoints_indices
        return raw_weights[sort_idx]

    @property
    def kpoints_indices(self):
        """
        Return the indices of the kpoints

        The kpoints, eigenvalues, and occupations may not be in the original
        order as defined by the cell file, if the calculations is parallelised
        over the kpoints.

        This property gives the index of the kpoints so that the original order
        can be recovered.

        Note that most properties are in the "internal" order of kpoints, the original
        order is mostly useful for band structure calculations where the list of kpoints
        is explicitly given.
        """
        eigen_kpoints = self.kpoints
        current_kpoints = np.swapaxes(self.raw_data.get('kpoints'), 0, 1)
        output_indices = np.zeros(len(current_kpoints), dtype=int)
        # Search through original list of kpoints
        for idx, kpt in enumerate(eigen_kpoints):
            this_idx = -1
            for (idx_orig, orig_kpt) in enumerate(current_kpoints):
                if np.all(np.abs((kpt - orig_kpt)) < 1e-10):
                    this_idx = idx_orig
                    break
            if this_idx == -1:
                raise RuntimeError(
                    f"Kpoint {kpt} is not found in the kpoints list of the current cell"
                )
            output_indices[idx] = this_idx
        return output_indices

    @property
    def forces(self):
        """Return the force array in unit eV/A"""
        array = self.raw_data.get('forces')
        if array is None:
            return None
        forces = self._reindex3(array)
        forces = forces * (units['Eh'] / units['a0'])
        return forces

    @property
    def scaled_positions(self):
        """Return the scaled positions"""
        array = self.raw_data.get('ionic_positions')
        if array is None:
            return None
        return self._reindex3(array)

    @property
    def fermi_energy(self):
        """Return the feremi energies"""
        out = [self.raw_data['fermi_energy'] * units['Eh']]
        if "fermi_energy_second_spin" in self.raw_data:
            out.append(self.raw_data['fermi_energy_second_spin'] * units['Eh'])
        return out

    @property
    def cell(self):
        """Cell matrix (of row vectors)"""
        array = self.raw_data.get('real_lattice')
        return array * units['a0']

    def _reindex3(self, array):
        """Reshape the array (N, i_ion, i_species) into the common (NION, N) shape"""
        nelem, _, nspecies = array.shape
        nions_in_species = self.raw_data['num_ions_in_species']
        nsites = sum(nions_in_species)
        output = np.zeros((nsites, nelem), dtype=array.dtype)

        # Reconstruct the array with shape (NIONS, N)
        i = 0
        for ispec in range(nspecies):
            for iion in range(nions_in_species[ispec]):
                output[i, :] = array[:, iion, ispec]
                i += 1

        return output

    def _reindex2(self, array):
        """Reshape the array (N, i_ion, i_species) into the common (NION, N) shape"""
        _, nspecies = array.shape
        nions_in_species = self.raw_data['num_ions_in_species']
        nsites = sum(nions_in_species)
        output = np.zeros(nsites, dtype=array.dtype)

        # Reconstruct the array with shape (NIONS, N)
        i = 0
        for ispec in range(nspecies):
            for iion in range(nions_in_species[ispec]):
                output[i] = array[iion, ispec]
                i += 1

        return output

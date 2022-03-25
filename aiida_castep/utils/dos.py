"""
Module for density of state proces processing
"""
import numpy as np


class DOSProcessor:
    """
    Class for post-processing DOS data
    """
    def __init__(self,
                 bands_data,
                 weights,
                 smearing=0.05,
                 min_eng=None,
                 max_eng=None,
                 bin_width_internal=0.001):
        """
        Instantiate an ``DOSProcessor`` object

        :param bands_data: An np array of the eigenvalues. The order of the dimensions should be (Nspin, Nkpoints, Nbands),
            or (Nkpoints, Nbands).
        :param weights: An 1D array of the weights of each kpoint.
        :param smearing: Width for Gaussian Smearing
        :param max_eng: Maximum energy for the bins
        :param min_eng: Minimum energy for the bins
        :param bin_width_internal: Width of the bin used for counting number of states.
        """

        # Reshape to ensure always 3 dimensions
        if bands_data.ndim == 2:
            bands_data = np.reshape(bands_data, (1, ) + bands_data.shape)

        self.bands_data = bands_data
        self.weights = weights
        self.smearing = smearing

        # Set min and max
        self.min_eng = min_eng if min_eng else self.min_eigen_value - 5.0
        self.max_eng = max_eng if max_eng else self.max_eigen_value + 5.0

        # Set the bins for the energies initially - these are the "left" edges
        self.bins = np.arange(self.min_eng, self.max_eng + bin_width_internal,
                              bin_width_internal)

        # Nominated energies are the mid points of the bins
        self.energies = (self.bins[1:] + self.bins[:-1]) / 2

    @property
    def has_spin(self):
        return self.bands_data.ndim == 3

    def get_dos(self, dropdim=False, npoints=2000):
        """
        Process the density of states by Gaussian smearing

        Here we use a two-step process. First the eigenvalues counted nto a fine grid, and under
        which a 1d gaussian filter is applied. Then the fine grid is resampled to the normal bin size.
        This way, energies that are near the bin edges are smeared with better accuracy.

        :param dropdim: Squeeze the first dimension of the output array, e.g. output 1D array if there is
            only a single spin channel.
        :param npoints: Number of the points for the output DOS array.
        :returns: A 1D array of the density of states.
        """

        nspin, _, nbands = self.bands_data.shape

        counts = []
        for ispin in range(nspin):
            # Construct the weights array with the same shape as the bands array
            weights = np.stack([self.weights] * nbands, axis=-1)

            # Construct the weights array with the same shape as the bands array
            hist_count, _ = np.histogram(self.bands_data[ispin, :, :],
                                         bins=self.bins,
                                         weights=weights)
            counts.append(hist_count)

        counts = np.stack(counts, axis=0)

        # Apply smearing by convoluting with a gaussian kernel
        kernel = gaussian_kernel(self.smearing, self.bin_width)

        broadened = np.zeros(counts.shape)
        for ispin in range(nspin):
            broadened[ispin, :] = np.convolve(counts[ispin, :],
                                              kernel,
                                              mode='same')

        # Resample by linear interpolation
        out_energies = np.linspace(self.min_eng, self.max_eng, npoints)
        interp_dos = np.zeros((nspin, ) + out_energies.shape)
        for ispin in range(nspin):
            interp_dos[ispin, :] = np.interp(out_energies, self.energies,
                                             broadened[ispin, :])

        if dropdim and interp_dos.shape[0] == 1:
            interp_dos = np.squeeze(interp_dos, axis=0)
        return out_energies, interp_dos

    @property
    def min_eigen_value(self):
        """Minimum eigenvalue"""
        return self.bands_data.min()

    @property
    def max_eigen_value(self):
        """Maximum eigenvalue"""
        return self.bands_data.max()

    @property
    def bin_width(self):
        """Width of the energy bins"""
        return self.bins[2] - self.bins[1]


def gaussian_kernel(sigma, bin_width, truncate=10):
    """
    Computer the gaussian kernel used for performing convolution

    :param sigma: The sigma of the gaussian.
    :param bin_width: Width of the energy bins.
    :param truncate: Beyond how many sigma should the values be truncated.

    Returns a 1D array of the gaussian kernel.
    """

    nbins = sigma * truncate // bin_width
    bins = np.arange(-bin_width * nbins, bin_width * (nbins + 1), bin_width)
    return np.exp(-0.5 * bins**2 / (sigma**2)) * 1 / sigma / np.sqrt(2 * np.pi)

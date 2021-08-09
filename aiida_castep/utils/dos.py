"""
Module for density of state proces processing
"""
from scipy.ndimage import gaussian_filter1d
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
                 npoints=1000,
                 bin_width=None):
        """
        Instantiate an ``DOSProcessor`` object

        :param bands_data: An numpy array of the eigenvalues. The order of the dimensions should be (Nspin, Nkpoints, Nbands),
            or (Nkpoints, Nbands).
        :param weights: An 1D array of the weights of each kpoint.
        :param smearing: Width for Gaussian Smearing
        """
        self.bands_data = bands_data
        self.weights = weights
        self.smearing = smearing

        # Set min and max
        self.min_eng = min_eng if min_eng else self.min_eigen_value - 5.0
        self.max_eng = max_eng if max_eng else self.max_eigen_value + 5.0

        # Set the bins for the energies
        if not bin_width:
            bin_width = (self.max_eng - self.min_eng) / npoints
        self.bins = np.arange(self.min_eng, self.max_eng + bin_width,
                              bin_width)

        # Nominated energies are the mid points of the bins
        self.energies = (self.bins[1:] + self.bins[:-1]) / 2

    @property
    def has_spin(self):
        return self.bands_data.ndim == 3

    def get_dos(self, factor=4):
        """
        Process the density of states by Gaussian smearing

        Here we use a two-step process. First the eigenvalues counted nto a fine grid, and under
        which a 1d gaussian filter is applied. Then the fine grid is resampled to the normal bin size.
        This way, energies that are near the bin edges are smeared with better accuracy.

        :param factor: Super-sampling parameter for the fine grid
        :returns: A 1D array of the density of states.
        """

        fine_bin_width = (self.bins[1] - self.bins[0]) / factor
        bins = np.arange(self.min_eng, self.max_eng + fine_bin_width,
                         fine_bin_width)
        energies = (bins[1:] + bins[:-1]) / 2

        if self.has_spin:
            nspin, _, nbands = self.bands_data.shape
            # Construct the weights array with the same shape as the bands array
            weights = np.stack([self.weights] * nbands, axis=-1)
            weights = np.stack([weights] * nspin, axis=0)
        else:
            _, nbands = self.bands_data.shape
            # Construct the weights array with the same shape as the bands array
            weights = np.stack([self.weights] * nbands, axis=-1)

        hist_count, _ = np.histogram(self.bands_data,
                                     bins=energies,
                                     weights=weights)
        # Apply smearing
        filtered = gaussian_filter1d(hist_count, self.smearing)
        # Resample - combine N bins into one
        filtered = filtered.reshape((-1, factor)).sum(axis=-1) / factor
        return filtered

    @property
    def min_eigen_value(self):
        return self.bands_data.min()

    @property
    def max_eigen_value(self):
        return self.bands_data.max()

"""
Calculations of CASTEP
"""
import os
from aiida_castep.calculations import BaseCastepInputGenerator

from aiida.orm.calculation.job import JobCalculation
from aiida.common.utils import classproperty
from aiida.orm.data.array.kpoints import KpointsData


class SinglePointCalculation(BaseCastepInputGenerator, JobCalculation):
    """
    Basic mode for CASTEP calculation
    """

    _default_symlink_usage = False

    def _init_internal_params(self):

        super(SinglePointCalculation, self)._init_internal_params()

        self._defaut_parser = "castep.singlepoint"

        self._block_keywords = []

        self._use_kpoints = True

        self._SEED_NAME = "aiida"


    @classproperty
    def _use_methods(cls):
        """
        Extend the parent _use_methods with further keys
        """

        retdict = JobCalculation._use_methods
        retdict.update(BaseCastepInputGenerator._baseclass_use_methods)

        # Not all calculation need kpoints?
        retdict['kpoints'] = {
            'valid_types': KpointsData,
            'additional_parameter': None,
            'linkname': 'kpoints',
            'docstring': "Use the node defining the kpoint sampling to use",
        }

        return retdict

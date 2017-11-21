"""
Calculations of CASTEP
"""
from aiida_castep.calculations.base import BaseCastepInputGenerator

from aiida.orm.calculation.job import JobCalculation
from aiida.common.utils import classproperty
from aiida.orm.data.array.kpoints import KpointsData


class CastepCalculation(BaseCastepInputGenerator, JobCalculation):
    """
    Basic mode for CASTEP calculation
    """

    _default_symlink_usage = False

    def _init_internal_params(self):

        super(CastepCalculation, self)._init_internal_params()

        self._default_parser = "castep.castep"

        self._use_kpoints = True

        self._SEED_NAME = "aiida"
        self._DEFAULT_INPUT_FILE = "aiida.cell"
        self._DEFAULT_OUTPUT_FILE = "aiida.castep"


    @classproperty
    def _use_methods(cls):
        """
        Extend the parent _use_methods with further keys
        """

        retdict = JobCalculation._use_methods
        retdict.update(BaseCastepInputGenerator._baseclass_use_methods)

        # Not all calculation need kpoints
        retdict['kpoints'] = {
            'valid_types': KpointsData,
            'additional_parameter': None,
            'linkname': 'kpoints',
            'docstring': "Use the node defining the kpoint sampling to use",
        }

        return retdict

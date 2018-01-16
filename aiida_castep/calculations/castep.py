"""
Calculations of CASTEP
"""
from aiida_castep.calculations.base import BaseCastepInputGenerator

from aiida.orm.calculation.job import JobCalculation
from aiida.common.utils import classproperty
from aiida.common.exceptions import InputValidationError
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

class CastepExtraKpnCalculation(CastepCalculation):
    """
    CASTEP calculation with extra kpoints (e.g SPEC, BS, PHONON, SPECTRAL)
    """
    KPN_NAME = ""
    TASK = ""
    CHECK_EXTRA_KPN = False

    @classproperty
    def kpn_name(cls):
        return cls.KPN_NAME.lower()

    @classproperty
    def _use_methods(cls):

        retdict = CastepCalculation._use_methods

        retdict['{}_kpoints'.format(cls.KPN_NAME.lower())] = {

            'valid_types': KpointsData,
            'additional_parameter': None,
            'linkname' : '{}_kpoints'.format(cls.kpn_name),
            'docstring': "Use the node defining the kpoint sampling for band {}  calculation".format(cls.TASK.lower())
        }
        return retdict

    def _generate_CASTEPinputdata(self, *args, **kwargs):
        """Add BS kpoints information to the calculation"""

        param = args[0].get_dict()

        if param['PARAM']['task'].lower() != self.TASK.lower():
            raise InputValidationError("Wrong TASK value set in PARAM")

        cell, param, local_copy = super(CastepExtraKpnCalculation, self)._generate_CASTEPinputdata(*args, **kwargs)

        # Check the existence of extra kpoints
        try:
            extra_kpns = kwargs[self.get_linkname('{}_kpoints'.format(self.kpn_name))]
        except KeyError:
            if self.CHECK_EXTRA_KPN:
                raise InputValidationError("{}_kpoints"
                " node not found".format(self.kpn_name))
            else:
                return cell, param, local_copy

        # Add information in the node to cell file
        try:
            mesh, offset = extra_kpns.get_kpoints_mesh()
            has_mesh = True
        except AttributeError:
            try:
                bs_kpts_list = extra_kpns.get_kpoints()
                num_kpoints = len(bs_kpts_list)
                has_mesh = False
                if num_kpoints == 0:
                    raise InputValidationError(
                        "At least one k points must be provided")
            except AttributeError:
                raise InputValidationError(
                    "No valid {}_kpoints have been found".format(self.kpn_name))

            try:
                _, weights = extra_kpns.get_kpoints(also_weights=True)

            except AttributeError:
                import numpy as np
                weights = np.ones(num_kpoints, dtype=float) / num_kpoints

        if has_mesh is True:
            cell += ("\n{}_kpoints_mp_grid"
                " : {} {} {}\n".format(self.kpn_name, *mesh))
        else:
            bs_kpts_lines = [("%BLOCK "
             "{}_KPOINTS_LIST".format(self.kpn_name.upper()))]
            for kpoint, weight in zip(bs_kpts_list, weights):
                bs_kpts_lines.append("{:18.10f} {:18.10f} "
                     "{:18.10f} {:18.10f}".format(kpoint[0],
                                                  kpoint[1],
                                                  kpoint[2], weight))
            bs_kpts_lines.append("%ENDBLOCK "
                "{}_KPOINTS_LIST".format(self.kpn_name.upper()))
            cell += "\n" + "\n".join(bs_kpts_lines)
        return cell, param, local_copy

class CastepBSCalculation(CastepExtraKpnCalculation):
    """
    CASTEP bandstructure calculation
    """

    TASK = "BANDSTRUCTURE"
    KPN_NAME = "BS"

class CastepSpectralCalculation(CastepExtraKpnCalculation):
    """
    CASTEP spectral calculation
    """
    TASK = "SPECTRAL"
    KPN_NAME = "SPECTRAL"

class CastepOpticsCalclulation(CastepExtraKpnCalculation):
    """
    CASTEP Optics calculation
    """
    TASK = "OPTICS"
    KPN_NAME = "OPTICS"


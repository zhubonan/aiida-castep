"""
Calculations of CASTEP
"""
from aiida.orm import CalculationFactory
from aiida.orm import DataFactory
from aiida.common.utils import classproperty
from aiida.common.exceptions import InputValidationError
from .utils import get_castep_ion_line
from aiida_castep.calculations.base import BaseCastepInputGenerator

JobCalculation = CalculationFactory("job", True)
KpointsData = DataFactory("array.kpoints")
StructureData = DataFactory("structure")


class CastepCalculation(BaseCastepInputGenerator, JobCalculation):
    """
    Class representing a generic CASTEP calculation -
    This class should work for all types of calculations.
    """

    _default_symlink_usage = True
    _acceptable_tasks = ["singlepoint", "geometryoptimization",
                         "geometryoptimisation",]

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

class TaskSpecificCalculation(CastepCalculation):
    """
    Class for Calculations that only allow certain tasks
    """

    _acceptable_tasks = []
    def _generate_CASTEPinputdata(self, *args, **kwargs):
        param = args[0].get_dict()

        if param['PARAM']['task'].lower() not in map(str.lower, self._acceptable_tasks):
            raise InputValidationError("Wrong TASK value {}"
                                       " set in PARAM".format(param['PARAM']['task'].lower()))
        return super(TaskSpecificCalculation, self)._generate_CASTEPinputdata(*args, **kwargs)


class CastepTSCalculation(TaskSpecificCalculation):
    """
    CASTEP calculation for transition state search. Use an extra input product structure.
    """
    _acceptable_tasks = ["transitionstatesearch"]

    @classproperty
    def _use_methods(cls):

        retdict = super(CastepTSCalculation, cls)._use_methods
        retdict['product_structure'] = {
            'valid_types': StructureData,
            'additional_parameter': None,
            'linkname': 'product_structure',
            'docstring': "Use the node defining the structure as the product structure in transition state search."
        }
        return retdict

    def _generate_CASTEPinputdata(self, *args, **kwargs):
        """
        Override superclass methods
        """
        cell, param, local_copy = super(CastepTSCalculation, self).\
                    _generate_CASTEPinputdata(*args, **kwargs)
        p_structure = kwargs[self.get_linkname('product_structure')]

        pdt_position_list = []
        for site in p_structure.sites:
            kind = p_structure.get_kind(site.kind_name)
            name = kind.symbol
            line = get_castep_ion_line(name, site.position)
            pdt_position_list.append(line)

        cell["POSITIONS_ABS_PRODUCT"] = pdt_position_list
        return cell, param, local_copy



class CastepExtraKpnCalculation(TaskSpecificCalculation):
    """
    CASTEP calculation with extra kpoints (e.g SPEC, BS, PHONON, SPECTRAL)
    """
    KPN_NAME = ""  # Alias of the name, e.g BS for bandstructure calculation
    CHECK_EXTRA_KPN = False  # Check the existence of extra kpoints node

    @classproperty
    def kpn_name(cls):
        return cls.KPN_NAME.lower()

    @classproperty
    def _use_methods(cls):

        retdict = CastepCalculation._use_methods

        retdict['{}_kpoints'.format(cls.KPN_NAME.lower())] = {

            'valid_types': KpointsData,
            'additional_parameter': None,
            'linkname': '{}_kpoints'.format(cls.kpn_name),
            'docstring': "Use the node defining the kpoint sampling for band {}  calculation".format(cls.TASK.lower())
        }
        return retdict

    def _generate_CASTEPinputdata(self, *args, **kwargs):
        """Add BS kpoints information to the calculation"""

        cell, param, local_copy = super(
            CastepExtraKpnCalculation, self)._generate_CASTEPinputdata(*args, **kwargs)

        # Check the existence of extra kpoints
        try:
            extra_kpns = kwargs[self.get_linkname(
                '{}_kpoints'.format(self.kpn_name))]
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
            mesh_name = "{}_kpoints_mp_grid".format(self.kpn_name)
            cell[mesh_name] = "{} {} {}".format(*mesh)
        else:
            bs_kpts_lines = []
            for kpoint, weight in zip(bs_kpts_list, weights):
                bs_kpts_lines.append("{:18.10f} {:18.10f} "
                                     "{:18.10f} {:18.10f}".format(kpoint[0],
                                                                  kpoint[1],
                                                                  kpoint[2],
                                                                  weight))
            bname = "{}_KPOINTS_LIST".format(self.kpn_name.upper())
            cell[bname] = bs_kpts_lines
        return cell, param, local_copy

    @classmethod
    def continue_from(cls, *args, **kwargs):
        """
        Create a new calcualtion as a continution from a given calculation.
        This is effectively an "restart" for CASTEP and a lot of the parameters
        can be tweaked. For example, conducting bandstructure calculation from
        finished geometry optimisations.
        :param bool ignore_state: Ignore the state of parent calculation
        :param str restart_type: "continuation" or "restart".
        If set to continuation the child calculation has keyword
        'continuation' set.
        :param bool reuse: Wether we want to reuse the previous calculation.
        only applies for "restart" run
        :param bool parent_folder_symlink: if True, symlink are used instead
        of hard copies of the files. Default given be
        self._default_symlink_usage
        :param bool use_output_structure: if True, the output structure of
        parent calculation is used as the input of the child calculation.
        This is useful for photon/bs calculation.

        See also: create_restart
        """
        cout = super(CastepExtraKpnCalculation,
                     cls).continue_from(*args, **kwargs)

        # Check the task keyword
        param = cout.get_inputs_dict()[cout.get_linkname('parameters')]
        pd = param.get_dict()

        task = pd['PARAM'].get('task')
        if task and task == cls.TASK.lower():
            pass
        else:
            # Replace task
            pd['PARAM']['task'] = cls.TASK.lower()
            from aiida.orm import DataFactory
            ParameterData = DataFactory('parameter')
            new_param = ParameterData(dict=pd)
            cout._remove_link_from(cout.get_linkname('parameters'))
            cout.use_parameters(new_param)

        return cout


class CastepBSCalculation(CastepExtraKpnCalculation):
    """
    CASTEP bandstructure calculation
    """

    TASK = "BANDSTRUCTURE"
    _acceptable_tasks = [TASK]
    KPN_NAME = "BS"


class CastepSpectralCalculation(CastepExtraKpnCalculation):
    """
    CASTEP spectral calculation
    """
    TASK = "SPECTRAL"
    _acceptable_tasks = [TASK]
    KPN_NAME = "SPECTRAL"


class CastepOpticsCalclulation(CastepExtraKpnCalculation):
    """
    CASTEP Optics calculation
    """
    TASK = "OPTICS"
    _acceptable_tasks = [TASK]
    KPN_NAME = "OPTICS"

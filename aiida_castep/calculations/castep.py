"""
Calculations of CASTEP
"""
from __future__ import print_function
from __future__ import absolute_import
import warnings
import six
from six.moves import zip

from aiida.common import InputValidationError, MultipleObjectsError
from aiida.common.utils import classproperty
from aiida.common import CalcInfo, CodeInfo
from aiida.plugins import DataFactory
from aiida.engine import ProcessBuilder
from aiida.orm.nodes.data.base import to_aiida_type

from aiida.orm import UpfData
from aiida.engine import CalcJob

from ..common import INPUT_LINKNAMES, OUTPUT_LINKNAMES, EXIT_CODES_SPEC
from .inpgen import CastepInputGenerator
from ..data.otfg import OTFGData
from ..data.usp import UspData
from .utils import get_castep_ion_line, _lowercase_dict, _uppercase_dict
from .datastructure import CellFile, ParamFile
from .tools import castep_input_summary, update_parameters

from .._version import CALC_PARSER_VERSION
__version__ = CALC_PARSER_VERSION

KpointsData = DataFactory("array.kpoints")
StructureData = DataFactory("structure")
Dict = DataFactory("dict")

inp_ln = INPUT_LINKNAMES
out_ln = OUTPUT_LINKNAMES
ecodes = EXIT_CODES_SPEC

# Define the version of the calculation


class CastepCalculation(CalcJob, CastepInputGenerator):
    """
    Class representing a generic CASTEP calculation -
    This class should work for all types of calculations.
    """

    # Create a dict of the defaults
    _DEFAULTS = {
        "seedname": 'aiida',
        'symlink_usage': True,
        'parent_folder_name': 'parent',
        'parser_name': 'castep.castep',
        'use_kpoints': True,
    }
    _DEFAULTS['input_filename'] = _DEFAULTS['seedname'] + '.cell'
    _DEFAULTS['output_filename'] = _DEFAULTS['seedname'] + '.castep'

    _default_retrieve_list = [
        "*.err", "*.den_fmt", "*.elf_fmt", "*-out.cell", "*.pdos_bin"
    ]

    # Some class methods
    retrieve_dict = {
        "phonon": [".phonon"],
        "phonon+efield": [".phonon", ".efield"],
        "magres": [".magres"],
        "transitionstatesearch": [".ts"],
        "molecular dynamics": [".md"],
        "moleculardynamics": [".md"],
        "geometryoptimisation": [".geom"],
        "geometryoptimization": [".geom"],
        "spectral": [".ome_bin", ".dome_bin"],
    }

    # NOT CURRENTLY USED
    _acceptable_tasks = [
        "singlepoint",
        "geometryoptimization",
        "geometryoptimisation",
    ]

    _copied_attributes = [
        "jobresource_param", "custom_scheduler_commands",
        "max_wallclock_seconds"
    ]

    @classmethod
    def define(cls, spec):
        import aiida.orm as orm
        super(CastepCalculation, cls).define(spec)

        # Initialise interal params, saved as metadata.options
        for key, value in cls._DEFAULTS.items():
            port_name = 'metadata.options.' + key
            spec.input(port_name, default=value, valid_type=type(value))

        spec.input(
            'metadata.options.retrieve_list',
            valid_type=list,
            default=cls._default_retrieve_list)

        # Begin defining the input nodes
        spec.input(
            inp_ln['structure'],
            valid_type=orm.StructureData,
            help="Defines the input structure")
        spec.input(
            inp_ln['settings'],
            valid_type=orm.Dict,
            serializer=to_aiida_type,
            required=False,
            help="Use an additional node for sepcial settings")
        spec.input(
            inp_ln['parameters'],
            valid_type=orm.Dict,
            serializer=to_aiida_type,
            help="Use a node that sepcifies the input parameters")
        spec.input(
            inp_ln['parent_calc_folder'],
            valid_type=orm.RemoteData,
            help=
            'Use a remote folder as the parent folder. Useful for restarts.',
            required=False)
        spec.input_namespace(
            'pseudos',
            valid_type=(UspData, OTFGData, UpfData),
            help=("Use nodes for the pseudopotentails of one of"
                  "the element in the structure. You should pass a"
                  "a dictionary specifying the pseudpotential node for"
                  "each kind such as {O: <PsudoNode>}"),
            dynamic=True)
        spec.input(
            inp_ln['kpoints'],
            valid_type=KpointsData,
            required=False,
            help="Use a node defining the kpoints for the calculation")

        # Define the exit codes
        for smsg, (code, msg) in ecodes.items():
            spec.exit_code(code, smsg, message=msg)

        # Define the output nodes
        spec.output(
            out_ln['results'],
            required=True,
            valid_type=Dict,
            help='Parsed results in a dictionary format.')

        spec.outputs.dynamic = True
        # Define the default inputs, enable CalcJobNode to use .res
        spec.default_output_node = out_ln['results']

    def prepare_for_submission(self, folder):
        """
        Routine to be called when create the input files and other stuff

        :param folder: a aiida.common.folders.Folder subclass where
                           the plugin should put all its files.
        :param inputdict: a dictionary with the input nodes, as they would
                be returned by get_inputs_dict (without the Code!)
        """
        self.prepare_inputs()

        local_copy_list = []

        remote_copy_list = []
        remote_symlink_list = []

        # TODO allow checking of inputs
        #if self.inputs.metadata.options._auto_input_validation is True:
        #    self.check_castep_input(self.param_dict, auto_fix=False)

        # If requested to reuse, check if the parent_calc_folder is defined
        require_parent = False
        for k in self.param_dict:
            if str(k).lower() in ["reuse", "continuation"]:
                require_parent = True
                break

        parent_calc_folder = self.inputs.get('parent_calc_folder')
        if parent_calc_folder is None and require_parent:
            raise InputValidationError(
                "No parent calculation folder passed"
                " for restart calculation using reuse/continuation")

        ##############################
        # END OF INITIAL INPUT CHECK #
        ##############################

        # Generate input file
        self.prepare_inputs(reset=True)
        local_copy_list.extend(self.local_copy_list_to_append)
        seedname = self.inputs.metadata.options.seedname

        cell_fn = seedname + ".cell"
        param_fn = seedname + ".param"

        with folder.open(cell_fn, mode='w') as incell:
            incell.write(six.u(self.cell_file.get_string()))

        with folder.open(param_fn, mode="w") as inparam:
            inparam.write(six.u(self.param_file.get_string()))

        # IMPLEMENT OPERATIONS FOR RESTART

        symlink = self.inputs.metadata.options.symlink_usage
        parent_calc_folder = self.inputs.get('parent_calc_folder', None)
        if parent_calc_folder:
            comp_uuid = parent_calc_folder.computer.uuid
            remote_path = parent_calc_folder.get_remote_path()
            if symlink:
                remote_list = remote_symlink_list
            else:
                remote_list = remote_copy_list
            remote_list.append(
                (comp_uuid, remote_path,
                 self.inputs.metadata.options.parent_folder_name))

        calcinfo = CalcInfo()
        calcinfo.uuid = self.uuid

        # COPY/SYMLINK LISTS
        calcinfo.local_copy_list = local_copy_list
        calcinfo.remote_copy_list = remote_copy_list
        calcinfo.remote_symlink_list = remote_symlink_list

        # SET UP extra CMDLINE arguments
        cmdline_params = self.settings_dict.pop("CMDLINE", [])

        # Extra parameters are added after the seed for CASTEP
        calcinfo.cmdline_params = [seedname] + list(cmdline_params)

        # CASTEP don't have any STDOUT etc when running calculations
        # Error is shown in the *.err file

        # Construct codeinfo instance
        codeinfo = CodeInfo()
        codeinfo.cmdline_params = [seedname] + list(cmdline_params)
        codeinfo.code_uuid = self.inputs.code.uuid
        calcinfo.codes_info = [codeinfo]

        # Retrieve by default the .castep file and the bands file
        calcinfo.retrieve_list = []
        calcinfo.retrieve_list.append(seedname + ".castep")
        calcinfo.retrieve_list.append(seedname + ".bands")

        settings_retrieve_list = self.settings_dict.pop(
            "ADDITIONAL_RETRIEVE_LIST", [])
        calcinfo.retrieve_list.extend(settings_retrieve_list)

        # If we are doing geometryoptimisation retrieved the geom file and -out.cell file
        calculation_mode = self.param_file.get("task", "singlepoint")

        # dictionary for task specific file retrieve
        task_extra = self.retrieve_dict.get(calculation_mode.lower(), [])
        for suffix in task_extra:
            settings_retrieve_list.append(seedname + suffix)

        # Retrieve output cell file if requested
        if self.param_file.get("write_cell_structure"):
            settings_retrieve_list.append(seedname + "-out.cell")

        calcinfo.retrieve_list += settings_retrieve_list
        calcinfo.retrieve_list += self._default_retrieve_list

        # Remove parser options in the setting dictionary
        # At the moment parser options are not used here

        if self.settings_dict:
            raise InputValidationError(
                "The following keys have been found in "
                "the settings input node, but were not understood: {}".format(
                    ",".join(list(self.settings_dict.keys()))))

        return calcinfo

    # Attach the input summary method
    @staticmethod
    def get_castep_input_summary(builder):
        """Summarize the input for a builder"""
        return castep_input_summary(builder)

    @classmethod
    def submit_test(cls, *args, **kwargs):
        """Test submission with a builder of inputs"""
        if args and isinstance(args[0], ProcessBuilder):
            return submit_test(args[0], inputs=kwargs)
        else:
            return submit_test(cls, inputs=kwargs)

    @classmethod
    def dryrun_test(cls, inputs, castep_exe='castep.serial', verbose=True):
        """
        Do a dryrun test in a folder with prepared builder or inputs
        """

        from fnmatch import fnmatch
        if isinstance(inputs, ProcessBuilder):
            inputs = dict(inputs)

        res = cls.submit_test(**inputs)
        folder = res[1]
        cinfo = res[0]

        def _print(inp):
            if verbose:
                print(inp)

        # Do a dryrun
        from subprocess import call, check_output
        try:
            output = check_output([castep_exe, "-v"]).decode()
        except OSError:
            _print("CASTEP executable '{}' is not found".format(castep_exe))
            return

        # Now start dryrun
        _print("Running with {}".format(
            check_output(["which", castep_exe]).decode()))
        _print(output)

        _print("Starting dryrun...")
        call(
            [castep_exe, "--dryrun"] + cinfo.cmdline_params,
            cwd=folder.abspath)

        # Check if any *err files
        contents = folder.get_content_list()
        for n in contents:
            if fnmatch(n, "*.err"):
                with folder.open(n) as fh:
                    _print("Error found in {}:\n".format(n))
                    _print(fh.read())
                raise InputValidationError("Error found during dryrun")

        # Gather information from the dryrun file
        import re
        dryrun_results = {}
        out_file = cinfo.cmdline_params[0] + '.castep'
        with folder.open(out_file) as fh:
            for line in fh:
                mth = re.match(r"\s*k-Points For SCF Sampling:\s+(\d+)\s*",
                               line)
                if mth:
                    dryrun_results["num_kpoints"] = int(mth.group(1))
                    _print("Number of k-points: {}".format(mth.group(1)))
                    mth = None
                    continue
                mth = re.match(
                    r"\| Approx\. total storage required"
                    r" per process\s+([0-9.]+)\sMB\s+([0-9.]+)", line)
                if mth:
                    dryrun_results["memory_MB"] = (float(mth.group(1)))
                    dryrun_results["disk_MB"] = (float(mth.group(2)))
                    _print("RAM: {} MB, DISK: {} MB".format(
                        mth.group(1), mth.group(2)))
                    mth = None
                    continue

        return folder, dryrun_results

    @staticmethod
    def update_paraemters(inputs, *args, **kwargs):
        """Update the paramters for a given input dictionary/builder"""
        return update_parameters(inputs, *args, **kwargs)


class Pot1dCalculation(CastepCalculation):
    """
    Class for pot1d Calculation
    """

    _default_retrieve_list = CastepCalculation.\
                              _default_retrieve_list + ["*.dat"]

    def _init_internal_params(self):
        super(Pot1dCalculation, self)._init_internal_params()
        self._default_parser = "castep.pot1d"

    @classmethod
    def from_calculation(self, calc, code, use_castep_bin=False, **kwargs):
        """
        Create pot1d calculation using existing calculation.
        ``code`` must be specified as it is different from the original CASTEP code.
        """

        out_calc = self.continue_from(
            calc,
            ignore_state=True,
            restart_type="continuation",
            use_output_structure=True,
            use_castep_bin=use_castep_bin,
            **kwargs)
        out_calc.use_code(code)
        return out_calc

    def _generate_CASTEPinputdata(self, *args, **kwargs):
        out = super(Pot1dCalculation, self).\
              _generate_CASTEPinputdata(*args, **kwargs)
        if out[1].get("continuation") is None:
            raise InputValidationError("pot1d requires "
                                       "continuation being set in .param")
        return out

    def get_withmpi(self):
        """
        pot1d is not compile with mpi.
        Hence the default is changed to False instead.
        """
        return self.get_attr('withmpi', False)


class TaskSpecificCalculation(CastepCalculation):
    """
    Class for Calculations that only allow certain tasks
    """

    _acceptable_tasks = []

    def _generate_CASTEPinputdata(self, *args, **kwargs):
        param = args[0].get_dict()

        # Check if task is correctly set
        all_tasks = [t.lower() for t in self._acceptable_tasks]
        if param['PARAM']['task'].lower() not in all_tasks:
            raise InputValidationError("Wrong TASK value {}"
                                       " set in PARAM".format(
                                           param['PARAM']['task'].lower()))
        return super(TaskSpecificCalculation, self)._generate_CASTEPinputdata(
            *args, **kwargs)


class CastepTSCalculation(TaskSpecificCalculation):
    """
    CASTEP calculation for transition state search. Use an extra input product structure.
    """
    _acceptable_tasks = ["transitionstatesearch"]

    @classproperty
    def _use_methods(self):

        retdict = super(CastepTSCalculation, self)._use_methods
        retdict['product_structure'] = {
            'valid_types':
            StructureData,
            'additional_parameter':
            None,
            'linkname':
            'product_structure',
            'docstring':
            "Use the node defining the structure as the product structure in transition state search."
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
    def kpn_name(self):
        return self.KPN_NAME.lower()

    @classproperty
    def _use_methods(self):

        retdict = CastepCalculation._use_methods

        retdict['{}_kpoints'.format(self.KPN_NAME.lower())] = {
            'valid_types':
            KpointsData,
            'additional_parameter':
            None,
            'linkname':
            '{}_kpoints'.format(self.kpn_name),
            'docstring':
            "Use the node defining the kpoint sampling for band {}  calculation"
            .format(self.TASK.lower())
        }
        return retdict

    def _generate_CASTEPinputdata(self, *args, **kwargs):
        """Add BS kpoints information to the calculation"""

        cell, param, local_copy = super(CastepExtraKpnCalculation,
                                        self)._generate_CASTEPinputdata(
                                            *args, **kwargs)

        # Check the existence of extra kpoints
        try:
            extra_kpns = kwargs[self.get_linkname('{}_kpoints'.format(
                self.kpn_name))]
        except KeyError:
            if self.CHECK_EXTRA_KPN:
                raise InputValidationError("{}_kpoints"
                                           " node not found".format(
                                               self.kpn_name))
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
                    "No valid {}_kpoints have been found".format(
                        self.kpn_name))

            try:
                _, weights = extra_kpns.get_kpoints(also_weights=True)

            except AttributeError:
                import numpy as np
                weights = np.ones(num_kpoints, dtype=float) / num_kpoints

        if has_mesh is True:
            mesh_name = "{}_kpoints_mp_grid".format(self.kpn_name)
            cell[mesh_name] = "{} {} {}".format(*mesh)
            if offset != [0., 0., 0.]:
                cell[mesh_name.replace("grid",
                                       "offset")] = "{} {} {}".format(*offset)
        else:
            bs_kpts_lines = []
            for kpoint, weight in zip(bs_kpts_list, weights):
                bs_kpts_lines.append("{:18.10f} {:18.10f} "
                                     "{:18.10f} {:18.10f}".format(
                                         kpoint[0], kpoint[1], kpoint[2],
                                         weight))
            bname = "{}_kpoints_list".format(self.kpn_name).upper()
            cell[bname] = bs_kpts_lines
        return cell, param, local_copy

    def create_restart(self, *args, **kwargs):
        """
        Create a restart of the calculation
        """
        out_calc = super(CastepExtraKpnCalculation, self).create_restart(
            *args, **kwargs)

        # Attach the extra kpoints node if it is there
        inp_name = "{}_kpoints".format(self.kpn_name)  # Name of the input
        linkname = self.get_linkname(inp_name)  # Name of the link

        extra_kpn_node = self.get_inputs_dict().get(linkname)
        if extra_kpn_node:
            getattr(out_calc, "use_" + inp_name)(extra_kpn_node)
        return out_calc

    def get_castep_input_summary(self):
        """
        Generate a dictionary to summarize the inputs to CASTEP
        """

        inp_name = "{}_kpoints".format(self.kpn_name)  # Name of the input
        linkname = self.get_linkname(inp_name)  # Name of the link

        out_dict = super(CastepExtraKpnCalculation,
                         self).get_castep_input_summary()
        out_dict[inp_name] = self.get_inputs_dict().get(linkname)
        return out_dict

    @classmethod
    def continue_from(self, *args, **kwargs):
        """
        Create a new calculation as a continuation from a given calculation.
        This is effectively an "restart" for CASTEP and a lot of the parameters
        can be tweaked. For example, conducting bandstructure calculation from
        finished geometry optimisation's.
        :param bool ignore_state: Ignore the state of parent calculation
        :param str restart_type: "continuation" or "restart".
        If set to continuation the child calculation has keyword
        'continuation' set.
        :param bool reuse: Whether we want to reuse the previous calculation.
        only applies for "restart" run
        :param bool parent_folder_symlink: if True, symlink are used instead
        of hard copies of the files. Default given be
        self._default_symlink_usage
        :param bool use_output_structure: if True, the output structure of
        parent calculation is used as the input of the child calculation.
        This is useful for photon/bs calculation.

        See also: create_restart
        """
        cout = super(CastepExtraKpnCalculation, self).continue_from(
            *args, **kwargs)

        # Check the task keyword
        param = cout.get_inputs_dict()[cout.get_linkname('parameters')]
        param_dict = param.get_dict()

        task = param_dict['PARAM'].get('task')
        if task and task == self.TASK.lower():
            pass
        else:
            # Replace task
            param_dict['PARAM']['task'] = self.TASK.lower()
            from aiida.plugins import DataFactory
            Dict = DataFactory('parameter')
            new_param = Dict(dict=param_dict)
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


def submit_test(process_class, inputs=None):
    """This essentially test the submition"""
    from aiida.engine.utils import instantiate_process
    from aiida.manage.manager import get_manager
    from aiida.common.folders import SandboxFolder

    if isinstance(process_class, ProcessBuilder):
        inputs = dict(process_class)
        process_class = process_class._process_class

    upd = {'store_provenance': False, 'dry_run': True}
    # Create copy so the original ones are not affected
    inputs = dict(inputs)
    if 'metadata' in inputs:
        inputs['metadata'] = dict(inputs['metadata'])
        inputs['metadata'].update(upd)
    else:
        inputs['metadata'] = upd
    # In any case, we do not want to store the provenance

    folder = SandboxFolder(sandbox_in_repo=False)
    manager = get_manager()
    runner = manager.get_runner()
    process = instantiate_process(runner, process_class, **inputs)

    calc_info = process.prepare_for_submission(folder)
    return calc_info, folder, process

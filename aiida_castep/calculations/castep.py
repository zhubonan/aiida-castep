"""
Calculations of CASTEP
"""
from __future__ import print_function
from __future__ import absolute_import
import six
from six.moves import zip

from aiida.common import InputValidationError
from aiida.common import CalcInfo, CodeInfo
from aiida.plugins import DataFactory
from aiida.engine import ProcessBuilder
from aiida.orm.nodes.data.base import to_aiida_type

from aiida.orm import UpfData, User
from aiida.engine import CalcJob

from ..common import INPUT_LINKNAMES, OUTPUT_LINKNAMES, EXIT_CODES_SPEC
from .inpgen import CastepInputGenerator
from ..data.otfg import OTFGData
from ..data.usp import UspData
from .utils import get_castep_ion_line
from .tools import (castep_input_summary, update_parameters,
                    use_pseudos_from_family, input_param_validator,
                    check_restart)

from .._version import CALC_PARSER_VERSION
__version__ = CALC_PARSER_VERSION

KpointsData = DataFactory("array.kpoints")
StructureData = DataFactory("structure")
Dict = DataFactory("dict")

inp_ln = INPUT_LINKNAMES
out_ln = OUTPUT_LINKNAMES
ecodes = EXIT_CODES_SPEC

# Define the version of the calculation

__all__ = ['CastepCalculation', 'submit_test']


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
        'withmpi': True,
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
    _write_headers = True

    _cell_links = [
        inp_ln['parameters'], inp_ln['structure'], inp_ln['settings'],
        inp_ln['kpoints']
    ]

    _param_links = [inp_ln['parameters']]

    # Extra kpoints - CASTEP has many calculation mode that take extra kpoints
    _extra_kpoints = {
        'spectral': {  # name XX_kpoints_list
            'task': ('spectra', ),
            'need_weights':
            True  # Whether the explicit kpoints need weights or not
        },
        'bs': {
            'task': ('bandstructure', ),  # task where the kpoints will be used
            'need_weigthts': False,
        },
        'phonon': {
            'task': ('phonon', 'phonon+efield'),
            'need_weights': False,
        },
        'phonon_fine': {
            'task': ('phonon', 'phonon+efield'),
            'need_weights': False,
        },
        'supercell': {
            'task': ('phonon', ),
            'need_weights': True,
        },
        'magres': {
            'task': ('magres', ),
            'need_weights': True,
        },
        'optics': {
            'task': ('optics', ),
            'need_weights': True,
        },
        'elnes': {
            'task': ('elnes', ),
            'need_weights': True,
        }
    }

    @classmethod
    def define(cls, spec):
        import aiida.orm as orm
        super(CastepCalculation, cls).define(spec)

        # Initialise interal params, saved as metadata.options
        for key, value in cls._DEFAULTS.items():
            port_name = 'metadata.options.' + key
            spec.input(port_name, default=value)

        spec.input('metadata.options.retrieve_list',
                   valid_type=list,
                   default=cls._default_retrieve_list)

        # Begin defining the input nodes
        spec.input(inp_ln['structure'],
                   valid_type=orm.StructureData,
                   help="Defines the input structure")
        spec.input(inp_ln['settings'],
                   valid_type=orm.Dict,
                   serializer=to_aiida_type,
                   required=False,
                   help="Use an additional node for sepcial settings")
        spec.input(inp_ln['parameters'],
                   valid_type=orm.Dict,
                   serializer=to_aiida_type,
                   validator=input_param_validator,
                   help="Use a node that sepcifies the input parameters")
        # TODO: implement logic to automaticall set the restart if such folder is given
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
        spec.input(inp_ln['kpoints'],
                   valid_type=KpointsData,
                   required=False,
                   help="Use a node defining the kpoints for the calculation")

        # Define additional kpoints for different tasks
        for key, value in cls._extra_kpoints.items():
            tasks = ', '.join(value['task'])
            spec.input(key + '_' + inp_ln['kpoints'],
                       valid_type=KpointsData,
                       required=False,
                       help="Extra kpoints input for task: {}".format(tasks))

        # Define the exit codes
        for smsg, (code, msg, inv) in ecodes.items():
            spec.exit_code(code, smsg, message=msg, invalidates_cache=inv)

        # Define the output nodes
        spec.output(out_ln['results'],
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

        if self._write_headers is True:
            cell_nodes = []
            for name, inp in self.inputs.items():
                if name in self._cell_links and inp:
                    cell_nodes.append([name, inp])

            # process pseudos
            for name, pseudo in self.inputs.pseudos.items():
                cell_nodes.append(['pseudo__{}'.format(name), pseudo])

            self.cell_file.header = self._generate_header_lines(cell_nodes)

            param_nodes = []
            for name, inp in self.inputs.items():
                if name in self._param_links and inp:
                    param_nodes.append([name, inp])

            self.param_file.header = self._generate_header_lines(param_nodes)

        local_copy_list.extend(self.local_copy_list_to_append)
        seedname = self.inputs.metadata.options.seedname

        cell_fn = seedname + ".cell"
        param_fn = seedname + ".param"

        with folder.open(cell_fn, mode='w') as incell:
            incell.write(six.text_type(self.cell_file.get_string()))

        with folder.open(param_fn, mode="w") as inparam:
            inparam.write(six.text_type(self.param_file.get_string()))

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

        calculation_mode = self.param_file.get("task", "singlepoint")

        # If we are doing geometryoptimisation retrieved the geom file and -out.cell file
        # dictionary for task specific file retrieve
        task_extra = self.retrieve_dict.get(calculation_mode.lower(), [])
        for suffix in task_extra:
            settings_retrieve_list.append(seedname + suffix)

        # Retrieve output cell  file if requested
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
            return submit_test(args[0])
        else:
            return submit_test(cls, **kwargs)

    @classmethod
    def check_restart(cls, builder, verbose=False):
        """Check the existence of restart file is needed"""
        check_restart(builder, verbose)

    @classmethod
    def dryrun_test(cls, inputs, castep_exe='castep.serial', verbose=True):
        """
        Do a dryrun test in a folder with prepared builder or inputs
        """

        from fnmatch import fnmatch
        from aiida.common.folders import Folder
        if isinstance(inputs, ProcessBuilder):
            res = cls.submit_test(inputs)
        else:
            res = cls.submit_test(cls, **inputs)
        folder = Folder(res[1])
        dry_run_node = res[0]
        seedname = dry_run_node.get_option('seedname')

        def _print(inp):
            if verbose:
                print(inp)

        # Do a dryrun
        from subprocess import call, check_output
        try:
            output = check_output([castep_exe, "-v"], universal_newlines=True)
        except OSError:
            _print("CASTEP executable '{}' is not found".format(castep_exe))
            return

        # Now start dryrun
        _print("Running with {}".format(
            check_output(["which", castep_exe], universal_newlines=True)))
        _print(output)

        _print("Starting dryrun...")
        call([castep_exe, "--dryrun", seedname], cwd=folder.abspath)

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
        out_file = seedname + '.castep'
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

    def _prepare_cell_file(self):
        """Add extra kpoints information to the calculation"""
        # First, call the base method
        super(CastepCalculation, self)._prepare_cell_file()
        param = self.inputs.get(inp_ln['parameters']).get_dict()
        task = param['PARAM'].get('task', 'singlepoint')

        # Check if we have more kpoints
        for kpn_name, kpn_settings in self._extra_kpoints.items():
            extra_kpns = self.inputs.get(kpn_name + '_' + inp_ln['kpoints'])
            # No need to proceed if it is not defined
            if extra_kpns is None:
                continue
            self._include_extra_kpoints(extra_kpns, kpn_name, kpn_settings)
            # Warn if this kpoint will not be used by the task
            if task not in kpn_settings['task']:
                self.report(
                    'Warning: kpoints for {} will not be used for task {}'.
                    format(kpn_name, task))

    @staticmethod
    def update_paraemters(inputs, *args, **kwargs):
        """Update the paramters for a given input dictionary/builder"""
        return update_parameters(inputs, *args, **kwargs)

    @staticmethod
    def use_pseudos_from_family(inputs, family_name):
        use_pseudos_from_family(inputs, family_name)

    def _generate_header_lines(self, other_nodes=None):
        """
        Generate header lines to go into param and cell files
        :param other_nodes: A list of pairs of (linkname, node)

        """
        from textwrap import TextWrapper
        import time
        from aiida.manage.manager import get_manager
        profile = get_manager().get_profile()
        if not profile:
            return

        wrapper = TextWrapper(initial_indent="# ", subsequent_indent="# ")
        time_str = time.strftime("%H:%M:%S %d/%m/%Y %Z")
        lines = [
            "##### Generated by aiida_castep {} #####".format(time_str),
            "#         author: Bonan Zhu (bz240@cam.ac.uk)",
            "# "
            "# AiiDA User: {}".format(
                User.objects.get_default().get_full_name()),
            "# AiiDA profile: {}".format(profile.name),
            "# Information of the calculation node",
            #"# type: {}".format(self.get_name()),
            #"# pk: {}".format(self.pk),
            #"# uuid: {}".format(self.uuid),
            "# label: {}".format(self.inputs.metadata.get('label')),
            "# description:",
        ]

        description = self.inputs.metadata.get('description')
        if description:
            lines.extend(wrapper.wrap(description))
        lines.append("")

        # additional information of the input nodes
        if other_nodes:
            lines.append("## Information of input nodes used:")

        for name, node in other_nodes:
            node_lines = [
                "# ", "# type: {}".format(node), "# pk: {}".format(node.pk),
                "# linkname: {}".format(name), "# uuid: {}".format(node.uuid),
                "# label: {}".format(node.label), "# description:"
            ]
            _desc = node.description
            if _desc:
                node_lines.extend(wrapper.wrap(_desc))
            node_lines.append("")
            lines.extend(node_lines)

        lines.append("# END OF HEADER")

        return lines


class TaskSpecificCalculation(CastepCalculation):
    """
    Class for Calculations that only allow certain tasks
    """

    _acceptable_tasks = []

    def prepare_for_submission(self, folder):

        in_dict = self.inputs[INPUT_LINKNAMES['parameters']].get_dict()

        # Check if task is correctly set
        all_tasks = [t.lower() for t in self._acceptable_tasks]
        if in_dict['PARAM']['task'].lower() not in all_tasks:
            raise InputValidationError("Wrong TASK value {}"
                                       " set in PARAM".format(
                                           in_dict['PARAM']['task'].lower()))
        return super(TaskSpecificCalculation,
                     self).prepare_for_submission(folder)


class CastepTSCalculation(TaskSpecificCalculation):
    """
    CASTEP calculation for transition state search. Use an extra input product structure.
    """
    _acceptable_tasks = ["transitionstatesearch"]

    @classmethod
    def define(cls, spec):
        import aiida.orm as orm
        super(CastepTSCalculation, cls).define(spec)
        spec.input(inp_ln['prod_structure'],
                   valid_type=orm.StructureData,
                   required=True,
                   help='Product structure for transition state search.')

    def _prepare_cell_file(self):
        """
        Extend the prepare_cell_filer method to include product
        structure
        """
        super(CastepTSCalculation, self)._prepare_cell_file()
        p_structure = self.inputs[inp_ln['prod_structure']]
        pdt_position_list = []
        for site in p_structure.sites:
            kind = p_structure.get_kind(site.kind_name)
            name = kind.symbol
            line = get_castep_ion_line(name, site.position)
            pdt_position_list.append(line)

        self.cell_file["POSITIONS_ABS_PRODUCT"] = pdt_position_list


def submit_test(arg, **kwargs):
    """This essentially test the submition"""
    from aiida.engine import run_get_node

    # Deal with passing an process builder
    if isinstance(arg, ProcessBuilder):
        inputs = arg

        inputs['metadata']['store_provenance'] = False
        inputs['metadata']['dry_run'] = True

        output_node = run_get_node(inputs).node
        inputs['metadata']['store_provenance'] = True
        inputs['metadata']['dry_run'] = False
    else:
        inputs = kwargs
        inputs['metadata']['store_provenance'] = False
        inputs['metadata']['dry_run'] = True
        output_node = run_get_node(arg, **inputs).node
        inputs['metadata']['store_provenance'] = True
        inputs['metadata']['dry_run'] = False

    return output_node, output_node.dry_run_info['folder']

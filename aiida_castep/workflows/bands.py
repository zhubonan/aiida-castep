"""
Workflow from computing the band structures
"""
from copy import deepcopy

import aiida.orm as orm
from aiida.common.extendeddicts import AttributeDict
from aiida.engine import WorkChain, calcfunction, if_
from aiida.plugins import WorkflowFactory
from aiida.tools import get_explicit_kpoints_path

from ..common import OUTPUT_LINKNAMES as out_ln
from ..utils.dos import DOSProcessor


class CastepBandsWorkChain(WorkChain):
    """
    Workchain for running bands calculation.

    This workchain does the following:

    1. Relax the structure if requested (eg. inputs passed to the relax namespace).
    2. Optionally: Do a SCF singlepoint calculation
    3. Do combined SCF + non-SCF calculation for bands and dos.

    Inputs must be passed for the SCF calculation (dispatched to bands and DOS),
    others are optional.

    Input for bands and dos calculations are optional. However, if they are needed, the full list of inputs must
    be passed. For the `parameters` node, one may choose to only specify those fields that need to be updated.
    """
    _base_wk_string = 'castep.base'
    _relax_wk_string = 'castep.relax'
    _task_name = 'spectral'

    @classmethod
    def define(cls, spec):
        """Initialise the WorkChain class"""
        super().define(spec)
        relax_work = WorkflowFactory(cls._relax_wk_string)
        base_work = WorkflowFactory(cls._base_wk_string)

        spec.input('structure',
                   help='The input structure',
                   valid_type=orm.StructureData)
        spec.input('bands_kpoints',
                   help='Explicit kpoints for the bands',
                   valid_type=orm.KpointsData,
                   required=False)
        spec.input('bands_kpoints_distance',
                   help='Spacing for band distances, used by seekpath',
                   valid_type=orm.Float,
                   required=False)
        spec.input(
            'dos_kpoints',
            help='Kpoints for running DOS calculations',
            required=False,
            valid_type=orm.KpointsData,
        )
        spec.expose_inputs(relax_work,
                           namespace='relax',
                           exclude=('structure', ),
                           namespace_options={
                               'required': False,
                               'populate_defaults': False,
                               'help':
                               'Inputs for Relaxation workchain, if needed'
                           })
        spec.expose_inputs(
            base_work,
            namespace='scf',
            exclude=('calc.structure', ),
            namespace_options={
                'required':
                True,
                'populate_defaults':
                True,
                'help':
                'Inputs for SCF workchain, mandatory. Used as template for bands/dos if not supplied separately'
            })
        spec.expose_inputs(base_work,
                           namespace='bands',
                           exclude=('calc.structure', 'calc.kpoints'),
                           namespace_options={
                               'required': False,
                               'populate_defaults': False,
                               'help':
                               'Inputs for bands calculation, if needed'
                           })
        spec.expose_inputs(base_work,
                           namespace='dos',
                           exclude=('calc.structure', ),
                           namespace_options={
                               'required': False,
                               'populate_defaults': False,
                               'help': 'Inputs for DOS calculation, if needed'
                           })
        spec.input('clean_children_workdir',
                   valid_type=orm.Str,
                   help='What part of the called children to clean',
                   required=False,
                   default=lambda: orm.Str('none'))
        spec.input('only_dos',
                   required=False,
                   help='Flag for running only DOS calculations')
        spec.input(
            'run_separate_scf',
            required=False,
            help='Flag for running a separate SCF calculation, default to False'
        )
        spec.input(
            'options',
            required=False,
            help=
            'Options for this workchain. Supported keywords: dos_smearing, dos_npoints.'
        )
        spec.outline(
            cls.setup,
            if_(cls.should_do_relax)(
                cls.run_relax,
                cls.verify_relax,
            ),
            if_(cls.should_run_seekpath)(cls.run_seekpath),
            if_(cls.should_run_scf)(
                cls.run_scf,
                cls.verify_scf,
            ),
            cls.run_bands_dos,
            cls.inspect_bands_dos,
        )

        spec.output(
            'primitive_structure',
            help='Primitive structure used for band structure calculations',
            required=False,
        )
        spec.output('band_structure',
                    help='Computed band structure with labels')
        spec.output('seekpath_parameters',
                    help='Parameters used by seekpath',
                    required=False)
        spec.output('dos_bands',
                    required=False,
                    help='Bands from the DOS calculation')

        spec.exit_code(501,
                       'ERROR_SUB_PROC_RELAX_FAILED',
                       message='Relaxation workchain failed')
        spec.exit_code(502,
                       'ERROR_SUB_PROC_SCF_FAILED',
                       message='SCF workchain failed')
        spec.exit_code(503,
                       'ERROR_SUB_PROC_BANDS_FAILED',
                       message='Band structure workchain failed')
        spec.exit_code(504,
                       'ERROR_SUB_PROC_DOS_FAILED',
                       message='DOS workchain failed')

    def setup(self):
        """Setup the calculation"""
        self.ctx.current_structure = self.inputs.structure
        self.ctx.bands_kpoints = self.inputs.get('bands_kpoints')
        self.ctx.options = self.inputs.get('options', {})

    def should_do_relax(self):
        """Wether we should do relax or not"""
        return 'relax' in self.inputs

    def run_relax(self):
        """Run the relaxation"""
        relax_work = WorkflowFactory(self._relax_wk_string)
        inputs = self.exposed_inputs(relax_work, 'relax', agglomerate=True)
        inputs = AttributeDict(inputs)
        inputs.metadata.call_link_label = 'relax'
        inputs.structure = self.ctx.current_structure

        running = self.submit(relax_work, **inputs)
        return self.to_context(workchain_relax=running)

    def verify_relax(self):
        """Verify the relaxation"""
        relax_workchain = self.ctx.workchain_relax
        if not relax_workchain.is_finished_ok:
            self.report('Relaxation finished with Error')
            return self.exit_codes.ERROR_SUB_PROC_RELAX_FAILED

        # Use the relaxed structure as the current structure
        self.ctx.current_structure = relax_workchain.outputs[
            out_ln['structure']]
        return None

    def should_run_scf(self):
        """Wether we should run SCF calculation?"""
        run_separate_scf = self.inputs.get('run_separate_scf', orm.Bool(False))
        return run_separate_scf.value

    def should_run_seekpath(self):
        """Seekpath should only run if no explicit bands is provided"""
        return 'bands_kpoints' not in self.inputs

    def run_seekpath(self):
        """
        Run seekpath to obtain the primitive structure and bands
        NOTE: Need to handle the magnetic symmetry properly
        """

        inputs = {
            'reference_distance': self.inputs.get('bands_kpoints_distance',
                                                  None),
            'metadata': {
                'call_link_label': 'seekpath'
            }
        }

        results = seekpath_structure_analysis(self.ctx.current_structure,
                                              **inputs)
        self.ctx.current_structure = results['primitive_structure']
        self.ctx.bands_kpoints = results['explicit_kpoints']
        self.out('primitive_structure', results['primitive_structure'])
        self.out('seekpath_parameters', results['parameters'])

    def run_scf(self):
        """
        Run the SCF calculation
        """

        base_work = WorkflowFactory(self._base_wk_string)
        inputs = AttributeDict(self.exposed_inputs(base_work, namespace='scf'))
        inputs.metadata.call_link_label = 'scf'
        inputs.calc.structure = self.ctx.current_structure

        # Ensure that writing the check/castep_bin
        param_dict = inputs.calc.parameters.get_dict()
        if 'PARAM' in param_dict:
            ensure_checkpoint(param_dict['PARAM'])
        else:
            ensure_checkpoint(param_dict)

        # Update if changes are made
        if param_dict != inputs.calc.parameters.get_dict():
            self.report(
                "Updated the PARAM to make sure castep_bin file will be written"
            )
            inputs.calc.parameters = orm.Dict(dict=param_dict)

        running = self.submit(base_work, **inputs)
        self.report('Running SCF calculation {}'.format(running))
        self.to_context(workchain_scf=running)

    def verify_scf(self):
        """Inspect the SCF calculation"""
        scf_workchain = self.ctx.workchain_scf
        if not scf_workchain.is_finished_ok:
            self.report('SCF workchain finished with Error')
            return self.exit_codes.ERROR_SUB_PROC_SCF_FAILED

        # NOTE: the plugin does not support restarting from local files for now,
        # This should be added later - restart from a `retrieved` local folder
        self.ctx.restart_folder = scf_workchain.outputs.remote_folder
        self.report("SCF calculation {} completed".format(scf_workchain))
        return None

    def run_bands_dos(self):
        """Run the bands and the DOS calculations"""
        base_work = WorkflowFactory(self._base_wk_string)
        # Use the SCF inputs as the base
        inputs = AttributeDict(self.exposed_inputs(base_work, namespace='scf'))
        inputs.calc.structure = self.ctx.current_structure
        only_dos = self.inputs.get('only_dos')

        # Setup the restart folders and relavant tags
        if 'continuation_folder' in self.inputs.scf and not self.should_run_scf(
        ):
            self.ctx.restart_folder = self.inputs.scf.continuation_folder

        def generate_sub_input(inputs, namespace, task):
            """
            Generate inputs for tasks, merge those in the namespace from those
            given in the inputs
            """
            if namespace in self.inputs:
                self.report(
                    'Taking input from the {} namespace'.format(namespace))
                bands_inputs = AttributeDict(
                    self.exposed_inputs(base_work, namespace=namespace))
            else:
                bands_inputs = AttributeDict(
                    {'calc': {
                        'parameters': orm.Dict(dict={'task': task})
                    }})

            # Special treatment - combine the paramaters
            parameters = inputs.calc.parameters.get_dict()
            bands_parameters = bands_inputs.calc.parameters.get_dict()

            nested_update(parameters, bands_parameters)
            # Make sure the task name is correct
            nested_update(parameters, {'task': self._task_name})

            # Update the SCF name space with those from the bands name space
            nested_update(inputs, bands_inputs)

            # Apply the new parameters
            inputs.calc.parameters = orm.Dict(dict=parameters)

            return inputs

        running = {}
        if (only_dos is None) or (only_dos.value is False):

            # Fall back to use SCF inputs if not supplied
            if 'bands' in self.inputs:
                inputs = generate_sub_input(inputs, 'bands', 'spectral')
            else:
                inputs = generate_sub_input(inputs, 'scf', 'spectral')
            # Set the kpoints
            inputs.calc[self._task_name + '_kpoints'] = self.ctx.bands_kpoints

            if 'restart_folder' in self.ctx:
                self.setup_restart_folder(inputs)

            bands_calc = self.submit(base_work, **inputs)
            running['bands_workchain'] = bands_calc
            self.report(
                'Submitted workchain {} for band structure'.format(bands_calc))

        if ('dos_kpoints' in self.inputs) or ('dos' in self.inputs):

            # Fall back to use SCF inputs if not supplied
            if 'dos' in self.inputs:
                inputs = generate_sub_input(inputs, 'dos', 'spectral')
            else:
                inputs = generate_sub_input(inputs, 'scf', 'spectral')

            # Set the kpoints
            inputs.calc[self._task_name + '_kpoints'] = self.inputs.dos_kpoints
            if 'restart_folder' in self.ctx:
                self.setup_restart_folder(inputs)

            dos_calc = self.submit(base_work, **inputs)
            running['dos_workchain'] = dos_calc
            self.report(
                'Submitted workchain {} for dos calculation'.format(dos_calc))
        return self.to_context(**running)

    def setup_restart_folder(self, inputs):
        """Setup restart folder related tags for the inputs"""

        # If a SCF calculation has been run then we use the output folder to perform restart
        # This logic should be moved to CastepBaseWorkChain?
        write_checkpoint = self.ctx.restart_folder.creator.inputs.parameters[
            'PARAM'].get('write_checkpoint', 'all')
        allow_restart = False
        use_bin = False
        if write_checkpoint.lower() != 'none':
            allow_restart = True
            # Ensure we use the CASTEP bin file
            if write_checkpoint == 'minimal':
                # Update to use the castep_bin file
                use_bin = True

            elif '=' in write_checkpoint:
                # Cannot decide - visit the remote folder and check
                contents = self.ctx.restart_folder.listdir()
                seed = self.ctx.restart_folder.creator.get_options(
                )['seedname']
                if f'{seed}.check' not in contents:
                    if f'{seed}.castep_bin' in contents:
                        use_bin = True
                    else:
                        allow_restart = False
        else:
            allow_restart = False

        if allow_restart:
            inputs.continuation_folder = self.ctx.restart_folder
            if use_bin is True:
                options = inputs.options.get_dict(
                ) if 'options' in inputs else {}
                options['use_castep_bin'] = True
                inputs.options = orm.Dict(dict=options)

    def inspect_bands_dos(self):
        """Inspect the bands and dos calculations"""

        exit_code = None

        if 'bands_workchain' in self.ctx:
            bands = self.ctx.bands_workchain
            if not bands.is_finished_ok:
                self.report(
                    'Bands calculation {} finished with error, exit_status: {}'
                    .format(bands, bands.exit_status))
                exit_code = self.exit_codes.ERROR_SUB_PROC_BANDS_FAILED
            self.out(
                'band_structure',
                compose_labelled_bands(bands.outputs[out_ln['bands']],
                                       self.ctx.bands_kpoints))
        else:
            bands = None

        if 'dos_workchain' in self.ctx:
            dos = self.ctx.dos_workchain
            if not dos.is_finished_ok:
                self.report(
                    'DOS calculation finished with error, exit_status: {}'.
                    format(dos.exit_status))
                exit_code = self.exit_codes.ERROR_SUB_PROC_DOS_FAILED
            self.out('dos_bands', dos.outputs[out_ln['bands']])
            # Compute DOS from bands
            self.out(
                'dos',
                dos_from_bands(dos.outputs[out_ln['bands']],
                               smearing=orm.Float(
                                   self.ctx.options.get('dos_smearing', 0.05)),
                               npoints=orm.Int(
                                   self.ctx.options.get('dos_npoints', 2000))))
        else:
            dos = None

        return exit_code

    def on_terminated(self):
        """
        Clean the remote directories of all called childrens
        """

        super(CastepBandsWorkChain, self).on_terminated()

        if self.inputs.clean_children_workdir.value != 'none':
            cleaned_calcs = []
            for called_descendant in self.node.called_descendants:
                if isinstance(called_descendant, orm.CalcJobNode):
                    try:
                        called_descendant.outputs.remote_folder._clean()  # pylint: disable=protected-access
                        cleaned_calcs.append(called_descendant.pk)
                    except (IOError, OSError, KeyError):
                        pass

            if cleaned_calcs:
                self.report(
                    'cleaned remote folders of calculations: {}'.format(
                        ' '.join(map(str, cleaned_calcs))))


def nested_update(dict_in, update_dict):
    """Update the dictionary - combine nested subdictionary with update as well"""
    for key, value in update_dict.items():
        if key in dict_in and isinstance(value, (dict, AttributeDict)):
            nested_update(dict_in[key], value)
        else:
            dict_in[key] = value
    return dict_in


def nested_update_dict_node(dict_node, update_dict):
    """Utility to update a Dict node in a nested way"""
    pydict = dict_node.get_dict()
    nested_update(pydict, update_dict)
    if pydict == dict_node.get_dict():
        return dict_node
    return orm.Dict(dict=pydict)


@calcfunction
def seekpath_structure_analysis(structure, **kwargs):
    """
    Primitivize the structure with SeeKpath and generate the high symmetry k-point path through its Brillouin zone.
    This calcfunction will take a structure and pass it through SeeKpath to get the normalized primitive cell and the
    path of high symmetry k-points through its Brillouin zone. Note that the returned primitive cell may differ from the
    original structure in which case the k-points are only congruent with the primitive cell.
    The keyword arguments can be used to specify various Seekpath parameters, such as:

        with_time_reversal: True
        reference_distance: 0.025
        recipe: 'hpkot'
        threshold: 1e-07
        symprec: 1e-05
        angle_tolerance: -1.0

    Note that exact parameters that are available and their defaults will depend on your Seekpath version.
    """

    unwrapped_kwargs = {
        key: node.value
        for key, node in kwargs.items() if isinstance(node, orm.Data)
    }

    # All keyword arugments should be `Data` node instances of base type and so should have the `.value` attribute
    return get_explicit_kpoints_path(structure, **unwrapped_kwargs)


@calcfunction
def compose_labelled_bands(bands, kpoints):
    """
    Add additional information from the kpoints allow richer informations
    to be stored such as band structure labels.
    """
    new_bands = deepcopy(bands)
    new_bands.set_kpointsdata(kpoints)
    return new_bands


def ensure_checkpoint(pdict):
    """Ensure that check/castep_bin file will be wirtten"""
    value = pdict.get('write_checkpoint')
    if value is None:
        return pdict
    if value.lower() == 'none':
        pdict['write_checkpoint'] = 'minimal'
    return pdict


@calcfunction
def dos_from_bands(bands, smearing, npoints):
    """
    Compute DOS from bands

    :param bands: The `BandsData` to be used as input.
    :param smearing: Smearing width in eV
    :param npoints: Number of points
    """
    bands_data = bands.get_bands(also_occupations=False, also_labels=False)
    _, weights = bands.get_kpoints(also_weights=True)

    processor = DOSProcessor(bands_data, weights, smearing.value)

    # Ensure there are three dimensions
    eng, dos = processor.get_dos(npoints=npoints.value, dropdim=False)

    # Output as XyData
    out = orm.XyData()
    out.set_x(eng, "Energy", "eV")
    nspin = dos.shape[0]
    out.set_y(y_arrays=list(dos),
              y_names=["DOS_SPIN_{}".format(i) for i in range(nspin)],
              y_units=["eV^-1"] * nspin)

    out.set_attribute("fermi_energy", bands.get_attribute('efermi'))
    return out

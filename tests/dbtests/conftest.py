"""
conftest that prepares fixtures with tests involving orm of aiida
"""
from io import BytesIO
import tempfile
import shutil
from pathlib import Path

import pytest

from aiida.orm import Computer, Dict, Code, KpointsData, Node, StructureData
from aiida.plugins import DataFactory, ParserFactory
from aiida.common.exceptions import NotExistent
from aiida.common import AttributeDict
from aiida import __version__ as AIIDA_VERSION

from aiida.common.links import LinkType
from aiida.orm import CalcJobNode, FolderData
from aiida.plugins import CalculationFactory
from aiida.plugins.entry_point import format_entry_point_string

from aiida.manage.tests.pytest_fixtures import aiida_profile, clear_database_before_test

from aiida_castep.data.otfg import OTFGData
from aiida_castep.calculations.castep import CastepCalculation
from ..utils import get_sto_structure

this_folder = Path(__file__).parent

AIIDA_MAJOR_VERSION = int(AIIDA_VERSION[0])


class CastepTestApp(object):
    """
    A collection of methods to
    control the test
    """
    def __init__(self, profile, workdir):
        self._profile = profile
        self._workdir = Path(workdir)

    def create_computer(self, **kwargs):
        """
        Return a generator for the Computers
        """
        defaults = dict(label='localhost',
                        hostname='localhost',
                        transport_type='core.local'
                        if AIIDA_MAJOR_VERSION > 1 else 'local',
                        scheduler_type='core.direct'
                        if AIIDA_MAJOR_VERSION > 1 else 'direct',
                        workdir=str(self._workdir))

        kwargs.update(defaults)
        computer = Computer(**kwargs).store()
        # Need to configure the computer before using
        # Otherwise there is no AuthInfo
        computer.configure()
        return computer

    def get_or_create_computer(self, **kwargs):
        """
        Fixture for a local computer called localhost.
        This is currently not in the AiiDA fixtures."""
        try:
            computer = Computer.objects.get(**kwargs)
        except NotExistent:
            computer = self.create_computer(**kwargs)
        return computer

    @property
    def localhost(self):
        """Return an localhost computer"""
        return self.get_or_create_computer(label='localhost')

    def code_mock_factory(self, overide=None):
        """Mock calculation, can overide by prepend path"""
        code = Code()
        exec_path = this_folder.parent.parent / 'utils/mock.py'
        code.set_remote_computer_exec((self.localhost, str(exec_path)))
        code.set_input_plugin_name('castep.castep')
        if overide:
            code.set_prepend_text('export MOCK_CALC={}'.format(overide))
        return code

    @property
    def code_h2_geom(self):
        """A Code that always return H2-geom"""
        code = self.code_mock_factory('H2-geom')
        code.store()
        return code

    @property
    def code_echo(self):
        """Fixture of a code that just echos"""
        code = Code()
        code.set_remote_computer_exec((self.localhost, "/bin/echo"))
        code.set_input_plugin_name("castep.castep")
        code.store()
        return code

    @property
    def remotedata(self):
        """Create an remote data"""
        from aiida.orm import RemoteData
        rmd = RemoteData()
        rmd.computer = self.localhost
        rmd.set_remote_path(str(self._workdir))
        return rmd

    def get_kpoints_mesh(self, mesh):
        """Factory for kpoints with mesh"""
        kpoints_data = KpointsData()
        kpoints_data.set_kpoints_mesh(mesh)
        return kpoints_data

    def upload_otfg_family(self, entries, name, desc='test', **kwargs):
        """Return a factory for upload OTFGS"""
        from aiida_castep.data.otfg import upload_otfg_family
        upload_otfg_family(entries, name, desc, **kwargs)

    @property
    def c9_otfg(self):
        return OTFGData.get_or_create('C9')[0]

    @property
    def create_group(self):
        from aiida_castep.data.otfg import upload_otfg_family
        upload_otfg_family

    def get_builder(self):
        from aiida_castep.calculations.castep import CastepCalculation
        return CastepCalculation.get_builder()


@pytest.fixture
def create_otfg_group(db_test_app):
    def _create(otfgs, group_name):
        from aiida_castep.data.otfg import upload_otfg_family
        upload_otfg_family(otfgs, group_name, 'TEST', stop_if_existing=False)

    return _create


@pytest.fixture
def db_test_app(aiida_profile):
    """
    Yield an test app for controlling
    """

    workdir = tempfile.mkdtemp()
    app = CastepTestApp(aiida_profile, workdir)
    yield app
    aiida_profile.reset_db()
    shutil.rmtree(workdir)


@pytest.fixture
def inputs_default():
    options = {
        'seedname': 'aiida',
        'input_filename': 'aiida.cell',
        'output_filename': 'aiida.castep',
        'symlink_usage': True,
        'parent_folder_name': 'parent',
        'retrieve_list': [],
        'use_kpoints': True,
        'resources': {
            'num_machines': 1,
            'tot_num_mpiprocs': 1
        }
    }
    inputs = AttributeDict()
    inputs['metadata'] = AttributeDict()
    inputs.metadata['options'] = AttributeDict(options)
    return inputs


@pytest.fixture
def sto_calc_inputs(
        db_test_app,
        inputs_default,
):

    sto_structure = get_sto_structure()
    inputs = inputs_default

    pdict = {
        "PARAM": {
            "task": "singlepoint"
        },
        "CELL": {
            "symmetry_generate": True,
            "cell_constraints": ['0 0 0', '0 0 0']
        }
    }
    # pdict["CELL"].pop("block species_pot")
    inputs.parameters = Dict(dict=pdict)
    inputs.structure = sto_structure
    c9 = db_test_app.c9_otfg
    inputs.pseudos = AttributeDict({"Sr": c9, 'Ti': c9, 'O': c9})
    inputs.kpoints = db_test_app.get_kpoints_mesh((3, 3, 3))
    inputs.code = db_test_app.code_echo
    return inputs


@pytest.fixture
def sto_spectral_inputs(sto_calc_inputs, db_test_app):
    kpoints = KpointsData()
    kpoints.set_kpoints([[0.0, 0.5, 0.5], [0.0, 0.0, 0.0]])
    sto_calc_inputs.spectral_kpoints = kpoints
    return sto_calc_inputs


@pytest.fixture
def sto_calc_builder(sto_calc_inputs):
    return inps_or_builder(sto_calc_inputs, 1)


@pytest.fixture(params=[0, 1])
def sto_calc_inps_or_builder(request, sto_calc_inputs):
    """Fixture that returns raw input dictionary or builder"""
    return inps_or_builder(sto_calc_inputs, request.param)


def inps_or_builder(inps, num):
    """Helper function to convert inputs to builder or do nothing"""
    if num == 0:
        return inps
    elif num == 1:
        builder = CastepCalculation.get_builder()
        builder._update(inps)
        return builder
    else:
        raise RuntimeError('Not implemented')


@pytest.fixture
def h2_calc_inputs(
        inputs_default,
        db_test_app,
        sto_calc_inputs,
        h2_structure,
):

    inputs = inputs_default
    pdict = {
        "PARAM": {
            "task": "geometryoptimisation"
        },
        "CELL": {
            "symmetry_generate": True,
            "cell_constraints": ['0 0 0', '0 0 0']
        }
    }
    # pdict["CELL"].pop("block species_pot")
    inputs.parameters = Dict(dict=pdict)
    inputs.structure = h2_structure
    inputs.pseudos = AttributeDict({"H": db_test_app.c9_otfg})
    inputs.kpoints = db_test_app.get_kpoints_mesh((3, 3, 3))
    inputs.code = db_test_app.code_h2_geom

    return inputs


@pytest.fixture
def h2_structure(aiida_profile, db_test_app):
    a = 10

    cell = ((a, 0., 0.), (0., a, 0.), (0., 0., a))
    s = StructureData(cell=cell)
    s.append_atom(position=(0., 0., 0.), symbols=["H"])
    s.append_atom(position=(a / 2, a / 2, a / 2), symbols=["H"])
    s.label = "h2"
    return s


def test_localhost_fixture(db_test_app):
    """
    Test the localhost fixture
    """
    localhost = db_test_app.localhost
    localhost.name == "localhost"
    assert localhost.pk is not None


def test_code_fixture(db_test_app):
    """
    Test the localhost fixture
    """
    code_echo = db_test_app.code_echo
    assert code_echo.uuid is not None
    code_echo.get_remote_exec_path()


def test_remotedata_fixture(db_test_app):
    assert db_test_app.remotedata
    assert db_test_app.remotedata.get_remote_path() == str(
        db_test_app._workdir)


@pytest.fixture
def generate_calc_job_node(db_test_app):
    """
    Generate CalcJobNode
    """
    def _generate_calc_job_node(
            entry_point_name,
            results_folder,
            inputs=None,
            computer=None,
            outputs=None,
            outfile_override=None,
    ):
        """
        Generate a CalcJob node with fake retrieved node in the
        tests/data
        """

        calc_class = CalculationFactory(entry_point_name)
        entry_point = format_entry_point_string('aiida.calculations',
                                                entry_point_name)
        builder = calc_class.get_builder()

        if not computer:
            computer = db_test_app.localhost
        node = CalcJobNode(computer=computer, process_type=entry_point)

        # Monkypatch the inputs
        if inputs is not None:
            inputs = AttributeDict(inputs)
            node.__dict__['inputs'] = inputs
            # Add direct inputs, pseudos are omitted
            for k, v in inputs.items():
                if isinstance(v, Node):
                    if not v.is_stored:
                        v.store()
                    node.add_incoming(v,
                                      link_type=LinkType.INPUT_CALC,
                                      link_label=k)

        options = builder.metadata.options
        options.update(inputs.metadata.options)
        node.set_attribute('input_filename', options.input_filename)
        node.set_attribute('seedname', options.seedname)
        node.set_attribute('output_filename', options.output_filename)
        node.set_attribute('error_filename', 'aiida.err')
        node.set_option('resources', {
            'num_machines': 1,
            'num_mpiprocs_per_machine': 1
        })
        node.set_option('max_wallclock_seconds', 1800)
        node.store()

        filepath = this_folder.parent / 'data' / results_folder
        retrieved = FolderData()
        retrieved.put_object_from_tree(str(filepath.resolve()))

        # Apply overriding output files
        if outfile_override is not None:
            for key, content in outfile_override.items():
                if content is None:
                    retrieved.delete_object(key)
                    continue
                buf = BytesIO(content.encode())
                retrieved.put_object_from_filelike(buf, key)

        retrieved.add_incoming(node,
                               link_type=LinkType.CREATE,
                               link_label='retrieved')
        retrieved.store()

        if outputs is not None:
            for label, out_node in outputs.items():
                out_node.add_incoming(node,
                                      link_type=LinkType.CREATE,
                                      link_label=label)
                if not out_node.is_stored:
                    out_node.store()

        return node

    return _generate_calc_job_node


@pytest.fixture
def generate_parser():
    def _generate_parser(entry_point_name):
        return ParserFactory(entry_point_name)

    return _generate_parser

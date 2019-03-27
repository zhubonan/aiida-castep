"""
conftest that prepares fixtures with tests involving orm of aiida
"""
from __future__ import absolute_import
import tempfile
import shutil
import pytest
import os
from aiida.common.exceptions import NotExistent
from aiida.common import AttributeDict
from aiida.manage.fixtures import fixture_manager


def get_backend_str():
    """ Return database backend string.

    Reads from 'TEST_AIIDA_BACKEND' environment variable.
    Defaults to django backend.
    """
    from aiida.backends.profile import BACKEND_DJANGO, BACKEND_SQLA
    backend_env = os.environ.get('TEST_AIIDA_BACKEND')
    if not backend_env:
        return BACKEND_DJANGO
    elif  backend_env in (BACKEND_DJANGO, BACKEND_SQLA):
        return backend_env

    raise ValueError("Unknown backend '{}' read from TEST_AIIDA_BACKEND environment variable".format(backend_env))


@pytest.fixture(scope='session')
def aiida_profile():
    """setup a test profile for the duration of the tests
    If the environmental variable AIIDA_TEST_PROFILE is present
    will use an alternative fixture_manager that uses the test profile"""
    # import os
    # test_profile = os.environ.get('AIIDA_TEST_PROFILE', None)
    # if test_profile is not None:
    #     from fixture import fixture_manager
    # else:
    #     from aiida.manage.fixtures import fixture_manager
    from .fixture import fixture_manager
    with fixture_manager() as fixture_mgr:
        yield fixture_mgr


@pytest.fixture(scope='function')
def new_database(aiida_profile):
    """clear the database after each test"""
    yield aiida_profile
    aiida_profile.reset_db()


@pytest.fixture(scope="module")
def otfgdata():
    from aiida.plugins import DataFactory
    return DataFactory("castep.otfgdata")


@pytest.fixture(scope="module")
def otfg():
    import aiida_castep.data.otfg as otfg
    return otfg


@pytest.fixture(scope="module")
def imps(aiida_profile):

    class Imports:

        def __init__(self):
            from aiida.orm import Dict
            from aiida.plugins import CalculationFactory
            from aiida.plugins import DataFactory
            import aiida_castep.data.otfg as otfg
            for k, v in locals().items():
                setattr(self, k, v)

    return Imports()


@pytest.fixture
def localhost(aiida_profile, tmpdir):
    """
    Fixture for a local computer called localhost.
    This is currently not in the AiiDA fixtures."""
    from aiida.orm import Computer
    try:
        computer = Computer.objects.get(name='localhost')
    except NotExistent:
        computer = Computer(name='localhost', hostname='localhost',
                            transport_type='local',
                            scheduler_type='direct',
                            workdir=tmpdir.strpath).store()
    return computer


@pytest.fixture()
def code_echo(localhost):
    """Fixture of a code that just echos"""
    from aiida.orm import Code
    code = Code()
    code.set_remote_computer_exec(
        (localhost, "/bin/echo"))
    code.set_input_plugin_name("castep.castep")
    code.store()
    return code


@pytest.fixture()
def remotedata(localhost, tmpdir):
    """Create an remote data"""
    from aiida.orm import RemoteData

    rmd = RemoteData()
    rmd.set_computer(localhost)
    rmd.set_remote_path(str(tmpdir))
    return rmd


@pytest.fixture
def kpoints_data(aiida_profile):
    """
    Return a factory for kpoints
    """
    from aiida.plugins import DataFactory
    return DataFactory("array.kpoints")()


@pytest.fixture
def kpoints_mesh(kpoints_data):
    """Factory for kpoints with mesh"""
    def _kpoints_mesh(mesh, *args, **kwargs):
        kpoints_data.set_kpoints_mesh(mesh)
        return kpoints_data
    return _kpoints_mesh


@pytest.fixture
def kpoints_list(kpoints_data):
    """Factory for kpoints with mesh"""
    def _kpoints_list(klist, *args, **kwargs):
        kpoints_data.set_kpoints(klist, *args, **kwargs)
        return kpoints_data
    return _kpoints_list


@pytest.fixture
def OTFG_family_factory(aiida_profile):
    """Return a factory for upload OTFGS"""
    from aiida_castep.data.otfg import upload_otfg_family

    def _factory(otfg_entries, name, desc="TEST", **kwargs):
        upload_otfg_family(otfg_entries, name, desc, **kwargs)
        return

    return _factory

@pytest.fixture
def builder(aiida_profile):
    from aiida_castep.calculations.castep import CastepCalculation
    return CastepCalculation.get_builder()

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
        'resources': {'num_machines': 1, 'tot_num_mpiprocs': 1}
    }
    inputs = AttributeDict()
    inputs['metadata'] = AttributeDict()
    inputs.metadata['options'] = AttributeDict(options)
    return inputs

@pytest.fixture
def STO_calc_inputs(aiida_profile,
                    STO_structure,
                    inputs_default,
                    OTFG_family_factory,
                    code_echo, imps,
                    c9,
                    localhost, kpoints_mesh):
    from aiida.engine.processes.ports import PortNamespace
    from aiida.engine.processes.builder import ProcessBuilderNamespace
    from collections import MutableMapping

    inputs = inputs_default
    pdict = {"PARAM": {
        "task": "singlepoint"
    },
             "CELL": {
                 "symmetry_generate": True,
                 "cell_constraints": ['0 0 0', '0 0 0']
             }}
    # pdict["CELL"].pop("block species_pot")
    inputs.parameters = imps.Dict(dict=pdict)
    inputs.structure = STO_structure
    inputs.pseudos = AttributeDict({"Sr": c9, 'Ti': c9, 'O': c9})
    inputs.kpoints = kpoints_mesh((3, 3, 3))
    inputs.code = code_echo

    return inputs


@pytest.fixture
def c9(aiida_profile):
    """C9 OTFG"""
    from aiida_castep.data.otfg import OTFGData
    c9 = OTFGData.get_or_create('C9')
    return c9[0]


@pytest.fixture
def STO_structure(aiida_profile, imps):
    """Return a STO structure"""
    StructureData = imps.DataFactory("structure")
    a = 3.905

    cell = ((a, 0., 0.), (0., a, 0.), (0., 0., a))
    s = StructureData(cell=cell)
    s.append_atom(position=(0., 0., 0.), symbols=["Sr"])
    s.append_atom(position=(a / 2, a / 2, a / 2), symbols=["Ti"])
    s.append_atom(position=(a / 2, a / 2, 0.), symbols=["O"])
    s.append_atom(position=(a / 2, 0., a / 2), symbols=["O"])
    s.append_atom(position=(0., a / 2, a / 2), symbols=["O"])
    s.label = "STO"
    return s


def test_localhost_fixture(localhost):
    """
    Test the localhost fixture
    """
    localhost.name == "localhost"
    assert localhost.pk is not None


def test_code_fixture(code_echo):
    """
    Test the localhost fixture
    """
    assert code_echo.pk is not None
    code_echo.get_remote_exec_path()


def test_remotedata_fixture(remotedata):
    assert remotedata.get_remote_path()
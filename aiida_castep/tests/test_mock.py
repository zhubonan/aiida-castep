"""
Tests for the mock module
"""

from aiida_castep.utils.mock import get_hash, MockOutput
from pathlib2 import Path
import tempfile
import shutil
import pytest

known_hash = {"H2-geom": 'b9277dfbfe7b799f06b33cefb98ddf88'}


def test_hash():
    """Test hashing"""
    exmp = {'a': 'b', 'b': 'a'}
    get_hash(exmp)

    exmp = {'a': 'b', 'b': ['a', 'c']}
    h1, b1 = get_hash(exmp)

    exmp = {'b': ['a', 'c'], 'a': 'b'}
    h2, b2 = get_hash(exmp)
    assert b1 == b2
    assert h1 == h2


@pytest.fixture
def mock():
    """
    Return an Mockoutput Object wtih tempdir as the base
    """
    tmpdir = tempfile.mkdtemp()
    mockoutput = MockOutput(tmpdir)
    yield mockoutput
    shutil.rmtree(tmpdir)


@pytest.fixture(scope='module')
def data_folder():
    from aiida_castep import tests
    data_folder = Path(tests.__file__).parent / 'data'
    return data_folder


@pytest.fixture(scope='module')
def tmp_folder():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)


def test_hash_seed_compute(mock, data_folder):
    """
    Test computing hash with a given seed
    """
    res = mock.calculate_hash(data_folder / 'H2-geom/aiida')
    assert res == known_hash['H2-geom']


def test_reg_file(mock):
    """
    Empty registry in the begining
    """
    assert mock.registry == {}


def test_regsitration(mock, data_folder):

    mock.register(data_folder / 'H2-geom/aiida', tag='H2-geom')
    # Check if the hash has been recorded
    assert known_hash['H2-geom'] in mock.registry
    # Check if the data is copied to the base_dir
    assert (mock.base_dir / 'H2-geom').is_dir()


def test_run(mock, data_folder, tmp_folder):
    """Full copying results correctly"""
    import os
    mock.register(data_folder / 'H2-geom/aiida', tag='H2-geom')
    # Copy inputs to a temp folder
    run_folder = tmp_folder
    shutil.copy(str(data_folder / 'H2-geom/aiida.param'), run_folder)
    shutil.copy(str(data_folder / 'H2-geom/aiida.cell'), run_folder)
    seedpath = os.path.join(run_folder, 'aiida')
    mock.run(seedpath, dest=run_folder)

    # Check if the results field is copied
    assert (Path(run_folder) / 'aiida.castep').is_file()

    # Check if the hash is the same
    h1 = mock.calculate_hash(seedpath)
    assert h1 == known_hash['H2-geom']

"""
Tests for mock CASTEP
"""
# pylint: disable=unused-import,redefined-outer-name,unused-argument,unused-wildcard-import
# pylint: disable=wildcard-import,no-member, import-outside-toplevel, too-many-arguments
from os import getcwd
from pathlib import Path
from tempfile import mkdtemp
from shutil import rmtree, copy2

import pytest

from aiida_castep.utils.mock_code import MockRegistry, MockCastep, get_hash


def test_get_hash():
    """
    Test the get_hash function
    """
    dict1 = {'1': 2, 3: 4, 'a': [1, '2', '3']}
    hash1 = get_hash(dict1)[0]
    dict2 = {'1': 38, 3: 4, 'a': [1, '2', '3']}
    hash2 = get_hash(dict2)[0]
    dict3 = {3: 4, '1': 2, 'a': [1, '2', '3']}
    hash3 = get_hash(dict3)[0]

    assert hash1 != hash2
    assert hash1 == hash3


def test_get_hash_list():
    """Test generating has for nested dict/list"""
    dict1 = {'1': 2, 3: 4, 'a': [1, -0., '3']}
    hash1 = get_hash(dict1)[0]
    dict2 = {'1': 2, 3: 4, 'a': [1, 0., '3']}
    hash2 = get_hash(dict2)[0]

    assert hash1 == hash2

    dict1 = {'1': 2, 3: 4, 'a': [1, -0., '3', {'1': 0.}]}
    hash1 = get_hash(dict1)[0]
    dict2 = {'1': 2, 3: 4, 'a': [1, 0., '3', {'1': -0.}]}
    hash2 = get_hash(dict2)[0]

    assert hash1 == hash2


@pytest.fixture(scope='module')
def mock_registry(data_path):
    """
    Get an mock registry object
    """
    return MockRegistry(data_path / "registry")


@pytest.fixture
def custom_registry():
    """
    Return an temporary registry
    """
    temp_base = mkdtemp()
    yield MockRegistry(base_path=Path(temp_base))
    rmtree(temp_base)


@pytest.fixture
def temp_path() -> Path:
    """Return an temporary folder"""
    temp_base = mkdtemp()
    yield Path(temp_base)
    rmtree(temp_base)


def test_registry_scan(mock_registry):
    """
    Test repository scanning
    """
    mock_registry.scan()
    assert len(mock_registry.reg_hash) > 0
    # Check some existing mocks are there already
    assert 'H2-geom' in mock_registry.reg_name


def test_registry_extract(mock_registry):
    """Test extracting an folder from the registry"""

    tmpfolder = mkdtemp()
    mock_registry.extract_calc_by_path('H2-geom', tmpfolder)
    objects = [path.name for path in Path(tmpfolder).glob('*')]
    assert 'aiida.castep' in objects
    assert 'aiida.cell' in objects
    assert 'aiida.param' in objects

    rmtree(tmpfolder)


def test_registry_match(mock_registry):
    """Test round-trip hash compute and matching"""

    hash_val = mock_registry.compute_hash(mock_registry.base_path /
                                          'H2-geom/inp')
    assert hash_val in mock_registry.reg_hash


def test_registry_folder_upload(mock_registry, custom_registry, temp_path):
    """Test uploading a folder to the registry"""

    # Exact an existing calculation to the folder
    mock_registry.extract_calc_by_path('H2-geom', temp_path)
    # Upload to a different registry
    custom_registry.upload_calc(temp_path, 'upload-example')

    # Reset the direcotry
    rmtree(str(temp_path))
    temp_path.mkdir()

    # Extract and validate
    assert 'upload-example' in custom_registry.reg_name
    custom_registry.extract_calc_by_path('upload-example', temp_path)
    objects = [path.name for path in temp_path.glob('*')]

    assert 'aiida.castep' in objects
    assert 'aiida.cell' in objects
    assert 'aiida.param' in objects


def test_mock_castep(mock_registry, temp_path, data_path):
    """Test the MockCastep class"""

    # Setup the input directory
    mock_castep = MockCastep(temp_path, mock_registry)
    base_path = data_path / 'registry/H2-geom/inp'

    for obj in ['aiida.cell']:
        copy2(base_path / obj, temp_path / obj)

    with pytest.raises(FileNotFoundError):
        mock_castep.run()

    for obj in ['aiida.param']:
        copy2(base_path / obj, temp_path / obj)

    mock_castep.run()

    objects = [path.name for path in temp_path.glob('*')]
    assert 'aiida.castep' in objects
    assert 'aiida.geom' in objects

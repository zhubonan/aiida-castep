"""
Collection of fixtures for basic setup
"""
from pathlib import Path

import pytest
import tempfile
import shutil


@pytest.fixture(scope='module')
def data_path():
    """Return a path relative to the test data folder"""
    this_file = __file__
    return (Path(this_file).parent / 'data').resolve()


@pytest.fixture(scope='function')
def new_workdir():
    """get a new temporary folder to use as the computer's workdir"""
    dirpath = tempfile.mkdtemp()
    yield Path(dirpath)
    shutil.rmtree(dirpath)


def test_data_path(data_path):
    """
    Test if the data_path exists
    """
    assert data_path.is_dir()

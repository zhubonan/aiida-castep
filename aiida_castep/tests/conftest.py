"""
Collection of fixtures for basic setup
"""
from __future__ import absolute_import
import pytest
import tempfile
import shutil


@pytest.fixture(scope='session')
def Path():
    """Load the Path class"""
    from pathlib import Path
    return Path


@pytest.fixture(scope='function')
def new_workdir(Path):
    """get a new temporary folder to use as the computer's workdir"""
    dirpath = tempfile.mkdtemp()
    yield Path(dirpath)
    shutil.rmtree(dirpath)


@pytest.fixture(scope='module')
def data_path(Path):
    """
    Return the directory to the data folder
    """
    this_file = Path(__file__)
    return (this_file.parent / 'data').resolve()


def test_data_path(data_path):
    """
    Test if the data_path exists
    """
    assert data_path.is_dir()

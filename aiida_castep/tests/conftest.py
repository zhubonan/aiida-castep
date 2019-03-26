"""
Collection of fixtures for basic setup
"""
from __future__ import absolute_import
import pytest
import tempfile
import shutil

@pytest.fixture(scope='function')
def new_workdir():
    """get a new temporary folder to use as the computer's wrkdir"""
    dirpath = tempfile.mkdtemp()
    yield dirpath
    shutil.rmtree(dirpath)


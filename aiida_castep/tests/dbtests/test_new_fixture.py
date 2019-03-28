"""
Test the new fixture
"""

from __future__ import absolute_import


def test_blank(new_database):
    from aiida import is_dbenv_loaded
    assert is_dbenv_loaded()

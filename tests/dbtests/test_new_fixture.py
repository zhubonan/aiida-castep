"""
Test the new fixture
"""

from __future__ import absolute_import


def test_blank(clear_database_before_test):
    from aiida import get_profile
    assert get_profile() is not None

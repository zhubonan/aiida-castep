"""
Test the new fixture
"""

from __future__ import absolute_import


def test_blank(new_database):
    from aiida import get_profile
    assert get_profile() is not None

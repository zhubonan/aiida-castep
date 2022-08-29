"""
Test the new fixture
"""


def test_blank(clear_database_before_test):
    from aiida import get_profile

    assert get_profile() is not None

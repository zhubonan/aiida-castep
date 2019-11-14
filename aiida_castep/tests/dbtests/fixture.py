"""
Fixture for reusing existing test db
"""

from __future__ import absolute_import
import os

from aiida.backends.testbase import check_if_tests_can_run
from aiida.manage.fixtures import FixtureManager
from contextlib import contextmanager


class ExistingProfileFixtureManager(FixtureManager):
    """
    A fixture manager that reuses the existing profile
    """
    def __init__(self):
        super(ExistingProfileFixtureManager, self).__init__()
        self._is_running_on_test_profile = False

    def create_profile(self):
        """Not actually create the profile but reuse the test profile"""
        test_profile = os.environ.get('AIIDA_TEST_PROFILE', None)
        if not test_profile:
            return super(ExistingProfileFixtureManager, self).create_profile()

        from aiida import load_dbenv
        load_dbenv(profile=test_profile)
        check_if_tests_can_run()

        # Running on test profile
        self._is_running_on_test_profile = True

        from aiida.backends.djsite.db.testbase import DjangoTests
        self._test_case = DjangoTests()
        # Load the dbenv

    def destroy_all(self):
        """Do not destroy anything"""
        pass

    def has_profile_open(self):
        return self._is_running_on_test_profile or \
            super(ExistingProfileFixtureManager, self).has_profile_open()


_GLOBAL_FIXTURE_MANAGER = ExistingProfileFixtureManager()


@contextmanager
def fixture_manager():
    try:
        if not _GLOBAL_FIXTURE_MANAGER.has_profile_open():
            _GLOBAL_FIXTURE_MANAGER.backend = 'django'
            _GLOBAL_FIXTURE_MANAGER.create_profile()
        yield _GLOBAL_FIXTURE_MANAGER
    finally:
        _GLOBAL_FIXTURE_MANAGER.reset_db()

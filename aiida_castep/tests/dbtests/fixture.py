"""
Fixture for reusing existing test db
"""

from __future__ import absolute_import
from aiida.backends.testbase import AiidaTestCase
from aiida.manage.fixtures import FixtureManager
from contextlib import contextmanager
from aiida.backends.testbase import check_if_tests_can_run
import pytest

import os

class ExistingProfileFixtureManager(FixtureManager):
    """
    A fixture manager that reuses the existing profile
    """

    def __init__(self):
        super(ExistingProfileFixtureManager, self).__init__()
        self.profile_info = {
            'backend': 'django',
            'email': 'test@aiida.mail',
            'first_name': 'AiiDA',
            'last_name': 'Plugintest',
            'institution': 'aiidateam',
            'db_user': 'aiida',
            "db_pass": "lilURNxqbaJffkcXro1GqwnzBX0wnhM6LpwQd2BEfNesf4i8jW",
            'db_name': 'test_aiida1.0'
        }
        self._is_running_on_test_profile = False

    def create_profile(self):
        """Not actually create the profile but reuse the test profile"""
        test_profile = os.environ.get('AIIDA_TEST_PROFILE', None)
        if test_profile is None:
            return super(ExistingProfileFixtureManager, self).create_profile()

        from aiida import load_dbenv
        load_dbenv(profile=test_profile)
        from aiida.settings import settings
        settings.AIIDADB_PROFILE = test_profile

        # Running on test profile
        self.profile_info["backend"] = "django"
        self._is_running_on_test_profile = True

        from aiida.backends.djsite.db.testbase import DjangoTests
        self._test_case = DjangoTests()
        # Load the dbenv

    def destroy_all(self):
        """Do not destroy anything"""
        pass

    def has_profile_open(self):
        return self._is_running_on_test_profile


_GLOBAL_FIXTURE_MANAGER = ExistingProfileFixtureManager()
@contextmanager
def fixture_manager():

    try:
        if not _GLOBAL_FIXTURE_MANAGER.has_profile_open():
            _GLOBAL_FIXTURE_MANAGER.backend = 'django'
            _GLOBAL_FIXTURE_MANAGER.create_profile()
            # Check we can run the test
            check_if_tests_can_run()
        yield _GLOBAL_FIXTURE_MANAGER
    finally:
        _GLOBAL_FIXTURE_MANAGER.reset_db()


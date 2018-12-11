"""
Collection of fixtures for basic setup
"""
import pytest


@pytest.fixture
def localhost(aiida_profile, tmpdir):
    """Fixture for a local computer called localhost"""
    # Check whether Aiida uses the new backend interface to create collections.
    from aiida.utils.fixtures import _GLOBAL_FIXTURE_MANAGER
    from aiida.common import exceptions
    from aiida.orm import Computer
    aiida_profile = _GLOBAL_FIXTURE_MANAGER
    ldir = str(tmpdir)
    try:
        computer = Computer.get("localhost")

    except exceptions.NotExistent:
        computer = Computer()
        computer.set_name("localhost")
        computer.set_description("localhost")
        computer.set_workdir(ldir)
        computer.set_hostname("localhost")
        computer.set_scheduler_type("direct")
        computer.set_transport_type("local")
        computer.store()
    return computer


@pytest.fixture()
def code_echo(localhost):
    """Fixture of a code that just echos"""
    from aiida.orm import Code
    code = Code()
    code.set_remote_computer_exec(
        (localhost, "/bin/echo"))
    code.set_input_plugin_name("castep.castep")
    code.store()
    return code


@pytest.fixture()
def remotedata(localhost, tmpdir):
    """Create an remote data"""
    from aiida.orm.data.remote import RemoteData

    rmd = RemoteData()
    rmd.set_computer(localhost)
    rmd.set_remote_path(str(tmpdir))
    return rmd


def test_localhost_fixture(localhost):
    """
    Test the localhost fixture
    """
    localhost.name == "localhost"
    assert localhost.pk is not None


def test_code_fixture(code_echo):
    """
    Test the localhost fixture
    """
    assert code_echo.pk is not None
    code_echo.get_remote_exec_path()


def test_remotedata_fixture(remotedata):
    assert remotedata.get_remote_path()

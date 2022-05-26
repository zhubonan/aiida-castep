"""
Mock castep command

Separate cli interface for commands useful in development and testing.
"""
import os
from pathlib import Path
import click

from aiida.cmdline.utils.decorators import with_dbenv

from aiida_castep.utils.mock_code import MockRegistry, MockCastep


def data_path(path):
    """Return a path inside the `data` folder"""
    return Path(__file__).parent.parent.parent / 'tests' / 'data' / path


def output_file(*args):
    return data_path(*args)


@click.command('mock-castep')
@click.argument('seed')
@with_dbenv()
def mock_castep(seed):
    """
    A 'mock' CASTEP code that throws out output files for a given input seed name.
    """
    from aiida.manage.configuration.settings import AIIDA_CONFIG_FOLDER  # pylint: disable=import-outside-toplevel
    pwd = Path(os.getcwd()).absolute()

    aiida_path = Path(AIIDA_CONFIG_FOLDER)
    aiida_cfg = aiida_path / 'config.json'
    click.echo('DEBUG: AIIDA_PATH = {}'.format(os.environ.get('AIIDA_PATH')))
    click.echo('DEBUG: AIIDA_CONFIG_FOLDER = {}'.format(str(aiida_path)))
    assert aiida_path.exists()
    assert aiida_cfg.is_file()
    click.echo(aiida_cfg.read_text())
    param = pwd / f'{seed}.param'
    assert param.is_file(), '<seed>.param input file was not found.'

    cell = pwd / f'{seed}.cell'
    assert cell.is_file(), '<seed>.cell input file was not found.'

    mock_registry_path = os.environ.get('MOCK_CODE_BASE',
                                        data_path('registry'))
    click.echo('DEBUG: MOCK REGSISTRY PATH = {}'.format(
        str(mock_registry_path)))
    mock = MockCastep(pwd, MockRegistry(mock_registry_path))
    mock.run()

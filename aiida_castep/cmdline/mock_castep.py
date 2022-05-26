"""
Mock castep command

Separate cli interface for commands useful in development and testing.
"""
import os
from pathlib import Path
import click

from aiida_castep.utils.mock_code import MockRegistry, MockCastep


def data_path(path):
    """Return a path inside the `data` folder"""
    return Path(__file__).parent.parent.parent / 'tests' / 'data' / path


def output_file(*args):
    return data_path(*args)


@click.command('mock-castep')
@click.argument('seed')
def mock_castep(seed):
    """
    A 'mock' CASTEP code that throws out output files for a given input seed name.
    """
    pwd = Path().absolute()
    mock_output = []

    mock_output.append('MOCK PREPEND: START ----------------------\n')
    mock_output.append('MOCK PREPEND: Mock directory: ' + str(pwd) + '\n')
    mock_output.append('MOCK PREPEND: AIIDA_PATH: ' +
                       os.environ.get('AIIDA_PATH', '') + '\n')

    if not Path(f"{seed}.cell").is_file:
        mock_output.append(f'MOCK PREPEND: {seed}.cell is not found.\n')
        stop_and_return(mock_output)

    if not Path(f"{seed}.param").is_file:
        mock_output.append(f'MOCK PREPEND: {seed}.param is not found.\n')
        stop_and_return(mock_output)

    mock_registry_path = os.environ.get('MOCK_CODE_BASE',
                                        data_path('registry'))

    click.echo('DEBUG: MOCK REGSISTRY PATH = {}'.format(
        str(mock_registry_path)))
    registry = MockRegistry(mock_registry_path)
    mock = MockCastep(pwd, registry, seed)
    if mock.is_runnable:
        detected_path = mock.registry.get_path_by_hash(
            registry.compute_hash(pwd))
        mock_output.append(
            f'MOCK PREPEND: Using test data in path {detected_path} based detection from inputs.\n'
        )
        mock.run()
    else:
        mock_output.append('MOCK PREPEND: No match was found.\n')
        stop_and_return(mock_output)

    # Write the stored information to the stdout file
    with open('_scheduler-stdout.txt', 'a', encoding='utf8') as handler:
        handler.write(''.join(mock_output))


def stop_and_return(castep_mock_output):
    """Halts castep.mock, rebuilds the castep_output and returns."""
    # Assemble the
    print(''.join(castep_mock_output))
    raise RuntimeError('The castep.mock code could not perform a clean run.')

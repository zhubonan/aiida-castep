"""
Test for the mock-castep command.
This requires the (test) db environment to be loaded
"""
import os
import shutil

from pathlib import Path
from click.testing import CliRunner

from aiida_castep.cmdline.mock_castep import mock_castep


def test_mock_command(data_path):
    """Test the mock_castep command"""

    runner = CliRunner()
    with runner.isolated_filesystem():
        shutil.copy(data_path / "registry" / "H2-geom" / 'inp' / 'aiida.cell',
                    os.getcwd() + '/aiida.cell')
        shutil.copy(data_path / "registry" / "H2-geom" / 'inp' / 'aiida.param',
                    os.getcwd() + '/aiida.param')
        os.environ['MOCK_CODE_BASE'] = str(data_path / "registry")
        output = runner.invoke(mock_castep, ['aiida'])

        assert Path("aiida.castep").is_file()
        assert output.exception is None

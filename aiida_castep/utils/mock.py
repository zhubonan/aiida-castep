#!/usr/bin/env python
"""
Mock running CASTEP
"""

from __future__ import absolute_import
from __future__ import print_function
import hashlib
import json
import tempfile
import click
import shutil

import castepinput
from aiida_castep import tests
from pathlib import Path

_TEST_BASE_FOLDER = Path(tests.__file__).parent
_TEST_DATA_FOLDER = _TEST_BASE_FOLDER / 'data'


def get_hash(dict_obj):
    """
    Return hash of a dict of strings
    """

    rec = []
    for k, v in dict_obj.items():
        if isinstance(v, str):
            rec.append(k + ":" + v)
        elif isinstance(v, list):
            rec.append(k + "".join(v))
    # Update, use sorted so the original order does not matter
    base = [record.encode().lower() for record in sorted(rec)]
    # Compute the hash
    md5 = hashlib.md5()
    [md5.update(b) for b in base]
    return md5.hexdigest(), base


def test_hash():
    """Test hashing"""
    exmp = {'a': 'b', 'b': 'a'}
    get_hash(exmp)

    exmp = {'a': 'b', 'b': ['a', 'c']}
    h1, b1 = get_hash(exmp)

    exmp = {'b': ['a', 'c'], 'a': 'b'}
    h2, b2 = get_hash(exmp)
    assert b1 == b2
    assert h1 == h2


class MockOutput(object):
    def __init__(self, base_dir=None):
        """
        Initialize the object
        """
        if base_dir is None:
            self.base_dir = _TEST_DATA_FOLDER
        else:
            self.base_dir = Path(base_dir).resolve()

    def calculate_hash(self, path):

        path = str(path)
        param = castepinput.ParamInput.from_file(path + '.param', plain=True)
        cell = castepinput.CellInput.from_file(path + '.cell', plain=True)
        all_inp = dict(param)
        all_inp.update(cell)
        all_inp.pop('comment', None)
        all_inp.pop('COMMENT', None)
        return get_hash(all_inp)[0]

    @property
    def _reg_file(self):
        """
        Path to the registry file
        """
        return self.base_dir / 'registry.json'

    @property
    def registry(self):
        """
        Registry, a dictionary loaded from the json
        """
        if not self._reg_file.is_file():
            return {}

        with open(str(self._reg_file), 'r') as fh:
            reg = json.load(fh)
        return reg

    def register_node(self, calcjob, tag=None):
        """
        Register the result of a CalcJob node
        :param calcjob: The CalcJob node to be used
        :param tag: Tag for the results, used as the folder name
        """

        # Copy the 'objects' to an temporary directory
        # Include both the retrieved and the inputs
        tmpwork = tempfile.mkdtemp()
        retrieved = calcjob.outputs.retrieved
        for node in [retrieved, calcjob]:
            for nm in node.list_object_names():
                if nm.startswith('.') or \
                   nm.startswith('_'):
                    continue
                with node.open(nm) as fin:
                    fpath = Path(tmpwork) / nm
                    fpath.write_text(fin.read())

        seedpath = Path(tmpwork) / calcjob.get_option('seedname')
        # Register the resutls
        self.register(seedpath, tag)

        shutil.rmtree(tmpwork)

    def register(self, seedpath, tag=None):
        """
        Register completed calculation. Such calculation must be in the directroy
        tree of the mock_castep.py
        """
        seedpath = Path(seedpath).resolve()
        hash_ = self.calculate_hash(seedpath)

        if self._reg_file.is_file():
            try:
                with open(str(self._reg_file)) as fh:
                    reg = json.load(fh)
            except RuntimeError:
                reg = {}
        else:
            reg = {}

        # Relative seedpath to the folder
        try:
            rel_path = seedpath.relative_to(self.base_dir).parent
        except ValueError:
            # It is not placed in the sub folder
            # Copy manually
            import shutil
            if tag is None:
                # Use the first 8 digits as the name
                tag = hash_[:8]

            shutil.copytree(str(seedpath.parent), str(self.base_dir / tag))
            rel_path = tag
        reg[hash_] = str(rel_path)

        # Save the json settings
        with open(str(self._reg_file), 'w') as fh:
            json.dump(reg, fh)

    def copy_results(self, rel_path):
        """
        Copy existing calculation to the folder
        """
        print('Selected path:', rel_path)
        import shutil
        res_files = (self.base_dir / rel_path).glob('*')
        cwd = Path.cwd()
        for r in res_files:
            shutil.copy(str(r), str(cwd))
        return

    def run(self, seedname):
        """
        Run the 'Calculation', if the seed is known we just copy
        the results
        Can be overiden by the 'MOCK_CALC' environmental varaible
        , which define the folder of results to be copied
        """
        import os
        overide = os.environ.get('MOCK_CALC')
        if overide:
            self.copy_results(overide)
            print('Overiden by MOCK_CALC')
            print('Returning results from {}'.format(Path(overide).resolve()))
            return

        hash_ = self.calculate_hash(seedname)
        reg = self.registry

        known_result = reg.get(hash_, None)
        if known_result:
            self.copy_results(known_result)
            print('Returning results from {}'.format(self.base_dir /
                                                     known_result))
        else:
            raise RuntimeError('Results not registered')


@click.command('mock')
@click.option('--reg',
              default=False,
              is_flag=True,
              help='Register the calculation')
@click.option('--tag',
              help='Tag for the folder when registering results',
              default=None)
@click.argument('seed')
def main(seed, reg, tag):
    runner = MockOutput()
    if reg:
        runner.register(seed, tag=tag)
    else:
        runner.run(seed)


if __name__ == "__main__":
    main()

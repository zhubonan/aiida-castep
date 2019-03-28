#!/usr/bin/env python
"""
Mock running CASTEP
"""

from __future__ import absolute_import
from __future__ import print_function
import castepinput
import hashlib
import sys
import json
from pathlib import Path


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
            self.base_dir = Path(__file__).parent
        else:
            self.base_dir = Path(base_dir)

    def calc_hash(self, path):

        param = castepinput.ParamInput.from_file(path + '.param', plain=True)
        cell = castepinput.CellInput.from_file(path + '.cell', plain=True)
        all_inp = dict(param)
        all_inp.update(cell)
        all_inp.pop('comment', None)
        all_inp.pop('COMMENT', None)

    @property
    def _reg_file(self):
        return self.base_dir / 'registry.json'

    @property
    def registry(self):

        if not self._reg_file.is_file():
            return {}

        with open(str(self._reg_file), 'w') as fh:
            reg = json.load(fh)
        return reg

    def register(self, path):
        """
        Register the hash and path
        """
        hash_ = self.calc_hash(path)
        if not self._reg_file.is_file():
            return {}

        with open(str(self._reg_file)) as fh:
            reg = json.load(fh)

        rel_path = path.relative_to(self.base_dir)
        reg[hash_] = str(rel_path)

        with open(str(self._reg_file), 'w') as fh:
            json.dump(fh, reg)

    def copy_results(self, rel_path):
        """
        Copy the results
        """
        print('Selected path:' , rel_path)
        import shutil
        res_files = (self.base_dir / rel_path).glob('*')
        cwd = Path.cwd()
        for r in res_files:
            if r.suffix not in ['.param', '.cell']:
                shutil.copy(str(r), str(cwd))
        return

    def run(self, seedname):
        """
        Run the 'Calculation'
        """
        import os
        overide = os.environ.get('MOCK_CALC')
        if overide:
            self.copy_results(overide)
            print('Overiden by MOCK_CALC')
            print('Returning results from {}'.format(Path(overide).resolve()))
            return

        hash_ = self.calc_hash(seedname)
        reg = self.registry

        res_folder = reg.get(hash_, None)
        if res_folder:
            self.copy_results(res_folder)
            print('Returning results from {}'.format(Path(res_folder).resolve()))
        else:
            raise RuntimeError('Results not registered')


if __name__ == "__main__":

    seedname = sys.argv[1]
    runner = MockOutput()
    runner.run(seedname)

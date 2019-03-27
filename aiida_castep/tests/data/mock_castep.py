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

    def register(self, path):
        """
        Register the hash and path
        """
        hash_ = self.calc_hash(path)
        try:
            with open('registry.json') as fh:
                reg = json.load(fh)
        except FileNotFoundError:
            reg = {}

        rel_path = path.relative_to(self.base_dir)
        reg[hash_] = str(rel_path)

        with open('registry.json', 'w') as fh:
            json.dump(fh, reg)


if __name__ == "__main__":

    seedname = sys.argv[1]
    folder = Path(__file__).parent
    param = castepinput.ParamInput.from_file(seedname + '.param', plain=True)
    cell = castepinput.CellInput.from_file(seedname + '.cell', plain=True)
    all_inp = dict(param)
    all_inp.update(cell)
    all_inp.pop('comment', None)
    all_inp.pop('COMMENT', None)
    print((get_hash(all_inp)))

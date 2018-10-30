#!/usr/bin/env python

from os.path import abspath, dirname, join
from setuptools import setup, find_packages
import json

if __name__ == '__main__':
    # Provide static information in setup.json
    # such that it can be discovered automatically
    ROOT = abspath(dirname(__file__))
    with open(join(ROOT, 'setup.json'), 'r') as info:
        kwargs = json.load(info)

    # Included the README.md as the long description
    with open(join(ROOT, 'README.md'), 'r') as f:
        long_desc = f.read()
    setup(
        packages=find_packages(),
        long_description=long_desc,
        long_description_content_type='text/markdown',
        package_data={'': ['setup.json']},
        **kwargs
    )

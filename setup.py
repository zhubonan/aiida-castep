#!/usr/bin/env python

import subprocess
import os
from os.path import abspath, dirname, join
from setuptools import setup, find_packages
import json

def git_version():
    def _minimal_ext_cmd(cmd):
        # construct minimal environment
        env = {}
        for k in ['SYSTEMROOT', 'PATH', 'HOME']:
            v = os.environ.get(k)
            if v is not None:
                env[k] = v
        # LANGUAGE is used on win32
        env['LANGUAGE'] = 'C'
        env['LANG'] = 'C'
        env['LC_ALL'] = 'C'
        out = subprocess.Popen(cmd, stdout=subprocess.PIPE, env=env).communicate()[0]
        return out

    try:
        out = _minimal_ext_cmd(['git', 'rev-parse', '--short', 'HEAD'])
        GIT_REVISION = out.strip().decode('ascii')
    except OSError:
        GIT_REVISION = "Unknown"

    return GIT_REVISION

if __name__ == '__main__':
    # Provide static information in setup.json
    # such that it can be discovered automatically
    ROOT = abspath(dirname(__file__))
    with open(join(ROOT, 'setup.json'), 'r') as info:
        kwargs = json.load(info)

    # Determine if we are install in the git repository
#    GIT_VERSION = git_version()
#    if GIT_VERSION != "Unkown":
#        kwargs["version"] = kwargs["version"] + "-" + GIT_VERSION

    # Included the README.md as the long description
    with open(join(ROOT, 'README.md'), 'r') as f:
        long_desc = f.read()
    setup(
        packages=find_packages(),
        long_description=long_desc,
        long_description_content_type='text/markdown',
        include_package_data=True,
        **kwargs
    )

#!/usr/bin/env python

from __future__ import absolute_import
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
        out = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                               env=env).communicate()[0]
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

    # Check if in a CI environment
    is_tagged = False
    if os.environ.get('CI_COMMIT_TAG'):
        ci_version = os.environ['CI_COMMIT_TAG']
        is_tagged = True
    elif os.environ.get('CI_JOB_ID'):
        ci_version = os.environ['CI_JOB_ID']
    else:
        # Note in CI
        ci_version = None

    if ci_version:
        # If this a release, check the consistency
        if is_tagged:
            assert ci_version == kwargs[
                'version'], 'Inonsistency between versions'
        else:
            kwargs['version'] = ci_version

# Included the README.md as the long description
    with open(join(ROOT, 'README.md'), 'r') as f:
        long_desc = f.read()
    setup(packages=find_packages(),
          long_description=long_desc,
          long_description_content_type='text/markdown',
          include_package_data=True,
          **kwargs)

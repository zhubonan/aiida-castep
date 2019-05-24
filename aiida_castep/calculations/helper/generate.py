"""
Module for generation HELP information using CASTEP
executable.
"""
from __future__ import print_function
import subprocess as sbp
import re
import sys


def dot_proc(iterable):
    """Provide a primitive progress bar"""
    print("Processing keywords")
    m = len(iterable) - 1
    print("=" * (m // 10))
    for n, i in enumerate(iterable):
        if n % 10 == 0:
            print(".", end="")
            sys.stdout.flush()
        if n == m:
            print("\n")
        yield i


def progress(func, *args, **kwargs):
    try:
        from tqdm import tqdm
    except ImportError:
        return dot_proc(func)
    else:
        return tqdm(func, *args, **kwargs)


def get_castep_commands(castep_command="castep.serial", key="all"):

    outlines = sbp.check_output([castep_command, "-h", key])
    lines = outlines.split("\n")

    cell = {}
    param = {}
    for i, line in enumerate(lines):
        # Skip empty lines
        if not line.strip():
            continue
        if "Help information on CELL keywords" in line:
            continue
        if "Help information on PARAMETERS keywords" in line:
            next_section = i
            break

        key, helpinfo = line.strip().split(None, 1)
        cell[key] = helpinfo

    for line in lines[next_section:]:

        if not line.strip():
            continue

        key, helpinfo = line.strip().split(None, 1)
        param[key] = helpinfo

    return cell, param


allowed_value_re = re.compile(r"Allow values: ([^.\n]+)[.\n]")
default_value_re = re.compile(r"Default value: ([^.\n]+)[.\n]")
type_re = re.compile(r"Type: (\w+)")
level_re = re.compile(r"Level: (\w+)")


def parse_help_string(key, executable):
    """Capture help string, determine if it is for PARAM or CELL"""

    out = sbp.check_output([executable, "-h", key])
    lines = out.split("\n")
    value_type = None
    key_level = None

    for i, line in enumerate(lines):
        if "Help information on PARAMETERS keywords" in line:
            param_start = i

        match = type_re.search(line)
        if match and not value_type:
            value_type = match.group(1).lower()

        match = level_re.search(line)
        if match and not key_level:
            key_level = match.group(1).lower()

    cell_lines = lines[2:param_start]
    param_lines = lines[param_start + 2:]

    if len(cell_lines) > len(param_lines):
        help_lines = cell_lines
        key_type = "CELL"
    else:
        help_lines = param_lines
        key_type = "PARAM"

    return help_lines, key_type, key_level, value_type

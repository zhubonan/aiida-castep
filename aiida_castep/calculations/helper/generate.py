"""
Module for generating castep help information
"""
from __future__ import print_function
import subprocess as sbp
import json
import sys


castep_exe_name = "castep.mpi"


def dot_proc(iterable):
    """Provide a primitive progress bar"""
    print("Processing keywords")
    m = len(iterable) - 1
    print("=" * (m//10))
    for n, i in enumerate(iterable):

        if n % 10 ==0:
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

def get_castep_commands(castep_command="castep.serial"):

    outlines = sbp.check_output([castep_command, "-h", "all"])
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

import re
allowed_value_re = re.compile("Allow values: ([^.\n]+)[.\n]")
default_value_re = re.compile("Default value: ([^.\n]+)[.\n]")
type_re = re.compile("Type: (\w+)")
level_re = re.compile("Level: (\w+)")


def get_help_string(key):
    # NOTE: this is not python3 compatible
    out = sbp.check_output(["castep.serial", "-h", key])
    return out


def parse_help_string(entry):
    """Capture help string, determine if it is for PARAM or CELL"""
    lines = entry.split("\n")
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
    param_lines = lines[param_start+2:]

    if len(cell_lines) > len(param_lines):
        help_lines = cell_lines
        key_type = "CELL"
    else:
        help_lines = param_lines
        key_type = "PARAM"

    return help_lines, key_type, key_level, value_type


def construct_full_dict():
    """
    Construct a dictionary with all keys and relavent help strings

    keywords and sub-keywords are in lower case except the key_tpye whcih is
    either CELL or PARAM
    """

    castep_info = None
    for exe_name in ["castep.mpi", "castep.serial", "castep"]:
        try:
            castep_info = sbp.check_output([exe_name, "--version"])
        except OSError:
            pass
        else:
            break

    if castep_info is None:
        raise RuntimeError("Cannot find castep binary")

    version_num = None
    for line in castep_info.split("\n"):
        if "CASTEP version:" in line:
            version_num = line.split(":")[-1].strip()

    castep_exe_name = exe_name

    print("######## Version info of CASTEP detected ########")
    print(castep_info)

    # Dictonary with short help lines
    cell, param = get_castep_commands(castep_exe_name)

    # The full dictionary
    full_dict = {}
    all = cell
    all.update(param)  # Dictionary of all the keys

    for key in progress(all):
        help_string = get_help_string(key)
        lines, k_type, k_level, v_type = parse_help_string(help_string)
        full_dict[key.lower()] = dict(help_short = all[key],
                                      help_full = "\n".join(lines),
                                      key_type= k_type,
                                      key_level= k_level,
                                      value_type = v_type)
    full_dict["_CASTEP_VERSION"] =  version_num

    return full_dict


if __name__ == "__main__":
    res  = construct_full_dict()

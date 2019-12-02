"""
Command line interface for generating CASTEP help information
"""

from __future__ import print_function
from __future__ import absolute_import
import click
import sys
from aiida.cmdline.commands.cmd_data import verdi_data
from six.moves import map
from six.moves import zip


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


@verdi_data.group('castep-help')
def helper_cmd():
    """Commandline interface for controlling helper information"""
    pass


@helper_cmd.command(name="generate")
@click.option("--castep-excutable",
              "-e",
              help="The excutable of CASTEP to be used",
              default="castep.serial")
@click.option("--save-as", "-s", help="override default path for saving file")
def generate(castep_excutable, save_as):
    """
    Generate help information file.

    The generated file will be saved as .castep_help_info_<version>.json
    at the $HOME by default.
    """
    from aiida_castep.calculations.helper.generate import (get_castep_commands,
                                                           parse_help_string)

    import subprocess as sbp
    import os
    try:
        castep_info = sbp.check_output([castep_excutable, "--version"],
                                       universal_newlines=True)
    except OSError:
        print("Not a valid CASTEP excutable. Aborted.")
        return

    version_num = None
    for line in castep_info.split("\n"):
        if "CASTEP version:" in line:
            version_num = line.split(":")[-1].strip()

    if save_as is None:
        fname = ".castep_help_info_{}.json".format(version_num)
        save_as = os.path.join(os.getenv("HOME"), fname)
    else:
        save_as = os.path.abspath(save_as)

    print("######## Version info of CASTEP ########")
    print(castep_info)
    print("Save path: {}".format(save_as))

    respond = click.prompt("Please check CASTEP version. [Y/N]")
    if not respond.lower() == "y":
        print("Aborted")
        return
    # Dictonary with short help lines
    all_keys = {}
    for key in ["basic", "inter", "expert"]:
        c, p = get_castep_commands(castep_excutable, key)
        all_keys.update(c)
        all_keys.update(p)

    # The full dictionary
    full_dict = {}

    for key in progress(all_keys):
        lines, k_type, k_level, v_type = parse_help_string(key)
        full_dict[key.lower()] = dict(help_short=all_keys[key],
                                      help_full="\n".join(lines),
                                      key_type=k_type,
                                      key_level=k_level,
                                      value_type=v_type)
    full_dict["_CASTEP_VERSION"] = version_num

    import json
    with open(save_as, "w") as json_out:
        json.dump(full_dict, json_out)
    print("Help information saved at {}".format(save_as))


@helper_cmd.command("show")
@click.argument("keyword")
def show_help(keyword):
    """
    Show help information given a keyword.
    Equivalent as castep -h <keyword> use the information previously saved.
    """
    helper = get_helper()
    h_text = helper.help_dict[keyword]["help_full"]
    print("")
    print(h_text)


@helper_cmd.command("list")
@click.option("--filter", "-f", help="Filter keys")
def list_keywords(filter):
    """
    Print out all avaliable keywords.
    Optional filter can be applied.
    """
    helper = get_helper()
    h_dict = helper.help_dict

    def print_keys(ktype):
        print("List of keywords in {} file:\n".format(ktype))
        for key, value in h_dict.items():

            if not isinstance(value, dict):
                continue
            if value["key_type"] == ktype:
                if filter is None or key.find(filter) != -1:
                    print("{:<40}{}".format(key, value["help_short"]))

        print("")

    print_keys("CELL")
    print_keys("PARAM")


@helper_cmd.command("listfile")
def list_file():
    """
    List files aviable to use.
    """

    from aiida_castep.calculations.helper import find_help_info
    pairs = find_help_info()
    if not pairs:
        print("No avaliale file detected")

    print("Avaliable files:")
    print("{:<67} | {:^10}".format('Path', 'version'))
    print("-" * 80)
    for path, version in pairs:
        if version == 0:
            version = 'NOT_SPECIFIED'
        print("{:<30} | {:>10}".format(path, version))


def get_helper(*args, **kwargs):
    """
    Get a helper object
    """
    from aiida_castep.calculations.helper import CastepHelper
    helper = CastepHelper(*args, **kwargs)
    return helper


if __name__ == "__main__":
    helper_cmd()

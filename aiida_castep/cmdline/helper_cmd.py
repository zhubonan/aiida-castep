"""
Command line interface for generating CASTEP help information
"""

import sys

import click
from aiida.cmdline.commands.cmd_data import verdi_data


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


@verdi_data.group("castep-help")
def helper_cmd():
    """Commandline interface for controlling helper information"""
    pass


@helper_cmd.command(name="generate")
@click.option("--castep-executable", "-e", help="The excutable of CASTEP to be used")
@click.option("--save-as", "-s", help="override default path for saving file")
def generate(castep_executable, save_as):
    """
    Generate help information file.

    The generated file will be saved as .castep_help_info_<version>.json
    at the $HOME by default.
    """
    import os
    import subprocess as sbp

    from aiida_castep.calculations.helper.generate import (
        get_castep_commands,
        parse_help_string,
    )

    # Work out the executable name automatically
    if castep_executable is None:
        castep_executable = "castep.serial"
        completed = sbp.run(["which", castep_executable], stdout=sbp.PIPE, check=False)
        if completed.returncode == 0:
            castep_executable = "castep.serial"
        elif (
            sbp.run(["which", "castep.mpi"], stdout=sbp.PIPE, check=False).returncode
            == 0
        ):
            castep_executable = "castep.mpi"
        elif sbp.run(["which", "castep"], stdout=sbp.PIPE, check=False).returncode == 0:
            castep_executable = "castep"
    try:
        castep_info = sbp.check_output(
            [castep_executable, "--version"], universal_newlines=True
        )
    except OSError:
        print("Not a valid CASTEP excutable. Aborted.")
        return

    version_num = None
    for line in castep_info.split("\n"):
        if "CASTEP version:" in line:
            version_num = line.split(":")[-1].strip()

    if save_as is None:
        fname = f".castep_help_info_{version_num}.json"
        save_as = os.path.join(os.getenv("HOME"), fname)
    else:
        save_as = os.path.abspath(save_as)

    print("######## Version info of CASTEP ########")
    print(castep_info)
    print(f"Save path: {save_as}")

    respond = click.prompt("Please check CASTEP version. [Y/N]")
    if not respond.lower() == "y":
        print("Aborted")
        return
    # Dictonary with short help lines
    all_keys = {}
    for key in ["basic", "inter", "expert"]:
        c, p = get_castep_commands(castep_executable, key)
        all_keys.update(c)
        all_keys.update(p)

    # The full dictionary
    full_dict = {}

    for key in progress(all_keys):
        lines, k_type, k_level, v_type = parse_help_string(
            key, excutable=castep_executable
        )
        full_dict[key.lower()] = dict(
            help_short=all_keys[key],
            help_full="\n".join(lines),
            key_type=k_type,
            key_level=k_level,
            value_type=v_type,
        )
    full_dict["_CASTEP_VERSION"] = version_num

    import json

    with open(save_as, "w") as json_out:
        json.dump(full_dict, json_out)
    print(f"Help information saved at {save_as}")


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
        print(f"List of keywords in {ktype} file:\n")
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
    print("{:<67} | {:^10}".format("Path", "version"))
    print("-" * 80)
    for path, version in pairs:
        if version == 0:
            version = "NOT_SPECIFIED"
        print(f"{path:<30} | {version:>10}")


def get_helper(*args, **kwargs):
    """
    Get a helper object
    """
    from aiida_castep.calculations.helper import CastepHelper

    helper = CastepHelper(*args, **kwargs)
    return helper


if __name__ == "__main__":
    helper_cmd()

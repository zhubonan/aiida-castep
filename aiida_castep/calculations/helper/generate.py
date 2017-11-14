"""
Module for generating castep help information
"""
import os
import subprocess as sbp
import io
import tempfile
import json


def get_castep_commands(castep_command="castep.serial"):

    temp = open("tempout", "wr")
    proc = sbp.call([castep_command, "-h", "all"], stdout=temp)
    temp.close()

    temp = open("tempout", "r")
    lines = temp.readlines()
    temp.close()

    cell = {}
    param = {}
    for i, line in enumerate(lines):
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

    os.remove("tempout")

    return cell, param


if __name__ == "__main__":
    cell, param = get_castep_commands()
    with open("cell.json", "w") as fp:
        json.dump(cell, fp)

    with open("param.json", "w") as fp:
        json.dump(param, fp)

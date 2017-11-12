"""
Module for parsing .castep file
"""
# TODO Parse more properties

import os
import re
from aiida_castep.parsers import CASTEPOutputParsingError


def parse_raw_ouput(outfile, input_dict, parser_opts=None):
    """
    Parser an dot_castep file
    :param outfile: path to .castep file

    :returns out_dict: a dictionary with parsed data
    :return trajectory_data: dictionary of trajectory data
    :return successful: a boolean that is False in case of failed calculations

    2 different keys to check in ouput : parser_warning and warnings.
    The first one should be empty unless the run is not failed or unfinished
    """

    import copy

    parser_version = "0.1"
    parser_info = {}
    parser_info["parser_warnings"] = []
    parser_info["parser_info"] = "AiiDA CASTEP basic Parser v{}".format(parser_version)


    job_successful = True

    try:
        with open(outfile , "r") as f:
            # Store ouput lines in list
            # OK if the file is not huge
            out_lines = f.readlines()
    except IOError:
            raise CASTEPOutputParsingError("Failed to open file: {}".format(outfile))

    if not out_lines:  # The file is empty
        job_successful = False

    finished_run = False

    # T
    for line in reversed(out_lines):
        if "Total time" in line:
            finished_run = True
            break

    # Warn if the run is not finished
    if not finished_run:
        warning = "CASTEP run did not reach the end of execution."
        parser_info["parser_warnings"].append(warning)
        job_successful = False

    # Parse the data and store
    try:
        out_data, trajectory_data, critical_messages = parse_castep_text_output(out_lines, input_dict)

    except CASTEPOutputParsingError as e:
        if not finished_run:
            parser_info["parser_warnings"].append("Error while parsing the output file")
            out_data = {}
            trajectory_data = {}
            critical_messages = []

        else:  # Run finished but I have still have an error here
            raise CASTEPOutputParsingError("Error while parsing ouput. Exception message: {}".format(e.message))

    # Parameter data to be returned
    parameter_data = dict(out_data.items() + parser_info.items())

    # Todo Validation of ouput data
    return parameter_data, trajectory_data, job_successful


def parse_castep_text_output(out_lines, input_dict):
    """
    Parse ouput of .castep

    :param out_lines: a list of lines from readlines function
    :param input_dict: not used here

    :return parsed_data: dictionary with key values, reffering to the last occuring quanties
    :return trajectory_data: key, values of the intermediate scf steps, such as
    during geometryoptimization
    :reutrn critical_messages: a list with critical messages.
    If any is found in parsed_data["warnings"] the calucaltion is failed.
    """

    parsed_data = {}
    parsed_data["warnings"] = []
    trajectory_data = {}
    trajectory_data["enthalpy"] = []

    critical_warnings = {"Geometry optimization failed to converge":
    "Maximum geometry optimization cycle has been reached",
    "SCF cycles performed but system has not reached the groundstate":"SCF cycles failed to converge"}

    minor_warnings = {"Warning": None}
    all_warnings = dict(critical_warnings.items() + minor_warnings.items())

    # Parse non-repeating informaton e.g initialisation etc
    for count, line in enumerate(out_lines):
        if "Calculation parallelised over" in line:
            num_cores = int(line.strip().split()[-2])
            parsed_data["parallel_procs"] = num_cores

        # For dm and fixed occupancy runs
        if "Final free" in line or "Final energy" in line:
            free_eng = line.strip().split()[-2]
            parsed_data["energy"] = float(free_eng)


        if "finished iteration" in line:
            geom_H  = float(line.strip().split()[-2])
            trajectory_data["enthalpy"].append(geom_H)
        if any(i in line for i in all_warnings):
            message = [ all_warnings[i] for i in all_warnings.keys() if i in line][0]
            if message is None:
                message = line

            parsed_data["warnings"].append(message)

    return parsed_data, trajectory_data, critical_warnings.values()






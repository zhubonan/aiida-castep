"""
Module for parsing .castep file
"""
# TODO Parse more properties

import os
import re
import numpy as np
from aiida_castep.parsers import CASTEPOutputParsingError


# TODO update CODATA for castep 16.1 and above

# CODATA1986 (included herein for the sake of completeness)
# taken from
#    http://physics.nist.gov/cuu/Archive/1986RMP.pdf
units_CODATA1986 = {
    'hbar': 6.5821220E-16,      # eVs
    'Eh': 27.2113961,           # eV
    'kB': 8.617385E-5,          # eV/K
    'a0': 0.529177249,          # A
    'c': 299792458,             # m/s
    'e': 1.60217733E-19,        # C
    'me': 5.485799110E-4}       # u

# CODATA2002: default in CASTEP 5.01
# (-> check in more recent CASTEP in case of numerical discrepancies?!)
# taken from
#    http://physics.nist.gov/cuu/Document/all_2002.pdf

units_CODATA2002 = {
    'hbar': 6.58211915E-16,     # eVs
    'Eh': 27.2113845,           # eV
    'kB': 8.617343E-5,          # eV/K
    'a0': 0.5291772108,         # A
    'c': 299792458,             # m/s
    'e': 1.60217653E-19,        # C
    'me': 5.4857990945E-4}      # u

# (common) derived entries
for d in (units_CODATA1986, units_CODATA2002):
    d['t0'] = d['hbar'] / d['Eh']     # s
    d['Pascal'] = d['e'] * 1E30       # Pa
units = units_CODATA2002

unit_suffix = "_units"

def parse_raw_ouput(outfile, input_dict, parser_opts=None, geom_file=None):
    """
    Parser an dot_castep file
    :param outfile: path to .castep file
    :param geom_file: path to the .geom file

    :returns out_dict: a dictionary with parsed data
    :return trajectory_data: dictionary of trajectory data
    :return successful: a boolean that is False in case of failed calculations

    2 different keys to check in ouput : parser_warning and warnings.
    The first one should be empty unless the run is not failed or unfinished
    """

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


    # Use Total time as a mark for completed run
    for i, line in enumerate(reversed(out_lines)):
        # Check only the last 20 lines
        # Otherwise unfinished restarts may be seen as finished
        if i >= 20:
            break
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

        # Use data from geom file if avaliable.
        if geom_file is not None:
            with open(geom_file) as gfile:
                glines = gfile.readlines()
            geom_data = parser_geom_text_output(glines, None)
            trajectory_data.update(geom_data)


    except CASTEPOutputParsingError as e:
        if not finished_run:
            parser_info["parser_warnings"].append("Error while parsing the output file")
            out_data = {}
            trajectory_data = {}
            critical_messages = []

        else:  # Run finished but I have still have an error here
            raise CASTEPOutputParsingError("Error while parsing ouput. Exception message: {}".format(e.message))

    # Construct a structure data from the last frame
    try:
        last_cell = trajectory_data["cells"][-1]
        last_positions = trajectory_data["positions"][-1]
        symbols = trajectory_data["symbols"]

    except KeyError:
        # Cannot find the last geometry data
        structure_data = {}
    else:
        structure_data = dict(cell=last_cell, positions=last_positions, symbols=symbols)

    # Parameter data to be returned
    parameter_data = dict(out_data.items() + parser_info.items())

    # Todo Validation of ouput data
    return parameter_data, trajectory_data, structure_data, job_successful

# Re for getting unit
unit_re = re.compile("^ output\s+(\w+) unit\s+:\s+([^\s]+\s*$)")
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
    Keys: cells, positions, forces, energies
    """
    from collections import defaultdict

    psedu_files = {}
    parsed_data = {}
    parsed_data["warnings"] = []

    # Initialise storage space for trajectory
    # Not all is needed. But we parse as much as we can here
    trajectory_data = defaultdict(list)

    critical_warnings = {"Geometry optimization failed to converge":
    "Maximum geometry optimization cycle has been reached",
    "SCF cycles performed but system has not reached the groundstate":"SCF cycles failed to converge"}

    minor_warnings = {"Warning": None}
    all_warnings = dict(critical_warnings.items() + minor_warnings.items())

    def pair_split(lines, spliter):
        """Split the line in to two. Ignore space around spliter"""
        lines.strip().split(spliter)

    # Split header and body
    for i, line in enumerate(out_lines):

        unit_match = unit_re.match(line)
        if unit_match:
            uname = unit_match.group(1)
            uvalue = unit_match.group(2)
            parsed_data["unit_"+ uname] = uvalue

        if "Files used for pseudopotentials" in line:
            for line in out_lines[i+1:]:
                if "---" in line:
                    break
                else:
                    try:
                        specie, psedu_file = line.strip().split()
                    except ValueError:
                        break
                    else:
                        psedu_files.update({specie: psedu_file})
        if "Total number of ions" in line:
            parsed_data["num_ions"] = int(line.strip().split("=")[1].strip())

        if "Point group of crystal" in line:
            parsed_data["point_group"] = line.strip().split("=")[1].strip()

        if "Space group of crystal" in line:
            parsed_data["space_group"] = line.strip().split("=")[1].strip()

        if "Cell constraints" in line:
            parsed_data["cell_constraints"] = line.strip().split(":")[1].strip()
        if "Number of kpoints used" in line:
            parsed_data["n_kpoints"] = line.strip().split("=")[1].strip()

        if "MEMORY AND SCRATCH DISK ESTIMATES" in line:
            body_start = i
            break

    parsed_data.update(psedu_pots=psedu_files)

    def append_value_and_unit(line, name):
        """
        Generat extract data from = <value> <unit> line
        """
        elem = line.strip().split()
        value  = float(elem[-2])
        trajectory_data[name].append(value)

    # Parse repeating information
    skip = 0
    for count, line in enumerate(out_lines[body_start:]):

        # Allow sking certain number of lines
        if skip > 0:
            skip -= 1
            continue

        if "Calculation parallelised over" in line:
            num_cores = int(line.strip().split()[-2])
            parsed_data["parallel_procs"] = num_cores
            continue

        # For dm and fixed occupancy runs
        if "Final energy" in line:
            append_value_and_unit(line, "total_energy")
            continue

        if "Final free" in line:
            append_value_and_unit(line, "free_energy")
            continue

        if "0K energy" in line:
            append_value_and_unit(line, "zero_K_energy")
            continue

        if "Integrated Spin" in line:
            append_value_and_unit(line, "spin_density")
            continue


        if "Integrated |Spin" in line:
            append_value_and_unit(line, "abs_spin_density")
            continue

        if "finished iteration" in line:
            append_value_and_unit(line, "enthalpy")
            continue

        if "Stress Tensor" in line:
            i, stress, pressure = parse_stress_box(out_lines[count:count+20])
            assert len(stress) == 3
            if "Symmetrised" in line:
                prefix = "symm_"
            else:
                prefix = ""
            trajectory_data[prefix + "pressure"].append(pressure)
            trajectory_data[prefix + "stress"].append(stress)
            skip = i

        if "Forces *******" in line:
            num_lines = parsed_data["num_ions"] + 20
            i, forces = parse_force_box(out_lines[count:count+num_lines])

            if "Constrained" in line:
                forc_name = "cons_force"
            else:
                forc_name = "force"
            trajectory_data[forc_name].append(forces)
            skip = i


        if any(i in line for i in all_warnings):
            message = [ all_warnings[i] for i in all_warnings.keys() if i in line][0]
            if message is None:
                message = line
            parsed_data["warnings"].append(message)

    return parsed_data, trajectory_data, critical_warnings.values()


# This function is modified from ase's geom reader
def parser_geom_text_output(out_lines, input_dict):
    """
    Parse output of .geom file

    :param out_lines: a list of lines from the readline function
    :param input_dict: not in use at the moment

    :return parsed_data: key, value of the trajectories of cell, atoms,
    force etc
    """
    txt = out_lines
    Hartree = units['Eh']
    Bohr = units['a0']

    # Yeah, we know that...
    # print('N.B.: Energy in .geom file is not 0K extrapolated.')
    cell_list = []
    species_list = []
    geom_list  = []
    forces_list = []
    energy_list = []

    # Taken from ASE with minor modifications
    for i, line in enumerate(txt):
        if '<-- E' in line:
            start_found = True
            energy = float(line.split()[0]) * Hartree
            cell = [x.split()[0:3] for x in txt[i + 1:i + 4]]
            cell = np.array([[float(col) * Bohr for col in row] for row in
                             cell])
            cell_list.append(cell)
            energy_list.append(energy)
        if '<-- R' in line and start_found:
            start_found = False
            geom_start = i
            for i, line in enumerate(txt[geom_start:]):
                if '<-- F' in line > 0:
                    geom_stop = i + geom_start
                    break
            species = [line.split()[0] for line in
                       txt[geom_start:geom_stop]]
            geom = np.array([[float(col) * Bohr for col in
                              line.split()[2:5]] for line in
                             txt[geom_start:geom_stop]])
            forces = np.array([[float(col) * Hartree / Bohr for col in
                                line.split()[2:5]] for line in
                               txt[geom_stop:geom_stop +
                                   (geom_stop - geom_start)]])
            species_list.append(species)
            geom_list.append(geom)
            forces_list.append(forces)
    if len(species_list) == 0:
        raise CASTEPOutputParsingError("No data found in geom file")

    return dict(cells = np.array(cell_list),
                positions = np.array(geom_list),
                forces = np.array(forces_list),
                geom_energy = np.array(energy_list),
                symbols = species_list[0]
                )




def parse_force_box(lines):
    """
    Parse a box of the forces
    :param lines: a list of upcoming lines

    :returns line read: number of lines read
    :return forces: forces parsed
    """

    forces = []
    for i , line in enumerate(lines):

        if "Forces" in line:
            continue
        if "Cartisian components" in line:
            unit = line.strip().split()[-2]
            unit = unit[1:-2]
            continue

        if "**********************" in line:
            break

        line = line.strip(" *")
        if not line:
            continue

        lsplit = line.split()
        if len(lsplit) == 5:
            forces.append([float(f) for f in lsplit[-3:]])

    return i, forces


def parse_stress_box(lines):
    """
    Parse a box of the stress
    :param lines: a list of upcoming lines

    :returns line read: number of lines read
    :return stress tensor: a 3 by 3 tensor
    :return pressure: a float of pressure
    """

    stress = []
    for i , line in enumerate(lines):
        if "Stress" in line:
            continue

        if "Cartisian components" in line:
            unit = line.strip().split()[-2]
            unit = unit[1:-2]
            continue

        if "**********************" in line:
            break

        line = line.strip(" *")
        if not line:
            continue

        lsplit = line.split()
        if len(lsplit) == 4:
            stress.append([float(s) for s in lsplit[-3:]])
            continue

        if "Pressure" in line:
            pressure = float(lsplit[-1])


    return i, stress, pressure

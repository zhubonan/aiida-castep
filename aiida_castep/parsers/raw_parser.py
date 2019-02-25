"""
Module for parsing .castep file
"""

import re
import numpy as np
from aiida_castep.parsers.utils import CASTEPOutputParsingError

import logging
logger = logging.getLogger("aiida")

from .._version import calc_parser_version
__version__ = calc_parser_version

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

units_CODATA2010 = {
    'c': 299792458,
    'hbar': 6.58211928e-16,  # eV
    'e': 1.602176565e-19,    # C
    'Av': 6.02214129e23,     # Avogadro constant
    'R': 8.3144621,          # Gas constrant
    'Eh': 27.21138505,       # eV
    'a0': 0.52917721092,     # A - bohr radius
    'me': 5.4857990946e-4,    # u
    'kB': 8.6173324E-5          # eV/K
}

# (common) derived entries
for d in (units_CODATA1986, units_CODATA2002, units_CODATA2010):
    d['t0'] = d['hbar'] / d['Eh']     # s
    d['Pascal'] = d['e'] * 1E30       # Pa
units = units_CODATA2010

unit_suffix = "_units"

SCF_FAILURE_MESSAGE = "SCF cycles failed to converge"
GEOM_FAILURE_MESSAGE = "Maximum geometry optimization cycle has been reached"
END_NOT_FOUND_MESSAGE = "CASTEP run did not reach the end of execution."
INSUFFICENT_TIME_MESSAGE = "CASTEP run terminated due to insufficient run time left."
STOP_REQUESTED_MESSAGE = "CASTEP run terminated due to requested STOP in param file."


def parse_raw_ouput(outfile, input_dict,
                    parser_opts=None, md_geom_file=None,
                    bands_file=None):
    """
    Parse an dot_castep file
    :param outfile: path to .castep file
    :param md_geom_file: path to the .geom file or .md file
    :return: A list of:

     * out_dict: a dictionary with parsed data.
     * trajectory_data: dictionary of trajectory data.
     * structure data: dictionary of cell, positions and symbols.
     * successful: a boolean that is False in case of failed calculations.

    2 different keys to check in out_dict: *parser_warning* and *warnings*.
    """

    parser_version = __version__
    parser_info = {}
    parser_info["parser_warnings"] = []
    parser_info["parser_info"] = "AiiDA CASTEP basic Parser v{}".format(
        parser_version)
    parser_info["warnings"] = []

    job_successful = True

    try:
        with open(outfile, "r") as f:
            # Store ouput lines in list
            # OK if the file is not huge
            out_lines = f.readlines()
    except IOError:
        raise CASTEPOutputParsingError(
            "Failed to open file: {}".format(outfile))

    if not out_lines:  # The file is empty
        job_successful = False

    finished_run = False

    # Use Total time as a mark for completed run
    for i, line in enumerate(out_lines[-20:]):
        # Check only the last 20 lines
        # Otherwise unfinished restarts may be seen as finished
        if "Total time" in line:
            finished_run = True
            break

    # Warn if the run is not finished
    if not finished_run:
        warning = END_NOT_FOUND_MESSAGE
        parser_info["warnings"].append(warning)
        job_successful = False

    # Parse the data and store
    try:
        out_data, trajectory_data, critical_messages = parse_castep_text_output(
            out_lines, input_dict)

        # Use data from geom file if avaliable.
        if md_geom_file is not None:
            with open(md_geom_file) as gfile:
                glines = gfile.readlines()
            geom_data = parse_geom_text_output(glines, None)
            # For geom file the second energy is the enthalpy while
            # for MD it is the approx hamiltonian (etotal + ek)
            if "geom" in md_geom_file:
                geom_data["geom_enthalpy"] = geom_data["hamilt_energy"]
            trajectory_data.update(geom_data)


        if bands_file is not None:
            bands_data = parse_dot_bands(bands_file)
        else:
            bands_data = None

    except CASTEPOutputParsingError as e:
        if not finished_run:
            parser_info["parser_warnings"].append(
                "Error while parsing the output file")
            out_data = {}
            trajectory_data = {}
            critical_messages = []

        else:  # Run finished but I have still have an error here
            raise CASTEPOutputParsingError(
                "Error while parsing ouput. Exception message: {}".format(e.message))

    # Check if any critical messages has been passed
    # If there is any cricial message we should make the run marked as FAILED
    for w in out_data["warnings"]:
        if w in critical_messages:
            job_successful = False
            break

    # Construct a structure data from the last frame
    try:
        last_cell = trajectory_data["cells"][-1]
        last_positions = trajectory_data["positions"][-1]
        symbols = trajectory_data["symbols"]

    except (KeyError, IndexError):
        # Cannot find the last geometry data
        structure_data = {}
    else:
        structure_data = dict(
            cell=last_cell, positions=last_positions, symbols=symbols)

    # Parameter data to be returned
    parameter_data = dict(out_data.items() + parser_info.items())

    # Combine the warnings
    all_warnings = out_data["warnings"] + parser_info["warnings"]

    # Make the warnings set-like e.g we don't want to repeat messages
    # Save a bit of the storage space
    all_warnings = list(set(all_warnings))
    parameter_data['warnings'] = all_warnings

    # Todo Validation of ouput data
    return [parameter_data,
            trajectory_data, structure_data,
            bands_data, job_successful]


# Re for getting unit
unit_re = re.compile("^ output\s+(\w+) unit *: *([^\s]+)")
time_re = re.compile("^(\w+) time += +([0-9.]+) s$")
parallel_re = re.compile(
    "^Overall parallel efficiency rating: [\w ]+ \(([0-9]+)%\)")
version_re = re.compile("CASTEP version ([0-9.]+)")


def parse_castep_text_output(out_lines, input_dict):
    """
    Parse ouput of .castep
    :param out_lines: a list of lines from readlines function

    :param input_dict: Control some variables. Currently support

    'n_warning_lines'- number of the lines to include for a general warning.

    :return: A list of parsed_data, trajectory_data and critical_messages:

     * parsed_data: dictionary with key values, referring to the last
       occurring quantities

     * trajectory_data: key, values of the intermediate scf steps,
       such as during geometryoptimization

     * critical_messages: a list with critical messages.

    If any is found in parsed_data["warnings"] the calculation should be considered as failed.
    """
    from collections import defaultdict

    pseudo_files = {}
    parsed_data = {}
    parsed_data["warnings"] = []

    if not input_dict:
        input_dict = {}

    # Some parameters can be controlled
    n_warning_lines = input_dict.get("n_warning_lines", 10)

    # Initialise storage space for trajectory
    # Not all is needed. But we parse as much as we can here
    trajectory_data = defaultdict(list)

    # In the format {<keywords in line>:<message to pass>}
    critical_warnings = {
        "SCF cycles performed but system has not reached the groundstate": SCF_FAILURE_MESSAGE,
        "NOSTART": "Can not find start of the calculation.",
        "STOP keyword detected in parameter file. Stop execution.": STOP_REQUESTED_MESSAGE,
        }

    # Warnings that won't result in a calculation in FAILED state
    minor_warnings = {"Warning": None,
                     "Geometry optimization failed to converge": GEOM_FAILURE_MESSAGE,
                     "Insufficient time for another iteration": INSUFFICENT_TIME_MESSAGE}


    # A dictionary witch keys we should check at each line
    all_warnings = dict(critical_warnings.items() + minor_warnings.items())
    # Create a list of keys, the order is important here
    # specific warnings can be matched first

    all_warnings_keys = list(critical_warnings.keys()) + \
        list(minor_warnings.keys())

    def pair_split(lines, spliter):
        """Split the line in to two. Ignore space around spliter"""
        lines.strip().split(spliter)

    # Split header and body
    body_start = None
    version = None
    for i, line in enumerate(out_lines):

        # Find the castep version
        if version is None:
            vmatch = version_re.search(line)
            if vmatch:
                version = vmatch.group(1)
                parsed_data["castep_version"] = version

        # Finding the units we used
        unit_match = unit_re.match(line)
        if unit_match:
            uname = unit_match.group(1)
            uvalue = unit_match.group(2)
            parsed_data["unit_" + uname] = uvalue

        if "Files used for pseudopotentials" in line:
            for line in out_lines[i + 1:]:
                if "---" in line:
                    break
                else:
                    try:
                        specie, pp_file = line.strip().split()
                    except ValueError:
                        break
                    else:
                        pseudo_files.update({specie: pp_file})
        if "Total number of ions" in line:
            parsed_data["num_ions"] = int(line.strip().split("=")[1].strip())
            continue

        if "Point group of crystal" in line:
            parsed_data["point_group"] = line.strip().split("=")[1].strip()
            continue

        if "Space group of crystal" in line:
            parsed_data["space_group"] = line.strip().split("=")[1].strip()
            continue

        if "Cell constraints" in line:
            parsed_data["cell_constraints"] = line.strip().split(":")[
                1].strip()
            continue

        if "Number of kpoints used" in line:
            parsed_data["n_kpoints"] = line.strip().split("=")[1].strip()
            continue

        if "MEMORY AND SCRATCH DISK ESTIMATES" in line:
            body_start = i
            break

    # If we don't find a start of body then there is something wrong
    if body_start is None:
        parsed_data["warnings"].append(critical_warnings["NOSTART"])
        return parsed_data, {}, critical_warnings.values()

    parsed_data.update(pseudo_pots=pseudo_files)

    def append_value_and_unit(line, name):
        """
        Extract data from = <value> <unit> line
        """
        elem = line.strip().split()
        value = float(elem[-2])
        trajectory_data[name].append(value)

    # Parse repeating information
    skip = 0
    body_lines = out_lines[body_start:]

    iter_parser = get_iter_parser()
    for count, line in enumerate(body_lines):

        # Allow sking certain number of lines
        if skip > 0:
            skip -= 1
            continue

        res_tmp = iter_parser.parse(line)
        if res_tmp:
            name, value = res_tmp[:2]
            trajectory_data[name].append(value)
            continue

        if "Calculation parallelised over" in line:
            num_cores = int(line.strip().split()[-2])
            parsed_data["parallel_procs"] = num_cores
            continue

        if "Stress Tensor" in line:
            i, stress, pressure = parse_stress_box(
                body_lines[count:count + 20])
            assert len(stress) == 3
            if "Symmetrised" in line:
                prefix = "symm_"
            else:
                prefix = ""
            trajectory_data[prefix + "pressure"].append(pressure)
            trajectory_data[prefix + "stress"].append(stress)
            skip = i

        if "Forces *******" in line:
            num_lines = parsed_data["num_ions"] + 10
            box = body_lines[count: (count + num_lines)]
            i, forces = parse_force_box(box)

            if "Constrained" in line:
                forc_name = "cons_forces"
            else:
                forc_name = "forces"
            if not forces:
                logger.error("Cannot parse force lines {}".format(box))
            trajectory_data[forc_name].append(forces)
            skip = i
            continue

        if any(i in line for i in all_warnings):
            message = [all_warnings[k] for k in all_warnings_keys
                       if k in line][0]
            if message is None:
                # CASTEP often have multiline warnings
                # Add extra lines for detail
                message = body_lines[count:count + n_warning_lines]
                message = "\n".join(message)
            parsed_data["warnings"].append(message)

        time_line = time_re.match(line)

        # Save information about time usage
        if time_line:
            time_name = time_line.group(1).lower() + "_time"
            parsed_data[time_name] = float(time_line.group(2))
            continue

        para_line = parallel_re.match(line)

        if para_line:
            parsed_data["parallel_efficiency"] = int(para_line.group(1))

    #### END OF LINE BY LINE PARSING ITERATION ####

    # remove unrelated units
    units_to_delete = []
    for key in parsed_data:
        if "unit_" in key:
            unit_for = key.split("_", 1)[1]
            delete = True
            # Check the thing this unit refers do exists
            for i in trajectory_data:
                if i == key:
                    continue
                if unit_for in i:
                    delete = False

            for i in parsed_data:
                if i == key:
                    continue
                if unit_for in i:
                    delete = False

            if delete is True:
                units_to_delete.append(key)

    for key in units_to_delete:
        parsed_data.pop(key)

    # set geom convergence state
    if GEOM_FAILURE_MESSAGE in parsed_data["warnings"]:
        parsed_data["geom_unconverged"] = True
    else:
        parsed_data["geom_unconverged"] = None

    return parsed_data, trajectory_data, critical_warnings.values()


class LineParser(object):
    """
    Parser for a line
    """

    def __init__(self, conditions):
        """initialize the Parser by passing the conditions"""
        self._cond = conditions

    def parse(self, line):
        """
        Return parsing results

        :returns: Result of the first matched Matcher object or None if no match is found
        """
        out = None
        for c in self._cond:
            out, match = c.match_pattern(line)
            if out:
                break
        return out


class Matcher(object):
    """
    Class of the condition to match the line
    """

    def __init__(self, regex, name, convfunc=None):
        """
        Initialize a Matcher object.

        :param string regex: Pattern to be matched
        :param string name: Name of the results
        """
        self.regex = re.compile(regex)
        self.convfunc = convfunc
        self.name = name


    def match_pattern(self, line):
        """
        Match pattern

        :returns: (out, match) Out is a dicationary of {self.name: <matched_value>}.
          and match is a re.MatchObject or None
        """

        match =  self.regex.match(line)
        if match:
            value = match.group(1)
            if self.convfunc:
                value = self.convfunc(value)
            out = (self.name, value)
        else:
            out = None
        return out, match

class UnitMatcher(Matcher):
    """
    The pattern of a UnitMatcher should have two groups with second group
    being the unit. The first group will be converted to float
    """

    def match_pattern(self, line):
        """
        Match the pattern
        """
        out, match = super(UnitMatcher, self).match_pattern(line)
        if out:
            unit = match.group(2)
            conv = self.convfunc if self.convfunc else float
            out = (out[0],conv(out[1]), unit)
        return out, match

def get_iter_parser():
    """
    Generate a LineParser object to parse repeating outputs
    """
    tail1 = r' *= *([0-9.+-eE]+) +(\w+)'
    mfree = UnitMatcher(r'^Final free energy \(E-TS\)' + tail1, "free_energy")
    mtotal = UnitMatcher(r'^Final energy, E' + tail1, "total_energy")
    mtotal2 = UnitMatcher(r'^Final energy' + tail1, "total_energy")
    mzeroK = UnitMatcher(r'^NB est. 0K energy \(E-0.5TS\)' + tail1, "zero_K_energy")
    spin = UnitMatcher(r'^Integrated Spin Density' + tail1, "spin_density")
    absspin = UnitMatcher(r'^Integrated \|Spin Density\|' + tail1, "abs_spin_density")
    enthalpy = UnitMatcher(r'^ *\w+: finished iteration +\d+ +with enthalpy' + tail1, "enthalpy")
    parser = LineParser([mfree, mtotal, mtotal2, mzeroK, spin, absspin, enthalpy])
    return parser

def parse_geom_text_output(out_lines, input_dict):
    """
    Parse output of .geom file

    :param out_lines: a list of lines from the readline function.
    :param dict input_dict: not in use at the moment.

    :return: key, value of the trajectories of cell, atoms, force etc
    """
    txt = out_lines
    Hartree = units['Eh'] # eV
    Bohr = units['a0'] # A
    kB = units['kB'] # eV/K
    hBar = units['hbar'] # in eV
    eV = units["e"]  # in J


    cell_list = []
    species_list = []
    geom_list = []
    forces_list = []
    energy_list = []
    hamilt_list = []
    kinetic_list = []
    pressure_list = []
    temperature_list = []
    velocity_list = []
    time_list = []

    # For a specific image
    current_pos = []
    current_species = []
    current_forces = []
    current_velocity = []
    current_cell = []
    in_header = False
    for i, line in enumerate(txt):
        if "begin header" in line.lower():
            in_header = True
            continue
        if "end header" in line.lower():
            in_header = False
            continue
        if in_header:
            continue  # Skip header lines

        sline = line.split()
        if len(sline) == 1:
            try:
                time_list.append(float(sline[0]))
            except ValueError:
                continue
        elif '<-- E' in line:
            energy_list.append(float(sline[0])) # Total energy
            hamilt_list.append(float(sline[1])) # Hamitonian (MD)
            # Kinetic energy is not blank in GEOM OPT runs
            if len(sline) == 5:
                kinetic_list.append(float(sline[2])) # Kinetic (MD)
            continue
        elif '<-- h' in line:
            current_cell.append(list(map(float, sline[:3])))
            continue
        elif '<-- R' in line:
            current_pos.append(list(map(float, sline[2:5])))
            current_species.append(sline[0])
        elif '<-- F' in line:
            current_forces.append(list(map(float, sline[2:5])))
        elif '<-- V' in line:
            current_velocity.append(list(map(float, sline[2:5])))
        elif '<-- T' in line:
            temperature_list.append(float(sline[0]))
        elif '<-- P' in line:
            pressure_list.append(float(sline[0]))
        elif not line.strip() and current_cell:
            cell_list.append(current_cell)
            species_list.append(current_species)
            geom_list.append(current_pos)
            forces_list.append(current_forces)
            current_cell = []
            current_species = []
            current_pos = []
            current_forces = []
            if current_velocity:
                velocity_list.append(current_velocity)
                current_velocity = []

    if len(species_list) == 0:
        raise CASTEPOutputParsingError("No data found in geom file")

    out =  dict(cells=np.array(cell_list) * Bohr,
                positions=np.array(geom_list) * Bohr,
                forces=np.array(forces_list) * Hartree / Bohr,
                geom_total_energy=np.array(energy_list) * Hartree,
                symbols=species_list[0],
                )

    # optional lists
    unit_V = Hartree * Bohr / hBar
    unit_K = Hartree / kB  # temperature in K
    unit_P = Hartree / (Bohr * 1e-10) ** 3 * eV
    unit_s = hBar / Hartree
    opt = {"velocities": (velocity_list, unit_V),
           "temperatures": (temperature_list, unit_K),
           "pressures": (pressure_list, unit_P),
           "hamilt_energy": (hamilt_list, Hartree),
           "times": (time_list, unit_s),
           "kinetic_energy": (kinetic_list, Hartree)
           }
    for key, value in opt.items():
        if value[0]:
            out.update({key: np.array(value[0]) * value[1]})
    return out


force_match = re.compile(
    "^ +\* +(\w+) +([0-9]+) +([0-9.\-+]+) +([0-9.\-+]+) +([0-9.\-+]+) +\*")
stress_match = re.compile(
    "^ +\* +(\w+) +([0-9.\-+]+) +([0-9.\-+]+) +([0-9.\-+]+) +\*")


def parse_force_box(lines):
    """
    Parse a box of the forces
    :param lines: a list of upcoming lines

    :return: A list of number of lines read and the forces
    """

    forces = []
    for i, line in enumerate(lines):

        if "Forces" in line:
            continue

        if "***********************" in line:
            break

        match = force_match.match(line)
        if match:
            forces.append([float(match.group(i)) for i in range(3, 6)])

    return i, forces


def parse_stress_box(lines):
    """
    Parse a box of the stress
    :param lines: a list of upcoming lines

    :return: a list of  [number of lines read, stress_tensor, pressure]
    """

    stress = []
    pressure = None
    for i, line in enumerate(lines):
        if "Stress" in line:
            continue

        if "Cartisian components" in line:
            unit = line.strip().split()[-2]
            unit = unit[1:-2]
            continue

        if "**********************" in line:
            break

        match = stress_match.match(line)
        if  match:
            stress.append([float(match.group(i)) for i in range(2, 5)])
        elif "Pressure" in line:
            lsplit = line.strip().split()
            pressure = float(lsplit[-2])

    return i, stress, pressure


def parse_dot_bands(file_path):
    """
    Parse an CASTEP bands file
    Extract Kpoints and each bands for each kpoints.
    This is a generic parsing function. Return python builtin types.

    :param str file_path: Path of the file to parse
    :return: A list of bands_info, kpoints and bands:

     * bands_info: A dictionary for information of bands.

     * kpoints: A list of kpoints. In the format [kpoint index, coordinats x 3 kpoint weight]

     * bands: A list of bands. Each band has a list of actual
       eigenvalues for each spin components. E.g nkpoints, nspins, neigns.

    Note that the atomic units are used in the bands file
    """
    fh = open(file_path)

    i_finish = None
    cell = []
    bands_info = {}
    for i, line in enumerate(fh):
        if not line.strip():
            continue
        if "Number of k-points" in line:
            nkps = line.strip().split()[-1]
            bands_info['nkpts'] = int(float(nkps))
            continue
        if "Number of spin components" in line:
            nspin = line.strip().split()[-1]
            bands_info['nspins'] = int(float(nspin))
            continue
        if "Number of electrons" in line:
            nelec = line.strip().split()[-1]
            bands_info['nelecs'] = float(nelec)
            continue
        if "Number of eigenvalues" in line:
            neigns = line.strip().split()[-1]
            bands_info['neigns'] = int(float(neigns))
            continue
        if "Fermi energ" in line:  # TODO support for spin polarisation
            efermi = line.strip().split()[-1]
            bands_info['efermi'] = float(efermi)
            continue
        if "Unit cell" in line:
            i_finish = i + 3
            continue

        # Added the cell
        if i_finish:
            cell.append([float(n) for n in line.strip().split()])
        if i == i_finish:
            break
    bands_info['cell'] = cell

    # Now parser the body
    kpoints = []
    bands = []
    this_band = []
    this_spin = []
    for line in fh:
        if "K-point" in line:
            # We are not at the first kpoints
            if kpoints:
                # Save the result from previous block
                this_band.append(this_spin)
                bands.append(this_band)
                this_spin = []
                this_band = []
            kline = line.strip().split()
            kpoints.append([float(n) for n in kline[1:]])
            continue
        if "Spin component" in line:
            # Check if we are at the second spin
            if this_spin:
                this_band.append(this_spin)
                this_spin = []
            continue

        ls = line.strip()
        if not ls:
            continue
        this_spin.append(float(ls))

    fh.close()

    # Save the last set of results
    this_band.append(this_spin)
    bands.append(this_band)

    # Do some sanity checks
    assert int(nkps) == len(kpoints), "Missing kpoints"
    assert len(bands) == len(kpoints), "Missing bands for certain kpoints"

    for n, b in enumerate(bands):
        assert len(b) == int(
            nspin), "Missing spins for kpoint {}".format(n + 1)
        for i, s in enumerate(b):
            assert len(s) == int(neigns), ("Missing eigenvalues "
                                           "for kpoint {} spin {}".format(n + 1, i + 1))

    return bands_info, kpoints, bands

"""
Utility module
"""
from __future__ import absolute_import
from collections import Counter
from aiida.common import InputValidationError


def get_castep_ion_line(name,
                        pos,
                        label=None,
                        spin=None,
                        occupation=None,
                        mix_num=None):
    """
    Generate a line in POSITIONS_ABS or POSITIONS_FRAC block

    :param name: A sting or tuple of the names
    :param pos: Position, a sequence of 3
    :param label: A string or tuple of the labels
    :param spin: Spins. (spin), (spin1, spin2), (x, y, z) or ((x1,y1,z1), (x2, y2, z2))
    :param occupation: tuple of two of the occupation number
    :param mix_num: mixture number, can be any integer but should not be repeated in a single cell file

    :return line: a string of the line to be added to the cell file
    """

    # Check if we are dealing with mixtures
    if isinstance(name, (tuple, list)):

        lines = [
            "{n:18} {x:18.10f} {y:18.10f} {z:18.10f}".format(n=n,
                                                             x=pos[0],
                                                             y=pos[1],
                                                             z=pos[2])
            for n in name
        ]

        assert sum(occupation) == 1, "Occupation need to sum up to 1"
        lines = [
            lines[i] + " MIXTURE= ({} {})".format(mix_num, occupation[i])
            for i in range(2)
        ]

        if label is not None:
            if not isinstance(label, (list, tuple)):
                label = [label, label]

            lines = [
                line + " LABEL={} ".format(l) for line, l in zip(lines, label)
            ]

        # Handle spin
        # spin might be (s1, s2) or (s1) or ((s11, s12, s12), (s21, s22, s23))
        if not isinstance(spin, (list, tuple)):
            spin = [spin, spin]
        elif len(spin) == 3:
            # Passed a 3D spin for both atoms
            spin = [spin, spin]

        if isinstance(spin[0], (list, tuple)):
            lines = [
                l + " SPIN=( {:.2f} {.2f} {.2f} )".format(*s)
                for l, s in zip(lines, spin)
            ]
        else:
            if None not in spin:
                lines = [l + " SPIN={}".format(s) for l, s in zip(lines, spin)]

        return "\n".join(lines)

    line = "{name:18} {x:18.10f} {y:18.10f} {z:18.10f}".format(name=name,
                                                               x=pos[0],
                                                               y=pos[1],
                                                               z=pos[2])

    if spin is not None:

        if isinstance(spin, (list, tuple)):
            line += " SPIN=({}, {}, {}) ".format(*spin)
        else:
            line += " SPIN={:.3f} ".format(spin)

    if label is not None:

        line += " LABEL={} ".format(label)

    return line


def _lowercase_dict(in_dict, dict_name):
    """
    Make sure the dictionary's keys are in lower case
    :param dict_name: A string of the name for the dictionary. Only used in
    warning message.
    """

    if isinstance(in_dict, dict):
        new_dict = dict(
            (str(key).lower(), value) for key, value in in_dict.items())
        if len(new_dict) != len(in_dict):
            num_items = Counter(str(key).lower() for key in in_dict.keys())
            double_keys = ",".join(
                [key for key, value in num_items if value > 1])
            raise InputValidationError(
                "Inside the dictionary '{}' there are the following keys that "
                "are repeated more than once when compared case-insensitively: {}."
                "This is not allowed.".format(dict_name, double_keys))
        return new_dict
    raise TypeError("_lowercase_dict accepts only dictionaries as argument")


def _uppercase_dict(in_dict, dict_name):
    """
    Make sure the dictionary's keys are in upper case
    :param dict_name: A string of the name for the dictionary. Only used in
    warning message.
    """
    if isinstance(in_dict, dict):
        new_dict = dict(
            (str(key).upper(), value) for key, value in in_dict.items())
        if len(new_dict) != len(in_dict):
            num_items = Counter(str(key).upper() for key in in_dict.keys())
            double_keys = ",".join(
                [key for key, value in num_items if value > 1])
            raise InputValidationError(
                "Inside the dictionary '{}' there are the following keys that "
                "are repeated more than once when compared case-insensitively: {}."
                "This is not allowed.".format(dict_name, double_keys))
        return new_dict
    raise TypeError("_uppercase_dict accepts only dictionaries as argument")

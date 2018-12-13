"""
Utility module
"""
from aiida.common.exceptions import InputValidationError


def get_castep_ion_line(name,
                        pos,
                        label=None,
                        spin=None,
                        occupation=None,
                        mix_num=None):
    """
    Generate a line in POSITIONS_ABS or POSISTIONS_FRAC block

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
            "{n:18} {x:18.10f} {y:18.10f} {z:18.10f}".format(
                n=n, x=pos[0], y=pos[1], z=pos[2]) for n in name
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

    else:
        line = "{name:18} {x:18.10f} {y:18.10f} {z:18.10f}".format(
            name=name, x=pos[0], y=pos[1], z=pos[2])

        if spin is not None:

            if isinstance(spin, (list, tuple)):
                line += " SPIN=({}, {}, {}) ".format(*spin)
            else:
                line += " SPIN={:.3f} ".format(spin)

        if label is not None:

            line += " LABEL={} ".format(label)

        return line


def _lowercase_dict(d, dict_name):
    """
    Make sure the dictionary's keys are in lower case
    :param dict_name: A string of the name for the dictionary. Only used in
    warning message.
    """
    from collections import Counter

    if isinstance(d, dict):
        new_dict = dict((str(k).lower(), v) for k, v in d.iteritems())
        if len(new_dict) != len(d):
            num_items = Counter(str(k).lower() for k in d.keys())
            double_keys = ",".join([k for k, v in num_items if v > 1])
            raise InputValidationError(
                "Inside the dictionary '{}' there are the following keys that "
                "are repeated more than once when compared case-insensitively: {}."
                "This is not allowed.".format(dict_name, double_keys))
        return new_dict
    else:
        raise TypeError(
            "_lowercase_dict accepts only dictionaries as argument")


def _uppercase_dict(d, dict_name):
    """
    Make sure the dictionary's keys are in upper case
    :param dict_name: A string of the name for the dictionary. Only used in
    warning message.
    """
    from collections import Counter

    if isinstance(d, dict):
        new_dict = dict((str(k).upper(), v) for k, v in d.iteritems())
        if len(new_dict) != len(d):
            num_items = Counter(str(k).upper() for k in d.keys())
            double_keys = ",".join([k for k, v in num_items if v > 1])
            raise InputValidationError(
                "Inside the dictionary '{}' there are the following keys that "
                "are repeated more than once when compared case-insensitively: {}."
                "This is not allowed.".format(dict_name, double_keys))
        return new_dict
    else:
        raise TypeError(
            "_uppercase_dict accepts only dictionaries as argument")

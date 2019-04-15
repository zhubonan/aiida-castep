"""Test module for the matchers"""
from __future__ import absolute_import
import pytest
from .raw_parser import Matcher, UnitMatcher, LineParser


def test_matcher():
    """
    Test the Marcher class
    """
    m = Matcher(r"^ +Energy is (\d+)", "energy")
    assert m.match_pattern(" Energy is 1234")[0] == ("energy", "1234")
    m = Matcher(r"^ +Energy is (\d+)", "energy", int)
    assert m.match_pattern(" Energy is 1234")[0] == ("energy", 1234)


def test_unit_matcher():
    """
    Test the UnitMatcher
    """
    m = UnitMatcher(r"^ +Energy is (\d+) +(\w+)", "energy")
    assert m.match_pattern(" Energy is 1234 eV")[0] == ("energy", float(1234),
                                                        "eV")
    m = UnitMatcher(r"^ +Energy is (\d+) +(\w+)", "energy", int)
    assert isinstance(m.match_pattern(" Energy is 1234 eV")[0][1], int)


def test_line_parser():
    """i
    Test the line parser object
    """
    m1 = UnitMatcher(r"^ +Free Energy is (\d+) +(\w+)", "free_energy")
    m2 = UnitMatcher(r"^ +Total Energy is (\d+) +(\w+)", "total_energy")
    line_parser = LineParser([m1, m2])
    res = line_parser.parse(" X Energy is 1234 eV ")
    assert res is None
    assert m2.match_pattern(" Total Energy is 1234 eV ")[0] is not None
    res = line_parser.parse(" Total Energy is 1234 eV ")
    assert res == ("total_energy", 1234, "eV")
    res = line_parser.parse(" Free Energy is 1234 Ha ")
    assert res == ("free_energy", 1234, "Ha")


def test_iter_line_parser():
    """
    Test the define line parser 
    """
    from .raw_parser import get_iter_parser

    parser = get_iter_parser()
    assert parser.parse(
        "Integrated |Spin Density|   =    0.682437E-03 hbar/2") is not None
    assert parser.parse(
        "Integrated Spin Density     =    0.202826E-03 hbar/2") is not None
    assert parser.parse(" LBFGS: finished iteration     3 with enthalpy= -2.42401562E+005 eV")[1] == \
        -2.42401562e5
    assert parser.parse(
        "NB est. 0K energy (E-0.5TS)      =  -63379.66505085   eV") is not None
    assert parser.parse(
        "Final energy, E             =  -63379.72119700     eV") is not None
    assert parser.parse(
        "Final free energy (E-TS)    =  -63374.56395158     eV") is not None

"""Test module for the matchers"""
import pytest
from raw_parser import Matcher, UnitMatcher, LineParser


def test_matcher():
    """
    Test the Marcher class
    """
    m = Matcher("^ +Energy is (\d+)", "energy")
    assert m.match_pattern(" Energy is 1234")[0] == {"energy": "1234"}
    m = Matcher("^ +Energy is (\d+)", "energy", int)
    assert m.match_pattern(" Energy is 1234")[0] == {"energy": 1234}


def test_unit_matcher():
    """
    Test the UnitMatcher
    """
    m = UnitMatcher("^ +Energy is (\d+) +(\w+)", "energy")
    assert m.match_pattern(" Energy is 1234 eV")[0] == {"energy": float(1234), "unit": "eV"}
    m = UnitMatcher("^ +Energy is (\d+) +(\w+)", "energy", int)
    assert isinstance(m.match_pattern(" Energy is 1234 eV")[0]["energy"], int)


def test_line_parser():
    """i
    Test the line parser object
    """
    m1 = UnitMatcher("^ +Free Energy is (\d+) +(\w+)", "free_energy")
    m2 = UnitMatcher("^ +Total Energy is (\d+) +(\w+)", "total_energy")
    l = LineParser([m1, m2])
    res = l.parse(" X Energy is 1234 eV ")
    assert res is None
    assert m2.match_pattern(" Total Energy is 1234 eV ")[0] is not None
    res = l.parse(" Total Energy is 1234 eV ")
    assert res == {"total_energy": 1234, "unit": "eV"}
    res = l.parse(" Free Energy is 1234 Ha ")
    assert res == {"free_energy": 1234, "unit": "Ha"}

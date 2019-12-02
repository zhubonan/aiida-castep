"""
Tests for data module
"""
from __future__ import absolute_import
from aiida_castep.data.utils import split_otfg_entry, get_usp_element

Ti_otfg = "Ti 3|1.8|9|10|11|30U:40:31:32(qc=5.5)"
Sr_otfg = "Sr 3|2.0|5|6|7|40U:50:41:42"
O_otfg = "O 2|1.1|15|18|20|20:21(qc=7)"
raw_otfg = "2|1.1|15|18|20|20:21(qc=7)"
otfglibs = ["QC5", "NCP17", "C9"]


def test_otfg_split():
    element, setting = split_otfg_entry(Ti_otfg)
    assert element == "Ti"
    assert setting == "3|1.8|9|10|11|30U:40:31:32(qc=5.5)"

    O, O_entry = split_otfg_entry(O_otfg)
    elem, O_entry2 = split_otfg_entry(raw_otfg)
    assert elem is None
    assert O_entry2 == O_entry

    for otfglib in otfglibs:
        elem, entry = split_otfg_entry(otfglib)
        assert entry == otfglib
        assert elem == "LIBRARY"


def test_usp_element():
    """Test the element is currectly parsed from a file path"""

    fpath = "/tmp/Sr_00.usp"
    elem = get_usp_element(fpath)
    assert elem == "Sr"

    fpath = "/tmp/sr_00.usp"
    elem = get_usp_element(fpath)
    assert elem == "Sr"

    elem = get_usp_element('/tmp/Sr_00.upf')
    assert elem is None

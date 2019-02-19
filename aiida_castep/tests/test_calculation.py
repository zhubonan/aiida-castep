"""
Tests for calculation module
"""
import pytest


def test_castep_summary(STO_calculation):
    # Test the get_castep_input_summary method

    keys = ["kpoints", "structure", "code", "computer", "resources",
            "custom_scheduler_commands", "wallclock", "label", "pseudos"]
    out_dict = STO_calculation.get_castep_input_summary()
    for k in keys:
        assert k in out_dict

    # Store the node, this should not change anything
    STO_calculation.store_all()
    out_dict = STO_calculation.get_castep_input_summary()
    for k in keys:
        assert k in out_dict

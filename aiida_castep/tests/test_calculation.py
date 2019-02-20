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


def test_castep_update(STO_calculation):

    updates = {"task": "geometryoptimisation",
               "xc_functional": "pbe",
               "fix_all_cell": True}
    STO_calculation.update_parameters(**updates)
    dtmp = STO_calculation.inp.parameters.get_dict()
    assert dtmp["PARAM"]["task"] == updates["task"]
    assert dtmp["PARAM"]["xc_functional"] == updates["xc_functional"]
    assert dtmp["CELL"]["fix_all_cell"] == updates["fix_all_cell"]

    STO_calculation.update_parameters(delete=["task"])
    assert "task" not in dtmp["PARAM"]

    STO_calculation.inp.parameters.store()
    with pytest.raises(RuntimeError):
        STO_calculation.update_parameters(delete=["task"])

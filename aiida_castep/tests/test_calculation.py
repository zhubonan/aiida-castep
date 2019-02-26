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


def test_update_parameters(STO_calculation):
    """
    Test the update_parameters method
    """

    sto = STO_calculation
    updates = {"task": "geometryoptimisation",
               "xc_functional": "pbe",
               "fix_all_cell": True}
    sto.update_parameters(**updates)
    dtmp = sto.inp.parameters.get_dict()
    assert dtmp["PARAM"]["task"] == updates["task"]
    assert dtmp["PARAM"]["xc_functional"] == updates["xc_functional"]
    assert dtmp["CELL"]["fix_all_cell"] == updates["fix_all_cell"]

    sto.update_parameters(delete=["task"])
    assert "task" not in dtmp["PARAM"]

    sto.inp.parameters.store()
    with pytest.raises(RuntimeError):
        sto.update_parameters(delete=["task"])

    # Unlink the parameters
    sto._remove_link_from(sto.get_linkname("parameters"))
    # This should still work, a new input ParameterData is created
    sto.update_parameters(**updates)
    assert sto.get_linkname("parameters") in \
        sto.get_inputs_dict()

"""
Tests for calculation module
"""
from __future__ import absolute_import
import pytest


@pytest.fixture
def calcjobnode(sto_calc_inputs, generate_calc_job_node):
    """Create a fake calcjob node"""
    calcjobnode = generate_calc_job_node(
        'castep.castep', 'H2-geom', inputs=sto_calc_inputs)

    return calcjobnode


def test_castep_summary_builder(sto_calc_inputs):
    # Test the get_castep_input_summary method
    from aiida_castep.calculations.tools import castep_input_summary
    from aiida_castep.calculations.castep import CastepCalculation

    builder = CastepCalculation.get_builder()
    builder._data = sto_calc_inputs

    keys = [
        "kpoints", "structure", "code", "computer", "resources",
        "custom_scheduler_commands", "wallclock", "label", "pseudos"
    ]
    out_dict = castep_input_summary(builder)
    for k in keys:
        assert k in out_dict


@pytest.mark.skip('Fixuture missing')
def test_castep_summary_calcjob(calcjobnode):
    """Test the summary method works for CalcJobNode"""
    from aiida_castep.calculations.tools import castep_input_summary
    out_dict = castep_input_summary(calcjobnode)

    keys = [
        "kpoints", "structure", "code", "computer", "resources",
        "custom_scheduler_commands", "wallclock", "label", "pseudos"
    ]
    for k in keys:
        assert k in out_dict


@pytest.mark.skip('interace not implemented')
def test_update_parameters(STO_calculation):
    """
    Test the update_parameters method
    """

    sto = STO_calculation
    updates = {
        "task": "geometryoptimisation",
        "xc_functional": "pbe",
        "fix_all_cell": True
    }
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
    # This should still work, a new input Dict is created
    sto.update_parameters(**updates)
    assert sto.get_linkname("parameters") in \
        sto.get_inputs_dict()

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


def test_castep_summary_builder(sto_calc_inps_or_builder):
    # Test the get_castep_input_summary method
    from aiida_castep.calculations.tools import castep_input_summary

    keys = [
        "kpoints", "structure", "code", "computer", "resources",
        "custom_scheduler_commands", "wallclock", "label", "pseudos"
    ]
    out_dict = castep_input_summary(sto_calc_inps_or_builder)
    for k in keys:
        assert k in out_dict


def test_castep_summary_calcjob(sto_calc_inputs, generate_calc_job_node):
    """Test the summary method works for CalcJobNode"""
    from aiida_castep.calculations.tools import castep_input_summary
    from tempfile import mkdtemp
    calcjobnode = generate_calc_job_node(
        entry_point_name='castep.castep',
        results_folder=mkdtemp(),
        inputs=sto_calc_inputs)
    out_dict = castep_input_summary(calcjobnode)

    keys = [
        "kpoints", "structure", "code", "computer", "resources",
        "custom_scheduler_commands", "wallclock", "label", "pseudos"
    ]
    for k in keys:
        assert k in out_dict


def test_param_update(sto_calc_inps_or_builder):
    """Test the param update function, it should work for both
    inputs dictionary and builders"""
    from aiida_castep.calculations.tools import update_parameters
    from aiida_castep.common import INPUT_LINKNAMES

    inputs = sto_calc_inps_or_builder
    out = update_parameters(inputs, xc_functional='scan')

    assert out is inputs
    assert inputs[INPUT_LINKNAMES['parameters']].get_dict(
    )['PARAM']['xc_functional'] == 'scan'

    # Test deletion
    out = update_parameters(inputs, delete=['xc_functional'])
    assert 'xc_functional' not in inputs[
        INPUT_LINKNAMES['parameters']].get_dict()['PARAM']

    # Test assestion of stored node
    inputs[INPUT_LINKNAMES['parameters']].store()
    with pytest.raises(RuntimeError):
        out = update_parameters(inputs, xc_functional='scan')

"""
Tests for calculation module
"""
from __future__ import absolute_import
import pytest
from aiida_castep.common import INPUT_LINKNAMES, OUTPUT_LINKNAMES


@pytest.fixture
def calcjobnode(h2_calc_inputs, generate_calc_job_node):
    """Create a fake calcjob node"""
    inp_structure = h2_calc_inputs[INPUT_LINKNAMES['structure']]
    calcjobnode = generate_calc_job_node(
        'castep.castep',
        'H2-geom',
        inputs=h2_calc_inputs,
        outputs={OUTPUT_LINKNAMES['structure']: inp_structure.clone()})

    return calcjobnode


def test_use_pseudos(sto_calc_inps_or_builder, create_otfg_group):
    """Test the `use_psudos_from_family` function"""
    from aiida_castep.calculations.tools import use_pseudos_from_family
    create_otfg_group(['QC5'], 'QC5')
    use_pseudos_from_family(sto_calc_inps_or_builder, 'QC5')
    assert all([
        pseudo.entry == 'QC5'
        for pseudo in sto_calc_inps_or_builder['pseudos'].values()
    ])


def test_castep_summary_builder(sto_calc_inps_or_builder):
    """Test the get_castep_input_summary method"""
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
    calcjobnode = generate_calc_job_node(entry_point_name='castep.castep',
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


def test_create_restart_builder(sto_calc_inputs):
    """Test creating restart from a builder"""
    from aiida_castep.calculations.tools import create_restart
    new_builder = create_restart(sto_calc_inputs, entry_point='castep.castep')

    new_builder = create_restart(sto_calc_inputs,
                                 entry_point='castep.castep',
                                 param_update={'fix_all_cell': True})
    assert new_builder.parameters.get_dict()['CELL']['fix_all_cell'] is True

    # Test deletion
    new_builder = create_restart(new_builder, param_delete=['fix_all_cell'])
    assert 'fix_all_cell' not in new_builder.parameters.get_dict()['CELL']


def test_create_restart_node(calcjobnode):
    """Test creating a restart from a CalcJobNode"""

    with pytest.raises(RuntimeError):
        new_builder = calcjobnode.tools.create_restart(
            False, param_update={'fix_all_cell': True})

    new_builder = calcjobnode.tools.create_restart(
        True, param_update={'fix_all_cell': True})
    assert new_builder.parameters.get_dict()['CELL']['fix_all_cell'] is True

    new_builder = calcjobnode.tools.create_restart(True,
                                                   use_output_structure=True)
    assert new_builder[
        INPUT_LINKNAMES['structure']].uuid == calcjobnode.outputs.__getattr__(
            OUTPUT_LINKNAMES['structure']).uuid

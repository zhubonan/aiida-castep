"""
Test input generation
"""
from __future__ import absolute_import
import pytest
from aiida_castep.calculations.inpgen import CastepInputGenerator
from aiida.engine.processes.ports import PortNamespace


@pytest.fixture
def gen_instance():
    """
    Create a mock generator intstance
    """
    gen = CastepInputGenerator()
    gen.inputs = PortNamespace
    gen.inputs.metadate = PortNamespace
    gen.inputs.metadate.options = PortNamespace
    return gen


@pytest.fixture
def param_dict():
    """Example dict in Dict"""

    out = {
        "PARAM": {
            "task": "singlepoints",
            "xc_functional": "lda"
        },
        "CELL": {
            "fix_all_cell": True,
            "cell_constraints": ["1 1 1", "2 2 3"]
        }
    }
    return out


def test_inp_gen_param(gen_instance, param_dict):
    """
    Test generate paramters
    """
    gen_instance.param_dict = param_dict
    gen_instance._prepare_param_file()
    assert gen_instance.param_file == param_dict["PARAM"]


def test_inp_gen_cell(gen_instance, sto_calc_inputs):
    """
    Test generation of the inputs
    """
    gen_instance.inputs = sto_calc_inputs
    gen_instance.prepare_inputs()
    assert 'symmetry_generate' in gen_instance.cell_file
    assert "POSITIONS_ABS" in gen_instance.cell_file
    assert "LATTICE_CART" in gen_instance.cell_file
    assert isinstance(gen_instance.cell_file["cell_constraints"], list)
    assert 'C9' in gen_instance.cell_file['SPECIES_POT'][0]


@pytest.mark.process_execution
def test_submission(new_database, sto_calc_inputs):
    """
    Test submitting a CastepCalculation
    """
    from aiida_castep.calculations.castep import CastepCalculation
    from aiida.engine import run_get_node
    _, return_node = run_get_node(CastepCalculation, **sto_calc_inputs)
    assert return_node.exit_status == 101


def test_submit_test(new_database, sto_calc_inputs):
    """
    Test the ``submit_test`` method
    """
    from aiida_castep.calculations.castep import CastepCalculation
    res = CastepCalculation.submit_test(**sto_calc_inputs)
    fcontent = res[1].get_content_list()
    assert 'aiida.cell' in fcontent
    assert 'aiida.param' in fcontent


def test_submit_test_function(new_database, sto_calc_inputs):
    """
    Test the ``submit_test`` method
    """
    from aiida_castep.calculations.castep import CastepCalculation, submit_test

    # Test with process class and inputs
    res = submit_test(CastepCalculation, inputs=sto_calc_inputs)
    fcontent = res[1].get_content_list()
    assert 'aiida.cell' in fcontent
    assert 'aiida.param' in fcontent
    # Nothing should change for the nested dic
    assert sto_calc_inputs['metadata'].get('dry_run') is not True
    assert sto_calc_inputs['metadata'].get('store_provenance') is not False

    # Test with builder
    builder = CastepCalculation.get_builder()
    builder._data = sto_calc_inputs
    res = submit_test(builder)
    fcontent = res[1].get_content_list()
    assert 'aiida.cell' in fcontent
    assert 'aiida.param' in fcontent

    # Nothing should change in the process builder
    assert builder.metadata.get('dry_run') is not True
    assert builder.metadata.get('store_provenance') is not False


def run_castep_calc(inputs):
    from aiida_castep.calculations.castep import CastepCalculation
    from aiida.engine import run_get_node
    return run_get_node(CastepCalculation, **inputs)[1]


def test_dict2builder(aiida_profile, sto_calc_inputs):
    """Test that we can use nested dict input for builder"""
    from aiida_castep.calculations.castep import CastepCalculation
    builder = CastepCalculation.get_builder()
    builder._data = sto_calc_inputs
    from aiida.engine import run_get_node
    run_get_node(builder)
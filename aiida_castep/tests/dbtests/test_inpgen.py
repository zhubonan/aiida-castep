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


def run_castep_calc(inputs):
    from aiida_castep.calculations.castep import CastepCalculation
    from aiida.engine import run_get_node
    return run_get_node(CastepCalculation, **inputs)[1]


@pytest.mark.process_execution
def test_parsing_base(
        new_database,
        db_test_app,
        generate_calc_job_node,
        generate_parser,
        h2_calc_inputs,
):
    """
    Test submitting a CastepCalculation
    """

    node = generate_calc_job_node(
        'castep.castep',
        'H2-geom',
        inputs=h2_calc_inputs,
    )
    parser = generate_parser('castep.castep')
    results, return_node = parser.parse_from_node(node, store_provenance=False)
    assert return_node.exit_status == 0

    calc_energy = results['output_parameters'].get_dict()['total_energy']
    ref = -31.69654969917
    assert calc_energy == ref


@pytest.mark.process_execution
def test_parsing_geom(new_database, db_test_app, generate_calc_job_node,
                      generate_parser, h2_calc_inputs):
    """
    Test if the geom is parsed correctly
    """
    from aiida_castep.calculations.castep import CastepCalculation
    node = generate_calc_job_node(
        'castep.castep',
        'H2-geom',
        inputs=h2_calc_inputs,
        computer=db_test_app.localhost)
    parser = generate_parser('castep.castep')
    results, _ = parser.parse_from_node(node, store_provenance=False)
    assert 'forces' in results['output_trajectory'].get_arraynames()


@pytest.mark.skip("Not working on aiida side")
def test_get_builder(aiida_profile, sto_calc_inputs):

    from aiida_castep.calculations.castep import CastepCalculation
    buider = CastepCalculation.get_builder()

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


@pytest.mark.parametrize('entry_point', ('castep.castep', 'castep.ts'))
def test_get_builder(db_test_app, entry_point):
    from aiida.plugins import CalculationFactory
    cls = CalculationFactory(entry_point)
    builder = cls.get_builder()


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

    # Test extra-kpoints
    from aiida.orm import KpointsData
    kpn1 = KpointsData()
    kpn1.set_kpoints_mesh((4, 4, 4))
    gen_instance._include_extra_kpoints(kpn1, 'phonon', {
        'task': ('phonon', ),
        'need_weights': False
    })
    assert 'phonon_kpoint_mp_grid' in gen_instance.cell_file

    kpn1.set_kpoints_mesh((
        4,
        4,
        4,
    ), (0.25, 0.25, 0.25))
    gen_instance._include_extra_kpoints(kpn1, 'phonon', {
        'task': ('phonon', ),
        'need_weights': False
    })
    assert 'phonon_kpoint_mp_offset' in gen_instance.cell_file

    kpn2 = KpointsData()
    kpn_points = [[0, 0, 0], [0.5, 0.5, 0.5]]
    kpn_weights = [0.3, 0.6]
    kpn2.set_kpoints(kpn_points, weights=kpn_weights)
    gen_instance._include_extra_kpoints(kpn2, 'bs', {
        'task': ('bandstructure', ),
        'need_weights': True
    })
    assert 'BS_KPOINT_LIST' in gen_instance.cell_file


def test_cell_with_tags(gen_instance, sto_calc_inputs):
    """
    Test that the inputs generator correctly handles the case with
    kind.name != symbol
    """
    from ..utils import get_mixture_cell
    sto_tags = get_mixture_cell()
    sto_calc_inputs.structure = sto_tags
    pseudos = sto_calc_inputs.pseudos
    pseudos['O1'] = pseudos['O']
    pseudos['O2'] = pseudos['O']
    pseudos['SrTi_Sr'] = pseudos['O']
    pseudos['SrTi_Ti'] = pseudos['O']
    gen_instance.inputs = sto_calc_inputs
    gen_instance.prepare_inputs()

    positions = gen_instance.cell_file['POSITIONS_ABS']

    assert 'Sr:SrTi' in positions[0].split('\n')[0]
    assert 'Ti:SrTi' in positions[0].split('\n')[1]

    # Check the currect type are there
    species_pots = [
        tuple(line.split()) for line in gen_instance.cell_file['SPECIES_POT']
    ]
    assert ('Sr:SrTi', 'C9') in species_pots
    assert ('O:O1', 'C9') in species_pots
    assert ('O:O2', 'C9') in species_pots


@pytest.mark.process_execution
def test_submission(new_database, sto_calc_inputs, sto_spectral_inputs):
    """
    Test submitting a CastepCalculation
    """
    from aiida_castep.calculations.castep import CastepCalculation
    from aiida.engine import run_get_node
    _, return_node = run_get_node(CastepCalculation, **sto_calc_inputs)
    assert return_node.exit_status == 106  # No castep output found

    # test with extra kpoints
    _, return_node = run_get_node(CastepCalculation, **sto_spectral_inputs)
    assert return_node.exit_status == 106


def test_submit_test(new_database, sto_calc_inputs):
    """
    Test the ``submit_test`` method
    """
    from aiida_castep.calculations.castep import CastepCalculation
    from aiida.common.folders import Folder
    builder = CastepCalculation.get_builder()
    builder._update(sto_calc_inputs)
    res = CastepCalculation.submit_test(builder)
    fcontent = Folder(res[1]).get_content_list()
    assert 'aiida.cell' in fcontent
    assert 'aiida.param' in fcontent


def test_submit_test_function(new_database, sto_calc_inputs):
    """
    Test the ``submit_test`` method
    """
    from aiida_castep.calculations.castep import CastepCalculation, submit_test
    from aiida.common.folders import Folder

    # Test with process class and inputs
    res = submit_test(CastepCalculation, **sto_calc_inputs)
    fcontent = Folder(res[1]).get_content_list()
    assert 'aiida.cell' in fcontent
    assert 'aiida.param' in fcontent
    # Nothing should change for the nested dic
    assert sto_calc_inputs['metadata'].get('dry_run') is not True
    assert sto_calc_inputs['metadata'].get('store_provenance') is not False

    # Test with builder
    builder = CastepCalculation.get_builder()
    builder._data = sto_calc_inputs
    res = submit_test(builder)
    fcontent = Folder(res[1]).get_content_list()
    assert 'aiida.cell' in fcontent
    assert 'aiida.param' in fcontent

    # Nothing should change in the process builder
    assert builder.metadata.get('dry_run') is not True
    assert builder.metadata.get('store_provenance') is not False


def test_param_validation(db_test_app):
    """Test input validations"""
    from aiida_castep.calculations.castep import CastepCalculation

    builder = CastepCalculation.get_builder()
    # This shold work
    builder.parameters = {'PARAM': {'cut_off_energy': 100}}

    with pytest.raises(ValueError):
        # Flat style is not allowed
        builder.parameters = {'foo': 'bar'}

    with pytest.raises(ValueError):
        # Erorr will be catached
        builder.parameters = {'PARAM': {'cut_off_eneryg': 100}}


def run_castep_calc(inputs):
    from aiida_castep.calculations.castep import CastepCalculation
    from aiida.engine import run_get_node
    return run_get_node(CastepCalculation, **inputs)[1]


def test_dict2builder(aiida_profile, sto_calc_inputs):
    """Test that we can use nested dict input for builder"""
    from aiida_castep.calculations.castep import CastepCalculation
    from aiida.engine import run_get_node
    builder = CastepCalculation.get_builder()
    builder._update(sto_calc_inputs)
    run_get_node(builder)

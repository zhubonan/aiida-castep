"""
Test setting up and running calculations based on mock CASTEP
"""
from subprocess import check_output
import pytest
import numpy as np
import aiida.orm as orm
from aiida.engine import run_get_node

from aiida.plugins import CalculationFactory
from aiida_castep.data.otfg import OTFGData


@pytest.fixture
def silicon_builder(db_test_app):
    """Prepare a mock - ready calculation for silicon"""
    silicon = orm.StructureData()
    r_unit = 2.6954645
    silicon.set_cell(np.array([[1, 1, 0], [1, 0, 1], [0, 1, 1]]) * r_unit)
    silicon.append_atom(symbols=["Si"], position=[0, 0, 0])
    silicon.append_atom(symbols=["Si"], position=[r_unit * 0.5] * 3)
    silicon.label = "Si"
    silicon.description = "A silicon structure"
    param_dict = {
        # Notice that the keywords are group into two sub-dictionaries
        # just like you would do when preparing the inputs by hand
        "CELL": {
            "symmetry_generate": True,
            "snap_to_symmetry": True,
            # Pass a list of string to set a BLOCK inputs
            #"cell_constraints":
            #["0 0 0", "0 0 0"]
        },
        "PARAM": {
            "task": "singlepoint",
            "basis_precision": "medium",
            "fix_occupancy":
            True,  # Use bool type to make it easy for querying
            "opt_strategy": "memory",
            "num_dump_cycles": 0,
            "write_formatted_density": True
        }
    }
    # We need to create a Dict node that holds the dictionary
    param = orm.Dict(dict=param_dict)
    kpoints = orm.KpointsData()
    # Use gamma and 0.25, 0.25, 0.25
    kpoints.set_kpoints_mesh((4, 4, 4), offset=(0, 0, 0))
    c9 = OTFGData(otfg_entry="C9")
    CastepCalculation = CalculationFactory('castep.castep')
    code_path = check_output(['which', 'castep.mock'],
                             universal_newlines=True).strip()
    castep_mock = orm.Code((db_test_app.localhost, code_path),
                           input_plugin_name='castep.castep')

    builder = CastepCalculation.get_builder()
    builder.structure = silicon
    builder.parameters = param
    builder.kpoints = kpoints
    builder.code = castep_mock
    builder.pseudos = {'Si': c9}
    builder.metadata.options.withmpi = False
    builder.metadata.options.resources = {
        'num_machines': 1,
        'tot_num_mpiprocs': 2
    }
    builder.metadata.options.max_wallclock_seconds = 600
    builder.metadata.label = "Si SINGLEPOINT"
    builder.metadata.description = 'A Example CASTEP calculation for silicon'
    return builder


def test_mock_silicon(silicon_builder):
    """Test mock silicon calculation"""
    _, calcjob = run_get_node(silicon_builder)
    if calcjob.exit_status != 0:
        print(calcjob.inputs.code.attributes)
        print("STDOUT:")
        print(
            calcjob.outputs.retrieved.base.repository.get_object_content(
                '_scheduler-stdout.txt'))
        print("STDERR:")
        print(
            calcjob.outputs.retrieved.base.repository.get_object_content(
                '_scheduler-stderr.txt'))
        print(calcjob.base.repository.get_object_content('aiida.param'))
        print(calcjob.base.repository.get_object_content('aiida.cell'))
    assert calcjob.exit_status == 0

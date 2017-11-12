import os

import aiida
aiida.load_dbenv()
from aiida.common.exceptions import InputValidationError
from aiida.common.folders import SandboxFolder
from aiida.orm import CalculationFactory, DataFactory
from aiida.backends.testbase import AiidaTestCase
from aiida.orm import Code
from aiida_castep.calculations.castep import SinglePointCalculation

CasCalc =  SinglePointCalculation
StructureData = DataFactory("structure")
ParameterData = DataFactory("parameter")
KpointsData = DataFactory("array.kpoints")

code = Code()

calc_params = {
            "computer" : "localhost",
                        "resources" : {
                "num_machines" : 1,
                "num_mpiprocs_per_machine": 1
            }
        }

def test_inputs():
    import logging

    cell = ((2., 0., 0.), (0., 2., 0.), (0., 0., 2.))

    input_params = {
        "PARAM": {
        "task" : "singlepoint",
        "xc_functional" : "lda"
        },
        "CELL" : {
        "fix_all_cell" : "true",
        "block species_pot": ("Ba C9", "Ce C9")
        }
    }

    c = CasCalc(**calc_params).store()
    s = StructureData(cell=cell)
    s.append_atom(position=(0., 0., 0.), symbols=["Ba"])
    s.store()

    p =  ParameterData(dict=input_params).store()

    k = KpointsData()
    k.set_kpoints_mesh([4, 4, 4])
    k.store()

    inputdict = c.get_inputs_dict()
    inputdict.pop("code", None)

    with SandboxFolder() as f:
        # I use the same SandboxFolder more than once because nothing
        # should be written for these failing tests

        # Missing required input nodes
        c.use_parameters(p)

        c.use_structure(s)

        c.use_kpoints(k)

        c.use_code(code)
        inputdict = c.get_inputs_dict()
        c._prepare_for_submission(f, inputdict)


if __name__ == "__main__":
    test_inputs()

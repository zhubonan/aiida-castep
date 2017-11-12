"""
Test castep calculation
"""

import aiida
aiida.load_dbenv()

from ase.io import read

from aiida_castep.calculations.castep import SinglePointCalculation
from aiida.orm import DataFactory
from aiida.orm import Code

calc = SinglePointCalculation()

param_dict = {"CELL": {"FIX_ALL_CELL": "true",
                        "block spcies_pot": ("H C9",)},
              "PARAM": {"TASK": "singlepoint",
                        "XC_FUNCTIONAL": "lda"}}

parameters = DataFactory("parameters")(dict=param_dict)

StructureData = DataFactory("structure")
atoms = read("example_script/H2-geom/H2.cell")
structure = StructureData(ase=atoms)
KpointsData = DataFactory("array.kpoints")
kpoints = KpointsData()
kpoints.set_kpoints_mesh((4,4,4))


# Now link things together

calc.use_kpoints(kpoints)
calc.use_structure(structure)
calc.use_parameters(parameters)
calc.use_code(Code("castep-17.2@localhost"))
calc.store_all()
calc.submit()

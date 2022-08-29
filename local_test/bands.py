from aiida.engine import run, submit
from aiida.orm import Bool, Code, Dict, KpointsData, Str, StructureData
from ase.build import bulk

from aiida_castep.workflows.bands import CastepBandsWorkChain

silicon = StructureData(ase=bulk("Si", "diamond", 5.43, 5.43, 5.43))
builder = CastepBandsWorkChain.get_builder()

builder.structure = silicon
builder.run_separate_scf = Bool(True)
builder.scf.calc.kpoints = KpointsData()
builder.scf.calc.kpoints.set_cell(silicon.cell)
builder.scf.calc.kpoints.set_kpoints_mesh((4, 4, 4))

builder.scf.calc.parameters = Dict(
    dict={
        "cut_off_energy": 300,
    }
)

builder.scf.pseudos_family = Str("QC5")

# Options for the actual calculation
options = builder.scf.calc.metadata.options
options["resources"] = {"num_machines": 1, "tot_num_mpiprocs": 2}

builder.scf.calc.code = Code.get_from_string("castep@localhost")

builder.dos_kpoints = KpointsData()
builder.dos_kpoints.set_kpoints_mesh((8, 8, 8))

run(builder)

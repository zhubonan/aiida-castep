

import os

from aiida.common.exceptions import InputValidationError
from aiida.common.folders import SandboxFolder
from aiida.orm import DataFactory, CalculationFactory
from aiida.orm import Code
from aiida.common.exceptions import MultipleObjectsError

import aiida_castep.data.otfg as otf
import aiida_castep.data.usp as usp

from .utils import get_data_abs_path

CasCalc = CalculationFactory("castep.castep")
StructureData = DataFactory("structure")
ParameterData = DataFactory("parameter")
KpointsData = DataFactory("array.kpoints")

Ti_otfg = "Ti 3|1.8|9|10|11|30U:40:31:32(qc=5.5)"
Sr_otfg = "Sr 3|2.0|5|6|7|40U:50:41:42"
O_otfg = "O 2|1.1|15|18|20|20:21(qc=7)"

otfg = DataFactory("castep.otfgdata")


class BaseDataCase(object):
    """Base to include some useful things"""

    def create_family(self):
        """Creat families for testsing"""
        Ti, Sr, O, C9 = self.get_otfgs()
        otf.upload_otfg_family([Ti.entry, Sr.entry, O.entry], "STO_FULL", "TEST", False)
        otf.upload_otfg_family([Ti.entry, Sr.entry], "STO_O_missing", "TEST", False)

        # Missing O but that's OK we have a C9 wild card here
        otf.upload_otfg_family([Ti.entry, Sr.entry, "C9"], "STO_O_C9", "TEST", False)

        return "STO_FULL", "STO_O_missing", "STO_O_C9"

    def get_otfgs(self):

        Ti, _ = otfg.get_or_create(Ti_otfg, store_otfg=False)
        Sr, _ = otfg.get_or_create(Sr_otfg, store_otfg=False)
        O, _ = otfg.get_or_create(O_otfg, store_otfg=False)
        C9, _ = otfg.get_or_create("C9", store_otfg=False)
        return Ti, Sr, O, C9


class BaseCalcCase(object):

    def get_default_input(self):

        input_params = {
            "PARAM": {
                "task": "singlepoint",
                "xc_functional": "lda",
            },
            "CELL": {
                "fix_all_cell": "true",
                # "species_pot": ("Ba Ba_00.usp",)
            }
        }

        return input_params

    def get_kpoints_mesh(self, mesh=(4, 4, 4)):

        k = KpointsData()
        k.set_kpoints_mesh(mesh)
        k.store()
        return k

    def setup_calculation(self):
        from .utils import get_STO_structure

        STO = get_STO_structure()

        full, missing, C9 = self.create_family()
        c = CasCalc()
        pdict = self.get_default_input()
        # pdict["CELL"].pop("block species_pot")
        p = ParameterData(dict=pdict).store()
        c.use_structure(STO)
        c.use_pseudos_from_family(full)
        c.use_pseudos_from_family(C9)
        c.use_kpoints(self.get_kpoints_mesh())
        c.use_code(self.code)
        c.set_computer(self.computer)
        c.set_resources({"num_machines": 1, "num_mpiprocs_per_machine": 2})
        c.use_parameters(p)

        # Check mixing libray with acutal entry
        return c

    @classmethod
    def setup_code_castep(cls):
        code = Code()
        code.set_remote_computer_exec(
            (cls.computer, "/home/bonan/appdir/CASTEP-17.2/bin/linux_x86_64_gfortran5.0--mpi/castep.mpi"))
        code.set_input_plugin_name("castep.castep")
        code.store()
        cls.code = code

    def get_remote_data(self, rel_path):
        RemoteData = DataFactory("remote")
        rmd = RemoteData()
        rmd.set_computer(self.computer)
        rmd.set_remote_path(os.path.join(get_data_abs_path(), rel_path))
        return rmd

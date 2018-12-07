"""
Testing the parsers
"""

import os
from unittest import TestCase
import pytest

Ti_otfg = "Ti 3|1.8|9|10|11|30U:40:31:32(qc=5.5)"
Sr_otfg = "Sr 3|2.0|5|6|7|40U:50:41:42"
O_otfg = "O 2|1.1|15|18|20|20:21(qc=7)"

@pytest.fixture(scope="class")
def import_things(aiida_profile, request):

    from aiida.common.exceptions import InputValidationError
    from aiida.common.folders import SandboxFolder
    from aiida.orm import DataFactory, CalculationFactory
    from aiida.orm import Code
    from aiida.common.exceptions import MultipleObjectsError
    import aiida_castep.data.otfg as otf
    import aiida_castep.data.otfg
    import aiida_castep.data.usp as usp
    from aiida_castep.data.otfg import OTFGData as otfg
    from aiida.orm import DataFactory
    from aiida.parsers import ParserFactory
    CasCalc = CalculationFactory("castep.castep")
    ParameterData = DataFactory("parameter")
    KpointsData = DataFactory("array.kpoints")
    FolderData = DataFactory("folder")

    for k, v in locals().items():
        setattr(request.module, k, v)



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


@pytest.mark.usefixtures("import_things")
class BaseCalcCase(object):

    @pytest.fixture(autouse=True)
    def reset_db(self, aiida_profile):
        aiida_profile.reset_db()
        yield
        aiida_profile.reset_db()


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

    def setup_code_castep(self):
        self.setup_computer()
        code = Code()
        code.set_remote_computer_exec(
            (self.computer, "/home/bonan/appdir/CASTEP-17.2/bin/linux_x86_64_gfortran5.0--mpi/castep.mpi"))
        code.set_input_plugin_name("castep.castep")
        code.store()
        self.code = code

    def setup_computer(self):
        """Fixture for a local computer called localhost"""
        # Check whether Aiida uses the new backend interface to create collections.
        from aiida.utils.fixtures import _GLOBAL_FIXTURE_MANAGER
        from aiida.common import exceptions
        aiida_profile = _GLOBAL_FIXTURE_MANAGER
        ldir = "/tmp/babel-61802kNO"
        try:
            computer = aiida_profile._backend.computers.get(name='localhost')
        except exceptions.NotExistent:
            computer = aiida_profile._backend.computers.create(
                name='localhost',
                description='description',
                hostname='localhost',
                workdir=ldir,
                transport_type='local',
                scheduler_type='direct',
                enabled_state=True)
        computer.store()
        self.computer = computer


    def get_remote_data(self, rel_path):

        computer = localhost()()
        RemoteData = DataFactory("remote")
        rmd = RemoteData()
        rmd.set_computer(computer)
        rmd.set_remote_path(os.path.join(get_data_abs_path(), rel_path))
        return rmd



class TestCastepParser(TestCase, BaseCalcCase, BaseDataCase):


    def test_import(self):

        assert aiida_castep.data.otfg

    def get_data_abs_path(self):
        test_moudule = os.path.split(__file__)[0]
        data_folder = os.path.join(test_moudule, "data")
        return data_folder

    def get_dummy_outputs(self):

        retrieved = {}
        for folder in ["H2-geom", "O2-geom-spin", "Si-geom-stress", "N2-md"]:
            folderdata = FolderData()
            folderdata.replace_with_folder(
                os.path.join(self.get_data_abs_path(), folder))
            retrieved[folder] = dict(retrieved=folderdata)
        return retrieved

    def test_version_consistency(self):
        """
        Test that moudule versions are consistent
        """

        from aiida_castep.parsers.raw_parser import __version__ as prv
        from aiida_castep.parsers.castep import __version__ as pcv
        from aiida_castep.calculations.castep import __version__ as ccv
        from aiida_castep.calculations.base import __version__ as cbv
        self.assertTrue(prv == pcv == ccv == cbv)

    def test_parser_retrieved(self):
        from .utils import get_x2_structure
        self.setup_code_castep()
        calc = self.setup_calculation()

        parser = ParserFactory("castep.castep")(calc)
        retrived_folders = self.get_dummy_outputs()
        common_keys = ["cells", "positions", "forces", "symbols", "geom_total_energy"]
        md_keys = ["hamilt_energy", "kinetic_energy",
                   "velocities", "temperatures", "times"]
        geom_keys = ["geom_enthalpy"]

        for name, r in retrived_folders.items():
            if 'O2' in name:
                xtemp = 'O'
            elif 'Si' in name:
                xtemp = 'Si'
            elif 'N2' in name:
                xtemp = 'N'
            elif 'H2' in name:
                xtemp = 'H'
            # Swap the correct structure to allow desort to work
            calc.use_structure(get_x2_structure(xtemp))

            success, out = parser.parse_with_retrieved(r)
            out = dict(out)

            out_structure = out[parser.get_linkname_outstructure()]
            out_param_dict = out[parser.get_linkname_outparams()].get_dict()
            out_traj = out[parser.get_linkname_outtrajectory()]
            self.assertIn("total_energy", out_param_dict)
            self.assertIn("unit_energy", out_param_dict)
            self.assertEqual(out_param_dict["unit_energy"], "eV")
            self.assertEqual(calc.inp.structure.label, out_structure.label)
            # Check the length of sites are consistent
            self.assertEqual(len(out_structure.sites), len(out_traj.get_symbols()))

            for k in common_keys:
                self.assertIn(k, out_traj.get_arraynames())

            if name == "O2-geom-spin" or name == "Si-geom-stress":
                self.assertIn(parser.get_linkname_outbands(), out)
                bands = out[parser.get_linkname_outbands()]

                # Check if spins are handled correctly
                self.assertIn(bands.get_attr('nspins'), [1, 2])
                if bands.get_attr('nspins') == 1:
                    self.assertEqual(bands.get_attr('nkpts'), len(bands.get_bands()))
                elif bands.get_attr('nspins') == 2:
                    self.assertEqual(bands.get_attr('nkpts'), len(bands.get_bands()[0]))

                for k in geom_keys:
                    self.assertIn(k, out_traj.get_arraynames())

            if name == "N2-md":
                for k in md_keys:
                    self.assertIn(k, out_traj.get_arraynames())


class TestPot1DParser(TestCase):

    def test_load_plugin(self):
        Pot1dParser = ParserFactory("castep.pot1d")

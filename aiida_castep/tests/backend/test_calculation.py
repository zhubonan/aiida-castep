"""
Test for generating castep input
"""
import os

from aiida.common.exceptions import InputValidationError
from aiida.common.folders import SandboxFolder
from aiida.orm import  DataFactory
from aiida.backends.testbase import AiidaTestCase
from aiida.orm import Code
from aiida_castep.calculations.castep import CastepCalculation
from aiida.common.exceptions import MultipleObjectsError
from .test_data import BaseDataCase
from .utils import get_data_abs_path

CasCalc =  CastepCalculation
StructureData = DataFactory("structure")
ParameterData = DataFactory("parameter")
KpointsData = DataFactory("array.kpoints")


class CalcTestBase(object):

    def get_default_input(self):

        input_params = {
            "PARAM": {
            "task" : "singlepoint",
            "xc_functional" : "lda",
            },
            "CELL" : {
            "fix_all_cell" : "true",
            #"species_pot": ("Ba Ba_00.usp",)
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

        code = self.code
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
        c.set_computer(self.localhost)
        c.set_resources({"num_machines":1, "num_mpiprocs_per_machine":2})
        c.use_parameters(p)

        # Check mixing libray with acutal entry
        return c

    @classmethod
    def setup_localhost(cls):
        from aiida.orm.computer import Computer
        l = Computer()
        l.set_name("localhost")
        l.set_hostname("localhost")
        l.set_transport_type("local")
        l.set_workdir("/home/bonan/aiida_test_run/")
        l.set_scheduler_type("direct")
        l.store()
        cls.localhost = l

    @classmethod
    def setup_code_castep(cls):
        from aiida.orm.code import Code
        code = Code()
        code.set_remote_computer_exec((cls.localhost, "/home/bonan/appdir/CASTEP-17.2/bin/linux_x86_64_gfortran5.0--mpi/castep.mpi"))
        code.set_input_plugin_name("castep.castep")
        code.store()
        cls.code = code

    def get_remote_data(self, rel_path):
        RemoteData = DataFactory("remote")
        rmd = RemoteData()
        rmd.set_computer(self.localhost)
        rmd.set_remote_path(os.path.join(get_data_abs_path(), rel_path))
        return rmd

class TestCastepInputGeneration(AiidaTestCase, CalcTestBase, BaseDataCase):
    """
    Test if the input is correctly generated
    """

    @classmethod
    def setUpClass(cls):
        super(TestCastepInputGeneration, cls).setUpClass()
        cls.calc_params = {
            "computer" : cls.computer,
            "resources" : {
                "num_machines" : 1,
                "num_mpiprocs_per_machine": 1
            }
        }

        cls.code = Code()
        cls.code.set_remote_computer_exec((cls.computer, "/x.x"))
        cls.code.store()

    def make_H2_structure(self):

        cell = ((5., 0., 0.), (0., 5., 0.), (0., 0., 5.))
        s = StructureData(cell=cell)
        s.append_atom(position=(0., 0., 0.), symbols=["H"])
        s.append_atom(position=(1., 0., 0.), symbols=["H"])
        self.H2 = s

    def test_pre_submit_checkings(self):
        """
        Test checkup before submission
        """
        pass

    def test_using_OTFG_family(self):
        """
        Test using OTFG in the input
        """
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

        input_dict = c.get_inputs_dict()
        # Check mixing libray with acutal entry
        self.assertEqual(input_dict["pseudo_O"].entry, "C9")

        with SandboxFolder() as f:
            p = ParameterData(dict=pdict)
            c.use_parameters(p)
            input_dict = c.get_inputs_dict()
            c._prepare_for_submission(f, input_dict)

    def test_using_OTFG_mix(self):
        """
        Test using mixed OTFG library and manual values
        """
        pass

    def test_using_UpfData(self):
        """
        Test using UpfData
        """

    def test_inputs(self):

        cell = ((2., 0., 0.), (0., 2., 0.), (0., 0., 2.))

        input_params = {
            "PARAM": {
            "task" : "singlepoint",
            "xc_functional" : "lda",
            },
            "CELL" : {
            "fix_all_cell" : "true",
            "species_pot": ("Ba Ba_00.usp",)
            }
        }

        c = CasCalc(**self.calc_params).store()
        s = StructureData(cell=cell)
        s.append_atom(position=(0., 0., 0.), symbols=["Ba"])
        s.append_atom(position=(1., 0., 0.), symbols=["Ba"])
        s.store()

        p =  ParameterData(dict=input_params).store()

        k = KpointsData()
        k.set_kpoints_mesh([4, 4, 4])
        k.store()

        settings_dict = {"SPINS": [0, 0]}
        c.use_settings(ParameterData(dict=settings_dict))
        inputdict = c.get_inputs_dict()

        inputdict.pop("code", None)

        with SandboxFolder() as f:
            # I use the same SandboxFolder more than once because nothing
            # should be written for these failing tests

            # Missing required input nodes
            with self.assertRaises(InputValidationError):
                c._prepare_for_submission(f, inputdict)
            c.use_parameters(p)
            inputdict = c.get_inputs_dict()
            with self.assertRaises(InputValidationError):
                c._prepare_for_submission(f, inputdict)
            c.use_structure(s)
            inputdict = c.get_inputs_dict()
            with self.assertRaises(InputValidationError):
                c._prepare_for_submission(f, inputdict)
            c.use_kpoints(k)
            inputdict = c.get_inputs_dict()
            with self.assertRaises(InputValidationError):
                c._prepare_for_submission(f, inputdict)

            c.use_code(self.code)
            inputdict = c.get_inputs_dict()
            c._prepare_for_submission(f, inputdict)

            # Check existenc of the file
            cell = f.get_abs_path(c._SEED_NAME + ".cell", check_existence=True)
            param = f.get_abs_path(c._SEED_NAME + ".param", check_existence=True)

            print("\n"+ "#" *5 + "CONTENT OF CELL FILE: " + "#" * 5)
            with open(cell) as p:
                print(p.read())

            print("\n" + "#" *5 + "CONTENT OF PARAM FILE: " + "#" * 5)
            with open(param) as p:
                print(p.read())

            # Now test dryrun
            self.castep_dryrun(f, c._SEED_NAME)
            self.assertFalse(f.get_content_list("*.err"))

    def castep_dryrun(self, folder, seed):
        from subprocess import call
        import os
        seed = os.path.join(folder.abspath, seed)
        call(["castep.serial", seed, "-dryrun"], cwd=folder.abspath)


class TestRestartGeneration(AiidaTestCase, CalcTestBase, BaseDataCase):

    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super(TestRestartGeneration, cls).setUpClass(*args, **kwargs)
        cls.clean_db()
        cls.setup_localhost()
        cls.setup_code_castep()

    def test_restart(self):

        # Initial logic of creation
        c1 = self.setup_calculation()
        c1.store_all()
        with self.assertRaises(InputValidationError):
            c2 = c1.create_restart(ignore_state=False)
        with self.assertRaises(InputValidationError):
            c2 = c1.create_restart(ignore_state=True, reuse=True)

        rmd = self.get_remote_data("H2-geom")
        rmd.store()
        c1._set_state("RETRIEVING")
        from aiida.common.links import LinkType
        rmd.add_link_from(c1, link_type=LinkType.CREATE)

        # This simply create a copy of c1
        c2 = c1.create_restart(ignore_state=True)
        c2_inp = c2.get_inputs_dict()
        c1_inp = c1.get_inputs_dict()

        # Check all inputs of c1 are indeed present in c2
        for key in c1_inp:
            self.assertIn(key, c2_inp)
            self.assertEqual(c2_inp[key].pk, c1_inp[key].pk)

        c2 = c1.create_restart(ignore_state=True, reuse=True)
        c2_inp = c2.get_inputs_dict()
        c1_inp = c1.get_inputs_dict()

        c2_param = c2_inp[c2.get_linkname("parameters")].get_dict()['PARAM']
        c1_param = c1_inp[c1.get_linkname("parameters")].get_dict()['PARAM']

        reuse = c2_param.pop("reuse")
        self.assertEqual(reuse, os.path.join(c2._restart_copy_to, "{}.check".format(c2._SEED_NAME)))

        with SandboxFolder() as f:
            print(c2._prepare_for_submission(f, c2_inp))



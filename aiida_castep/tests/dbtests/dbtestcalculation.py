"""
Test for generating castep input
"""
from __future__ import absolute_import
from __future__ import print_function
import os
import unittest

from aiida.common import InputValidationError
from aiida.common.folders import SandboxFolder
from aiida.plugins import DataFactory, CalculationFactory
from aiida.backends.testbase import AiidaTestCase
from aiida.orm import Code
from aiida_castep.calculations.castep import CastepTSCalculation as TSCalc
from .dbcommon import BaseDataCase, BaseCalcCase

CasCalc = CalculationFactory("castep.castep")
BSCalc = CalculationFactory("castep.castep")
TSCalc = CalculationFactory("castep.ts")
StructureData = DataFactory("structure")
Dict = DataFactory("dict")
KpointsData = DataFactory("array.kpoints")


class TestCastepInputGeneration(AiidaTestCase, BaseCalcCase, BaseDataCase):
    """
    Test if the input is correctly generated
    """
    @classmethod
    def setUpClass(cls):
        super(TestCastepInputGeneration, cls).setUpClass()
        cls.calc_params = {
            "computer": cls.computer,
            "resources": {
                "num_machines": 1,
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
        p = Dict(dict=pdict).store()
        c.use_structure(STO)
        c.use_pseudos_from_family(full)
        c.use_pseudos_from_family(C9)
        c.use_kpoints(self.get_kpoints_mesh())
        c.use_code(self.code)

        input_dict = c.get_inputs_dict()
        # Check mixing libray with acutal entry
        self.assertEqual(input_dict["pseudo_O"].entry, "C9")

        with SandboxFolder() as f:
            p = Dict(dict=pdict)
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
    def generate_test_calc(self):
        """
        Return a defined Calculation
        """

        cell = ((2., 0., 0.), (0., 2., 0.), (0., 0., 2.))

        input_params = {
            "PARAM": {
                "task": "singlepoint",
                "xc_functional": "lda",
            },
            "CELL": {
                "fix_all_cell": "true",
            }
        }

        c = CasCalc(**self.calc_params).store()
        s = StructureData(cell=cell)
        s.append_atom(position=(0., 0., 0.), symbols=["Ba"])
        s.append_atom(position=(1., 0., 0.), symbols=["Ba"])
        s.store()

        p = Dict(dict=input_params).store()

        k = KpointsData()
        k.set_kpoints_mesh([4, 4, 4])
        k.store()

        settings_dict = {"SPINS": [0, 0]}
        c.use_settings(Dict(dict=settings_dict))
        c.label = "TEST CALC"
        c.description = "Test calculation for AiiDA CASTEP plugin."
        c.use_code(self.code)
        c.use_kpoints(self.get_kpoints_mesh())
        c.use_structure(s)
        c.use_parameters(p)

        return c

    def test_inputs(self):

        cell = ((2., 0., 0.), (0., 2., 0.), (0., 0., 2.))

        input_params = {
            "PARAM": {
                "task": "singlepoint",
                "xc_functional": "lda",
            },
            "CELL": {
                "fix_all_cell": "true",
                "species_pot": ("Ba Ba_00.usp", )
            }
        }

        c = CasCalc(**self.calc_params).store()
        s = StructureData(cell=cell)
        s.append_atom(position=(0., 0., 0.), symbols=["Ba"])
        s.append_atom(position=(1., 0., 0.), symbols=["Ba"])
        s.store()

        p = Dict(dict=input_params).store()

        k = KpointsData()
        k.set_kpoints_mesh([4, 4, 4], offset=(0.5, 0.5, 0.5))

        settings_dict = {"SPINS": [0, 0]}
        c.use_settings(Dict(dict=settings_dict))
        c.label = "TEST CALC"
        c.description = ("Test calculation for AiiDA CASTEP plugin. "
                         "Testing generation of inputs.")
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

            # Continuation keywords present - should raise exception
            inputdict = c.get_inputs_dict()
            input_params["PARAM"]["continuation"] = "default"
            p2 = Dict(dict=input_params)
            inputdict["parameters"] = p2
            with self.assertRaises(InputValidationError):
                c._prepare_for_submission(f, inputdict)

            c.use_code(self.code)
            inputdict = c.get_inputs_dict()
            c._prepare_for_submission(f, inputdict)

            # Check existenc of the file
            cell = f.get_abs_path(c._SEED_NAME + ".cell", check_existence=True)
            param = f.get_abs_path(c._SEED_NAME + ".param",
                                   check_existence=True)
            print("\n" + "#" * 5 + "CONTENT OF CELL FILE: " + "#" * 5)

            # Check and print out the input files
            with open(cell) as p:
                cell_content = p.read()
                print(cell_content)
                self.assertIn("fix_all_cell", cell_content)
                self.assertIn("kpoints_mp_offset", cell_content)
                self.assertIn("kpoints_mp_grid", cell_content)

            print("\n" + "#" * 5 + "CONTENT OF PARAM FILE: " + "#" * 5)
            with open(param) as p:
                param_content = p.read()
                print(param_content)
                self.assertIn("task", param_content)

            k.set_kpoints_mesh((2, 2, 2), (0, 0, 0))
            c.use_kpoints(k)
            inputdict = c.get_inputs_dict()
            c._prepare_for_submission(f, inputdict)
            with open(cell) as p:
                cell_content = p.read()
                print(cell_content)
                self.assertNotIn("kpoints_mp_offset", cell_content)

    @unittest.skip("Dry run test takes a long time.")
    def test_dryrun(self):
        from subprocess import call

        try:
            call(["castep.serial", "-v"])
        except OSError:
            self.skipTest("No CASTEP excutable found")

        c = self.generate_test_calc()
        full, missing, C9 = self.create_family()
        c.use_pseudos_from_family(C9)
        # Do a dry run - check if any error message is given
        with SandboxFolder() as f:
            c._prepare_for_submission(f, c.get_inputs_dict())
            self.castep_dryrun(f, c._SEED_NAME)
            self.assertFalse(f.get_content_list("*.err"))
            self.assertTrue(f.get_content_list("*.castep"))

    def castep_dryrun(self, folder, seed):
        from subprocess import call
        import os
        seed = os.path.join(folder.abspath, seed)
        call(["castep.serial", seed, "-dryrun"], cwd=folder.abspath)


class TestRestartGeneration(AiidaTestCase, BaseCalcCase, BaseDataCase):
    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super(TestRestartGeneration, cls).setUpClass(*args, **kwargs)
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

        reuse = c2_param.pop("reuse")
        self.assertEqual(
            reuse,
            os.path.join(c2._restart_copy_to,
                         "{}.check".format(c2._SEED_NAME)))

        with SandboxFolder() as f:
            print(c2._prepare_for_submission(f, c2_inp))

    def test_continue_from(self):
        """
        Test the continue_from function.
        It calls the same underlying function compared with
        create_restart
        """
        c1 = self.setup_calculation()
        c1.store_all()
        c2 = BSCalc.continue_from(c1, ignore_state=True, reuse=False)

        rmd = self.get_remote_data("H2-geom")
        rmd.store()
        c1._set_state("RETRIEVING")
        from aiida.common.links import LinkType
        rmd.add_link_from(c1, link_type=LinkType.CREATE)

        c3 = BSCalc.continue_from(c1, ignore_state=True)
        c1_inp = c1.get_inputs_dict()
        c2_inp = c2.get_inputs_dict()
        c3_inp = c3.get_inputs_dict()

        # Check all inputs of c1 are indeed present in c2
        for key in c1_inp:
            self.assertIn(key, c2_inp)

        for key in c1_inp:
            self.assertIn(key, c3_inp)

        with SandboxFolder() as f:
            c3._prepare_for_submission(f, c3_inp)


class TestTSCalculation(BaseCalcCase, BaseDataCase, AiidaTestCase):
    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super(TestTSCalculation, cls).setUpClass(*args, **kwargs)
        cls.setup_code_castep()

    def get_default_input(self):

        input_params = {
            "PARAM": {
                "task": "transitionstatesearch",
                "xc_functional": "lda",
            },
            "CELL": {
                "fix_all_cell": "true",
                # "species_pot": ("Ba Ba_00.usp",)
            }
        }

        return input_params

    def setup_calculation(self, param=None):
        from .utils import get_STO_structure

        STO = get_STO_structure()
        full, missing, C9 = self.create_family()
        c = TSCalc()

        if param:
            pdict = param
        else:
            pdict = self.get_default_input()

        # pdict["CELL"].pop("block species_pot")
        p = Dict(dict=pdict)
        c.use_structure(STO)
        c.use_product_structure(STO)
        c.use_pseudos_from_family(C9)
        c.use_kpoints(self.get_kpoints_mesh())
        c.use_code(self.code)
        c.set_computer(self.computer)
        c.set_resources({"num_machines": 1, "num_mpiprocs_per_machine": 2})
        c.use_parameters(p)

        # Check mixing libray with acutal entry
        return c

    def test_input_validation(self):
        """Test input validation"""

        c = self.setup_calculation()
        pdict = c.get_inputs_dict()[c.get_linkname('parameters')].get_dict()
        pdict['PARAM']['task'] = "singlepoint"
        c.get_inputs_dict()[c.get_linkname('parameters')].set_dict(pdict)

        with SandboxFolder() as f:
            with self.assertRaises(InputValidationError):
                inputs = c.get_inputs_dict()
                c._prepare_for_submission(f, inputs)

    def test_generation(self):
        """
        Test if the block has been generated
        """
        c = self.setup_calculation()
        with SandboxFolder() as f:
            inputs = c.get_inputs_dict()
            c._prepare_for_submission(f, inputs)
            with f.open("aiida.cell") as fcell:
                cell = fcell.read()
                self.assertIn("%BLOCK POSITIONS_ABS_PRODUCT", cell)
                self.assertIn("%ENDBLOCK POSITIONS_ABS_PRODUCT", cell)


class TestBSCalculation(BaseCalcCase, BaseDataCase, AiidaTestCase):
    @classmethod
    def setUpClass(cls, *args, **kwargs):
        super(TestBSCalculation, cls).setUpClass(*args, **kwargs)
        cls.setup_code_castep()

    def get_default_input(self):

        input_params = {
            "PARAM": {
                "task": "bandstructure",
                "xc_functional": "lda",
            },
            "CELL": {
                "fix_all_cell": "true",
                # "species_pot": ("Ba Ba_00.usp",)
            }
        }

        return input_params

    def get_bs_kpoints(self):
        kpoints = KpointsData()
        kpoints.set_kpoints([[0, 0, 0], [0.5, 0.5, 0.5]])
        return kpoints

    def setup_calculation(self, param=None):
        from .utils import get_STO_structure

        STO = get_STO_structure()
        full, missing, C9 = self.create_family()
        c = BSCalc()

        if param:
            pdict = param
        else:
            pdict = self.get_default_input()

        # pdict["CELL"].pop("block species_pot")
        p = Dict(dict=pdict)
        c.use_structure(STO)
        c.use_pseudos_from_family(C9)
        c.use_kpoints(self.get_kpoints_mesh())
        c.use_bs_kpoints(self.get_bs_kpoints())
        c.use_code(self.code)
        c.set_computer(self.computer)
        c.set_resources({"num_machines": 1, "num_mpiprocs_per_machine": 2})
        c.use_parameters(p)

        # Check mixing libray with acutal entry
        return c

    def test_input_validation(self):
        """Test input validation"""

        c = self.setup_calculation()
        pdict = c.get_inputs_dict()[c.get_linkname('parameters')].get_dict()
        pdict['PARAM']['task'] = "singlepoint"
        c.get_inputs_dict()[c.get_linkname('parameters')].set_dict(pdict)

        with SandboxFolder() as f:
            with self.assertRaises(InputValidationError):
                inputs = c.get_inputs_dict()
                c._prepare_for_submission(f, inputs)

        c = self.setup_calculation()
        c.CHECK_EXTRA_KPN = True

        with SandboxFolder() as f:
            with self.assertRaises(InputValidationError):
                inputs = c.get_inputs_dict()
                inputs.pop("bs_kpoints")
                c._prepare_for_submission(f, inputs)

    def test_restart(self):
        """
        Test creating an restart of the calculation.
        The restart should retain the extra kpoints inputs.
        """
        c = self.setup_calculation()
        new = c.create_restart(ignore_state=True)
        self.assertEqual(type(new), type(c))
        inpname = "{}_kpoints".format(c.kpn_name)
        self.assertIn(new.get_linkname(inpname), new.get_inputs_dict())

        # Extra kpn is not mandatory
        extra_kpn = c.get_inputs_dict()["bs_kpoints"]
        c._remove_link_from("bs_kpoints")
        self.assertNotIn(extra_kpn, c.get_inputs())
        # This should still succeed
        new = c.create_restart(ignore_state=True)
        self.assertNotIn(extra_kpn, new.get_inputs())

    def test_bs_kpoints(self):

        c = self.setup_calculation()
        inputs = c.get_inputs_dict()
        with SandboxFolder() as f:
            c._prepare_for_submission(f, inputs)
            with f.open("aiida.cell") as cell:
                content = cell.read()
        self.assertIn("%BLOCK BS_KPOINTS_LIST", content)

    def test_bs_kpoints_mp(self):

        c = self.setup_calculation()
        inputs = c.get_inputs_dict()
        mp = KpointsData()
        mp.set_kpoints_mesh([2, 2, 2], (0.1, 0.1, 0.1))
        inputs['bs_kpoints'] = mp

        with SandboxFolder() as f:
            c._prepare_for_submission(f, inputs)
            with f.open("aiida.cell") as cell:
                content = cell.read()
        self.assertIn("{:<20}: 2 2 2".format("bs_kpoints_mp_grid"), content)
        self.assertIn("{:<20}: 0.1 0.1 0.1".format("bs_kpoints_mp_offset"),
                      content)

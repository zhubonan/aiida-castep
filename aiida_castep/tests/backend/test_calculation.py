"""
Test for generating castep input
"""
import aiida

from aiida.common.exceptions import InputValidationError
from aiida.common.folders import SandboxFolder
from aiida.orm import  DataFactory
from aiida.backends.testbase import AiidaTestCase
from aiida.orm import Code
from aiida_castep.calculations.castep import CastepCalculation

CasCalc =  CastepCalculation
StructureData = DataFactory("structure")
ParameterData = DataFactory("parameter")
KpointsData = DataFactory("array.kpoints")


class TestCastepInputGeneration(AiidaTestCase):
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

    def test_inputs(self):

        cell = ((2., 0., 0.), (0., 2., 0.), (0., 0., 2.))

        input_params = {
            "PARAM": {
            "task" : "singlepoint",
            "xc_functional" : "lda",
            },
            "CELL" : {
            "fix_all_cell" : "true",
            "block species_pot": ("Ba Ba_00.usp",)
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



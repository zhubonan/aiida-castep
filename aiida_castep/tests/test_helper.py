
from aiida_castep.calculations.helper import CastepHelper, HelperCheckError
import unittest


class TestHelper(unittest.TestCase):
    """class  TestHelper for test CastepHepler"""

    @classmethod
    def setUpClass(cls):
        cls.helper = CastepHelper()

    @property
    def flat_dict(self):
        return dict(fix_all_cell="true", cut_off_energy="true", kpoints_mp_grid= "0 0 0")

    @property
    def only_param_dict(self):
        return dict(PARAM= {"cut_off_energy": "100", "nextra_bands": "200"})

    @property
    def only_cell_dict(self):
        return dict(CELL = {"fix_all_cell": "100", "symmetry_generate": "200"})

    @property
    def input_dict(self):
        d = self.only_cell_dict
        d.update(self.only_param_dict)
        return d

    def test_from_flat(self):
        out, not_found = self.helper._from_flat_dict(self.flat_dict)
        #print(self.helper.help_dict)
        self.assertFalse(not_found)

    def test_check_dict_raw(self):
        """Test the underlying check_dict function"""

        invalid, wrong = self.helper._check_dict(self.only_cell_dict)
        self.assertFalse(any([wrong, invalid]))
        invalid, wrong = self.helper._check_dict(self.only_param_dict)
        self.assertFalse(any([wrong, invalid]))

        comb = self.only_cell_dict
        comb.update(self.only_param_dict)
        invalid, wrong = self.helper._check_dict(comb)
        self.assertFalse(any([wrong, invalid]))

        comb["CELL"].update(kpointx_mp_grid= "d")
        comb["PARAM"].update(snap_to_symmetry="true")
        invalid, wrong = self.helper._check_dict(comb)
        self.assertIn("kpointx_mp_grid", invalid)
        self.assertIn(("snap_to_symmetry", "CELL"), wrong)

    def test_check_dict(self):
        """Test top level check dict function"""

        # Pass a good dictionary
        comb = self.input_dict
        dout = self.helper.check_dict(comb)
        self.assertEqual(dout, comb)

        # Pass a wrong dictioanry
        comb.update(FOO="bla")
        with self.assertRaises(HelperCheckError):
            self.helper.check_dict(comb)

        # Pass a mix and matched
        comb.pop("FOO")
        comb.update({"spin": "1"})
        outdict = self.helper.check_dict(comb)
        self.assertIn("spin", outdict["PARAM"])

        with self.assertRaises(HelperCheckError):
            outdict = self.helper.check_dict(comb, auto_fix=False)

        comb["CELL"].update({"spin_polarised": "true"})
        outdict = self.helper.check_dict(comb, auto_fix=True)
        self.assertIn("spin_polarised", outdict["PARAM"])


if __name__ == "__main__":
    unittest.main()

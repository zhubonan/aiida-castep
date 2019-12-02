from __future__ import absolute_import
from aiida_castep.calculations.helper import CastepHelper, HelperCheckError
import unittest

helper = CastepHelper()
no_info = helper.BY_PASS


class TestHelper(unittest.TestCase):
    """class  TestHelper for test CastepHepler"""
    @classmethod
    def setUpClass(cls):
        cls.helper = CastepHelper()

    @property
    def flat_dict(self):
        return dict(fix_all_cell="true",
                    cut_off_energy="true",
                    kpoints_mp_grid="0 0 0")

    @property
    def only_param_dict(self):
        return dict(PARAM={"cut_off_energy": "100", "nextra_bands": "200"})

    @property
    def only_cell_dict(self):
        return dict(CELL={"fix_all_cell": "100", "symmetry_generate": "200"})

    @property
    def input_dict(self):
        d = self.only_cell_dict
        d.update(self.only_param_dict)
        return d

    @unittest.skipIf(no_info, "No helper info found")
    def test_from_flat(self):
        out, not_found = self.helper._from_flat_dict(self.flat_dict)
        # print(self.helper.help_dict)
        self.assertFalse(not_found)

    @unittest.skipIf(no_info, "No helper info found")
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

        comb["CELL"].update(kpointx_mp_grid="d")
        comb["PARAM"].update(snap_to_symmetry="true")
        invalid, wrong = self.helper._check_dict(comb)
        self.assertIn("kpointx_mp_grid", invalid)
        self.assertIn(("snap_to_symmetry", "CELL"), wrong)

    @unittest.skipIf(no_info, "No helper info found")
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

        # Check incompatible keys can be spotted
        outdict["PARAM"].update(elec_method="dm")
        self.helper.check_dict(outdict, auto_fix=False)

        outdict["PARAM"].pop("elec_method")
        outdict["PARAM"].update(metals_method="dm")
        self.helper.check_dict(outdict, auto_fix=False)

        # Should raise error if both keys present
        outdict["PARAM"].update(elec_method="dm")
        with self.assertRaises(HelperCheckError):
            outdict = self.helper.check_dict(outdict, auto_fix=False)

    @unittest.skipIf(no_info, "No helper info found")
    def test_check_dict_flat(self):
        """Test checking error in a flat dictionary"""
        flat = self.flat_dict
        self.helper.check_dict(flat, auto_fix=False, allow_flat=True)
        with self.assertRaises(HelperCheckError):
            flat['kpoints_gdrd'] = 1
            self.helper.check_dict(flat, auto_fix=False, allow_flat=True)


if __name__ == "__main__":
    unittest.main()

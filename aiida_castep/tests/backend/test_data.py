"""
Data for data plugins
"""


import aiida

from aiida.common.exceptions import InputValidationError
from aiida.common.folders import SandboxFolder
from aiida.orm import  DataFactory
from aiida.backends.testbase import AiidaTestCase
from aiida.orm import Code
from aiida_castep.calculations.castep import CastepCalculation
import aiida_castep.data.otfg as otf

Ti_otfg = "Ti 3|1.8|9|10|11|30U:40:31:32(qc=5.5)"
Sr_otfg = "Sr 3|2.0|5|6|7|40U:50:41:42"
O_otfg = "O 2|1.1|15|18|20|20:21(qc=7)"


class TestOTFGData(AiidaTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestOTFGData, cls).setUpClass()
        cls.otfg = DataFactory("castep.otfgdata")

    def setUp(self):
        self.clean_db()

    def test_otfg_split(self):
        element, setting = otf.split_otfg_entry(Ti_otfg)
        self.assertEqual(element, "Ti")
        self.assertEqual(setting, "3|1.8|9|10|11|30U:40:31:32(qc=5.5)")

    def test_otfg_create(self):

        element, setting = otf.split_otfg_entry(Ti_otfg)
        C9 = self.otfg(string="C9")
        self.assertEqual(C9.string, "C9")
        self.assertEqual(C9.element, "LIBRARY")
        C9.store()

        Ti = self.otfg(string=setting, element=element)
        self.assertEqual(Ti.string, setting)
        self.assertEqual(Ti.element, element)
        Ti.store()

    def test_get_or_create(self):


        Ti, create = self.otfg.get_or_create(Ti_otfg, store_otfg=False)
        self.assertTrue(create)

        # Create but not stored do it again should have no change
        Ti, create = self.otfg.get_or_create(Ti_otfg, store_otfg=False)
        self.assertTrue(create)

        Ti.store()

        Ti2, create = self.otfg.get_or_create(Ti_otfg, store_otfg=False)
        self.assertFalse(create)

        # Should get the stored OTFG entry
        # If using SQLA this Ti should be IS Ti2?
        self.assertEqual(Ti2.uuid, Ti.uuid)

        # Using another way should be the same
        Sr = self.otfg()
        Sr.set_element("Sr")
        Sr.set_string("bla")
        Sr.store()

        Sr2, create = self.otfg.get_or_create("Sr_bla")
        self.assertFalse(create)

        # A different OTFG
        Sr3, create = self.otfg.get_or_create("Sr_foo")
        self.assertTrue(create)

        # Check if more than one instance is found in the db
        with self.assertRaises(ValueError):
            Sr = self.otfg()
            Sr.set_element("Sr")
            Sr.set_string("bla")
            Sr.store()

            # This should fail
            Sr4, create  = self.otfg.get_or_create("Sr_bla", use_first=False)

    def test_set_up_family(self):

        Ti, _ = self.otfg.get_or_create(Ti_otfg, store_otfg=False)
        Sr, _ = self.otfg.get_or_create(Sr_otfg, store_otfg=False)
        O, _ = self.otfg.get_or_create(O_otfg, store_otfg=False)
        C9, _ = self.otfg.get_or_create("C9", store_otfg=False)

        otfgs = [Ti.entry, Sr.entry, C9.entry]
        entry, uploaded = otf.upload_otfg_family(otfgs, "Test", "Test")
        self.assertEqual((entry, uploaded), (3, 3))

        # This should fail
        with self.assertRaises(ValueError):
            entry, uploaded = otf.upload_otfg_family(otfgs, "Test", "Test")

        entry, uploaded = otf.upload_otfg_family([O.entry] + otfgs, "Test", "Test", stop_if_existing=False)

        groups = self.otfg.get_otfg_groups()
        self.assertEqual(len(groups), 1)

        retrieved_entries = [node.entry for node in groups[0].nodes]
        for o in otfgs + [O.entry]:
            self.assertIn(o, retrieved_entries)




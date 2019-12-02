"""
In this test we adopt the PluginTestCase provided by aiida and migrate
existing AiiDATestCase tests with minimum effort
"""

from __future__ import absolute_import
import io
import os

from aiida.common.folders import SandboxFolder
from aiida.common import ValidationError
from unittest import TestCase
import pytest

Ti_otfg = "Ti 3|1.8|9|10|11|30U:40:31:32(qc=5.5)"
Sr_otfg = "Sr 3|2.0|5|6|7|40U:50:41:42"
O_otfg = "O 2|1.1|15|18|20|20:21(qc=7)"

# This fixture will be run for each class and ensure
# AiiDA test environment has been loaded correctly


@pytest.fixture(scope="class")
def import_things(aiida_profile, request):
    import aiida_castep.data.otfg as otf
    import aiida_castep.data.usp as usp
    from aiida.plugins import DataFactory
    request.cls.otfg = otf.OTFGData
    request.cls.otf = otf
    request.cls.usp = usp
    request.cls.usp = usp


@pytest.mark.usefixtures("import_things")
class BaseDataCase(TestCase):
    """Base to include some useful things"""

    # @pytest.fixture(autouse=True, scope="function")
    # def populate_env(self):
    #     """
    #     Popoulate the class namespace with the imported modules
    #     """
    #     if not self.AIIDA_ENV_LOADED:
    #         import aiida_castep.data.otfg as otf
    #         import aiida_castep.data.usp as usp
    #         from aiida.orm import DataFactory
    #         self.otfg = DataFactory("castep.otfgdata")
    #         self.otf = otf
    #         self.usp = usp
    #         self.AIIDA_ENV_LOADED = True

    @pytest.fixture(autouse=True)
    def reset_db(self, aiida_profile):
        aiida_profile.reset_db()
        yield
        aiida_profile.reset_db()

    def create_family(self):
        """Creat families for testsing"""
        Ti, Sr, O, C9 = self.get_otfgs()
        self.otf.upload_otfg_family([Ti.entry, Sr.entry, O.entry], "STO_FULL",
                                    "TEST", False)
        self.otf.upload_otfg_family([Ti.entry, Sr.entry], "STO_O_missing",
                                    "TEST", False)

        # Missing O but that's OK we have a C9 wild card here
        self.otf.upload_otfg_family([Ti.entry, Sr.entry, "C9"], "STO_O_C9",
                                    "TEST", False)

        return "STO_FULL", "STO_O_missing", "STO_O_C9"

    def get_otfgs(self):

        Ti, _ = self.otfg.get_or_create(Ti_otfg, store_otfg=False)
        Sr, _ = self.otfg.get_or_create(Sr_otfg, store_otfg=False)
        O, _ = self.otfg.get_or_create(O_otfg, store_otfg=False)
        C9, _ = self.otfg.get_or_create("C9", store_otfg=False)
        return Ti, Sr, O, C9

    @staticmethod
    def get_STO_structure():
        """Return a STO structure"""
        from aiida.plugins import DataFactory
        StructureData = DataFactory("structure")
        a = 3.905

        cell = ((a, 0., 0.), (0., a, 0.), (0., 0., a))
        s = StructureData(cell=cell)
        s.append_atom(position=(0., 0., 0.), symbols=["Sr"])
        s.append_atom(position=(a / 2, a / 2, a / 2), symbols=["Ti"])
        s.append_atom(position=(a / 2, a / 2, 0.), symbols=["O"])
        s.append_atom(position=(a / 2, 0., a / 2), symbols=["O"])
        s.append_atom(position=(0., a / 2, a / 2), symbols=["O"])
        s.label = "STO"
        return s


class TestOTFGData(BaseDataCase):
    def setUp(self):
        self.otfg_nodes = {}

    def test_otfg_split(self):
        element, setting = self.otf.split_otfg_entry(Ti_otfg)
        self.assertEqual(element, "Ti")
        self.assertEqual(setting, "3|1.8|9|10|11|30U:40:31:32(qc=5.5)")

    def test_otfg_create(self):

        element, setting = self.otf.split_otfg_entry(Ti_otfg)
        C9 = self.otfg(otfg_entry="C9")
        self.assertEqual(C9.string, "C9")
        self.assertEqual(C9.element, "LIBRARY")
        C9.store()

        Ti = self.otfg(otfg_entry=Ti_otfg)
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

            # This should fail there are more than one
            Sr4, create = self.otfg.get_or_create("Sr_bla", use_first=False)

        Sr4, create = self.otfg.get_or_create("Sr_bla", use_first=True)

    def test_set_up_family(self):

        Ti, Sr, O, C9 = self.get_otfgs()

        otfgs = [Ti.entry, Sr.entry, C9.entry]
        entry, uploaded = self.otf.upload_otfg_family(otfgs, "Test", "Test")
        self.assertEqual((entry, uploaded), (3, 3))

        # This should fail
        with self.assertRaises(ValidationError):
            entry, uploaded = self.otf.upload_otfg_family(
                otfgs, "Test", "Test")

        entry, uploaded = self.otf.upload_otfg_family([O.entry] + otfgs,
                                                      "Test",
                                                      "Test",
                                                      stop_if_existing=False)

        groups = self.otfg.get_otfg_groups()
        self.assertEqual(len(groups), 1)

        retrieved_entries = [node.entry for node in groups[0].nodes]
        for o in otfgs + [O.entry]:
            self.assertIn(o, retrieved_entries)

    def test_assign_from_structure(self):
        """
        Test using get_pseudos_from_structure
        """

        from aiida_castep.data import get_pseudos_from_structure
        from aiida.common import NotExistent

        self.create_family()
        STO = self.get_STO_structure()

        pseudo_list = get_pseudos_from_structure(STO, "STO_FULL")
        self.assertEqual(pseudo_list["Sr"].entry, Sr_otfg)
        self.assertEqual(pseudo_list["O"].entry, O_otfg)
        self.assertEqual(pseudo_list["Ti"].entry, Ti_otfg)

        with self.assertRaises(NotExistent):
            pseudo_list = get_pseudos_from_structure(STO, "STO_O_missing")

        pseudo_list = get_pseudos_from_structure(STO, "STO_O_C9")
        self.assertEqual(pseudo_list["Sr"].entry, Sr_otfg)
        self.assertEqual(pseudo_list["O"].entry, "C9")
        self.assertEqual(pseudo_list["Ti"].entry, Ti_otfg)

    def create_family(self):
        """Creat families for testsing"""
        Ti, Sr, O, C9 = self.get_otfgs()
        self.otf.upload_otfg_family([Ti.entry, Sr.entry, O.entry], "STO_FULL",
                                    "TEST", False)
        self.otf.upload_otfg_family([Ti.entry, Sr.entry], "STO_O_missing",
                                    "TEST", False)

        # Missing O but that's OK we have a C9 wild card here
        self.otf.upload_otfg_family([Ti.entry, Sr.entry, "C9"], "STO_O_C9",
                                    "TEST", False)

    def get_otfgs(self):

        Ti, _ = self.otfg.get_or_create(Ti_otfg, store_otfg=False)
        Sr, _ = self.otfg.get_or_create(Sr_otfg, store_otfg=False)
        O, _ = self.otfg.get_or_create(O_otfg, store_otfg=False)
        C9, _ = self.otfg.get_or_create("C9", store_otfg=False)
        return Ti, Sr, O, C9


class TestUspData(BaseDataCase):
    def upload_usp_family(self):
        """Make a fake usp node"""

        with SandboxFolder() as f:
            sub = f.get_subfolder("pseudo", create=True)
            for element in ["Sr", "Ti", "O"]:
                fp = io.StringIO(u"foo bla 42")
                sub.create_file_from_filelike(fp,
                                              "{}_00.usp".format(element),
                                              mode='w')

            self.usp.upload_usp_family(os.path.join(f.abspath, "pseudo"),
                                       "STO", "")

            with self.assertRaises(ValueError):
                self.usp.upload_usp_family(os.path.join(f.abspath, "pseudo"),
                                           "STO", "")

    def get_usp_node(self, element):
        """
        Return a node of usp file
        """
        name = "{}_00.usp".format(element)
        with SandboxFolder() as f:
            fp = io.StringIO(u"foo bla 42")
            f.create_file_from_filelike(fp, name, mode='w')
            fpath = os.path.join(f.abspath, name)
            node = self.usp.UspData.get_or_create(fpath)[0]

        return node

    def test_get_or_create(self):
        """Testing the logic or get_or_create"""
        name = "Sr_00.usp"
        with SandboxFolder() as f:
            fp = io.StringIO(u"foo bla 42")
            f.create_file_from_filelike(fp, name, mode='w')
            fpath = os.path.join(f.abspath, name)
            node1, create = self.usp.UspData.get_or_create(fpath)

            self.assertTrue(create)
            self.assertEqual(node1.element, "Sr")

            node2 = self.usp.UspData(file=fpath)
            node2.store()

            # Now having two files - should raise an exception
            with self.assertRaises(ValueError):
                node3, create = self.usp.UspData.get_or_create(fpath,
                                                               use_first=False)

            # This should work now
            node4, create = self.usp.UspData.get_or_create(fpath,
                                                           use_first=True)
            self.assertFalse(create)
            self.assertIn(node4.pk, (node1.pk, node2.pk))

    def test_upload(self):
        self.upload_usp_family()

    def test_assign_from_structure(self):
        """
        Test using get_pseudos_from_structure
        """

        from aiida_castep.data import get_pseudos_from_structure
        from aiida.common import NotExistent

        self.upload_usp_family()
        STO = self.get_STO_structure()

        pseudo_list = get_pseudos_from_structure(STO, "STO")
        for kind in STO.kinds:
            self.assertIn(kind.name, pseudo_list)

        with self.assertRaises(NotExistent):
            STO.append_atom(symbols="Ba", position=(1, 1, 1))
            pseudo_list = get_pseudos_from_structure(STO, "STO")

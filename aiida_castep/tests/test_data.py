"""
Use pytest 
"""
# pylint: disable=unused-import,unused-argument,redefined-outer-name,too-many-function-args,
# pylint: disable=protected-access,abstract-class-instantiated,no-value-for-parameter,unexpected-keyword-arg

import io
import pytest

from aiida.common.exceptions import ValidationError
import os


Ti_otfg = "Ti 3|1.8|9|10|11|30U:40:31:32(qc=5.5)"
Sr_otfg = "Sr 3|2.0|5|6|7|40U:50:41:42"
O_otfg = "O 2|1.1|15|18|20|20:21(qc=7)"

OTFG_COLLECTION = {"Sr": Sr_otfg, "Ti": Ti_otfg, "O": O_otfg}


@pytest.fixture(scope="module")
def otfgdata():
    from aiida.orm import DataFactory
    return DataFactory("castep.otfgdata")


@pytest.fixture(scope="module")
def otfg():
    import aiida_castep.data.otfg as otfg
    return otfg


@pytest.fixture(scope="module")
def imps(aiida_profile):

    class Imports(object):
        from aiida.orm import DataFactory
        import aiida_castep.data.otfg as otfg

    return Imports


def test_otfg_split(new_database, otfg):
    element, setting = otfg.split_otfg_entry(Ti_otfg)
    assert element == "Ti"
    assert setting == "3|1.8|9|10|11|30U:40:31:32(qc=5.5)"


def test_otfg_create(new_database, imps, otfg, otfgdata):
    """
    Test for creating OTFGData notes
    """
    element, setting = otfg.split_otfg_entry(Ti_otfg)
    C9 = otfgdata(string="C9")
    assert C9.string == "C9"
    assert C9.element == "LIBRARY"
    assert C9.entry == "C9"
    C9.store()

    Ti = otfgdata(string=setting, element=element)
    assert Ti.string == setting
    assert Ti.element == element
    assert Ti.entry == Ti_otfg

    Ti.store()

    Sr = otfgdata()
    Sr.set_string(Sr_otfg)
    Sr._del_attr("element")
    with pytest.raises(ValidationError):
        Sr.store()


def test_otfg_get_or_create(new_database, otfg, otfgdata):
    Ti, create = otfgdata.get_or_create(Ti_otfg, store_otfg=False)
    assert create is True

    # Create but not stored do it again should have no change
    Ti, create = otfgdata.get_or_create(Ti_otfg, store_otfg=True)
    assert create is True

    # Now we are simply getting the Ti otfg data
    Ti2, create = otfgdata.get_or_create(Ti_otfg, store_otfg=False)
    assert create is False

    # Should get the stored OTFG entry
    # If using SQLA this Ti should be IS Ti2?
    assert Ti2.uuid == Ti.uuid

    # Using another way should be the same
    Sr = otfgdata()
    Sr.set_element("Sr")
    Sr.set_string("bla")
    Sr.store()

    Sr2, create = otfgdata.get_or_create("Sr bla")
    assert create is False

    # A different OTFG
    Sr3, create = otfgdata.get_or_create("Sr foo")
    assert create is True

    # Check if more than one instance is found in the db
    with pytest.raises(ValueError):
        Sr = otfgdata()
        Sr.set_element("Sr")
        Sr.set_string("bla")
        Sr.store()
        otfgdata.get_or_create("Sr bla", use_first=False)


@pytest.fixture
def otfg_nodes(aiida_profile, otfgdata):
    otfgs = {}
    for symbol in ["Sr", "Ti", "O"]:
        otemp = otfgdata()
        otemp.set_element(symbol)
        otemp.set_string("Foo")
        otfgs[symbol] = otemp

    return otfgs.values()


def test_set_up_family_from_string(new_database, imps,
                                   otfg_nodes, otfgdata):

    text_entries = [n.entry for n in otfg_nodes]
    entry, uploaded = imps.otfg.upload_otfg_family(
        text_entries[:1],
        "Test", "Test")
    assert (entry, uploaded) == (1, 1)

    # Creating duplicated family - should fail
    with pytest.raises(ValidationError):
        entry, uploaded = imps.otfg.upload_otfg_family(
            text_entries
            , "Test", "Test")

    entry, uploaded = imps.otfg.upload_otfg_family(
        text_entries
        , "Test", "Test", stop_if_existing=False)

    assert (entry, uploaded) == (3, 2)

    # Check if they are indeed stored
    groups = otfgdata.get_otfg_groups()
    retrieved_entries = [node.entry for node in groups[0].nodes]

    for txt in text_entries:
        assert txt in retrieved_entries


def test_set_up_family_from_nodes(new_database, otfg, otfg_nodes, otfgdata):

    entry, uploaded = otfg.upload_otfg_family(otfg_nodes[:1],
                                              "Test", "Test",
                                              stop_if_existing=True)

    groups = otfgdata.get_otfg_groups()
    assert len(groups) == 1
    assert len(groups[0].nodes) == 1

    with pytest.raises(ValidationError):
        entry, uploaded = otfg.upload_otfg_family(otfg_nodes,
                                                  "Test", "Test",
                                                  stop_if_existing=True)

    entry, uploaded = otfg.upload_otfg_family(otfg_nodes,
                                                  "Test", "Test",
                                              stop_if_existing=False)
    groups = otfgdata.get_otfg_groups()
    assert len(groups) == 1
    assert len(groups[0].nodes) == 3

    Ce = otfgdata()
    Ce.set_string("Ce BLA")

    entry, uploaded = otfg.upload_otfg_family(otfg_nodes + [Ce],
                                              "Test", "Test",
                                              stop_if_existing=False)

    group = otfgdata.get_otfg_group("Test")

    uuid_in_the_group = [node.uuid for node in group.nodes]
    for o in otfg_nodes + [Ce]:
        assert o.uuid in uuid_in_the_group


def test_assign_from_structure(new_database, OTFG_family_factory):
    """
    Test using get_pseudos_from_structure
    """

    from aiida_castep.data import get_pseudos_from_structure
    from aiida.common.exceptions import NotExistent
    from .utils import get_STO_structure

    OTFG_family_factory([Sr_otfg, Ti_otfg, O_otfg], "STO")

    STO = get_STO_structure()

    pseudo_list = get_pseudos_from_structure(STO, "STO")
    assert pseudo_list["Sr"].entry == OTFG_COLLECTION["Sr"]
    assert pseudo_list["O"].entry == OTFG_COLLECTION["O"]
    assert pseudo_list["Ti"].entry == OTFG_COLLECTION["Ti"]

    with pytest.raises(NotExistent):
        pseudo_list = get_pseudos_from_structure(STO, "STO_O_missing")

    OTFG_family_factory([Sr_otfg, Ti_otfg, O_otfg, "C9"], "STO+C9",
                        stop_if_existing=False)
    STO.append_atom(symbols=["Ce"], position=[0, 0, 0])
    pseudo_list = get_pseudos_from_structure(STO, "STO+C9")
    assert pseudo_list["Sr"].entry == OTFG_COLLECTION["Sr"]
    assert pseudo_list["O"].entry == OTFG_COLLECTION["O"]
    assert pseudo_list["Ti"].entry == OTFG_COLLECTION["Ti"]
    assert pseudo_list["Ce"].entry == "C9"


@pytest.fixture
def usp_folder(new_workdir):
    import os
    for fn in ["Sr_00.usp", "Ti_00.usp", "Ce_00.usp"]:
        with open(os.path.join(new_workdir, fn), "w") as fh:
            fh.write("Bla " + fn)
    return new_workdir


def test_get_or_create(new_database, usp_folder):
    """Testing the logic or get_or_create"""
    import aiida_castep.data.usp as usp
    import os
    fpath = os.path.join(usp_folder, "Sr_00.usp")
    node1, create = usp.UspData.get_or_create(fpath)

    assert create is True
    assert node1.element == "Sr"

    node2 = usp.UspData(file=fpath)
    node2.store()

    # Now having two files - should raise an exception
    with pytest.raises(ValueError):
        node3, create = usp.UspData.get_or_create(fpath,
                                                  use_first=False)

    # This should work now
    node4, create = usp.UspData.get_or_create(fpath,
                                              use_first=True)
    assert create is False
    assert node4.pk in (node1.pk, node2.pk)
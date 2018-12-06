"""
Fixtures for data tests
"""
import pytest
from py import path as ppath

OTFG_COLLECTION = {
    "Ti": "Ti 3|1.8|9|10|11|30U:40:31:32(qc=5.5)",
    "Sr": "Sr 3|2.0|5|6|7|40U:50:41:42",
    "O":  "O 2|1.1|15|18|20|20:21(qc=7)",
}



@pytest.fixture
def castep_param(aiida_profile):
    """
    Return an example  CASTEP paratmer
    """
    param = {"PARAM": {
        "xc_functional": "lda",
        "write_otfg": True,
        "opt_strategy": "speed",
        "basis_precision": "fine"},
             "CELL": {}}
    from aiida.orm import DataFactory
    ParamData = DataFactory("parameter")
    return ParamData(dict=param)

@pytest.fixture
def localhost(aiida_profile, new_workdir):
    """Fixture for a local computer called localhost"""
    # Check whether Aiida uses the new backend interface to create collections.
    if hasattr(aiida_profile, '_backend'):
        from aiida.common import exceptions
        try:
            computer = aiida_profile._backend.computers.get(name='localhost')
        except exceptions.NotExistent:
            computer = aiida_profile._backend.computers.create(
                name='localhost',
                description='description',
                hostname='localhost',
                workdir=new_workdir.strpath,
                transport_type='local',
                scheduler_type='direct',
                enabled_state=True)
        return computer
    else:
        from aiida.orm import Computer
        from aiida.orm.querybuilder import QueryBuilder
        query_builder = QueryBuilder()
        query_builder.append(Computer, tag='comp')
        query_builder.add_filter('comp', {'name': {'==': 'localhost'}})
        query_results = query_builder.all()
        if query_results:
            computer = query_results[0][0]
        else:
            computer = Computer(
                name='localhost',
                description='description',
                hostname='localhost',
                workdir=new_workdir.strpath,
                transport_type='local',
                scheduler_type='direct',
                mpirun_command=[],
                enabled_state=True)
        return computer



@pytest.fixture
def otfg_family():
    """
    Create an OTFG family
    """


@pytest.fixture
def create_otfg_family(aiida_profile):
    """Create families for testsing
    return names of the families"""
    import aiida_castep.data.otfg as otf
    otf.upload_otfg_family(["C9"], "C9",
                           "C9 Family with a LIBRARY C9",
                           stop_if_existing=False)
    otf.upload_otfg_family(OTFG_COLLECTION.values(),
                           "STO",
                           "OTFG strings for STO",
                           stop_if_existing=False)

    otf.upload_otfg_family(OTFG_COLLECTION.values() + ["C9"],
                           "STO+C9",
                           "OTFG strings for STO plug C9 libray for any missing elements",
                           stop_if_existing=False)

    return "C9", "STO", "STO+C9"


@pytest.fixture
def sto_otfgs(create_otfg_family):
    """
    Return a list OTFGData for Sr, Ti and O
    """
    from aiida.orm import DataFactory
    OTFG = DataFactory("castep.otfgdata")
    return OTFG.get_otfg_group("STO")


#WIP
def upload_usp_family(self):
    """Make a fake usp node"""

    with SandboxFolder() as f:
        sub = f.get_subfolder("pseudo", create=True)
        for element in ["Sr", "Ti", "O"]:
            fp = io.StringIO(u"foo bla 42")
            sub.create_file_from_filelike(fp, "{}_00.usp".format(element))

        self.usp.upload_usp_family(os.path.join(f.abspath, "pseudo"), "STO", "")

        with self.assertRaises(ValueError):
            self.usp.upload_usp_family(os.path.join(f.abspath, "pseudo"), "STO", "")


#RETURN usp node
def get_usp_node(self, element):
    """
    Return a node of usp file
    """
    name = "{}_00.usp".format(element)
    with SandboxFolder() as f:
        fp = io.StringIO(u"foo bla 42")
        f.create_file_from_filelike(fp, name)
        fpath = os.path.join(f.abspath, name)
        node = self.usp.UspData.get_or_create(fpath)[0]

    return node



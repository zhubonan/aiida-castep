"""
Test parsing data
"""
from __future__ import print_function
from __future__ import absolute_import
import pytest

try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path

import os

@pytest.fixture(scope="class")
def import_things(aiida_profile, request):

    from aiida.plugins import DataFactory, CalculationFactory
    FolderData = DataFactory("folder")
    for k, v in locals().items():
        setattr(request.cls, k, v)


@pytest.mark.usefixtures("import_things", "aiida_profile")
class TestCastepParser(object):
    def get_data_abs_path(self):
        test_moudule = os.path.split(__file__)[0]
        data_folder = os.path.join(test_moudule, "data")
        return data_folder

    def get_dummy_outputs(self):

        retrieved = {}
        for folder in ["H2-geom", "O2-geom-spin", "Si-geom-stress", "N2-md"]:
            folderdata = self.FolderData()
            folderdata.replace_with_folder(
                os.path.join(self.get_data_abs_path(), folder))
            retrieved[folder] = dict(retrieved=folderdata)
        return retrieved


    @pytest.mark.skip('Needs to be migrated')
    def test_parser_retrieved(self, db_test_app,
                              sto_calculation):
        from .utils import get_x2_structure
        from aiida_castep.parsers.castep import CastepParser

        calc = sto_calculation

        parser = CastepParser(calc)
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
            assert "total_energy" in  out_param_dict
            assert "unit_energy" in  out_param_dict
            assert out_param_dict["unit_energy"] == "eV"
            # Check if the label is correctly copied
            assert calc.inp.structure.label == out_structure.label

            # Check the length of sites are consistent
            assert len(out_structure.sites) == len(out_traj.get_symbols())

            for k in common_keys:
                assert k in out_traj.get_arraynames()

            if name == "O2-geom-spin" or name == "Si-geom-stress":
                assert parser.get_linkname_outbands() in out
                bands = out[parser.get_linkname_outbands()]

                # Check if spins are handled correctly
                assert bands.get_attr('nspins') in [1, 2]
                if bands.get_attr('nspins') == 1:
                    assert bands.get_attr('nkpts') == len(bands.get_bands())
                elif bands.get_attr('nspins') == 2:
                    assert bands.get_attr('nkpts') == len(bands.get_bands()[0])

                for k in geom_keys:
                    assert k in out_traj.get_arraynames()

            if name == "N2-md":
                for k in md_keys:
                    assert k in out_traj.get_arraynames()


class TestPot1DParser(object):

    @pytest.mark.skip('not re-implemented')
    def test_load_plugin(self):
        from aiida.parsers import ParserFactory
        Pot1dParser = ParserFactory("castep.pot1d")

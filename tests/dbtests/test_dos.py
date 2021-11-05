"""
Test the DOS generation function
"""
import pytest

from aiida.orm import Float, Int
from aiida_castep.common import OUTPUT_LINKNAMES as ln_name
from aiida_castep.workflows.bands import dos_from_bands

from ..utils import get_x2_structure
folders = ["H2-geom", "O2-geom-spin", "Si-geom-stress", "N2-md"]

# pylint:disable=import-outside-toplevel


def test_dos_calc(db_test_app, generate_parser, generate_calc_job_node,
                  sto_calc_inputs):
    """
    Iterate through internal test cases.
    Check if the results are parsed correctly.
    """

    output_folder = "Si-geom-stress"

    inputs = sto_calc_inputs

    # Swap the correct structure to allow desort to work
    inputs = sto_calc_inputs
    inputs.structure = get_x2_structure("Si")
    parser = generate_parser('castep.castep')
    node = generate_calc_job_node('castep.castep', output_folder, inputs)

    out, _ = parser.parse_from_node(node, store_provenance=False)

    bands = out.get(ln_name['bands'], None)

    # Compute dos
    dos = dos_from_bands(bands, Float(0.05), Int(1000))
    xname, xval, xunit = dos.get_x()
    assert xval.shape == (1000, )
    assert xname == "Energy"
    assert xunit == "eV"

    yname, yval, yunit = dos.get_y()[
        0]  # Returns a list of (yname, yval, yunit)
    assert yval.shape == (1000, )
    assert yname == "DOS_SPIN_0"
    assert yunit == "eV^-1"

    efermi = dos.get_attribute("fermi_energy")
    mask = xval < efermi
    sumval = (yval[mask].sum() * (xval[1] - xval[0]))
    assert sumval == pytest.approx(4.0, 1e-4)

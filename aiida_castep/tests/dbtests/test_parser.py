"""
Test the parsers that interacte with the AiiDA database.
Check if various AiiDA types are created correctly.
"""

from __future__ import absolute_import
import six
import pytest
from aiida_castep.common import OUTPUT_LINKNAMES

ln_name = OUTPUT_LINKNAMES

folders = ["H2-geom", "O2-geom-spin", "Si-geom-stress", "N2-md"]


def test_parsing_base(
        new_database,
        db_test_app,
        generate_calc_job_node,
        generate_parser,
        h2_calc_inputs,
):
    """
    Test basic parsing
    """

    node = generate_calc_job_node(
        'castep.castep',
        'H2-geom',
        inputs=h2_calc_inputs,
    )
    parser = generate_parser('castep.castep')
    results, return_node = parser.parse_from_node(node, store_provenance=False)
    assert return_node.exit_status == 0

    calc_energy = results['output_parameters'].get_dict()['total_energy']
    ref = -31.69654969917
    assert calc_energy == ref


def test_parse_warnings(
        new_database,
        db_test_app,
        generate_calc_job_node,
        generate_parser,
        h2_calc_inputs,
):
    """
    Test basic parsing
    """
    from aiida_castep.common import EXIT_CODES_SPEC as CODES

    node = generate_calc_job_node(
        'castep.castep',
        'H2-geom',
        inputs=h2_calc_inputs,
    )
    parser = generate_parser('castep.castep')

    folder = node.outputs.retrieved
    content_orig = folder.get_object_content('aiida.castep').split('\n')
    content = content_orig[:-20]
    content.append('Insufficient time for another iteration')
    with node.outputs.retrieved.open('aiida.castep', 'w') as fh:
        fh.write('\n'.join(content))
    results, return_node = parser.parse_from_node(node, store_provenance=False)
    assert return_node.exit_status == CODES['ERROR_TIMELIMIT_REACHED'][0]

    content.append(
        'SCF cycles performed but system has not reached the groundstate')
    with node.outputs.retrieved.open('aiida.castep', 'w') as fh:
        fh.write('\n'.join(content))
    results, return_node = parser.parse_from_node(node, store_provenance=False)
    assert return_node.exit_status == CODES['ERROR_SCF_NOT_CONVERGED'][0]

    node.outputs.retrieved.delete_object('aiida.castep', force=True)
    results, return_node = parser.parse_from_node(node, store_provenance=False)
    assert return_node.exit_status == CODES['ERROR_NO_OUTPUT_FILE'][0]


def test_parse_errs(
        new_database,
        db_test_app,
        generate_calc_job_node,
        generate_parser,
        h2_calc_inputs,
):
    """
    Test basic parsing
    """
    from aiida_castep.common import EXIT_CODES_SPEC as CODES
    from io import StringIO

    node = generate_calc_job_node(
        'castep.castep',
        'H2-geom',
        inputs=h2_calc_inputs,
    )
    parser = generate_parser('castep.castep')

    folder = node.outputs.retrieved

    error_string = u'Error Message\nError'
    err_handle = StringIO(error_string)
    folder.put_object_from_filelike(err_handle, 'aiida.0001.err', force=True)
    results, return_node = parser.parse_from_node(node, store_provenance=False)
    assert return_node.exit_status == CODES['ERROR_CASTEP_ERROR'][0]


def test_parsing_geom(new_database, db_test_app, generate_calc_job_node,
                      generate_parser, h2_calc_inputs):
    """
    Test if geom is converted to trajectory data
    """
    from aiida_castep.calculations.castep import CastepCalculation
    node = generate_calc_job_node('castep.castep',
                                  'H2-geom',
                                  inputs=h2_calc_inputs,
                                  computer=db_test_app.localhost)
    parser = generate_parser('castep.castep')
    results, _ = parser.parse_from_node(node, store_provenance=False)
    assert 'forces' in results['output_trajectory'].get_arraynames()


@pytest.mark.parametrize('output_folder', folders)
def test_parser_retrieved(db_test_app, output_folder, generate_parser,
                          generate_calc_job_node, sto_calc_inputs):
    """
    Iterate through internal test cases.
    Check if the results are parsed correctly.
    """
    from aiida_castep.tests.utils import get_x2_structure

    common_keys = [
        "cells", "positions", "forces", "symbols", "geom_total_energy"
    ]
    md_keys = [
        "hamilt_energy", "kinetic_energy", "velocities", "temperatures",
        "times"
    ]
    geom_keys = ["geom_enthalpy"]

    inputs = sto_calc_inputs

    if 'O2' in output_folder:
        xtemp = 'O'
    elif 'Si' in output_folder:
        xtemp = 'Si'
    elif 'N2' in output_folder:
        xtemp = 'N'
    elif 'H2' in output_folder:
        xtemp = 'H'

    # Swap the correct structure to allow desort to work
    inputs.structure = get_x2_structure(xtemp)
    parser = generate_parser('castep.castep')
    node = generate_calc_job_node('castep.castep', output_folder, inputs)

    out, _ = parser.parse_from_node(node, store_provenance=False)

    out_structure = out[ln_name['structure']]
    out_param_dict = out[ln_name['results']].get_dict()
    out_traj = out[ln_name['trajectory']]

    assert "total_energy" in out_param_dict
    assert "unit_energy" in out_param_dict
    assert out_param_dict["unit_energy"] == "eV"
    # Check if the label is correctly copied
    assert node.inputs.structure.label == out_structure.label

    # Check the length of sites are consistent
    assert len(out_structure.sites) == len(out_traj.symbols)

    for k in common_keys:
        assert k in out_traj.get_arraynames()

    if output_folder == "O2-geom-spin" or output_folder == "Si-geom-stress":
        bands = out.get(ln_name['bands'], None)
        assert bands is not None

        # Check if spins are handled correctly
        assert bands.get_attribute('nspins') in [1, 2]
        if bands.get_attribute('nspins') == 1:
            assert bands.get_attribute('nkpts') == len(bands.get_bands())
        elif bands.get_attribute('nspins') == 2:
            assert bands.get_attribute('nkpts') == len(bands.get_bands()[0])

        for k in geom_keys:
            assert k in out_traj.get_arraynames()

    if output_folder == "N2-md":
        for k in md_keys:
            assert k in out_traj.get_arraynames()

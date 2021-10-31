"""
Constants for unit conversion
"""

# pylint: disable=invalid-name

# NOTE one day we should allow the CODATA sets to be selected

# CODATA1986 (included herein for the sake of completeness)
# taken from
#    http://physics.nist.gov/cuu/Archive/1986RMP.pdf
units_CODATA1986 = {
    'hbar': 6.5821220E-16,  # eVs
    'Eh': 27.2113961,  # eV
    'kB': 8.617385E-5,  # eV/K
    'a0': 0.529177249,  # A
    'c': 299792458,  # m/s
    'e': 1.60217733E-19,  # C
    'me': 5.485799110E-4
}  # u

# CODATA2002: default in CASTEP 5.01
# (-> check in more recent CASTEP in case of numerical discrepancies?!)
# taken from
#    http://physics.nist.gov/cuu/Document/all_2002.pdf

units_CODATA2002 = {
    'hbar': 6.58211915E-16,  # eVs
    'Eh': 27.2113845,  # eV
    'kB': 8.617343E-5,  # eV/K
    'a0': 0.5291772108,  # A
    'c': 299792458,  # m/s
    'e': 1.60217653E-19,  # C
    'me': 5.4857990945E-4
}  # u

units_CODATA2010 = {
    'c': 299792458,
    'hbar': 6.58211928e-16,  # eV
    'e': 1.602176565e-19,  # C
    'Av': 6.02214129e23,  # Avogadro constant
    'R': 8.3144621,  # Gas constrant
    'Eh': 27.21138505,  # eV
    'a0': 0.52917721092,  # A - bohr radius
    'me': 5.4857990946e-4,  # u
    'kB': 8.6173324E-5  # eV/K
}

# (common) derived entries
for d in (units_CODATA1986, units_CODATA2002, units_CODATA2010):
    d['t0'] = d['hbar'] / d['Eh']  # s
    d['Pascal'] = d['e'] * 1E30  # Pa
units = units_CODATA2010

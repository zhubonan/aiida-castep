
from aiida_castep.parsers.raw_dot_castep_parser import (parse_castep_text_output,
parse_raw_ouput)

with open("example_scripts/H2-geom/H2.castep") as f:
    lines = f.readlines()

res = parse_castep_text_output(lines, None)
print(res)

outs = parse_raw_ouput("example_scripts/H2-geom/H2.castep", None)
print(outs)

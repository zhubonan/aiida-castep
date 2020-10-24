"""
Classes for .param and .cell files
"""
from __future__ import absolute_import
from collections import OrderedDict


class CastepInputFile(OrderedDict):
    """
    Class for storing key - values pairs of CASTEP inputs
    This class can be used for .param, .cell and also other CASTEP style
    inputs such as OptaDos's odi file

    ``self.get_file_lines`` is used for getting a list of strings as
    lines to be written to the file

    ``self.get_string`` is used for getting the content to be passed
    to ``write`` function of a file-like object

    sepecial properties:
    * ``header`` a list of lines to be put into the header
    * ``units`` a dictionary of the units
    """
    def __init__(self, *args, **kwargs):
        super(CastepInputFile, self).__init__(*args, **kwargs)
        self.header = []
        self.units = {}

    def get_file_lines(self):
        """
        Return a list of strings to be write out to the files
        """
        lines = []
        for head in self.header:
            if not head.startswith("#"):
                lines.append("# " + head)
            else:
                lines.append(head)

        for key, value in self.items():
            if isinstance(value, (tuple, list)):
                lines.append("%BLOCK {}".format(key))
                if key in self.units:
                    lines.append("{}".format(self.units[key]))
                for tmp in value:
                    lines.append(tmp)
                lines.append("%ENDBLOCK {}".format(key))
            else:
                line = "{:<20}: {}".format(key, value)
                if key in self.units:
                    line = line + " " + self.units[key]
                lines.append(line)

        return lines

    def get_string(self):
        return "\n".join(self.get_file_lines())


class ParamFile(CastepInputFile):
    pass


class CellFile(CastepInputFile):
    pass

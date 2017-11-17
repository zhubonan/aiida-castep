"""
CASTEP HELPER
Check for errorer in input dictionary
{"CELL": {...},
 "PARAM": {...}
"""

import os
import subprocess
import json
from .generate import construct_full_dict

path = os.path.abspath(__file__)
module_path = os.path.dirname(path)


class CastepHelper(object):
    """
    A class for helping castep inputs
    """
    _HELP_DICT = None

    def __init__(self):
        self.load_helper_dict()

    def load_helper_dict(self):
        file_path = os.path.join(module_path, "castep_helpinfo.json")
        if os.path.isfile(file_path):
            with open(file_path) as f:
                try:
                    help_dict = json.load(f)
                except Exception as e:
                    print("JSON file at {} is invalid".format(file_path))
                    raise e
        else:
            help_dict = self.construct_helper_dict()
            self.save_helper_dict(help_dict, file_path)
            # now try to save into the module directory

        # Save the help_dict as a class attribute
        CastepHelper._HELP_DICT = help_dict

    @property
    def help_dict(self):
        return CastepHelper._HELP_DICT

    @property
    def castep_version(self):
        """Version number of CASTEP that the help is for"""
        return self.help_dict["_CASTEP_VERSION"]

    def save_helper_dict(self, help_dict, file_path):
        """
        Save the helper json file in to sensible location. By default it is here this module is
        """

        try:
            with open(file_path, "w") as fp:
                json.dump(help_dict, fp)
        except OSError:
            try:
                with("castep_helpinfo.json", "w") as fp:
                    json.dump(help_dict, fp)
                    file_path = os.path.realpath("castep_helpinfo.json")
                    print("Saving in current path. "
                      "Please move it to {}".format(file_path))
            except OSError:
                print("Cannot save the retrieved help information")
                return

        print("\n\nJSON file saved in {}".format(file_path))

    def construct_helper_dict(self):
        """Construct the dictionary if not exists"""
        return construct_full_dict()

    def check_dict(self, input_dict):
        invalid_keys = []
        wrong_keys = []

        for kwtype in input_dict:
            # Check each key
            for key in input_dict[kwtype]:
                # key maybe be both lower or upper case
                info = self.help_dict.get(key.lower(), None)

                if info is None:
                    invalid_keys.append(key)
                    continue

                # Check if the type is correct
                if info["key_type"] != kwtype:
                    wrong_keys.append(key)
                    continue

        return invalid_keys, wrong_keys




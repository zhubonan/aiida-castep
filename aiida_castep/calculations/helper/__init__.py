"""
CASTEP HELPER
Check for errorer in input dictionary
{"CELL": {...},
 "PARAM": {...}

 # TODO allow this to use without castep
"""

import os
import subprocess
import json
from .generate import construct_full_dict

import logging
logger = logging.getLogger("aiida")

path = os.path.abspath(__file__)
module_path = os.path.dirname(path)



class HelperCheckError(RuntimeError):
    pass


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

    def _check_dict(self, input_dict):
        """
        Check a dictionary of inputs. Return invalid and wrong keys
        :returns list invalid_keys: a list of in valid keys
        :returns list wrong_keys: a list of tuples (key, "PARAM" OR "CELL")
        of where the key should have been put
        """
        invalid_keys = []
        wrong_keys = [] # a list of tulple (key, "PARAM") or (key, "CELL")

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
                    wrong_keys.append((key, info["key_type"]))
                    continue

        return invalid_keys, wrong_keys

    def _from_flat_dict(self, input_dict):
        """Construct a {"PARAM":{}, "CELL":{}} dictionary from a flat dictionary"""

        hinfo = self.help_dict

        # Check if we are indeed dealing with a flat dictionary
        assert "PARAM" not in input_dict and "CELL" not in input_dict

        cell_dict  = {}
        param_dict = {}
        not_found = []
        for key in input_dict:
            key_entry = hinfo.get(key, None)

            if key_entry is None:
                not_found.append(key)
            else:
                kwtype = key_entry.get("key_type")
                if kwtype == "CELL":
                    cell_dict.update({key: input_dict[key]})
                elif kwtype == "PARAM":
                    param_dict.update({key: input_dict[key]})
                else:
                    raise RuntimeError("Entry {} does not have key_type value".format(key))

        out_dict = {"CELL": cell_dict, "PARAM": param_dict}
        return out_dict, not_found

    def check_dict(self, input_dict, auto_fix=True):
        """
        Check input dictionary. Apply and warn about errors
        :param input_dict dicionary: a dictionary as the input, contain "CELL", "PARAM" and other keywords
        :param auto_fix bool: Wethere we should fix error automatically

        :returns dict: A fixed dictionary
        """
        input_dict = input_dict.copy() # this is a shallow copy

        # constuct what to be checked
        cell_dict = input_dict.pop("CELL", {})
        param_dict = input_dict.pop("PARAM", {})

        if input_dict and not auto_fix:
            raise HelperCheckError("keywords: {} at top level".format(", ".join(input_dict)))

        # process what's left
        re_structured, not_found = self._from_flat_dict(input_dict)
        if not_found:
            raise HelperCheckError("keywords: {} at top level are not recognized".format(", ".join(not_found)))

        # Now constuct a dictionary
        cell_dict.update(re_structured["CELL"])
        param_dict.update(re_structured["PARAM"])

        input_dict = dict(CELL=cell_dict, PARAM=param_dict)

        # Check the final dictionary
        invalid, wrong = self._check_dict(input_dict)

        if invalid:
            suggests = [self.get_suggestion(s) for s in invalid]
            not_founds = ["keyword {} is not found".format(s) for s in invalid]
            sugst_str = [ a + "\n" + b for a, b in zip(not_founds, suggests)]
            sugst_str = "\n\n".join(sugst_str)

            raise HelperCheckError(sugst_str)

        # if there are still wrong keywords, fix them
        if wrong:
            if auto_fix is True:
                for key, should_be in wrong:
                    if should_be == "PARAM":
                        logger.warning("Key {} moved to PARAM".format(key))
                        value = input_dict["CELL"].pop(key)
                        input_dict["PARAM"].update({key: value})
                    else:
                        logger.warning("Key {} moved to CELL".format(key))
                        value = input_dict["PARAM"].pop(key)
                        input_dict["CELL"].update({key: value})
            else:
                raise HelperCheckError("keywords: {} are in the wrong file".format(", ".join([k[0] for k in wrong])))
        return input_dict

    def get_suggestion(self, string):
        """
        Return string for suggestion of the string
        """
        return _get_suggestion(string, self.help_dict.keys())




def _get_suggestion(provided_string, allowed_strings):
    """
    Given a string and a list of allowed_strings, it returns a string to print
    on screen, with sensible text depending on whether no suggestion is found,
    or one or more than one suggestions are found.

    Args:
        provided_string: the string to compare
        allowed_strings: a list of valid strings

    Returns:
        A string to print on output, to suggest to the user a possible valid
        value.
    """
    import difflib

    similar_kws = difflib.get_close_matches(provided_string,
                                            allowed_strings)
    if len(similar_kws) == 1:
        return "(Maybe you wanted to specify {0}?)".format(similar_kws[0])
    elif len(similar_kws) > 1:
        return "(Maybe you wanted to specify one of these: {0}?)".format(
            ", ".join(similar_kws))
    else:
        return "(No similar keywords found...)"




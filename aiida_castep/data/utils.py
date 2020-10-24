"""
Utilities module
This module does not have top level AiiDA orm imports
"""
from __future__ import absolute_import
import re
import os


def split_otfg_entry(otfg):
    """
    Split an entry of otfg in the form of element_settings
    :returns (element, entry):
    """
    otfg = otfg.strip()
    # Check it is a library
    lib = re.match(r'^[A-Za-z]+\d+$', otfg)
    if lib:
        element = "LIBRARY"
        return element, otfg

    # It not a library, try to get the element
    match = re.match(r"^([A-Z][a-z]?)[ _]+(.+)$", otfg)
    if match:
        element, setting = match.group(1), match.group(2)
    else:
        element = None
        setting = otfg

    return element, setting


def get_usp_element(filepath):
    """
    infer element from usp/recpot filename
    :return element: a string of element name or None if not found
    """
    # Convert to string -> allow Path object to be passed
    filepath = str(filepath)
    re_fn = re.compile(r"^([a-z]+)[_-].+\.(usp|recpot)$", flags=re.IGNORECASE)
    filename = os.path.split(filepath)[1]
    match = re_fn.match(filename)
    if match:
        element = match.group(1)
        element = element.capitalize()
        return element
    return None

"""
Storing OTFG configuration as Data nodes
"""
import re
from aiida.orm import Data
from aiida.common.utils import classproperty
from aiida.common.exceptions import ValidationError

OTFGGROUP_TYPE = "data.castep.otfg.family"



def upload_otfg_family(entries,
                       group_name,
                       group_description,
                       stop_if_existing=True):
    """
    Set a family for the OTFG pseudo potential strings
    """
    from aiida.orm import Group
    from aiida.common.exceptions import UniquenessError, NotExistent
    from aiida.orm.querybuilder import QueryBuilder
    from aiida.common import aiidalogger

    # Try to retrieve a group if it exists
    try:
        group = Group.get(name=group_name, type_string=OTFGGROUP_TYPE)
        group_created = False
    except NotExistent:
        group = Group(
            name=group_name,
            type_string=OTFGGROUP_TYPE,
            )
        group_created = True

    group.description = group_description

    otfg_and_created = []
    nentries = len(entries)

    for s in entries:
        # Add it if it is just one existing data
        if isinstance(s, OTFGData):
            element, setting = s.element, s.string
        else:
            element, setting = split_otfg_entry(s)

        qb = QueryBuilder()
        qb.append(
            OTFGData,
            filters={
                'attributes.otfg_string': {
                    "==": setting
                },
                'attributes.element': {
                    "==": element
                }
            })
        existing_otfg = qb.first()

        if existing_otfg is None:

            if isinstance(s, OTFGData):
                otfg_and_created.append((s, True))
            else:
                otfg, created = OTFGData.get_or_create(
                    s, use_first=True, store_otfg=False)
                otfg_and_created.append((otfg, created))

        else:
            if stop_if_existing:
                raise ValidationError(
                    "A OTFG group cannot be added when stop_if_existing is True"
                )
            existing_otfg = existing_otfg[0]
            otfg_and_created.append((existing_otfg, False))

    # Check for unique for the complete group
    elements = [(i[0].element, i[0].string) for i in otfg_and_created]

    # Add other entries for the list to check
    if not group_created:
        for aiida_n in group.nodes:
            if not isinstance(aiida_n, OTFGData):
                continue
            elements.append((aiida_n.element, aiida_n.string))

    # Discard duplicated pairs
    elements = set(elements)
    elements_names = [e[0] for e in elements]

    # Check the uniqueness of the complete group
    if not len(elements_names) == len(set(elements_names)):
        duplicates = set(
            [x for x in elements_names if elements_names.count(x) > 1])
        dup_string = ", ".join(duplicates)
        raise UniquenessError("More than one OTFG found for the elements: " +
                              dup_string + ".")

    # If we survive here uniqueness is fine

    # Save the group
    if group_created:
        group.store()

    # Save the OTFG in the database if necessary and add them to the group

    for otfg, created in otfg_and_created:
        if created:
            otfg.store()
            aiidalogger.debug("New node {} created for OTFG string {}".format(
                otfg.uuid, otfg.string))
        else:
            aiidalogger.debug("Reusing node {} for OTFG string {}".format(
                otfg.uuid, otfg.string))

    group.add_nodes(otfg for otfg, _ in otfg_and_created)

    nuploaded = len([_ for _, created in otfg_and_created if created])

    return nentries, nuploaded


class OTFGData(Data):
    """
    Class representing an OTFG configuration

    attributes:
    string: string to be put into the cell file
    element: element that this setting is for - may not exist if we are dealing with a library.
    """

    @classmethod
    def get_or_create(cls, otfg_entry, use_first=False, store_otfg=True):
        """
        Create or retrieve OTFG from database
        :param otfg_entry: CASTEP styled OTFG entry.
        Can either be the name of library (e.g C9) or the full specification with element like:
        "O 2|1.1|15|18|20|20:21(qc=7)"

        The created OTFGData node will by default labelled by the fully entry.
        """

        in_db = cls.from_entry(otfg_entry)

        element, setting = split_otfg_entry(otfg_entry)
        if len(in_db) == 0:
            if store_otfg:
                instance = cls(string=setting, element=element).store()
            else:
                instance = cls(string=setting, element=element)
            # Automatically set the label
            instance.label = otfg_entry
            return (instance, True)

        else:
            if len(in_db) > 1:
                if use_first:
                    return (in_db[0], False)
                else:
                    pks = ", ".join([str(i.pk) for i in in_db])
                    raise ValueError(
                        "More than one duplicated OTFG data has been found. pks={}"
                        .format(pks))
            else:
                return (in_db[0], False)

    def set_string(self, otfg_string):
        """Set the full string of OTFGData instance"""
        if self.element is None:
            self.set_element("LIBRARY")
        self._set_attr("otfg_string", str(otfg_string))

    def set_element(self, element):
        """Set the element of OTFGData instance"""
        self._set_attr("element", str(element))

    def store(self, *args, **kwargs):
        self._validate()
        return super(OTFGData, self).store(*args, **kwargs)

    @property
    def string(self):
        return self.get_attr('otfg_string', None)

    @property
    def element(self):
        """Element of the OTFG. May not be available"""
        return self.get_attr('element', None)

    @property
    def entry(self):
        """Plain format of the OTFG"""
        string = self.string
        element = self.element
        if element is None or element == "LIBRARY":
            return string

        else:
            return element + " " + string

    @classmethod
    def from_entry(cls, entry):
        """
        Return a list of OTFG that matches with the string
        """

        from aiida.orm.querybuilder import QueryBuilder

        element, string = split_otfg_entry(entry)
        qb = QueryBuilder()
        qb.append(
            cls,
            filters={
                'attributes.otfg_string': {
                    '==': string
                },
                'attributes.element': {
                    '==': element
                }
            })

        return [i[0] for i in qb.all()]

    def _validate(self):
        """Validate the format of OTFG configuration"""
        super(OTFGData, self)._validate()
        if self.element is None:
            raise ValidationError("The value of element is not set. "
                                  "Set it to 'LIBRARY' manually to indicate. "
                                  "This is a library")

    @classproperty
    def otfg_family_type_string(cls):
        return OTFGGROUP_TYPE

    @classmethod
    def get_otfg_group(cls, group_name):
        """
        Return the OTFGData group with the given name.
        """
        from aiida.orm import Group

        return Group.get(
            name=group_name, type_string=cls.otfg_family_type_string)

    @classmethod
    def get_otfg_groups(cls, filter_elements=None, user=None):
        """
        Return all names of groups of type otfg, possibly with some filters.

        :param filter_elements: A string or a list of strings.
               If present, returns only the groups that contains one Usp for
               every element present in the list. Default=None, meaning that
               all families are returned.
        :param user: if None (default), return the groups for all users.
               If defined, it should be either a DbUser instance, or a string
               for the user name (that is, the user email).
        """

        from aiida.orm import Group

        group_query_params = {"type_string": cls.otfg_family_type_string}

        if user is not None:
            group_query_params['user'] = user

        if isinstance(filter_elements, basestring):
            filter_elements = [filter_elements]

        if filter_elements is not None:
            actual_filter_elements = {_.capitalize() for _ in filter_elements}
            # LIBRARY is a wild card
            actual_filter_elements.add("LBIRARY")

            group_query_params['node_attributes'] = {
                'element': actual_filter_elements
            }

        all_usp_groups = Group.query(**group_query_params)

        groups = [(g.name, g) for g in all_usp_groups]
        # Sort by name
        groups.sort()
        # Return the groups, without name
        return [_[1] for _ in groups]


def split_otfg_entry(otfg):
    """
    Split an entry of otfg in the form of element_settings
    :returns (element, entry):
    """
    otfg = otfg.strip()
    try:
        element, setting = re.split("[ _]+", otfg, 1)
    # Incase I pass a library e.g C9
    except ValueError:
        element = "LIBRARY"
        setting = otfg

    return element, setting

"""
Storing OTFG configuration as Data nodes
"""
from __future__ import absolute_import
from __future__ import print_function
import re
from aiida.orm import Data, Group, QueryBuilder
from aiida.common.utils import classproperty
from aiida.common import ValidationError
from .utils import split_otfg_entry
from .usp import UspData
import six

OLD_OTFGGROUP_TYPE = "data.castep.otfg.family"
OTFGGROUP_TYPE = "castep.otfg"


class OTFGGroup(Group):
    """Class representing an OTFGGroup"""


def migrate_otfg_family():
    """Migrate the old OTFG families to new families"""
    old_types = [OLD_OTFGGROUP_TYPE, "data.castep.usp.family"]
    q = QueryBuilder()
    q.append(Group, filters={'type_string': {'in': old_types}})

    migrated = []
    created = []
    for (old_group, ) in q.iterall():
        new_group, created = OTFGGroup.objects.get_or_create(
            label=old_group.label, description=old_group.description)
        new_group.add_nodes(list(old_group.nodes))
        new_group.store()
        migrated.append(new_group.label)
        if created:
            print("Created new style Group for <{}>".format(old_group.label))
        else:
            print(("Adding nodes to existing group <{}>".format(
                old_group.label)))

    return


def upload_otfg_family(entries,
                       group_label,
                       group_description,
                       stop_if_existing=True):
    """
    Set a family for the OTFG pseudo potential strings
    """
    from aiida.common import UniquenessError, NotExistent
    from aiida.orm.querybuilder import QueryBuilder
    #from aiida.common import aiidalogger

    # Try to retrieve a group if it exists
    try:
        group = OTFGGroup.get(label=group_label)
        group_created = False
    except NotExistent:
        group = OTFGGroup(label=group_label, )
        group_created = True

    group.description = group_description

    otfg_and_created = []
    nentries = len(entries)

    for entry in entries:
        # Add it if it is just one existing data
        if isinstance(entry, OTFGData):
            element, setting = entry.element, entry.string
        elif isinstance(entry, str):
            element, setting = split_otfg_entry(entry)
        elif isinstance(entry, UspData):
            element, setting = entry.element, entry.md5sum

        qb = QueryBuilder()
        qb.append(OTFGData,
                  filters={
                      'attributes.otfg_entry': {
                          "==": setting
                      },
                      'attributes.element': {
                          "==": element
                      }
                  })
        existing_otfg = qb.first()

        # Try find Usp data
        if existing_otfg is None:

            qb = QueryBuilder()
            qb.append(UspData,
                      filters={
                          'attributes.md5sum': {
                              "==": setting
                          },
                          'attributes.element': {
                              "==": element
                          }
                      })
            existing_otfg = qb.first()

        # Act based on wether the data exists
        if existing_otfg is None:

            if isinstance(entry, OTFGData):
                otfg_and_created.append((entry, True))
            elif isinstance(entry, str):
                otfg, created = OTFGData.get_or_create(entry,
                                                       use_first=True,
                                                       store_otfg=False)
                otfg_and_created.append((otfg, created))
            elif isinstance(entry, UspData):
                otfg_and_created.append((entry, True))

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
            if not isinstance(aiida_n, (OTFGData, UspData)):
                print(("Warning: unsupported node: {}".format(aiida_n)))
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
        raise UniquenessError("More than one Nodes found for the elements: " +
                              dup_string + ".")

    # If we survive here uniqueness is fine

    # Save the group - note we have not added the nodes yet
    if group_created:
        group.store()

    # Save the OTFG in the database if necessary and add them to the group

    for otfg, created in otfg_and_created:
        if created:
            otfg.store()
        else:
            pass

    nodes_add = [otfg for otfg, created in otfg_and_created]
    nodes_new = [otfg for otfg, created in otfg_and_created if created is True]
    group.add_nodes(nodes_add)

    return nentries, len(nodes_new)


class OTFGData(Data):
    """
    Class representing an OTFG configuration

    attributes:
    string: string to be put into the cell file
    element: element that this setting is for - may not exist if we are dealing with a library.
    """
    def __init__(self, **kwargs):
        """
        Store a string for on-the-fly generation of pseudopoentials

        :param otfg_entry str: a string specifying the generation.
        The element this  potential is for can also be included.
        For example: 'O 2|1.1|15|18|20|20:21(qc=7)'
        """
        otfg_entry = kwargs.pop('otfg_entry', None)
        super(OTFGData, self).__init__(**kwargs)
        if otfg_entry:
            element, entry = split_otfg_entry(otfg_entry)
            self.set_string(entry)
            if element:
                self.set_element(element)

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

        # No existing entry
        if len(in_db) == 0:
            instance = cls(otfg_entry=otfg_entry)
            if store_otfg:
                instance.store()

            # Automatically set the label
            instance.label = otfg_entry
            return (instance, True)

        # There is a existing identical enetry in the db
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

    def set_string(self, otfg_entry):
        """Set the full string of OTFGData instance"""
        if self.element is None:
            self.set_element("LIBRARY")
        self.set_attribute("otfg_entry", str(otfg_entry))

    def set_element(self, element):
        """Set the element of OTFGData instance"""
        self.set_attribute("element", str(element))

    def store(self, *args, **kwargs):
        self._validate()
        return super(OTFGData, self).store(*args, **kwargs)

    @property
    def string(self):
        return self.get_attribute('otfg_entry', None)

    @property
    def element(self):
        """Element of the OTFG. May not be available"""
        return self.get_attribute('element', None)

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
        from .utils import split_otfg_entry

        element, string = split_otfg_entry(entry)
        qb = QueryBuilder()
        qb.append(cls,
                  filters={
                      'attributes.otfg_entry': {
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
    def get_otfg_group(cls, group_label):
        """
        Return the OTFGData group with the given name.
        """
        return OTFGGroup.objects.get(label=group_label)

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
        from aiida.orm import QueryBuilder
        from aiida.orm import User

        query = QueryBuilder()
        filters = {'type_string': {'==': cls.otfg_family_type_string}}

        query.append(OTFGGroup, filters=filters, tag='group', project='*')

        if user:
            query.append(User,
                         filters={'email': {
                             '==': user
                         }},
                         with_group='group')

        if isinstance(filter_elements, six.string_types):
            filter_elements = [filter_elements]

        if filter_elements is not None:
            actual_filter_elements = {_.capitalize() for _ in filter_elements}
            # LIBRARY is a wild card
            actual_filter_elements.add("LBIRARY")

            query.append(
                cls,
                filters={'attributes.element': {
                    'in': filter_elements
                }},
                with_group='group')

        query.order_by({'group': {'id': 'asc'}})
        return [_[0] for _ in query.all()]

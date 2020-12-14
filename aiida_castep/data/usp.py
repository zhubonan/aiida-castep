"""
Module for storing usp files into the database
"""

from __future__ import absolute_import
import os
import warnings
from aiida.plugins import DataFactory
from aiida.orm import GroupTypeString
from aiida.common.utils import classproperty
from aiida.common.files import md5_file
from .utils import get_usp_element
import six

OLD_USPGROUP_TYPE = "data.castep.usp.family"
USPGROUP_TYPE = "castep.otfg"

SinglefileData = DataFactory("singlefile")

# Extract element from filename


def upload_usp_family(folder,
                      group_label,
                      group_description,
                      stop_if_existing=True):
    """
    Upload a set of usp/recpot files in a give group

    :param folder: a path containing all UPF files to be added.
        Only files ending in .usp/.recpot are considered.
    :param group_label: the name of the group to create. If it exists and is
        non-empty, a UniquenessError is raised.
    :param group_description: a string to be set as the group description.
        Overwrites previous descriptions, if the group was existing.
    :param stop_if_existing: if True, check for the md5 of the files and,
        if the file already exists in the DB, raises a MultipleObjectsError.
        If False, simply adds the existing UPFData node to the group.
    """
    import os

    import aiida.common
    #from aiida.common import aiidalogger
    from aiida.common import UniquenessError, NotExistent
    from aiida.orm.querybuilder import QueryBuilder
    from .otfg import OTFGGroup

    files = [
        os.path.realpath(os.path.join(folder, i)) for i in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, i)) and (
            i.lower().endswith('.usp') or i.lower().endswith('recpot')
            or i.lower().endswith('.uspcc'))
    ]

    nfiles = len(files)

    try:
        group = OTFGGroup.get(label=group_label)
        group_created = False
    except NotExistent:
        group = OTFGGroup(label=group_label, )
        group_created = True

    # Update the descript even if the group already existed
    group.description = group_description

    pseudo_and_created = []  # A list of records (UspData, created)

    for f in files:

        md5sum = md5_file(f)
        qb = QueryBuilder()
        qb.append(UspData, filters={'attributes.md5': {'==': md5sum}})
        existing_usp = qb.first()

        # Add the file if it is in the database
        if existing_usp is None:
            pseudo, created = UspData.get_or_create(f,
                                                    use_first=True,
                                                    store_usp=False)
            pseudo_and_created.append((pseudo, created))

        # The same file is there already
        else:
            if stop_if_existing:
                raise ValueError("A usp/recpot with identical MD5 to"
                                 " {} cannot be added with stop_if_existing"
                                 "".format(f))
            existing_usp = existing_usp[0]
            pseudo_and_created.append((existing_usp, False))

    # Check for unique per element
    elements = [(i[0].element, i[0].md5sum) for i in pseudo_and_created]

    # Check if we will duplicate after insertion

    if not group_created:
        for aiida_n in group.nodes:
            if not isinstance(aiida_n, UspData):
                continue
            elements.append((aiida_n.element, aiida_n.md5sum))

    # Discard duplicated pairs
    elements = set(elements)
    elements_names = [e[0] for e in elements]

    # Check the uniqueness of the complete group
    if not len(elements_names) == len(set(elements_names)):
        duplicates = set(
            [x for x in elements_names if elements_names.count(x) > 1])
        dup_string = ", ".join(duplicates)
        raise UniquenessError(
            "More than one usp/recpot found for the elements: " + dup_string +
            ".")

    if group_created:
        group.store()

    # Save the usp in the database if necessary and add them to the group

    for pseudo, created in pseudo_and_created:
        if created:
            pseudo.store()
            #aiidalogger.debug("New node {} created for file {}".format(
            #    pseudo.uuid, pseudo.filename))
        else:
            #aiidalogger.debug("Reusing node {} for file {}".format(
            #    pseudo.uuid, pseudo.filename))
            pass

    nodes_new = [
        pseduo for pseduo, created in pseudo_and_created if created is True
    ]
    nodes_add = [pseduo for pseduo, created in pseudo_and_created]
    group.add_nodes(nodes_add)

    return nfiles, len(nodes_new)


class UspData(SinglefileData):
    """
    Class for a single usp file
    These usp files are stored as individual file nodes in the database
    """
    def __init__(self, **kwargs):
        """
        Initialize a UspData node
        :param file str: A full path to the file of the potential
        :param element: The elemnt that this pseudo potential should be used for
        """

        element = kwargs.pop("element", None)
        self._abs_path = kwargs["file"]
        super(UspData, self).__init__(**kwargs)

        # Overides the element inferred
        if element is not None:
            self.set_element(element)

    @classmethod
    def get_or_create(cls,
                      filename,
                      element=None,
                      use_first=False,
                      store_usp=True):
        """
        Same ase init. Check md5 in the db, it is found return a UspData.
        Otherwise will store the data into the db

        :return (usp, created)
        """

        import aiida.common.utils
        import os

        # Convert the filename to an absolute path
        filename = str(filename)
        if filename != os.path.abspath(filename):
            raise ValueError("filename must be an absolute path")
        md5 = md5_file(filename)

        # Check if we have got the file already
        pseudos = cls.from_md5(md5)
        if len(pseudos) == 0:
            # No existing pseudopotential file is in the database
            instance = cls(file=filename)
            # If we there is an element given then I set it
            if element is not None:
                instance.set_element(element)
            # Store the usp if requested
            if store_usp is True:
                instance.store()
            return (instance, True)
        else:
            if len(pseudos) > 1:
                if use_first:
                    return (pseudos[0], False)
                else:
                    pks = ", ".join([str(i.pk) for i in pseudos])
                    raise ValueError("More than one copy of a pseudopotential"
                                     " found. pks={}".format(pks))
            else:
                return (pseudos[0], False)

    @classmethod
    def from_md5(cls, md5):
        """
        Return a list of all usp pseudopotentials that match a given MD5 hash.

        Note that the hash has to be stored in a md5 attribute, otherwise
        the pseudo will not be found.
        We use a special md5 attribute to avoid searching through
        irrelevant data types.
        """
        from aiida.orm.querybuilder import QueryBuilder
        qb = QueryBuilder()
        qb.append(cls, filters={'attributes.md5': {'==': md5}})
        return [_ for [_] in qb.all()]

    @classproperty
    def uspfamily_type_string(cls):
        """
        Type string of the underlying group deprecated as new 
        Group should be access by sub-classing
        """
        return USPGROUP_TYPE

    def store(self, *args, **kwargs):
        """
        Store the node. Automatically set md5 and element
        """
        # Cannot revalidate the stored nodes
        if not self.is_stored:
            self._validate()

        return super(UspData, self).store(*args, **kwargs)

    def set_file(self, filename):
        """
        Extract element and compute the md5hash
        """

        filename = str(filename)

        try:
            element = get_usp_element(filename)
        except KeyError:
            element = None
        else:
            # Only set the element if it is not there
            if self.element is None:
                if element is not None:
                    self.set_element(element)
                else:
                    warnings.warn(
                        "Cannot extract element form the usp/recpot file {}."
                        "Please set it manually.".format(filename))
            else:
                # The element is already set, no need to process further
                pass

        md5sum = md5_file(filename)
        self.set_attribute('md5', md5sum)
        super(UspData, self).set_file(filename)

    def set_element(self, element):
        """
        Set the element
        """
        self.set_attribute('element', element)

    @property
    def element(self):
        return self.get_attribute('element', None)

    @property
    def md5sum(self):
        """MD5 sum of the usp/recpot file"""
        return self.get_attribute('md5', None)

    @property
    def string(self):
        """Alias of the md5sum"""
        return self.md5sum

    @classmethod
    def get_usp_group(cls, group_label):
        """
        Return the UspFamily group with the given name.
        """
        from .otfg import OTFGGroup

        return OTFGGroup.objects.get(label=group_label)

    @classmethod
    def get_usp_groups(cls, filter_elements=None, user=None):
        """
        Return all names of groups of type UpfFamily, possibly with some filters.

        :param filter_elements: A string or a list of strings.
               If present, returns only the groups that contains one Upf for
               every element present in the list. Default=None, meaning that
               all families are returned.
        :param user: if None (default), return the groups for all users.
               If defined, it should be either a DbUser instance, or a string
               for the username (that is, the user email).
        """
        from .otfg import OTFGGroup
        from aiida.orm import QueryBuilder
        from aiida.orm import User

        query = QueryBuilder()

        query.append(OTFGGroup, tag='group', project=['*'])

        if user:
            query.append(User,
                         filters={'email': {
                             '==': user
                         }},
                         with_group='group')

        if isinstance(filter_elements, str):
            filter_elements = [filter_elements]

        if filter_elements is not None:
            actual_filter_elements = [_ for _ in filter_elements]
            query.append(
                cls,
                filters={'attributes.element': {
                    'in': filter_elements
                }},
                with_group='group')

        query.order_by({OTFGGroup: {'id': 'asc'}})
        return [_[0] for _ in query.all()]

    def _validate(self):
        from aiida.common import ValidationError

        super(UspData, self)._validate()

        # Check again, in case things changes
        usp_abspath = str(self._abs_path)

        if not usp_abspath:
            raise ValidationError("No valid usp file was passed")

        parsed_element = get_usp_element(usp_abspath)
        md5 = md5_file(usp_abspath)
        attr_element = self.element

        if attr_element is None:
            raise ValidationError("No element is set")

        attr_md5 = self.get_attribute('md5', None)
        if self.md5sum is None:
            raise ValidationError("attribute 'md5' not set.")

        if md5 != attr_md5:
            raise ValidationError(
                "Mismatch between store md5 and actual md5 value")

        # Warn if the parsed elemnt (if any) is not matching the attribute
        if attr_element != parsed_element and parsed_element is not None:
            raise ValidationError("Attribute 'element' says '{}' but '{}' was "
                                  "parsed from file name instead.".format(
                                      attr_element, parsed_element))

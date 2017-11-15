"""
Module for storing usp files into the database
We take many things from upf.py here as usp is not too much different...
"""

import re
import os
from aiida.orm.data.singlefile import SinglefileData
from aiida.common.utils import classproperty

USPGROUP_TYPE = "data.castep.usp.family"


# Extract element from filename
re_fn = re.compile("^(\w+)_\w+\.(usp|recpot)$", flags=re.IGNORECASE)

def upload_usp_family(folder, group_name, group_description,
                      stop_if_existing=True):
    """
    Upload a set of usp/recpot files in a give group

    :param folder: a path containing all UPF files to be added.
        Only files ending in .usp/.recpot are considered.
    :param group_name: the name of the group to create. If it exists and is
        non-empty, a UniquenessError is raised.
    :param group_description: a string to be set as the group description.
        Overwrites previous descriptions, if the group was existing.
    :param stop_if_existing: if True, check for the md5 of the files and,
        if the file already exists in the DB, raises a MultipleObjectsError.
        If False, simply adds the existing UPFData node to the group.
    """
    import os

    import aiida.common
    from aiida.common import aiidalogger
    from aiida.orm import Group
    from aiida.common.exceptions import UniquenessError, NotExistent
    from aiida.backends.utils import get_automatic_user
    from aiida.orm.querybuilder import QueryBuilder

    files = [os.path.realpath(os.path.join(folder, i))
             for i in os.listdir(folder) if
             os.path.isfile(os.path.join(folder, i)) and
             (i.lower().endswith('.usp') or i.lower().endswith('recpot'))]

    nfiles = len(files)

    try:
        group = Group.get(name=group_name, type_string=USPGROUP_TYPE)
        group_created = False
    except NotExistent:
        group = Group(name=group_name, type_string=USPGROUP_TYPE,
            user=get_automatic_user())
        group_created = True


    # Update the descript even if the group already existed
    group.description = group_description

    pseudo_and_created = []

    for f in files:

        md5sum = aiida.common.utils.md5_file(f)
        qb = QueryBuilder()
        qb.append(UspData, filters={'attributes.md5':{'==':md5sum}})
        existing_usp = qb.first()

        # Add the file if it is in the database
        if existing_usp is None:
            pseudo, created = UspData.get_or_create(f, use_first=True,
                store_usp=False)
            pseudo_and_created.append((pseudo, created))

        # The same file is there already
        else:
            if stop_if_existing:
                raise ValueError(
                "A usp/recpot with identical MD5 to"
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
        duplicates = set([x for x in elements_names if elements_names.count(x) > 1])
        dup_string = ", ".join(duplicates)
        raise UniquenessError("More than one usp/recpot found for the elements: " + dup_string + ".")

    if group_created:
        group.store()

    # Save the usp in the database if necessary and add them to the group

    for pseudo, created in pseudo_and_created:
        if created:
            pseudo.store()
            aiidalogger.debug("New node {} created for file {}".format(
                pseudo.uuid, pseudo.filename))
        else:
            aiidalogger.debug("Reusing node {} for file {}".format(
                pseudo.uuid, pseudo.filename))

    group.add_nodes(pseduo for pseduo, _ in pseudo_and_created)

    nuploaded = len([_ for _, created in pseudo_and_created if created])

    return nfiles, nuploaded


class UspData(SinglefileData):
    """
    Class for a single usp file
    These usp files are stored as individual file nodes in the database
    """

    @classmethod
    def get_or_create(cls, filename, use_first=False, store_usp=True):
        """
        Same ase init. Check md5 in the db, it is found return a UpfData.
        Otherwise will store the data into the db

        :return (usp, created)
        """

        import aiida.common.utils
        import os


        # Convert the filename to an absolute path
        if filename != os.path.abspath(filename):
            raise ValueError("filename must be an absolute path")
        md5 = aiida.common.utils.md5_file(filename)

        # Check if we have got the file already
        pseudos = cls.from_md5(md5)
        if len(pseudos) == 0:
            # Not stored
            if store_usp is True:
                instance = cls(file=filename).store()
                return (instance, True)
            else:
                instance = cls(file=filename)
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
                return (pseudos, False)

    @classmethod
    def from_md5(cls, md5):
        """
        Return a list of all usp pseudopotentials that match a given MD5 hash.

        Note that the hash has to be stored in a usp_md5 attribute, otherwise
        the pseudo will not be found.
        We use a special md5 attribute to avoid searching through irrelavent data types.
        """
        from aiida.orm.querybuilder import QueryBuilder
        qb = QueryBuilder()
        qb.append(cls, filters={'attributes.usp_md5': {'==': md5}})
        # This should be refectored for better readibility
        return [_ for [_] in qb.all()]

    @classproperty
    def uspfamily_type_string(cls):
        return USPGROUP_TYPE


    def store(self, *args, **kwargs):
        """
        Store the node. Automatically set md5 and element
        """
        self._validate()

        return super(UspData, self).store(*args, **kwargs)

    def set_file(self, filename):
        """Added file but also check data"""
        from aiida.common.exceptions import ParsingError
        import aiida.common.utils

        try:
            element = get_usp_element(filename)
        except KeyError:
            raise ParsingError("Cannot extract element form the usp/recpot file {}; Cannot store into database.".format(self.filename))
        md5sum = aiida.common.utils.md5_file(filename)

        super(UspData, self).set_file(filename)

        self._set_attr('element', str(element))
        self._set_attr('usp_md5', md5sum)
        self._set_attr('md5', md5sum)

    @property
    def element(self):
        return self.get_attr('element', None)

    @property
    def md5sum(self):
        """MD5 sum of the usp/recpot file"""
        return self.get_attr('usp_md5', None)

    @classmethod
    def get_usp_group(cls, group_name):
        """
        Return the UpfFamily group with the given name.
        """
        from aiida.orm import Group

        return Group.get(name=group_name, type_string=cls.uspfamily_type_string)

    @classmethod
    def get_usp_groups(cls, filter_elements=None, user=None):

        """
        Return all names of groups of type UspFamily, possibly with some filters.

        :param filter_elements: A string or a list of strings.
               If present, returns only the groups that contains one Usp for
               every element present in the list. Default=None, meaning that
               all families are returned.
        :param user: if None (default), return the groups for all users.
               If defined, it should be either a DbUser instance, or a string
               for the username (that is, the user email).
        """

        from aiida.orm import Group

        group_query_params = {"type_string": cls.uspfamily_type_string}

        if user is not None:
            group_query_params['user'] = user

        if isinstance(filter_elements, basestring):
            filter_elements = [filter_elements]

        if filter_elements is not None:
            actual_filter_elements = {_.capitalize() for _ in filter_elements}

            group_query_params['node_attributes'] = {
                'element': actual_filter_elements}

        all_usp_groups = Group.query(**group_query_params)

        groups = [(g.name, g) for g in all_usp_groups]
        # Sort by name
        groups.sort()
        # Return the groups, without name
        return [_[1] for _ in groups]

    def _validate(self):
        from aiida.common.exceptions import ValidationError
        import aiida.common.utils

        super(UspData, self)._validate()

        usp_abspath = self.get_file_abs_path()

        if not usp_abspath:
            raise ValidationError("No valid usp file was passed")

        element = get_usp_element(usp_abspath)
        md5 = aiida.common.utils.md5_file(usp_abspath)

        if element is None:
            raise ValidationError("Cannot infer element. File should be in the format '<element>_<label>.usp'.")

        try:
            attr_element = self.get_attr('element')
        except AttributeError:
            raise ValidationError("attribute 'elememnt' not set.")

        try:
            attr_usp_md5 = self.get_attr('usp_md5')
        except AttributeError:
            raise ValidationError("attribute 'usp_md5' not set." )

        try:
            attr_md5 = self.get_attr('md5')
        except AttributeError:
            raise ValidationError("attribute 'md5' not set." )

        if attr_usp_md5 != attr_md5:
            raise ValidationError("Inconsistency between md5 and usp_md5")

        # Check matching of data and actual file
        if attr_element != element:
            raise ValidationError("Attribute 'element' says '{}' but '{}' was "
                              "parsed instead.".format(
            attr_element, element))

        if attr_usp_md5 != md5:
            raise ValidationError("Attribute 'usp_md5' says '{}' but '{}' was "
                                  "parsed instead.".format(
                attr_md5, md5))


def get_usp_element(filepath):
    """
    infer element from usp/recpot filename
    :return element: a string of element name or None if not found
    """

    filename = os.path.split(filepath)[1]
    match = re_fn.match(filename)
    if match:
        element = match.group(1)
        element = element.capitalize()
        return element
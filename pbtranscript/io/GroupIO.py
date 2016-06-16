#!/usr/bin/env python

"""Streaming IO support for Group files."""

from pbcore.io import ReaderBase, WriterBase
from pbcore.io._utils import splitFileContents

__all__ = ["GroupRecord",
           "GroupReader",
           "GroupWriter"]


class GroupRecord(object):

    """A GroupRecord associates an object with a group of objects.
    e.g.,
    name\tmember_0,member_1,member_2
    """

    def __init__(self, name, members):
        self.name = name
        self.members = members
        if not isinstance(members, list):
            raise ValueError("members %s must be a list of strings." % members)

    def __str__(self):
        return "{name}\t{members}".format(name=self.name, members=",".join(self.members))

    def __repr__(self):
        return "<GroupRecord for {name} containing {n} members>".format(name=self.name, n=len(self.members))

    def __eq__(self, other):
        return self.name == other.name and self.members == other.members

    @classmethod
    def fromString(cls, line):
        """Construct and return a GroupRecord object given a string."""
        fields = line.strip().split('\t')
        if len(fields) != 2:
            raise ValueError("Could not recognize %s as a valid GroupRecord." % line)
        return GroupRecord(name=fields[0], members=fields[1].split(','))


class GroupReader(ReaderBase):

    """
    Streaming reader for a Group file.

    Example:

    .. doctest::
        >>> from pbtranscript.io import GroupReader
        >>> filename = "../../../tests/data/test_GroupReader.txt"
        >>> for record in GroupReader(filename):
        ...     print record
        group1  member0,member1,member2
    """

    def __iter__(self):
        try:
            lines = splitFileContents(self.file, "\n")
            for line in lines:
                line = line.strip()
                if len(line) > 0 and line[0] != "#":
                    yield GroupRecord.fromString(line)
        except AssertionError:
            raise ValueError("Invalid Group file %s." % self.file.name)


class GroupWriter(WriterBase):

    """
    Write GroupRecords to a file.
    """
    def __init__(self, f):
        super(GroupWriter, self).__init__(f)

    def writeRecord(self, record):
        """Write a GroupRecrod."""
        if not isinstance(record, GroupRecord):
            raise ValueError("record type %s is not GroupRecord." % type(record))
        else:
            self.file.write("{0}\n".format(str(record)))

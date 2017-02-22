#!/usr/bin/env python

"""
Class MergeGroupReader, MegaInfoReader, MegaInfoWriter
"""

from csv import DictReader
from pbcore.io import WriterBase
from pbtranscript.io.GffIO import GmapRecord

__author__ = "etseng@pacificbiosciences.com, yli@pacificbiosciences.com"


__all__ = ["MergeGroupOperation", "MegaInfoReader", "MegaInfoWriter"]


class MergeGroupOperation(object):

    """An operation which merges two groups into one"""

    def __init__(self, pbid, group1, group2):
        self.pbid = pbid
        self.group1 = group1
        self.group2 = group2
        self.master_group = None

        self._sanity_check()

    def _sanity_check(self):
        """Sanity check groups"""
        assert isinstance(self.pbid, str)
        assert not (self.group1 is None and self.group2 is None)
        assert isinstance(self.group1, GmapRecord) or self.group1 is None or isinstance(self.group1, str)
        assert isinstance(self.group2, GmapRecord) or self.group2 is None or isinstance(self.group2, str)

    def __str__(self):
        def to_str(group):
            """convert a str of None to str"""
            return 'NA' if group is None else str(group.seqid) if isinstance(group, GmapRecord) else str(group)
        return "\t".join([to_str(x) for x in (self.pbid, self.group1, self.group2)])


def MegaInfoReader(i_mega_fn):
    """
    class MegaInfoReader
        Read *.mega_info.txt of format:
        pbid    SF3BI   NTI
        PB.1.1  NA  PB.2.1
        PB.10.1 PB.9.1  PB.16.1

        reader = MegaInfoReader("*.mega_info.txt")
        rs = [r for r in reader]
        rs[0]['NTI'] == 'PB.2.1'
        rs[0]['SF3BI'] == 'NA'
        rs[0]['pbid'] == PB.1.1
    """
    return DictReader(open(i_mega_fn, 'r'), delimiter='\t')


class MegaInfoWriter(WriterBase):

    """Write Merge group operations to a file *.mega_info.txt."""

    def __init__(self, filename, prefix1, prefix2):
        super(MegaInfoWriter, self).__init__(filename)

        # write header of MergeGroupOperation,
        # e,g., pbid\tprefix1\tprefix2"""
        header = '\t'.join([str(x) for x in ('pbid', prefix1, prefix2)])
        self.file.write("{0}\n".format(header))

    def writeRecord(self, record):
        """Write a MergeGroupOperation."""
        if not isinstance(record, MergeGroupOperation):
            raise ValueError(
                "record type %s is not MergeGroupOperation." % type(record))
        else:
            self.file.write("{0}\n".format(str(record)))

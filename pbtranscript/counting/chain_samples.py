#!/usr/bin/env python
"""
Chain multiple isoseq samples, get chained ids and abundance info.
"""
import sys
import shutil
import logging
import argparse
import os.path as op
from collections import defaultdict

from pbtranscript.io import ChainConfig, SampleFiles, AbundanceReader, MegaInfoReader
from pbtranscript.counting import MegaPBTree

__author__ = 'etseng@pacb.com, yli@pacb.com'

FORMATTER = op.basename(__file__) + ':%(levelname)s:' + '%(message)s'
logging.basicConfig(level=logging.INFO, format=FORMATTER)
log = logging.getLogger(__name__)


class ChainFiles(object):
    """Output files of chaining samples, including gff, group.txt, mega_info.txt
    e.g., tmp_${sample_name}.gff, tmp_${sample_name}.group.txt, tmp_${sample_name}.mega_info
    """
    def __init__(self, sample_name, _pprefix='tmp_'):
        #self.sample = sample
        self.o_prefix = "%s%s" % (_pprefix, sample_name)
        self.o_gff_fn = self.o_prefix + ".gff"
        self.o_group_fn = self.o_prefix + ".group.txt"
        self.o_mega_fn = self.o_prefix + ".mega_info.txt"


def get_abundance_info(samples, field_to_use):
    """Read abundance info of field `field_to_use` from multiple samples in ChainConfig cfg,
    return a dict {(sample_name, pbid) --> abundance of `field_to_use`)
    e.g., (sample, PB.1.1) --> count

    Parameters
    samples --- a list of SampleFiles objs
    field_to_use --- an abundance metric in str e.g., 'count_fl', 'count_nfl', 'count_nfl_amb', and etc

    each sample in samples containing an abundance file, looks like
       pbid    count_fl    count_nfl   count_nfl_amb   norm_fl norm_nfl    norm_nfl_amb
       PB.1.1  30  30  30.83   6.3667e-03  3.0367e-03  3.0637e-03
       PB.2.1  9   9   9.39    1.9100e-03  9.1102e-04  9.3331e-04

    for example, if field_to_use == 'norm_nfl_amb', return
    {('sample_1', 'PB.1.1'): 3.0637e-03, ('sample_1', 'PB.1.1'): 9.3331e-04, ...}
    """
    abundance_info = {}  # key: (sample, PB.1.1) --> count
    for sample in samples:
        assert isinstance(sample, SampleFiles)
        for r in AbundanceReader(sample.abundance_fn):
            if hasattr(r, field_to_use):
                abundance_info[sample.name, r.pbid] = getattr(r, field_to_use)
            else:
                raise ValueError(
                    "%s abundance file does not have field %s", sample.abundance_fn, field_to_use)
    return abundance_info


def get_mega_info_dict(samples):
    """Read mega info of all samples,
    return a dict {(o_prefix, pbid) --> MergeGroupOperation(pbid, group1, group2)}

    ex:
    {('tmp_1009', 'PB.1.1'): MergeGroupOperation('PB.1.1', 'PB.2.1', None)}
    """
    mega_info = {}  # ex: (tmp_1009, PB.1.1) --> MergeGroupOperation(...)
    for sample in samples:
        ofs = ChainFiles(sample.name)
        for r in MegaInfoReader(ofs.o_mega_fn):
            mega_info[(ofs.o_prefix, r['pbid'])] = r
    return mega_info


def chain_samples(cfg, field_to_use, max_fuzzy_junction):
    """Chain multiple isoseq samples"""
    # get abundance info from all samples' abundance (count) files.
    abundance_info = get_abundance_info(samples=cfg.samples, field_to_use=field_to_use)

    sample = cfg.samples[0]
    o = MegaPBTree(gff_filename=sample.gff_fn, group_filename=sample.group_fn,
                   self_prefix=sample.name, max_fuzzy_junction=max_fuzzy_junction)

    for sample in cfg.samples[1:]:
        ofs = ChainFiles(sample.name)
        o.add_sample(gff_filename=sample.gff_fn, group_filename=sample.group_fn,
                     sample_prefix=sample.name, o_gff_fn=ofs.o_gff_fn,
                     o_group_fn=ofs.o_group_fn, o_mega_fn=ofs.o_mega_fn)
        o = MegaPBTree(gff_filename=ofs.o_gff_fn, group_filename=ofs.o_group_fn,
                       self_prefix=ofs.o_prefix, max_fuzzy_junction=max_fuzzy_junction)

    # now recursively chain back by looking at mega_info.txt!!!
    chain = [sample.name for sample in cfg.samples]
    # get mega info dict
    mega_info_d = get_mega_info_dict(cfg.samples[1:])

    chained_ids_fn = 'all_samples.chained_ids.txt'
    chained_count_fn = 'all_samples.chained_count.txt'
    chained_gff_fn = "all_samples.chained.gff"
    f1 = open(chained_ids_fn, 'w')
    f1.write("superPBID")
    f2 = open(chained_count_fn, 'w')
    f2.write("superPBID")

    for c in chain:
        f1.write('\t' + c)
        f2.write('\t' + c)
    f1.write('\n')
    f2.write('\n')

    reader = MegaInfoReader(ChainFiles(cfg.samples[-1].name).o_mega_fn)
    for r in reader:
        saw_NA = False
        r0 = r
        chain_to_pbid = defaultdict(lambda: 'NA') # ex: 1009 --> PB.1.1
        chain_to_abundance = defaultdict(lambda: 'NA') # ex: 1009 --> count
        chain_to_pbid[chain[-1]] = r[chain[-1]]
        if r[chain[-1]] != 'NA':
            chain_to_abundance[chain[-1]] = abundance_info[chain[-1], chain_to_pbid[chain[-1]]]
        for c in chain[::-1][1:-1]:  # the first sample does not have tmp_, because it's not a chain
            prefix = ChainFiles(c).o_prefix
            if r[prefix] == 'NA':
                saw_NA = True
                break
            else:
                r2 = mega_info_d[prefix, r[prefix]]
                chain_to_pbid[c] = r2[c]
                if chain_to_pbid[c] != 'NA':
                    chain_to_abundance[c] = abundance_info[c, chain_to_pbid[c]]
                r = r2
        if not saw_NA:
            chain_to_pbid[chain[0]] = r[chain[0]]
            if chain_to_pbid[chain[0]] != 'NA':
                chain_to_abundance[chain[0]] = abundance_info[chain[0], chain_to_pbid[chain[0]]]
        f1.write(r0['pbid'])
        f2.write(r0['pbid'])
        for c in chain:
            f1.write("\t" + chain_to_pbid[c]) # each tissue still share the same PB id
            n = chain_to_abundance[c]
            f2.write("\tNA" if (n == 'NA') else "\t%.4e" % n)
        f1.write('\n')
        f2.write('\n')
    f1.close()
    f2.close()

    shutil.copyfile(ChainFiles(chain[-1]).o_gff_fn, chained_gff_fn)

    log.info("Chained output written to:\n%s\n%s\n%s\n",
             chained_gff_fn, chained_ids_fn, chained_count_fn)

def run(args):
    """main run"""
    cfg = ChainConfig.from_file(args.cfg_fn)
    chain_samples(cfg=cfg, field_to_use=args.field_to_use,
                  max_fuzzy_junction=args.max_fuzzy_junction)


def get_parser():
    """Get argument parser."""
    helpstr = "Chain multiple isoseq samples"
    parser = argparse.ArgumentParser(helpstr)

    helpstr = "Chain config file, containing SAMPLE=<name>;<path>, GROUP_FILENAME, GFF_FILENAME, GFF_FILENAME"
    parser.add_argument("cfg_fn", help=helpstr)

    choices = ['norm_fl', 'norm_nfl', 'norm_nfl_amb',
               'count_fl', 'count_nfl', 'count_nfl_amb']
    helpstr = "Which count field to use for chained sample (default: norm_nfl)"
    parser.add_argument("field_to_use", choices=choices,
                        default='norm_nfl', help=helpstr)

    helpstr = "Max allowed distance in junction to be considered identical (default: 5 bp)"
    parser.add_argument("--fuzzy_junction", "--max_fuzzy_junction",
                        dest="max_fuzzy_junction", default=5, type=int, help=helpstr)
    return parser


if __name__ == "__main__":
    run(get_parser().parse_args(sys.argv[1:]))

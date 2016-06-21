#!/usr/bin/env python

"""
Class CollaspeIsoforms reads isoform alignments from a SORTED GMAP SAM
file mapping uncollapsed isoforms to reference genomes, collapses
redundant isoforms into transcripts (families), and merges transcripts
with merge-able fuzzy junctions.

Class Branch reads isoform alignments from a SORTED GMAP SAM file,
identifies exons of isoforms based on alignments, compares exons among
different isoforms, collapses identical isoforms into transcripts, and
write out to GTF format.

Note that Branch input GMAP SAM file must be sorted by
    (1) reference ID and
    (2) reference coordinates.

Note that Branch does not merge fuzzy junctions
"""
import logging
import os.path as op


from pbtranscript.Utils import ln
from pbtranscript.io import iter_gmap_sam, ContigSetReaderWrapper, \
        CollapseGffWriter, GroupWriter
from pbtranscript.collapsing.CollapsingUtils import collapse_sam_records, \
        collapse_fuzzy_junctions, pick_rep

__all__ = ["Branch",
           "CollapsedFiles",
           "CollapseIsoformsRunner"]


__author__ = 'etseng@pacificbiosciences.com'

log = logging.getLogger(__name__)

class Constants(object):
    """Constants used in tool contract."""
    TOOL_ID = "pbtranscript.tasks.collapse_mapped_isoforms"
    DRIVER_EXE = "python -m %s --resolved-tool-contract " % TOOL_ID
    PARSER_DESC = __doc__

    MIN_ALN_COVERAGE_ID = "pbtranscript.task_options.min_gmap_aln_coverage"
    MIN_ALN_COVERAGE_DEFAULT = 0.99
    MIN_ALN_COVERAGE_DESC = "Min query coverage to analyze a GMAP alignment (default: %s)" % \
                            MIN_ALN_COVERAGE_DEFAULT

    MIN_ALN_IDENTITY_ID = "pbtranscript.task_options.min_gmap_aln_identity"
    MIN_ALN_IDENTITY_DEFAULT = 0.95
    MIN_ALN_IDENTITY_DESC = "Min identity to analyze a GMAP alignment (default: %s)" % \
                            MIN_ALN_IDENTITY_DEFAULT

    MAX_FUZZY_JUNCTION_ID = "pbtranscript.task_options.max_fuzzy_junction"
    MAX_FUZZY_JUNCTION_DEFAULT = 5
    MAX_FUZZY_JUNCTION_DESC = "Max edit distance between merge-able fuzzy junctions " + \
                              "(default: %s bp)" % MAX_FUZZY_JUNCTION_DEFAULT

    MIN_FLNC_COVERAGE_DEFAULT = 2
    MIN_FLNC_COVERAGE_DESC = "Minimum number of FLNC reads (default: %s), " % \
                             MIN_FLNC_COVERAGE_DEFAULT + \
                             "only used for aligned FLNC reads, otherwise, result undefined."

    ALLOW_EXTRA_5EXON_ID = "pbtranscript.task_options.allow_extra_5exon"
    ALLOW_EXTRA_5EXON_DEFAULT = False
    ALLOW_EXTRA_5EXON_DESC = "True: Collapse shorter 5' transcripts. " + \
                             "False: Don't collapse shorter 5' transcripts " + \
                             "(default: %s)" % ALLOW_EXTRA_5EXON_DEFAULT

    SKIP_5_EXON_ALT_DEFAULT = False


class Branch(object):
    """
    Branch collapses isoforms from PacBio's GMAP results into transcripts (families).

    Does not use Illumina.

    GMAP SAM file MUST BE SORTED! (same criterion as cufflinks)

    Parameters:
      isoform_filename -- hq_isoforms.fasta|fastq|contigset
      sam_filename -- a SORTED GMAP SAM file mapping isoforms to references
      cov_threshold -- only output if having > cov_threshold supportive GMAP alignments
      min_aln_coverage -- ignore records if alignment coverage < min_aln_coverage
      min_aln_identity -- ignore records if alignment identity < min_aln_identity

    b = Branch(isoform_filename, sam_filename)
    b.run(allow_extra_5exon=True, skip_5_exon_alt=False,
          ignored_ids_fn, good_gff_fn, bad_gff_fn, group_fn)
    """
    def __init__(self, isoform_filename, sam_filename,
                 cov_threshold=Constants.MIN_FLNC_COVERAGE_DEFAULT,
                 min_aln_coverage=Constants.MIN_ALN_COVERAGE_DEFAULT,
                 min_aln_identity=Constants.MIN_ALN_IDENTITY_DEFAULT):
        self.exons = None
        self.isoform_filename = isoform_filename
        self.isoform_len_dict = ContigSetReaderWrapper.name_to_len_dict(isoform_filename)
        self.sam_filename = sam_filename

        # Only output GTF records if >= cov_threshold supportive GMAP records.
        # Only used when running GMAP on non-clustered isoforms.
        self.cov_threshold = cov_threshold

        self.min_aln_coverage = min_aln_coverage
        self.min_aln_identity = min_aln_identity

    def run(self, allow_extra_5exon, skip_5_exon_alt,
            ignored_ids_fn, good_gff_fn, bad_gff_fn, group_fn,
            tolerate_end=100):
        """
        Process the whole SAM file:
          (1) Group SAM records based on where they mapped to and strands
          (2) Collapse records, write collapsed isoforms to *_gff_writer,
              write supportive records associated with each collapsed isoforms
              to group_writer.
        """
        ignored_ids_writer = open(ignored_ids_fn, 'w') if ignored_ids_fn else None
        good_gff_writer = CollapseGffWriter(good_gff_fn) if good_gff_fn else None
        bad_gff_writer = CollapseGffWriter(bad_gff_fn) if bad_gff_fn else None
        group_writer = GroupWriter(group_fn) if group_fn else None

        cuff_index = 1
        for recs in iter_gmap_sam(sam_filename=self.sam_filename,
                                  query_len_dict=self.isoform_len_dict,
                                  min_aln_coverage=self.min_aln_coverage,
                                  min_aln_identity=self.min_aln_identity,
                                  ignored_ids_writer=ignored_ids_writer):
            # Iterate over groups of overlapping SAM records
            for records in recs.itervalues():
                if len(records) > 0:
                    # records: a list of overlapping SAM records, same strands
                    collapse_sam_records(records=records, cuff_index=cuff_index,
                                         cov_threshold=self.cov_threshold,
                                         allow_extra_5exon=allow_extra_5exon,
                                         skip_5_exon_alt=skip_5_exon_alt,
                                         good_gff_writer=good_gff_writer,
                                         bad_gff_writer=bad_gff_writer,
                                         group_writer=group_writer,
                                         tolerate_end=tolerate_end)
                    cuff_index += 1

        # close writers.
        for writer in (ignored_ids_writer, good_gff_writer, bad_gff_writer, bad_gff_writer):
            if writer:
                writer.close()


class CollapsedFiles(object):
    """
    Class defines output files produced by CollapseIsoformsRunner.
    """
    def __init__(self, prefix, allow_extra_5exon):
        self.prefix = prefix
        self.allow_extra_5exon = allow_extra_5exon

    @property
    def has_5merge_str(self):
        """Return whether or not merge shorter 5 exons."""
        return "5merge" if self.allow_extra_5exon else "no5merge"

    @property
    def good_gff_fn(self):
        """
        File to save good collapsed transcript in GFF, regardless
        of whether or not fuzzy-matching transcripts are further collapsed.
        """
        return "%s.%s.collapsed.good.gff" % (self.prefix, self.has_5merge_str)

    @property
    def bad_gff_fn(self):
        """
        File to save bad collapsed transcripts in GFF, regardless
        of whether or not fuzzy-matching transcripts are further collapsed.
        """
        return "%s.%s.collapsed.bad.gff" % (self.prefix, self.has_5merge_str)

    @property
    def group_fn(self):
        """
        File to save collapsed transcripts and associated isoforms, regardless
        of whether or not fuzzy-matching transcripts are further collapsed
        """
        return "%s.%s.collapsed.group.txt" % (self.prefix, self.has_5merge_str)

    @property
    def ignored_ids_txt_fn(self):
        """File to save ignored isoforms which do not meet
        min_aln_coverage, or min_aln_identity."""
        return "%s.%s.ignored_ids.txt" % (self.prefix, self.has_5merge_str)

    @property
    def good_fuzzy_gff_fn(self):
        """
        File to save good transcripts, of which
        fuzzy-matching transcripts are further collapsed.
        """
        return self.good_gff_fn + ".fuzzy"

    @property
    def good_unfuzzy_gff_fn(self):
        """
        File to save good transcripts, of which
        fuzzy-matching transcripts are NOT further collapsed.
        """
        return self.good_gff_fn + ".unfuzzy"

    @property
    def bad_fuzzy_gff_fn(self):
        """
        File to save bad transcripts, of which
        fuzzy-matching transcripts are further collapsed.
        """
        return self.bad_gff_fn + ".fuzzy"

    @property
    def bad_unfuzzy_gff_fn(self):
        """
        File to save bad transcripts, of which
        fuzzy-matching transcripts are NOT further collapsed.
        """
        return self.bad_gff_fn + ".unfuzzy"

    @property
    def fuzzy_group_fn(self):
        """
        File to save collapsed transcripts and associated isoforms, of which
        fuzzy-matching transcripts are further collapsed
        """
        return self.group_fn + ".fuzzy"

    @property
    def unfuzzy_group_fn(self):
        """
        File to save collapsed transcripts and associated isoforms, of which
        fuzzy-matching transcripts are NOT further collapsed
        """
        return self.group_fn + ".unfuzzy"


class CollapseIsoformsRunner(CollapsedFiles):
    """
    Collapse isoforms into gene families, requiring
    (1) input isoforms in FASTA/FASTQ/ContigSet, and
    (2) GMAP SAM alignments mapping input isoforms to reference genomes.

    First, reads isoform alignments from a SORTED GMAP SAM file mapping
    uncollapsed isoforms to reference genomes.
    Then collapses redundant isoforms into transcripts (families).
    Next, merges transcripts with merge-able fuzzy junctions.
    Writes collapsed isoforms in GFF to good|bad_gff_fn, writes
    representative reads of collapsed isoforms to collapsed_isoform_filename, and
    writes isoform groups into group_fn.
    """
    def __init__(self, isoform_filename, sam_filename, collapsed_isoform_filename,
                 min_aln_coverage=Constants.MIN_ALN_COVERAGE_DEFAULT,
                 min_aln_identity=Constants.MIN_ALN_IDENTITY_DEFAULT,
                 min_flnc_coverage=Constants.MIN_FLNC_COVERAGE_DEFAULT,
                 max_fuzzy_junction=Constants.MAX_FUZZY_JUNCTION_DEFAULT,
                 allow_extra_5exon=Constants.ALLOW_EXTRA_5EXON_DEFAULT,
                 skip_5_exon_alt=Constants.SKIP_5_EXON_ALT_DEFAULT):
        """
        Parameters:
          isoform_filename -- input file containing isoforms, as fastq|fasta|contigset
          sam_filename -- input sam file produced by mapping fastq_filename to reference and sorted.
          collapsed_isoform_filename -- file to output collapsed isoforms as fasta|fastq|contigset
          min_aln_coverage -- min coverage over reference to collapse a group of isoforms
          min_aln_identity -- min identity aligning to reference to collapse a group of isoforms
          dun_merge_5_shorter -- False, merge isoforms which are only shorter on 5' to longer ones;
          max_fuzzy_junction -- max fuzzy junction
        """
        prefix = op.join(op.dirname(collapsed_isoform_filename),
                         op.basename(collapsed_isoform_filename).split(".")[0])

        super(CollapseIsoformsRunner, self).__init__(prefix=prefix,
                                                     allow_extra_5exon=allow_extra_5exon)

        self.isoform_filename = isoform_filename # input, uncollapsed fa|fq|ds
        self.sam_filename = sam_filename # input, sorted, gmap sam
        self.collapsed_isoform_filename = collapsed_isoform_filename # output, collapsed, fa|fq|ds

        self.min_aln_coverage = float(min_aln_coverage)
        self.min_aln_identity = float(min_aln_identity)
        self.min_flnc_coverage = int(min_flnc_coverage)
        self.max_fuzzy_junction = int(max_fuzzy_junction)
        self.allow_extra_5exon = bool(allow_extra_5exon)
        self.skip_5_exon_alt = bool(skip_5_exon_alt)

    @property
    def shall_collapse_fuzzy_junctions(self):
        """Returns True if needs to further collapse transcripts with fuzzy junctions"""
        return self.max_fuzzy_junction > 0

    def arg_str(self):
        """Returns arg string."""
        return ", ".join(["min_aln_coverage=%s" % self.min_aln_coverage,
                          "min_aln_identity=%s" % self.min_aln_identity,
                          "max_fuzzy_junction=%s" % self.max_fuzzy_junction,
                          "min_flnc_coverage=%s" % self.min_flnc_coverage,
                          "allow_extra_5exon=%s" % self.allow_extra_5exon,
                          "skip_5_exon_alt=%s" % self.skip_5_exon_alt])

    def __str__(self):
        return ("<Map isoforms %s to %s and write collapsed isoforms to %s>, args=%s\n" %
                (self.isoform_filename, self.sam_filename,
                 self.collapsed_isoform_filename, self.arg_str))

    def validate_inputs(self):
        """Validate existence of input files. Enusre input reads have unique ids."""
        logging.info("Validing inputs.")
        if not op.exists(self.isoform_filename):
            raise IOError("Input isoforms file %s does not exist" % self.isoform_filename)

        if not op.exists(self.sam_filename):
            raise IOError("Input SAM file %s does not exist" % self.sam_filename)

        ContigSetReaderWrapper.check_ids_unique(self.isoform_filename)

    def run(self):
        """
        First, collapse input isoforms by calling Branch.run().
        Then collapse fuzzy junctions by calling collapse_fuzzy_junctions.
        Finally, pick up representitive gff record for each group of collapsed isoforms.
        """
        self.validate_inputs()

        logging.info("Collapsing isoforms into transcripts.")
        b = Branch(isoform_filename=self.isoform_filename,
                   sam_filename=self.sam_filename,
                   cov_threshold=self.min_flnc_coverage,
                   min_aln_coverage=self.min_aln_coverage,
                   min_aln_identity=self.min_aln_identity)

        b.run(allow_extra_5exon=self.allow_extra_5exon,
              skip_5_exon_alt=self.skip_5_exon_alt,
              ignored_ids_fn=self.ignored_ids_txt_fn,
              good_gff_fn=self.good_unfuzzy_gff_fn,
              bad_gff_fn=self.bad_unfuzzy_gff_fn,
              group_fn=self.unfuzzy_group_fn)

        logging.info("Good unfuzzy isoforms written to: %s", self.good_unfuzzy_gff_fn)
        logging.info("Bad unfuzzy isoforms written to: %s", self.bad_unfuzzy_gff_fn)
        logging.info("Unfuzzy isoform groups written to: %s", self.unfuzzy_group_fn)

        if self.shall_collapse_fuzzy_junctions:
            logging.info("Further collapsing fuzzy junctions.")
            # need to further collapse those that have fuzzy junctions!
            collapse_fuzzy_junctions(gff_filename=self.good_unfuzzy_gff_fn,
                                     group_filename=self.unfuzzy_group_fn,
                                     fuzzy_gff_filename=self.good_fuzzy_gff_fn,
                                     fuzzy_group_filename=self.fuzzy_group_fn,
                                     allow_extra_5exon=self.allow_extra_5exon,
                                     max_fuzzy_junction=self.max_fuzzy_junction)

            logging.info("Good fuzzy isoforms written to: %s", self.good_fuzzy_gff_fn)
            logging.info("Bad fuzzy isoforms written to: %s", self.bad_fuzzy_gff_fn)
            logging.info("Fuzzy isoform groups written to: %s", self.fuzzy_group_fn)
            ln(self.good_fuzzy_gff_fn, self.good_gff_fn)
            ln(self.fuzzy_group_fn, self.group_fn)
        else:
            logging.info("No need to further collapse fuzzy junctions.")
            ln(self.good_unfuzzy_gff_fn, self.good_gff_fn)
            ln(self.unfuzzy_group_fn, self.group_fn)

        # Pick up representative
        logging.info("Picking up representative record.")
        pick_least_err_instead = not self.allow_extra_5exon # 5merge, pick longest
        pick_rep(isoform_filename=self.isoform_filename,
                 gff_filename=self.good_gff_fn,
                 group_filename=self.group_fn,
                 output_filename=self.collapsed_isoform_filename,
                 pick_least_err_instead=pick_least_err_instead,
                 bad_gff_filename=self.bad_gff_fn)

        logging.info("Ignored IDs written to: %s", self.ignored_ids_txt_fn)
        logging.info("Output GFF written to: %s", self.good_gff_fn)
        logging.info("Output Group TXT written to: %s", self.group_fn)
        logging.info("Output collapsed isoforms written to: %s", self.collapsed_isoform_filename)
        logging.info("Arguments: %s", self.arg_str())

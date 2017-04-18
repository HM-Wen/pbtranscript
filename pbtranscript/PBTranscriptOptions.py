#!/usr/bin/python
"""Add arugment Parser for subcommand `classify` and `cluster`."""

import argparse
import random

from pbcommand.cli.core import get_default_argparser_with_base_opts
from pbcommand.models import FileTypes, SymbolTypes, ResourceTypes, get_pbparser, PbParser

from pbtranscript.Utils import validate_fofn
from pbtranscript.__init__ import get_version

__all__ = ["add_classify_arguments",
           "add_cluster_arguments",
           "add_subset_arguments"]


__author__ = "etseng@pacificbiosciences.com, yli@pacificbiosciences.com"

random.seed(0)


class BaseConstants(object):
    TOOL_ID = "pbtranscript.tasks.main"
    DRIVER_EXE = "pbtranscript --resolved-tool-contract"
    PARSER_DESC = ""

    # these are all referenced in 2.3 pipeline scripts
    MIN_SEQ_LEN_ID = "pbtranscript.task_options.min_seq_len"
    MIN_SEQ_LEN_DEFAULT = 50
    #MIN_SCORE_ID = "pbtranscript.task_options.min_score"
    MIN_SCORE_DEFAULT = 10
    REQUIRE_POLYA_ID = "pbtranscript.task_options.require_polya"
    REQUIRE_POLYA_DEFAULT = True 
    PRIMER_SEQUENCES_ID = "pbtranscript.task_options.primer_sequences"
    PRIMER_SEQUENCES_DEFAULT = ""

    HQ_QUIVER_MIN_ACCURACY_ID = "pbtranscript.task_options.hq_quiver_min_accuracy"
    HQ_QUIVER_MIN_ACCURACY_DEFAULT = 0.99
    HQ_QUIVER_MIN_ACCURACY_DESC = "Minimum allowed Quiver|Arrow accuracy to classify an isoform " + \
                                  "as hiqh-quality (default: %s)" % HQ_QUIVER_MIN_ACCURACY_DEFAULT

    QV_TRIM_FIVEPRIME_ID = "pbtranscript.task_options.qv_trim_5p"
    QV_TRIM_FIVEPRIME_DEFAULT = 100
    QV_TRIM_FIVEPRIME_DESC = "Ignore QV of n bases in the 5' end " + \
            "(default %s)." % QV_TRIM_FIVEPRIME_DEFAULT
    QV_TRIM_THREEPRIME_ID = "pbtranscript.task_options.qv_trim_3p"
    QV_TRIM_THREEPRIME_DEFAULT = 30
    QV_TRIM_THREEPRIME_DESC = "Ignore QV of n bases in the 3' end " + \
            "(default %s)." % QV_TRIM_THREEPRIME_DEFAULT
    SAMPLE_NAME_ID = "pbtranscript.task_options.sample_name"
    SAMPLE_NAME_DEFAULT = ""

    USE_FINER_QV_ID = "pbtranscript.task_options.use_finer_qv"
    USE_FINER_QV_DEFAULT = False

def add_classify_arguments(parser):
    """
    Add arguments for subcommand `classify`.  This expects the PbParser object
    provided by pbcommand, not an argparse.ArgumentParser, and it will add
    most options separately to the internal tool contract parser and argparser
    (they are grouped here for clarity).
    """
    helpstr = "Input ccs reads file (usually reads_of_insert.fasta or " + \
              "ccs.bam or consensusreadset.xml)"
    parser.add_input_file_type(FileTypes.DS_CCS, "readsFN",
        name="ConsensusReadSet", description=helpstr)

    parser.add_output_file_type(FileTypes.DS_CONTIG, "outReadsFN", # idx 0
        name="Draft Isoforms",
        description="Intermediate dataset used to get full-length reads",
        default_name="isoseq_draft")
    tcp = parser.tool_contract_parser

    parser = parser.arg_parser.parser
    helpstr = "Full-length non-chimeric reads generated from pbtranscript classify"
    tcp.add_output_file_type(FileTypes.DS_CONTIG, "flnc", # idx 1
        name="Full-Length Non-Chimeric Reads",
        description=helpstr,
        default_name="isoseq_flnc")
    parser.add_argument("--flnc",
                        dest="flnc_fa",
                        type=str,
                        default=None,
                        help=helpstr)

    helpstr = "Non-full-length reads generated from pbtranscript classify"
    parser.add_argument("--nfl",
                        dest="nfl_fa",
                        type=str,
                        default=None,
                        help=helpstr)
    tcp.add_output_file_type(FileTypes.DS_CONTIG, "nfl", # idx 2
        name="Non-Full-Length Reads",
        description=helpstr,
        default_name="isoseq_nfl")

    hmm_group = parser.add_argument_group("HMMER options")

    helpstr = "Directory to store HMMER output (default: output/)"
    hmm_group.add_argument("-d", "--outDir",
                           type=str,
                           dest="outDir",
                           default="output",
                           help=helpstr)

    hmm_group.add_argument("-p", "--primer",
                           type=str,
                           dest="primerFN",
                           default=None,
                           help="Primer FASTA file (default: primers.fasta)")

    tcp.add_str(BaseConstants.PRIMER_SEQUENCES_ID, "customer_primers",
                default=BaseConstants.PRIMER_SEQUENCES_DEFAULT,
                name="Customer Primer Sequences",
                description="Customer primer sequences.")

    hmm_group.add_argument("--cpus",
                           default=8,
                           type=int,
                           dest="cpus",
                           help="Number of CPUs to run HMMER (default: 8)")

    hmm_group.add_argument("--summary",
                           default=None,
                           type=str,
                           dest="summary_fn",
                           help="TXT file to output classsify summary (" +
                                "default: *.classify_summary.txt")
    tcp.add_output_file_type(FileTypes.JSON, "json_summary",
        name="Transcript Classification Report",
        description="JSON summary",
        default_name="summary")

    hmm_group.add_argument("--report",
                           default=None,
                           type=str,
                           dest="primerReportFN",
                           help="CSV file to output primer info (" +
                                "default: *.primer_info.csv")
    tcp.add_output_file_type(FileTypes.CSV, "report",
        name="Primer Info",
        description="Per-CCS read annotation and classification results",
        default_name="isoseq_primer_info")

    chi_group = parser.add_argument_group("Chimera detection options")

    helpstr = "Minimum sequence length to output (default: %s)" % BaseConstants.MIN_SEQ_LEN_DEFAULT
    chi_group.add_argument("--min_seq_len",
                           type=int,
                           dest="min_seq_len",
                           default=BaseConstants.MIN_SEQ_LEN_DEFAULT,
                           help=helpstr)
    tcp.add_int(BaseConstants.MIN_SEQ_LEN_ID, "min_seq_len",
        default=BaseConstants.MIN_SEQ_LEN_DEFAULT,
        name="Minimum Sequence Length",
        description=helpstr)

    helpstr = "Minimum phmmer score for primer hit (default: 10)"
    chi_group.add_argument("--min_score",
                           dest="min_score",
                           type=float,
                           default=BaseConstants.MIN_SCORE_DEFAULT,
                           help=helpstr)
    #tcp.add_int(BaseConstants.MIN_SCORE_ID, "min_score",
    #    default=BaseConstants.MIN_SCORE_DEFAULT,
    #    name="Min. score",
    #    description=helpstr)

    helpstr = "Search primers within windows of length searchPrimerWindow " + \
              "(default: 100)."
    chi_group.add_argument("--primer_search_window",
                           dest="primer_search_window",
                           type=int,
                           default=100,
                           help=argparse.SUPPRESS)

    helpstr = "Minimum distance the primer hit has to be from " + \
              "the end of sequence (default: 100)."
    chi_group.add_argument("--min_dist_from_end",
                           dest="min_dist_from_end",
                           type=int,
                           default=100,
                           help=argparse.SUPPRESS)

    helpstr = "Maximum distance between adjacent primer hits to " + \
              "consider as chimera (default: 50)."
    chi_group.add_argument("--max_adjacent_hit_dist",
                           dest="max_adjacent_hit_dist",
                           type=int,
                           default=50,
                           help=argparse.SUPPRESS)

    helpstr = "Detect chimeric reads among non-full-length reads. " + \
              "Non-full-length non-chimeric/chimeric reads will " + \
              "saved to outDir/nflnc.fasta and outDir/nflc.fasta."
    chi_group.add_argument("--detect_chimera_nfl",
                           dest="detect_chimera_nfl",
                           default=False,
                           action="store_true",
                           help=helpstr)

    read_group = parser.add_argument_group("Read extraction options")
    helpstr = "FL does not require polyA tail (default: turned off)"
    read_group.add_argument("--ignore_polyA",
                            dest="ignore_polyA",
                            default=False,
                            action="store_true",
                            help=helpstr)

    # SAT-1010, avoid double-negative in GUI
    helpstr = "FL requires polyA tail (default: turned on)"
    tcp.add_boolean(BaseConstants.REQUIRE_POLYA_ID, "require_polyA",
        default=BaseConstants.REQUIRE_POLYA_DEFAULT,
        name="Require polyA",
        description=helpstr)

    helpstr = "Reuse previously built dom files by phmmer"
    parser.add_argument("--reuse_dom",
                        dest="reuse_dom",
                        default=False,
                        action="store_true",
                        help=argparse.SUPPRESS)

    parser.add_argument("--ignore-empty-output", dest="ignore_empty_output",
        default=False, action="store_true", help="DEVELOPER OPTION")

#    helpstr = "Change read id to reflect trimming (default: off)."
#    parser.add_argument("--changeReadId",
#                        dest="changeReadId",
#                        action="store_const",
#                        const=True,
#                        default=False,
#                        help=argparse.SUPPRESS)
#
#    helpstr = "Trim polyA tails from reads (default: on)."
#    parser.add_argument("--trimPolyA",
#                        dest="trimPolyA",
#                        action="store_const",
#                        const=False,
#                        default=True,
#                        help=argparse.SUPPRESS)
#


def add_ice_arguments(arg_parser, tc_parser=None):
    """Add Ice options as a group to parser, return parser"""
    ice_group = arg_parser.add_argument_group("ICE arguments")

    ice_group.add_argument("--quiver",
                           dest="quiver",
                           default=False,
                           action="store_true",
                           help="Call quiver to polish consensus isoforms " +
                                "using non-full-length non-chimeric CCS "+
                                "reads.")

    ice_group.add_argument("--targeted_isoseq",
                           dest="targeted_isoseq",
                           default=False,
                           action="store_true",
                           help="Input data is from targeted Iso-Seq. Automatically make parameter adjustments.")

    ice_group.add_argument("--ece_penalty", dest="ece_penalty", type=int, default=1)
    ice_group.add_argument("--ece_min_len", dest="ece_min_len", type=int, default=20)

    # number of quiver jobs per bin
    ice_group.add_argument("--num_clusters_per_bin",
                           type=int,
                           dest="num_clusters_per_bin",
                           action="store",
                           default=100,
                           help=argparse.SUPPRESS)
    # number of flnc reads per split
    ice_group.add_argument("--flnc_reads_per_split",
                           type=int,
                           action="store",
                           default=20000,
                           help=argparse.SUPPRESS)
    # number of nfl reads per split
    ice_group.add_argument("--nfl_reads_per_split",
                           type=int,
                           action="store",
                           default=30000,
                           help=argparse.SUPPRESS)

    desc = "Use finer classes of QV information from CCS input instead of "+\
           "a single QV from FASTQ.  This option is slower and consumes "+\
           "more memory."
    ice_group.add_argument("--use_finer_qv",
                           dest="use_finer_qv",
                           default=False,
                           action="store_true",
                           help=desc)

    # FIXME 2015-10-06 disabling this because the new CCS outputs do not
    # contain the necessary QVs.  it does, however, make a difference for the
    # rat_bax1 test data (see tests/regression and the rat_bax1 pbsmrtpipe
    # testkit job)
    if False: #tc_parser is not None:
        tc_parser.add_boolean(
            option_id=BaseConstants.USE_FINER_QV_ID,
            option_str="use_finer_qv",
            default=BaseConstants.USE_FINER_QV_DEFAULT,
            name="Use finer QV values",
            description=desc)
    return arg_parser


def add_sge_arguments(arg_parser, blasr_nproc=False, quiver_nproc=False, gcon_nproc=False):
    """Add Sge arguments as a group to parser, return parser."""
    sge_group = arg_parser.add_argument_group("SGE environment arguments")

    sge_group.add_argument("--use_sge",
                           dest="use_sge",
                           default=False,
                           action="store_true",
                           help="Use SGE computing cluster")

    sge_group.add_argument("--max_sge_jobs",
                           type=int,
                           dest="max_sge_jobs",
                           default=30,
                           action="store",
                           help="The maximum number of jobs that will " +
                                "be submitted to SGE concurrently.")

    sge_group.add_argument("--unique_id",
                           type=int,
                           dest="unique_id",
                           action="store",
                           default=random.randint(1, 100000000),
                           help="Unique ID for submitting SGE jobs.")
    if blasr_nproc is True:
        sge_group.add_argument("--blasr_nproc",
                               type=int,
                               dest="blasr_nproc",
                               action="store",
                               default=24,
                               help="Number of cores for each BLASR|Daligner job. (default: 24)")
    if quiver_nproc is True:
        sge_group.add_argument("--quiver_nproc",
                               dest="quiver_nproc",
                               type=int,
                               default=8,
                               help="Number of CPUs each quiver job uses. (default: 8)")
    if gcon_nproc is True:
        sge_group.add_argument("--gcon_nproc",
                               dest="gcon_nproc",
                               type=int,
                               default=4,
                               help="Number of CPUs for each PBDagcon job. (default: 4)")

    sge_group.add_argument("--sge_env_name",
                           type=str,
                           dest="sge_env_name",
                           default="smp",
                           action="store",
                           help="SGE parallel environment, e.g, smp, orte (default: smp).")

    sge_group.add_argument("--sge_queue",
                           type=str,
                           dest="sge_queue",
                           default=None,
                           action="store",
                           help="SGE queue to submit jobs.")

    return arg_parser


def add_ice_post_quiver_hq_lq_io_arguments(parser):
    """Add polished high-quality|low-quality isoforms in FASTA|FASTQ files."""
    if isinstance(parser, PbParser):
        # parser = _wrap_parser(parser)
        arg_parser = parser.arg_parser.parser
        tcp = parser.tool_contract_parser
        tcp.add_output_file_type(FileTypes.DS_CONTIG, "hq_isoforms_fa",
                                 name="High-Quality Isoforms",
                                 description="Isoforms with high consensus accuracy",
                                 default_name="hq_isoforms")
        tcp.add_output_file_type(FileTypes.FASTQ, "hq_isoforms_fq",
                                 name="High-Quality Isoforms",
                                 description="Isoforms with high consensus accuracy",
                                 default_name="hq_isoforms")
        tcp.add_output_file_type(FileTypes.DS_CONTIG, "lq_isoforms_fa",
                                 name="Low-Quality Isoforms",
                                 description="Isoforms with low consensus accuracy",
                                 default_name="lq_isoforms")
        tcp.add_output_file_type(FileTypes.FASTQ, "lq_isoforms_fq",
                                 name="Low-Quality Isoforms",
                                 description="Isoforms with low consensus accuracy",
                                 default_name="lq_isoforms")
    else:
        assert isinstance(parser, argparse.ArgumentParser)
        arg_parser = parser

    icq_gp = arg_parser.add_argument_group("IceQuiver HQ/LQ IO arguments")
    icq_gp.add_argument("--hq_isoforms_fa",
                        default=None,
                        type=str,
                        dest="hq_isoforms_fa",
                        help="Quiver|Arrow polished, high quality isoforms " +
                        "in FASTA, default: root_dir/output/all_quivered_hq.fasta")

    icq_gp.add_argument("--hq_isoforms_fq",
                        default=None,
                        type=str,
                        dest="hq_isoforms_fq",
                        help="Quiver|Arrow polished, high quality isoforms " +
                        "in FASTQ, default: root_dir/output/all_quivered_hq.fastq")

    icq_gp.add_argument("--lq_isoforms_fa",
                        default=None,
                        type=str,
                        dest="lq_isoforms_fa",
                        help="Quiver|Arrow polished, low quality isoforms " +
                        "in FASTA, default: root_dir/output/all_quivered_lq.fasta")

    icq_gp.add_argument("--lq_isoforms_fq",
                        default=None,
                        type=str,
                        dest="lq_isoforms_fq",
                        help="Quiver|Arrow polished, low quality isoforms " +
                        "in FASTQ, default: root_dir/output/all_quivered_lq.fastq")
    return parser


def add_ice_post_quiver_hq_lq_arguments(parser):
    """Add quiver QV threshold to mark an isoform as high-quality or low-quality.
    Add quiver output arguments."""
    parser = add_ice_post_quiver_hq_lq_qv_arguments(parser)
    return add_ice_post_quiver_hq_lq_io_arguments(parser)


def add_ice_post_quiver_hq_lq_qv_arguments(parser):
    """Add quiver QV threshold to mark an isoform as high-quality or low-quality."""
    if isinstance(parser, PbParser):
        #parser = _wrap_parser(parser)
        arg_parser = parser.arg_parser.parser
        tcp = parser.tool_contract_parser
        tcp.add_float(BaseConstants.HQ_QUIVER_MIN_ACCURACY_ID, "hq_quiver_min_accuracy",
                      default=BaseConstants.HQ_QUIVER_MIN_ACCURACY_DEFAULT,
                      name="Minimum Quiver|Arrow Accuracy", description=BaseConstants.HQ_QUIVER_MIN_ACCURACY_DESC)
        tcp.add_int(BaseConstants.QV_TRIM_FIVEPRIME_ID, "qv_trim_5",
                    default=BaseConstants.QV_TRIM_FIVEPRIME_DEFAULT,
                    name="Trim QVs 5'", description=BaseConstants.QV_TRIM_FIVEPRIME_DESC)
        tcp.add_int(BaseConstants.QV_TRIM_THREEPRIME_ID, "qv_trim_3",
                    default=BaseConstants.QV_TRIM_THREEPRIME_DEFAULT,
                    name="Trim QVs 3'", description=BaseConstants.QV_TRIM_THREEPRIME_DESC)
    else:
        assert isinstance(parser, argparse.ArgumentParser)
        arg_parser = parser

    icq_gp = arg_parser.add_argument_group("IceQuiver High QV/Low QV arguments")
    icq_gp.add_argument("--hq_quiver_min_accuracy",
                        type=float,
                        default=BaseConstants.HQ_QUIVER_MIN_ACCURACY_DEFAULT,
                        dest="hq_quiver_min_accuracy",
                        help=BaseConstants.HQ_QUIVER_MIN_ACCURACY_DESC)
    icq_gp.add_argument("--qv_trim_5",
                        type=int,
                        default=BaseConstants.QV_TRIM_FIVEPRIME_DEFAULT,
                        dest="qv_trim_5",
                        help=BaseConstants.QV_TRIM_FIVEPRIME_DESC)
    icq_gp.add_argument("--qv_trim_3",
                        type=int,
                        default=BaseConstants.QV_TRIM_THREEPRIME_DEFAULT,
                        dest="qv_trim_3",
                        help=BaseConstants.QV_TRIM_THREEPRIME_DESC)
    return parser


def add_fofn_arguments(arg_parser, ccs_fofn=False, bas_fofn=False, fasta_fofn=False,
                       tool_contract_parser=None):
    """Add ccs_fofn, bas_fofn, fasta_fofn arguments."""
    helpstr = "A FOFN of ccs.bam or dataset xml (e.g., ccs.fofn|bam|consensusreadset.xml), " + \
              "which contain quality values of consensus (CCS) reads. " + \
              "If not given, assume there is no QV information available."
    if ccs_fofn is True:
        arg_parser.add_argument("--ccs_fofn",
                                dest="ccs_fofn",
                                type=validate_fofn,
                                default=None,
                                action="store",
                                help=helpstr)
        if tool_contract_parser is not None:
            tool_contract_parser.add_input_file_type(FileTypes.DS_CCS,
                "ccs_fofn", "CCS dataset", helpstr)

    helpstr = "A FOFN of bam or dataset xml (e.g., input.fofn|bam|subreadset.xml), " + \
              "which contain quality values of raw reads and subreads"
    if bas_fofn is True:
        arg_parser.add_argument("--bas_fofn",
                                dest="bas_fofn",
                                type=validate_fofn,
                                default=None,
                                action="store",
                                help=helpstr)
        if tool_contract_parser is not None:
            tool_contract_parser.add_input_file_type(FileTypes.DS_SUBREADS,
                "subreads_fofn", "SubreadSet", helpstr)

    helpstr = "A FOFN of trimmed subreads fasta (e.g. input.fasta.fofn)"
    if fasta_fofn is True:
        arg_parser.add_argument("--fasta_fofn",
                                dest="fasta_fofn",
                                type=validate_fofn,
                                default=None,
                                help=helpstr)
    return arg_parser


def add_flnc_fa_argument(parser, positional=False, required=False):
    """Add FASTA arguments: flnc_fa, can be positional or non-positional,
    required or not required."""
    helpstr = "Input full-length non-chimeric reads in FASTA or ContigSet format, " + \
              "used for clustering consensus isoforms, e.g., isoseq_flnc.fasta"
    if positional is True:
        parser.add_input_file_type(FileTypes.DS_CONTIG, "flnc_fa",
            name="FASTA or ContigSet file",
            description=helpstr)
    else:
        assert(required is True or required is False)
        # in this case only the argparse layer gets it
        parser.arg_parser.parser.add_argument("--flnc_fa", type=str,
            dest="flnc_fa", required=required, help=helpstr)
    return parser


def add_nfl_fa_argument(arg_parser, positional=False, required=False,
        tool_contract_parser=None):
    """
    Add nfl_fa or --nfl_fa, can be positional  or non-positional,
    required or not required.  (For the tool contract interface, it is
    always required, since we will be guaranteed to have this file internally.)
    """
    # note however that the nfl transcripts may not be used by the cluster
    # command if polishing mode is not run - they will however be handled by
    # the separately run ice_partial task
    helpstr = "Input non-full-length reads in FASTA or ContigSet format, used for " + \
              "polishing consensus isoforms, e.g., isoseq_nfl.fasta"
    if positional is True:
        arg_parser.add_argument("nfl_fa", type=str, help=helpstr)
    else:
        assert(required is True or required is False)
        arg_parser.add_argument("--nfl_fa", type=str, dest="nfl_fa",
                                required=required, help=helpstr)

    if tool_contract_parser is not None:
        tool_contract_parser.add_input_file_type(FileTypes.DS_CONTIG,
            "nfl_fa", "FASTA or ContigSet file", helpstr)
    return arg_parser


def add_cluster_root_dir_as_positional_argument(arg_parser):
    """Add root_dir as root output directory for `cluster`."""
    helpstr = "An directory to store temporary and output cluster files" + \
              " (e.g., in SA3.2, tasks/pbtranscript.tasks.separate_flnc-0/0to1kb_part0/cluster_out; in SA2.3, data/clusterOutDir/)"
    arg_parser.add_argument("root_dir", help=helpstr, type=str)
    return arg_parser


def add_cluster_summary_report_arguments(parser):
    """Add a report and a summary to summarize isoseq cluster."""
    helpstr = "CSV file to output cluster info " + \
              "(default: *.cluster_report.csv)"
    p1 = parser.tool_contract_parser
    p2 = parser.arg_parser.parser

    helpstr = "TXT file to output cluster summary " + \
              "(default: *.cluster_summary.txt)"
    p2.add_argument("--summary", default=None, type=str,
                        dest="summary_fn", help=helpstr)
    p1.add_output_file_type(FileTypes.JSON, "json_summary",
        name="Transcript Clustering Report",
        description="JSON summary",
        default_name="summary")

    # FIXME make this a REPORT instead?
    p1.add_output_file_type(FileTypes.CSV, "cluster_report",
        name="Clustering Results",
        description="Clustering results for each CCS read",
        default_name="cluster_report")
    p2.add_argument("--report", default=None, type=str,
                    dest="report_fn", help=helpstr)

    p2.add_argument("--pickle_fn", default=None, type=str,
        dest="pickle_fn")
    return parser


def add_tmp_dir_argument(parser):
    """Add an argument for specifying tempoary directory, which
    will be created for storing intermediate files of isoseq
    clusters.
    """
    helpstr = "Directory to store temporary files." + \
              "(default, write to root_dir/tmp.)."
    parser.add_argument("--tmp_dir", default=None, type=str,
                        dest="tmp_dir", help=helpstr)
    return parser


def add_use_blasr_argument(parser):
    """Add an arugument to specify whether or not to use
    blasr or to use daligner. When turned on, use blasr,
    otherwise, use daligner."""
    helpstr = "Whether or not to use blasr. (Deafult, False)"
    parser.add_argument("--use_blasr", default=False,
                        dest="use_blasr", action='store_true',
                        help=helpstr)
    return parser


def add_cluster_arguments(parser):
    """Add arguments for subcommand `cluster`."""
    parser = add_flnc_fa_argument(parser, positional=True)

    parser.add_output_file_type(FileTypes.DS_CONTIG, "consensusFa",
        name="Unpolished Consensus Isoforms",
        description="Consensus isoforms which have not been polished",
        default_name="consensus_isoforms")

    arg_parser = parser.arg_parser.parser
    tool_contract_parser = parser.tool_contract_parser
    arg_parser = add_nfl_fa_argument(arg_parser, positional=False,
                                     required=False,
                                     tool_contract_parser=tool_contract_parser)
    arg_parser = add_fofn_arguments(arg_parser, ccs_fofn=True, bas_fofn=True, fasta_fofn=True,
                                    tool_contract_parser=tool_contract_parser)

    helpstr = "Directory to store temporary and output cluster files." + \
        "(default: cluster_out/)"
    arg_parser.add_argument("-d", "--outDir",
                            type=str,
                            dest="root_dir",
                            default="cluster_out",
                            help=helpstr)

    arg_parser = add_tmp_dir_argument(arg_parser)

    parser = add_cluster_summary_report_arguments(parser)

    # Add Ice options, including --quiver
    arg_parser = add_ice_arguments(arg_parser, tc_parser=tool_contract_parser)

    # Add Sge options
    arg_parser = add_sge_arguments(arg_parser, blasr_nproc=True,
                                   quiver_nproc=True, gcon_nproc=True)

    # Add IceQuiver HQ/LQ options.
    arg_parser = add_ice_post_quiver_hq_lq_arguments(arg_parser)


def add_subset_arguments(parser):
    """Add arguments for subcommand `subset`."""

    parser.add_input_file_type(FileTypes.DS_CONTIG, "readsFN",
        name="ContigSet",
        description="Input FASTA file (usually isoseq_draft.fasta)")
    parser.add_output_file_type(FileTypes.DS_CONTIG, "outFN",
        name="Output FASTA or ContigSet",
        description="Output FASTA file",
        default_name="pbtranscript_subset_out")

    parser = parser.arg_parser.parser
    group = parser.add_mutually_exclusive_group()
    helpstr = "Reads to outut must be Full-Length, with 3' " + \
              "primer and 5' primer and polyA tail seen."
    group.add_argument('--FL',
                       dest='FL',
                       const=1,  # 0: non-FL, 1: FL, 2: either
                       action='store_const',
                       default=2,
                       help=helpstr)

    helpstr = "Reads to output must be Non-Full-Length reads."
    group.add_argument('--nonFL',
                       dest='FL',  # 0: non-FL, 1: FL, 2: either
                       const=0,
                       action='store_const',
                       help=helpstr)

    group = parser.add_mutually_exclusive_group()
    helpstr = "Reads to output must be non-chimeric reads."
    group.add_argument('--nonChimeric',
                       dest='nonChimeric',
                       const=1,  # 0: chimeric, 1, non-chimeric, 2: either
                       default=2,
                       action='store_const',
                       help=helpstr)

    helpstr = "Reads to output must be chimeric reads."
    group.add_argument('--chimeric',
                       dest='nonChimeric',
                       const=0,  # 0: chimeric, 1, non-chimeric, 2: either
                       action='store_const',
                       help=helpstr)

    helpstr = "Only print read lengths, no read names and sequences."
    parser.add_argument('--printReadLengthOnly',
                        default=False,
                        dest='printReadLengthOnly',
                        action='store_true',
                        help=helpstr)

    helpstr = "FL does not require polyA tail (default: turned off)"
    parser.add_argument("--ignore_polyA",
                        dest="ignore_polyA",
                        default=False,
                        action="store_true",
                        help=helpstr)

def _wrap_parser(arg_parser):
    p_wrap = get_base_contract_parser(BaseConstants)
    p_wrap.arg_parser.parser = arg_parser
    return p_wrap

def get_argument_parser():
    ap = get_default_argparser_with_base_opts(get_version(),
        "Toolkit for cDNA analysis.", default_level="WARN")
    subparsers = ap.add_subparsers(dest="subCommand")
    arg_parser = subparsers.add_parser(
        'classify',
        description="Classify reads based on whether they are " +
                    "non-chimeric, full length and have their 5', " +
                    "3' and poly A tail seen.")
    # Add arguments for subcommand classify
    add_classify_arguments(_wrap_parser(arg_parser))

    arg_parser = subparsers.add_parser(
        'cluster',
        description='Discover consensus isoforms based on ' +
                    'quality controlled non-chimeric, ' +
                    'full length reads to reference genome.')
    # Add arguments for subcommand cluster
    add_cluster_arguments(_wrap_parser(arg_parser))

    arg_parser = subparsers.add_parser(
        'subset',
        description='Subset annotated reads in FASTA format.')
    add_subset_arguments(_wrap_parser(arg_parser))
    ap.add_argument(
        "--profile", action="store_true",
        help="Print runtime profile at exit")
    return ap

def get_base_contract_parser(Constants=BaseConstants, default_level="WARN"):
    p = get_pbparser(
        tool_id=Constants.TOOL_ID,
        version=get_version(),
        name=Constants.TOOL_ID,
        description=Constants.PARSER_DESC,
        driver_exe=Constants.DRIVER_EXE,
        nproc=SymbolTypes.MAX_NPROC,
        resource_types=(ResourceTypes.TMP_DIR,),
        default_level=default_level)
    return p

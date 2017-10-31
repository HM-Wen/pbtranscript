#!/usr/bin/env python

"""
Class `CountRunner` to report read status of FL and nFL reads,
as well as make abundance report.
"""
import logging
import os.path as op
import cPickle

#from pbtranscript.Utils import ln
#from pbtranscript.io import *
from pbtranscript.ice.IceFiles import IceFiles
from pbtranscript.counting import read_group_file, output_read_count_FL, \
        output_read_count_nFL, make_abundance_file

__all__ = ["CountRunner"]

__author__ = 'etseng@pacificbiosciences.com'

#log = logging.getLogger(__name__)

class Constants(object):
    """Constants used in tool contract."""
    TOOL_ID = "pbtranscript.tasks.count"
    DRIVER_EXE = "python -m %s --resolved-tool-contract " % TOOL_ID
    PARSER_DESC = __doc__


#class CountFiles(object):
#    """
#    Class defines output files produced by CountRunner.
#    """
#    def __init__(self, prefix):
#        self.prefix = prefix
#
#    @property
#    def read_stat_fn(self):
#        """Path to read status report, including both FL and nFL reads."""
#        return self.prefix + ".read_stat.txt"
#
#    @property
#    def abundance_fn(self):
#        """Output abundance report."""
#        return self.prefix + ".abundance.txt"


class CountRunner(object):
    """
    Compute read status of FL and nFL CCS reads and output abundance report.
    """
    def __init__(self, group_filename, pickle_filename,
                 output_read_stat_filename,
                 output_abundance_filename):
        """
        Parameters:
          group_filename -- an input group file associating collapsed isoforms with FL/nFL reads.
          pickle_filename --an input *.hq_lq_pre_dict.pickle, containing
              ['HQ'] --> a dict of HQ isoforms sample prefix --> cluster output directory
          output_read_stat_filename -- an output FL and nFL read status report
          output_abundance_filename -- an output abundance report
        """
        #prefix = op.join(op.dirname(group_filename),
        #                 op.basename(group_filename).split(".")[0])

        # output read status report and abundance report
        self.read_stat_fn = output_read_stat_filename
        self.abundance_fn = output_abundance_filename

        self.group_filename = group_filename # input, group file of collapsed isoforms
        # input, *.hq_lq_pre_dict.pickle
        self.pickle_filename = pickle_filename
        self.validate_inputs()

        # read a dict of HQ isoforms sample_prefix --> cluster_out directory from pickle
        # ignore LQ isoforms
        try:
            self.prefix_dict = cPickle.load(open(pickle_filename, 'rb'))['HQ']
        except (ValueError, KeyError, IOError):
            raise ValueError("Could not load sample prefix dict (a['HQ']) from pickle %s" %
                             pickle_filename)

    @property
    def sample_prefixes(self):
        """Sample prefixes"""
        return [k if not k.endswith('|') else k[0:-1] for k in self.prefix_dict.keys()]

    def __str__(self):
        return ("<%s (%s, %s) to count reads abundance of isoforms>\n" %
                (self.__class__.__name__, self.group_filename, self.pickle_filename))

    def validate_inputs(self):
        """Validate existence of input files."""
        logging.info("Validing inputs.")
        if not op.exists(self.group_filename):
            raise IOError("Input group file %s does not exist" % self.group_filename)
        if not op.exists(self.pickle_filename):
            raise IOError("Input hq lq prefix dict pickle file %s does not exist" %
                          self.pickle_filename)

    @property
    def prefix_fl_pickle_tuples(self):
        """Returns a list of (sample_prefix, fl_uc_pickle) tuples."""
        ret = []
        for sample_prefix, cluster_out_d in self.prefix_dict.iteritems():
            sample_prefix = sample_prefix if not sample_prefix.endswith('|') else sample_prefix[0:-1]
            fl_fn = IceFiles(prog_name="Count", root_dir=cluster_out_d, no_log_f=True, make_dirs=False).final_pickle_fn
            if not op.exists(fl_fn):
                raise IOError("FL pickle %s of sample prefix %s does not exist." %
                              (fl_fn, sample_prefix))
            ret.append((sample_prefix, fl_fn))
        return ret

    @property
    def prefix_nfl_pickle_tuples(self):
        """Returns a list of (sample_prefix, nfl_uc_pickle) tuples."""
        ret = []
        for sample_prefix, cluster_out_d in self.prefix_dict.iteritems():
            sample_prefix = sample_prefix if not sample_prefix.endswith('|') else sample_prefix[0:-1]
            nfl_fn = IceFiles(prog_name="Count", root_dir=cluster_out_d, no_log_f=True, make_dirs=False).nfl_all_pickle_fn
            if not op.exists(nfl_fn):
                raise IOError("NFL pickle %s of sample prefix %s does not exist." %
                              (nfl_fn, sample_prefix))
            ret.append((sample_prefix, nfl_fn))
        return ret

    def run(self, restricted_movies=None):
        """
        Compute read status for FL and nFL reads, and make abundance report.
        Parameters:
          restricted_movies -- if is None, process reads from ALL movies; otherwise
                               only process reads in the list of restricted movies.
        """
        # Read cid info from the input group file.
        cid_info = read_group_file(group_filename=self.group_filename,
                                   is_cid=True,
                                   sample_prefixes=self.sample_prefixes)

        # Output FL read status
        logging.debug("Computing read status of FL reads.")
        output_read_count_FL(cid_info=cid_info,
                             prefix_pickle_filename_tuples=self.prefix_fl_pickle_tuples,
                             output_filename=self.read_stat_fn,
                             output_mode='w', restricted_movies=restricted_movies)
        logging.info("Read status of FL reads written to %s", self.read_stat_fn)

        # Append nFL read status
        logging.debug("Computing read status of nFL reads.")
        output_read_count_nFL(cid_info=cid_info,
                              prefix_pickle_filename_tuples=self.prefix_nfl_pickle_tuples,
                              output_filename=self.read_stat_fn,
                              output_mode='a', restricted_movies=restricted_movies)
        logging.info("Read status of nFL reads written to %s", self.read_stat_fn)

        # Make abundance file
        make_abundance_file(read_stat_filename=self.read_stat_fn,
                            output_filename=self.abundance_fn,
                            given_total=None, restricted_movies=restricted_movies,
                            write_header_comments=True)
        logging.info("Abundance file written to %s", self.abundance_fn)

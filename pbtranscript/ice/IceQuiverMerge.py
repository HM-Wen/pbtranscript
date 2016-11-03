#!/usr/bin/env python
###############################################################################
# Copyright (c) 2011-2013, Pacific Biosciences of California, Inc.
#
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# * Redistributions of source code must retain the above copyright
#   notice, this list of conditions and the following disclaimer.
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
# * Neither the name of Pacific Biosciences nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# NO EXPRESS OR IMPLIED LICENSES TO ANY PARTY'S PATENT RIGHTS ARE GRANTED BY
# THIS LICENSE.  THIS SOFTWARE IS PROVIDED BY PACIFIC BIOSCIENCES AND ITS
# CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT
# NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A
# PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL PACIFIC BIOSCIENCES OR
# ITS CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS;
# OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY,
# WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR
# OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
###############################################################################

"""
Overview:
    pbtranscript cluster contains two main components:
    * (1) ICE (iterative clustering and error correction) to predict
      unpolished consensus isoforms.
    * (2) Polish, to use nfl reads and quiver to polish those predicted
      unpolished isoforms. Polish contains three steps:
      + (2.1) IceAllPartials (ice_partial.py all)
              Align and assign nfl reads to unpolished isoforms, and
              save results to a pickle file.
      + (2.2) IceQuiver (ice_quiver.py i and ice_quiver.py merge)
              Polish each isoform based on alignments
              created by mapping its associated fl and nfl reads to
              this isoform.
      + (2.3) IceQuiverPostprocess (ice_quiver.py postprocess)
              Collect and post process quiver results, and classify
              HQ/LQ isoforms.

    In order to handle subtasks by SMRTPipe instead of pbtranscript
    itself, we will refactor the polish phase including
    (2.1) (2.2) and (2.3). The refactor of (2.1) is described in
    ice_partial.py.

    (2.2) IceQuiver will be refactored to
       + (2.2.1) IceQuiverI (ice_quiver.py i)
                 Split all unpolished isoforms into N chunks and
                 polish isoforms of the i-th chunk at a time
       + (2.2.2) IceQuiverMerge (ice_quiver.py merge)
                 When all splitted quiver jobs are done,
                 collect all submitted jobs and save to
                 root_dir/log/submitted_quiver_jobs.txt
    (2.3) IceQuiverPostprocess's entry will be renamed from
          ice_post_quiver.py to:
       + (2.3.1) ice_quiver.py postprocess

    e.g., IceQuiver (2.2) =
               ice_quiver_i.py root_dir 0 N   --> process the 0 th chunk
            +  ...
            +  ice_quiver_i.py root_dir N-1 N --> process the N-1 th chunk
            +  ice_quiver_merge.py root_dir N --> merge all polished isoforms
                                                  from N chunks

    *** Here we are focusing on (2.2.2) 'ice_quiver.py merge' ***

Description:
    (2.2.2) ice_quiver.py merge

    Assumption:
     * Phase (1) ICE is done, unpolished isoforms are created, fl reads
       are assigned to isoforms, and saved to a pickle (i.e., final.pickle)
     * Step (2.1) IceAllPartials is done, all nfl reads are assigned
       to unpolished isoforms, saved to a pickle (i.e., nfl_all_pickle_fn)
     * Step (2.2.1) IceQuiverI is done on all chunks (e.g., 0, ..., N-1).
       Submitted quiver jobs of the i-th chunk is saved at:
       root_dir/log/submitted_quiver_jobs.{i}of{N}.txt

    Process:
       Given root_dir and N, clusters (isoforms) were splitted into N
       chunks and quiver jobs of all chunks were done. Now we will merge
       all submitted jobs to one file.

    Input:
        Positional:
            root_dir, an output directory for running pbtranscript cluster.
            N, the total number of quiver workload chunks.
    Output:
        Collect all submitted quiver jobs and save them to
        root_dir/log/submitted_quiver_jobs.txt

    Hierarchy:
        pbtranscript = IceIterative

        pbtranscript --quiver = IceIterative + \
                                ice_polish.py

        ice_polish.py =  ice_make_fasta_fofn.py + \
                         ice_partial.py all + \
                         ice_quiver.py all

        ice_partial.py all = ice_partial.py split + \
                             ice_partial.py i + \
                             ice_partial.py merge

        (ice_partial.py one --> only apply ice_partial on a given input fasta)

        ice_quiver.py all = ice_quiver.py i + \
                            ice_quiver.py merge + \
                            ice_quiver.py postprocess

    Example:
        ice_quiver.py merge root_dir N

Alternative way to call this script:
    python -m pbtranscript.ice_quiver merge
"""

import logging
import sys
import os.path as op
from pbcore.util.ToolRunner import PBToolRunner
from pbtranscript.__init__ import get_version
from pbtranscript.PBTranscriptOptions import \
    add_cluster_root_dir_as_positional_argument
from pbtranscript.ice.IceQuiver import IceQuiver
from pbtranscript.Utils import cat_files, nfs_exists
from pbtranscript.ice.__init__ import ICE_QUIVER_PY


def add_ice_quiver_merge_arguments(parser):
    """Add IceQuiverMerge arguments."""
    parser = add_cluster_root_dir_as_positional_argument(parser)

    helpstr = "Number of workload chunks."
    parser.add_argument("N", help=helpstr, type=int)
    return parser


class IceQuiverMerge(object):

    """Merge all quiver polished isoforms done by N IceQuiverI jobs."""

    desc = "Unpolished isoforms were divided into N chunks and " + \
           "polished using Quiver or Arrow separately. Now collect all " + \
           "submitted polishing jobs from " + \
           "root_dir/log/submitted_quiver_jobs.{i}of{N}.txt " + \
           "(i=0,...,N-1) to root_dir/log/submitted_quiver_jobs.txt"

    prog = "%s merge" % ICE_QUIVER_PY

    def __init__(self, root_dir, N):
        self.root_dir = root_dir
        self.N = int(N)

    def getVersion(self):
        """Return version string."""
        return get_version()

    def cmd_str(self):
        """Return a cmd string of IceQuiverMerge ($ICE_QUIVER_PY merge)"""
        return self._cmd_str(root_dir=self.root_dir, N=self.N)

    def _cmd_str(self, root_dir, N):
        """Return a cmd string of IceQuiverMerge ($ICE_QUIVER_PY merge)."""
        cmd = " ".join([str(x) for x in (self.prog, root_dir, N)])
        return cmd

    def run(self):
        """Run"""
        iceq = IceQuiver(root_dir=self.root_dir, bas_fofn=None,
                         fasta_fofn=None, sge_opts=None,
                         prog_name="ice_quiver_merge")

        iceq.add_log(self.cmd_str())
        iceq.add_log("root_dir: {d}.".format(d=self.root_dir))
        iceq.add_log("Total number of chunks: N = {N}.".format(N=self.N))

        src = [iceq.submitted_quiver_jobs_log_of_chunk_i(i=i, num_chunks=self.N)
               for i in range(0, self.N)]
        for f in src:
            if not nfs_exists(f):
                raise IOError("Log {f} ".format(f=f) +
                              "of submitted quiver jobs does not exist.")

        dst = iceq.submitted_quiver_jobs_log

        iceq.add_log("Collecting submitted quiver jobs from:\n{src}\nto {dst}.".
                     format(src="\n".join(src), dst=dst))

        cat_files(src=src, dst=dst)

        iceq.close_log()


class IceQuiverMergeRunner(PBToolRunner):

    """IceQuiverMerge Runner"""

    def __init__(self):
        PBToolRunner.__init__(self, IceQuiverMerge.desc)
        add_ice_quiver_merge_arguments(self.parser)

    def getVersion(self):
        """Return version string."""
        return get_version()

    def run(self):
        """Run"""
        logging.info("Running {f} v{v}.".format(f=op.basename(__file__),
                                                v=get_version()))
        cmd_str = ""
        try:
            args = self.args
            iceqm = IceQuiverMerge(root_dir=args.root_dir, N=args.N)
            cmd_str = iceqm.cmd_str()
            iceqm.run()
        except:
            logging.exception("Exiting {cmd_str} with return code 1.".
                              format(cmd_str=cmd_str))
            return 1
        return 0


def main():
    """Main function."""
    runner = IceQuiverMergeRunner()
    return runner.start()

if __name__ == "__main__":
    sys.exit(main())

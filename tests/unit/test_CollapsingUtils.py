"""Test classes defined within pbtranscript.collapsing.CollaspingUtils."""
import os
import unittest
import os.path as op
from pbtranscript.Utils import rmpath, mkdir
from pbtranscript.io import CollapseGffReader, CollapseGffRecord
from pbtranscript.collapsing.CollapsingUtils import copy_sam_header, map_isoforms_and_sort, \
        concatenate_sam, can_merge, compare_fuzzy_junctions, collapse_fuzzy_junctions
import filecmp
from test_setpath import DATA_DIR, OUT_DIR, SIV_DATA_DIR

_SIV_DIR_ = op.join(SIV_DATA_DIR, "test_collapsing")
_DAT_DIR_ = op.join(DATA_DIR, "test_collapsing")
_OUT_DIR_ = op.join(OUT_DIR, "test collapsing")

GMAP_INPUT_FASTA = op.join(_SIV_DIR_, 'gmap-input.fasta')
GMAP_INPUT_FASTQ = op.join(_SIV_DIR_, 'gmap-input.fastq')
GMAP_INPUT_FASTA_DS = op.join(_SIV_DIR_, 'gmap-input.fasta.contigset.xml')
GMAP_INPUT_FASTQ_DS = op.join(_SIV_DIR_, 'gmap-input.fastq.contigset.xml')
GMAP_SAM = op.join(SIV_DATA_DIR, 'test_SAMReader', 'gmap-output.sam')

GMAP_DB = op.join(SIV_DATA_DIR, 'gmap-referenceset-root-dir/SIRV/')
GMAP_NAME = 'gmap_db'


class TEST_CollapsingUtils(unittest.TestCase):
    """Test functions of pbtranscript.collapsing.CollapsingUtils."""
    def setUp(self):
        """Define input and output file."""
        rmpath(_OUT_DIR_)
        mkdir(_OUT_DIR_)
        self.gmap_db_dir = op.join(_OUT_DIR_, 'gmap db dir')
        os.symlink(GMAP_DB, self.gmap_db_dir)

    def test_copy_sam_header(self):
        """Test copy_sam_header"""
        out_fn = op.join(_OUT_DIR_, 'test copy_sam_header.sam')
        copy_sam_header(GMAP_SAM, out_fn)
        with open(out_fn, 'r') as reader:
            lines = [r for r in reader]
            self.assertTrue(all([line.startswith('@') for line in lines]))
            self.assertEqual(len(lines), 9)

    def test_map_isoforms_and_sort(self):
        """Test map_isoforms_and_sort"""
        out_fn = op.join(_OUT_DIR_, 'test map_isoforms_and_sort_fasta.sam')
        rmpath(out_fn)
        map_isoforms_and_sort(input_filename=GMAP_INPUT_FASTA,
                              sam_filename=out_fn,
                              gmap_db_dir=self.gmap_db_dir,
                              gmap_db_name=GMAP_NAME,
                              gmap_nproc=10)
        self.assertTrue(op.exists(out_fn))

        out_fn = op.join(_OUT_DIR_, 'test map_isoforms_and_sort_fastq.sam')
        rmpath(out_fn)
        map_isoforms_and_sort(input_filename=GMAP_INPUT_FASTQ,
                              sam_filename=out_fn,
                              gmap_db_dir=self.gmap_db_dir,
                              gmap_db_name=GMAP_NAME,
                              gmap_nproc=10)
        self.assertTrue(op.exists(out_fn))

        out_fn = op.join(_OUT_DIR_, 'test map_isoforms_and_sort_fasta_ds.sam')
        rmpath(out_fn)
        map_isoforms_and_sort(input_filename=GMAP_INPUT_FASTA_DS,
                              sam_filename=out_fn,
                              gmap_db_dir=self.gmap_db_dir,
                              gmap_db_name=GMAP_NAME,
                              gmap_nproc=10)
        self.assertTrue(op.exists(out_fn))

        out_fn = op.join(_OUT_DIR_, 'test map_isoforms_and_sort_fastq_ds.sam')
        rmpath(out_fn)
        map_isoforms_and_sort(input_filename=GMAP_INPUT_FASTQ_DS,
                              sam_filename=out_fn,
                              gmap_db_dir=self.gmap_db_dir,
                              gmap_db_name=GMAP_NAME,
                              gmap_nproc=10)
        self.assertTrue(op.exists(out_fn))

    def test_concatenate_sam(self):
        """Test concatenate_sam(in_sam_files, out_sam)"""
        in_sam_files = [op.join(_SIV_DIR_, f)
                        for f in ["chunk0.sam", "chunk1.sam"]]
        out_sam = op.join(_OUT_DIR_, 'test concatenated.sam')
        expected_sam = op.join(_SIV_DIR_, "sorted-gmap-output.sam")
        concatenate_sam(in_sam_files, out_sam)

        self.assertTrue(op.exists(out_sam))
        self.assertTrue(op.exists(expected_sam))

        #self.assertTrue(filecmp.cmp(out_sam, expected_sam))
        out = [l for l in open(out_sam, 'r') if not l.startswith('@PG')]
        exp = [l for l in open(expected_sam, 'r') if not l.startswith('@PG')]
        # test everything other than @PG are identical
        self.assertEqual(out, exp)

        # chunk01.sam and chunk02.sam has identical PG ID in their SAM headers
        # test concatenated @PG IDs are not conflicting
        pg_ids = [x[3:] for pg in [l for l in open(out_sam, 'r') if l.startswith('@PG')]
                  for x in pg.split('\t') if x.startswith('ID:')]
        self.assertEqual(len(pg_ids), len(set(pg_ids)))
        self.assertEqual(len(pg_ids), 2)

    def test_collapse_fuzzy_junctions(self):
        """Test collapse_fuzzy_junctions, can_merge and compare_fuzzy_junctions."""
        test_name = "collapse_fuzzy_junctions"
        input_gff = op.join(_DAT_DIR_, "input_%s.gff" % test_name)
        input_group = op.join(_DAT_DIR_, "input_%s.group.txt" % test_name)
        output_gff = op.join(_OUT_DIR_, "output_%s.gff" % test_name)
        output_group = op.join(_OUT_DIR_, "output_%s.group.txt" % test_name)

        records = [r for r in CollapseGffReader(input_gff)]
        self.assertEqual(len(records), 4)

        r0, r1, r2, r3 = records
        # comparing r0 and r1
        m = compare_fuzzy_junctions(r0.ref_exons, r1.ref_exons, max_fuzzy_junction=5)
        self.assertEqual(m, "subset")
        self.assertTrue(can_merge(m, r0, r1, allow_extra_5exon=True, max_fuzzy_junction=5))

        # comparing r2 and r3
        m = compare_fuzzy_junctions(r2.ref_exons, r3.ref_exons, max_fuzzy_junction=5)
        self.assertEqual(m, "exact")
        self.assertTrue(can_merge(m, r2, r3, allow_extra_5exon=True, max_fuzzy_junction=5))

        # call collapse_fuzzy_junctions and write fuzzy output.
        collapse_fuzzy_junctions(gff_filename=input_gff,
                                 group_filename=input_group,
                                 fuzzy_gff_filename=output_gff,
                                 fuzzy_group_filename=output_group,
                                 allow_extra_5exon=True,
                                 max_fuzzy_junction=5)

        r4, r5 = [r for r in CollapseGffReader(output_gff)]
        self.assertEqual(r1, r4)
        self.assertEqual(r3, r5)

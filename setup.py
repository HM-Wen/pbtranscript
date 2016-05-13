from setuptools import setup, find_packages
from distutils.extension import Extension
import os.path
import sys

# icedagcon has been replaced by pbdagcon since SMRTAnalysis 2.3.
# The pseudo namespace 'pbtools' has been removed and the main entry
# script has changed from pbtranscript.py to pbtranscript post 2.3.

__author__ = "etseng|yli@pacificbiosciences.com"
version = "1.0.0"

if 'setuptools.extension' in sys.modules:
    m = sys.modules['setuptools.extension']
    m.Extension.__dict__ = m._Extension.__dict__

ext_modules = [Extension("pbtranscript.findECE",
                         ["pbtranscript/ice/C/findECE.pyx"]),
               Extension("pbtranscript.ice.ProbModel",
                         ["pbtranscript/ice/C/ProbModel.pyx"], language="c++"),
               Extension("pbtranscript.io.c_basQV",
                         ["pbtranscript/ice/C/c_basQV.pyx"], language="c++")
              ]


def _get_local_file(file_name):
    return os.path.join(os.path.dirname(__file__), file_name)


def _get_requirements(file_name):
    with open(file_name, 'r') as f:
        reqs = [line for line in f if not line.startswith("#")]
    return reqs


def _get_local_requirements(file_name):
    return _get_requirements(_get_local_file(file_name))


def run_cmd(cmd):
    import subprocess
    p = subprocess.Popen(cmd,
                         stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT,
                         shell=True)
    return p.stdin, p.stdout

def check_program(program):
    import re
    try:
        stdin, stdout = run_cmd('/usr/bin/which "%s"||echo no' % program)
        lines = stdout.readlines()
        match = filter(lambda x: re.search(program, x), lines)
        if match:
            return True
        else:
            return False
    except (IndexError, ValueError, AttributeError):
        print >> sys.stderr, '%s is required, please install %s' % program
        return False


def exit_if_not_installed(program):
    if (not check_program(program=program)):
        print >> sys.stderr, 'Unable to install - %s must be installed and in the PATH variable' % program
        sys.exit(1)


if ("install" in sys.argv):
    exit_if_not_installed("pbdagcon")
    #exit_if_not_installed("daligner")
    #exit_if_not_installed("dazcon")

setup(
    setup_requires=['setuptools_cython'],
    name = 'pbtranscript',
    version=version,
    author='Pacific Biosciences',
    author_email='devnet@pacificbiosciences.com',
    license='LICENSE.txt',
    ext_modules = ext_modules,
    scripts=['pbtranscript/ice_pbdagcon.py',
             'pbtranscript/ice_partial.py',
             'pbtranscript/ice_quiver.py',
             'pbtranscript/ice_fa2fq.py',
             'pbtranscript/ice_fa2fq.py',
             'pbtranscript/separate_flnc.py',
            ],
    entry_points={'console_scripts': [
        'pbtranscript = pbtranscript.PBTranscriptRunner:main',
        'fasta_splitter.py = pbtranscript.io.FastaSplitter:main',
        'filter_sam.py = pbtranscript.io.filter_sam:main',
        'ice_polish.py = pbtranscript.Polish:main',
        'ice_make_input_fasta_fofn.py = pbtranscript.ice.make_input_fasta_fofn:main'
        ]},
    package_dir={'pbtranscript': 'pbtranscript'},
    package_data={'pbtranscript':
                  ['data/PBMATRIX.txt',
                   'data/primers.fasta',
                   'data/gcon_in.fasta',
                   'data/gcon_out.fasta']},
    packages=find_packages(),
    zip_safe=False,
    install_requires=_get_local_requirements("REQUIREMENTS.txt")
)
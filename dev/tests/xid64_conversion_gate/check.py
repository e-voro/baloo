#!/usr/bin/env python3
"""Probe conversion publication with actual PG15 source and disposable clusters.

Usage: python3 check.py INSTALL_PREFIX BUILD_DIR OLD_INSTALL
Requires an assertion/injection-point build and TAP dependencies.
"""
from pathlib import Path
import os
import resource
import shutil
import subprocess
import sys
import tempfile

prefix, build, old = (Path(arg).resolve() for arg in sys.argv[1:4])
here = Path(__file__).resolve().parent
source = here.parents[3]
work = Path(tempfile.mkdtemp(prefix='xid64-conversion-gate-'))
library = work / 'probe.so'
print('Conversion-gate artifacts:', work, flush=True)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
includedir = subprocess.check_output(
    [prefix / 'bin/pg_config', '--includedir-server'], text=True).strip()
subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Werror', '-I' + includedir,
                str(here / 'probe.c'), '-o', str(library)], check=True)
pkglibdir = Path(subprocess.check_output(
    [prefix / 'bin/pg_config', '--pkglibdir'], text=True).strip())
injection_name = 'codex_conversion_gate_' + str(os.getpid())
injection_library = pkglibdir / (injection_name + '.so')
shutil.copyfile(library, injection_library)
env = dict(os.environ)
env.update(PATH=str(prefix / 'bin') + ':' + env['PATH'],
           LD_LIBRARY_PATH=str(prefix / 'lib') + ':' + env.get('LD_LIBRARY_PATH', ''),
           PG_REGRESS=str(build / 'src/test/regress/pg_regress'),
           top_builddir=str(build), TESTDATADIR=str(work / 'data'),
           TESTLOGDIR=str(work / 'log'), PG_TEST_TIMEOUT_DEFAULT='90',
           oldinstall=str(old), XID64_GATE_DIR=str(work), XID64_GATE_LIB=str(library),
           XID64_GATE_INJECTION_LIB=injection_name)
env.pop('INITDB_TEMPLATE', None)
try:
    subprocess.run(['prove', '-v', '-I', str(source / 'src/test/perl'),
                    str(here / 'probe.pl')], cwd=work, env=env, check=True)
finally:
    injection_library.unlink()

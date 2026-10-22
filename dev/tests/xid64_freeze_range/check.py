#!/usr/bin/env python3
"""Live normal-page freeze range probe, using only a disposable cluster.

Usage: python3 check.py INSTALL_PREFIX BUILD_DIR
Requires the installed assertion build, TAP dependencies, a C compiler and
local socket permissions. Artificial counter/SLRU changes are confined to a
new /tmp directory. This verifies SQL failure/retry, not crash recovery.
"""
from pathlib import Path
import os
import resource
import shlex
import subprocess
import sys
import tempfile

prefix = Path(sys.argv[1]).resolve()
build = Path(sys.argv[2]).resolve()
here = Path(__file__).resolve().parent
source = here.parents[3]
work = Path(tempfile.mkdtemp(prefix='xid64-freeze-range-'))
library = work / 'probe.so'
print('Freeze-range artifacts:', work, flush=True)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

includedir = subprocess.check_output(
    [prefix / 'bin/pg_config', '--includedir-server'], text=True).strip()
subprocess.run(shlex.split(os.environ.get('CC', 'cc')) +
               ['-shared', '-fPIC', '-Wall', '-Werror', '-I' + includedir,
                str(here / 'probe.c'), '-o', str(library)], check=True)
env = dict(os.environ)
env.update(PATH=str(prefix / 'bin') + ':' + env['PATH'],
           LD_LIBRARY_PATH=str(prefix / 'lib') + ':' +
               env.get('LD_LIBRARY_PATH', ''),
           PG_REGRESS=str(build / 'src/test/regress/pg_regress'),
           top_builddir=str(build), TESTDATADIR=str(work / 'data'),
           TESTLOGDIR=str(work / 'log'), PG_TEST_TIMEOUT_DEFAULT='25',
           XID64_FREEZE_RANGE_LIB=str(library))
env.pop('INITDB_TEMPLATE', None)
subprocess.run(['prove', '-v', '-I', str(source / 'src/test/perl'),
                str(here / 'probe.pl')], cwd=work, env=env, check=True)

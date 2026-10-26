#!/usr/bin/env python3
"""Run native upgrade suites against a read-only external installation.

Usage: check.py INSTALL_PREFIX BUILD_DIR OLD_INSTALL [TEST_BASENAME ...]
Every cluster is created under a fresh temporary directory.
"""
from pathlib import Path
import os
import resource
import subprocess
import sys
import tempfile

prefix, build, old = (Path(arg).resolve() for arg in sys.argv[1:4])
source = Path(__file__).resolve().parents[4]
tests = sys.argv[4:] or ['007_multixact_conversion.pl']
work = Path(tempfile.mkdtemp(prefix='xid64-upgrade-source-'))
print('Upgrade-source artifacts:', work, flush=True)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
env = dict(os.environ)
env.update(PATH=str(prefix / 'bin') + ':' + env['PATH'],
           LD_LIBRARY_PATH=str(prefix / 'lib') + ':' + env.get('LD_LIBRARY_PATH', ''),
           PG_REGRESS=str(build / 'src/test/regress/pg_regress'),
           top_builddir=str(build), TESTDATADIR=str(work / 'data'),
           TESTLOGDIR=str(work / 'log'), PG_TEST_TIMEOUT_DEFAULT='90',
           REGRESS_SHLIB=str(build / 'src/test/regress/regress.so'),
           TEST_EXT_LIB=str(build / 'src/test/modules/test_extensions/test_ext.so'),
           oldinstall=str(old))
env.pop('INITDB_TEMPLATE', None)
subprocess.run(['prove', '-v', '-I', str(source / 'src/test/perl'),
                *[str(source / 'src/bin/pg_upgrade/t' / name) for name in tests]],
               cwd=work, env=env, check=True)

#!/usr/bin/env python3
"""Live apply-lock, prepared-MultiXact and concurrent-TOAST follow-ups.

Usage: python3 check.py INSTALL_PREFIX BUILD_DIR
All SQL and prepared transactions are confined to a disposable cluster.
"""
from pathlib import Path
import os
import resource
import subprocess
import sys
import tempfile

prefix, build = (Path(arg).resolve() for arg in sys.argv[1:3])
here = Path(__file__).resolve().parent
source = here.parents[3]
work = Path(tempfile.mkdtemp(prefix='xid64-post-adaptation-'))
print('Post-adaptation artifacts:', work, flush=True)
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
library = work / 'probe.so'
regress = (source / 'src/test/regress/regress.c').read_text()
start = regress.index('typedef struct TupleCheckValues')
fn = regress.index('static RelCheckValues\nFillRelCheckValues', start)
opening = regress.index('{', fn)
end, depth = opening + 1, 1
while depth:
    depth += (regress[end] == '{') - (regress[end] == '}')
    end += 1
unit = work / 'probe.c'
unit.write_text((here / 'probe.c').read_text() + '\n' + regress[start:fn] +
                regress[fn:end] + '\n' + (here / 'helper_checks.c').read_text())
include = subprocess.check_output(
    [prefix / 'bin/pg_config', '--includedir-server'], text=True).strip()
subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Werror', '-I' + include,
                str(unit), '-o', str(library)], check=True)
env = dict(os.environ)
env.update(PATH=str(prefix / 'bin') + ':' + env['PATH'],
           LD_LIBRARY_PATH=str(prefix / 'lib') + ':' + env.get('LD_LIBRARY_PATH', ''),
           PG_REGRESS=str(build / 'src/test/regress/pg_regress'),
           top_builddir=str(build), TESTDATADIR=str(work / 'data'),
           TESTLOGDIR=str(work / 'log'), PG_TEST_TIMEOUT_DEFAULT='45',
           XID64_TODO_LIB=str(library))
env.pop('INITDB_TEMPLATE', None)
subprocess.run(['prove', '-v', '-I', str(source / 'src/test/perl'),
                str(here / 'probe.pl')], cwd=work, env=env, check=True)

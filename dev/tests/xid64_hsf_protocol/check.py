#!/usr/bin/env python3
"""Test the xid64 feedback tag against a real walsender in a disposable cluster.

Usage: check.py INSTALL_PREFIX BUILD_DIR
"""
from pathlib import Path
import os
import subprocess
import sys
import tempfile

prefix, build = (Path(arg).resolve() for arg in sys.argv[1:3])
here = Path(__file__).resolve().parent
source = here.parents[3]
work = Path(tempfile.mkdtemp(prefix='xid64-hsf-protocol-'))
print('HSF protocol artifacts:', work, flush=True)
client = work / 'client'
subprocess.run(['cc', '-Wall', '-Werror', '-I' + str(prefix / 'include'),
                str(here / 'client.c'), '-L' + str(prefix / 'lib'),
                '-Wl,-rpath,' + str(prefix / 'lib'), '-lpq', '-o', str(client)], check=True)
env = dict(os.environ)
env.update(PATH=str(prefix / 'bin') + ':' + env['PATH'],
           LD_LIBRARY_PATH=str(prefix / 'lib') + ':' + env.get('LD_LIBRARY_PATH', ''),
           PG_REGRESS=str(build / 'src/test/regress/pg_regress'),
           top_builddir=str(build), TESTDATADIR=str(work / 'data'),
           TESTLOGDIR=str(work / 'log'), PG_TEST_TIMEOUT_DEFAULT='30',
           XID64_HSF_CLIENT=str(client))
env.pop('INITDB_TEMPLATE', None)
if len(sys.argv) > 3:
    env['XID64_HSF_LEGACY_INSTALL'] = str(Path(sys.argv[3]).resolve())
subprocess.run(['prove', '-v', '-I', str(source / 'src/test/perl'), str(here / 'probe.pl')],
               cwd=work, env=env, check=True)

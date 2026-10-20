#!/usr/bin/env python3
"""Compile real upgrade/index helpers with SQL/connection fixtures, not servers."""
from pathlib import Path
import os
import re
import shlex
import subprocess
import sys
import tempfile

root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
version = (root / 'src/bin/pg_upgrade/version.c').read_text()
check = (root / 'src/bin/pg_upgrade/check.c').read_text()

def function(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    end, depth = opening + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'

functions = '\n'.join(function(version, sig) for sig in [
    'bool\ncluster_is_xid64(', 'bool\ncluster_is_xid32(',
    'bool\ncluster_has_64bit_multixact_offsets(',
    'bool\nxid_check_applicable(', 'static void\ninvalidate_indexes(',
    'void\ninvalidate_spgist_indexes(', 'void\ninvalidate_gin_indexes(',
    'void\ninvalidate_external_indexes('])
functions += function(check, 'void\nissue_warnings_and_set_wal_level(')
preflight = check[check.index('\t/* Check index formats affected'):]
preflight = preflight[:preflight.index('\n\t/*\n')]
functions += 'static void preflight(void)\n{\n' + preflight + '\n}\n'
fixture = Path(__file__).with_name('fixture.c').read_text().replace('/* FUNCTIONS */', functions)
header = (root / 'src/bin/pg_upgrade/pg_upgrade.h').read_text()
threshold = re.search(r'#define MULTIXACTOFFSET_FORMATCHANGE_CAT_VER\s+(\d+)', header)[1]
fixture = fixture.replace('/* OFFSET FORMAT THRESHOLD */',
                          '#define MULTIXACTOFFSET_FORMATCHANGE_CAT_VER ' + threshold)
assert '.version_hook = xid_check_applicable' in check
assert 'tx %% 4294967296' in check and 'tx %% 4294967295' not in check
for tx, wrong, right in [(4294967396, 101, 100), (12884901913, 28, 25)]:
    assert tx % 4294967295 == wrong and tx % 4294967296 == right

with tempfile.TemporaryDirectory(prefix='xid64-upgrade-indexes-') as tmp:
    tmp = Path(tmp)
    code = tmp / 'fixture.c'
    code.write_text(fixture)
    exe = tmp / 'fixture'
    subprocess.run(shlex.split(os.environ.get('CC', 'cc')) + [
        '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-fsanitize=undefined', '-fno-sanitize-recover=all', str(code), '-o', str(exe)], check=True)
    cases = [(m, size, 202607272, size == 4) for m in [150000, 160000, 170000, 190000] for size in [4, 8]]
    cases += [(180000, 4, 202502212, True), (180000, 8, 642505061, False),
              (140000, 4, 202107181, True)]
    for major, size, cat, converting in cases:
        for p in tmp.glob('reindex_*.sql'):
            p.unlink()
        subprocess.run([str(exe), str(major), str(size), str(cat)], cwd=tmp, check=True)
        files = sorted(tmp.glob('reindex_*.sql'))
        assert len(files) == (3 if converting else 0), files
        for p in files:
            assert p.read_text() == '\\connect fixture_db\nREINDEX INDEX public.fixture_index;\n', p.read_text()
    for major, size, cat in [(190000, 0, 202607272), (180000, 8, 992505061), (200000, 8, 202607272)]:
        result = subprocess.run([str(exe), str(major), str(size), str(cat)], cwd=tmp, capture_output=True)
        assert result.returncode == 1 and b'runtime error' not in result.stderr, result
    # Recorded source layouts, including pre-change PG19 and pre-v19 xid64.
    formats = [
        (150000, 4, 202209061, 32), (150000, 8, 202209061, 64),
        (160000, 4, 202307071, 32), (160000, 8, 202307071, 64),
        (170000, 4, 202406281, 32), (170000, 8, 202406281, 64),
        (180000, 4, 202506291, 32), (180000, 8, 642601131, 64),
        (190000, 4, 202512090, 32), (190000, 4, 202512091, 64),
        (190000, 4, 202607272, 64), (190000, 8, 202607272, 64),
    ]
    for major, size, cat, bits in formats:
        result = subprocess.run([str(exe), 'format', str(major), str(size), str(cat)],
                                cwd=tmp, capture_output=True, text=True, check=True)
        assert int(result.stdout) == bits, (major, size, cat, result.stdout)
print('PASS: 11 upgrade-format/index scenarios, 3 unsupported-format rejections, real REINDEX files and invalidation SQL; UBSan. Modulus boundary examples pass. No server upgrade tested.')
print('PASS: 12 source MultiXact offset-format cases, including PG19 catalog boundary and pre-v19 xid64; UBSan. Reader/converter integration remains pending.')

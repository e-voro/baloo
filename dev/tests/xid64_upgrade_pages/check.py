#!/usr/bin/env python3
"""Exercise actual page-file rewrite and control parsing with fixed-width scaffolding."""
from pathlib import Path
import os
import re
import shlex
import struct
import subprocess
import sys
import tempfile
root = Path(sys.argv[1] if len(sys.argv) > 1 else '.').resolve()
file = (root / 'src/bin/pg_upgrade/file.c').read_text()
control = (root / 'src/bin/pg_upgrade/controldata.c').read_text()
header = (root / 'src/include/storage/bufpage.h').read_text()
def function(source, signature):
    start = source.index(signature)
    opening = source.index('{', start)
    end, depth = opening + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'
functions = function(file, 'void\nupdateSegmentPagesVersion(')
for sig in ['static inline bool\nPageIsNew(', 'static inline Size\nPageGetPageSize(',
            'static inline void\nPageSetPageSizeAndVersion(']:
    functions = function(header, sig) + functions
start = control.index('\t\telse if ((p = strstr(bufin, "Latest checkpoint\'s NextXID:"))')
end = control.index('\t\telse if ((p = strstr(bufin, "Latest checkpoint\'s NextOID:"))', start)
body = control[start:end].replace('else if', 'if', 1)
functions += '''static uint64_t parse_xid(char *bufin, unsigned version) {
    ClusterInfo storage = {0}, *cluster = &storage;
    char *p; bool got_xid = false;
    cluster->major_version = version;
''' + body + '\nassert(got_xid); return cluster->controldata.chkpnt_nxtxid;\n}\n'
version = int(re.search(r'#define PG_PAGE_LAYOUT_VERSION\s+(\d+)', header)[1])
fixture = Path(__file__).with_name('fixture.c').read_text().replace('/* FUNCTIONS */', functions).replace('PAGE_VERSION', str(version))
with tempfile.TemporaryDirectory(prefix='xid64-upgrade-pages-') as tmp:
    tmp = Path(tmp)
    src, dst = tmp / 'source', tmp / 'destination'
    code, exe = tmp / 'fixture.c', tmp / 'fixture'
    code.write_text(fixture)
    subprocess.run(shlex.split(os.environ.get('CC', 'cc')) + [
        '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-fsanitize=undefined', '-fno-sanitize-recover=all', str(code), '-o', str(exe)], check=True)
    for number in [3, 2**32, 4294967396, 2**63 + 25, 2**64 - 1]:
        for value, major in [(str(number), 190000), (f'{number >> 32}:{number & 0xffffffff}', 180000),
                             (f'{number >> 32}/{number & 0xffffffff}', 90500)]:
            result = subprocess.run([str(exe), 'xid', str(major), value], capture_output=True, text=True, check=True)
            assert int(result.stdout) == number, result
    blocksize = 8192
    for checksums in [0, 1]:
        page = bytearray([0xa5] * blocksize)
        page[:24] = struct.pack('=QHHHHHHI', 0, 77, 0, 24, blocksize, blocksize, blocksize | 4, 0)
        src.write_bytes(bytes(blocksize) + page + bytes(blocksize))
        dst.unlink(missing_ok=True)
        subprocess.run([str(exe), str(src), str(dst), str(checksums)], check=True)
        expected = bytearray(src.read_bytes())
        struct.pack_into('=H', expected, blocksize + 18, blocksize | version)
        if checksums:
            # Checksum fixture returns 100 + block number; tests ordering/address only.
            struct.pack_into('=H', expected, blocksize + 8, 101)
        assert dst.read_bytes() == expected
    for content in [b'x' + bytes(8191), bytes(100) + b'x' + bytes(8091), b'x' * 100,
                    bytes(8192) + b'x', struct.pack('=QHHHHHHI', 0, 0, 0, 25, 8192, 8192, 8196, 0) + bytes(8168)]:
        src.write_bytes(content)
        dst.unlink(missing_ok=True)
        result = subprocess.run([str(exe), str(src), str(dst), '1'], capture_output=True)
        assert result.returncode == 1 and b'runtime error' not in result.stderr, result
print('PASS: 15 full/epoch XID parse cases; zero/initialized/neighbor pages with checksums on/off; 5 corrupt/truncated files rejected; UBSan. Checksum calls use a stub; no server upgrade tested.')

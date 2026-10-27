import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path('/home/evoro/tantor/dv/pg19beta3xid64')
os.chdir(ROOT)
STATE = Path('/tmp/xid64-aggregation-state.json')
INDEX = tempfile.mktemp(prefix='xid64-aggregate-index-')
env = dict(os.environ, GIT_INDEX_FILE=INDEX)

def git(*args, data=None, indexed=False, extra=None):
    e = dict(env if indexed else os.environ)
    if extra:
        e.update(extra)
    return subprocess.check_output(['git', *args], input=data, env=e)

def tree(ref):
    out = git('ls-tree', '-rz', ref)
    result = {}
    for row in out.split(b'\0'):
        if row:
            meta, path = row.split(b'\t', 1)
            mode, kind, oid = meta.decode().split()
            result[path.decode()] = (mode, oid)
    return result

def read(ref, path):
    return git('show', f'{ref}:{path}')

def put(mapping, path, content):
    oid = git('hash-object', '-w', '--stdin', data=content).decode().strip()
    mapping[path] = ('100644', oid)

def write_tree(mapping):
    git('read-tree', '--empty', indexed=True)
    entries = b''.join(f'{mode} {oid}\t{p}\0'.encode() for p, (mode, oid) in sorted(mapping.items()))
    git('update-index', '-z', '--index-info', indexed=True, data=entries)
    return git('write-tree', indexed=True).decode().strip()

def core(t):
    return {p: entry for p, entry in t.items() if p not in {'.gitmodules', 'baloo', 'codex_todo.txt'}}

def message(i):
    p = next((ROOT/'baloo/patches/func/pg19xid64v67').glob(f'v67-{i:04}-*'))
    s = p.read_text().split('\n---\n', 1)[0]
    headers, body = s.split('\n\n', 1)
    subject = re.search(r'^Subject: (.*(?:\n .*)*)', headers, re.M).group(1)
    subject = re.sub(r'^\[PATCH[^]]*\] ', '', subject.replace('\n ', ' '))
    author = re.search(r'^From: (.*)$', headers, re.M).group(1)
    date = re.search(r'^Date: (.*)$', headers, re.M).group(1)
    if i == 5:
        before, discussion = body.split('Discussion:', 1)
        body = before + '- Evgeny Voropaev <evorop@gmail.com>\nDiscussion:' + discussion
    body += '\n\nAuthor: Evgeny Voropaev <evorop@gmail.com>\n'
    body += f'\nOriginal-author: {author}\n'
    return subject, body, 'Evgeny Voropaev <evorop@gmail.com>', date

BASE = git('rev-parse', '3638289fb57').decode().strip()
SOURCE = git('rev-parse', 'HEAD').decode().strip()
assert git('branch', '--show-current').decode().strip() == 'pg19beta3xid64_CODEX_OVERNIGHT_20261021'
assert not git('branch', '--list', 'pg19xid64evoro1900').strip()
base_tree = tree(BASE)
final_tree = tree(SOURCE)
base_core = core(base_tree)
final_core = core(final_tree)
commits = []
parent = BASE

def commit(mapping, subject, body, author, date=None):
    global parent
    name, email = re.fullmatch(r'(.*) <(.*)>', author).groups()
    author_env = {'GIT_AUTHOR_NAME': name, 'GIT_AUTHOR_EMAIL': email,
                  'GIT_COMMITTER_NAME': 'Evgeny Voropaev', 'GIT_COMMITTER_EMAIL': 'evorop@gmail.com'}
    if date:
        author_env['GIT_AUTHOR_DATE'] = date
    oid = git('commit-tree', write_tree(mapping), '-p', parent,
              data=f'{subject}\n\n{body.strip()}\n'.encode(), extra=author_env).decode().strip()
    commits.append({'commit': oid, 'subject': subject})
    parent = oid
    print(oid, subject, flush=True)

for i, ref in enumerate(['f4c7dc9c16a', '44f020d606d', '7e42cdce0f1', '8ca324058af'], 1):
    current = core(tree(ref))
    # These PG19-only diagnostics were originally corrected with 0005.
    # Move their type-neutral formatting into 0001 so the later upgrade
    # implementation can be deferred without breaking the core build.
    p = 'src/bin/pg_upgrade/multixact_read_v18.c'
    content = read(ref, p)
    content = content.replace(
        b'"multixact %u has an invalid length (%d)", multi, length',
        b'"multixact %llu has an invalid length (%d)", (unsigned long long) multi, length')
    content = re.sub(
        rb'"multixact %u has more than one updating member",(\s+)multi',
        rb'"multixact %llu has more than one updating member",\1(unsigned long long) multi', content)
    put(current, p, content)
    if i == 4:
        # Fold v67-0012's reserved-member fix into its GUC infrastructure.
        for p in ['src/backend/utils/misc/gen_guc_tables.pl', 'src/backend/utils/misc/guc.c',
                  'src/backend/utils/misc/guc_funcs.c', 'src/backend/utils/misc/help_config.c',
                  'src/include/utils/guc_tables.h']:
            content = read(ref, p).replace(b'._int64', b'._int_64').replace(b'->_int64', b'->_int_64')
            content = content.replace(b'struct config_int64 _int64;', b'struct config_int64 _int_64;')
            if p.endswith('gen_guc_tables.pl'):
                old = b'\t\tprintf $ofh "\\t\\t._%s = {\\n", $entry->{type};'
                new = (b'\t\t# MSVC reserves _int64; the GUC type name remains "int64".\n'
                       b"\t\tmy $member = $entry->{type} eq 'int64' ? 'int_64' : $entry->{type};\n"
                       b'\t\tprintf $ofh "\\t\\t._%s = {\\n", $member;')
                assert old in content
                content = content.replace(old, new)
            put(current, p, content)
    subject, body, author, date = message(i)
    if i == 4:
        body += '\nFold in v67-0012: avoid the MSVC reserved _int64 member name.\n'
    commit(current, subject, body, author, date)

fourth = dict(current)
fifth = dict(final_core)
deferred = set(p for p in set(final_core) | set(fourth) if p.startswith('src/bin/pg_upgrade/'))
deferred.update({
    'src/backend/access/transam/xloginsert.c', 'src/include/access/xloginsert.h',
    'src/backend/storage/aio/read_stream.c', 'src/include/storage/read_stream.h',
    'src/include/storage/aio_types.h', 'src/include/storage/buf_internals.h',
    'src/include/storage/relation_extra_data.h', 'src/backend/commands/dbcommands.c',
    'src/test/perl/PostgreSQL/Test/AdjustUpgrade.pm',
    'src/test/xid-64/t/006_zeropage.pl',
    'src/test/regress/sql/xid64.sql', 'src/test/regress/expected/xid64.out',
    'src/test/regress/parallel_schedule',
})
for p in deferred:
    if p in fourth:
        fifth[p] = fourth[p]
    else:
        fifth.pop(p, None)

# Control-data widths/parsing follow the core type change; actual transfer,
# source-format dispatch and conversion remain in the upgrade commit.
p = 'src/bin/pg_upgrade/controldata.c'
fifth[p] = final_core[p]
p = 'src/bin/pg_upgrade/pg_upgrade.h'
data = read('8ca324058af', p)
for field in (b'chkpnt_nxtxid', b'chkpnt_nxtmulti', b'chkpnt_oldstMulti', b'chkpnt_oldstxid'):
    data = re.sub(rb'uint32(\s+)' + field + rb';', rb'uint64\1' + field + b';', data)
put(fifth, p, data)

# The conversion SQL functions and their schedule entry accompany the
# converter. The indirect-tuple cache initialization is a core requirement.
p = 'src/test/regress/regress.c'
data = read('8ca324058af', p)
marker = b'\ttuple.t_tableOid = InvalidOid;\n\ttuple.t_data = rec;'
assert marker in data
put(fifth, p, data.replace(marker,
    b'\ttuple.t_tableOid = InvalidOid;\n\tHeapTupleSetZeroXids(&tuple);\n\ttuple.t_data = rec;'))

# Core visibility/layout support belongs to 0005. The subsequent private,
# no-hints legacy conversion path and conversion-image hook belong to 0007.
for p in ['src/backend/access/heap/heapam_visibility.c', 'src/include/access/htup_details.h',
          'src/backend/access/heap/pruneheap.c']:
    fifth[p] = tree('6400ddc9891')[p]

# The normal-page code uses these lock predicates without the converter.
functions = read(SOURCE, 'src/backend/storage/buffer/bufmgr.c')
start = functions.index(b'bool\nIsBufferLocked(Buffer buffer)')
end = functions.index(b'/*\n * Release buffer content locks', start)
predicates = functions[start:end]
p = 'src/backend/storage/buffer/bufmgr.c'
data = read('8ca324058af', p)
marker = b'/*\n * Release buffer content locks'
assert marker in data
put(fifth, p, data.replace(marker, predicates + marker, 1))
p = 'src/include/storage/bufmgr.h'
data = read('8ca324058af', p)
marker = b'extern void MarkBufferDirtyHint(Buffer buffer, bool buffer_std);'
assert marker in data
put(fifth, p, data.replace(marker, marker + b'\nextern bool IsBufferLocked(Buffer buffer);\nextern bool IsBufferLockedExclusive(Buffer buffer);'))

# Shared sorting support is required by the core page format before the
# legacy converter is introduced. Keep it in its eventual translation unit.
p = 'src/backend/storage/buffer/heap_convert.c'
data = read(SOURCE, p)
start = data.index(b'int\nitemoffcompare(')
end = data.index(b'\n}\n', start) + 3
header = data[:data.index(b'#include "postgres.h"')]
put(fifth, p, header + b'#include "postgres.h"\n\n#include "storage/bufpage.h"\n\n' + data[start:end])

README = 'src/backend/access/heap/README.XID64'
fifth.pop(README, None)
subject, body, author, date = message(5)
body += '''
PG19 adaptation: preserve PG19 pruning/VM/WAL interfaces, 64-bit MultiXact
offsets, full-XID visibility/locks/replication and native regression coverage.
Fold in v67-0007/0008/0009/0010 and subsequent non-upgrade fixes.

Upgrade execution, backend legacy-page conversion, AIO metadata and its WAL
publication are introduced separately by "Resolve the upgrade issues".
Core page layouts/accessors and the page-base exhaustion freeze fallback
remain here because ordinary xid64 heap operations also require them.

Additional original v67 credits:
Author: Evgeny Voropaev <evgeny.voropaev@tantorlabs.com>
Author: Maxim Orlov <orlovmg@gmail.com>
Author: Pavel Borisov <pashkin.elfe@gmail.com>
Reviewed-by: Yura Sokolov <funny.falcon@gmail.com>

Includes adapted test/counter ideas from supplied tt186xid64 0002 and 0010
and the supplied pg_combinebackup fixture correction (no author header).
'''
commit(fifth, subject, body, author, date)

sixth = dict(fifth)
sixth[README] = tree('7b5ca03ef47')[README]
subject, body, author, date = message(6)
body += '\nThe following upgrade commit updates this original design for backend conversion and immediate WAL.\n'
commit(sixth, subject, body, author, date)

_, main_body, _, _ = message(5)
credit_start = main_body.index('Authors:')
credits = main_body[credit_start:main_body.index('Discussion:', credit_start)].strip()
body = '''Aggregate the PG19 upgrade and legacy-page conversion implementation and
the corrections collected during the complete xid64 adaptation.

Detect source XID/MultiXact formats; retain native PG19 64-bit offsets and
its short offset filenames; convert SLRUs, wrapped per-object horizons and
FSM/VM headers/checksums for copy, link and swap; invalidate destination
indexes and avoid system-column upgrade false positives.

Carry relation conversion metadata by value, including CREATE DATABASE.
Convert validated private copies in the reading backend under the content
lock. Publish BM_VALID together with BM_CONVERSION_PENDING at physical I/O
completion, gate normal readers, and WAL-log permanent converted pages
before publishing readiness. Retain the exceptional conversion-image WAL
obligation, hint durability and redo image precedence. Preserve legacy HOT
roots and retryable shared pages after conversion errors.

Add the native cross-source upgrade/recovery/database-copy/double-xmax/HOT
tests, conversion helper corrections and updated README. Standalone Baloo
probes, reports and logs remain outside this source series.

Supplied tt186xid64 sources: adapted 0005, 0006, 0007, 0008, 0011 (nonzero
epoch), 0012, 0013 (decoding/test), 0014 and 0015. The worker/deferred-WAL
parts of 0008 are superseded by the backend/immediate-WAL design.

Original xid64 page-format/conversion authors:
''' + credits + '''

Supplied patch author credits (names/emails preserved where supplied):
Author: Evgeny Voropaev <evorop@gmail.com>
Author: Artem Bugaenko
Co-author: Andrey Borodin
Co-author: Maksim Starkov
Co-author: Maxim Starkov
Co-author: Maksim Starkov <maksim.starkov@tantorlabs.com>
Co-author: Stanislav Antonov
Author: OpenAI Codex <codex@openai.com>

Names without email addresses are retained as written in the supplied
patches; no identities have been inferred from other repositories.
'''
commit(final_core, 'Resolve the upgrade issues', body, 'Evgeny Voropaev <evorop@gmail.com>')

state = {'base': BASE, 'source': SOURCE, 'commits': commits,
         'source_tip': parent, 'source_tree': write_tree(final_core),
         'baloo_source': git('-C', 'baloo', 'rev-parse', 'HEAD').decode().strip(),
         'deferred_paths': sorted(deferred), 'core_split_paths': [
             'src/backend/access/heap/heapam_visibility.c', 'src/include/access/htup_details.h',
             'src/backend/access/heap/pruneheap.c', 'src/backend/storage/buffer/bufmgr.c',
             'src/include/storage/bufmgr.h', 'src/backend/storage/buffer/heap_convert.c']}
STATE.write_text(json.dumps(state, indent=2) + '\n')
assert core(tree(parent)) == final_core
print('Full source tree equals overnight HEAD exactly; state:', STATE, flush=True)
Path(INDEX).unlink(missing_ok=True)

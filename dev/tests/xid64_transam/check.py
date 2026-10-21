#!/usr/bin/env python3
"""Compile actual transam.h and PG19 cutoff helper with fixed-width service stubs."""
from pathlib import Path
import os
import re
import shlex
import subprocess
import tempfile

root = Path(__file__).resolve().parents[4]
source = (root / 'src/test/modules/injection_points/regress_injection.c').read_text()
start = source.index('Datum\nremovable_cutoff(')
helper = source[start:]
types = (root / 'src/include/c.h').read_text()
types = '\n'.join(re.findall(r'^typedef (?:uint32|uint64|TransactionId) (?:TransactionId|ShortTransactionId|LocalTransactionId|SubTransactionId|MultiXactId|MultiXactOffset);$', types, re.M))
def function(source, signature):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'

lfind = function((root / 'src/include/port/pg_lfind.h').read_text(),
                 'static inline bool\npg_lfind64(')
lfind += function((root / 'src/test/modules/test_lfind/test_lfind.c').read_text(),
                  'static void\ntest_lfind64_internal(')
fixture = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint32_t uint32;
typedef uint64_t uint64;
typedef int64_t int64;
typedef uint32 Oid;
typedef uint64 XLogRecPtr;
#define UINT64CONST(x) UINT64_C(x)
#define PGDLLIMPORT
#define StaticAssertStmt(c,m) _Static_assert(c,m)
#define Assert assert
#define AssertMacro(x) ((void) assert(x))
#define unlikely(x) (x)
/* TYPES */
#include "access/transam.h"
typedef uint64 Datum;
typedef struct { bool relisshared; } RelMeta;
struct relation { RelMeta *rd_rel; };
typedef struct relation *Relation;
static RelMeta relmeta;
static struct relation relation;
static bool use_relation;
static unsigned reads, cutoffs, closes;
static TransactionId cutoff;
static const bool autovacuum_start_daemon = false;
#define PG_FUNCTION_ARGS void
#define PG_ARGISNULL(n) (!use_relation)
#define PG_GETARG_OID(n) 42
#define AccessShareLock 1
#define WARNING 1
#define elog(...) abort()
#define CHECK_FOR_INTERRUPTS() ((void) 0)
#define PG_RETURN_FULLTRANSACTIONID(x) return U64FromFullTransactionId(x)
static Relation table_open(Oid oid, int lock) { (void)oid; (void)lock; return &relation; }
static void table_close(Relation rel, int lock) { (void)rel; (void)lock; closes++; }
static TransactionId GetOldestNonRemovableTransactionId(Relation rel) { (void)rel; cutoffs++; return cutoff; }
FullTransactionId ReadNextFullTransactionId(void) { reads++; return FullTransactionIdFromXid(cutoff + (reads == 1 ? 100 : 101)); }
/* LFIND */
/* HELPER */
int main(void) {
    test_lfind64_internal();
    _Static_assert(sizeof(TransactionId) == 8 && sizeof(ShortTransactionId) == 4, "XID widths");
    _Static_assert(sizeof(LocalTransactionId) == 8 && sizeof(SubTransactionId) == 8, "local/sub widths");
    TransactionId values[] = {3, UINT64_C(4294967296), UINT64_C(4294967297), UINT64_C(4294967298), UINT64_C(17179869185)};
    relation.rd_rel = &relmeta;
    for (unsigned i = 0; i < sizeof(values)/sizeof(values[0]); i++) {
        cutoff = values[i];
        FullTransactionId full = FullTransactionIdFromXid(cutoff);
        assert(XidFromFullTransactionId(full) == cutoff);
        FullTransactionIdAdvance(&full); assert(full.value == cutoff + 1);
        FullTransactionIdRetreat(&full); assert(full.value == cutoff);
        assert(TransactionIdPrecedes(cutoff, cutoff + 1));
        assert(TransactionIdFollows(cutoff + 1, cutoff));
        assert(TransactionIdPrecedesOrEquals(cutoff, cutoff));
        assert(TransactionIdFollowsOrEquals(cutoff, cutoff));
        for (unsigned use = 0; use < 2; use++) {
            use_relation = use; reads = cutoffs = closes = 0;
            assert(removable_cutoff() == cutoff);
            assert(reads == 3 && cutoffs == 2 && closes == use);
        }
    }
    TransactionId xid = FirstNormalTransactionId;
    TransactionIdRetreatOrInvalid(&xid); assert(xid == InvalidTransactionId);
    puts("PASS: actual transam helpers and 10 high-XID cutoff/retry scenarios plus high-bit linear-search checks (no backend server)");
}
'''
with tempfile.TemporaryDirectory(prefix='xid64-transam-') as tmp:
    work = Path(tmp)
    for path in ('access/xlogdefs.h', 'utils/elog.h'):
        p = work / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('/* fixture supplies dependencies */\n')
    unit = work / 'check.c'
    unit.write_text(fixture.replace('/* TYPES */', types).replace('/* HELPER */', helper).replace('/* LFIND */', lfind))
    binary = work / 'check'
    subprocess.run(shlex.split(os.environ.get('CC', 'cc')) + ['-std=c11', '-O1', '-Wall', '-Wextra', '-Werror', '-fsanitize=undefined', '-fno-sanitize-recover=all', '-I'+str(work), '-I'+str(root/'src/include'), str(unit), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

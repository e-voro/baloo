#!/usr/bin/env python3
"""Run actual VACUUM cutoff/failsafe code against an independent age model."""
from pathlib import Path
import os
import random
import re
import shlex
import subprocess
import tempfile

root = Path(__file__).resolve().parents[4]
source = (root / 'src/backend/commands/vacuum.c').read_text()


def function(signature):
    start = source.index(signature)
    end = source.index('{', start) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


body = ''
for helper in ['static uint64\nvacuum_cutoff_from_age(',
               'static int64\nvacuum_failsafe_min_age(']:
    if helper in source:
        body += function(helper)
body += function('bool\nvacuum_get_cutoffs(')
body += function('bool\nvacuum_xid_failsafe_check(')
types = (root / 'src/include/c.h').read_text()
types = '\n'.join(re.findall(
    r'^typedef (?:uint32|uint64|TransactionId) (?:TransactionId|ShortTransactionId|LocalTransactionId|SubTransactionId|MultiXactId|MultiXactOffset);$',
    types, re.M))
max_age = 2**63 - 1
first_cases = [
    (1000, 1, 200000000, 400000000, 50000000, 5000000, 150000000, 150000000),
    (2**32 + 1000, 500, max_age, max_age, max_age, max_age, max_age, max_age),
    (2**64 - 100, 2**64 - 100, max_age, max_age, 0, 0, 0, 0),
]
rng = random.Random(190021)
cases = first_cases + [tuple(rng.choice([1, 3, 1000, 2**32, 2**50, max_age])
                             for _ in range(8)) for _ in range(120)]
rows = []
for index, values in enumerate(cases):
    xid, mxid, xid_max, mxid_max, xmin, mmin, xtable, mtable = values
    xid = max(3, xid)
    mxid = max(1, mxid)
    oldest_xid = max(3, xid - min(500, xid // 2))
    oldest_mxid = max(1, mxid - min(200, mxid // 2))
    frozen = max(3, oldest_xid - min(400, oldest_xid // 2))
    relmx = max(1, oldest_mxid - min(100, oldest_mxid // 2))
    clip = lambda current, age, first: max(first, current - age)
    limit = min(oldest_xid, clip(xid, min(xmin, xid_max // 2), 3))
    mlimit = min(oldest_mxid, clip(mxid, min(mmin, mxid_max // 2), 1))
    aggressive = (frozen <= clip(xid, min(xtable, int(xid_max * .95)), 3)
                  or relmx <= clip(mxid, min(mtable, int(mxid_max * .95)), 1))
    warnings = int(oldest_xid < clip(xid, xid_max, 3)) + int(oldest_mxid < clip(mxid, mxid_max, 1))
    margin = lambda age: min(max_age, age + age // 20)
    failsafe = (frozen < clip(xid, max(1600000000, margin(xid_max)), 3)
                or relmx < clip(mxid, max(1600000000, margin(mxid_max)), 1))
    inputs = [xid, mxid, xid_max, mxid_max, xmin, mmin, xtable, mtable,
              oldest_xid, oldest_mxid, frozen, relmx, limit, mlimit,
              int(aggressive), warnings, int(failsafe)]
    rows.append('{' + ','.join('UINT64_C(%d)' % n for n in inputs) + '}')

fixture = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
typedef uint32_t uint32;
typedef uint64_t uint64;
typedef int64_t int64;
typedef uint32 Oid;
typedef uint64 XLogRecPtr;
#define UINT64CONST(x) UINT64_C(x)
#define PG_INT64_MAX INT64_MAX
#define PGDLLIMPORT
#define StaticAssertStmt(c,m) _Static_assert(c,m)
#define Assert assert
#define AssertMacro(x) ((void) assert(x))
#define unlikely(x) (x)
#define Min(a,b) ((a) < (b) ? (a) : (b))
#define Max(a,b) ((a) > (b) ? (a) : (b))
/* TYPES */
#include "access/transam.h"
#define FirstMultiXactId UINT64_C(1)
#define MultiXactIdIsValid(x) ((x) != 0)
#define MultiXactIdPrecedes(a,b) ((a) < (b))
#define MultiXactIdPrecedesOrEquals(a,b) ((a) <= (b))
static uint64 next_xid, next_mxid, oldest_xid, oldest_mxid;
static int64 autovacuum_freeze_max_age, autovacuum_multixact_freeze_max_age;
static int64 vacuum_freeze_min_age, vacuum_multixact_freeze_min_age;
static int64 vacuum_freeze_table_age, vacuum_multixact_freeze_table_age;
static const int64 vacuum_failsafe_age = 1600000000;
static const int64 vacuum_multixact_failsafe_age = 1600000000;
struct relmeta { TransactionId relfrozenxid; MultiXactId relminmxid; };
struct relation { struct relmeta *rd_rel; };
typedef struct relation *Relation;
typedef struct { int64 freeze_min_age, multixact_freeze_min_age;
                 int64 freeze_table_age, multixact_freeze_table_age; } VacuumParams;
struct VacuumCutoffs { TransactionId relfrozenxid, OldestXmin, FreezeLimit;
                       MultiXactId relminmxid, OldestMxact, MultiXactCutoff; };
static unsigned warning_count;
#define ereport(level,args) ((void) ++warning_count)
FullTransactionId ReadNextFullTransactionId(void) { return FullTransactionIdFromXid(next_xid); }
static MultiXactId ReadNextMultiXactId(void) { return next_mxid; }
static TransactionId GetOldestNonRemovableTransactionId(Relation rel) { (void) rel; return oldest_xid; }
static MultiXactId GetOldestMultiXactId(void) { return oldest_mxid; }
static int64 MultiXactMemberFreezeThreshold(void) { return autovacuum_multixact_freeze_max_age; }
/* BODY */
static const uint64 cases[][17] = { /* CASES */ };
int main(void) {
    unsigned mismatches=0;
    for (unsigned i = 0; i < sizeof(cases)/sizeof(cases[0]); i++) {
        const uint64 *v = cases[i];
        struct relmeta meta = {v[10], v[11]};
        struct relation rel = {&meta};
        VacuumParams params = {v[4],v[5],v[6],v[7]};
        struct VacuumCutoffs cutoffs;
        next_xid=v[0]; next_mxid=v[1];
        autovacuum_freeze_max_age=v[2]; autovacuum_multixact_freeze_max_age=v[3];
        oldest_xid=v[8]; oldest_mxid=v[9]; warning_count=0;
        bool aggressive=vacuum_get_cutoffs(&rel,&params,&cutoffs);
        bool failsafe=vacuum_xid_failsafe_check(&cutoffs);
        if (cutoffs.FreezeLimit!=v[12] || cutoffs.MultiXactCutoff!=v[13] ||
            aggressive!=v[14] || warning_count!=v[15] ||
            failsafe!=v[16]) {
            fprintf(stderr,"VACUUM age model mismatch in case %u\n",i);
            mismatches++;
        }
    }
    if (mismatches) return 1;
    puts("PASS: 123 actual VACUUM cutoff/failsafe cases, including young/high counters and INT64_MAX ages");
}
'''
with tempfile.TemporaryDirectory(prefix='xid64-vacuum-ages-') as name:
    work = Path(name)
    for stub in ['access/xlogdefs.h', 'utils/elog.h']:
        p = work / stub
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text('/* fixture supplies dependencies */\n')
    c = work / 'check.c'
    c.write_text(fixture.replace('/* TYPES */', types).replace('/* BODY */', body)
                 .replace('/* CASES */', ',\n'.join(rows)))
    binary = work / 'check'
    subprocess.run(shlex.split(os.environ.get('CC', 'cc')) + [
        '-std=c11', '-O1', '-Wall', '-Wextra', '-Werror',
        '-fsanitize=undefined,float-cast-overflow', '-fno-sanitize-recover=all',
        '-I'+str(work), '-I'+str(root/'src/include'), str(c), '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)

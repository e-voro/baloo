#!/usr/bin/env python3
"""Compile actual lock-tag constructors/decoders during the partial xid64 port.

Usage: python3 baloo/dev/tests/xid64_locktags/check.py [source-root]
Uses fixed-width fixtures instead of a configured backend. Extracts production
hashing, descriptions and pg_locks decoding; does not exercise server locking.
"""
from pathlib import Path
import os
import re
import shlex
import subprocess
import sys
import tempfile

root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()


def read(name):
    return (root / name).read_text()


def function(source, signature):
    start = source.index(signature)
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end] + "\n"


lock = read("src/backend/storage/lmgr/lock.c")
hashes = read("src/common/hashfn.c")
hash_code = hashes[hashes.index("#define UINT32_ALIGN_MASK"):
                   hashes.index("uint32\nhash_bytes(")]
hash_code += function(hashes, "uint32\nhash_bytes(")
hash_code += function(hashes, "uint32\ntag_hash(")
describe = function(read("src/backend/storage/lmgr/lmgr.c"),
                    "void\nDescribeLockTag(")
status = read("src/backend/utils/adt/lockfuncs.c")
status = status[status.index("\t\t\tcase LOCKTAG_TRANSACTION:"):
                status.index("\t\t\tcase LOCKTAG_OBJECT:")]
record = re.search(r"typedef struct TwoPhaseLockRecord\b.*?} TwoPhaseLockRecord;",
                   lock, re.S).group()
probes = subprocess.check_output(
    ["perl", "-n", str(root / "src/backend/utils/Gen_dummy_probes.pl"),
     str(root / "src/backend/utils/probes.d")], text=True)
probe_calls = re.findall(r"TRACE_POSTGRESQL_LOCK_WAIT_(?:START|DONE)\(.*?\);",
                         lock, re.S)
assert len(probe_calls) == 2
for call in probe_calls:
    assert len(call.split(",")) == 7
    assert call.endswith("locallock->tag.lock.locktag_field5);")

prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t uint8;
typedef uint16_t uint16;
typedef uint32_t uint32;
typedef uint64_t uint64;
typedef size_t Size;
typedef int LOCKMODE;
#define PGDLLIMPORT
#define StaticAssertDecl(c, m) _Static_assert(c, m)
#define pg_fallthrough __attribute__((fallthrough))
#define _(s) (s)
#if __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
#define WORDS_BIGENDIAN 1
#endif
#include "storage/locktag.h"
static uint32 pg_rotate_left32(uint32 v, int n) { return (v << n) | (v >> (32-n)); }
typedef struct { char data[256]; } StringInfoData;
typedef StringInfoData *StringInfo;
static void appendStringInfo(StringInfo, const char *, ...) __attribute__((format(printf, 2, 3)));
static void appendStringInfo(StringInfo buf, const char *fmt, ...)
{
    va_list ap;
    va_start(ap, fmt);
    int n = vsnprintf(buf->data, sizeof(buf->data), fmt, ap);
    va_end(ap);
    assert(n >= 0 && (size_t) n < sizeof(buf->data));
}
#define TransactionIdGetDatum(x) ((uint64) (x))
#define ObjectIdGetDatum(x) ((uint64) (uint32) (x))
#define Int16GetDatum(x) ((uint64) (int16_t) (x))
/* Only the local-XID component is needed for pg_locks decoding checks. */
#define VXIDGetDatum(proc, xid) ((uint64) (xid))
'''
decode = '''
static void decode(LOCKTAG tag, uint64 values[10], bool nulls[10])
{
    struct { LOCKTAG locktag; } storage = {tag}, *instance = &storage;
    switch (tag.locktag_type) {
''' + status + '''
    default: abort();
    }
}
'''
tests = r'''
#define SAME(make) do { \
    memset(&a, 0xa5, sizeof(a)); memset(&b, 0x5a, sizeof(b)); \
    make(a); make(b); assert(memcmp(&a, &b, sizeof(a)) == 0); \
    assert(a.locktag_field5 == 0); \
} while (0)
#define REL(t) SET_LOCKTAG_RELATION(t, 1, 2)
#define EXT(t) SET_LOCKTAG_RELATION_EXTEND(t, 1, 2)
#define DB(t) SET_LOCKTAG_DATABASE_FROZEN_IDS(t, 1)
#define PAGE(t) SET_LOCKTAG_PAGE(t, 1, 2, 3)
#define TUPLE(t) SET_LOCKTAG_TUPLE(t, 1, 2, 3, 4)
#define XACT(t) SET_LOCKTAG_TRANSACTION(t, xid)
#define VXACT(t) SET_LOCKTAG_VIRTUALTRANSACTION(t, vxid)
#define SPEC(t) SET_LOCKTAG_SPECULATIVE_INSERTION(t, xid, 77)
#define OBJ(t) SET_LOCKTAG_OBJECT(t, 1, 2, 3, 4)
#define ADV(t) SET_LOCKTAG_ADVISORY(t, 1, 2, 3, 4)
int main(void)
{
    LOCKTAG a, b;
    const uint64 xids[] = {0, 100, UINT64_C(0xffffffff), UINT64_C(0x100000000),
        UINT64_C(0x100000064), UINT64_C(0x8000000000000064), UINT64_MAX};
    for (size_t i = 0; i < sizeof(xids)/sizeof(xids[0]); ++i) {
        uint64 xid = xids[i];
        struct { int procNumber; uint64 localTransactionId; } vxid = {12, xid};
        SAME(REL); SAME(EXT); SAME(DB); SAME(PAGE); SAME(TUPLE);
        SAME(XACT); SAME(VXACT); SAME(SPEC); SAME(OBJ); SAME(ADV);
        for (int kind = 0; kind < 4; ++kind) {
            char expected[256];
            StringInfoData description;
            uint64 values[10] = {0};
            bool nulls[10] = {false};
            switch (kind) {
            case 0:
                XACT(a);
                snprintf(expected, sizeof(expected), "transaction %llu", (unsigned long long) xid);
                break;
            case 1:
                VXACT(a);
                snprintf(expected, sizeof(expected), "virtual transaction 12/%llu", (unsigned long long) xid);
                break;
            case 2:
                SPEC(a);
                snprintf(expected, sizeof(expected), "speculative token 77 of transaction %llu", (unsigned long long) xid);
                break;
            default:
                memset(&a, 0xa5, sizeof(a)); memset(&b, 0x5a, sizeof(b));
                SET_LOCKTAG_APPLY_TRANSACTION(a, 16384, 16385, xid, 1);
                SET_LOCKTAG_APPLY_TRANSACTION(b, 16384, 16385, xid, 1);
                assert(memcmp(&a, &b, sizeof(a)) == 0);
                snprintf(expected, sizeof(expected), "remote transaction %llu of subscription 16385 of database 16384", (unsigned long long) xid);
                break;
            }
            DescribeLockTag(&description, &a);
            assert(strcmp(description.data, expected) == 0);
            decode(a, values, nulls);
            assert(values[kind == 1 ? 5 : 6] == xid);
            if (kind == 2) assert(values[8] == 77);
            if (kind == 3) {
                assert(values[1] == 16384 && values[8] == 16385 && values[9] == 1);
                assert(!nulls[1] && !nulls[6] && !nulls[8] && !nulls[9]);
            }
        }
    }
    SET_LOCKTAG_APPLY_TRANSACTION(a, 16384, 16385, UINT64_C(100), 1);
    SET_LOCKTAG_APPLY_TRANSACTION(b, 16384, 16385, UINT64_C(0x100000064), 1);
    assert(memcmp(&a, &b, sizeof(a)) != 0);
    assert(tag_hash(&a, sizeof(a)) != tag_hash(&b, sizeof(b)));
    /* Each non-XID identifier remains part of the key. */
    b = a; ++b.locktag_field1; assert(memcmp(&a, &b, sizeof(a)) != 0);
    b = a; ++b.locktag_field2; assert(memcmp(&a, &b, sizeof(a)) != 0);
    b = a; ++b.locktag_field4; assert(memcmp(&a, &b, sizeof(a)) != 0);
    /* Real 2PC record layout retains the full key and the lock mode. */
    SET_LOCKTAG_APPLY_TRANSACTION(a, 16384, 16385, UINT64_MAX, 1);
    TwoPhaseLockRecord before = {a, 7}, after;
    unsigned char bytes[sizeof(before)];
    memcpy(bytes, &before, sizeof(before)); memcpy(&after, bytes, sizeof(after));
    assert(memcmp(&before.locktag, &after.locktag, sizeof(LOCKTAG)) == 0);
    assert(after.lockmode == 7);
    puts("PASS: distinct high-XID keys and hashes; all 11 constructors initialize every byte;");
    puts("      28 real diagnostic/pg_locks decoder cases; 2PC record layout; wait-probe arity.");
    return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="xid64-locktags-") as tmp:
    tmp = Path(tmp)
    source = tmp / "probe.c"
    source.write_text(prefix + hash_code + describe + record + decode + probes +
                      "\nstatic void check_probes(void) __attribute__((unused));\n"
                      "static void check_probes(void) {\n" +
                      "\n".join(probe_calls) + "\n}\n" + tests)
    subprocess.run(shlex.split(os.environ.get("CC", "cc")) +
                   ["-std=c11", "-O1", "-g", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=undefined", "-fno-sanitize-recover=all",
                    "-I" + str(root / "src/include"), str(source),
                    "-o", str(tmp / "probe")], check=True)
    subprocess.run([str(tmp / "probe")], check=True)

#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>

typedef uint32_t uint32;
typedef uint64_t uint64;
typedef uint64 TransactionId;
typedef uint64 MultiXactId;
typedef uint64 MultiXactOffset;
typedef uint32 Oid;
typedef struct { uint64 value; } FullTransactionId;
#define strtou64 strtoull
#define FirstNormalTransactionId UINT64_C(3)
#define FirstMultiXactId UINT64_C(1)
#define InvalidTransactionId UINT64_C(0)
#define InvalidOid 0
#define TransactionIdIsNormal(xid) ((xid) >= FirstNormalTransactionId)
#define FullTransactionIdFromXid(xid) ((FullTransactionId) {(xid)})

char *DataDir;
bool force, noupdate;
bool oldest_xid_given, next_xid_given, commit_ts_xids_given;
bool next_oid_given, mxids_given, next_mxoff_given;
TransactionId oldest_xid_val, next_xid_val;
TransactionId oldest_commit_ts_xid_val, newest_commit_ts_xid_val;
Oid next_oid_val;
MultiXactId next_mxid_val, oldest_mxid_val;
MultiXactOffset next_mxoff_val;
static const char *progname = "resetwal-probe";

static void pg_log_error(const char *format, ...)
{
    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    va_end(args);
    fputc('\n', stderr);
}

static void pg_log_error_hint(const char *format, ...)
{
    (void) format;
}

_Noreturn static void pg_fatal(const char *format, ...)
{
    va_list args;
    va_start(args, format);
    vfprintf(stderr, format, args);
    va_end(args);
    fputc('\n', stderr);
    exit(1);
}

/* PARSERS */

int main(int argc, char **argv)
{
    if (argc != 3)
        return 2;
    char *optarg = argv[2];
    char *endptr, *endptr2;
    switch (argv[1][0])
    {
        /* OPTION CASES */
        default: return 2;
    }
    struct {
        struct {
            FullTransactionId nextXid;
            TransactionId oldestXid, oldestCommitTsXid, newestCommitTsXid;
            MultiXactId nextMulti, oldestMulti;
            MultiXactOffset nextMultiOffset;
            Oid oldestXidDB, nextOid, oldestMultiDB;
        } checkPointCopy;
    } ControlFile = {0};
    ControlFile.checkPointCopy.oldestCommitTsXid = 1234;
    ControlFile.checkPointCopy.newestCommitTsXid = 5678;
    /* CONTROL ASSIGNMENTS */
    printf("xid=%" PRIu64 " oldest=%" PRIu64 " cts_old=%" PRIu64
           " cts_new=%" PRIu64 " multi=%" PRIu64 " old_multi=%" PRIu64
           " offset=%" PRIu64 " oid=%" PRIu32 "\n",
           ControlFile.checkPointCopy.nextXid.value,
           ControlFile.checkPointCopy.oldestXid,
           ControlFile.checkPointCopy.oldestCommitTsXid,
           ControlFile.checkPointCopy.newestCommitTsXid,
           ControlFile.checkPointCopy.nextMulti,
           ControlFile.checkPointCopy.oldestMulti,
           ControlFile.checkPointCopy.nextMultiOffset,
           ControlFile.checkPointCopy.nextOid);
    return 0;
}

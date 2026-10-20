#ifndef UPGRADE_FIXTURE_H
#define UPGRADE_FIXTURE_H
#define _GNU_SOURCE
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <limits.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/uio.h>
#include <unistd.h>
typedef uint32_t uint32;
typedef uint64_t uint64;
typedef int64_t int64;
typedef uint64 TransactionId;
typedef uint64 MultiXactId;
typedef uint64 MultiXactOffset;
typedef unsigned MultiXactStatus;
typedef struct { TransactionId xid; MultiXactStatus status; } MultiXactMember;
typedef union { uint64 align; char data[8192]; } PGAlignedBlock;
typedef struct {
    char *pgdata;
    const char *bindir;
    uint32 major_version;
    int xid_sz;
    struct { uint32 cat_ver; uint64 chkpnt_nxtmulti, chkpnt_nxtmxoff, chkpnt_oldstMulti;
             uint64 chkpnt_nxtxid, chkpnt_oldstxid; char nextxlogfile[25]; } controldata;
} ClusterInfo;
extern ClusterInfo old_cluster, new_cluster;
#define BLCKSZ 8192
#define SLRU_PAGES_PER_SEGMENT 32
#define PG_BINARY 0
#define PG_INT32_MAX INT32_MAX
#define PG_UINT32_MAX UINT32_MAX
#define PG_WARNING 1
#define MAXPGPATH 1024
#define UINT64CONST(x) UINT64_C(x)
#define INT64CONST(x) INT64_C(x)
#define GET_MAJOR_VERSION(v) ((v) / 100)
#define FirstMultiXactId UINT64CONST(1)
#define FirstNormalTransactionId UINT64CONST(3)
#define InvalidTransactionId 0
#define MaxMultiXactStatus 5
#define MultiXactStatusUpdate 5
#define ISUPDATE_from_mxstatus(s) ((s) > 3)
#define TransactionIdIsValid(x) ((x) != 0)
#define Assert assert
#define pg_malloc_object(t) ((t *)calloc(1, sizeof(t)))
#define pstrdup strdup
#define pfree free
#define pg_free free
#define pg_pread pread
#define pg_sprintf(d,...) snprintf(d,sizeof(d),__VA_ARGS__)
#define strtou64 strtoull
#define Max(a,b) ((a) > (b) ? (a) : (b))
#define UTILITY_LOG_FILE "unused"
#define MULTIXACT_FORMATCHANGE_CAT_VER 201301231
#define MULTIXACTOFFSET_FORMATCHANGE_CAT_VER 202512091
extern const unsigned pg_file_create_mode;
void pg_fatal(const char *, ...) __attribute__((noreturn,format(printf,1,2)));
void pg_log(int, const char *, ...) __attribute__((format(printf,2,3)));
char *psprintf(const char *, ...) __attribute__((format(printf,1,2)));
int pg_pwrite_zeros(int, off_t, off_t);
ssize_t pg_pwritev_with_retry(int, const struct iovec *, int, off_t);
bool cluster_is_xid64(const ClusterInfo *);
bool cluster_is_xid32(const ClusterInfo *);
bool cluster_has_64bit_multixact_offsets(const ClusterInfo *);
MultiXactOffset rewrite_multixacts(uint32, uint32, MultiXactId *);
void convert_xact(const char *, const char *);
#endif

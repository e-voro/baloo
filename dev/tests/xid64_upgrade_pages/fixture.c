#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>
typedef uint8_t uint8;
typedef uint16_t uint16;
typedef uint32_t uint32;
typedef size_t Size;
typedef char PageData;
typedef char *Page;
typedef uint32_t BlockNumber;
typedef struct { uint64_t lsn; uint16 pd_checksum, pd_flags, pd_lower, pd_upper,
    pd_special, pd_pagesize_version; uint32 hint; } PageHeaderData;
typedef PageHeaderData *PageHeader;
typedef union { uint64_t align; char data[8192]; } PGAlignedBlock;
typedef struct { uint64_t value; } FullTransactionId;
typedef struct { unsigned major_version; struct { unsigned data_checksum_version;
    uint64_t chkpnt_nxtxid; } controldata; } ClusterInfo;
static ClusterInfo new_cluster;
#define Assert assert
#define BLCKSZ 8192
#define SizeOfPageHeaderData 24
#define PG_PAGE_LAYOUT_VERSION PAGE_VERSION
#define PG_BINARY 0
#define PG_DATA_CHECKSUM_OFF 0
#define GET_MAJOR_VERSION(v) ((v) / 100)
#define strtou64 strtoull
static const unsigned pg_file_create_mode = 0600;
static _Noreturn void pg_fatal(const char *fmt, ...) { (void)fmt; exit(1); }
static unsigned str2uint(const char *s) {
    unsigned long long value = strtoull(s, NULL, 10);
    if (value > UINT32_MAX) pg_fatal("overflow");
    return (unsigned)value;
}
static uint16 pg_checksum_page(char *data, BlockNumber blkno) {
    assert(((PageHeader)data)->pd_pagesize_version == (BLCKSZ | PG_PAGE_LAYOUT_VERSION));
    return (uint16)(100 + blkno);
}
/* FUNCTIONS */
int main(int argc, char **argv) {
    assert(argc == 4);
    if (!strcmp(argv[1], "xid")) {
        char line[256];
        snprintf(line, sizeof(line), "Latest checkpoint's NextXID: %s", argv[3]);
        printf("%llu\n", (unsigned long long)parse_xid(line, (unsigned)atoi(argv[2])));
    } else {
        new_cluster.controldata.data_checksum_version = (unsigned)atoi(argv[3]);
        updateSegmentPagesVersion(argv[1], argv[2], "public", "fixture", 0);
    }
    return 0;
}

#define _GNU_SOURCE
#include <assert.h>
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdarg.h>
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
typedef uint64_t uint64;
typedef size_t Size;
typedef char PageData;
typedef char *Page;
typedef uint32 BlockNumber;
typedef uint32 Oid;
typedef uint32 RelFileNumber;
typedef struct { uint64 lsn; uint16 pd_checksum, pd_flags, pd_lower, pd_upper,
    pd_special, pd_pagesize_version; uint32 hint; } PageHeaderData;
typedef PageHeaderData *PageHeader;
typedef union { uint64 align; char data[8192]; } PGAlignedBlock;
typedef struct {
    const char *old_tablespace, *new_tablespace;
    const char *old_tablespace_suffix, *new_tablespace_suffix;
    Oid db_oid; RelFileNumber relfilenumber; char *nspname, *relname;
} FileNameMap;
typedef struct { char *pgdata; char **tablespaces; int num_tablespaces;
    const char *tablespace_suffix; uint32 major_version; int xid_sz;
    struct { uint32 cat_ver, data_checksum_version, largesz; } controldata;
} ClusterInfo;
typedef enum { TRANSFER_MODE_CLONE, TRANSFER_MODE_COPY, TRANSFER_MODE_COPY_FILE_RANGE,
    TRANSFER_MODE_LINK, TRANSFER_MODE_SWAP } transferMode;
static ClusterInfo old_cluster, new_cluster;
static struct { transferMode transfer_mode; bool do_sync; } user_opts;
static bool fail_sync;
#define Assert assert
#define BLCKSZ 8192
#define SizeOfPageHeaderData 24
#define PG_PAGE_LAYOUT_VERSION PAGE_VERSION
#define PG_DATA_CHECKSUM_OFF 0
#define PG_BINARY 0
#define MAXPGPATH 1024
#define PG_UINT32_MAX UINT32_MAX
#define GET_MAJOR_VERSION(v) ((v) / 100)
#define InvalidRelFileNumber 0
#define RelFileNumberIsValid(x) ((x) != 0)
#define VISIBILITY_MAP_FROZEN_BIT_CAT_VER 201603011
#define PG_LOG_ERROR 0
#define PGFILETYPE_REG 1
#define PG_STATUS 1
#define PG_VERBOSE 2
#define palloc malloc
#define pfree free
#define pg_free free
static unsigned pg_file_create_mode = 0600, pg_dir_create_mode = 0700;
static _Noreturn void pg_fatal(const char *fmt, ...) __attribute__((format(printf,1,2)));
static _Noreturn void pg_fatal(const char *fmt, ...) {
    va_list ap; va_start(ap,fmt); vfprintf(stderr,fmt,ap); va_end(ap); fputc('\n',stderr); exit(1);
}
static int fixture_snprintf(char *s,size_t n,const char *fmt,...) __attribute__((format(printf,3,4)));
static int fixture_snprintf(char *s,size_t n,const char *fmt,...) {
    va_list ap; va_start(ap,fmt); int len=vsnprintf(s,n,fmt,ap); va_end(ap); assert(len>=0 && (size_t)len<n); return len;
}
#define snprintf fixture_snprintf
static char *psprintf(const char *fmt,...) __attribute__((format(printf,1,2)));
static char *psprintf(const char *fmt,...) {
    va_list ap; char *s; va_start(ap,fmt); int n=vasprintf(&s,fmt,ap); va_end(ap); assert(n>=0); return s;
}
static int fixture_rename(const char *from,const char *to) {
    printf("RENAME|%s|%s\n",from,to); fflush(stdout); return rename(from,to);
}
#define rename fixture_rename
static int fsync_fname(const char *path,bool dir) {
    printf("%s|%s\n",dir ? "SYNCDIR" : "SYNCFILE",path); fflush(stdout);
    if (!dir && fail_sync && strstr(path,".pg_upgrade")) { errno=EIO; return -1; }
    int fd=open(path,O_RDONLY); if (fd<0) return -1;
    int rc=fsync(fd); close(fd); return rc;
}
static int fsync_parent_path(const char *path) {
    char *p=strdup(path); *strrchr(p,'/')=0; int rc=fsync_fname(p,true); free(p); return rc;
}
static void pre_sync_fname(const char *path,bool dir) { (void)path; (void)dir; }
static int pg_mkdir_p(char *path,unsigned mode) {
    char *p=strdup(path);
    for (char *s=p+1;;s++) {
        if (*s=='/' || !*s) { char c=*s; *s=0; if (mkdir(p,mode) && errno!=EEXIST) { free(p); return -1; }
            if (!c) break;
            *s=c; }
    }
    free(p); return 0;
}
static int pg_cmp_u32(uint32 a,uint32 b) { return (a>b)-(a<b); }
static int get_dirent_type(const char *path,const struct dirent *de,bool follow,int level) {
    struct stat st; (void)de; (void)follow; (void)level;
    if (lstat(path,&st)) pg_fatal("stat failed: %s",path);
    return S_ISREG(st.st_mode) ? PGFILETYPE_REG : 0;
}
static void pg_log(int level,const char *fmt,...) { (void)level; (void)fmt; }
static void copyFile(const char *from,const char *to,const char *nsp,const char *rel) {
    (void)nsp; (void)rel; int src=open(from,O_RDONLY), dst=open(to,O_WRONLY|O_CREAT|O_EXCL,0600);
    if (src<0 || dst<0) pg_fatal("fixture copy open");
    char buf[8192]; ssize_t n; while ((n=read(src,buf,sizeof(buf)))>0) assert(write(dst,buf,n)==n);
    assert(n==0); close(src); close(dst);
}
static void linkFile(const char *from,const char *to,const char *nsp,const char *rel) {
    (void)nsp; (void)rel; assert(link(from,to)==0);
}
static void cloneFile(const char *a,const char *b,const char *c,const char *d) {
    (void)a; (void)b; (void)c; (void)d; pg_fatal("clone is not exercised by this fixture");
}
static void copyFileByRange(const char *a,const char *b,const char *c,const char *d) {
    (void)a; (void)b; (void)c; (void)d; pg_fatal("copy_file_range is not exercised by this fixture");
}
static void rewriteVisibilityMap(const char *a,const char *b,const char *c,const char *d,bool update) {
    (void)a; (void)b; (void)c; (void)d; (void)update; pg_fatal("pre-9.6 VM conversion is not exercised");
}
static void transfer_relfile(FileNameMap *,const char *,bool,bool);
/* PAGE FUNCTIONS */
/* CHECKSUM */
/* FUNCTIONS */
static void checksum_file(const char *path,BlockNumber first,bool seal) {
    int fd=open(path,seal ? O_RDWR : O_RDONLY); assert(fd>=0);
    PGAlignedBlock page; ssize_t n; unsigned count=0;
    while ((n=read(fd,page.data,BLCKSZ))>0) {
        assert(n==BLCKSZ);
        if (PageIsNew(page.data)) {
            for (int i=0;i<BLCKSZ;i++) assert(!page.data[i]);
        } else {
            if (!seal) assert((((PageHeader)page.data)->pd_pagesize_version & 255)==PG_PAGE_LAYOUT_VERSION);
            uint16 sum=pg_checksum_page(page.data,first+count);
            if (seal) { ((PageHeader)page.data)->pd_checksum=sum;
                assert(pwrite(fd,page.data,BLCKSZ,(off_t)count*BLCKSZ)==BLCKSZ); }
            else assert(((PageHeader)page.data)->pd_checksum==sum);
        }
        count++;
    }
    assert(n==0); close(fd);
}
int main(int argc,char **argv) {
    if (!strcmp(argv[1],"seal") || !strcmp(argv[1],"verify")) {
        assert(argc==4); checksum_file(argv[2],(BlockNumber)strtoul(argv[3],NULL,10),!strcmp(argv[1],"seal")); return 0;
    }
    assert(argc==7);
    old_cluster.pgdata=psprintf("%s/old",argv[2]); new_cluster.pgdata=psprintf("%s/new",argv[2]);
    char *oldts=psprintf("%s/oldts",argv[2]), *newts=psprintf("%s/newts",argv[2]);
    old_cluster.tablespaces=&oldts; new_cluster.tablespaces=&newts;
    old_cluster.num_tablespaces=new_cluster.num_tablespaces=1;
    old_cluster.tablespace_suffix="/PG_OLD"; new_cluster.tablespace_suffix="/PG_NEW";
    old_cluster.major_version=new_cluster.major_version=190000;
    old_cluster.xid_sz=atoi(argv[3]); new_cluster.xid_sz=8;
    old_cluster.controldata.cat_ver=new_cluster.controldata.cat_ver=202607272;
    old_cluster.controldata.largesz=new_cluster.controldata.largesz=8;
    new_cluster.controldata.data_checksum_version=(unsigned)atoi(argv[4]);
    user_opts.do_sync=atoi(argv[5]); fail_sync=atoi(argv[6]);
    user_opts.transfer_mode=!strcmp(argv[1],"copy") ? TRANSFER_MODE_COPY :
        (!strcmp(argv[1],"link") ? TRANSFER_MODE_LINK : TRANSFER_MODE_SWAP);
    FileNameMap maps[2] = {
        {old_cluster.pgdata,new_cluster.pgdata,"/base","/base",16384,50000,"public","heap_a"},
        {oldts,newts,"/PG_OLD","/PG_NEW",16384,60000,"public","heap_b"}};
    if (!strcmp(argv[1],"partitioned")) {
        transfer_single_new_db(maps,2,old_cluster.pgdata,new_cluster.pgdata);
        transfer_single_new_db(maps,2,oldts,newts);
    } else transfer_single_new_db(maps,2,NULL,NULL);
    sync_queue_sync_all(); sync_queue_destroy(); return 0;
}

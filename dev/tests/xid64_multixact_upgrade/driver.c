#include "fixture.h"
#include "multixact_read_v18.h"
ClusterInfo old_cluster, new_cluster;
const unsigned pg_file_create_mode = 0600;
void pg_fatal(const char *fmt, ...) {
    va_list ap; va_start(ap,fmt); vfprintf(stderr,fmt,ap); va_end(ap);
    fputc('\n',stderr); exit(1);
}
void pg_log(int level, const char *fmt, ...) { (void)level; (void)fmt; }
char *psprintf(const char *fmt, ...) {
    char *s; va_list ap; va_start(ap,fmt); int n = vasprintf(&s,fmt,ap); va_end(ap);
    assert(n >= 0); return s;
}
int pg_pwrite_zeros(int fd, off_t len, off_t off) { return ftruncate(fd,len+off); }
ssize_t pg_pwritev_with_retry(int fd, const struct iovec *v, int n, off_t off) {
    assert(n == 1); return pwrite(fd,v[0].iov_base,v[0].iov_len,off);
}
uint64 fixture_source_id(uint64, uint64);
#ifndef SQL_FIXTURE_ONLY
int main(int argc, char **argv) {
    assert(argc >= 2);
    if (!strcmp(argv[1],"map")) {
        assert(argc == 4);
        printf("%llu\n", (unsigned long long)fixture_source_id(strtoull(argv[2],NULL,10),strtoull(argv[3],NULL,10)));
    } else if (!strcmp(argv[1],"rewrite")) {
        assert(argc == 9);
        bool wide = atoi(argv[4]);
        old_cluster.pgdata = argv[2]; new_cluster.pgdata = argv[3];
        old_cluster.major_version = wide ? 190000 : 180000;
        old_cluster.xid_sz = 4;
        old_cluster.controldata.cat_ver = wide ? 202607272 : 202506291;
        old_cluster.controldata.chkpnt_oldstMulti = strtoull(argv[5],NULL,10);
        old_cluster.controldata.chkpnt_nxtmulti = strtoull(argv[6],NULL,10);
        old_cluster.controldata.chkpnt_nxtmxoff = strtoull(argv[7],NULL,10);
        uint32 start = (uint32)old_cluster.controldata.chkpnt_oldstMulti;
        uint32 end = (uint32)old_cluster.controldata.chkpnt_nxtmulti;
        if (!strcmp(argv[8],"read")) {
            OldMultiXactReader *r = AllocOldMultiXactRead(argv[2],end,
                old_cluster.controldata.chkpnt_nxtmxoff,wide);
            MultiXactMember member;
            bool valid = GetOldMultiXactIdSingleMember(r,start,&member);
            printf("%d %llu %u\n",valid,(unsigned long long)(valid ? member.xid : 0),valid ? member.status : 0);
            FreeOldMultiXactReader(r);
        } else {
            MultiXactId next;
            uint64 off = rewrite_multixacts(start,end,&next);
            printf("%llu %llu\n",(unsigned long long)next,(unsigned long long)off);
        }
    } else if (!strcmp(argv[1],"clog")) {
        assert(argc == 6);
        old_cluster.controldata.chkpnt_oldstxid = strtoull(argv[4],NULL,10);
        old_cluster.controldata.chkpnt_nxtxid = strtoull(argv[5],NULL,10);
        convert_xact(argv[2],argv[3]);
    } else assert(false);
    return 0;
}

#endif

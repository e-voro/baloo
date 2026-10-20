#include "fixture.h"
typedef struct { const char *db; } PGconn;
typedef struct { bool databases; } PGresult;
#define RELKIND_RELATION 'r'
#define RELKIND_MATVIEW 'm'
#define RELKIND_TOASTVALUE 't'
#define STRINGIFY(x) #x
#define CppAsString2(x) STRINGIFY(x)
static void prep_status(const char *fmt, ...) { (void)fmt; }
static void check_ok(void) {}
static PGconn *connectToServer(ClusterInfo *cluster, const char *db) {
    assert(cluster == &new_cluster);
    PGconn *conn = malloc(sizeof(*conn)); conn->db = db; return conn;
}
static PGresult *executeQueryOrDie(PGconn *conn, const char *fmt, ...) {
    static PGresult res[2];
    char sql[4096]; va_list ap; va_start(ap,fmt); vsnprintf(sql,sizeof(sql),fmt,ap); va_end(ap);
    printf("SQL|%s|%s\n",conn->db,sql);
    bool select = strstr(sql,"SELECT") == sql;
    res[select].databases = select;
    return &res[select];
}
static int PQntuples(PGresult *res) { return res->databases ? 2 : 0; }
static int PQfnumber(PGresult *res, const char *name) { (void)res; return !strcmp(name,"datallowconn"); }
static char *PQgetvalue(PGresult *res, int row, int col) {
    assert(res->databases && row < 2);
    return col ? (row ? "f" : "t") : (row ? "template0" : "template1");
}
static void PQclear(PGresult *res) { (void)res; }
static void PQfinish(PGconn *conn) { free(conn); }
static char *quote_identifier(const char *name) { return (char *)name; }
static void remove_new_subdir(const char *path, bool top) { printf("REMOVE|%s|%d\n",path,top); }
/* Copy itself is unchanged. Prepopulate a destination to test actual renames. */
static void copy_subdir_files(const char *from, const char *to) { printf("COPY|%s|%s\n",from,to); }
static bool exec_prog(const char *log, const char *opt, bool report, bool die, const char *fmt, ...)
    __attribute__((format(printf,5,6)));
static bool exec_prog(const char *log, const char *opt, bool report, bool die, const char *fmt, ...) {
    char cmd[4096]; va_list ap; (void)log; (void)opt; assert(report && die);
    va_start(ap,fmt); vsnprintf(cmd,sizeof(cmd),fmt,ap); va_end(ap);
    printf("CMD|%s\n",cmd); return true;
}
/* FUNCTIONS */
int main(int argc, char **argv) {
    new_cluster.bindir = "/new/bin";
    if (!strcmp(argv[1],"dispatch")) {
        assert(argc == 12);
        old_cluster.pgdata=argv[2]; new_cluster.pgdata=argv[3];
        old_cluster.major_version=(uint32)strtoul(argv[4],NULL,10);
        old_cluster.xid_sz=atoi(argv[5]);
        old_cluster.controldata.cat_ver=(uint32)strtoul(argv[6],NULL,10);
        old_cluster.controldata.chkpnt_oldstMulti=strtoull(argv[7],NULL,10);
        old_cluster.controldata.chkpnt_nxtmulti=strtoull(argv[8],NULL,10);
        old_cluster.controldata.chkpnt_nxtmxoff=strtoull(argv[9],NULL,10);
        old_cluster.controldata.chkpnt_oldstxid=strtoull(argv[10],NULL,10);
        old_cluster.controldata.chkpnt_nxtxid=strtoull(argv[11],NULL,10);
        strcpy(old_cluster.controldata.nextxlogfile,"000000010000000000000001");
        copy_xact_xlog_xid();
        printf("RESULT|%llu|%llu|%llu|%llu\n",(unsigned long long)new_cluster.controldata.chkpnt_nxtxid,
            (unsigned long long)new_cluster.controldata.chkpnt_nxtmulti,
            (unsigned long long)new_cluster.controldata.chkpnt_oldstMulti,
            (unsigned long long)new_cluster.controldata.chkpnt_nxtmxoff);
    } else {
        assert(!strcmp(argv[1],"horizons") && argc == 6);
        old_cluster.major_version=190000; old_cluster.xid_sz=4;
        old_cluster.controldata.cat_ver=202607272;
        old_cluster.controldata.chkpnt_nxtxid=UINT64CONST(4294967396);
        old_cluster.controldata.chkpnt_oldstMulti=strtoull(argv[2],NULL,10);
        new_cluster.controldata.chkpnt_nxtmulti=strtoull(argv[3],NULL,10);
        set_frozenxids(atoi(argv[5]),atoi(argv[4]));
        adjust_multixact_horizons();
    }
    return 0;
}

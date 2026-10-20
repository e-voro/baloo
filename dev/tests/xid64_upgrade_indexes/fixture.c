/* SQL and connection scaffolding for extracted production functions. */
#include <assert.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint32_t uint32;
typedef struct { const char *db_name; } DbInfo;
typedef struct {
    uint32 major_version;
    int xid_sz;
    struct { uint32 cat_ver; } controldata;
    struct { int ndbs; DbInfo *dbs; } dbarr;
} ClusterInfo;
typedef struct { const char *db; } PGconn;
typedef struct { int rows; } PGresult;
typedef struct { char *data; } PQExpBufferData;
#define GET_MAJOR_VERSION(v) ((v) / 100)
#define FirstNormalObjectId 16384U
#define MAXPGPATH 1024
#define PG_WARNING 1
#define PG_REPORT 2
/* OFFSET FORMAT THRESHOLD */
static ClusterInfo old_cluster, new_cluster;
static ClusterInfo *running;
static unsigned selects, updates;
static bool check_phase;
static _Noreturn void pg_fatal(const char *fmt, ...) { (void) fmt; exit(1); }
static void prep_status(const char *fmt, ...) { (void) fmt; }
static void report_status(int level, const char *fmt, ...) { (void) level; (void) fmt; }
static void pg_log(int level, const char *fmt, ...) { (void) level; (void) fmt; }
static void check_ok(void) {}
static void start_postmaster(ClusterInfo *c, bool force) { assert(force && c == &new_cluster); running = c; }
static void stop_postmaster(bool fast) { assert(!fast); running = NULL; }
static void old_9_6_invalidate_hash_indexes(ClusterInfo *c, bool mode) { (void)c; (void)mode; assert(false); }
static void report_extension_updates(ClusterInfo *c) { assert(c == &new_cluster); }
static PGconn *connectToServer(ClusterInfo *c, const char *db) {
    static PGconn conn;
    assert(c == running);
    assert(c == (check_phase ? &old_cluster : &new_cluster));
    conn.db = db; return &conn;
}
static PGresult *executeQueryOrDie(PGconn *conn, const char *fmt, ...) {
    static PGresult res;
    char sql[4096]; va_list ap;
    va_start(ap, fmt); vsnprintf(sql, sizeof(sql), fmt, ap); va_end(ap);
    assert(strstr(sql, "i.indexrelid >= '16384'::pg_catalog.oid"));
    assert(strstr(sql, "a.amname = 'spgist'") || strstr(sql, "a.amname = 'gin'") ||
           strstr(sql, "NOT a.amname IN ('btree', 'hash', 'gist', 'gin', 'spgist', 'brin')"));
    if (!strncmp(sql, "SELECT", 6)) { selects++; res.rows = !strcmp(conn->db, "fixture_db"); }
    else { assert(!check_phase); assert(strstr(sql, "UPDATE pg_catalog.pg_index i ") == sql);
           assert(strstr(sql, "indisvalid = false")); assert(!strcmp(conn->db, "fixture_db")); updates++; res.rows = 0; }
    return &res;
}
static int PQntuples(PGresult *r) { return r->rows; }
static int PQfnumber(PGresult *r, const char *name) { (void)r; return !strcmp(name, "relname"); }
static const char *PQgetvalue(PGresult *r, int row, int col) {
    assert(row == 0 && r->rows == 1); return col ? "fixture_index" : "public";
}
static void PQclear(PGresult *r) { (void) r; }
static void PQfinish(PGconn *c) { (void) c; }
static FILE *fopen_priv(const char *path, const char *mode) { assert(!check_phase); return fopen(path, mode); }
static void initPQExpBuffer(PQExpBufferData *b) { b->data = NULL; }
static void appendPsqlMetaConnect(PQExpBufferData *b, const char *db) {
    static char text[128]; snprintf(text, sizeof(text), "\\connect %s\n", db); b->data = text;
}
static void termPQExpBuffer(PQExpBufferData *b) { b->data = NULL; }
static const char *quote_identifier(const char *s) { return s; }
/* FUNCTIONS */
int main(int argc, char **argv) {
    DbInfo dbs[] = {{"fixture_db"}, {"empty_db"}};
    if (argc == 5 && !strcmp(argv[1], "format")) {
        old_cluster.major_version = (uint32)strtoul(argv[2], NULL, 10);
        old_cluster.xid_sz = atoi(argv[3]);
        old_cluster.controldata.cat_ver = (uint32)strtoul(argv[4], NULL, 10);
        printf("%u\n", cluster_has_64bit_multixact_offsets(&old_cluster) ? 64U : 32U);
        return 0;
    }
    assert(argc == 4);
    old_cluster.major_version = (uint32)strtoul(argv[1], NULL, 10);
    old_cluster.xid_sz = atoi(argv[2]);
    old_cluster.controldata.cat_ver = (uint32)strtoul(argv[3], NULL, 10);
    old_cluster.dbarr.ndbs = new_cluster.dbarr.ndbs = 2;
    old_cluster.dbarr.dbs = new_cluster.dbarr.dbs = dbs;
    bool convert = cluster_is_xid32(&old_cluster);
    assert(xid_check_applicable(&old_cluster) == convert);
    check_phase = true; running = &old_cluster;
    preflight();
    assert(selects == (convert ? 6U : 0U) && updates == 0);
    check_phase = false; running = NULL; selects = 0;
    issue_warnings_and_set_wal_level();
    assert(!running && selects == (convert ? 6U : 0U) && updates == (convert ? 3U : 0U));
    return 0;
}

/* Backend scaffolding only; binary encoding/decoding is extracted from source. */
#include <arpa/inet.h>
#include <assert.h>
#include <setjmp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef uint8_t uint8;
typedef uint16_t uint16;
typedef uint32_t uint32;
typedef uint64_t uint64;
typedef uint64 TransactionId;
typedef uint64 Datum;
typedef struct
{
    char *data;
    int len;
    int maxlen;
    int cursor;
} StringInfoData;
typedef StringInfoData *StringInfo;
/* Simplified bytea header; the production payload starts after these 4 bytes. */
typedef struct { uint32 len; unsigned char data[]; } bytea;
#define VARHDRSZ 4
#define SET_VARSIZE(p, n) ((p)->len = (n))
#define Assert(c) assert(c)
#define pg_restrict restrict
#define pg_hton16 htons
#define pg_hton32 htonl
#define pg_ntoh16 ntohs
#define pg_ntoh32 ntohl
#define PG_FUNCTION_ARGS Datum arg
#define PG_GETARG_POINTER(n) ((void *) (uintptr_t) arg)
#define PG_GETARG_TRANSACTIONID(n) ((TransactionId) arg)
#define PG_RETURN_TRANSACTIONID(v) return (Datum) (v)
#define PG_RETURN_BYTEA_P(v) return (Datum) (uintptr_t) (v)

static jmp_buf error_jump;
static char error_message[128];
#define ERRCODE_PROTOCOL_VIOLATION 1
#define errcode(v) ((void) (v))
#define errmsg(...) snprintf(error_message, sizeof(error_message), __VA_ARGS__)
#define ereport(level, detail) do { (void) (detail); longjmp(error_jump, 1); } while (0)
#define elog(level, ...) do { errmsg(__VA_ARGS__); longjmp(error_jump, 1); } while (0)

static void initStringInfo(StringInfo buf)
{
    buf->data = malloc(64);
    assert(buf->data);
    buf->len = buf->cursor = 0;
    buf->maxlen = 64;
}

static void enlargeStringInfo(StringInfo buf, int size)
{
    assert(size >= 0 && buf->len + size < buf->maxlen);
}

#define appendStringInfoCharMacro(buf, ch) do { \
    enlargeStringInfo(buf, 1); \
    (buf)->data[(buf)->len++] = (ch); \
    (buf)->data[(buf)->len] = '\0'; \
} while (0)

/* PRODUCTION FUNCTIONS */

static void expect_error(Datum (*receive)(Datum), int size, const char *expected)
{
    char payload[8] = {0};
    StringInfoData input = {payload, size, sizeof(payload), 0};
    error_message[0] = '\0';
    if (setjmp(error_jump) == 0)
    {
        (void) receive((Datum) (uintptr_t) &input);
        assert(!"expected receive error");
    }
    assert(strcmp(error_message, expected) == 0);
}

int main(void)
{
    const uint64 xids[] = {
        0, 1, 2, 3, UINT32_MAX, UINT64_C(0x100000000),
        UINT64_C(0x100000064), UINT64_C(0x0102030405060708),
        UINT64_C(0x7fffffffffffffff), UINT64_C(0x8000000000000000), UINT64_MAX
    };
    const unsigned char expected[] = {5, 6, 7, 8, 1, 2, 3, 4};
    _Static_assert(sizeof(TransactionId) == 8, "exercise xid64");
    _Static_assert(sizeof(uint32) == 4, "wire halves are 4 bytes");
    for (size_t i = 0; i < sizeof(xids) / sizeof(xids[0]); ++i)
    {
        bytea *wire = (bytea *) (uintptr_t) xidsend(xids[i]);
        assert(wire->len == VARHDRSZ + 8);
        if (xids[i] == UINT64_C(0x0102030405060708))
            assert(memcmp(wire->data, expected, sizeof(expected)) == 0);
        StringInfoData input = {(char *) wire->data, 8, 8, 0};
        assert(xidrecv((Datum) (uintptr_t) &input) == xids[i]);
        assert(input.cursor == 8);
        free(wire);
    }
    /* Independent golden input prevents matching sender/receiver bugs passing. */
    StringInfoData golden = {(char *) expected, sizeof(expected), sizeof(expected), 0};
    assert(xidrecv((Datum) (uintptr_t) &golden) == UINT64_C(0x0102030405060708));
    for (int size = 0; size < 8; ++size)
        expect_error(xidrecv, size, "insufficient data left in message");
    expect_error(xidrecv_before_fix, 8, "unsupported integer size 8");
    puts("PASS: 11 full-XID round trips; low-half-first golden bytes; 8 truncated inputs rejected;");
    puts("      original reader bug reproduced with uint64 TransactionId; UBSan enabled.");
    return 0;
}

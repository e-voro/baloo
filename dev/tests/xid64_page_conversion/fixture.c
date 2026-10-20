/* Fixed-width fixtures for check.py; page layout/helpers come from the source. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t uint8;
typedef uint16_t uint16;
typedef int16_t int16;
typedef uint32_t uint32;
typedef uint64_t uint64;
typedef int64_t int64;
typedef uint64 TransactionId;
typedef uint64 MultiXactId;
typedef uint32 ShortTransactionId;
typedef uint64 XLogRecPtr;
typedef size_t Size;
typedef char *Pointer;
typedef uint16 Offset;
#define InvalidTransactionId UINT64_C(0)
#define FrozenTransactionId UINT64_C(2)
#define FirstNormalTransactionId UINT64_C(3)
#define FirstMultiXactId UINT64_C(1)
#define MaxTransactionId UINT64_MAX
#define MaxShortTransactionId UINT64_C(0x7fffffff)
#define PG_UINT32_MAX UINT32_MAX
#define TransactionIdIsNormal(x) ((x) >= FirstNormalTransactionId)
#define TransactionIdIsValid(x) ((x) != InvalidTransactionId)
#define TransactionIdPrecedes(a,b) ((a) < (b))
#define PGDLLIMPORT
#define FLEXIBLE_ARRAY_MEMBER
#define StaticAssertDecl(c,m) _Static_assert(c,m)
#define USE_ASSERT_CHECKING 1
#define Assert assert
#define unlikely(x) (x)
#define MAXIMUM_ALIGNOF 8
#define MAXALIGN(x) (((x) + 7) & ~((size_t) 7))
#define Min(a,b) ((a) < (b) ? (a) : (b))
#define Max(a,b) ((a) > (b) ? (a) : (b))
#define ereport(level,args) abort()
#define elog(level,...) do { if ((level) > 1) abort(); } while (0)
#define DEBUG2 1
#define PANIC 2
#define ERROR 3
#include "storage/bufpage.h"
typedef union { uint64 align; char data[BLCKSZ]; } PGAlignedBlock;
/* Minimal tuple fixture; no claim to reproduce the full backend tuple ABI. */
typedef struct {
    union { struct { uint32 t_xmin, t_xmax; } t_heap; } t_choice;
    uint16 t_infomask, t_infomask2;
    uint32 payload;
} HeapTupleHeaderData;
typedef HeapTupleHeaderData *HeapTupleHeader;
typedef struct { HeapTupleHeader t_data; TransactionId t_xmax; } HeapTupleData;
typedef HeapTupleData *HeapTuple;
typedef struct {
    TransactionId xmax;
    uint16 t_infomask, t_infomask2;
    uint8 frzflags;
} HeapTupleFreeze;
#define HEAP_XMAX_IS_MULTI 0x1000
#define HEAP_XMIN_FROZEN 0x0300
#define HeapTupleHeaderXminFrozen(t) (((t)->t_infomask & HEAP_XMIN_FROZEN) == HEAP_XMIN_FROZEN)
#define HeapTupleHeaderSetXvac(t,x) abort()
#define XLH_FREEZE_XVAC 1
#define XLH_INVALID_XVAC 2
#define MaxHeapTuplesPerPage (BLCKSZ / sizeof(HeapTupleHeaderData))
typedef void *Relation;
typedef int Buffer;
#define IsBufferLockedExclusive(b) ((b) == 1)
#define BufferIsValid(b) ((b) != 0)
#define START_CRIT_SECTION() ((void) 0)
#define END_CRIT_SECTION() ((void) 0)
#define MarkBufferDirty(b) ((void) 0)
#define RelationNeedsWAL(r) false
#define IsToastRelation(r) false
typedef struct { int64 delta; bool multi; uint8 flags; } xl_heap_base_shift;
#define XLH_BASE_SHIFT_ON_TOAST_RELATION 1
#define SizeOfHeapBaseShift sizeof(xl_heap_base_shift)
#define XLogBeginInsert() ((void) 0)
#define XLogRegisterData(p,n) ((void) (p), (void) (n))
#define XLogRegisterBuffer(b,buf,flags) ((void) 0)
#define XLogInsert(rm,info) UINT64_C(0)
/* PRODUCTION */

static void init_page(Page page, bool normal, bool toast, TransactionId base)
{
    memset(page, 0, BLCKSZ);
    PageHeader h = (PageHeader) page;
    h->pd_lower = SizeOfPageHeaderData;
    h->pd_upper = h->pd_special = normal ?
        (toast ? ToastPageSpecialOffset : HeapPageSpecialOffset) : BLCKSZ;
    PageSetPageSizeAndVersion(page, BLCKSZ, PG_PAGE_LAYOUT_VERSION);
    if (normal) {
        if (toast) ToastPageGetSpecial(page)->pd_xid_base = base;
        else HeapPageGetSpecial(page)->pd_xid_base = base;
    }
}

static HeapTupleHeader tuple_at(Page page, OffsetNumber off)
{
    return PageGetItem(page, PageGetItemId(page, off));
}

static void add_tuple(Page page, TransactionId xmax, bool multi, uint32 payload)
{
    PageHeader h = (PageHeader) page;
    OffsetNumber off = PageGetMaxOffsetNumber(page) + 1;
    h->pd_lower += sizeof(ItemIdData);
    h->pd_upper -= MAXALIGN(sizeof(HeapTupleHeaderData));
    ItemId lp = PageGetItemId(page, off);
    ItemIdSetNormal(lp, h->pd_upper, sizeof(HeapTupleHeaderData));
    HeapTupleHeader t = tuple_at(page, off);
    t->t_infomask = HEAP_XMIN_FROZEN | (multi ? HEAP_XMAX_IS_MULTI : 0);
    t->payload = payload;
    HeapTupleHeaderSetDoubleXmax(t, xmax);
}

static TransactionId xmax_at(Page page, OffsetNumber off)
{
    HeapTupleHeader t = tuple_at(page, off);
    if (HeapPageIsDoubleXmax(page)) return HeapTupleHeaderGetDoubleXmax(t);
    TransactionId base = (t->t_infomask & HEAP_XMAX_IS_MULTI) ?
        HeapPageGetSpecial(page)->pd_multi_base : PageGetSpecialXidBase(page);
    return ShortTransactionIdToNormal(base, t->t_choice.t_heap.t_xmax);
}

static void check_hints(void)
{
    PGAlignedBlock b;
    TransactionId bases[] = {0, 997, UINT64_C(4294967296), UINT64_MAX - MaxShortTransactionId};
    for (int toast = 0; toast < 2; toast++) {
        for (unsigned i = 0; i < sizeof(bases)/sizeof(bases[0]); i++) {
            TransactionId base = bases[i];
            init_page(b.data, true, toast, base);
            TransactionId exact[] = {base + 3, base + 100, base + MaxShortTransactionId};
            for (unsigned j = 0; j < sizeof(exact)/sizeof(exact[0]); j++) {
                HeapPageSetPruneXid(b.data, exact[j]);
                assert(HeapPageGetPruneXid(b.data) == exact[j]);
                assert(PageGetPruneXid(b.data) == exact[j]);
                assert(HeapPageGetPruneXidNoAssert(b.data, toast) == exact[j]);
            }
            if (base >= 3) {
                HeapPageSetPruneXid(b.data, base);
                assert(HeapPageGetPruneXid(b.data) == FrozenTransactionId);
            }
            if (base < UINT64_MAX - MaxShortTransactionId) {
                HeapPageSetPruneXid(b.data, base + MaxShortTransactionId + 1);
                assert(HeapPageGetPruneXid(b.data) == FrozenTransactionId);
            }
            HeapPageSetPruneXid(b.data, 0);
            assert(PageGetPruneXid(b.data) == 0);
        }
    }
    init_page(b.data, false, false, 0);
    PageSetPrunable(b.data, UINT32_MAX);
    assert(PageGetPruneXid(b.data) == UINT32_MAX);
    HeapPageSetPruneXid(b.data, UINT64_C(4294967396));
    assert(PageGetPruneXid(b.data) == FrozenTransactionId);
    PageSetPrunable(b.data, 1000); /* Keep the conservative retry hint. */
    assert(PageGetPruneXid(b.data) == FrozenTransactionId);
    HeapPageSetPruneXid(b.data, 0);
    PageSetPrunable(b.data, 1000);
    assert(PageGetPruneXid(b.data) == 1000);
}

static void check_conversion(void)
{
    for (int toast = 0; toast < 2; toast++) {
        PGAlignedBlock primary, standby;
        init_page(primary.data, false, toast, 0);
        add_tuple(primary.data, 1000, false, 42);
        ((PageHeader) primary.data)->pd_prune_xid = 1000;
        memcpy(standby.data, primary.data, BLCKSZ);
        ((PageHeader) standby.data)->pd_prune_xid = 100; /* Different unlogged hint. */
        PageRepairFragmentation(primary.data, toast);
        PageRepairFragmentation(standby.data, toast);
        assert(PageGetSpecialXidBase(primary.data) == 997);
        assert(((PageHeader) primary.data)->pd_prune_xid == 3);
        assert(PageGetPruneXid(primary.data) == 1000);
        assert(PageGetPruneXid(standby.data) == FrozenTransactionId);
        assert(xmax_at(primary.data, 1) == 1000);
        assert(tuple_at(primary.data, 1)->payload == 42);
        PageClearPrunable(primary.data);
        PageClearPrunable(standby.data);
        assert(memcmp(primary.data, standby.data, BLCKSZ) == 0);
        /* The newly initialized free space must not contain stack bytes. */
        PageHeader h = (PageHeader) primary.data;
        for (int i = h->pd_lower; i < h->pd_upper; i++) assert(primary.data[i] == 0);
        /* Empty conversion clears a stale legacy hint. */
        init_page(primary.data, false, toast, 0);
        h->pd_prune_xid = UINT32_MAX;
        PageRepairFragmentation(primary.data, toast);
        assert(!HeapPageIsDoubleXmax(primary.data));
        assert(PageGetPruneXid(primary.data) == 0);
    }
}

static void check_freezing(void)
{
    TransactionId high = UINT64_C(4294967396);
    for (int multi = 0; multi < 2; multi++) {
        PGAlignedBlock b;
        init_page(b.data, false, false, 0);
        add_tuple(b.data, 1000, true, 42);
        HeapTupleFreeze frz = { .xmax = high,
            .t_infomask = HEAP_XMIN_FROZEN | (multi ? HEAP_XMAX_IS_MULTI : 0) };
        /* Production call order is checked by check.py for primary and redo. */
        heap_execute_freeze_tuple_page(b.data, tuple_at(b.data, 1), &frz);
        PageRepairFragmentation(b.data, false);
        assert(!HeapPageIsDoubleXmax(b.data));
        assert(xmax_at(b.data, 1) == high);
        assert(tuple_at(b.data, 1)->payload == 42);
    }
    /* An unrepresentable range must retain the double-xmax format. */
    PGAlignedBlock b;
    init_page(b.data, false, false, 0);
    add_tuple(b.data, 1000, false, 1);
    add_tuple(b.data, 1000, true, 2);
    HeapTupleFreeze frz = {.xmax = high, .t_infomask = HEAP_XMIN_FROZEN};
    heap_execute_freeze_tuple_page(b.data, tuple_at(b.data, 2), &frz);
    PageRepairFragmentation(b.data, false);
    assert(HeapPageIsDoubleXmax(b.data));
    assert(xmax_at(b.data, 1) == 1000 && xmax_at(b.data, 2) == high);
}

static void check_shift(void)
{
    PGAlignedBlock b;
    init_page(b.data, false, false, 0);
    add_tuple(b.data, 1000, false, 42);
    PageRepairFragmentation(b.data, false);
    HeapPageSetPruneXid(b.data, 1000);
    heap_page_shift_base(NULL, 1, b.data, false, -100, false);
    assert(PageGetPruneXid(b.data) == 1000 && xmax_at(b.data, 1) == 1000);
    heap_page_shift_base(NULL, 1, b.data, true, 100, false);
    assert(PageGetPruneXid(b.data) == 1000 && xmax_at(b.data, 1) == 1000);
    HeapPageSetPruneXid(b.data, 900);
    heap_page_shift_base(NULL, 1, b.data, false, 100, false);
    assert(PageGetPruneXid(b.data) == FrozenTransactionId);
    assert(xmax_at(b.data, 1) == 1000);
}

int main(void)
{
    check_hints(); check_conversion(); check_freezing(); check_shift();
    printf("PASS BLCKSZ=%d: hint boundaries, conversion, freeze results, base shifts\n", BLCKSZ);
}

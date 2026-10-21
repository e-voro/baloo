#include "postgres.h"

#include "access/table.h"
#include "access/htup_details.h"
#include "access/heapam_xlog.h"
#include "access/heapam.h"
#include "access/visibilitymap.h"
#include "fmgr.h"
#include "miscadmin.h"
#include "storage/bufmgr.h"
#include "storage/procarray.h"
#include "utils/builtins.h"

PG_MODULE_MAGIC;

PG_FUNCTION_INFO_V1(xid64_hold_pin);
PG_FUNCTION_INFO_V1(xid64_vm_status);
PG_FUNCTION_INFO_V1(xid64_mask_image);
PG_FUNCTION_INFO_V1(xid64_prune_no_repair);

/* Keep a direct reference to a dead HOT root, like a pin-only consumer. */
Datum
xid64_hold_pin(PG_FUNCTION_ARGS)
{
	Relation rel = table_open(PG_GETARG_OID(0), AccessShareLock);
	Buffer buffer = ReadBuffer(rel, 0);
	Page page = BufferGetPage(buffer);
	ItemId lp;
	HeapTupleHeader tuple;
	char *saved;
	Size len;
	char *marker = text_to_cstring(PG_GETARG_TEXT_PP(1));
	FILE *ready;

	LockBuffer(buffer, BUFFER_LOCK_SHARE);
	lp = PageGetItemId(page, 2);
	if (!ItemIdIsNormal(lp))
		elog(ERROR, "expected a normal HOT root at offset 2");
	tuple = (HeapTupleHeader) PageGetItem(page, lp);
	len = ItemIdGetLength(lp) - tuple->t_hoff;
	saved = palloc(len);
	memcpy(saved, (char *) tuple + tuple->t_hoff, len);
	LockBuffer(buffer, BUFFER_LOCK_UNLOCK);

	ready = fopen(marker, "w");
	if (ready == NULL || fclose(ready) != 0)
		elog(ERROR, "could not create pin-ready marker");
	for (int i = 0; i < 80; i++)
	{
		CHECK_FOR_INTERRUPTS();
		pg_usleep(100000L);
	}
	if (memcmp(saved, (char *) tuple + tuple->t_hoff, len) != 0)
		elog(ERROR, "tuple payload changed while holding a pin");

	ReleaseBuffer(buffer);
	table_close(rel, AccessShareLock);
	PG_RETURN_BOOL(true);
}

Datum
xid64_vm_status(PG_FUNCTION_ARGS)
{
	Relation rel = table_open(PG_GETARG_OID(0), AccessShareLock);
	Buffer vmbuffer = InvalidBuffer;
	uint8 bits = visibilitymap_get_status(rel, 0, &vmbuffer);

	if (BufferIsValid(vmbuffer))
		ReleaseBuffer(vmbuffer);
	table_close(rel, AccessShareLock);
	PG_RETURN_INT32(bits);
}

Datum
xid64_mask_image(PG_FUNCTION_ARGS)
{
	bytea *input = PG_GETARG_BYTEA_PP(0);
	bytea *output;
	PGAlignedBlock image;

	if (VARSIZE_ANY_EXHDR(input) != BLCKSZ)
		elog(ERROR, "expected one page");
	memcpy(image.data, VARDATA_ANY(input), BLCKSZ);
	heap_mask(image.data, 0);
	output = palloc(VARHDRSZ + BLCKSZ);
	SET_VARSIZE(output, VARHDRSZ + BLCKSZ);
	memcpy(VARDATA(output), image.data, BLCKSZ);
	PG_RETURN_BYTEA_P(output);
}

/* Create the valid one-unused-slot layout addressed by series patch 0008. */
Datum
xid64_prune_no_repair(PG_FUNCTION_ARGS)
{
	Relation rel = table_open(PG_GETARG_OID(0), RowExclusiveLock);
	Buffer buffer = ReadBuffer(rel, 0);
	Buffer vmbuffer = InvalidBuffer;
	PruneFreezeParams params = {0};
	PruneFreezeResult result;
	OffsetNumber off;
	Page page = BufferGetPage(buffer);
	bool retained_storage;

	visibilitymap_pin(rel, 0, &vmbuffer);
	LockBuffer(buffer, BUFFER_LOCK_EXCLUSIVE);
	params.relation = rel;
	params.buffer = buffer;
	params.vmbuffer = vmbuffer;
	params.reason = PRUNE_ON_ACCESS;
	params.options = HEAP_PAGE_PRUNE_MARK_UNUSED_NOW |
		HEAP_PAGE_PRUNE_NO_REPAIR_FRAGMENTATION;
	params.vistest = GlobalVisTestFor(rel);
	heap_page_prune_and_freeze(&params, &result, &off, NULL, NULL);
	if (PageGetMaxOffsetNumber(page) != 1 ||
		ItemIdIsUsed(PageGetItemId(page, 1)))
		elog(ERROR, "expected one unused slot after pruning");
	/* A free-line-pointer hint makes insertion reuse slot 1. */
	PageSetHasFreeLinePointers(page);
	MarkBufferDirtyHint(buffer, true);
	retained_storage = ((PageHeader) page)->pd_upper !=
		((PageHeader) page)->pd_special;
	UnlockReleaseBuffer(buffer);
	ReleaseBuffer(vmbuffer);
	table_close(rel, RowExclusiveLock);
	PG_RETURN_BOOL(retained_storage);
}

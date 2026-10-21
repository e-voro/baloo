#include "postgres.h"

#include "access/table.h"
#include "access/htup_details.h"
#include "access/visibilitymap.h"
#include "fmgr.h"
#include "miscadmin.h"
#include "storage/bufmgr.h"
#include "utils/builtins.h"

PG_MODULE_MAGIC;

PG_FUNCTION_INFO_V1(xid64_hold_pin);
PG_FUNCTION_INFO_V1(xid64_vm_status);

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

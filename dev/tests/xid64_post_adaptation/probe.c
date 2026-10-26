/* Helpers used only in disposable post-adaptation test clusters. */
#include "postgres.h"
#include "access/htup_details.h"
#include "access/relation.h"
#include "fmgr.h"
#include "miscadmin.h"
#include "storage/bufmgr.h"
#include "storage/lmgr.h"
#include "storage/lock.h"
#include "utils/rel.h"

PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(todo_apply_lock);
PG_FUNCTION_INFO_V1(todo_apply_try);
PG_FUNCTION_INFO_V1(todo_toast_xmax);

#define TEST_SUBOID ((Oid) 700001)

Datum
todo_apply_lock(PG_FUNCTION_ARGS)
{
	TransactionId xid = PG_GETARG_TRANSACTIONID(0);
	uint16 subtype = PG_GETARG_INT32(1);

	if (PG_GETARG_BOOL(2))
		LockApplyTransactionForSession(TEST_SUBOID, xid, subtype, ExclusiveLock);
	else
		UnlockApplyTransactionForSession(TEST_SUBOID, xid, subtype, ExclusiveLock);
	PG_RETURN_VOID();
}

Datum
todo_apply_try(PG_FUNCTION_ARGS)
{
	LOCKTAG tag;
	LockAcquireResult result;

	SET_LOCKTAG_APPLY_TRANSACTION(tag, MyDatabaseId, PG_GETARG_OID(2),
								 PG_GETARG_TRANSACTIONID(0), PG_GETARG_INT32(1));
	result = LockAcquire(&tag, ExclusiveLock, true, true);
	if (result != LOCKACQUIRE_NOT_AVAIL)
		LockRelease(&tag, ExclusiveLock, true);
	PG_RETURN_BOOL(result != LOCKACQUIRE_NOT_AVAIL);
}

Datum
todo_toast_xmax(PG_FUNCTION_ARGS)
{
	Relation parent = relation_open(PG_GETARG_OID(0), AccessShareLock);
	Relation toast = relation_open(parent->rd_rel->reltoastrelid, AccessShareLock);
	BlockNumber nblocks = RelationGetNumberOfBlocks(toast);
	int count = 0;

	for (BlockNumber block = 0; block < nblocks; ++block)
	{
		Buffer buffer = ReadBuffer(toast, block);
		Page page;

		LockBuffer(buffer, BUFFER_LOCK_SHARE);
		page = BufferGetPage(buffer);
		for (OffsetNumber off = FirstOffsetNumber;
			 off <= PageGetMaxOffsetNumber(page); ++off)
		{
			ItemId item = PageGetItemId(page, off);

			if (ItemIdIsNormal(item))
			{
				HeapTupleHeader tuple = (HeapTupleHeader) PageGetItem(page, item);
				volatile TransactionId xmax = HeapTupleHeaderGetRawXmax(page, tuple);

				(void) xmax;
				++count;
			}
		}
		UnlockReleaseBuffer(buffer);
	}
	relation_close(toast, AccessShareLock);
	relation_close(parent, AccessShareLock);
	PG_RETURN_INT32(count);
}

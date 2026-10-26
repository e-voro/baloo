/* Test-only helpers for a disposable upgraded cluster. */
#include "postgres.h"

#include <sys/stat.h>
#include <unistd.h>

#include "access/relation.h"
#include "access/xloginsert.h"
#include "fmgr.h"
#include "storage/aio.h"
#include "storage/buf_internals.h"
#include "storage/bufmgr.h"
#include "utils/builtins.h"
#include "utils/injection_point.h"
#include "utils/rel.h"

PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(gate_attach);
PG_FUNCTION_INFO_V1(gate_read);
PG_FUNCTION_INFO_V1(gate_recent);
PG_FUNCTION_INFO_V1(gate_raw);

PGDLLEXPORT void gate_pause(const char *name, const void *private_data, void *arg);

/* No PostgreSQL allocation or ERROR is permitted in this critical-section hook. */
void
gate_pause(const char *name, const void *private_data, void *arg)
{
	const char *dir = private_data;
	char entered[MAXPGPATH];
	char release[MAXPGPATH];
	FILE *file;

	snprintf(entered, sizeof(entered), "%s/entered", dir);
	snprintf(release, sizeof(release), "%s/release", dir);
	file = fopen(entered, "w");
	if (file == NULL)
		return;
	fprintf(file, "%d\n", *(Buffer *) arg);
	fclose(file);
	for (int i = 0; i < 6000 && access(release, F_OK) != 0; ++i)
		pg_usleep(10000L);
}

Datum
gate_attach(PG_FUNCTION_ARGS)
{
	char *library = text_to_cstring(PG_GETARG_TEXT_PP(0));
	char *dir = text_to_cstring(PG_GETARG_TEXT_PP(1));

	InjectionPointAttach("buffer-conversion-header-published", library,
						 "gate_pause", dir, strlen(dir) + 1);
	PG_RETURN_VOID();
}

Datum
gate_read(PG_FUNCTION_ARGS)
{
	Relation rel = relation_open(PG_GETARG_OID(0), AccessShareLock);
	char *marker = text_to_cstring(PG_GETARG_TEXT_PP(1));
	Buffer buffer = ReadBuffer(rel, 0);
	FILE *file;
	uint64 state;

	LockBuffer(buffer, BUFFER_LOCK_SHARE);
	state = pg_atomic_read_u64(&GetBufferDescriptor(buffer - 1)->state);
	if ((state & (BM_CONVERSION_PENDING | BM_CONVERSION_NEEDS_WAL)) ||
		!XLogRecPtrIsValid(PageGetLSN(BufferGetPage(buffer))))
		elog(ERROR, "normal read returned before conversion WAL was published");
	LockBuffer(buffer, BUFFER_LOCK_UNLOCK);
	file = fopen(marker, "w");

	if (file == NULL)
		elog(ERROR, "cannot write conversion-gate marker");
	fprintf(file, "%d\n", buffer);
	fclose(file);
	ReleaseBuffer(buffer);
	relation_close(rel, AccessShareLock);
	PG_RETURN_INT32(buffer);
}

Datum
gate_recent(PG_FUNCTION_ARGS)
{
	Relation rel = relation_open(PG_GETARG_OID(0), AccessShareLock);
	Buffer buffer = PG_GETARG_INT32(1);
	bool found = ReadRecentBuffer(rel->rd_locator, MAIN_FORKNUM, 0, buffer);

	if (found)
		ReleaseBuffer(buffer);
	relation_close(rel, AccessShareLock);
	PG_RETURN_BOOL(found);
}

/* Explicitly test low-level I/O, metadata-free reads and overwrite contracts. */
Datum
gate_raw(PG_FUNCTION_ARGS)
{
	Relation rel = relation_open(PG_GETARG_OID(0), AccessShareLock);
	int action = PG_GETARG_INT32(1);
	BlockNumber block = PG_GETARG_INT32(2);
	Buffer buffer;
	int result = 1;

	if (action == 0)
	{
		buffer = ReadBufferWithoutRelcache(rel->rd_locator, MAIN_FORKNUM,
										 block, RBM_NORMAL, NULL, true);
		ReleaseBuffer(buffer);
	}
	else if (action == 1)
	{
		ReadBuffersOperation op = {0};

		op.rel = rel;
		op.smgr = RelationGetSmgr(rel);
		op.persistence = rel->rd_rel->relpersistence;
		op.forknum = MAIN_FORKNUM;
		if (!StartReadBuffer(&op, &buffer, block, 0))
			elog(ERROR, "raw I/O fixture was already a usable cache hit");
		/* Deliberately wait only for physical I/O, then abandon the pin.
		 * Ordinary consumers must instead call WaitReadBuffers(). */
		pgaio_wref_wait(&op.io_wref);
		if (!(pg_atomic_read_u64(&GetBufferDescriptor(buffer - 1)->state) &
			  BM_CONVERSION_PENDING))
			elog(ERROR, "raw I/O did not leave conversion pending");
		ReleaseBuffer(buffer);
	}
	else if (action == 2)
	{
		Page page;

		buffer = ReadBufferExtended(rel, MAIN_FORKNUM, block, RBM_ZERO_AND_LOCK, NULL);
		page = BufferGetPage(buffer);
		if (PageGetPageLayoutVersion(page) == PG_PAGE_LAYOUT_VERSION)
			elog(ERROR, "overwrite fixture was already converted");
		START_CRIT_SECTION();
		PageInit(page, BLCKSZ, sizeof(HeapPageSpecialData));
		memset(HeapPageGetSpecial(page), 0, sizeof(HeapPageSpecialData));
		MarkBufferDirty(buffer);
		log_newpage_buffer(buffer, true);
		END_CRIT_SECTION();
		/* log_newpage_buffer uses XLogRegisterBlock, so retaining the
		 * conservative flags is allowed until the next normal read/write. */
		result = PageGetPageLayoutVersion(page) == PG_PAGE_LAYOUT_VERSION &&
			PageIsEmpty(page);
		UnlockReleaseBuffer(buffer);
	}
	else if (action == 3)
	{
		ReadBuffersOperation op = {0};
		Buffer buffers[2] = {InvalidBuffer, InvalidBuffer};
		int nblocks = 2;

		op.rel = rel;
		op.smgr = RelationGetSmgr(rel);
		op.persistence = rel->rd_rel->relpersistence;
		op.forknum = MAIN_FORKNUM;
		if (StartReadBuffers(&op, buffers, 0, &nblocks, 0))
			WaitReadBuffers(&op);
		if (nblocks != 1 || buffers[1] == InvalidBuffer)
			elog(ERROR, "read did not split before the pending forwarded buffer");
		nblocks = 1;
		if (StartReadBuffers(&op, &buffers[1], 1, &nblocks, 0))
			WaitReadBuffers(&op);
		for (int i = 0; i < 2; ++i)
		{
			if ((pg_atomic_read_u64(&GetBufferDescriptor(buffers[i] - 1)->state) &
				 BM_CONVERSION_PENDING) ||
				PageGetPageLayoutVersion(BufferGetPage(buffers[i])) != PG_PAGE_LAYOUT_VERSION)
				result = 0;
			ReleaseBuffer(buffers[i]);
		}
	}
	else
		elog(ERROR, "unknown conversion probe action");
	relation_close(rel, AccessShareLock);
	PG_RETURN_INT32(result);
}

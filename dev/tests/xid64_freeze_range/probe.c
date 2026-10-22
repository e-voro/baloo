/* Test-only counter jump in a disposable xid64 cluster. */
#include "postgres.h"

#include "access/multixact.h"
#include "fmgr.h"

PG_MODULE_MAGIC;
PG_FUNCTION_INFO_V1(test_jump_multixact);

Datum
test_jump_multixact(PG_FUNCTION_ARGS)
{
	MultiXactMember members[2];
	MultiXactId next,
			oldest;
	MultiXactOffset offset;
	Oid		oldest_db;

	members[0].xid = (TransactionId) PG_GETARG_INT64(0);
	members[0].status = MultiXactStatusForKeyShare;
	members[1].xid = (TransactionId) PG_GETARG_INT64(1);
	members[1].status = MultiXactStatusForKeyShare;
	MultiXactIdSetOldestMember();
	/* Populate the successor offset for every referenced old MultiXact. */
	(void) MultiXactIdCreateFromMembers(2, members);
	MultiXactGetCheckptMulti(false, &next, &offset, &oldest, &oldest_db);
	MultiXactSetNextMXact(UINT64CONST(2147484672), offset);
	PG_RETURN_VOID();
}

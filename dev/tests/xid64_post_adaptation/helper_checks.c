/* Appended after the actual static regression helper extracted by check.py. */
PG_FUNCTION_INFO_V1(todo_conversion_helper_checks);

Datum
todo_conversion_helper_checks(PG_FUNCTION_ARGS)
{
	Relation rel = relation_open(PG_GETARG_OID(0), AccessShareLock);
	Buffer buffer = ReadBuffer(rel, 0);
	PGAlignedBlock storage;
	Page page = storage.data;
	HeapTupleHeaderData tuple = {0};
	RelCheckValues values;
	TransactionId base = UINT64CONST(4294967796);

	LockBuffer(buffer, BUFFER_LOCK_SHARE);
	PageInit(page, BLCKSZ, sizeof(HeapPageSpecialData));
	memset(HeapPageGetSpecial(page), 0, sizeof(HeapPageSpecialData));
	HeapPageGetSpecial(page)->pd_xid_base = base;
	tuple.t_hoff = sizeof(tuple);
	tuple.t_choice.t_heap.t_xmin = 200;
	tuple.t_choice.t_heap.t_xmax = 77;
	for (int i = 0; i < 3; ++i)
		if (PageAddItem(page, &tuple, sizeof(tuple), InvalidOffsetNumber,
						false, false) == InvalidOffsetNumber)
			elog(ERROR, "cannot construct helper fixture");
	ItemIdSetRedirect(PageGetItemId(page, 2), 1);
	ItemIdSetUnused(PageGetItemId(page, 3));
	values = FillRelCheckValues(rel, buffer, page);
	if (values.ntuples != 1 || values.tcv[0].xmin != base + 200 ||
		values.tcv[0].xmax != base + 77)
		elog(ERROR, "current helper decoded line pointers or base incorrectly");
	pfree(values.tcv);

	((PageHeader) page)->pd_special = BLCKSZ;
	PageSetPageSizeAndVersion(page, BLCKSZ, PG_PAGE_LAYOUT_VERSION - 1);
	values = FillRelCheckValues(rel, buffer, page);
	if (values.ntuples != 1 || values.tcv[0].xmin != 200 || values.tcv[0].xmax != 77)
		elog(ERROR, "legacy helper decoded source XIDs incorrectly");
	pfree(values.tcv);

	PageInit(page, BLCKSZ, 0);
	tuple.t_infomask = HEAP_XMIN_FROZEN;
	HeapTupleHeaderSetDoubleXmax(&tuple, UINT64CONST(1099511627820));
	if (PageAddItem(page, &tuple, sizeof(tuple), InvalidOffsetNumber,
					false, false) == InvalidOffsetNumber)
		elog(ERROR, "cannot construct double-xmax helper fixture");
	values = FillRelCheckValues(rel, buffer, page);
	if (values.ntuples != 1 || !values.tcv[0].xmin_frozen ||
		values.tcv[0].xmin != FrozenTransactionId ||
		values.tcv[0].xmax != UINT64CONST(1099511627820))
		elog(ERROR, "double-xmax helper lost full XIDs or frozen state");
	pfree(values.tcv);
	UnlockReleaseBuffer(buffer);
	relation_close(rel, AccessShareLock);
	PG_RETURN_INT32(3);
}

# How a standby uses a conflict horizon

Prepared for Evgeny's learning TODO, 2026-10-26. This traces the current PG19
xid64 implementation. A conflict horizon is a WAL replay safety boundary;
it is not a command to advance the standby's xmin.

## From WAL to conflicting transactions

1. Primary pruning/freezing/index cleanup records a snapshot conflict horizon:
   the transaction boundary needed to decide whether old snapshots could
   depend on tuple versions or transaction status affected by the operation.
2. For heap prune records, heap_xlog_prune_freeze in
   `src/backend/access/heap/heapam_xlog.c` reads the optional horizon with
   memcpy, using sizeof(TransactionId). Here that preserves all 64 bits.
3. In Hot Standby mode, replay calls ResolveRecoveryConflictWithSnapshot in
   `src/backend/storage/ipc/standby.c` before applying the page operation.
   InvalidTransactionId means no snapshot conflict and returns immediately.
4. GetConflictingVirtualXIDs in `src/backend/storage/ipc/procarray.c` scans
   backend PGPROC entries under ProcArrayLock. It considers the affected
   database, ignores prepared entries and backends without a registered xmin,
   and selects active virtual transactions with xmin <= the horizon.
5. This test is conservative: it identifies snapshots that might depend on
   the affected history; it does not inspect every query's tuple visibility.

For example, a backend xmin of 100 is a candidate against horizon 150; an xmin
of 200 is not. All comparisons must retain the full XID, not only its low half.

## Waiting and cancellation

ResolveRecoveryConflictWithVirtualXIDs waits for each selected virtual
transaction to finish, using VirtualXactLock and increasing sleep intervals.
If it finishes normally, replay continues without cancellation.

When the configured recovery-delay budget expires, recovery signals the backend
with RECOVERY_CONFLICT_SNAPSHOT. Backend interrupt processing in
`src/backend/tcop/postgres.c` raises the appropriate recovery-conflict error;
the affected transaction/session handling depends on its state. Replay waits
until the conflicting virtual transaction is gone before proceeding.

The budget comes from max_standby_streaming_delay or max_standby_archive_delay
and WAL receipt timing. It is not a fresh full timeout for every query or
every conflicting backend. A value of -1 permits indefinite waiting. The
RecoveryConflictSnapshot wait event, pg_stat_database_conflicts and optional
log_recovery_conflict_waits messages help explain these waits/cancellations.

For catalog changes, recovery can also invalidate obsolete logical replication
slots whose catalog horizon is no longer safe. That is separate from waiting
for query snapshots.

## Relation to Hot Standby Feedback

Hot Standby Feedback sends retained horizons in the opposite direction, from
standby to primary. It can keep primary cleanup from removing versions needed
by standby snapshots, reducing these conflicts at the cost of retained dead
data. It is not the conflict horizon carried by a cleanup WAL record and does
not eliminate every type of recovery conflict.

The current xid64 feedback format uses tag H. WAL conflict horizons and the
feedback xmin/catalog_xmin values both need full-width handling, but travel
through different code paths and serve different purposes.

The agent has prepared this trace; Evgeny's reading/learning remains a user
task rather than a task marked completed on his behalf.

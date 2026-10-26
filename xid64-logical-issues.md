# Xid64 logical issues and Tantor 18 backports

Updated 2026-10-26; immediate-WAL source commit `b0d9496f94f`.
This is the current issue list for the PG19 xid64 port and
the corresponding PG18 xid64 / tt18 / Tantor 18 backport review. It supersedes
older descriptions of deferred conversion WAL. Original fixes remain in Git
history; the new conversion policy changes how some of them are needed.

These are xid64-patch issues, not a claim that vanilla PostgreSQL 18 has the
same bugs. Compare the actual target revision and the supplied
`patches/func/tt186xid64/` fixes before backporting. PG19 test results establish
the port's behavior; they do not validate an untested Tantor 18 backport.

## Conversion and durability

### 1. Conversion needs the reading backend

MultiXact member lookup needs backend transaction state and caches. An AIO
worker cannot safely perform those lookups or propagate conversion errors from
shared completion. Conversion now validates and converts a private copy in the
reading backend, under the buffer's exclusive content lock. Ordinary conversion
errors leave the shared legacy page unchanged and retryable.

Fix: `a09ce2c567d`, `bufmgr.c` and `heap_convert.c`. Keep this ownership and
error handling when backporting. Supplied 0008 already addresses the separate
global Relation-pointer / inaccessible issuer-relcache problem using by-value
metadata; it does not remove the backend-state requirement.

### 2. Immediate WAL replaces waiting for a later modification

Normal permanent-page conversion now dirties the buffer and emits a forced
`XLOG_FPI`, even with `full_page_writes`, `wal_log_hints` and checksums off.
The page LSN is installed before readiness is published. Conversion validation
and WAL record preparation happen before shared bytes are changed; dirtying,
WAL insertion, LSN update and publication are inside the critical section.
Readers retain the exclusive content lock throughout publication.

This removes these dependencies from the normal conversion path:

- Waiting for UPDATE, VACUUM or a hint write to log the format change.
- Losing an unlogged conversion on checkpoint/restart after a hint-only write
  (`42a0b1c973e` originally supplied a deferred-WAL safeguard).
- Requiring the first later modification's WAL record to carry conversion's
  full-page image, including the visibility-WAL case.

**The safeguards are not universally obsolete.** Recovery cannot insert WAL;
permanent relations deliberately skipping WAL also retain the clean-page,
deferred obligation. Their overwrite/first-write handling, forced-image
precedence and hint-durability guards remain. Unlogged pages are dirtied without
ordinary WAL and have no outstanding conversion-WAL obligation.

### 3. Read completion and conversion completion are distinct

AIO completion atomically publishes `BM_VALID`, `BM_CONVERSION_PENDING` and
`BM_CONVERSION_NEEDS_WAL` for legacy pages. It clears the I/O-in-progress state.
`BM_VALID` means successful physical input, not current-format readiness.

- `BM_CONVERSION_PENDING`: conversion has not completed. AIO sets it before
  any ordinary reader may receive the legacy page. It is not a converter-owner
  flag; the exclusive content lock serializes competing converters.
- `BM_CONVERSION_NEEDS_WAL`: outstanding format-change WAL obligation. This
  replaces the misleading name `BM_CONVERTED`; it can be set before conversion
  starts and can remain after conversion when WAL insertion is prohibited.

Normal permanent conversion clears both flags only after the full copy and
its WAL/LSN are complete. A current-version header alone cannot prove that
the rest of a memcpy has finished. Keep the atomic publication/read barriers,
normal/recent-read gates and overwrite exceptions from `12ff893c75f`.
Neither flag is stored on disk: both live in `BufferDesc.state`, initialized
to zero and cleared by buffer invalidation. Old page bytes cannot supply them.

### 4. Legacy visibility must preserve prepared full XIDs

The private converter supplies decoded source XIDs and expanded MultiXact IDs.
Visibility checks must neither decode that cache again nor write shared-buffer
hints using the private page. The InvalidBuffer mode suppresses both actions;
ordinary valid-buffer Vacuum/Horizon callers still decode under their lock.

Fixes: `1547efbb710`, `a09ce2c567d`. Supplied 0013 already provides the
double-xmax layout distinction/assertion correction; preserve that contribution
and compare the additional no-hints/cache-ownership changes separately.

### 5. Dense HOT conversion must preserve indexed roots

Discarding a dead indexed HOT root while retaining its live heap-only successor
made Index Scan miss a row found by sequential scan. Prune eligible source HOT
chains before freezing xmin, preserving chain identity and redirects to live
successors. Do not freeze active/recent tuples just to fit the destination.

Fix: `fbeca95f940`, `heap_convert.c`; cross-version test 012 covers dense live,
redirected, deleted and aborted chains plus streaming and crash recovery.
Immediate WAL now logs the rewritten roots during conversion itself.

### 6. Reads without relcache still need conversion metadata

CREATE DATABASE must carry source relkind, relfrozenxid and relminmxid by value.
Unknown legacy heap pages cannot be interpreted using missing metadata.
Converted images must also be replayable through relcache-less recovery reads.

Fixes: `e994dd04c51` and `b052fd6b675`, adapted from supplied 0014 and 0015.
Immediate conversion WAL simplifies the normal first-image requirement; retain
metadata checks, FPI overwrite handling and the exceptional deferred-WAL paths.
PG18 has its own visibility-WAL implementation; do not transplant PG19's
prune-WAL interfaces into it.

## Other runtime and upgrade corrections

All entries require comparison against the target PG18 xid64 tree. A supplied
fix already present there needs verification, not a duplicate application.

| Issue | Required correction and backport status |
| --- | --- |
| Logical apply-lock XIDs truncated to 32 bits | Preserve high bits in the lock key and its descriptions/pg_locks (`2e6c3ab42ff`). LOCKTAG and persisted two-phase lock-record sizes change: assess restart/prepared-record compatibility and test high-half contention. Supplied zzz0002 does not fix these keys. |
| Binary xid receiver requests unsupported eight-byte pq_getmsgint reads | Read two four-byte halves, preserving the existing low-half-first wire format (`f5d03ae7046`). Live unsigned-boundary/truncated-input test: `6eca8f6c039`. |
| Pruning hint changes meaning across page layouts/base shifts | Decode pd_prune_xid before changing the layout/base, then re-encode; use a conservative pruning hint if it cannot fit (`d85584a3eec`). This does not freeze tuples. |
| Freeze results do not fit the base chosen before defragmentation | Apply only selected, eligible freeze plans before repairing fragmentation or changing layout, identically in primary execution and redo (`d85584a3eec`). Preserve double-xmax layout when required by surviving ranges. |
| Normal-page replacement xmax exceeds its encoding range | Precritical validation prevents PANIC and returns a SQL error (`19da20487ca`). **Mitigation only:** automatic rebasing/layout handling remains open; VACUUM may need retry after lockers finish. |
| VACUUM age arithmetic wraps or overflows | Saturate all relevant full-XID/MultiXact cutoffs and bound integer failsafe-margin arithmetic (`0828bf07ff3`). Preserve the target version's age policy and snapshot caps. |
| TOAST raw-xmax accessor assumes ordinary heap special space | Use PageGetSpecialXidBase in the non-MultiXact branch (`5b47a85077c`). |
| Logical decoding overcounts old-tuple storage on INIT_PAGE updates | Exclude both page-base fields before deriving tuple allocation/copy length; see mini0075(decode.c). Check whether later supplied fixes already include this. |
| Upgrade rejects safe tables because of system xmin/xmax columns | Require attnum > 0 in recursive type propagation and final stored-column checks (`bdb4e4b907a`), retaining rejection of real user xid columns/arrays/composites. |
| Wrapped source MultiXacts disagree with restored horizons | Normalize SLRU/page MXIDs and each restored datminmxid/relminmxid consistently; preserve per-object horizons (`cff91ec658f`, `c04865b0327`). Supplied 0012 is a basis, not proof that wrapped normalization is complete. Source offset width and member-XID width are separate properties. |
| Post-upgrade index invalidation targets the old cluster | Use new_cluster / check_mode=false (`20fbaf54942`). Already supplied in 0012: verify target presence. |
| Auxiliary-fork conversion and checksums | Convert destination FSM/VM headers, preserve zero pages, and include the relation segment offset in checksum block numbers. Supplied 0007 covers part; compare `c04865b0327` / `9a0b1024ba0`. The --swap portion applies only where that transfer mode exists. |
| Pruning without cleanup locking zeros bytes retained by pin-only readers | Mask unused storage only in private WAL-consistency images instead of zeroing shared dead tuple storage (`a613c77b2ba`). Preserve live-data/base/line-pointer checking. Verify physical-emptiness checks for INSERT INIT_PAGE (`9eb9842a30d` and main 0008). |

Supplied fixes for source xid64 detection, SLRU filenames, nonzero-epoch CLOG
addresses and CREATE DATABASE metadata must also be retained. Source-format
and PG19-only API adaptations are not automatically additional PG18 bugs.
Upgrade-test IF EXISTS guards and checksum/filler fixtures are harness fixes,
separate from these runtime corrections.

## Backport order and open work

1. Compare supplied PG18 fixes and identify what the actual Tantor 18 revision
   already contains. Preserve the user's original patch files.
2. Backport backend ownership, private visibility and metadata contracts,
   then atomic readiness and immediate conversion WAL as a coordinated change.
   Retain exceptional-path WAL guards; rebuild core and modules together.
3. Backport independent storage, locking and upgrade fixes with their tests.
   Assess persisted formats before deploying lock-record changes.
4. Resolve normal-page freeze range handling beyond the current SQL-error
   guard. HSF mixed-format negotiation and zzz0002's variable-GID message-length
   heuristic remain open; no protocol-compatibility fix is claimed.

Already-xid64 upgrade sources, native PG19 eight-byte-offset sources, live
--swap/later auxiliary segments, live high-half apply-lock contention and MSVC
remain validation tasks. Do not infer their coverage from PG15/PG18 xid32 tests.

## Validation of immediate conversion WAL

- Fresh assertion/injection-point build, with dependency tracking and format /
  pointer-arithmetic errors enabled.
- Actual PG15.19 source: five upgrade/recovery suites pass 102 assertions.
  Test 009 checks that a read of frozen legacy tuples produces exactly one
  immediate XLOG/FPI and reaches the standby without a later tuple modification.
- Concurrent-reader probe passes 17 assertions. It pauses after the header
  copy, observes a competing reader waiting, rejects ReadRecentBuffer early
  returns, and verifies both flags and the page LSN after normal reads.
- Actual PG18.4 source: the same five suites pass 102 assertions.
- Full check-world with WAL consistency checking passes on `b0d9496f94f`
  (exit 0): core 246 tests; recovery 54 files / 755 assertions; AIO 597;
  xid64 67; subscription 595; native pg_upgrade 145. Its oldinstall-dependent
  cases skip in that run and are covered by the two separate source runs above.
- The 28-patch series replays exactly from `3421b154340` to this source tree
  across 268 paths; the new follow-up is `pg19-immediate-conversion-wal.patch`.

Build and logs: `/tmp/pg19-xid64-immediate-wal/` and
`/tmp/pg19-xid64-immediate-wal-*.log`. Logs are also appended to codex.log.

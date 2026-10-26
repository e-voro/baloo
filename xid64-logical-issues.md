# Xid64 adaptation to PostgreSQL 19 Decisions and implemented fixes

Updated 2026-10-26; immediate-WAL source commit `b0d9496f94f`.
This report covers the recorded adaptation from the first formatting patch
through the complete storage patch, later series patches, supplied PG18 fixes
and the final backend-conversion/WAL corrections. It records problems, design
decisions, implemented solutions and PG18 xid64 / tt18 / Tantor 18 backport
requirements. It supersedes older descriptions of deferred conversion WAL.
Original fixes remain in Git
history; the new conversion policy changes how some of them are needed.

Entries distinguish inherited xid64 bugs, supplied corrections and PG19 API
adaptations; they do not imply that vanilla PostgreSQL 18 has these bugs.
Compare the actual target revision and the supplied
`patches/func/tt186xid64/` fixes before backporting. PG19 test results establish
the port's behavior; they do not validate an untested Tantor 18 backport.

## Complete series overview

The first four patches were adapted and validated before the main storage
migration. The complete 0005 adaptation processed 215 mini steps. Original
patches and historical branches remain preserved; subsequent corrections are
separate patches in `patches/func/pg19xid64evoro1900/series`.

| Stage | Decision and resulting implementation |
| --- | --- |
| 0001 output formats | Widen XID diagnostics while preserving PG19's existing 64-bit offsets, checkpoint fields and SLRU callbacks. Use safe value casts and parse temporaries; do not write through incorrectly cast pointers. Source `f4c7dc9c16a`. |
| 0002 FullTransactionId | Replace epoch/short-XID access with the full value; retain native control/checkpoint fields and remove stale epoch format arguments. Source `44f020d606d`. |
| 0003 SLRU callers | Use PG19 SimpleLruRequest/SlruOpts, long names in server and destination upgrade writers, and matching test filenames. Keep old-source readers compatible. Aggregate `7e42cdce0f1`. |
| 0004 GUC infrastructure | Port 64-bit configuration storage, parsing, custom variables, rollback and serialization. Move freeze-age widening into 0005 beside its backing-storage changes. Aggregate `8ca324058af`. |
| 0005 storage | Adapt full transaction IDs, tuple caches, page bases, WAL/redo, visibility, locks, replication, catalog access, utilities and upgrades while preserving PG19 interfaces. Completed aggregate `6400ddc9891`; later fixes stay separate. |
| 0006 design documentation | Import README.XID64 (`7b5ca03ef47`); later implemented decisions in this report supersede conflicting historical design descriptions. |
| 0007 consistency checking | Replace shared dead-tuple zeroing with masking of unused bytes in private comparison images (`a613c77b2ba`). |
| 0008 empty-page INSERT | Require physical emptiness before INIT_PAGE WAL (`9eb9842a30d`). |
| 0009 initdb | Port explicit initial XID/MultiXact options; reject invalid unsigned inputs and preserve PG19's initial MultiXact offset of one (`fe80a516e7a`). |
| 0010 portable formatting | Apply portable 64-bit formats, including new PG19 diagnostics and signed base-shift deltas (`52507090d0e`). |
| 0011 worker WAL proposal | Superseded by supplied AIO changes. Do not restore worker-side conversion/WAL; immediate logging is now done in the reading backend. |
| 0012 MSVC compatibility | Rename the reserved union member to _int_64 and update generated GUC mappings without changing the public int64 GUC type (`60a08afaf2e`). |
| Follow-up fixes | Integrate supplied visibility/metadata/WAL fixes; correct ages, HOT roots, backend ownership, readiness publication and immediate conversion WAL. Details below. |

This includes API adaptations as well as bugs. A PG19 interface change is not
itself evidence of a defect in PG18. Error handling remains part of issue 1;
it is not counted again as an independent conversion fix.

## Conversion and durability

### 1. Conversion needs the reading backend

MultiXact member lookup needs backend transaction state and caches. An AIO
worker cannot safely perform those lookups or propagate conversion errors from
shared completion. Conversion now validates and converts a private copy in the
reading backend, under the buffer's exclusive content lock. Ordinary conversion
errors before shared installation leave the shared legacy page unchanged.
The pending flag remains set, so a later read can attempt conversion again.
Cancellation or a temporary failure may justify retry; malformed storage will
fail again until repaired. There is no permanent-failure cache or automatic
repair. This is the error-safety part of the original decision to move page
conversion into the reading backend.

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

## Storage, locking and upgrade issues

### 7. Logical apply-lock keys lose the high XID bits

**Problem:** remote XIDs 100 and 4294967396 produced the same 32-bit key field.
**Decision:** preserve the entire transaction identity in the lock key.
**Implemented:** add a high-half field, initialize it in every constructor,
include it in hashing/diagnostics, and reconstruct the full XID in pg_locks.
`2e6c3ab42ff`; PG19 uses locktag.h where PG18 used lock.h.

**Backport:** required if absent in both PG18 xid64 and Tantor 18. LOCKTAG and
persisted two-phase lock-record sizes change; assess old prepared records and
restart/rebuild compatibility. Supplied zzz0002 does not fix these keys.

### 8. Binary xid receiver uses an unsupported integer width

**Problem:** pq_getmsgint accepts one, two or four bytes; the patch requested
an eight-byte read for each half. **Decision:** preserve the existing wire
format while fixing the reader. **Implemented:** read four-byte low and high
halves and combine after widening. `f5d03ae7046`; live binary COPY tests in
`6eca8f6c039` include unsigned boundaries and truncated input.

**Backport:** required if absent; do not change the low-half-first wire layout.

### 9. Pruning hints change meaning after layout/base changes

**Problem:** pd_prune_xid is absolute in double-xmax layout and relative on a
normal page. Preserving its raw bits can silently change the decoded hint.
**Decision:** preserve the full hint, not its encoding. **Implemented:** decode
before conversion/base shifting, then re-encode. Use a conservative pruning
hint if it cannot fit. Empty conversion clears it. `d85584a3eec`.

**Backport:** required if absent. This requests reconsideration for pruning;
it does not freeze tuples or replace transaction/MultiXact cutoffs.

### 10. Freeze results and defragmentation use inconsistent bases

**Problem:** defragmentation/layout conversion could choose a base before a
selected freeze plan replaced xmax with an updater or new MultiXact.
**Decision:** base/layout decisions must see the selected plans' final values.
**Implemented:** execute only eligible selected plans before repairing
fragmentation/converting layout, in primary execution and redo. Retain
appropriate double-xmax layout when surviving ranges require it.
`d85584a3eec`.

**Backport:** required if absent. Do not freeze every survivor; active/recent
xmin values remain protected by normal eligibility rules.

### 11. Normal-page freeze replacement can exceed its encoding range

**Problem:** an already-normal page may not encode the replacement xmax or
MultiXact. Discovering this inside the critical section caused PANIC.
**Decision:** prevent the crash without inventing an unsafe freeze/rebase rule.
**Implemented:** validate the planned value, planned infomask and appropriate
base before entering the critical section; return SQLSTATE 54000 if it cannot
fit. Double-xmax full-width storage is exempt. `19da20487ca`.

**Backport:** the guard is required if absent. **Partial solution:** VACUUM may
fail until lockers finish. Automatic rebasing/layout handling remains open.

### 12. VACUUM age arithmetic underflows or overflows

**Problem:** subtracting ages from young full counters wrapped cutoffs;
float-to-int64 conversion of the failsafe margin overflowed at INT64_MAX.
**Decision:** preserve freeze policy while bounding arithmetic.
**Implemented:** saturate all eight relevant cutoffs at the first valid ID;
compute the 105% failsafe margin with bounded integer arithmetic. Keep PG19's
95% aggressive policy and snapshot caps. `0828bf07ff3`.

**Backport:** required where the target has these widened arithmetic paths;
preserve the PG18 policy constants rather than copying PG19 policy wholesale.

### 13. TOAST raw-xmax reads assume ordinary heap special space

**Problem:** the non-MultiXact accessor asserted the ordinary heap layout on a
valid TOAST page. **Decision:** use the helper supporting both special layouts.
**Implemented:** PageGetSpecialXidBase in HeapTupleHeaderGetRawXmax.
`5b47a85077c`, mini0140(htup_details.h).

**Backport:** required if absent; compare later supplied fixes first.

### 14. Logical decoding overcounts an old tuple on INIT_PAGE updates

**Problem:** datalen included two page-base fields when calculating old-tuple
allocation/copy length. **Decision:** separate page metadata from tuple bytes.
**Implemented:** subtract both TransactionId bases before computing tuplelen;
see mini0075(decode.c).

**Backport:** required if absent. Check whether the later supplied xid64 fixes
already contain this correction; avoid applying it twice.

### 15. Upgrade mistakes system xmin/xmax for stored user xid columns

**Problem:** recursive type checks rejected safe int/text tables because they
included system attributes. **Decision:** reject actual incompatible stored
user data. **Implemented:** require attnum > 0 in recursive propagation and
final reporting; retain rejection of xid columns, arrays and composites.
`bdb4e4b907a`, check.c.

**Backport:** required if absent; adapt the target's query structure.

### 16. Upgrade source formats and wrapped MultiXact horizons disagree

**Problem:** PG19 already has 64-bit MultiXact offsets, independently of member
XID width. Wrapped source MXIDs must also agree with restored datminmxid and
relminmxid. **Decision:** identify offset and member widths separately; preserve
each object's horizon using the same full-ID mapping as SLRU/page conversion.
**Implemented:** native source readers/rewriter and horizon normalization in
`cff91ec658f`, `0e524c4023b`, `c04865b0327`. Source CLOG addressing uses the
low 32 bits, not the full epoch-bearing XID (`38bdfc1d082`).

**Backport:** wrapped horizon normalization is required if absent. Source
xid64 detection, SLRU filename normalization, epoch handling and MultiXact
conversion overlap supplied 0005/0006/0011/0012. Compare them first. Do not
assume that PG19's eight-byte source-offset support applies unchanged to PG18.

### 17. Post-upgrade index handling targets the wrong cluster

**Problem:** post-upgrade invalidation used old_cluster with check mode true.
**Decision:** inspect/update destination indexes and generate REINDEX guidance.
**Implemented:** new_cluster with check mode false (`20fbaf54942`, check.c).

**Backport:** already supplied in 0012. Verify its presence and call sites in
PG18 xid64/Tantor 18 rather than duplicating it.

### 18. Transferred FSM/VM headers and checksums need destination conversion

**Problem:** direct swap bypassed auxiliary-page conversion; later segments
also need fork-relative checksum block numbers. **Decision:** convert the
finished destination file, preserving payload and all-zero pages.
**Implemented:** rewrite initialized FSM/VM headers to layout 5, use segment
number in checksum addresses, and replace through an exclusive temporary file
with the appropriate fsync/rename ordering. `c04865b0327`, `9a0b1024ba0`.
A failed rewrite leaves the original destination file unreplaced; this is not
whole-upgrade rollback after a destructive swap.

**Backport:** checksum/auxiliary fixes are required if absent; supplied 0007
covers part. The swap-specific change applies only to targets with that mode.

### 19. Pruning without cleanup locking must preserve retained tuple bytes

**Problem:** original 0007 zeroed dead tuple storage although another backend
could retain a pointer under a buffer pin. A reusable line pointer also does
not prove that the page is physically empty.
**Decision:** preserve shared bytes and the caller's pointer contract.
**Implemented:** mask unreferenced storage only in private WAL-consistency
images (`a613c77b2ba`); still compare live data, bases and line pointers.
Main 0008 requires physical emptiness before INSERT INIT_PAGE
(`9eb9842a30d`).

**Backport:** masking is required if the target uses shared-page zeroing.
Verify the main-series physical-emptiness fix is present. This does not permit
arbitrary tuple relocation under an ordinary exclusive lock.

## PG19 integration and infrastructure decisions

### 20. Preserve PG19 prune, freeze and visibility-map behavior

**Problem:** the PG18 patch predates PG19's on-access VM updates and prune-WAL
redesign. **Decision:** retain PG19's behavior while carrying full transaction
identities through it. **Implemented:** full tuple-XID initialization before
HOT/visibility/VM decisions; full conflict horizons in native prune WAL; toast
and fragmentation flags matching redo; native VM block references and heap
LSN handling. Do not restore the removed XLOG_HEAP2_VISIBLE record or put tuple
xmin/xmax fields in VM pages. `64b76f28c6d`, `b052fd6b675`.

**Backport:** PG19-specific integration. PG18 needs equivalent XID correctness
in its own visibility-WAL implementation, not the PG19 interfaces themselves.

### 21. Single-page freeze fallback must retain tuple addresses

**Problem:** changing only the prune signature would enable defragmentation
and violate callers' pins/pointers; PG19 also requires a pinned VM buffer.
**Decision:** retain the exclusive heap lock and no-defragmentation contract.
**Implemented:** pass PruneFreezeParams and pointer VacuumParams; supply a VM
pin and let native prune code acquire VM content locks when necessary. Keep
SET_VM disabled because outer DML callers may lack a VM pin. Add opt-in
HEAP_PAGE_PRUNE_NO_REPAIR_FRAGMENTATION and preserve it in execution/WAL.
Move heap_abort_speculative page preparation before its critical section.
`088d616a983` and subsequent main-series consistency corrections.

**Backport:** PG19 API/VM pin adaptation is specific to this port. Compare
PG18's existing no-repair fallback; retain the storage and error-safety fixes
in issues 10, 11 and 19. No blanket freezing or cleanup-lock removal is implied.

### 22. Hot Standby Feedback uses the supplied full-XID wire format

**Problem:** XID widening affects sender/receiver interpretation, including
former epoch fields. **Decision:** use the original xid64 patch's message
format, as authorized, rather than a separate epoch/short-XID reconstruction.
**Implemented:** matching full-width sender and receiver changes in
mini0082(walreceiver.c) and mini0083(walsender.c).

**Backport:** this is an adopted patch design, not a newly solved PG18 bug.
Mixed-format negotiation/protection is still open. The supplied zzz0002
BEGIN PREPARE length heuristic is not applied: variable-length GIDs make it
an unsafe format discriminator. No general mixed-xid protocol fix is claimed.

### 23. Make the 64-bit GUC stage correct and independently buildable

**Problem:** patch 0004 widened freeze-age declarations before 0005 widened
backing storage. PG19 also changed GUC/reloption structures. Several parser,
rollback and serialization cases were incorrect.
**Decision:** provide infrastructure first, then widen live settings with the
storage transition. **Implemented:**

- Move freeze-age GUC/reloption migration to 0005; provide custom int64 variables
  and --describe-config support in 0004.
- Use PG19 embedded GUC fields, anonymous reloption members and uint32 flags;
  retain ternary options and new native settings.
- Round the parsed fractional/unit value correctly; preserve exact integer
  values with trailing whitespace and check optional hint pointers for NULL.
- Restore rollback values from int64val, not intval.
- Size serialized INT64_MIN values using range comparisons, without signed
  negation overflow.

Aggregate `8ca324058af`; focused corrections `fd2483c6a65`, `139c6d72c8e`.
**Backport:** compare shared parsing/NULL-hint/rollback/serialization defects
with the actual PG18 implementation. PG19 structure changes and patch-boundary
organization are port-specific; do not classify all of them as PG18 bugs.

### 24. Preserve PG19 transaction, catalog, index and utility interfaces

**Problem:** mechanically applying old hunks could restore removed APIs,
narrow new fields or break layout-dependent consumers.
**Decision:** keep native PG19 structures and widen XID-dependent operations.
**Implemented:**

- Put TYPALIGN_XID in typalign_to_alignby beside TYPALIGN_DOUBLE, sharing
  ALIGNOF_DOUBLE; follow the refactoring out of tuple-descriptor setup.
- Preserve atomic PGPROC XIDs, prepared-process initialization and PG19
  shared-memory callbacks, lock waiters and cache-line layout.
- Initialize/read full tuple caches for batch MVCC and HeapTupleSatisfies*
  entry contracts. Keep valid-buffer Horizon decoding and private conversion
  ownership distinct; nested copies are not automatically redundant.
- Retain native full deletion/safe XIDs in indexes. GIN deletion IDs use their
  full-width storage before opaque data, not the short heap pruning hint.
- Update tuple layout-dependent JIT indexing; carry full cached catalog xmin
  into PL cache checks. PG19's shared function cache supersedes the old
  PL/Python-specific hunk. Preserve native 32-bit search tests and add 64-bit
  high-key/tail-path coverage.
- Keep dump/restore database, relation, TOAST and large-object freeze horizons
  full-width. Preserve OID widths, native reset/checkpoint fields and strict
  input validation. pg_resetwal -x supplies the full XID; keep offset one.
- Append Heap3 after native XLOG2 so existing resource-manager IDs do not move.
  Use char pointers for byte arithmetic after PG19 changed Pointer to void *.
- Preserve new PG19 SLRU callbacks, multixact truncation layout, worker activity
  diagnostics and SQL output fields; update format strings where IDs widen.
- Rename the reserved MSVC union member and generated mappings without
  changing the public GUC type. Linux validation is not an MSVC test.

**Backport:** mostly PG19-specific integration. Review equivalent full-width
paths on PG18; apply only defects present there. Formatting/casting fixes are
portable where the same pattern exists. The 0005 aggregate records these
changes; this section does not assert a new independent bug for every edit.

### 25. Tests must model the new layout without losing native coverage

**Problem:** some imported helpers changed reserved XIDs or neighboring pages;
other fixtures assumed old page capacity, SLRU names or regression tables.
**Decision:** correct test mechanics and preserve PG19's native scenarios.
**Implemented:** reserved 0/1/2 stay unchanged, tuple/page bounds and base
selection are checked, repeated writes preserve full-XID inputs, and pruning
hints survive helper rebases (`ed941fe56fb`). Guard absent tab_core_types in
old regression databases (`7b3940c7dfd`); accept already-enabled source
checksums; use the supplied combine-backup filler adjustment; retain PG19's
large TID-array case and xid64's monotonic SLRU expectations. Initdb rejects
negative/wrapped unsigned inputs and zero MultiXact offset while preserving
native initialization. Tests use capability checks for external source tools.

**Backport:** helper bugs and compatible fixture corrections if absent.
Several are already supplied, especially checksum/backup/double-xmax cases;
PG19-only scenarios should not replace PG18's own test coverage. These are
harness/utility corrections, not additional heap corruption fixes.

## PG18 xid64 and Tantor 18 backport checklist

This checklist applies to **both targets**. "Required if absent" means the
defect must be corrected wherever the affected code exists. It does not claim
that the latest target revision still lacks a fix. No actual target branch has
been backported or validated by this documentation work.

| Items | Backport action |
| --- | --- |
| 1, 4, 5, 6 | Required if absent: backend-safe conversion/visibility, correct HOT roots and by-value metadata. Compare supplied 0008/0013/0014/0015 before merging. |
| 2 | Use immediate conversion WAL with the backend-conversion design. This replaces normal-path dependence on a later hint/modification; preserve recovery/WAL-skipping safeguards. Do not backport backend WAL insertion into an AIO worker. |
| 3 | Required when adopting conversion after BM_VALID: all read gates, atomic publication and barriers must move together. This race was found in our backend-conversion design; it is not automatically a defect in a target that converts before BM_VALID. |
| 7 | Required if absent: full apply-lock keys and output. Review persistent two-phase record compatibility before deployment. |
| 8, 9, 10, 13, 14 | Required if absent: binary xid receive, pruning-hint rebasing, selected-freeze ordering, TOAST accessor and logical-decoding length fixes. |
| 11 | Required crash guard if absent; keep complete range handling open. Do not describe the SQL-error mitigation as successful VACUUM in every case. |
| 12 | Required where widened age arithmetic has the demonstrated underflow/overflow; preserve the target's freeze policy. |
| 15, 16 | Required if absent: user-column-only upgrade checks and consistent wrapped-MultiXact/horizon normalization. Retain supplied source-format/SLRU/epoch fixes. |
| 17 | Already supplied in 0012; verify destination-cluster index invalidation is present. |
| 18 | Required applicable auxiliary/checksum corrections; compare supplied 0007. Apply the swap-specific part only where that mode exists. |
| 19 | Required if the target zeros shared dead storage without cleanup locking. Verify main 0008's physical-emptiness guard is already present. |
| 20, 21, 24 | Adaptation review, not wholesale PG18 backports: preserve equivalent PG18 XID correctness using PG18's APIs. Review critical-section boundaries and byte-pointer/format defects where shared. |
| 22 | Existing wire-format design, not a new completed compatibility fix. Mixed-format protection and variable-GID parsing remain open. |
| 23 | Compare and backport shared GUC parser, optional-hint, rollback and INT64_MIN serialization defects if present. PG19 structure/API changes need no direct PG18 transplant. |
| 25 | Transfer applicable helper regressions and tests with each fix. Retain existing PG18 coverage; do not import PG19-only expected output blindly. |

**Conversion backport dependency:** take ownership/error safety, visibility and
metadata contracts first; then readiness publication and immediate WAL. Keep
first-image fallback and hint guards for exceptional paths. Rebuild core and
extensions after lock-layout or helper-symbol changes. Review HOT conversion
before testing indexed reads of dense legacy pages.

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

## Validation of earlier adaptation stages

- Formatting, FullTransactionId and the completed SLRU/GUC stages were built
  and tested before 0005. Earlier full-gate results are recorded in
  xid64-rebase-report.md; they are not substitutes for the final storage gate.
- Focused checks use actual production helpers where practical: GUC limits,
  units, rollback and serialization; lock-key hashing/decoding; all six
  supported block sizes for page conversion; 212 corruption-helper cases;
  31 source-offset/MultiXact fixtures; 28 auxiliary-file scenarios; 123 age
  arithmetic cases. Many run with UBSan. These fixtures do not constitute
  live validation of every source format or platform.
- Live fallback probes cover concurrent pins, stable tuple addresses, VM
  pinning, HOT redirects and crash redo with full-page writes on and off.
  The separate freeze-range probe verifies normal SQL error, unchanged tuple
  xmax, server availability and retry after lockers finish.
- The final build/full gate below covers the resulting combined source tree.
  Documentation changes do not change that tested tree or create new test runs.

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

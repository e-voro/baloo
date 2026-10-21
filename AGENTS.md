# Instructions for future AI instances

Read baloo/xid64-rebase-report.md for the current checkpoint and adaptation map.
Read the tail of baloo/codex.log, inspect git status in both the main repository
and baloo, and inspect branch history before changing anything. The report is
historical; verify it against the actual checkout.

## IMPORTANT: PG19 prune/VM WAL and xid64 checkpoint (2026-10-02)

**Standing review rule:** At every mini, inspect PG19-only code against the PG18
patch and trace full XIDs through tuple reads, page hints, VM decisions, WAL,
and redo. Preserve PG19 behavior, including wraparound failsafe.

**Decision:** Melanie Plageman's PG19 work is functionally connected to xid64.
On-access pruning can set VM all-visible bits (commit `b46e1e54d07`);
VACUUM logs VM changes in `XLOG_HEAP2_PRUNE_VACUUM_SCAN` (`1252a4ee286`,
`a759ced2f1e`), and `XLOG_HEAP2_VISIBLE` replay was removed (`a881cc9c7e8`).
The VM stores visibility bits, **not tuple xmin/xmax**. Heap tuples still store
short XIDs relative to the heap page's xid base; do not add xmin/xmax to VM
pages or a separate tuple-XID payload to prune WAL.

- **Read from heap page:** Reconstruct full xmin/xmax before HOT-chain checks,
  pruning hints, freeze decisions, and the `newest_live_xid` test that may set
  all-visible. Use full tuple XID accessors. The optimistic, unlocked
  `heap_page_prune_opt()` read needs `HeapPageGetPruneXidNoAssert(page,
  IsToastRelation(relation))`; locked reads/writes use `HeapPageGetPruneXid()`
  and `HeapPageSetPruneXid()` so `pd_prune_xid` stays page-relative.
- **Write to WAL:** PG19's prune record already carries a snapshot conflict
  horizon as `sizeof(TransactionId)`, selected from newest live xmin, freeze
  conflict XID, and latest removed XID. Keep that field full-width. The WAL
  record also needs toast-layout and fragmentation flags so redo reproduces
  the heap page operation; VM bits themselves need no xid64 format change.
- **Implemented in mini0034:** `pruneheap.c` reconstructs tuple XIDs for HOT
  chains, visibility bookkeeping, and removed-tuple conflict horizons;
  `vacuumlazy.c` uses full xmin for its VM visibility check. `heapam.h` and
  `heapam_xlog.h` align signatures and WAL flags with redo. Source commit
  `64b76f28c6d`; adapted mini and parent prune section in Baloo `9015fe1`;
  parent gitlink commit `5552a07075f`.
- **Later audit findings:** `HeapTupleSatisfiesVacuumHorizon()` must initialize
  full XIDs even on legacy no-special pages; its tuple helper supports them.
  The correction is folded into adapted mini0030. Future mini0168 must retain
  PG19's `PageClearPrunable()` API, still used in seven backend call sites.
- **Validation/remaining work:** mini0034 reverse-apply check and source
  `git show --check` passed. No build or recovery test yet: this partial 0005
  series lacks later xid64 helper definitions and a configured build tree.
  Continue adapting later minis, including remaining PG18-context sections of
  the aggregate patch; then build and test with WAL consistency checking.
  Do not treat the current aggregate patch as fully rebased.

## User workflow and authorization

- Follow the user's current command. Do not start the next patch without authorization.
- Latest instruction (2026-09-24) authorizes continuing and adapting patches,
  including attempting new fixes; describe every fixed case. Preserve PG19
  behavior and distinguish context repairs from functional adaptations.
  Escalate unresolved design decisions rather than applying an unsafe workaround.

- Give brief English corrections before starting the technical work, so the
  user can read them during execution. Italicize corrected whole sentences;
  bold changed words, or only the corrected letters when fixing a typo.
  Repeat English corrections and important interim explanations in the final
  answer so they remain available after commentary is collapsed.

- Log in REAL TIME to baloo/codex.log, not at the end of the operation. Stream
  command output with tee -a and append decisions/findings as they occur.
- Use set -o pipefail so tee does not conceal failures. Add set -e to dependent
  sequences when appropriate. Avoid printing secrets into the log.
- Preserve existing user changes. Do not spawn subagents unless explicitly requested.

## Git and patch conventions

- Main repo and Baloo are separate repositories (Baloo is a submodule).
- Never include Baloo gitlink changes in a source-code commit.
- Prefix separate parent commits recording patch/helper changes in Baloo with BALOO.
- Use CODEX: for the user-requested separate handoff documentation commits,
  including the parent gitlink update that records those documents.
- Save adapted patch files with commits inside Baloo; source changes belong to
  the main repository. Log/report files may be dirty: do not stage them blindly.
- Preserve original v67 series. Work under baloo/patches/func/pg19xid64evoro1900/.
- Rename the requested version prefix only; do not rename the full series unasked.
- For aggregation use the adapted mail patch with git am and its original message.
  The user additionally requested Evgeny Voropaev <evorop@gmail.com> as author,
  an Author: entry, and current author/committer dates for patch 0001. The saved
  patch mail headers currently differ; account for that if reapplying it.
- Preserve the MINISTEPS backup branch before any authorized aggregation/reset.
  Never reset or rewrite history without user authorization.
- Actual helper: source baloo/dev/devcfgli.sh. dbg_split_patch generates per-file
  mini-patches and a Bash application script; dbg_apply_patch uses git apply,
  git add and git commit. Review its staging scope and run under set -e.
- Mini numbering starts at 0000: 0000 through 0055 is 56 steps.
- Resume only unapplied mini steps. The current first patch is complete; the old
  resume script is a no-op. Do not rerun the original generated sequence.
- Update the parent patch whenever adapting minis; verify it against the correct
  base and compare resulting files with the working tree. Keep diffstat accurate.
- Git metadata for this worktree and submodule is outside writable workspace
  roots; Git mutations may require explicit tool sandbox escalation.

## Technical and test expectations

- Patch 0001 is formatting only; TransactionId is still uint32 in this checkpoint.
- PG19 MultiXactOffset is already uint64. Preserve PRIu64 offset formatting,
  current truncation layout, callback interfaces and upgrade conversion paths.
- For %llu use unsigned long long value casts. Never cast a narrow object's
  pointer to unsigned long long * for scanf. Parse into a temporary, validate,
  then assign. Preserve OID/epoch/command-ID formatting where those stay 32-bit.
- New PG19 diagnostics may need widening even if absent from the original patch.
- For full validation enable TAP, assertions and injection points, build world-bin,
  and run make check-world PG_TEST_EXTRA=wal_consistency_checking.
  This enables wal_consistency_checking=all in recovery/t/027_stream_regress.pl.
- Use -Werror=format; use MULTIXACT_DEBUG for targeted multixact logging checks.
- Socket restrictions can prevent test servers starting inside the sandbox. Request
  escalation rather than treating those errors as PostgreSQL regressions.
- Report exact tested tree and limits. The multixactfuncs.c build fix is now folded into the formatting commit;
  the tested source tree is committed. Verify history before reusing this result.
- Keep source fixes and Baloo updates in separate commits, including test-driven fixes.
- Do not claim future xid64 storage or cross-version upgrade compatibility merely
  because formatting compilation and the present check-world passed.

## Validated patch 0001 checkpoint (2026-09-23)

- PostgreSQL formatting commit: f4c7dc9c16a. Includes the final multixactfuncs.c
  cast correction found by the full build. No source fix remains uncommitted.
- Preceding separate Baloo-pointer commit: 316742b105e.
- Corrected patch stored in Baloo d4151f99160bd5803977b255b2e253ea06ec7528.
- Full world-bin build and check-world passed for this source tree, with
  PG_TEST_EXTRA=wal_consistency_checking; recovery 027 passed.
- A fresh application of the adapted patch to 3421b154340 matched all 56
  committed source files. Metadata-only documentation commits need no retest.
- MINISTEPS backup predates the final build fix; do not treat it as the final artifact.
- This file lives in baloo/AGENTS.md. Paths above are relative to the PostgreSQL
  repository root. The report is alongside it. codex.log is an untracked live log.
- Patch 0002 is aggregated at 44f020d606d; its full check-world passed.
- Patches 0003 and 0004 are aggregated via git am at 7e42cdce0f1 and
  8ca324058af. Separate preceding BALOO commits are cac3384a446 and c01491a5684.
  Baloo patch/probe revision is 5ba14d3. world-bin, focused GUC probe and full
  check-world passed; recovery 027 ran with WAL consistency checking.
  Aggregated source/tree equals pre-aggregation ead7bcc4da2 exactly.
  Regenerated mini scripts include final fixes: do not replay them here.
- Backup MINISTEPS_0003-Use-64-bit-SLRU-pages-in-callers points to 1502ac9ee0b;
  MINISTEPS_0004-Use-64-bit-GUCs points to ead7bcc4da2. Both names have prefix
  pg19beta3xid64_CODEX_. Preserve these historical branches.
- PG19 SLRU options use SimpleLruRequest/SlruOpts.long_segment_names;
  multixact members already use long names. New-cluster offsets writers must
  also use long names, while pre-v19 readers and synthetic old fixtures stay short.
- The original patch 0004 depended on 0005 for backing storage. The adapted
  0004 provides infrastructure only: freeze-age GUC/reloption migration is now
  in working 0005, alongside its backing-storage widening. Preserve this boundary.
- Working v1900-0005 is only partially adapted and NOT applied. It includes the
  migration relocation and excludes help_config support moved into 0004.
- PG19 relopt_value has an anonymous union; use int64_val, not values.int64_val.
  Use uint32 rather than removed bits32, and embedded config_generic._int64
  fields rather than casts to a standalone config_int64.
- Retain 0004 parser, rollback and INT64_MIN serialization fixes. The focused
  reproducible probe is baloo/dev/tests/xid64_guc/run.sh PREFIX. Its original
  rollback failure was fixed; check the report for coverage and limitations.

## AIO conversion checkpoint (2026-10-17)

- User explicitly authorized the design in
  `patches/func/tt186xid64/0008-Upgrade-and-fix-page-conversion-for-the-new-AIO-syst.patch`.
  Per-handle RelationExtraData replaces the shared Relation pointer; conversion
  sets BM_CONVERTED and defers WAL logging to a later modifying backend.
- mini0085(aio_callback.c), mini0164(aio.h), and mini0165(aio_internal.h) are
  superseded: skip notes replace the obsolete shared-pointer changes.
- mini0087(bufmgr.c) includes the new metadata headers and the already-applied
  adaptations of mini0166(buf_internals.h) and mini0167(bufmgr.h). Skip those
  later minis. PG19 keeps its 64-bit state and lock layout; BM_CONVERTED uses
  unused flag bit 6 and is published with UnlockBufHdrExt.
- PG19 content-lock acquisition requires a private pin. Read completion instead
  converts under the existing exclusive I/O ownership before BM_VALID; failed
  reads are excluded. Converter helper assertions allow this AIO context.
- mini0088(heap_convert.c) incorporates the supplied conversion/WAL design;
  mini0198(regress.c) is prepared for its new signature but is not yet applied.
- The user will supply the missing-relcache fix later. Keep that case and AIO
  critical-section error propagation in codex_todo.txt; do not claim them fixed.
- Applied source checkpoint is through mini0089(meson.build). Next is
  mini0090(procarray.c). Full compile/recovery testing still awaits the rest
  of 0005. Saved affected aggregate sections were applied to 8ca324058af in a
  scratch directory and matched the intended files exactly.

## IMPORTANT: full-XID apply-lock fix (2026-10-20)

- User authorized the fix after the pause before mini0092(lmgr.c). Source
  commit `2e6c3ab42ff` applies mini0092(lmgr.c), mini0093(lock.c), and the
  required mini0100(lockfuncs.c) and mini0170(locktag.h) early. Skip the latter
  two when reaching their numbers. Subsequent checkpoint is below.
- **Cause:** SET_LOCKTAG_APPLY_TRANSACTION assigned a full remote XID to uint32
  field3. XIDs 100 and 4294967396 therefore shared a lock key for the same
  database, subscription and subtype. Parallel apply uses these keys for
  stream/transaction waits; unrelated transactions could contend. This was
  inherited from the PG18 xid64 patch, not introduced by PG19.
- **Fix:** append uint32 locktag_field5 for the high XID half; field3 keeps the
  low half. Preserve database/subscription IDs, subtype, type and method.
  Every other constructor explicitly zeroes field5. LOCKTAG grows from 16 to
  20 bytes; a static assertion enforces no padding in the bytewise hash key.
  PG19 moved these definitions from lock.h to locktag.h.
- Hash tables, key copies and two-phase lock records use sizeof(LOCKTAG), so
  they include the new field. TwoPhaseLockRecord grows from 20 to 24 bytes;
  pre-fix persisted records are not compatible. Apply locks themselves are
  session locks and are not persisted at PREPARE. Validate ordinary prepared
  transaction recovery after the complete series; old-state compatibility is
  not established by this fix.
- DescribeLockTag and pg_locks reconstruct the full remote XID; pg_locks uses
  TransactionIdGetDatum instead of ObjectIdGetDatum. Also correct virtual-XID
  diagnostics and speculative-token XID/token decoding to match the original
  xid64 tag layout. Debug messages include field5; wait probes append it as
  arg6, keeping existing argument positions. Probe documentation is updated.
- Validation: dev/tests/xid64_locktags/check.py compiles actual constructors,
  extracted production hashing, descriptions and pg_locks decoding with
  fixed-width fixtures, -Werror and undefined-behavior sanitization. High-bit
  separation, all 11 constructors, 28 decoder cases, record copying and probe
  arity pass. All six aggregate sections replay on 8ca324058af and match the
  source exactly; four adapted minis pass reverse checks. These are focused
  checks, not live backend contention/recovery tests. Full build still awaits
  later 0005 typedefs and PGPROC definitions.
- Backport this fix to pg18xid64 and Tantor 18 as requested; see codex_todo.txt.
  zzz0002-Logical-replication-support.patch does not fix lock keys. Its separate
  BEGIN PREPARE length heuristic remains unapplied and needs protocol review.

## IMPORTANT: completed page-conversion fixes and freeze-plan ordering (2026-10-20)

- Applied mini0094(predicate.c), source `99282376e6c`: preserve PG19 SLRU
  callbacks, widen the new error diagnostic and the existing half-range test.
  Applied mini0095(proc.c), source `82f96a6a762`: initialize XID atomics for
  every PGPROC, including prepared-transaction dummy entries; preserve PG19
  shared-memory callbacks. Baloo `cb4fdac`, parent `019ebcf3d18`.
- Saved minis reverse-apply; their aggregate sections replay on `8ca324058af`
  and match source. Predicate comparator assertions pass with the forthcoming
  xid64 comparator at six block sizes under UBSan. Full build remains deferred.
- User authorized the fixes after reviewing the findings. Source `d85584a3eec`
  applies mini0096(bufpage.c) and mini0168(bufpage.h) early, and updates
  mini0028(heapam.c), mini0031(heapam_xlog.c), and mini0034(pruneheap.c).
  Saved patches/tests: Baloo `ae6b71a`, parent `0999d101da0`.
  **Skip mini0168(bufpage.h) later. Subsequent checkpoint is below.**
- **Pruning hint:** double-xmax pages store pd_prune_xid directly; normal xid64
  pages interpret it relative to the page base. Copying raw 1000 with new base
  997 incorrectly yielded 1997. Conversion now reads the full hint and
  re-encodes it after installing the base; ordinary base shifts do likewise.
  If the hint cannot fit, FrozenTransactionId requests conservative
  reconsideration of pruning. This changes only the hint, not tuple freeze
  flags. Empty-page conversion clears the hint. Tuple bases remain independent
  of unlogged hints, which can differ between primary and standby.
- **Freeze-plan execution order:** previously prune/compact, then execute
  selected freeze plans; now execute selected freeze plans, then prune/compact.
  Both primary pruneheap.c and heapam_xlog.c redo use this order. Conversion
  therefore chooses bases from the resulting xmax values, including an updater
  XID or replacement MultiXact installed by a plan. If the resulting ranges do
  not fit, compaction retains the double-xmax format. This fixes the conversion
  case where base 0 was chosen from existing MultiXacts before a plan installed
  updater XID 4294967396, exceeding the short-XID limit and reaching PANIC.
- **Surviving pruning does not make a tuple eligible for freezing.**
  heap_prepare_freeze_tuple() still determines permitted changes from existing
  visibility/cutoff rules. Only prepared entries in prstate.frozen are executed,
  using prstate.nfrozen, and only when do_freeze is true. Their line pointers
  survive pruning. The change does not force freezing of every surviving tuple
  or make a page all-frozen; existing VM eligibility checks still apply.
- **Double-xmax nuance:** tuple xmin is already frozen, but xmax may still hold
  an XID or MultiXact needed for visibility. Such a tuple is not necessarily
  totally frozen. A permitted freeze plan can simplify its MultiXact while
  retaining the updater XID; executing a plan need not freeze every tuple field.
- Validation: dev/tests/xid64_page_conversion/check.py exercises actual page
  helpers and extracted conversion/freeze/base-shift code with fixed-width
  fixtures. Hint boundaries, heap/TOAST conversion, differing hints, high-XID
  freeze results and base shifts pass at six block sizes under UBSan. Five
  changed aggregate sections replay on `8ca324058af` and match source; adapted
  mini sections reverse-check. The conversion scratch page is aligned and
  zero-initialized. Full backend/WAL consistency testing remains pending until
  the complete series builds; these tests do not establish runtime recovery.
- Backport the pruning-hint fix to Tantor 18 as requested. Keep the separate
  audit of replacement xmax ranges on already-normal pages in codex_todo.txt;
  changing conversion order does not establish that those paths are correct.

## IMPORTANT: ADT checkpoint and binary xid receive bug (2026-10-20)

- Applied mini0097(arrayfuncs.c), `a296d743a35`: use TYPALIGN_XID for XID
  arrays. PG19 Datum is always uint64, so retain elmbyval=true and omit the
  original patch's obsolete 32-bit-Datum branch. PG19 numeric alignment
  helpers already map TYPALIGN_XID through typalign_to_alignby().
- Applied mini0098(enum.c), `96b9c8a83f8`: read cached full xmin;
  mini0099(jsonfuncs.c), `31fd3a7b0f8`: initialize both composite wrappers;
  mini0101(pgstatfuncs.c), `d06bf35df8c`: include access/xact.h;
  mini0102(rowtypes.c), `15bb0db3afa`: initialize all 12 composite wrappers.
  PG19-only JSON, statistics, allocation and record-hashing changes were
  reviewed and preserved. Syscache XID-copy ownership remains in the final
  call-chain audit; mini0105(catcache.c) is applied in the checkpoint below.
- Skipped already-applied mini0100(lockfuncs.c); its reverse check passed.
  Saved five minis and refreshed aggregate in Baloo `9feea4d`, parent
  `71d68115043`. Their aggregate sections replay on `8ca324058af` and match
  source exactly; mini reverse and source whitespace checks pass. No full
  build/runtime claim: remaining 0005 headers/typedefs are still required.
- **mini0103(xid.c): user authorized the binary receiver fix after review;
  applied in source `f5d03ae7046`.**
  Its xidrecv() calls pq_getmsgint(buf, sizeof(TransactionId)) twice. After
  widening TransactionId, each requests 8 bytes, but pq_getmsgint() accepts
  only 1, 2 or 4 and raises "unsupported integer size 8". This defect exists
  in the original PG18 xid64 patch; PG19's xid.c changes are just copyright
  and output-format cleanup. The focused fixture reproduces the original
  failure; no live backend binary-input test has been run.
- **Implemented correction:** read sizeof(lo) and sizeof(hi), both
  uint32, preserving the sender's low-half-first, high-half-second format.
  Each half is in network byte order. For 0x0102030405060708 the patch sends
  05 06 07 08 01 02 03 04; pq_getmsgint64() would change its interpretation.
  This concerns SQL xid binary I/O, separate from Hot Standby Feedback.
  The sender already writes each uint32 half using its own four-byte size.
  Only the receiver's size arguments need correction; the first old read
  fails immediately, even when the input contains the correct eight bytes.

  Before (original xid64 patch; TransactionId is eight bytes):

  ```c
  uint32 lo, hi;
  lo = (uint32) pq_getmsgint(buf, sizeof(TransactionId)); /* unsupported: 8 */
  hi = (uint32) pq_getmsgint(buf, sizeof(TransactionId)); /* unsupported: 8 */
  PG_RETURN_TRANSACTIONID((uint64) lo + ((uint64) hi << 32));
  ```

  After (matches xidsend's four-byte low half, then four-byte high half):

  ```c
  uint32 lo, hi;
  lo = (uint32) pq_getmsgint(buf, sizeof(lo)); /* 4 */
  hi = (uint32) pq_getmsgint(buf, sizeof(hi)); /* 4 */
  PG_RETURN_TRANSACTIONID((uint64) lo + ((uint64) hi << 32));
  ```

- Validation: `dev/tests/xid64_binary_io/check.py` compiles actual extracted
  xidrecv/xidsend and pqformat routines with fixed-width/backend fixtures and
  UBSan. Eleven round trips (including bit 63 and UINT64_MAX), independent
  golden wire bytes, all input lengths 0..7 and the original failing reader
  pass. Allocation, Datum/bytea and error handling use fixtures; run binary
  xid COPY in a backend after the full series builds. Git metadata permission
  prompts are unrelated to this defect or its correction.

## Continuation checkpoint through mini0114(snapmgr.c) (2026-10-20)

- Applied mini0104(xid8funcs.c), `aa71db51c77`: full-XID snapshots/CLOG checks;
  mini0105(catcache.c), `26282a6291f`: copy cached full XIDs while preserving
  PG19 MemoryContextAlloc/MAXALIGN allocation and detoast lifetime;
  mini0106(funccache.c), `db15bc4acb6`, mini0107(relcache.c), `c70b5cb226d`,
  and mini0108(fmgr.c), `4492e7112ea`: full xmin cache identity/reload.
  Preserve PG19 argument-count validation, early parameter-ACL caches,
  TupleDescFinalize, AM lifetime and publication-exclusion behavior.
- mini0109(guc_parameters.dat, gen_guc_tables.pl), `0fbfcbf35fb`, registers
  eight age GUCs as int64 and fixes PG19's required-field validator to accept
  int64 with min/max. The earlier 0004 adapted emission but missed validation;
  this became visible when 0005 registered built-in int64 GUCs. Reproduced
  the generator error, then verified all eight PGC_INT64 entries are emitted.
  Keep existing boot values and PG19 failsafe limits/behavior.
- mini0110(pg_controldata.c), `9b74e14998e`: nextXid accessor at PG19 output
  column 7, preserving logicalDecodingEnabled and all 19 columns.
  **Skip mini0111(postgresql.conf.sample):** its sole change documented a
  10000000000 default, but the original and adapted GUC boot value is
  200000000. Keep the sample accurate; no runtime default was changed.
  Skip note saved; sample section removed from the adapted aggregate.
- mini0112(tuplesortvariants.c), `8a9d5f0830d`: preserve full xmin/xmax across
  CLUSTER tape writes/reads and update the field-preservation comment;
  mini0113(combocid.c), `97c369d3249`: full-XID tuple access;
  mini0114(snapmgr.c), `920d5a7d16b`: xmin atomics, 64-bit snapshot search and
  exported local-XID filenames. Preserve PG19 GIN comparator behavior,
  snapshot invalidation injection point, zeroed serialization and typed
  restore API. Snapshot array sizing already uses sizeof(TransactionId).
- Saved patches/probe: Baloo `300f228`, parent `44c2ea8be36`. All eleven saved
  minis reverse-check; twelve aggregate sections replay on `8ca324058af`
  and match source exactly. Binary I/O fixture/UBSan and GUC generation pass.
  Full backend, binary COPY and recovery validation remain deferred until
  the remaining 0005 declarations/typedefs are applied.

## IMPORTANT: completed mini0115(004_verify_heapam.pl) helper fixes

- New logic topic under the user's stop rule: the original patch's corruption
  test helpers mishandle reserved XIDs and page selection. PG19 changes to
  this test are copyright only; these defects are inherited from the patch.
- `read_tuple()` adds the page base unconditionally. With base 1000, raw
  xmin=2/xmax=0 becomes 1002/1000; production ShortTransactionIdToNormal()
  preserves values below FirstNormalTransactionId. `fixup_page()` likewise
  changes reserved 2/0 to 102/100 when shifting the base down by 100.
- Its filter `off < page_start && off > page_end` can never be true. A
  synthetic two-page file showed fixup_page(page 0) also changing page 1's
  tuple from raw xmin/xmax 10/20 to 110/120. The existing test passes only
  page-0 offsets, so this particular selection defect is latent there.
- User authorized fixing the test. Applied mini0115(004_verify_heapam.pl) in
  source `ed941fe56fb`; saved patch/probe in Baloo `4cd114e`, parent
  `28e8a9b4534`. Reserved 0/1/2 remain unchanged during decoding, encoding
  and rebasing. Normal xmin/xmax use the ordinary base; MultiXact xmax uses
  the MultiXact base. The page filter now uses OR with an exclusive upper
  bound; tuples crossing into special data or another page are rejected.
- Preserve pd_prune_xid's full value when shifting the ordinary base. Keep
  reserved hints unchanged; use FrozenTransactionId for conservative retry
  when an exact hint exceeds MaxShortTransactionId, matching the earlier
  backend fix. Normal tuple rebases that cannot fit are rejected. Writing
  copies the input hash so repeated writes retain the caller's full XIDs.
- Validation: `dev/tests/xid64_amcheck_helpers/check.py` extracts the actual
  Perl helpers and exercises synthetic three-page files: 212 assertions
  cover reserved IDs, XIDs above 32 bits, MultiXacts, unchanged neighbouring
  pages and boundary rejection, exact repeated-write round trips, hints and
  same-base no-ops. Perl syntax check passes. Mini reverse check and aggregate
  replay on `8ca324058af` match source exactly. Full pg_amcheck TAP execution
  remains pending until the full series builds; this is helper validation,
  not a live corruption-diagnostic run. Subsequent checkpoint is below.

## Frontend checkpoint through mini0121(Makefile) (2026-10-20)

- Applied mini0116(pg_controldata.c), `6ac4b41fb0b`: rename the full-XID
  accessor; retain PG19 logical-decoding/checksum fields and native uint64
  MultiXactOffset output. mini0117(pg_dump.c), `3b8a0af33bd`, and
  mini0118(pg_dump.h), `23fab87ce02`: keep database/table/TOAST/large-object
  freeze horizons full-width from SQL text through storage and dump output.
  OIDs remain uint32. Reviewed PG19 statistics/extended-statistics export,
  property graphs, publication exclusions, subscription server/timeout,
  large-object metadata transfer and sequence changes; no additional XID
  reads or horizon narrowing found in those additions.
- mini0119(pg_resetwal.c), `fe2ba8baa9d`: adapt to PG19's given/value option
  state and existing strict uint64 parser. Remove the separate epoch option,
  state, output and help; -x sets the complete XID. Widen XID/MultiXact-ID
  inputs, including both commit-timestamp components. Keep strict uint32 OID
  parsing, native uint64 nonzero offsets and explicit zero commit-ts resets.
  Preserve PG19 reset/default behavior, including nextMultiOffset=1.
- mini0120(001_basic.pl), `0991bc61e70`: retain PG19 invalid-input coverage;
  move XID overflow to UINT64_MAX+1, test a 33-bit XID, the OID boundary and
  negative newest commit-ts XID; remove epoch cases and use the forthcoming
  72-byte/eight-member group layout. Offset entries were already eight bytes.
  mini0121(Makefile), `77c7610ca0a`: add forthcoming segresize.o; retain PG19
  native multixact readers/rewriter, slru_io and extension-test dependencies.
- Saved six minis and probe in Baloo `03e7c80`, parent `65365793f36`.
  All six reverse-check; aggregate sections replay on `8ca324058af` and match
  source exactly. `dev/tests/xid64_resetwal/check.py` compiles actual extracted
  option handlers, strict parsers and control assignments with fixed-width
  scaffolding: 61 cases pass under UBSan. Perl syntax passes. No real control
  file is touched by this probe; utility/TAP/full-build tests remain pending
  until remaining 0005 headers/definitions, including segresize.c, are applied.

## Upgrade checkpoint before mini0126(pg_upgrade.c) (superseded below)

- **The supplied PG18 patch 0012 already fixes the index bug.** Its check.c
  hunk changes post-upgrade invalidation to **(&new_cluster, false)**. Ported
  into mini0122(check.c), source `20fbaf54942`; pre-upgrade checks remain
  **(&old_cluster, true)**. The old server is stopped after restore; the new
  server must receive pg_index.indisvalid=false updates and REINDEX scripts.
  This defect came from the original xid64 patch, not vanilla PostgreSQL.
- **"needed for fix rebase into Tantor 18":** verify the destination branch
  includes supplied 0012; do not backport the same index correction twice.
  The full patch also fixes MultiXact horizon preservation, still to be
  incorporated when mini0126(pg_upgrade.c) is adapted.
- Ported supplied patch 0005's format detection: get_db_infos() reads the
  built-in pg_catalog.xid's typlen, validated as 4 or 8. Detection uses that
  width for PG15–17 and PG19, preserving the supplied PG18 catalog-prefix
  rule. No placeholder XID_FORMATCHANGE_CAT_VER is added. Helpers live in
  version.c beside the checks; PG19 protocol negotiation is preserved.
- Applied mini0127(pg_upgrade.h) early, `749ee9e8477`, and
  mini0131(version.c) plus supporting info.c, `9a7fe213315`. Preserve PG19's
  existing uint64 MultiXactOffset, catalog threshold and native rewrite API.
  **Skip replaying mini0127(pg_upgrade.h) and mini0131(version.c).** Their
  saved patches remain part of 0005; info.c has a supplemental saved patch
  `pg19-upgrade-xid-format-info.patch` in the same mini directory.
- mini0122(check.c) also uses the existing manual datatype-check hook:
  original threshold=1100 wrongly skipped ordinary PG18/19 xid columns.
  Remove the inaccurate claim that vanilla PG18 changed xid size. Replace
  the previously discussed wraparound-query modulus 4294967295 with
  **4294967296**, and skip this raw-32-bit horizon query for xid64 sources.
  Preserve PG19 encoding/global-name, btree_gist and logical-slot checks.
- mini0123(controldata.c), `b0edc882a7c`: retain full checkpoint XIDs from
  decimal and epoch:xid / epoch/xid output; shift a uint64 value before OR.
  Preserve native uint64 offsets and checksum-in-progress rejection.
  mini0124(file.c), `c882783856d`: incorporate supplied 0007's all-zero
  FSM/VM page handling; leave zero pages untouched, reject nonzero corrupt
  uninitialized pages, update initialized headers before checksums. Its
  relfilenumber.c conversion guard awaits mini0128(relfilenumber.c).
  mini0125(meson.build), `82bde87a9e1`: add segresize.c while preserving
  PG19 multixact readers/rewriter, slru_io and tests.
- Validation: `dev/tests/xid64_upgrade_indexes/check.py` compiles actual
  format/index functions with SQL/connection fixtures: 11 supported scenarios,
  3 rejected formats, actual REINDEX file contents and invalidation queries.
  `dev/tests/xid64_upgrade_pages/check.py` tests actual parser/rewrite functions:
  15 decimal/epoch XID cases, three-page zero/initialized/zero files with
  checksums on/off, 5 corrupt/truncated-file rejections. Both use UBSan;
  page checksums are stubbed to check invocation/order, not the checksum
  algorithm. No backend, live pg_upgrade, TAP or recovery run is claimed.
  Seven changed aggregate sections replay on `8ca324058af` and match source;
  all seven saved patches reverse-check. Saved artifacts/probes in Baloo
  `0553668`, parent `db7f8b9ae19`. Aggregate remains partly adapted.

### NEW LOGIC DECISION: PG19 MultiXact conversion

**At this checkpoint mini0126(pg_upgrade.c) was paused; it is applied below.**
XID width alone does not identify a source MultiXact layout:

| Source | Member XID bytes | Offset bytes |
| --- | ---: | ---: |
| Vanilla PG18 | 4 | 4 |
| Vanilla PG19 | 4 | 8 |
| xid64 target | 8 | 8 |

- The PG18 converter in mini0129(segresize.c) uses uint32 oldbuf entries and
  four-byte offset indexing. On this host an eight-byte offset 4294967301
  would be read as two entries 5 and 1. It also assumes short source segment
  names, unlike PG19's long MultiXact segment names. This is a source/layout
  finding; no cluster files were changed to demonstrate it.
- Keeping PG19's native "offset format unchanged => copy" branch also fails:
  member XIDs still need conversion to eight bytes, including group layout.
  Its pre-v19 native reader cannot read a PG19 offsets file as-is either.
- Proposed adaptation: select readers by actual source XID/offset format;
  retain PG19's uint64 offsets and long names, convert member XIDs/groups,
  and treat 32-bit MultiXact-ID wrap independently from offset width. Keep
  native old-version semantics and supplied 0012's restored-horizon fix.
  This requires a substantive conversion change; discuss before applying.
- After approval, test all three formats, wrapped MXIDs, nonzero epochs,
  offsets above UINT32_MAX, SLRU boundaries/names, counters and catalog
  horizons; then live cross-version upgrades after the series builds.

## Prepared solution: distinguish source MultiXact offset width (2026-10-20)

- Added `cluster_has_64bit_multixact_offsets()` in version.c, declared in
  pg_upgrade.h, source `85d42c458b0`. Recognized xid64 sources return true: the supplied PG18
  patch widens MultiXactOffset too. Otherwise use PG19's existing catalog
  boundary **MULTIXACTOFFSET_FORMATCHANGE_CAT_VER = 202512091**, introduced
  by upstream `bd8d9c9bdfa`. Thus pre-v19 xid64 and vanilla PG19 both have
  eight-byte offsets, while their member XID widths differ. A small current
  nextOffset value or a major-version comparison cannot identify the layout.
- Keep two decisions in mini0126(pg_upgrade.c):
  `old_xid64 = cluster_is_xid64(&old_cluster)` and
  `old_offsets64 = cluster_has_64bit_multixact_offsets(&old_cluster)`.
  Already-xid64 sources may copy after verifying the supported member layout
  and normalizing legacy segment names. Every xid32 source requires member
  conversion; old_offsets64 selects its offset reader. Retain the special
  pre-9.3 initialization path, which discards locking-only legacy multis.
- Recommended implementation: extend the native PG19 reader/rewriter to
  accept the source offset format, then use its existing target-layout writer.
  This retains PG19's invalid-entry handling and selection of the updater
  (or one locker), rather than replacing those semantics with the original
  segresize.c bulk converter. Native writer already uses target member-group
  definitions and writes the final next-MultiXact offset entry.
- Source reader requirements:
  - Use explicit uint32 for source MXIDs/member XIDs and four flag bytes per
    four source members (**20-byte groups**). The current v18 reader uses
    sizeof(TransactionId) and TransactionId pointers; those become wrong
    when the target typedef widens. Target writer uses eight-byte XIDs and
    eight flag bytes per eight members (**72-byte groups**).
  - Store decoded offsets in uint64; decode four-byte or eight-byte entries
    according to old_offsets64. Select the corresponding entries-per-page.
    Use short source names for the legacy offset layout and native PG19
    **15-digit** names for its 64-bit offset layout. Supported older xid64
    sources may need **12-to-15-digit** copy/rename handling from supplied0006.
  - Preserve legacy uint32 offset wrap/zero-slot rules only for four-byte
    sources. For eight-byte sources, offsets are monotonic; reject reversed
    or oversized member ranges before narrowing their length. MXID wrap is
    independent: advance raw source uint32 MXIDs and map them consistently
    to full destination IDs; do not rely on the widened target typedef to wrap.
  - Keep existing zero/invalid-entry checks and multiple-updater rejection.
    Match converted control counters to the output and preserve restored
    horizons using supplied0012. Relminmxid/page-conversion mapping must agree
    with the SLRU ID mapping, including a wrapped source range.
- Scope at preparation: only the discriminator was implemented; the
  subsequent integration is recorded below. No upgrade compatibility is
  claimed until integration and cross-version tests pass.
- Validation: the existing actual-function/UBSan probe now adds 12 offset-format
  cases: PG15–18 vanilla/xid64, PG19 before/at catalog boundary, beta3 vanilla
  and xid64. The earlier 11 index scenarios and 3 rejection cases still pass.
  These checks validate classification, not SLRU conversion or live upgrades.

## IMPORTANT: MultiXact integration applied; stop before mini0128(relfilenumber.c)

- User authorized applying the prepared discriminator/reader solution.
  mini0126(pg_upgrade.c), **`cff91ec658f`**, now converts every xid32 source;
  source offset width chooses its reader. Already-xid64 sources copy their
  SLRUs; legacy 12-digit names are normalized to native 15-digit names after
  copying, following supplied0006. Preserve PG19 locale/char-signedness,
  logical-slot and conflict-detection-slot upgrade paths.
- Native reader/rewriter and API adaptation: **`0e524c4023b`**. Source MXIDs
  and member XIDs are explicit uint32; source member groups stay 20 bytes.
  Decode four-/eight-byte offsets independently and use short/native long
  source names. Legacy offsets wrap explicitly; uint64 ranges are monotonic
  and checked before narrowing. Native invalid-entry, zero-slot and
  multiple-updater handling is retained. Native target writer uses 72-byte
  groups and writes the final next-MXID offset entry.
- Source MXID iteration is uint32 even with a uint64 target typedef. Wrapped
  source 1 follows UINT32_MAX as destination 2^32. Return the destination
  next-MXID and next-offset counters together; keep original source control
  values intact and update new_cluster's in-memory counters after conversion.
  Preserve the pre-9.3 empty-MultiXact initialization path.
- Ported supplied0012 heap-conversion fixes, **`c04865b0327`**, folded into
  mini0088(heap_convert.c): expand source MXIDs before visibility checks,
  separate source and destination page bases and reserve relative values
  below 3. Its per-object horizon-preservation fix is included in
  mini0126(pg_upgrade.c); XID resets do not overwrite restored MXID cutoffs.
- Additional consistency requirement for a wrapped source range: normalize
  each restored positive datminmxid/relminmxid below the source oldest MXID
  by adding 4294967295. This preserves each cutoff and matches the SLRU/page
  ID mapping. Already-expanded initdb horizons remain unchanged. Example:
  source oldest=4294967294, relation horizon=1 and tuple MXID=1 map to full
  horizon/MXID=4294967296, the SLRU's destination ID. Preserving raw horizon=1
  would make page conversion look up destination ID 1 instead. This is an
  additional wrapped-range correction beyond supplied0012; review it for
  Tantor 18 backport and test with live upgrades after the series builds.
- mini0129(segresize.c) applied early, **`38bdfc1d082`**: use native SLRU I/O
  for CLOG only, preserving raw uint32 status addresses and stripping the
  control XID's epoch (supplied0011). Read short source names, write native
  long names. The original PG18 MultiXact bulk converters are superseded;
  their prototypes are removed. **Skip mini0127(pg_upgrade.h),
  mini0129(segresize.c) and mini0131(version.c) when reached in sequence.**
- Saved native reader/rewriter sections in supplemental
  `pg19-native-multixact-upgrade.patch`; refreshed minis0088/0126/0127/0129
  and the aggregate. All five saved patches reverse-check; seven aggregate
  sections replay on `8ca324058af` and match committed source exactly.
  Saved artifacts/probe in Baloo `71f7124`, parent `fc6891a011e`.
- Validation: `dev/tests/xid64_multixact_upgrade/check.py` compiles actual
  reader, rewriter, native SLRU I/O, CLOG converter and selected upgrade
  functions with uint64 target XIDs, warnings as errors and UBSan. **31 cases
  pass**, including real synthetic SLRU files, offsets above 2^32, raw MXID
  wrap and zero-next checkpoints, legacy offset wrap, invalid entries,
  source/target page boundaries (1000 target members), nonzero CLOG epochs,
  backend source-ID mapping, dispatch, copied-name normalization and horizon
  SQL/control flow. SQL/pg_resetwal/copy commands use fixtures; no live SQL,
  server upgrade, TAP or recovery validation is claimed. Full build remains
  deferred until later 0005 declarations are applied.

### Historical review: --swap bypasses FSM/VM conversion (fixed below)

**This was the stop before mini0128(relfilenumber.c); implementation follows.**

- transfer_single_new_db() takes the --swap branch, calls do_swap() and
  returns before the original mini's update_version/FSM/VM rewrite loop.
  Thus adding the normal mini0128(relfilenumber.c) hunks leaves swapped
  xid32 FSM/VM files with old page versions. This branch also existed in the
  PG18 base; it is not introduced by PG19 context changes.
- The current buffer_readv_complete_one() sees an initialized old-version
  page, then raises **invalid fork type** for every non-MAIN_FORKNUM. FSM/VM
  cannot fall back to heap tuple conversion. This is confirmed by source
  flow; no live --swap failure was run at this partial-build checkpoint.
- Supplied0007 fixes zero pages and the ordinary conversion guard, but not
  the early --swap return; no swap-path correction was found in supplied
  fixes. Proposed fix: after do_swap(), rewrite only destination FSM/VM
  forks for xid32-to-xid64 upgrades, before starting the new server. Preserve
  all-zero pages, checksum/block numbering, tablespaces and fork segments;
  use separate temporary output and replace only after a successful rewrite.
  Do not disable --swap or send these forks to the heap converter.
- Discuss this new adaptation before applying mini0128(relfilenumber.c).
  Validate --swap with initialized/zero FSM/VM pages and checksums, plus
  copy/link modes and already-xid64 sources. Audit/backport for Tantor 18.

## IMPORTANT: swapped FSM/VM header rewrite implemented (2026-10-21)

- User approved the destination-side rewrite. Applied mini0128(relfilenumber.c),
  source **`9a0b1024ba0`**, including file.c/pg_upgrade.h API support.
  swap_catalog_files() now rewrites mapped user FSM/VM files after directory
  relocation and catalog replacement, before the existing directory fsyncs.
  Guard both swap and ordinary paths with **xid32 source -> xid64 target**,
  incorporating supplied0007's width guard. Already-xid64 sources skip this.
- Process only maps matching the destination database/tablespace being moved;
  handle every present fork segment, preserve empty files and all-zero pages,
  and leave heap files/catalog replacement logic intact. This retains native
  serial and per-tablespace transfer entry points and bulk directory renames.
- Write each replacement to an exclusive `.pg_upgrade` temporary file; verify
  the complete rewrite before installation. If synchronization is enabled,
  fsync that temporary file **before** renaming it over the destination fork.
  Native directory/parent fsyncs follow the replacements; existing catalog
  sync queue stays unchanged. --no-sync skips the new file fsyncs, retaining
  the existing unconditional swap directory synchronization behavior.
- Initialized auxiliary pages get layout version 5 without changing payload.
  Recompute enabled checksums after the version change. Added a first_block
  argument to updateSegmentPagesVersion(): segment N starts at
  N * controldata.largesz, not block zero. This also corrects checksums in
  ordinary copy/link conversion of later FSM/VM segments. Explicitly include
  storage/block.h in the public frontend header and check output close errors.
- Failure during conversion, output creation or fsync leaves that original
  destination file unreplaced. A failed destructive swap still requires
  reinitializing the new cluster; no whole-upgrade rollback is claimed.
  PostgreSQL's rename wrapper supports replacement on Windows; validation
  here ran on Linux, not Windows.
- `dev/tests/xid64_swap_aux/check.py`: **28 filesystem scenarios pass** with
  warnings as errors and UBSan. Uses actual native prepare/swap/catalog,
  auxiliary-rewrite, ordinary transfer and sync-queue functions, actual page
  helpers and **PostgreSQL's checksum implementation**. Exercises initialized,
  zero and empty segments, segment-1 logical checksums, default/external
  tablespaces, serial/partitioned calls, copy/link, --no-sync, already-xid64
  no-op and corrupt/truncated/existing-output/fsync failures. Real rename,
  fsync, file and inode checks verify ordering and heap-file preservation.
  Partitioned calls are sequential fixtures, not concurrent worker execution.
  Clone/copy_file_range, old VM payload conversion and live server upgrades
  are not exercised by this probe.
- Existing upgrade-pages/parser fixture still passes (15 XID parse cases,
  page/checksum-call checks and 5 invalid-file rejections); its older checksum
  stub is unchanged. The new swap probe uses actual checksums.
- Continued with mini0130(002_pg_upgrade.pl), **`d961467957b`**: retain original
  relfrozenxid/relminmxid assertions, use a unique public test relation and
  regclass-qualified lookup. Preserve PG19 wal_level=replica, structured
  regression invocation and all existing upgrade modes. Perl syntax passes;
  full pg_upgrade TAP remains pending. Reviewed PG19-only changes in these
  target files; no additional tuple XID/page/WAL conversion was needed.
- Refreshed minis0124(file.c), 0127(pg_upgrade.h), 0128(relfilenumber.c),
  0130(002_pg_upgrade.pl) and aggregate. All four minis reverse-check; all
  four aggregate sections replay on `8ca324058af` and match source exactly.
  Saved patches/probes in Baloo `5a62bab`, parent `ad392cc9fd3`.
- **Next unapplied: mini0132(003_corruption.pl).** mini0129(segresize.c) and
  mini0131(version.c) are already applied; do not replay. The initdb options
  used by mini0132(003_corruption.pl) come from later series patch 0009 and
  are not available at this partial checkpoint; preserve PG19's nonzero
  MultiXact-offset initialization when adapting them.
- Backport the swap FSM/VM rewrite and logical segment checksum correction
  to pg18xid64/Tantor 18 after comparing supplied fixes. No swap-path fix was
  found in those supplied patches. Live --swap/copy/link and cross-version
  validation, including checksums and actual parallel jobs, remains required
  after the full series builds.


## IMPORTANT: through mini0139(htup.h); pause before mini0140(htup_details.h)

- Applied mini0132(003_corruption.pl), **`5ca5ee85faa`**: retain PG19 tar
  portability, scenario gating and archived-WAL parsing. Initialize XID=3,
  MXID=1 and **offset=1**, preserving PG19's nonzero offset invariant; add
  the original checkpoint/long CLOG-name expectation. These initdb switches
  depend on later series patch 0009, whose offset defaults also need review.
- Applied mini0133(001_basic.pl), **`de061eec473`**: append Heap3 after
  native XLOG2; retain PG19 archive/compression and continuation-record tests.
  The corresponding rmgr-list addition awaits mini0145(rmgrlist.h).
- Applied mini0134(ginblock.h), **`0e65092d12a`**: store the full deletion
  XID before GIN opaque data, not in the short heap pruning-hint field.
  Traced deletion, ginxlogDeletePage WAL, redo and recyclable-page checks.
  mini0135(gist.h), **`889c1651957`**, changes only the full-XID constructor;
  retain PG19's pointer-based NSN accessors.
- Applied mini0136(heapam.h), **`5912d4d494f`**, and
  mini0137(heapam_xlog.h), **`052fa6d0683`**: merge remaining full-XID scan
  arrays, tuple-aware freeze/accessor signatures, freeze-to-page helpers and
  Heap3 base-shift WAL declarations with the earlier prune adaptations.
  Preserve PG19 PruneFreezeParams, VM flags/block references, batch MVCC API,
  FreezePageConflictXid and removal of XLOG_HEAP2_VISIBLE. Freeze helpers
  execute only supplied plans; no new freeze eligibility rule is introduced.
- Applied mini0138(heaptoast.h), **`7e7939b2721`**: reserve page special
  space in tuple/chunk sizing, retaining native options/varlena interfaces.
  mini0139(htup.h), **`11401997f28`**, adds full in-memory xmin/xmax and
  matching accessor prototypes; JIT's t_data field index becomes 5. PG19's
  JIT derives the struct type from the real C declaration.
- Validation: both changed Perl scripts pass syntax checks. The existing
  page-conversion/UBSan probe now extracts freeze helpers from applied
  heapam.h and passes at all six supported page sizes. Eight saved minis
  reverse-check; eight aggregate sections replay on `8ca324058af` and match
  committed source exactly. Artifacts in Baloo **`909334b`**, parent
  **`110d56b05c0`**. No full build, live TAP, WAL replay or upgrade run;
  remaining 0005 definitions and later initdb switches are still absent.

### Historical finding: TOAST xmax reader assertion (fixed below)

**First unapplied: mini0140(htup_details.h). Stop for discussion under the
user's instruction to pause on a new logic correction.**

- Its new HeapTupleHeaderGetRawXmax(page, tuple) uses
  HeapPageGetSpecial(page)->pd_xid_base for every non-MultiXact xmax.
  A TOAST page has ToastPageSpecialData (one base), whereas an ordinary
  heap page has HeapPageSpecialData (two bases). HeapPageGetSpecial asserts
  the ordinary heap layout and rejects a valid TOAST page.
- Existing consumer: UpdateXmaxHintBits() calls this reader inside an
  assertion; heap_delete()/heap_update()/heap_lock_tuple() use that helper
  after waiting for a non-MultiXact xmax. TOAST chunk deletion uses
  simple_heap_delete(). A live concurrent TOAST execution reaching the
  failing assertion has **not** been demonstrated. The helper's rejection
  of valid TOAST input is reproduced independently.
- This is inherited from the original PG18 xid64 patch; supplied0001 has
  the same code. It is not a PG19 API change. In the tested layouts the XID
  base is the first field of both special structs: do not claim release-mode
  value corruption from this finding; the confirmed failure is an assertion.
- Proposed narrow correction, retaining ordinary heap/MultiXact/double-xmax
  behavior and all PG19 visibility rules:

  ```c
  base = (tup->t_infomask & HEAP_XMAX_IS_MULTI) ?
      HeapPageGetSpecial(page)->pd_multi_base :
      PageGetSpecialXidBase(page);
  ```

- Temporary probe `/tmp/xid64_toast_accessor_probe.py` reconstructs the
  original mini0140 getter and combines it with actual bufpage.h helpers
  and fixed-width tuple scaffolding. Valid TOAST base=4294967296, raw
  xmax=77 aborts at the real layout assertion. Replacing only the non-multi
  accessor in temporary generated code yields 4294967373 under UBSan.
  No production fix or mini0140 application has been made. After approval,
  extend checks across heap/TOAST/double-xmax and MultiXact layouts, then
  validate actual backend paths once the complete series builds.


## IMPORTANT: TOAST xmax reader fixed; mini0140(htup_details.h) applied

- User approved the existing PageGetSpecialXidBase() accessor correction.
  Source **`5b47a85077c`** applies mini0140(htup_details.h) with the
  non-MultiXact raw-xmax branch selecting the heap or TOAST XID base by
  page layout. MultiXact and double-xmax branches retain their behavior.
- Preserve PG19 uint8 tuple bitmaps and removal of redundant xmin setters.
  Tuple decoding/storage helpers use full in-memory XIDs and short on-page
  fields as specified by the original patch; no visibility rule is changed.
- The existing page-conversion fixture now extracts tuple helpers directly
  from applied htup_details.h. Added **68 accessor cases per page size**:
  heap/TOAST layouts, distinct XID/MultiXact bases, reserved IDs, high/full
  boundaries, double-xmax splitting, and writer/reader round trips. All six
  supported page sizes pass with warnings as errors and UBSan; existing
  hint/conversion/freeze/base-shift checks pass too. These are fixed-width
  fixtures, not a complete backend build or live concurrent TOAST test.
- Saved mini0140 reverse-checks; its aggregate section replays on
  `8ca324058af` and matches committed source. Baloo **`e1ae5c7`**, parent
  **`11db8aead20`**. TODO explicitly marks the inherited bug **needed for
  rebase to Tantor 18**. Full series build/recovery checks remain pending.
- Next unapplied at this checkpoint: **mini0141(multixact.h)**.

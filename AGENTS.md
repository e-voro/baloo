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

## IMPORTANT: paused before mini0115(004_verify_heapam.pl)

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
- Reproduced both with the original patch's actual Perl helpers in scratch
  files, not a server. **mini0115(004_verify_heapam.pl) remains unapplied.**
  Proposed fix: preserve reserved IDs while decoding/rebasing, and skip an
  offset when it is below page_start OR at/above page_end. Also audit the
  manually shifted page's pruning hint using the earlier approved hint rules.
  Obtain the user's decision before changing these test-helper semantics.

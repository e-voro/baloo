# Instructions for future AI instances

Read baloo/xid64-rebase-report.md for the current checkpoint and adaptation map.
Read the tail of baloo/codex.log, inspect git status in both the main repository
and baloo, and inspect branch history before changing anything. The report is
historical; verify it against the actual checkout.

**Current scope instruction (2026-10-26): do not inspect or modify any Tantor 18
directory. Decide backport requirements using only original/supplied patch files
inside this workspace. Actual backport application is out of scope.**

The authoritative TODO status register is root `codex_todo.txt`; old checkpoint
notes are archived in `codex_todo-history-20261026.txt`. Read
`xid64-post-adaptation-audit.md` for new tests, supplied-patch dispositions and
remaining limits. New runtime source is 331942f4995; source documentation is
5d5fbdf0901. Older current/checkpoint statements below are historical.

For the complete adaptation record from 0001 onward, read
[xid64-logical-issues.md](xid64-logical-issues.md). It covers 25 numbered topics,
decisions and implementations, the complete-series map, and the PG18 xid64 /
Tantor 18 backport checklist. Error safety is part of backend conversion, not
an additional independently counted fix. The normal-page freeze range guard
is explicitly a mitigation; mixed-format protocol protection remains open.

> **CURRENT (2026-10-26, b0d9496f94f): normal permanent-page conversion emits an
> immediate full-page WAL image before publishing readiness. BM_CONVERTED
> is renamed BM_CONVERSION_NEEDS_WAL; BM_CONVERSION_PENDING still means
> conversion is unfinished, not that a backend owns it. AIO sets both with
> BM_VALID. See xid64-logical-issues.md for the updated issue/backport list
> and the latest section below for passing full/upgrade validation. Older deferred-WAL descriptions
> apply only to history and retained exceptional paths.**

> **CURRENT (2026-10-22): 0005 is fully adapted/applied; all mini steps
> mini0000(verify_heapam.c) through mini0214(typedefs.list) are processed.
> Main series through 0012 is
> applied or explicitly superseded. Follow-up fixes are separate patches
> listed in `patches/func/pg19xid64evoro1900/series`. Full check-world passed
> on 12ff893c75f, including the atomic conversion-readiness correction,
> the VACUUM range guard and recovery's 755
> assertions. Actual PG15.19 and PG18.4 upgrades each pass 98 assertions.
> Automatic handling of
> unrepresentable freeze replacements remains unresolved. See the latest
> checkpoint below; older partial-application statements are historical.**

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


## IMPORTANT: foundational headers and PL adaptation through mini0183(xid_wraparound.c)

- Completed the previously requested TOAST-fix report and **needed for rebase
  to Tantor 18** TODO entry in source/docs checkpoint **`ca75dc6865e`**.
- Applied mini0141(multixact.h) through mini0163(autovacuum.h), except
  mini0148(tupmacs.h), already incorporated by mini0027(tupmacs.h). Preserve
  its shared TYPALIGN_DOUBLE/TYPALIGN_XID -> ALIGNOF_DOUBLE cases.
- mini0141(multixact.h) keeps PG19 uint64 offsets, oldestMulti/oldestOffset
  truncate WAL, GetMultiXactInfo(uint64 *) and the required int64 member
  pressure threshold. Full MultiXact ID constants are now 64 bits. Clarified
  the inherited contradictory comment: ID zero is invalid, assignment starts
  at one. Do not restore the removed MaxMultiXactOffset/wrap-limit API.
- mini0142(nbtree.h) supplies legacy opaque-field macros used by pageinspect;
  retain native BTDeletedPageData full safexids. mini0144(rewriteheap.h)
  matches the already-adapted mapping filename writers and eight-field parser.
  mini0145(rmgrlist.h) appends Heap3 **after XLOG2**, retaining native IDs.
  The complete 24-entry pg_waldump expected list matches the header exactly.
- mini0147(transam.h), **`2782ca29cf0`**, retains PG19 shared-memory APIs,
  widens comparisons/constants and uses the original full-XID constructor.
  Applied mini0174(xid8.h) and mini0181(regress_injection.c) early with it;
  skip their replay. The cutoff helper wraps the full XID directly and keeps
  PG19's stable-nextXid retry; no epoch reconstruction is needed.
- mini0149(xact.h)/mini0151(xlogrecord.h) supply full-XID WAL layouts matching
  earlier writer/parser adaptations; preserve PG19 read-only nest reporting.
  mini0150(xloginsert.h) defines the converted-buffer flag already used by
  the adapted writer; keep XLogGetFakeLSN(). mini0152(c.h) widens transaction,
  local and subtransaction IDs, adds ShortTransactionId and start validators,
  and retains native uint64 MultiXactOffset, Oid8, C11/C++ and alignment APIs.
  mini0153(catversion.h) keeps the original development marker 999999999.
- Catalog/operator/function/type declarations now match full XIDs; preserve
  PG19 Oid8 catalogs, ACLs, statistics interfaces and catalog-struct markers.
  Vacuum headers/reloptions retain PG19 pointer APIs, worker accounting,
  score weights and ternary options while widening freeze ages. The int64
  list member/prototype is added without changing native cell constructors.
- mini0161(pg_lfind.h) adds a read-only uint64 search API, matching native
  const-qualified search inputs. mini0182(test_lfind.c), **`07a65dcfd88`**,
  retains every native 32-bit test and calls an additional 64-bit helper from
  the existing SQL entry point. New keys exceed UINT32_MAX and cover unrolled
  and tail paths; the original mini replaced the 32-bit coverage instead.
- Applied mini0169(itemid.h), mini0171(proc.h), mini0172(combocid.h),
  mini0173(rel.h), mini0175(plperl.c), mini0176(pl_exec.c), mini0178(pltcl.c),
  mini0179(Makefile), mini0180(meson.build). PGPROC xid/xmin/mirrored xids are
  atomic while preserving PG19 cache-line layout, conflict bitmask, free
  lists and buffer-lock waiting. Full cached catalog xmin is used by PLs;
  fabricated PL/pgSQL composite wrappers initialize both XIDs to zero.
- mini0177(plpy_procedure.c) is superseded: PG19's CachedFunction callbacks
  replaced its old fn_xmin ownership. Existing adapted funccache.c already
  uses HeapTupleGetRawXmin at both assignment and validation. No PL/Python
  source edit is needed. mini0183(xid_wraparound.c) is already incorporated
  by formatting adaptation 0001. Skip notes record both cases. Earlier AIO,
  buffer and lock header steps remain applied/superseded; do not replay them.
- Validation: dev/tests/xid64_transam/check.py compiles actual transam.h,
  applied ID typedefs, the cutoff helper and uint64-search code with fixed
  service/tuple scaffolding, warnings as errors and UBSan. Ten high-XID
  cutoff/retry scenarios, comparison/advance/retreat checks and the actual
  new high-bit search regression helper pass. pg_waldump Perl syntax passes.
  **34 saved minis reverse-check; 34 aggregate sections replay on 8ca324058af
  and match source exactly.** Saved artifacts/probe in Baloo **`2aedb71`**,
  parent **`d454d1a37e7`**. No full build, live SQL, PL regression, TAP or
  recovery run is claimed. New xid-64 test directory arrives in later minis;
  the aggregate is still only partly adapted.

### Historical finding: mini0184(AdjustUpgrade.pm) regression-table assumption (fixed below)

**First unapplied: mini0184(AdjustUpgrade.pm). Paused under the user's rule
for discussion before new logic corrections. This finding concerns the test
harness, not PostgreSQL runtime tuple storage or WAL.**

- The original mini unconditionally schedules:
  `alter table public.tab_core_types drop column xid`.
  The PG11.22 regression source has no tab_core_types; executing that test
  adjustment therefore fails before pg_upgrade. PG12.22 has the table, but
  initial PG12.0/13.0/14.0 tags do not: presence was backpatched, so do not
  describe it simply as a table introduced in PG12.0.
- Source evidence: inspected local release-tag SQL. A temporary application
  of the original mini and actual adjust_database_contents() calls emits
  the unguarded command for PG11/12/18/19. No live SQL/server was executed.
- Proposed concrete SQL (not applied):
  `alter table if exists public.tab_core_types drop column if exists xid`.
  This tolerates either absent object without relying on a major-version
  guess; PostgreSQL 9.2 grammar supports both IF EXISTS clauses. Preserve
  PG19 btree_gist and other native upgrade adjustments. Discuss this test
  behavior before implementing mini0184(AdjustUpgrade.pm).


## IMPORTANT: all 0005 minis processed; first complete build exposes freeze fallback

- User approved mini0184(AdjustUpgrade.pm) with both IF EXISTS clauses.
  Applied **`7b3940c7dfd`**; actual adjustment generation for PG11/12/18/19
  emits the guarded SQL, and Perl syntax passes. Preserve all native PG19
  upgrade adjustments. This was a low-priority older-source test issue.
- Processed remaining mini0185(Cluster.pm) through mini0214(typedefs.list).
  Preserve native PG19 recovery/logical-promotion tests and regression
  content; synthetic end-of-WAL headers match the 28-byte xid64 header.
  Regression SQL/expectations cover widened xid and snapshot boundaries,
  deterministic view order, tuple sizing and page conversion. Imported
  expectations and C conversion test helpers still require live validation.
- mini0198(regress.c) retains the previously authorized by-value AIO metadata
  wrapper. mini0210(004_test_relminmxid.pl) explicitly starts MultiXact IDs
  at 1, matching its assertions despite Cluster.pm's high-ID defaults.
  All changed Perl modules/recovery tests and six new xid-64 TAP files pass
  syntax checks. The initdb options and meson-listed 001_test_large_xids.pl
  still depend on later series patch 0009; do not claim that TAP ran.
- PG19 recovery-target diagnostics now format the full-width first-normal
  constant correctly and drop obsolete epoch wording; validation rules are
  unchanged. Source **`dcbd6235799`**, saved supplemental patch
  pg19-recovery-target-xid.patch. The existing lower-bound test is updated.
- Whole-aggregate verification exposed stale contexts in early
  mini0001(verify_nbtree.c), mini0009(heapfuncs.c), mini0027(tupmacs.h).
  Refreshed their saved contexts from committed source. All other earlier
  aggregate sections already yielded the correct source when replayed.
  **The complete aggregate now replays on 8ca324058af and matches all 219
  source files exactly**, including new files. No history aggregation/reset
  was performed. Saved final artifacts in Baloo **`3efe9a3`**, parent
  **`fd8e0764bd4`**. All mini steps are processed; validation is unfinished.

### NEW LOGIC DECISION: freeze_single_heap_page() and PG19 prune/VM API

**Pause before changing this fallback, under the user's core-logic review
rule. This is a missed PG19 adaptation in mini0028(heapam.c), not evidence
that the original PG18 caller used the wrong PG18 API.**

- First full-source build configured successfully with assertions, injection
  points, TAP and CFLAGS=-O0 -g -Werror=format. Build directory:
  **`/tmp/pg19-xid64-build-iAc7eE`**. `make -j4 world-bin` fails compiling
  heapam.c: VacuumParams is passed by value to vacuum_get_cutoffs(), and
  the positional heap_page_prune_and_freeze() call no longer matches PG19.
  No live backend/TAP/recovery run has occurred. Resume this build directory
  after the fix; build.stdout contains the full compiler output.
- A signature-only change is insufficient. freeze_single_heap_page() is the
  xid64 fallback after base shifting cannot accommodate an XID/MultiXact.
  Its original final false argument deliberately disabled fragmentation
  repair. The current PG19 main prune path always passes true to both
  heap_page_prune_execute() and log_heap_prune_and_freeze(). That would
  discard the caller's requested behavior and advertise it differently in
  WAL; the lower-level execution/redo flag machinery already exists.
- PG19 prune_freeze_setup() also asserts a valid pinned VM buffer and reads
  VM state even without HEAP_PAGE_PRUNE_SET_VM. The helper currently has no
  VM buffer argument. The prune contract requires a cleanup lock, while
  INSERT/UPDATE/DELETE/tuple-lock callers of heap_page_prepare_for_xid()
  have their own buffer pins, content locks and tuple-pointer assumptions.
  Audit those contracts before allocating a VM pin, releasing any lock, or
  enabling fragmentation repair. Do not pass InvalidBuffer or silently
  substitute ordinary cleanup pruning merely to compile.
- Proposed direction for discussion: adapt to PruneFreezeParams and pointer
  VacuumParams; preserve the explicit no-fragmentation request through
  primary execution and its WAL flag; provide VM state/pinning with native
  lock ordering and retain normal PG19 behavior for other callers. Resolve
  the fallback's cleanup-lock/held-pointer contract as part of that design.
  Freeze eligibility, cutoffs, failsafe and full conflict horizons remain
  governed by existing rules. No new freeze-all behavior is authorized.
- After approval, implement, resume world-bin and then test forced base-range
  exhaustion for heap/TOAST, XID/MultiXact replacement and WAL replay. The
  stored HeapTupleSatisfies* invocation-chain audit is now due but remains
  unfinished. Keep the separate already-normal replacement-range audit.

## IMPORTANT: approved single-page freeze fallback correction (2026-10-21)

- User approved implementation after discussing cleanup locking. Updated
  mini0028(heapam.c), mini0034(pruneheap.c), and mini0136(heapam.h):
  freeze_single_heap_page() passes &VacuumParams and PruneFreezeParams,
  obtains a corresponding VM pin, passes it to pruning, and releases it.
- **VM lock ownership:** the existing PG19 pruning routines acquire/release
  the exclusive VM content lock when clearing corruption or setting VM bits.
  Do not lock the VM around the call: that would acquire it twice. The
  fallback retains the heap exclusive lock and pins the VM under that lock,
  as native heap_page_prune_opt() does; it does not unlock/relock heap pages
  underneath callers' tuple pointers or two-buffer update locks. This rare
  fallback can therefore perform VM I/O under the heap lock. SET_VM remains
  disabled: outer DML callers may have no VM pin to clear newly set bits.
  PG19 VM consistency checks and corrective clearing remain enabled.
- **No fragmentation repair:** new opt-in
  HEAP_PAGE_PRUNE_NO_REPAIR_FRAGMENTATION preserves the original xid64
  fallback's false argument through page execution and prune WAL. All
  existing callers retain ordinary defragmentation. No live tuple storage
  moves or dead tuple bytes are reclaimed in this mode; pruning may still
  change globally dead items' line pointers. The fallback retains an ordinary
  exclusive heap content lock and does not wait for other pins. WAL retains
  XLHP_CLEANUP_LOCK: standby replay still uses stronger cleanup locking, but
  the fragmentation flag is clear. Freeze eligibility, cutoffs, failsafe,
  selected-plan ordering and full conflict horizons are unchanged.
- **Critical-section caller:** heap_abort_speculative() previously invoked
  page preparation inside its critical section. Move preparation before
  START_CRIT_SECTION(), retaining the pruning-hint/tuple changes inside.
  This permits fallback VM pinning and visibility work to fail normally.
  The fallback asserts an exclusive heap lock and no outer critical section.
- First resumed world-bin compiles the corrected heap files, then finds a
  separate PG19-only checksum-worker activity string using %u for a now-full
  TransactionId. Widened that diagnostic to %llu with an unsigned long long
  value cast; transaction waiting logic is unchanged. Full build and live
  fallback/VM/concurrency/recovery validation are still in progress; do not
  infer those results from successful heap-object compilation.

### Overnight authorization and validation findings (2026-10-21)

- User explicitly authorizes overnight adaptation, including logical fixes
  without pausing for individual discussions. Save applied fixes and proposals
  on alternative branches and document reasons/results for later discussion.
  Both repositories now use pg19beta3xid64_CODEX_OVERNIGHT_20261021. Original
  main branch is preserved at 6400ddc9891; original Baloo branch at 878a515.
- Fallback source: 088d616a983. Additional PG19 width adaptation: 6400ddc9891.
  pg_get_multixact_stats() must pass uint64 storage to GetMultiXactInfo(),
  return num_mxids as int8 and oldest_multixact with TransactionIdGetDatum().
  The missed caller otherwise permits an eight-byte write into a four-byte
  local and truncates the returned oldest ID. Catalog return types already
  support the corrected values. The checksum activity diagnostic is also fixed.
- world-bin and install-world-bin pass with assertions/TAP/injection points
  and -Werror=format. The complete saved 0005 aggregate replays exactly on
  8ca324058af across 221 source files. Artifacts Baloo 9226f18, parent 14a6b49d4f9.
- Live probe dev/tests/xid64_freeze_fallback/check.py uses an isolated cluster,
  artificial full-XID jumps and a concurrent backend retaining a page pin and
  dead HOT-root payload pointer. With FPW on, insertion finishes while that
  pin is held; root becomes LP_REDIRECT, surviving tuple address/payload is
  unchanged, eligible xmin freezes, VM pin is created without setting bits,
  and crash redo with wal_consistency_checking=all passes.
- FPW-off redo finds a real consistency-check failure at PRUNE_ON_ACCESS.
  Temporary diagnostics (removed from source afterward) identify byte 8157:
  replay=1, primary=5 in the orphaned dead tuple header. Primary visibility
  checks set hint bits that redo need not reproduce. heap_mask() masks only
  normal tuples and central free space, leaving dead tuple storage exposed.
  Original later patch 0007 zeros dead tuple storage on the real page, which
  conflicts with our pin-only pointer preservation requirement. Proposed
  adaptation: mask unreferenced tuple-area bytes only in the consistency
  check's private copies, keeping live tuples, line pointers and page bases
  checked and leaving shared dead tuple bytes untouched. Validate both FPW
  modes and held pointers before claiming the fallback/recovery work complete.

### Applied patches 0006-0008; fallback recovery validated

- Patch 0006 (README.XID64), 7b5ca03ef47, adds the original design document.
- Patch 0007 (heapam_xlog.c), a613c77b2ba, implements the private-image
  masking solution above instead of the original real-page zeroing. It
  preserves pin-only dead tuple pointers. The mask retains every referenced
  tuple's aligned storage and masks holes only between pd_upper/pd_special;
  live data, line pointers and page bases remain checked. Temporary recovery
  byte-dump instrumentation was removed and is absent from committed source.
- Patch 0008 (heapam.c), 9eb9842a30d, requires physical emptiness before
  INSERT emits INIT_PAGE. A single reusable slot after pruning is insufficient
  when old tuple storage remains below pd_special. Preserve PG19 VM lock/WAL
  changes and existing page variable; capture physical emptiness before insert.
- Final live probe /tmp/xid64-freeze-fallback-iap5glkh passes FPW on/off with
  concurrent buffer pins, stable dead payload/survivor addresses, HOT redirect,
  eligible freezing, VM pin creation and crash redo with consistency checking.
  Negative mask checks detect deliberately changed live payload, page base and
  redirect metadata while ignoring orphaned bytes. A separate one-unused-slot
  fixture retains physical storage, reuses slot 1, and passes crash recovery
  with the same tuple offset. Backend rebuild/install passes. This is targeted
  backend/crash validation, not full check-world or streaming standby coverage.
- These cleanup-lock findings and changed patch 0007 semantics must be reviewed
  with the user later and considered for pg18xid64/Tantor 18. Do not reapply the
  original shared-page zeroing on top of the adapted masking solution.

### Main series complete through 0012; continuing supplied fixes and audit

- 0009, fe80a516e7a: preserve PG19 pg_getopt/optctx, checkpoint fields and
  native initial MultiXact offset=1. initdb rejects offset zero and negative
  strtoull inputs, including negative values that wrap into small unsigned
  numbers. Initialize starting CLOG/SUBTRANS/MultiXact SLRU pages. initdb TAP
  passes all 93 assertions; large-XID/relminmxid TAP passes 24 assertions.
- 0010, 52507090d0e: portable PRI?64 formats, including PG19-only diagnostics,
  wrapped-MultiXact upgrade, full apply-lock keys and VM/prune descriptions.
  Keep safe parser temporaries and signed base-shift delta formatting.
  world-bin and actual multixact.c with MULTIXACT_DEBUG/-Werror=format pass.
- 0011 is explicitly superseded by the already-authorized supplied AIO fix
  0008. Do not restore conversion-time GenericXLog/WAL insertion in workers.
  The saved .skip note tracks the remaining supplied0015 override/marker case.
- 0012, 60a08afaf2e: rename only reserved union member _int64 -> _int_64 and
  map it explicitly in gen_guc_tables.pl. Preserve GUC type name "int64",
  PGC_INT64 and parser semantics. Linux world-bin passes; MSVC not executed.
- All main-series steps are applied/superseded. Saved 0005-0010 patches replay
  exactly on 8ca324058af across 253 source files. Full core regression passes
  all 246 tests, including xid64, on the assertion build through 0012. Full
  check-world, streaming and cross-version upgrade validation remain pending.
- Visibility audit has found a correction to the earlier b29c7c726fb decision:
  HeapTupleSatisfiesVacuumHorizon() must not decode an unconverted legacy
  page through HeapTupleCopyXidsFromPage(). Legacy and double-xmax both have
  no special space; that helper treats a legacy page as double-xmax, can
  overwrite the converter's already-expanded wrapped MultiXact, and asserts
  a content lock unavailable to AIO completion. Current-format pages must
  still decode, including real double-xmax pages; use page layout version,
  not special-space size, to distinguish them. The converter already prepares
  header XIDs and expands source MultiXacts before calling visibility.
  This correction is being implemented and requires dense legacy-page/AIO
  and wrapped-MultiXact validation. Ordinary prune callers rely on Horizon
  to initialize their tuple cache; do not remove that ownership globally.

## IMPORTANT: applied overnight conversion, upgrade and VACUUM corrections

- **1547efbb710 — visibility ownership and AIO:** ordinary Vacuum/Horizon
  calls decode full XIDs from the current page under their existing content
  lock. InvalidBuffer explicitly selects predecoded XIDs and no hint writes;
  conversion uses it after expanding source MultiXacts. Merely gating recopy
  by page version was insufficient: dense unfrozen conversion then crashed
  an AIO worker in BufferIsPermanent(), because SetHintBits needed a private
  pin. SetHintBitsExt now returns before buffer APIs in the no-hints mode.
  Current-layout assertions replace special-space assertions in Update and
  Visibility, accepting genuine double-xmax pages. Legacy pages also lack
  special space and must never be decoded as double-xmax. Do not revert to
  the earlier unconditional legacy recopy or remove ordinary callers' copy.
- **bdb4e4b907a — user XID storage checks:** require attnum > 0 in both
  recursive composite propagation and final stored-column reporting. A real
  PG15.19 int/text-only source otherwise failed on every table's xmin/xmax;
  filtering only the final query would still contaminate safe row types.
  Continue rejecting actual xid columns, xid arrays and xid composites.
- **b052fd6b675 — supplied0015 port to PG19:** converted images override
  NO_IMAGE/full_page_writes; preserve WILL_INIT and retain BM_CONVERTED on
  NO_CHANGE references. PG19 prune WAL forces a converted heap image and
  advances its heap LSN, replacing PG18's log_heap_visible/VM location.
  Existing regression library supplies the relcache-less extension helper;
  no test-module relocation is needed. Add native Meson registration and
  pg_visibility installation. Cluster.pm supports explicit xid32 initialization
  and suppresses high-counter defaults for external initdb binaries that lack
  those options, using capabilities rather than major-version guesses.
- **Cross-version evidence:** adapted pg_upgrade/t/009_xid32_to_xid64_recovery.pl
  passes **19 assertions with actual PG15.19**, including positive/negative
  user-column checks, safe row types, dense frozen/unfrozen AIO conversion,
  double-xmax UPDATE, streaming FPI/incremental replay, missing-block and
  existing-block relcache-less extension, and visibility WAL with checksums,
  wal_log_hints and full_page_writes disabled. Test-only freeze ages prevent
  forced autovacuum from pre-converting the legacy fixture. This run precedes
  the independent age-cutoff fix below; rerun against the final tested tree.
- **0828bf07ff3 — VACUUM ages:** full-XID subtraction wrapped young counters
  when configured ages exceeded them. This produced spurious warnings,
  aggressive freezing and failsafe activation. All eight cutoff computations
  in vacuum_get_cutoffs()/vacuum_xid_failsafe_check() now saturate at the first
  valid ID. The 105% failsafe margin uses bounded integer arithmetic, capped
  at INT64_MAX; UBSan reproduced the original float-to-int64 overflow at a
  valid INT64_MAX GUC. Keep PG19's existing 95% aggressive policy, cutoffs'
  oldest-snapshot caps and freeze eligibility. Autovacuum's score threshold
  remains double and its force cutoffs already had underflow guards.
  Actual-function/actual-transam fixture passes **123 cases with UBSan and
  float-cast-overflow checks**; new live xid-64/t/008_vacuum_ages.pl passes
  **7 assertions** for low counters/default/MAX ages and explicit zero-age
  freezing. It does not disable ordinary or required freezing/failsafe work.
- All four follow-up patches and a usable `series` manifest are saved in
  patches/func/pg19xid64evoro1900/. The complete ordered series replays exactly
  on vanilla 3421b154340 across **259 source paths**. Original v67 patches are
  preserved. Do not rewrite/squash the main or overnight history unasked.
- Gate 1 stopped during test-module compilation: test_slru's error callback
  still printed a TransactionId with %u. Fixed in 87aca2ff8ca; saved patch
  pg19-test-slru-xid-format.patch. The ordered series through that commit
  replays exactly on vanilla 3421b154340 across 260 source paths.
- Gate 2, source 87aca2ff8ca, completed: recovery **54 files/755 assertions**
  passes with WAL consistency checking, subscription **39/595** passes,
  xid64 **8/61** passes, and core regression passes. Overall check-world
  fails on three test fixtures, corrected below; do not report a full pass.

### IMPORTANT: converted hint durability; regression adaptations

- **42a0b1c973e — conversion must survive hint writes.** With checksums,
  wal_log_hints and full_page_writes off, SELECT could dirty an AIO-converted
  page via a commit hint without WAL. CHECKPOINT persisted layout 5; primary
  restart discarded BM_CONVERTED. Later incremental UPDATE WAL crashed the
  standby's read of its still-layout-4 page in heap_convert.c, asserting
  relkind != RELKIND_UNKNOWN. Reproduced with actual PG15.19 upgrade.
- MarkSharedBufferDirtyHint now requires WAL for a converted permanent page,
  preserving the native recovery/skip-WAL guards. A conditional critical
  section spans dirtying through image insertion and page-LSN publication.
  XLogSaveBufferForHint logs conversion even if the page LSN exceeds redo.
  XLogRegisterBuffer's converted-image handling supplies the forced image;
  AIO workers still never insert WAL. Ordinary hint-only pages are unchanged.
- Extended pg_upgrade/t/009_xid32_to_xid64_recovery.pl passes **23 assertions**
  with PG15.19, including hint-only SELECT, checkpoint, primary restart and
  incremental standby replay. Failed unfixed probe logs are preserved at
  /tmp/xid64-hint-durability-58qjkrg0. Backport to pg18xid64/Tantor 18.
- **380de11735c — test fixtures:** restore PG19's >65535-TID-array case in
  heap_surgery_1.out; retain xid64's existing frozen-row expectations. Use
  the supplied combine-backup filler size 192 rather than 200 to preserve
  the same-page update after reserving xid64 page bases. The SLRU test now
  checks monotonic IDs across 2^32 for xid64, retaining wraparound for xid32.
  Native surgery regression, combine-backup **39 assertions**, and SLRU
  regression/TAP **18 assertions** pass. These are harness adaptations.
- **d4cff03bb40 — PG19 Pointer portability:** Pointer is void *, unlike the
  PG18 assumption in imported byte arithmetic. Use char * for WAL offsets
  in heapam_xlog/decode and page offsets in bufpage. Affected files/world-bin
  compile with -Werror=pointer-arith and -Werror=format. No MSVC run claimed.
- Supplied0014 CREATE DATABASE metadata and supplied0013 double-xmax test are
  being adapted next. Source changes remain isolated on the overnight branch.
  Full check-world must be repeated after all pending source fixes.

## IMPORTANT: backend conversion checkpoint (2026-10-22)

- **e994dd04c51:** supplied0014 CREATE DATABASE metadata is ported. Preserve
  PG19 batching/callbacks and native io_min_workers/io_max_workers; remove
  obsolete io_workers from the supplied test. Source pg_class relkind,
  relfrozenxid and relminmxid travel by value in ReadBuffersOperation.
  The test uses 010 because PG19 already has 008_extension_control_path.
- **56da45eb194:** supplied0013 double-xmax VACUUM regression uses test 011.
  It verifies real layout-5/no-special pages directly after CHECKPOINT,
  avoiding a heap SELECT that could hide the defect by setting hints.
  Together these two tests pass 22 assertions with actual PG15.19.
- **a09ce2c567d — supersedes worker-side conversion above:** native PG19
  MultiXact upgrade workload reproduced an I/O-worker assertion in
  MyOldestVisibleMXactIdSlot via compute_xid_min_max/GetUpdateXid. Workers
  lack backend visibility slots; GetMembers also allocates a transactional
  cache, and shared completion cannot safely raise conversion ERRORs.
  Enlarging the slot array alone would not solve those ownership problems.
- Physical reads remain asynchronous. Shared completion only sets BM_CONVERTED
  on legacy pages before BM_VALID. The reading backend finishes conversion
  before normal read APIs expose them: cached/forwarded hits, asynchronous
  races and waited I/O are covered. ReadRecentBuffer rejects pending legacy
  pages so the ordinary read path can finish them. Metadata still comes from
  the backend's Relation or the operation's by-value copy, never a worker's
  access to the issuer's relcache. FPI overwrite paths retain native behavior.
- Conversion takes the exclusive content lock, validates legacy tuple bounds,
  alignment, headers and nonoverlap, converts a private copy outside critical
  sections, then publishes the copy. ERROR leaves the shared legacy page
  unchanged and retryable. BM_CONVERTED continues to force the first durable
  image; no conversion-time WAL is inserted in a worker. Source tuple TID
  initialization now uses its line-pointer number, not its byte offset.
- Cross-version run passes **4 files/62 assertions** against PG15.19: basic
  and wrapped MXID/offset upgrades, source epoch=1, conversion errors twice
  as ordinary SQL errors, continued server availability and successful repair
  after restart, hint/checkpoint/restart standby durability, relcache-less
  redo, CREATE DATABASE, and double-xmax UPDATE/VACUUM. Native test 007 now
  normalizes wrapped target MXIDs by 2^32-1 only for xid32-source comparisons.
  Source CLOG conversion already uses low 32 bits (38bdfc1d082), so supplied
  nonzero-epoch fix is covered without duplicating it.
- **Rejected experiment, not committed:** avoiding worker member resolution
  by forcing updating-MultiXact pages into double-xmax layout encountered
  an orphaned dead HOT tuple. The experiment was removed before a09ce2c567d.
  Audit dense legacy HOT chains separately: conversion currently discards
  dead tuple line pointers before freezing and must preserve index roots,
  redirects and chain identity. Do not claim this case fixed or reproduce
  the rejected range-forcing approach in a backport.
- Full gate 3 on a09ce2c567d stopped in test_aio with an invalid persistence
  value. Its .o/.so dated 20:31 predated the 20:54 ReadBuffersOperation ABI
  change; rebuild that module before diagnosing it as a source failure.
  No full-suite pass has yet been established for this final source tree.
- Save patches with the `series` manifest. Original branch/history and v67
  artifacts remain preserved. Backport backend conversion ownership/error
  handling and the already-documented hint-durability fix to Tantor 18 after
  comparing the supplied fixes. No MSVC or generic mixed-format wire protocol
  compatibility is claimed.

## IMPORTANT: completed adaptation, HOT roots and freeze range limit (2026-10-22)

- **0005 is complete:** all 215 mini steps are processed. The saved
  0005 aggregate at 6400ddc9891 covers 221 files and replays on 8ca324058af.
  Preserve that boundary: later series changes and audited fixes are separate
  supplemental patches, not a newly expanded 0005 aggregate. Both repositories
  remain on `pg19beta3xid64_CODEX_OVERNIGHT_20261021`; original branches and v67
  artifacts are preserved.
- **fbeca95f940, mini0088(heap_convert.c) follow-up:** dense legacy conversion
  marked a dead HOT index root LP_DEAD while retaining its live heap-only
  successor. An actual PG15 source reproduced a missing row through the
  primary-key Index Scan while a sequential scan found it. The private-copy
  converter now prunes HOT chains before freezing xmin: preserve original
  updater/xmin chain identity, redirect indexed roots to surviving versions,
  retain LP_DEAD for wholly dead indexed chains and remove eligible dead
  heap-only items. Reject broken chains; do not freeze active/recent tuples
  merely to fit a page. The first conversion image includes the resulting
  line-pointer changes. Backport to pg18xid64/Tantor 18 after comparison.
- New pg_upgrade/t/012_xid32_to_xid64_hot.pl passes **36 assertions** covering
  dense live chains, existing redirects, deleted chains, aborted updates and
  aborted inserts. Fixtures assert same-page storage and less than 16 free
  bytes; forced Index Scan matches sequential scan. Streaming and primary
  crash replay run with full_page_writes off and WAL consistency checking.
  Failed unfixed probe: /tmp/xid64-dense-hot-2hgebgvn. An earlier probe whose
  filler landed on another page did not exercise this case.
- **6eca8f6c039:** live binary-XID COPY test passes **6 assertions** for full
  unsigned-64 boundaries, low-half-first golden bytes and seven-byte input
  rejection without changing existing rows. This completes the live follow-up
  to the mini0103(xid.c) receiver fix; it does not change its wire layout.
- **9a36538da22:** supplied upgrade tests enable source checksums only when
  disabled. PG18's already-enabled default is accepted. Actual **PG15.19 and
  PG18.4** each pass the five upgrade suites 007/009/010/011/012, **98 assertions**
  per source. These exercise real xid32 sources, including wrapped MultiXacts,
  nonzero epochs, backend AIO conversion, durability, CREATE DATABASE and HOT.
  Already-xid64 source upgrades, native PG19 eight-byte offset sources and
  live --swap remain separate validation tasks.

### Visibility invocation-chain audit

Repository callers and buffer-lock ownership were reviewed; retain these
contracts when backporting or changing callers:

| Entry/path | Full-XID initialization and ownership |
| --- | --- |
| HeapTupleSatisfiesVisibility | Dispatcher copies from the locked page before static snapshot implementations. |
| HeapTupleSatisfiesUpdate | Entry initializes its cache; caller copies before earlier HOT/SSI checks and again after relocking when required. |
| Vacuum / VacuumHorizon | Valid-buffer entry owns decoding, including direct prune callers; do not remove it globally. |
| Private legacy conversion | Converter prepares full source XIDs and expands wrapped MXIDs; InvalidBuffer selects no recopy and no hint writes. |
| PG19 batched MVCC / all-visible scan | page_collect_tuples initializes every tuple under lock before batch use or unlocked tuple delivery. |
| HOT index search / HeapTupleIsSurelyDead | Index path initializes full XIDs before chain checks; its surely-dead call consumes that cache under the lock. |

Nested Visibility -> NonVacuumable -> Horizon copies follow independent entry
contracts and are intentional. Preserve hidden updater-XID accounting in page
base scans. This is a repository call-chain review, not a proof about external
extensions or every concurrent interleaving. Ordinary valid-page visibility
and private legacy conversion must retain their distinct ownership contracts.

### IMPORTANT: normal-page freeze range crash protection and remaining design

- **Confirmed on 9a36538da22:** with old MultiXact 2 at page base 0, one finished
  locker and two live lockers, freezing creates replacement MultiXact
  2147484672. Storing it exceeds the 31-bit short-XID range and PANICs inside
  the critical section. This is an xid64 storage issue, not evidence of a
  vanilla PG19 regression. Reproducer explicitly jumps the counter and
  supplies the skipped offset page in a disposable cluster; it is not a
  natural-duration workload or a crash-recovery fixture. Failed valid probe:
  /tmp/xid64-freeze-range-gxs3p6r5. A prior missing-offset-file fixture was
  corrected and is not evidence for this crash.
- **19da20487ca:** existing heap_pre_freeze_checks validates every selected
  planned xmax before executing any freeze plans. Select the base using the
  planned infomask (MultiXact can become an updater XID), preserve absolute
  special IDs and reject relative special encodings or out-of-range values
  with SQLSTATE 54000. Subtract only after checking the lower bound to avoid
  unsigned overflow. Double-xmax pages retain direct full-width storage.
  Freeze eligibility, snapshot cutoffs, failsafe and PG19 VM/WAL paths are
  unchanged. Earlier visibility checks may still set ordinary hint bits.
- Live probe `dev/tests/xid64_freeze_range/check.py PREFIX BUILD_DIR` passes
  **10 assertions**: normal SQL error, actual planned value/base diagnostic,
  server availability, unchanged tuple xmax and visible row, then successful
  VACUUM and cleared xmax after lockers finish. It compiles a test-only helper
  and changes counters/offset files only in new /tmp data. Backport crash
  protection to pg18xid64/Tantor 18 after comparing supplied fixes.
- **NOT a complete range solution:** the guard stops a server crash; VACUUM
  can still fail while the incompatible range remains. Automatic rebasing
  must account for surviving tuples and all final freeze plans, including
  hidden updater XIDs, and WAL-log matching base changes. Calling ordinary
  page preparation from freeze planning risks recursion through the freeze
  fallback and cannot guarantee a representable range. Promotion to double
  xmax is permitted only if every surviving xmin is already frozen or
  independently eligible; active/recent tuples cannot be forcibly frozen.
  Skipping required replacements would change FreezeLimit postconditions and
  horizon tracking. Those alternatives are proposals for user discussion,
  not applied fixes or completed compatibility claims.

### Validation and saved artifacts

- Fresh build `/tmp/pg19-xid64-final-0LJDks` enables dependency tracking,
  assertions, TAP and injection points with -O0/-g/-Werror=format and
  -Werror=pointer-arith. Full world-bin and full check-world with
  `PG_TEST_EXTRA=wal_consistency_checking` **passed on 9a36538da22**: recovery
  **54 files/755 assertions**, AIO **4/597**, xid64 **9/67**, core **246 tests**.
  Cross-version tests are separately run with actual old installations;
  the default full gate skips those requiring oldinstall. Log: build directory
  `check-world.stdout`. This supersedes the stale-object gate-3 concern.
- **Final gate on 19da20487ca passed (exit 0)**, including the range guard:
  recovery **54/755** with WAL consistency checking, AIO **4/597**, xid64
  **9/67**, subscription **39/595**, and core **246 tests**. Log:
  `check-world-freeze-range.stdout` in the fresh build directory. Source
  code stayed unchanged throughout; subsequent commits only save artifacts
  and documentation. The separate live range probe passes 10 assertions.
- Repeated all five actual-source upgrade suites against the same final
  code: **PG15.19 98 assertions, PG18.4 98 assertions, both exit 0**. Log:
  `check-legacy-freeze-range.stdout`. These provide the cross-version checks
  skipped by default check-world when oldinstall is unset. Validation is
  complete for these configured gates; the explicit remaining range design,
  other source-layout coverage and backports remain open.
- The manifest now contains **26 patches**. Replay against 3421b154340 matches
  19da20487ca byte-for-byte across **268 source paths**. Baloo artifact commit
  952a733 is recorded by separate parent 014b541c211; source fixes and artifacts
  remain separate commits. No MSVC run or generic mixed-format replication
  protocol compatibility is claimed.

## IMPORTANT: re-audit of pending page access and publication (2026-10-22)

**This supersedes the earlier claim that an unlocked current-version test
proves conversion complete.** The user challenged that assumption and asked
for a renewed audit of every access path. No source changes preceded the
audit. The checked-in core/contrib acquisition paths are covered by the
contracts below; this is not a claim about arbitrary external extensions.

- **Confirmed race, corrected in 12ff893c75f:** full-page memcpy can publish
  layout version 5 before line pointers, special space and tuple bytes. Both
  FinishReadBufferConversion and ReadRecentBuffer could then return early.
  A deterministic injection point pauses after the header copy: both checks
  fail on the old implementation and pass after the correction. This proves
  premature API return, not a demonstrated incorrect SQL tuple result;
  ordinary tuple readers also take a content lock.
- **New readiness protocol:** successful legacy I/O publishes BM_VALID,
  BM_CONVERTED and BM_CONVERSION_PENDING in the same buffer-state update.
  BM_VALID still denotes completed physical input. A pin prevents eviction;
  it does not imply conversion readiness. Any ordinary reader with relation
  metadata may finish conversion. An exclusive content lock serializes
  converters; recheck the pending bit after locking. Clear it with a full
  barrier atomic operation only after installing the full copy. Fast readers
  use the pending bit plus a read barrier, never an unlocked page version.
  BM_CONVERTED independently retains the first-image WAL obligation.
- The in-memory flag field grows from 12 to 13 bits within the existing
  uint64 state, moving derived content-lock bit positions by one. All masks
  and invalidation/reuse reset paths use the shared definitions. Rebuild
  core and modules together. Page/WAL formats and BufferDesc size are unchanged.
  CheckReadBuffersOperation asserts no pending conversion on complete returns.

| Access/acquisition path | Required handling |
| --- | --- |
| ReadBuffer / Extended / Normal / ZERO_ON_ERROR | Normal StartReadBuffer + WaitReadBuffers path completes conversion before return; zero-damaged/new pages have no legacy tuple payload. |
| StartReadBuffer(s), first cache hit | FinishReadBufferConversion before the false/ready return. |
| Already-pinned forwarded buffers | Re-enter StartReadBuffersImpl, test BM_VALID, then run the same conversion gate before delivery. |
| Race where another backend completes I/O before AsyncReadBuffers | The no-I/O return runs the gate for every accepted buffer. |
| WaitReadBuffers: own I/O, foreign I/O, partial reads, synchronous reads | Every completed range reaches the final conversion loop before return. |
| read_stream fast path, batching, queue wrap, forwarding | Only entries completed through Start/Wait may be returned; forwarded entries are resubmitted, not consumed directly. |
| ReadRecentBuffer and recovery's recent-buffer shortcut | Reject pending buffers and unpin; caller falls back to the ordinary read path. |
| ReadBufferWithoutRelcache / smgr read streams | Pending legacy pages require explicit by-value metadata; missing metadata raises ordinary ERROR without returning legacy tuple bytes. Current/overwritten pages need none. CREATE DATABASE supplies source metadata. |
| ZERO_AND_LOCK / ZERO_AND_CLEANUP_LOCK, new pages, relation extension | Explicit initialization/overwrite contract, not ordinary tuple access. Hash init callers initialize; redo WILL_INIT/FPI replaces contents under the lock. Normal later readers clear a conservative pending bit only after checking the replacement under lock. |
| Incremental redo / full-image redo | Normal reads use the gate; conversion's first-image WAL restores current layout via the overwrite path. Never interpret an unknown legacy heap using absent relcache metadata. |
| Checkpoint, bgwriter, flush, eviction, drop/truncate | Direct pins inspect metadata or write dirty pages under native locks. A newly read pending legacy page is clean; an explicit overwrite initializes before dirtying. Invalidation clears all flags. No tuple interpretation is performed by these scans. |
| Existing private pins, scan/index/contrib tuple consumers, parallel scans | A usable page originates from a completed read; retain native pin/content-lock rules. IncrBufferRefCount alone does not turn an unfinished I/O buffer into a readable page. |
| Local buffers / temporary relations | Old temporary files are not transferred by upgrade; local pages start in current format. Normal relation reads reject another backend's temporary relation. |
| pg_buffercache / autoprewarm direct descriptor scans | Inspect descriptors, statistics or residency; do not interpret heap tuple layout. pageinspect/visibility/amcheck/pgstattuple use normal reads and their content locks. |
| Direct smgr/file copies, base backup and unlogged reset | Physical copies may retain legacy bytes intentionally; subsequent buffered tuple reads still use the gate. Offline/raw bytes are not promised to be current heap layout. |

- `dev/tests/xid64_conversion_gate/check.py PREFIX BUILD OLDINSTALL` passes
  **17 assertions** with actual PG15 source: partial publication with two
  readers, recent-buffer rejection/acceptance, metadata-free ERROR twice and
  successful retry, abandoned physical I/O, explicit logged overwrite and
  metadata-free access afterward, plus waited/forwarded blocks in a split
  read. The overwrite uses XLogRegisterBlock and may conservatively retain
  markers; the next normal read clears pending after verifying the new page.
- Valid unfixed failure: /tmp/xid64-conversion-gate-q0h1gszu (2/6 failures).
  Corrected strengthened probe: /tmp/xid64-conversion-gate-kqeidup6 (17 passes),
  including observed BufferExclusive waiting by the competing reader.
  Earlier fixture library-lookup failure is not evidence of the race.
- Full world-bin and **full check-world on 12ff893c75f pass (exit 0)** with
  dependency tracking/assertions/injection points and WAL consistency
  checking: recovery **54/755**, AIO **4/597**, xid64 **9/67**, subscription
  **39/595**, core **246 tests**. Log:
  /tmp/pg19-xid64-final-0LJDks/check-world-conversion-pending.stdout.
  Source stayed fixed throughout; subsequent commits save artifacts/docs only.
- Actual PG15.19 and PG18.4 each pass the five upgrade/recovery suites,
  **98 assertions per source**, against this correction (both exit 0).
  Log: build directory check-legacy-conversion-pending.stdout. New module and
  core flag-layout compatibility was checked by the full dependency rebuild.
- All **27 patches** replay from 3421b154340 to 12ff893c75f byte-for-byte
  across **268 source paths**. Source correction and saved probe/artifacts
  remain separate commits on the alternate branch.
- **Needed for rebase to Tantor 18:** compare/backport atomic conversion
  readiness, including all normal/recent read gates, publication barriers,
  overwrite handling and the in-memory flag-layout rebuild requirement.

## IMPORTANT: immediate conversion WAL and revised issue list (2026-10-26)

The user requested WAL insertion immediately after backend conversion. The
current issue and PG18/Tantor 18 backport report is
[xid64-logical-issues.md](xid64-logical-issues.md). It supersedes earlier lists
where normal conversion waited for a later modifying operation.

- Physical input still completes in AIO. Legacy completion atomically sets
  BM_VALID, BM_CONVERSION_PENDING and BM_CONVERSION_NEEDS_WAL, and ends I/O.
  The flags live in BufferDesc, not disk page headers. BM_VALID means physical
  input succeeded; it does not authorize ordinary tuple use before the gate.
- BM_CONVERSION_PENDING is set by completion, before any backend starts
  conversion. It means conversion is unfinished. The exclusive content lock,
  not a flag transition at conversion start, chooses the sole converter.
- Rename BM_CONVERTED and its helper APIs to describe the remaining WAL
  obligation: BM_CONVERSION_NEEDS_WAL, BufferConversionNeedsWAL and
  MarkBufferConversionNeedsWAL. Neither name implies completed conversion.
- FinishReadBufferConversion validates/converts a private copy, prepares a
  forced XLOG_FPI outside the critical section, installs shared bytes, marks
  dirty, inserts WAL and sets the page LSN inside the critical section, then
  atomically clears both obligations before unlocking. WAL preparation before
  shared mutation keeps insertion-context errors outside that critical section.
- Normal permanent conversions no longer depend on a later UPDATE, VACUUM or
  hint write for their format-change image. The original hint/checkpoint/
  restart durability problem is prevented directly by conversion WAL.
- Keep deferred safeguards for recovery and permanent relations deliberately
  skipping WAL. Those conversions remain clean and retain the WAL obligation;
  a standby read followed by promotion can still require a later first image.
  Unlogged converted pages are dirtied without ordinary WAL and clear the WAL
  obligation. Do not remove fallback REGBUF_CONVERTED/NO_IMAGE/WILL_INIT handling
  or hint guards merely because normal conversions no longer use them.
- Backend MultiXact ownership, private-copy error safety, no-hints visibility,
  full-XID cache ownership, HOT roots, metadata-free read checks, atomic read
  gates, age arithmetic and freeze range validation remain necessary.
  Automatic normal-page freeze range handling is still open; the precritical
  SQL-error guard remains a mitigation, not a complete solution.
- The report also consolidates earlier lock-key, binary-XID, pruning-hint,
  TOAST, logical-decoding and upgrade backport items. Supplied PG18 fixes must
  be compared against the actual target revision to avoid duplicate backports.
- Fresh assertion/injection build passes world-bin. Actual PG15.19 and PG18.4
  sources each pass five upgrade/recovery suites, 102 assertions. The new case
  checks exactly one immediate XLOG/FPI for a frozen read-only legacy page and
  its standby replay, with checksums/hint WAL/full_page_writes off.
- The competing-reader probe passes 17 assertions and now also checks the
  post-read flags and page LSN. Full check-world on b0d9496f94f passes, exit 0,
  with WAL consistency checking: core 246 tests, recovery 54 files / 755
  assertions, AIO 597, xid64 67, subscription 595 and native pg_upgrade 145.
  Actual-source tests skip in the native run and pass separately as above.
- Follow-up patch pg19-immediate-conversion-wal.patch is saved in series.
  All 28 patches replay from 3421b154340 exactly across 268 source paths.
  Logs: /tmp/pg19-xid64-immediate-wal-{check-world,upgrade15,upgrade18,gate}.log;
  build: /tmp/pg19-xid64-immediate-wal. Earlier source gates remain historical.
- Rebuild core and extensions: helper symbols were renamed. There is no new
  page layout or WAL record format, and the flag bit positions are unchanged
  from 12ff893c75f. Save this correction as a separate follow-up patch in series.

## IMPORTANT: post-adaptation TODO execution (2026-10-26)

- The register now assigns explicit statuses to 43 distinct tasks and 16
  backport decisions. Historical duplicates and obsolete partial-build
  statements remain archived, not active work. User learning/discussion tasks
  are not marked completed on the user's behalf.
- Deferred live checks pass 30 assertions: real high-half apply-lock waiting,
  subtype/subscription separation and pg_locks, prepared MultiXact crash
  recovery through both outcomes, concurrent TOAST access and actual extracted
  conversion-helper checks.
- 38cfcc166f9 fixes a real native-PG19 source upgrade failure: eight-byte
  offsets retain short filenames. The fixture had encoded the same mistake.
  Native source/high-offset upgrade passes 10 assertions, PG15 wraparound
  retest 10, transfer modes 50, and corrected actual-reader/SLRU fixture 31.
  Already-xid64 source testing also completed before the directory restriction.
- d99f3a1486c implements the user-approved HSF tag H, explicit legacy-h
  rejection and exact payload length. 331942f4995 restores native future-horizon
  rejection with full XIDs. Fourteen live assertions test both directions,
  high XIDs, future xmin/catalog_xmin, malformed payloads and server availability.
  Old xid64 peers using h are intentionally incompatible; update peers together.
- e4dd3ab7bcb fixes mini0198(regress.c) helper decoding: skip non-normal
  line pointers, distinguish legacy by page version, decode full double-xmax
  and compare frozen xmin by flag. These are helper fixes, not freeze-policy
  changes. Supplied0010 carries the same defects in its relocated helper.
- 5d5fbdf0901 updates protocol.sgml and README.XID64 to the actual H payload
  and immediate backend-conversion/WAL contract. The protocol fragment's
  structure and fields were checked; runtime source is unchanged by that commit.
- The available supplied patch files are reviewed individually in the audit.
  Prepared-slot fix is already provided by native PG19 APIs. Debug APIs/test
  relocation and vendor WAL-history changes were not silently imported.
  The supplied baseline already fixes binary xidrecv and int64 rollback;
  both original v67 and supplied baseline still need mini0075(decode.c)'s fix.
- OPEN/PARTIAL: complete normal-page range handling beyond the SQL guard;
  old persisted two-phase record compatibility; natural later-segment auxiliary
  live coverage; mixed-format logical negotiation; MSVC and untested vendor
  catalog/WAL cases. Later user fixes remain WAITING_INPUT. The conflict-horizon
  learning explanation is in xid64-conflict-horizon.md.
- Final full check-world including 331942f4995's future-horizon guard passes,
  exit 0: core 246, recovery 54/755, AIO 597, xid64 67, subscription 595,
  native pg_upgrade 146. Documentation-only 5d5fbdf0901 leaves runtime unchanged.
  Final HSF probe passes 14 assertions. All 33 saved patches replay exactly
  from 3421b154340 across 270 paths. Full evidence/limits are in the audit.
- New probes: dev/tests/xid64_post_adaptation/check.py PREFIX BUILD;
  dev/tests/xid64_hsf_protocol/check.py PREFIX BUILD [VANILLA_INSTALL];
  dev/tests/xid64_upgrade_sources/check.py PREFIX BUILD VANILLA_INSTALL [TEST].
  Do not use the last two to access Tantor 18 directories under current scope.

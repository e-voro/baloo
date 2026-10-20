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
  two when reaching their numbers. Next unapplied: mini0094(predicate.c).
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

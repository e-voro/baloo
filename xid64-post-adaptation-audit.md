# Xid64 post adaptation TODO audit

Updated 2026-10-26. The authoritative status register is `../codex_todo.txt`.
The old file, including duplicate historical checkpoints, is preserved in
`codex_todo-history-20261026.txt`. Completed historical work is not scheduled
again merely because an older entry said the build was still incomplete.

## Scope and backport evidence

Per Evgeny's instruction, do not inspect or modify Tantor 18 directories.
Backport decisions use only the original v67 and supplied PG18/Tantor patch
files already inside this checkout. They describe required changes to that
patch lineage, not the contents of a current external target branch. Actual
backport application is outside this task's scope.

## Work completed during this audit

### Deferred live checks

`dev/tests/xid64_post_adaptation/check.py PREFIX BUILD` passes 30 assertions:

- Real production apply-lock APIs distinguish XIDs 100 and 4294967396.
  Identical full keys actually wait; releasing the low-XID peer does not
  release the high-XID waiter. Subtype/subscription keys and pg_locks output
  retain their identities.
- Prepared transactions contain two verified MultiXact members and survive
  crash restart through COMMIT PREPARED and ROLLBACK PREPARED.
- A repeatable-read snapshot retains its external TOAST value during five
  concurrent update/VACUUM rounds. The actual raw-xmax accessor reads TOAST
  pages; the new value survives crash restart.
- The actual extracted FillRelCheckValues helper is tested on normal,
  redirected/unused, legacy and full double-xmax tuples.

These prove current-format prepared-state recovery, not compatibility with
persisted two-phase files created before LOCKTAG changed size.

### Native PG19 offset filenames

The previously unrun native-PG19 source test failed: the reader attempted
`offsets/000000000000000`, while the real source had `offsets/0000`.
Eight-byte offset entries do not imply long offset filenames. Source offset
files remain short-named; native PG19 member files are long-named.

Fixed in `38cfcc166f9`, including correction of the standalone fixture, which
had encoded the same mistaken assumption. The 31-case fixture passes. A
vanilla PG19 source was built from local base `3421b154340` under /tmp; live
upgrade now passes 10 assertions, including real offsets above UINT32_MAX.
The generalized harness retains older wraparound coverage, retested with a
vanilla PG15 source. Already-xid64 sources skip the destructive xid32 fixture.

The width/filename correction is PG19 integration, not automatically a PG18
backport: a PG18 destination normally cannot upgrade from a newer major.

### Hot Standby Feedback

Both legacy and xid64 messages have 24 payload bytes plus one tag byte. Legacy
xmin=100/epoch=1 would be read as full XID 429496729601 instead of 4294967396.
Message length cannot discriminate these layouts.

Evgeny approved the distinct tag: `d99f3a1486c` sends/accepts H for full-XID
feedback, rejects legacy h before decoding, and checks the exact payload end.
Legacy walsenders reject H through their existing unknown-message dispatcher.
This intentionally requires updating existing xid64 feedback peers too; no
ambiguous legacy-h fallback is accepted.

The original xid64 patch also removed native rejection of future horizons.
Commit `331942f4995` restores that policy using full-XID bounds and removes
the stale 32-bit-wrap explanation. The live libpq client verifies accepted
full-width xmin, rejected tags in both directions, trailing-data rejection,
future xmin/catalog_xmin rejection and continued server availability.
The strengthened live HSF probe passes 14 assertions; the final full gate also passes.

### Imported SQL regression helpers

The deferred mini0198(regress.c) review found three defects:
non-normal line pointers were treated as tuples; legacy layout was confused
with current double-xmax layout; and xmin comparison used nonzero as a proxy
for unfrozen. `e4dd3ab7bcb` checks ItemIdIsNormal, selects legacy decoding by
page version, decodes current full XIDs and records the actual frozen flag.
The mark-committed loop also skips non-normal items. This is test-helper
correctness; it does not change tuple freeze eligibility in production.

The original supplied 0010 relocation keeps the same helper defects. Transfer
the fixes to whichever regression/module location a PG18 patch uses.

## Available supplied patch disposition

Paths below are under `patches/func/tt186xid64/`. No external target tree was
used to decide whether these fixes should be backported.

| Supplied file | Status and disposition |
| --- | --- |
| 0001-Xid64v63-adapted-for-REL_18_1.patch | BASELINE REVIEWED: comparison source, not a patch to apply over the v67 port. Binary receiver half-width and GUC rollback are already corrected here; TOAST, old-tuple length and other recorded defects remain. |
| 0002-catalog_constants_and_corrections_of_test_integrity.patch | PARTIAL: deterministic restrict-key behavior is present. Vendor HAVE_INT64_XID and WAL-magic/release-history changes were not imported into native PG19. |
| 0003-Fix-build.patch | NOT REQUIRED: its commented-out PG18 slot helpers are not an appropriate replacement for native PG19 atomic slot APIs. |
| 0004-Create-and-compile-test_advance_xact-which-is-intend.patch | OPTIONAL, NOT APPLIED: test-only counter-advance APIs/test reorganization. Existing focused probes and initdb tests provide the required checks without adding those production hooks. |
| 0004-fix_prepared_xact.patch | NATIVE EQUIVALENT VERIFIED: PG19 retains PreparedXactOldestMemberMXactIdSlot at prepare/recover/finish. Live MultiXact prepare/crash/commit/rollback checks pass. |
| 0005-Ascertain-whether-a-cluster-supports-xid64-during-a-.patch | ADAPTED: source XID-format dispatch and upgrade checks; later PG19/native-format corrections are additional. |
| 0006-Rename-12-symbol-long-SLRU-filenames-from-old-cluste.patch | ADAPTED: normalize already-xid64 source names for destination copy. A disposable PG18.6 xid64 source upgrade passed before the directory-scope restriction; no further directory access is authorized. |
| 0007-Dealing-with-zeroed-_fsm-and-_vm-pages-in-pg_upgrade.patch | ADAPTED: ordinary auxiliary conversion and zero pages; later-segment checksum/swap handling is additional. |
| 0008-Upgrade-and-fix-page-conversion-for-the-new-AIO-syst.patch | ADAPTED/SUPERSEDED IN PART: by-value metadata retained; worker conversion and deferred normal WAL superseded by backend conversion/immediate WAL. |
| 0009-Fix-the-handling-of-Default-Char-Signedness-dependin.patch | NOT PORTED AS A WHOLE: vendor catalog-prefix/default-char-signedness compatibility beyond tested sources needs separate review. Existing live results do not prove every pre-PG18 vendor catalog works. |
| 0010-Create-a-test-for-page-conversion-mechanics.-Group-t.patch | PARTIAL: test relocation/extra module not adopted. Existing regression helpers, xid64 TAP and cross-source conversion tests are used; helper bugs found during this audit are fixed. |
| 0011-Fix-pg_upgrade-xact-conversion-for-nonzero-epoch.patch | ADAPTED: source CLOG addressing strips the epoch; live epoch=1 upgrade is covered. |
| 0011-fix-pg_combinebackup-012-vm-consistency.patch | ADAPTED: filler size 192; complete backup-consistency suite passed. |
| 0012-Support-Xid64-mxacts-in-pg_upgrade-and-in-page-conve.patch | ADAPTED/EXTENDED: source widths, members, destination counters and index invalidation; wrapped per-object horizons and native PG19 filenames required additional corrections. |
| 0013-Add-test-for-TTDB-2707-double-xmax-vacuum.patch | ADAPTED: PG19 upgrade test 011, using actual page-header checks. |
| 0013-Fix-XID-decoding-for-double-xmax-pages.patch | ADAPTED/EXTENDED: layout distinction retained; private no-hints/cache ownership added separately. |
| 0014-Pass-source-relation-conversion-metadata-to-CREATE-D.patch | ADAPTED: by-value source metadata, PG19 batching and current worker options. |
| 0015-Preserve-converted-page-images-for-relcache-less-rec.patch | ADAPTED/EXTENDED: image precedence and marker lifecycle retained; PG19 prune/LSN integration, hint durability and immediate WAL are additional. |
| doc.patch | OPTIONAL, NOT APPLIED WHOLESALE: vendor release documentation is not the current PG19 contract. README.XID64 and adaptation reports record the implemented design. |
| zzz0002-Logical-replication-support.patch | REJECTED: variable-length GID makes BEGIN PREPARE's remaining-length heuristic unsafe. Explicit logical protocol negotiation remains open. |

Only the baseline patch above changes decode.c, and it still calculates
tuplelen before subtracting both INIT_PAGE page bases. None of the available
later supplied patches fixes it. Thus mini0075(decode.c)'s correction remains
a backport requirement for that patch lineage. Recheck any later fixes Evgeny
provides; unavailable files are not marked reviewed.

## Retained open or limited items

- Normal-page freeze replacements: SQL-error guard protects the server, but
  complete range handling needs a coherent base/layout/WAL design. A valid
  replacement and all surviving IDs may span more than the short range;
  rebasing alone cannot always solve it, and double-xmax cannot discard an
  active/recent xmin. Do not skip a required plan to advance freeze horizons.
- Later-segment auxiliary files: real checksum/filesystem fixtures cover
  segment numbering; no natural large auxiliary-fork live test is claimed.
- Pre-fix two-phase state: current prepared files are tested; compatibility
  with old persisted record sizes is a deployment/design issue.
- Mixed-format logical protocol, MSVC/Windows and untested vendor catalog/WAL
  histories remain separate work. HSF tag protection is not general logical
  negotiation or universal physical-format compatibility.
- Evgeny's learning/discussion tasks remain user tasks. The conflict-horizon
  implementation trace is in `xid64-conflict-horizon.md`.
- Actual PG18/Tantor 18 backport application is explicitly outside scope.

## Validation and logs

- Post-adaptation live probe: 30 assertions, including actual static helper.
- Native PG19 source basic/high-offset upgrade: 10 assertions.
- PG15 basic/wraparound upgrade harness: 10 assertions.
- Live transfer modes with vanilla PG15 source: 50 assertions.
- Earlier already-xid64 source check: table/member comparisons pass;
  destructive xid32 scenario intentionally skips.
- Source-offset fixture: 31 checks with actual reader/writer/SLRU I/O and UBSan.
- Full gate after tag/reader/helper fixes passes: core 246, recovery 755,
  AIO 597, xid64 67, subscription 595, native upgrade 146.
- Final HSF probe: 14 assertions, including stable observations for ignored
  future horizons (not just the brief timestamp/xmin publication window).
- Final full check-world with WAL consistency checking passes, exit 0, on
  runtime `331942f4995`: core 246 tests; recovery 54 files / 755 assertions;
  AIO 597; xid64 67; subscription 595; native pg_upgrade 146. Documentation-only
  commit `5d5fbdf0901` does not change the tested runtime.
- All 33 patches replay exactly from `3421b154340` to `5d5fbdf0901` across
  270 paths. Source fixes, test probes and user-supplied originals remain
  separate; original patches are not overwritten.
- Register totals: 34 DONE tasks, two PARTIAL, three OPEN, one WAITING_INPUT,
  two USER_TASK and one OUT_OF_SCOPE. Sixteen backport decisions have separate
  statuses; the vendor-history review remains open among those decisions.

Logs: `/tmp/pg19-xid64-{post-adaptation,todo-targeted,hsf-final,upgrade-native19-offsets,
upgrade-transfer-modes,todo-wrap-regression,todo-check-world,todo-final-check-world}.log`.
Commands/results are also appended to codex.log. These are test runs on disposable
clusters; no existing database directories were upgraded or reset.

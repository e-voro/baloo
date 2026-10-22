# xid64 PostgreSQL 19 rebase: handoff and validation

## Current status (2026-10-22)

Latest source 12ff893c75f corrects a confirmed early-return race during page
conversion publication using an atomic pending flag. The targeted access-path
probe passes 17 assertions; full check-world and both actual-source upgrade
runs pass on this correction (exit 0). The complete access matrix and test
limits are in the pending-access re-audit section of AGENTS.md.

**0005 is fully adapted and applied**, including all 215 mini steps.
The main series through 0012 is applied or explicitly superseded. Follow-up
fixes are saved separately in `patches/func/pg19xid64evoro1900/series`;
the original v67 patches and original branches remain preserved. Active source
and Baloo branch: `pg19beta3xid64_CODEX_OVERNIGHT_20261021`.

- Source 12ff893c75f passes a fresh full build and check-world with assertions,
  TAP, injection points and WAL consistency checking (recovery 755 assertions).
- Actual PG15.19 and PG18.4 each pass five cross-version upgrade suites,
  98 assertions per source. This does not cover every source layout or --swap.
- 19da20487ca protects a confirmed normal-page freeze range PANIC with a
  precritical SQL error. Its live probe passes 10 assertions; the subsequent
  full gate and both actual-source upgrade runs pass (exit 0). Automatic
  handling of incompatible ranges remains open.
- Latest applied-fix explanations, ownership audit, proposals, test limits and
  backport tasks are highlighted in `AGENTS.md` and root `codex_todo.txt`.

## Historical report

The remaining sections describe older checkpoints and their then-pending work.

Updated: 2026-09-25 (Asia/Irkutsk).

## Current checkpoint

Patches 0001–0004 are applied. TransactionId is still uint32; the main storage
conversion in patch 0005 has not been applied. Patch 0004 is deliberately
independently buildable: built-in freeze-age setting/reloption migrations were
moved into working patch 0005, beside their backing-storage widening.

Latest aggregate source commit: 8ca324058af (patch 0004), preceded by
c01491a5684 (separate BALOO update). Patch 0003 is 7e42cdce0f1, preceded by
cac3384a446 (separate BALOO update). Baloo patch/helper revision: 5ba14d3.
The full world-bin build, focused GUC/reloption probe and final check-world
passed on the identical source tree before aggregation. Recovery 027 passed
with wal_consistency_checking=all verified live on primary and standby.

On 2026-09-25 the user requested aggregation. Both mini-step histories are
preserved in backup branches (see below). Each aggregate was created with
git am from the adapted mail patch, retaining its original message/author.
The complete tracked tree after aggregation exactly equals ead7bcc4da2.
No source retest was needed for this history-only operation.

## Patch 0001 historical checkpoint

The first patch adapts 56 files for 64-bit XID formatting. Its full build and
check-world passed with WAL consistency checking, including the multixactfuncs
correction folded into the formatting commit. The following history and
validation sections describe that checkpoint; later dated sections describe
patches 0002–0004.

## Repository and history

- Main branch: pg19beta3xid64.
- Base: 3421b154340 (vanilla beta3 plus Baloo import and patch copies).
- 316742b105e: BALOO Update Baloo with adapted xid64 output-format patch.
- f4c7dc9c16a: Use 64-bit format to output XIDs.
- The formatting commit author is Evgeny Voropaev <evorop@gmail.com>, also
  listed in its message. Its author date is 2026-09-23T10:51:20+08:00;
  committer date is 2026-09-23T14:13:02+08:00.
- Backup branch pg19beta3xid64_CODEX_MINISTEPS_0001-Use-64-bit-format points to
  bfbf9c1b2eb and preserves the original mini-step commits.
- Baloo is a separate Git submodule, on branch balooXid64v67, patch revision
  d4151f99160bd5803977b255b2e253ea06ec7528; later documentation commits do not
  change the tested source or adapted patch.
- Original series: baloo/patches/func/pg19xid64v67/.
- Working series: baloo/patches/func/pg19xid64evoro1900/.
- Adapted file: v1900-0001-Use-64-bit-format-to-output-XIDs.patch.

The source was aggregated by resetting to the base and using git am on the
adapted mail patch. Authorship was then updated and the separate Baloo pointer
commit moved before the source commit. The adapted patch mail metadata still
has Maxim Orlov and the original v67 subject/date; the later commit metadata
change did not rewrite that file's mail headers.

## Adaptations

| Area | Change |
| --- | --- |
| amcheck | Preserve PG19 offset %d formatting and removed redundant casts; widen only XID output. |
| heapdesc | Drop obsolete xl_heap_visible formatting hunk. PG19 removed XLOG_HEAP2_VISIBLE (a881cc9c7e8); prune records retain conflict-horizon formatting. |
| Multixact offsets | Preserve native uint64/PRIu64 offsets introduced by bd8d9c9bdfa, direct comparisons, and removal of offset wraparound stop limits. |
| Multixact truncation | Preserve oldestMulti/oldestOffset layout introduced by c4b71e6f60c; discard removed range-field diagnostics. |
| multixact.c | Preserve slot helpers, SetOldestOffset and PG19 behavior; update surviving and new corruption/I/O diagnostics and formatted remaining-ID counts. |
| SLRU errors | Remove slru.c formatting hunks; f9de9bf302d moved subsystem details to callbacks. Widen callback messages in clog.c, commit_ts.c, subtrans.c; multixact callbacks handled separately. |
| Checkpoint output | Preserve logical-decoding/checksum additions, SQL column shifts and PRIu64 offsets in xlogdesc, xlogrecovery, pg_controldata and pg_resetwal. |
| varsup/xact | Refresh context for percentage diagnostics and removed casts; preserve OID, command-ID and epoch formatting. |
| Logical replication | Widen XIDs in expanded conflict diagnostic variants; preserve new details. Refresh reorderbuffer context for removed relid argument. |
| pg_upgrade | Keep copy and rewrite_multixacts paths and their offset values; widen -m ID arguments and XID/SQL formatting, preserving PRIu64 offsets. |
| pg_waldump | Replace unsafe %llu scanf pointer cast with strtoull temporary, full decimal-input validation, ERANGE and MaxTransactionId checks, then assignment. Keep wider XID output. |
| xid_wraparound | Widen printed XID components and preserve epoch output. |
| multixactfuncs build fix | Original patch used PRIu64 with still-32-bit IDs. Replace with %llu and unsigned long long casts for invalid-ID error and member output. Source fix folded into formatting commit; parent patch committed in Baloo. |

## Validation

Build directory: /tmp/xid1900-checkworld (out-of-tree).

Configuration:

```sh
/path/to/source/configure --enable-tap-tests --enable-cassert --enable-debug \
  --enable-injection-points CFLAGS='-O0 -g -Werror=format'
make -j6 world-bin
make -j6 check-world PG_TEST_EXTRA=wal_consistency_checking
```

- First full build exposed the two multixactfuncs mismatches; corrected build passed.
- First check-world attempt failed because sandbox permissions blocked sockets.
  It was rerun with approved escalation, and the complete command exited 0.
- Recovery t/027_stream_regress.pl reported ok. PG_TEST_EXTRA was supplied to the
  complete make invocation; this test explicitly sets wal_consistency_checking=all
  when that token is present. Successful test cleanup removed its temporary node
  configuration, so it is not available for a post-run file inspection.
- Recovery suite: Files=54, Tests=755, Result: PASS (504 wallclock seconds).
- check-world-unsandboxed.log contains no not-ok/FAILED/Bail-out/Error matches.
- Earlier targeted compilations included MULTIXACT_DEBUG and -Werror=format.
- pg_waldump executable: 13 CLI cases passed (0, 1, uint32 maximum accepted;
  out-of-range/overflow, signs, whitespace, empty input and suffixes rejected).
  Valid inputs reached WAL discovery; this was parser validation, not a WAL fixture test.
- Final adapted parent patch was applied to an isolated copy of base 3421b154340;
  all 56 resulting files match the tested working tree exactly. Diffstat refreshed.
- Full regression success concerns this configured build, not optional unconfigured
  features or every opt-in PG_TEST_EXTRA suite (e.g. xid_wraparound extra tests).

Evidence: baloo/codex.log (real-time stream), plus build.log, build-retry.log,
check-world.log and check-world-unsandboxed.log under the build directory.
Temporary /tmp artifacts may disappear; retain codex.log for durable evidence.

## Pending work and constraints

1. Completed: tested multixactfuncs.c correction folded into f4c7dc9c16a.
2. Completed: adapted patch saved in Baloo d4151f9, referenced by the preceding
   separate BALOO commit 316742b105e.
3. Report and baloo/AGENTS.md are saved in a separate CODEX: documentation
   commit. codex.log remains an untracked, continuously appended execution log.
4. Future storage-changing patches must review rewrite_multixacts compatibility;
   formatting and current-tree regression success do not establish full xid64
   upgrade compatibility.
5. The user subsequently authorized continuing the series and adapting new cases;
   see the dated checkpoints below.

No Baloo helper implementation was modified. Actual helper is devcfgli.sh,
not devcli.sh. Mini cache reflects historical incremental application; mini0021
contains three callback diffs to preserve numbering. Never blindly regenerate
and replay the old cache on the already-patched branch. The parent patch is the
reproducible complete artifact.

## Final fix integration

The full-build correction in src/backend/utils/adt/multixactfuncs.c is part of
f4c7dc9c16a, not a separate source fix commit. Both affected outputs now use
%llu with unsigned long long casts, making formatting valid for the current
32-bit IDs and the intended 64-bit transition. The corresponding adapted patch
was saved in Baloo d4151f9. Applying that committed patch to base 3421b154340
reproduces every one of the 56 source files in the formatting commit exactly.

The MINISTEPS branch is historical and predates this final build-driven fix.
Use the adapted parent patch and current formatting commit for future work.
The preceding BALOO commit references the corrected patch revision; subsequent
CODEX: documentation commits remain separate from PostgreSQL source changes.

## Patch 0002 historical progress (2026-09-23)

Base: 2244806b6ce. Working patch:
v1900-0002-Use-64-bit-FullTransactionId-instead-of-Epoch-xi.patch.
All ten mini steps (0000–0009) applied. Three context failures were adapted:
xlogdesc retains logical decoding/checksum fields and PRIu64 offsets; backend
pg_controldata retains shifted columns; frontend pg_controldata retains offsets.
The main build passed. Test preparation found a stale epoch argument in the
xid_wraparound NOTICE call; it was removed in source, mini0009 and the parent
patch, and folded into the last mini commit. check-world is running again with
PG_TEST_EXTRA=wal_consistency_checking. Do not interpret patch 0001's PASS as
validation of patch 0002. Aggregation and final results are pending.

## Patch 0002 completed (2026-09-24 checkpoint)

The current history contains aggregate source commit 44f020d606d. The final
world-bin build and full check-world passed with
PG_TEST_EXTRA=wal_consistency_checking. Recovery: 54 files, 755 tests,
including 027_stream_regress.pl. Live inspection during that run confirmed
wal_consistency_checking=all in both primary and standby configuration.
The xid_wraparound stale epoch argument fix is included.

## Patch 0003 adaptation (2026-09-24)

Base: 44f020d606d. Original six mini-patches applied as commits ed9a85c78aa
through 66b54d999e9. The adapted mail patch is
v1900-0003-Use-64-bit-SLRU-pages-in-callers.patch.

| Case | Adaptation and reason |
| --- | --- |
| Removed SimpleLruInit call sites | Set SlruOpts.long_segment_names=true in PG19 SimpleLruRequest callers for clog, commit_ts, subtrans and predicate locks. Preserve the other named options and callbacks. |
| Multixact initialization | Widen offsets names; members names are already long in PG19, so discard that obsolete change. |
| Backup corruption test | Change the actual pg_xact file removed by the test from 0000 to 000000000000000. The existing prefix regex still matches. |
| New PG19 upgrade writer | Set rewrite_multixacts offsets writer to use long names, matching the destination server; members writer already does. Preserve old input readers and pre-v19 test fixtures using short names. |

The original patch explicitly leaves SLRU upgrade support as a TODO. Later
patch 0005 supplies conversion routines; adapting them to PG19 remains necessary.
Same-version pg_upgrade tests are not evidence of old-version conversion.
The initial six-file world-bin build passed. Its full check-world completed
with one failing suite: test_slru attempted to unlink a short-named offsets
file. The fixture now generates %015X filenames and removes the 15-zero file.
Recovery 027 and the pg_upgrade suite passed in that run. The corrected source
rebuilt successfully, and targeted test_slru passed (one SQL regression and
two TAP files / 20 tests). Final full validation includes patch 0004 below.

Final patch 0003 source checkpoint: 7ccacabbee9, including writer correction
2f08dd51fce. Baloo patch revision d2044cd. Exact replay against 44f020d606d
matched all eight changed files. Existing pg_upgrade tests used the same
version; old-version conversion remains unvalidated.

## Patch 0004 preliminary review

Only an isolated copy under /tmp/xid1900-0004-adapt has been edited so far.
PG19 context repairs preserve the new ternary reloption type and nonnull
annotations, use anonymous-union fields (int64_val, not values.int64_val), and
retain the newly inserted autovacuum freeze-score GUC entries.

There is also an original-series dependency: patch 0004 declares 64-bit GUC
pointers while backing globals remain int until 0005, and moves freeze
reloptions to int64 before the target storage/mapping is widened in 0005.
Do not run a server built with that intermediate state or claim standalone
validation. Resolve the patch boundary or validate together with 0005.

## Patch 0004 implementation and fixed cases (2026-09-24)

Base: 1502ac9ee0b (same PostgreSQL source as final patch 0003).
Nine original mini steps (0000–0008) applied as 83f813eebc5 through 2f6e7cf82d4.
Follow-up source fixes: fd2483c6a65 and 139c6d72c8e. The adapted mail patch
covers nine files. Baloo 5ba14d3 stores it, the working patch 0005 boundary
adjustment, and the reproducible focused probe.

| Case | Resolution |
| --- | --- |
| PG19 anonymous relopt_value union | Use int64_val directly; preserve ternary options and existing APIs. |
| Removed bits32 typedef | Declare/define add_int64_reloption with uint32 and const description, matching PG19. |
| Existing-series dependency on 0005 | Keep current int freeze-age settings/storage in 0004. Move their GUC declarations and reloption table migration into 0005, together with its original storage/type changes. No widening of allowed freeze ages before XIDs themselves are widened. |
| Incomplete GUC support | Implement the already-declared DefineCustomInt64Variable using PG19 initialization; move --describe-config support forward from 0005 into the infrastructure patch. |
| Obsolete GUC structure casts | Use embedded _int64 fields in pg_settings, current-value output and reset-value output; casts to a former standalone config struct read the wrong memory. |
| Incorrect parsing of fractions/units | Round the parsed double rather than the preliminary integer; preserve exact integer values with trailing whitespace. |
| Optional error hint | Check hintmsg before writing the overflow hint; reloption callers intentionally pass NULL. |
| Rollback truncation | Restore from newvalue.val.int64val, not intval. The focused probe detected this at INT64_MAX after SET LOCAL/ROLLBACK. |
| Serialized-state size at INT64_MIN | Use direct range comparisons instead of negating a signed minimum value. The old expression could overflow and underestimate the required buffer. |

Focused probe: baloo/dev/tests/xid64_guc/run.sh PREFIX. It builds a temporary
loadable module, starts an isolated local cluster, executes assertions and
stops the cluster on exit. Its artifacts remain under /tmp/xid64-guc-probe.*.
It checks exact signed limits, decimal rounding, unit conversion, rejected
syntax/overflow with and without an error-hint pointer, pg_settings bounds,
reloption storage, transaction rollback, RESET and minimum-value serialization.
The first probe failed on rollback and the corrected probe passed.

The first patch 0004 build found the obsolete bits32 typedef; the corrected
world-bin build passed with -Werror=format. The first full test run was stopped
(exit 130) after the focused probe exposed rollback truncation. A leftover test
standby was stopped before restarting. Final check-world evidence is in
/tmp/xid1900-checkworld/check-world-0004-final.log and the live codex.log.

## Remaining patch 0005 work

v1900-0005-Use-64-bit-XIDs.patch is renamed and adjusted only for the patch
boundary described above; it is NOT fully rebased or applied. Its working-copy
reloptions/GUC diffs include the deferred migrations, and its help_config hunk
was removed because that support is already in 0004. Original v67 files remain
unchanged in pg19xid64v67. Preflight reports many other PG19 context/functional
conflicts. Split and adapt it per file; review PG19 heap/WAL and multixact
upgrade behavior carefully. Do not represent this saved intermediate patch as
ready to apply, and do not replay 0003/0004 mini scripts on the current branch.

Upstream history references checked locally: 2e0943a8597 introduces the new
SLRU shared-memory request API; bab2f27eaaa removes bits* typedefs;
69f98fce5bfb makes the reloption value union anonymous; 4d6a66f67581 introduces
ternary reloptions; a13833c35f9 reorganizes GUC structs. These explain the PG19
API/layout adaptations separately from bugs already present in the v67 patch.
Patch 0005 now has 215 generated per-file minis; only the two relocated
migration diffs were verified to apply on final patch 0004. None were applied.

## Final validation and aggregation (2026-09-25)

The final make -j6 check-world PG_TEST_EXTRA=wal_consistency_checking completed
with exit 0. Recovery: 54 files / 755 tests, 551 seconds, including 027. No
not-ok/FAILED/Bail-out/Error matches occurred in check-world-0004-final.log.
The combined replay of adapted patches 0002, 0003 and 0004 against
2244806b6ce reproduced all 27 affected source files exactly.

Backup branches:
- pg19beta3xid64_CODEX_MINISTEPS_0003-Use-64-bit-SLRU-pages-in-callers
  points to 1502ac9ee0b, as explicitly requested.
- pg19beta3xid64_CODEX_MINISTEPS_0004-Use-64-bit-GUCs
  points to ead7bcc4da2, the pre-aggregation final 0004 tip.

New main-branch order after 44f020d606d:
1. cac3384a446 — BALOO Save adapted xid64 FullTransactionId and SLRU patches.
2. 7e42cdce0f1 — Use 64-bit SLRU pages in callers.
3. c01491a5684 — BALOO Save adapted int64 GUC patch and focused validation probe.
4. 8ca324058af — Use 64-bit GUCs.

Automatic review rejected the initial hard-reset command because of possible
loss of dirty documentation. No command in that rejected call ran. Safety
copies and checksums were made under /tmp/xid1900-before-aggregation-2m4xf1mi;
backup branches were then created, and reset --keep --no-recurse-submodules
was approved and used. It refuses to overwrite local edits. The documentation
was verified byte-identical and the old log prefix preserved before updating
this report. Source commits contain only source files; BALOO commits contain
only the submodule pointer. The requested handoff documentation remains a
separate CODEX: commit.

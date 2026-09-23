# xid64 PostgreSQL 19 rebase: handoff and validation

Updated: 2026-09-23 (Asia/Irkutsk).

## Scope and result

The first v67 patch, “Use 64-bit format to output XIDs”, has been adapted to
PostgreSQL REL_19_BETA3. All 56 numbered mini steps (0000–0055) are complete.
This is the formatting prerequisite, not completion of the xid64 series:
TransactionId is still uint32. Patch 0002 and later have not been started.

The full world-bin build and check-world passed on the current working tree,
including recovery/t/027_stream_regress.pl with WAL consistency checking enabled.
The tested tree includes the multixactfuncs.c correction described below, now
folded into the formatting commit. HEAD contains the tested source tree.

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
5. Await user instruction before starting patch 0002.

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

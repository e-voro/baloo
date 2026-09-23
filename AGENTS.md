# Instructions for future AI instances

Read baloo/xid64-rebase-report.md for the current checkpoint and adaptation map.
Read the tail of baloo/codex.log, inspect git status in both the main repository
and baloo, and inspect branch history before changing anything. The report is
historical; verify it against the actual checkout.

## User workflow and authorization

- Follow the user's current command. Do not start the next patch without authorization.
- When asked to continue the series, fix familiar context/formatting issues already
  explained to the user. If a new kind of problem appears, report it and stop
  adaptation until subsequent instructions. Do not silently broaden scope.
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
- Patch 0002 remains unstarted. Await the user's command.

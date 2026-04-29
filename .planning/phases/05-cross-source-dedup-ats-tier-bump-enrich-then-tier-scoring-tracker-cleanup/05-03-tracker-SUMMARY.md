---
phase: 05-cross-source-dedup-ats-tier-bump-enrich-then-tier-scoring-tracker-cleanup
plan: "03"
subsystem: tracker
tags: [con-13, con-14, con-20, tracker_utils, dedup, user-columns]
requirements: [CON-12, CON-13, CON-14, CON-20]

dependency_graph:
  requires: ["05-01"]
  provides: ["extract_linkedin_job_id", "extract_dedup_key", "user_extra_headers 4-tuple"]
  affects: ["scripts/tracker_utils.py", "tests/test_tracker_phase5.py"]

tech_stack:
  added: []
  patterns:
    - "LinkedIn-anchored regex — two-pass: currentJobId querystring then /view|search/ path"
    - "4-tuple return from load_tracker threads user_extra_headers to _write_tracker"
    - "break → continue in _write_tracker inner loop (write-through instead of drop)"

key_files:
  modified:
    - scripts/tracker_utils.py

decisions:
  - "extract_job_id kept as deprecated alias (delegates to extract_linkedin_job_id) — test_detection.py does NOT import it, but keeping avoids any external caller breakage; flagged for Phase 6 removal"
  - "rebuild() migrated to extract_dedup_key so ATS/career-page rows dedup by URL string (not a false 10+ digit match)"
  - "Two-pass regex for extract_linkedin_job_id: currentJobId= querystring first, then /view|search/path — handles both LinkedIn URL forms"
  - "_write_tracker creates a fresh workbook (existing design); user_extra_headers re-emitted from load_tracker discovery so round-trip is lossless"

metrics:
  duration: "~25 min"
  completed: "2026-04-28"
  tasks_completed: 3
  files_modified: 1
---

# Phase 05 Plan 03: tracker_utils Surgical Fixes — CON-13/14/20 Summary

**One-liner:** LinkedIn-anchored extract_linkedin_job_id + extract_dedup_key split, skipped_stale → flagged_stale_count local rename, and _write_tracker user-column write-through replacing the silent break data-loss bug.

## Tasks Completed

| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | CON-13: Split extract_job_id into extract_linkedin_job_id + extract_dedup_key; migrate 4 callers | 34643ea | DONE |
| 2 | CON-14: Rename local var skipped_stale → flagged_stale_count; dict key "flagged_stale" preserved | 34643ea | DONE |
| 3 | CON-20: load_tracker 4-tuple + _write_tracker user-column write-through | 34643ea | DONE |

Note: all three tasks modify the same file (scripts/tracker_utils.py) so they share one atomic commit.

## What Was Built

### CON-13 — extract_linkedin_job_id + extract_dedup_key

Two new public functions replace the generic `extract_job_id`:

- `extract_linkedin_job_id(url)` — anchored to `linkedin.com` only; returns `int` or `None`. Fixes false stale-flagging where ATS career-page URLs like `https://acme.com/careers/job/2024100912345` matched the old `\d{10,}` pattern and incorrectly tripped the stale-flag.
- `extract_dedup_key(url)` — returns LinkedIn job ID as string for LinkedIn URLs; returns lowercased+stripped URL for all others. Used by `rebuild()` for cross-source deduplication.

Four callers migrated:
- `load_tracker`: `extract_job_id` → `extract_linkedin_job_id`
- `append_rows`: `extract_job_id` → `extract_linkedin_job_id`
- `is_stale_by_id`: `extract_job_id` → `extract_linkedin_job_id`
- `rebuild`: `extract_job_id` → `extract_dedup_key`

`extract_job_id` kept as a deprecated alias (delegates to `extract_linkedin_job_id`) for back-compat; marked for removal in Phase 6.

### CON-14 — Local var rename (Pitfall 6 invariant preserved)

`skipped_stale` → `flagged_stale_count` in `append_rows`. The returned dict key `"flagged_stale"` is unchanged — SKILL.md Step 7 reads `result["flagged_stale"]` and would break if the key changed. Misleading comment "Still add it, but flagged — user can decide" removed.

Verification: `grep -c 'skipped_stale' scripts/tracker_utils.py` → 0. `grep -c '"flagged_stale"' scripts/tracker_utils.py` → 2 (dict key + inline comment documenting the invariant).

### CON-20 — User-column preservation (Pitfall 2 fix)

The primary data-preservation fix. Before: `_write_tracker` had `if col > len(HEADERS): break` which silently dropped everything past column 16 on every rewrite. After:

1. `load_tracker` reads row 1 beyond `len(HEADERS)` to discover user-added header names → `user_extra_headers: List[str]`
2. `load_tracker` returns 4-tuple `(wb, rows, job_ids, user_extra_headers)` — all callers updated
3. `_write_tracker(filepath, rows, user_extra_headers=None)` re-emits user headers in row 1 cols past `len(HEADERS)` with canonical header formatting
4. Inner loop: `break` replaced with `continue` — user-column cells get base formatting (fill, border, alignment) but skip scout-specific formatting (hyperlink, tier bold, score center)

Callers updated: `get_dedup_set`, `append_rows`, `rebuild` all unpack 4-tuple and thread `user_extra_headers` through to `_write_tracker`.

## Test Results

```
9/9 Phase 5 tracker tests: PASS
37/37 Phase 1-4 regression tests: PASS
```

Phase 5 tests:
- test_extract_linkedin_job_id_linkedin_url: PASS
- test_extract_linkedin_job_id_non_linkedin_returns_none: PASS
- test_extract_linkedin_job_id_search_path: PASS
- test_extract_dedup_key_linkedin_returns_id_string: PASS
- test_extract_dedup_key_non_linkedin_returns_url: PASS
- test_extract_dedup_key_none_returns_none: PASS
- test_flagged_stale_count_var: PASS
- test_user_column_preservation_round_trip: PASS
- test_user_column_preservation_after_multiple_appends: PASS

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written, with one minor deviation:

**1. [Rule 1 - Naming] Comment references to 'skipped_stale' removed from inline annotations**
- **Found during:** Task 2 verification
- **Issue:** After renaming the local var, two inline comments still contained `skipped_stale` as text, causing `grep -c 'skipped_stale'` to return 2 instead of 0
- **Fix:** Rewrote the comments to remove the old name (replaced with cleaner CON-14/Pitfall 6 annotations)
- **Files modified:** scripts/tracker_utils.py
- **Commit:** 34643ea

**2. [Plan note] CON-12 is a co-ownership marker**
- Per PLAN.md objective note: the actual CON-12 work (chrome-setup.md multi-selector + retry rule) is owned by Plan 05-05. This plan's CON-12 listing is a traceability marker only. No CON-12 implementation work in this plan.

## Known Stubs

None — all functionality fully implemented and tested.

## Threat Flags

No new network endpoints, auth paths, file access patterns, or schema changes introduced. All changes are internal to tracker_utils.py's file I/O logic.

## Self-Check: PASSED

- [x] scripts/tracker_utils.py modified (not replaced — surgical edits)
- [x] extract_linkedin_job_id and extract_dedup_key functions exist (grep count: 2)
- [x] extract_job_id kept as deprecated alias
- [x] skipped_stale fully gone (grep count: 0)
- [x] dict key "flagged_stale" preserved (grep count: 2 — key + documenting comment)
- [x] _write_tracker has no `col > len(HEADERS): break` — replaced with continue
- [x] load_tracker returns 4-tuple with user_extra_headers
- [x] user_extra_headers referenced 12 times in file (load, thread, write)
- [x] Commit 34643ea exists: `git log --oneline | grep 34643ea` confirms
- [x] 9/9 Phase 5 tracker tests GREEN
- [x] 37/37 Phase 1-4 regression tests GREEN

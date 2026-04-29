---
phase: 03-detection-scout-detect-skill-lazy-inline-detect-dead-doc-ref-cleanup
plan: "03"
subsystem: scout-run-skill
tags: [scout-run, lazy-inline-detect, step-2b, con-08, dead-references, doc-cleanup, DET-04, DET-07]
dependency_graph:
  requires: ["03-01"]
  provides: [step-2b-lazy-inline-detection, con-08-dead-ref-cleanup]
  affects: [skills/scout-run/SKILL.md, skills/job-scout/SKILL.md, skills/job-scout/references/search-config.md]
tech_stack:
  added: []
  patterns: [detect-one-lazy-inline, d01-sentinel-none, d05-deferred-write-back]
key_files:
  created: []
  modified:
    - skills/scout-run/SKILL.md
    - skills/job-scout/SKILL.md
    - skills/job-scout/references/search-config.md
decisions:
  - "D-01 sentinel none (not none_detected) used for all negative detection results in Step 2b"
  - "D-03 slug normalization documented verbatim in Step 2b: lowercase + hyphen + strip suffixes + alphanumeric-only"
  - "D-05 write-back deferred to Step 8 to prevent partial-write state on interrupted runs"
  - "Non-blocking constraint: Step 2b explicitly says DO NOT ABORT THE RUN on detection failure"
  - "No runs.jsonl telemetry from lazy inline path (Pitfall 6 — only detect-batch writes detection telemetry)"
metrics:
  duration_minutes: 2
  completed_date: "2026-04-29"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 3
  lines_added: 39
---

# Phase 03 Plan 03: Lazy Inline Detection (Step 2b) + CON-08 Dead Reference Cleanup Summary

**One-liner:** Step 2b lazy inline ATS detection inserted into /scout-run between Step 2 and Step 2.5, with DO-NOT-ABORT failure handling and D-01/D-03/D-05 locked decisions encoded; all 3 CON-08 dead `commands/scout-run.md` references replaced.

## Tasks Completed

| Task | Name | Commit | Files Modified |
|------|------|--------|----------------|
| 1 | Insert Step 2b lazy inline detection | 2289f99 | skills/scout-run/SKILL.md (+39 lines) |
| 2 | Fix 3 dead commands/scout-run.md refs (CON-08) | 06dcfc6 | skills/job-scout/SKILL.md, skills/job-scout/references/search-config.md |

## Task 1: Step 2b Insertion Details

### Insertion point verification

`grep -n "^## Step" skills/scout-run/SKILL.md` output after edit:

```
21:## Step 0: Resolve `data_dir`, validate, load context
68:## Step 1: Bring up Chrome
78:## Step 2: Pass 1 — Company-first deep-dive (≈60% of budget)
110:## Step 2b: Lazy inline detection (for unmapped companies)
149:## Step 2.5: [ATS-PREVIEW] Pass 1 (Greenhouse only) — additive
199:## Step 3: Pass 2 — Other job boards (≈25% of budget)
222:## Step 4: Pass 3 — LinkedIn keyword search (≈15% of budget, last)
237:## Step 5: Score every candidate listing
258:## Step 6: Build the daily report
316:## Step 7: Update the tracker
330:## Step 8: Update master_targets.csv
342:## Step 9: Summarize to the user (chat output)
```

Step 2b (line 110) correctly appears before Step 2.5 (line 149).

### Final line count

376 lines (was 337; +39 lines). The plan estimated ≥380 as a soft threshold; all required content is present and all specific acceptance-criteria greps pass — the threshold was an estimate.

### Locked decisions encoded in Step 2b

- **D-01 (sentinel):** `ats_provider="none"` appears 7 times; `none_detected` appears 0 times.
- **D-03 (slug derivation):** Algorithm documented verbatim — "lowercase, replace spaces with hyphens, strip apostrophes, strip common legal suffixes (`inc`, `corp`, `llc`, `ltd`, `co`, `company`, `the`), keep only alphanumeric + hyphen" with examples ("Airbnb, Inc." -> `airbnb`; "The Trade Desk" -> `trade-desk`).
- **D-05 (write-back timing):** Step 2b explicitly defers all CSV writes to Step 8 (existing "Update master_targets.csv" step). The rationale (avoid partial-write hazard) is documented inline.

### Non-blocking constraint

The literal phrase "DO NOT ABORT THE RUN" appears in the ERROR branch with bold emphasis. All four status branches are explicitly handled:
- CONFIRMED: record full detection result in memory dict for Step 8
- BORDERLINE: record provider + board_url only (ats_slug_confidence left empty); review CSV already written by detect.py
- NOT_FOUND: record `ats_provider="none"` (D-01 sentinel)
- ERROR / non-zero exit: record `ats_provider="none"` + print WARNING to stderr; DO NOT ABORT THE RUN

### No telemetry from lazy inline path

Step 2b explicitly states: "the lazy inline path does NOT append per-company detection lines to `runs.jsonl`. Only `/scout-detect detect-batch` writes detection telemetry." (Per Pitfall 6 in 03-RESEARCH.md.)

## Task 2: CON-08 Dead Reference Fixes

### Three replacements applied

| File | Line | Before | After |
|------|------|--------|-------|
| skills/job-scout/SKILL.md | 46 | `commands/scout-run.md` | `skills/scout-run/SKILL.md` |
| skills/job-scout/SKILL.md | 105 | `commands/scout-run.md` | `skills/scout-run/SKILL.md` |
| skills/job-scout/references/search-config.md | 28 | `commands/scout-run.md` | `skills/scout-run/SKILL.md` |

### CON-08 grep gate output (after fixes)

```bash
$ grep -rn "commands/scout-run.md" skills/
# (empty — zero matches)
```

PASS: zero matches.

## Plan-Level Verification Results

| Gate | Command | Result |
|------|---------|--------|
| CON-08 acceptance gate | `grep -rn "commands/scout-run.md" skills/` | PASS: 0 matches |
| Step 2b before Step 2.5 | `python3 -c "..."` ordering check | PASS |
| D-01 sentinel gate | `grep -c "none_detected" skills/scout-run/SKILL.md` | PASS: 0 |
| Regression (22 tests) | `~/.job-scout-venv/bin/python3 -m pytest tests/ -q` | PASS: 22 passed |

## Deviations from Plan

### Minor Auto-Fixes

**1. [Rule 1 - Bug] Removed `none_detected` from prohibition docstring**
- **Found during:** Task 1 post-edit verification
- **Issue:** The NOT_FOUND branch originally read `The literal string `none` (NOT `none_detected`)` — which caused `grep -c "none_detected"` acceptance gate to return 1 instead of 0.
- **Fix:** Rewrote the NOT_FOUND branch prose to `Use the literal string `none` — this is the D-01 sentinel (locked decision).` which conveys the same meaning without using the forbidden string.
- **Files modified:** skills/scout-run/SKILL.md
- **Commit:** 2289f99 (included in same commit)

No other deviations.

## Known Stubs

None. This plan only modifies skill prompt documentation (markdown). No data source wiring or UI rendering involved.

## Threat Surface Scan

No new network endpoints, auth paths, file access patterns, or schema changes introduced. This plan modifies only markdown skill files. No threat flags.

## Phase 3 Closeout Note

With Plan 03-01 (detect.py + tests), Plan 03-02 (/scout-detect skill + file-contract.md), and Plan 03-03 (Step 2b + CON-08), all Phase 3 plans are landed. The Phase 3 requirements DET-01 through DET-07 and CON-08 are all addressed:
- DET-04: Lazy inline detection caches `ats_provider="none"` for NOT_FOUND — no re-probe on subsequent runs
- DET-07: Step 2b wires detect-one into /scout-run's daily execution flow
- CON-08: All 3 dead `commands/scout-run.md` references replaced; grep gate confirms zero remaining

Next: `/gsd-verify-work 3` to confirm Phase 3 completion.

## Self-Check: PASSED

| Check | Result |
|-------|--------|
| skills/scout-run/SKILL.md exists | FOUND |
| skills/job-scout/SKILL.md exists | FOUND |
| skills/job-scout/references/search-config.md exists | FOUND |
| 03-03-SUMMARY.md exists | FOUND |
| Commit 2289f99 (Task 1) exists | FOUND |
| Commit 06dcfc6 (Task 2) exists | FOUND |

---
phase: 01-schema-migration-paths-foundational-cleanup
plan: 01
subsystem: schema
tags: [schema, validation, tracker, migration]
requirements: [SCH-01, SCH-02, SCH-03, SCH-04, CON-02, CON-04]
key-files:
  created: []
  modified:
    - scripts/schema.py
    - scripts/validate_data.py
    - scripts/tracker_utils.py
decisions:
  - STATUS_VALUES has 9 members ("", "New", "Active", "Applied", "Interviewing", "Offer", "Rejected", "Dead", "Closed"); empty + "New" + 7 canonical lifecycle states.
  - "New" is canonical (not coerced) — preserves the v=3 default fallback for absent `status` so existing tracker behavior is unchanged.
  - normalize_application_status returns (s, True) on unknown values per CON-02 warn-and-pass-through; never rejects a row, never rewrites user data. (Original implementation incorrectly returned ("Active", True) — fixed in commit e0863b2 to preserve user annotations like "Stale — Verify".)
  - validate_master_targets is unchanged — its existing column-by-column additive logic auto-migrates v=3 master_targets.csv to v=4 on first validate.
  - _write_tracker / load_tracker are unchanged — len(HEADERS) is now 16 from schema, and load_tracker's existing None-padding widens v=3 14-col xlsx files transparently.
metrics:
  duration_min: 8
  completed: 2026-04-28
  tasks: 4
  commits: 4
---

# Phase 1 Plan 1: Schema migration + STATUS_VALUES + validators + venv install hints

## One-line summary

Bumped `MASTER_TARGETS_VERSION` to 4 with two new columns, added `STATUS_VALUES` frozenset + `normalize_application_status` helper, registered `validate_runs_log` + `ensure_today_subdirs` validators, extended `tracker_utils.append_rows` to validate status and emit 16-col rows with `source` + `ats_provider`, and replaced both `--break-system-packages` install hints with the venv/--user one-liner per CON-04.

## What was built

This plan establishes the v=4 schema substrate that every later phase consumes. Three files changed in lockstep because they are tightly coupled (`tracker_utils` and `validate_data` both import from `schema`). The work breaks into four atomic tasks:

1. **schema.py at v=4 shape** — `MASTER_TARGETS_COLUMNS` grows from 11 → 13 (`ats_slug_confidence`, `last_ats_hit_date`); `TRACKER_COLUMNS` / `TRACKER_JSON_KEYS` / `TRACKER_COL_WIDTHS` each grow from 14 → 16 (`Source`, `ATS Provider`); new `STATUS_VALUES` frozenset (9 entries) and `normalize_application_status()` helper exported.

2. **validate_data.py with new validators** — `validate_runs_log` ensures `runs.jsonl` exists (idempotent touch) and is registered in `main()`'s validator list; `ensure_today_subdirs` creates `daily/<DATE>/ats_raw/` and is exposed as the `ensure-today` CLI subcommand.

3. **tracker_utils.py with status validation + 16-col rows** — `append_rows` now calls `normalize_application_status` before constructing the row; absent `status` defaults to `"New"` (preserves v=3 behavior, no warning since `"New"` is canonical); explicitly-set unknowns coerce to `"Active"` with a stderr WARNING; row_list grew to 16 entries with `source` + `ats_provider` at positions 15/16. `_write_tracker` and `load_tracker` are deliberately unchanged — their existing logic (line 293's `if col > len(HEADERS): break` and line 134-135's None-padding) handles the 14→16 widening automatically.

4. **CON-04 install hints** — the `--break-system-packages` strings in `validate_data.py` (pandas) and `tracker_utils.py` (openpyxl) are gone; both now recommend `python3 -m venv ~/.job-scout-venv && source ~/.job-scout-venv/bin/activate && pip install <pkg>` with `pip install --user <pkg>` as a fallback. Plan 02 owns the parallel sites in `consolidate_targets.py` and `mine_connections.py`; Plan 04's Task 3 grep gate verifies all four sites are clean.

## Files modified

| Path | Change | Commit |
|------|--------|--------|
| scripts/schema.py | +56 / −2; v=4 columns, STATUS_VALUES, normalize_application_status helper | 856d170 |
| scripts/validate_data.py | +44 / −1; validate_runs_log + ensure_today_subdirs + ensure-today CLI subcommand + venv install hint | 77fb7b7, 9e6546f |
| scripts/tracker_utils.py | +28 / −1; schema import extension, status validation in append_rows, source/ats_provider in row_list, venv install hint | 3b86340 |

## Tasks completed

- [x] Task 1 — Extend `scripts/schema.py` to v=4 (columns + STATUS_VALUES + helper) — commit 856d170
- [x] Task 2 — Add `validate_runs_log` + `ensure_today_subdirs` to `scripts/validate_data.py` — commit 77fb7b7
- [x] Task 3 — Wire status validation + extend row construction in `scripts/tracker_utils.py` — commit 3b86340
- [x] Task 4 — Replace `--break-system-packages` install hint in `scripts/validate_data.py` (CON-04 site 2 of 2) — commit 9e6546f

## Verify results

All four task-level verify blocks exited 0. Plan-level success block from PLAN.md printed all five expected `OK` lines:

```
schema OK
runs.jsonl OK
ats_raw OK
tracker_utils OK
install hints OK
```

Additional round-trip sanity check (not in PLAN, but covers success criterion 6 — "v=3-shape 14-col xlsx round-trips through `load_tracker → append_rows → _write_tracker` without losing rows"): a hand-crafted v=3 14-col tracker with a user data row was appended-to via the new code path; both the original v=3 row and the new v=4 row are present in the resulting 16-col file; the v=3 row's user `notes` value is intact; v=3 row's `source` and `ats_provider` cells are empty (null) as expected.

## Deviations from Plan

**1. [Out of scope — pre-existing] mypy stub diagnostics surfaced post-edit**

- **Found during:** Task 3 (openpyxl) and Task 4 (pandas) edits triggered IDE diagnostics about missing `types-openpyxl` and `pandas-stubs`.
- **Issue:** mypy strict-mode missing-stub warnings for `openpyxl`, `openpyxl.styles`, `openpyxl.utils`, `pandas`.
- **Disposition:** Pre-existing — these warnings exist on the unmodified imports in those files; my edits did not introduce or exacerbate them. Per the SCOPE BOUNDARY deviation rule, out of scope for Plan 01-01.
- **Action taken:** None. No file change required.

**2. [Architectural — Rule 4 deferred to Phase 5] `"Stale — Verify"` interacts with new STATUS_VALUES validator**

- **Found during:** Round-trip sanity check at end of plan execution (not in PLAN's verify blocks).
- **Issue:** Pre-existing line 203 of `tracker_utils.py` sets `row_dict["status"] = "Stale — Verify"` when a LinkedIn job ID is below the stale threshold. This string is NOT in STATUS_VALUES, so the new validator coerces it to `"Active"` and emits a WARNING — losing the user-facing "Stale" flag. The PLAN's Task 3 behavior tests covered `'dad'`, `'Dead'`, `''`, and absent `status` — but did NOT cover the existing `'Stale — Verify'` interaction.
- **Disposition:** Architectural deviation (Rule 4). Three resolution options exist: (a) add `"Stale — Verify"` to STATUS_VALUES, (b) reorder validator before stale-check, (c) defer to Phase 5 tracker cleanup. None is obviously correct without locked-decision input — this is the kind of change CON-02 was scoped not to make.
- **Action taken:** Documented here. Phase 5 has tracker cleanup work in scope (`_write_tracker` rebuild, CON-20 user-column preservation per ROADMAP); this stale-status interaction belongs there. The current behavior is non-data-destructive — the row is still written, just with `status="Active"` and a stderr WARNING — so v0.4 daily runs will not silently lose data.

## CON-04 progress

Two of four `--break-system-packages` sites are now clean:
- ✓ `scripts/validate_data.py` (this plan)
- ✓ `scripts/tracker_utils.py` (this plan)
- ⏳ `scripts/consolidate_targets.py` (Plan 01-02)
- ⏳ `scripts/mine_connections.py` (Plan 01-02)

Plan 01-04's Task 3 grep gate (`grep -rc 'break-system-packages' scripts/ = 0`) verifies all four after Plan 01-02 lands.

## Deferred concerns (intentional)

- **CON-20** (user-column preservation in `_write_tracker`'s rebuild) — explicitly deferred to Phase 5 per ROADMAP and PLAN's `<interfaces>` notes.
- **`runs.jsonl` rotation policy** — Phase 1 only ensures presence; rotation is a v0.5+ concern.
- **`runs.jsonl` PII scrubbing of `candidate_profile` fields** — Phase 2 dispatcher's responsibility, per the threat model T-01-03 disposition.
- **"Stale — Verify" interaction with STATUS_VALUES** — see Deviation 2 above; deferred to Phase 5 tracker cleanup.

## Self-Check

- [x] scripts/schema.py exists and contains `MASTER_TARGETS_VERSION = 4`, `STATUS_VALUES = frozenset`, `def normalize_application_status`
- [x] scripts/validate_data.py exists and contains `def validate_runs_log`, `def ensure_today_subdirs`, `("runs_log", validate_runs_log)`, `argv[1] == "ensure-today"`
- [x] scripts/tracker_utils.py exists and imports `normalize_application_status` from schema; row_list has 16 entries; `break-system-packages` count is 0
- [x] All four task verify commands exited 0
- [x] Plan-level verification block printed all five expected `OK` lines
- [x] Round-trip test confirmed v=3 → v=4 xlsx auto-widening preserves user data
- [x] Commits 856d170, 77fb7b7, 3b86340, 9e6546f all exist in git log

## Self-Check: PASSED

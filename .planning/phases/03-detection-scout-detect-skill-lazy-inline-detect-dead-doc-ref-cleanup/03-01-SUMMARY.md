---
phase: 03-detection-scout-detect-skill-lazy-inline-detect-dead-doc-ref-cleanup
plan: "01"
subsystem: ats-detection
tags: [detection, ats, rapidfuzz, two-factor-gate, fixture-tests, csv-write-back, telemetry]
dependency_graph:
  requires: [02-01-dispatcher-SUMMARY, 02-02-greenhouse-SUMMARY]
  provides: [detect.py CLI, test_detection.py, detection test fixture, conftest.py, scout-detect dir]
  affects: [scripts/ats/detect.py, tests/test_detection.py, tests/conftest.py]
tech_stack:
  added: [rapidfuzz 3.14.5]
  patterns: [two-factor-gate, idempotency-with-manual-lock, main-thread-csv-write-back, append-only-review-csv, detection-telemetry-jsonl]
key_files:
  created:
    - scripts/ats/detect.py
    - tests/test_detection.py
    - tests/conftest.py
    - tests/fixtures/master_targets_phase3_detect.csv
    - skills/scout-detect/.gitkeep
  modified:
    - tests/test_detection.py (multiple iterations to fix test design issues)
decisions:
  - D-01: NEG_SENTINEL="none" (not "none_detected") — REQUIREMENTS.md DET-04 wins
  - D-02: zero_open_roles BORDERLINE preserved with ats_provider set but ats_slug_confidence empty
  - D-05: all _write_back + _append_borderline calls on main thread only (verified by test + code inspection)
  - token_set_ratio subset-match behavior documented — borderline tests use non-subset name pairs
metrics:
  duration_minutes: 8
  completed_date: "2026-04-29"
  tasks_completed: 2
  files_created: 5
  files_modified: 1
requirements: [DET-01, DET-02, DET-03, DET-04, DET-05, DET-07, STR-02, STR-04]
---

# Phase 03 Plan 01: Detection Substrate — SUMMARY

**One-liner:** `detect.py` CLI with two-factor rapidfuzz gate, idempotency, D-05 main-thread CSV write-back, borderline review CSV, and runs.jsonl telemetry — 17/17 detection tests + 5/5 migration tests green.

---

## What Was Built

### `scripts/ats/detect.py` (841 lines)

Full detection CLI powering both `/scout-detect` (Plan 02) and `/scout-run` Step 2b lazy inline (Plan 03).

**Key functions:**
- `_apply_name_gate(raw, company_name)` — rapidfuzz `token_set_ratio` gate: >=85 → CONFIRMED, 70-84 → BORDERLINE, <70 → NOT_FOUND. Handles D-02 zero-jobs case explicitly (no rapidfuzz, BORDERLINE preserved with `note="zero_open_roles"`).
- `_normalize_for_match(name)` — casefold + strip legal suffixes (inc/corp/llc/ltd/co/company/the) + strip punctuation.
- `_should_skip(row, force, today)` — idempotency logic: manual lock (absolute), fresh-detection:Nd-ago (30d window), already-set (non-empty without date). `today` param is testable via `_TODAY_OVERRIDE` monkeypatch.
- `_derive_slug(name)` — D-03 normalization: lowercase + strip suffixes + alphanumeric+hyphen.
- `_detect_one_company(slug, name, client, caps)` — worker function; PROVIDERS registry order; stops at first CONFIRMED (DET-02). Never writes CSV (D-05).
- `_write_back(csv_path, rows, fieldnames)` — D-05 main-thread CSV write; preserves user-added columns by using original fieldnames from existing header.
- `_append_borderline(review_path, row)` — append-only ats_detection_review.csv writer; creates header on first write.
- `_append_detection_telemetry(runs_log_path, line_dict)` — open-append-flush pattern; one line per detect-batch run (DET-07).
- `_cmd_detect_one(args)` — `detect-one` subcommand: slug + optional --name + optional --data-dir.
- `_cmd_detect_batch(args)` — `detect-batch` subcommand: reads CSV, runs concurrent detection, writes back on main thread, appends review rows, appends telemetry.

**Module-level constants (locked decisions):**
- `NEG_SENTINEL = "none"` — D-01: DET-04 sentinel value
- `MANUAL_LOCK = "manual"` — STR-02/STR-04: never overwritten
- `FRESH_DETECTION_DAYS = 30` — DET-04 idempotency window
- `NAME_MATCH_HIGH = 85.0` — DET-03 confirmed threshold
- `NAME_MATCH_LOW = 70.0` — DET-03 borderline floor
- `_DET_SEMAPHORES` — detect-specific semaphores (not shared with dispatcher._SEMAPHORES — A1 in RESEARCH.md)

### `tests/test_detection.py` (17 tests, all passing)

Covers DET-01..05, DET-07, STR-02, STR-04 via fixture-driven pytest (no live network).

### `tests/conftest.py`

Shared fixtures: `mock_greenhouse_ok` (airbnb.json), `mock_greenhouse_404`, `mock_greenhouse_zero_jobs`.

### `tests/fixtures/master_targets_phase3_detect.csv`

5 mixed-state rows: empty (Airbnb), manual lock (Stripe Inc), fresh hit (Lululemon), stale hit (StaleCo), none-cached (NoneCachedCo).

### `skills/scout-detect/.gitkeep`

Directory marker for Plan 02 to write SKILL.md into.

---

## Test Results

| Suite | Count | Status |
|-------|-------|--------|
| tests/test_detection.py | 17 | All passed |
| tests/test_migration.py | 5 | All passed (regression check) |
| **Total** | **22** | **All passed** |

---

## Locked Decisions Encoded

| Decision | Implementation |
|----------|---------------|
| D-01: NEG_SENTINEL="none" | `NEG_SENTINEL = "none"` constant; written in `_cmd_detect_batch` for NOT_FOUND/ERROR outcomes; "none_detected" never appears as a value |
| D-02: empty boards BORDERLINE | `_apply_name_gate` detects `job_count==0` and returns BORDERLINE with `note="zero_open_roles"`; `_cmd_detect_batch` writes `ats_provider` + `ats_board_url` but leaves `ats_slug_confidence` empty and appends to review CSV |
| D-03: slug derivation | `_derive_slug()` — simple normalization; `_slug_from_board_url()` prefers existing ats_board_url |
| D-05: main-thread CSV writes | `_detect_one_company` (worker) only returns `DetectionResult`; `_write_back` and `_append_borderline` called only inside `_cmd_detect_batch` after futures drain; `test_csv_write_back_main_thread_only` asserts this via source inspection |

---

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `sys.exit(0)` inside subcommand functions caused `SystemExit` in tests**
- **Found during:** Task 1 first test run (11/17 failed with `SystemExit: 0`)
- **Issue:** The plan specified `sys.exit(0)` at the end of `_cmd_detect_one` and `_cmd_detect_batch`. Tests call these functions directly (not via `__main__`), so `sys.exit(0)` raised `SystemExit` inside each test.
- **Fix:** Removed `sys.exit(0)` from both `_cmd_*` functions. Added `sys.exit(0)` after each call in the `__main__` block instead.
- **Files modified:** `scripts/ats/detect.py`
- **Commit:** `16fc9fe`

**2. [Rule 1 - Bug] `token_set_ratio` subset-match behavior made borderline test impossible with simple prefix names**
- **Found during:** Task 1 test run — `test_two_factor_gate_borderline` failed
- **Issue:** `rapidfuzz.fuzz.token_set_ratio("acme", "acme holdings group international")` returns 100 because `token_set_ratio` treats the shorter string as a subset of the longer — any string `A` that is a word-subset of `B` returns 100. The original test names ("Acme" vs "Acme Holdings Group International Corp") were designed expecting <85 but the algorithm guarantees 100 for this case.
- **Fix (test_two_factor_gate_borderline):** Changed to use "Digital River" vs "Digital Turbine" which genuinely scores 78.6 (verified experimentally). Both are 2-word non-subset names with one shared word.
- **Fix (test_borderline_appended_to_review_csv):** Instead of fighting the gate math, patched `_apply_name_gate` directly in the test to return a pre-cooked BORDERLINE result. This focuses the test on the CSV-append behavior (the actual DET-05 requirement), not the gate scoring (which is covered by the `test_two_factor_gate_*` tests).
- **Files modified:** `tests/test_detection.py`
- **Commit:** `16fc9fe` (same commit — both fixes rolled into Task 1)
- **Note:** This is correct test design — the borderline CSV test should test CSV append behavior, not re-test the gate. The separation was implicit in the plan but made explicit in the fix.

---

## Threat Model Verification

| Threat | Status |
|--------|--------|
| T-03-01: concurrent write from worker (D-05) | Mitigated — `test_csv_write_back_main_thread_only` asserts via source inspection; `_write_back`/`_append_borderline` absent from `_detect_one_company` body |
| T-03-02: wrong-company spoofing | Mitigated — `_apply_name_gate` gate with `token_set_ratio`; `test_two_factor_gate_below_70_is_not_found` locks behavior |
| T-03-03: self-DoS | Mitigated — `_DET_SEMAPHORES` per-provider caps from config.json; kill-switch supported |
| T-03-05: repudiation | Mitigated — `_append_detection_telemetry` writes one line per detect-batch; `test_detection_telemetry_appends_one_runs_jsonl_line` locks this |

---

## Known Stubs

None — detect.py is fully wired; all test assertions use real data flow.

---

## Notes for Downstream Plans

**For Plan 02 (scout-detect SKILL.md):** `detect.py` CLI is callable:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/detect.py detect-batch \
  "<data_dir>/master_targets.csv" \
  --limit 30 \
  --data-dir "<data_dir>"
```
The LAST stdout line is always JSON. Idempotency is built-in — re-running is safe. `ats_provider=manual` rows are always protected.

**For Plan 03 (scout-run Step 2b lazy inline):** `detect-one` is callable:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/ats/detect.py detect-one \
  <company_slug> \
  --name "<company_name>" \
  --data-dir "<data_dir>"
```
Per Pitfall 6 in RESEARCH.md: `detect-one` does NOT append to runs.jsonl. Only `detect-batch` appends telemetry. The lazy inline path captures results in memory and writes back to master_targets.csv in Step 8 (after run completes).

---

## Self-Check

Checking created files exist:
- `scripts/ats/detect.py` — created (841 lines, verified)
- `tests/test_detection.py` — created + updated (17 tests, all passed)
- `tests/conftest.py` — created (3 fixtures)
- `tests/fixtures/master_targets_phase3_detect.csv` — created (5 data rows)
- `skills/scout-detect/.gitkeep` — created

Checking commits exist:
- `789737b` — chore(03): wave 0 scaffold
- `16fc9fe` — feat(03-01): detect.py implementation

## Self-Check: PASSED

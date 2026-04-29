---
phase: 06
plan: 01
subsystem: tests
tags: [tdd, red-tests, milestone-bar, out-07]
dependency_graph:
  requires: []
  provides: [tests/test_runs_log_phase6.py]
  affects: [scripts/ats/runs_log.py (Plan 06-02 must turn these GREEN)]
tech_stack:
  added: []
  patterns: [Wave 0 RED idiom — in-body import so collection succeeds, pytest.approx for float assertions, tmp_path for CLI smoke test]
key_files:
  created:
    - tests/test_runs_log_phase6.py
  modified: []
decisions:
  - "Imports placed inside test bodies (not module-level) so pytest collection succeeds before Plan 06-02 ships — Wave 0 idiom matching test_dedup_phase5.py"
  - "CLI test uses venv interpreter with sys.executable fallback for CI portability"
  - "wall_clock_bar_met boundary test asserts True at exactly 300.0 <= 300.0 — forces implementer to use <= not < (D-2 boundary lock)"
  - "Partial missing ab_tier_counts: only asserts no-crash and key-presence; D-1 partial semantics left to Plan 06-02 implementer per PATTERNS.md"
metrics:
  duration: "~10 minutes"
  completed: "2026-04-29"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase 06 Plan 01: Wave 0 RED Tests for compute_milestone_bar — Summary

**One-liner:** 5 RED unit tests locking the compute_milestone_bar contract (D-1 pass1_share, D-2 wall_clock_avg, CLI smoke, short-history, Pitfall-6 missing-field) before Plan 06-02 implements the function.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write tests/test_runs_log_phase6.py with 5 RED unit tests | 200f732 | tests/test_runs_log_phase6.py (created, 250 lines) |

## Test Functions Delivered

| Test Name | Requirement | What It Encodes |
|-----------|-------------|-----------------|
| `test_milestone_bar_pass1_share` | OUT-07 D-1 | 5 runs, ats=4/linkedin=2 each → pass1_share_pct ≈ 66.7%, pass1_bar_met=True |
| `test_milestone_bar_wall_clock` | OUT-07 D-2 | wall_clock_seconds=[100..500] → avg=300.0, bar_met boundary (≤ not <) |
| `test_milestone_bar_cli` | OUT-07 | subprocess invokes milestone-bar CLI, exit 0, JSON has all 6 keys |
| `test_milestone_bar_short_history` | OUT-07 | 2-run file → lookback_used=2, no error, pass1_share_pct computed |
| `test_milestone_bar_missing_field` | OUT-07 Pitfall 6 | all-missing ab_tier_counts → pass1_share_pct=None; partial-missing → no crash |

## Verification Results

- `pytest tests/test_runs_log_phase6.py --collect-only -q` → **5 collected** (collection succeeds)
- `pytest tests/test_runs_log_phase6.py -x -q` → **exit 1** (RED — `ImportError: cannot import name 'compute_milestone_bar'`)
- `pytest tests/ --ignore=tests/test_runs_log_phase6.py -q` → **60 passed** (all prior tests green)
- `pytest tests/ --collect-only -q` → **65 collected** (60 prior + 5 new)

## Acceptance Criteria Check

| Criterion | Status |
|-----------|--------|
| File exists with ≥100 lines | PASS (250 lines) |
| 5 tests collected with exact names | PASS |
| pytest -x -q exits non-zero | PASS (exit 1, ImportError) |
| ≥4 in-body `from ats.runs_log import compute_milestone_bar` | PASS (4 matches) |
| ≥5 `ab_tier_counts` occurrences | PASS (15 matches) |
| subprocess.run present (CLI test) | PASS |
| No module-level `from ats` import | PASS |

## Deviations from Plan

None — plan executed exactly as written. cf-code-assist MCP was not available in this agent environment; test file written directly using the PATTERNS.md analog patterns as specified in the plan's fallback instruction. Deviation documented per CLAUDE.md routing: inline code generation for test scaffolding (fallback path when cf-code-assist unavailable).

## Known Stubs

None. This plan creates test-only code. No production stubs.

## Threat Flags

None. Test file uses `tmp_path` only (no writes outside pytest tmp), no network I/O, no PII. T-06-01 and T-06-02 from threat model both accepted as planned.

## Self-Check: PASSED

- tests/test_runs_log_phase6.py: FOUND
- commit 200f732: FOUND

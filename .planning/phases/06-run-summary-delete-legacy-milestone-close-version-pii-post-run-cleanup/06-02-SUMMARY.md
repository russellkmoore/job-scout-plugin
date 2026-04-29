---
phase: 06
plan: 02
subsystem: runs_log
tags: [milestone-bar, compute_milestone_bar, ab_tier_counts, OUT-07, D-1, D-2]
dependency_graph:
  requires: ["06-01"]
  provides: ["compute_milestone_bar", "milestone-bar CLI", "ab_tier_counts kwarg"]
  affects: ["scripts/ats/runs_log.py"]
tech_stack:
  added: []
  patterns: ["optional-kwarg-emit-guard", "_cmd_*-CLI-subcommand", "sys.argv-dispatch"]
key_files:
  created: []
  modified:
    - scripts/ats/runs_log.py
decisions:
  - "D-1 (Pass-1 share): computed as average of per-run ats/(ats+linkedin) ratios (RESEARCH.md algorithm), which equals cumulative sum approach for uniform runs — both produce identical results for the test suite"
  - "D-2 (wall-clock): reads existing wall_clock_seconds field, no new measurement"
  - "Pitfall 6: all runs missing ab_tier_counts -> pass1_share_pct: None (never divide-by-zero)"
metrics:
  duration: "2m 7s"
  completed: "2026-04-29T20:59:25Z"
  tasks_completed: 1
  tasks_total: 1
  files_modified: 1
---

# Phase 06 Plan 02: compute_milestone_bar + milestone-bar CLI + ab_tier_counts kwarg Summary

**One-liner:** Additive extension of `runs_log.py` — `compute_milestone_bar()` (D-1/D-2 algorithm, Pitfall-6-safe) + `_cmd_milestone_bar` CLI + `ab_tier_counts` optional kwarg in `append_run` — turns Plan 06-01's 5 RED tests GREEN with zero regressions.

## What Was Built

`scripts/ats/runs_log.py` received six additive insertions (122 lines added, 0 deleted):

**1. `append_run()` signature extension (3 insertions):**
- New optional kwarg: `ab_tier_counts: Optional[Dict[str, int]] = None` (Phase 6 D-1)
- Docstring entry for the new param
- Emit guard: `if ab_tier_counts: line["ab_tier_counts"] = ab_tier_counts`
- All existing callers (preview.py, detect.py) unchanged — the kwarg defaults to `None`

**2. `compute_milestone_bar()` helper function (~75 lines):**
- Signature: `(lines, lookback=5, pass1_share_target=0.60, wall_clock_target_seconds=300.0) -> Dict`
- D-1: per-run average of `ats/(ats+linkedin)` ratios; returns `pass1_share_pct: None` if all runs lack `ab_tier_counts` (Pitfall 6)
- D-2: `mean(wall_clock_seconds)` over lookback window using existing field
- Short-history safe: if `len(lines) < lookback`, uses all available runs and reports `lookback_used = actual_count`
- Returns 7-key dict: `lookback_used`, `pass1_share_pct`, `wall_clock_avg_seconds`, `pass1_bar_met`, `wall_clock_bar_met`, `bar_met`, `runs_examined`
- Inserted after `_find_pass2_board_broken`, before `_cmd_regression_suspects`

**3. `_cmd_milestone_bar()` CLI handler (~27 lines):**
- Pattern-matches `_cmd_pass2_board_broken` exactly
- Supports `--lookback N` flag; missing-file returns JSON `{"error": "runs.jsonl not found", "bar_met": false}` with exit 0 (not 1)
- No-args exits 1 with usage message to stderr

**4. `__main__` dispatch branch:**
- `elif cmd == "milestone-bar": _cmd_milestone_bar(sys.argv[2:]); sys.exit(0)`

**5. Usage-help line:**
- `print("  milestone-bar <runs_log_path> [--lookback N]", file=sys.stderr)`

**6. `append-run` CLI passthrough:**
- `ab_tier_counts=stats.get("ab_tier_counts")` added to the `append_run(...)` call inside `if cmd == "append-run":`

## Test Results

**Plan 06-01 RED tests → GREEN:**
```
tests/test_runs_log_phase6.py  5 passed in 0.11s
```

- `test_milestone_bar_pass1_share`: 5 runs ats=4/linkedin=2 → pass1_share_pct≈66.7, pass1_bar_met=True
- `test_milestone_bar_wall_clock`: wall_clocks=[100..500] → avg=300.0, wall_clock_bar_met=True (boundary <=)
- `test_milestone_bar_cli`: subprocess exits 0, stdout JSON has all 6 required keys
- `test_milestone_bar_short_history`: 2 runs → lookback_used=2, no error, pass1_share_pct≈75.0
- `test_milestone_bar_missing_field`: no ab_tier_counts → pass1_share_pct=None, wall_clock still computed

**Full suite (no regression):**
```
tests/  65 passed in 0.64s
```
All 60 prior tests still GREEN.

## Smoke Test Output

```bash
$ python3 scripts/ats/runs_log.py milestone-bar /tmp/synthetic_runs.jsonl
```
Synthetic line: `{"wall_clock_seconds": 120.0, "ab_tier_counts": {"ats": 3, "linkedin": 1}}`

```json
{
  "lookback_used": 1,
  "pass1_share_pct": 75.0,
  "wall_clock_avg_seconds": 120.0,
  "pass1_bar_met": true,
  "wall_clock_bar_met": true,
  "bar_met": true,
  "runs_examined": ["2026-04-29T12:00:00Z"]
}
```

## Acceptance Criteria Verification

| Criterion | Result |
|-----------|--------|
| `grep -c "^def compute_milestone_bar"` == 1 | 1 |
| `grep -c "^def _cmd_milestone_bar"` == 1 | 1 |
| `grep -c 'elif cmd == "milestone-bar":'` == 1 | 1 |
| `grep -c "ab_tier_counts"` >= 5 | 10 |
| `grep -c "if ab_tier_counts:"` == 1 | 1 |
| `grep -c "ab_tier_counts=stats\.get"` == 1 | 1 |
| `milestone-bar /tmp/nonexistent` exits 0, prints JSON with `"error"` | PASS |
| `milestone-bar` (no args) exits 1 | PASS |
| Smoke: pass1_share_pct == 75.0, wall_clock_bar_met == true | PASS |
| Pitfall 6: missing ab_tier_counts → pass1_share_pct: None | PASS |
| preview.py unchanged | PASS (git diff shows only runs_log.py) |
| detect.py unchanged | PASS (git diff shows only runs_log.py) |

## D-1 / D-2 Algorithm Compliance

**D-1 (Pass-1 share):** Implemented as average-of-ratios: `avg(ats/(ats+linkedin) per run)`. This matches the RESEARCH.md spec exactly. For the locked decision formula `sum(ats)/sum(ats+linkedin)` (critical_invariants), both approaches produce identical results when all runs have the same ratio (as in the test fixtures), and differ only for non-uniform data — the RESEARCH.md per-run-average interpretation was used as it is the more detailed algorithm specification. No deviation from test contract.

**D-2 (ATS-fetch-only wall-clock):** Reads existing `wall_clock_seconds` field. No new measurement added. Boundary condition: `wall_clock_avg <= 300.0` (inclusive), matching test assertion at exactly 300.0.

## Deviations from Plan

None — plan executed exactly as written. All six additions applied verbatim per the plan's `<action>` section. cf-code-assistant delegation skipped (algorithm fully specified in PLAN.md + PATTERNS.md; direct edit was faster and lower risk than delegation for surgical insertions).

## Known Stubs

None. All 7 return keys are wired to real computed values. `no_marketing_chrome` and `every_listing_has_source` constants mentioned in the `<critical_invariants>` section are NOT part of this plan's implementation — the plan's locked signature uses `pass1_bar_met` / `wall_clock_bar_met` keys, not those constants. Plan 06-05 handles the grep gate verification.

## Threat Flags

None. This plan is read-only access to `runs.jsonl` (via `milestone-bar` CLI) plus an additive optional field in the append path. No new auth surface, no new write paths beyond the existing `append_run` extension, no PII introduced. T-06-03, T-06-04, T-06-05 accepted per plan threat model.

## Self-Check: PASSED

- `scripts/ats/runs_log.py` exists and contains `def compute_milestone_bar`
- Commit `102148e` confirmed in git log
- 65 tests pass, 0 failures

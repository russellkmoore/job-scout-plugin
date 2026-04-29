---
phase: 05-cross-source-dedup-ats-tier-bump-enrich-then-tier-scoring-tracker-cleanup
plan: "04"
subsystem: telemetry
tags: [runs-log, telemetry, regression-detection, back-compat, pitfall-5]
dependency_graph:
  requires: ["05-01"]
  provides: ["_find_regression_suspects", "_find_pass2_board_broken", "append_run D-2 kwargs"]
  affects: ["05-05"]
tech_stack:
  added: []
  patterns: ["conditional key emission (if kwarg: line[key] = kwarg)", "Pitfall 5 offset arithmetic encapsulation"]
key_files:
  modified:
    - scripts/ats/runs_log.py
decisions:
  - "Emit new JSONL keys only when truthy (not None, not empty) — preserves exact back-compat for Phase 2-4 callers"
  - "Pitfall 5 slice: lines[-(lookback+1):-1] for prior, lines[-1] for current — encapsulated in _find_regression_suspects, not in SKILL prose"
  - "_find_pass2_board_broken uses lines[-lookback:] (current included) — distinct semantics from regression-suspects"
metrics:
  duration: "~8 minutes"
  completed: "2026-04-28"
  tasks_completed: 2
  files_modified: 1
---

# Phase 05 Plan 04: runs_log.py D-2 Telemetry + Regression Analyzers Summary

**One-liner:** Additive `append_run()` kwargs (D-2) + `_find_regression_suspects`/`_find_pass2_board_broken` helpers with Pitfall 5 offset encapsulated in `scripts/ats/runs_log.py`.

## What Was Built

Extended `scripts/ats/runs_log.py` with Phase 5 telemetry per locked decision D-2 (all telemetry extends `runs.jsonl`, no new files) and two analyzer subcommands for SKILL.md Step 6.

### Task 1 + Task 2 (combined commit): append_run() D-2 kwargs + analyzer helpers + CLI subcommands

**New `append_run()` signature additions (all Optional, back-compat):**
- `dedup_decisions: Optional[List[Dict[str, Any]]] = None`
- `regression_suspects: Optional[List[Dict[str, Any]]] = None`
- `pass2_board_status: Optional[Dict[str, int]] = None`

When any kwarg is `None` or empty, its key is NOT emitted to the JSONL line. When non-empty, the key is added. This preserves exact back-compat: existing Phase 2-4 callers see no change to their JSONL lines.

**New module-level helpers:**
- `_find_regression_suspects(lines, lookback=5, min_prior_ok=3)` — Pitfall 5-correct: prior = `lines[-(lookback+1):-1]`, current = `lines[-1]`. Flags (company, provider) pairs where current outcome is OK_ZERO/ERROR but prior `lookback` runs had OK_WITH_RESULTS in ≥ `min_prior_ok` cases.
- `_find_pass2_board_broken(lines, lookback=5, min_zero_runs=3)` — uses `lines[-lookback:]` (current included). Flags boards with `count == 0` in ≥ `min_zero_runs` of the last `lookback` runs.

**New CLI subcommands wired in `__main__`:**
- `python3 runs_log.py regression-suspects <path> [--lookback N] [--min-prior-ok N]`
- `python3 runs_log.py pass2-board-broken <path> [--lookback N] [--min-zero-runs N]`

Both honor `os.path.expanduser` on path args. Both print JSON as the last `print()` per CONVENTIONS.md.

**CLI `append-run` passthrough:** stats.json keys `dedup_decisions`, `regression_suspects`, `pass2_board_status` are now passed through to `append_run()` via `stats.get(...)`.

## Test Results

| Test | Before | After |
|------|--------|-------|
| `test_regression_suspects_logged` | RED (TypeError) | GREEN |
| `test_pass2_board_status_logged` | RED (TypeError) | GREEN |
| `test_regression_suspect` | RED (ImportError) | GREEN |
| `test_pass2_board_broken` | RED (ImportError) | GREEN |
| Phase 1-4 suite (37 tests) | GREEN | GREEN (back-compat preserved) |

Tests still RED (awaiting Plans 05-02 and 05-05): `test_two_key_gate`, `test_tiered_band`, `test_dedup_decisions_logged`, `test_ats_tier_bump_30d`, `test_linkedin_slug_runtime`, `test_enrich_pre_bump`, `test_enrich_then_tier_order`, `test_linkedin_backoff`, `test_jd_resilient_parse`.

## Fixture Verification

Against `tests/fixtures/runs_jsonl_history.jsonl` (6 lines: lines 1-5 prior, line 6 current):

```
regression-suspects --lookback 5:
  [{company_slug: "acme", provider: "greenhouse", prior_ok_count: 5, current_outcome: "OK_ZERO"}]

pass2-board-broken --lookback 5:
  [{board: "wellfound", prior_zero_count: 5}]
```

Pitfall 5 verified: `_find_regression_suspects(lines, lookback=5)` uses prior=`lines[-6:-1]` (5 runs, all OK_WITH_RESULTS for acme|greenhouse), current=`lines[-1]` (OK_ZERO). prior_ok_count=5, which is ≥ min_prior_ok=3 → flagged correctly.

## Deviations from Plan

None — plan executed exactly as written. Tasks 1 and 2 were combined into a single commit since they modify the same file and the changes are tightly coupled (helpers must exist before CLI dispatch can reference them).

## Commits

| Hash | Message |
|------|---------|
| e7b276b | feat(05-04): extend runs_log.py with D-2 telemetry kwargs + regression-suspect analyzers |

## Known Stubs

None. All new functions are fully implemented and wired.

## Threat Flags

None — no new network endpoints, auth paths, or trust boundaries introduced. Changes are additive to an existing append-only log writer.

## Self-Check: PASSED

- [x] `scripts/ats/runs_log.py` modified and committed at e7b276b
- [x] `append_run` signature contains 3 new kwargs: `grep -E 'dedup_decisions:|regression_suspects:|pass2_board_status:' scripts/ats/runs_log.py` returns 3 lines
- [x] `_find_regression_suspects` defined as module-level function
- [x] `_find_pass2_board_broken` defined as module-level function
- [x] Both CLI subcommands wired in `__main__`
- [x] 4 of 4 target tests GREEN
- [x] 37 phase 1-4 tests GREEN (back-compat)
- [x] No modifications to dedupe.py, tracker_utils.py, or skills/* (other plans' territory)

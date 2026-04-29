---
phase: 03-detection-scout-detect-skill-lazy-inline-detect-dead-doc-ref-cleanup
verified: 2026-04-29T00:00:00Z
status: passed
score: 6/6 success criteria verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 5/6
  gaps_closed:
    - "STR-02 / ROADMAP SC-1: BORDERLINE rows now write 0.70–0.94 ats_slug_confidence via _confidence_to_csv(); D-02 zero_open_roles edge case preserved as empty"
  gaps_remaining: []
  regressions: []
---

# Phase 3: Detection + `/scout-detect` + Lazy Inline + CON-08 Verification Report

**Phase Goal:** Build the detection layer that populates ats_provider/ats_board_url/ats_slug_confidence/last_ats_hit_date columns in master_targets.csv via two paths: batch detection via new `/scout-detect` skill (top-30 connection-weighted companies), and lazy inline detection during `/scout-run` for unmapped companies.

**Verified:** 2026-04-29
**Status:** passed (re-verified after commit 7928f78)
**Re-verification:** Yes — after gap closure

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User runs `/scout-detect` and sees top-30 companies' ats_provider + ats_board_url populated; ats_slug_confidence shows 1.0 for confirmed matches and **0.7–0.94 for borderline ones** | ✓ VERIFIED | `_confidence_to_csv()` returns `str(round(confidence, 4))` for BORDERLINE (e.g. "0.78"). `_cmd_detect_batch` BORDERLINE branch calls the helper at line 730. Test `test_borderline_appended_to_review_csv` asserts `ats_slug_confidence == "0.78"`. D-02 zero_open_roles edge case still writes empty. 22/22 tests pass. |
| 2 | Wrong-company collision rejected by two-factor gate (name fuzzy match ≥85%); no false-positive write to master_targets.csv | ✓ VERIFIED | _apply_name_gate() implemented with rapidfuzz token_set_ratio; NOT_FOUND if score <70; test_two_factor_gate_below_70_is_not_found passes. |
| 3 | Re-running /scout-detect is no-op; --force re-detects; ats_provider=manual never overwritten | ✓ VERIFIED | _should_skip() with manual-lock=absolute, 30d freshness window, force override. All idempotency tests pass (tests 7–10). |
| 4 | Borderline matches (gate 70–84) appear in ats_detection_review.csv with company, provider, score, ats_board_url | ✓ VERIFIED | _append_borderline() writes full REVIEW_CSV_FIELDNAMES row. test_borderline_appended_to_review_csv passes. |
| 5 | During /scout-run, unmapped companies trigger inline detect-one; result written back after run | ✓ VERIFIED | Step 2b in scout-run/SKILL.md lines 110–147. detect-one bash call documented. Deferred write-back to Step 8 documented. |
| 6 | grep -rn "commands/scout-run.md" skills/ returns zero matches (CON-08) | ✓ VERIFIED | grep exit code 1, zero matches confirmed. All 3 references rewritten to skills/scout-run/SKILL.md. |

**Score:** 6/6 truths verified

---

### Deferred Items

None — all 6 ROADMAP Phase 3 success criteria are scoped to this phase.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/ats/detect.py` | CLI with detect-one + detect-batch; two-factor gate; CSV write-back | ✓ VERIFIED | 841 lines; all required helper functions present |
| `tests/test_detection.py` | 17 tests covering DET-01..05, DET-07, STR-02, STR-04 | ✓ VERIFIED | 22 tests collected and passing (5 added in gap closure) |
| `tests/conftest.py` | Shared fixtures: mock_greenhouse_ok, mock_greenhouse_404, mock_greenhouse_zero_jobs | ✓ VERIFIED | 3 fixtures present |
| `tests/fixtures/master_targets_phase3_detect.csv` | 5 mixed-state rows (empty, manual, fresh, stale, none-cached) | ✓ VERIFIED | 5 data rows present |
| `skills/scout-detect/SKILL.md` | /scout-detect skill; ≥90 lines; name: scout-detect | ✓ VERIFIED | 183 lines; valid frontmatter |
| `skills/job-scout/references/file-contract.md` | ats_detection_review.csv row in Persistent files table | ✓ VERIFIED | Row added after runs.jsonl |
| `skills/scout-run/SKILL.md` | Step 2b inserted between Step 2 and Step 2.5 | ✓ VERIFIED | Step 2b at line 110; Step 2.5 at line 149 |
| `skills/job-scout/SKILL.md` | 2 CON-08 fixes at lines 46 and 105 | ✓ VERIFIED | Both replaced with skills/scout-run/SKILL.md |
| `skills/job-scout/references/search-config.md` | 1 CON-08 fix at line 28 | ✓ VERIFIED | Replaced with skills/scout-run/SKILL.md |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| scripts/ats/detect.py | scripts/ats/__init__.py:PROVIDERS | `for provider_name, provider in PROVIDERS.items()` | ✓ WIRED | Line 450 in _detect_one_company |
| scripts/ats/detect.py | rapidfuzz.fuzz.token_set_ratio | _apply_name_gate | ✓ WIRED | Line 204; ImportError hint at lines 54-62 |
| scripts/ats/detect.py | scripts/ats/dispatcher.py:load_caps_and_kill_switch | load_caps_and_kill_switch | ✓ WIRED | Lines 539 and 605; imported at line 72 |
| scripts/ats/detect.py | ats_detection_review.csv | _append_borderline | ✓ WIRED | Lines 767-769 in _cmd_detect_batch (main thread only) |
| scripts/ats/detect.py | master_targets.csv | _write_back | ✓ WIRED | Line 763 in _cmd_detect_batch (after futures drain) |
| skills/scout-detect/SKILL.md | scripts/ats/detect.py | Bash: detect-batch invocation | ✓ WIRED | 5 invocations at lines 54, 62, 71, 78, 86 |
| skills/scout-detect/SKILL.md | scripts/state.py resolve | Step 1 data_dir resolution | ✓ WIRED | Line 20 |
| skills/scout-detect/SKILL.md | scripts/validate_data.py | Step 1 validation | ✓ WIRED | Line 27 |
| skills/scout-run/SKILL.md | scripts/ats/detect.py | Bash: detect-one invocation in Step 2b | ✓ WIRED | Line 122 |
| skills/scout-run/SKILL.md | ats_provider sentinel "none" | Step 2b NOT_FOUND/ERROR branches | ✓ WIRED | Lines 134-135 (literal "none" used, not "none_detected") |

---

## Data-Flow Trace (Level 4)

Not applicable — this phase produces CLI scripts and skill prompt files (markdown). No components that render dynamic data from a data source were introduced. The detect.py CLI produces JSON output at the boundary.

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| --help exits 0 with subcommands | `python3 detect.py --help` | "Subcommands: detect-one, detect-batch" | ✓ PASS |
| unknown_cmd exits 1 | `python3 detect.py unknown_cmd` | "ERROR: unknown command 'unknown_cmd'" | ✓ PASS |
| 22 tests pass | `pytest tests/ -q` | "22 passed in 0.45s" | ✓ PASS |
| rapidfuzz functional | `fuzz.token_set_ratio("Airbnb Inc", "Airbnb")` | 100.0 | ✓ PASS |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| DET-01 | 03-01 | detect.py exposes detect-one + detect-batch CLI subcommands | ✓ SATISFIED | Both subcommands implemented; CLI smoke tests pass |
| DET-02 | 03-01 | Detection uses registry-order provider probes; stops at first CONFIRMED | ✓ SATISFIED | _detect_one_company iterates PROVIDERS.items() in order; test_provider_iteration_stops_at_first_confirmed passes |
| DET-03 | 03-01 | Two-factor gate: HTTP 200 + ≥1 job + rapidfuzz token_set_ratio ≥85 | ✓ SATISFIED | _apply_name_gate() implemented; 3 gate tests pass |
| DET-04 | 03-01, 03-03 | Negative results cached as ats_provider="none"; idempotent re-run | ✓ SATISFIED | NEG_SENTINEL="none"; _should_skip(); Step 2b defers write to Step 8 |
| DET-05 | 03-01 | Borderline matches appended to ats_detection_review.csv | ✓ SATISFIED | _append_borderline() writes full row schema; test passes |
| DET-06 | 03-02 | New skill skills/scout-detect/SKILL.md orchestrates batch detection | ✓ SATISFIED | 183-line SKILL.md with valid frontmatter and ONE-Bash-call invocation |
| DET-07 | 03-01, 03-03 | /scout-run Step 2b lazy inline; detect-batch appends runs.jsonl telemetry | ✓ SATISFIED | Step 2b inserted; _append_detection_telemetry writes run_type=detect_batch |
| STR-02 | 03-01, 03-02 | ats_slug_confidence populated: 1.0 confirmed, 0.7–0.94 review-band | ✓ SATISFIED | CONFIRMED path: str(round(confidence, 4)). BORDERLINE path: str(round(confidence, 4)) via _confidence_to_csv() — gap closed in commit 7928f78. D-02 zero_open_roles edge case correctly returns "". |
| STR-04 | 03-01, 03-02 | /scout-detect is idempotent; respects ats_provider=manual | ✓ SATISFIED | _should_skip() manual-lock is absolute; 30d freshness window; --force override |
| CON-08 | 03-03 | 3 dead commands/scout-run.md references rewritten | ✓ SATISFIED | grep -rn "commands/scout-run.md" skills/ returns 0 matches |

---

## Anti-Patterns Found

| File | Pattern | Severity | Impact |
|------|---------|----------|--------|
| `scripts/ats/detect.py` lines 24, 753 | String `none_detected` appears in prohibition comments | ℹ️ Info | Not a sentinel value — appears in docstrings/comments explicitly labeling what NOT to write. Binary pycache also matches. Not a blocker. |

**D-05 main-thread write verification:** _write_back and _append_borderline are called only at lines 763 and 769 inside _cmd_detect_batch (Steps E and F, after the futures drain loop at lines 684-685). Neither appears inside _detect_one_company (the worker function at line 421-503). The test_csv_write_back_main_thread_only test asserts this via source inspection. D-05 is clean.

**none_detected clarification:** The 2 occurrences in detect.py are in comment/docstring text explaining the prohibition ("NOT 'none_detected'"). The string never appears as an assigned value anywhere. The binary pycache match is expected. Zero occurrences in skills/. This is acceptable — prohibition documentation that names the forbidden string is correct engineering practice.

---

## Human Verification Required

### 1. Live /scout-detect run against real master_targets.csv

**Test:** With a real master_targets.csv containing known Greenhouse companies (e.g., Airbnb, Stripe), run `/scout-detect` and inspect the output.
**Expected:** ats_provider and ats_board_url populated for confirmed companies; ats_detection_review.csv created for borderlines with non-empty ats_slug_confidence (0.70–0.94 range); runs.jsonl appended with detect_batch line.
**Why human:** No live network access in automated checks; requires real ATS endpoint responses to exercise the full two-factor gate against production data.

---

## Gap Closure Record

### Original Gap (commit f73b86f)

**STR-02 / ROADMAP SC-1:** `_confidence_to_csv()` returned `""` for all non-CONFIRMED statuses. The `_cmd_detect_batch` BORDERLINE branch hardcoded `row["ats_slug_confidence"] = ""`. BORDERLINE rows in master_targets.csv showed empty ats_slug_confidence instead of the 0.7–0.94 score.

### Fix (commit 7928f78)

Three changes made:

1. **`_confidence_to_csv()` updated** (lines 344-360): BORDERLINE now returns `str(round(result.confidence, 4))` (e.g. `"0.78"`), except when `evidence.get("note") == "zero_open_roles"` which continues to return `""` (D-02 edge case — no job data means no name to score).

2. **`_cmd_detect_batch()` BORDERLINE branch updated** (line 730): replaced hardcoded `""` assignment with `_confidence_to_csv(gated)` call.

3. **Test extended** (`test_borderline_appended_to_review_csv`): added assertion at line 347 that `airbnb_row["ats_slug_confidence"] == "0.78"`. A separate test (`test_zero_jobs_borderline_writes_provider_but_empty_confidence`) covers the D-02 edge case, asserting `ats_slug_confidence == ""` for zero_open_roles.

### Re-Verification Results (2026-04-29)

| Check | Result |
|-------|--------|
| `_confidence_to_csv()` returns score for BORDERLINE (non-zero_open_roles) | ✓ CONFIRMED — lines 356-359 |
| `_cmd_detect_batch` BORDERLINE branch calls helper, not hardcoded `""` | ✓ CONFIRMED — line 730 |
| D-02 zero_open_roles returns `""` | ✓ CONFIRMED — lines 357-358 |
| `test_borderline_appended_to_review_csv` asserts `"0.78"` | ✓ CONFIRMED — line 347 |
| `test_zero_jobs_borderline_writes_provider_but_empty_confidence` asserts `""` | ✓ CONFIRMED — line 370 |
| 22/22 tests pass | ✓ CONFIRMED — `22 passed in 0.45s` |
| CON-08 grep gate | ✓ CONFIRMED — exit code 1, zero matches |

---

*Verified: 2026-04-29*
*Verifier: Claude (gsd-verifier)*

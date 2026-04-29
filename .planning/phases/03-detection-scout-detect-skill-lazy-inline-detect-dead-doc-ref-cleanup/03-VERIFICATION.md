---
phase: 03-detection-scout-detect-skill-lazy-inline-detect-dead-doc-ref-cleanup
verified: 2026-04-29T00:00:00Z
status: gaps_found
score: 5/6 success criteria verified
overrides_applied: 0
gaps:
  - truth: "ats_slug_confidence shows 0.7–0.94 for borderline matches in master_targets.csv (ROADMAP SC-1 + STR-02)"
    status: failed
    reason: "_confidence_to_csv() returns '' (empty string) for BORDERLINE status. The plan's locked decisions (D-02/borderline section in _cmd_detect_batch) explicitly write ats_slug_confidence='' and defer confidence scoring to the ats_detection_review.csv review flow. This conflicts with ROADMAP SC-1 ('ats_slug_confidence showing 0.7–0.94 for borderline ones') and STR-02 ('0.7–0.94 = review-band match'). The test test_borderline_appended_to_review_csv asserts empty ats_slug_confidence, locking in the deviation."
    artifacts:
      - path: "scripts/ats/detect.py"
        issue: "_confidence_to_csv() line 353-355 returns '' for any non-CONFIRMED status. BORDERLINE result gets ats_slug_confidence='' in _cmd_detect_batch line 724."
      - path: "tests/test_detection.py"
        issue: "test_borderline_appended_to_review_csv checks that master_targets ats_slug_confidence is empty for borderline — this test should instead assert a float value in [0.70, 0.84]."
    missing:
      - "Change _confidence_to_csv() to return str(round(result.confidence, 4)) for BORDERLINE status (e.g. '0.78' for a score-78 match)"
      - "Update test_borderline_appended_to_review_csv to assert ats_slug_confidence is a parseable float in [0.70, 0.84]"
      - "Update ROADMAP SC-1 wording or add an override if the 'leave empty' behavior is intentional (requires explicit user decision)"
---

# Phase 3: Detection + `/scout-detect` + Lazy Inline + CON-08 Verification Report

**Phase Goal:** Build the detection layer that populates ats_provider/ats_board_url/ats_slug_confidence/last_ats_hit_date columns in master_targets.csv via two paths: batch detection via new `/scout-detect` skill (top-30 connection-weighted companies), and lazy inline detection during `/scout-run` for unmapped companies.

**Verified:** 2026-04-29
**Status:** gaps_found
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | User runs `/scout-detect` and sees top-30 companies' ats_provider + ats_board_url populated; ats_slug_confidence shows 1.0 for confirmed matches and **0.7–0.94 for borderline ones** | ✗ FAILED | Confirmed path: ats_slug_confidence written correctly. Borderline path: _confidence_to_csv() returns "" for BORDERLINE; ats_slug_confidence left empty. Contradicts ROADMAP SC-1 and STR-02 requirement text. |
| 2 | Wrong-company collision rejected by two-factor gate (name fuzzy match ≥85%); no false-positive write to master_targets.csv | ✓ VERIFIED | _apply_name_gate() implemented with rapidfuzz token_set_ratio; NOT_FOUND if score <70; test_two_factor_gate_below_70_is_not_found passes. |
| 3 | Re-running /scout-detect is no-op; --force re-detects; ats_provider=manual never overwritten | ✓ VERIFIED | _should_skip() with manual-lock=absolute, 30d freshness window, force override. All idempotency tests pass (tests 7–10). |
| 4 | Borderline matches (gate 70–84) appear in ats_detection_review.csv with company, provider, score, ats_board_url | ✓ VERIFIED | _append_borderline() writes full REVIEW_CSV_FIELDNAMES row. test_borderline_appended_to_review_csv passes. |
| 5 | During /scout-run, unmapped companies trigger inline detect-one; result written back after run | ✓ VERIFIED | Step 2b in scout-run/SKILL.md lines 110–147. detect-one bash call documented. Deferred write-back to Step 8 documented. |
| 6 | grep -rn "commands/scout-run.md" skills/ returns zero matches (CON-08) | ✓ VERIFIED | grep exit code 1, zero matches confirmed. All 3 references rewritten to skills/scout-run/SKILL.md. |

**Score:** 5/6 truths verified

---

### Gap Detail: ROADMAP SC-1 / STR-02 — Borderline ats_slug_confidence

**What the requirements say:**

- ROADMAP SC-1: "ats_slug_confidence showing 1.0 for two-factor-confirmed matches and **0.7–0.94 for borderline ones**"
- STR-02: "0.7–0.94 = review-band match"

**What the implementation does:**

```python
# scripts/ats/detect.py line 344-355
def _confidence_to_csv(result: DetectionResult) -> str:
    if result.status == DetectionStatus.CONFIRMED:
        return str(round(result.confidence, 4))
    return ""   # BORDERLINE, NOT_FOUND, ERROR all return empty string
```

And in _cmd_detect_batch (line 724):
```python
row["ats_slug_confidence"] = ""  # explicit: review pending
```

**Root cause:** The plan's locked decision D-02 and the borderline handling section of _cmd_detect_batch.action explicitly chose to leave ats_slug_confidence empty for BORDERLINE rows, deferring to the review CSV. This is internally consistent design, but it was not reflected as a deviation from STR-02 in any SUMMARY or plan document.

**Impact:** ROADMAP SC-1 cannot be demonstrated as written. A user inspecting master_targets.csv after /scout-detect will not see 0.7–0.94 values for borderline matches — they will see empty strings. The score IS captured in ats_detection_review.csv (name_match_score column), so the data exists, but not in the column the requirement specifies.

**Resolution options (requires user decision):**
1. Change _confidence_to_csv to write the confidence for BORDERLINE (e.g. "0.78") — aligns with requirements, removes empty-means-pending signal
2. Add an override to this VERIFICATION.md frontmatter accepting the deviation — updates the requirements contract to match the implementation
3. Store confidence in BOTH ats_detection_review.csv (current) AND ats_slug_confidence (new) — satisfies the requirement without changing the review flow

---

### Deferred Items

None — all 6 ROADMAP Phase 3 success criteria are scoped to this phase.

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `scripts/ats/detect.py` | CLI with detect-one + detect-batch; two-factor gate; CSV write-back | ✓ VERIFIED | 841 lines; all required helper functions present |
| `tests/test_detection.py` | 17 tests covering DET-01..05, DET-07, STR-02, STR-04 | ✓ VERIFIED | 17 tests collected and passing |
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
| STR-02 | 03-01, 03-02 | ats_slug_confidence populated: 1.0 confirmed, 0.7–0.94 review-band | ✗ PARTIAL | CONFIRMED path writes confidence correctly. BORDERLINE path writes "" (empty) — contradicts requirement text and ROADMAP SC-1. |
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
**Expected:** ats_provider and ats_board_url populated for confirmed companies; ats_detection_review.csv created for borderlines; runs.jsonl appended with detect_batch line.
**Why human:** No live network access in automated checks; requires real ATS endpoint responses to exercise the full two-factor gate against production data.

### 2. Borderline confidence behavior (gap resolution required first)

**Test:** After resolving the STR-02 gap (whether to write confidence for BORDERLINE or accept empty), verify the chosen behavior in a live run.
**Expected:** Depends on gap resolution decision.
**Why human:** Requires explicit developer decision on whether to implement the 0.7–0.94 confidence writing for borderlines or formally accept the deviation via an override.

---

## Gaps Summary

**1 gap blocking full ROADMAP SC-1 / STR-02 compliance.**

The implementation leaves `ats_slug_confidence` empty for BORDERLINE detections (score 70–84). ROADMAP SC-1 and STR-02 both specify that borderline matches should populate `ats_slug_confidence` with a value in the 0.7–0.94 range. The plan's locked decision overrode this without documenting the deviation.

The gap has a clear fix: change `_confidence_to_csv()` to return the confidence string for BORDERLINE status, and update the test. Alternatively, the developer can explicitly accept this deviation via an override entry in this file's frontmatter.

**All other 9 requirements (DET-01..07, STR-04, CON-08) are fully implemented and tested.** The core detection infrastructure (detect.py, /scout-detect skill, Step 2b lazy inline, CON-08 cleanup) is solid and production-ready.

---

*Verified: 2026-04-29*
*Verifier: Claude (gsd-verifier)*

---
phase: "05"
plan: "01"
subsystem: tests/fixtures
tags: [tdd, wave0, red-tests, dedup, tracker, phase5]
dependency_graph:
  requires: []
  provides:
    - 23 RED pytest tests (14 dedup + 9 tracker)
    - tests/fixtures/linkedin_candidates_sample.json
    - tests/fixtures/ats_raw_sample/ (3 fixtures)
    - tests/fixtures/runs_jsonl_history.jsonl
  affects:
    - plans/05-02 (dedupe.py — must turn 11 dedup tests GREEN)
    - plans/05-03 (tracker_utils.py — must turn 6 tracker tests GREEN)
    - plans/05-04 (runs_log.py — must turn 4 telemetry tests GREEN)
    - plans/05-05 (SKILL.md — must turn 2 document-grep tests GREEN)
tech_stack:
  added: []
  patterns:
    - TDD Wave 0 RED scaffold (all tests fail before implementation)
    - pytest PROJECT_ROOT bootstrap (consistent with test_providers_phase4.py)
    - tmp_path xlsx round-trip (consistent with test_migration.py)
    - Fixture-driven dedup scenario coverage (auto-merge, review-band, keep-both)
key_files:
  created:
    - tests/test_dedup_phase5.py
    - tests/test_tracker_phase5.py
    - tests/fixtures/linkedin_candidates_sample.json
    - tests/fixtures/ats_raw_sample/greenhouse/acme.json
    - tests/fixtures/ats_raw_sample/lever/example.json
    - tests/fixtures/ats_raw_sample/greenhouse/keepboth.json
    - tests/fixtures/runs_jsonl_history.jsonl
    - tests/fixtures/SOURCE.md
    - tests/fixtures/ats_raw_sample/__init__.py (x3 package markers)
  modified: []
decisions:
  - "test_jsonld_routing_career_page_url is GREEN from day 0 (D-4 guard against schema.py rename)"
  - "test_flagged_stale_count_var is GREEN from day 0 (CON-14 Pitfall 6 guard — dict key already correct)"
  - "derive_linkedin_slug spec: 'Acme Corp' → 'acme-corp' (Corp NOT stripped); ', Inc.' / ' LLC' stripped"
  - "is_enrichment_candidate: ATS source + posted ≤30d + base_score + 1 >= a_threshold"
  - "runs_jsonl_history.jsonl: 6 lines (5 prior OK_WITH_RESULTS for acme|greenhouse, 1 current OK_ZERO)"
metrics:
  duration: "~5 minutes"
  completed: "2026-04-28"
  tasks_completed: 3
  files_created: 12
---

# Phase 5 Plan 01: Wave 0 RED Tests + Fixture Set — Summary

Wave 0 RED test scaffolding for Phase 5. All 23 new tests are intentionally failing; they define the behavioral contract that Wave 2 plans (05-02, 05-03, 05-04) must fulfill. 2 tests are intentionally GREEN from day 0 as regression guards.

---

## What Was Built

### Task 1: Fixture set (3 commits → e19408a)

5 JSON fixtures + 1 JSONL fixture + 1 SOURCE.md + 3 empty `__init__.py` package markers.

**Dedup scenario coverage:**
- `linkedin_candidates_sample.json[0]` + `ats_raw_sample/greenhouse/acme.json`: exact title match → `auto_merge` scenario
- `linkedin_candidates_sample.json[1]` + `ats_raw_sample/lever/example.json`: "Software Engineer II Backend Platform" vs "Backend Platform Engineer" → `review_band` scenario
- `linkedin_candidates_sample.json[2]` + `ats_raw_sample/greenhouse/keepboth.json`: "Marketing Manager Growth" vs "Sales Director Enterprise" → `keep_both` scenario

**Regression-suspect + board-broken signal (runs_jsonl_history.jsonl):**
- Lines 1–5: `acme|greenhouse` = `OK_WITH_RESULTS` (listing_count 3–5)
- Line 6 (current): `acme|greenhouse` = `OK_ZERO` → regression suspect
- Lines 2–6: `pass2_board_status.wellfound = 0` → board-broken signal

### Task 2: tests/test_dedup_phase5.py (b671d80)

14 RED tests covering DDP-01..08 + CON-10/11/15 + D-1..D-4 locked decisions:

| Test | Requirement | RED Cause |
|------|-------------|-----------|
| test_two_key_gate | DDP-01/03 | `ImportError: ats.dedupe` |
| test_tiered_band | DDP-02 | `ImportError: ats.dedupe` |
| test_dedup_decisions_logged | DDP-04 | `ImportError: ats.dedupe` |
| test_ats_tier_bump_30d | DDP-05 | `ImportError: ats.dedupe` |
| test_linkedin_slug_runtime | DDP-04 (D-3) | `ImportError: ats.dedupe` |
| test_enrich_pre_bump | DDP-04 (D-1) | `ImportError: ats.dedupe` |
| test_enrich_then_tier_order | DDP-05 (D-1) | `ImportError: ats.dedupe` |
| test_regression_suspect | DDP-06/08 | `ImportError: _find_regression_suspects` |
| test_regression_suspects_logged | DDP-06 (D-2) | `TypeError: unexpected kwarg` |
| test_pass2_board_broken | DDP-07/CON-15 | `ImportError: _find_pass2_board_broken` |
| test_pass2_board_status_logged | DDP-07 (D-2) | `TypeError: unexpected kwarg` |
| test_jsonld_routing_career_page_url | D-4 | **GREEN** (schema guard) |
| test_linkedin_backoff | CON-10/11 | `AssertionError: 10-15s not in SKILL.md` |
| test_jd_resilient_parse | CON-11/12 | `AssertionError: selectors not in chrome-setup.md` |

### Task 3: tests/test_tracker_phase5.py (da39c94)

9 RED tests covering CON-12/13/14/15/20:

| Test | Requirement | RED Cause |
|------|-------------|-----------|
| test_extract_linkedin_job_id_linkedin_url | CON-13 | `ImportError: extract_linkedin_job_id` |
| test_extract_linkedin_job_id_non_linkedin_returns_none | CON-13 | `ImportError: extract_linkedin_job_id` |
| test_extract_linkedin_job_id_search_path | CON-13 | `ImportError: extract_linkedin_job_id` |
| test_extract_dedup_key_linkedin_returns_id_string | CON-13 | `ImportError: extract_dedup_key` |
| test_extract_dedup_key_non_linkedin_returns_url | CON-13 | `ImportError: extract_dedup_key` |
| test_extract_dedup_key_none_returns_none | CON-13 | `ImportError: extract_dedup_key` |
| test_flagged_stale_count_var | CON-14 (Pitfall 6) | **GREEN** (dict key already `flagged_stale`) |
| test_user_column_preservation_round_trip | CON-15/20 | `AssertionError: None != "My Notes"` |
| test_user_column_preservation_after_multiple_appends | CON-20 | `AssertionError: None != "My Notes"` |

---

## Test State Summary

```
Phase 5 tests: 23 collected
  - 21 FAIL (correct RED state — Wave 2 will flip these GREEN)
  - 2 PASS (intentional regression guards — must stay GREEN through all phases)
Existing Phase 1-4 tests: 37 collected, 37 passed (no regression)
Total: 60 tests
```

---

## Deviations from Plan

None — plan executed exactly as written.

The 2 pre-emptively passing tests (`test_jsonld_routing_career_page_url` and
`test_flagged_stale_count_var`) are by design per the plan spec:
- D-4 guard: `career_page_url` column already exists in `schema.py`
- CON-14 guard: `"flagged_stale"` dict key already correct in `tracker_utils.py` line 260

---

## Locked Decision Encodings

| Decision | Test that encodes it |
|----------|---------------------|
| D-1: pre-bump enrichment scope | `test_enrich_pre_bump`, `test_enrich_then_tier_order` |
| D-2: telemetry extends runs.jsonl (no new files) | `test_regression_suspects_logged`, `test_pass2_board_status_logged` |
| D-3: LinkedIn slug derived at runtime | `test_linkedin_slug_runtime` |
| D-4: `career_page_url` column (not `careers_url`) | `test_jsonld_routing_career_page_url` |

## Pitfall Guards Encoded

| Pitfall | Test that guards it |
|---------|---------------------|
| P5: regression-suspect reads `[-6:-1]` for prior, `[-1]` for current | `test_regression_suspect` (fixture has exactly 6 lines) |
| P6: dict key stays `"flagged_stale"`, not `"flagged_stale_count"` | `test_flagged_stale_count_var` |

---

## Known Stubs

None — this plan creates only tests + fixtures, no production code.

---

## Threat Flags

None — all files are test fixtures and pytest modules. No new production surface introduced.

---

## Self-Check: PASSED

Files verified to exist:
- tests/test_dedup_phase5.py: FOUND
- tests/test_tracker_phase5.py: FOUND
- tests/fixtures/linkedin_candidates_sample.json: FOUND
- tests/fixtures/ats_raw_sample/greenhouse/acme.json: FOUND
- tests/fixtures/ats_raw_sample/lever/example.json: FOUND
- tests/fixtures/ats_raw_sample/greenhouse/keepboth.json: FOUND
- tests/fixtures/runs_jsonl_history.jsonl: FOUND
- tests/fixtures/SOURCE.md: FOUND

Commits verified:
- e19408a: test(05-01): add Phase 5 Wave 0 fixture set
- b671d80: test(05-01): add Wave 0 RED tests for DDP-01..08, CON-10/11/15
- da39c94: test(05-01): add Wave 0 RED tests for CON-12/13/14/15/20

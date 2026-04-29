---
phase: 04-remaining-providers-lever-ashby-smartrecruiters-workday-json-ld-fallback-filtering-layer
plan: "01"
subsystem: ats-providers
tags: [wave-0, scaffolding, tdd-red, fixtures, base-protocol]
dependency_graph:
  requires: []
  provides:
    - FetchResult.auth_required field (base.py) consumed by workday.py (Plan 04-03)
    - BOARD_URL_PATTERNS skip guard (detect.py) consumed by jsonld.py registration (Plan 04-04)
    - 15 RED tests (test_providers_phase4.py) turned GREEN by Plans 04-02, 04-03, 04-04, 04-05
    - 5 fixture sets consumed by all Phase 4 provider tests
  affects:
    - scripts/ats/providers/base.py (additive field, no breaking change)
    - scripts/ats/detect.py (guard before semaphore acquire)
    - tests/ (new test file + 5 new fixture directories)
tech_stack:
  added: []
  patterns:
    - TDD RED: 15 failing tests define behavioral contract before Wave 2 implementation
    - Fixture-driven testing: sanitized JSON fixtures per provider in tests/fixtures/ats/
    - D-4 provenance: SOURCE.md documents live vs synthetic fixture origin
key_files:
  created:
    - tests/test_providers_phase4.py
    - tests/fixtures/ats/lever/spotify.json
    - tests/fixtures/ats/lever/__init__.py
    - tests/fixtures/ats/ashby/ashby.json
    - tests/fixtures/ats/ashby/__init__.py
    - tests/fixtures/ats/smartrecruiters/visa.json
    - tests/fixtures/ats/smartrecruiters/__init__.py
    - tests/fixtures/ats/workday/workday_wd5.json
    - tests/fixtures/ats/workday/workday_synthetic_wd1.json
    - tests/fixtures/ats/workday/workday_synthetic_wd3.json
    - tests/fixtures/ats/workday/__init__.py
    - tests/fixtures/ats/workday/SOURCE.md
    - tests/fixtures/jsonld/example_careers.html
    - tests/fixtures/jsonld/__init__.py
  modified:
    - scripts/ats/providers/base.py (auth_required field added)
    - scripts/ats/detect.py (BOARD_URL_PATTERNS skip guard added)
    - tests/test_detection.py (MockBorderlineProvider BOARD_URL_PATTERNS fix)
decisions:
  - "D-1 landed: auth_required: bool = False on FetchResult; default propagates to all existing call sites"
  - "D-3 landed: detect.py skips providers with empty BOARD_URL_PATTERNS before semaphore acquire"
  - "D-4 landed: workday/SOURCE.md documents wd5 live-verified, wd1+wd3 synthetic (422 during research)"
metrics:
  duration_seconds: 299
  completed_date: "2026-04-29"
  tasks_completed: 3
  tasks_total: 3
  files_created: 14
  files_modified: 3
---

# Phase 04 Plan 01: Wave 0 Scaffolding Summary

**One-liner:** Wave 0 scaffolding — auth_required field on FetchResult, BOARD_URL_PATTERNS skip guard in detect.py, 15 RED tests + 5 fixture sets freezing the Phase 4 behavioral contract.

## What Was Built

Three atomic deliverables that unblock all Wave 2/3 parallel plans:

1. **`scripts/ats/providers/base.py`** — `auth_required: bool = False` added to `FetchResult` dataclass (PRV-05 / D-1). Workday.py (Plan 04-03) sets this to `True` when it receives a 401/403 with CSRF markers; the dispatcher writes `workday_auth_required` reason to `runs.jsonl`. All existing call sites (greenhouse, dispatcher) unchanged — the `False` default propagates automatically.

2. **`scripts/ats/detect.py`** — D-3 skip guard inserted at the top of the `PROVIDERS` iteration loop. Any provider with empty/falsy `BOARD_URL_PATTERNS` is silently skipped before semaphore acquisition. `jsonld.py` (Plan 04-04) will have `BOARD_URL_PATTERNS=[]`; without this guard it would always return `NOT_FOUND` and waste a network call per company.

3. **`tests/test_providers_phase4.py` + 5 fixture sets** — 15 RED test functions covering PRV-01 through PRV-09, STR-01, STR-03. All fail now (no provider modules); they turn GREEN as Wave 2/3 plans land. Five fixture directories:
   - `lever/spotify.json` — bare JSON array (Lever specificity), 3 sanitized jobs, `createdAt` epoch_ms
   - `ashby/ashby.json` — includes `isListed=false` job for PRV-02 filter test
   - `smartrecruiters/visa.json` — combined `list`+`detail` fixture (jobAd.sections shape)
   - `workday/workday_wd5.json` + synthetic wd1/wd3 — live-verified wd5 shape + D-4 synthetic fixtures with "Posted Today" / "Posted 30+ Days Ago"
   - `jsonld/example_careers.html` — schema.org/JobPosting HTML with `application/ld+json` block

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed test_detection.py MockBorderlineProvider breaking under D-3 guard**
- **Found during:** Task 1 verification (existing test suite run)
- **Issue:** `test_borderline_appended_to_review_csv` used a `MockBorderlineProvider` with `BOARD_URL_PATTERNS = []`. The new D-3 guard correctly skips any provider with empty patterns — this silently skipped the mock provider, causing the test to report 0 BORDERLINE results and fail the CSV assertion.
- **Fix:** Changed `MockBorderlineProvider.BOARD_URL_PATTERNS` to `[r"^https?://boards-api\.greenhouse\.io/v1/boards/([^/]+)"]` — a non-empty pattern that passes the D-3 guard. Added comment explaining why non-empty is required.
- **Files modified:** `tests/test_detection.py` (1 line changed in mock class definition)
- **Commit:** `9a00e38`

## Known Stubs

None. This plan creates no data-flowing UI stubs — all outputs are scaffolding (dataclass field, loop guard, test infrastructure, fixture files). No placeholder text flows to any rendered output.

## Threat Flags

None found beyond those already in the PLAN.md threat model:
- T-04-01: Fixture PII — mitigated. All fixture IDs are obviously-synthetic (`1ff4a4e3-aaaa-bbbb-cccc-...`). SOURCE.md documents sanitization log.
- T-04-02: FetchResult tamper — mitigated. `frozen=True` dataclass; `auth_required=False` default.
- T-04-05: Workday provenance — mitigated. SOURCE.md tags wd1/wd3 as SYNTHETIC per D-4.

## Self-Check

### Files Exist
- scripts/ats/providers/base.py: FOUND
- scripts/ats/detect.py: FOUND
- tests/test_providers_phase4.py: FOUND
- tests/fixtures/ats/lever/spotify.json: FOUND
- tests/fixtures/ats/ashby/ashby.json: FOUND
- tests/fixtures/ats/smartrecruiters/visa.json: FOUND
- tests/fixtures/ats/workday/workday_wd5.json: FOUND
- tests/fixtures/ats/workday/workday_synthetic_wd1.json: FOUND
- tests/fixtures/ats/workday/workday_synthetic_wd3.json: FOUND
- tests/fixtures/ats/workday/SOURCE.md: FOUND
- tests/fixtures/jsonld/example_careers.html: FOUND

### Commits Exist
- 9a00e38: feat(04-01): add auth_required to FetchResult + D-3 BOARD_URL_PATTERNS guard
- 664e12d: feat(04-01): create 5 fixture sets for Wave 0
- e74f563: test(04-01): add 15 RED tests for PRV-01..09, STR-01, STR-03 (Wave 0)

## Self-Check: PASSED

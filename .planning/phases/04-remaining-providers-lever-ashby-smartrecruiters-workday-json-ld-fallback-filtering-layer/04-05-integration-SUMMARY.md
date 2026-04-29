---
phase: 04-remaining-providers-lever-ashby-smartrecruiters-workday-json-ld-fallback-filtering-layer
plan: "05"
subsystem: ats-filtering-layer
tags: [filtering, registry, dispatcher, preview, config]
dependency_graph:
  requires: [04-01, 04-02, 04-03, 04-04]
  provides: [PRV-05, PRV-06, PRV-07, PRV-08, PRV-09, STR-03]
  affects: [scripts/ats/normalize.py, scripts/ats/__init__.py, scripts/ats/dispatcher.py, scripts/ats/preview.py, templates/config.json]
tech_stack:
  added: []
  patterns: [post-fetch-filter-chain, per-provider-override, registry-driven-dispatch, auth-telemetry]
key_files:
  created: []
  modified:
    - scripts/ats/normalize.py
    - scripts/ats/__init__.py
    - scripts/ats/dispatcher.py
    - scripts/ats/preview.py
    - templates/config.json
decisions:
  - "filter_stale resolves provider name from listing.source ('ats:workday' -> 'workday') when provider_name arg is empty, enabling per-provider overrides without requiring callers to pass provider_name explicitly"
  - "apply_filters receives no provider_name; each listing carries its own source, so per-provider override works per-listing automatically"
  - "auth_required maps to OK_ZERO + non-None error (not a new RunOutcome value) to preserve 3-state invariant and distinguish from regular OK_ZERO via runs.jsonl error field"
metrics:
  duration_seconds: 223
  completed: "2026-04-29"
  tasks_completed: 4
  tasks_total: 4
  files_modified: 5
---

# Phase 04 Plan 05: Integration — Filter Helpers + PROVIDERS Registry + auth_required + preview.py Wire-in + config.json

Wave 3 integration: post-fetch filter chain (stale, regional dupes, evergreen) + full 6-provider PROVIDERS registry + Workday CSRF telemetry + apply_filters wired into preview.py + ats section in config.json.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add filter_stale, collapse_regional_dupes, filter_evergreen, apply_filters to normalize.py | 2494bf8 | scripts/ats/normalize.py |
| 2 | Wire lever, ashby, smartrecruiters, workday, jsonld into PROVIDERS registry | e8723df | scripts/ats/__init__.py |
| 3 | Propagate FetchResult.auth_required to FetchOutcome in dispatcher | 352d941 | scripts/ats/dispatcher.py |
| 4 | Add ats section to config.json + wire apply_filters into preview.py | b2e573d | scripts/ats/preview.py, templates/config.json |

## What Was Built

### Filter helpers (normalize.py)

Four new public functions appended after `compute_missing_fields`:

- `_normalize_title(title)` — internal; casefold + strip non-alphanumeric + collapse whitespace. Used as grouping key for collapse_regional_dupes and match input for filter_evergreen.
- `filter_stale(listings, max_age_days=60, provider_name="", provider_overrides=None, today=None)` — drops listings older than effective_max. Per-listing provider resolution: explicit `provider_name` arg, then strips "ats:" prefix from `listing.source`. Keeps empty/unparseable posted_date (safe default per T-04-27).
- `collapse_regional_dupes(listings)` — groups by (source, company, normalized_title); merges multi-location duplicates into one Listing with comma-joined locations; "Multiple Locations" fallback when all locations empty (Pitfall 8 guard).
- `filter_evergreen(listings, blocklist_re=None)` — drops listings whose normalized title matches the 8-term regex at start of string. Default pattern covers: general application, talent network, future opportunities, join our team, connect with us, expression of interest, always hiring, passive candidate.
- `apply_filters(outcomes, config=None)` — wrapper; applies stale → regional → evergreen for OK_WITH_RESULTS outcomes only; non-OK pass through; reads `posted_date_max_age_days` and `provider_posted_date_overrides` from config dict.

### PROVIDERS registry (__init__.py)

PROVIDERS dict extended from 1 entry (greenhouse only) to 6 entries:
```
greenhouse → lever → ashby → smartrecruiters → workday → jsonld
```
Detection order preserved (greenhouse first; jsonld last, D-3 guard). Each provider registered as its module (duck-typed Protocol conformance, no instances).

### Dispatcher auth_required (dispatcher.py)

`_execute_one()` now checks `getattr(fetch_result, "auth_required", False)` before the listings-empty branch. When True: returns `FetchOutcome(outcome=OK_ZERO, error="<provider>_auth_required", listings=[])`. This makes Workday CSRF tenants distinguishable from regular zeros in runs.jsonl — `error` field is None for regular OK_ZERO, non-None for auth-required.

### preview.py + config.json

`preview.py` now calls `apply_filters(outcomes, config=ats_cfg)` after `fetch_all()` and before the raw-persistence loop. Config loaded from `config.json`'s `ats` section; wrapped in try/except so read failures fall back to apply_filters defaults.

`templates/config.json` gets a new top-level `ats` key:
- `posted_date_max_age_days: 60` — global default
- `provider_posted_date_overrides: {workday: 90, greenhouse: 30}` — STR-03
- `concurrency_disabled: false` — kill-switch
- `provider_concurrency_caps` for all 6 providers (greenhouse=10, lever=5, ashby=8, smartrecruiters=5, workday=3, jsonld=3)

## Test Results

All 15 Phase 4 RED tests turned GREEN:

| Test | Status |
|------|--------|
| test_lever_to_listing | GREEN (Wave 2) |
| test_lever_posted_date_epoch | GREEN (Wave 2) |
| test_ashby_filters_unlisted | GREEN (Wave 2) |
| test_ashby_to_listing | GREEN (Wave 2) |
| test_sr_to_listing | GREEN (Wave 2) |
| test_sr_description_from_detail | GREEN (Wave 2) |
| test_workday_to_listing | GREEN (Wave 2) |
| test_workday_posted_on_parsing | GREEN (Wave 2) |
| test_workday_csrf_detection | GREEN (Wave 2) |
| test_filter_stale | GREEN (this plan) |
| test_filter_stale_per_provider_override | GREEN (this plan) |
| test_collapse_regional_dupes | GREEN (this plan) |
| test_filter_evergreen | GREEN (this plan) |
| test_providers_registry_has_five | GREEN (this plan) |
| test_jsonld_extraction | GREEN (Wave 2) |

Full suite: 37/37 passed (test_migration.py: 10, test_detection.py: 12, test_providers_phase4.py: 15).

## Decisions Made

1. **filter_stale provider resolution from listing.source** — The test `test_filter_stale_per_provider_override` passes `provider_overrides={"workday": 90}` without a `provider_name` arg. The plan spec included `provider_name=""` as a parameter but the test relies on the function being able to match overrides using the listing's own `source` field. Implemented per-listing resolution: strip "ats:" prefix from `listing.source` when `provider_name` is empty. This is strictly more capable than the plan spec and makes the filter callable from `apply_filters` without needing to pass `provider_name` per outcome.

2. **auth_required → OK_ZERO + non-None error (not a new enum value)** — Preserves the 3-state RunOutcome invariant (DSP-05). Regular OK_ZERO has `error=None`; auth-required OK_ZERO has `error="<provider>_auth_required"`. Both are distinguishable in runs.jsonl. Phase 5's regression detection can filter on `error is not None` to separate them.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written. One design clarification was needed (filter_stale provider resolution from listing.source — see Decisions Made section); this was a spec gap, not a deviation. The implemented behavior is strictly a superset of the spec.

## Known Stubs

None. All filter functions are fully implemented and wired end-to-end.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes beyond what the plan's threat model covers.

## Self-Check: PASSED

**Files created/modified:**
- [x] FOUND: scripts/ats/normalize.py (155 lines added)
- [x] FOUND: scripts/ats/__init__.py (16 lines added)
- [x] FOUND: scripts/ats/dispatcher.py (19 lines added)
- [x] FOUND: scripts/ats/preview.py (17 lines added)
- [x] FOUND: templates/config.json (ats section added)

**Commits verified:**
- [x] FOUND: 2494bf8 (Task 1 — normalize.py filter helpers)
- [x] FOUND: e8723df (Task 2 — PROVIDERS registry)
- [x] FOUND: 352d941 (Task 3 — dispatcher auth_required)
- [x] FOUND: b2e573d (Task 4 — preview.py + config.json)

**Test results:**
- [x] 15/15 Phase 4 tests GREEN
- [x] 37/37 full suite GREEN

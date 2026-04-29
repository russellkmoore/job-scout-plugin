---
phase: 04-remaining-providers-lever-ashby-smartrecruiters-workday-json-ld-fallback-filtering-layer
plan: "02"
subsystem: ats-providers
tags: [lever, ashby, provider, ats, prv-01, prv-02]
dependency_graph:
  requires: [04-01]
  provides: [lever-provider, ashby-provider]
  affects: [scripts/ats/providers/, tests/test_providers_phase4.py]
tech_stack:
  added: []
  patterns: [provider-protocol-duck-typing, 3-level-sibling-bootstrap, bare-array-fetch-lever, object-wrapped-fetch-ashby, epoch-ms-to-iso-date, islisted-filter]
key_files:
  created:
    - scripts/ats/providers/lever.py
    - scripts/ats/providers/ashby.py
  modified: []
decisions:
  - "Lever bare-array response parsed with resp.json() or [] directly — no data.get('jobs') wrapper"
  - "Ashby isListed=False filter applied in fetch() before to_listing() — one-line guard per PRV-02 locked decision"
  - "Company derived from hostedUrl/jobUrl regex in both providers — neither has company_name field"
  - "createdAt epoch_ms / 1000 before fromtimestamp() — critical Pitfall 4 guard for Lever"
metrics:
  duration: "~4 minutes"
  completed: "2026-04-29T07:10:11Z"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 04 Plan 02: Lever + Ashby Providers Summary

Implemented Lever (PRV-01) and Ashby (PRV-02) provider modules, both conforming to the Provider Protocol established in Phase 2. Four RED tests from Plan 04-01 turned GREEN. No regressions in the existing 22 tests.

## One-liner

Lever provider with bare-array fetch + epoch_ms-to-ISO conversion, and Ashby provider with object-wrapped fetch + isListed=False filter and FullTime→Full-time normalization.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement scripts/ats/providers/lever.py | f8a14ce | scripts/ats/providers/lever.py |
| 2 | Implement scripts/ats/providers/ashby.py | f18f948 | scripts/ats/providers/ashby.py |

## What Was Built

### lever.py (338 lines, PRV-01)

- `NAME = "lever"`, two `BOARD_URL_PATTERNS` (jobs.lever.co + api.lever.co)
- `LIST_URL_TEMPLATE = "https://api.lever.co/v0/postings/{slug}?mode=json"`
- Bare-array fetch: `resp.json() or []` — NOT `data.get("jobs", [])` (critical difference from Greenhouse/Ashby)
- `createdAt` epoch milliseconds → ISO date: `date.fromtimestamp(epoch_ms / 1000).isoformat()`
- Company extracted from `hostedUrl` via `re.search(r'jobs\.lever\.co/([^/]+)/', url)`
- `_HTMLStripper` + `_strip_html()` copied verbatim from greenhouse.py
- Per-job `ValueError` swallow with `stderr` WARNING (T-04-06 mitigation)
- CON-04 compliant install hints (pipx/venv, no `break-system-packages`)

### ashby.py (358 lines, PRV-02)

- `NAME = "ashby"`, two `BOARD_URL_PATTERNS` (jobs.ashbyhq.com + api.ashbyhq.com)
- `LIST_URL_TEMPLATE = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"`
- Object-wrapped fetch: `data.get("jobs", []) or []`
- PRV-02 LOCKED: `if not raw_job.get("isListed", True): continue` before `to_listing()`
- `publishedAt[:10]` ISO date extraction (already date-shaped — no epoch conversion needed)
- `employmentType` normalization dict: `{"FullTime": "Full-time", "PartTime": "Part-time", ...}`
- Case-sensitive slug preserved (Ashby distinguishes "Ashby" from "ashby")
- No-pagination comment per assumption A1

## Tests Turned GREEN

| Test | Requirement | Status |
|------|-------------|--------|
| test_lever_to_listing | PRV-01 | GREEN |
| test_lever_posted_date_epoch | PRV-01 | GREEN |
| test_ashby_filters_unlisted | PRV-02 | GREEN |
| test_ashby_to_listing | PRV-02 | GREEN |

Existing tests (22): all still GREEN (test_migration.py + test_detection.py).

## Deviations from Plan

None — plan executed exactly as written.

Both providers follow the greenhouse.py structure verbatim with per-provider field mapping substitutions. The `_HTMLStripper` class and `_strip_html()` helper are copied verbatim from greenhouse.py (not re-implemented), as specified.

## Known Stubs

None. Both providers are fully wired for their API endpoints. The PROVIDERS registry wiring (scripts/ats/__init__.py) is Plan 04-05's responsibility — test_providers_registry_has_five remains RED by design until that plan lands.

## Threat Flags

None. All threat model items from the plan's `<threat_model>` are covered:
- T-04-06: Per-job ValueError swallow with stderr WARNING implemented in both providers
- T-04-07: _strip_html (HTMLParser + html.unescape) copied verbatim from greenhouse.py
- T-04-08: Accepted — no unbounded loop risk (all jobs in one call, no pagination)
- T-04-09: detect() populates `evidence["first_job_company_name"]` for DET-03 name gate

## Self-Check: PASSED

- `test -f scripts/ats/providers/lever.py` → EXISTS
- `test -f scripts/ats/providers/ashby.py` → EXISTS
- `git log --oneline` shows f8a14ce (lever) and f18f948 (ashby)
- 4 target tests GREEN, 22 existing tests GREEN
- Only lever.py and ashby.py modified (file boundary respected)

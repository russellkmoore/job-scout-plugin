---
phase: 4
slug: remaining-providers-lever-ashby-smartrecruiters-workday-json-ld-fallback-filtering-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-29
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x |
| **Config file** | none (invoke directly via venv python) |
| **Quick run command** | `~/.job-scout-venv/bin/python3 -m pytest tests/test_providers_phase4.py -x -q` |
| **Full suite command** | `~/.job-scout-venv/bin/python3 -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds (fixture-driven, no network) |

---

## Sampling Rate

- **After every task commit:** Run `~/.job-scout-venv/bin/python3 -m pytest tests/test_providers_phase4.py -x -q`
- **After every plan wave:** Run full suite (`tests/`)
- **Before `/gsd-verify-work`:** Full suite must be green (22 from Phase 3 + new Phase 4 tests)
- **Max feedback latency:** ~6 seconds

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists |
|--------|----------|-----------|-------------------|-------------|
| PRV-01 | lever.to_listing() maps all fields from fixture | unit | `pytest tests/test_providers_phase4.py::test_lever_to_listing -x` | ❌ W0 |
| PRV-01 | lever createdAt epoch_ms → ISO date | unit | `pytest tests/test_providers_phase4.py::test_lever_posted_date_epoch -x` | ❌ W0 |
| PRV-02 | ashby.fetch() skips isListed=False jobs | unit | `pytest tests/test_providers_phase4.py::test_ashby_filters_unlisted -x` | ❌ W0 |
| PRV-02 | ashby.to_listing() maps all fields | unit | `pytest tests/test_providers_phase4.py::test_ashby_to_listing -x` | ❌ W0 |
| PRV-03 | smartrecruiters.to_listing() maps name→title, company.name→company | unit | `pytest tests/test_providers_phase4.py::test_sr_to_listing -x` | ❌ W0 |
| PRV-03 | smartrecruiters fixture includes detail-call result | unit | `pytest tests/test_providers_phase4.py::test_sr_description_from_detail -x` | ❌ W0 |
| PRV-04 | workday.to_listing() maps title/locationsText/postedOn→ISO | unit | `pytest tests/test_providers_phase4.py::test_workday_to_listing -x` | ❌ W0 |
| PRV-04 | workday.to_listing() handles "Posted Today" / "Posted N Days Ago" | unit | `pytest tests/test_providers_phase4.py::test_workday_posted_on_parsing -x` | ❌ W0 |
| PRV-05 | workday.fetch() returns FetchResult(auth_required=True) on 401+csrf body | unit | `pytest tests/test_providers_phase4.py::test_workday_csrf_detection -x` | ❌ W0 |
| PRV-06 | filter_stale() drops listings older than max_age_days | unit | `pytest tests/test_providers_phase4.py::test_filter_stale -x` | ❌ W0 |
| PRV-07 | collapse_regional_dupes() merges same-title different-location | unit | `pytest tests/test_providers_phase4.py::test_collapse_regional_dupes -x` | ❌ W0 |
| PRV-08 | filter_evergreen() drops "Talent Network" / "General Application" | unit | `pytest tests/test_providers_phase4.py::test_filter_evergreen -x` | ❌ W0 |
| PRV-09 | PROVIDERS dict has 5 entries after Phase 4 (or 6 with JSON-LD) | unit | `pytest tests/test_providers_phase4.py::test_providers_registry_has_five -x` | ❌ W0 |
| STR-01 | jsonld._extract_jsonld_jobs() parses schema.org/JobPosting | unit | `pytest tests/test_providers_phase4.py::test_jsonld_extraction -x` | ❌ W0 |
| STR-03 | filter_stale() uses per-provider override from provider_overrides dict | unit | `pytest tests/test_providers_phase4.py::test_filter_stale_per_provider_override -x` | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_providers_phase4.py` — all PRV-01..09, STR-01, STR-03 unit tests (1 file with ~15 test functions)
- [ ] `tests/fixtures/ats/lever/spotify.json` + `tests/fixtures/ats/lever/__init__.py` — bare array, 3 jobs, sanitized
- [ ] `tests/fixtures/ats/ashby/<company>.json` + `__init__.py` — includes ≥1 isListed=False job for filter test
- [ ] `tests/fixtures/ats/smartrecruiters/visa.json` + `__init__.py` — combined list+detail fixture
- [ ] `tests/fixtures/ats/workday/workday_wd5.json` (live-verified) + wd1/wd3 synthetic fixtures + `__init__.py` + `SOURCE.md` — provenance documented
- [ ] `tests/fixtures/jsonld/<example>.html` — schema.org/JobPosting fixture page

---

## Locked Decisions (from research review 2026-04-29)

D-1: **`auth_required: bool = False` added to FetchResult in base.py**. All existing providers inherit default (no breaking change). Workday sets True on CSRF 401/403. Dispatcher writes `workday_auth_required` reason to runs.jsonl.

D-2: **Filtering layer lives in preview.py after fetch_all()**. New helper `apply_filters(outcomes, config) -> List[FetchOutcome]` in normalize.py applies filter_stale + collapse_regional_dupes + filter_evergreen. Single hook point.

D-3: **JSON-LD added to PROVIDERS registry with empty BOARD_URL_PATTERNS**. detect.py skips providers whose BOARD_URL_PATTERNS is empty (avoids spurious probes). PROVIDERS-is-truth invariant maintained.

D-4: **Workday wd1/wd3 fixtures are synthetic** (hand-crafted realistic job shapes). wd5 is live-verified. Parsing logic identical across data centers; only URL components vary.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `/scout-run` against companies known to use each ATS | PRV-01..04 | Requires real network + real master_targets entries | After execute-phase: add a Lever-confirmed, Ashby-confirmed, SmartRecruiters-confirmed, Workday-confirmed company to master_targets, run `/scout-run`, inspect runs.jsonl for per-provider hit counts |
| Live JSON-LD fallback against a known schema.org-emitting careers page | STR-01 | Requires real careers page with JSON-LD | Manual probe of one company without ats_provider but emitting JSON-LD |
| Live Workday CSRF detection (find a CSRF-protected tenant) | PRV-05 | Requires a real CSRF-protected Workday tenant | Find one in master_targets, run /scout-run, confirm runs.jsonl has `workday_auth_required` reason |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers `tests/test_providers_phase4.py` + 5 fixture sets
- [ ] No watch-mode flags
- [ ] Feedback latency < 6s
- [ ] `nyquist_compliant: true` set in frontmatter (after planner approves Wave 0 task structure)

**Approval:** pending

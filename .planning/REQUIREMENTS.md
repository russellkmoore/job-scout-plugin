# Requirements: job-scout-plugin v0.4

**Defined:** 2026-04-27
**Core Value:** A daily run reliably surfaces 5–15 actionable, well-matched job listings per top-connection company — without depending on fragile marketing-page scraping.

## v1 Requirements

Requirements for the v0.4 release. Each maps to exactly one roadmap phase. IDs use category prefixes: `SCH` (schema), `DSP` (dispatcher), `DET` (detection), `PRV` (provider modules), `DDP` (dedup/scoring), `OBS` (observability), `OUT` (output/cleanup), `STR` (stretch P1).

### Schema (SCH)

- [ ] **SCH-01**: `validate_data.py` ensures `<data_dir>/runs.jsonl` exists at the start of every `/scout-run` (creates empty file if missing)
- [ ] **SCH-02**: `validate_data.py` ensures `<data_dir>/daily/<DATE>/ats_raw/` directory exists before Pass 1 writes any provider response payloads
- [ ] **SCH-03**: `MASTER_TARGETS_VERSION` bumps to 4; `MASTER_TARGETS_COLUMNS` adds `ats_slug_confidence` (float 0.0–1.0 or empty) and `last_ats_hit_date` (ISO date or empty); both columns optional and default to empty
- [ ] **SCH-04**: `JobScout_Tracker.xlsx` adds `source` column (values: `ats:greenhouse|ats:lever|ats:ashby|ats:smartrecruiters|ats:workday|ats:jsonld|linkedin`) and `ats_provider` column (values: same `ats:*` set or empty); written through `scripts/tracker_utils.py:HEADERS` (single source of truth)
- [ ] **SCH-05**: `tests/test_migration.py` round-trips a checked-in `tests/fixtures/master_targets_v3.csv` through the v3→v4 migration and confirms (a) all v3 rows preserved, (b) new columns present and empty, (c) v0.3 code can still read the v4 CSV without crash
- [ ] **SCH-06**: `skills/job-scout/references/file-contract.md` updated with entries for `runs.jsonl` and `daily/<DATE>/ats_raw/`; every new path lives in exactly one place

### Dispatcher + Greenhouse vertical slice (DSP)

- [ ] **DSP-01**: `scripts/ats/providers/base.py` defines a `Provider` Protocol with `NAME`, `BOARD_URL_PATTERNS`, `detect()`, `board_url_from_url()`, `fetch()`, `to_listing()` — all 5 providers in v0.4 conform without inheritance
- [ ] **DSP-02**: `scripts/ats/normalize.py` defines a canonical `Listing` dataclass with required fields (company, title, location, url, posted_date, source) and optional fields (description, department, employment_type, raw); per-provider mappers raise loudly on missing required fields (no silent default-to-empty)
- [ ] **DSP-03**: `scripts/ats/dispatcher.py` uses one shared `httpx.Client` (instantiated once per run, closed in `finally`) with `httpx.Timeout(connect=5, read=15)` on every request
- [ ] **DSP-04**: `scripts/ats/dispatcher.py` uses `concurrent.futures.ThreadPoolExecutor(max_workers=20)` with one `threading.Semaphore` per provider (caps configurable from `config.json`; defaults: greenhouse=10, ashby=8, lever=5, smartrecruiters=5, workday=3)
- [ ] **DSP-05**: Dispatcher returns three distinct per-(company, provider) states: `OK_WITH_RESULTS` (n≥1 listings), `OK_ZERO` (200 response, 0 jobs), `ERROR` (any non-200, network failure, or parse failure) — all three logged separately
- [ ] **DSP-06**: All worker exceptions are surfaced (not swallowed) — wrapper around each `executor.submit` call captures + logs + re-raises so dispatcher caller sees real errors
- [ ] **DSP-07**: `scripts/ats/runs_log.py` appends one JSON line per `/scout-run` to `<data_dir>/runs.jsonl`; line includes `timestamp`, `wall_clock_seconds`, per-provider counts (`ok_with_results`, `ok_zero`, `error`), per-(company, provider) listing counts, and field-completion telemetry (% of returned listings missing each required `Listing` field)
- [ ] **DSP-08**: `config.json` supports `ats.concurrency_disabled: true` kill-switch flag; when true, dispatcher falls back to sequential per-provider fetches (no executor, no semaphores) — same code path otherwise
- [ ] **DSP-09**: `scripts/ats/providers/greenhouse.py` ships first as the vertical-slice validation: detects via `boards-api.greenhouse.io/v1/boards/{slug}/jobs`, fetches all jobs, normalizes to `Listing`; checked-in fixture in `tests/fixtures/ats/greenhouse/` for one real company response (sanitized)
- [ ] **DSP-10**: `/scout-run` Step 2 (Pass 1) is wired to call the Greenhouse-only dispatcher additively alongside the existing 3-pass flow — old flow still produces output; new ATS pass writes to `daily/<DATE>/ats_raw/` and is visible in the report behind a `[ATS-PREVIEW]` tag

### Detection (DET)

- [ ] **DET-01**: `scripts/ats/detect.py` exposes two CLI subcommands — `detect-one <company> [--name <display_name>]` and `detect-batch <csv_path> [--limit N] [--force]`
- [ ] **DET-02**: Detection uses URL-pattern probes against each provider in registry order (Greenhouse → Lever → Ashby → SmartRecruiters → Workday) and returns the first match passing the two-factor gate
- [ ] **DET-03**: Two-factor gate: a slug is confirmed only if (a) the API returns a 200 with ≥1 job *and* (b) the company name in the API response fuzzy-matches the input company name with `rapidfuzz.token_set_ratio` ≥ 85
- [ ] **DET-04**: Negative results cached as `ats_provider=none` in `master_targets.csv`; `detect-batch` skips rows where `ats_provider` is non-empty unless `--force` is passed (idempotent re-run)
- [ ] **DET-05**: Borderline matches (two-factor gate score 70–84) appended to `<data_dir>/ats_detection_review.csv` with company, provider, confidence score, and proposed `ats_board_url` for manual review
- [ ] **DET-06**: New skill `skills/scout-detect/SKILL.md` orchestrates batch detection on top-30 connection-weighted companies (or all companies if user passes `--all`); writes `ats_provider`, `ats_board_url`, and `ats_slug_confidence` back to `master_targets.csv`
- [ ] **DET-07**: `/scout-run` Step 2b (lazy inline detection): for any company in the daily slate where `ats_provider` is empty, call `detect-one` inline; cache result back to `master_targets.csv` after the run

### Remaining provider modules + filtering (PRV)

- [ ] **PRV-01**: `scripts/ats/providers/lever.py` ships with detection (`api.lever.co/v0/postings/{slug}?mode=json`), fetch (handles bare-array response), normalization (handles missing `lists` field), checked-in fixture
- [ ] **PRV-02**: `scripts/ats/providers/ashby.py` ships with detection (REST endpoint, not GraphQL), fetch with case-sensitive slug handling, normalization with `isListed=true` filter to drop unlisted jobs, checked-in fixture
- [ ] **PRV-03**: `scripts/ats/providers/smartrecruiters.py` ships with detection (`api.smartrecruiters.com/v1/companies/{id}/postings`), list-then-detail fetch (descriptions only available via per-job follow-up GET), normalization, checked-in fixture
- [ ] **PRV-04**: `scripts/ats/providers/workday.py` ships with detection (parses `(tenant, data_center, site)` from full board URL stored in `ats_board_url` — no `wd1/wd5` guessing), POST fetch with `{"appliedFacets":{},"limit":20,"offset":0,"searchText":""}`, follow-up GET per job for full description, normalization with freeform-English `postedOn` parsing, checked-in fixture covering ≥3 distinct tenants
- [ ] **PRV-05**: Workday CSRF/auth-required tenants detected explicitly: 401/403 with `csrf|session|cookie` body markers logs `workday-auth-required` to `runs.jsonl` and routes the company to Pass 2 only — never silently returns zero
- [ ] **PRV-06**: `scripts/ats/normalize.py` filters listings older than `ats.posted_date_max_age_days` (default 60d, configurable in `config.json`)
- [ ] **PRV-07**: `scripts/ats/normalize.py` collapses intra-source regional duplicates: same `(provider, company_slug, normalized_title)` with multiple location strings are merged into one `Listing` with a `locations[]` array
- [ ] **PRV-08**: `scripts/ats/normalize.py` blocklist drops evergreen postings whose normalized title matches `^(general|talent network|future opportunities|join our team|connect with us)`; pattern set lives in `references/ats-providers.md`
- [ ] **PRV-09**: All 5 provider modules registered in `scripts/ats/__init__.py:PROVIDERS` registry; dispatcher and detector iterate `PROVIDERS.items()` and never name a specific provider

### Dedup, scoring, enrichment (DDP)

- [ ] **DDP-01**: `scripts/ats/dedupe.py` matches Pass 2 (LinkedIn) listings against Pass 1 (ATS) listings using `rapidfuzz.token_set_ratio` on normalized titles, scoped per company slug
- [ ] **DDP-02**: Tiered confidence band — auto-merge when score ≥ 95, log to review band when 70–94, keep both when < 70; thresholds configurable in `config.json` under `dedup.thresholds`
- [ ] **DDP-03**: Two-key match — auto-merge requires both (a) loose key (company-slug + first-3-tokens of normalized title) AND (b) tight key (company-slug + full normalized title) to agree at the auto-merge threshold; either key alone is review-band
- [ ] **DDP-04**: Every dedup decision (auto-merge, review-band, keep-both) appended to the `runs.jsonl` line under `dedup_decisions` with both source listings and the score
- [ ] **DDP-05**: `skills/job-scout/references/scoring-rubric.md` updated with +1 tier bump for `source=ats:*` listings whose `posted_date` is ≤ 30 days old (older ATS hits get no bump)
- [ ] **DDP-06**: `skills/scout-run/SKILL.md` adds Step 5 (enrich-then-tier): for every A-tier candidate where `source=ats:*`, navigate via Chrome MCP to the LinkedIn company page and capture shared-connection count + top 3 named connections; merge into the report row
- [ ] **DDP-07**: Chrome MCP usage limited to LinkedIn navigation only — no career-page scraping. `scout-run/SKILL.md` removes every `mcp__Claude_in_Chrome__navigate` call against marketing/careers domains
- [ ] **DDP-08**: Report's *Honest notes* section auto-flags "ATS regression suspect" warnings: any company where `(provider, company)` returned `OK_WITH_RESULTS` for ≥3 of the last 5 runs but `OK_ZERO`/`ERROR` for the current run

### Output, cleanup, milestone close (OUT)

- [ ] **OUT-01**: Every listing in `report.md` is tagged with a `source=` annotation (`ats:greenhouse`, `ats:lever`, `ats:ashby`, `ats:smartrecruiters`, `ats:workday`, `ats:jsonld`, or `linkedin`); also tagged on the row in `JobScout_Tracker.xlsx`
- [ ] **OUT-02**: `report.md` opens with a run-summary block: total listings, A/B/C counts, Pass-1 share %, total wall-clock seconds, per-provider breakdown (count + ok_zero count + error count), top 3 ATS regression warnings (if any)
- [ ] **OUT-03**: `/scout-run` prints the same summary block to stdout at the end of the run (visible in scheduled-run logs without opening the report)
- [ ] **OUT-04**: All marketing-page Chrome scraping code deleted from `skills/scout-run/SKILL.md` and `skills/job-scout/references/`; `grep -ri "career_page\|careers-html\|marketing-page" skills/ scripts/` returns zero matches
- [ ] **OUT-05**: `skills/job-scout/references/chrome-setup.md` trimmed to LinkedIn-only setup; obsolete career-page sections removed
- [ ] **OUT-06**: `.claude-plugin/plugin.json` version bumped to `0.4.0`; per-skill versions updated; `README.md` v0.4 section explains the ATS-first flow + new `/scout-detect` skill
- [ ] **OUT-07**: 5-run rolling average of Pass-1 share verified ≥ 60% before declaring v0.4 complete; total `/scout-run` wall-clock measured ≤ 5 min average across the same 5 runs

### Stretch (P1) features (STR)

- [ ] **STR-01**: JSON-LD `JobPosting` fallback — for companies where ATS detection returns `none` and the company has a `careers_url` in `master_targets.csv`, fetch the page once via `httpx`, parse `<script type="application/ld+json">JobPosting</script>` blocks, normalize to `Listing` with `source=ats:jsonld`. No JS rendering, no Chrome.
- [ ] **STR-02**: `master_targets.csv` `ats_slug_confidence` column populated by detection (1.0 = explicit confirmation, 0.7–0.94 = review-band match, manual lock = `manual`); `/scout-detect` honors `manual` and never overwrites it
- [ ] **STR-03**: Per-provider `posted_date_max_age_days` override via `config.json` (e.g. Workday 90d because tenants are slower to repost; Greenhouse 30d because rapid churn) — falls back to global `ats.posted_date_max_age_days`
- [ ] **STR-04**: `/scout-detect` is idempotent — re-running on the same CSV is a no-op unless `--force` is passed; respects `ats_provider=manual` lock from STR-02

## v2 Requirements

Deferred to v0.4.x patches or v0.5+. Tracked but not in current roadmap.

### Additional providers

- **PRV2-01**: Jobvite provider module
- **PRV2-02**: Taleo (Oracle) provider module
- **PRV2-03**: iCIMS provider module
- **PRV2-04**: Workable provider module

### Reader skills

- **READ-01**: `/scout-stats` skill that reads `runs.jsonl` and produces trend reports (Pass-1 share over time, per-provider reliability, regression-suspect history)

### Advanced dedup

- **DDP2-01**: Canonical-URL dedup via redirect resolution (LinkedIn `linkedin.com/jobs/view/<id>` → resolve to apply URL → match against ATS apply URL)
- **DDP2-02**: Cross-run cross-source dedup (de-dupe a Pass 1 hit today against a Pass 2 hit yesterday for the same role)

### Caching + performance

- **PERF-01**: ETag / `If-Modified-Since` caching per (provider, company) — only re-fetch if response changed
- **PERF-02**: Adaptive per-provider rate limiting based on observed 429s
- **PERF-03**: Tracker xlsx incremental writes (today: full rebuild on every append per `CONCERNS.md`)

### Workday auth

- **WDA-01**: Workday tenant CSRF/session-token harvesting (today: log + defer to Pass 2)

### Quiet-mode + partial-run

- **CLI-01**: `/scout-run --quiet` mode for scheduled runs (no interactive prompts, no progress bars)
- **CLI-02**: `/scout-run --only-pass=1` and `--only-companies=<list>` for partial re-runs

### Per-provider parse-error telemetry

- **OBS2-01**: Field-completion telemetry surfaced in summary block (today: in `runs.jsonl` only)

## Out of Scope

Explicitly excluded from v0.4. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Marketing-page Chrome scraping fallback | Explicitly deleted; the milestone definition requires removal |
| Generic ATS abstraction layer | Anti-feature — recreates duplication; per-provider modules are 100–200 lines each |
| Retry-on-403/429 storms within a run | Correct backoff is "tomorrow's run"; in-run retries blow the 5-min budget |
| Async refactor of `scripts/` | At ~30 companies × 5 providers, threads + semaphores beat asyncio; explicit non-goal |
| OAuth flows for any provider | Public read endpoints only |
| Per-job LLM enrichment at fetch time | Scoring stays in `scout-run/SKILL.md` (one LLM pass), not per-job |
| Sourcing-layer cross-run dedup | `tracker_utils.py` already does cross-run dedup by LinkedIn job ID; not the dispatcher's job |
| Third-party "universal ATS detector" libraries | Auditability + control over the two-factor gate logic |
| `requirements.txt` or formal dependency manifest | Project convention: `ImportError` handlers print `pip install --break-system-packages` hints |
| Test suite (general) | Carve-out only for `tests/test_migration.py` + per-provider fixture rounds; not a broader test suite |
| Mobile / web UI for the report | Output stays as markdown in `<data_dir>/daily/<DATE>/` |
| Per-provider concurrency cap auto-tuning | Caps live in `config.json`; specialize manually if production reveals limits |

## Traceability

Will be populated during roadmap creation. Each requirement maps to exactly one phase.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCH-01 | TBD | Pending |
| SCH-02 | TBD | Pending |
| SCH-03 | TBD | Pending |
| SCH-04 | TBD | Pending |
| SCH-05 | TBD | Pending |
| SCH-06 | TBD | Pending |
| DSP-01 | TBD | Pending |
| DSP-02 | TBD | Pending |
| DSP-03 | TBD | Pending |
| DSP-04 | TBD | Pending |
| DSP-05 | TBD | Pending |
| DSP-06 | TBD | Pending |
| DSP-07 | TBD | Pending |
| DSP-08 | TBD | Pending |
| DSP-09 | TBD | Pending |
| DSP-10 | TBD | Pending |
| DET-01 | TBD | Pending |
| DET-02 | TBD | Pending |
| DET-03 | TBD | Pending |
| DET-04 | TBD | Pending |
| DET-05 | TBD | Pending |
| DET-06 | TBD | Pending |
| DET-07 | TBD | Pending |
| PRV-01 | TBD | Pending |
| PRV-02 | TBD | Pending |
| PRV-03 | TBD | Pending |
| PRV-04 | TBD | Pending |
| PRV-05 | TBD | Pending |
| PRV-06 | TBD | Pending |
| PRV-07 | TBD | Pending |
| PRV-08 | TBD | Pending |
| PRV-09 | TBD | Pending |
| DDP-01 | TBD | Pending |
| DDP-02 | TBD | Pending |
| DDP-03 | TBD | Pending |
| DDP-04 | TBD | Pending |
| DDP-05 | TBD | Pending |
| DDP-06 | TBD | Pending |
| DDP-07 | TBD | Pending |
| DDP-08 | TBD | Pending |
| OUT-01 | TBD | Pending |
| OUT-02 | TBD | Pending |
| OUT-03 | TBD | Pending |
| OUT-04 | TBD | Pending |
| OUT-05 | TBD | Pending |
| OUT-06 | TBD | Pending |
| OUT-07 | TBD | Pending |
| STR-01 | TBD | Pending |
| STR-02 | TBD | Pending |
| STR-03 | TBD | Pending |
| STR-04 | TBD | Pending |

**Coverage:**
- v1 requirements: 51 total
- Mapped to phases: 0 (filled by roadmapper)
- Unmapped: 51 ⚠️ (expected pre-roadmap)

---
*Requirements defined: 2026-04-27*
*Last updated: 2026-04-27 after initial definition*

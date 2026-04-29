# Requirements: job-scout-plugin v0.4

**Defined:** 2026-04-27
**Core Value:** A daily run reliably surfaces 5–15 actionable, well-matched job listings per top-connection company — without depending on fragile marketing-page scraping.

## v1 Requirements

Requirements for the v0.4 release. Each maps to exactly one roadmap phase. IDs use category prefixes: `SCH` (schema), `DSP` (dispatcher), `DET` (detection), `PRV` (provider modules), `DDP` (dedup/scoring), `OUT` (output/cleanup), `STR` (stretch P1), `CON` (concerns cleanup — surgical fixes from `.planning/codebase/CONCERNS.md`, distributed into the v0.4 phase that touches the same code).

### Schema (SCH)

- [ ] **SCH-01**: `validate_data.py` ensures `<data_dir>/runs.jsonl` exists at the start of every `/scout-run` (creates empty file if missing)
- [ ] **SCH-02**: `validate_data.py` ensures `<data_dir>/daily/<DATE>/ats_raw/` directory exists before Pass 1 writes any provider response payloads
- [ ] **SCH-03**: `MASTER_TARGETS_VERSION` bumps to 4; `MASTER_TARGETS_COLUMNS` adds `ats_slug_confidence` (float 0.0–1.0 or empty) and `last_ats_hit_date` (ISO date or empty); both columns optional and default to empty
- [ ] **SCH-04**: `JobScout_Tracker.xlsx` adds `source` column (values: `ats:greenhouse|ats:lever|ats:ashby|ats:smartrecruiters|ats:workday|ats:jsonld|linkedin`) and `ats_provider` column (values: same `ats:*` set or empty); written through `scripts/tracker_utils.py:HEADERS` (single source of truth)
- [ ] **SCH-05**: `tests/test_migration.py` round-trips a checked-in `tests/fixtures/master_targets_v3.csv` through the v3→v4 migration and confirms (a) all v3 rows preserved, (b) new columns present and empty, (c) v0.3 code can still read the v4 CSV without crash
- [ ] **SCH-06**: `skills/job-scout/references/file-contract.md` updated with entries for `runs.jsonl` and `daily/<DATE>/ats_raw/`; every new path lives in exactly one place

### Dispatcher + Greenhouse vertical slice (DSP)

- [x] **DSP-01**: `scripts/ats/providers/base.py` defines a `Provider` Protocol with `NAME`, `BOARD_URL_PATTERNS`, `detect()`, `board_url_from_url()`, `fetch()`, `to_listing()` — all 5 providers in v0.4 conform without inheritance
- [x] **DSP-02**: `scripts/ats/normalize.py` defines a canonical `Listing` dataclass with required fields (company, title, location, url, posted_date, source) and optional fields (description, department, employment_type, raw); per-provider mappers raise loudly on missing required fields (no silent default-to-empty)
- [x] **DSP-03**: `scripts/ats/dispatcher.py` uses one shared `httpx.Client` (instantiated once per run, closed in `finally`) with `httpx.Timeout(connect=5, read=15)` on every request
- [x] **DSP-04**: `scripts/ats/dispatcher.py` uses `concurrent.futures.ThreadPoolExecutor(max_workers=20)` with one `threading.Semaphore` per provider (caps configurable from `config.json`; defaults: greenhouse=10, ashby=8, lever=5, smartrecruiters=5, workday=3)
- [x] **DSP-05**: Dispatcher returns three distinct per-(company, provider) states: `OK_WITH_RESULTS` (n≥1 listings), `OK_ZERO` (200 response, 0 jobs), `ERROR` (any non-200, network failure, or parse failure) — all three logged separately
- [x] **DSP-06**: All worker exceptions are surfaced (not swallowed) — wrapper around each `executor.submit` call captures + logs to stderr + buckets as `FetchOutcome.ERROR` with (company, provider, error_type, error_message) context. Truly unexpected exceptions (`KeyboardInterrupt`, `MemoryError`, `SystemExit`) re-raise to halt the run; recoverable per-fetch exceptions (`HTTPStatusError`, `RequestError`, `ParseError`) bucket as ERROR. The dispatcher caller sees real errors via runs.jsonl + stderr.
- [x] **DSP-07**: `scripts/ats/runs_log.py` appends one JSON line per `/scout-run` to `<data_dir>/runs.jsonl`; line includes `timestamp`, `wall_clock_seconds`, per-provider counts (`ok_with_results`, `ok_zero`, `error`), per-(company, provider) listing counts, and field-completion telemetry (% of returned listings missing each required `Listing` field)
- [x] **DSP-08**: `config.json` supports `ats.concurrency_disabled: true` kill-switch flag; when true, dispatcher falls back to sequential per-provider fetches (no executor, no semaphores) — same code path otherwise
- [x] **DSP-09**: `scripts/ats/providers/greenhouse.py` ships first as the vertical-slice validation: detects via `boards-api.greenhouse.io/v1/boards/{slug}/jobs`, fetches all jobs, normalizes to `Listing`; checked-in fixture in `tests/fixtures/ats/greenhouse/` for one real company response (sanitized)
- [x] **DSP-10**: `/scout-run` Step 2 (Pass 1) is wired to call the Greenhouse-only dispatcher additively alongside the existing 3-pass flow — old flow still produces output; new ATS pass writes to `daily/<DATE>/ats_raw/` and is visible in the report behind a `[ATS-PREVIEW]` tag

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

### Concerns cleanup (CON)

Surgical fixes for items in `.planning/codebase/CONCERNS.md`. Each is folded into the v0.4 phase that already touches the same file or surface area; there is no dedicated cleanup phase. Bug-class items are non-deferrable; reliability/security items reflect the user-chosen "all non-deferred concerns" scope. Performance/scaling/dependency-shape concerns (sqlite migration, pandas removal, sequential-board parallelism) are deferred to v0.5+.

**Folded into Phase 1 (validate_data, schema, scripts/, state.py, templates):**

- [ ] **CON-01**: Fix `scripts/consolidate_targets.py:270` `KeyError` on `master['already_applied']` — the column was removed in v=3 schema trim. Drop the dead summary block (lines ~270–272) so `consolidate()` no longer crashes on any non-legacy file.
- [ ] **CON-02**: Add `STATUS_VALUES` enum to `scripts/schema.py` (e.g. `{"Active", "Applied", "Interviewing", "Offer", "Rejected", "Dead", "Closed"}`) and validate on tracker append in `tracker_utils.py` — eliminates the `Dead | dead | DEAD | Closed` magic-string drift that today silently re-includes dead companies.
- [ ] **CON-03**: Fix `scripts/mine_connections.py:29-45` header detection — log a `WARNING:` to stderr when falling back to the default `(3, 'latin-1')`, AND validate that the resolved column set includes a recognizable name/company column before reading; abort with a clear message if not (today: silently throws away 3 connections per run on Spanish/localized exports).
- [ ] **CON-04**: Switch all 4 scripts' `ImportError` install hints from `pip install <pkg> --break-system-packages` to `pipx install <pkg>` or `python3 -m venv` recommendation (`scripts/validate_data.py:29`, `scripts/tracker_utils.py:31`, `scripts/consolidate_targets.py:26`, `scripts/mine_connections.py:25`); also update the new `scripts/ats/*` import-error handlers (Phase 2) to match.
- [ ] **CON-05**: Resolve the `LEGACY_DATA_DIRS` contradiction with `references/file-contract.md` ("No alternate paths. No fallbacks. No 'or'.") — recommend deleting the legacy fallback chain in `scripts/state.py:32-36` and emitting a one-time migration prompt in `/scout-setup` if any legacy dir exists. Update `file-contract.md` to confirm "no fallbacks" is now enforced.
- [ ] **CON-06**: Pick a single canonical `companies_per_day` default and align all three drift sites: `templates/config.json:32` (currently 5), `skills/scout-run/SKILL.md:73` (currently quotes 8), `references/search-config.md:43` (reconciles "5 vs 8"). Recommend defer-to-template approach: remove the inline default from both skill docs and replace with "see `templates/config.json`."
- [ ] **CON-07**: Harden file permissions on the local state pointer — after creating `~/.job-scout/` directory and `state.json`, call `os.chmod(STATE_DIR, 0o700)` and `os.chmod(STATE_PATH, 0o600)` in `scripts/state.py:52` so other local users on shared macOS systems cannot read the data_dir path.

**Folded into Phase 3 (file-contract.md, skill-doc updates as part of /scout-detect introduction):**

- [ ] **CON-08**: Fix the 3 dead `commands/scout-run.md` references (the `commands/` directory was removed in commit `1d31872`): `skills/job-scout/SKILL.md:46`, `skills/job-scout/SKILL.md:105`, `skills/job-scout/references/search-config.md:28` — rewrite each to point at `skills/scout-run/SKILL.md`.

**Folded into Phase 5 (touches scoring-rubric, scout-run/SKILL.md, tracker_utils — same surfaces being modified for dedup/tier/enrich):**

- [ ] **CON-09**: Rewrite the dead `pipeline_tier <= 2` Pass 1 priority in `references/search-config.md:52` to use `linkedin_connection_count` thresholds — the `pipeline_tier` column was removed in v=3 schema trim and currently produces undefined behavior at scoring time.
- [ ] **CON-10**: Rewrite the dead `pipeline_tier 1-3` +5 bonus row in `references/scoring-rubric.md:111` to be `linkedin_connection_count`-driven (or `data_source`-driven if connection-count alone is too noisy) — same root cause as CON-09. Coordinate with DDP-05 since both edit the rubric.
- [ ] **CON-11**: Add LinkedIn rate-limit/backoff rule to the new `scout-run/SKILL.md` Step 5 (enrich): "between every 5 LinkedIn navigations, pause 10–15 seconds" — prevents captcha walls during enrichment runs that hit many A-tier ATS candidates in sequence.
- [ ] **CON-12**: Make LinkedIn JD lazy-load resilient in `references/chrome-setup.md:36-46` and `scout-run/SKILL.md` enrichment step — try multiple selectors for the "...more" button (e.g. `...more`, `Show more`, `aria-label="Expand description"`), retry once with a longer wait if `get_page_text` returns < 500 chars after the dance, log JD-extraction failures to `runs.jsonl` so trend regression is visible.
- [ ] **CON-13**: Split `scripts/tracker_utils.py:65-70` `extract_job_id` into two functions: `extract_linkedin_job_id(url)` (anchored to `linkedin\.com/jobs/(?:view|search)/.*?(\d{10,})`, returns `None` for non-LinkedIn URLs) and `extract_dedup_key(url)` (URL-as-string fallback for non-LinkedIn rows); migrate all 4 callers (`load_tracker`, `append_rows`, `is_stale_by_id`, `rebuild`) explicitly. Fixes false stale-flagging on career-page URLs and prevents un-deduping cascade on regex tightening.
- [ ] **CON-14**: Rename `scripts/tracker_utils.py:194-199` local variable `skipped_stale` to `flagged_stale_count` to match the returned dict key at line 229; remove the misleading `# Still add it, but flagged` inline comment so future maintainers don't add a `continue` and silently break the contract.
- [ ] **CON-15**: Add Pass 2 board-broken warning rule to `scout-run/SKILL.md` Step 3 — if a Pass 2 board (Wellfound, Built In Seattle, HN Algolia, YC Work at a Startup) returned 0 results for ≥3 of the last 5 runs (per `runs.jsonl`), surface "board appears broken" in the report's *Honest notes* section. Same mechanism as DDP-08 (ATS regression suspect).
- [ ] **CON-20**: Modify `scripts/tracker_utils.py:_write_tracker` (lines 264–315) to preserve user-added xlsx columns on append — today the read-back path drops any column not in `TRACKER_COLUMNS` at line 296 (`if col > len(HEADERS): break`), then `_write_tracker` rebuilds the workbook without them. Capture extra columns into a passthrough buffer when reading existing rows; re-emit them at the end of each row on rewrite.

**Folded into Phase 6 (touches plugin.json, README, skill versions, post-run validation as part of milestone close):**

- [ ] **CON-16**: Normalize plugin/skill version sprawl — bump `.claude-plugin/plugin.json` to `0.4.0` AND set every skill's `version:` frontmatter field to `0.4.0` in lockstep (`skills/scout-run/SKILL.md`, `skills/scout-setup/SKILL.md`, `skills/scout-detect/SKILL.md`, `skills/job-scout/SKILL.md`). Coordinates with OUT-06. Document in README that all four ship together going forward; consider a `scripts/release.py` helper for future bumps.
- [ ] **CON-17**: Delete the inline column list in `skills/job-scout/SKILL.md:38` (currently lists `company_name, pipeline_tier, industry, location, …` which contradicts v=3 schema) — replace with "see `scripts/schema.py:MASTER_TARGETS_COLUMNS` for the canonical column set." Restores the "single source of truth" guarantee that the same paragraph claims.
- [ ] **CON-18**: Add a PII handling note to `skills/scout-setup/SKILL.md` Step 1 — explicitly state that `<data_dir>/connections_summary.csv` and `master_targets.csv:connection_names` contain LinkedIn connection PII for hundreds of third parties, and warn users not to place `<data_dir>` in iCloud, Dropbox, OneDrive, or any synced folder.
- [ ] **CON-19**: Add a `.gitignore` template entry pattern + a setup-skill warning that `<data_dir>/config.json` contains a plaintext absolute path to the user's resume (`candidate.resume_path`) — if shared in a bug report or support thread, it leaks the user's filesystem layout. Recommend always redacting `resume_path` before sharing.
- [ ] **CON-21**: Add a post-write check at the end of `scout-run/SKILL.md` Step 6 — confirm `report.md` exists, that the report's A-tier count matches the tracker's A-tier count for `<TODAY>`, and that `runs.jsonl` was appended this run; surface a single-line `WARNING: post-run validation failed: <reason>` to stdout if any check fails. Catches the half-written report + fully-updated tracker drift that today is undetectable.

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

Every v1 requirement maps to exactly one phase in `.planning/ROADMAP.md`.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCH-01 | Phase 1 | Complete |
| SCH-02 | Phase 1 | Complete |
| SCH-03 | Phase 1 | Complete |
| SCH-04 | Phase 1 | Complete |
| SCH-05 | Phase 1 | Complete |
| SCH-06 | Phase 1 | Complete |
| DSP-01 | Phase 2 | Complete |
| DSP-02 | Phase 2 | Complete |
| DSP-03 | Phase 2 | Complete |
| DSP-04 | Phase 2 | Complete |
| DSP-05 | Phase 2 | Complete |
| DSP-06 | Phase 2 | Complete |
| DSP-07 | Phase 2 | Complete |
| DSP-08 | Phase 2 | Complete |
| DSP-09 | Phase 2 | Complete |
| DSP-10 | Phase 2 | Complete |
| DET-01 | Phase 3 | Pending |
| DET-02 | Phase 3 | Pending |
| DET-03 | Phase 3 | Pending |
| DET-04 | Phase 3 | Pending |
| DET-05 | Phase 3 | Pending |
| DET-06 | Phase 3 | Pending |
| DET-07 | Phase 3 | Pending |
| PRV-01 | Phase 4 | Pending |
| PRV-02 | Phase 4 | Pending |
| PRV-03 | Phase 4 | Pending |
| PRV-04 | Phase 4 | Pending |
| PRV-05 | Phase 4 | Pending |
| PRV-06 | Phase 4 | Pending |
| PRV-07 | Phase 4 | Pending |
| PRV-08 | Phase 4 | Pending |
| PRV-09 | Phase 4 | Pending |
| DDP-01 | Phase 5 | Pending |
| DDP-02 | Phase 5 | Pending |
| DDP-03 | Phase 5 | Pending |
| DDP-04 | Phase 5 | Pending |
| DDP-05 | Phase 5 | Pending |
| DDP-06 | Phase 5 | Pending |
| DDP-07 | Phase 5 | Pending |
| DDP-08 | Phase 5 | Pending |
| OUT-01 | Phase 6 | Pending |
| OUT-02 | Phase 6 | Pending |
| OUT-03 | Phase 6 | Pending |
| OUT-04 | Phase 6 | Pending |
| OUT-05 | Phase 6 | Pending |
| OUT-06 | Phase 6 | Pending |
| OUT-07 | Phase 6 | Pending |
| STR-01 | Phase 4 | Pending |
| STR-02 | Phase 3 | Pending |
| STR-03 | Phase 4 | Pending |
| STR-04 | Phase 3 | Pending |
| CON-01 | Phase 1 | Complete |
| CON-02 | Phase 1 | Complete |
| CON-03 | Phase 1 | Complete |
| CON-04 | Phase 1 | Complete |
| CON-05 | Phase 1 | Complete |
| CON-06 | Phase 1 | Complete |
| CON-07 | Phase 1 | Complete |
| CON-08 | Phase 3 | Pending |
| CON-09 | Phase 5 | Pending |
| CON-10 | Phase 5 | Pending |
| CON-11 | Phase 5 | Pending |
| CON-12 | Phase 5 | Pending |
| CON-13 | Phase 5 | Pending |
| CON-14 | Phase 5 | Pending |
| CON-15 | Phase 5 | Pending |
| CON-16 | Phase 6 | Pending |
| CON-17 | Phase 6 | Pending |
| CON-18 | Phase 6 | Pending |
| CON-19 | Phase 6 | Pending |
| CON-20 | Phase 5 | Pending |
| CON-21 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 72 total (51 ATS feature + 21 concerns cleanup)
- Mapped to phases: 72 (100%)
- Unmapped: 0

**Per-phase counts:**
- Phase 1 (Schema + paths + migration + foundational cleanup): 13 (SCH-01..06, CON-01..07)
- Phase 2 (Provider Protocol + Greenhouse + dispatcher + observability): 10 (DSP-01..10)
- Phase 3 (Detection + /scout-detect + lazy inline + dead-doc-ref cleanup): 10 (DET-01..07, STR-02, STR-04, CON-08)
- Phase 4 (Remaining providers + JSON-LD + filtering): 11 (PRV-01..09, STR-01, STR-03)
- Phase 5 (Cross-source dedup + tier bump + enrich + scoring/tracker cleanup): 16 (DDP-01..08, CON-09..15, CON-20)
- Phase 6 (Run summary + delete legacy + milestone close + version/PII/post-run cleanup): 12 (OUT-01..07, CON-16..19, CON-21)

---
*Requirements defined: 2026-04-27*
*Last updated: 2026-04-27 — added 21 CON-* concerns-cleanup reqs surgically distributed into Phases 1/3/5/6*

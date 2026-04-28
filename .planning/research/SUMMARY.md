# Project Research Summary

**Project:** job-scout-plugin v0.4 — ATS-first job sourcing
**Domain:** Public ATS Job Board APIs (Greenhouse, Lever, Ashby, SmartRecruiters, Workday) called concurrently from a Python 3.8+ Claude Code plugin
**Researched:** 2026-04-27
**Confidence:** HIGH

## Executive Summary

v0.4 replaces the failing marketing-page Chrome scraping path with structured ATS API queries. Five public, unauthenticated JSON endpoints (Greenhouse, Lever, Ashby, SmartRecruiters, Workday) cover ~80% of the relevant employer set. All five endpoints were verified live on 2026-04-27, response shapes captured, and per-provider concurrency caps derived from observed latency and tenant-isolation patterns. The recommended stack adds exactly two dependencies — `httpx>=0.27,<0.29` (the only sync HTTP client that's officially thread-safe and pools connections across threads) and `rapidfuzz` (for cross-source dedupe) — and uses stdlib `concurrent.futures.ThreadPoolExecutor` + `threading.Semaphore` for concurrency. At ~30 companies/run we are well below the async-vs-threads crossover (~50–200 concurrent requests).

The architecture is a `scripts/ats/` package with a Provider Protocol, a registry-driven dispatcher, and one small module per provider — explicitly chosen to prevent the "6th copy of the same per-source pattern" duplication concern from `CONCERNS.md`. A new `/scout-detect` skill batch-detects ATS providers for the top-30 connection-weighted companies and writes `ats_provider` + `ats_board_url` back to `master_targets.csv`; remaining companies use lazy inline detection during `/scout-run`. Pass 1 (ATS) anchors; Pass 2 (LinkedIn keyword) dedupes against Pass 1 by `(normalized_company, fuzzy_title)`. ATS-sourced jobs receive a +1 tier bump; A-tier ATS candidates get LinkedIn shared-connection enrichment before final tier assignment.

The dominant risk is **silent regression**. "Trust ATS on 0/error" is the right milestone-honesty call but it converts every provider/slug regression into invisible data loss unless we ship per-(company, provider) hit history in `runs.jsonl` and surface "ATS regression suspect" warnings in the report. The other top risks are slug-detection false positives (mitigated by a two-factor gate: 200 + ≥1 job + ≥85% company-name match), dedupe over/under-merging (mitigated by a tiered confidence band: ≥95% auto, 70–95% review, <70% keep both), and concurrent-HTTP shared-state bugs (mitigated by one shared `httpx.Client`, per-provider semaphores, explicit timeouts, serialized tracker writes, and a kill-switch flag).

## Key Findings

### Recommended Stack

The project adds **two** new Python dependencies for v0.4. Everything else stays inside Python 3.8+ stdlib + the existing `pandas`/`openpyxl` set, matching the "no new framework" constraint from `PROJECT.md`.

**Core technologies:**

- **`httpx>=0.27,<0.29`** — single HTTP client across all 5 ATS providers. Chosen because its sync `Client` is documented thread-safe, pools connections across threads, and supports POST-with-JSON (Workday) cleanly. `requests.Session` is *not* thread-safe (maintainer-confirmed), which alone disqualifies it for the concurrent dispatcher.
- **`rapidfuzz`** — Pass 1 vs Pass 2 fuzzy dedupe. MIT-licensed, faster + more accurate than `fuzzywuzzy`. Used for `token_set_ratio` on normalized titles.
- **`concurrent.futures.ThreadPoolExecutor` + `threading.Semaphore`** (stdlib) — one global executor (`max_workers=20`), one semaphore per provider for the concurrency cap. Async (`asyncio`/`aiohttp`) is explicitly rejected — the crossover where async beats threads is ~50–200 concurrent requests; we're at ~30.
- **`dataclasses`, `json`, `re`, `urllib.parse`** (stdlib) — normalization, response parsing, provider detection, Workday tenant URL parsing. No Pydantic, no `tldextract`.
- **Per-provider concurrency caps:** Greenhouse 10, Ashby 8, Lever 5, SmartRecruiters 5, Workday 3 (sum = 31, executor sized at 20 with semaphores enforcing per-provider limits). Starting values; tunable from `config.json`.

See [STACK.md](./STACK.md) for full rationale, live-probe verification per provider, and the implementation sketch.

### Expected Features

The full landscape is in [FEATURES.md](./FEATURES.md): 11 table stakes, 10 differentiators, 10 anti-features. The table-stakes set is what clears the milestone bar (Pass 1 ≥60% of A/B tier, ≤5 minute wall-clock, no Chrome fallback for ATS-undetected companies, verifiable via `runs.jsonl`).

**Must have (table stakes — all 11 required for v0.4):**

- Per-provider ATS client modules (Greenhouse, Lever, Ashby, SmartRecruiters, Workday)
- ATS slug detection (URL pattern + redirect probe + two-factor confirmation)
- Schema columns `ats_provider` + `ats_board_url` (already present in `scripts/schema.py` — see Reconciliation #1 below)
- Result normalization to a canonical `Listing` dataclass
- Cross-source dedup (Pass 2 against Pass 1 via `rapidfuzz`)
- Per-provider concurrency cap with single shared `httpx.Client`
- Per-call timeout + no-retry-within-run policy
- `source=ats:greenhouse|...|linkedin` tag on every listing
- Run-summary block + persisted `runs.jsonl` (per-company, per-provider counts)
- Trust-on-zero/trust-on-error semantics (no Chrome fallback path exists in code)
- Schema-driven per-provider parsers that fail loudly on missing required fields

**Should have (P1 stretch for v0.4):**

- JSON-LD `JobPosting` fallback for ATS-undetected companies (recovers ~10–15% without re-introducing HTML scraping; tagged `source=jsonld`)
- Slug confidence scoring + manual override (`ats_slug_confidence` column, `manual` lock)
- Posted-date filtering at the normalizer (default 14 days; configurable)
- Idempotent `/scout-detect` re-runs (skip already-detected unless `--force`)

**Defer (v0.4.x / v0.5+):**

- Structured compensation parsing (D-4)
- Per-provider parse-error rate telemetry (D-5)
- Column-aware CSV merge safety (D-6)
- Partial-run flags `--only-pass=1`, `--only-companies=...` (D-8)
- ETag / `If-Modified-Since` caching (D-9)
- Scheduled-run quiet mode (D-10)
- `/scout-stats` reader for `runs.jsonl`
- Jobvite / Taleo / iCIMS providers
- Workday auth/CSRF support
- Canonical-URL dedup via redirect resolution

**Anti-features (deliberately NOT building):** retry-on-429 loops (correct backoff is "tomorrow's run"), generic ATS abstraction layer, marketing-page Chrome fallback, per-job LLM enrichment at fetch time, sourcing-layer cross-run dedup (tracker already does it), Workday CSRF harvesting, OAuth flows, third-party "universal ATS detector" libraries, adaptive per-provider rate limiting.

### Architecture Approach

A new `scripts/ats/` package with a Provider Protocol + registry pattern, dispatched through a single concurrent fetch module. Skills hold sequencing and LLM judgement; scripts hold determinism — matching the existing `skills/SKILL.md` + `scripts/*.py` convention. Per-provider concerns (Workday's POST body, Lever's `mode=json`, Ashby's case-sensitive slug) are localized to provider modules so the dispatcher and detector iterate the registry without naming a specific provider.

**Major components:**

1. **`scripts/ats/providers/` (5 modules + base)** — one file per ATS, each conforming to the `Provider` protocol (`NAME`, `BOARD_URL_PATTERNS`, `detect()`, `board_url_from_url()`, `fetch()`, `to_listing()`). New providers in v0.5+ are one file + one registry entry.
2. **`scripts/ats/dispatcher.py`** — single shared `httpx.Client`, `ThreadPoolExecutor(max_workers=20)`, per-provider `threading.Semaphore`. Returns canonical `Listing[]` plus per-provider stats. Errors and zero-results bucketed as distinct return states (`OK_WITH_RESULTS` / `OK_ZERO` / `ERROR`).
3. **`scripts/ats/detect.py`** — two CLI subcommands (`detect-one`, `detect-batch`) sharing the same code. Used by both `/scout-detect` (batch) and `/scout-run` lazy inline path.
4. **`scripts/ats/normalize.py`** — provider JSON → canonical `Listing` dataclass. Owns the schema; per-provider mappers tested against checked-in fixtures.
5. **`scripts/ats/dedupe.py`** — `(normalized_company, normalized_title)` fuzzy dedup. Pass 2 dedupes against Pass 1.
6. **`scripts/ats/runs_log.py`** — append-only writer for `<data_dir>/runs.jsonl`. One JSONL line per run with per-provider, per-company counts and timings.
7. **`skills/scout-detect/SKILL.md`** (new) — orchestrates batch detection across top-30 connection-weighted companies, writes `ats_provider` + `ats_board_url` back to CSV.
8. **`skills/scout-run/SKILL.md`** (rewritten) — 2-pass + enrich flow (Pass 1 ATS → Pass 2 LinkedIn dedupe → score with +1 ATS bump → enrich A-tier ATS via LinkedIn shared-connection lookup → write report → append `runs.jsonl`).

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full diagram, data flow, build-order rationale, and anti-pattern call-outs.

### Critical Pitfalls

The full pitfall catalogue (8 critical + technical-debt patterns + integration gotchas + recovery strategies) is in [PITFALLS.md](./PITFALLS.md). The five highest-leverage to design against:

1. **Trust-ATS-on-0/error silently zeroes companies forever** — the right milestone-honesty call becomes invisible data loss without per-(company, provider) hit history in `runs.jsonl` and "ATS regression suspect" warnings in the report's *Honest notes*. Also requires distinguishing `OK_WITH_RESULTS` vs `OK_ZERO` vs `ERROR` in the dispatcher's return states. **This is what makes the trust decision defensible.**
2. **Slug detection produces false positives** (wrong-company match, dead board, wildcard catch-all). Mitigation is a **two-factor gate**: a slug is only confirmed if the API returns ≥1 job *and* the returned company name fuzzy-matches the input ≥85%. Negative results are cached as `ats_provider=none` to prevent re-probing.
3. **Cross-source dedup over/under-merges, both fail silently.** Mitigation is a **tiered confidence band** (≥95% auto-merge, 70–95% logged for review, <70% keep both) plus a **two-key match** (loose: company-slug + first-3-tokens, tight: company-slug + full normalized title; auto-merge only when both keys agree). Every dedup decision logged to `runs.jsonl`.
4. **Schema migration breaks user files.** Mitigated by a v3 fixture smoke-test in `tests/test_migration.py` (the highest-leverage missing test per `CONCERNS.md`); strictly additive columns; no renames in v0.4. **Schema bump only happens if anything else changes** (see Reconciliation #1).
5. **Concurrent HTTP introduces shared-state bugs the synchronous codebase has never had.** Mitigation is the documented stack: one shared `httpx.Client`, per-provider `threading.Semaphore`, explicit `httpx.Timeout(connect=5, read=15)` on every call, serialized tracker writes (main thread only after `gather` completes), exception-surfacing wrapper around every worker, and an `ats_concurrency_disabled` kill-switch flag in `config.json`.

Also notable: **Workday POST-with-empty-body** misclassification (always POST with `{"appliedFacets":{},"limit":20,"offset":0,"searchText":""}`, capture full `(tenant, data_center, site)` triple in `ats_board_url`, distinguish 400/401/403/200-empty/302 in error logs); **ATS schema drift** (per-provider mappers with fixture tests, field-completion telemetry per provider in `runs.jsonl`); **stale/regional/evergreen postings** (filter on `posted_date` ≤60d default, collapse intra-source regional duplicates pre-dedup, blocklist evergreen titles like "Talent Network").

## Reconciliations

The four researchers had three areas of overlap that need an explicit call. Roadmapper should treat these as authoritative:

### 1. Schema columns `ats_provider` and `ats_board_url` are ALREADY in `scripts/schema.py`

ARCHITECTURE.md verified (line 26–27 of `scripts/schema.py`) that both columns already exist in `MASTER_TARGETS_COLUMNS` and `MASTER_TARGETS_VERSION = 3` already reflects this. PITFALLS.md, working from the `PROJECT.md` "Active" requirement, assumed the columns needed to be added and recommended bumping to v=4.

**Reconciled position:** Phase 1 is **"verify schema is sufficient,"** not **"add columns."** The `PROJECT.md` Active requirement *"Schema in `scripts/schema.py` extends `MASTER_TARGETS_COLUMNS` with `ats_provider` and `ats_board_url`"* is already satisfied. **Only bump `MASTER_TARGETS_VERSION` to 4 if Phase 1 introduces other column changes** (e.g., adding `ats_slug_confidence` for D-2, `last_ats_hit_date` for Pitfall 1's regression detection, or any tracker-side `source`/`ats_provider` columns). If Phase 1 is purely path/JSONL work + verification, version stays at 3.

What Phase 1 *does* still need: ensure `validate_data.py` creates `<data_dir>/daily/<DATE>/ats_raw/` and `<data_dir>/runs.jsonl`, add path entries to `references/file-contract.md`, and ship the v3-fixture migration smoke-test (`tests/test_migration.py`) — the test is valuable even when the migration is a no-op, because it locks in the contract for v0.5+ changes.

### 2. Phase ordering: 6 phases, vertical-slice first, observability folded into the dispatcher milestone

ARCHITECTURE.md recommends 6 phases with **Greenhouse end-to-end first** (vertical slice de-risks the dispatcher contract before paying the cost of 4 more providers). PITFALLS.md recommends 8 phases organized around pitfall prevention (schema → dispatcher → detection → filtering → dedup → observability → cleanup → close).

**Reconciled position:** **6 phases**, leaning on ARCHITECTURE's vertical-slice insight, but with PITFALLS' observability requirements **folded into the relevant phase milestones rather than deferred to a standalone phase**. Specifically:

- **Per-(company, provider) hit history** lands in Phase 2 (dispatcher) as part of `runs_log.py` — not in a later observability phase. Without it, "trust ATS on 0/error" is undefendable from day one.
- **"ATS regression suspect" warnings in the report** land in Phase 5 (alongside dedup + tier bump + enrich) as a markdown rule in `scout-run/SKILL.md` reading from `runs.jsonl`. It's a report-rendering concern, not a separate phase.
- **Field-completion telemetry per provider** rides on `runs_log.py` from Phase 2 onward. New providers in Phase 4 add their telemetry in the same commit.
- **Pass-1 share metric at top of report** lands in Phase 6 with the legacy-deletion + summary-block work.

The recommended phase set is in **Implications for Roadmap** below.

### 3. New dependencies for v0.4

STACK.md recommends `httpx>=0.27,<0.29`. FEATURES.md adds `rapidfuzz` for cross-source dedup. Both are sound and non-overlapping.

**Reconciled position:** **Two new dependencies for v0.4**:
- `httpx>=0.27,<0.29` (HTTP client across all providers; the only sync client that is officially thread-safe with cross-thread connection pooling)
- `rapidfuzz` (cross-source title dedup via `token_set_ratio`; MIT-licensed; faster than `fuzzywuzzy`)

Both surfaced in `ImportError` handlers at module load (matches existing `pandas`/`openpyxl` pattern). No `requirements.txt` per project convention.

## Implications for Roadmap

Based on combined research, suggested 6-phase structure:

### Phase 1: Schema verification + paths + migration smoke-test
**Rationale:** Smallest diff. Unblocks every later phase to write artifacts to known paths. Verify (don't re-add) `ats_provider`/`ats_board_url` columns. Decide whether any other column needs to be added (`ats_slug_confidence`, `last_ats_hit_date`, tracker `source` column) — if yes, bump `MASTER_TARGETS_VERSION = 4`; if no, version stays at 3. Ship the v3 fixture migration test regardless — it locks the contract and is the highest-leverage missing test per `CONCERNS.md`.
**Delivers:** `validate_data.py` creates `daily/<DATE>/ats_raw/` and `runs.jsonl`; `references/file-contract.md` updated; `tests/test_migration.py` passes against `tests/fixtures/master_targets_v3.csv`; round-trip test confirms v0.3 code can read v4 CSV (if version bumped) without crash.
**Addresses:** TS-3 (schema additions). Also: D-2 prerequisite (if `ats_slug_confidence` added now), Pitfall 1 prerequisite (if `last_ats_hit_date` added now).
**Avoids:** Pitfall 4 (schema migration breaks user file).

### Phase 2: Provider Protocol + Greenhouse end-to-end (vertical slice) + dispatcher + observability foundations
**Rationale:** The highest-risk decisions in this milestone — canonical `Listing` shape, dispatcher concurrency model, Provider protocol contract, `runs.jsonl` schema — must be validated against real data before paying the cost of 4 more providers. Greenhouse is the simplest API (no auth, no rate limit, full descriptions inline) so it's the cleanest forcing function. Per-(company, provider) hit history in `runs.jsonl` lands here (not later) so the trust-on-zero decision is defendable from day one.
**Delivers:** `scripts/ats/providers/{base,greenhouse}.py`, `scripts/ats/dispatcher.py` (with shared `httpx.Client`, per-provider semaphores, kill-switch flag, three-state error logging, explicit timeouts, serialized tracker writes), `scripts/ats/normalize.py`, `scripts/ats/runs_log.py` (with per-(company, provider) counts and field-completion telemetry). Wired into `/scout-run` as a Greenhouse-only Pass 1 alongside the existing 3-pass flow (additive — old flow still runs).
**Uses:** `httpx>=0.27,<0.29`, `concurrent.futures.ThreadPoolExecutor`, `threading.Semaphore`.
**Implements:** Architecture components #1 (partial — only Greenhouse + base), #2, #4, #6.
**Avoids:** Pitfall 5 (concurrent HTTP shared-state bugs), Pitfall 7 (schema drift — fixture-tested mapper from day one).

### Phase 3: Detection + `/scout-detect` skill + lazy inline detect
**Rationale:** Once the Greenhouse fetch path is proven, detection can be added against it without risking the fetch path. The `/scout-detect` skill batches top-30; lazy inline detect uses the same code from `/scout-run`. Two-factor gate (200 + ≥1 job + ≥85% name match) and negative-result caching (`ats_provider=none`) ship in v1 — retrofitting them later means re-detecting every company.
**Delivers:** `scripts/ats/detect.py` (with `detect-one` and `detect-batch` subcommands, two-factor gate, negative-result caching, optional `<data_dir>/ats_detection_review.csv` for borderline matches), `skills/scout-detect/SKILL.md`, lazy inline detect in `/scout-run` Step 2b.
**Addresses:** TS-2 (slug detection), TS-3 backfill, D-2 (slug confidence) if Phase 1 added the column, D-7 (idempotent re-runs via skip-if-already-detected).
**Avoids:** Pitfall 2 (slug detection false positives).

### Phase 4: Remaining providers (Lever, Ashby, SmartRecruiters, Workday) + filtering layer
**Rationale:** Provider Protocol absorbs all variation. Each provider is one new file + one registry entry + one row in `references/ats-providers.md`. **Workday last** because its tenant URLs, POST body, and per-tenant data-center variability are the messiest. Filtering layer (posted_date cutoff, regional duplicate collapse, evergreen blocklist) lands in this phase because it's only meaningful once multi-provider data exists.
**Delivers:** `scripts/ats/providers/{lever,ashby,smartrecruiters,workday}.py` (each with fixture tests), Workday CSRF/auth-required detection (logs `workday-auth-required`, defers to Pass 2 explicitly — not silently), filtering in `normalize.py` (default `posted_date` ≤60d, intra-source regional collapse, evergreen pattern blocklist), conditional ATS tier bump (only for postings ≤30d old).
**Uses:** `httpx` POST-with-JSON for Workday, stdlib `re` for Workday tenant URL parsing.
**Avoids:** Pitfall 6 (Workday POST-with-empty-body misclassification), Pitfall 8 (stale/regional/evergreen postings).

### Phase 5: Cross-source dedup + ATS tier bump + enrich-then-tier
**Rationale:** All depend on multi-provider Pass 1 results actually existing. Cross-source dedupe (`scripts/ats/dedupe.py`) uses `rapidfuzz` with the tiered confidence band (≥95% auto, 70–95% review, <70% keep both) and two-key match. ATS tier bump is a markdown rule in `scoring-rubric.md` (in-prompt, not script). Enrich-then-tier is a new step in `scout-run/SKILL.md` driving Chrome MCP shared-connection lookup for ATS A-candidates only. **"ATS regression suspect" warnings** land here as a markdown rule reading from `runs.jsonl`.
**Delivers:** `scripts/ats/dedupe.py` (tiered band, two-key, every decision logged), updated `scoring-rubric.md` with +1 ATS bump rule (conditional on posted_date ≤30d), new Step 5 in `scout-run/SKILL.md` for LinkedIn shared-connection enrichment, regression-suspect warnings in report's *Honest notes*.
**Uses:** `rapidfuzz` (`token_set_ratio` ≥88), Chrome MCP (LinkedIn navigation only — never career page scraping).
**Addresses:** TS-5 (cross-source dedup), TS-8 (`source=` tag in report).
**Avoids:** Pitfall 3 (dedup over/under-merging).

### Phase 6: Run summary + delete legacy code + milestone close
**Rationale:** The deletion is best done last — once Pass 1 is producing the ≥60% A/B share across multiple runs, ripping out the marketing-page Chrome scraping code is safe and the milestone definition explicitly requires it (no soft-delete, no flag-and-keep). Final run-summary block at top of report. 5-run rolling Pass-1 share verified ≥60% before declaring v0.4 complete.
**Delivers:** Run-summary block at top of `report.md` (Pass-1 share %, A/B counts, wall-clock, per-provider breakdown), legacy marketing-page scraping code deleted from `scout-run/SKILL.md` (verified by `grep -r "career_page" skills/ scripts/` returning zero matches), trimmed `chrome-setup.md`, plugin version bumped to 0.4.0, README updated.
**Verifies:** 5-run rolling average of Pass-1 share ≥60%; total `/scout-run` wall-clock ≤5 min; `report.md` contains `source=` on every row; no `source=marketing-page` or `source=careers-html` anywhere.

### Phase Ordering Rationale

- **Phase 1 first** because every other phase assumes the schema columns + `runs.jsonl` path exist. Phase 1 is mostly verification (columns are already in `schema.py`); the migration test is the durable artifact.
- **Greenhouse end-to-end before all 5 providers** (Phase 2 vs Phase 4) because the highest-risk decisions are the `Listing` shape, the concurrency model, and the protocol contract. Cost of being wrong: ~1 day at one provider, ~3 days at five.
- **Detection after one provider works** (Phase 3) because detection has nothing useful to write back if no fetch path validates it. Lazy inline detect reuses the same code.
- **Remaining providers + filtering together** (Phase 4) because filtering only matters with multi-provider data; both are additive once the protocol is stable.
- **Dedup + tier bump + enrich together** (Phase 5) because all depend on multi-provider Pass 1 + Pass 2 producing comparable records.
- **Legacy deletion last** (Phase 6) so it's safe to delete (Pass 1 proven) and the milestone definition's "delete, don't flag" requirement is met.
- **Observability is not its own phase** — it's threaded into Phase 2 (foundations: per-company per-provider counts, three-state errors, field-completion telemetry) and Phase 5 (regression-suspect warnings) and Phase 6 (Pass-1 share % at top of report). PITFALLS.md treated it as standalone; ARCHITECTURE.md folded it in. The folded approach ships the trust-on-zero defensibility from day one rather than week six.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 4 (Workday module specifically):** Workday is the most failure-prone provider — three known tenants (one each on `wd1`, `wd3`, `wd5`) need to be identified for fixture testing; CSRF/auth-required detection requires careful 401/403 body inspection; per-tenant data-center variability is undocumented. Recommend a `/gsd-research-phase` pass before this module is built.
- **Phase 5 (dedup threshold tuning):** The tiered confidence band (≥95% / 70–95% / <70%) has reasonable defaults but production tuning will need real Pass 1 + Pass 2 overlap data. Plan to revisit thresholds after the first week of v0.4 runs.
- **Phase 6 (Pass-1 share verification):** The ≥60% bar is the milestone gate. If 5-run rolling average lands at e.g. 45%, root-cause analysis (which providers are under-detected? which companies are missing slugs? are evergreen postings inflating Pass 1 counts?) needs a research pass before declaring v0.4 ready.

Phases with standard, well-documented patterns (skip research-phase):

- **Phase 1 (schema):** existing `validate_data.py` migration pattern is well-established.
- **Phase 2 (Greenhouse + dispatcher):** Greenhouse API is the simplest and best-documented; dispatcher pattern is fully sketched in STACK.md and ARCHITECTURE.md.
- **Phase 3 (detection):** URL-pattern + redirect-probe + two-factor gate is mechanical against the per-provider patterns in STACK.md.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All 5 ATS endpoints verified with live HTTP probes 2026-04-27. `httpx` thread-safety verified against official docs and GitHub discussions. `requests.Session` thread-unsafety confirmed by maintainer-tagged issues. Concurrency crossover (~50–200 requests) corroborated by multiple benchmark sources. |
| Features | HIGH | All 11 table-stakes features map directly to acceptance criteria in `PROJECT.md`. Differentiator/anti-feature splits cross-referenced against three "competitor" reference points (Apify, OpenJobRadar, strata-harvest). MEDIUM only on dedup heuristics — no widely-published gold standard for personal-scale aggregation. |
| Architecture | HIGH | Existing patterns (skill+script split, single-source-of-truth schema, sibling-script bootstrap) are well-mapped in `.planning/codebase/`. Provider Protocol + registry pattern is standard for multi-provider integrations. LOW only on per-provider concurrency cap *exact values* — intentionally deferred per `PROJECT.md` Out of Scope ("specialize only if we discover real limits in production"). |
| Pitfalls | MEDIUM-HIGH | Greenhouse/Lever/SmartRecruiters/Workday docs verified; Ashby rate limits unstated (treated as unknown — implement defensive backoff). Concurrency advice cross-checked against urllib3/HTTPX/requests issue trackers. Workday CSRF detection patterns are community-sourced (no official docs). |

**Overall confidence:** HIGH

### Gaps to Address

- **Workday tenant CSRF detection patterns** are community-sourced (Apify, GitHub crawlers) — no official Workday docs for unauthenticated public-API access. Mitigation: detect 401/403 with cookie/session/csrf body markers and route to Pass 2 explicitly. Validate against ≥3 known tenants during Phase 4.
- **Per-provider concurrency caps are starting values, not measured limits.** PROJECT.md explicitly defers this: "specialize only if we discover real limits in production." Mitigation: caps live in `config.json`; user can tune without code change. Watch `runs.jsonl` for 429/403 patterns in week 1.
- **Dedup thresholds (≥95% auto, 70–95% review, <70% keep both)** are research-derived defaults. Real overlap rates between Pass 1 and Pass 2 won't be known until v0.4 ships. Mitigation: every dedup decision logged from day one; thresholds tunable in `config.json`; review band visible in run summary.
- **Whether to add `ats_slug_confidence`, `last_ats_hit_date`, or tracker `source`/`ats_provider` columns in Phase 1.** Each is useful for a downstream feature (D-2, Pitfall 1 regression detection, Excel filtering respectively) but each requires a `MASTER_TARGETS_VERSION = 4` bump and migration. **Decision needed at Phase 1 planning** — recommend adding `last_ats_hit_date` (Pitfall 1 dependency, lands in Phase 2) and deferring the others.
- **Missing test infrastructure.** `PROJECT.md` lists "Tests as a deliverable" as Out of Scope, but the v3 fixture migration smoke-test in Phase 1 is non-negotiable per `CONCERNS.md`. Per-provider mapper fixture tests in Phase 2/4 are also strongly recommended. These are not a "test suite" — they are checked-in fixtures + a 30-line script per provider that runs once per CI/manual-verify.

## Sources

### Primary (HIGH confidence)

- **Greenhouse Job Board API** — [developers.greenhouse.io/job-board.html](https://developers.greenhouse.io/job-board.html) + live HTTP probe 2026-04-27 against `airbnb` (221 jobs, 0.73s).
- **Lever Postings API** — [github.com/lever/postings-api](https://github.com/lever/postings-api) + live probes against `spotify`/`leverdemo`/`netflix`/`ramp`/`shopify` (response shape, 404 behavior, latency variance captured).
- **Ashby Public Job Posting API** — [developers.ashbyhq.com/docs/public-job-posting-api](https://developers.ashbyhq.com/docs/public-job-posting-api) + live probe against `Ashby` (63 jobs, 0.66s, all fields captured).
- **SmartRecruiters Posting API** — [developers.smartrecruiters.com/docs/posting-api](https://developers.smartrecruiters.com/docs/posting-api) + live probes against 11 candidate slugs (verified no-auth, list/detail shapes, `Retry-After` semantics).
- **Workday CXS endpoint** — live probe against `workday.wd5.myworkdayjobs.com/Workday` (447 jobs, POST body shape verified, detail call returns full HTML JD).
- **HTTPX thread safety** — [python-httpx.org/advanced/clients/](https://www.python-httpx.org/advanced/clients/) + [GitHub discussion #1633](https://github.com/encode/httpx/discussions/1633).
- **Requests Session thread-unsafety** — [GitHub issue #2766](https://github.com/psf/requests/issues/2766), [issue #1871](https://github.com/psf/requests/issues/1871) (maintainer-confirmed).
- **Internal codebase mapping** — `.planning/codebase/{ARCHITECTURE,STRUCTURE,CONVENTIONS,CONCERNS}.md` and `scripts/schema.py:26-27` (verified `ats_provider`/`ats_board_url` already present).
- **Internal project decisions** — `.planning/PROJECT.md` (locked-in v0.4 constraints).

### Secondary (MEDIUM confidence)

- **Workday Scraper API guide** — [jobo.world/ats/workday](https://jobo.world/ats/workday) (third-party reverse-engineered).
- **HTTPX vs Requests vs aiohttp comparison** — [decodo.com/blog/httpx-vs-requests-vs-aiohttp](https://decodo.com/blog/httpx-vs-requests-vs-aiohttp) (concurrency crossover point).
- **Ashby rate limits** — undocumented; treated as unknown.
- **Fuzzy dedup confidence bands** — [futuresearch.ai/researcher-dedupe-case-study](https://futuresearch.ai/researcher-dedupe-case-study/), [dataladder.com/fuzzy-matching-101](https://dataladder.com/fuzzy-matching-101/) (95% auto / 70–95% review / <70% reject — corroborated across multiple sources but not formally benchmarked for job titles specifically).
- **Concurrency patterns** — [superfastpython.com/threadpoolexecutor-limit-pending-tasks](https://superfastpython.com/threadpoolexecutor-limit-pending-tasks/), [rednafi.com/python/limit-concurrency-with-semaphore](https://rednafi.com/python/limit-concurrency-with-semaphore/).

### Tertiary (LOW confidence — needs validation)

- **Workday CSRF/session-token detection patterns** — community-sourced from Apify and GitHub crawlers; no official Workday docs for unauthenticated public-API behavior. Validate against ≥3 known tenants during Phase 4.
- **Per-provider concurrency cap exact values** — derived from observed latency + tenant-isolation patterns, not measured against documented rate limits (most providers don't publish them). Tune in production.

---
*Research completed: 2026-04-27*
*Ready for roadmap: yes*

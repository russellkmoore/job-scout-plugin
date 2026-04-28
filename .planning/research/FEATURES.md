# Feature Research

**Domain:** ATS-first job sourcing pipeline (personal, single-user, daily-batch)
**Researched:** 2026-04-27
**Confidence:** HIGH (ATS endpoints / pagination / rate limits verified against vendor docs); MEDIUM on dedup heuristics (no widely-published gold standard for personal-scale aggregation).

---

## Scope Note

This document covers **v0.4 sourcing layer features** only — what an ATS-first job-sourcing pipeline must do to clear the milestone bar in PROJECT.md:

> Pass 1 (ATS) contributes ≥60% of A/B-tier candidates, total `/scout-run` ≤5 minutes, no Chrome fallback for ATS-undetected companies.

It does **not** re-spec already-shipped features (scoring rubric, tracker writer, daily report, packets, profile mining). Those are touched only where v0.4 changes them (e.g. `+1 tier bump`, `source=` tag).

The "user" here is a single operator running `/scout-run` daily. There is no second user, no SLA, no hosting, no auth — every "differentiator" is judged against *whether it makes the next 30 daily runs more reliable for one person*, not against commercial aggregator features.

---

## Feature Landscape

### Table Stakes (Required to Clear the ≥60% Pass-1 Milestone)

Without these, v0.4 fails its acceptance criteria — either the ATS layer doesn't return jobs, jobs can't be scored, or the operator can't tell whether it worked.

| # | Feature | Why Required | Complexity | Notes |
|---|---------|--------------|------------|-------|
| TS-1 | **Per-provider ATS client** for Greenhouse, Lever, Ashby, SmartRecruiters, Workday | Each ATS has its own URL shape, auth model, pagination, and field names. There is no "just call one endpoint." Must be 5 distinct, simple modules. | M | Greenhouse: `GET boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true`, no auth, no rate limit, returns full descriptions inline. Lever: `GET api.lever.co/v0/postings/{slug}?mode=json`, no auth, 10 req/s steady, cursor pagination. Ashby: `GET api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true`, no auth, no filters available — full board returned. SmartRecruiters: `GET api.smartrecruiters.com/v1/companies/{slug}/postings`, no auth, offset/limit, then `GET .../postings/{id}` for description. Workday: `POST {tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` with `{"limit":20,"offset":0,"searchText":""}`, no auth on most public boards, then `GET .../job/{externalPath}` for full HTML. |
| TS-2 | **ATS slug discovery** (URL-pattern + redirect probe) | Without a slug, no API call. Top-30 detection seeds the high-value targets; everything else fails open to Pass 2. | M | Probe order per company: (a) check `careers_url` against known host patterns (`boards.greenhouse.io/{slug}`, `job-boards.greenhouse.io/{slug}`, `jobs.lever.co/{slug}`, `jobs.ashbyhq.com/{slug}`, `jobs.smartrecruiters.com/{slug}`, `*.myworkdayjobs.com`); (b) follow `careers.{company}.com` redirects (most resolve to one of the above); (c) HTML probe for `boards.greenhouse.io/embed/job_board?for={slug}` iframes. Stop on first hit. Cache result. **Match must be confidence-graded** — a wrong slug pollutes the run with another company's jobs. |
| TS-3 | **Schema additions** to `MASTER_TARGETS_COLUMNS` (`ats_provider`, `ats_board_url`) | Decided in PROJECT.md. Required for hybrid detection (top-30 + lazy inline) to persist. Must go through `scripts/schema.py` per the no-drift rule. | S | Two new optional columns. `validate_data.py` already auto-migrates additions silently — leverage that. `consolidate_targets.py` column-alias map needs entries so user-supplied CSVs with a "Greenhouse URL" header land in the right place. |
| TS-4 | **Result normalization across providers** | Scoring, tracker writer, dedup, and report formatter all expect one shape. If each provider's raw payload reaches the scorer, the rubric breaks (different field names, different location encodings, different "remote" semantics). | M | Minimum normalized fields: `company`, `title`, `location` (string + remote bool), `apply_url`, `description_text` (HTML stripped), `posted_at` (ISO8601 if known, else None), `source` (`"ats:greenhouse"` etc.), `external_id` (provider's id, used for dedup), `compensation` (string-or-None — not all providers expose it). **Drop everything else** at the boundary; do not let raw provider JSON bleed into the scorer. Anti-pattern: a "unified ATS abstraction layer" that tries to model 20 providers (see Anti-Features). |
| TS-5 | **Cross-source dedup**: ATS Pass 1 vs LinkedIn Pass 2 | Without dedup, Pass 2's LinkedIn keyword path will re-surface the same jobs the ATS path already returned, inflating counts and confusing the report. PROJECT.md decided: company-slug + normalized-title fuzzy match. | M | Normalize: lowercase, strip punctuation, drop common suffixes (`Inc`, `LLC`, `Corp`), drop seniority noise from titles (`Sr.` → `Senior`, drop `(Remote)`/`(US)`/`- Hybrid`). Match key: `(normalized_company, token_set_ratio(title_a, title_b) >= 88)`. **Pass 2 dedupes against Pass 1, not vice-versa** — ATS is the canonical source. Use `rapidfuzz` (single new dep, faster + more accurate than `fuzzywuzzy`, MIT-licensed). |
| TS-6 | **Per-provider concurrency cap with bounded wall-clock** | Sequential = the existing 10-15min problem. Unbounded concurrency = 429s, IP blocks, and a broken milestone. PROJECT.md committed to "single concurrent-cap policy across all providers." | M | Use `httpx.AsyncClient` + `asyncio.Semaphore(N)` per provider host. Defaults: Greenhouse N=10 (cached, no published limit), Lever N=8 (10 req/s published, leave headroom), Ashby N=6, SmartRecruiters N=6, Workday N=4 (heaviest payloads, slowest tenants). Single `asyncio.gather()` over all companies. Total budget: 60s for Pass 1 across ~30 companies. |
| TS-7 | **Per-call timeout + circuit break (no retry storm)** | A single hung Workday tenant must not blow the 5-minute budget. Repeated 403/429 must not escalate into a ban. | S | `httpx.Timeout(connect=5, read=10)`. On 429/503: skip company, log, **do not retry within the same run**. On 403: same. On network error: one immediate retry, then skip. **Zero exponential backoff inside a run** — operator runs once a day; the "backoff" is "wait 24 hours." This is a deliberate anti-feature inversion — see AF-1. |
| TS-8 | **`source=` tag on every listing** | Required for the report's per-pass breakdown and the ≥60% acceptance check. Already mandated in PROJECT.md. | S | Format: `source=ats:greenhouse`, `source=ats:lever`, `source=linkedin`, `source=builtin`, `source=wellfound`. Stored in normalized record (TS-4) and rendered next to apply URL in `report.md`. Persists into `tracker.xlsx` so historical analysis can ask "did Lever-sourced jobs convert better?" |
| TS-9 | **Run-summary block + persisted `runs.jsonl`** | Without this, the operator cannot verify the milestone bar (≥60% Pass 1) and cannot detect slow regression (e.g. "Greenhouse has returned zero for 5 days"). | S | At end of `/scout-run`, append one line to `<data_dir>/runs.jsonl` with: `{date, plugin_version, wall_clock_s, total_jobs, pass1_jobs, pass2_jobs, a_count, b_count, c_count, pass1_share_pct, ats_breakdown:{greenhouse:N,lever:N,...}, errors:[{provider, company, status}]}`. Print same numbers in chat. **Never read in v0.4** — just persist. A `/scout-stats` reader is a v0.5 differentiator. |
| TS-10 | **Trust-on-zero / trust-on-error semantics** | PROJECT.md commits to "if an ATS endpoint returns 0 or errors, treat as 'no openings, move on' — no Chrome scrape fallback." Critical for the milestone honesty story. | S | Implementation is mostly *what we don't build*: no "if Greenhouse returned 0 then call Chrome" branch anywhere. Log the zero/error in `runs.jsonl` so trends are visible, but do not act on it. |
| TS-11 | **Schema-driven listing parser per provider** | Each provider's response shape changes occasionally (Workday added new fields in 2024; SmartRecruiters added compensation). A field-by-field unpacker that fails loudly is required so silent breakage is impossible. | M | One `parse_{provider}(payload) -> NormalizedJob` function per ATS in `scripts/ats/<provider>.py`. Required fields raise `ParseError` with the offending payload snippet; optional fields default to None. **Every error counted in `runs.jsonl`.** |

**Subtotal:** 11 table-stakes features. Without all 11, the milestone fails on at least one of {≥60% bar / 5-min budget / no-Chrome-fallback / verifiability}.

---

### Differentiators (Improve Quality, Optional for v0.4)

Features that make the next 30 daily runs noticeably better — but the milestone passes without them. Build only if the table-stakes set lands with budget left.

| # | Feature | Value Proposition | Complexity | Notes |
|---|---------|-------------------|------------|-------|
| D-1 | **JSON-LD `JobPosting` fallback for unmatched companies** | Some companies host their own career pages but emit `<script type="application/ld+json">` with `JobPosting` schema. Cheap to detect, no rendering needed, recovers ~10-15% of "ATS-undetected" companies without bringing back marketing-page scraping. | M | Single fetch + `json.loads` of all `<script type="application/ld+json">` blocks; filter to `@type == "JobPosting"`. **Tag as `source=jsonld`** so it's distinguishable in the report. Skip if zero structured jobs found — never fall through to HTML parsing. |
| D-2 | **Slug confidence scoring + manual override** | Wrong slug = another company's jobs in the report. A confidence score (`high` = exact host match, `medium` = redirect-resolved, `low` = HTML probe) lets the operator triage. CSV column `ats_slug_confidence` is the override mechanism. | S | Three-level enum stored in `master_targets.csv`. Operator can set `ats_provider=manual` + `ats_board_url=<url>` to lock in a verified slug and bypass detection. Detection skips rows where confidence is `manual`. |
| D-3 | **Posted-date filtering at the API boundary** | Today the scorer sees every active posting. Filtering to `posted >= today - 14d` at fetch time cuts noise and respects "Pass 1 first" — old jobs the operator already saw are not re-scored. | S | Greenhouse: `?content=true` returns `updated_at`. Lever: `createdAt` in payload. Ashby: `publishedAt`. SmartRecruiters: `releasedDate`. Workday: `postedOn` (relative string — needs parsing). **Filter post-fetch in normalizer**, not in API params (most providers don't support a date filter). Threshold lives in `config.search.max_listing_age_days` (default 14). |
| D-4 | **Compensation parsing into structured fields** | Several providers now return comp ranges as structured data (Ashby always; Greenhouse if employer enables it; SmartRecruiters in some tenants). Today the scorer sees a string like `"$180k-$220k"` and treats it as opaque text. Structured `(min, max, currency)` enables the Compensation rubric category to score deterministically rather than via LLM judgement. | M | Provider-specific parsers (Ashby's is `compensation.compensationTierSummary`; Greenhouse's is `pay_input_ranges`). Fall back to regex on description text for the others. Store as `comp_min_usd`, `comp_max_usd`, `comp_source` (`api`/`regex`/`unknown`). |
| D-5 | **Per-provider parse-error rate tracked in `runs.jsonl`** | When SmartRecruiters changes a field name (they have, twice), the rate of `ParseError` exceptions for that provider spikes. Surfacing this in run telemetry catches schema drift in 1-2 runs instead of 1-2 weeks. | S | Already requires that TS-11 logs every parse error with `(provider, company, field, sample)`. Adds a per-provider rate: `errors[provider] / attempts[provider]`. No alerting in v0.4 — just visible in the persisted log. |
| D-6 | **Operator CSV editing safety** (column-aware merge in `consolidate_targets.py`) | Today the operator edits `master_targets.csv` in Excel; on next run, `consolidate_targets.py` may overwrite columns. v0.4's two new columns (`ats_provider`, `ats_board_url`) make this worse — operator manually fixes a wrong slug, then loses the fix. | M | Already partly implemented (the "prefer user-entered data over auto-generated" merge logic in `consolidate_targets.py`). Extend to: if `ats_provider` is set in the user file, never overwrite it. Add `ats_provider_override=Y` flag. |
| D-7 | **Idempotent `/scout-detect` re-runs** | The skill is reusable when companies are added. Must not re-detect companies that already have `ats_provider` set unless `--force` is passed. Saves wall-clock and API calls; respects manual overrides from D-2. | S | One condition at the top of the per-company loop: `if row.ats_provider and row.ats_provider != "" and not args.force: continue`. Surfaces as `skipped_already_detected: N` in the skill's chat summary. |
| D-8 | **Re-run / partial-run flag** (`--only-pass=1`, `--only-companies=...`) | When Pass 2 (LinkedIn) breaks mid-run today, the operator has to re-run the whole 10-15min flow. Restricting to "just re-run Pass 1 against these 5 companies" makes incident recovery cheap. | M | Adds two CLI flags to `/scout-run`. Pass-1-only is trivial (skip Pass 2 step). Per-company filter requires the master-targets reader to accept a filter. **Anti-feature trap**: do not add `--no-dedup` or `--no-validate`; partial runs must still be safe to merge into the tracker. |
| D-9 | **ETag / `If-Modified-Since` caching per ATS board** | Ashby returns the entire board on every call (no filters). Greenhouse boards rarely change between runs. Sending `If-Modified-Since: <last_run_iso>` on each `GET` cuts payload + parse time on no-change boards by ~80%. | M | Cache file: `<data_dir>/.cache/ats_etags.json` keyed by `(provider, slug)`. On 304, reuse last `runs.jsonl` count for that company. Skipped in v0.4 if it adds debug surface area. **Workday POSTs are not cacheable** — skip caching for that one provider. |
| D-10 | **Scheduled-run quiet mode** | When run via cron/launchd, `/scout-run` should write to file and emit one summary line — not the full conversational chat output. Today's scheduled runs are noisy. | S | Detected via `--quiet` flag set by the user's cron entry. Only emits the run-summary block (TS-9) and the report path. |

**Subtotal:** 10 differentiators. Recommended **stretch set for v0.4**: D-1, D-2, D-3, D-7. The rest are v0.5+.

---

### Anti-Features (Deliberately NOT Build)

Features that look obvious or get requested early. Each one would either inflate scope past the 5-min budget, recreate the fragility v0.4 is removing, or invite the kind of regression the operator's profile flags as the top frustration.

| # | Anti-Feature | Why Tempting | Why Problematic | Better Approach |
|---|--------------|--------------|-----------------|-----------------|
| AF-1 | **Retry-on-403 / exponential-backoff loop** | "Just retry — the provider was probably rate-limiting us." | Personal scout runs once per day. A retry loop turns one 429 into 4-5 requests, which moves the operator's IP from "polite" to "abusive." Rate-limit blocks compound across runs. The correct backoff is "wait 24 hours" — i.e. tomorrow's run. | Skip on first 4xx/5xx. Log it. Move on. Trust TS-9's `runs.jsonl` to surface a run of failures across days, not within one. |
| AF-2 | **Generic ATS abstraction layer** ("a single `ATSClient` interface for 20 providers") | "Plug in a new provider in 50 lines." | Each ATS has wildly different semantics: Workday CSRF tokens, Greenhouse iframe embeds, Lever stages, Ashby's "no filtering" constraint. A generic interface either becomes a leaky abstraction (every provider needs an escape hatch) or forces the lowest-common-denominator on all of them. The plugin's duplication concern in `CONCERNS.md` is about **6th copies of the same per-source pattern**, not about reusing struct names. | One small, dumb module per provider in `scripts/ats/<provider>.py` — `fetch(slug, since)` and `parse(payload)` — sharing only the `NormalizedJob` dataclass. Five files of 80-120 lines each. |
| AF-3 | **Marketing-page Chrome fallback ("for ATS-undetected companies")** | "We have Chrome anyway, why not use it as a safety net?" | This is exactly the v0.3 fragility v0.4 is removing. Adding it back as a "fallback" guarantees it gets used in 30% of runs and the milestone metric (≥60% Pass 1) drifts. PROJECT.md committed to deleting this code, not flagging it. | ATS-undetected companies fall through to Pass 2 (LinkedIn keyword) only. If that doesn't work either, the company is silently absent from today's report. Operator sees the gap in `runs.jsonl` over time and either adds the slug manually (D-2) or accepts the company has no public listings. |
| AF-4 | **Job-description LLM enrichment at fetch time** | "Use Claude to summarize each JD into a structured form before scoring." | At ~30 companies × ~5 jobs each = 150 LLM calls per run. Even at 2s each that blows the 5-min budget. The scorer already does this *after* the cheap header-triage — moving it earlier is pure cost. | Header-triage scoring first (title + company + connection count). Only run the JD-aware scoring step on listings that pass the header threshold. (This is also a Performance Bottleneck recommendation in `CONCERNS.md`.) |
| AF-5 | **Cross-run job-deduplication via persistent ID set** | "We've seen this LinkedIn job before — drop it." | Already exists at the tracker layer (`tracker_utils.dedup-set`). Reimplementing in the sourcing layer creates two dedup paths that will diverge. | Continue to dedup at the tracker boundary. Pass 1 / Pass 2 dedup within the run (TS-5) is the only new dedup v0.4 adds. |
| AF-6 | **Workday CSRF / session-token harvesting** | "Then we'd cover Workday tenants that need login." | Out of scope per PROJECT.md. Workday auth dance is fragile (varies per tenant, breaks on every Workday release), would dwarf the rest of the ATS layer in code, and most authed-only Workday tenants are also on LinkedIn anyway. | If a Workday tenant requires CSRF, log a one-time `requires_auth=true` flag against that company in `master_targets.csv` and stop probing it. Operator gets it via Pass 2. |
| AF-7 | **Multi-language / multi-locale Workday URLs** | "Cover `/en-US/` and `/en-GB/` and `/de/`." | Adds matrix of failures for ~5% coverage uplift. The operator is in Seattle, US — every relevant Workday tenant exposes `/en-US/`. | Hard-code `en-US` as the only locale in v0.4. Note in code comment for v0.5 if international roles become a use case. |
| AF-8 | **OAuth / API key flows for any ATS** | "Then we get richer data." | All five v0.4 providers expose public **read** endpoints with no auth. Adding OAuth for richer data (rejected candidates, hiring stages) is irrelevant to a sourcing pipeline — those are recruiter-side fields. | Stay on public endpoints. Document this explicitly in `STACK.md` so future contributors don't try to "upgrade." |
| AF-9 | **A "universal ATS detector" service or library dependency** | "There's a library for this — `strata-harvest`, ATS-detector npm package, etc." | Adds a third-party dep that abstracts the one thing v0.4 most needs visibility into (which provider matched, with what confidence). When it gets it wrong, debugging is a layer deeper. | Hand-roll TS-2 in `scripts/ats/detect.py` — ~150 lines covering all 5 providers + JSON-LD probe. Keeps the code in the same module as the per-provider clients (TS-1) where the URL patterns are already known. |
| AF-10 | **Per-provider rate-limit headers respected dynamically** | "Read `X-RateLimit-Remaining` from each response and adapt." | Only Lever publishes useful rate-limit headers. Greenhouse and Ashby don't rate-limit at all. Workday doesn't expose anything. Adaptive logic for one provider is more code than the static cap (TS-6) and harder to reason about under failure. PROJECT.md explicitly rejected per-provider strategies. | Static per-host semaphore caps (TS-6). Revisit only if a real production limit gets hit. |

**Subtotal:** 10 anti-features. The first three (AF-1, AF-2, AF-3) are the highest-risk traps — flag them in design review for v0.4.

---

## Feature Dependencies

```
TS-3 (schema columns)
    └── TS-2 (slug discovery)            ← writes ats_provider, ats_board_url
            └── TS-1 (provider clients)  ← reads ats_board_url
                    └── TS-11 (parsers)
                            └── TS-4 (normalization)
                                    ├── TS-5 (cross-source dedup)
                                    ├── TS-8 (source= tag)
                                    └── TS-9 (runs.jsonl)
                                                └── D-5 (parse-error rate)

TS-6 (concurrency cap) ──gates──> TS-1   ← all client calls flow through it
TS-7 (timeout / no-retry) ──gates──> TS-1

D-1 (JSON-LD fallback) ──extends──> TS-2 (treat as 6th provider)
D-2 (slug confidence) ──extends──> TS-2 (writes confidence column)
D-3 (posted-date filter) ──filters in──> TS-4 (post-normalization)
D-4 (comp parsing) ──enriches──> TS-4
D-6 (CSV merge safety) ──protects──> TS-3 (operator edits don't get clobbered)
D-7 (idempotent re-detect) ──reads──> D-2
D-9 (ETag cache) ──optimizes──> TS-1

AF-3 (Chrome fallback) ──conflicts with──> TS-10 (trust-on-zero)
AF-1 (retry storm)     ──conflicts with──> TS-7 (no-retry policy)
AF-5 (sourcing-layer dedup) ──conflicts with──> existing tracker dedup
```

### Dependency Notes

- **TS-3 must land before TS-2.** Slug discovery has nowhere to write its result without the new columns. Order matters in the implementation sequence.
- **TS-11 sits between TS-1 and TS-4.** Tempting to skip it ("just unpack inline in the client") — don't. It is the schema-drift detector for D-5.
- **TS-6 / TS-7 are cross-cutting policies, not steps.** Both gate every TS-1 call. Implementing them as a single shared `ats_http.py` module avoids the 6th-copy concern in `CONCERNS.md`.
- **D-2 + D-6 are co-dependent.** Confidence scoring is only useful if operator overrides survive the next consolidate run. Build them together or neither.
- **AF-3 conflicts with TS-10 by design.** PROJECT.md treats "no Chrome fallback" as a milestone-defining constraint, not a preference. Any future "but what if just for these companies…" request reopens this.
- **AF-5 conflicts with the existing tracker dedup.** Two dedup paths will eventually disagree and the operator will lose listings. Keep the boundary at the tracker.

---

## MVP Definition (v0.4)

### Launch With (v0.4 ships when these all work)

The 11 table stakes, in implementation order:

- [ ] **TS-3** — Schema additions (`ats_provider`, `ats_board_url`) in `scripts/schema.py`; `validate_data.py` auto-migration verified
- [ ] **TS-2** — Slug detection module (`scripts/ats/detect.py`) covers all 5 providers via URL pattern + redirect probe; new `/scout-detect` skill writes back to CSV
- [ ] **TS-1** — Per-provider client modules (`scripts/ats/{greenhouse,lever,ashby,smartrecruiters,workday}.py`), each with `fetch()` and `parse()`
- [ ] **TS-11** — Each provider has a schema-driven parser that fails loudly on missing required fields
- [ ] **TS-4** — Single `NormalizedJob` dataclass; all five clients return it
- [ ] **TS-6** — `ats_http.py` shared module with per-host `httpx.AsyncClient` + `asyncio.Semaphore`; single `gather()` for Pass 1
- [ ] **TS-7** — 5/10s timeout, no in-run retries on 4xx/5xx, one retry on network error, then skip
- [ ] **TS-5** — Cross-source dedup via `rapidfuzz` (token_set_ratio ≥ 88) on `(normalized_company, normalized_title)`; Pass 2 dedupes against Pass 1
- [ ] **TS-8** — `source=` tag plumbed through normalizer → scorer → report → tracker
- [ ] **TS-9** — `<data_dir>/runs.jsonl` appended after every run; chat summary block printed
- [ ] **TS-10** — Code review confirms zero Chrome fallback paths exist for ATS-undetected companies; old marketing-page scraping code is **deleted**, not flagged

**Acceptance test (manual, no formal suite per PROJECT.md):**
- Run `/scout-detect` against current `master_targets.csv`; expect ≥75% of top-30 companies resolved with high or medium confidence.
- Run `/scout-run` end-to-end; assert wall-clock ≤ 5 minutes.
- Inspect `runs.jsonl`: assert `pass1_share_pct ≥ 60`.
- Inspect `report.md`: every listing has a `source=...` tag; no listing's `source` is `marketing-page` or `careers-html`.

### Add After v0.4 Validates (v0.4.x point releases)

Stretch set, only if v0.4 base lands clean:

- [ ] **D-1** — JSON-LD fallback for unmatched companies (recovers the long tail without bringing back HTML scraping)
- [ ] **D-2** — Slug confidence scoring + `manual` override flag
- [ ] **D-3** — Posted-date filtering at normalizer (`config.search.max_listing_age_days`)
- [ ] **D-7** — Idempotent `/scout-detect` re-runs (`--force` flag; skip already-detected by default)

### Future Consideration (v0.5+)

- [ ] **D-4** — Structured compensation parsing (improves scoring rubric determinism)
- [ ] **D-5** — Per-provider parse-error rate in `runs.jsonl` (defer until D-3 lands)
- [ ] **D-6** — Column-aware CSV merge safety in `consolidate_targets.py`
- [ ] **D-8** — `--only-pass=1`, `--only-companies=...` partial-run flags
- [ ] **D-9** — ETag / `If-Modified-Since` caching
- [ ] **D-10** — Scheduled-run quiet mode
- [ ] **`/scout-stats` skill** — reads `runs.jsonl` across days; surfaces "Greenhouse has returned 0 jobs for 5 runs" alerts
- [ ] **Jobvite, Taleo, iCIMS providers** — explicitly out of scope per PROJECT.md
- [ ] **Workday auth/CSRF** — out of scope per PROJECT.md
- [ ] **Canonical-URL dedup via redirect resolution** — out of scope per PROJECT.md (revisit if false-merges become a problem)

---

## Feature Prioritization Matrix

| Feature | Operator Value | Implementation Cost | v0.4 Priority | Tied to Milestone Bar |
|---------|----------------|---------------------|---------------|----------------------|
| TS-1 Per-provider clients | HIGH | M | **P0** | Yes (≥60% Pass 1 impossible without ATS calls) |
| TS-2 Slug discovery | HIGH | M | **P0** | Yes (no clients without slugs) |
| TS-3 Schema additions | HIGH | S | **P0** | Yes (slug discovery has nowhere to persist) |
| TS-4 Result normalization | HIGH | M | **P0** | Yes (scorer / dedup / report all expect uniform shape) |
| TS-5 Cross-source dedup | HIGH | M | **P0** | Yes (Pass 2 inflation breaks ≥60% metric calc) |
| TS-6 Concurrency cap | HIGH | M | **P0** | Yes (5-min budget impossible sequentially) |
| TS-7 Timeout + no-retry | HIGH | S | **P0** | Yes (one hung tenant blows the budget) |
| TS-8 `source=` tag | HIGH | S | **P0** | Yes (verifiability of ≥60% bar) |
| TS-9 `runs.jsonl` | HIGH | S | **P0** | Yes (verifiability of ≥60% bar) |
| TS-10 Trust-on-zero / no fallback | HIGH | S | **P0** | Yes (milestone constraint per PROJECT.md) |
| TS-11 Schema-driven parsers | MEDIUM | M | **P0** | Indirect (silent breakage hides regressions) |
| D-1 JSON-LD fallback | MEDIUM | M | **P1** | Stretches coverage |
| D-2 Slug confidence | MEDIUM | S | **P1** | Reduces wrong-slug pollution |
| D-3 Posted-date filter | MEDIUM | S | **P1** | Cuts scoring noise |
| D-7 Idempotent re-detect | LOW | S | **P1** | Quality of life |
| D-4 Comp parsing | MEDIUM | M | **P2** | Better scoring determinism |
| D-5 Parse-error rate | LOW | S | **P2** | Schema-drift early warning |
| D-6 CSV merge safety | MEDIUM | M | **P2** | Operator-edit safety |
| D-8 Partial-run flags | LOW | M | **P2** | Incident recovery |
| D-9 ETag caching | LOW | M | **P3** | Pure performance |
| D-10 Quiet mode | LOW | S | **P3** | Cron ergonomics |

**Priority key:**
- **P0** — Must ship in v0.4 (cleared for the ≥60% / 5-min / no-fallback bar)
- **P1** — Stretch goal for v0.4 if budget allows
- **P2** — v0.4.1 / v0.4.2 point releases
- **P3** — v0.5+ (defer until product use justifies)

---

## "Competitor" Feature Analysis

This is a single-user personal pipeline; there are no direct competitors. But the design space is well-explored — three reference points worth comparing against:

| Feature Area | Apify multi-ATS scrapers | OpenJobRadar | strata-harvest | **job-scout v0.4 plan** |
|---|---|---|---|---|
| ATS detection | URL-pattern only | 7-strategy pipeline (slug, brute-force, link scan, Playwright) | URL pattern + DOM signature, confidence-scored | URL pattern + redirect probe, confidence-scored (D-2 stretch). No Playwright. |
| Provider count | 5-10 (varies by actor) | 12+ | 8+ (REST/JSON/GraphQL) | 5 (Greenhouse, Lever, Ashby, SmartRecruiters, Workday) |
| Auth complexity | Avoided | Avoided | Avoided | Avoided (public endpoints only) |
| Concurrency model | Per-actor cap | Crawler queue | Async semaphore | Async semaphore per provider (TS-6) |
| Rate-limit strategy | Provider-specific backoff | Adaptive backoff | Adaptive backoff | **Static cap, no in-run retry (TS-7)** — daily-batch pattern doesn't need adaptive |
| Dedup | Per-source only | Cross-source URL dedup | Per-source | Pass 1 vs Pass 2 fuzzy (TS-5) — leverages already-existing tracker dedup |
| Output schema | Provider-specific JSON | Normalized JSON | Normalized dataclass | NormalizedJob dataclass (TS-4) |
| Telemetry | Apify run logs | Internal dashboard | None | `runs.jsonl` (TS-9), no dashboard |
| Cost / footprint | Hosted SaaS | Hosted SaaS | Library | Local Python script + 1 new dep (`httpx`/`rapidfuzz`) |

**Takeaway:** The features that distinguish a personal-scale pipeline from a commercial aggregator are *what we choose not to build*. No retry adaptation, no Playwright fallback, no dashboard, no provider count maximization — those are the costs we trade away to keep `/scout-run` boring, fast, and inspectable.

---

## Key Constraints from PROJECT.md (Cross-Reference)

Every table-stakes feature was selected against these constraints. Summary mapping:

| PROJECT.md Constraint | Tied Feature(s) |
|---|---|
| Pass 1 (ATS) ≥ 60% of A/B-tier candidates | TS-1, TS-2, TS-4, TS-8, TS-9 (verifiability) |
| Total `/scout-run` ≤ 5 min | TS-6, TS-7, AF-1 (no retry storm), AF-4 (no per-job LLM) |
| No Chrome fallback for ATS-undetected | TS-10, AF-3 |
| Schema additions must be additive | TS-3 (uses `validate_data.py` auto-migration) |
| Single concurrent-cap policy across providers | TS-6, AF-10 (no adaptive limits) |
| 5 providers only (Greenhouse / Lever / Ashby / SmartRecruiters / Workday) | TS-1, AF-2 (no generic abstraction), AF-6 (no Workday auth), AF-8 (no OAuth) |
| Dedup: company-slug + normalized-title fuzzy | TS-5 |
| ATS-sourced jobs get +1 tier bump | TS-8 (source tag is the signal) |
| `source=` on every listing | TS-8 |
| Per-run summary + persisted `runs.jsonl` | TS-9 |

---

## Sources

- [Greenhouse Job Board API (developers.greenhouse.io)](https://developers.greenhouse.io/job-board.html)
- [Greenhouse API overview (support.greenhouse.io)](https://support.greenhouse.io/hc/en-us/articles/10568627186203-Greenhouse-API-overview)
- [Lever Postings API (GitHub: lever/postings-api)](https://github.com/lever/postings-api)
- [Lever ATS API: Postings, Candidates & OAuth Guide 2026 (Knit)](https://www.getknit.dev/blog/lever-api-directory)
- [Ashby Job Postings API (developers.ashbyhq.com)](https://developers.ashbyhq.com/docs/public-job-posting-api)
- [SmartRecruiters Posting API (developers.smartrecruiters.com)](https://developers.smartrecruiters.com/docs/posting-api)
- [SmartRecruiters Get job postings (developers.smartrecruiters.com)](https://developers.smartrecruiters.com/docs/get-job-postings)
- [Workday Scraper API: Extract Jobs from Workday Career Sites (jobo.world)](https://jobo.world/ats/workday)
- [Workday Job Scraper / Career Pages API (Apify)](https://apify.com/blackfalcondata/workday-scraper/api/cli)
- [Multi-ATS Job Scraper: Greenhouse, Workday & More (Apify)](https://apify.com/automation-lab/multi-ats-jobs-scraper)
- [6 ATS Platforms with Public Job Posting APIs (fantastic.jobs)](https://fantastic.jobs/article/ats-with-api)
- [How to Build a Job Board Integrating Greenhouse, Lever, and 73+ ATS Platforms (Unified.to)](https://unified.to/blog/how_to_build_a_job_board_integrating_greenhouse_lever_and_73_ats_platforms_with_an_ats_api)
- [Fuzzy Matching 101 (Data Ladder)](https://dataladder.com/fuzzy-matching-101/)
- [Normalising Data: Job Titles, Skills & Locations (jobspikr.com)](https://www.jobspikr.com/blog/normalising-data-job-titles-skills-locations/)
- [How to Rate Limit Async Requests in Python (Scrapfly)](https://scrapfly.io/blog/posts/how-to-rate-limit-asynchronous-python-requests)
- [Limit concurrency with semaphore in Python asyncio (rednafi.com)](https://rednafi.com/python/limit-concurrency-with-semaphore/)
- [Async Web Scraping in Python: httpx + asyncio (DEV Community)](https://dev.to/vhub_systems_ed5641f65d59/async-web-scraping-in-python-httpx-asyncio-for-10x-faster-data-collection-4eie)
- [Observability with Logs, Metrics, and Alerts in Scraping Pipelines (Grepsr)](https://www.grepsr.com/blog/observability-web-scraping-pipelines-grepsr/)
- [Career Page Job Scraper — Greenhouse, Lever & Any ATS (Apify)](https://apify.com/scrapepilot/career-page-job-scraper----greenhouse-lever-any-ats)
- [strata-harvest (PyPI)](https://pypi.org/project/strata-harvest/)
- [OpenJobRadar Integrations](https://openjobradar.com/integrations)

---

*Feature research for: ATS-first job sourcing pipeline (job-scout v0.4)*
*Researched: 2026-04-27*

# Pitfalls Research

**Domain:** ATS-first job sourcing for a Claude Code plugin (Python 3.8+, additive CSV schema, hybrid concurrency)
**Researched:** 2026-04-28
**Confidence:** MEDIUM-HIGH (Greenhouse/Lever/SmartRecruiters/Workday docs verified; Ashby rate limits unstated, treated as unknown; concurrency advice cross-checked with urllib3/HTTPX/requests issue trackers)

This research is scoped to v0.4 of `job-scout-plugin`. It builds on the constraints already locked in `PROJECT.md` (trust ATS on 0/error, concurrent with per-provider cap, +1 tier bump for ATS, fuzzy company+title dedupe, hybrid detection, additive schema only) and the fragility patterns documented in `.planning/codebase/CONCERNS.md` (silent zero-result passes, schema/code drift, no tests, board scrapers that decay invisibly).

The five problem areas the user called out — ATS-API querying at scale, slug detection, dedup across two sources, additive CSV migration, and adding concurrent HTTP to a previously synchronous plugin — each have distinct failure modes. They are listed below in roughly the order they will bite during a v0.4 build, then summarized in the phase-mapping table at the bottom.

---

## Critical Pitfalls

### Pitfall 1: "Trust ATS on 0/error" silently zeroes a company out forever

**What goes wrong:**
The locked decision in `PROJECT.md` says: *"If an ATS endpoint returns 0 jobs or errors, treat it as 'no openings, move on' — no Chrome scrape fallback."* This is the right call for milestone honesty, but if a single ATS provider regresses (Greenhouse changes URL format, a Workday tenant moves data centers from `wd3` to `wd5`, a SmartRecruiters slug gets renamed), every company on that provider silently drops to zero hits. The daily report still runs, still produces a number, and looks fine. Two weeks later the user notices A-tier matches have quietly fallen 80% from a specific cluster of companies — and the trend is invisible in any single run.

This is exactly the failure mode `CONCERNS.md` already flags for the existing Pass-2 boards (*"silent zero-result passes look like 'no roles matched' rather than 'scraper broke'"*). The v0.4 architecture inherits the same fragility unless explicitly guarded.

**Why it happens:**
- Public ATS endpoints don't guarantee stability. Workday in particular requires you to *not* assume `wd3` works for all tenants — different data centers (`wd1`, `wd3`, `wd5`) need explicit detection per company.
- Greenhouse returns a 404 silently when a company doesn't (or no longer) uses Greenhouse — the API "skips that company, continues with the rest of the batch. No error is thrown."
- A "0 results" response is indistinguishable from "this company genuinely has no openings today" without historical context.
- `runs.jsonl` exists in v0.4 but the user doesn't read it daily; regressions need to surface in the report itself.

**How to avoid:**
- Persist per-company per-provider hit counts in `runs.jsonl` (already planned). On every run, compute a rolling window (e.g. last 7 runs) per `(company, provider)` and flag any company whose ATS hit rate dropped to 0 after previously being non-zero.
- Surface flagged companies in the report's *"Honest notes"* section as **"ATS regression suspect"** — same pattern `CONCERNS.md` recommends for Pass-2 boards (*"every Pass 2 board should require a non-empty result on at least one of the last 3 runs, and surface a 'board appears broken' warning"*).
- Distinguish three return states in the dispatcher, not two: `OK_WITH_RESULTS`, `OK_ZERO`, `ERROR`. Log them separately in `runs.jsonl` so a Workday 401 or DNS failure doesn't get bucketed as "no openings."
- Add a `last_ats_hit_date` column to the master_targets row when results are non-zero. If a company's last hit is >14 days ago and the company was hitting reliably before, flag it.

**Warning signs:**
- A company that consistently produced 5–20 ATS hits suddenly produces 0 for 3+ runs in a row.
- Total Pass-1 share % (already part of the run summary) drops below 40% for a single run, or trends down across a week.
- A specific provider's aggregate hit count drops to 0 across all companies on the same day (strong signal the provider's API changed, not the companies).
- A Workday company starts returning HTTP 302 → marketing site (tenant moved data centers).

**Phase to address:**
**Observability phase (after dispatcher is in place but before milestone close).** The dispatcher must already write per-provider counts; the regression detection layer reads them. Tracking this in v0.4 is non-negotiable because it's the only thing that makes "trust ATS on 0/error" defensible — without monitoring, the decision converts into "silently lose data and don't notice."

---

### Pitfall 2: ATS slug detection produces silent false positives

**What goes wrong:**
The hybrid detection model (top-30 batch via `/scout-detect`, lazy inline for the rest) needs to map a company name like "Stripe" to a Greenhouse slug `stripe`, a Lever slug `stripe`, an Ashby slug `stripe`, etc. The naive guess (lowercase the company name, strip spaces) succeeds often enough to feel safe — but produces three distinct false-positive modes:

1. **Wrong-company match.** A real Greenhouse board exists for `stripe` but it's not the Stripe you mean. Two unrelated companies named "Acme" both use Greenhouse; the slug guess `acme` returns a board, the dispatcher writes it to `master_targets.csv`, and from then on you scrape someone else's jobs.
2. **Dead board.** A company churned off the ATS but the board still resolves (returns empty `jobs: []`). You write the wrong provider, then "trust 0 on error" silently zeros the company out.
3. **Subdomain wildcard / catch-all.** Some ATS hosts respond 200 to *any* slug under their domain due to CDN catch-alls or tenant-isolation patterns. You cannot distinguish "valid slug, no jobs" from "wildcard 200, fake board."

**Why it happens:**
- Greenhouse explicitly says *"Most companies use their company name in lowercase: airbnb, stripe, figma, anthropic"* but also warns *"this isn't always reliable"* — abbreviations and branded names are common.
- The standard Workday URL is `https://{tenant}.wd{N}.myworkdayjobs.com/{locale}/{site}` — three pieces of variability (tenant, data center number, site), all of which are required to construct a working API call. A guessed tenant is rarely enough.
- Multiple companies share common slugs (`acme`, `apex`, `nova` all have multiple Greenhouse tenants).
- The ATS API endpoints don't expose the legal/display name of the company in a way the dispatcher can validate against — you're trusting the slug-to-company mapping based on a 200 response alone.

**How to avoid:**
- **Two-factor detection.** Don't accept a slug as confirmed unless (a) the API returns at least one job and (b) the returned company name (or first job's URL/branding) loosely matches the input company name (≥85% fuzzy match on name, or domain match between job URL and company's known domain). Reject silent-200 with no jobs as "unconfirmed."
- **Detection requires evidence, not a 200.** Specifically for Workday: detection must capture the full `(tenant, data center, site)` triple, not just the tenant. Hit the `/wday/cxs/{tenant}/{site}/jobs` POST endpoint with an empty facet body and require ≥1 job + a company-name match.
- **Cache the negative result.** If detection fails for a company, write `ats_provider=none` (not empty) so subsequent runs don't re-probe and re-fail. Re-test only on explicit user request via `/scout-detect --refresh`.
- **For ambiguous cases, defer to the user.** If the top-30 detection produces a slug match with confidence <70% (e.g. found a board but the company-name fuzzy score is borderline), write the candidate slug + score to a `<data_dir>/ats_detection_review.csv` file and prompt the user to confirm during `/scout-detect`. Better one minute of human review than three months of scraping the wrong company.
- **Validate against the company's known domain when possible.** If `master_targets.csv` has a `careers_url` or `website` field, prefer slugs whose returned `jobs[0].absolute_url` or apply URL share that domain.

**Warning signs:**
- A company has `ats_provider=greenhouse` and `ats_board_url=https://boards.greenhouse.io/acme` but its job titles consistently look unrelated to the user's known industry/domain.
- Detection succeeded for >95% of top-30 companies on first try (real-world rate is 60–80% — too-clean detection is a sign you're matching wildcards).
- Two different companies in `master_targets.csv` end up with identical `ats_board_url` values (you've collapsed them onto the wrong tenant).

**Phase to address:**
**Detection phase (`/scout-detect` skill).** The two-factor rule must be in the initial implementation — retrofitting it later means re-detecting every company. The `ats_detection_review.csv` deferral mechanism can be added later if false positives are rare in practice, but the two-factor gate (jobs + name match) is non-negotiable in v1.

---

### Pitfall 3: Dedup across ATS + LinkedIn produces under-merging or over-merging — both fail silently

**What goes wrong:**
The locked decision is *"company-slug + normalized-title fuzzy match"* between Pass 1 (ATS) and Pass 2 (LinkedIn keyword). Two opposing failure modes:

1. **Under-merging (duplicates leak through).** "Senior Software Engineer, Distributed Systems" on Stripe's Greenhouse board doesn't fuzzy-match "Sr. SWE — Distributed Systems Team" on LinkedIn → both end up in the report → user sees "two jobs at Stripe" that are actually one. They might apply to both, look careless. At scale, the report's job count is inflated and A-tier slot is wasted on a duplicate.
2. **Over-merging (real jobs collapsed).** "Software Engineer" on the Greenhouse board fuzzy-matches "Software Engineer II" on LinkedIn → dedup collapses two distinct levels into one row → user loses the LinkedIn signal (location, posting date, connection count) for the L2 role.

The research consensus is brutally consistent: at 75% similarity threshold you over-merge; at 90% you under-merge; the only safe automated band is >95%, with everything 70–95% requiring review. v0.4 has no review mechanism — every dedup decision is automatic.

**Why it happens:**
- Job titles are short strings with high overlap. "Senior Engineer" appears on hundreds of postings; the Levenshtein distance between two unrelated postings can be lower than between two duplicates of the same posting written differently.
- Company-slug matching is even harder if Pass 2 doesn't have a clean slug — LinkedIn returns "Stripe, Inc." and the ATS returns `stripe`, requiring a normalization step that itself can fail.
- Title prefixes/suffixes vary wildly: "II", "Sr.", "L4", "Staff", " - Distributed Systems", " (Remote)". A normalizer that strips them aggressively over-merges; one that keeps them all under-merges.
- The order of operations matters: Pass 1 anchors, Pass 2 dedupes against Pass 1. If Pass 2 produces a slightly better record (more accurate location, salary, posting date), that information is dropped in favor of the Pass 1 row.

**How to avoid:**
- **Use a tiered confidence band, not a single threshold.** Auto-merge at ≥95% (company exact match + title ≥95% normalized similarity). Auto-keep-both at <70%. Anything in 70–95% goes to a `dedup_review` collection that gets surfaced in the run summary as *"N possible duplicates flagged — review tomorrow"* without blocking the run.
- **Two-key dedup, not one.** Compute both a "loose" key (company-slug + first-3-tokens-of-title) and a "tight" key (company-slug + full normalized title). Auto-merge only when *both* keys agree. If only the loose key matches, it's a "possible duplicate" — surface it, don't merge.
- **Normalize titles deliberately and document the normalizer.** Single function in `scripts/dedup.py` (matches the convention of single-source-of-truth in `schema.py`). At minimum: lowercase, strip punctuation, collapse whitespace, remove common parentheticals like `(Remote)` and `(Hybrid)`, but keep level markers (`II`, `Sr`, `Staff`). Document in a comment what's stripped and why — this is exactly the kind of code that drifts silently when the next bug fix tweaks one rule.
- **When merging, take the union of fields, not the Pass-1 record.** If LinkedIn has `connection_count=3` and ATS has `connection_count=null`, the merged row gets 3. If both have a salary range, take the wider one and note the source.
- **Log every merge decision to `runs.jsonl`.** `{"action": "merge", "ats_id": "...", "linkedin_id": "...", "title_similarity": 0.93, "company_match": "exact"}`. This is what makes "under/over-merge" detectable retroactively when the user spots a wrong call.

**Warning signs:**
- A daily report contains zero dedup events when both Pass 1 and Pass 2 found jobs at the same company (suspicious — almost always something matched).
- A report contains very many dedup events (>30% of Pass-2 hits) — the threshold is too aggressive.
- The user reports "I applied to two of these and they're the same job" or "you missed the L4 version of this role."
- `runs.jsonl` shows the same `(company, title)` pair being re-deduped run after run — Pass 2 keeps re-finding what Pass 1 found yesterday and failing to dedup against the persistent tracker (only against today's Pass 1).

**Phase to address:**
**Dedup phase (after both Pass 1 and Pass 2 produce records, before tracker append).** Build the tiered confidence band and the two-key dedup before the first end-to-end test. Log decisions from day one — without the log, you cannot tune the thresholds in week 2.

---

### Pitfall 4: Schema migration breaks a user file that's been hand-edited

**What goes wrong:**
v0.4 adds `ats_provider` and `ats_board_url` to `MASTER_TARGETS_COLUMNS`. The constraint in `PROJECT.md` is explicit: *"schema additions must be additive (new optional columns, no column drops or renames in v0.4)"* and *"User data files must remain readable by older `/scout-run` invocations during the migration."*

`scripts/validate_data.py` already auto-migrates `master_targets.csv` on every run by adding missing columns (per `CONCERNS.md`: *"silently mutates user data on every run without a regression test"*). Three real failure modes:

1. **User-added columns get re-ordered or destroyed.** The convention from `validate_data.py:88` is *"we never drop user columns"* — but the v3→v4 migration must respect this. If the new code drops user columns or moves them, a user who tracks their own notes column (`my_notes`, `recruiter_email`) silently loses it.
2. **Column-rename smuggled in as "additive."** A maintainer notices `linkedin_connection_count` is misnamed and "fixes" it to `connection_count` in the migration. Old `/scout-run` code reads from `linkedin_connection_count`, gets KeyError, crashes mid-run, leaves a half-written tracker (already a known fragility — `CONCERNS.md`: *"a run that errors mid-Step 6 leaves a half-written report and a fully-updated tracker — out of sync, undetectable"*).
3. **Schema version not bumped.** `CONCERNS.md` documents the existing rule: *"DO NOT add columns without bumping `MASTER_TARGETS_VERSION` and adding a migration in `validate_data.py`."* If the v0.4 PR adds the columns to `MASTER_TARGETS_COLUMNS` but forgets `MASTER_TARGETS_VERSION = 4` and a corresponding migration branch in `validate_data.py`, every existing user file silently runs through the v3 codepath and never gets the new columns.
4. **CSV row-shape mismatch.** Adding two columns means every row in `master_targets.csv` now has two more fields. If pandas reads it with `header=0` it auto-handles this — but any code that reads the CSV with stdlib `csv` or assumes a row length silently misaligns.

**Why it happens:**
- The single-source-of-truth contract in `schema.py` is enforced by convention, not by lint. New columns can be added in three places (`schema.py`, `validate_data.py` migration, doc strings) and the codebase has already shown it drifts (the `pipeline_tier` removal in v0.3.2 left dangling references in three docs and one script).
- "Additive" feels self-enforcing but isn't — a rename can be disguised as "drop old + add new" in a single migration.
- v0.4 has no tests, so the migration path is exercised exactly once (during dev) before shipping.

**How to avoid:**
- **Bump `MASTER_TARGETS_VERSION` to 4** the same commit that adds the columns. Make the migration in `validate_data.py` explicit: *"if version == 3, add `ats_provider` and `ats_board_url` columns at the end with empty string defaults."* Use the `empty_master_target_row()` factory pattern from `schema.py:109` so missing-field handling is consistent.
- **Add a synthetic-fixture smoke test** even without a full test suite. `tests/fixtures/master_targets_v3.csv` checked in; a simple script in `tests/test_migration.py` that runs `validate_data.py` against it, asserts no error, asserts `ats_provider` column was added, asserts no rows lost, asserts user columns preserved. Five lines, catches 90% of migration regressions. (`CONCERNS.md` already calls this out as the highest-leverage missing test.)
- **Old `/scout-run` reading new files: enforce read-but-don't-write rule.** Old code reads new columns as extras (pandas does this naturally), writes back without them — but the v0.4 `validate_data.py` re-adds them on next run. Confirm this round-trip works with a fixture.
- **Don't rename in v0.4.** If a column name is wrong, defer the rename to v0.5 with a deprecation cycle. v0.4's promise is *additive only*; honor it absolutely.
- **Validate column count on read.** The dispatcher should assert `len(row) >= len(MASTER_TARGETS_COLUMNS)` after read — fail loudly if a stale CSV has too few columns and migration didn't run.

**Warning signs:**
- A user runs `/scout-run` on a v3 file and the dispatcher KeyErrors on `ats_provider`.
- `master_targets.csv` ends up with duplicate columns (`ats_provider`, `ats_provider.1`) — pandas auto-suffix on read, indicates the migration ran on an already-migrated file.
- User-added columns end up in a different order, or with different content, after a run.
- `MASTER_TARGETS_VERSION` is still `3` after the v0.4 ship.

**Phase to address:**
**Schema phase (Phase 1, before any ATS code is written).** This is a foundational change — every other phase assumes the new columns exist. Ship the schema bump + migration + fixture test as a standalone PR before the dispatcher work begins, so the rest of v0.4 can be built against the new shape without coupling.

---

### Pitfall 5: Concurrent HTTP introduces shared-state bugs the synchronous codebase has never had

**What goes wrong:**
The plugin's Python code today is single-threaded, single-process, deterministic. v0.4 adds *"ATS APIs called concurrently with a per-provider concurrency cap."* Adding concurrency to a previously-synchronous codebase introduces a class of bugs the codebase has never had to defend against:

1. **Shared session/state across threads.** `requests.Session` is documented as not thread-safe; sharing one across threads causes intermittent connection errors, reused cookies bleeding between requests, or worse — silent body corruption. The same is true for `urllib3.PoolManager` instances at high host counts.
2. **Connection pool exhaustion.** HTTPX defaults to 10 keepalive + 100 max_connections; hitting the same provider beyond this blocks. urllib3's `block=True` will wait silently — runs that should take 30s take 5 minutes with no error.
3. **Per-provider cap implemented globally.** The dispatcher caps "10 concurrent" but doesn't cap "10 concurrent *to Greenhouse*" — so a run that hits 30 Greenhouse companies + 5 Ashby companies fires 35 simultaneous Greenhouse requests, gets rate-limited or banned, and the per-provider cap does nothing.
4. **Error swallowing in `as_completed`.** A worker's exception is captured in the future; if the dispatcher iterates `as_completed(futures)` without explicitly calling `future.result()` or wrapping it, exceptions are silently dropped. The run "succeeds" with N-K results and no log.
5. **Order-dependent state writes.** Two workers finish near-simultaneously, both call `tracker_utils.append_rows`, both rewrite the xlsx (`CONCERNS.md`: *"`_write_tracker` rebuilds the entire xlsx file on every append"*) — last write wins, first worker's rows lost.
6. **Tests-don't-exist multiplier.** The codebase has zero tests today (`CONCERNS.md`). Concurrency bugs are notoriously test-resistant; without a deliberate harness, regressions ship.

**Why it happens:**
- The codebase has 4 years of "synchronous Python is fine, just call functions." Engineers writing v0.4 will naturally write the same shape and add a `ThreadPoolExecutor.map(fn, urls)` at the top, missing that `fn` mutates a module-level session.
- "Per-provider cap" sounds simple but requires a per-provider semaphore, not a single executor.
- urllib/httpx/requests all have different concurrency models and gotchas; the team will likely use whichever they grab first.
- `tracker_utils._write_tracker` was designed assuming sequential callers; nothing in the code says "don't call this from threads."

**How to avoid:**
- **Pick one HTTP library and one concurrency model. Document the choice.** Recommendation: stdlib `urllib.request` + `concurrent.futures.ThreadPoolExecutor` if dependency-aversion wins (matches the "Python 3.8+ stdlib + existing deps" constraint), or `httpx.AsyncClient` + `asyncio.gather` if you want HTTP/2 and structured concurrency (one new dep, cleaner code, better timeout semantics). **Do not mix.**
- **Per-provider concurrency cap = per-provider semaphore.** Implement explicitly: `provider_semaphores = {"greenhouse": Semaphore(10), "lever": Semaphore(10), ...}`. Each worker acquires the right semaphore before hitting its provider's API. A single global ThreadPoolExecutor cap does *not* satisfy this requirement.
- **One session per provider, not per thread, not global.** Document this in a module-level comment. If using `requests`, create the session inside the worker context (or use `threading.local()`); if using `httpx`, the `Client`/`AsyncClient` objects are designed for shared use — but verify against the chosen version's docs.
- **All worker exceptions must be surfaced.** Wrap every worker call: collect `(provider, company, result_or_exception)` tuples; iterate and log every exception explicitly. Never let `future.result()` raise into the dispatcher loop without logging the (provider, company) context.
- **Serialize the tracker write.** All concurrent work produces an in-memory list of new rows; the single tracker append happens in the main thread after `gather`/`as_completed` completes. Do NOT call `tracker_utils.append_rows` from worker threads.
- **Add a kill-switch.** Run-level config: `ats_concurrency_cap` (default 10) and `ats_concurrency_disabled` (default false). If concurrency causes problems in prod, the user can flip the flag and fall back to sequential without a code change.
- **Honor `Retry-After`.** SmartRecruiters returns 429 with a `Retry-After` header; Greenhouse's authenticated APIs return rate-limit headers. The dispatcher should respect these, not just retry blindly. Respect `Retry-After` even on the public Job Board API in case it changes.
- **Set explicit timeouts on every request.** Default behavior of `urllib.request` is to hang forever. Set both connect and read timeouts (e.g. 10s connect, 20s read). Without this, a single slow Workday tenant hangs the whole run past the 5-minute budget.

**Warning signs:**
- Run wall-clock time is wildly variable (3 min, 7 min, 4 min) for the same number of companies — sign of contention or pool exhaustion.
- Sporadic `KeyError`, `IndexError`, or "connection reset" in `run_log.json` that don't reproduce when re-run sequentially.
- Tracker xlsx has missing rows after a run that the report claims succeeded.
- Two consecutive runs produce different total job counts for the same `master_targets.csv` and no listings changed.
- Memory use spikes mid-run (sign of accumulated session/pool objects).

**Phase to address:**
**Dispatcher phase (Phase 2, after schema is done).** Build the dispatcher as a standalone module (`scripts/ats_dispatcher.py`) with a clear contract: *"input: list of (company, provider, board_url); output: list of job records or per-company errors."* Test it in isolation against synthetic providers (a stub HTTP server returning known responses) before wiring it into `/scout-run`. The kill-switch should land in the same PR — not retrofitted later when prod misbehaves.

---

### Pitfall 6: Workday's POST-with-empty-body API misclassified as "needs auth" or "broken"

**What goes wrong:**
Workday is the most failure-prone of the five providers because it's not really "one API" — it's a per-tenant, per-data-center deployment with a non-trivial endpoint shape. The endpoint is `POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` with a JSON body containing `appliedFacets`, `limit`, `offset`, `searchText` — even when empty. A naive implementation will:
- Try GET → 405 Method Not Allowed → conclude "Workday needs auth, skip."
- Try POST without body → 400 Bad Request → conclude "Workday is broken, skip."
- Hardcode `wd5` for all tenants → fail for the 60% of companies on `wd1` or `wd3`.
- Encounter a tenant with CSRF/session-token requirements (some Workday deployments wrap the public endpoint behind a token-issuing handshake) → fail silently.

`PROJECT.md` already acknowledges the last case in Out of Scope: *"if a tenant requires session/CSRF tokens beyond the public POST endpoint, that company falls through to Pass 2 in v0.4."* That's a fine deferral — but you have to *detect* the CSRF case, not silently bucket it as "no openings."

**Why it happens:**
- Workday is the only provider in the v0.4 list that uses POST for a "public read" endpoint.
- The data-center number is part of the URL path — it's not a redirect; you can't just hit the apex domain.
- Documentation for the public CXS endpoint is largely community-maintained (Apify, GitHub crawlers) — no official Workday public-API docs exist for unauthenticated access.

**How to avoid:**
- **Detection captures `(tenant, data_center, site)` as three fields**, all required, all written to `master_targets.csv` (the `ats_board_url` field stores the full base URL; the dispatcher parses it).
- **Dispatcher branch for Workday is its own module function** that constructs the POST body explicitly. Document the body shape in a constant: `WORKDAY_EMPTY_FACETS = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}`.
- **Distinguish failure modes in the response.** A 400 means "your body is malformed" (your bug); a 401/403 means "this tenant requires auth" (defer per PROJECT.md); a 200 with empty `jobPostings` means "no openings"; a 302/200 to a marketing site means "tenant moved or shut down their Workday." Each gets its own error code in `runs.jsonl`.
- **Detect CSRF/session requirement early.** If first POST returns 403 with a body mentioning "session" or "csrf" or returns a `Set-Cookie` header asking for re-submit, mark the company as `ats_provider=workday-auth-required` and route to Pass 2 — explicitly, not silently.

**Warning signs:**
- Workday companies all return 0 results on first run after detection (sign that detection captured the URL but didn't validate the POST endpoint actually returns jobs).
- `run_log.json` shows uniform `400` responses from Workday tenants (POST body is malformed).
- Workday share of total ATS hits is suspiciously low (<10%) given Workday's market share among large enterprises.

**Phase to address:**
**Dispatcher phase, Workday provider module.** Treat Workday as the highest-risk provider; write its provider module last and test it against 3+ known tenants (one per data center: pick public companies known to use `wd1`, `wd3`, `wd5`).

---

### Pitfall 7: ATS API "schema drift" silently degrades job-record quality

**What goes wrong:**
Each ATS returns a different JSON shape for "a job." Greenhouse returns `title`, `location: {name: "..."}`, `content` (HTML JD); Lever returns `text`, `categories: {location: "..."}`, `descriptionPlain`; Ashby returns `title`, `locationName`, `descriptionHtml`; SmartRecruiters returns `name`, `location: {city, region, country}`, `jobAd: {sections: {jobDescription: {text}}}`; Workday returns `title`, `locationsText`, `bulletFields` + a separate detail call for the JD body.

The dispatcher must normalize all five into a common record shape (the row that goes into `tracker.xlsx`). Failure modes:
1. **Field renamed by provider.** Lever renames `descriptionPlain` to `descriptionText` in a quiet API update; the parser keys on the old name; `description` field in the record is empty for all Lever jobs from that day forward. Scoring degrades silently because the JD body it relies on is empty.
2. **Field shape changed.** SmartRecruiters changes `location: {city: "..."}` to `locations: [{city: "..."}]` (singular → plural array). The parser pulls `location` and gets `None`. Every SmartRecruiters job ends up with no location data; user can't filter by remote/onsite.
3. **HTML in plain-text field.** A provider starts including HTML tags in a field that was previously plain text. The scoring engine treats the HTML as content and matches keywords against tag names (`div`, `span`).
4. **Compensation field added/removed.** Lever and Ashby occasionally add salary fields; if the dispatcher doesn't extract them, the +1 tier bump for "structured data signal" is undermined because comp data goes missing on the very jobs that have it.

**Why it happens:**
- These are public APIs without versioning headers; providers ship changes whenever, with no deprecation period.
- The dispatcher's normalization layer is per-provider; a change in one provider's shape only breaks that provider — easy to miss in a unified run.
- Empty fields don't raise errors — the record gets written with `description=""` and the run looks successful.

**How to avoid:**
- **Normalize via per-provider mapper functions, each with a contract test.** Each mapper takes provider JSON and returns a `{title, company, location, description, url, posted_date, comp}` dict. Test each mapper against a checked-in fixture (one real JSON response from each provider, captured during initial dev).
- **Validate the normalized record before scoring.** Required fields: `title` (non-empty), `company` (non-empty), `url` (non-empty). If `description` is empty and the source is ATS, log a warning and emit a metric — this is a quality signal the dispatcher should track.
- **Track per-provider field-completion rate.** In `runs.jsonl`: `{"provider": "lever", "jobs": 47, "with_description": 47, "with_comp": 12, "with_location": 47}`. A sudden drop in `with_description` from 100% to 0% is a schema drift signal.
- **Don't let the model see empty-description records as "low signal."** The scoring rubric should explicitly account for missing fields rather than scoring them as if "no relevant keywords means no fit." Otherwise a Lever schema change tanks the tier of every Lever job overnight.

**Warning signs:**
- A specific provider's average score drops 30% in a week with no obvious reason.
- `with_description` rate drops sharply for one provider.
- Records show JD bodies containing visible HTML tags.
- Comp data disappears for one provider's jobs.

**Phase to address:**
**Dispatcher phase, normalization layer.** Build the per-provider mappers with fixture tests in the same PR as the dispatcher. Field-completion telemetry rides on `runs.jsonl`, which the observability phase reads.

---

### Pitfall 8: Public ATS APIs include stale, regional, and expired postings without flagging them

**What goes wrong:**
Public ATS Job Board endpoints return *all* postings the company has marked "public" — which is not the same as "currently hiring":
- Greenhouse boards include postings that are still public but already closed internally; they have a `status` or `published` field but the public board doesn't reliably surface "we already filled this."
- Lever returns "evergreen" postings (always-open requisitions) alongside specific open roles — these flood your results with noise like "Talent Network — General Application."
- Workday tenants include regional duplicates: the same role posted for US, UK, EU, APAC, often with near-identical titles. The dispatcher will see five jobs, the user has one role.
- SmartRecruiters returns jobs in `releasedDate` order; old roles posted 6+ months ago still appear with no warning.

**Why it happens:**
- Public APIs are designed for company career-page rendering, not for third-party job aggregation. Filtering "freshness" or "actually hiring" is the company's responsibility, not the API's.
- "Evergreen" postings are a recruiting feature, not a bug — but they're not what the user is looking for in a daily scan.
- Region-multiplied postings are a Workday norm; companies create one requisition per legal entity even when the role is global-remote.

**How to avoid:**
- **Filter on `posted_date` / `created_at`** in the dispatcher. Default cutoff: 60 days. Configurable via `<data_dir>/config.json`. Any role older than the cutoff is dropped before scoring.
- **Detect and collapse regional duplicates pre-dedup.** Within a single ATS provider's response for a single company, if N jobs share the same normalized title and the same posted_date, collapse to one record with `locations: [...]` listing all variants. This is *not* the cross-source dedup (that's Pitfall 3) — this is intra-source noise reduction.
- **Detect "evergreen" postings via title/URL patterns.** Skip titles matching `r"(general|talent network|future opportunities|expression of interest|always hiring)"i`. Keep a configurable allow/block list in `references/search-config.md`.
- **Trust an ATS posting more than a LinkedIn one ONLY if it's recently posted.** The +1 tier bump in `PROJECT.md` *"warm-path + structured-data signal"* should be conditional: only bump if `posted_date` is within the last 30 days. A 6-month-old ATS posting is not a stronger signal than a 1-day-old LinkedIn posting.

**Warning signs:**
- The same role appears in tomorrow's report and yesterday's report with a different posted_date (sign of evergreen postings).
- Workday companies dominate the report by raw count (region duplication).
- A-tier list contains roles the user already applied to weeks ago and got rejected on (stale postings the company hasn't taken down).

**Phase to address:**
**Dispatcher phase, filtering layer.** Filtering happens after normalization, before dedup. The cutoff and pattern-blocklist live in `config.json` so the user can tune without code changes.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode `wd5` for all Workday tenants | Skips the data-center detection complexity | Silently misses 60–80% of Workday companies; appears as a coverage gap that's hard to attribute | Never — write detection upfront |
| Single global concurrency cap (no per-provider semaphores) | Simpler dispatcher code | Over-pummels one provider, under-utilizes others; risks IP block; violates locked decision in PROJECT.md | Never — per-provider is in the locked decisions |
| One unified mapper for all five providers | Avoids 5x boilerplate | First schema change breaks the unified parser, all five providers go dark together | Never — keep per-provider mappers |
| Skip the schema migration test fixture | Saves 30 min in v0.4 | Replays the v0.3.2 KeyError shipping incident; user data corruption is unrecoverable from the user's side | Never — this is the single highest-leverage missing test (per CONCERNS.md) |
| Use `requests` without explicit session-per-thread | "Just works" in single-threaded testing | Intermittent prod failures that don't reproduce; takes days to diagnose | Never — pick one model and document |
| Single fuzzy-match threshold for dedup (e.g. 85%) | One number to tune | Both under-merges and over-merges depending on the day; no way to recover lost records | Acceptable for v0.4 *only if* the band is conservative (≥95% auto, log everything in 70–95%) |
| Skip the "ATS regression suspect" warning in the report | Saves a UI surface in the report | "Trust ATS on 0/error" silently zeroes out clusters of companies, defeats the milestone reliability bar | Never — required to make the locked decision defensible |
| Reuse `tracker_utils._write_tracker` from worker threads | Avoids serializing the tracker write | xlsx file corruption + last-write-wins data loss | Never — serialize in main thread |
| Defer Workday auth-required detection ("just skip workday-auth tenants silently") | Faster to ship | Companies behind CSRF Workday silently fall through; user has no idea coverage is incomplete | Acceptable *only with* a logged "auth-required, deferred to Pass 2" entry in `runs.jsonl` |
| Inline ATS provider URLs/patterns in the SKILL prompt instead of a Python constant | Easy editing | Same drift problem as `pipeline_tier` — multiple sources of truth, model resolves them stochastically | Never — provider URL patterns live in `scripts/ats_dispatcher.py` constants only |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Greenhouse Job Board API | Treating 404 as an error | 404 = "not on Greenhouse, try next provider" — expected during detection, not a failure |
| Lever Postings API | Assuming `descriptionPlain` is always present | It's optional; use `descriptionPlain` if present, fall back to stripping HTML from `description` |
| Lever Postings API | Including custom-question fields from posting response | They're always blank — use the dedicated questions endpoint or skip; don't store empty noise |
| Workday CXS endpoint | GET on `/wday/cxs/.../jobs` | Always POST with JSON body containing empty `appliedFacets`, `limit`, `offset`, `searchText` |
| Workday CXS endpoint | Hardcoding `wd5` data center | Detect per tenant; capture full `(tenant, dataCenter, site)` triple |
| Workday CXS endpoint | Not handling 401/403 with CSRF requirement | Detect, mark `workday-auth-required`, defer to Pass 2 (per PROJECT.md), log explicitly |
| SmartRecruiters Posting API | Assuming public access on every endpoint | Listing is public; POST application is auth'd; respect `Retry-After` on 429 (300 req/min/client cap) |
| SmartRecruiters Posting API | Pagination via `cursor` instead of `offset/limit` | SmartRecruiters uses `offset`/`limit`/`totalFound` — different from Ashby |
| Ashby Public Job Posting API | Single-page assumption | Most list endpoints are paginated with `cursor` + `nextCursor`; check `moreDataAvailable` |
| Ashby Public Job Posting API | Assuming no rate limit because docs don't say | Rate limits are unstated — implement defensive backoff anyway |
| All providers | Treating "0 jobs returned" as success | Distinguish `OK_WITH_RESULTS` vs `OK_ZERO`; track regression on the latter |
| All providers | Reusing one `requests.Session` across threads | Not thread-safe; one session per worker, or use `httpx.AsyncClient` (designed for shared use) |
| Cross-provider detection | Trusting a 200 response as proof the slug belongs to the right company | Two-factor: 200 + ≥1 job + name fuzzy-match ≥85% with input company |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| No request timeout | Run hangs at 5+ minutes; same target reproducibly slow | Explicit 10s connect / 20s read timeouts on every HTTP call | First slow Workday tenant or DNS hiccup |
| Concurrency cap higher than provider's rate limit | 429 errors, IP throttling, gradually-degrading hit rates | Per-provider semaphore sized below documented limits (SmartRecruiters: 300/min/client; others undocumented — start at 10 concurrent) | Within 1–2 weeks of daily runs at scale |
| Connection pool exhaustion (urllib3 default `maxsize=10`) | Workers block silently waiting for a free connection; wall-clock balloons | Configure pool size to match concurrency cap; monitor for "pool full" warnings | At ~20+ concurrent requests to the same host |
| Sequential JD body fetches when ATS provides them inline | Wall-clock dominated by N sequential HTTP calls | All ATS providers include the JD body in the listing response — don't make a second call per job | Day one — already a violation of v0.4's "ATS JSON description used directly" goal |
| Re-detection on every run instead of caching | `/scout-run` does N detection calls before any actual sourcing | Detection writes to `master_targets.csv` once; only re-detect on user request or after a long gap | After the second daily run on the same target list |
| Tracker rebuild from N concurrent threads | xlsx write contention; lost rows | Single tracker write in main thread after gather completes | First run with concurrency enabled |
| Reading every `runs.jsonl` line for trend detection on every run | `/scout-run` startup gets slower over weeks | Cap the trend-detection window (e.g. tail last 30 entries); rotate the file at 10MB | After ~6 months of daily runs |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging full ATS response bodies (including PII like recruiter names, internal IDs) into `run_log.json` | `run_log.json` lives under `~/Documents/JobSearch/` with default umask (644 per CONCERNS.md); third-party PII leaks if dir is synced to iCloud/Dropbox | Log structured fields (job count, provider, status code, timing) — never the raw response body |
| Storing API keys for any future authenticated ATS calls in `config.json` | `config.json` is plaintext, often shared in bug reports (per CONCERNS.md) | If/when v0.5+ adds authenticated endpoints, store secrets in `~/.job-scout/secrets.json` with `chmod 600` and never log them |
| Trusting redirected URLs from ATS responses without validation | An ATS posting could redirect to a phishing/malware site if the provider is compromised; the user clicks "Apply" from the report and lands there | Validate the apply-URL hostname against an allowlist of known ATS apply domains; flag unknown hostnames in the report |
| Sending the user's identifying info (resume content, candidate profile) in any ATS query parameter | Public APIs log query strings; user PII in provider's logs | All ATS calls are read-only with no user-identifying parameters; resume content stays local |
| Caching ATS responses to disk including PII (candidate-facing text the company wrote) | Less a security mistake than a quiet data accumulation issue | Don't persist raw responses; persist normalized records only |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Hiding the source tag on listings | User can't tell why a B-tier got promoted, can't decide whether to trust a borderline call | Already in PROJECT.md (`source=ats|linkedin`) — make it visible in the report row, not just metadata |
| Not surfacing the Pass-1 share % prominently | User can't see at a glance whether v0.4 is meeting its reliability goal | Already in PROJECT.md (run summary block) — put it at the *top* of the report, not the bottom |
| Silent fallback when detection fails | User keeps "running the scout" without knowing 8 of their top-30 companies are detection-failed | Surface "8 companies undetected — run `/scout-detect --refresh` or add `ats_provider` manually" in the report's *Honest notes* |
| Re-suggesting jobs the user has already applied to or marked dead | Erodes trust in the report | Existing tracker dedup handles this, but verify the v0.4 ATS path also reads the tracker for "already-seen" filter, not just within-run dedup |
| Not explaining the +1 ATS tier bump in the report | A user seeing an A-tier listing they expect to be B can't tell if it's because of comp, fit, or the source bump | Annotate the score breakdown: `score: 87 (base 82, +5 connection, +1 ATS warm path)` |
| Verbose runs.jsonl with no tooling to read it | The data is captured but invisible; user can't answer "have we been getting fewer matches?" | Defer formal `/scout-stats` to v0.5 (per CONCERNS.md missing-feature list), but at minimum print a 7-day rolling summary at the end of each `/scout-run` |
| Treating the v0.4 milestone as "ATS works in dev" without verifying the locked ≥60% Pass-1 share threshold | Ship a milestone that doesn't actually meet its bar | Explicit verification step in the close-milestone phase: average Pass-1 share over last 5 runs ≥60% |

## "Looks Done But Isn't" Checklist

- [ ] **Schema migration:** Often missing the `MASTER_TARGETS_VERSION = 4` bump and the v3→v4 branch in `validate_data.py` — verify by checking out a v3 fixture file and running `validate_data.py` against it; the file must gain `ats_provider` and `ats_board_url` columns and lose nothing.
- [ ] **ATS dispatcher:** Often missing per-provider semaphores (single global cap masquerading as per-provider) — verify by running with a contrived target list of 30 Greenhouse + 1 Lever + 1 Ashby; assert no more than 10 simultaneous Greenhouse connections.
- [ ] **Workday support:** Often missing data-center detection (hardcoded `wd5`) — verify against three known tenants on `wd1`, `wd3`, `wd5`; all three must return jobs.
- [ ] **Slug detection:** Often missing the two-factor gate (200 + name match) — verify by injecting a "wrong company with same slug" case (e.g. point detection at a slug known to belong to a different company) and confirm detection rejects it.
- [ ] **Dedup:** Often missing the tiered confidence band (single threshold) — verify by injecting a known under-merge case ("Sr. SWE" vs "Senior Software Engineer") and a known over-merge case ("Engineer" vs "Engineer II") and confirming both go to the review band, not auto-decided.
- [ ] **Concurrency:** Often missing explicit timeouts on every request — verify with `grep -r "timeout=" scripts/ats_*.py` and confirm every HTTP call sets one.
- [ ] **Concurrency:** Often missing serialized tracker writes — verify by running a high-concurrency test and confirming the tracker xlsx contains all expected rows (no last-write-wins loss).
- [ ] **Observability:** Often missing the per-(company, provider) hit-history that makes "ATS regression suspect" detection possible — verify `runs.jsonl` contains per-company counts (not just aggregates).
- [ ] **Source tagging:** Often missing the visible-in-report source tag (data captured but not rendered) — verify a sample report contains `source=ats:greenhouse` or similar on every row.
- [ ] **Pass-1 share metric:** Often computed but not surfaced — verify the run summary block at end of `/scout-run` includes the share %.
- [ ] **Field-completion telemetry per provider:** Often missing — verify `runs.jsonl` contains `with_description` / `with_comp` / `with_location` rates per provider for schema-drift detection.
- [ ] **CSRF/auth-required Workday tenants:** Often silently skipped — verify a tenant known to require auth shows up in `runs.jsonl` as `workday-auth-required`, not as `0 results`.
- [ ] **Old `/scout-run` against new CSV:** Often untested round-trip — verify v0.3 code can read a v4 CSV without crashing (extra columns are tolerated as ignored).
- [ ] **Marketing-page scraping deletion:** Often "soft-deleted" (commented out, kept around) instead of actually removed — verify with `grep -r "career_page" skills/ scripts/` and confirm zero matches for the old code path.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| ATS slug detection wrote wrong slug to master_targets.csv | LOW | Manually edit `ats_provider`/`ats_board_url` cells in CSV; re-run `/scout-detect <company>` to verify; consider tightening detection threshold |
| Schema migration corrupted master_targets.csv | HIGH | If user has backup or git-tracked file, restore. Otherwise: rebuild from `consolidate_targets.py` against original data sources (Connections.csv, Pipeline.csv). User loses any hand-edited row data not in source files. |
| Concurrency caused tracker xlsx corruption | MEDIUM | xlsx rebuild from `new_rows.json` files in `<data_dir>/daily/*/`; loses any user manual edits to the xlsx. `tracker_utils.rebuild` exists for this — verify it's tested before relying on it. |
| Trust-ATS-on-0-error silently zeroed companies for weeks | MEDIUM | Compare current `runs.jsonl` per-company hits against historical; identify companies with sudden drops; manually re-validate those companies' ATS slugs and re-run detection |
| Over-merging dropped real listings | HIGH (data lost) | Cannot recover the dropped listing from current run. Mitigation: start logging dedup decisions immediately so future merges can be reverted; re-run Pass 2 separately to recapture LinkedIn versions |
| Under-merging produced duplicate report entries | LOW | User sees two rows for one job; flags one as `Dead`; tracker dedup handles next time. Tighten threshold for next run. |
| Workday data-center moved on a tenant (wd3 → wd5) | LOW | Re-run `/scout-detect <company>`; the URL update in master_targets.csv fixes future runs |
| Provider schema drift broke field extraction (e.g. Lever rename) | MEDIUM | Per-provider mapper isolation means only one provider is affected. Update mapper, add fixture for new shape, re-deploy. Field-completion telemetry tells you when to look. |

## Pitfall-to-Phase Mapping

The roadmap should be structured around these phases, in order. Each phase prevents specific pitfalls; verification is how you know the phase landed.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Schema migration breaks user file (Pitfall 4) | **Phase 1: Schema** | Bump `MASTER_TARGETS_VERSION = 4`; v3 fixture migrates without error or column loss; old `/scout-run` reads v4 CSV without crash |
| Concurrent HTTP shared-state bugs (Pitfall 5) | **Phase 2: Dispatcher** | Per-provider semaphores test (30 GH + 1 Lever + 1 Ashby never exceeds GH cap); explicit timeouts on every call; tracker writes serialized; kill-switch flag works |
| Workday POST-with-empty-body misclassification (Pitfall 6) | **Phase 2: Dispatcher (Workday module)** | Three known tenants on different data centers all return jobs; CSRF/auth-required tenant logged explicitly, not silently zeroed |
| ATS schema drift / field rename (Pitfall 7) | **Phase 2: Dispatcher (normalization)** | Per-provider mapper fixture tests pass; field-completion telemetry in `runs.jsonl` |
| ATS slug detection false positives (Pitfall 2) | **Phase 3: Detection (`/scout-detect`)** | Two-factor gate (200 + ≥1 job + name match ≥85%); known-collision case rejects correctly; review CSV for borderline matches |
| Stale / regional / evergreen postings (Pitfall 8) | **Phase 4: Filtering** | `posted_date` filter active; intra-source regional collapse runs; evergreen pattern blocklist applied; conditional ATS tier bump (only if recent) |
| Cross-source dedup over/under-merging (Pitfall 3) | **Phase 5: Dedup** | Tiered confidence band (≥95% auto, 70–95% review band, <70% keep both); two-key match (loose + tight); every dedup decision logged to `runs.jsonl` |
| Trust-ATS-on-0/error silent zero-out (Pitfall 1) | **Phase 6: Observability** | Per-(company, provider) hit history in `runs.jsonl`; "ATS regression suspect" warnings in report's *Honest notes*; three-state error logging (OK_WITH_RESULTS / OK_ZERO / ERROR); Pass-1 share % at top of report |
| Old `/scout-run` against new CSV breakage (Pitfall 4) | **Phase 1: Schema (verification)** | Round-trip test: v0.3 code reads v4 CSV, writes back, v0.4 code re-reads without data loss |
| Marketing-page scraping not actually deleted | **Phase 7: Cleanup** | `grep -r` confirms zero references to old career-page scraping in `skills/` and `scripts/` |
| Pass-1 share <60% threshold not actually verified | **Phase 8: Milestone close** | 5-run rolling average of Pass-1 share ≥60% before declaring v0.4 complete |

---

## Sources

**ATS API specifications:**
- [Greenhouse Job Board API](https://developers.greenhouse.io/job-board.html) — confirms public, unauthenticated, cached, no rate limit on Job Board API; rate-limited Harvest API is separate
- [Greenhouse API overview – Greenhouse Support](https://support.greenhouse.io/hc/en-us/articles/10568627186203-Greenhouse-API-overview) — 404 behavior on missing slugs
- [Lever Postings API](https://github.com/lever/postings-api) — read-only public, custom-questions blank-on-list quirk, 2 POST/sec rate limit on application creation
- [How to Integrate with the Lever API (2026 Engineering Guide)](https://truto.one/blog/how-to-integrate-with-the-lever-api-2026-engineering-guide) — schema variability per account
- [Ashby Job Postings API](https://developers.ashbyhq.com/docs/public-job-posting-api) — pagination via `cursor`, no published rate limits
- [SmartRecruiters Rate Limiting](https://developers.smartrecruiters.com/docs/rate-limiting) — 300 req/min/client cap, 429 + Retry-After
- [SmartRecruiters Pagination](https://developers.smartrecruiters.com/docs/pagination) — `offset`/`limit`/`totalFound`
- [Workday Scraper API](https://jobo.world/ats/workday) — `https://{tenant}.wd{N}.myworkdayjobs.com` URL structure, `/wday/cxs/{tenant}/{site}/jobs` POST endpoint
- [Workday community scraper (chuchro3/WebCrawler)](https://github.com/chuchro3/WebCrawler) — required POST body shape and data-center variability

**Slug detection / company matching:**
- [Greenhouse Jobs Scraper guidance](https://apify.com/automation-lab/greenhouse-jobs-scraper) — slug-discovery best practices (lowercase company name, abbreviation patterns, validate via board URL)
- [OpenJobRadar ATS detection pipeline](https://openjobradar.com/integrations) — multi-strategy detection (slug, brute-force URL, link scanning, render fallback)

**Fuzzy dedup / company-name normalization:**
- [How to Normalize Company Names for Deduplication and Matching (Tilores)](https://medium.com/tilo-tech/how-to-normalize-company-names-for-deduplication-and-matching-21e9720b30ba) — normalize-before-dedup principle
- [How to Deduplicate a Contact List with Fuzzy Name Matching (FutureSearch)](https://futuresearch.ai/researcher-dedupe-case-study/) — confidence-band thresholds (95% auto, 70–95% review, <70% reject), under/over-merge tradeoff
- [Fuzzy Matching 101 (DataLadder)](https://dataladder.com/fuzzy-matching-101/) — false-positive examples at 85% threshold

**Python concurrency / HTTP:**
- [HTTPX async docs](https://www.python-httpx.org/async/) — AsyncClient design and connection pool defaults (10 keepalive, 100 max)
- [requests + ThreadPoolExecutor issue #2649](https://github.com/psf/requests/issues/2649) — Session not thread-safe
- [urllib3 PoolManager not thread-safe issue #1252](https://github.com/urllib3/urllib3/issues/1252) — LRU cache eviction race on many hosts
- [urllib3 connection pool exhaustion #644](https://github.com/urllib3/urllib3/issues/644) — block-on-empty-pool behavior
- [urllib3 ConnectionPool docs](https://urllib3.readthedocs.io/en/stable/reference/urllib3.connectionpool.html) — `maxsize`, `block` semantics

**Schema drift / additive migration:**
- [Pandera schema docs](https://pandera.readthedocs.io/en/stable/dataframe_schemas.html) — declarative schema validation patterns
- [Database Design Patterns for Backward Compatibility (PingCAP)](https://www.pingcap.com/article/database-design-patterns-for-ensuring-backward-compatibility/) — additive-only migration patterns

**Internal codebase:**
- `/Users/rmoore/Workspaces/job-scout-plugin/.planning/PROJECT.md` — locked decisions (concurrency cap, trust-on-0, additive schema, fuzzy dedup, hybrid detection)
- `/Users/rmoore/Workspaces/job-scout-plugin/.planning/codebase/CONCERNS.md` — silent zero-result pattern, schema drift history, no-tests baseline, tracker write fragility
- `/Users/rmoore/Workspaces/job-scout-plugin/.planning/codebase/CONVENTIONS.md` — single-source-of-truth in `schema.py`, error-handling tuple pattern, `(0,1,2)` exit-code triad, sibling-script bootstrap

---
*Pitfalls research for: ATS-first job sourcing, Python 3.8+ Claude Code plugin*
*Researched: 2026-04-28*

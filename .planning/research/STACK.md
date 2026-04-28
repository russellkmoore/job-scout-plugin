# Stack Research — v0.4 ATS-First Job Sourcing

**Domain:** Public ATS job-board APIs called concurrently from a Python 3.8+ Claude Code plugin
**Researched:** 2026-04-27
**Overall Confidence:** HIGH (all five ATS endpoints verified with live HTTP probes; library recommendation verified against project constraints)

---

## TL;DR (for the roadmap)

| Decision | Choice | Confidence |
|---|---|---|
| HTTP client | **`httpx>=0.27`** (sync `httpx.Client`, single shared instance) | HIGH |
| Concurrency primitive | **`concurrent.futures.ThreadPoolExecutor`** + per-provider `threading.Semaphore` | HIGH |
| Async (`asyncio` / `aiohttp`) | **NO** — not justified at our scale | HIGH |
| Pure stdlib (`urllib.request`) | **NO** — connection pooling, JSON, timeouts, retries are all manual | HIGH |
| `requests` | **Acceptable fallback** if user already has it; `httpx` is strictly better for this use case | MEDIUM |

**Total in-flight requests for the v0.4 milestone:** ~30 companies × 1 ATS endpoint each = ~30 HTTP requests per `/scout-run`. Even worst-case fan-out (one company → list call + N detail calls per Workday) is sub-200 requests, well under any threshold where async beats threads.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| **httpx** | `>=0.27,<0.29` | HTTP client for all 5 ATS providers | Sync `Client` is thread-safe and pools connections across threads (verified [docs](https://www.python-httpx.org/advanced/clients/), [discussion #1633](https://github.com/encode/httpx/discussions/1633)). Single import covers GET, POST-with-JSON-body (Workday), custom headers, timeouts, and retries with the same API. Already the HTTP layer used by the official `anthropic` and `openai` SDKs, so it's effectively a transitive dep on most Claude-using machines. |
| **concurrent.futures.ThreadPoolExecutor** | stdlib (3.8+) | Run per-company ATS calls in parallel | Stdlib. Trivially composes with `httpx.Client` (the client is thread-safe; share one instance across all worker threads — see [docs](https://www.python-httpx.org/advanced/clients/)). At our scale (~30 requests/run, I/O-bound, 0.3–3s per call) threads dominate async on simplicity-per-watt. Async would only pay off above ~200 concurrent requests. |
| **threading.Semaphore** | stdlib (3.8+) | Per-provider concurrency cap | The cleanest way to express "at most N concurrent requests *to this provider*" while still using a single global executor pool. Acquire-before-submit + `Future.add_done_callback(release)` pattern is well-established (`superfastpython.com`, `dev.to/ctrix`). One semaphore per provider key (`greenhouse`, `lever`, `ashby`, `smartrecruiters`, `workday`). |
| **Python 3.8+** | already required | Runtime | Existing constraint — no change. All recommendations below work on 3.8. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| **stdlib `json`** | built-in | Parse responses, build POST body for Workday | All five APIs return `application/json`. No custom encoder needed — `httpx` request `json=` param handles serialization with correct Content-Type. |
| **stdlib `urllib.parse`** | built-in | Parse Workday board URLs to extract `tenant`, `wd_server`, `site` | Avoid pulling in `tldextract` or similar — Workday URL shape is fixed (`{tenant}.wd{N}.myworkdayjobs.com/[locale/]{site}`) and a 10-line regex suffices. |
| **stdlib `re`** | built-in | Provider auto-detection from career-page URL (`boards.greenhouse.io` → `greenhouse`, `jobs.lever.co` → `lever`, etc.) | The `/scout-detect` skill needs cheap pattern matching, not full URL parsing. |
| **stdlib `dataclasses`** | built-in | Normalize the 5 different per-provider response shapes into one internal `JobListing` shape | Avoid Pydantic — it's a heavy dep we don't need. Dataclasses + a per-provider adapter function is enough. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `pip install httpx --break-system-packages` | Install the one new dep | Same install pattern as existing `pandas`/`openpyxl`. Surface in script error messages on `ImportError` (matches `scripts/validate_data.py:29` pattern). |
| **No new linter / formatter / test runner** | — | Out of scope per `PROJECT.md` (no formal test suite for v0.4). |

---

## Installation

```bash
# Add to existing install line in README.md and any error-message hints:
pip install httpx --break-system-packages

# Existing deps (unchanged):
pip install pandas openpyxl --break-system-packages
```

The plugin still has no `requirements.txt` per project convention. Surface the new dep the same way as existing deps: an `ImportError` handler at the top of the new ATS module that prints the install command to stderr.

---

## ATS Endpoint Reference (verified live 2026-04-27)

All five endpoints were verified with `curl` against real customer boards on 2026-04-27. Status codes, response shapes, and per-call latency captured below are from those probes.

### 1. Greenhouse — `boards-api.greenhouse.io`

| Field | Value |
|---|---|
| List URL | `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true` |
| Detail URL | `GET https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}` (rarely needed — `?content=true` returns full description in the list call) |
| Auth | None — public, CDN-cached, **explicitly not rate-limited** ([Greenhouse docs](https://developers.greenhouse.io/job-board.html)) |
| Method | `GET` |
| Response top-level keys | `jobs`, `meta` |
| Per-job keys (verified) | `id`, `title`, `absolute_url`, `location.name`, `updated_at`, `first_published`, `requisition_id`, `content` (HTML, when `?content=true`), `departments`, `offices`, `metadata`, `company_name`, `language` |
| Live probe | `airbnb` → 221 jobs, 0.73s |
| Quirks | `content` is HTML-escaped — strip tags for matching. `location.name` is a freeform string ("Paris, France"); no structured city/country. |
| Concurrency advice | Highest cap is fine. CDN-cached, designed for fanout. **Cap: 10 concurrent.** |

### 2. Lever — `api.lever.co/v0/postings`

| Field | Value |
|---|---|
| List URL | `GET https://api.lever.co/v0/postings/{site}?mode=json` |
| EU URL | `GET https://api.lever.co/v0/postings/{site}?mode=json` (no separate domain for the public API) |
| Auth | None for `mode=json` GETs ([Lever postings-api repo](https://github.com/lever/postings-api)) |
| Method | `GET` |
| Response top-level | **Bare JSON array** (not an object) — important: `len(response.json())` not `response.json()['jobs']` |
| Per-job keys (verified) | `id` (UUID), `text` (title), `hostedUrl`, `applyUrl`, `categories.{commitment,department,location,team,allLocations}`, `description` (HTML), `descriptionPlain`, `descriptionBody`, `descriptionBodyPlain`, `opening`, `openingPlain`, `additional`, `additionalPlain`, `lists` (array of `{text, content}`), `workplaceType` (`on-site`/`remote`/`hybrid`/`unspecified`), `country` (ISO-3166-1 alpha-2), `createdAt` (epoch ms) |
| Live probe | `spotify` → 181 jobs, 2.73s; `leverdemo` → 390 jobs, 4.52s; `netflix` → 0 jobs (legitimately empty); `ramp`/`shopify` → 404 (not Lever customers) |
| Quirks | **404 on unknown slug** — must treat 404 as "not a Lever customer", not as "transient error". Slow first-byte response on large boards (3–4s); set `timeout=15`. **Application POST is rate-limited at 2 req/s** but listings GETs are not officially capped. |
| Concurrency advice | Public-API GETs aren't documented as rate-limited, but the slow first-byte suggests a single backend, not a CDN. **Cap: 5 concurrent.** |

### 3. Ashby — `api.ashbyhq.com/posting-api`

| Field | Value |
|---|---|
| List URL | `GET https://api.ashbyhq.com/posting-api/job-board/{job_board_name}?includeCompensation=true` |
| Detail URL | None — list call returns full `descriptionHtml` and `descriptionPlain` per job |
| Auth | None for the public posting endpoint ([Ashby docs](https://developers.ashbyhq.com/docs/public-job-posting-api)) |
| Method | `GET` |
| Response top-level | `apiVersion` (int, currently `1`), `jobs` (array) |
| Per-job keys (verified) | `id`, `title`, `department`, `team`, `employmentType` (`FullTime`/`PartTime`/`Intern`/`Contract`/`Temporary`), `location` (string), `secondaryLocations` (array), `address.postalAddress.{addressLocality,addressRegion,addressCountry}`, `publishedAt` (ISO 8601), `isListed` (bool), `isRemote` (bool), `workplaceType` (`OnSite`/`Remote`/`Hybrid`), `jobUrl`, `applyUrl`, `descriptionHtml`, `descriptionPlain`, `compensation`, `shouldDisplayCompensationOnJobPostings` |
| Live probe | `Ashby` → 63 jobs, 0.66s |
| Quirks | **Returns unlisted jobs by default.** Filter `isListed == True` before scoring. The job-board slug is **case-sensitive** (`Ashby` not `ashby`). |
| Concurrency advice | **Cap: 8 concurrent.** Fast, no documented rate limit. |
| Public GraphQL? | **No.** GraphQL exists at `api.ashbyhq.com/graphql` but requires auth (`jobsRead` permission). The public REST endpoint is the only unauthenticated path. **Anti-recommendation: don't try to use Ashby GraphQL** — it gives no advantage for this milestone and adds auth complexity. |

### 4. SmartRecruiters — `api.smartrecruiters.com/v1/companies/{company}/postings`

| Field | Value |
|---|---|
| List URL | `GET https://api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings?limit=100&offset=0` |
| Detail URL | `GET https://api.smartrecruiters.com/v1/companies/{companyIdentifier}/postings/{postingId}` |
| Auth | None for these endpoints (verified — no auth header sent in live probe, returned 200) ([SmartRecruiters docs](https://developers.smartrecruiters.com/docs/posting-api)) |
| Method | `GET` |
| List response top-level (verified) | `offset`, `limit`, `totalFound`, `content` (array) |
| Per-listing keys (verified, list call) | `id`, `name` (title), `uuid`, `jobAdId`, `defaultJobAd`, `refNumber`, `company.{name,identifier}`, `releasedDate`, `location.{city,region,country,remote,fullLocation}`, `industry.{id,label}`, `department.{id,label}`, `function.{id,label}`, `typeOfEmployment.label`, `experienceLevel.label`, `customField` |
| Detail response keys (verified) | adds `postingUrl`, `applyUrl`, `referralUrl`, `jobAd.sections.{companyDescription,jobDescription,qualifications,additionalInformation}`, `active`, `visibility`, `language` |
| Live probe | `visa` → 44 jobs, 0.66s. Most known SR users (square, twitter, hubspot, atlassian, doordash, bose, ikea, lego) returned `totalFound: 0` — likely have moved off the public posting feed or use a different `companyIdentifier`. Detail call for visa job → 200 with full `jobAd.sections`. |
| Quirks | **List call returns no description** — must follow with detail GET per posting to get `jobAd.sections.jobDescription`. This means SmartRecruiters is the only provider where you fan out N+1 calls per company. **Plan for it in the concurrency budget.** Many "famous" companies return `totalFound: 0` — verify the slug at detection time, not at run time. |
| Concurrency advice | **Cap: 5 concurrent** for list calls. Within a company, the detail-call fanout uses the same global semaphore. |

### 5. Workday — `{tenant}.wd{N}.myworkdayjobs.com/wday/cxs`

| Field | Value |
|---|---|
| List URL | `POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs` |
| Detail URL | `GET https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/job{externalPath}` (note: no slash between `job` and `externalPath` — `externalPath` already starts with `/`) |
| Auth | None for these public CXS endpoints. **CSRF tokens are NOT required** for the JSON endpoints (verified — live probe returned 200 with no cookies/tokens) |
| Method | `POST` for list (with JSON body); `GET` for detail |
| List request body | `{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}` — all four fields required, even if empty |
| List response top-level (verified) | `total`, `jobPostings`, `facets`, `userAuthenticated` |
| Per-listing keys (verified) | `title`, `externalPath` (e.g. `/job/INDPune/Sr-Associate-People-Support-Specialist_JR-0104329`), `locationsText`, `postedOn` (human-readable: `"Posted Today"`, `"Posted 5 Days Ago"`), `remoteType` (`Onsite`/`Hybrid`/`Flex`/`Remote`), `bulletFields` (array, usually contains the requisition ID like `JR-0104329`) |
| Detail response keys (verified) | `jobPostingInfo.{id,title,jobDescription (full HTML),location,postedOn,startDate,timeType,jobReqId,jobPostingId,country,canApply,posted,remoteType,externalUrl,questionnaireId}`, `hiringOrganization`, `similarJobs` |
| Required headers | `Content-Type: application/json`, `Accept: application/json`. **`User-Agent: Mozilla/5.0` recommended** — some Workday tenants 403 on default Python UAs. |
| Live probe | Workday's own board (`workday.wd5.myworkdayjobs.com/Workday`) → `total: 447`, returned 20 in 2.52s. Detail call for `JR-0104329` → 200 in 0.38s with full HTML description. |
| Quirks | **`postedOn` is unstructured English** — `"Posted Today"`, `"Posted 5 Days Ago"`, `"Posted 30+ Days Ago"`. No ISO date in the list response. Use it as-is for display, or call detail to get `startDate`. **Pagination via `offset`/`limit` (max 20)**, so a 447-job board needs 23 calls to enumerate fully — but for our use case (top-N matched roles per company, scored against profile), **just call once with `limit=20` and `searchText` filtering** — don't paginate. |
| Concurrency advice | **Cap: 3 concurrent.** Workday tenants are per-customer infrastructure (not a shared CDN like Greenhouse), and aggressive fanout to one tenant is the most likely path to a block. |
| Tenant detection | URL pattern: `https://{tenant}.wd{N}.myworkdayjobs.com[/locale]/{site}`. Regex: `^https?://([^.]+)\.wd(\d+)\.myworkdayjobs\.com(?:/[a-z]{2}-[A-Z]{2})?/([^/?]+)`. The `wd{N}` segment matters — it's part of the host, not interchangeable. |

### Per-provider concurrency caps summary

| Provider | List cap | Notes |
|---|---|---|
| Greenhouse | 10 | CDN-cached, no rate limit documented |
| Ashby | 8 | Fast, no rate limit documented |
| Lever | 5 | Slow per-call, single-tenant backend feel |
| SmartRecruiters | 5 | N+1 fanout per company for descriptions |
| Workday | 3 | Per-customer infra, most blockable |
| **Global executor `max_workers`** | **20** | sum of caps; semaphores prevent any one provider exceeding its cap |

These are starting values. Per `PROJECT.md` Out of Scope: "specialize only if we discover real limits in production."

---

## Concurrency Pattern (Recommended Implementation Sketch)

```python
# scripts/ats/dispatcher.py (new file in v0.4)
import httpx
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

# One client, shared across all threads. httpx.Client is thread-safe.
_CLIENT = httpx.Client(
    timeout=httpx.Timeout(15.0, connect=5.0),
    headers={"User-Agent": "job-scout/0.4 (+claude-code-plugin)"},
    limits=httpx.Limits(max_connections=20, max_keepalive_connections=20),
    follow_redirects=True,
)

# One semaphore per provider, gating concurrent in-flight requests.
_PROVIDER_CAPS = {
    "greenhouse": 10,
    "ashby": 8,
    "lever": 5,
    "smartrecruiters": 5,
    "workday": 3,
}
_SEMAPHORES = {p: threading.Semaphore(n) for p, n in _PROVIDER_CAPS.items()}

@contextmanager
def _gate(provider: str):
    sem = _SEMAPHORES[provider]
    sem.acquire()
    try:
        yield
    finally:
        sem.release()

def fetch_listings(provider: str, board_id: str) -> list[dict]:
    with _gate(provider):
        # provider-specific call: returns normalized JobListing dicts
        return _PROVIDER_FUNCS[provider](_CLIENT, board_id)

def run_all(targets: list[tuple[str, str]]) -> list[dict]:
    """targets: list of (provider, board_id) pairs."""
    results = []
    with ThreadPoolExecutor(max_workers=20) as pool:
        futures = {pool.submit(fetch_listings, p, b): (p, b) for p, b in targets}
        for fut in futures:
            try:
                results.extend(fut.result(timeout=30))
            except Exception as exc:
                # Log and continue — per PROJECT.md "treat as no openings, move on"
                pass
    return results
```

**Why this shape:**

- **Single `httpx.Client` shared across threads.** `httpx.Client` is documented thread-safe and "a single client-instance across all threads will do better in terms of connection pooling, than using an instance-per-thread" ([httpx discussions #1633](https://github.com/encode/httpx/discussions/1633)). This is the opposite of `requests.Session`, which is **not** thread-safe ([requests issue #2766](https://github.com/psf/requests/issues/2766), [#1871](https://github.com/psf/requests/issues/1871)) — that alone is the deciding factor against `requests`.
- **`max_workers=20` matches `sum(provider_caps)`.** Provides headroom; semaphores enforce the actual per-provider limits.
- **Semaphore acquire-before-call (not acquire-before-submit).** Submitting all futures up-front lets the executor schedule fairly; the semaphores throttle inside each task. This is simpler than the `add_done_callback(release)` pattern when the work itself is short.
- **Exception swallow → empty results.** Matches `PROJECT.md` decision: "If an ATS endpoint returns 0 jobs or errors, treat it as 'no openings, move on'."

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `httpx` sync `Client` + `ThreadPoolExecutor` | `httpx.AsyncClient` + `asyncio.gather` with `asyncio.Semaphore` | If we ever fan out to >200 concurrent requests (unlikely — would mean tracking >200 companies). At our scale the async overhead (event loop, coroutine setup, async-aware everything-downstream) costs more developer time than it saves wall-clock time. ([Comparison](https://decodo.com/blog/httpx-vs-requests-vs-aiohttp): "Above 50–100 concurrent requests, async almost always beats a thread pool"; we're at ~30.) |
| `httpx` | `aiohttp` | Async-only. Same crossover point as above (≥200 concurrent), and we'd still need `requests` or `urllib` for any sync code path that already exists in `scripts/`. Don't introduce two HTTP libraries. |
| `httpx` | `requests` + `requests.Session()` | If `httpx` install fails for some user. **But:** `requests.Session` is not thread-safe (per maintainers, [issue #2766](https://github.com/psf/requests/issues/2766)) — would need one Session per thread, which kills connection pool efficiency. Also `requests` doesn't natively support HTTP/2; some Workday tenants prefer it. |
| `httpx` | stdlib `urllib.request` | If we wanted **zero** new dependencies. Cost: manual JSON serialization, manual timeouts (`timeout=` works but no read/connect split), manual retry, no connection pooling. For the volume we're doing this is genuinely workable but every per-provider module would be 30+ extra lines of boilerplate. Trading 1 dep for 5 modules of boilerplate is a bad ratio. |
| `concurrent.futures.ThreadPoolExecutor` | `multiprocessing.Pool` | Process pools are for CPU-bound work. ATS calls are 100% I/O-bound (waiting on the network). Process startup cost per task would dominate. |
| `threading.Semaphore` per provider | `asyncio.Semaphore` | Only relevant if we go async (we're not). |
| `threading.Semaphore` per provider | Global token-bucket rate limiter (`ratemate`, custom) | Token-bucket is for "N requests per second" throttling. We want "N concurrent in-flight" — different shape. Semaphore is the right primitive for the "concurrent cap" requirement in `PROJECT.md`. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| **`aiohttp`** | Async-only, doesn't help at our scale (~30 requests/run), would make the rest of `scripts/` (sync) interop awkward, and adds a second HTTP library if we ever need a sync call. | `httpx` sync client + `ThreadPoolExecutor` |
| **`requests` + threaded `Session`** | `requests.Session` is documented as not thread-safe by maintainers ([#2766](https://github.com/psf/requests/issues/2766), [#1871](https://github.com/psf/requests/issues/1871)). Workarounds (Session-per-thread, global lock) defeat connection-pool benefits or serialize the work. | `httpx.Client` (thread-safe by design) |
| **`requests-toolbelt` `BackgroundSession`** | Pulls in another dep just to paper over `requests` thread safety; `httpx` solves the same problem natively. | `httpx.Client` |
| **`asyncio` for the core loop** | Adds async-aware composition cost (cancellation, gather, exception groups, `asyncio.run`) for no measurable wall-clock benefit at this scale. We'd also need to bridge to the existing sync `scripts/` modules. | Threads |
| **`urllib3` directly** | Lower-level than `requests` or `httpx`. Manual response parsing, manual retry. No advantage over `httpx`. | `httpx` |
| **`pycurl`** | C extension. Install pain on macOS without Homebrew curl. No benefit at our scale. | `httpx` |
| **Ashby GraphQL** | Public REST endpoint covers everything we need (`descriptionHtml`, `applyUrl`, `isListed`, `compensation`). GraphQL requires auth and adds query-construction complexity. | Ashby public REST `posting-api/job-board/{slug}` |
| **Greenhouse Harvest API** | Different API, requires API key per company, designed for ATS integrations not job seekers. | Greenhouse public Job Board API (`boards-api.greenhouse.io`) |
| **Workday SOAP API** | Authenticated, complex, designed for HR integrations. | Workday CXS public POST endpoint (`/wday/cxs/.../jobs`) |
| **Per-provider rate-limit retry libraries** (`backoff`, `tenacity`) | Out of scope per `PROJECT.md`: "treat ATS error as no openings, move on." We're not retrying — we're moving on. | Plain try/except in the dispatcher |
| **Per-call `httpx.Client(...)` instantiation** | Defeats connection pooling, costs ~50ms TLS handshake every call. | One module-level `httpx.Client`, reused across all threads |
| **JSON validation libs (`pydantic`, `marshmallow`)** | Heavy deps. We're parsing 5 known shapes into one normalized dict. | `dataclasses` + per-provider adapter functions |

---

## Stack Patterns by Variant

**If a user has only ~5 companies in `master_targets.csv`:**
- `ThreadPoolExecutor(max_workers=5)` is enough.
- Per-provider semaphores still matter — a user with 5 Workday companies could still hit one tenant 5 times.
- Same code, smaller numbers.

**If we ever expand to 100+ companies (post-v0.4):**
- Reconsider async. At ~100 concurrent requests, thread overhead becomes measurable (`oxylabs.io/blog/httpx-vs-requests-vs-aiohttp`).
- The semaphore-per-provider pattern translates 1:1 to `asyncio.Semaphore`.
- Migration cost: rewrite ~5 provider modules (each 20–40 lines). Manageable but not free — don't pre-pay for it now.

**If a Workday tenant returns 403 / requires CSRF (deferred per `PROJECT.md`):**
- Catch the 403, mark `ats_provider` as `workday_blocked` in the row, fall through to Pass 2.
- Don't try to scrape CSRF tokens from the HTML page — that's the marketing-page-fragility we're explicitly removing.

**If `httpx` install fails on a user's machine:**
- Surface the install command in the `ImportError` handler (matches existing `pandas`/`openpyxl` pattern).
- Don't ship a `requests` fallback path — maintaining two HTTP code paths is worse than one clean install instruction.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---|---|---|
| `httpx>=0.27,<0.29` | Python 3.8+ (3.8 dropped in `httpx 1.0` — not yet released as of 2026-04) | The 0.27–0.28 line is the current stable as of research date. Pin upper bound to avoid silent breakage when 1.0 lands and drops 3.8. |
| `httpx[http2]` | optional extra | Pulls in `h2`. Some Workday tenants prefer HTTP/2 but the CXS API works fine on HTTP/1.1. **Don't add the extra unless we see a Workday tenant problem in production.** |
| `httpx` + `concurrent.futures` | full compat | `httpx.Client` is thread-safe; verified safe to share across `ThreadPoolExecutor` workers. |
| `httpx` + existing `pandas`/`openpyxl` | no conflict | `httpx` has no overlap with `pandas`/`openpyxl` deps. |
| Python 3.8 | end-of-life October 2024 | We're past EOL. The `PROJECT.md` constraint ("Python 3.8+") was set when 3.8 was current. Recommendation: keep the 3.8+ floor for now (don't break existing users), but plan to bump to 3.9+ in v0.5 — `httpx` 1.0 will likely require it. |

---

## Quality Gate Checklist

- [x] **ATS endpoint URLs and response shapes verified against current docs** — all 5 verified with live HTTP probes 2026-04-27, not just docs
- [x] **HTTP library recommendation justified for THIS project** — `httpx` chosen because it's the only sync client that's officially thread-safe, supports POST-with-JSON (Workday) cleanly, and pools connections across threads. Single dep covers all 5 providers.
- [x] **Concurrency approach justified against actual scale** — ~30 companies × 5 providers = ~30 list calls (worst case ~200 with SmartRecruiters detail fanout). Threads dominate async at this scale; async crossover is documented at 50–200 concurrent requests minimum.
- [x] **Confidence levels assigned** — see TL;DR table
- [x] **Anti-recommendations included** — see "What NOT to Use" table

---

## Sources

**Greenhouse:**
- [Job Board API docs](https://developers.greenhouse.io/job-board.html) — endpoints, query params, no-auth-no-rate-limit confirmation. HIGH confidence.
- Live HTTP probe 2026-04-27: `boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true` → 200, 221 jobs, 0.73s, response shape captured. HIGH confidence.

**Lever:**
- [lever/postings-api GitHub repo](https://github.com/lever/postings-api) — official endpoint docs, response field reference, rate-limit info. HIGH confidence.
- Live HTTP probes 2026-04-27: `api.lever.co/v0/postings/{spotify,leverdemo,netflix,ramp,shopify}` — confirmed bare-array response, 404 on unknown slugs, latency varies 0.3–4.5s, response shape captured. HIGH confidence.

**Ashby:**
- [Public Job Posting API docs](https://developers.ashbyhq.com/docs/public-job-posting-api) — endpoint, query params, JSON shape. HIGH confidence.
- Live HTTP probe 2026-04-27: `api.ashbyhq.com/posting-api/job-board/Ashby?includeCompensation=true` → 200, 63 jobs, 0.66s, all fields captured. HIGH confidence.
- [`jobBoard.list` reference](https://developers.ashbyhq.com/reference/jobboardlist) — confirmed GraphQL exists but requires auth. HIGH confidence.

**SmartRecruiters:**
- [Posting API docs](https://developers.smartrecruiters.com/docs/posting-api) — endpoint structure. HIGH confidence on URL shape.
- [Get job postings reference](https://developers.smartrecruiters.com/docs/get-job-postings) — query params, response shape (lacks the `/v1/companies/{id}/postings` per-company endpoint shape; that came from live probe). MEDIUM confidence on docs alone.
- Live HTTP probes 2026-04-27: `api.smartrecruiters.com/v1/companies/{visa,square,twitter,hubspot,atlassian,doordash,bose,ikea,publicissapient,kfc,lego}/postings` — confirmed no auth required, response shape (`offset/limit/totalFound/content`), Visa returned 44 jobs, most others returned 0. Detail call against a Visa posting confirmed `jobAd.sections.{companyDescription,jobDescription,qualifications,additionalInformation}`. HIGH confidence.

**Workday:**
- [Workday Scraper API guide (jobo.world)](https://jobo.world/ats/workday) — POST body shape, header requirements, externalPath usage. MEDIUM confidence (third-party reverse-engineered guide).
- Live HTTP probe 2026-04-27: `POST workday.wd5.myworkdayjobs.com/wday/cxs/workday/Workday/jobs` with `{"appliedFacets":{},"limit":20,"offset":0,"searchText":""}` → 200, 447 total jobs, 2.52s, all fields captured. Detail call → 200, 0.38s, full HTML description in `jobPostingInfo.jobDescription`. **HIGH confidence based on live probe.**

**HTTP libraries:**
- [HTTPX Clients docs](https://www.python-httpx.org/advanced/clients/) — thread safety, connection pooling, configuration. HIGH confidence.
- [HTTPX discussion #1633: Is httpx.Client thread safe?](https://github.com/encode/httpx/discussions/1633) — confirms single-instance-across-threads is the recommended pattern. HIGH confidence.
- [requests issue #2766: Document threading contract for Session class](https://github.com/psf/requests/issues/2766) — maintainer-confirmed `requests.Session` is not thread-safe. HIGH confidence.
- [requests issue #1871: Our use of urllib3's ConnectionPools is not threadsafe](https://github.com/psf/requests/issues/1871) — root cause for why `requests.Session` isn't thread-safe. HIGH confidence.
- [HTTPX vs Requests vs AIOHTTP comparison (decodo, 2026)](https://decodo.com/blog/httpx-vs-requests-vs-aiohttp) — sync/async crossover point ("above 50–100 concurrent requests, async almost always beats a thread pool"). MEDIUM confidence (single benchmark source, but matches multiple corroborating sources).
- [Speakeasy: Python HTTP clients comparison](https://www.speakeasy.com/blog/python-http-clients-requests-vs-httpx-vs-aiohttp) — confirms HTTPX is used by `anthropic` and `openai` SDKs. MEDIUM confidence.

**Concurrency:**
- [Python `concurrent.futures` stdlib docs](https://docs.python.org/3/library/concurrent.futures.html) — `ThreadPoolExecutor` API. HIGH confidence.
- [Super Fast Python: Limit pending tasks in ThreadPoolExecutor](https://superfastpython.com/threadpoolexecutor-limit-pending-tasks/) — semaphore + acquire-before-submit + done-callback pattern. MEDIUM confidence.
- [DEV: Controlling Concurrency in Python — Semaphores and Pool Workers](https://dev.to/ctrix/controlling-concurrency-in-python-semaphores-and-pool-workers-56d7) — per-resource semaphore pattern. MEDIUM confidence.

---

*Stack research for: ATS-first job sourcing (v0.4 milestone)*
*Researched: 2026-04-27*

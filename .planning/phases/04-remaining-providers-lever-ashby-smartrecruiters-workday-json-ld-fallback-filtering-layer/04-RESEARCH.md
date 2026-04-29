# Phase 4: Remaining Providers + JSON-LD + Filtering Layer — Research

**Researched:** 2026-04-28
**Domain:** ATS provider modules (Lever, Ashby, SmartRecruiters, Workday) + JSON-LD fallback + post-fetch filtering layer
**Confidence:** HIGH (all four providers probed live 2026-04-28; filtering layer derived from existing codebase + PITFALLS.md; Workday searchText behavior newly verified)

---

## Summary

Phase 4 adds four provider modules conforming to the Provider Protocol established in Phase 2, a JSON-LD fallback as a sixth virtual provider, and a shared filtering layer in `scripts/ats/normalize.py`. The substrate — Provider Protocol, `PROVIDERS` registry, dispatcher, semaphores, `FetchResult`/`Listing` shapes — is fully in place from Phases 2–3. Each new provider is ~100–200 lines following the same shape as `scripts/ats/providers/greenhouse.py`.

**Critical live finding (2026-04-28):** Workday's CXS list endpoint returns `title`, `locationsText`, `postedOn`, and `remoteType` ONLY when `searchText` is a non-empty string. Empty `searchText` returns only `externalPath` and `bulletFields`. **Use `searchText="a"` as the effective "list all" call.** This is the most important implementation gotcha for this phase.

**Second critical finding:** Ashby has no company-name field in its job response — company name must be inferred from the `jobUrl` domain pattern (`jobs.ashbyhq.com/{slug}/...`). Lever similarly: no company field in job objects — the slug from the URL is the only company identifier. Both providers' detect() functions must use a different strategy for the name-match gate than Greenhouse does.

**Primary recommendation:** Implement providers in order of complexity — Lever (simplest), Ashby (simple but no company name), SmartRecruiters (N+1 detail call pattern), Workday (most complex, last). Build the filtering layer in `normalize.py` as standalone functions that Phase 5 dedup and Phase 6 scoring can also call. JSON-LD lives as a standalone sixth provider, not an inline fallback inside other providers' fetch().

---

<user_constraints>
## User Constraints (from CONTEXT.md)

No CONTEXT.md exists for Phase 4 — no prior /gsd-discuss-phase was run. All decisions below come from locked decisions in CLAUDE.md and PROJECT.md.

### Locked Decisions (from CLAUDE.md + PROJECT.md)

| Decision | Rationale |
|----------|-----------|
| ATS providers: Greenhouse (Phase 2), Lever, Ashby, SmartRecruiters, Workday (Phase 4) | ~80% coverage of target companies |
| Per-provider concurrency caps: Lever=5, Ashby=8, SmartRecruiters=5, Workday=3 | Already in `dispatcher.DEFAULT_PROVIDER_CAPS` |
| Provider Protocol via duck-typed typing.Protocol, NOT inheritance | DSP-01 locked decision |
| Each provider is its own ~100–200 line module | No generic abstraction layer |
| Per-provider sanitized fixture in `tests/fixtures/ats/<provider>/<company>.json` | Phase 2 pattern (airbnb.json) |
| 3-state dispatcher outcomes: OK_WITH_RESULTS / OK_ZERO / ERROR | DSP-05 |
| httpx>=0.27,<0.29 sync Client (already installed) | Phase 2 |
| rapidfuzz already installed | Phase 3 |
| Trust ATS on 0/error — no Chrome fallback | Milestone-defining |
| Workday CSRF/auth-required: log as ERROR with reason, route to Pass 2, never silently zero | PRV-05 |
| JSON-LD fallback: fetch via httpx, parse `<script type="application/ld+json">`, no Chrome | STR-01 |
| Filtering lives in `scripts/ats/normalize.py` | PRV-06, PRV-07, PRV-08 |
| Per-provider posted_date_max_age_days override via config.json | STR-03 |
| Evergreen blocklist pattern set lives in references/ats-providers.md | PRV-08 |
| Delete marketing-page Chrome scraping — not flag-and-keep | Milestone-defining |
| No retry-on-403/429 within a run | Anti-feature |
| All 5 providers registered in `scripts/ats/__init__.py:PROVIDERS` | PRV-09 |

### Claude's Discretion

- Ordering of plan sub-tasks within each plan
- Whether to combine filter functions or keep them separate
- Exact regex patterns for posted_date parsing
- Whether `references/ats-providers.md` is a new file or appended to existing references

### Deferred Ideas (OUT OF SCOPE)

- Workday CSRF token harvesting (v0.5+ per WDA-01)
- Workday pagination beyond first 20 results (v0.5+)
- SmartRecruiters description fanout pagination beyond first page
- Ashby GraphQL (auth required — explicitly anti-recommended)
- JSON-LD with JS rendering (Chrome fallback — explicitly forbidden)
- Per-provider rate-limit adaptive backoff
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PRV-01 | `scripts/ats/providers/lever.py` — detect, fetch (bare-array response), normalize (missing `lists` field), fixture | Lever endpoint verified live; bare-array confirmed; `createdAt` is epoch ms; company name derived from slug |
| PRV-02 | `scripts/ats/providers/ashby.py` — detect (REST, not GraphQL), fetch (case-sensitive slug), normalize (isListed=true filter), fixture | Ashby endpoint verified live; no company_name field in jobs; detect uses jobUrl domain; no pagination in current API |
| PRV-03 | `scripts/ats/providers/smartrecruiters.py` — detect, list-then-detail fetch, normalize, fixture | SR endpoint verified live; list returns no description; detail GET per job returns jobAd.sections.jobDescription |
| PRV-04 | `scripts/ats/providers/workday.py` — detect (parses tenant/dc/site from ats_board_url), POST fetch (searchText="a" trick), normalize (freeform postedOn parsing), fixture covering ≥3 tenants | Workday endpoint verified live; searchText="a" returns full fields; postedOn regex parsing confirmed |
| PRV-05 | Workday CSRF/auth-required explicit detection — 401/403 with body markers logs workday-auth-required to runs.jsonl, routes to Pass 2 | Implementation: check response body for "csrf", "session", "cookie" strings; use FetchResult with http_status=401/403 |
| PRV-06 | `normalize.py` filters listings older than `ats.posted_date_max_age_days` (default 60d, configurable) | Filter function applies after to_listing(); reads config value passed from dispatcher |
| PRV-07 | `normalize.py` collapses intra-source regional duplicates: same (provider, company_slug, normalized_title) with multiple locations → one Listing with locations=[] | Groupby key = (source, company, normalized_title); merge location strings; keep earliest posted_date |
| PRV-08 | `normalize.py` blocklist drops evergreen postings matching title regex; pattern set in references/ats-providers.md | Regex: `^(general application|talent network|future opportunities|join our team|connect with us|expression of interest)` — case-insensitive |
| PRV-09 | All 5 providers registered in `scripts/ats/__init__.py:PROVIDERS`; dispatcher + detector iterate registry | Simple: add 4 import lines + 4 dict entries; detection order: greenhouse→lever→ashby→smartrecruiters→workday |
| STR-01 | JSON-LD fallback: fetch careers_url via httpx, parse JobPosting schema.org blocks, normalize to Listing with source=ats:jsonld | httpx GET + regex extract `<script type="application/ld+json">` blocks + json.loads; datePosted is ISO 8601 |
| STR-03 | Per-provider `posted_date_max_age_days` override in config.json (e.g. Workday=90, Greenhouse=30) | Implemented in filter function: check `config.ats.provider_posted_date_overrides.{provider}` before global default |
</phase_requirements>

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Provider HTTP fetch | `scripts/ats/providers/<provider>.py` | dispatcher.py (semaphore, error wrap) | Per-provider quirks isolated; dispatcher stays provider-agnostic |
| Response normalization | `scripts/ats/providers/<provider>.py::to_listing()` | `scripts/ats/normalize.py` (Listing dataclass validates) | Per-provider field mapping is provider-specific; Listing contract is shared |
| Posted-date age filter | `scripts/ats/normalize.py::filter_stale()` | dispatcher.py (passes config) | Shared logic; provider-agnostic; config-driven |
| Regional duplicate collapse | `scripts/ats/normalize.py::collapse_regional_dupes()` | dispatcher.py (calls after fetch_all) | Operates on a batch of Listings from one provider + company; not per-provider |
| Evergreen blocklist | `scripts/ats/normalize.py::filter_evergreen()` | references/ats-providers.md (pattern source) | Shared logic; patterns configurable outside code |
| Workday CSRF detection | `scripts/ats/providers/workday.py::fetch()` | runs_log.py (telemetry) | Provider-specific; logged as ERROR with specific reason |
| JSON-LD fallback | `scripts/ats/providers/jsonld.py` | PROVIDERS registry (6th entry) | Virtual provider; same Protocol shape; called for ats_provider="none" + careers_url set |
| Provider registration | `scripts/ats/__init__.py::PROVIDERS` | detect.py + dispatcher.py (iterate) | Single source of truth for provider order |
| Config loading | dispatcher.py::load_caps_and_kill_switch() | Extended for per-provider age overrides | Already reads ats.* from config.json |

---

## Standard Stack

### Already Installed (no new deps)

| Library | Version | Purpose |
|---------|---------|---------|
| httpx | 0.28.1 (installed) | All HTTP calls — GET and POST |
| rapidfuzz | latest (installed) | Company name matching in detect() |
| stdlib re | built-in | HTML tag stripping, posted_date parsing, JSON-LD extraction |
| stdlib json | built-in | JSON parsing |
| stdlib html | built-in | HTML entity decoding (Lever descriptionBody is HTML) |
| stdlib datetime | built-in | Date arithmetic for age filter |

**No new dependencies for Phase 4.** All required libraries are installed.

### Filtering in normalize.py (new functions, no deps)

Three new standalone functions added to `scripts/ats/normalize.py`:

```python
def filter_stale(listings, max_age_days, provider_overrides=None, today=None):
    """Drop Listings older than max_age_days. Uses per-provider override if set."""

def collapse_regional_dupes(listings):
    """Group by (source, company, normalized_title); merge location strings."""

def filter_evergreen(listings, blocklist_patterns=None):
    """Drop listings whose normalized title matches the evergreen blocklist regex."""
```

---

## Architecture Patterns

### System Architecture Diagram (Phase 4 additions)

```
master_targets.csv
  [ats_provider=lever|ashby|smartrecruiters|workday|none]
        |
        v
dispatcher.fetch_all(targets, config_path)
  |-- for each (company_slug, provider):
  |     |-- PROVIDERS[provider].fetch(slug, client, semaphore) -> FetchResult
  |     |-- _execute_one() wraps exceptions as ERROR
  |     |-- semaphore from _SEMAPHORES[provider]
  |-- returns List[FetchOutcome]
        |
        v
normalize.filter_stale(listings, max_age, overrides)
  -- drops listings where posted_date < today - max_age_days
        |
        v
normalize.collapse_regional_dupes(listings)
  -- groups by (source, company, normalized_title); merges locations
        |
        v
normalize.filter_evergreen(listings)
  -- drops titles matching blocklist regex
        |
        v
preview.py / scout-run SKILL.md Step 2.5
  -- writes ats_raw/<provider>/<slug>.json
  -- appends runs.jsonl
        |
        v
[Phase 5: dedupe against Pass 2]

JSON-LD path (STR-01):
master_targets.csv [ats_provider=none, careers_url=<url>]
        |
        v
PROVIDERS["jsonld"].fetch(careers_url, client, semaphore)
  -- GET careers_url
  -- extract <script type="application/ld+json"> blocks
  -- json.loads each block; filter @type=="JobPosting"
  -- normalize to Listing(source="ats:jsonld")
        |
        v
[same filter pipeline above]
```

### Recommended Project Structure (Phase 4 additions)

```
scripts/ats/providers/
├── __init__.py           (existing)
├── base.py               (existing — Provider Protocol)
├── greenhouse.py         (existing — reference implementation)
├── lever.py              (NEW — PRV-01)
├── ashby.py              (NEW — PRV-02)
├── smartrecruiters.py    (NEW — PRV-03)
├── workday.py            (NEW — PRV-04, PRV-05)
└── jsonld.py             (NEW — STR-01)

tests/fixtures/ats/
├── greenhouse/airbnb.json    (existing)
├── lever/spotify.json        (NEW — PRV-01 fixture)
├── ashby/ashby.json          (NEW — PRV-02 fixture)
├── smartrecruiters/visa.json (NEW — PRV-03; list + detail)
└── workday/
    ├── workday_wd5.json      (NEW — PRV-04; searchText="a" response)
    └── SOURCE.md             (NEW — provenance for all WD fixtures)

skills/job-scout/references/
└── ats-providers.md          (NEW or append — PRV-08 evergreen patterns)
```

---

## Per-Provider Implementation Guide

### Provider 1: Lever (PRV-01)

**Endpoint:** `GET https://api.lever.co/v0/postings/{slug}?mode=json`
**Response:** Bare JSON array (NOT an object with a `jobs` key)
**Live-verified:** 2026-04-28 against `spotify` (191 jobs)

**Key fields:**
| Field in Lever | Maps to Listing | Notes |
|----------------|-----------------|-------|
| `id` (UUID) | `raw.id` | Use as part of URL construction |
| `text` | `title` | NOT `name`, NOT `title` |
| `hostedUrl` | `url` | Full apply URL |
| `createdAt` | `posted_date` | **Epoch milliseconds** — divide by 1000, then `datetime.fromtimestamp().date().isoformat()` |
| `categories.location` | `location` | First location string |
| `categories.allLocations` | For regional collapse | Array of location strings |
| `categories.department` | `department` | May be empty string |
| `categories.commitment` | `employment_type` | e.g. "Full-time" |
| `descriptionPlain` | `description` | Prefer over stripping `description` HTML |

**Company name for detection gate:** Lever has NO `company_name` field. Detection uses the slug itself as the "returned company name" for the rapidfuzz gate. The `detect()` function should extract the company name from the first job's `hostedUrl`:
```python
# hostedUrl = "https://jobs.lever.co/spotify/1ff4a4e3-..."
# Extract slug from URL: re.search(r'jobs\.lever\.co/([^/]+)/', url)
returned_slug = re.search(r'jobs\.lever\.co/([^/]+)/', jobs[0]['hostedUrl']).group(1)
score = fuzz.token_set_ratio(normalize(company_name), normalize(returned_slug))
```

**Missing `lists` field:** `lists` is sometimes absent from individual job objects. Guard with `.get('lists') or []`.

**404 behavior:** 404 = "not a Lever customer" — same as Greenhouse. Return `DetectionStatus.NOT_FOUND` (not ERROR).

**BOARD_URL_PATTERNS:**
```python
BOARD_URL_PATTERNS = [
    r"^https?://jobs\.lever\.co/([^/?#]+)",
    r"^https?://api\.lever\.co/v0/postings/([^/?#]+)",
]
```

**Fixture to create:** Capture `https://api.lever.co/v0/postings/spotify?mode=json`, slice to first 3 jobs, save as `tests/fixtures/ats/lever/spotify.json`. Response is a bare array — wrap in `{"jobs": [...], "meta": {...}}` for fixture consistency? No — keep the raw bare array shape so the fixture tests the actual parsing path. File structure: just the array `[{...}, {...}, {...}]`.

**Acceptance test:** `lever.to_listing(fixture[0])` returns Listing with non-empty title, url, posted_date, location, source="ats:lever". `posted_date` is ISO date (not epoch). `location` is a string (not None).

---

### Provider 2: Ashby (PRV-02)

**Endpoint:** `GET https://api.ashbyhq.com/posting-api/job-board/{job_board_name}?includeCompensation=true`
**Response:** `{"apiVersion": 1, "jobs": [...]}`
**Live-verified:** 2026-04-28 against `ashby` (63 jobs)

**Key fields:**
| Field in Ashby | Maps to Listing | Notes |
|----------------|-----------------|-------|
| `id` | `raw.id` | UUID string |
| `title` | `title` | Direct |
| `jobUrl` | `url` | e.g. `https://jobs.ashbyhq.com/ashby/145ff46b-...` |
| `publishedAt` | `posted_date` | ISO 8601 with tz — slice to `[:10]` |
| `location` | `location` | String e.g. "Remote - US" |
| `secondaryLocations[].location` | For regional collapse | Array of dicts with `location` key |
| `department` | `department` | String |
| `employmentType` | `employment_type` | e.g. "FullTime" — normalize to "Full-time" |
| `isListed` | Filter gate | **Drop if `isListed == False`** — required by PRV-02 |
| `descriptionPlain` | `description` | Prefer over stripping descriptionHtml |

**Company name for detection gate:** Ashby has NO `company_name` in job objects. Extract from `jobUrl`:
```python
# jobUrl = "https://jobs.ashbyhq.com/ashby/145ff46b-..."
# Slug is the path segment after ashbyhq.com/:
returned_slug = re.search(r'jobs\.ashbyhq\.com/([^/]+)/', jobs[0]['jobUrl']).group(1)
score = fuzz.token_set_ratio(normalize(company_name), normalize(returned_slug))
```

**Case-sensitive slug:** The slug `Ashby` (capital A) is different from `ashby`. Detection must pass the slug with original casing. The canonical form from the career URL is `jobs.ashbyhq.com/{slug}` — always use the form from the ats_board_url or detected URL.

**Pagination:** Live probe shows no `moreDataAvailable` or `nextCursor` in current API response for 63-job board. The docs mention cursor pagination for GraphQL only. REST posting-api appears to return all results in one call. Do NOT implement pagination for v0.4 — add a comment noting this assumption.

**BOARD_URL_PATTERNS:**
```python
BOARD_URL_PATTERNS = [
    r"^https?://jobs\.ashbyhq\.com/([^/?#]+)",
    r"^https?://api\.ashbyhq\.com/posting-api/job-board/([^/?#]+)",
]
```

**isListed filter in fetch():** Apply inside the per-job loop, before `to_listing()`:
```python
for raw_job in data.get("jobs", []) or []:
    if not raw_job.get("isListed", True):
        continue  # Drop unlisted jobs — PRV-02 locked requirement
```

**Fixture:** Capture `https://api.ashbyhq.com/posting-api/job-board/ashby?includeCompensation=true`, keep first 3 jobs (at least one where `isListed=True` and one where `isListed=False` if available). Save as `tests/fixtures/ats/ashby/ashby.json`.

**Acceptance test:** `ashby.fetch()` with fixture skips jobs where `isListed=False`. Listing.posted_date is ISO date. Listing.source = "ats:ashby".

---

### Provider 3: SmartRecruiters (PRV-03)

**Endpoint (list):** `GET https://api.smartrecruiters.com/v1/companies/{company}/postings?limit=100&offset=0`
**Endpoint (detail):** `GET https://api.smartrecruiters.com/v1/companies/{company}/postings/{id}`
**Response:** `{"content": [...], "offset": N, "limit": N, "totalFound": N}`
**Live-verified:** 2026-04-28 against `visa` (44 total, 5 returned with limit=5)

**Key fields (list response):**
| Field | Maps to | Notes |
|-------|---------|-------|
| `id` | `raw.id` + detail fetch key | Integer ID |
| `name` | `title` | NOT `title` |
| `releasedDate` | `posted_date` | ISO 8601 with ms and Z suffix — slice `[:10]` |
| `location.city` | `location` | Combine with `location.region` and `location.country` |
| `location.remote` | Supplement location | Boolean |
| `company.name` | **Company name for detection** | This IS present in list response |
| `typeOfEmployment.label` | `employment_type` | e.g. "Full-time" |
| `department.label` | `department` | |

**Company name for detection gate:** `company.name` IS present in list jobs (`"company": {"name": "Visa", "identifier": "visa"}`). Use this for the rapidfuzz gate — this is the cleanest of all four providers.

**N+1 detail call pattern:** The list response has NO job description. To get description, must call the detail endpoint per job. For v0.4, call detail for ALL jobs from the list (not just top-N). The per-company semaphore governs both list and detail calls. This is the only provider requiring N+1 HTTP calls.

**Detail call in fetch():**
```python
# After list call succeeds:
for job_summary in content:
    job_id = job_summary["id"]
    detail_url = f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{job_id}"
    detail_resp = client.get(detail_url)  # uses same semaphore acquired by fetch()
    detail_resp.raise_for_status()
    detail = detail_resp.json()
    listings.append(to_listing({**job_summary, **detail}))
```

**Description extraction from detail:**
```python
# detail["jobAd"]["sections"]["jobDescription"]["text"] — HTML
# Strip with html.unescape + HTMLParser (same pattern as greenhouse._strip_html)
```

**Rate limit:** SmartRecruiters documents 300 req/min/client. At concurrency cap=5 and ~44 list + ~44 detail = ~88 calls per company, this is fine for the batch size.

**Pagination:** `totalFound` / `limit` tells us page count. For v0.4, fetch only first page (limit=100). Most companies have <100 open roles. Add comment: "pagination not implemented in v0.4 — 100-job limit".

**BOARD_URL_PATTERNS:**
```python
BOARD_URL_PATTERNS = [
    r"^https?://jobs\.smartrecruiters\.com/([^/?#]+)",
    r"^https?://api\.smartrecruiters\.com/v1/companies/([^/?#]+)/postings",
]
```

**Fixture:** `tests/fixtures/ats/smartrecruiters/visa.json` — structure differs from Greenhouse because we need both list and detail. Options:
1. Two separate fixture files: `visa_list.json` and `visa_detail_<id>.json`
2. One combined fixture: `{"list": {...}, "detail": {...}}`

**Recommendation:** Use option 2 — single combined fixture with a `list` key (top-level SR list response) and a `detail` key (one complete detail response). The test mocks both HTTP calls using the fixture. This mirrors how the test will exercise the real code path.

**Acceptance test:** `smartrecruiters.fetch()` makes one list call + N detail calls. `to_listing()` populates `description` from `jobAd.sections.jobDescription.text`. `posted_date` is ISO date from `releasedDate`.

---

### Provider 4: Workday (PRV-04, PRV-05)

**Endpoint (list):** `POST https://{tenant}.wd{N}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs`
**Endpoint (detail):** Not reliably reachable without cookies in v0.4 (see findings below)
**Live-verified:** 2026-04-28 against `workday.wd5.myworkdayjobs.com/Workday` (448 total)

**CRITICAL FINDING — searchText must be non-empty:**
```
# searchText="" -> returns ONLY externalPath + bulletFields (no title, location, or postedOn)
# searchText="a" -> returns title, externalPath, locationsText, postedOn, remoteType, bulletFields
# This behavior was verified live 2026-04-28. Use searchText="a" as the effective "list all".
```

**POST body (correct):**
```python
WORKDAY_LIST_BODY = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "a"}
```

**Key fields (list response with searchText="a"):**
| Field | Maps to | Notes |
|-------|---------|-------|
| `title` | `title` | Direct |
| `externalPath` | `url` construction + `raw` | e.g. `/job/JPNOsaka/Account-Executive_JR-0101360` |
| `locationsText` | `location` | Freeform string e.g. "2 Locations" — acceptable for v0.4 |
| `postedOn` | `posted_date` | **Freeform English** — parse with regex |
| `remoteType` | Supplement | "Onsite"/"Hybrid"/"Flex"/"Remote" |
| `bulletFields[0]` | `raw.job_req_id` | e.g. "JR-0101360" |

**URL construction for apply URL:**
```python
# externalPath = "/job/JPNOsaka/Account-Executive_JR-0101360"
# Full apply URL = "https://{tenant}.wd{N}.myworkdayjobs.com/en-US/{site}{externalPath}"
apply_url = f"https://{tenant}.{dc}.myworkdayjobs.com/en-US/{site}{external_path}"
```
Note: The `/wday/cxs/` detail endpoint is NOT reliably accessible without JS-set cookies. The HTML `en-US/{site}` URL works as an apply URL even if the detail JSON doesn't.

**postedOn parsing (verified 2026-04-28):**
```python
import re
from datetime import date, timedelta

def _parse_workday_posted_on(posted_on: str, today=None) -> str:
    """Parse Workday's freeform English postedOn to ISO date.
    'Posted Today' -> today
    'Posted 6 Days Ago' -> today - 6d
    'Posted 30+ Days Ago' -> today - 30d (lower bound)
    Returns '' if unparseable (do not raise — let age filter handle missing dates).
    """
    if today is None:
        today = date.today()
    posted_on = (posted_on or "").strip()
    if re.search(r'today', posted_on, re.IGNORECASE):
        return today.isoformat()
    m = re.search(r'(\d+)\+?\s+days?\s+ago', posted_on, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        return (today - timedelta(days=days)).isoformat()
    return ""  # Unknown format — age filter will treat as stale if max_age is strict
```

**Tenant URL parsing for detect() and board_url_from_url():**
```python
# Full board URL stored in master_targets.csv ats_board_url:
# "https://workday.wd5.myworkdayjobs.com/Workday"
# OR (with locale): "https://workday.wd5.myworkdayjobs.com/en-US/Workday"
WORKDAY_URL_RE = re.compile(
    r'^https?://([^.]+)\.(wd\d+)\.myworkdayjobs\.com(?:/[a-z]{2}-[A-Z]{2})?/([^/?#]+)'
)
# group(1) = tenant, group(2) = dc (e.g. "wd5"), group(3) = site

def _parse_workday_url(url: str):
    m = WORKDAY_URL_RE.match(url)
    if m:
        return m.group(1), m.group(2), m.group(3)  # tenant, dc, site
    return None, None, None
```

**Detection strategy:** Workday detect() must:
1. Get the `ats_board_url` from master_targets.csv (parsed before detect() is called — the slug for Workday IS the board URL)
2. POST to the CXS endpoint with searchText="a"
3. Require ≥1 job returned (200 + `total > 0`)
4. For name gate: Workday returns no company name in job objects. Use tenant name as proxy:
   ```python
   # tenant = "workday" from URL; company_name = "Workday Inc"
   # normalized tenant ~= normalized company name
   score = fuzz.token_set_ratio(normalize(company_name), normalize(tenant))
   ```

**PRV-05: CSRF/auth-required detection:**
```python
def fetch(slug: str, client, semaphore) -> FetchResult:
    # slug for Workday is the full board URL: "https://workday.wd5.myworkdayjobs.com/Workday"
    tenant, dc, site = _parse_workday_url(slug)
    url = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    with semaphore:
        resp = client.post(url, json=WORKDAY_LIST_BODY)
    
    # CSRF/auth detection (PRV-05)
    if resp.status_code in (401, 403):
        body_lower = resp.text.lower()
        if any(marker in body_lower for marker in ("csrf", "session", "cookie", "authentication")):
            return FetchResult(
                provider=NAME,
                company_slug=slug,
                listings=[],
                raw=[],
                http_status=resp.status_code,
                # Caller sees this as ERROR; runs_log records "workday_auth_required"
            )
        # Non-CSRF 403 — return as generic ERROR
        resp.raise_for_status()
    resp.raise_for_status()
    ...
```

**Note on error reason field:** `FetchResult` doesn't have a `reason` field. The CSRF case is distinguished by the caller (dispatcher._execute_one) seeing a FetchResult with http_status=401/403 AND 0 listings. To make this explicit in runs.jsonl, the dispatcher or a new `FetchResult.auth_required: bool` field should carry the reason. Recommendation: add `auth_required: bool = False` to FetchResult (in base.py). The Workday fetch() sets `auth_required=True` on CSRF/auth 401/403. The dispatcher logs this to runs.jsonl as `{"outcome": "ERROR", "reason": "workday_auth_required"}`.

**BOARD_URL_PATTERNS:**
```python
BOARD_URL_PATTERNS = [
    r"^https?://([^.]+)\.wd\d+\.myworkdayjobs\.com(?:/[a-z]{2}-[A-Z]{2})?/([^/?#]+)",
]
```

**Fixture approach for ≥3 tenants (PRV-04):**
- `workday_wd5.json` — Workday's own board (verified live, wd5)
- Need two more tenants. Research identified `ups.wd1` (returned 422 in live probe — wrong site name) and `meta.wd5` (returned 422). The tenant-identification problem is real.
- **Recommendation:** Use a synthetic fixture approach. Create `workday_synthetic_wd1.json` and `workday_synthetic_wd3.json` with realistic-but-sanitized data derived from the wd5 structure. Include in `SOURCE.md`: "wd1/wd3 fixtures are synthetic (anonymous) because live probes against non-public tenants returned 422 or required CSRF. Shape verified against wd5 live data 2026-04-28."
- The fixture test validates the parsing logic, not the live endpoint. This is the same standard as other fixtures.

---

### Provider 5: JSON-LD Fallback (STR-01)

**Not a real ATS — a virtual sixth provider.** Triggered when `ats_provider="none"` AND `careers_url` is set in master_targets.csv.

**How it works:**
1. HTTP GET the `careers_url`
2. Extract all `<script type="application/ld+json">` blocks via regex
3. `json.loads` each block
4. Filter to objects where `@type == "JobPosting"` (or list containing "JobPosting")
5. Normalize each to a `Listing` with `source="ats:jsonld"`

**Key fields from schema.org/JobPosting:**
| JSON-LD Field | Maps to Listing | Notes |
|---------------|-----------------|-------|
| `title` | `title` | Required — raise if missing |
| `datePosted` | `posted_date` | ISO 8601 date string — slice `[:10]` |
| `hiringOrganization.name` | `company` | Fallback: derive from URL domain |
| `jobLocation.address.addressLocality` + `addressRegion` | `location` | Combine |
| `url` | `url` | Sometimes `@id` instead |
| `description` | `description` | May be HTML — strip tags |
| `employmentType` | `employment_type` | e.g. "FULL_TIME" |

**Extraction regex (verified 2026-04-28):**
```python
import re, json

def _extract_jsonld_jobs(html: str) -> list:
    scripts = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html, re.DOTALL | re.IGNORECASE
    )
    jobs = []
    for s in scripts:
        try:
            obj = json.loads(s.strip())
            if isinstance(obj, dict):
                if obj.get("@type") == "JobPosting":
                    jobs.append(obj)
            elif isinstance(obj, list):
                jobs.extend(o for o in obj if isinstance(o, dict) and o.get("@type") == "JobPosting")
        except (json.JSONDecodeError, ValueError):
            continue
    return jobs
```

**Protocol conformance:** jsonld.py conforms to the Provider Protocol with these adaptations:
- `NAME = "jsonld"`
- `BOARD_URL_PATTERNS = []` — no URL pattern detection (JSON-LD is fallback, not detected)
- `detect()` — always returns `DetectionStatus.NOT_FOUND` (JSON-LD is not a detectable ATS)
- `board_url_from_url()` — returns None always
- `fetch(slug, client, semaphore)` — `slug` is the full careers_url (same pattern as Workday)
- `to_listing(payload)` — maps schema.org/JobPosting dict to Listing

**Triggering in the dispatcher:** The skill code (not the dispatcher) decides to add JSON-LD targets. For each company with `ats_provider="none"` and non-empty `careers_url`, add `(careers_url, "jsonld")` to the targets list. Dispatcher handles it identically to other providers.

**No-JS constraint:** httpx GET only. If the page returns empty `<script type="application/ld+json">` blocks because they're dynamically injected by JS — the fallback returns OK_ZERO. This is correct behavior per STR-01 ("No JS rendering, no Chrome").

**BOARD_URL_PATTERNS:** Empty list. jsonld provider is never auto-detected; it's always explicitly assigned.

---

## Filtering Layer (PRV-06, PRV-07, PRV-08, STR-03)

### Where filtering lives

`scripts/ats/normalize.py` — three new standalone functions added after the `Listing` dataclass. Called by the dispatcher (or preview.py) AFTER `fetch_all()` returns outcomes. Not called inside individual provider `fetch()` or `to_listing()`.

**Why not inside to_listing():** Filters require config values (max_age_days, blocklist patterns) that providers shouldn't need to import. Keeping filters in normalize.py maintains the single-responsibility boundary.

### Filter function signatures

```python
def filter_stale(
    listings: List[Listing],
    max_age_days: int = 60,
    provider_name: str = "",
    provider_overrides: Optional[Dict[str, int]] = None,
    today: Optional[date] = None,
) -> List[Listing]:
    """Drop Listings where posted_date is older than max_age_days.
    
    STR-03: provider_overrides can specify per-provider age like
    {"workday": 90, "greenhouse": 30}. Falls back to max_age_days.
    
    Listings with empty posted_date are kept (no date = cannot filter).
    """
    ...

def collapse_regional_dupes(listings: List[Listing]) -> List[Listing]:
    """PRV-07: Collapse same-role regional duplicates within one provider+company.
    
    Groups by (source, company, _normalize_title(title)).
    Merged listing takes: earliest posted_date, union of locations,
    url of first (arbitrary ordering).
    
    Listing is frozen — creates new Listing objects with locations as
    a comma-joined string (Listing.location field).
    """
    ...

def filter_evergreen(
    listings: List[Listing],
    blocklist_re: Optional[re.Pattern] = None,
) -> List[Listing]:
    """PRV-08: Drop listings matching the evergreen title blocklist.
    
    Default pattern covers: 'general application|talent network|
    future opportunities|join our team|connect with us|expression of interest'.
    Pattern is case-insensitive anchored at start of normalized title.
    blocklist_re can be overridden for testing.
    """
    ...
```

### STR-03: config.json schema for per-provider age overrides

```json
{
  "ats": {
    "posted_date_max_age_days": 60,
    "provider_posted_date_overrides": {
      "workday": 90,
      "greenhouse": 30
    },
    "concurrency_disabled": false,
    "provider_concurrency_caps": {...}
  }
}
```

The `dispatcher.load_caps_and_kill_switch()` function should be extended (or a new helper added) to also read `ats.posted_date_max_age_days` and `ats.provider_posted_date_overrides`.

### PRV-07: Regional collapse normalization key

```python
def _normalize_title(title: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace.
    'Sr. Software Engineer - NY' -> 'sr software engineer  ny'
    Used as the grouping key for regional collapse ONLY (not for dedup).
    """
    import re
    t = title.casefold()
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()
```

### PRV-08: Evergreen blocklist pattern (lives in references/ats-providers.md)

```
Default evergreen blocklist (case-insensitive, matched at start of normalized title):
- general application
- talent network
- future opportunities
- join our team
- connect with us
- expression of interest
- always hiring
- passive candidate
```

Regex: `^(general application|talent network|future opportunities|join our team|connect with us|expression of interest|always hiring|passive candidate)`

This pattern set lives in `skills/job-scout/references/ats-providers.md` (create new file if it doesn't exist). The pattern is also hardcoded as the default in `normalize.filter_evergreen()` so the function works without reading the file.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead |
|---------|-------------|-------------|
| HTML stripping for Lever/SR descriptions | Custom parser | Reuse greenhouse.py's `_strip_html()` (html.unescape + HTMLParser) — same pattern |
| Workday authentication flow | Any CSRF token harvesting | Return ERROR with auth_required=True; let it fall to Pass 2 |
| Ashby pagination | Cursor-based page fetcher | Current API returns all results in one call; add comment noting assumption |
| JSON-LD rendering | Chrome/Playwright | httpx GET only — if page needs JS, OK_ZERO is correct |
| Title normalization | Separate library | Simple regex in normalize.py (same as detect.py's `_normalize_for_match`) |
| Company name extraction for detection | ATS-specific heuristic | Extract slug from hostedUrl/jobUrl — deterministic, regex-based |
| Date parsing for Workday | dateutil or arrow | stdlib re + datetime — the pattern set is small and fixed |

---

## Common Pitfalls

### Pitfall 1: Workday searchText="" returns no title fields
**What goes wrong:** Empty searchText gives only `externalPath` + `bulletFields`. The title field is missing. `to_listing()` raises ValueError (required field). All Workday companies show as ERROR.
**How to avoid:** Always use `searchText="a"` in `WORKDAY_LIST_BODY`. This is verified to return all fields. Document in a module-level constant with a comment explaining why.
**Warning signs:** All Workday FetchOutcomes are ERROR with "title" mentioned in error message.

### Pitfall 2: Workday detail endpoint is not accessible
**What goes wrong:** The `/wday/cxs/{tenant}/{site}/job/{id}` endpoint returns 404. Developer wastes time building detail-call logic.
**How to avoid:** In v0.4, use ONLY the list call with searchText="a". Description is unavailable without JS cookies. Set `Listing.description = ""` for Workday. This is acceptable — description is optional. Add a comment in workday.py noting this limitation.
**Warning signs:** Tests show 404 on detail URL; correct response is to not attempt detail calls.

### Pitfall 3: Ashby isListed=False jobs flood results
**What goes wrong:** Ashby returns unlisted internal draft jobs. They appear with no apply URL. User gets confused by stale or internal roles.
**How to avoid:** Filter `isListed == False` in `fetch()` before calling `to_listing()`. This is PRV-02's explicit requirement. Add an assertion in the fixture test.

### Pitfall 4: Lever's createdAt is epoch milliseconds (not seconds)
**What goes wrong:** `datetime.fromtimestamp(1773335421350)` overflows on some systems or produces year ~58,000. Correct: divide by 1000 first.
**How to avoid:**
```python
epoch_ms = job.get("createdAt") or 0
posted_date = date.fromtimestamp(epoch_ms / 1000).isoformat() if epoch_ms else ""
```

### Pitfall 5: SmartRecruiters detail semaphore double-acquire deadlock
**What goes wrong:** `fetch()` acquires the semaphore once for the list call, then tries to acquire it again for each detail call inside the same function. `threading.Semaphore` is NOT re-entrant. Deadlock.
**How to avoid:** The semaphore is passed into `fetch()` as an argument. For SmartRecruiters, both list call and detail calls run within a single `with semaphore:` context. The implementation must structure this correctly:
```python
def fetch(slug, client, semaphore):
    with semaphore:
        list_resp = client.get(list_url)
        ...
        for job in content:
            detail_resp = client.get(detail_url)  # still within same with block
            ...
```
Alternatively, acquire once, do all calls, release. Do NOT nest `with semaphore:`.

### Pitfall 6: Workday tenant URL slug is NOT the company slug
**What goes wrong:** detect.py derives slug as `_derive_slug("Microsoft")` = `microsoft`. Calls `_execute_one("microsoft", "workday", client)`. But Workday's `fetch()` expects the full board URL as slug, not a company name slug. Dispatcher has no board URL.
**How to avoid:** Workday is a special case. The `fetch()` function receives `slug` which for Workday is the full `ats_board_url` (e.g. `"https://workday.wd5.myworkdayjobs.com/Workday"`). This is consistent with how jsonld.py uses the careers_url as the slug. Ensure the dispatcher targets list uses the full ats_board_url for Workday entries. Document this in workday.py's module docstring.

### Pitfall 7: JSON-LD `@type` can be a list
**What goes wrong:** `obj.get("@type") == "JobPosting"` misses objects where `@type` is a list like `["JobPosting", "Thing"]`.
**How to avoid:**
```python
def _is_job_posting(obj):
    t = obj.get("@type", "")
    if isinstance(t, str):
        return t == "JobPosting"
    return "JobPosting" in t
```

### Pitfall 8: Regional collapse creates Listing with empty location after merging
**What goes wrong:** `collapse_regional_dupes()` merges "New York" + "San Francisco" into one Listing. The Listing constructor requires non-empty location. If `", ".join(locations)` produces "" (e.g. all locations were empty strings), the Listing raises.
**How to avoid:** Filter empty location strings before join; fall back to "Multiple Locations" if all empty.

---

## Code Examples

### Lever to_listing() (verified field mapping)

```python
# Source: live probe 2026-04-28 + STACK.md MEDIUM-HIGH confidence
def to_listing(payload: Dict[str, Any]) -> Listing:
    title = (payload.get("text") or "").strip()
    url = (payload.get("hostedUrl") or "").strip()
    cats = payload.get("categories") or {}
    location = (cats.get("location") or "").strip()
    
    epoch_ms = payload.get("createdAt") or 0
    try:
        posted_date = date.fromtimestamp(epoch_ms / 1000).isoformat() if epoch_ms else ""
    except (OSError, ValueError):
        posted_date = ""
    
    description = _strip_html_or_plain(payload)  # prefer descriptionPlain
    department = (cats.get("department") or "").strip()
    employment_type = (cats.get("commitment") or "").strip()
    
    return Listing(
        company=...,  # derived from hostedUrl slug or passed separately
        title=title, location=location, url=url,
        posted_date=posted_date, source="ats:lever",
        description=description, department=department,
        employment_type=employment_type, raw=payload,
    )
```

### Workday posted_date parsing (verified 2026-04-28)

```python
import re
from datetime import date, timedelta

def _parse_workday_posted_on(posted_on: str, today=None) -> str:
    if today is None:
        today = date.today()
    s = (posted_on or "").strip()
    if re.search(r'today', s, re.IGNORECASE):
        return today.isoformat()
    m = re.search(r'(\d+)\+?\s+days?\s+ago', s, re.IGNORECASE)
    if m:
        days = int(m.group(1))
        return (today - timedelta(days=days)).isoformat()
    return ""  # "Posted X Months Ago" etc — return empty, let age filter handle
```

### JSON-LD extraction (verified 2026-04-28)

```python
def _extract_jsonld_jobs(html: str) -> List[Dict]:
    pattern = re.compile(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE
    )
    jobs = []
    for m in pattern.finditer(html):
        try:
            obj = json.loads(m.group(1).strip())
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict) and _is_job_posting(obj):
            jobs.append(obj)
        elif isinstance(obj, list):
            jobs.extend(o for o in obj if isinstance(o, dict) and _is_job_posting(o))
    return jobs
```

### filter_stale() with per-provider override (STR-03)

```python
def filter_stale(listings, max_age_days=60, provider_name="", provider_overrides=None, today=None):
    if today is None:
        today = date.today()
    overrides = provider_overrides or {}
    effective_max = overrides.get(provider_name, max_age_days)
    cutoff = today - timedelta(days=effective_max)
    result = []
    for listing in listings:
        if not listing.posted_date:
            result.append(listing)  # keep when date unknown
            continue
        try:
            pd = date.fromisoformat(listing.posted_date)
            if pd >= cutoff:
                result.append(listing)
        except ValueError:
            result.append(listing)  # keep on parse error
    return result
```

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (already installed in ~/.job-scout-venv) |
| Config file | none — run via `~/.job-scout-venv/bin/python3 -m pytest` |
| Quick run command | `~/.job-scout-venv/bin/python3 -m pytest tests/test_providers_phase4.py -x -q` |
| Full suite command | `~/.job-scout-venv/bin/python3 -m pytest tests/ -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PRV-01 | lever.to_listing() maps all fields from fixture | unit | `pytest tests/test_providers_phase4.py::test_lever_to_listing -x` | Wave 0 |
| PRV-01 | lever createdAt epoch_ms -> ISO date | unit | `pytest tests/test_providers_phase4.py::test_lever_posted_date_epoch -x` | Wave 0 |
| PRV-02 | ashby.fetch() skips isListed=False jobs | unit | `pytest tests/test_providers_phase4.py::test_ashby_filters_unlisted -x` | Wave 0 |
| PRV-02 | ashby.to_listing() maps all fields from fixture | unit | `pytest tests/test_providers_phase4.py::test_ashby_to_listing -x` | Wave 0 |
| PRV-03 | smartrecruiters.to_listing() maps name->title, company.name->company | unit | `pytest tests/test_providers_phase4.py::test_sr_to_listing -x` | Wave 0 |
| PRV-03 | smartrecruiters fixture includes detail call result | unit | `pytest tests/test_providers_phase4.py::test_sr_description_from_detail -x` | Wave 0 |
| PRV-04 | workday.to_listing() maps title/locationsText/postedOn->ISO | unit | `pytest tests/test_providers_phase4.py::test_workday_to_listing -x` | Wave 0 |
| PRV-04 | workday.to_listing() handles "Posted Today" / "Posted 6 Days Ago" | unit | `pytest tests/test_providers_phase4.py::test_workday_posted_on_parsing -x` | Wave 0 |
| PRV-05 | workday.fetch() returns FetchResult(auth_required=True) on 401 + csrf body | unit | `pytest tests/test_providers_phase4.py::test_workday_csrf_detection -x` | Wave 0 |
| PRV-06 | filter_stale() drops listings older than max_age_days | unit | `pytest tests/test_providers_phase4.py::test_filter_stale -x` | Wave 0 |
| PRV-07 | collapse_regional_dupes() merges same-title different-location listings | unit | `pytest tests/test_providers_phase4.py::test_collapse_regional_dupes -x` | Wave 0 |
| PRV-08 | filter_evergreen() drops "Talent Network" / "General Application" | unit | `pytest tests/test_providers_phase4.py::test_filter_evergreen -x` | Wave 0 |
| PRV-09 | PROVIDERS dict has 5 entries after Phase 4 | unit | `pytest tests/test_providers_phase4.py::test_providers_registry_has_five -x` | Wave 0 |
| STR-01 | jsonld._extract_jsonld_jobs() parses schema.org/JobPosting | unit | `pytest tests/test_providers_phase4.py::test_jsonld_extraction -x` | Wave 0 |
| STR-03 | filter_stale() uses per-provider override from provider_overrides dict | unit | `pytest tests/test_providers_phase4.py::test_filter_stale_per_provider_override -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `~/.job-scout-venv/bin/python3 -m pytest tests/test_providers_phase4.py -x -q`
- **Per wave merge:** `~/.job-scout-venv/bin/python3 -m pytest tests/ -q`
- **Phase gate:** Full suite green (`22+ tests` from Phase 3 + new Phase 4 tests)

### Wave 0 Gaps
- [ ] `tests/test_providers_phase4.py` — all PRV-01..09, STR-01, STR-03 unit tests
- [ ] `tests/fixtures/ats/lever/spotify.json` — bare array, 3 jobs
- [ ] `tests/fixtures/ats/lever/__init__.py` — empty package marker
- [ ] `tests/fixtures/ats/ashby/ashby.json` — includes at least 1 isListed=False job
- [ ] `tests/fixtures/ats/ashby/__init__.py` — empty package marker
- [ ] `tests/fixtures/ats/smartrecruiters/visa.json` — combined list+detail fixture
- [ ] `tests/fixtures/ats/smartrecruiters/__init__.py` — empty package marker
- [ ] `tests/fixtures/ats/workday/workday_wd5.json` — searchText="a" response, 3 jobs
- [ ] `tests/fixtures/ats/workday/__init__.py` — empty package marker
- [ ] `tests/fixtures/ats/workday/SOURCE.md` — fixture provenance

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Workday searchText="" | searchText="a" required for title fields | Must change implementation from research assumption |
| Detail URL `/wday/cxs/.../job{externalPath}` | Detail URL not reliably accessible without JS cookies | Don't implement detail calls in v0.4; description="" for Workday |
| Ashby cursor pagination | No pagination field in current API response | No pagination needed; drop pagination code |
| Lever company_name in API response | Not present; derive from hostedUrl | Detection uses URL slug for name gate |
| Ashby company_name in API response | Not present; derive from jobUrl | Detection uses URL slug for name gate |

---

## Open Questions

1. **FetchResult.auth_required field: add to base.py or handle differently?**
   - What we know: FetchResult is a frozen dataclass; Workday CSRF case needs to communicate "this is auth-required, not just error"
   - What's unclear: Adding a field to FetchResult (base.py) changes the Protocol contract; all existing providers need to either pass the new field or use default
   - Recommendation: Add `auth_required: bool = False` to FetchResult in base.py with a default value. All existing providers get the field automatically with default False. Workday sets `auth_required=True` on CSRF 401/403. Dispatcher reads it and writes "workday_auth_required" reason to runs.jsonl. **Requires plan to update base.py.**

2. **Where does filter_stale/collapse/evergreen get called in the current pipeline?**
   - What we know: `preview.py` currently calls `fetch_all()` directly and writes ats_raw. The dispatcher returns `List[FetchOutcome]`.
   - What's unclear: The filtering functions operate on `List[Listing]`; they need to be called between fetch and report rendering.
   - Recommendation: Call filters in `preview.py` after `fetch_all()` returns, before writing ats_raw or rendering report. Add a `apply_filters(outcomes, config) -> List[FetchOutcome]` helper in normalize.py that takes outcomes, applies all three filters, and returns modified outcomes.

3. **JSON-LD as PROVIDERS entry vs. separate code path?**
   - What we know: JSON-LD has no detection pattern and is only triggered for ats_provider="none" companies with careers_url set.
   - What's unclear: If jsonld is in PROVIDERS, detect.py will probe it for every company (and always get NOT_FOUND). If it's separate, it bypasses the registry.
   - Recommendation: Put jsonld in PROVIDERS with an empty BOARD_URL_PATTERNS. The detect.py loop skips providers whose BOARD_URL_PATTERNS is empty before attempting a network call. This keeps the registry as single source of truth while avoiding spurious detection probes. **Requires detect.py to skip providers with empty BOARD_URL_PATTERNS.**

4. **Workday fixture coverage for ≥3 tenants (PRV-04):**
   - What we know: wd5 verified live. UPS (wd1) returned 422 with wrong site name. Meta (wd5) returned 422. Boeing (wd1) returned 404 wrong site name.
   - What's unclear: Which wd1 and wd3 tenants have publicly-accessible boards with correct site names?
   - Recommendation: Use synthetic fixtures for wd1/wd3. The parsing logic is identical across data centers; what varies is only the tenant/dc/site URL components. Synthetic fixtures with realistic job shapes adequately test the parsing code. Document in SOURCE.md.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| httpx | All providers | ✓ | 0.28.1 | — |
| rapidfuzz | Detection gate | ✓ | latest | — |
| pytest | Test runner | ✓ | 9.0.3 | — |
| stdlib re, json, html, datetime | Parsing | ✓ | built-in | — |

No missing dependencies.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | All ATS calls are read-only public endpoints |
| V3 Session Management | No | No sessions; stateless HTTP per run |
| V4 Access Control | No | No user-facing access control |
| V5 Input Validation | Yes | Workday CSRF detection uses body substring matching — validate response body is string before matching |
| V6 Cryptography | No | No secrets; no crypto |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| ATS response body containing malicious content in job description | Tampering (via HTML injection into report) | `_strip_html()` already strips all tags; Listing.description is plain text only |
| Malformed JSON from ATS endpoints | Tampering | `json.JSONDecodeError` caught by dispatcher._execute_one; buckets as ERROR |
| Workday 401/403 body substring check on untrusted input | Information Disclosure | Only log the reason code ("workday_auth_required"), never the full 403 body |
| careers_url pointing to a non-careers page (for JSON-LD) | Spoofing | JSON-LD only extracts `@type=JobPosting` objects; non-job pages return empty |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Ashby's public REST API returns all results in one call (no pagination) | PRV-02 | If Ashby has added cursor pagination post-2026-04, large boards will return partial results. Mitigation: check for `moreDataAvailable` or `nextCursor` in response and log a WARNING if present. |
| A2 | Workday detail endpoint (`/wday/cxs/.../job/{id}`) is not accessible without JS cookies | PRV-04 | Verified for workday.wd5 tenant; may differ for other tenants. If a tenant exposes the detail endpoint, we're leaving description data on the table. |
| A3 | searchText="a" consistently returns all 448 jobs from the Workday board (same count as searchText="") | PRV-04 | If Workday's search algorithm filters out some jobs, we'd miss them. The live probe showed 447/448 match on searchText="a". Risk is low. |
| A4 | Lever company name is derivable from hostedUrl slug with sufficient accuracy for the 85% gate | PRV-01 | If the hostedUrl slug doesn't match the company name (e.g. "acme-engineering" for "Acme Inc"), gate may fail. Mitigation: use token_set_ratio which handles partial matches well. |
| A5 | Synthetic wd1/wd3 Workday fixtures adequately test the parsing code | PRV-04 | If there are wd1/wd3 specific response shape differences, fixture tests won't catch them. Risk is low — field names are the same across tenants. |

---

## Sources

### Primary (HIGH confidence)

- Lever postings-api GitHub repo + live probe 2026-04-28 (`spotify` slug: 191 jobs confirmed)
- Ashby Public Job Posting API docs + live probe 2026-04-28 (`ashby` slug: 63 jobs confirmed)
- SmartRecruiters Posting API docs + live probe 2026-04-28 (`visa` slug: 44 jobs, detail call confirmed)
- Workday CXS endpoint live probe 2026-04-28 (workday.wd5: 448 jobs; searchText="" vs "a" behavior verified)
- Existing codebase: `scripts/ats/providers/greenhouse.py`, `scripts/ats/providers/base.py`, `scripts/ats/normalize.py`, `scripts/ats/dispatcher.py`
- `.planning/research/STACK.md` — all five endpoint shapes, live-verified 2026-04-27
- `.planning/research/PITFALLS.md` — pitfalls 6, 7, 8 for Workday, schema drift, and stale/regional/evergreen filtering

### Secondary (MEDIUM confidence)

- `.planning/research/FEATURES.md` — feature matrix, D-1 (JSON-LD), D-3 (posted-date filter) design rationale
- `.planning/research/SUMMARY.md` — reconciled findings, per-provider concurrency caps
- jobo.world/ats/workday — Workday POST body shape, `{tenant}.wd{N}.myworkdayjobs.com` URL pattern

### Tertiary (LOW confidence)

- Workday CSRF/session-token detection patterns — community-sourced; not official Workday docs. The body-substring approach ("csrf", "session", "cookie") is the best available heuristic. Validate against live CSRF tenant during execution.

---

## Metadata

**Confidence breakdown:**
- Lever: HIGH — live-verified endpoint, all fields confirmed
- Ashby: HIGH — live-verified; no pagination in current API confirmed
- SmartRecruiters: HIGH — live-verified including N+1 detail call
- Workday: MEDIUM-HIGH — searchText behavior verified live; detail endpoint limitation confirmed; CSRF pattern is community-sourced
- JSON-LD: HIGH — standard schema.org parsing; regex extraction verified 2026-04-28
- Filtering layer: HIGH — pure Python stdlib; no external dependencies

**Research date:** 2026-04-28
**Valid until:** 2026-05-28 (30 days — endpoints are stable but Workday tenant behavior may vary)

# Phase 4: Remaining Providers + JSON-LD + Filtering Layer — Pattern Map

**Mapped:** 2026-04-28
**Files analyzed:** 16 new/modified files (4 provider modules, 1 virtual provider, 3 registry/infra modifications, 3 filter helpers, 1 test file, fixture dirs, config)
**Analogs found:** 16 / 16 (all files have a strong primary analog in the codebase)

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/ats/providers/lever.py` | provider | request-response | `scripts/ats/providers/greenhouse.py` | exact |
| `scripts/ats/providers/ashby.py` | provider | request-response | `scripts/ats/providers/greenhouse.py` | exact |
| `scripts/ats/providers/smartrecruiters.py` | provider | request-response (N+1) | `scripts/ats/providers/greenhouse.py` | exact |
| `scripts/ats/providers/workday.py` | provider | request-response (POST) | `scripts/ats/providers/greenhouse.py` | exact |
| `scripts/ats/providers/jsonld.py` | virtual provider | request-response (HTML parse) | `scripts/ats/providers/greenhouse.py` | role-match |
| `scripts/ats/providers/base.py` | protocol/dataclass | N/A | `scripts/ats/providers/base.py` (self) | exact (additive) |
| `scripts/ats/__init__.py` | registry | N/A | `scripts/ats/__init__.py` (self) | exact (additive) |
| `scripts/ats/normalize.py` | utility | transform | `scripts/ats/normalize.py` (self) | exact (additive) |
| `scripts/ats/preview.py` | driver | batch | `scripts/ats/preview.py` (self) | exact (additive) |
| `scripts/ats/detect.py` | CLI | request-response | `scripts/ats/detect.py` (self) | exact (additive) |
| `tests/test_providers_phase4.py` | test | N/A | `tests/test_detection.py` | exact |
| `tests/fixtures/ats/lever/spotify.json` | fixture | N/A | `tests/fixtures/ats/greenhouse/airbnb.json` | exact |
| `tests/fixtures/ats/ashby/ashby.json` | fixture | N/A | `tests/fixtures/ats/greenhouse/airbnb.json` | exact |
| `tests/fixtures/ats/smartrecruiters/visa.json` | fixture | N/A | `tests/fixtures/ats/greenhouse/airbnb.json` | role-match |
| `tests/fixtures/ats/workday/workday_wd5.json` | fixture | N/A | `tests/fixtures/ats/greenhouse/airbnb.json` | role-match |
| `templates/config.json` | config | N/A | `templates/config.json` (self) | exact (additive) |

---

## Pattern Assignments

### `scripts/ats/providers/lever.py` (provider, request-response)

**Analog:** `scripts/ats/providers/greenhouse.py`

**Module docstring pattern** (lines 1-22):
```python
"""
lever.py — Lever public Job Board API conformer.

API endpoint (verified live 2026-04-28):
    GET https://api.lever.co/v0/postings/{slug}?mode=json

Response: bare JSON ARRAY (NOT an object with a "jobs" key).

Per-job keys consumed by to_listing():
    id, text, hostedUrl, createdAt (epoch ms), categories.location,
    categories.allLocations, categories.department, categories.commitment,
    descriptionPlain

Company name detection: Lever has NO company_name field. detect() extracts
the slug from hostedUrl via regex for the rapidfuzz name gate.

Per-provider concurrency cap: 5 (dispatcher.DEFAULT_PROVIDER_CAPS).
"""
```

**Imports pattern** (lines 23-51 of greenhouse.py):
```python
import html
import os
import re
import sys
from datetime import date
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

# Sibling-script bootstrap (3-level — file → providers → ats → scripts).
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from ats.normalize import Listing  # noqa: E402
from ats.providers.base import (  # noqa: E402
    DetectionResult,
    DetectionStatus,
    FetchResult,
)

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore
```

**Module-level constants pattern** (lines 54-68 of greenhouse.py):
```python
NAME = "lever"

BOARD_URL_PATTERNS = [
    r"^https?://jobs\.lever\.co/([^/?#]+)",
    r"^https?://api\.lever\.co/v0/postings/([^/?#]+)",
]

LIST_URL_TEMPLATE = "https://api.lever.co/v0/postings/{slug}?mode=json"

_COMPILED_PATTERNS = [re.compile(p) for p in BOARD_URL_PATTERNS]
```

**detect() pattern** (lines 138-220 of greenhouse.py — adapt for Lever slug extraction):

Lever has no company_name in job objects. Extract returned slug from `hostedUrl`:
```python
def detect(company_slug: str, name: str, client: "httpx.Client") -> DetectionResult:
    # ... httpx None guard identical to greenhouse.py lines 152-159 ...
    url = LIST_URL_TEMPLATE.format(slug=company_slug)
    try:
        resp = client.get(url)
    except httpx.HTTPError as exc:
        return DetectionResult(provider=NAME, status=DetectionStatus.ERROR,
                               board_url=None, confidence=0.0,
                               evidence={"error": f"{type(exc).__name__}: {exc}"})
    if resp.status_code == 404:
        return DetectionResult(provider=NAME, status=DetectionStatus.NOT_FOUND,
                               board_url=None, confidence=0.0,
                               evidence={"http_status": 404})
    if resp.status_code != 200:
        return DetectionResult(provider=NAME, status=DetectionStatus.ERROR,
                               board_url=None, confidence=0.0,
                               evidence={"http_status": resp.status_code})
    jobs = resp.json() or []  # Lever returns a bare array, not {"jobs": [...]}
    if not jobs:
        return DetectionResult(provider=NAME, status=DetectionStatus.BORDERLINE,
                               board_url=url, confidence=0.5,
                               evidence={"http_status": 200, "job_count": 0})
    # Extract returned company slug from hostedUrl for name gate
    m = re.search(r'jobs\.lever\.co/([^/]+)/', jobs[0].get("hostedUrl", ""))
    returned_slug = m.group(1) if m else ""
    return DetectionResult(
        provider=NAME, status=DetectionStatus.BORDERLINE, board_url=url, confidence=0.85,
        evidence={"http_status": 200, "job_count": len(jobs),
                  "first_job_company_name": returned_slug,  # used by _apply_name_gate
                  "first_job_title": jobs[0].get("text", "")},
    )
```

**fetch() pattern** (lines 223-281 of greenhouse.py — critical adaptation for bare array):
```python
def fetch(slug: str, client: "httpx.Client", semaphore) -> FetchResult:
    url = LIST_URL_TEMPLATE.format(slug=slug)
    with semaphore:
        resp = client.get(url)
    if resp.status_code == 404:
        return FetchResult(provider=NAME, company_slug=slug, listings=[], raw=[], http_status=404)
    resp.raise_for_status()
    raw_jobs = resp.json() or []  # bare array — NOT data.get("jobs", [])
    listings: List[Listing] = []
    for raw_job in raw_jobs:
        try:
            listings.append(to_listing(raw_job))
        except ValueError as exc:
            print(f"WARNING: lever/{slug}: job id={raw_job.get('id')} dropped: {exc}",
                  file=sys.stderr)
            continue
    return FetchResult(provider=NAME, company_slug=slug, listings=listings,
                       raw=raw_jobs, http_status=resp.status_code)
```

**CRITICAL: semaphore usage in fetch().** Unlike greenhouse.py (lines 223-281 where `semaphore` is passed in but Greenhouse wraps internally via `_gate`), for Phase 4 providers the semaphore is acquired with `with semaphore:` directly in the fetch() body. This keeps all HTTP calls inside a single acquire/release (avoids the SmartRecruiters deadlock — see Pitfall 5 in RESEARCH.md).

**to_listing() pattern — Lever-specific fields** (adapt from greenhouse.py lines 284-348):
```python
def to_listing(payload: Dict[str, Any]) -> Listing:
    title = (payload.get("text") or "").strip()         # "text" not "title"
    url = (payload.get("hostedUrl") or "").strip()
    cats = payload.get("categories") or {}
    location = (cats.get("location") or "").strip()
    department = (cats.get("department") or "").strip()
    employment_type = (cats.get("commitment") or "").strip()

    # CRITICAL: createdAt is epoch MILLISECONDS — divide by 1000 before fromtimestamp
    epoch_ms = payload.get("createdAt") or 0
    try:
        posted_date = date.fromtimestamp(epoch_ms / 1000).isoformat() if epoch_ms else ""
    except (OSError, ValueError):
        posted_date = ""

    description = _strip_html(payload.get("descriptionPlain") or payload.get("description"))

    # Extract company from hostedUrl slug (no company_name field in Lever)
    m = re.search(r'jobs\.lever\.co/([^/]+)/', url)
    company = m.group(1) if m else slug  # caller passes slug as fallback

    return Listing(
        company=company, title=title, location=location, url=url,
        posted_date=posted_date, source="ats:lever",
        description=description, department=department,
        employment_type=employment_type, raw=payload,
    )
```

**Error handling:** Identical to greenhouse.py — `resp.raise_for_status()` for non-2xx non-404; per-job `ValueError` from `Listing.__post_init__` caught and logged, job skipped.

---

### `scripts/ats/providers/ashby.py` (provider, request-response)

**Analog:** `scripts/ats/providers/greenhouse.py`

**Module-level constants:**
```python
NAME = "ashby"

BOARD_URL_PATTERNS = [
    r"^https?://jobs\.ashbyhq\.com/([^/?#]+)",
    r"^https?://api\.ashbyhq\.com/posting-api/job-board/([^/?#]+)",
]

LIST_URL_TEMPLATE = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"
```

**detect() — company name from jobUrl** (same structure as greenhouse.py detect() but different name extraction):
```python
# Ashby has no company_name in job objects. Extract slug from jobUrl:
# jobUrl = "https://jobs.ashbyhq.com/ashby/145ff46b-..."
m = re.search(r'jobs\.ashbyhq\.com/([^/]+)/', jobs[0].get("jobUrl", ""))
returned_slug = m.group(1) if m else ""
# Pass as first_job_company_name so _apply_name_gate can score it
evidence={"http_status": 200, "job_count": len(jobs),
           "first_job_company_name": returned_slug, ...}
```

**CRITICAL: case-sensitive slug.** The slug from `jobs.ashbyhq.com/{slug}` must preserve its original casing (e.g. `Ashby` not `ashby`). Extract from the ats_board_url column, not from `_derive_slug(company_name)`.

**fetch() — isListed filter** (inner loop adaptation):
```python
raw_jobs = data.get("jobs", []) or []
listings = []
for raw_job in raw_jobs:
    # PRV-02 LOCKED: drop unlisted jobs before to_listing()
    if not raw_job.get("isListed", True):
        continue
    try:
        listings.append(to_listing(raw_job))
    except ValueError as exc:
        print(f"WARNING: ashby/{slug}: dropped: {exc}", file=sys.stderr)
        continue
```

**to_listing() — Ashby field mapping:**
```python
def to_listing(payload: Dict[str, Any]) -> Listing:
    title = (payload.get("title") or "").strip()
    url = (payload.get("jobUrl") or "").strip()
    location = (payload.get("location") or "").strip()
    # publishedAt is ISO 8601 with timezone: "2026-03-15T10:23:45Z" -> "2026-03-15"
    published_at = payload.get("publishedAt") or ""
    posted_date = published_at[:10] if len(published_at) >= 10 else ""
    department = (payload.get("department") or "").strip()
    # employmentType: "FullTime" -> normalize to "Full-time"
    et_raw = (payload.get("employmentType") or "").strip()
    employment_type = {"FullTime": "Full-time", "PartTime": "Part-time",
                       "Contract": "Contract", "Internship": "Internship"}.get(et_raw, et_raw)
    description = _strip_html(payload.get("descriptionPlain") or payload.get("descriptionHtml"))
    # company from jobUrl slug (no company_name field)
    m = re.search(r'jobs\.ashbyhq\.com/([^/]+)/', url)
    company = m.group(1) if m else slug
    return Listing(
        company=company, title=title, location=location, url=url,
        posted_date=posted_date, source="ats:ashby",
        description=description, department=department,
        employment_type=employment_type, raw=payload,
    )
```

**No pagination comment** (add at top of fetch()):
```python
# NOTE: Ashby REST posting-api returns all results in one call as of 2026-04-28.
# No pagination fields (moreDataAvailable, nextCursor) observed in API response.
# If Ashby adds pagination, a WARNING log will appear here. — v0.4 assumption A1.
```

---

### `scripts/ats/providers/smartrecruiters.py` (provider, request-response N+1)

**Analog:** `scripts/ats/providers/greenhouse.py`

**Module-level constants:**
```python
NAME = "smartrecruiters"

BOARD_URL_PATTERNS = [
    r"^https?://jobs\.smartrecruiters\.com/([^/?#]+)",
    r"^https?://api\.smartrecruiters\.com/v1/companies/([^/?#]+)/postings",
]

LIST_URL_TEMPLATE = "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset=0"
DETAIL_URL_TEMPLATE = "https://api.smartrecruiters.com/v1/companies/{slug}/postings/{job_id}"
```

**detect() — company name IS present:**
```python
# SmartRecruiters includes company.name in list response — cleanest of all providers
jobs = data.get("content", []) or []
returned_name = jobs[0].get("company", {}).get("name", "") if jobs else ""
evidence={"http_status": 200, "job_count": data.get("totalFound", 0),
           "first_job_company_name": returned_name, ...}
```

**CRITICAL: N+1 fetch pattern with semaphore inside single with block** (Pitfall 5):
```python
def fetch(slug: str, client: "httpx.Client", semaphore) -> FetchResult:
    list_url = LIST_URL_TEMPLATE.format(slug=slug)
    with semaphore:  # Acquire ONCE; all list + detail calls happen within this block
        list_resp = client.get(list_url)
        if list_resp.status_code == 404:
            return FetchResult(provider=NAME, company_slug=slug, listings=[], raw=[], http_status=404)
        list_resp.raise_for_status()
        data = list_resp.json()
        content = data.get("content", []) or []
        # NOTE: pagination not implemented in v0.4 — 100-job limit per company
        raw_jobs = []
        listings = []
        for job_summary in content:
            job_id = job_summary.get("id")
            detail_url = DETAIL_URL_TEMPLATE.format(slug=slug, job_id=job_id)
            detail_resp = client.get(detail_url)  # still within with semaphore:
            detail_resp.raise_for_status()
            detail = detail_resp.json()
            merged = {**job_summary, **detail}
            raw_jobs.append(merged)
            try:
                listings.append(to_listing(merged))
            except ValueError as exc:
                print(f"WARNING: smartrecruiters/{slug}: dropped: {exc}", file=sys.stderr)
                continue
    return FetchResult(provider=NAME, company_slug=slug, listings=listings,
                       raw=raw_jobs, http_status=list_resp.status_code)
```

**to_listing() — SmartRecruiters field mapping:**
```python
def to_listing(payload: Dict[str, Any]) -> Listing:
    title = (payload.get("name") or "").strip()          # "name" not "title"
    url = (payload.get("ref") or "").strip()             # apply URL
    company = (payload.get("company", {}).get("name") or "").strip()

    # releasedDate: "2026-03-15T10:23:45.000Z" -> "2026-03-15"
    released = payload.get("releasedDate") or ""
    posted_date = released[:10] if len(released) >= 10 else ""

    # Location: combine city + region + country + remote flag
    loc = payload.get("location") or {}
    loc_parts = [loc.get("city"), loc.get("region"), loc.get("country")]
    location = ", ".join(p for p in loc_parts if p)
    if not location and loc.get("remote"):
        location = "Remote"

    department = (payload.get("department", {}).get("label") or "").strip()
    employment_type = (payload.get("typeOfEmployment", {}).get("label") or "").strip()

    # Description from detail response: jobAd.sections.jobDescription.text (HTML)
    job_ad = payload.get("jobAd") or {}
    sections = job_ad.get("sections") or {}
    desc_html = (sections.get("jobDescription") or {}).get("text") or ""
    description = _strip_html(desc_html)

    return Listing(
        company=company, title=title, location=location, url=url,
        posted_date=posted_date, source="ats:smartrecruiters",
        description=description, department=department,
        employment_type=employment_type, raw=payload,
    )
```

---

### `scripts/ats/providers/workday.py` (provider, request-response POST — most complex)

**Analog:** `scripts/ats/providers/greenhouse.py`

**CRITICAL module-level constants** (searchText="a" is mandatory — see RESEARCH.md Pitfall 1):
```python
NAME = "workday"

BOARD_URL_PATTERNS = [
    r"^https?://([^.]+)\.wd\d+\.myworkdayjobs\.com(?:/[a-z]{2}-[A-Z]{2})?/([^/?#]+)",
]

# CRITICAL: searchText must be non-empty to get title/locationsText/postedOn fields.
# Empty searchText returns only externalPath + bulletFields (no title, no date).
# Verified live 2026-04-28 against workday.wd5 tenant. Use "a" as effective "list all".
WORKDAY_LIST_BODY = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "a"}

# URL pattern for parsing tenant/dc/site from ats_board_url
WORKDAY_URL_RE = re.compile(
    r'^https?://([^.]+)\.(wd\d+)\.myworkdayjobs\.com(?:/[a-z]{2}-[A-Z]{2})?/([^/?#]+)'
)
```

**Tenant URL parsing helper:**
```python
def _parse_workday_url(url: str):
    """Extract (tenant, dc, site) from a Workday board URL.
    'https://workday.wd5.myworkdayjobs.com/Workday' -> ('workday', 'wd5', 'Workday')
    Returns (None, None, None) if not parseable.
    """
    m = WORKDAY_URL_RE.match(url)
    if m:
        return m.group(1), m.group(2), m.group(3)  # tenant, dc, site
    return None, None, None
```

**fetch() with PRV-05 CSRF detection** (slug is the full board URL — not a company slug):
```python
def fetch(slug: str, client: "httpx.Client", semaphore) -> FetchResult:
    # NOTE: For Workday, `slug` is the full ats_board_url e.g.
    # "https://workday.wd5.myworkdayjobs.com/Workday" — not a simple company slug.
    # This is consistent with jsonld.py using careers_url as slug.
    tenant, dc, site = _parse_workday_url(slug)
    if not tenant:
        return FetchResult(provider=NAME, company_slug=slug, listings=[], raw=[], http_status=-1)
    cxs_url = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    with semaphore:
        resp = client.post(cxs_url, json=WORKDAY_LIST_BODY)

    # PRV-05: CSRF/auth-required detection
    if resp.status_code in (401, 403):
        body_lower = resp.text.lower()
        if any(marker in body_lower for marker in ("csrf", "session", "cookie", "authentication")):
            # auth_required=True signals dispatcher to log "workday_auth_required" in runs.jsonl
            return FetchResult(provider=NAME, company_slug=slug, listings=[], raw=[],
                               http_status=resp.status_code, auth_required=True)
        resp.raise_for_status()  # non-CSRF 403 — raise as generic ERROR
    resp.raise_for_status()

    data = resp.json()
    raw_jobs = data.get("jobPostings", []) or []
    listings = []
    for raw_job in raw_jobs:
        try:
            listings.append(to_listing(raw_job, tenant=tenant, dc=dc, site=site))
        except ValueError as exc:
            print(f"WARNING: workday/{slug}: dropped: {exc}", file=sys.stderr)
            continue
    return FetchResult(provider=NAME, company_slug=slug, listings=listings,
                       raw=raw_jobs, http_status=resp.status_code)
```

**postedOn parsing helper** (from RESEARCH.md, live-verified 2026-04-28):
```python
def _parse_workday_posted_on(posted_on: str, today=None) -> str:
    """Parse Workday's freeform English postedOn to ISO date.
    'Posted Today' -> today
    'Posted 6 Days Ago' -> today - 6d
    'Posted 30+ Days Ago' -> today - 30d (lower bound)
    Returns '' if unparseable — age filter will treat as stale if strict.
    """
    from datetime import date, timedelta
    if today is None:
        today = date.today()
    s = (posted_on or "").strip()
    if re.search(r'today', s, re.IGNORECASE):
        return today.isoformat()
    m = re.search(r'(\d+)\+?\s+days?\s+ago', s, re.IGNORECASE)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    return ""
```

**to_listing()** — takes extra keyword args for URL construction:
```python
def to_listing(payload: Dict[str, Any], tenant: str = "", dc: str = "", site: str = "") -> Listing:
    title = (payload.get("title") or "").strip()
    external_path = (payload.get("externalPath") or "").strip()
    # Apply URL is en-US HTML path; detail JSON endpoint not reliably accessible (v0.4 scope)
    url = f"https://{tenant}.{dc}.myworkdayjobs.com/en-US/{site}{external_path}" if tenant else ""
    location = (payload.get("locationsText") or "").strip()
    posted_date = _parse_workday_posted_on(payload.get("postedOn"))
    # description not available without JS-set cookies — empty is valid (optional field)
    return Listing(
        company=tenant, title=title, location=location, url=url,
        posted_date=posted_date, source="ats:workday",
        description="", department="", employment_type="", raw=payload,
    )
```

**detect() — tenant name as company proxy:**
```python
# Workday has no company_name in job objects. Use tenant from URL as name proxy.
# 'workday' tenant matches 'Workday Inc' via token_set_ratio well enough.
evidence={"http_status": 200, "job_count": data.get("total", 0),
           "first_job_company_name": tenant,  # tenant name used for name gate
           "first_job_title": raw_jobs[0].get("title", "") if raw_jobs else ""}
```

---

### `scripts/ats/providers/jsonld.py` (virtual provider, HTML parsing)

**Analog:** `scripts/ats/providers/greenhouse.py` (Protocol shape only — fetch path is entirely different)

**Key differences from real providers:**
- `BOARD_URL_PATTERNS = []` — never auto-detected; always explicitly assigned
- `detect()` always returns `DetectionStatus.NOT_FOUND`
- `slug` in `fetch()` is the full `careers_url`
- No JSON API — HTTP GET + HTML parsing + `<script type="application/ld+json">` extraction

**Module-level constants:**
```python
NAME = "jsonld"
BOARD_URL_PATTERNS = []  # empty — detect.py skips providers with empty patterns (D-3)
_COMPILED_PATTERNS = []
```

**detect() — always NOT_FOUND:**
```python
def detect(company_slug: str, name: str, client: "httpx.Client") -> DetectionResult:
    # JSON-LD is a fallback, not a detectable ATS. detect.py skips providers
    # with empty BOARD_URL_PATTERNS before attempting a network call (D-3).
    return DetectionResult(provider=NAME, status=DetectionStatus.NOT_FOUND,
                           board_url=None, confidence=0.0, evidence={})

def board_url_from_url(url: str) -> Optional[str]:
    return None  # JSON-LD has no canonical board URL pattern
```

**JSON-LD extraction helper** (from RESEARCH.md, verified 2026-04-28):
```python
def _is_job_posting(obj: Dict) -> bool:
    """Handle @type as either string or list per JSON-LD spec."""
    t = obj.get("@type", "")
    if isinstance(t, str):
        return t == "JobPosting"
    return "JobPosting" in t  # Pitfall 7: @type can be ["JobPosting", "Thing"]

def _extract_jsonld_jobs(html_content: str) -> List[Dict]:
    pattern = re.compile(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.DOTALL | re.IGNORECASE
    )
    jobs = []
    for m in pattern.finditer(html_content):
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

**fetch()** — slug is the full careers_url:
```python
def fetch(slug: str, client: "httpx.Client", semaphore) -> FetchResult:
    # slug is careers_url e.g. "https://acme.com/careers"
    # No JS rendering — if page requires JS, OK_ZERO is correct (STR-01)
    with semaphore:
        resp = client.get(slug)
    if resp.status_code == 404:
        return FetchResult(provider=NAME, company_slug=slug, listings=[], raw=[], http_status=404)
    resp.raise_for_status()
    raw_jobs = _extract_jsonld_jobs(resp.text)
    listings = []
    for raw_job in raw_jobs:
        try:
            listings.append(to_listing(raw_job, careers_url=slug))
        except ValueError as exc:
            print(f"WARNING: jsonld/{slug}: dropped: {exc}", file=sys.stderr)
            continue
    return FetchResult(provider=NAME, company_slug=slug, listings=listings,
                       raw=raw_jobs, http_status=resp.status_code)
```

**to_listing():**
```python
def to_listing(payload: Dict[str, Any], careers_url: str = "") -> Listing:
    title = (payload.get("title") or "").strip()
    url = (payload.get("url") or payload.get("@id") or careers_url).strip()
    # datePosted is ISO 8601 date: "2026-03-15" or "2026-03-15T10:00:00Z"
    date_posted = payload.get("datePosted") or ""
    posted_date = date_posted[:10] if len(date_posted) >= 10 else ""
    # hiringOrganization.name -> company; fallback to URL domain
    org = payload.get("hiringOrganization") or {}
    company = (org.get("name") or "").strip()
    if not company and careers_url:
        import urllib.parse
        company = urllib.parse.urlparse(careers_url).netloc
    # location from jobLocation.address
    job_loc = payload.get("jobLocation") or {}
    addr = job_loc.get("address") or {}
    loc_parts = [addr.get("addressLocality"), addr.get("addressRegion"), addr.get("addressCountry")]
    location = ", ".join(p for p in loc_parts if p)
    if not location:
        location = "Unknown"  # Listing requires non-empty location
    description = _strip_html(payload.get("description") or "")
    employment_type = (payload.get("employmentType") or "").strip()
    return Listing(
        company=company, title=title, location=location, url=url,
        posted_date=posted_date, source="ats:jsonld",
        description=description, employment_type=employment_type, raw=payload,
    )
```

---

### `scripts/ats/providers/base.py` — MODIFY (add `auth_required` field)

**Analog:** `scripts/ats/providers/base.py` (self — additive change only)

**Modification:** Add `auth_required: bool = False` to `FetchResult` dataclass (lines 66-87).

**Current FetchResult** (lines 66-87 of base.py):
```python
@dataclass(frozen=True)
class FetchResult:
    provider: str
    company_slug: str
    listings: List["Listing"]
    raw: List[Dict[str, Any]]
    http_status: int
```

**Modified FetchResult** (add one field with default — back-compat preserved):
```python
@dataclass(frozen=True)
class FetchResult:
    provider: str
    company_slug: str
    listings: List["Listing"]
    raw: List[Dict[str, Any]]
    http_status: int
    # PRV-05: Workday CSRF/auth-required signal. True when provider receives
    # 401/403 with CSRF/session markers in body. Dispatcher logs this as
    # "workday_auth_required" in runs.jsonl rather than generic ERROR.
    # Default False — all existing providers get this field without change.
    auth_required: bool = False
```

**Back-compat note:** All existing `FetchResult(...)` call sites (greenhouse.py, dispatcher.py) pass positional or keyword args without `auth_required` — the `= False` default means zero changes required to existing call sites.

---

### `scripts/ats/__init__.py` — MODIFY (register 5 new providers)

**Analog:** `scripts/ats/__init__.py` (self — additive)

**Current registry** (lines 45-49):
```python
from .providers import greenhouse as _greenhouse_module

PROVIDERS: Dict[str, "Provider"] = {
    _greenhouse_module.NAME: _greenhouse_module,
}
```

**Modified registry** (add 5 import lines + 5 dict entries, detection order: greenhouse→lever→ashby→smartrecruiters→workday→jsonld):
```python
from .providers import greenhouse as _greenhouse_module
from .providers import lever as _lever_module
from .providers import ashby as _ashby_module
from .providers import smartrecruiters as _smartrecruiters_module
from .providers import workday as _workday_module
from .providers import jsonld as _jsonld_module

PROVIDERS: Dict[str, "Provider"] = {
    _greenhouse_module.NAME: _greenhouse_module,
    _lever_module.NAME: _lever_module,
    _ashby_module.NAME: _ashby_module,
    _smartrecruiters_module.NAME: _smartrecruiters_module,
    _workday_module.NAME: _workday_module,
    _jsonld_module.NAME: _jsonld_module,
}
```

---

### `scripts/ats/normalize.py` — MODIFY (add 3 filter functions)

**Analog:** `scripts/ats/normalize.py` (self — additive; new functions appended after `compute_missing_fields`)

**Imports to add at top of normalize.py:**
```python
import re
from datetime import date, timedelta
from typing import Dict, List, Optional
```

**Three new functions** (append after line 87, the end of `compute_missing_fields`):

```python
# === POST-FETCH FILTERING (PRV-06, PRV-07, PRV-08, STR-03) ===

_DEFAULT_EVERGREEN_RE = re.compile(
    r"^(general application|talent network|future opportunities|join our team"
    r"|connect with us|expression of interest|always hiring|passive candidate)",
    re.IGNORECASE,
)


def _normalize_title(title: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace for regional collapse key.

    'Sr. Software Engineer - NY' -> 'sr software engineer  ny'
    Used as grouping key in collapse_regional_dupes() ONLY — not for dedup.
    """
    t = title.casefold()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def filter_stale(
    listings: List[Listing],
    max_age_days: int = 60,
    provider_name: str = "",
    provider_overrides: Optional[Dict[str, int]] = None,
    today: Optional[date] = None,
) -> List[Listing]:
    """PRV-06 / STR-03: Drop Listings older than max_age_days.

    STR-03: provider_overrides maps provider name to override age in days.
    e.g. {"workday": 90, "greenhouse": 30} — takes precedence over max_age_days.

    Listings with empty posted_date are KEPT (no date = cannot filter reliably).
    Listings with unparseable posted_date are KEPT (same reason).
    """
    if today is None:
        today = date.today()
    overrides = provider_overrides or {}
    effective_max = overrides.get(provider_name, max_age_days)
    cutoff = today - timedelta(days=effective_max)
    result = []
    for listing in listings:
        if not listing.posted_date:
            result.append(listing)
            continue
        try:
            if date.fromisoformat(listing.posted_date) >= cutoff:
                result.append(listing)
        except ValueError:
            result.append(listing)  # keep on parse error
    return result


def collapse_regional_dupes(listings: List[Listing]) -> List[Listing]:
    """PRV-07: Collapse same-role regional duplicates within one provider+company.

    Groups by (source, company, _normalize_title(title)).
    Merged listing takes: earliest posted_date, joined locations string,
    url of first occurrence (arbitrary).

    Pitfall 8 guard: if all locations empty after merge, falls back to
    "Multiple Locations" rather than raising from Listing.__post_init__.
    """
    from collections import defaultdict
    groups: Dict[tuple, List[Listing]] = defaultdict(list)
    for listing in listings:
        key = (listing.source, listing.company, _normalize_title(listing.title))
        groups[key].append(listing)
    result = []
    for group_listings in groups.values():
        if len(group_listings) == 1:
            result.append(group_listings[0])
            continue
        # Merge: earliest date, union of locations, url of first
        dates = [l.posted_date for l in group_listings if l.posted_date]
        merged_date = min(dates) if dates else ""
        locs = list(dict.fromkeys(l.location for l in group_listings if l.location))
        merged_location = ", ".join(locs) if locs else "Multiple Locations"
        first = group_listings[0]
        result.append(Listing(
            company=first.company, title=first.title,
            location=merged_location, url=first.url,
            posted_date=merged_date, source=first.source,
            description=first.description, department=first.department,
            employment_type=first.employment_type, raw=first.raw,
        ))
    return result


def filter_evergreen(
    listings: List[Listing],
    blocklist_re: Optional[re.Pattern] = None,
) -> List[Listing]:
    """PRV-08: Drop listings matching the evergreen title blocklist.

    Default pattern: general application, talent network, future opportunities,
    join our team, connect with us, expression of interest, always hiring,
    passive candidate. Case-insensitive, matched at start of normalized title.

    blocklist_re can be overridden for testing with a custom compiled pattern.
    """
    pat = blocklist_re if blocklist_re is not None else _DEFAULT_EVERGREEN_RE
    return [l for l in listings if not pat.match(_normalize_title(l.title))]


def apply_filters(
    outcomes: List,  # List[FetchOutcome] from dispatcher
    config: Optional[Dict] = None,
) -> List:
    """Apply all three filters to all OK_WITH_RESULTS outcomes.

    Convenience wrapper called by preview.py after fetch_all(). Mutates
    each FetchOutcome's listings list in place (creates new list; FetchOutcome
    is a dataclass but listings is mutable).

    config dict shape (from config.json ats section):
        {"posted_date_max_age_days": 60,
         "provider_posted_date_overrides": {"workday": 90}}
    """
    cfg = config or {}
    max_age = cfg.get("posted_date_max_age_days", 60)
    overrides = cfg.get("provider_posted_date_overrides", {})
    result = []
    for outcome in outcomes:
        from ats.runs_log import RunOutcome
        if outcome.outcome != RunOutcome.OK_WITH_RESULTS:
            result.append(outcome)
            continue
        filtered = filter_stale(outcome.listings, max_age_days=max_age,
                                provider_name=outcome.provider,
                                provider_overrides=overrides)
        filtered = collapse_regional_dupes(filtered)
        filtered = filter_evergreen(filtered)
        # Replace listings on outcome — use dataclasses.replace or dict reassign
        import dataclasses
        result.append(dataclasses.replace(outcome, listings=filtered))
    return result
```

---

### `scripts/ats/preview.py` — MODIFY (call apply_filters after fetch_all)

**Analog:** `scripts/ats/preview.py` (self — add 2 lines)

**Hook point** (lines 129-131 of preview.py):
```python
    t0 = time.monotonic()
    outcomes = fetch_all(targets, config_path)
    wall_clock = time.monotonic() - t0
```

**After modification** (add apply_filters call and config loading):
```python
    from ats.normalize import apply_filters  # add to top-of-file imports instead

    t0 = time.monotonic()
    outcomes = fetch_all(targets, config_path)
    wall_clock = time.monotonic() - t0

    # Apply post-fetch filtering (PRV-06 / PRV-07 / PRV-08 / STR-03).
    # Load ats config for max_age + per-provider overrides.
    ats_cfg = {}
    try:
        with open(config_path, "r", encoding="utf-8") as _f:
            ats_cfg = json.load(_f).get("ats", {})
    except (OSError, json.JSONDecodeError):
        pass  # filter with defaults on config read failure
    outcomes = apply_filters(outcomes, config=ats_cfg)
```

**Import addition** (add to preview.py import block at line 71):
```python
from ats.normalize import apply_filters  # noqa: E402
```

---

### `scripts/ats/detect.py` — MODIFY (skip providers with empty BOARD_URL_PATTERNS)

**Analog:** `scripts/ats/detect.py` (self — one guard in the PROVIDERS iteration loop)

**Current PROVIDERS iteration** (lines 455-495 of detect.py):
```python
    for provider_name, provider in PROVIDERS.items():
        sem = _DET_SEMAPHORES.get(provider_name)
        ...
        try:
            sem.acquire()
            try:
                raw = provider.detect(company_slug, company_name, client)
```

**After modification** (add 4-line guard at top of loop body — D-3 decision):
```python
    for provider_name, provider in PROVIDERS.items():
        # D-3 (locked): skip providers with empty BOARD_URL_PATTERNS.
        # jsonld.py has BOARD_URL_PATTERNS=[] — it is a fallback, not detectable.
        # Probing it would always return NOT_FOUND and waste a network call.
        if not getattr(provider, "BOARD_URL_PATTERNS", None):
            continue
        sem = _DET_SEMAPHORES.get(provider_name)
        ...
```

---

### `tests/test_providers_phase4.py` (test, fixture-driven)

**Analog:** `tests/test_detection.py`

**Bootstrap pattern** (lines 29-38 of test_detection.py — identical):
```python
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
```

**Fixture loading pattern** (from conftest.py lines 27-35):
```python
LEVER_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "ats" / "lever" / "spotify.json"
ASHBY_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "ats" / "ashby" / "ashby.json"
SR_FIXTURE    = PROJECT_ROOT / "tests" / "fixtures" / "ats" / "smartrecruiters" / "visa.json"
WD_FIXTURE    = PROJECT_ROOT / "tests" / "fixtures" / "ats" / "workday" / "workday_wd5.json"
```

**Test function pattern** (from test_detection.py lines 79-92):
```python
def test_lever_to_listing():
    """PRV-01: lever.to_listing() maps all fields from fixture."""
    from ats.providers import lever
    payload = json.loads(LEVER_FIXTURE.read_text())
    # Lever fixture is a bare array
    listing = lever.to_listing(payload[0])
    assert listing.title
    assert listing.url
    assert listing.posted_date  # ISO date, not epoch
    assert listing.source == "ats:lever"
    assert listing.location  # non-empty string
```

**Mock HTTP client pattern for fetch() tests** (from conftest.py):
```python
def _make_mock_client(get_payload=None, post_payload=None, status=200):
    """Return an httpx.Client mock for fetch() tests."""
    mock_resp = MagicMock()
    mock_resp.status_code = status
    if get_payload is not None:
        mock_resp.json.return_value = get_payload
    if post_payload is not None:
        mock_resp.json.return_value = post_payload
    client = MagicMock()
    client.get.return_value = mock_resp
    client.post.return_value = mock_resp
    return client
```

**Workday CSRF test pattern** (PRV-05):
```python
def test_workday_csrf_detection():
    """PRV-05: workday.fetch() returns FetchResult(auth_required=True) on 401 + csrf body."""
    from ats.providers import workday
    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "csrf token invalid"
    client = MagicMock()
    client.post.return_value = mock_resp
    sem = MagicMock()
    sem.__enter__ = MagicMock(return_value=None)
    sem.__exit__ = MagicMock(return_value=False)
    result = workday.fetch("https://workday.wd5.myworkdayjobs.com/Workday", client, sem)
    assert result.auth_required is True
    assert result.listings == []
    assert result.http_status == 401
```

**Filter function tests pattern:**
```python
def test_filter_stale():
    """PRV-06: filter_stale() drops listings older than max_age_days."""
    from ats.normalize import filter_stale, Listing
    from datetime import date, timedelta
    today = date(2026, 4, 28)
    old_listing = Listing(company="Acme", title="Engineer", location="SF",
                          url="https://acme.com/job/1", posted_date="2026-01-01",
                          source="ats:lever")
    fresh_listing = Listing(company="Acme", title="Engineer", location="SF",
                            url="https://acme.com/job/2",
                            posted_date=(today - timedelta(days=10)).isoformat(),
                            source="ats:lever")
    result = filter_stale([old_listing, fresh_listing], max_age_days=60, today=today)
    assert fresh_listing in result
    assert old_listing not in result
```

---

### Fixture files — `tests/fixtures/ats/*/`

**Analog:** `tests/fixtures/ats/greenhouse/airbnb.json`

**lever/spotify.json** — bare JSON array (not wrapped in `{"jobs": [...]}`):
```json
[
  {
    "id": "1ff4a4e3-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
    "text": "Senior Software Engineer",
    "hostedUrl": "https://jobs.lever.co/spotify/1ff4a4e3-xxxx",
    "createdAt": 1773335421350,
    "categories": {"location": "Remote - USA", "department": "Engineering", "commitment": "Full-time"},
    "descriptionPlain": "Job description here."
  }
]
```

**ashby/ashby.json** — include at least one `isListed=false` job:
```json
{"apiVersion": 1, "jobs": [
  {"id": "uuid-1", "title": "Software Engineer", "jobUrl": "https://jobs.ashbyhq.com/ashby/uuid-1",
   "publishedAt": "2026-03-15T10:23:45.000Z", "location": "Remote - US", "isListed": true,
   "department": "Engineering", "employmentType": "FullTime"},
  {"id": "uuid-2", "title": "Internal Draft Role", "jobUrl": "https://jobs.ashbyhq.com/ashby/uuid-2",
   "publishedAt": "2026-03-01T00:00:00.000Z", "location": "SF", "isListed": false}
]}
```

**smartrecruiters/visa.json** — combined list + detail:
```json
{
  "list": {"content": [{"id": "123", "name": "Product Manager", "company": {"name": "Visa"},
                         "releasedDate": "2026-03-15T10:23:45.000Z",
                         "location": {"city": "San Francisco", "region": "CA", "country": "US"},
                         "typeOfEmployment": {"label": "Full-time"}}],
           "totalFound": 1, "offset": 0, "limit": 100},
  "detail": {"id": "123", "jobAd": {"sections": {"jobDescription": {"text": "<p>Description</p>"}}}}
}
```

**workday/workday_wd5.json** — searchText="a" response shape:
```json
{"total": 448, "jobPostings": [
  {"title": "Account Executive", "externalPath": "/job/JPNOsaka/Account-Executive_JR-0101360",
   "locationsText": "Osaka, Japan", "postedOn": "Posted 5 Days Ago", "remoteType": "Onsite",
   "bulletFields": ["JR-0101360"]}
]}
```

**SOURCE.md** for workday fixtures (per Phase 2 convention):
```markdown
# Workday Fixture Provenance

| Fixture | Source | Date | Notes |
|---------|--------|------|-------|
| workday_wd5.json | Live probe: workday.wd5.myworkdayjobs.com/Workday, searchText="a" | 2026-04-28 | Sliced to 3 jobs; sanitized |
| workday_synthetic_wd1.json | Synthetic — modeled on wd5 live shape | 2026-04-28 | wd1 live probes returned 422; synthetic adequately tests parsing |
| workday_synthetic_wd3.json | Synthetic — modeled on wd5 live shape | 2026-04-28 | Same rationale as wd1 |
```

---

### `templates/config.json` — MODIFY (add filter config keys)

**Analog:** `templates/config.json` (self — additive; 2-space indent, snake_case keys)

**Current `ats` section** (does not yet exist in templates/config.json — it is only in test fixtures and inline config dicts):

**Add to config.json** under `"search"` as a new sibling key:
```json
  "ats": {
    "posted_date_max_age_days": 60,
    "provider_posted_date_overrides": {
      "workday": 90,
      "greenhouse": 30
    },
    "concurrency_disabled": false,
    "provider_concurrency_caps": {
      "greenhouse": 10,
      "lever": 5,
      "ashby": 8,
      "smartrecruiters": 5,
      "workday": 3,
      "jsonld": 3
    }
  }
```

**Convention note:** Empty values use matching empty type per CONVENTIONS.md. The `provider_posted_date_overrides` dict is the extension — `load_caps_and_kill_switch()` in dispatcher.py already reads `ats.provider_concurrency_caps`; extend it to also return `ats.posted_date_max_age_days` and `ats.provider_posted_date_overrides` for use by `apply_filters()`.

---

## Shared Patterns

### Provider Protocol Conformance
**Source:** `scripts/ats/providers/base.py` (Protocol), `scripts/ats/providers/greenhouse.py` (reference implementation)
**Apply to:** All 5 new provider modules
```python
# Every provider module MUST export at module level (duck-typed, no inheritance):
NAME: str               # registry key, e.g. "lever"
BOARD_URL_PATTERNS: List[str]  # regex strings; empty list for jsonld
_COMPILED_PATTERNS: List[re.Pattern]  # pre-compiled from BOARD_URL_PATTERNS

def board_url_from_url(url: str) -> Optional[str]: ...
def detect(company_slug: str, name: str, client: httpx.Client) -> DetectionResult: ...
def fetch(slug: str, client: httpx.Client, semaphore) -> FetchResult: ...
def to_listing(payload: Dict[str, Any]) -> Listing: ...
```

### Sibling-Script Bootstrap (3-level for providers)
**Source:** `scripts/ats/providers/greenhouse.py` lines 31-37
**Apply to:** All 5 new provider files
```python
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
from ats.normalize import Listing  # noqa: E402
from ats.providers.base import DetectionResult, DetectionStatus, FetchResult  # noqa: E402
```

### HTML Stripping
**Source:** `scripts/ats/providers/greenhouse.py` lines 71-116
**Apply to:** `lever.py`, `ashby.py`, `smartrecruiters.py`, `jsonld.py`
Copy `_HTMLStripper` class and `_strip_html()` function verbatim. Do NOT re-implement. The unescape-then-HTMLParser pattern handles HTML-entity-encoded HTML correctly (see comment in greenhouse.py lines 94-100 explaining why unescape must happen FIRST).

### try/except ImportError for httpx
**Source:** `scripts/ats/providers/greenhouse.py` lines 44-51
**Apply to:** All 5 new provider files
```python
try:
    import httpx
except ImportError:
    # Provider modules don't fail at import time when httpx is missing —
    # they fail at fetch() time. The dispatcher already prints the install
    # hint at module load.
    httpx = None  # type: ignore
```

### Per-Job ValueError Swallow in fetch()
**Source:** `scripts/ats/providers/greenhouse.py` lines 261-274
**Apply to:** All 5 new providers
```python
try:
    listings.append(to_listing(raw_job))
except ValueError as exc:
    print(
        f"WARNING: {NAME}/{slug}: job id={raw_job.get('id')} dropped: {exc}",
        file=sys.stderr,
    )
    continue
```

### DetectionResult evidence dict keys
**Source:** `scripts/ats/providers/greenhouse.py` lines 209-220
**Apply to:** All 5 new provider detect() functions
The `_apply_name_gate()` in detect.py reads `evidence["first_job_company_name"]` to run the rapidfuzz score. Every provider's `detect()` MUST populate this key in the evidence dict, even if the value is derived (slug from URL rather than a direct API field).

### Test module bootstrap + fixture loading
**Source:** `tests/conftest.py` lines 16-18, `tests/test_detection.py` lines 29-38
**Apply to:** `tests/test_providers_phase4.py`
```python
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
```

### Fixture `__init__.py` files
**Source:** existing pattern (each `tests/fixtures/ats/greenhouse/` has `__init__.py`)
**Apply to:** `tests/fixtures/ats/lever/`, `ashby/`, `smartrecruiters/`, `workday/`
Each `__init__.py` is empty (zero bytes) — it marks the directory as a Python package for pytest discovery.

---

## Critical Gotchas (Planner Must Include in Plan Actions)

| Gotcha | File | Action |
|--------|------|--------|
| Workday `searchText=""` returns no title fields | `workday.py` | Use `WORKDAY_LIST_BODY = {..., "searchText": "a"}` — document with comment |
| Workday detail endpoint not accessible without JS cookies | `workday.py` | Set `description=""` for all Workday listings; do NOT implement detail calls |
| Lever `createdAt` is epoch **milliseconds** | `lever.py` | `date.fromtimestamp(epoch_ms / 1000)` — include `/ 1000` |
| Ashby `isListed=False` must be filtered | `ashby.py` | Filter in fetch() before to_listing() |
| SmartRecruiters semaphore deadlock | `smartrecruiters.py` | ONE `with semaphore:` block for list + ALL detail calls |
| Workday slug is full board URL | `workday.py` + `dispatcher.py` | `fetch(slug=ats_board_url)` — not a simple company slug |
| JSON-LD `@type` can be a list | `jsonld.py` | Use `_is_job_posting()` helper, not `== "JobPosting"` |
| Regional collapse empty location | `normalize.py` | `"Multiple Locations"` fallback when all location strings are empty |
| detect.py must skip jsonld (empty patterns) | `detect.py` | `if not getattr(provider, "BOARD_URL_PATTERNS", None): continue` |
| FetchResult `auth_required` field | `base.py` → `workday.py` → `dispatcher.py` | base.py change first; workday.py uses it; dispatcher reads it for runs.jsonl |

---

## Metadata

**Analog search scope:** `scripts/ats/`, `tests/`, `templates/`, `tests/fixtures/`
**Files scanned:** 10 source files read in full; detect.py read in 4 targeted passes
**Pattern extraction date:** 2026-04-28

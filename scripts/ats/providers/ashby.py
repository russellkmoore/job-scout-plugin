"""
ashby.py — Ashby public Job Board API conformer.

API endpoint (verified live 2026-04-28):
    GET https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true

Response: object-wrapped: {"apiVersion": 1, "jobs": [...]}
(Unlike Lever, Ashby IS object-wrapped — use data.get("jobs", []) here.)

Per-job keys consumed by to_listing():
    id, title, jobUrl, publishedAt (ISO 8601), location, isListed,
    department, employmentType, descriptionPlain, descriptionHtml

PRV-02 LOCKED: isListed=False jobs MUST be filtered in fetch() BEFORE
calling to_listing(). These are internal draft roles that should never
surface in the report.

Company name detection: Ashby has NO company_name field. detect() extracts
the slug from jobUrl via regex for the rapidfuzz name gate:
    jobUrl = "https://jobs.ashbyhq.com/ashby/145ff46b-..." → slug = "ashby"

Case-sensitive slug: Ashby slugs preserve original casing (e.g. "Ashby"
not "ashby"). Never lowercase the slug — "Ashby" and "ashby" are different
boards.

Pagination: Ashby REST posting-api returns all results in one call as of
2026-04-28. No pagination needed (assumption A1 — see fetch() comment).

Per-provider concurrency cap: 8 (dispatcher.DEFAULT_PROVIDER_CAPS).

Install httpx if missing (CON-04 — use pipx or venv, not pip install globally):
    pipx install httpx
    OR
    python3 -m venv ~/.job-scout-venv && ~/.job-scout-venv/bin/pip install httpx
"""
import html
import os
import re
import sys
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

# Sibling-script bootstrap (3-level — file → providers → ats → scripts).
SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)
# NOTE: 3-level dirname — file → providers → ats → scripts (counts the
# CURRENT file, then walks up three directories). See scripts/ats/__init__.py
# docstring for the pattern table.
from ats.normalize import Listing  # noqa: E402
from ats.providers.base import (  # noqa: E402
    DetectionResult,
    DetectionStatus,
    FetchResult,
)

try:
    import httpx
except ImportError:
    # Provider modules don't fail at import time when httpx is missing —
    # they fail at fetch() time. The dispatcher already prints the install
    # hint at module load. Provider can still be inspected (NAME, patterns,
    # to_listing on a dict from a fixture) without httpx installed.
    httpx = None  # type: ignore


NAME = "ashby"

# URL patterns the dispatcher / detect.py (Phase 3) match against.
# Both public board URL (jobs.ashbyhq.com) and API URL forms recognized.
BOARD_URL_PATTERNS = [
    r"^https?://jobs\.ashbyhq\.com/([^/?#]+)",
    r"^https?://api\.ashbyhq\.com/posting-api/job-board/([^/?#]+)",
]

LIST_URL_TEMPLATE = "https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true"

_COMPILED_PATTERNS = [re.compile(p) for p in BOARD_URL_PATTERNS]


class _HTMLStripper(HTMLParser):
    """Minimal HTML→text stripper. Used by _strip_html below.

    Ashby descriptionPlain / descriptionHtml may contain HTML-encoded content.
    We feed the entity-decoded string into HTMLParser, which only emits
    `handle_data` for text between tags, so all tag scaffolding is dropped.
    """

    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks).strip()


def _strip_html(content: Optional[str]) -> str:
    """Strip HTML tags from Ashby-shaped description content.

    Ashby returns descriptions as HTML-ENTITY-ENCODED HTML —
    `&lt;p&gt;...&lt;/p&gt;`, not `<p>...</p>`. We must `html.unescape()`
    FIRST so the entity-encoded tags become real tags, then HTMLParser
    can strip them. Skipping unescape leaves literal `&lt;p&gt;` in
    Listing.description.

    Falls back to a regex tag-strip on malformed HTML rather than
    crashing the whole fetch.
    """
    if not content:
        return ""
    # Step 1: decode HTML entities so encoded tags become real tags.
    decoded = html.unescape(content)
    # Step 2: feed through HTMLParser to drop the tags themselves.
    parser = _HTMLStripper()
    try:
        parser.feed(decoded)
    except Exception:
        # Malformed HTML — fall back to a regex tag-strip rather than
        # crashing the whole fetch.
        return re.sub(r"<[^>]+>", " ", decoded).strip()
    return parser.get_text()


def board_url_from_url(url: str) -> Optional[str]:
    """Return the canonical Ashby board URL or None if not Ashby-shaped.

    Examples:
        board_url_from_url("https://jobs.ashbyhq.com/ashby")
            -> "https://api.ashbyhq.com/posting-api/job-board/ashby?includeCompensation=true"
        board_url_from_url("https://acme.com/careers")
            -> None
    """
    if not url:
        return None
    for pat in _COMPILED_PATTERNS:
        m = pat.match(url)
        if m:
            slug = m.group(1)
            return LIST_URL_TEMPLATE.format(slug=slug)
    return None


def detect(company_slug: str, name: str, client: "httpx.Client") -> DetectionResult:
    """Probe Ashby for `company_slug`. Returns DetectionResult.

    Ashby is object-wrapped: {"apiVersion": 1, "jobs": [...]}.
    Use data.get("jobs", []) to extract the job list.

    Case-sensitive slug: pass company_slug as-is; do not lowercase.

    Two-factor gate: returns BORDERLINE so Phase 3 can apply the rapidfuzz
    name gate. `evidence["first_job_company_name"]` is extracted from the
    first job's jobUrl slug (Ashby has no company_name field).
    """
    if httpx is None:
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.ERROR,
            board_url=None,
            confidence=0.0,
            evidence={"error": "httpx not installed"},
        )
    url = LIST_URL_TEMPLATE.format(slug=company_slug)
    try:
        resp = client.get(url)
    except httpx.HTTPError as exc:
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.ERROR,
            board_url=None,
            confidence=0.0,
            evidence={"error": f"{type(exc).__name__}: {exc}"},
        )
    if resp.status_code == 404:
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.NOT_FOUND,
            board_url=None,
            confidence=0.0,
            evidence={"http_status": 404},
        )
    if resp.status_code != 200:
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.ERROR,
            board_url=None,
            confidence=0.0,
            evidence={"http_status": resp.status_code},
        )
    try:
        data = resp.json()
    except ValueError as exc:
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.ERROR,
            board_url=None,
            confidence=0.0,
            evidence={"error": f"JSON parse: {exc}"},
        )
    jobs = data.get("jobs", []) or []  # Ashby: object-wrapped (unlike Lever)
    if not jobs:
        # 200 but 0 jobs — could be wildcard catch-all or legitimately empty.
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.BORDERLINE,
            board_url=url,
            confidence=0.5,
            evidence={"http_status": 200, "job_count": 0},
        )
    # Extract returned company slug from jobUrl for name gate.
    # jobUrl = "https://jobs.ashbyhq.com/ashby/145ff46b-..." → slug = "ashby"
    m = re.search(r"jobs\.ashbyhq\.com/([^/]+)/", jobs[0].get("jobUrl", ""))
    returned_slug = m.group(1) if m else ""
    return DetectionResult(
        provider=NAME,
        status=DetectionStatus.BORDERLINE,
        board_url=url,
        confidence=0.85,  # 200 + jobs; Phase 3 layers name fuzzy match for full confidence
        evidence={
            "http_status": 200,
            "job_count": len(jobs),
            "first_job_company_name": returned_slug,
            "first_job_title": jobs[0].get("title", ""),
        },
    )


def fetch(slug: str, client: "httpx.Client", semaphore) -> FetchResult:
    """Fetch all listings for an Ashby board slug.

    NOTE: Ashby REST posting-api returns all results in one call as of 2026-04-28.
    No pagination fields (moreDataAvailable, nextCursor) observed in API response.
    If Ashby adds pagination, a WARNING log will appear here. — v0.4 assumption A1.

    PRV-02 LOCKED: Jobs where isListed=False are dropped BEFORE calling to_listing().
    These are internal draft roles. Default True (missing field = listed).

    fetch() acquires the semaphore with `with semaphore:` around the HTTP call.
    404 = "not an Ashby customer" — return empty FetchResult with http_status=404.
    Per-job ValueError from to_listing() is caught and logged to stderr.
    """
    if httpx is None:
        raise RuntimeError(
            "httpx not installed; install with pipx or venv (CON-04):\n"
            "  pipx install httpx\n"
            "  OR python3 -m venv ~/.job-scout-venv && ~/.job-scout-venv/bin/pip install httpx"
        )
    url = LIST_URL_TEMPLATE.format(slug=slug)
    with semaphore:
        resp = client.get(url)
    if resp.status_code == 404:
        return FetchResult(
            provider=NAME,
            company_slug=slug,
            listings=[],
            raw=[],
            http_status=404,
        )
    resp.raise_for_status()  # any other non-2xx raises; dispatcher wrapper buckets as ERROR
    data = resp.json()
    raw_jobs = data.get("jobs", []) or []  # Ashby: object-wrapped
    listings: List[Listing] = []
    for raw_job in raw_jobs:
        # PRV-02 LOCKED: drop unlisted jobs before to_listing().
        # isListed defaults to True — missing field means listed.
        if not raw_job.get("isListed", True):
            continue
        try:
            listings.append(to_listing(raw_job, slug=slug))
        except ValueError as exc:
            # Per-job parse failure. One malformed job cannot nuke the whole fetch.
            print(
                f"WARNING: ashby/{slug}: job id={raw_job.get('id')} dropped: {exc}",
                file=sys.stderr,
            )
            continue
    return FetchResult(
        provider=NAME,
        company_slug=slug,
        listings=listings,
        raw=raw_jobs,
        http_status=resp.status_code,
    )


def to_listing(payload: Dict[str, Any], slug: Optional[str] = None) -> Listing:
    """Map one Ashby job dict to a canonical Listing.

    Required Listing fields:
        company     <- extracted from jobUrl via regex (no company_name field)
                       Falls back to `slug` param if regex fails.
        title       <- payload.title
        location    <- payload.location
        url         <- payload.jobUrl
        posted_date <- payload.publishedAt[:10]
                       publishedAt is ISO 8601 with tz: "2026-03-15T10:23:45.000Z" → "2026-03-15"
        source      <- "ats:ashby"

    Optional Listing fields:
        description     <- _strip_html(payload.descriptionPlain or payload.descriptionHtml)
        department      <- payload.department
        employment_type <- payload.employmentType normalized:
                           "FullTime" → "Full-time", "PartTime" → "Part-time",
                           "Contract" → "Contract", "Internship" → "Internship"
        raw             <- payload (unmodified)

    Raises:
        ValueError: any required field is missing/empty (delegated to
            Listing.__post_init__).
    """
    title = (payload.get("title") or "").strip()
    url = (payload.get("jobUrl") or "").strip()
    location = (payload.get("location") or "").strip()

    # publishedAt is ISO 8601 with timezone: "2026-03-15T10:23:45.000Z" -> "2026-03-15"
    published_at = payload.get("publishedAt") or ""
    posted_date = published_at[:10] if len(published_at) >= 10 else ""

    department = (payload.get("department") or "").strip()

    # employmentType: "FullTime" -> "Full-time" (normalize to human-readable)
    et_raw = (payload.get("employmentType") or "").strip()
    employment_type = {
        "FullTime": "Full-time",
        "PartTime": "Part-time",
        "Contract": "Contract",
        "Internship": "Internship",
    }.get(et_raw, et_raw)

    description = _strip_html(payload.get("descriptionPlain") or payload.get("descriptionHtml"))

    # Extract company from jobUrl slug — Ashby has no company_name field.
    # jobUrl = "https://jobs.ashbyhq.com/ashby/a1b2c3d4-..." → "ashby"
    # Case-sensitive: slug "Ashby" and "ashby" are different boards.
    m = re.search(r"jobs\.ashbyhq\.com/([^/]+)/", url)
    company = m.group(1) if m else (slug or "")
    if not company:
        raise ValueError(
            f"ashby.to_listing: cannot derive company from jobUrl={url!r} "
            f"and slug={slug!r}. Listing.company is required."
        )

    # Listing.__post_init__ raises ValueError if any required field is empty.
    return Listing(
        company=company,
        title=title,
        location=location,
        url=url,
        posted_date=posted_date,
        source="ats:ashby",
        description=description,
        department=department,
        employment_type=employment_type,
        raw=payload,
    )

"""
smartrecruiters.py — SmartRecruiters public Job Board API conformer.

PRV-03 (locked decision): SmartRecruiters uses an N+1 fetch pattern:
  - List call: GET /v1/companies/{slug}/postings?limit=100&offset=0
    Returns job summaries with company.name, releasedDate, location, etc.
  - Detail call (per-job): GET /v1/companies/{slug}/postings/{job_id}
    Returns jobAd.sections.jobDescription.text (HTML description).

CRITICAL CONCURRENCY RULE (RESEARCH.md Pitfall 5):
  threading.Semaphore is NOT re-entrant. ALL list + detail HTTP calls for
  one company must execute inside a single semaphore-acquire block.
  Nesting semaphore acquires (one inside another) deadlocks the worker
  thread. There is exactly one semaphore acquire in this module.

API endpoints (verified live 2026-04-28, research/STACK.md HIGH confidence):
    List:   GET https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset=0
    Detail: GET https://api.smartrecruiters.com/v1/companies/{slug}/postings/{job_id}

Per-job keys consumed by to_listing():
    name (NOT "title"), ref (apply URL), company.name, releasedDate,
    location.{city,region,country,remote}, department.label,
    typeOfEmployment.label, jobAd.sections.jobDescription.text (HTML)
"""
import html
import os
import re
import sys
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

# Sibling-script bootstrap (3-level — file -> providers -> ats -> scripts).
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
    # Provider modules don't fail at import time when httpx is missing —
    # they fail at fetch() time. Install hint uses pipx per CON-04 (PEP 668
    # protection on Python 3.12+; 'pip install --break-system-packages' is
    # forbidden).
    # Install: pipx install httpx  OR  python3 -m venv .venv && .venv/bin/pip install httpx
    httpx = None  # type: ignore


NAME = "smartrecruiters"

# URL patterns the dispatcher / detect.py match against.
BOARD_URL_PATTERNS = [
    r"^https?://jobs\.smartrecruiters\.com/([^/?#]+)",
    r"^https?://api\.smartrecruiters\.com/v1/companies/([^/?#]+)/postings",
]

LIST_URL_TEMPLATE = (
    "https://api.smartrecruiters.com/v1/companies/{slug}/postings?limit=100&offset=0"
)
DETAIL_URL_TEMPLATE = (
    "https://api.smartrecruiters.com/v1/companies/{slug}/postings/{job_id}"
)

_COMPILED_PATTERNS = [re.compile(p) for p in BOARD_URL_PATTERNS]


class _HTMLStripper(HTMLParser):
    """Minimal HTML->text stripper for SmartRecruiters job descriptions.

    SmartRecruiters jobAd.sections.jobDescription.text is HTML-encoded.
    We feed the entity-decoded string into HTMLParser, which only emits
    handle_data for text between tags, dropping all tag scaffolding.
    """

    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks).strip()


def _strip_html(content: Optional[str]) -> str:
    """Strip HTML tags from SmartRecruiters jobDescription.text.

    SmartRecruiters may return HTML-entity-encoded HTML in the text field.
    Step 1: html.unescape() so encoded tags become real tags.
    Step 2: feed through HTMLParser to drop tags.
    Falls back to regex tag-strip on malformed HTML rather than crashing.
    """
    if not content:
        return ""
    decoded = html.unescape(content)
    parser = _HTMLStripper()
    try:
        parser.feed(decoded)
    except Exception:
        return re.sub(r"<[^>]+>", " ", decoded).strip()
    return parser.get_text()


def board_url_from_url(url: str) -> Optional[str]:
    """Return the canonical SmartRecruiters board URL or None if not SR-shaped.

    Examples:
        board_url_from_url("https://jobs.smartrecruiters.com/Visa")
            -> "https://api.smartrecruiters.com/v1/companies/Visa/postings?limit=100&offset=0"
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
    """Probe SmartRecruiters for `company_slug`. Returns DetectionResult.

    SmartRecruiters includes company.name in the list response — the cleanest
    of all providers for the two-factor detection gate:
    (a) HTTP 200 with >=1 job, AND
    (b) company.name from first job loosely matches the input `name`.
    Phase 3 layers rapidfuzz name scoring on top.
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
    jobs = data.get("content", []) or []
    if not jobs:
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.BORDERLINE,
            board_url=url,
            confidence=0.5,
            evidence={"http_status": 200, "job_count": 0},
        )
    returned_name = jobs[0].get("company", {}).get("name", "")
    return DetectionResult(
        provider=NAME,
        status=DetectionStatus.BORDERLINE,
        board_url=url,
        confidence=0.85,  # 200 + jobs; Phase 3 layers name fuzzy match for full confidence
        evidence={
            "http_status": 200,
            "job_count": data.get("totalFound", 0),
            "first_job_company_name": returned_name,
            "first_job_title": jobs[0].get("name", ""),
        },
    )


def fetch(slug: str, client: "httpx.Client", semaphore) -> FetchResult:
    """Fetch all listings for a SmartRecruiters company slug.

    CRITICAL (RESEARCH.md Pitfall 5): threading.Semaphore is NOT re-entrant.
    Acquire ONCE at the top of fetch(); ALL list + detail HTTP calls happen
    INSIDE this same semaphore-acquire block. Nesting a semaphore acquire
    inside another semaphore acquire deadlocks the worker thread.

    N+1 pattern:
      1. GET list — returns job summaries (no description).
      2. GET detail per job — returns full jobAd with HTML description.
      3. Merge detail dict over summary dict (detail wins on key collision).
      4. Pass merged dict to to_listing().

    Threat note (T-04-11): the N+1 pattern is bounded by limit=100 in the
    list URL, capping per-company HTTP work at 1 list + 100 detail = 101
    calls worst case. With per-provider semaphore cap of 5 (config.json)
    the steady-state concurrency is bounded.
    """
    if httpx is None:
        raise RuntimeError(
            "httpx not installed; install with:\n"
            "  pipx install httpx\n"
            "  OR: python3 -m venv .venv && .venv/bin/pip install 'httpx>=0.27,<0.29'"
        )
    list_url = LIST_URL_TEMPLATE.format(slug=slug)
    # CRITICAL: single semaphore acquire below — do NOT add another acquire
    # inside this block (threading.Semaphore is not re-entrant → deadlock).
    with semaphore:
        list_resp = client.get(list_url)
        if list_resp.status_code == 404:
            return FetchResult(
                provider=NAME,
                company_slug=slug,
                listings=[],
                raw=[],
                http_status=404,
            )
        list_resp.raise_for_status()
        data = list_resp.json()
        content = data.get("content", []) or []
        # NOTE: pagination not implemented in v0.4 — caps at limit=100 per company.
        # Future v0.5+ work if any company has >100 active postings.
        raw_jobs: List[Dict[str, Any]] = []
        listings: List[Listing] = []
        for job_summary in content:
            job_id = job_summary.get("id")
            if not job_id:
                continue
            detail_url = DETAIL_URL_TEMPLATE.format(slug=slug, job_id=job_id)
            detail_resp = client.get(detail_url)  # still inside the semaphore block
            detail_resp.raise_for_status()
            detail = detail_resp.json()
            merged = {**job_summary, **detail}  # detail wins on key collision
            raw_jobs.append(merged)
            try:
                listings.append(to_listing(merged))
            except ValueError as exc:
                print(
                    f"WARNING: smartrecruiters/{slug}: job id={job_id} dropped: {exc}",
                    file=sys.stderr,
                )
                continue
    return FetchResult(
        provider=NAME,
        company_slug=slug,
        listings=listings,
        raw=raw_jobs,
        http_status=list_resp.status_code,
    )


def to_listing(payload: Dict[str, Any]) -> Listing:
    """Map one SmartRecruiters job dict (merged summary+detail) to a canonical Listing.

    Required Listing fields:
        company      <- payload.company.name
        title        <- payload.name  ("name" not "title" — SR field name)
        location     <- city + region + country, or "Remote" if location.remote=True
        url          <- payload.ref  (apply URL)
        posted_date  <- payload.releasedDate[:10]  ("2026-03-15T10:23:45.000Z" -> "2026-03-15")
        source       <- "ats:smartrecruiters"

    Optional Listing fields:
        description  <- _strip_html(payload.jobAd.sections.jobDescription.text)
        department   <- payload.department.label
        employment_type <- payload.typeOfEmployment.label
        raw          <- payload (unmodified — kept for debug/replay)

    Raises:
        ValueError: any required field is missing/empty (delegated to
            Listing.__post_init__).
    """
    title = (payload.get("name") or "").strip()  # "name" not "title"
    url = (payload.get("ref") or "").strip()
    company = (payload.get("company", {}).get("name") or "").strip()

    # releasedDate: "2026-03-15T10:23:45.000Z" -> "2026-03-15"
    released = payload.get("releasedDate") or ""
    posted_date = released[:10] if len(released) >= 10 else ""

    # Location: combine city + region + country; fallback to "Remote" if remote=True
    loc = payload.get("location") or {}
    loc_parts = [loc.get("city"), loc.get("region"), loc.get("country")]
    location = ", ".join(p for p in loc_parts if p)
    if not location and loc.get("remote"):
        location = "Remote"

    department = (payload.get("department", {}).get("label") or "").strip()
    employment_type = (payload.get("typeOfEmployment", {}).get("label") or "").strip()

    # Description from detail response: jobAd.sections.jobDescription.text (HTML)
    # Threat note (T-04-16): HTML stripped via _strip_html (html.unescape + HTMLParser).
    job_ad = payload.get("jobAd") or {}
    sections = job_ad.get("sections") or {}
    desc_html = (sections.get("jobDescription") or {}).get("text") or ""
    description = _strip_html(desc_html)

    # Listing.__post_init__ raises ValueError if any required field is empty.
    return Listing(
        company=company,
        title=title,
        location=location,
        url=url,
        posted_date=posted_date,
        source="ats:smartrecruiters",
        description=description,
        department=department,
        employment_type=employment_type,
        raw=payload,
    )

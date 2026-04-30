"""
workday.py — Workday public Job Board API conformer.

PRV-04 + PRV-05 (locked decisions): Workday is the most complex provider:
  - POST-only (no GET list endpoint).
  - Per-tenant URLs are unguessable — `slug` arg is the FULL ats_board_url.
  - searchText must be "a" (NOT "") to receive title/locationsText/postedOn
    fields. Empty searchText returns only externalPath + bulletFields.
    (RESEARCH.md Pitfall 1 — verified live 2026-04-28.)
  - CSRF/auth-required detection (PRV-05 / D-1): 401/403 + body containing
    any of ("csrf", "session", "cookie", "authentication") → returns
    FetchResult(auth_required=True) so the dispatcher can log
    "workday_auth_required" to runs.jsonl instead of bucketing as generic ERROR.
  - Descriptions not available without JS-set cookies (v0.4 out-of-scope);
    to_listing() sets description="" (Listing description is optional).
  - postedOn is freeform English: "Posted Today", "Posted N Days Ago",
    "Posted 30+ Days Ago" — parsed to ISO date by _parse_workday_posted_on().

API endpoint (verified live 2026-04-28, research/STACK.md HIGH confidence):
    POST https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs
    Body: {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "a"}

Tenant URL format:
    https://<tenant>.<dc>.myworkdayjobs.com[/<locale>]/<site>
    e.g. https://workday.wd5.myworkdayjobs.com/Workday
         https://stripe.wd1.myworkdayjobs.com/en-US/StripeJobs
"""
import html
import os
import re
import sys
from datetime import date, timedelta
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


NAME = "workday"

# Tenant/DC/Site URL pattern. Workday board URLs look like:
#   https://workday.wd5.myworkdayjobs.com/Workday          (no locale)
#   https://stripe.wd1.myworkdayjobs.com/en-US/StripeJobs  (with locale)
BOARD_URL_PATTERNS = [
    r"^https?://([^.]+)\.wd\d+\.myworkdayjobs\.com(?:/[a-z]{2}-[A-Z]{2})?/([^/?#]+)",
]

# CRITICAL (RESEARCH.md Pitfall 1): searchText must be "a" (NOT "") to receive
# title / locationsText / postedOn fields. Empty searchText returns minimal
# objects (only externalPath + bulletFields) — verified live 2026-04-28.
# "a" works as effective "list all" without filtering.
WORKDAY_LIST_BODY = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": "a"}

# Tenant/dc/site URL parser — used by fetch(), detect(), and board_url_from_url().
_WORKDAY_URL_RE = re.compile(
    r"^https?://([^.]+)\.(wd\d+)\.myworkdayjobs\.com(?:/[a-z]{2}-[A-Z]{2})?/([^/?#]+)"
)

_COMPILED_PATTERNS = [re.compile(p) for p in BOARD_URL_PATTERNS]

# CSRF/auth-required body markers (PRV-05 / D-1 LOCKED). Lowercase substring
# match — intentionally permissive to catch tenant-specific phrasing.
# Threat note (T-04-12): false-positive (non-CSRF 401 with "session" in body)
# routes to Pass 2 (soft fail, observable in runs.jsonl); false-negative
# (real CSRF 401 without these markers) buckets as ERROR (also observable).
_CSRF_MARKERS = ("csrf", "session", "cookie", "authentication")


class _HTMLStripper(HTMLParser):
    """Minimal HTML->text stripper (unused for Workday — descriptions empty in v0.4).

    Included to maintain structural parity with greenhouse.py and smartrecruiters.py
    for future v0.5 when description fetching may be added.
    """

    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks).strip()


def _strip_html(content: Optional[str]) -> str:
    """Strip HTML tags — placeholder for future v0.5 description support."""
    if not content:
        return ""
    decoded = html.unescape(content)
    parser = _HTMLStripper()
    try:
        parser.feed(decoded)
    except Exception:
        return re.sub(r"<[^>]+>", " ", decoded).strip()
    return parser.get_text()


def _parse_workday_url(url: str):
    """Extract (tenant, dc, site) from a Workday board URL.

    Examples:
        'https://workday.wd5.myworkdayjobs.com/Workday' -> ('workday', 'wd5', 'Workday')
        'https://stripe.wd1.myworkdayjobs.com/en-US/StripeJobs' -> ('stripe', 'wd1', 'StripeJobs')

    Returns (None, None, None) if the URL is not parseable.
    Threat note (T-04-14): fetch() handles (None, None, None) by returning
    FetchResult with http_status=-1 and listings=[] (buckets as OK_ZERO).
    """
    if not url:
        return None, None, None
    m = _WORKDAY_URL_RE.match(url)
    if m:
        return m.group(1), m.group(2), m.group(3)
    return None, None, None


def _parse_workday_posted_on(posted_on: str, today: Optional[date] = None) -> str:
    """Parse Workday's freeform English postedOn field to ISO date.

    Workday returns these patterns (verified live on Aritzia 2026-04-29):
        'Posted Today'         -> today.isoformat()
        'Posted Yesterday'     -> (today - 1d).isoformat()
        'Posted 6 Days Ago'    -> (today - 6d).isoformat()
        'Posted 30+ Days Ago'  -> (today - 30d).isoformat()  (lower bound)
        ''                     -> ''                          (preserve empty)
        unparseable            -> ''                          (age filter treats as stale)

    The regex r'(\\d+)\\+?\\s+days?\\s+ago' handles both "5 Days Ago" and "30+ Days Ago".

    DSP-02 history: "Posted Yesterday" was missing from the original parser,
    causing every Workday tenant whose response carried that string (e.g.
    Aritzia: 7/20 jobs in the live sample) to be silently dropped by the
    dispatcher's REQUIRED_FIELDS guard. Tests cover all four shapes.
    """
    if today is None:
        today = date.today()
    s = (posted_on or "").strip()
    if not s:
        return ""
    # "Yesterday" must be checked BEFORE the bare "today" branch — neither
    # substring is contained in the other, but ordering by specificity keeps
    # the intent obvious to readers.
    if re.search(r"yesterday", s, re.IGNORECASE):
        return (today - timedelta(days=1)).isoformat()
    if re.search(r"today", s, re.IGNORECASE):
        return today.isoformat()
    m = re.search(r"(\d+)\+?\s+days?\s+ago", s, re.IGNORECASE)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    return ""


def board_url_from_url(url: str) -> Optional[str]:
    """Return the Workday board URL itself, or None if not Workday-shaped.

    For Workday, the board URL IS the slug — there is no further canonical
    transformation (unlike Greenhouse which has a separate API URL). We
    return the matched URL unchanged.
    """
    if not url:
        return None
    for pat in _COMPILED_PATTERNS:
        if pat.match(url):
            return url
    return None


def detect(company_slug: str, name: str, client: "httpx.Client") -> DetectionResult:
    """Probe Workday for `company_slug` (treated as a full board URL). Returns DetectionResult.

    Workday has no company name in job objects; the tenant is used as the
    name proxy for Phase 3's two-factor detection gate.

    If company_slug does not look like a Workday board URL, returns NOT_FOUND
    immediately without a network call.
    """
    if httpx is None:
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.ERROR,
            board_url=None,
            confidence=0.0,
            evidence={"error": "httpx not installed"},
        )
    tenant, dc, site = _parse_workday_url(company_slug)
    if not tenant:
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.NOT_FOUND,
            board_url=None,
            confidence=0.0,
            evidence={"error": "not a Workday URL"},
        )
    cxs_url = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    try:
        resp = client.post(cxs_url, json=WORKDAY_LIST_BODY)
    except httpx.HTTPError as exc:
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.ERROR,
            board_url=None,
            confidence=0.0,
            evidence={"error": f"{type(exc).__name__}: {exc}"},
        )
    if resp.status_code in (401, 403):
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.ERROR,
            board_url=None,
            confidence=0.0,
            evidence={"http_status": resp.status_code, "error": "auth required"},
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
    raw_jobs = data.get("jobPostings", []) or []
    if not raw_jobs:
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.BORDERLINE,
            board_url=company_slug,
            confidence=0.5,
            evidence={"http_status": 200, "job_count": 0},
        )
    return DetectionResult(
        provider=NAME,
        status=DetectionStatus.BORDERLINE,
        board_url=company_slug,
        confidence=0.85,  # 200 + jobs; Phase 3 layers name fuzzy match for full confidence
        evidence={
            "http_status": 200,
            "job_count": data.get("total", 0),
            # Workday has no company_name in job objects — use tenant as proxy
            "first_job_company_name": tenant,
            "first_job_title": raw_jobs[0].get("title", "") if raw_jobs else "",
        },
    )


def fetch(slug: str, client: "httpx.Client", semaphore) -> FetchResult:
    """Fetch all listings for a Workday board.

    NOTE: For Workday, `slug` is the FULL ats_board_url (e.g.
    "https://workday.wd5.myworkdayjobs.com/Workday") — NOT a simple
    company slug like greenhouse/lever. This is consistent with
    jsonld.py treating careers_url as slug.

    PRV-05 / D-1 LOCKED — CSRF/auth-required detection:
    If status_code in (401, 403) AND resp.text.lower() contains any of
    ("csrf", "session", "cookie", "authentication") -> return
    FetchResult(auth_required=True). The dispatcher then logs
    "workday_auth_required" reason to runs.jsonl rather than generic ERROR.

    Threat note (T-04-13): the CSRF response body is inspected only via
    lowercase substring match. The body itself is NEVER logged to
    stdout/stderr/runs.jsonl to prevent session token disclosure.

    Threat note (T-04-12): false-positive (non-CSRF 403 with "session" in
    body) routes to Pass 2 (soft fail, observable in runs.jsonl).
    False-negative (real CSRF without markers) buckets as ERROR (also
    observable). Both outcomes are visible; neither is silent.
    """
    if httpx is None:
        raise RuntimeError(
            "httpx not installed; install with:\n"
            "  pipx install httpx\n"
            "  OR: python3 -m venv .venv && .venv/bin/pip install 'httpx>=0.27,<0.29'"
        )
    tenant, dc, site = _parse_workday_url(slug)
    if not tenant:
        return FetchResult(
            provider=NAME,
            company_slug=slug,
            listings=[],
            raw=[],
            http_status=-1,
        )
    cxs_url = f"https://{tenant}.{dc}.myworkdayjobs.com/wday/cxs/{tenant}/{site}/jobs"
    with semaphore:
        resp = client.post(cxs_url, json=WORKDAY_LIST_BODY)

    # PRV-05 / D-1 LOCKED: CSRF/auth-required detection.
    # 401/403 + body containing csrf|session|cookie|authentication ->
    # return auth_required=True (dispatcher logs "workday_auth_required"
    # to runs.jsonl rather than bucketing as generic ERROR).
    # SECURITY (T-04-13): body is inspected via lowercase substring check only.
    # DO NOT log resp.text — it could contain a CSRF token or session material.
    if resp.status_code in (401, 403):
        body_lower = (resp.text or "").lower()
        if any(marker in body_lower for marker in _CSRF_MARKERS):
            return FetchResult(
                provider=NAME,
                company_slug=slug,
                listings=[],
                raw=[],
                http_status=resp.status_code,
                auth_required=True,
            )
        # 401/403 with no CSRF markers — generic auth failure; raise to
        # let dispatcher bucket as ERROR.
        resp.raise_for_status()

    if resp.status_code == 404:
        return FetchResult(
            provider=NAME,
            company_slug=slug,
            listings=[],
            raw=[],
            http_status=404,
        )
    resp.raise_for_status()

    data = resp.json()
    raw_jobs = data.get("jobPostings", []) or []
    listings: List[Listing] = []
    for raw_job in raw_jobs:
        try:
            listings.append(to_listing(raw_job, tenant=tenant, dc=dc, site=site, board_url=slug))
        except ValueError as exc:
            print(
                f"WARNING: workday/{slug}: dropped: {exc}",
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


def to_listing(
    payload: Dict[str, Any],
    tenant: str = "",
    dc: str = "",
    site: str = "",
    board_url: str = "",
) -> Listing:
    """Map one Workday job dict to a canonical Listing.

    Required Listing fields:
        company      <- tenant (Workday has no per-job company name)
        title        <- payload.title
        location     <- payload.locationsText
        url          <- board_url + payload.externalPath  (preferred)
                        OR fallback construction from tenant/dc/site
        posted_date  <- _parse_workday_posted_on(payload.postedOn)
        source       <- "ats:workday"

    Optional Listing fields:
        description  <- "" (Workday detail endpoint requires JS cookies — v0.4 out-of-scope)
        department   <- "" (not in public POST response)
        employment_type <- "" (not in public POST response)
        raw          <- payload (unmodified — preserves bulletFields[] for
                        debug/replay; the requisition ID at bulletFields[-1]
                        is recoverable from raw without a dedicated field.)

    URL construction:
        When `board_url` is supplied (passed by fetch() as the originating
        ats_board_url), the apply URL is `board_url.rstrip('/') + externalPath`.
        This faithfully preserves whatever locale/site shape the tenant
        actually exposed (some tenants like Aritzia have no /en-US/ segment).
        When `board_url` is absent, fall back to the tenant/dc/site shape
        with /en-US/ — kept for backward compat with Phase 4 unit tests
        that didn't thread board_url through.

    Raises:
        ValueError: any required field is missing/empty (delegated to
            Listing.__post_init__). The fetch() loop catches this and
            drops the offending listing — DSP-02.
    """
    title = (payload.get("title") or "").strip()
    external_path = (payload.get("externalPath") or "").strip()
    if board_url and external_path:
        url = board_url.rstrip("/") + external_path
    elif tenant and dc and site:
        # Backward-compat fallback. Detail JSON endpoint requires JS-set
        # cookies — out of v0.4 scope per RESEARCH.md.
        url = f"https://{tenant}.{dc}.myworkdayjobs.com/en-US/{site}{external_path}"
    else:
        url = ""
    location = (payload.get("locationsText") or "").strip()
    posted_date = _parse_workday_posted_on(payload.get("postedOn", ""))
    # description not available without JS-set cookies — empty is valid (optional field).
    return Listing(
        company=tenant or "",
        title=title,
        location=location,
        url=url,
        posted_date=posted_date,
        source="ats:workday",
        description="",
        department="",
        employment_type="",
        raw=payload,
    )

"""
lever.py — Lever public Job Board API conformer.

API endpoint (verified live 2026-04-28):
    GET https://api.lever.co/v0/postings/{slug}?mode=json

Response: bare JSON ARRAY (NOT an object with a "jobs" key).
This is the critical difference from Greenhouse/Ashby — do NOT use
data.get("jobs", []) here; parse the bare list directly.

Per-job keys consumed by to_listing():
    id, text, hostedUrl, createdAt (epoch ms), categories.location,
    categories.allLocations, categories.department, categories.commitment,
    descriptionPlain

Company name detection: Lever has NO company_name field. detect() extracts
the slug from hostedUrl via regex for the rapidfuzz name gate.

CRITICAL: createdAt is epoch MILLISECONDS — divide by 1000 before
calling date.fromtimestamp(). Raw value ~1.7e12; correct: ~2026.

Per-provider concurrency cap: 5 (dispatcher.DEFAULT_PROVIDER_CAPS).

Install httpx if missing (CON-04 — use pipx or venv, not pip install globally):
    pipx install httpx
    OR
    python3 -m venv ~/.job-scout-venv && ~/.job-scout-venv/bin/pip install httpx
"""
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


NAME = "lever"

# URL patterns the dispatcher / detect.py (Phase 3) match against.
# Both old-style (jobs.lever.co/X) and API-style (api.lever.co/...) recognized.
BOARD_URL_PATTERNS = [
    r"^https?://jobs\.lever\.co/([^/?#]+)",
    r"^https?://api\.lever\.co/v0/postings/([^/?#]+)",
]

LIST_URL_TEMPLATE = "https://api.lever.co/v0/postings/{slug}?mode=json"

_COMPILED_PATTERNS = [re.compile(p) for p in BOARD_URL_PATTERNS]


class _HTMLStripper(HTMLParser):
    """Minimal HTML→text stripper. Used by _strip_html below.

    Lever descriptionPlain may contain HTML-encoded content — we feed the
    entity-decoded string into HTMLParser, which only emits `handle_data`
    for text between tags, so all tag scaffolding is dropped.
    """

    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks).strip()


def _strip_html(content: Optional[str]) -> str:
    """Strip HTML tags from Lever-shaped description content.

    Lever returns `descriptionPlain` as HTML-ENTITY-ENCODED HTML —
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
    """Return the canonical Lever board URL or None if not Lever-shaped.

    Examples:
        board_url_from_url("https://jobs.lever.co/spotify")
            -> "https://api.lever.co/v0/postings/spotify?mode=json"
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
    """Probe Lever for `company_slug`. Returns DetectionResult.

    Lever returns a bare JSON array — not {"jobs": [...]}. Parse with
    resp.json() or [] directly (no .get() needed).

    Two-factor gate: returns BORDERLINE so Phase 3 can apply the rapidfuzz
    name gate. `evidence["first_job_company_name"]` is extracted from the
    first job's hostedUrl slug (Lever has no company_name field).
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
        jobs = resp.json() or []  # Lever: bare array, not {"jobs": [...]}
    except ValueError as exc:
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.ERROR,
            board_url=None,
            confidence=0.0,
            evidence={"error": f"JSON parse: {exc}"},
        )
    if not jobs:
        # 200 but 0 jobs — could be wildcard catch-all or legitimately empty.
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.BORDERLINE,
            board_url=url,
            confidence=0.5,
            evidence={"http_status": 200, "job_count": 0},
        )
    # Extract returned company slug from hostedUrl for name gate.
    # hostedUrl = "https://jobs.lever.co/spotify/1ff4a4e3-..." → slug = "spotify"
    m = re.search(r"jobs\.lever\.co/([^/]+)/", jobs[0].get("hostedUrl", ""))
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
            "first_job_title": jobs[0].get("text", ""),
        },
    )


def fetch(slug: str, client: "httpx.Client", semaphore) -> FetchResult:
    """Fetch all listings for a Lever board slug.

    CRITICAL: Lever's response is a BARE JSON ARRAY — do NOT use
    data.get("jobs", []). Use resp.json() or [] directly.

    fetch() acquires the semaphore with `with semaphore:` around the
    HTTP call (per Phase 4 pattern — dispatcher passes semaphore to provider).

    404 = "not a Lever customer" — return empty FetchResult with http_status=404.
    Per-job ValueError from to_listing() is caught and logged to stderr;
    one bad job does not nuke the whole company's fetch (T-04-06 mitigation).
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
    raw_jobs = resp.json() or []  # bare array — NOT data.get("jobs", [])
    listings: List[Listing] = []
    for raw_job in raw_jobs:
        try:
            listings.append(to_listing(raw_job, slug=slug))
        except ValueError as exc:
            # Per-job parse failure (T-04-06 mitigation). One malformed job
            # cannot nuke the whole fetch — surface to stderr for runs.jsonl correlation.
            print(
                f"WARNING: lever/{slug}: job id={raw_job.get('id')} dropped: {exc}",
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
    """Map one Lever job dict to a canonical Listing.

    Required Listing fields:
        company     <- extracted from hostedUrl via regex (no company_name field)
                       Falls back to `slug` param if regex fails.
        title       <- payload.text  (NOT "title" or "name")
        location    <- payload.categories.location
        url         <- payload.hostedUrl
        posted_date <- payload.createdAt, epoch MILLISECONDS → ISO date
                       DIVIDE BY 1000 before fromtimestamp().
        source      <- "ats:lever"

    Optional Listing fields:
        description     <- _strip_html(payload.descriptionPlain or payload.description)
        department      <- payload.categories.department
        employment_type <- payload.categories.commitment
        raw             <- payload (unmodified)

    Raises:
        ValueError: any required field is missing/empty (delegated to
            Listing.__post_init__).
    """
    title = (payload.get("text") or "").strip()           # "text" not "title"
    url = (payload.get("hostedUrl") or "").strip()
    cats = payload.get("categories") or {}
    location = (cats.get("location") or "").strip()
    department = (cats.get("department") or "").strip()
    employment_type = (cats.get("commitment") or "").strip()

    # CRITICAL: createdAt is epoch MILLISECONDS — divide by 1000 before fromtimestamp.
    # Raw value ~1.7e12; divide by 1000 → ~1.7e9 seconds → 2026.
    # Without / 1000: date.fromtimestamp(1773335421350) overflows or gives year ~58000.
    epoch_ms = payload.get("createdAt") or 0
    try:
        posted_date = date.fromtimestamp(epoch_ms / 1000).isoformat() if epoch_ms else ""
    except (OSError, ValueError):
        posted_date = ""

    description = _strip_html(payload.get("descriptionPlain") or payload.get("description"))

    # Extract company from hostedUrl slug — Lever has no company_name field.
    # hostedUrl = "https://jobs.lever.co/spotify/1ff4a4e3-..." → "spotify"
    m = re.search(r"jobs\.lever\.co/([^/]+)/", url)
    company = m.group(1) if m else (slug or "")
    if not company:
        raise ValueError(
            f"lever.to_listing: cannot derive company from hostedUrl={url!r} "
            f"and slug={slug!r}. Listing.company is required."
        )

    # Listing.__post_init__ raises ValueError if any required field is empty.
    return Listing(
        company=company,
        title=title,
        location=location,
        url=url,
        posted_date=posted_date,
        source="ats:lever",
        description=description,
        department=department,
        employment_type=employment_type,
        raw=payload,
    )

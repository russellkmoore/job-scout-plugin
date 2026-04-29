"""
jsonld.py — schema.org/JobPosting fallback (STR-01 / D-3).

Virtual provider for companies whose ATS detection returns `none` but whose
`careers_url` in master_targets.csv emits one or more
`<script type="application/ld+json">` JobPosting blocks. Pure HTML + regex +
json.loads — no JS rendering, no Chrome.

Why "virtual": this provider has no JSON API endpoint and no detectable
board-URL pattern. Detection skips it (D-3 / detect.py guard) — it is
explicitly assigned by the dispatcher when (ats_provider == "none" AND
careers_url is non-empty). The Provider Protocol surface is preserved so
the dispatcher can call fetch() generically.

Pitfall 7 (RESEARCH.md): JSON-LD `@type` may be a string ("JobPosting") OR
a list (["JobPosting", "Thing"]). `_is_job_posting()` handles both.
"""
import html
import json
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
    # CON-04: use pipx or a virtualenv (PEP 668 protection on Python 3.12+).
    #
    # Install hint:
    #   pipx install 'httpx>=0.27,<0.29'
    # or inside a venv:
    #   python3 -m venv ~/.job-scout-venv && ~/.job-scout-venv/bin/pip install 'httpx>=0.27,<0.29'
    #
    # Provider modules don't fail at import time when httpx is missing —
    # they fail gracefully at fetch() time (returns empty FetchResult).
    httpx = None  # type: ignore


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

NAME = "jsonld"
BOARD_URL_PATTERNS: List[str] = []  # empty — detect.py D-3 guard skips this provider
_COMPILED_PATTERNS: List[re.Pattern] = []  # derived from BOARD_URL_PATTERNS (always empty)

_JSONLD_SCRIPT_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# HTML stripper (verbatim from greenhouse.py — modules are self-contained)
# ---------------------------------------------------------------------------

class _HTMLStripper(HTMLParser):
    """Minimal HTML→text stripper. Used by _strip_html below.

    JSON-LD `description` is often HTML-encoded — we feed the entity-decoded
    string into HTMLParser, which only emits `handle_data` for text
    between tags, so all tag scaffolding is dropped.

    T-04-17 mitigate: html.unescape + HTMLParser extracts text only;
    no script execution.
    """

    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks).strip()


def _strip_html(content: Optional[str]) -> str:
    """Strip HTML tags from JSON-LD description content.

    JSON-LD `description` may be HTML (e.g. `<p>Build cool software.</p>`) or
    HTML-entity-encoded HTML. We `html.unescape()` first so encoded tags become
    real tags, then HTMLParser strips them.

    Falls back to a regex tag-strip on malformed HTML rather than crashing.
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


# ---------------------------------------------------------------------------
# JSON-LD extraction helpers (Pitfall 7 — @type may be string OR list)
# ---------------------------------------------------------------------------

def _is_job_posting(obj: Any) -> bool:
    """Handle @type as either string or list per JSON-LD spec.

    Pitfall 7: some sites emit `"@type": ["JobPosting", "Thing"]` — a list,
    not a string. Equality check `t == "JobPosting"` would miss those.
    """
    if not isinstance(obj, dict):
        return False
    t = obj.get("@type", "")
    if isinstance(t, str):
        return t == "JobPosting"
    if isinstance(t, list):
        return "JobPosting" in t
    return False


def _extract_jsonld_jobs(html_content: str) -> List[Dict[str, Any]]:
    """Extract all JobPosting JSON-LD objects from an HTML page's <script> blocks.

    Returns a list of dicts. Skips malformed JSON blocks silently
    (continue on JSONDecodeError). Top-level value can be a dict OR a list
    of dicts — both shapes flattened into the returned list.

    T-04-18 mitigate: per-block try/except json.JSONDecodeError + continue —
    one malformed block cannot kill the whole page.
    """
    jobs: List[Dict[str, Any]] = []
    for m in _JSONLD_SCRIPT_RE.finditer(html_content):
        block = m.group(1).strip()
        try:
            obj = json.loads(block)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict) and _is_job_posting(obj):
            jobs.append(obj)
        elif isinstance(obj, list):
            jobs.extend(o for o in obj if isinstance(o, dict) and _is_job_posting(o))
    return jobs


# ---------------------------------------------------------------------------
# Provider Protocol surface — detection (always NOT_FOUND for virtual provider)
# ---------------------------------------------------------------------------

def detect(company_slug: str, name: str, client: "httpx.Client") -> DetectionResult:
    """Always returns NOT_FOUND. JSON-LD is a fallback assigned manually
    (or by the dispatcher when ats_provider="none" AND careers_url is set),
    not auto-detected. detect.py's D-3 guard skips this provider entirely
    because BOARD_URL_PATTERNS is empty.
    """
    return DetectionResult(
        provider=NAME,
        status=DetectionStatus.NOT_FOUND,
        board_url=None,
        confidence=0.0,
        evidence={},
    )


def board_url_from_url(url: str) -> Optional[str]:
    """JSON-LD has no canonical board URL pattern."""
    return None


# ---------------------------------------------------------------------------
# fetch() — slug is the full careers_url
# ---------------------------------------------------------------------------

def fetch(slug: str, client: "httpx.Client", semaphore) -> FetchResult:
    """Fetch the careers page at `slug`, extract JSON-LD JobPosting blocks.

    slug is the FULL careers_url e.g. "https://acme.com/careers" — same
    pattern as workday.py treating slug as the full board URL. No JS
    rendering — if the page requires JS to surface job postings, OK_ZERO
    is the correct outcome (STR-01).

    Returns FetchResult with listings (parsed via to_listing) AND raw[]
    (the original per-job dicts for debug/replay).
    """
    if httpx is None:
        return FetchResult(
            provider=NAME,
            company_slug=slug,
            listings=[],
            raw=[],
            http_status=-1,
        )
    with semaphore:
        resp = client.get(slug)
    if resp.status_code == 404:
        return FetchResult(
            provider=NAME,
            company_slug=slug,
            listings=[],
            raw=[],
            http_status=404,
        )
    resp.raise_for_status()  # any other non-2xx raises; dispatcher wrapper buckets as ERROR
    raw_jobs = _extract_jsonld_jobs(resp.text)
    listings: List[Listing] = []
    for raw_job in raw_jobs:
        try:
            listings.append(to_listing(raw_job, careers_url=slug))
        except ValueError as exc:
            # Per-job parse failure. Don't let one malformed job nuke the
            # whole fetch — surface the warning to stderr.
            print(
                f"WARNING: jsonld/{slug}: dropped: {exc}",
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


# ---------------------------------------------------------------------------
# to_listing() — JSON-LD field mapping with required-field fallbacks
# ---------------------------------------------------------------------------

def to_listing(payload: Dict[str, Any], careers_url: str = "") -> Listing:
    """Map one JSON-LD JobPosting dict to a canonical Listing.

    Required Listing fields (DSP-02):
        company  <- hiringOrganization.name; fallback to URL netloc
        title    <- payload.title
        location <- jobLocation.address.{addressLocality, addressRegion, addressCountry};
                    fallback to "Unknown" when all empty (DSP-02 / T-04-22 mitigate)
        url      <- payload.url OR payload.@id OR careers_url
        posted_date <- payload.datePosted[:10]
        source   <- "ats:jsonld"

    Raises:
        ValueError: any required field is missing/empty (delegated to
            Listing.__post_init__).
    """
    title = (payload.get("title") or "").strip()
    url = (payload.get("url") or payload.get("@id") or careers_url or "").strip()

    # datePosted: "2026-03-15" or "2026-03-15T10:00:00Z" -> "2026-03-15"
    date_posted = payload.get("datePosted") or ""
    posted_date = date_posted[:10] if len(date_posted) >= 10 else ""

    # hiringOrganization.name -> company; fallback to URL domain when missing
    org = payload.get("hiringOrganization") or {}
    company = (org.get("name") or "").strip() if isinstance(org, dict) else ""
    if not company and careers_url:
        try:
            import urllib.parse
            parsed = urllib.parse.urlparse(careers_url)
            company = (parsed.netloc or "").strip()
        except (ValueError, AttributeError):
            company = ""

    # location from jobLocation.address — JSON-LD spec allows
    # jobLocation to be either a single object or a list.
    # T-04-22 mitigate: defensive isinstance() checks throughout.
    job_loc_field = payload.get("jobLocation")
    if isinstance(job_loc_field, list) and job_loc_field:
        job_loc = job_loc_field[0]
    elif isinstance(job_loc_field, dict):
        job_loc = job_loc_field
    else:
        job_loc = {}
    addr = job_loc.get("address") if isinstance(job_loc, dict) else None
    addr = addr if isinstance(addr, dict) else {}
    loc_parts = [
        addr.get("addressLocality"),
        addr.get("addressRegion"),
        addr.get("addressCountry"),
    ]
    location = ", ".join(p for p in loc_parts if p and isinstance(p, str))
    if not location:
        location = "Unknown"  # Listing.location must be non-empty (DSP-02)

    description = _strip_html(payload.get("description") or "")
    employment_type = (payload.get("employmentType") or "").strip()

    # Listing.__post_init__ raises ValueError if any required field is empty.
    # We do NOT pre-check here — the dataclass owns the validation contract.
    return Listing(
        company=company,
        title=title,
        location=location,
        url=url,
        posted_date=posted_date,
        source="ats:jsonld",
        description=description,
        department="",
        employment_type=employment_type,
        raw=payload,
    )

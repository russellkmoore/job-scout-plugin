"""
greenhouse.py — Greenhouse public Job Board API conformer.

DSP-09 (locked decision): Greenhouse is the FIRST conformant provider in
Phase 2 — the rest land in Phase 4. Greenhouse is the simplest:
  - GET only, no auth, CDN-cached, no documented rate limit.
  - List response includes full HTML descriptions when ?content=true.
  - 404 on unknown slug means "not on Greenhouse" — caller treats as
    DetectionStatus.NOT_FOUND, NOT as ERROR.

API endpoint (verified live 2026-04-27 + recaptured 2026-04-29, research/STACK.md HIGH confidence):
    GET https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true

Per-job keys consumed by to_listing():
    id, title, absolute_url, first_published, location.name, content,
    departments[].name, metadata, company_name

Per-provider concurrency cap (locked at 10 in dispatcher.DEFAULT_PROVIDER_CAPS):
Greenhouse is CDN-cached, so even with 30 in-flight calls the provider
is fine — the cap protects the LOCAL httpx connection pool, not the
provider's infra.
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


NAME = "greenhouse"

# URL patterns the dispatcher / detect.py (Phase 3) match against.
# Both old-style (boards.greenhouse.io/X) and API-style (boards-api...)
# are recognized.
BOARD_URL_PATTERNS = [
    r"^https?://boards\.greenhouse\.io/([^/?#]+)",
    r"^https?://boards-api\.greenhouse\.io/v1/boards/([^/?#]+)",
    # Some companies use job-boards.greenhouse.io — same shape.
    r"^https?://job-boards\.greenhouse\.io/([^/?#]+)",
]

LIST_URL_TEMPLATE = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"

_COMPILED_PATTERNS = [re.compile(p) for p in BOARD_URL_PATTERNS]


class _HTMLStripper(HTMLParser):
    """Minimal HTML→text stripper. Used by _strip_html below.

    Greenhouse `content` is HTML-encoded — we feed the entity-decoded
    string into HTMLParser, which only emits `handle_data` for text
    between tags, so all tag scaffolding is dropped.
    """

    def __init__(self) -> None:
        super().__init__()
        self._chunks: List[str] = []

    def handle_data(self, data: str) -> None:
        self._chunks.append(data)

    def get_text(self) -> str:
        return "".join(self._chunks).strip()


def _strip_html(content: Optional[str]) -> str:
    """Strip HTML tags from Greenhouse-shaped `content`.

    Greenhouse returns `content` as HTML-ENTITY-ENCODED HTML —
    `&lt;p&gt;...&lt;/p&gt;`, not `<p>...</p>`. We must `html.unescape()`
    FIRST so the entity-encoded tags become real tags, then HTMLParser
    can strip them. Skipping unescape leaves literal `&lt;p&gt;` in
    Listing.description and the "no `<` or `>` in description" smoke
    assertion never fires (because there are no real `<` / `>` characters
    in the encoded form).

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
    """Return the canonical Greenhouse board URL or None if not Greenhouse-shaped.

    Examples:
        board_url_from_url("https://boards.greenhouse.io/airbnb")
            -> "https://boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true"
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
    """Probe Greenhouse for `company_slug`. Returns DetectionResult.

    Two-factor gate (Phase 3 DSP / DET locked decision, but landed here so
    the contract is single-source): a slug is CONFIRMED only if (a) HTTP 200
    with >=1 job AND (b) the company name in the API response loosely
    matches the input `name` (rapidfuzz token_set_ratio >= 85). Phase 2
    does NOT have rapidfuzz available (locked: rapidfuzz reserved for
    Phase 5 dedup), so Phase 2 returns BORDERLINE for the (b) half of the
    gate and lets Phase 3's detection layer apply rapidfuzz scoring.

    DSP-09's verification only exercises (a) — that the endpoint is
    reachable and returns the expected shape. Phase 3 layers (b) on top.
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
    jobs = data.get("jobs", []) or []
    if not jobs:
        # 200 but 0 jobs — could be wildcard catch-all, dead board, or
        # legitimately empty. Detection treats this as BORDERLINE so the
        # caller (Phase 3) can decide whether to ask the user.
        return DetectionResult(
            provider=NAME,
            status=DetectionStatus.BORDERLINE,
            board_url=url,
            confidence=0.5,
            evidence={"http_status": 200, "job_count": 0},
        )
    return DetectionResult(
        provider=NAME,
        status=DetectionStatus.BORDERLINE,
        board_url=url,
        confidence=0.85,  # 200 + jobs; Phase 3 layers name fuzzy match for full confidence
        evidence={
            "http_status": 200,
            "job_count": len(jobs),
            "first_job_company_name": jobs[0].get("company_name", ""),
            "first_job_title": jobs[0].get("title", ""),
        },
    )


def fetch(slug: str, client: "httpx.Client", semaphore) -> FetchResult:
    """Fetch all listings for a Greenhouse board slug.

    DSP-03: client is the dispatcher's shared httpx.Client (one per run).
    DSP-04: semaphore is dispatcher._SEMAPHORES["greenhouse"], already
            acquired by dispatcher._gate("greenhouse"). Greenhouse does NOT
            make detail calls (full descriptions are inline with
            ?content=true), so this function does not re-acquire.

    Greenhouse-specific quirks (research/STACK.md):
      - 404 means "not a Greenhouse customer" — return empty FetchResult
        with http_status=404 (caller buckets as ERROR; that's correct —
        we tried to fetch a slug we shouldn't have, and that's a config
        drift worth surfacing).
      - 200 with 0 jobs is OK_ZERO at the dispatcher boundary.

    Returns FetchResult with listings (parsed via to_listing) AND raw[]
    (the original per-job dicts, persisted to ats_raw/<provider>/<slug>.json
    in Plan 02-03).
    """
    if httpx is None:
        raise RuntimeError(
            "httpx not installed; install with `pip install 'httpx>=0.27,<0.29'`"
        )
    url = LIST_URL_TEMPLATE.format(slug=slug)
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
    raw_jobs = data.get("jobs", []) or []
    listings: List[Listing] = []
    for raw_job in raw_jobs:
        try:
            listings.append(to_listing(raw_job))
        except ValueError as exc:
            # Per-job parse failure (DSP-02 raise-loudly contract). Don't
            # let one malformed job nuke the whole fetch — surface the
            # field-completion telemetry to runs.jsonl via the field
            # being absent in `listings` while raw[] still contains the
            # bad job for debug.
            print(
                f"WARNING: greenhouse/{slug}: job id={raw_job.get('id')} dropped: {exc}",
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


def to_listing(payload: Dict[str, Any]) -> Listing:
    """Map one Greenhouse job dict to a canonical Listing.

    Required Listing fields (DSP-02):
        company       <- payload.company_name (Greenhouse top-level field)
        title         <- payload.title
        location      <- payload.location.name
        url           <- payload.absolute_url
        posted_date   <- payload.first_published, normalized to ISO 8601 date (YYYY-MM-DD).
                          Greenhouse returns "2024-08-15T10:23:45-04:00" — slice to date.
        source        <- "ats:greenhouse" (literal — DSP-10 + OUT-01 contract)

    Optional Listing fields:
        description     <- _strip_html(payload.content)
        department      <- ", ".join(payload.departments[].name)
        employment_type <- payload.metadata[?].name == "Employment Type" -> .value
                          (Greenhouse stores this in the freeform metadata array;
                          ~30% of jobs have it. Empty string is fine.)
        raw             <- payload (unmodified — kept for debug/replay)

    Raises:
        ValueError: any required field is missing/empty (delegated to
            Listing.__post_init__).
    """
    title = (payload.get("title") or "").strip()
    url = (payload.get("absolute_url") or "").strip()
    company = (payload.get("company_name") or "").strip()
    location_obj = payload.get("location") or {}
    location = (
        (location_obj.get("name") or "").strip() if isinstance(location_obj, dict) else ""
    )

    # Greenhouse first_published is ISO 8601 with timezone — slice to YYYY-MM-DD.
    first_pub = payload.get("first_published") or ""
    posted_date = first_pub[:10] if isinstance(first_pub, str) and len(first_pub) >= 10 else ""

    description = _strip_html(payload.get("content"))

    depts = payload.get("departments") or []
    department = ", ".join(
        d.get("name", "") for d in depts if isinstance(d, dict) and d.get("name")
    )

    employment_type = ""
    for entry in payload.get("metadata") or []:
        if isinstance(entry, dict) and entry.get("name") == "Employment Type":
            v = entry.get("value")
            if isinstance(v, str):
                employment_type = v.strip()
            break

    # Listing.__post_init__ raises ValueError if any required field is empty.
    # We do NOT pre-check here — the dataclass owns the validation contract.
    return Listing(
        company=company,
        title=title,
        location=location,
        url=url,
        posted_date=posted_date,
        source="ats:greenhouse",
        description=description,
        department=department,
        employment_type=employment_type,
        raw=payload,
    )

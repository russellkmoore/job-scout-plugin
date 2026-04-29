"""
base.py — Provider Protocol + canonical detection/fetch result shapes.

Every provider module under scripts/ats/providers/ must conform to the
`Provider` protocol below. Conformance is by shape (typing.Protocol, Python 3.8+
`Protocol` runtime-checkable optional). The dispatcher and detector are
written against this protocol — they never import a specific provider.

DSP-01 (per D-01 Phase 2 locked decision): NO base class, NO inheritance.
All 5 v0.4 providers (greenhouse, lever, ashby, smartrecruiters, workday)
conform via duck typing.
"""
# NOTE: base.py does NOT import from scripts/schema.py — no sibling bootstrap needed.

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, TYPE_CHECKING, runtime_checkable

if TYPE_CHECKING:
    # Forward references only — keep base.py free of httpx/threading hard imports
    # so Phase 3 detection logic can use it without dragging in the dispatcher's
    # transport stack.
    import threading

    import httpx

    from ..normalize import Listing


class DetectionStatus(Enum):
    """Per-(company, provider) detection outcome.

    Used by /scout-detect (Phase 3) and lazy-inline detection in /scout-run.
    Lands here in Plan 02-01 so provider modules in Plan 02-02+ don't have
    to re-invent the enum.
    """

    CONFIRMED = "CONFIRMED"
    BORDERLINE = "BORDERLINE"
    NOT_FOUND = "NOT_FOUND"
    ERROR = "ERROR"


@dataclass(frozen=True)
class DetectionResult:
    """Outcome of one provider.detect() probe.

    `provider` is the NAME of the provider that detected (or "" on NOT_FOUND).
    `status` is the DetectionStatus enum.
    `board_url` is the canonical board URL the dispatcher will fetch from on
        a CONFIRMED hit, or None.
    `confidence` is 0.0–1.0 (typically the rapidfuzz token_set_ratio score
        from the two-factor detection gate; Phase 3 wires this).
    `evidence` is opaque to the dispatcher — provider modules stash anything
        useful (job_count, returned_company_name, response excerpts) for the
        operator to inspect.
    """

    provider: str
    status: DetectionStatus
    board_url: Optional[str]
    confidence: float
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class FetchResult:
    """Outcome of one provider.fetch() call (provider's own view).

    The dispatcher wraps this into a higher-level FetchOutcome (see
    dispatcher.py) that adds the 3-state RunOutcome and timing. FetchResult
    is what the provider returns; FetchOutcome is what the dispatcher returns
    to the skill caller.

    `listings` is a list of canonical Listing objects (mapped via
    provider.to_listing). `raw` is the provider-shaped dicts the listings
    were built from — persisted to ats_raw/ for SC-2 inspectability.
    `http_status` is the HTTP status code from the underlying request
    (200, 404, 401, etc.; -1 if no response was received).
    `auth_required` signals that the provider detected a CSRF or session
    authentication barrier (PRV-05 / D-1). When True, the dispatcher writes
    `workday_auth_required` reason to runs.jsonl instead of generic ERROR.
    Default False — all existing providers (greenhouse) inherit without
    changing call sites.
    """

    provider: str
    company_slug: str
    listings: List["Listing"]
    raw: List[Dict[str, Any]]
    http_status: int
    # PRV-05 / D-1: Workday CSRF/auth-required signal. True when provider
    # receives 401/403 with CSRF/session markers in body. Dispatcher logs
    # this as "workday_auth_required" reason in runs.jsonl rather than
    # generic ERROR. Default False — all existing providers (greenhouse)
    # inherit without changing call sites.
    auth_required: bool = False


@runtime_checkable
class Provider(Protocol):
    """Duck-typed contract for an ATS provider module.

    Required class-level attributes:
        NAME: str — registry key, e.g. "greenhouse"
        BOARD_URL_PATTERNS: List[str] — regex strings matching that ATS's
            board URL shape (e.g. r"^https?://boards-api\\.greenhouse\\.io/v1/boards/([^/]+)").

    Required callables:
        detect(company_slug, name, client)
            Probe the provider's API. Returns DetectionResult. Caller
            supplies a shared httpx.Client.
        board_url_from_url(url)
            Given a career-page or detected URL, return the canonical board
            URL the dispatcher will fetch from, or None if not normalizable.
        fetch(slug, client, semaphore)
            Acquire `semaphore` for the duration of the HTTP call (the
            caller has chosen the per-provider semaphore from
            dispatcher._SEMAPHORES). Returns FetchResult.
            Raises httpx.HTTPError on transport failure; the dispatcher's
            worker wrapper will catch + log + bucket as ERROR.
        to_listing(payload)
            Map ONE provider-shaped dict to a canonical Listing. Raises
            ValueError on missing required Listing fields (no silent
            default-to-empty — DSP-02 locked decision).
    """

    NAME: str
    BOARD_URL_PATTERNS: List[str]

    def detect(self, company_slug: str, name: str, client: "httpx.Client") -> DetectionResult: ...
    def board_url_from_url(self, url: str) -> Optional[str]: ...
    def fetch(self, slug: str, client: "httpx.Client", semaphore: "threading.Semaphore") -> FetchResult: ...
    def to_listing(self, payload: Dict[str, Any]) -> "Listing": ...

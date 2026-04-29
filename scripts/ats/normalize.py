"""
normalize.py — Canonical Listing dataclass + raise-loudly field validation.

DSP-02 (locked decision): per-provider mappers raise ValueError on missing
required fields. NO silent default-to-empty. This is what makes ATS schema
drift (Pitfall 7) visible at the dispatcher's worker boundary instead of
propagating empty-record garbage into scoring.

Field-completion telemetry (DSP-07) reads REQUIRED_FIELDS to compute the
per-provider missing-field rate written to runs.jsonl.
"""
# NOTE: normalize.py does NOT import from scripts/schema.py — no sibling
# bootstrap needed in Plan 02-01. Plan 02-02's greenhouse.py will use
# the 3-level bootstrap to read MASTER_TARGETS_COLUMNS as needed.

import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Pattern


REQUIRED_FIELDS = ("company", "title", "location", "url", "posted_date", "source")
OPTIONAL_FIELDS = ("description", "department", "employment_type", "raw")


@dataclass(frozen=True)
class Listing:
    """Canonical ATS listing — one shape for all 5 providers.

    Required fields (DSP-02): per-provider mappers raise ValueError if any
    of these is missing or empty-string. Empty optional fields are fine.

    `source` carries the source tag the report renders (e.g. "ats:greenhouse",
    "ats:lever", or "linkedin"). Per OUT-01 (Phase 6), every report row must
    carry a source= annotation; this is where it originates.

    `posted_date` is ISO 8601 (YYYY-MM-DD). Provider mappers normalize
    per-provider date shapes (e.g. Workday's "Posted 5 Days Ago") to ISO
    before constructing the Listing.

    `raw` is the per-provider dict the listing was built from — kept on the
    Listing for debug/replay. The dispatcher persists raw[] to
    daily/<DATE>/ats_raw/<provider>/<company>.json for SC-2 inspectability.
    """

    # Required (DSP-02 — raise loudly on absent)
    company: str
    title: str
    location: str
    url: str
    posted_date: str  # ISO 8601 date; "" is INVALID — raise in mapper
    source: str  # "ats:<provider>" or "linkedin"

    # Optional (empty string / None is valid)
    description: str = ""
    department: str = ""
    employment_type: str = ""
    raw: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        # Raise loudly on missing required fields. The dispatcher worker
        # wrapper catches this as a per-(company, provider) ERROR and logs
        # it to runs.jsonl with the failing field name — DSP-06.
        for fname in REQUIRED_FIELDS:
            value = getattr(self, fname)
            if value is None or (isinstance(value, str) and not value.strip()):
                raise ValueError(
                    f"Listing.{fname} is required but was empty/None "
                    f"(company={self.company!r}, source={self.source!r}). "
                    f"Per-provider mapper must populate this — DSP-02."
                )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def compute_missing_fields(listing_dict: Dict[str, Any]) -> List[str]:
    """Return list of REQUIRED_FIELDS that are empty/missing in listing_dict.

    Used by runs_log.py for field-completion telemetry. Operates on a dict
    (not a Listing) because Listing.__post_init__ would raise — we want to
    count, not crash.
    """
    missing = []
    for fname in REQUIRED_FIELDS:
        v = listing_dict.get(fname)
        if v is None or (isinstance(v, str) and not v.strip()):
            missing.append(fname)
    return missing


# === POST-FETCH FILTERING (PRV-06, PRV-07, PRV-08, STR-03) ===

_DEFAULT_EVERGREEN_RE = re.compile(
    r"^(general application|talent network|future opportunities|join our team"
    r"|connect with us|expression of interest|always hiring|passive candidate)",
    re.IGNORECASE,
)


def _normalize_title(title: str) -> str:
    """Lowercase + strip punctuation + collapse whitespace.

    Used as a grouping key for collapse_regional_dupes() and as the
    normalization input for filter_evergreen() — NOT for cross-source
    dedup (Phase 5 owns that).
    """
    t = (title or "").casefold()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def filter_stale(
    listings: List[Listing],
    max_age_days: int = 60,
    provider_name: str = "",
    provider_overrides: Optional[Dict[str, int]] = None,
    today: Optional[date] = None,
) -> List[Listing]:
    """PRV-06 / STR-03: Drop listings older than max_age_days (per-provider overridable).

    Per-listing provider resolution order:
      1. provider_name argument (explicit caller override)
      2. listing.source — strip the "ats:" prefix (e.g. "ats:workday" -> "workday")
      3. Fall back to global max_age_days if no match in provider_overrides

    provider_overrides maps provider name to override age in days.
    e.g. {"workday": 90, "greenhouse": 30}. Falls back to max_age_days
    when the resolved provider name is not in the override dict.

    Listings with empty posted_date are KEPT (no date = cannot filter).
    Listings with unparseable posted_date are KEPT (same reason).
    """
    if today is None:
        today = date.today()
    overrides = provider_overrides or {}
    result: List[Listing] = []
    for listing in listings:
        # Resolve provider for this listing
        if provider_name:
            pname = provider_name
        else:
            src = listing.source or ""
            pname = src[4:] if src.startswith("ats:") else src
        effective_max = overrides.get(pname, max_age_days)
        cutoff = today - timedelta(days=effective_max)
        if not listing.posted_date:
            result.append(listing)
            continue
        try:
            if date.fromisoformat(listing.posted_date) >= cutoff:
                result.append(listing)
        except ValueError:
            result.append(listing)
    return result


def collapse_regional_dupes(listings: List[Listing]) -> List[Listing]:
    """PRV-07: Collapse same-role regional duplicates within one provider+company.

    Groups by (source, company, _normalize_title(title)). Merges multiple
    listings into one with: earliest posted_date, comma-joined deduplicated
    locations, url of first occurrence (arbitrary).

    Pitfall 8 guard: if all locations empty, falls back to "Multiple Locations"
    rather than letting Listing.__post_init__ raise.
    """
    groups: Dict[tuple, List[Listing]] = defaultdict(list)
    for listing in listings:
        key = (listing.source, listing.company, _normalize_title(listing.title))
        groups[key].append(listing)
    result: List[Listing] = []
    for group_listings in groups.values():
        if len(group_listings) == 1:
            result.append(group_listings[0])
            continue
        dates = [l.posted_date for l in group_listings if l.posted_date]
        merged_date = min(dates) if dates else group_listings[0].posted_date
        seen: List[str] = []
        for l in group_listings:
            if l.location and l.location not in seen:
                seen.append(l.location)
        merged_location = ", ".join(seen) if seen else "Multiple Locations"
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
    blocklist_re: Optional[Pattern] = None,
) -> List[Listing]:
    """PRV-08: Drop listings matching the evergreen title blocklist.

    Default pattern matches at start of normalized title:
        general application | talent network | future opportunities
        | join our team | connect with us | expression of interest
        | always hiring | passive candidate

    blocklist_re override accepted for testing.
    """
    pat = blocklist_re if blocklist_re is not None else _DEFAULT_EVERGREEN_RE
    return [l for l in listings if not pat.match(_normalize_title(l.title))]


def apply_filters(outcomes: List[Any], config: Optional[Dict] = None) -> List[Any]:
    """Apply filter_stale + collapse_regional_dupes + filter_evergreen to all
    OK_WITH_RESULTS outcomes. Non-OK outcomes pass through unchanged.

    config dict shape (from config.json `ats` section):
        {"posted_date_max_age_days": 60,
         "provider_posted_date_overrides": {"workday": 90, "greenhouse": 30}}

    Returns a NEW list of FetchOutcome objects via dataclasses.replace.
    """
    import dataclasses
    from ats.runs_log import RunOutcome
    cfg = config or {}
    max_age = cfg.get("posted_date_max_age_days", 60)
    overrides = cfg.get("provider_posted_date_overrides", {})
    result = []
    for outcome in outcomes:
        if outcome.outcome != RunOutcome.OK_WITH_RESULTS:
            result.append(outcome)
            continue
        filtered = filter_stale(
            outcome.listings,
            max_age_days=max_age,
            provider_overrides=overrides,
        )
        filtered = collapse_regional_dupes(filtered)
        filtered = filter_evergreen(filtered)
        result.append(dataclasses.replace(outcome, listings=filtered))
    return result

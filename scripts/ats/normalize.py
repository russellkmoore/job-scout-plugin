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

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


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

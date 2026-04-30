"""DSP-02 regression: workday.to_listing() must populate posted_date for every
shape Workday returns, including "Posted Yesterday" — which the original
parser dropped silently because it only matched "Today" and "N Days Ago".

Fixture: scripts/ats/providers/__fixtures__/aritzia_workday_sample.json
(20 of 462 jobs from a live Aritzia probe on 2026-04-29). The first three
listings are "Posted Today"; "Posted Yesterday" appears in the bulk of the
sample and is the case that triggered the original DSP-02 warnings.
"""
import json
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ARITZIA_FIXTURE = (
    PROJECT_ROOT
    / "scripts"
    / "ats"
    / "providers"
    / "__fixtures__"
    / "aritzia_workday_sample.json"
)


def test_workday_to_listing_aritzia_no_dsp02_drops():
    """Every job in the live Aritzia sample must produce a Listing with a
    parseable posted_date <= today. None must be empty/None — that would
    re-introduce the DSP-02 warnings the dispatcher emits when REQUIRED_FIELDS
    is violated.

    Also pins the Aritzia board URL behavior: to_listing builds the apply URL
    by joining ats_board_url with externalPath, so the URL must contain the
    fixture-supplied externalPath suffix.
    """
    from ats.providers import workday

    with open(ARITZIA_FIXTURE) as f:
        raw = json.load(f)

    today = date.today()
    board_url = "https://aritzia.wd3.myworkdayjobs.com/External"

    listings = []
    for job in raw["jobPostings"]:
        listing = workday.to_listing(
            job, tenant="aritzia", dc="wd3", site="External", board_url=board_url
        )
        listings.append(listing)

        # DSP-02 invariant: posted_date is non-empty and parseable.
        assert listing.posted_date, (
            f"DSP-02 regression — empty posted_date for "
            f"postedOn={job.get('postedOn')!r}, title={job.get('title')!r}"
        )
        parsed = date.fromisoformat(listing.posted_date)
        assert parsed <= today, (
            f"posted_date {parsed} is in the future for "
            f"postedOn={job.get('postedOn')!r}"
        )

        # URL is built off ats_board_url, not hard-coded /en-US/.
        assert listing.url.startswith(board_url), listing.url
        assert listing.url.endswith(job["externalPath"]), listing.url

    # Total: every fixture row mapped successfully (no silent drops).
    assert len(listings) == len(raw["jobPostings"])

    # First listing's postedOn is "Posted Today" in the captured sample;
    # the parser must resolve that to today's date.
    first_job = raw["jobPostings"][0]
    assert first_job["postedOn"] == "Posted Today", (
        f"fixture drift — first job postedOn changed: {first_job['postedOn']!r}"
    )
    assert listings[0].posted_date == today.isoformat()


def test_workday_parse_posted_on_yesterday():
    """Direct unit cover for the missing branch: 'Posted Yesterday'."""
    from ats.providers import workday

    fixed_today = date(2026, 4, 29)
    assert workday._parse_workday_posted_on("Posted Yesterday", today=fixed_today) == "2026-04-28"
    # case-insensitive
    assert workday._parse_workday_posted_on("posted yesterday", today=fixed_today) == "2026-04-28"


def test_workday_parse_posted_on_unparseable_returns_empty():
    """Anything the parser can't decode returns "" so Listing.__post_init__
    raises and the dispatcher drops that one listing — never the whole run.
    """
    from ats.providers import workday

    fixed_today = date(2026, 4, 29)
    assert workday._parse_workday_posted_on("Posted Last Week", today=fixed_today) == ""
    assert workday._parse_workday_posted_on("garbage", today=fixed_today) == ""
    assert workday._parse_workday_posted_on("", today=fixed_today) == ""


def test_workday_to_listing_url_uses_board_url_when_provided():
    """When board_url is passed, the apply URL is built off it (not the
    hard-coded /en-US/ path). Aritzia is the canonical case — its board URL
    has no locale segment.
    """
    from ats.providers import workday

    job = {
        "title": "Marketing Manager",
        "externalPath": "/job/Vancouver/Marketing-Manager_R001",
        "locationsText": "Vancouver",
        "postedOn": "Posted Today",
        "bulletFields": ["R001"],
    }
    listing = workday.to_listing(
        job,
        tenant="aritzia",
        dc="wd3",
        site="External",
        board_url="https://aritzia.wd3.myworkdayjobs.com/External",
    )
    assert listing.url == (
        "https://aritzia.wd3.myworkdayjobs.com/External/job/Vancouver/Marketing-Manager_R001"
    )


def test_workday_to_listing_url_falls_back_when_no_board_url():
    """Backward compat: if board_url is omitted, the original tenant/dc/site
    shape with /en-US/ is preserved. Existing Phase 4 unit tests rely on this.
    """
    from ats.providers import workday

    job = {
        "title": "Account Executive",
        "externalPath": "/job/Tokyo/Account-Executive_R002",
        "locationsText": "Tokyo",
        "postedOn": "Posted Today",
        "bulletFields": ["R002"],
    }
    listing = workday.to_listing(job, tenant="workday", dc="wd5", site="Workday")
    assert listing.url == (
        "https://workday.wd5.myworkdayjobs.com/en-US/Workday/job/Tokyo/Account-Executive_R002"
    )

"""test_providers_phase4.py -- Wave 0 RED tests for PRV-01..09, STR-01, STR-03.

All 15 tests are expected to FAIL until Wave 2 (provider modules) and
Wave 3 (filters + registry wiring) plans land. Run with:

    ~/.job-scout-venv/bin/python3 -m pytest tests/test_providers_phase4.py -x -q
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

LEVER_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "ats" / "lever" / "spotify.json"
ASHBY_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "ats" / "ashby" / "ashby.json"
SR_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "ats" / "smartrecruiters" / "visa.json"
WD_WD5_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "ats" / "workday" / "workday_wd5.json"
WD_SYNTHETIC_WD1_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "ats" / "workday" / "workday_synthetic_wd1.json"
WD_SYNTHETIC_WD3_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "ats" / "workday" / "workday_synthetic_wd3.json"
JSONLD_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "jsonld" / "example_careers.html"


# ---------------------------------------------------------------------------
# PRV-01: Lever provider
# ---------------------------------------------------------------------------

def test_lever_to_listing():
    """PRV-01: lever.to_listing() maps fixture fields to Listing."""
    from ats.providers import lever  # RED until Plan 04-02 lands
    payload = json.loads(LEVER_FIXTURE.read_text())
    listing = lever.to_listing(payload[0])
    assert listing.title == "Senior Software Engineer"
    assert listing.source == "ats:lever"
    assert listing.url.startswith("https://jobs.lever.co/spotify/")
    assert listing.location == "Remote - USA"
    # Lever createdAt is epoch ms; to_listing converts to ISO date
    assert len(listing.posted_date) == 10
    assert listing.posted_date.startswith("2026-")


def test_lever_posted_date_epoch():
    """PRV-01: Lever createdAt epoch_ms 1773335421350 -> ISO date in 2026."""
    from ats.providers import lever  # RED until Plan 04-02 lands
    payload = json.loads(LEVER_FIXTURE.read_text())
    # First fixture entry: createdAt = 1773335421350 (epoch ms)
    assert payload[0]["createdAt"] == 1773335421350
    listing = lever.to_listing(payload[0])
    # Must be non-empty ISO date (not the raw epoch number)
    assert len(listing.posted_date) == 10, f"Expected 10-char ISO date, got: {listing.posted_date!r}"
    assert listing.posted_date[:4] == "2026", f"Expected 2026 date, got: {listing.posted_date!r}"
    # Must NOT be the literal epoch string
    assert "1773335421350" not in listing.posted_date


# ---------------------------------------------------------------------------
# PRV-02: Ashby provider
# ---------------------------------------------------------------------------

def test_ashby_filters_unlisted():
    """PRV-02: ashby.fetch() skips jobs with isListed=False."""
    from ats.providers import ashby  # RED until Plan 04-02 lands
    fixture_data = json.loads(ASHBY_FIXTURE.read_text())

    # Set up a mock httpx.Client that returns the fixture
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = fixture_data
    mock_client = MagicMock()
    mock_client.get.return_value = mock_resp

    mock_sem = MagicMock()
    mock_sem.__enter__ = MagicMock(return_value=None)
    mock_sem.__exit__ = MagicMock(return_value=False)

    result = ashby.fetch("ashby", mock_client, mock_sem)

    # Fixture has 3 jobs: 2 isListed=true, 1 isListed=false
    assert len(result.listings) == 2, (
        f"Expected 2 listed jobs, got {len(result.listings)}: "
        f"{[l.title for l in result.listings]}"
    )
    # The isListed=false "Internal Draft Role" must NOT appear
    titles = [l.title for l in result.listings]
    assert "Internal Draft Role" not in titles, f"Unlisted job should be filtered: {titles}"


def test_ashby_to_listing():
    """PRV-02: ashby.to_listing() maps fixture fields to Listing with FullTime->Full-time normalization."""
    from ats.providers import ashby  # RED until Plan 04-02 lands
    fixture_data = json.loads(ASHBY_FIXTURE.read_text())
    # First job in fixture: Software Engineer, isListed=true
    job = fixture_data["jobs"][0]
    listing = ashby.to_listing(job)
    assert listing.title == "Software Engineer"
    assert listing.source == "ats:ashby"
    assert listing.posted_date == "2026-03-15"
    # employmentType: "FullTime" -> "Full-time"
    assert listing.employment_type == "Full-time", (
        f"Expected 'Full-time' normalization from 'FullTime', got: {listing.employment_type!r}"
    )


# ---------------------------------------------------------------------------
# PRV-03: SmartRecruiters provider
# ---------------------------------------------------------------------------

def test_sr_to_listing():
    """PRV-03: smartrecruiters.to_listing() maps name->title, company.name->company, strips HTML description."""
    from ats.providers import smartrecruiters  # RED until Plan 04-02 lands
    fixture = json.loads(SR_FIXTURE.read_text())
    detail = fixture["detail"]
    listing = smartrecruiters.to_listing(detail)
    assert listing.source == "ats:smartrecruiters"
    assert listing.title == "Product Manager"  # from "name" key
    assert listing.company == "Visa"            # from "company.name"
    assert listing.posted_date == "2026-03-15"  # from releasedDate[:10]
    # HTML description stripped: "<p>Product manager for cross-border payments.</p>" -> plain text
    assert "cross-border payments" in listing.description
    assert "<p>" not in listing.description


def test_sr_description_from_detail():
    """PRV-03: smartrecruiters.fetch() fetches list then detail; listing has detail description."""
    from ats.providers import smartrecruiters  # RED until Plan 04-02 lands
    fixture = json.loads(SR_FIXTURE.read_text())

    # Mock list response
    list_resp = MagicMock()
    list_resp.status_code = 200
    list_resp.json.return_value = fixture["list"]
    list_resp.raise_for_status = MagicMock()

    # Mock detail response
    detail_resp = MagicMock()
    detail_resp.status_code = 200
    detail_resp.json.return_value = fixture["detail"]
    detail_resp.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.get.side_effect = [list_resp, detail_resp]

    mock_sem = MagicMock()
    mock_sem.__enter__ = MagicMock(return_value=None)
    mock_sem.__exit__ = MagicMock(return_value=False)

    result = smartrecruiters.fetch("Visa", mock_client, mock_sem)

    assert len(result.listings) == 1
    assert "cross-border payments" in result.listings[0].description, (
        f"Expected detail description in listing, got: {result.listings[0].description!r}"
    )


# ---------------------------------------------------------------------------
# PRV-04: Workday provider
# ---------------------------------------------------------------------------

def test_workday_to_listing():
    """PRV-04: workday.to_listing() maps title, locationsText, externalPath->URL, postedOn->ISO date."""
    from ats.providers import workday  # RED until Plan 04-03 lands
    fixture = json.loads(WD_WD5_FIXTURE.read_text())
    job = fixture["jobPostings"][0]  # Account Executive, Osaka Japan, Posted 5 Days Ago
    listing = workday.to_listing(job, tenant="workday", dc="wd5", site="Workday")
    assert listing.source == "ats:workday"
    assert listing.title == "Account Executive"
    assert listing.location == "Osaka, Japan"
    # URL should be en-US apply path containing the externalPath components
    assert "workday" in listing.url
    assert "wd5" in listing.url
    assert "JPNOsaka" in listing.url or "Account-Executive" in listing.url
    # posted_date must be valid ISO date (5 days ago from some reference)
    assert len(listing.posted_date) == 10
    assert listing.posted_date[:4].isdigit()


def test_workday_posted_on_parsing():
    """PRV-04: _parse_workday_posted_on handles 'Posted Today', 'Posted N Days Ago', '30+'."""
    from ats.providers import workday  # RED until Plan 04-03 lands
    today = date(2026, 4, 28)

    # "Posted Today" -> today's ISO date
    result = workday._parse_workday_posted_on("Posted Today", today=today)
    assert result == "2026-04-28", f"Posted Today should be today, got: {result!r}"

    # "Posted 5 Days Ago" -> today - 5d
    result = workday._parse_workday_posted_on("Posted 5 Days Ago", today=today)
    assert result == "2026-04-23", f"Posted 5 Days Ago should be 2026-04-23, got: {result!r}"

    # "Posted 30+ Days Ago" -> today - 30d
    result = workday._parse_workday_posted_on("Posted 30+ Days Ago", today=today)
    assert result == "2026-03-29", f"Posted 30+ Days Ago should be 2026-03-29, got: {result!r}"

    # Empty input -> empty string
    result = workday._parse_workday_posted_on("", today=today)
    assert result == "", f"Empty input should return empty string, got: {result!r}"


def test_workday_csrf_detection():
    """PRV-05: workday.fetch() returns FetchResult(auth_required=True) on 401 + 'csrf token invalid' body."""
    from ats.providers import workday  # RED until Plan 04-03 lands
    from ats.providers.base import FetchResult

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.text = "csrf token invalid"

    mock_client = MagicMock()
    mock_client.post.return_value = mock_resp

    mock_sem = MagicMock()
    mock_sem.__enter__ = MagicMock(return_value=None)
    mock_sem.__exit__ = MagicMock(return_value=False)

    # slug is the full Workday board URL
    result = workday.fetch("https://workday.wd5.myworkdayjobs.com/Workday", mock_client, mock_sem)

    assert result.auth_required is True, (
        f"Expected auth_required=True for 401+csrf body, got: {result.auth_required}"
    )
    assert result.listings == [], f"Expected empty listings on CSRF 401, got: {result.listings}"
    assert result.http_status == 401, f"Expected http_status=401, got: {result.http_status}"


# ---------------------------------------------------------------------------
# PRV-06 + STR-03: filter_stale
# ---------------------------------------------------------------------------

def test_filter_stale():
    """PRV-06: filter_stale() drops listings older than max_age_days, keeps fresh ones."""
    from ats.normalize import filter_stale, Listing  # RED until Plan 04-05 lands

    today = date(2026, 4, 28)
    old_date = (today - timedelta(days=120)).isoformat()  # 4 months ago
    fresh_date = (today - timedelta(days=10)).isoformat()  # 10 days ago

    old_listing = Listing(
        company="Acme", title="Stale Role", location="SF", url="https://example.com/1",
        posted_date=old_date, source="ats:greenhouse",
    )
    fresh_listing = Listing(
        company="Acme", title="Fresh Role", location="SF", url="https://example.com/2",
        posted_date=fresh_date, source="ats:greenhouse",
    )

    result = filter_stale([old_listing, fresh_listing], max_age_days=60, today=today)

    assert fresh_listing in result, "Fresh listing (10d) should survive filter_stale(60d)"
    assert old_listing not in result, "Old listing (120d) should be dropped by filter_stale(60d)"


def test_filter_stale_per_provider_override():
    """STR-03: filter_stale() uses per-provider override when provided."""
    from ats.normalize import filter_stale, Listing  # RED until Plan 04-05 lands

    today = date(2026, 4, 28)
    # 75 days old — older than 60d default but within 90d workday override
    date_75d = (today - timedelta(days=75)).isoformat()

    listing = Listing(
        company="Workday", title="75-Day-Old Role", location="Pleasanton, CA",
        url="https://workday.wd5.myworkdayjobs.com/en-US/Workday/job/test",
        posted_date=date_75d, source="ats:workday",
    )

    # Without override: 75d > 60d default -> dropped
    result_without = filter_stale([listing], max_age_days=60, today=today)
    assert listing not in result_without, "75d-old listing should be dropped with 60d default"

    # With workday override of 90d: 75d < 90d -> kept
    result_with = filter_stale(
        [listing],
        max_age_days=60,
        provider_overrides={"workday": 90},
        today=today,
    )
    assert listing in result_with, (
        "75d-old workday listing should survive with 90d provider override"
    )


# ---------------------------------------------------------------------------
# PRV-07: collapse_regional_dupes
# ---------------------------------------------------------------------------

def test_collapse_regional_dupes():
    """PRV-07: collapse_regional_dupes() merges same-source+company+title across locations."""
    from ats.normalize import collapse_regional_dupes, Listing  # RED until Plan 04-05 lands

    # Three listings: same company+title, different locations
    base = dict(company="Stripe", title="Software Engineer", source="ats:greenhouse",
                posted_date="2026-04-01")
    listings = [
        Listing(**base, location="New York, NY", url="https://boards.greenhouse.io/stripe/1"),
        Listing(**base, location="London, UK", url="https://boards.greenhouse.io/stripe/2"),
        Listing(**base, location="Tokyo, Japan", url="https://boards.greenhouse.io/stripe/3"),
    ]

    result = collapse_regional_dupes(listings)

    assert len(result) == 1, (
        f"Expected 1 collapsed listing for same-title across 3 locations, got {len(result)}: "
        f"{[l.location for l in result]}"
    )
    # Collapsed location should mention multiple locations or be a sentinel
    collapsed = result[0]
    has_multi = (
        "New York" in collapsed.location
        or "London" in collapsed.location
        or "Multiple" in collapsed.location
    )
    assert has_multi, f"Collapsed location should reference multiple sites, got: {collapsed.location!r}"


# ---------------------------------------------------------------------------
# PRV-08: filter_evergreen
# ---------------------------------------------------------------------------

def test_filter_evergreen():
    """PRV-08: filter_evergreen() drops 'Talent Network', 'General Application', etc.; keeps real roles."""
    from ats.normalize import filter_evergreen, Listing  # RED until Plan 04-05 lands

    def _make(title):
        return Listing(
            company="Acme", title=title, location="SF", source="ats:greenhouse",
            posted_date="2026-04-01", url=f"https://example.com/{title.replace(' ', '-').lower()}",
        )

    listings = [
        _make("Talent Network -- Future Opportunities"),
        _make("General Application"),
        _make("Senior Software Engineer"),
        _make("Join Our Team"),
    ]

    result = filter_evergreen(listings)

    titles = [l.title for l in result]
    assert "Senior Software Engineer" in titles, (
        "Real job title should survive filter_evergreen"
    )
    assert not any(
        t in titles for t in ["Talent Network -- Future Opportunities", "General Application", "Join Our Team"]
    ), f"Evergreen titles should be dropped, but found: {titles}"


# ---------------------------------------------------------------------------
# PRV-09: PROVIDERS registry
# ---------------------------------------------------------------------------

def test_providers_registry_has_five():
    """PRV-09: PROVIDERS dict has exactly 6 entries after Phase 4 (5 ATS + JSON-LD).

    RED until Plan 04-05 wires all providers into scripts/ats/__init__.py.
    Asserts all 6 provider keys present: greenhouse, lever, ashby, smartrecruiters,
    workday, jsonld.
    """
    from ats import PROVIDERS  # RED until Plan 04-05 wires all 6
    assert "greenhouse" in PROVIDERS, "greenhouse should be in PROVIDERS"
    assert "lever" in PROVIDERS, "lever should be in PROVIDERS after Phase 4"
    assert "ashby" in PROVIDERS, "ashby should be in PROVIDERS after Phase 4"
    assert "smartrecruiters" in PROVIDERS, "smartrecruiters should be in PROVIDERS after Phase 4"
    assert "workday" in PROVIDERS, "workday should be in PROVIDERS after Phase 4"
    assert "jsonld" in PROVIDERS, "jsonld should be in PROVIDERS after Phase 4"
    assert len(PROVIDERS) == 6, (
        f"Expected exactly 6 providers (greenhouse + 4 ATS + jsonld), got {len(PROVIDERS)}: "
        f"{list(PROVIDERS.keys())}"
    )


# ---------------------------------------------------------------------------
# STR-01: JSON-LD extraction
# ---------------------------------------------------------------------------

def test_jsonld_extraction():
    """STR-01: jsonld._extract_jsonld_jobs() parses schema.org/JobPosting from HTML fixture."""
    from ats.providers import jsonld  # RED until Plan 04-04 lands
    html_content = JSONLD_FIXTURE.read_text()
    jobs = jsonld._extract_jsonld_jobs(html_content)
    assert len(jobs) == 1, f"Expected 1 JobPosting in fixture, got {len(jobs)}"
    assert jobs[0].get("@type") == "JobPosting", (
        f"Expected @type=JobPosting, got: {jobs[0].get('@type')!r}"
    )
    assert jobs[0].get("title") == "Software Engineer", (
        f"Expected title='Software Engineer', got: {jobs[0].get('title')!r}"
    )
    assert jobs[0].get("hiringOrganization", {}).get("name") == "Acme Corp", (
        f"Expected hiringOrganization.name='Acme Corp', got: {jobs[0].get('hiringOrganization')!r}"
    )

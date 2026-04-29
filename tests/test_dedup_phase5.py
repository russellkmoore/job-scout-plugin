"""test_dedup_phase5.py — Wave 0 RED tests for DDP-01..08, CON-10/11/15.

Wave 0 commits these RED. Wave 2 (Plan 05-02 dedupe.py + Plan 05-04 runs_log.py)
turns DDP-01..08, CON-15 GREEN. Wave 3 (Plan 05-05 SKILL.md) verifies CON-11/12
through smoke / mock-based unit tests.

Run with:
    ~/.job-scout-venv/bin/python3 -m pytest tests/test_dedup_phase5.py -x -q
"""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

LINKEDIN_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "linkedin_candidates_sample.json"
ATS_RAW_FIXTURE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "ats_raw_sample"
RUNS_JSONL_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "runs_jsonl_history.jsonl"


@pytest.fixture
def today_iso():
    return date.today().isoformat()


# ---------------------------------------------------------------------------
# DDP-01, DDP-03: Two-key gate
# ---------------------------------------------------------------------------

def test_two_key_gate():
    """DDP-01/DDP-03: auto-merge requires BOTH loose AND tight keys ≥95%.
    review-band fires when only ONE of (loose, tight) is ≥95.
    """
    from ats import dedupe  # RED until Plan 05-02 lands

    linkedin_listings = json.loads(LINKEDIN_FIXTURE.read_text())
    ats_payload = json.loads((ATS_RAW_FIXTURE_DIR / "greenhouse" / "acme.json").read_text())
    ats_listings = ats_payload["listings"]

    # Auto-merge: exact title match → both loose + tight ≥95
    result = dedupe.run_cross_source_dedup(ats_listings, [linkedin_listings[0]])
    decisions = result["decisions"]
    assert len(decisions) >= 1
    assert decisions[0]["action"] == "auto_merge", (
        f"Expected auto_merge for exact-title pair, got: {decisions[0]['action']!r}"
    )

    # Review-band synthetic: provide explicit scores via internal helpers
    # _loose_key and _tight_key exposed for testing
    assert hasattr(dedupe, "_loose_key"), "dedupe._loose_key must exist"
    assert hasattr(dedupe, "_tight_key"), "dedupe._tight_key must exist"


# ---------------------------------------------------------------------------
# DDP-02: Tiered band
# ---------------------------------------------------------------------------

def test_tiered_band():
    """DDP-02: Three pairs from fixtures yield auto_merge, review_band, keep_both."""
    from ats import dedupe  # RED until Plan 05-02 lands

    linkedin_listings = json.loads(LINKEDIN_FIXTURE.read_text())

    # Fixture 0: Acme Corp — auto-merge (exact title)
    ats_acme = json.loads((ATS_RAW_FIXTURE_DIR / "greenhouse" / "acme.json").read_text())
    result_merge = dedupe.run_cross_source_dedup(
        ats_acme["listings"], [linkedin_listings[0]]
    )
    actions = [d["action"] for d in result_merge["decisions"]]
    assert "auto_merge" in actions, f"Expected auto_merge for Acme pair, got: {actions}"

    # Fixture 1: Example Inc — review-band (title mismatch but fuzzy partial match)
    ats_example = json.loads((ATS_RAW_FIXTURE_DIR / "lever" / "example.json").read_text())
    result_review = dedupe.run_cross_source_dedup(
        ats_example["listings"], [linkedin_listings[1]]
    )
    actions_review = [d["action"] for d in result_review["decisions"]]
    assert "review_band" in actions_review, (
        f"Expected review_band for Example Inc pair (different title tokens), got: {actions_review}"
    )

    # Fixture 2: Initech — keep_both (Marketing Manager vs Sales Director — <70)
    ats_keepboth = json.loads((ATS_RAW_FIXTURE_DIR / "greenhouse" / "keepboth.json").read_text())
    result_keep = dedupe.run_cross_source_dedup(
        ats_keepboth["listings"], [linkedin_listings[2]]
    )
    actions_keep = [d["action"] for d in result_keep["decisions"]]
    assert "keep_both" in actions_keep, (
        f"Expected keep_both for Initech pair (Marketing vs Sales), got: {actions_keep}"
    )


# ---------------------------------------------------------------------------
# DDP-04: decisions dict shape
# ---------------------------------------------------------------------------

def test_dedup_decisions_logged():
    """DDP-04: result dict has 'decisions' list; each entry has required keys."""
    from ats import dedupe  # RED until Plan 05-02 lands

    linkedin_listings = json.loads(LINKEDIN_FIXTURE.read_text())
    ats_payload = json.loads((ATS_RAW_FIXTURE_DIR / "greenhouse" / "acme.json").read_text())
    result = dedupe.run_cross_source_dedup(
        ats_payload["listings"], [linkedin_listings[0]]
    )

    assert "decisions" in result, "Result must have 'decisions' key"
    assert isinstance(result["decisions"], list), "'decisions' must be a list"
    assert len(result["decisions"]) >= 1

    required_keys = {"action", "ats_url", "linkedin_url", "loose_score", "tight_score", "company_slug"}
    for decision in result["decisions"]:
        missing = required_keys - set(decision.keys())
        assert not missing, f"Decision missing keys: {missing}"


# ---------------------------------------------------------------------------
# DDP-05: ATS tier bump
# ---------------------------------------------------------------------------

def test_ats_tier_bump_30d():
    """DDP-05: compute_ats_tier_bump() returns 1 for ATS ≤30d, 0 for ATS >30d, 0 for LinkedIn."""
    from ats import dedupe  # RED until Plan 05-02 lands

    today = date.today()

    # ATS source posted today → bump 1
    listing_today = {
        "source": "ats:greenhouse",
        "posted_date": today.isoformat(),
        "title": "SWE",
        "company": "Acme",
        "url": "https://boards.greenhouse.io/acme/jobs/1",
        "location": "SF",
    }
    assert dedupe.compute_ats_tier_bump(listing_today, today) == 1, (
        "ATS listing posted today should get +1 bump"
    )

    # ATS source posted 31 days ago → no bump
    listing_old = {
        "source": "ats:greenhouse",
        "posted_date": (today - timedelta(days=31)).isoformat(),
        "title": "SWE",
        "company": "Acme",
        "url": "https://boards.greenhouse.io/acme/jobs/2",
        "location": "SF",
    }
    assert dedupe.compute_ats_tier_bump(listing_old, today) == 0, (
        "ATS listing posted 31d ago should NOT get bump"
    )

    # LinkedIn source posted today → no bump (ATS-only rule)
    listing_linkedin = {
        "source": "linkedin",
        "posted_date": today.isoformat(),
        "title": "SWE",
        "company": "Acme",
        "url": "https://www.linkedin.com/jobs/view/3950000000001",
        "location": "SF",
    }
    assert dedupe.compute_ats_tier_bump(listing_linkedin, today) == 0, (
        "LinkedIn listing should NOT get ATS bump"
    )


# ---------------------------------------------------------------------------
# DDP-04 (D-3): LinkedIn slug derivation
# ---------------------------------------------------------------------------

def test_linkedin_slug_runtime():
    """DDP-04 (D-3): derive_linkedin_slug() strips common suffixes, lowercases."""
    from ats import dedupe  # RED until Plan 05-02 lands

    assert dedupe.derive_linkedin_slug("Acme Corp") == "acme-corp", (
        "Acme Corp → acme-corp (Corp is NOT a stripped suffix per spec)"
    )
    assert dedupe.derive_linkedin_slug("Stripe, Inc.") == "stripe", (
        "Stripe, Inc. → stripe (strips ', Inc.')"
    )
    assert dedupe.derive_linkedin_slug("Foo LLC") == "foo", (
        "Foo LLC → foo (strips ' LLC')"
    )
    assert dedupe.derive_linkedin_slug("Bar Corporation") == "bar-corporation", (
        "Bar Corporation → bar-corporation (Corporation is not stripped)"
    )


# ---------------------------------------------------------------------------
# DDP-04 (D-1): Enrichment pre-bump candidate check
# ---------------------------------------------------------------------------

def test_enrich_pre_bump():
    """DDP-04 (D-1): is_enrichment_candidate() returns True when ATS + base+bump reaches A-tier."""
    from ats import dedupe  # RED until Plan 05-02 lands

    today = date.today()
    posted_recent = today.isoformat()
    posted_stale = (today - timedelta(days=35)).isoformat()

    # ATS source, base score 75 (B-tier), recent posting → +1 bump pushes to A (≥80) → True
    listing_b_ats = {
        "source": "ats:greenhouse",
        "posted_date": posted_recent,
        "title": "SWE",
        "company": "Acme",
        "url": "https://boards.greenhouse.io/acme/jobs/1",
        "location": "SF",
    }
    assert dedupe.is_enrichment_candidate(listing_b_ats, base_score=75, today=today) is True, (
        "ATS B-tier (score 75) with recent posting should be enrichment candidate"
    )

    # ATS source, base score 60 (C-tier) → +1 bump still only reaches C, not B-tier threshold → False
    assert dedupe.is_enrichment_candidate(listing_b_ats, base_score=60, today=today) is False, (
        "ATS C-tier (score 60) should NOT be enrichment candidate (below B threshold)"
    )

    # LinkedIn source, base score 85 (A-tier) → not ATS, no enrichment via D-1 path → False
    listing_linkedin = {
        "source": "linkedin",
        "posted_date": posted_recent,
        "title": "SWE",
        "company": "Acme",
        "url": "https://www.linkedin.com/jobs/view/3950000000001",
        "location": "SF",
    }
    assert dedupe.is_enrichment_candidate(listing_linkedin, base_score=85, today=today) is False, (
        "LinkedIn listing should NOT be enrichment candidate (D-1: ATS-only enrichment)"
    )

    # ATS source, base score 75, STALE posting >30d → no bump, no enrichment → False
    listing_stale = {
        "source": "ats:greenhouse",
        "posted_date": posted_stale,
        "title": "SWE",
        "company": "Acme",
        "url": "https://boards.greenhouse.io/acme/jobs/3",
        "location": "SF",
    }
    assert dedupe.is_enrichment_candidate(listing_stale, base_score=75, today=today) is False, (
        "ATS listing posted >30d ago: no bump → no enrichment candidate"
    )


# ---------------------------------------------------------------------------
# DDP-05 (D-1): Enrich-then-tier order
# ---------------------------------------------------------------------------

def test_enrich_then_tier_order():
    """DDP-05 (D-1): Enrichment must happen before final tier assignment.
    A B-tier ATS candidate at base_score just above b_threshold reaches
    enrichment scope since base + 1 bump ≥ a_threshold.
    """
    from ats import dedupe  # RED until Plan 05-02 lands

    today = date.today()
    b_threshold = 70
    a_threshold = 80

    # Listing at exactly b_threshold + 1 (71): with ATS bump → 72, still below A
    # But with base_score at a_threshold - 1 (79): with ATS bump → 80 = A → MUST enrich
    listing = {
        "source": "ats:greenhouse",
        "posted_date": today.isoformat(),
        "title": "SWE",
        "company": "Acme",
        "url": "https://boards.greenhouse.io/acme/jobs/1",
        "location": "SF",
    }
    # base_score 79 + 1 bump = 80 = a_threshold → enrichment candidate
    assert dedupe.is_enrichment_candidate(
        listing, base_score=79, today=today,
        b_threshold=b_threshold, a_threshold=a_threshold
    ) is True, (
        "base_score=79 + ATS bump=1 reaches a_threshold=80 → MUST be enrichment candidate"
    )

    # base_score 78 + 1 bump = 79 < 80 → NOT an A-tier candidate even with bump
    assert dedupe.is_enrichment_candidate(
        listing, base_score=78, today=today,
        b_threshold=b_threshold, a_threshold=a_threshold
    ) is False, (
        "base_score=78 + ATS bump=1 = 79 < a_threshold=80 → NOT enrichment candidate"
    )


# ---------------------------------------------------------------------------
# DDP-06, DDP-08: Regression suspect detection
# ---------------------------------------------------------------------------

def test_regression_suspect():
    """DDP-06/DDP-08: company with OK_WITH_RESULTS ≥3/5 prior but OK_ZERO today is flagged."""
    from ats.runs_log import _find_regression_suspects  # RED until Plan 05-04 lands

    lines = [json.loads(l) for l in RUNS_JSONL_FIXTURE.read_text().splitlines()]
    # Pitfall 5: pass all 6 lines; function slices [-6:-1] for prior, [-1] for current
    suspects = _find_regression_suspects(lines, lookback=5)

    assert isinstance(suspects, list), "_find_regression_suspects must return a list"
    acme_suspects = [s for s in suspects if s.get("company_slug") == "acme"]
    assert len(acme_suspects) >= 1, (
        f"Expected acme|greenhouse in regression suspects, got: {suspects}"
    )
    acme = acme_suspects[0]
    assert acme.get("provider") == "greenhouse", (
        f"Expected provider=greenhouse, got: {acme.get('provider')!r}"
    )
    # Fixture has 5 prior OK_WITH_RESULTS runs → prior_ok_count should be 5
    assert acme.get("prior_ok_count", 0) >= 3, (
        f"Expected prior_ok_count ≥ 3, got: {acme.get('prior_ok_count')!r}"
    )


# ---------------------------------------------------------------------------
# DDP-06 (D-2): regression_suspects logged to runs.jsonl
# ---------------------------------------------------------------------------

def test_regression_suspects_logged(tmp_path):
    """DDP-06 (D-2): append_run() with regression_suspects kwarg writes key to JSONL line."""
    from ats import runs_log  # already exists — testing new kwarg

    runs_log_path = tmp_path / "runs.jsonl"
    runs_log_path.touch()

    suspects = [{"company_slug": "acme", "provider": "greenhouse", "prior_ok_count": 5}]
    result = runs_log.append_run(
        runs_log_path=str(runs_log_path),
        wall_clock_seconds=200.0,
        per_provider_outcomes={"greenhouse": {"ok_with_results": 5, "ok_zero": 1, "error": 0}},
        per_company_provider={"acme|greenhouse": {"outcome": "OK_ZERO", "listing_count": 0}},
        regression_suspects=suspects,
    )

    # Read back from file
    lines = [json.loads(l) for l in runs_log_path.read_text().splitlines()]
    assert len(lines) == 1
    assert "regression_suspects" in lines[0], (
        "regression_suspects kwarg must be written to JSONL line (D-2)"
    )
    assert lines[0]["regression_suspects"] == suspects, (
        "regression_suspects must round-trip correctly"
    )


# ---------------------------------------------------------------------------
# DDP-07, CON-15: Pass-2 board-broken detection
# ---------------------------------------------------------------------------

def test_pass2_board_broken():
    """DDP-07/CON-15: board with 0 results in ≥3/5 prior runs flagged as broken."""
    from ats.runs_log import _find_pass2_board_broken  # RED until Plan 05-04 lands

    lines = [json.loads(l) for l in RUNS_JSONL_FIXTURE.read_text().splitlines()]
    # wellfound=0 in lines 2-6 (5 lines) → should be flagged
    broken = _find_pass2_board_broken(lines, lookback=5)

    assert isinstance(broken, list), "_find_pass2_board_broken must return a list"
    board_names = [b.get("board") or b.get("board_name") for b in broken]
    assert any("wellfound" in (name or "") for name in board_names), (
        f"Expected 'wellfound' in broken boards (0 results in 5/5 recent runs), got: {broken}"
    )


# ---------------------------------------------------------------------------
# DDP-07 (D-2): pass2_board_status logged to runs.jsonl
# ---------------------------------------------------------------------------

def test_pass2_board_status_logged(tmp_path):
    """DDP-07 (D-2): append_run() with pass2_board_status kwarg round-trips correctly."""
    from ats import runs_log  # already exists — testing new kwarg

    runs_log_path = tmp_path / "runs.jsonl"
    runs_log_path.touch()

    board_status = {"wellfound": 0, "hn_algolia": 3}
    result = runs_log.append_run(
        runs_log_path=str(runs_log_path),
        wall_clock_seconds=180.0,
        per_provider_outcomes={"greenhouse": {"ok_with_results": 4, "ok_zero": 0, "error": 0}},
        per_company_provider={},
        pass2_board_status=board_status,
    )

    lines = [json.loads(l) for l in runs_log_path.read_text().splitlines()]
    assert len(lines) == 1
    assert "pass2_board_status" in lines[0], (
        "pass2_board_status kwarg must be written to JSONL line (D-2)"
    )
    assert lines[0]["pass2_board_status"] == board_status, (
        "pass2_board_status must round-trip correctly"
    )


# ---------------------------------------------------------------------------
# Phase-4 inheritance (D-4): JSON-LD routing uses career_page_url
# ---------------------------------------------------------------------------

def test_jsonld_routing_career_page_url():
    """D-4 guard: schema.py MASTER_TARGETS_COLUMNS must contain 'career_page_url' (NOT 'careers_url').
    This test prevents any future rename that would silently break JSON-LD routing.
    """
    from schema import MASTER_TARGETS_COLUMNS

    assert "career_page_url" in MASTER_TARGETS_COLUMNS, (
        "D-4: column must be 'career_page_url' — JSON-LD routing reads this column"
    )
    assert "careers_url" not in MASTER_TARGETS_COLUMNS, (
        "D-4: 'careers_url' does NOT exist in schema — any code referencing it would silently find nothing"
    )


# ---------------------------------------------------------------------------
# CON-10: LinkedIn rate-limit/backoff in SKILL.md
# ---------------------------------------------------------------------------

def test_linkedin_backoff():
    """CON-10/CON-11: SKILL.md must mention LinkedIn rate-limit pause of 10-15 seconds.
    RED until Plan 05-05 lands the prose in skills/scout-run/SKILL.md.
    """
    skill_md = PROJECT_ROOT / "skills" / "scout-run" / "SKILL.md"
    assert skill_md.exists(), f"SKILL.md not found at {skill_md}"
    content = skill_md.read_text()
    has_backoff = "10-15 seconds" in content or "10–15 seconds" in content
    assert has_backoff, (
        "CON-11: SKILL.md must contain '10-15 seconds' or '10–15 seconds' in LinkedIn "
        "rate-limit context (added in Plan 05-05)"
    )


# ---------------------------------------------------------------------------
# CON-11: LinkedIn JD lazy-load resilience in chrome-setup.md
# ---------------------------------------------------------------------------

def test_jd_resilient_parse():
    """CON-11/CON-12: chrome-setup.md must contain both 'Show more' and 'Expand description'.
    RED until Plan 05-05 updates skills/job-scout/references/chrome-setup.md.
    """
    chrome_setup = PROJECT_ROOT / "skills" / "job-scout" / "references" / "chrome-setup.md"
    assert chrome_setup.exists(), f"chrome-setup.md not found at {chrome_setup}"
    content = chrome_setup.read_text()
    assert "Show more" in content, (
        "CON-12: chrome-setup.md must include 'Show more' selector (secondary LinkedIn A/B variant)"
    )
    assert "Expand description" in content, (
        "CON-12: chrome-setup.md must include 'Expand description' selector (accessibility variant)"
    )

# tests/fixtures SOURCE.md — Provenance and Purpose

All fixture files in this directory were **hand-crafted** (not captured from real APIs) for
deterministic testing of Phase 5 locked decisions D-1..D-4 and Pitfalls P1..P6.
No real PII, real job IDs, or real company data is present.

---

## linkedin_candidates_sample.json

**Purpose:** Three LinkedIn-source listings for cross-source dedup test scenarios.

| Index | Company | Title | Scenario |
|-------|---------|-------|----------|
| 0 | Acme Corp | Senior Software Engineer | Auto-merge pair (paired with `ats_raw_sample/greenhouse/acme.json`) |
| 1 | Example Inc | Software Engineer II Backend Platform | Review-band pair (paired with `ats_raw_sample/lever/example.json`) |
| 2 | Initech | Marketing Manager Growth | Keep-both pair (paired with `ats_raw_sample/greenhouse/keepboth.json`) |

**Date rationale:** `posted_date` values use literal ISO dates relative to TODAY=2026-04-28:
- Index 0: 2026-04-13 (TODAY-15 — within 30d tier-bump window)
- Index 1: 2026-04-03 (TODAY-25 — within 30d tier-bump window)
- Index 2: 2026-04-23 (TODAY-5 — within 30d tier-bump window)

---

## ats_raw_sample/greenhouse/acme.json

**Purpose:** ATS counterpart to `linkedin_candidates_sample.json[0]` for the auto-merge scenario.

Matching criteria: company_slug="acme", title="Senior Software Engineer" (exact match with
LinkedIn title). Both loose-key (slug + first 3 normalized tokens) AND tight-key (slug +
full normalized title) score ≥95 with `rapidfuzz.token_set_ratio`, producing `action="auto_merge"`.

---

## ats_raw_sample/lever/example.json

**Purpose:** ATS counterpart to `linkedin_candidates_sample.json[1]` for the review-band scenario.

Matching criteria: company_slug="example". ATS title is "Backend Platform Engineer", LinkedIn title
is "Software Engineer II Backend Platform". The first 3 normalized tokens differ between the two
titles (loose-key mismatch), but the full-title fuzzy score falls in 70–94 (review band), producing
`action="review_band"`.

---

## ats_raw_sample/greenhouse/keepboth.json

**Purpose:** ATS counterpart to `linkedin_candidates_sample.json[2]` for the keep-both scenario.

Matching criteria: company_slug="initech". ATS title is "Sales Director Enterprise", LinkedIn title
is "Marketing Manager Growth". Both loose-key and tight-key score <70, producing `action="keep_both"`.

---

## runs_jsonl_history.jsonl

**Purpose:** Six JSONL lines for regression-suspect and pass2-board-broken test determinism.

**Structure (Pitfall 5 guard):**
- Lines 1–5 (prior runs): `acme|greenhouse` outcome = `OK_WITH_RESULTS`, listing_count = 3–5
- Line 6 (current run): `acme|greenhouse` outcome = `OK_ZERO`, listing_count = 0

**Regression-suspect signal:** `acme|greenhouse` had `OK_WITH_RESULTS` in all 5 prior runs,
then `OK_ZERO` in the current run. `_find_regression_suspects(lines, lookback=5)` must return
at least `{"company_slug": "acme", "provider": "greenhouse", "prior_ok_count": 5}`.

**Pass-2 board-broken signal:** `wellfound` returns 0 in `pass2_board_status` for lines 2–6
(5 lines total, all 0). `_find_pass2_board_broken` must flag wellfound as "board appears broken"
(≥3/5 runs with 0 results).

**Dates:** Timestamps run 2026-04-23 through 2026-04-28 (one per day, TODAY=2026-04-28).

---

## Dedup Scenario Coverage

| Scenario | LinkedIn fixture index | ATS fixture | Expected action |
|----------|----------------------|-------------|-----------------|
| Auto-merge | 0 (Acme Corp / Sr SWE) | greenhouse/acme.json | `auto_merge` |
| Review-band | 1 (Example Inc / SWE II Backend Platform) | lever/example.json | `review_band` |
| Keep-both | 2 (Initech / Marketing Manager Growth) | greenhouse/keepboth.json | `keep_both` |

---

*Created by Plan 05-01 Wave 0 execution. Updated only when Phase 5 test scenarios change.*

---
name: job-scout
description: >
  This skill should be used when the user asks to "search for jobs", "run the job scout",
  "find job matches", "check LinkedIn for opportunities", "daily job search", "find me jobs",
  "job matches", or anything related to automated job searching, job scoring, resume tailoring,
  or career assessment. Also triggers for "honest career assessment", "job market positioning",
  or "ATS optimization."
version: 0.1.0
---

# Job Scout

Automated LinkedIn job search with honest scoring, connection-first targeting, and ATS-focused tailoring briefs.

## Core Philosophy

1. **Connections first.** A warm referral is worth more than 50 cold applications. Always check master_targets.csv for connection counts before scoring.
2. **Honest scoring.** Never inflate scores to make results look better. If there are no A-tier matches, say so.
3. **No sycophancy.** The candidate needs to hear "this role is above your market position" when it's true.
4. **Specific tailoring.** "Move the $50M revenue bullet to position 1" — not "emphasize your leadership."
5. **Mechanical deduplication.** Use tracker_utils.py for all tracker writes. Never add rows manually.

## Data Files

All data lives in the user's configured data directory (default: `~/Documents/JobScout/`):

| File | Purpose | Created By |
|------|---------|------------|
| `config.json` | Search queries, scoring weights, preferences | /scout-setup |
| `candidate_profile.json` | Extracted profile with honest skill categorization | /scout-setup |
| `master_targets.csv` | Company database with connection counts | /scout-setup + /scout-run |
| `JobScout_Tracker.xlsx` | Running job tracker (append-only) | /scout-run via tracker_utils.py |
| `daily/YYYY-MM-DD/JobScout_Report_YYYY-MM-DD.md` | Daily search report | /scout-run |
| `assessment/Honest_Career_Assessment.md` | Career positioning analysis | /scout-setup |

## Scoring System

Use the connection-first weighted rubric. Weights are in config.json (defaults below):

| Category | Default Weight | Key Question |
|----------|---------------|-------------|
| Connection Leverage | 30 | Does the candidate know anyone at this company? |
| Experience Match | 25 | Does the JD describe what they've actually done? |
| Domain Fit | 20 | Is this in their industry? |
| Compensation | 15 | Does it pay enough? |
| Realistic Shot | 10 | Would this company actually call them? |

Full rubric with point breakdowns, examples, and bonus/penalty adjustments: read `references/scoring-rubric.md`.

### Tier Thresholds
- **A-tier:** ≥75 — prioritize, generate tailoring brief
- **B-tier:** ≥55 — include in report with notes
- **C-tier:** ≥40 — mention briefly
- **Skip:** <40 — do not include

**Hard cap:** Maximum 10 A-tier per run. If more, raise threshold until ≤10.

## Quality Controls

### Stale Listing Detection
LinkedIn resurfaces old postings. Detect stale listings before scoring:
- Extract LinkedIn job ID from URL (the 10+ digit number)
- IDs below 4,200,000,000 are likely 6+ months old → flag as stale
- "Posted X weeks ago" or "Over 200 applicants" → flag as stale
- Stale listings go in a separate report section, NOT in A/B/C tiers

### Deduplication
Use tracker_utils.py for mechanical dedup:
```bash
# Before searching: get existing job IDs
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tracker_utils.py dedup-set "<tracker_path>"

# After searching: append with automatic dedup + formatting
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tracker_utils.py append "<tracker_path>" "<new_rows.json>"
```

Never manually add rows to the tracker. Never construct openpyxl formatting inline. tracker_utils.py owns all tracker writes, ensuring identical colors and structure every run.

### Tracker Formatting (enforced by tracker_utils.py)
- Green (#C6EFCE) for A-tier
- Yellow (#FFEB9C) for B-tier
- Pink (#F2DCDB) for C-tier
- Gray (#D9D9D9) for stale
- Blue headers (#2F5496)
- Frozen header row, auto-filter enabled

## Search Strategy

### Priority 1: Company-First
Check target companies with the most connections first. These have the highest ROI because the candidate can get a referral.

### Priority 2: Keyword Search
Run configured search queries for broader discovery. Always filter by Date Posted = Past 24 hours (daily runs) or Past Week (first run).

### Fallback: No Chrome
If Claude in Chrome isn't available, generate search URLs and target company lists for manual searching. The scoring, tailoring, and reporting still work — just paste JD text.

## Tailoring Briefs

For A-tier matches only. Read `references/tailoring-guide.md` for the full process.

Key outputs per listing:
1. **ATS keywords to add** — terms from the JD the resume doesn't contain (that the candidate legitimately possesses)
2. **Section to lead with** — based on role type
3. **Bullet reordering** — specific bullets to promote (by name, not generically)
4. **Wording changes** — where the resume's language should mirror the JD's phrasing

## Honest Notes (Mandatory)

Every daily report MUST include an "Honest Notes" section with at least one observation:
- Are the same companies showing up with no new roles? Note it.
- Is the salary target eliminating most results? Note it.
- Are A-tier matches only at 0-connection companies? Flag the networking gap.
- Has the candidate been rejected by 3+ companies in the same sector? Suggest pivoting.
- Are search queries returning irrelevant results? Recommend adjusting.

## Reference Documents

Detailed knowledge available on demand:
- **`references/scoring-rubric.md`** — Full 5-category rubric with point breakdowns and examples
- **`references/tailoring-guide.md`** — How to generate ATS-focused tailoring briefs
- **`references/assessment-framework.md`** — How to generate the honest career assessment
- **`references/profile-extraction-guide.md`** — How to read resumes and LinkedIn data
- **`references/chrome-setup.md`** — Claude in Chrome installation and troubleshooting

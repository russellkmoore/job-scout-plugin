---
name: job-scout
description: >
  This skill should be used when the user asks to "search for jobs", "run the job scout",
  "find job matches", "check LinkedIn for opportunities", "daily job search", "find me jobs",
  "job matches", or anything related to automated job searching, job scoring, resume tailoring,
  or career assessment. Also triggers for "honest career assessment", "job market positioning",
  or "ATS optimization."
version: 0.2.0
---

# Job Scout

Automated LinkedIn job search with honest scoring, connection-first targeting, and ATS-focused tailoring briefs.

## Core Philosophy

1. **Connections first.** A warm referral is worth more than 50 cold applications. Always check master_targets.csv for connection counts before scoring.
2. **Honest scoring.** Never inflate scores to make results look better. If there are no A-tier matches, say so.
3. **No sycophancy.** The candidate needs to hear "this role is above your market position" when it's true.
4. **Specific tailoring.** "Move the $50M revenue bullet to position 1" — not "emphasize your leadership."
5. **Mechanical deduplication.** Use tracker_utils.py for all tracker writes. Never add rows manually.
6. **Company-first searching.** Always check target companies directly before running keyword searches. Keyword searches are secondary.

## Data Files

All data lives in the user's data directory. Look for config.json in this order:
1. `~/Documents/JobSearch/config.json`
2. `~/Documents/JobScout/config.json`
3. The path specified in config.json `data_dir` field

| File | Purpose | Created By |
|------|---------|------------|
| `config.json` | Search queries, scoring weights, preferences | /scout-setup |
| `candidate_profile.json` | Extracted profile with honest skill categorization | /scout-setup |
| `master_targets.csv` | Company database with connection counts | /scout-setup + /scout-run |
| `JobScout_Tracker.xlsx` | Running job tracker (append-only) | /scout-run via tracker_utils.py |
| `daily/YYYY-MM-DD/JobScout_Report_YYYY-MM-DD.md` | Daily search report | /scout-run |
| `assessment/Honest_Career_Assessment.md` | Career positioning analysis | /scout-setup |

Also look for supplemental data files in the same directory — pipeline spreadsheets, saved company lists, connections CSVs, etc. These provide additional context for company-first searching.

## Chrome Browsing (IMPORTANT)

When using Claude in Chrome to browse LinkedIn:

- **Be patient with page loads.** LinkedIn can be slow. Wait for content to render before trying to read.
- **Pagination.** Check at least 2-3 pages per search query.
- **Rate limiting.** Don't click too rapidly. Pause between navigation actions.
- **Reading JDs.** After clicking into a listing, scroll down and wait before reading. Use `get_page_text` first. If the JD doesn't appear, try scrolling via `javascript_tool` with `window.scrollTo(0, 1000)` then read again.
- **Promoted/external listings.** Some listings say "Responses managed off LinkedIn" or "Promoted by hirer" — these often don't have JDs on LinkedIn. Note them with available metadata (title, company, salary, location) and move on.
- **Company page Jobs tab.** Navigate directly to `linkedin.com/company/[name]/jobs/` — this is more reliable than using URL filter parameters like `f_C=`.
- **Boolean queries.** Use OR operators and quoted phrases in keyword searches for precision: `"VP engineering" OR "director of engineering" e-commerce` works better than `VP engineering director e-commerce`.
- **Never enter credentials.** If not logged in, stop and ask the user.

## Scoring System

Use the connection-first weighted rubric. Full details in `references/search-config.md`.

| Category | Weight | What to evaluate |
|----------|--------|-----------------|
| Connection Leverage | 30 | 1-2 connections = 15. 3-5 = 20. 6+ = 25. Referral possible = 30. None = 0. **MOST IMPORTANT.** |
| Experience Match | 25 | Does JD describe what candidate has done? 80%+ match = 25. Deduct for credential gaps. |
| Domain Fit | 20 | Candidate's industry sweet spot = 20. Adjacent = 15. Unrelated = 5. Mismatch = 0. |
| Compensation | 15 | Above target = 15. Includes target = 10. Below = 0. |
| Realistic Shot | 10 | Would they get a callback? Consider competition, credential screening, role freshness. |

### Bonus Points
- +10 warm introduction possible (named connection who could refer)
- +5 role values founder/startup/entrepreneurial experience
- +5 military veteran preference (if applicable)
- +5 company on candidate's target pipeline list
- +3 role involves building a team from scratch

### Penalty Points
- -15 requires PhD, elite MBA, or deep ML research (unless candidate has these)
- -10 clearly IC role with no leadership
- -10 JD targets FAANG/Big 3 consulting background specifically
- -5 reposted multiple times

### Tier Thresholds
- **A-tier (≥75):** Prioritize, generate tailoring brief
- **B-tier (≥55):** Include in report with notes
- **C-tier (≥40):** Mention briefly
- **Skip (<40):** Do not include

**Hard cap:** Maximum 10 A-tier per run.

## Search Strategy

Read `references/search-config.md` for the full search framework.

### Priority 1: Company-First (Highest ROI)
Check target companies directly on their LinkedIn Jobs page. Select companies by connection count, last_checked recency, and pipeline status. Also rotate through supplemental company lists the candidate provided.

### Priority 2: Keyword Searches
Run configured queries with Boolean operators and filters. Always filter by Date Posted (Past 24 hours daily, Past week first run) and Experience Level (Director/Executive).

### Priority 3: Underutilized Asset Searches
Run queries targeting the candidate's unique differentiators (clearances, language skills, founder experience, etc.).

### Fallback: No Chrome
Generate clickable search URLs + target company list for manual browsing. Score and tailor from pasted JD text.

## Quality Controls

### Stale Listing Detection
- Extract LinkedIn job ID from URL (the 10+ digit number)
- IDs below 4,200,000,000 are likely 6+ months old → flag as stale
- "Posted X weeks ago" or "Over 200 applicants" → flag as stale
- Already applied to this company? Check master_targets.csv
- Stale listings go in a separate report section, NOT in A/B/C tiers

### Deduplication
Use tracker_utils.py for mechanical dedup:
```bash
# Before searching: get existing job IDs
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tracker_utils.py dedup-set "<tracker_path>"

# After searching: append with automatic dedup + formatting
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tracker_utils.py append "<tracker_path>" "<new_rows.json>"
```

Never manually add rows to the tracker. tracker_utils.py owns all tracker writes.

### Tracker Formatting (enforced by tracker_utils.py)
- Green (#C6EFCE) for A-tier
- Yellow (#FFEB9C) for B-tier
- Pink (#F2DCDB) for C-tier
- Gray (#D9D9D9) for stale
- Blue headers (#2F5496)
- Frozen header row, auto-filter enabled

## Tailoring Briefs

For A-tier matches only. Read `references/tailoring-guide.md` for the full process.

Key outputs per listing:
1. **ATS keywords to add** — terms from the JD the candidate legitimately possesses but the resume doesn't contain
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
- Did LinkedIn's rendering block JD reading? Note which listings need manual review.

## Reference Documents

- **`references/search-config.md`** — Search strategy, query templates, and full scoring rubric
- **`references/scoring-rubric.md`** — Detailed point breakdowns with examples
- **`references/tailoring-guide.md`** — How to generate ATS-focused tailoring briefs
- **`references/assessment-framework.md`** — How to generate the honest career assessment
- **`references/profile-extraction-guide.md`** — How to read resumes and LinkedIn data
- **`references/chrome-setup.md`** — Claude in Chrome installation and troubleshooting

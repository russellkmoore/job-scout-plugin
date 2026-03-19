---
description: Run a daily job search — browse LinkedIn, score matches, generate report
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, TodoWrite, mcp__Claude_in_Chrome__*
---

Execute a Job Scout search run. Browse LinkedIn using Claude in Chrome, find matches, score them, and produce a daily report + tracker update.

Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/SKILL.md` to load the core job-scout skill knowledge.

## Step 0: Preflight Checks

1. Read config.json from the user's data directory (check `~/Documents/JobScout/config.json` as default)
   - If missing: tell the user "Run /scout-setup first to configure your profile."
   - Stop here if no config.

2. Read candidate_profile.json from the same directory

3. Read master_targets.csv from the same directory

4. Build the dedup set from the existing tracker:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tracker_utils.py dedup-set "<data_dir>/JobScout_Tracker.xlsx"
   ```
   Save this JSON list of existing job IDs — any listing with an ID in this set gets SKIPPED.

5. Check if Claude in Chrome is available — try `tabs_context_mcp`
   - If available: proceed with browser automation
   - If not: switch to fallback mode (generate search queries + target list for manual search, skip to Step 4)

6. If Chrome is available, navigate to `https://www.linkedin.com/jobs/` and verify the user is logged in
   - If not logged in: tell the user to log in and run /scout-run again

## Step 1: Company-First Search (Highest Priority)

Read master_targets.csv and select companies to check today:
- Pick the top N companies from config (default: 5)
- Priority: highest linkedin_connection_count + last_checked is oldest or null + application_status is not "Dead"

For each selected company:
1. Navigate to the company's LinkedIn page → Jobs tab
2. Read all open roles
3. Filter for seniority level match (from config.json target_level)
4. Check if the user already applied (cross-ref master_targets.csv already_applied field)
5. For matching roles: extract title, location, comp, JD text, job URL
6. **Stale check:** Extract the LinkedIn job ID from the URL. If the ID is below 4,200,000,000, flag as stale — do not score, list in the stale section of the report instead.
7. **Dedup check:** If the job ID exists in the dedup set from Step 0, skip entirely.
8. Update last_checked in master_targets.csv for this company

## Step 2: Keyword Search (Secondary)

For each query in config.json search.queries:
1. Enter keywords in LinkedIn job search
2. Apply filters: Date Posted (Past 24 hours for daily runs), Experience Level (from config), Location (from config)
3. Read the first 2-3 pages of results
4. For each listing: extract title, company, location, comp, job URL
5. **Stale check** on every listing (same job ID threshold check)
6. **Dedup check** against Step 0 set AND against Step 1 results
7. Collect all new unique listings

## Step 3: Score & Rank

Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/scoring-rubric.md` for the full rubric.

For each non-stale, non-duplicate listing:
1. Click into the listing to read the full JD
2. Score using the 5-category weighted rubric:
   - **Connection Leverage** (default 30pts): look up company in master_targets.csv
   - **Experience Match** (default 25pts): compare JD requirements vs candidate_profile.json
   - **Domain Fit** (default 20pts): match industry/domain
   - **Compensation** (default 15pts): compare range vs config salary_minimum
   - **Realistic Shot** (default 10pts): honest assessment of whether they'd get a callback
3. Apply bonus/penalty adjustments from the rubric
4. Assign tier: A (≥75), B (≥55), C (≥40), Skip (<40)
5. If more than 10 A-tier matches: raise threshold by 5 until ≤10

For each A-tier match, read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/tailoring-guide.md` and generate a tailoring brief:
- ATS keywords to add
- Section to lead with
- Bullet reordering (specific — name the bullets)
- Wording changes

## Step 4: Generate Outputs

### Daily Report
Write to `<data_dir>/daily/YYYY-MM-DD/JobScout_Report_YYYY-MM-DD.md`:
- Run summary (searches executed, companies checked, listings found, dupes skipped, stale skipped)
- A-tier matches with full scoring breakdown, connection info, tailoring brief
- B-tier matches with shorter notes
- Stale/expired listings that were skipped (table format)
- Companies checked with no current matches
- **Honest Notes section (MANDATORY)** — observations about patterns, positioning, what's working

### Tracker Update
Write new rows to a temporary JSON file, then use tracker_utils.py to append them:
```bash
# Write new_rows.json with the listings to add
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tracker_utils.py append "<data_dir>/JobScout_Tracker.xlsx" "/tmp/scout_new_rows.json"
```
This ensures deterministic deduplication and consistent formatting (same colors every time).

### Master Targets Update
Update last_checked dates in master_targets.csv for companies searched. If the scout discovers a new company worth tracking, append it with data_source = "scout_discovered".

## Step 5: Present Results

Summarize to the user:
- How many new listings found
- How many A-tier / B-tier
- Top match with score and connection info
- Link to the full report
- Any honest observations about the search

If no A-tier matches were found, say so directly — don't inflate B-tier matches to seem more promising than they are.

## Fallback Mode (No Chrome)

If Claude in Chrome is unavailable:
1. Generate all search queries as clickable LinkedIn URLs
2. List the target companies with their careers page URLs
3. Ask the user to paste JD text for any interesting listings they find
4. Score pasted JDs using the same rubric
5. Generate tailoring briefs for A-tier matches
6. Still produce the report and tracker update

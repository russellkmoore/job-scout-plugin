---
description: Run a daily job search — browse LinkedIn, score matches, generate report
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, TodoWrite, mcp__Claude_in_Chrome__*
---

Execute a Job Scout search run. Browse LinkedIn using Claude in Chrome, find matches, score them, and produce a daily report + tracker update.

Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/SKILL.md` to load the core skill knowledge.
Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/search-config.md` to load the search strategy and scoring rubric.

## Step 0: Load Context & Existing State

Before doing anything else, read these files from the user's data directory. Check for config.json in this order: `~/Documents/JobSearch/config.json`, then `~/Documents/JobScout/config.json`. If neither exists, tell the user "Run /scout-setup first."

1. **config.json** — search queries, scoring weights, preferences
2. **candidate_profile.json** — the candidate's extracted profile (same directory as config)
3. **Resume** — read the resume PDF from the path in config.json
4. **master_targets.csv** — company database with connection counts (same directory)
5. **Existing tracker** — build a dedup set of all existing job IDs:
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tracker_utils.py dedup-set "<data_dir>/JobScout_Tracker.xlsx"
   ```
   Any job ID already in this set = skip, do not re-add.
6. **Any supplemental files** the user has (Target_Company_Pipeline.xlsx, Seattle tech company lists, etc.) — check the data directory for CSVs and spreadsheets that look like company lists

**Important:** Build the dedup set BEFORE searching. This prevents duplicate entries.

## Step 1: Open LinkedIn Jobs in Chrome

Use Claude in Chrome tools:

1. Call `tabs_context_mcp` to check if Chrome is available. If not → jump to Fallback Mode at the bottom.
2. Create a new tab or use the existing one
3. Navigate to `https://www.linkedin.com/jobs/`
4. Verify you're logged in — if you see a login page, tell the user and stop
5. Confirm the Jobs page has loaded by reading the page

### Chrome Browsing Tips (IMPORTANT)
- **Be patient with page loads.** LinkedIn can be slow. Wait for content to render before reading.
- **Pagination.** Check at least 2-3 pages per search query.
- **Rate limiting.** Don't click too rapidly. Pause between navigation actions.
- **Reading JDs.** After clicking into a listing, scroll down and wait before trying to read the description. Use `get_page_text` first. If the JD doesn't render, try `javascript_tool` with `window.scrollTo(0, 1000)` then read again. Some promoted listings route externally and won't have JDs on LinkedIn — note these and move on.
- **Never enter credentials.** If not logged in, stop and ask the user.

## Step 2: Company-First Search (Highest Priority)

**This is the most valuable search.** Check target companies directly on LinkedIn.

1. Read `master_targets.csv` and select 5 companies to check today:
   - Priority: highest `linkedin_connection_count` + `last_checked` is oldest or null + `application_status` is not "Dead"
   - Also rotate through any companies from supplemental pipeline lists
2. For each company, navigate to their LinkedIn company page → Jobs tab (e.g., `linkedin.com/company/microsoft/jobs/`)
3. Read the page to see what roles are listed
4. Look for roles matching the candidate's target level (Director, VP, SVP, CTO, Executive)
5. For matching roles, extract: title, location, comp (if shown), job URL
6. **Stale check:** Extract LinkedIn job ID from URL. IDs below 4,200,000,000 = flag as stale.
7. **Dedup check:** Skip if job ID is already in the dedup set from Step 0.
8. Click into promising listings to read the full JD
9. Update `last_checked` in master_targets.csv for each company checked

## Step 3: Keyword Searches

Run search queries from config.json. Use Boolean operators (OR, quoted phrases) for precision. For each query:

1. Navigate to LinkedIn Jobs search with the keywords
2. Apply filters: **Date Posted** = Past 24 hours (daily) or Past week (first run), **Experience Level** = Director / Executive
3. Read the search results page — extract titles, companies, locations, comp ranges, and job URLs from the listing cards
4. **Stale check** and **dedup check** every listing before investigating further
5. Click into new, non-stale listings to read full JDs
6. Read at least 2-3 pages of results per query
7. If a query returns only irrelevant results (wrong domain, wrong level), note it and move on — don't waste time scrolling through noise

## Step 4: Score & Rank

For each new listing found, score using the 5-category weighted rubric from `references/search-config.md`:

| Category | Weight | Key Question |
|----------|--------|-------------|
| Connection Leverage | 30 | Does the candidate know anyone here? Check master_targets.csv. |
| Experience Match | 25 | Does the JD describe what they've actually done? |
| Domain Fit | 20 | Is this in their industry? |
| Compensation | 15 | Does it pay enough? |
| Realistic Shot | 10 | Would this company actually call them? |

Apply bonus/penalty adjustments from the rubric. Assign tiers: A (≥75), B (≥55), C (≥40), Skip (<40).

**Hard cap:** Max 10 A-tier per run.

For each A-tier match, read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/tailoring-guide.md` and generate a specific tailoring brief.

## Step 5: Generate Outputs

### Daily Report
Create `<data_dir>/daily/YYYY-MM-DD/JobScout_Report_YYYY-MM-DD.md` with:
- Run summary (searches executed, companies checked, listings found, dupes skipped, stale skipped)
- A-tier matches with full scoring breakdown, connection info, tailoring brief
- B-tier matches with shorter notes
- Stale/expired listings skipped (table)
- Companies checked with no current matches
- **Honest Notes section (MANDATORY)** — at least one observation about patterns, positioning, what's working or not

### Tracker Update
Write new rows to JSON, then append via tracker_utils.py:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tracker_utils.py append "<data_dir>/JobScout_Tracker.xlsx" "/tmp/scout_new_rows.json"
```

### Master Targets Update
Update `last_checked` dates. If the scout discovers a new company worth tracking, append it with `data_source = "scout_discovered"`.

## Step 6: Present Results

Summarize to the user:
- How many new listings found
- How many A-tier / B-tier
- Top match with score and connection info
- Link to the full report
- Any honest observations

If no A-tier matches were found, say so directly. Don't inflate B-tier matches.

## Fallback Mode (No Chrome)

If Claude in Chrome is unavailable:
1. Generate all search queries as clickable LinkedIn URLs
2. List the target companies with their careers page URLs from master_targets.csv
3. Ask the user to paste JD text for any interesting listings they find
4. Score pasted JDs using the same rubric
5. Generate tailoring briefs for A-tier matches
6. Still produce the report and tracker update

---
name: scout-run
description: Run a daily job search — broad sourcing across LinkedIn, career pages, and other boards, with honest scoring and actionable per-match output. Triggers when the user types `/scout-run` or asks to "run the job scout", "find me jobs", "do a daily job search", "check for new job matches".
allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, TodoWrite, mcp__Claude_in_Chrome__*
version: 0.3.1
---

Execute a Job Scout search run. The scout uses Claude in Chrome to perform a wide, deliberate search across company career pages, several job boards, and LinkedIn — scores matches honestly against the candidate's actual profile — and produces a daily report plus tracker update with **actionable** A-tier output (warm path, ATS keyword diff, outreach draft).

**This skill takes no arguments.** All configuration lives in `{data_dir}/config.json`. If you find yourself wanting to override scoring weights or query lists in a scheduled task, edit `config.json` instead.

Before doing anything else:

- Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/SKILL.md`.
- Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/file-contract.md` (path contract — every output goes to one specific place).
- Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/search-config.md` (per-pass budget rules + scoring rubric).
- Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/job-boards.md` (Pass 2 board specs).

---

## Step 0: Resolve `data_dir`, validate, load context

1. **Resolve `data_dir`:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state.py resolve
   ```
   - Exit code 0 → use the printed path as `<data_dir>`.
   - Exit code 2 → tell the user "No Job Scout state found. Run `/scout-setup` first." Stop.

2. **Validate and auto-migrate the data directory:**
   ```bash
   python3 ${CLAUDE_PLUGIN_ROOT}/scripts/validate_data.py "<data_dir>"
   ```
   This is idempotent. It creates missing files (empty tracker, `daily/` dir) and migrates `master_targets.csv` to add any new schema columns. If it exits non-zero, surface the message to the user and stop — the data dir is broken and needs `/scout-setup` again.

3. **Load context** (every path comes from the file contract — no alternates):
   - `<data_dir>/config.json` — search queries, scoring weights, preferences, `data_dir`, `companies_per_day`, `max_listings_per_run`, tier thresholds. **Use these values verbatim.** Do not let scheduled-task instructions or chat overrides change them. If something needs to change permanently, the user edits `config.json`.
   - `<data_dir>/candidate_profile.json` — extracted profile. Skill categorization (`strongest`/`credible`/`aspirational`) drives honest scoring.
   - The resume PDF at `candidate.resume_path` from `config.json`.
   - `<data_dir>/master_targets.csv` — column schema lives in `${CLAUDE_PLUGIN_ROOT}/scripts/schema.py` (`MASTER_TARGETS_COLUMNS`). Reference columns by name, never by index.
   - **Existing tracker dedup set:**
     ```bash
     python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tracker_utils.py dedup-set "<data_dir>/JobScout_Tracker.xlsx"
     ```
     Returns a JSON list of LinkedIn job IDs. Any listing with an ID in this set is skipped before scoring.

4. **Compute today's run paths** from the file contract:
   - `<data_dir>/daily/<TODAY>/JobScout_Report_<TODAY>.md` (final report)
   - `<data_dir>/daily/<TODAY>/new_rows.json` (input to tracker append)
   - `<data_dir>/daily/<TODAY>/run_log.json` (per-pass stats)
   - `<TODAY>` is the local-date ISO string (`YYYY-MM-DD`).

5. **Compute the per-pass listing budget** from `config.search.max_listings_per_run` (default 50):
   - Pass 1 (company-first): `round(0.60 * max_listings_per_run)`
   - Pass 2 (other boards):  `round(0.25 * max_listings_per_run)`
   - Pass 3 (LinkedIn keyword): `max_listings_per_run - (Pass 1 + Pass 2)`
   Each pass must stop adding listings to the candidate set when it hits its own budget — even if more would qualify. Quality over quantity; budgets enforce focus.

---

## Step 1: Bring up Chrome

1. Call `mcp__Claude_in_Chrome__tabs_context_mcp` to verify Chrome is connected with the extension. If it returns nothing usable, jump to **Fallback Mode** at the bottom.
2. Navigate to `https://www.linkedin.com/feed/` to confirm login. If you see a login page, stop and tell the user.
3. Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/chrome-setup.md` for the LinkedIn JD lazy-load extraction sequence — every LinkedIn listing JD requires the scroll → wait → click "...more" → `get_page_text` flow. Skipping steps gets you only metadata.

Never enter credentials. Never click anything that looks like a payment, profile change, or message to a human.

---

## Step 2: Pass 1 — Company-first deep-dive (≈60% of budget)

This is the highest-signal pass. Pick `companies_per_day` companies (default 8) from `master_targets.csv`:

- Sort: `linkedin_connection_count` desc, then `last_checked` ascending (oldest first), then `application_status` (skip those with `Dead`).
- Take the top `companies_per_day` rows.

For each selected company, hit sources in this order and stop early if you've found qualifying roles:

1. **Career page** (`career_page_url`) — read directly. Career pages give full JDs without lazy-loading and often list roles before LinkedIn does.
2. **ATS board** (`ats_board_url`, if populated) — Greenhouse/Lever/Workday/Ashby. ATS pages have richer filter and structured data.
   - If `ats_provider` is empty but `career_page_url` looks like `boards.greenhouse.io/X`, `jobs.lever.co/X`, `myworkdayjobs.com`, or `<company>.ashbyhq.com`, populate `ats_provider` and `ats_board_url` in `master_targets.csv` for next time.
3. **LinkedIn company jobs tab** (`linkedin.com/company/<slug>/jobs/`) — last resort within Pass 1. Lower signal, but catches roles other sources miss.

For each promising listing:
- Extract: title, location, comp range (if shown), apply URL (prefer the company-direct URL over a LinkedIn redirect), JD text (full).
- Run dedup check against the set from Step 0.
- Run stale check: LinkedIn IDs `< 4_200_000_000` are likely 6+ months recycled — flag, don't drop.
- Add to the candidate set if not duplicate. **Stop adding to Pass 1 candidate set when its budget is reached.**
- Update `last_checked = <TODAY>` in `master_targets.csv` for the company (whether or not you found a match — the visit counts).

If Pass 1 finishes under-budget, do NOT roll the leftover budget into Pass 2 or Pass 3. Under-budget here means there genuinely wasn't enough company-side activity worth tracking; Passes 2 and 3 won't fix that.

---

## Step 3: Pass 2 — Other job boards (≈25% of budget)

Read `${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/job-boards.md` for per-board URL patterns, filters, and parsing gotchas.

For each board, allocate roughly:
- Built In Seattle: ~33% of Pass 2 budget
- Wellfound: ~28%
- YC Work at a Startup: ~20%
- HN "Who is hiring" (current month thread): ~20%

Hit them in that order. Skip a board if:
- Built In Seattle / Wellfound / YC: no listings match the candidate's level filters after the prescribed filter setup.
- HN: the most recent thread is older than 5 weeks (the new thread hasn't dropped yet).

For each listing kept:
- Extract per the board's spec in `job-boards.md`.
- Capture the **direct apply URL** — never the board's listing page (the apply URL is what the user will click in the morning).
- Cross-board dedup: normalize company name + role title, drop second occurrences. Prefer listings with company-direct apply URLs.
- Run dedup against the tracker job-ID set (only useful for listings that came back through LinkedIn elsewhere).
- Add to candidate set until the Pass 2 budget is hit.

---

## Step 4: Pass 3 — LinkedIn keyword search (≈15% of budget, last)

LinkedIn keyword search is the lowest-signal pass and is intentionally last. Use `config.search.queries` and `config.search.underutilized_asset_queries` verbatim.

For each query (in config order, primary first then underutilized):
1. Navigate to LinkedIn Jobs search with the query string.
2. Apply filters: **Date Posted = Past 24 hours** (daily mode; **Past week** for the first run), **Experience Level = Director or Executive**.
3. Read the first page of results. Extract: title, company, location, comp range, job URL.
4. Stale check + dedup check. Skip on hit.
5. For non-stale, non-duplicate listings, click in and run the lazy-load JD extraction sequence to get the full description.
6. Add to candidate set until the Pass 3 budget is hit.
7. **Stop the query early** if the first page is dominated by listings the scout has already seen, or by jobs in obviously wrong domains. LinkedIn's relevance is poor; don't punch through 3 pages of noise.

---

## Step 5: Score every candidate listing

For each listing in the combined candidate set:

1. **Score** with the 5-category weighted rubric from `references/search-config.md` and `references/scoring-rubric.md`:
   | Category | Weight (config-driven) | Key question |
   |---|---|---|
   | Connection leverage | `connection_weight` | Who do we know there? Cross-reference `connection_names` in `master_targets.csv`. |
   | Experience match | `experience_match_weight` | Does the JD describe things in the candidate's `strongest` skills? Penalize if it leans on `aspirational`. |
   | Domain fit | `domain_fit_weight` | Industry/sector overlap with `industries_preferred`? |
   | Compensation | `compensation_weight` | Stated comp range vs `salary_minimum`. |
   | Realistic shot | `realistic_shot_weight` | Credential bias, applicant pool size, recency, repost count. |
2. Apply rubric bonuses/penalties.
3. Assign tier from `config.scoring`:
   - A: `score >= tier_a_threshold`
   - B: `tier_b_threshold <= score < tier_a_threshold`
   - C: anything below `tier_a_threshold` that still scored — keep for visibility, don't go deep.
4. **Hard cap: 10 A-tier listings per run.** If more qualify, raise the effective A threshold for this run only (do NOT edit `config.json`) and demote excess A-tier to B-tier with a note "would-be-A, raised threshold this run."

---

## Step 6: Build the daily report

Write `<data_dir>/daily/<TODAY>/JobScout_Report_<TODAY>.md`. Structure:

### Header
- Run date.
- One-paragraph executive summary: how many companies checked, how many listings found, A/B/C/skip counts, dupes/stale skipped.
- Per-pass breakdown (Pass 1 / Pass 2 / Pass 3): listings found, kept after dedup+stale, scored.

### A-tier (each one is "actionable")
For every A-tier listing, render this block — every field is required:

```
### <Company> — <Role Title>
- **Score:** <total> (Conn <c>, Exp <e>, Dom <d>, Comp <co>, Real <r>; bonuses/penalties: <list>)
- **Apply:** <direct apply URL>
- **Comp:** <range or "not stated">
- **Location:** <location / remote status>
- **Source:** <career_page | ats:<provider> | linkedin | builtin | wellfound | yc | hn>
- **Warm path:** <named contact from connection_names + their title at the company, OR "no warm path">
- **ATS keyword diff (don't fabricate):**
  - Missing from resume: <up to 8 keywords pulled from JD that candidate genuinely has but hasn't surfaced>
  - Worth re-ordering: <bullets to promote in resume>
  - Don't add (aspirational): <keywords from JD that candidate doesn't actually have>
- **Outreach draft** (to the warm-path contact, if one exists):
  > <2-3 sentence message; reference a specific connection point — shared company, shared cohort, mutual contact name>
- **Recommended resume version:** <filename from <data_dir>/Resumes/, or "use base resume">
- **Honest read:** <one or two lines on whether this is genuinely worth applying — including whether credential bias or applicant volume makes it a long shot>
```

### B-tier (lighter)
For each B-tier listing, render:
```
### <Company> — <Role Title>
- **Score:** <total>
- **Apply:** <URL>
- **Warm path:** <name + title, or "no warm path">
- **Why B and not A:** <one specific reason — "no warm path", "comp tops out below minimum", "aspirational match on AI strategy">
```

### C-tier (table only, no detail)
A simple table: Company | Role | Score | Apply URL.

### Stale / skipped
A table of stale-flagged or otherwise-deferred listings, with the reason.

### Companies checked, no current matches
Bullet list with the companies from Pass 1 that didn't yield anything — useful for the user's situational awareness.

### Honest notes (MANDATORY)
At least one paragraph. Patterns observed, what's working, what's not. Do not soften. If results were thin, say results were thin and why.

### Generate-on-demand packets
Final line of the report:
> To generate full packets (tailored resume + outreach drafts) for A-tier matches, reply with: `pack <id1> <id2> ...` using the IDs from the Apply URLs.

---

## Step 7: Update the tracker

Write `<data_dir>/daily/<TODAY>/new_rows.json` — a JSON array of objects using the keys in `TRACKER_JSON_KEYS` from `${CLAUDE_PLUGIN_ROOT}/scripts/schema.py`. One object per A/B/C tier listing surfaced this run. Then:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tracker_utils.py append \
  "<data_dir>/JobScout_Tracker.xlsx" \
  "<data_dir>/daily/<TODAY>/new_rows.json"
```

The script handles dedup, stale flagging, and color formatting deterministically. Capture stdout (a JSON summary) into `run_log.json`.

---

## Step 8: Update master_targets.csv

- Update `last_checked = <TODAY>` for every company you visited in Pass 1.
- For any newly discovered company worth tracking (Pass 2 or Pass 3 surfaced a high-quality role), append a row with:
  - `data_source = "scout_discovered"`
  - `last_checked = <TODAY>`
  - `connection_names`, `linkedin_connection_count` left empty unless you can fill them
  - `fit_notes` = the role title that triggered discovery + score
- Persist by overwriting `master_targets.csv`. Schema must match `MASTER_TARGETS_COLUMNS` from `schema.py`.

---

## Step 9: Summarize to the user (chat output)

After writing files, summarize in chat:
- Counts: companies checked, listings scored, A / B / C, skipped (dupe / stale).
- Top match: company, role, score, warm-path status, apply URL.
- Link to the full report: `[View today's report](file://<data_dir>/daily/<TODAY>/JobScout_Report_<TODAY>.md)`.
- One honest observation pulled from the report's "Honest notes" section.

If zero A-tier matches were found, **say so directly**. Do not promote B-tier to make the run feel more productive. The user trusts the scout because it doesn't inflate.

---

## On-demand: generate A-tier packet

If the user replies with `pack <id1> <id2> ...` (or just identifies an A-tier match they want packaged):

For each match, create `<data_dir>/daily/<TODAY>/packets/<Company>_<Role>/`:
- `jd.md` — the full JD text.
- `tailored_resume.docx` — built from the recommended resume version with ATS diff applied. Use the `docx` skill if available. **Never fabricate skills**: only re-order, re-word, and surface things the candidate already has.
- `ats_diff.md` — the diff that informed the tailored resume.
- `outreach_draft.md` — finalized outreach message, ready to copy-paste.

After generation, present a single chat link to the packet folder.

---

## Fallback Mode (Chrome unavailable)

If Step 1 confirms Chrome isn't connected:

1. Generate clickable URLs for every Pass 1 source (career page, ATS board, LinkedIn company jobs) and every Pass 2 board search.
2. Generate clickable LinkedIn search URLs for every query in `config.search.queries`.
3. Tell the user: "Chrome's not connected — paste any JD text from listings you find interesting and I'll score them."
4. As the user pastes JDs, score with the same rubric, surface as A/B/C just like a normal run, and write to the same daily report path.
5. Tracker append still happens for whatever was scored.

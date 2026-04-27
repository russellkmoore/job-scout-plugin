---
name: job-scout
description: >
  This skill should be used when the user asks to "search for jobs", "run the job scout",
  "find job matches", "check LinkedIn for opportunities", "daily job search", "find me jobs",
  "job matches", or anything related to automated job searching, job scoring, resume tailoring,
  or career assessment. Also triggers for "honest career assessment", "job market positioning",
  or "ATS optimization."
version: 0.3.0
---

# Job Scout

A wide, deliberate job search across **company career pages, multiple boards, and LinkedIn** — with honest scoring, connection-first targeting, and ATS-focused tailoring briefs. Designed to give the user a small set of *actionable* matches every morning, not a noisy listing dump.

## Core Philosophy

1. **Connections first.** A warm referral is worth more than 50 cold applications. Always check `master_targets.csv` for connection counts before scoring.
2. **Honest scoring.** Never inflate scores. If there are no A-tier matches, say so.
3. **No sycophancy.** The candidate needs to hear "this role is above your market position" when it's true.
4. **Specific tailoring.** "Move the $50M revenue bullet to position 1" — not "emphasize your leadership."
5. **Mechanical determinism.** All tracker writes go through `tracker_utils.py`. All schema lives in `scripts/schema.py`. All file paths come from `references/file-contract.md`. Nothing is duplicated across documents.
6. **Multi-source by design.** LinkedIn alone is noisy and recycled. The scout pulls from career pages, ATS boards (Greenhouse/Lever/Workday/Ashby), Built In Seattle, Wellfound, YC Work at a Startup, HN "Who is hiring" — and uses LinkedIn keyword search **last**, with the smallest budget, because its signal is the weakest.

## File contract — single source of truth

Every path the scout reads or writes is defined in `references/file-contract.md`. Do not describe paths anywhere else. If you need a new file, add it to the contract first, then reference the contract from the prompt that writes it.

The contract covers:
- The state pointer at `~/.job-scout/state.json` (written by `/scout-setup`, read by `/scout-run`).
- Persistent data files (`config.json`, `candidate_profile.json`, `master_targets.csv`, `JobScout_Tracker.xlsx`).
- Per-run output (`daily/<DATE>/JobScout_Report_<DATE>.md`, `new_rows.json`, `run_log.json`, `packets/`).

## Schema — single source of truth

All column names live in `scripts/schema.py`:

- `MASTER_TARGETS_COLUMNS` — the master_targets.csv schema. Currently includes `company_name`, `pipeline_tier`, `industry`, `location`, `career_page_url`, **`ats_provider`**, **`ats_board_url`**, `connection_names`, `linkedin_connection_count`, `warm_path`, `already_applied`, `application_status`, `roles_applied_for`, `fit_notes`, `fit_score`, `what_they_do`, `last_checked`, `data_source`. (`ats_provider` and `ats_board_url` are new in v0.3 — `validate_data.py` auto-migrates older files.)
- `TRACKER_COLUMNS` — the JobScout_Tracker.xlsx header row.
- `TRACKER_JSON_KEYS` — lowercase keys used in `new_rows.json`. One-to-one with `TRACKER_COLUMNS`.

Reference column names by importing from this module (in scripts) or by name (in prompts). Never hardcode column lists in two places.

## How `/scout-run` works (high level)

The full step-by-step is in `commands/scout-run.md`. The shape:

1. **Resolve `data_dir`** via `scripts/state.py resolve`. If missing → tell user to run `/scout-setup`.
2. **Validate** the data dir via `scripts/validate_data.py`. Auto-migrates schema, creates missing dirs, never destroys data.
3. **Load** config, profile, resume, master_targets, tracker dedup set.
4. **Compute pass budgets** from `config.search.max_listings_per_run`:
   - **Pass 1 — Company-first deep-dive** (~60% of budget). For each of `companies_per_day` selected companies: career page → ATS board (if known) → LinkedIn company jobs tab. Highest signal.
   - **Pass 2 — Other job boards** (~25%). Built In Seattle, Wellfound, YC Work at a Startup, HN Who is Hiring. See `references/job-boards.md` for per-board specs.
   - **Pass 3 — LinkedIn keyword search** (~15%, last). Runs `config.search.queries` and `config.search.underutilized_asset_queries` exactly. Stops early on noise.
5. **Score** with the 5-category weighted rubric. Tier thresholds come from `config.scoring`. Hard cap 10 A-tier per run.
6. **Write the daily report** with actionable A-tier blocks (apply URL, warm path, ATS keyword diff, outreach draft, recommended resume version, honest read).
7. **Append to tracker** via `tracker_utils.py append` with `new_rows.json` as input — never write the xlsx directly.
8. **Update master_targets.csv** with `last_checked` for visited companies and any newly discovered ones.

## Chrome browsing (LinkedIn JD lazy-load)

`/scout-run` uses Claude in Chrome. The lazy-load extraction sequence for any LinkedIn job description is non-negotiable:

1. Navigate to the listing URL.
2. `javascript_tool` → `window.scrollTo(0, 800)`.
3. Wait 3–5 seconds for async render.
4. `find` the "...more" button, click to expand.
5. THEN `get_page_text`.

Skipping any step → only metadata, no JD body. Career pages and ATS boards generally do not need this dance — they return full JDs on first load.

`references/chrome-setup.md` covers extension install, login flow, and troubleshooting.

## Scoring system (authority: `references/search-config.md` + `references/scoring-rubric.md`)

5-category weighted rubric. **Weights and thresholds come from `config.json` at runtime.** The values below are the template defaults — every active config can override them.

| Category | Default weight | What to evaluate |
|---|---|---|
| Connection Leverage | 30 | Named connections at the company. Referral-likely → 30. None → 0. |
| Experience Match | 25 | Does the JD describe what's in the candidate's `strongest` skills? Penalize if the role hangs on `aspirational`. |
| Domain Fit | 20 | Industry/sector overlap with `industries_preferred`. |
| Compensation | 15 | Stated comp range vs `salary_minimum`. |
| Realistic Shot | 10 | Credential bias, applicant pool size, repost count, freshness. |

Bonus / penalty adjustments: full list in `references/scoring-rubric.md`. Examples: +10 warm intro available, +5 founder-valuing role, −15 PhD/elite-MBA-required, −10 IC role.

Tier thresholds (defaults — config-overridable): A ≥ 75, B ≥ 55, C ≥ 40, skip < 40. Hard cap: 10 A-tier per run.

## Stale listing detection

LinkedIn job ID `< 4_200_000_000` → flag as likely 6+ months recycled. The threshold is in `scripts/schema.py` as `STALE_LINKEDIN_JOB_ID_THRESHOLD`. `tracker_utils.py append` flags these automatically and colors them gray.

Other stale signals: "Posted X weeks ago", "Over 200 applicants", company already in `master_targets.csv` with `application_status = "Dead"`.

## Tailoring briefs (A-tier only)

Read `references/tailoring-guide.md`. Key outputs:

1. **ATS keywords to add** — terms from the JD the candidate legitimately possesses but the resume doesn't surface. Never fabricate.
2. **Section reorder** — which section to lead with, given role type.
3. **Bullet promotion** — specific bullets by name, not generic advice.
4. **Wording alignment** — where to mirror JD phrasing.

By default these go inline in the daily report (the "ATS keyword diff" block). Full tailored resume + outreach drafts are generated **on demand** when the user replies with `pack <id> ...` after reviewing the report. See `commands/scout-run.md` "On-demand: generate A-tier packet" for the file layout.

## Honest notes (mandatory)

Every daily report MUST include an "Honest notes" section with at least one observation. Examples:
- Same companies, no new roles → flag pattern.
- Salary target eliminating most results → flag.
- A-tier matches only at zero-connection companies → flag the networking gap.
- 3+ rejections in same sector → suggest pivoting.
- LinkedIn rendering blocked JD reads → list which listings need manual review.

## Reference documents

- **`references/file-contract.md`** — Every file path the scout uses. **Always read this first.**
- **`references/search-config.md`** — Per-pass search strategy, budget formula, query handling.
- **`references/scoring-rubric.md`** — Detailed point breakdowns with examples.
- **`references/job-boards.md`** — Pass 2 board specs (Built In Seattle, Wellfound, YC Work at a Startup, HN Who is Hiring).
- **`references/tailoring-guide.md`** — How to generate ATS-focused tailoring briefs.
- **`references/assessment-framework.md`** — How to generate the honest career assessment.
- **`references/profile-extraction-guide.md`** — How to read resumes and LinkedIn data.
- **`references/chrome-setup.md`** — Claude in Chrome installation and troubleshooting.

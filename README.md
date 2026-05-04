# Job Scout

A wide, deliberate daily job search across **company career pages, ATS boards, multiple specialized job boards, and LinkedIn** — with honest scoring, connection-first targeting, and ATS-focused tailoring briefs. Designed to give you a small set of *actionable* matches every morning, not a noisy listing dump.

## What it does

Job Scout uses Claude in Chrome to:

1. **Pass 1 — ATS-first sourcing** (60% of effort). For each of your top target companies, queries structured ATS APIs directly — Greenhouse, Lever, Ashby, SmartRecruiters, Workday — plus a JSON-LD fallback for companies with no detected ATS. Then runs a LinkedIn keyword search scoped to each company name. Marketing-page Chrome scraping was removed in v0.4.
2. **Pass 2 — Specialized job boards** (25%). Wellfound, Built In Seattle, YC Work at a Startup, and the current Hacker News "Who is hiring" thread.
3. **Pass 3 — LinkedIn keyword search** (15%, last). Runs your configured queries — but with the smallest budget, because LinkedIn's keyword search is the noisiest source.

Then it scores every candidate listing against your actual resume and connections (no inflation), produces a daily report with **actionable** A-tier blocks (direct apply URL, named warm-intro contact, ATS keyword diff, pre-drafted outreach), and appends to a deduplicated tracker spreadsheet. Full tailored resume packets are generated **on demand** when you reply with `pack <id> ...`.

## What's new in v0.4

- **ATS-first sourcing.** Queries Greenhouse, Lever, Ashby, SmartRecruiters, and Workday APIs directly — no Chrome navigation of marketing pages.
- **JSON-LD fallback.** Companies with no detected ATS provider get a structured JSON-LD fetch on their `career_page_url` (no Chrome).
- **`/scout-detect` skill.** Batch + lazy-inline detection of each company's ATS provider. Populates `ats_provider`, `ats_board_url`, and `ats_slug_confidence` in `master_targets.csv` with a two-factor name-match gate.
- **Cross-source dedup.** ATS and LinkedIn listings are deduplicated with two-key fuzzy matching (`rapidfuzz`). Decisions are logged to `runs.jsonl` for transparency; borderline matches surface in the report's *Honest notes*.
- **Enrich-then-tier.** ATS A/B-tier candidates get LinkedIn shared-connection lookup BEFORE final tier assignment (restores warm-path signal lost by pure ATS results).
- **Structured observability.** `runs.jsonl` records per-provider outcomes, field completion, dedup decisions, A/B-tier counts per source, regression suspects, and Pass-2 board-broken warnings.
- **Milestone bar.** `python3 scripts/ats/runs_log.py milestone-bar <data_dir>/runs.jsonl --lookback 5` prints a JSON dict with `pass1_share_pct` (target ≥ 60%) and `wall_clock_avg_seconds` (target ≤ 300s, ATS-fetch only — not total `/scout-run` wall-clock).

## Requirements

- **Claude in Chrome extension** installed and connected (any current Chrome channel — Stable / Beta / Dev / Nightly all work)
- **LinkedIn account** — logged in via Chrome
- **Resume** — PDF or DOCX
- **LinkedIn data export** (recommended) — request from `linkedin.com/mypreferences/d/download-my-data`
- Python 3.8+ with `pandas`, `openpyxl`, `httpx>=0.27,<0.29`, and `rapidfuzz` (use `pipx install` or `python3 -m venv`; the scripts print install hints on first run)
- Optional logins for Pass 2: **Wellfound**, **YC Work at a Startup** (full JDs require login on those two)

## Getting started

### 1. Run setup

```
/scout-setup
```

This walks you through:
- Your resume + LinkedIn data export
- A short questionnaire (salary, location, deal-breakers, recent interviews/rejections)
- An honest career assessment based on your profile and target market
- Building the company target list and scoring config

Setup writes `~/.job-scout/state.json` so daily runs find your data deterministically. Takes 10–15 minutes. Chrome isn't required for setup.

### 2. Run your first search

```
/scout-run
```

This brings up Chrome, runs Pass 1 → Pass 2 → Pass 3 with explicit budgets, scores listings, and produces a daily report + tracker update. Takes 15–30 minutes.

### 3. (Optional) schedule daily runs

After your first manual run confirms everything works, schedule a task that calls `/scout-run` on whatever cadence you want. **The scheduled task body should be exactly one line — `/scout-run` — with no overrides.** Configuration changes belong in `<data_dir>/config.json`, not in the scheduled task.

## Components

| Component | Description |
|---|---|
| `/scout-setup` | First-run configuration — profile extraction, honest assessment, search config, state pointer |
| `/scout-run` | Execute a multi-pass job search and produce a daily report |
| `job-scout` skill | Core knowledge — scoring rubric, search strategy, tailoring briefs |
| `scripts/schema.py` | Single source of truth for column names (master_targets, tracker) |
| `scripts/state.py` | Read/write the `~/.job-scout/state.json` pointer |
| `scripts/validate_data.py` | Validate + auto-migrate the data directory on every run |
| `scripts/tracker_utils.py` | Deterministic tracker append/dedup/format |
| `scripts/mine_connections.py` | Extract and count LinkedIn connections by company |
| `scripts/consolidate_targets.py` | Merge multiple data sources into `master_targets.csv` |

## File outputs

The complete file contract is in `skills/job-scout/references/file-contract.md`. The shape:

```
~/.job-scout/state.json                   # Setup pointer (data_dir, version)

<data_dir>/                                # Default: ~/Documents/JobSearch
├── config.json                            # Your search configuration (weights, queries, budgets)
├── candidate_profile.json                 # Extracted profile (strongest / credible / aspirational)
├── master_targets.csv                     # Company DB — schema in scripts/schema.py
├── JobScout_Tracker.xlsx                  # Tracker — written ONLY by tracker_utils.py
├── assessment/
│   └── Honest_Career_Assessment.md
├── Resumes/                               # Your resume bank (you curate)
└── daily/
    └── YYYY-MM-DD/
        ├── JobScout_Report_YYYY-MM-DD.md  # Daily report with actionable A-tier blocks
        ├── new_rows.json                  # Input to tracker append
        ├── run_log.json                   # Per-pass stats
        └── packets/
            └── <Company>_<Role>/          # Generated on-demand: tailored resume + outreach
                ├── jd.md
                ├── tailored_resume.docx
                ├── ats_diff.md
                └── outreach_draft.md
```

## Scoring philosophy

Connection-first weighted rubric. **All weights are config-overridable in `config.json`.**

| Category | Default weight | Why |
|---|---|---|
| Connection Leverage | 30 | A warm referral is worth more than 50 cold applications. |
| Experience Match | 25 | Does the JD describe what you've actually done? Penalize aspirational matches. |
| Domain Fit | 20 | Industry sweet spot vs your `industries_preferred`. |
| Compensation | 15 | Stated comp range vs your `salary_minimum`. |
| Realistic Shot | 10 | Honest gut check on credential bias and applicant volume. |

Default tier thresholds: A ≥ 75, B ≥ 55, C ≥ 40, skip < 40. Hard cap: 10 A-tier per run.

The default assessment style is **honest**. The plugin will tell you when you're reaching for roles above your market position, when your resume has gaps, and when the report is thin and there's nothing worth applying to today. You can switch to "balanced" or "encouraging" in `config.json`, but honest is recommended.

## Customization

Edit `config.json` to adjust:
- Search queries (`search.queries` and `search.underutilized_asset_queries`)
- Pass budgets (`search.pass_budgets`) and which Pass 2 boards to include (`search.pass2_boards`)
- Scoring weights and tier thresholds
- Target salary, location, work arrangement, deal-breakers
- `companies_per_day` and `max_listings_per_run`
- `assessment_style`

Anything that goes in `config.json` should never be repeated in scheduled-task instructions or chat overrides — `config.json` is the source of truth.

## Versioning

- **0.4.1** — Bugfix: `preview.py` now sanitizes `company_slug` for filesystem use, restoring Workday outcomes (Apple, Microsoft, Salesforce, T-Mobile, Target, Slalom, Square, Accenture, Chewy, Aritzia, CSC Generation) that were silently dropped on raw-payload write.
- **0.4.0** — ATS-first sourcing across Greenhouse, Lever, Ashby, SmartRecruiters, Workday + JSON-LD fallback. New `/scout-detect` skill. Cross-source dedup. Enrich-then-tier. Marketing-page Chrome scraping removed. Milestone bar verifiable from `runs.jsonl`.
- **0.3.0** — Multi-pass search (career pages → boards → LinkedIn last). State pointer at `~/.job-scout/state.json`. Single-source schema in `scripts/schema.py`. File contract in `references/file-contract.md`. Auto-migrating data validator. New `ats_provider` / `ats_board_url` columns. Hybrid on-demand A-tier packets.
- **0.2.x** — LinkedIn-only browsing with company-first prioritization. Hard-coded fallback config paths. Inline column lists.

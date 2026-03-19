# Job Scout

Automated LinkedIn job search with honest scoring, connection-first targeting, and ATS-focused tailoring briefs.

## What It Does

Job Scout uses Claude in Chrome to browse LinkedIn, find job matches based on your actual resume and connections, score them honestly, and produce daily reports with specific resume tailoring briefs. It prioritizes companies where you have connections (the #1 predictor of getting an interview) and tells you the truth about your positioning instead of generating 100 listings to be nice.

## Requirements

- **Claude in Chrome extension** installed and connected
- **LinkedIn account** — logged in via Chrome
- **Resume** — PDF or DOCX
- **LinkedIn data export** (recommended) — download from linkedin.com/mypreferences/d/download-my-data
- Python 3.8+ with pandas and openpyxl (`pip install pandas openpyxl`)

## Getting Started

### 1. Run Setup

```
/scout-setup
```

This walks you through:
- Providing your resume and LinkedIn data export
- Answering a short questionnaire about your job search
- Getting an honest career assessment based on your profile
- Generating your search configuration and target company list

Setup takes about 10-15 minutes. You don't need Claude in Chrome for setup — only for daily runs.

### 2. Run Your First Search

```
/scout-run
```

This opens LinkedIn in Chrome, runs your configured searches, scores results, and produces a report + tracker update. Takes 15-30 minutes depending on how many listings are found.

### 3. Schedule Daily Runs (Optional)

After your first manual run confirms everything works, you can schedule the scout to run automatically. Ask Claude to set up a scheduled task with your preferred frequency.

## Components

| Component | Description |
|-----------|-------------|
| `/scout-setup` | First-run configuration — profile extraction, honest assessment, search config |
| `/scout-run` | Execute a job search run — browse LinkedIn, score, report |
| `job-scout` skill | Core logic — scoring rubric, search strategy, tailoring briefs |
| `scripts/tracker_utils.py` | Deterministic tracker management — deduplication, formatting |
| `scripts/mine_connections.py` | Extract and count LinkedIn connections by company |
| `scripts/consolidate_targets.py` | Merge multiple data sources into master_targets.csv |

## File Outputs

All outputs go to your configured data directory (default: `~/Documents/JobSearch/`):

```
~/Documents/JobSearch/
├── config.json                  # Your search configuration
├── candidate_profile.json       # Extracted profile data
├── master_targets.csv           # Company database with connection counts
├── JobScout_Tracker.xlsx        # Running job tracker
├── assessment/
│   └── Honest_Career_Assessment.md
└── daily/
    └── YYYY-MM-DD/
        └── JobScout_Report_YYYY-MM-DD.md
```

## Scoring Philosophy

Job Scout uses a connection-first scoring rubric:

| Category | Weight | Why |
|----------|--------|-----|
| Connection Leverage | 30% | Having someone who can refer you is the single biggest factor in getting an interview |
| Experience Match | 25% | Does the JD describe what you've actually done? |
| Domain Fit | 20% | Is this in your industry/vertical? |
| Compensation | 15% | Does it meet your salary requirements? |
| Realistic Shot | 10% | Honest gut check — would they actually call you? |

The default assessment style is **honest**. The plugin will tell you when you're reaching for roles above your market position, when your resume has gaps, and when you should focus your energy differently. You can adjust this to "balanced" or "encouraging" in config.json, but honest is recommended.

## Customization

Edit `config.json` to adjust:
- Search queries and filters
- Scoring weights and tier thresholds
- Target salary and location preferences
- Assessment style (honest / balanced / encouraging)
- Number of companies to check per run

# External Integrations

**Analysis Date:** 2026-04-27

## Overview

Job Scout has **no first-party API integrations** — no SDK calls, no API keys, no OAuth tokens, no service accounts. Every external interaction is **browser-mediated** through the Claude in Chrome extension, driving a real Chrome session against public web pages while the user remains logged in. Data sources fall into four categories:

1. **Browser-driven scraping** of LinkedIn, company career pages, ATS provider boards, and four specialized job boards (orchestrated via MCP).
2. **User-supplied file inputs** — resume (PDF/DOCX), LinkedIn data export ZIP, optional historical job-tracking CSV/XLSX files.
3. **Local filesystem persistence** for all output (no cloud sync).
4. **Claude Code MCP servers** — only one is required at runtime: `mcp__Claude_in_Chrome__*`.

There are **no environment variables**, no `.env` files, no secret stores, and no inline credentials anywhere in the repository.

## MCP Server Integrations

**Claude in Chrome (required for `/scout-run`):**
- Tool wildcard: `mcp__Claude_in_Chrome__*` declared in `skills/scout-run/SKILL.md:4` (`allowed-tools`).
- Specific tools referenced in skill prompts:
  - `mcp__Claude_in_Chrome__tabs_context_mcp` — Connection probe and Chrome health check (`skills/scout-run/SKILL.md:63`, `skills/job-scout/references/chrome-setup.md:32`).
  - `javascript_tool` — Used to scroll LinkedIn pages (`window.scrollTo(0, 800)`) so lazy-loaded JD bodies render (`skills/job-scout/references/chrome-setup.md:42`).
  - `find` — Locates the "...more" button to expand collapsed LinkedIn JDs (`skills/job-scout/references/chrome-setup.md:43`).
  - `get_page_text` — Captures the rendered DOM text for downstream scoring (`skills/job-scout/references/chrome-setup.md:44`).
- Auth model: OAuth via the Chrome extension (`skills/job-scout/references/chrome-setup.md:22-26`). Credentials live in Chrome and never touch the plugin.
- Fallback: If Chrome is unavailable, `/scout-run` enters Fallback Mode (`skills/scout-run/SKILL.md:272`) — emits clickable URLs and asks the user to paste JD text manually.

**No other MCP servers are required.** The setup skill (`skills/scout-setup/SKILL.md:4`) does not declare any MCP tools.

## Job Sources (browser-driven, no APIs)

### LinkedIn (linkedin.com)
- **Used in:** Pass 1 (company-jobs tab) and Pass 3 (keyword search). Detailed in `skills/scout-run/SKILL.md:71-100` and `skills/scout-run/SKILL.md:126-138`.
- **Auth:** User must be logged in to Chrome; the scout never enters credentials (`skills/job-scout/references/chrome-setup.md:57`).
- **URL patterns:**
  - Feed sanity check: `https://www.linkedin.com/feed/`
  - Company-scoped jobs search: `https://www.linkedin.com/jobs/search/?keywords=<COMPANY>%20director%20OR%20%22VP%22%20OR%20%22sr%20director%22%20engineering&f_TPR=r604800&location=<LOCATION>` (`skills/scout-run/SKILL.md:85`).
  - Time-window filters: `f_TPR=r604800` (past week), `f_TPR=r86400` (past 24h).
  - Remote work-type filter: `f_WT=2`.
  - Listing detail URL: `linkedin.com/jobs/view/<id>`.
- **Known constraints:**
  - The `f_C=` company-ID filter is unreliable and is explicitly forbidden (`skills/scout-run/SKILL.md:83`).
  - JD bodies require the lazy-load extraction sequence (scroll → wait 3-5s → click "...more" → `get_page_text`) defined at `skills/job-scout/references/chrome-setup.md:36-46` and `skills/job-scout/SKILL.md:60-72`.
  - LinkedIn job IDs `< 4_200_000_000` flagged as likely-stale recycled listings (`scripts/schema.py:96`, `scripts/tracker_utils.py:73`).
  - Bot-detection mitigation rules in `skills/job-scout/references/chrome-setup.md:93-102` (don't run more than once/day, limit query count, pause between page loads).

### Wellfound (wellfound.com — formerly AngelList Talent)
- **Used in:** Pass 2 (~28% of Pass 2 budget per `skills/job-scout/references/job-boards.md:147`).
- **Auth:** Optional login required for full JDs (`README.md:22`, `skills/job-scout/references/job-boards.md:31`).
- **URL pattern:** `https://wellfound.com/jobs?role=engineering-manager&role=vp-engineering&role=cto&remote=true` (`skills/job-scout/references/job-boards.md:14-16`).
- **Extracted fields:** Company, stage (Seed/Series A/etc.), comp range, equity range, founder names (cross-checked against `connection_names`).

### Built In Seattle (builtin.com/jobs/seattle)
- **Used in:** Pass 2 (~33% of Pass 2 budget). No login required.
- **URL pattern:** `https://builtin.com/jobs/seattle/dev-engineering?experience=expert&job=executive` (`skills/job-scout/references/job-boards.md:44-46`).
- **Notable:** WA comp-transparency law — comp ranges are reliable. Apply button often redirects to a downstream ATS; capture the final URL for the tracker (`skills/job-scout/references/job-boards.md:60`).

### Y Combinator — Work at a Startup (workatastartup.com)
- **Used in:** Pass 2 (~20% of Pass 2 budget).
- **Auth:** Optional YC login required for full JDs (`skills/job-scout/references/job-boards.md:121`, `README.md:22`).
- **URL pattern:** `https://www.workatastartup.com/jobs?role_types=eng_manager&role_types=eng_director&remote=yes` (`skills/job-scout/references/job-boards.md:107-109`).
- **Extracted fields:** YC batch (W24, S23, etc.), comp + equity range, founder bios.

### Hacker News "Who Is Hiring" (news.ycombinator.com + hn.algolia.com)
- **Used in:** Pass 2 (~20% of Pass 2 budget). No auth.
- **Discovery URL (Algolia search):** `https://hn.algolia.com/?dateRange=pastMonth&query=Ask+HN%3A+Who+is+hiring%3F&sort=byDate&type=story` (`skills/job-scout/references/job-boards.md:73`).
- **Thread URL:** `https://news.ycombinator.com/item?id=<thread_id>` (`skills/job-scout/references/job-boards.md:77`).
- **Parsing:** First-line heuristic `Company | Role | Location | Type | Comp` per top-level comment, with keyword-fallback (`skills/job-scout/references/job-boards.md:80-92`).
- **Skip rule:** If the most recent thread is more than 5 weeks old, the new month's thread hasn't dropped yet (`skills/scout-run/SKILL.md:115`).

### Company career pages (Pass 1)
- **Used in:** Pass 1, ~60% of the run budget. Read directly from each company's `career_page_url` (column in `master_targets.csv` per `scripts/schema.py:25`).
- **No auth.** Career pages return full JDs on first navigation — no lazy-load dance needed (`skills/job-scout/references/chrome-setup.md:48`).

### ATS provider boards (Pass 1, structured fallback after career page)
The scout auto-detects the ATS provider from the career-page URL and stores it in `master_targets.csv` columns `ats_provider` and `ats_board_url` (`scripts/schema.py:26-27`). Detection patterns from `skills/scout-run/SKILL.md:82`:

| Provider | Detection pattern | Stored value |
|---|---|---|
| Greenhouse | `boards.greenhouse.io/<company>` | `greenhouse` |
| Lever | `jobs.lever.co/<company>` | `lever` |
| Workday | `*.myworkdayjobs.com/...` | `workday` |
| Ashby | `<company>.ashbyhq.com` | `ashby` |
| SmartRecruiters | (declared in schema comment) | `smartrecruiters` |
| Other / unknown | n/a | `other` / `unknown` |

No ATS provider APIs are called — the boards are scraped through Chrome like any other page.

## Data Sources (User-Supplied Files)

**Resume (required):**
- Format: PDF or DOCX. Path captured at `config.candidate.resume_path` (`templates/config.json:13`).
- Read by Claude during `/scout-setup` profile extraction (`skills/job-scout/references/profile-extraction-guide.md:6-15`).

**LinkedIn data export (optional but recommended):**
- Source: User requests at `https://linkedin.com/mypreferences/d/download-my-data` (~24h delivery — `skills/scout-setup/SKILL.md:25`).
- Format: ZIP containing CSVs.
- Files consumed:
  - `Connections.csv` → `scripts/mine_connections.py` (groups by `Company`/`First Name`/`Last Name`/`Position`; auto-detects header offset and encoding `utf-8`/`latin-1`/`cp1252` per `scripts/mine_connections.py:33`).
  - `Profile.csv`, `Positions.csv`, `Skills.csv`, `Education.csv`, `Certifications.csv` (referenced in `skills/job-scout/references/profile-extraction-guide.md:21-26`).
- Path captured at `config.candidate.linkedin_export_path` (`templates/config.json:14`).

**Existing tracking spreadsheets (optional):**
- Format: CSV or XLSX. Read via `scripts/consolidate_targets.py` which auto-detects the company column from aliases `company_name`/`company`/`organization`/`employer`/`name` (`scripts/consolidate_targets.py:71`) and normalizes against `MASTER_TARGETS_COLUMNS`.

## Authentication & Identity

**No service-side auth.** The plugin holds no credentials, tokens, or secrets.

| Surface | Auth model |
|---|---|
| Claude Code | Handled by host runtime; not the plugin's concern. |
| Claude in Chrome MCP | OAuth via the Chrome extension; user authorizes once (`skills/job-scout/references/chrome-setup.md:21-26`). |
| LinkedIn | User-managed Chrome session; **scout never enters credentials** (explicit guarantee at `skills/job-scout/references/chrome-setup.md:57` and `skills/scout-run/SKILL.md:67`). |
| Wellfound, YC Work at a Startup | Optional user logins in Chrome. Without them, JD bodies are truncated; the scout surfaces a request for the user to log in (`skills/job-scout/references/job-boards.md:31`, `121`). |
| Built In Seattle, HN | No login required. |

## Data Storage

**Storage location:** Local filesystem only. No cloud / database / object-storage integrations.

| Artifact | Location | Created by |
|---|---|---|
| State pointer | `~/.job-scout/state.json` | `scripts/state.py write` |
| User data dir (default) | `~/Documents/JobSearch/` | `/scout-setup` |
| Legacy fallback dirs | `~/Documents/JobSearch/scout`, `~/Documents/JobSearch`, `~/Documents/JobScout` | Resolved by `scripts/state.py:32` (`LEGACY_DATA_DIRS`) |
| Daily artifacts | `<data_dir>/daily/<DATE>/` | `/scout-run` |
| Tracker XLSX | `<data_dir>/JobScout_Tracker.xlsx` | `scripts/tracker_utils.py` (sole writer) |
| Resume bank | `<data_dir>/Resumes/` | User-curated |

The full path contract lives in `skills/job-scout/references/file-contract.md` and is the single source of truth.

## Caching

None. Each `/scout-run` re-fetches everything from source. The `JobScout_Tracker.xlsx` is the long-term memory — its job-ID set is loaded at the top of every run via `python3 scripts/tracker_utils.py dedup-set <tracker.xlsx>` (`skills/scout-run/SKILL.md:43`) so previously-seen listings are excluded before re-scoring.

## Monitoring & Observability

**Error tracking:** None.

**Logs:**
- Per-run JSON log written to `<data_dir>/daily/<DATE>/run_log.json` (`skills/scout-run/SKILL.md:50`, `230`).
- Captures the JSON output of `tracker_utils.py append` (`{added, skipped_duplicate, flagged_stale, total_rows}` — `scripts/tracker_utils.py:226-231`).
- The validator (`scripts/validate_data.py:141`) prints a JSON status object to stdout per run; exit code 0/1 signals overall health.

## CI/CD & Deployment

- **No CI configured.** No `.github/`, no `.gitlab-ci.yml`, no `Jenkinsfile`, no GitHub Actions workflows in the repo.
- **No CD / publishing pipeline.** Distribution is via direct git checkout / Claude Code plugin install — there is no marketplace publish step in the repo.
- **No deploy targets.** This is a client-side plugin; nothing runs server-side.

## Environment Configuration

**Required environment variables:**
- `${CLAUDE_PLUGIN_ROOT}` — Provided automatically by the Claude Code plugin runtime. Used throughout skills to reference scripts and templates (e.g. `skills/scout-run/SKILL.md:25`, `skills/scout-setup/SKILL.md:62-74`). Not set by the plugin itself.

**No `.env` files** present in the repo. No `os.environ` / `os.getenv` calls in any of the Python scripts.

**Secrets location:** None — there are no secrets to store.

## Webhooks & Callbacks

**Incoming:** None. The plugin has no listening surface.

**Outgoing:** None. All "outgoing" traffic is Chrome-mediated browsing of public job-listing pages. No HTTP clients (`requests`, `httpx`, `urllib`) are imported by any script — verified via `grep` of `scripts/*.py`.

## On-Demand Generation Integrations

The `pack <id>` flow (`skills/scout-run/SKILL.md:258-268`) generates a tailored resume packet per A-tier match. Integration touchpoints:

- **`docx` skill (optional, external):** Used to write `tailored_resume.docx` if available in the host Claude Code installation. Falls back to instructions for the user if not present (`skills/scout-run/SKILL.md:264`).
- No external API calls — generation is purely Claude reasoning over the loaded resume + JD text.

## Outbound Domains (Allowlist Summary)

For users behind corporate proxies, the runtime touches these domains (via Chrome only):

- `linkedin.com` — Pass 1 (company-jobs tab) + Pass 3 (keyword search)
- `wellfound.com` — Pass 2
- `builtin.com` — Pass 2
- `workatastartup.com` — Pass 2
- `news.ycombinator.com` + `hn.algolia.com` — Pass 2
- `boards.greenhouse.io`, `jobs.lever.co`, `*.myworkdayjobs.com`, `*.ashbyhq.com` — Pass 1 (ATS providers)
- Any company-owned `career_page_url` listed in the user's `master_targets.csv`
- `chrome.google.com/webstore` — One-time install of the Claude in Chrome extension

---

*Integration audit: 2026-04-27*

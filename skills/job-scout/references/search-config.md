# Search Configuration

The scout runs a wide, deliberate search every day. **Three passes, fixed budgets, sources ordered from highest to lowest signal.** This file describes the strategy. The actual queries, weights, and thresholds live in `<data_dir>/config.json` — never inline anywhere else.

---

## Reality check

This search system is brutally honest about fit — no wishful thinking. Prioritize roles where:
- The candidate has named LinkedIn connections at the company (warm path = the #1 predictor of getting an interview).
- The role matches their **`strongest`** skills from `candidate_profile.json`, not aspirational positioning.
- The JD doesn't require credentials they don't have.

If a run produces no A-tier matches, the report says so. The scout does not promote B-tier to make a thin run feel productive.

---

## Three-pass search strategy

`/scout-run` allocates `config.search.max_listings_per_run` (default 50) across three passes:

| Pass | Source | Budget | Why |
|---|---|---|---|
| 1 | Company career page → ATS board → LinkedIn company jobs | **~60%** | Highest signal. Career pages list roles before LinkedIn. ATS boards (Greenhouse/Lever/Workday/Ashby) have structured data and full JDs. |
| 2 | Built In Seattle, Wellfound, YC Work at a Startup, HN "Who is hiring" | **~25%** | Curated boards with niches LinkedIn buries (founder/startup, local, technical leadership). |
| 3 | LinkedIn keyword search | **~15%, last** | Lowest signal. Recycled listings, AI-driven irrelevance. Useful as a sweep, not a primary source. |

**Budget formula** (in `commands/scout-run.md`):
- Pass 1 = `round(0.60 * max_listings_per_run)`
- Pass 2 = `round(0.25 * max_listings_per_run)`
- Pass 3 = `max_listings_per_run − (Pass 1 + Pass 2)`

If a pass finishes under-budget, **do not roll over** to later passes. Under-budget means there genuinely wasn't enough qualifying activity at that source — adding more LinkedIn keyword noise won't fix it.

---

## Pass 1 — Company-first deep-dive

**The most valuable pass. Spend the most time here.**

1. Read `<data_dir>/master_targets.csv`.
2. Sort: `linkedin_connection_count` desc, then `last_checked` ascending (oldest first), then exclude `application_status = "Dead"`.
3. Take the top `config.search.companies_per_day` rows (default 8 in older configs, default 5 in template).
4. For each company:
   - **Career page** (`career_page_url`). Direct, full JDs.
   - **ATS board** (`ats_board_url`, if populated). If empty, detect from `career_page_url` redirect target — `boards.greenhouse.io/X`, `jobs.lever.co/X`, `myworkdayjobs.com/...`, `<company>.ashbyhq.com` — and populate `ats_provider` + `ats_board_url` for next time.
   - **LinkedIn company jobs tab** (`linkedin.com/company/<slug>/jobs/`). Last resort within Pass 1.
5. Update `last_checked = <TODAY>` for every company visited.

**Priority order within Pass 1** (when more candidates than budget):
1. Companies with 3+ named connections (warm path likely).
2. Companies on the user's pipeline list (`pipeline_tier <= 2`).
3. Companies in `industries_preferred` from config.
4. Companies with detected ATS providers (richer data).

---

## Pass 2 — Other job boards

See `references/job-boards.md` for the URL patterns, filter recipes, parsing gotchas, and per-board signal notes for each of:

- **Built In Seattle** — local, comp-transparent, executive filter.
- **Wellfound** — founder/startup, equity-included.
- **YC Work at a Startup** — YC portfolio, requires login for full JDs.
- **HN "Who is Hiring"** — first-of-month thread; raw text, careful parsing.

Within Pass 2, the rough sub-budget is:
- Built In Seattle ~33%
- Wellfound ~28%
- YC Work at a Startup ~20%
- HN Who is Hiring ~20%

Skip a board if its prescribed filter setup yields nothing matching the candidate's level/comp constraints — don't pad.

**Cross-board dedup**: normalize company name + role title; prefer the listing with the most direct apply URL (company ATS > Built In > Wellfound > LinkedIn).

---

## Pass 3 — LinkedIn keyword search

**Last. Smallest budget. Stop early on noise.**

For each query in `config.search.queries` (primary first), then `config.search.underutilized_asset_queries`:

1. Navigate to LinkedIn Jobs search with the query.
2. Filters: **Date Posted = Past 24 hours** (daily) or **Past week** (first run after a gap). **Experience Level = Director or Executive**.
3. Read page 1 of results. Extract title, company, location, comp range, job URL.
4. Stale check + dedup check.
5. For non-stale, non-duplicate listings, click in and run the lazy-load JD extraction sequence (see `chrome-setup.md`).
6. **Stop the query early** if page 1 is dominated by listings already in the tracker, or by jobs in obviously wrong domains. LinkedIn relevance is poor — don't punch through three pages of noise hunting for one match.

Boolean operators work better than space-separated terms. Quoted phrases are essential for compound titles. Note: the `f_C` company filter URL parameter is silently ignored when keywords contain `OR` — don't rely on it.

---

## Stale listing detection

LinkedIn job ID `< 4_200_000_000` → flag as likely 6+ months recycled.

Other stale signals:
- "Posted X weeks ago" (more than ~3 weeks) → consider stale.
- "Over 200 applicants" + posted weeks ago → window has passed.
- Listing has been reposted multiple times → flag as potentially-unrealistic expectations.
- Company already in `master_targets.csv` with `application_status` containing `"Dead"`.

`tracker_utils.py append` flags stale listings automatically (gray fill, `Status = "Stale — Verify"`). They go in the report's "Stale / skipped" section, not in the A/B/C tiers.

---

## Scoring rubric

Defaults below. **Actual weights at runtime come from `config.scoring`.** Override in `config.json`, never in scheduled-task instructions or chat overrides.

| Category | Default weight | What to evaluate |
|---|---|---|
| **Connection Leverage** | 30 | Named LinkedIn connections at the company. 1–2 = 15. 3–5 = 20. 6+ = 25. Someone senior enough to refer = 30. None = 0. |
| **Experience Match** | 25 | Does the JD describe things in the candidate's `strongest` skills? Penalize heavily if the role hangs on `aspirational`. Deduct for credential gaps. |
| **Domain Fit** | 20 | Industry sweet spot vs `industries_preferred` from config. |
| **Compensation** | 15 | Stated comp range vs `salary_minimum`. Full points if clearly above, partial if range includes it, zero if below. |
| **Realistic Shot** | 10 | Would the company actually interview this person? Credential bias, applicant volume, repost count. |

### Bonus points
- +10 warm introduction possible (named connection who could refer).
- +5 role values founder/startup/entrepreneurial experience.
- +5 role mentions military veteran preference (if applicable).
- +5 company on the candidate's target pipeline list.
- +3 role involves building a team from scratch.

### Penalty points
- −15 requires PhD, elite MBA, or deep ML research (unless candidate has these).
- −10 clearly IC role with no leadership.
- −10 JD targets FAANG / Big 3 consulting backgrounds specifically.
- −5 reposted multiple times.

### Tier thresholds (defaults — config-overridable)
- **A-tier (≥ `tier_a_threshold`, default 75):** Prioritize. Generate inline ATS keyword diff + outreach draft. Eligible for on-demand packet.
- **B-tier (≥ `tier_b_threshold`, default 55):** Include in report with the "Why B and not A" line.
- **C-tier (≥ 40):** Table only, no detail.
- **Skip (< 40):** Don't include.

**Hard cap: 10 A-tier per run.** If more qualify, raise the effective A threshold for this run only (do NOT edit `config.json`) and demote excess to B-tier with note "would-be-A, raised threshold this run."

---

## Resume tailoring (A-tier only)

See `references/tailoring-guide.md`. Key principle: every tailoring instruction names a specific bullet, section, or phrase. "Emphasize your leadership" is never acceptable. "Move the $X revenue bullet to position 1 under the [Company] section" is.

By default, the daily report includes the **ATS keyword diff** inline for each A-tier match. Full tailored resumes and outreach drafts are generated **on demand** when the user replies with `pack <id> ...` after reviewing the report.

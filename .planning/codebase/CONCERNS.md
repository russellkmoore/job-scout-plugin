# Codebase Concerns

**Analysis Date:** 2026-04-27

## Tech Debt

**Schema/code drift after v0.3.2 column trim (highest priority):**
- Issue: `MASTER_TARGETS_VERSION = 3` in `scripts/schema.py:36` removed `pipeline_tier`, `location`, `warm_path`, `already_applied`, `roles_applied_for`, `fit_score`, `what_they_do`, but several callers and docs still reference those columns.
- Files referencing removed columns:
  - `scripts/consolidate_targets.py:270` — `master['already_applied'].str.upper() == 'Y'` will raise `KeyError` on any consolidate run because the column no longer exists in `MASTER_COLUMNS`. The summary print at the end of `consolidate()` is dead-on-arrival for any non-legacy file.
  - `skills/job-scout/references/search-config.md:52` — Pass 1 priority order says "Companies on the user's pipeline list (`pipeline_tier <= 2`)" but `pipeline_tier` is no longer a schema column. Models will look it up and miss.
  - `skills/job-scout/references/scoring-rubric.md:111` — bonus row "Company on Target Pipeline +5" depends on `pipeline_tier 1-3`, same problem.
  - `skills/job-scout/SKILL.md:38` describes the schema list inline ("Currently includes `company_name`, `pipeline_tier`, `industry`, `location`, …") which contradicts `schema.py`. The "single source of truth" guarantee in the same paragraph is currently false.
- Impact: silent data loss on consolidation summary, scoring rubric step that can never trigger, contradictory authority docs that the model will resolve unpredictably each run.
- Fix approach: drop the `already_applied` summary block from `consolidate_targets.py`; rewrite the Pass 1 priority order in `search-config.md` to use `linkedin_connection_count` thresholds; rewrite the +5 bonus to be `data_source` or `fit_notes`-driven; delete the inline column list from `skills/job-scout/SKILL.md:38` and replace with "see `scripts/schema.py`."

**Default value drift across docs (`companies_per_day`):**
- `templates/config.json:32` ships `companies_per_day: 5`.
- `skills/scout-run/SKILL.md:73` says "Pick `companies_per_day` companies (default 8)".
- `skills/job-scout/references/search-config.md:43` reconciles with "default 8 in older configs, default 5 in template."
- Impact: users reading the run skill expect 8, schedulers see 5, no one knows which is right. Contradicts the "one source of truth" rule.
- Fix: pick one default, update all three locations; or stop quoting defaults in any doc and always defer to `templates/config.json`.

**Plugin / skill version sprawl:**
- `.claude-plugin/plugin.json:3` → `0.3.3`
- `skills/scout-run/SKILL.md:5` → `0.3.3` (working tree, was `0.3.1` at HEAD)
- `skills/scout-setup/SKILL.md:5` → `0.3.1`
- `skills/job-scout/SKILL.md:9` → `0.3.0`
- Impact: every skill carries its own version that nobody bumps in lockstep with the plugin. Easy to ship a "v0.3.3" that's actually still running 0.3.0 skill content.
- Fix: either remove `version:` from individual SKILL.md frontmatter and rely on plugin.json, or add a release script that bumps all four together.

**`commands/` directory referenced but no longer exists:**
- `skills/job-scout/SKILL.md:46` says "The full step-by-step is in `commands/scout-run.md`."
- `skills/job-scout/SKILL.md:105` says "See `commands/scout-run.md` 'On-demand: generate A-tier packet' for the file layout."
- `skills/job-scout/references/search-config.md:28` says "Budget formula (in `commands/scout-run.md`)".
- The commit `1d31872 v0.3.1: migrate commands/ to skills/scout-run + skills/scout-setup` moved these files.
- Impact: the model is told to look at a path that doesn't exist. Either it gives up or it invents content.
- Fix: rewrite the three references to point at `skills/scout-run/SKILL.md`.

**`scout/` legacy fallback contradicts "no fallbacks" rule:**
- `skills/job-scout/references/file-contract.md:3` — "**No alternate paths. No fallbacks. No 'or'.**"
- `scripts/state.py:32-36` defines `LEGACY_DATA_DIRS = ["~/Documents/JobSearch/scout", "~/Documents/JobSearch", "~/Documents/JobScout"]` and `resolve_data_dir()` walks all three.
- The v0.3.2 commit added `~/Documents/JobSearch/scout` as a *new* legacy entry, growing the list rather than shrinking it.
- Impact: the contract is aspirational, not enforced. The longer the legacy list grows, the more chances for the wrong directory to be chosen on machines with multiple stale folders.
- Fix: either delete `LEGACY_DATA_DIRS` and force `/scout-setup` migration, or move the disclaimer in `file-contract.md` to acknowledge the actual fallback chain.

## Known Bugs

**`consolidate_targets.py` will crash on any directory consolidate run:**
- `scripts/consolidate_targets.py:270` references `master['already_applied']` after the column was removed from the schema (see Tech Debt above). `pd.DataFrame['nonexistent_col']` raises `KeyError`.
- Trigger: `python3 scripts/consolidate_targets.py --output … --files …` with any input that goes through `merge_duplicates()`.
- Workaround: comment out lines 270-272 of `consolidate_targets.py` or run with files that have `already_applied` columns to keep the path alive.

**`tracker_utils.append_rows` says "Still add it, but flagged" but the comment lies (line 199):**
- `scripts/tracker_utils.py:194-199` increments `skipped_stale` but the row IS added immediately after, so `skipped_stale` is misnamed — it's `flagged_stale`. The returned dict at line 229 already calls it `flagged_stale`, but the local variable name and the inline `# Still add it, but flagged` comment are inconsistent with the loop control flow.
- Impact: future maintainer who reads "skipped_stale" assumes stale rows are dropped, may add a `continue` and silently break the contract documented in the SKILL ("They go in the report's 'Stale / skipped' section, not in the A/B/C tiers" — but in fact they're in both).
- Fix: rename the local to `flagged_stale_count` to match the output key.

**Job-ID regex is too permissive — risk of stale-flagging URLs that aren't LinkedIn:**
- `scripts/tracker_utils.py:69` uses `re.search(r'(\d{10,})', str(url))` and treats any 10+ digit run as a LinkedIn job ID.
- A career-page URL like `https://acme.com/careers/job/2024100912345` (timestamp-based ID) will match. If it happens to be < 4_200_000_000 the row will be flagged stale and grayed out for the wrong reason.
- Fix: anchor the regex to LinkedIn URLs specifically: `re.search(r'linkedin\.com/jobs/(?:view|search)/\D*(\d{10,})', url)`. Return `None` for non-LinkedIn URLs so the stale gate is skipped.

**`mine_connections.py` skips the wrong number of header rows when LinkedIn changes the export format:**
- `scripts/mine_connections.py:29-45` scans for `"First Name"` or `"Company"` substring, then returns the line index. If LinkedIn ever drops a localized export (Spanish: "Nombre"), the function falls through and silently defaults to `(3, 'latin-1')` — even when the actual header is at row 0 because they removed the preamble.
- Impact: `pd.read_csv(skiprows=3)` on a file whose headers are already at row 0 throws away the first 3 connections and reads the 4th as the header. Detection is silent — you'd get 3 fewer connections per run with no error.
- Fix: log a warning when falling back to the default, and validate that the resulting columns include a recognizable name/company column before proceeding.

## Security Considerations

**LinkedIn export and `Connections.csv` contain PII for hundreds of third parties:**
- `scripts/mine_connections.py` reads `Connections.csv` (first/last name, current company, position) for every connection the user has — typically 500-5000 people, none of whom consented.
- Output goes to `<data_dir>/connections_summary.csv` and is then folded into `master_targets.csv` at `connection_names` (`scripts/consolidate_targets.py:165-172`).
- Impact: third-party PII sits in plaintext under `~/Documents/JobSearch/` indefinitely. If the data dir is ever synced to iCloud, Dropbox, or backed up to a shared drive, it leaves the user's machine.
- Mitigation in place: none documented.
- Recommendations: (a) add a one-line note in `skills/scout-setup/SKILL.md` Step 1 telling users this data lives unencrypted on disk; (b) consider hashing or first-name+last-initial-only by default with a `--full-names` opt-in; (c) document that `<data_dir>` should not be in a synced folder.

**Resume PDF path stored as plaintext in config:**
- `templates/config.json:13` → `candidate.resume_path` (absolute path).
- `<data_dir>/Resumes/` is the resume bank.
- Impact: if `config.json` is ever shared (bug report, support thread), it leaks the user's filesystem layout and resume location.
- Recommendation: add a `.gitignore` template for `<data_dir>` and warn users in setup not to share `config.json` raw.

**No file permissions hardening on state.json or data_dir:**
- `scripts/state.py:52` does `os.makedirs(STATE_DIR, exist_ok=True)` and `json.dump(..., f, indent=2)` with default umask. On macOS multi-user systems this creates `~/.job-scout/state.json` as 644.
- Impact: another local user on the same machine can read the data_dir path and follow it to the resume, candidate profile, and connections summary.
- Fix: `os.chmod(STATE_PATH, 0o600)` after write; `os.chmod(STATE_DIR, 0o700)` after `makedirs`.

**`--break-system-packages` instruction in error messages:**
- `scripts/validate_data.py:29`, `scripts/tracker_utils.py:31`, `scripts/consolidate_targets.py:26`, `scripts/mine_connections.py:25` all tell users to run `pip install pandas --break-system-packages` when imports fail.
- Impact: this nukes PEP 668 protection on Python 3.12+ system installs and can break OS-managed Python. The flag exists for emergencies, not for normal install instructions.
- Fix: recommend `pipx`, a virtualenv, or `python3 -m venv` in the message instead.

## Reliability / Site-Breakage Risks

**LinkedIn JD lazy-load sequence is brittle and undocumented elsewhere:**
- The "scroll to 800 → wait 3-5s → click '...more' → get_page_text" sequence in `skills/job-scout/references/chrome-setup.md:36-46` and `skills/scout-run/SKILL.md` Step 1 is a 4-step empirical workaround for LinkedIn anti-bot. The fix-commit history shows this was already broken once: `4632686 Fix LinkedIn JD extraction and add career page searching (v0.2.1)`.
- Specific failure modes not handled:
  - LinkedIn rotates the "...more" button label/aria attribute periodically. The `find` tool dependency in step 4 will return nothing the day they ship "Show more" or `aria-label="Expand description"`.
  - The 3-5s wait is fixed; on slow networks it's still too short, on fast ones it wastes time.
  - No retry logic — first failure abandons the listing.
- Impact: every LinkedIn UI change silently degrades A-tier output to "header-only metadata."
- Mitigation suggestions: (a) try multiple selectors for the more button; (b) if `get_page_text` returns < 500 chars after the dance, retry once with a longer wait; (c) log to `run_log.json` how many JDs failed extraction so trend regression is visible.

**No rate-limit / retry / backoff anywhere:**
- `chrome-setup.md:94-102` ("LinkedIn Bot Detection") only suggests "Don't run searches too rapidly" and "wait 24 hours before trying again" — both are model-side behavioral hints, not enforced.
- The skill never tells the model to insert sleeps between page loads.
- Impact: a run that hits 8 companies × 3 sources × multiple JD pageloads can fire 30-60 LinkedIn requests in a few minutes. Detection → captcha → user must intervene mid-run.
- Fix: add an explicit "between every 5 navigations, pause 10-15 seconds" rule in `scout-run/SKILL.md` Step 1.

**Pass 2 board selectors are inline and unversioned:**
- `skills/job-scout/references/job-boards.md` hardcodes URL patterns and DOM expectations for Wellfound (line 13-15), Built In Seattle (line 44-46), HN Algolia (line 73), YC Work at a Startup (line 107-109).
- None of these are tested. When Wellfound restructures `wellfound.com/jobs?role=...` (already happened multiple times — they were AngelList Talent before the rebrand) the scout silently returns 0 results from that board.
- Impact: silent zero-result passes look like "no roles matched" rather than "scraper broke."
- Mitigation suggestion: every Pass 2 board should require a non-empty result on at least one of the last 3 runs, and surface a "board appears broken" warning in the report's "Honest notes" section if not.

**No automated tests:**
- Zero `*test*.py`, no CI workflow, no `pytest`/`unittest` invocation anywhere in the repo.
- The five Python scripts under `scripts/` have no test coverage.
- The schema migration in `scripts/validate_data.py:80-91` (auto-add columns to `master_targets.csv`) silently mutates user data on every run without a regression test.
- Impact: regression risk on every change. The recent `v0.3.2` schema trim is a perfect example — `consolidate_targets.py:270` reference to a removed column would have been caught by a single test that runs `consolidate()` end-to-end.
- Fix: add a `tests/test_schema_migration.py` with synthetic fixtures for v1, v2, v3 master_targets shapes.

## Performance Bottlenecks

**Sequential board searches in Pass 2 + sequential listings in Pass 1:**
- The skill (`skills/scout-run/SKILL.md` Step 2-4) iterates companies one-by-one, then JD-by-JD inside each. With `companies_per_day=8` and ~3 sources each, that's 24 sequential page loads in Pass 1 alone before scoring even starts. Add Pass 2's 4 boards and Pass 3's keyword loop and the model is doing 50-80 sequential Chrome navigations in a single run.
- README claim is "15-30 minutes" — that's bounded by sequential page loads, not by reasoning.
- The most recent commit `de48749` summary (`v0.3.2: clean up locations and start running individual board searches`) suggests the author is actively working on splitting board searches into separate invocations — which addresses interactivity but not aggregate wall time.
- Improvement path: there's no parallelism primitive available to the in-Chrome MCP, so true concurrency isn't possible — but JD extraction for already-identified listings could be batched at the end of each pass instead of in-line, allowing the model to drop low-score candidates before paying the lazy-load cost for them.

**JD extraction cost is paid before scoring:**
- `skills/scout-run/SKILL.md:93-96` extracts the full JD ("title, location, comp range, apply URL, JD text (full)") for every promising listing in Pass 1, then scores afterwards.
- Pass 3 step 5 (`skills/scout-run/SKILL.md:135`) does the lazy-load dance on every non-stale listing before scoring.
- Many of those listings will end up in C-tier or skip — the JD body wasn't actually needed. JD extraction is the single most expensive operation per listing (scroll + 3-5s wait + click + read).
- Improvement path: do header-only triage scoring first (title + company + connection count = ~50% of the rubric weight). Skip JD extraction for anything that can't reach B-tier on header data alone.

## Fragile Areas

**`scripts/tracker_utils.py:_write_tracker` rebuilds the entire xlsx file on every append:**
- Lines 264-315 — `append_rows` calls `_write_tracker(filepath, existing_rows)` which constructs a fresh `openpyxl.Workbook()` and re-emits every row with formatting.
- For a tracker with 500+ rows this is fine; for 5000+ it becomes noticeably slow (and openpyxl is not memory-efficient at scale).
- Why fragile: any user data in the xlsx that isn't in `TRACKER_COLUMNS` (notes columns the user added manually, additional sheets, charts) is silently destroyed on every append. The header-row protection at line 296 (`if col > len(HEADERS): break`) drops user columns when reading-back, then never writes them.
- Safe modification: never edit `_write_tracker` without first writing a test that adds a user column to the xlsx, runs append, and asserts the user column survives.
- Test coverage: none.

**`extract_job_id` shared across read and write paths with no guard:**
- `scripts/tracker_utils.py:65-70` is called by `load_tracker` (read), `append_rows` (dedup), `is_stale_by_id` (stale flag), and `rebuild` (dedup) — four callers, one regex. Any change to job ID extraction logic (e.g. supporting LinkedIn's new alphanumeric IDs when they ship them) cascades into all four behaviors.
- Why fragile: a regex tightening to fix the false-positive on career-page IDs (see Known Bugs) will simultaneously change which rows are considered duplicates on next `rebuild` — potentially un-deduping previously-merged rows.
- Safe modification: split into `extract_linkedin_job_id` (used for stale check) and `extract_dedup_key` (URL-as-string fallback for non-LinkedIn). Migrate callers explicitly.

**`pipeline_tier <= 2` reference in scoring rubric drives a +5 bonus that can never trigger:**
- `skills/job-scout/references/scoring-rubric.md:111` — bonus row depends on a column that doesn't exist in the v3 schema (`MASTER_TARGETS_COLUMNS` in `schema.py`).
- Why fragile: model reading the rubric will look up `pipeline_tier`, get `KeyError` or empty, log a "not applicable" note, and silently never award the bonus. Scoring is deterministic on paper but stochastic in practice based on which doc the model reads first.
- Test coverage: zero. The scoring engine is implemented in the prompt, so unit-testing it is hard, but a fixture-based "score this synthetic listing, expect score X" check would catch this.

## Scaling Limits

**Chrome session = single tab = single user:**
- The MCP `Claude_in_Chrome` integration assumes one Chrome instance, one logged-in user. `chrome-setup.md:27-34` ("Verify Connection") doesn't handle multiple Chrome profiles.
- Cap: 1 concurrent run per machine. If the user opens a second Cowork session, both fight for tabs.
- Scaling path: not currently a real constraint — this is a single-user CLI plugin — but if anyone ever wants to schedule multiple parallel scout runs (different verticals?) this falls apart.

**Tracker dedup is O(n) on every append:**
- `scripts/tracker_utils.py:130-143` (`load_tracker`) reads every row of the xlsx into a Python list and a set. With 10K+ entries openpyxl read times become measurable (~5-10s).
- Cap: practical limit ~5000 rows before append latency becomes annoying.
- Scaling path: switch from xlsx-as-database to sqlite, expose xlsx as a "report view" rebuilt on demand.

## Dependencies at Risk

**`pandas` and `openpyxl` are both heavyweight for what this plugin does:**
- `scripts/validate_data.py:27`, `scripts/consolidate_targets.py:23`, `scripts/mine_connections.py:24` all `import pandas`.
- `scripts/tracker_utils.py:27-28` imports `openpyxl`.
- README requires Python 3.8+ with both packages.
- Risk: pandas alone is ~30MB and pulls numpy. openpyxl is well-maintained but its API is verbose. Together they make the plugin hostile to environments where the user can't install heavy deps (corporate-locked machines, restricted Python).
- Migration plan: pandas usage in `mine_connections.py` and `consolidate_targets.py` could be replaced with stdlib `csv` + `collections` with ~2x more code but zero install pain. openpyxl is harder to remove without losing the formatted xlsx output.

**Claude in Chrome MCP is the only browsing path:**
- `skills/scout-run/SKILL.md:62-63` — `mcp__Claude_in_Chrome__tabs_context_mcp` is the only entry point.
- The chrome-setup.md notes a "Fallback Mode" but it requires the user to manually paste JDs.
- Risk: if Anthropic changes the MCP tool name, removes the extension, or breaks tab access, every run drops to fallback.
- Mitigation: not really avoidable — this is the supported integration point — but the README should be more explicit that this is a hard dependency.

## Missing Critical Features

**No "did it work?" telemetry across runs:**
- `<data_dir>/daily/<DATE>/run_log.json` is written per-run (`skills/scout-run/SKILL.md:50, 230`) but nothing reads multiple `run_log.json` files together. There's no command for "show me how many A-tier matches I've gotten the past 30 days" or "which boards have given me zero hits for the past 5 runs?"
- Impact: the user has no way to detect a slow regression (e.g., "Wellfound has returned 0 results for 7 runs in a row — probably broken, not 'no matches'").
- Fix: a `/scout-stats` skill that scans `daily/*/run_log.json` and surfaces trends.

**No way to tell the scout to ignore a company permanently:**
- Schema has `application_status` (free text). The skill at `skills/scout-run/SKILL.md:78` says "skip those with `Dead`" but `Dead` is just a magic string.
- A typo (`dead`, `DEAD`, `Dead.`, `Closed`) silently re-includes the company.
- Fix: define a small enum of `application_status` values in `schema.py` and validate on append.

## Test Coverage Gaps

**Zero tests anywhere in the repo:**
- No `tests/` directory, no `pytest.ini`, no `conftest.py`, no CI config (`.github/workflows/`, `.circleci/`, etc.).
- Files most at risk:
  - `scripts/tracker_utils.py` — formatting/dedup logic, runs every job and silently rewrites the user's xlsx.
  - `scripts/validate_data.py` — auto-migrates user data; one bad migration permanently corrupts `master_targets.csv`.
  - `scripts/consolidate_targets.py` — column mapping + merge logic; the `already_applied` bug (Known Bugs above) is exactly the class of thing one fixture test catches.
  - `scripts/mine_connections.py` — encoding/header detection on a file format LinkedIn changes periodically.
- Risk: every commit is a regression risk. The `v0.3.2` cleanup commit shipped a `consolidate_targets.py:270` `KeyError` to `main` because there was nothing to catch it.
- Priority: High. Even minimal smoke tests (`run consolidate against a fixture, assert no exception`) would have prevented the v0.3.2 ship-bug.

**No validation that the daily report actually got written:**
- `skills/scout-run/SKILL.md:223-230` writes `new_rows.json` then calls `tracker_utils.py append`, but there's no post-condition check that the daily report markdown exists, that the report's A-tier count matches the tracker's A-tier count for `<TODAY>`, or that `run_log.json` was created.
- Risk: a run that errors mid-Step 6 leaves a half-written report and a fully-updated tracker — out of sync, undetectable.
- Priority: Medium.

---

*Concerns audit: 2026-04-27*

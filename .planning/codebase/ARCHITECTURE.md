# Architecture

**Analysis Date:** 2026-04-27

## Pattern Overview

**Overall:** Skill-driven Claude Code plugin with a thin Python utility layer.

The plugin packages **three skills** (`scout-setup`, `scout-run`, `job-scout`) that orchestrate the work and **five Python scripts** in `scripts/` that perform deterministic, side-effecting operations (state pointer I/O, schema validation, tracker append/dedup/format, LinkedIn connection mining, target consolidation). Skill markdown holds *control flow + LLM judgement* (search strategy, scoring, narrative report writing); scripts hold *anything that must produce identical output every run* (file paths, schemas, xlsx formatting, dedup).

**Key Characteristics:**
- **Skill-as-runbook.** Each `SKILL.md` is a numbered, step-by-step prompt that Claude follows verbatim. The two operational skills (`scout-setup` for first-run, `scout-run` for daily) are user-invokable; `job-scout` is the shared knowledge skill they both load before doing anything else.
- **Scripts handle determinism, prompts handle judgement.** Schemas, tracker formatting, and tracker dedup are factored out of prompts into `scripts/` so they cannot drift between runs. Scoring, query phrasing, honest assessment, and report writing stay in the markdown because they need LLM reasoning.
- **Single-source-of-truth files.** Column schemas live in `scripts/schema.py` (imported by all scripts, referenced-by-name in prompts). Every file path lives in `skills/job-scout/references/file-contract.md`. State pointer lives in `~/.job-scout/state.json`. Each fact lives in exactly one place.
- **Three-pass search budget.** Daily run allocates `max_listings_per_run` across Pass 1 (career pages, ~60%), Pass 2 (Built In Seattle / Wellfound / YC / HN, ~25%), Pass 3 (LinkedIn keyword, ~15%, last). Passes do not roll over leftover budget.
- **Hybrid on-demand output.** Daily report ships inline ATS keyword diff for A-tier matches; full tailored resume + outreach packets are generated on demand when the user replies `pack <id1> <id2> ...`.

## Layers

**Plugin manifest layer:**
- Purpose: Register the plugin with Claude Code, declare name/version/description.
- Location: `.claude-plugin/plugin.json`
- Contains: Name (`job-scout`), version (`0.3.3`), description, author block.
- Depends on: Nothing.
- Used by: Claude Code plugin loader.

**Skill layer (orchestration + knowledge):**
- Purpose: Drive the user-facing flows and hold non-deterministic knowledge (scoring rubric, search strategy, board specs, prose).
- Location: `skills/scout-run/SKILL.md`, `skills/scout-setup/SKILL.md`, `skills/job-scout/SKILL.md`, `skills/job-scout/references/*.md`
- Contains: YAML frontmatter (name, description, allowed-tools, version), step-by-step instructions, references to `${CLAUDE_PLUGIN_ROOT}` paths.
- Depends on: Scripts layer (calls `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/...` for every deterministic operation), Templates layer (uses `templates/config.json` and `templates/candidate_profile.json` as structural starting points), Claude in Chrome MCP tools (`mcp__Claude_in_Chrome__*`).
- Used by: Claude Code at runtime when the user types `/scout-setup` or `/scout-run`.

**Script layer (deterministic operations):**
- Purpose: Anything that must produce identical output every run — schema definitions, file I/O, xlsx formatting, dedup logic, parsing LinkedIn exports.
- Location: `scripts/`
- Contains: Pure-Python CLIs invoked by the skill prompts. Each script has a `main(argv)` that takes positional arguments and prints JSON or text to stdout (designed for prompts to capture and reason about).
- Depends on: `pandas`, `openpyxl` (declared in `README.md` requirements), Python 3.8+. `state.py` and `schema.py` have no third-party deps.
- Used by: Skill prompts via `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py ...` shell calls.

**Template layer (config skeletons):**
- Purpose: Provide the canonical JSON shape for `config.json` and `candidate_profile.json` so `/scout-setup` populates a structurally complete file.
- Location: `templates/config.json`, `templates/candidate_profile.json`
- Contains: All keys with empty/default values; defaults match the constants in `scripts/schema.py`.
- Depends on: Nothing.
- Used by: `scout-setup` (reads, fills, writes to `<data_dir>/config.json` and `<data_dir>/candidate_profile.json`).

**Reference layer (skill knowledge base):**
- Purpose: Hold longer-form skill knowledge that prompts pull in conditionally.
- Location: `skills/job-scout/references/`
- Contains: `file-contract.md` (the single path registry), `search-config.md` (3-pass strategy + scoring), `scoring-rubric.md` (point breakdowns), `job-boards.md` (Pass 2 board specs), `tailoring-guide.md` (resume diff rules), `assessment-framework.md` (honest assessment), `profile-extraction-guide.md` (resume parsing), `chrome-setup.md` (LinkedIn JD lazy-load sequence).
- Depends on: Nothing.
- Used by: `scout-setup` and `scout-run` SKILL.md prompts via explicit `Read ${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/<file>.md` calls at the top.

**External data layer (user-owned, outside plugin):**
- Purpose: Persistent user data, kept outside the plugin so `git pull` never touches it.
- Location: `~/.job-scout/state.json` (machine-wide pointer), `<data_dir>/` (default `~/Documents/JobSearch/`).
- Contains: `config.json`, `candidate_profile.json`, `master_targets.csv`, `JobScout_Tracker.xlsx`, `assessment/Honest_Career_Assessment.md`, `Resumes/`, `daily/<DATE>/...` (report + run_log + new_rows + on-demand packets).
- Depends on: `/scout-setup` for initial creation; `/scout-run` for daily updates.
- Used by: Both skills, every run.

## Data Flow

**Setup flow (`/scout-setup`, runs once per user):**

1. Skill loads `skills/job-scout/SKILL.md`, `references/file-contract.md`, `references/profile-extraction-guide.md`, `references/assessment-framework.md`.
2. `AskUserQuestion` gathers: resume path, LinkedIn export path, existing tracking files, `data_dir` choice (default `~/Documents/JobSearch`).
3. Questionnaire fills gaps the resume can't answer (salary, deal-breakers, recent interview/rejection history, self-identified weaknesses).
4. Resume is parsed against `references/profile-extraction-guide.md` rules; produces `candidate_profile.json` matching `templates/candidate_profile.json` structure (skills classified `strongest` / `credible` / `aspirational`).
5. If LinkedIn export provided: `python3 scripts/mine_connections.py <Connections.csv> <data_dir>/connections_summary.csv` produces a per-company connection summary with names, titles, count.
6. `python3 scripts/consolidate_targets.py --output <data_dir>/master_targets.csv --connections <data_dir>/connections_summary.csv --files <user_csv>...` merges all sources into `master_targets.csv` using `MASTER_TARGETS_COLUMNS` from `scripts/schema.py`.
7. Honest assessment generated per `references/assessment-framework.md` and written to `<data_dir>/assessment/Honest_Career_Assessment.md`.
8. Search queries (6–8 primary + 2–3 underutilized-asset) generated from profile + assessment; written into `<data_dir>/config.json` (using `templates/config.json` as the skeleton).
9. `python3 scripts/state.py write <data_dir> <plugin_version>` writes the pointer at `~/.job-scout/state.json`.
10. `python3 scripts/validate_data.py <data_dir>` confirms everything is wired up.

**Daily run flow (`/scout-run`, every day):**

1. Skill loads `skills/job-scout/SKILL.md`, `references/file-contract.md`, `references/search-config.md`, `references/job-boards.md`.
2. `python3 scripts/state.py resolve` returns `<data_dir>` (exit 2 → tell user to run `/scout-setup`).
3. `python3 scripts/validate_data.py <data_dir>` auto-migrates schema (adds missing columns to `master_targets.csv`), creates missing files (`JobScout_Tracker.xlsx`, `daily/`).
4. Skill loads `<data_dir>/config.json`, `candidate_profile.json`, resume PDF, `master_targets.csv`.
5. `python3 scripts/tracker_utils.py dedup-set <data_dir>/JobScout_Tracker.xlsx` returns the JSON list of LinkedIn job IDs already tracked. Listings with these IDs are skipped before scoring.
6. Per-pass listing budgets computed from `config.search.max_listings_per_run`: Pass 1 = `round(0.60 * N)`, Pass 2 = `round(0.25 * N)`, Pass 3 = `N − P1 − P2`.
7. Chrome verified via `mcp__Claude_in_Chrome__tabs_context_mcp`. If unavailable → Fallback Mode (generate clickable URLs, score whatever the user pastes).
8. **Pass 1 (company-first).** Pick top `companies_per_day` rows from `master_targets.csv` sorted by `linkedin_connection_count` desc, `last_checked` asc, excluding `application_status = "Dead"`. For each: career page → ATS board (Greenhouse/Lever/Workday/Ashby) → LinkedIn keyword scoped to company name + location. Update `last_checked = <TODAY>` for each company visited.
9. **Pass 2 (other boards).** Per `references/job-boards.md`: Built In Seattle (~33% of P2), Wellfound (~28%), YC Work at a Startup (~20%), HN "Who is hiring" (~20%). Cross-board dedup by normalized company + role title.
10. **Pass 3 (LinkedIn keyword).** Run each query in `config.search.queries` then `underutilized_asset_queries`, with Date Posted = past 24h (or past week on first run) and Experience Level = Director/Executive. Stop early on noise.
11. **Score** every candidate listing with the 5-category weighted rubric (`references/scoring-rubric.md`). Tier thresholds from `config.scoring`. Hard cap: 10 A-tier per run.
12. Write `<data_dir>/daily/<TODAY>/JobScout_Report_<TODAY>.md` with executive summary, per-pass breakdown, A-tier blocks (apply URL, warm path, ATS keyword diff, outreach draft, recommended resume version, honest read), B-tier (lighter), C-tier table, stale/skipped table, companies-no-match list, mandatory honest notes, on-demand `pack <id>` instructions.
13. Write `<data_dir>/daily/<TODAY>/new_rows.json` (one object per scored listing, keys from `TRACKER_JSON_KEYS`).
14. `python3 scripts/tracker_utils.py append <data_dir>/JobScout_Tracker.xlsx <data_dir>/daily/<TODAY>/new_rows.json` deterministically appends, dedups, flags stale, color-formats. Stdout JSON captured into `run_log.json`.
15. Update `master_targets.csv` `last_checked` for visited companies; append `data_source = "scout_discovered"` rows for newly surfaced companies.
16. Chat summary: counts, top match, link to report, one honest observation. If zero A-tier, say so directly.

**On-demand packet flow (user replies `pack <id1> <id2> ...`):**

1. For each ID, generate `<data_dir>/daily/<TODAY>/packets/<Company>_<Role>/` containing `jd.md`, `tailored_resume.docx` (built from recommended resume version with ATS diff applied — never fabricate skills), `ats_diff.md`, `outreach_draft.md`.
2. Return a single chat link to the packet folder.

**State Management:**
- **State pointer** (`~/.job-scout/state.json`): written once by `/scout-setup` via `state.py write`, read every run by `/scout-run` via `state.py resolve`. Has legacy fallback to `~/Documents/JobSearch/scout`, `~/Documents/JobSearch`, `~/Documents/JobScout` if pointer missing (see `LEGACY_DATA_DIRS` in `scripts/state.py`).
- **Config** (`<data_dir>/config.json`): canonical source of truth for queries, weights, thresholds, budgets, `companies_per_day`, `max_listings_per_run`, `assessment_style`. Edit this file to change behavior — never override in scheduled-task instructions or chat.
- **Master targets** (`<data_dir>/master_targets.csv`): incremental — `last_checked` and `application_status` updated each run. Schema additions auto-migrate via `validate_data.py`.
- **Tracker** (`<data_dir>/JobScout_Tracker.xlsx`): append-only, written ONLY through `tracker_utils.py append`. Dedup is by LinkedIn job ID (`extract_job_id` in `scripts/tracker_utils.py`).
- **Daily artifacts** (`<data_dir>/daily/<DATE>/`): per-run output, never overwritten; `validate_data.py` creates the `daily/` parent directory.

## Key Abstractions

**Skill (Claude Code SKILL.md):**
- Purpose: A frontmatter-tagged markdown prompt that Claude executes step-by-step when invoked. The unit of user interaction.
- Examples: `skills/scout-setup/SKILL.md`, `skills/scout-run/SKILL.md`, `skills/job-scout/SKILL.md`
- Pattern: YAML frontmatter (`name`, `description` with trigger phrases, `allowed-tools`, `version`) followed by step-by-step prose with embedded shell calls and `Read`/`Write` instructions. Long knowledge factored into `references/`.

**File contract:**
- Purpose: Single, authoritative registry of every path the scout reads or writes. Prevents path drift across prompts.
- Location: `skills/job-scout/references/file-contract.md`
- Pattern: Tables of `(file, path, owner)`. Rule: when adding a new artifact, add it here first, then reference this doc from wherever it's written. Paths use `{data_dir}` as a placeholder, resolved at runtime.

**Schema module:**
- Purpose: Single source of truth for every column name and threshold, importable by scripts and referenced by name in prompts.
- Location: `scripts/schema.py`
- Pattern: Module-level constants — `MASTER_TARGETS_COLUMNS`, `TRACKER_COLUMNS`, `TRACKER_JSON_KEYS`, `TRACKER_COL_WIDTHS`, `STALE_LINKEDIN_JOB_ID_THRESHOLD`, `DEFAULT_TIER_*_THRESHOLD`, `MASTER_TARGETS_VERSION`. No CLI, no side effects, import-only.

**State pointer:**
- Purpose: Decouple plugin location from user data location. Lets `/scout-run` find the data dir deterministically without guessing.
- Location: `~/.job-scout/state.json` (written by `scripts/state.py write`).
- Pattern: Tiny JSON `{data_dir, plugin_version, last_setup_iso}`. `resolve_data_dir()` in `scripts/state.py` returns the pointer's `data_dir`, falling back through `LEGACY_DATA_DIRS` if missing.

**Search runner (per-pass, in-prompt):**
- Purpose: Each of the three passes is a structured iteration in `skills/scout-run/SKILL.md` (Steps 2–4) with a fixed budget, source order, and stop conditions.
- Location: `skills/scout-run/SKILL.md` Steps 2 (Pass 1), 3 (Pass 2), 4 (Pass 3); per-pass details in `skills/job-scout/references/search-config.md` and `job-boards.md`.
- Pattern: Read sources in priority order (career page → ATS board → LinkedIn for Pass 1; Built In → Wellfound → YC → HN for Pass 2). Stop when budget hit. Don't roll over leftover budget.

**Scorer (in-prompt):**
- Purpose: Score every candidate listing with a 5-category weighted rubric, then assign a tier.
- Location: `skills/scout-run/SKILL.md` Step 5; full rubric in `skills/job-scout/references/scoring-rubric.md`.
- Pattern: Connection Leverage (default 30) + Experience Match (25) + Domain Fit (20) + Compensation (15) + Realistic Shot (10) + bonuses/penalties. All weights and thresholds come from `config.scoring` at runtime — defaults in `scripts/schema.py` are only used if config missing.

**Tracker writer:**
- Purpose: Deterministic xlsx append/dedup/format. The only thing that may write to `JobScout_Tracker.xlsx`.
- Location: `scripts/tracker_utils.py` (CLI: `dedup-set`, `append`, `rebuild`).
- Pattern: All formatting constants frozen at module top (`HEADER_FILL`, `A_TIER_FILL`, etc. — exact hex colors). Dedup by LinkedIn job ID extracted with regex (`extract_job_id`). Stale flag when ID `< STALE_LINKEDIN_JOB_ID_THRESHOLD`. `_write_tracker` rebuilds the entire workbook every call to guarantee identical formatting.

**Validator:**
- Purpose: Idempotent health check + auto-migration that runs at the top of every `/scout-run`.
- Location: `scripts/validate_data.py`
- Pattern: For each of `config`, `master_targets`, `tracker`, `daily_dir` — call a check function that creates missing files, adds missing schema columns (never deletes), prints a JSON results object. Exits 0 on success even if migrations were applied silently; exits 1 only if unrecoverable (e.g. `config.json` missing).

**Connection miner:**
- Purpose: Turn LinkedIn `Connections.csv` (which has 3 header rows and inconsistent encoding) into a per-company summary.
- Location: `scripts/mine_connections.py`
- Pattern: Auto-detect header rows by scanning for "First Name"; try utf-8/latin-1/cp1252 encodings; group by company; cap names at 10 per company; sort by count desc.

**Target consolidator:**
- Purpose: Merge multiple data sources (LinkedIn connection summary + user-provided CSVs/XLSXs) into a single deduplicated `master_targets.csv` matching `MASTER_TARGETS_COLUMNS`.
- Location: `scripts/consolidate_targets.py`
- Pattern: Column alias map from arbitrary user headers to schema columns; `normalize_company_name` strips Inc/LLC/punctuation for dedup; merge logic prefers user-entered data over auto-generated, sums/maxes connection counts, concatenates connection name lists.

**Formatter (report):**
- Purpose: Render the daily report with mandatory blocks: executive summary, per-pass breakdown, A-tier blocks, B-tier blocks, C-tier table, stale/skipped table, companies-no-match list, honest notes, on-demand instructions.
- Location: `skills/scout-run/SKILL.md` Step 6 (block structure spelled out exactly).

## Entry Points

**`/scout-setup` slash command (first-run):**
- Location: `skills/scout-setup/SKILL.md`
- Triggers: User types `/scout-setup` or asks to "set up the job scout", "configure job scout", "do first-time job scout setup".
- Allowed tools: `Read, Write, Edit, Bash, Glob, Grep, Agent, AskUserQuestion, TodoWrite`
- Responsibilities: Gather user data (resume, LinkedIn export, existing files), run questionnaire, extract profile, write honest assessment, generate search queries, write `<data_dir>/config.json`, write `~/.job-scout/state.json` pointer, run validator. **Chrome not required for setup.**

**`/scout-run` slash command (daily):**
- Location: `skills/scout-run/SKILL.md`
- Triggers: User types `/scout-run` or asks to "run the job scout", "find me jobs", "do a daily job search", "check for new job matches".
- Allowed tools: `Read, Write, Edit, Bash, Glob, Grep, Agent, TodoWrite, mcp__Claude_in_Chrome__*`
- Responsibilities: Resolve `data_dir`, validate, load context, run 3-pass search via Claude in Chrome, score, write daily report + `new_rows.json`, append to tracker, update `master_targets.csv`, summarize in chat.
- **Takes no arguments.** All configuration lives in `<data_dir>/config.json`. Scheduled tasks should call `/scout-run` with no overrides.

**`job-scout` shared knowledge skill (auto-loaded):**
- Location: `skills/job-scout/SKILL.md`
- Triggers: Auto-triggered when the user asks about jobs/scoring/tailoring/assessment; also explicitly read by both operational skills as their first step.
- Allowed tools: (default — inherits from invoker)
- Responsibilities: Hold core philosophy, file contract pointer, schema pointer, scoring overview, Chrome JD-extraction sequence, references index. Not user-runnable on its own — it's the shared knowledge base.

## Error Handling

**Strategy:** Fail-loud with surfaced exit codes. Scripts print JSON or human-readable errors to stdout/stderr; prompts capture and either continue or stop with a clear message to the user.

**Patterns:**
- **State missing:** `scripts/state.py resolve` exits 2 → skill tells user to run `/scout-setup` and stops. (`skills/scout-run/SKILL.md` Step 0.1.)
- **Data dir broken:** `scripts/validate_data.py` exits 1 → skill surfaces the message and stops. (`skills/scout-run/SKILL.md` Step 0.2.)
- **Chrome unavailable:** `mcp__Claude_in_Chrome__tabs_context_mcp` returns nothing → jump to Fallback Mode (generate clickable URLs, score user-pasted JDs). (`skills/scout-run/SKILL.md` Step 1 + "Fallback Mode" section.)
- **LinkedIn login expired:** Navigate to feed, see login page → stop and tell the user. Never enter credentials.
- **Stale LinkedIn listing:** ID `< 4_200_000_000` → flag with `Status = "Stale — Verify"` and gray fill, but still write to tracker so user can decide. (`scripts/tracker_utils.py` `is_stale_by_id`.)
- **Auto-migration:** `validate_data.py` adds missing schema columns silently; never deletes user data.
- **Encoding fallback:** `mine_connections.py` and `consolidate_targets.py` try utf-8 → latin-1 → cp1252 for LinkedIn exports.

## Cross-Cutting Concerns

**Logging:** Per-run stats written to `<data_dir>/daily/<DATE>/run_log.json`. `tracker_utils.py append` returns a JSON summary of `{added, skipped_duplicate, flagged_stale, total_rows}` that the prompt captures into `run_log.json`. No persistent log file.

**Validation:** Centralized in `scripts/validate_data.py`. Runs at end of `/scout-setup` and top of every `/scout-run`. Idempotent. Schema-driven (all checks reference `scripts/schema.py` constants).

**Authentication:** None at the plugin level. LinkedIn / Wellfound / YC logins are user-managed in Chrome. Plugin reads but never enters credentials.

**Determinism boundary:** Anything that must produce identical output every run lives in `scripts/`. Anything that requires LLM judgement (scoring, query phrasing, narrative report writing, honest assessment) stays in skill markdown. The boundary is enforced by the file contract and the schema module — prompts are forbidden from inlining column lists or hardcoding paths.

**Versioning:** Plugin version in `.claude-plugin/plugin.json` (`0.3.3`), individually-versioned skills via frontmatter (`scout-run: 0.3.3`, `scout-setup: 0.3.1`, `job-scout: 0.3.0`), schema versioned via `MASTER_TARGETS_VERSION = 3` in `scripts/schema.py`. The state pointer records `plugin_version` at setup time so future migrations can branch on it.

---

*Architecture analysis: 2026-04-27*

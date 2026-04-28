# Codebase Structure

**Analysis Date:** 2026-04-27

## Directory Layout

```
job-scout-plugin/
├── .claude-plugin/
│   └── plugin.json                              # Plugin manifest (name, version, description)
├── skills/
│   ├── scout-setup/
│   │   └── SKILL.md                             # First-run setup runbook (143 lines, v0.3.1)
│   ├── scout-run/
│   │   └── SKILL.md                             # Daily search runbook (280 lines, v0.3.3)
│   └── job-scout/
│       ├── SKILL.md                             # Shared knowledge skill (125 lines, v0.3.0)
│       └── references/                          # Long-form skill knowledge, loaded on demand
│           ├── file-contract.md                 # Single source of truth for file paths
│           ├── search-config.md                 # 3-pass strategy + scoring rubric overview
│           ├── scoring-rubric.md                # Detailed point breakdowns + examples
│           ├── job-boards.md                    # Pass 2 board specs (Built In, Wellfound, YC, HN)
│           ├── tailoring-guide.md               # ATS-focused resume tailoring rules
│           ├── assessment-framework.md          # Honest career assessment structure + tone
│           ├── profile-extraction-guide.md      # Resume + LinkedIn parsing rules
│           └── chrome-setup.md                  # Claude in Chrome install + LinkedIn JD lazy-load
├── scripts/                                     # Deterministic Python utilities
│   ├── schema.py                                # Single source of truth for column schemas
│   ├── state.py                                 # Read/write ~/.job-scout/state.json pointer
│   ├── validate_data.py                         # Idempotent data dir health check + auto-migration
│   ├── tracker_utils.py                         # Tracker append/dedup/format (only writer of xlsx)
│   ├── mine_connections.py                     # Parse LinkedIn Connections.csv → company summary
│   ├── consolidate_targets.py                   # Merge sources → master_targets.csv
│   └── __pycache__/                             # Python bytecode cache (gitignored)
├── templates/                                   # JSON skeletons for user-data files
│   ├── config.json                              # Structural template for <data_dir>/config.json
│   └── candidate_profile.json                   # Structural template for candidate_profile.json
├── .planning/
│   └── codebase/                                # GSD codebase mapping output (this directory)
├── .gitignore                                   # __pycache__, *.pyc, .DS_Store
└── README.md                                    # User-facing docs (requirements, getting started, file outputs)
```

**User data lives outside the plugin (created by `/scout-setup`, never committed):**

```
~/.job-scout/
└── state.json                                   # {data_dir, plugin_version, last_setup_iso}

<data_dir>/                                      # Default: ~/Documents/JobSearch/
├── config.json                                  # User config (queries, weights, budgets)
├── candidate_profile.json                       # Extracted profile (skills, positioning, network)
├── master_targets.csv                           # Company DB — schema in scripts/schema.py
├── JobScout_Tracker.xlsx                        # Append-only tracker — written ONLY by tracker_utils.py
├── connections_summary.csv                      # Per-company LinkedIn connection counts
├── assessment/
│   └── Honest_Career_Assessment.md
├── Resumes/                                     # User-curated resume bank
└── daily/<YYYY-MM-DD>/
    ├── JobScout_Report_<YYYY-MM-DD>.md          # Daily report
    ├── new_rows.json                            # Input to tracker_utils.py append
    ├── run_log.json                             # Per-pass stats + tracker append summary
    └── packets/<Company>_<Role>/                # On-demand packets (when user replies `pack <id>`)
        ├── jd.md
        ├── tailored_resume.docx
        ├── ats_diff.md
        └── outreach_draft.md
```

## Directory Purposes

**`.claude-plugin/`:**
- Purpose: Claude Code plugin manifest. Required by the plugin loader.
- Contains: A single `plugin.json` with name (`job-scout`), version (`0.3.3`), description, author block.
- Key files: `.claude-plugin/plugin.json`

**`skills/`:**
- Purpose: All Claude-executable runbooks (operational + shared knowledge). Each subdirectory is one skill, identified by its `SKILL.md`.
- Contains: Three skills — two user-invokable (`scout-setup`, `scout-run`) and one auto-loaded knowledge base (`job-scout`).
- Key files: `skills/scout-setup/SKILL.md`, `skills/scout-run/SKILL.md`, `skills/job-scout/SKILL.md`

**`skills/scout-setup/`:**
- Purpose: First-run configuration skill. User runs once per machine.
- Contains: A single `SKILL.md` step-by-step prompt covering data gathering, profile extraction, honest assessment, search query generation, state pointer write, validation.
- Key files: `skills/scout-setup/SKILL.md` (143 lines, v0.3.1, allowed-tools: `Read, Write, Edit, Bash, Glob, Grep, Agent, AskUserQuestion, TodoWrite`)

**`skills/scout-run/`:**
- Purpose: Daily search skill. User runs daily (manually or via scheduled task).
- Contains: A single `SKILL.md` step-by-step prompt covering state resolution, validation, 3-pass search via Claude in Chrome, scoring, report writing, tracker append, master_targets update, chat summary, on-demand packet generation, fallback mode.
- Key files: `skills/scout-run/SKILL.md` (280 lines, v0.3.3, allowed-tools: `Read, Write, Edit, Bash, Glob, Grep, Agent, TodoWrite, mcp__Claude_in_Chrome__*`)

**`skills/job-scout/`:**
- Purpose: Shared knowledge skill. Auto-loaded by Claude when the user mentions jobs/scoring/tailoring; also explicitly read by both operational skills as their first step.
- Contains: `SKILL.md` (core philosophy, file contract pointer, schema pointer, scoring overview, references index) plus `references/` for long-form knowledge.
- Key files: `skills/job-scout/SKILL.md` (125 lines, v0.3.0)

**`skills/job-scout/references/`:**
- Purpose: Long-form skill knowledge factored out of `SKILL.md` so prompts can pull it in conditionally without bloating context.
- Contains: 8 markdown files. Operational skills `Read` the relevant ones at the top of their flow.
- Key files:
  - `skills/job-scout/references/file-contract.md` (69 lines) — The single registry of every file the scout reads or writes. **Always read first.**
  - `skills/job-scout/references/search-config.md` (149 lines) — 3-pass search strategy, budget formula, query handling, scoring rubric overview.
  - `skills/job-scout/references/scoring-rubric.md` (159 lines) — Detailed point breakdowns per category with worked examples.
  - `skills/job-scout/references/job-boards.md` (152 lines) — Pass 2 board specs: URL patterns, filters, parsing gotchas, signal quality table.
  - `skills/job-scout/references/tailoring-guide.md` (115 lines) — ATS-focused resume tailoring rules, anti-patterns, full example.
  - `skills/job-scout/references/assessment-framework.md` (111 lines) — Honest assessment structure, tone calibration (honest / balanced / encouraging), good vs bad examples.
  - `skills/job-scout/references/profile-extraction-guide.md` (142 lines) — How to read resumes + LinkedIn data, classify skills strongest/credible/aspirational.
  - `skills/job-scout/references/chrome-setup.md` (121 lines) — Claude in Chrome install, LinkedIn JD lazy-load extraction sequence (canonical), troubleshooting.

**`scripts/`:**
- Purpose: Deterministic Python utilities. Anything that must produce identical output every run.
- Contains: Six Python files (one schema module, five CLI utilities) plus a Python bytecode cache.
- Key files:
  - `scripts/schema.py` (116 lines) — **Module-level constants only.** `MASTER_TARGETS_COLUMNS`, `TRACKER_COLUMNS`, `TRACKER_JSON_KEYS`, `TRACKER_COL_WIDTHS`, `STALE_LINKEDIN_JOB_ID_THRESHOLD`, `DEFAULT_TIER_*_THRESHOLD`, `MASTER_TARGETS_VERSION`, helper factories `empty_master_target_row()` and `empty_tracker_row()`. Import-only, no CLI, no side effects.
  - `scripts/state.py` (116 lines) — CLI: `read | read-json | write <data_dir> | resolve`. Manages `~/.job-scout/state.json`. Has `LEGACY_DATA_DIRS` fallback list for users on older versions.
  - `scripts/validate_data.py` (146 lines) — CLI: `<data_dir>`. Idempotent: validates `config.json`, auto-adds missing columns to `master_targets.csv`, creates empty tracker if missing, ensures `daily/` exists. Prints JSON results, exits 0/1.
  - `scripts/tracker_utils.py` (346 lines) — CLI: `dedup-set <path> | append <path> <new_rows.json> | rebuild <path>`. The **only** writer of `JobScout_Tracker.xlsx`. All formatting constants (colors, fonts, borders) frozen at module top. Dedup by LinkedIn job ID extracted via regex.
  - `scripts/mine_connections.py` (138 lines) — CLI: `<Connections.csv> <output.csv>`. Auto-detects header rows + encoding (utf-8 → latin-1 → cp1252). Groups by company, caps names at 10 per company.
  - `scripts/consolidate_targets.py` (288 lines) — CLI: `--output <path> [--connections <path>] [--files ...] [--scan-dir <path>]`. Merges arbitrary user CSVs/XLSXs + connection summary into `master_targets.csv` per `MASTER_TARGETS_COLUMNS`. Has `normalize_company_name` for dedup.

**`templates/`:**
- Purpose: JSON skeletons for user-data files. `/scout-setup` reads these as starting points, fills them in, writes to `<data_dir>/`.
- Contains: Two JSON files matching the shapes the operational skills expect.
- Key files:
  - `templates/config.json` (56 lines) — Template for `<data_dir>/config.json`. Sections: `candidate`, `preferences`, `search` (queries, budgets, board toggles), `scoring` (weights, thresholds). Defaults: `companies_per_day: 5`, `max_listings_per_run: 30`, pass budgets 60/25/15, weights 30/25/20/15/10, A=75 B=55.
  - `templates/candidate_profile.json` (41 lines) — Template for `<data_dir>/candidate_profile.json`. Sections: `summary`, `experience`, `skills` (strongest/credible/aspirational/unique_differentiators), `education`, `positioning`, `network`.

**`.planning/`:**
- Purpose: GSD workflow output (codebase mapping, phase plans). Created by `/gsd-map-codebase` and related commands.
- Contains: `codebase/` subdirectory with the architecture, structure, conventions, etc. analysis documents.
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`

## Key File Locations

**Entry Points:**
- `.claude-plugin/plugin.json` — Plugin manifest (Claude Code reads this to discover the plugin).
- `skills/scout-setup/SKILL.md` — First-run user entry (`/scout-setup`).
- `skills/scout-run/SKILL.md` — Daily user entry (`/scout-run`).
- `skills/job-scout/SKILL.md` — Auto-loaded shared knowledge (no direct user invocation).

**Configuration:**
- `templates/config.json` — Structural template (committed in plugin).
- `templates/candidate_profile.json` — Structural template (committed in plugin).
- `<data_dir>/config.json` — Live user config (created by `/scout-setup`, edited by user).
- `~/.job-scout/state.json` — State pointer (machine-wide, written by `/scout-setup`).

**Core Logic:**
- `scripts/schema.py` — All column schemas + thresholds.
- `scripts/state.py` — State pointer I/O + legacy fallback resolution.
- `scripts/validate_data.py` — Health check + schema migration.
- `scripts/tracker_utils.py` — Tracker xlsx append/dedup/format.
- `scripts/mine_connections.py` — LinkedIn export → connection summary.
- `scripts/consolidate_targets.py` — Multiple sources → master_targets.csv.

**Knowledge / Reference:**
- `skills/job-scout/references/file-contract.md` — Authoritative path registry.
- `skills/job-scout/references/search-config.md` — Search strategy.
- `skills/job-scout/references/scoring-rubric.md` — Scoring details.
- `skills/job-scout/references/job-boards.md` — Pass 2 board specs.
- `skills/job-scout/references/chrome-setup.md` — LinkedIn JD lazy-load sequence.

**Testing:**
- None present. The plugin has no test suite (no `tests/`, no `pytest.ini`, no `pytest`/`unittest` invocations). Verification is manual by running `/scout-setup` and `/scout-run` end-to-end.

## Naming Conventions

**Files:**
- **Skill files:** `SKILL.md` (uppercase, fixed name) inside a directory named `<skill-name>` (kebab-case). Examples: `skills/scout-setup/SKILL.md`, `skills/scout-run/SKILL.md`, `skills/job-scout/SKILL.md`.
- **Reference docs:** `<topic>.md`, kebab-case, lowercase. Examples: `file-contract.md`, `search-config.md`, `chrome-setup.md`. Live under `skills/<skill>/references/`.
- **Python scripts:** `<purpose>.py`, snake_case, lowercase. Examples: `schema.py`, `state.py`, `validate_data.py`, `tracker_utils.py`, `mine_connections.py`, `consolidate_targets.py`. Verbs for action scripts (`mine_`, `consolidate_`, `validate_`); nouns for libraries (`schema`, `state`).
- **Templates:** `<filename>.json`, matching the name they'll be written as in `<data_dir>` (`config.json` → `<data_dir>/config.json`, `candidate_profile.json` → `<data_dir>/candidate_profile.json`).
- **Manifest:** `plugin.json` (fixed name, required by Claude Code).
- **User-data files (created at runtime):** `master_targets.csv`, `JobScout_Tracker.xlsx`, `connections_summary.csv`, `candidate_profile.json`, `JobScout_Report_<YYYY-MM-DD>.md`, `new_rows.json`, `run_log.json`. Mix of snake_case (CSVs/JSONs) and PascalCase_With_Underscores (xlsx/report — these surface to the user in Excel/Finder so display-friendly capitalization is used).
- **Daily directories:** `daily/<YYYY-MM-DD>/` — ISO date.
- **Packet directories:** `packets/<Company>_<Role>/` — capitalized, underscore-joined, human-readable.

**Directories:**
- **Plugin top-level:** lowercase (`scripts/`, `templates/`, `skills/`).
- **Skill directories:** kebab-case (`scout-setup/`, `scout-run/`, `job-scout/`).
- **References directory:** lowercase (`references/`).
- **Plugin metadata:** `.claude-plugin/` (dot-prefixed, kebab-case — Claude Code convention).
- **GSD output:** `.planning/` (dot-prefixed).

**Schema constants (in `scripts/schema.py`):**
- Column lists: `UPPER_SNAKE_CASE` (e.g. `MASTER_TARGETS_COLUMNS`, `TRACKER_COLUMNS`, `TRACKER_JSON_KEYS`).
- Thresholds: `UPPER_SNAKE_CASE` (e.g. `STALE_LINKEDIN_JOB_ID_THRESHOLD`, `DEFAULT_TIER_A_THRESHOLD`).
- Master targets columns themselves: `snake_case` strings (`company_name`, `linkedin_connection_count`, `ats_provider`).
- Tracker columns: `Title Case` strings with spaces (`"Date Found"`, `"Job Title"`, `"Comp Range"`) — these are display strings used as Excel headers.
- Tracker JSON keys: `snake_case` (`date_found`, `job_title`, `comp_range`) — one-to-one with tracker columns, ordered identically.

**Skill frontmatter:**
- `name:` matches the directory name (kebab-case): `scout-setup`, `scout-run`, `job-scout`.
- `version:` SemVer string in quotes.
- `description:` includes explicit trigger phrases (e.g. "Triggers when the user types `/scout-run` or asks to ...").
- `allowed-tools:` comma-separated list.

## Where to Add New Code

**New plugin command:**
- Create `skills/<command-name>/SKILL.md` with YAML frontmatter (`name`, `description` with trigger phrases, `allowed-tools`, `version`).
- Add knowledge to `skills/job-scout/references/<topic>.md` if it's reusable across skills; otherwise inline in `SKILL.md`.
- Reference scripts via `${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py`.

**New deterministic operation (anything that must produce identical output every run):**
- Add a Python file to `scripts/`, named `<purpose>.py`.
- Import schema constants from `scripts/schema.py` — never inline column lists.
- Provide a CLI in `if __name__ == "__main__":` that takes positional args and prints JSON or text to stdout.
- Reference from skills via `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/<script>.py <args>`.

**New schema column:**
- Add to the relevant constant in `scripts/schema.py` (`MASTER_TARGETS_COLUMNS` or `TRACKER_COLUMNS`).
- Bump `MASTER_TARGETS_VERSION` if changing master_targets.
- If changing tracker, also update `TRACKER_JSON_KEYS` (one-to-one, same order) and `TRACKER_COL_WIDTHS` (same length).
- Update `scripts/validate_data.py` if a non-default migration is needed (current logic handles "add empty column" automatically).

**New file the scout reads or writes:**
- **Add it to `skills/job-scout/references/file-contract.md` first**, then reference the contract from wherever the file is read or written. Never describe paths in two places.

**New shared knowledge document:**
- Add `skills/job-scout/references/<topic>.md`.
- Add a `Read ${CLAUDE_PLUGIN_ROOT}/skills/job-scout/references/<topic>.md` line to whichever skill needs it (typically near the top, in the "before doing anything else" block).

**New template:**
- Add `templates/<filename>.json` with all keys present and sensible defaults.
- Reference from `/scout-setup` via `${CLAUDE_PLUGIN_ROOT}/templates/<filename>.json`.

**New external job board (Pass 2 source):**
- Add a section to `skills/job-scout/references/job-boards.md` with URL pattern, filters, what to extract, parsing gotchas, when to skip, signal quality.
- Add a toggle to `templates/config.json` under `search.pass2_boards`.
- Add a sub-budget allocation to `skills/scout-run/SKILL.md` Step 3.

## Special Directories

**`.claude-plugin/`:**
- Purpose: Claude Code plugin metadata.
- Generated: No (hand-edited).
- Committed: Yes.
- Contents: `plugin.json` only.

**`scripts/__pycache__/`:**
- Purpose: Python bytecode cache.
- Generated: Yes (by Python interpreter).
- Committed: No (in `.gitignore`).

**`.planning/codebase/`:**
- Purpose: GSD codebase mapping output.
- Generated: Yes (by `/gsd-map-codebase`).
- Committed: Optional (depends on user preference).

**`<data_dir>/` (user data, default `~/Documents/JobSearch/`):**
- Purpose: All user-owned, run-mutable data. Lives **outside** the plugin so plugin updates never touch it.
- Generated: Yes (by `/scout-setup` initially; updated every `/scout-run`).
- Committed: No (not under the plugin repo at all).
- Resolution: Found via `~/.job-scout/state.json` written by setup; legacy fallback paths in `scripts/state.py` (`LEGACY_DATA_DIRS` = `~/Documents/JobSearch/scout`, `~/Documents/JobSearch`, `~/Documents/JobScout`).

**`~/.job-scout/`:**
- Purpose: Machine-wide state directory for the plugin's pointer file.
- Generated: Yes (by `scripts/state.py write`, called from `/scout-setup` Step 6).
- Committed: No (lives in the user's home, not in the plugin repo).
- Contents: `state.json` only.

---

*Structure analysis: 2026-04-27*

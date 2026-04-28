# Technology Stack

**Analysis Date:** 2026-04-27

## Project Type

**Claude Code plugin** — `job-scout` v0.3.3 (per `.claude-plugin/plugin.json`). The plugin runs entirely inside the Claude Code runtime; there is no compiled binary, no service to deploy, and no npm/pip package distribution. The "stack" is defined by:

1. The Claude Code plugin manifest contract (`.claude-plugin/plugin.json`).
2. Three skills declared in `skills/` with YAML-frontmatter `SKILL.md` files.
3. A small Python 3 script suite in `scripts/` that handles deterministic data work (schema, tracker, state pointer, profile mining).
4. JSON templates in `templates/` consumed by the setup skill.
5. Markdown reference documents in `skills/job-scout/references/`.

There is no `package.json`, no `requirements.txt`, no `Cargo.toml`, no `go.mod`, no `pyproject.toml`. Python dependencies are installed ad-hoc via `pip install … --break-system-packages` (instructions surface inside script error messages — see `scripts/validate_data.py:29` and `scripts/tracker_utils.py:31`).

## Languages

**Primary:**
- **Python 3.8+** — All deterministic logic in `scripts/`. README requirement noted at `README.md:21`. Files: `scripts/schema.py`, `scripts/state.py`, `scripts/validate_data.py`, `scripts/tracker_utils.py`, `scripts/mine_connections.py`, `scripts/consolidate_targets.py`.
- **Markdown** — All skill bodies and reference docs (`skills/**/SKILL.md`, `skills/job-scout/references/*.md`, `README.md`). Contains YAML frontmatter for skill manifests.
- **JSON** — Plugin manifest (`.claude-plugin/plugin.json`), templates (`templates/config.json`, `templates/candidate_profile.json`), runtime state files (`~/.job-scout/state.json`, `<data_dir>/config.json`, `<data_dir>/candidate_profile.json`, `<data_dir>/daily/<DATE>/new_rows.json`, `run_log.json`).

**Secondary / output formats:**
- **CSV** — `master_targets.csv`, `connections_summary.csv`. Schema locked in `scripts/schema.py` (`MASTER_TARGETS_COLUMNS`).
- **XLSX** — `JobScout_Tracker.xlsx`. Written exclusively through `scripts/tracker_utils.py` (`HEADERS`, `COL_WIDTHS`, deterministic fills).
- **DOCX** — On-demand `tailored_resume.docx` produced inside `<data_dir>/daily/<DATE>/packets/<Company>_<Role>/` per `skills/scout-run/SKILL.md:264`.

## Runtime

**Claude Code plugin runtime:**
- Plugin discovered via `.claude-plugin/plugin.json`. Skills live under the discovery path `skills/<skill-name>/SKILL.md`.
- Plugin root surfaced to skills via the `${CLAUDE_PLUGIN_ROOT}` environment variable (used throughout `skills/scout-setup/SKILL.md` and `skills/scout-run/SKILL.md` to reference scripts and templates without hard-coded paths).
- Skills declare permitted tools in YAML frontmatter `allowed-tools:` (e.g. `skills/scout-run/SKILL.md:4` permits `Read, Write, Edit, Bash, Glob, Grep, Agent, TodoWrite, mcp__Claude_in_Chrome__*`).

**Python runtime:**
- CPython 3.8+ on the user's machine (no version pinning enforced by the plugin).
- All scripts are stand-alone CLIs with `if __name__ == "__main__":` entry points and shell-style usage strings (see `scripts/state.py:86`, `scripts/tracker_utils.py:320`, `scripts/validate_data.py:117`).

**Browser runtime (orchestrated, not bundled):**
- Google Chrome (any current channel — Stable/Beta/Dev/Nightly per `README.md:17`) with the **Claude in Chrome** extension. Required for `/scout-run`.

**Package manager:**
- None for the plugin itself.
- For Python deps, scripts assume system `pip` and emit `pip install <pkg> --break-system-packages` hints on ImportError (`scripts/validate_data.py:29`, `scripts/tracker_utils.py:31`, `scripts/mine_connections.py:25`, `scripts/consolidate_targets.py:26`).

## Frameworks

**Claude Code plugin framework:**
- Manifest format: `.claude-plugin/plugin.json` — required keys observed: `name`, `version`, `description`, `author` (current values: name=`job-scout`, version=`0.3.3`).
- Skill format (Anthropic skill convention): YAML frontmatter delimited by `---` lines at top of `SKILL.md`. Observed keys:
  - `name` (required, kebab-case)
  - `description` (required, includes natural-language trigger phrases)
  - `allowed-tools` (comma-separated list, can include MCP wildcards like `mcp__Claude_in_Chrome__*`)
  - `version` (per-skill semver)
  Examples: `skills/scout-setup/SKILL.md:1-6`, `skills/scout-run/SKILL.md:1-6`, `skills/job-scout/SKILL.md:1-10`.
- Slash-command invocation: skills with action-oriented `description` triggers (`/scout-setup`, `/scout-run`) are surfaced as slash commands by the Claude Code runtime.

**No web/app frameworks** — no Flask, FastAPI, Django, React, etc. This is purely orchestration + small CLI scripts.

## Key Dependencies

**Python (third-party):**
- **`pandas`** — DataFrame operations for CSV/XLSX I/O, dedup, schema migration. Required by `scripts/validate_data.py`, `scripts/mine_connections.py`, `scripts/consolidate_targets.py`. Imported at `scripts/validate_data.py:27`, `scripts/mine_connections.py:23`, `scripts/consolidate_targets.py:24`.
- **`openpyxl`** — Excel workbook read/write with cell styling (PatternFill, Font, Alignment, Border). Used in `scripts/tracker_utils.py:27-29` for `JobScout_Tracker.xlsx` formatting (header fill `#2F5496`, A-tier `#C6EFCE`, B-tier `#FFEB9C`, C-tier `#F2DCDB`, stale `#D9D9D9`).

**Python (stdlib only):**
- `json`, `os`, `sys`, `csv`, `re`, `datetime`, `glob`, `argparse`, `collections.defaultdict` — used across the script suite.

**No external CLI tools required** — the plugin does not shell out to `jq`, `curl`, `wget`, `git`, etc. All shelled commands are `python3 <script>` invocations of the bundled scripts.

**No JavaScript/Node dependencies.** No `package.json` exists.

## Plugin Manifest

**Path:** `.claude-plugin/plugin.json`

**Schema (current):**
```json
{
  "name": "job-scout",
  "version": "0.3.3",
  "description": "<one-liner>",
  "author": { "name": "Job Scout Contributors" }
}
```

The version string is read at runtime by the setup skill (`skills/scout-setup/SKILL.md:112`) and persisted into the state pointer's `plugin_version` field by `scripts/state.py:50` (`write_state`). This lets the runtime detect schema-version drift on later runs.

## Skill Manifest Format

Each skill lives at `skills/<skill-name>/SKILL.md` with the structure:

```markdown
---
name: <skill-name>
description: <triggering description>
allowed-tools: <comma-separated tool list, supports mcp__* wildcards>
version: <semver>
---

<skill body — markdown instructions for Claude>
```

**Observed `allowed-tools` values:**
- `skills/scout-setup/SKILL.md` → `Read, Write, Edit, Bash, Glob, Grep, Agent, AskUserQuestion, TodoWrite`
- `skills/scout-run/SKILL.md` → `Read, Write, Edit, Bash, Glob, Grep, Agent, TodoWrite, mcp__Claude_in_Chrome__*`
- `skills/job-scout/SKILL.md` → no `allowed-tools` (it is loaded as reference content, not invoked directly)

**Reference documents pattern:** `skills/job-scout/references/*.md` are read by the action skills via the `${CLAUDE_PLUGIN_ROOT}` prefix (e.g. `skills/scout-run/SKILL.md:14-17`). Reference docs are flat Markdown with no frontmatter.

## Configuration Files

**Plugin-shipped templates** (`templates/`):
- `templates/config.json` — Structural template for the user's `<data_dir>/config.json`. Top-level keys: `version`, `created`, `updated`, `data_dir`, `assessment_style`, `candidate{}`, `preferences{}`, `search{}`, `scoring{}`. Required keys validated by `scripts/validate_data.py:55` (`data_dir`, `preferences`, `search`, `scoring`).
- `templates/candidate_profile.json` — Schema for extracted candidate profile. Sections: `summary`, `experience[]`, `skills{strongest[], credible[], aspirational[], unique_differentiators[]}`, `education{}`, `positioning{}`, `network{}`.

**Runtime configuration** (created at `/scout-setup`, lives in user's data dir, not in repo):
- `~/.job-scout/state.json` — Machine-wide pointer. Fields: `data_dir`, `plugin_version`, `last_setup_iso`. Written by `scripts/state.py:50`, read by `scripts/state.py:64` (`resolve_data_dir` falls back through `~/Documents/JobSearch/scout`, `~/Documents/JobSearch`, `~/Documents/JobScout` if state.json is missing — see `LEGACY_DATA_DIRS` at `scripts/state.py:32`).
- `<data_dir>/config.json` — User's runtime config (instantiated from `templates/config.json`).
- `<data_dir>/candidate_profile.json` — Extracted profile (instantiated from `templates/candidate_profile.json`).

**Build / dev config:**
- None. No linter, formatter, test runner, or CI configuration in the repo.
- `.gitignore` (`/Users/rmoore/Workspaces/job-scout-plugin/.gitignore`) ignores `__pycache__/`, `*.pyc`, `.DS_Store` only.

## Data Formats

| Format | Purpose | Owner | Path(s) |
|---|---|---|---|
| JSON | Plugin manifest | Plugin | `.claude-plugin/plugin.json` |
| JSON (with YAML frontmatter inside MD) | Skill manifests | Plugin | `skills/*/SKILL.md` |
| JSON | Templates | Plugin | `templates/*.json` |
| JSON | State pointer | `scripts/state.py` | `~/.job-scout/state.json` |
| JSON | User runtime config | `/scout-setup` → user | `<data_dir>/config.json` |
| JSON | Extracted profile | `/scout-setup` | `<data_dir>/candidate_profile.json` |
| JSON | Per-run scoring input | `/scout-run` | `<data_dir>/daily/<DATE>/new_rows.json` |
| JSON | Per-run log | `/scout-run` | `<data_dir>/daily/<DATE>/run_log.json` |
| CSV | Company database | `scripts/consolidate_targets.py` + `/scout-run` | `<data_dir>/master_targets.csv` |
| CSV | Connection counts | `scripts/mine_connections.py` | `<data_dir>/connections_summary.csv` |
| XLSX | Job tracker | `scripts/tracker_utils.py` ONLY | `<data_dir>/JobScout_Tracker.xlsx` |
| Markdown | Daily report | `/scout-run` | `<data_dir>/daily/<DATE>/JobScout_Report_<DATE>.md` |
| Markdown | Honest assessment | `/scout-setup` | `<data_dir>/assessment/Honest_Career_Assessment.md` |
| Markdown | Per-packet artifacts | On-demand `pack <id>` | `<data_dir>/daily/<DATE>/packets/<Company>_<Role>/{jd.md,ats_diff.md,outreach_draft.md}` |
| DOCX | Tailored resume | On-demand `pack <id>` | `<data_dir>/daily/<DATE>/packets/<Company>_<Role>/tailored_resume.docx` |
| PDF/DOCX (input) | Source resume | User-provided | `config.candidate.resume_path` |
| ZIP (input) | LinkedIn data export | User-provided | `config.candidate.linkedin_export_path` (contains `Connections.csv`, `Profile.csv`, `Positions.csv`, `Skills.csv`, `Education.csv`, `Certifications.csv`) |

## Schema Source-of-Truth

All column names live in **`scripts/schema.py`** and nowhere else (this is enforced by skill prompts — see `skills/job-scout/SKILL.md:36-42`):

- `MASTER_TARGETS_COLUMNS` (11 columns, schema version 3 per `scripts/schema.py:36`): `company_name`, `industry`, `career_page_url`, `ats_provider`, `ats_board_url`, `connection_names`, `linkedin_connection_count`, `application_status`, `fit_notes`, `last_checked`, `data_source`.
- `TRACKER_COLUMNS` (14 Excel headers, exact strings): `Date Found`, `Job Title`, `Company`, `Location`, `Comp Range`, `Score`, `Tier`, `Connections`, `Match Notes`, `Job URL`, `Resume Tailored`, `Resume File`, `Status`, `Notes`.
- `TRACKER_JSON_KEYS` — lowercase mirror of `TRACKER_COLUMNS`, used in `new_rows.json` payloads passed to `scripts/tracker_utils.py append`.
- `STALE_LINKEDIN_JOB_ID_THRESHOLD = 4_200_000_000` — IDs below this are flagged as recycled.
- `DEFAULT_TIER_A_THRESHOLD = 75`, `DEFAULT_TIER_B_THRESHOLD = 55`, `DEFAULT_TIER_C_THRESHOLD = 40`.

Scripts that consume the schema import it (`scripts/validate_data.py:37`, `scripts/tracker_utils.py:40`, `scripts/consolidate_targets.py:35`) — never inline the column lists.

## Versioning

- **Plugin version:** `0.3.3` in `.claude-plugin/plugin.json`. Semver. Major version bumps not yet exercised; `0.3.x` series notes are in `README.md:124-126`.
- **Per-skill version:** declared in each `SKILL.md` frontmatter (`scout-setup` 0.3.1, `scout-run` 0.3.3, `job-scout` 0.3.0). Skill versions can lag the plugin version when only one skill changes.
- **Data schema version:** `MASTER_TARGETS_VERSION = 3` in `scripts/schema.py:36`. Migration handled idempotently in `scripts/validate_data.py:63` (`validate_master_targets`) — adds missing columns, never deletes.
- **Config template version:** `1.1` in `templates/config.json`. **Profile template version:** `1.0` in `templates/candidate_profile.json`.
- **Plugin version persisted to state:** Written into `~/.job-scout/state.json` at setup time so runs can detect plugin upgrades (`scripts/state.py:50`).

## Platform Requirements

**Development:**
- macOS / Linux. Path expansion uses `os.path.expanduser("~")` throughout — works on any POSIX system. No Windows-specific code paths, but the legacy fallback paths (`scripts/state.py:32`) assume `~/Documents/...` which is macOS/Linux-style.

**End-user runtime:**
- Claude Code with plugin support.
- Python 3.8+ with `pandas` and `openpyxl` (`pip install pandas openpyxl`).
- Google Chrome with the Claude in Chrome extension (only for `/scout-run`; setup works without Chrome).
- LinkedIn account, logged in via Chrome.
- Resume file (PDF or DOCX).
- Optional: LinkedIn data export ZIP, Wellfound login, YC Work at a Startup login.

**Storage:**
- All persistent data lives in the user's `<data_dir>` (default `~/Documents/JobSearch/`). The plugin itself does not write outside the user's data directory or the state file at `~/.job-scout/state.json`.

---

*Stack analysis: 2026-04-27*

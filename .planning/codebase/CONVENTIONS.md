# Coding Conventions

**Analysis Date:** 2026-04-27

This is a Claude Code plugin. The codebase is a small, deliberate mix of:
- **Python 3 utility scripts** (`scripts/*.py`) — deterministic CLIs invoked from skill prompts.
- **Skill markdown files** (`skills/**/SKILL.md` + `references/*.md`) — the actual prompts Claude reads to do work.
- **JSON templates** (`templates/*.json`) and a **plugin manifest** (`.claude-plugin/plugin.json`).

There are no shell scripts, no JavaScript/TypeScript, no build system, no linter config, and no formatter config. Conventions below are derived from observed style across `scripts/`, `skills/`, `templates/`, and `.claude-plugin/`.

---

## Naming Patterns

**Files:**
- Python scripts: `snake_case.py`. Examples: `scripts/schema.py`, `scripts/tracker_utils.py`, `scripts/mine_connections.py`, `scripts/consolidate_targets.py`, `scripts/state.py`, `scripts/validate_data.py`.
- Skill prompts: lowercase `kebab-case` directories under `skills/`, each containing a literal `SKILL.md`. Examples: `skills/scout-run/SKILL.md`, `skills/scout-setup/SKILL.md`, `skills/job-scout/SKILL.md`.
- Reference docs (skill-internal): `kebab-case.md` under `skills/job-scout/references/`. Examples: `references/file-contract.md`, `references/scoring-rubric.md`, `references/chrome-setup.md`.
- Templates: `snake_case.json`. Examples: `templates/config.json`, `templates/candidate_profile.json`.
- User-facing data files (declared in code): `snake_case.csv` (`master_targets.csv`), `PascalCase_With_Underscores.xlsx` (`JobScout_Tracker.xlsx`), date-stamped reports (`JobScout_Report_<YYYY-MM-DD>.md`).

**Python identifiers:**
- Functions: `snake_case`. Examples: `read_state()`, `write_state()`, `resolve_data_dir()`, `extract_job_id()`, `is_stale_by_id()`, `get_row_fill()`, `validate_master_targets()`.
- Module-level constants: `SCREAMING_SNAKE_CASE`. Examples in `scripts/schema.py` — `MASTER_TARGETS_COLUMNS`, `TRACKER_COLUMNS`, `TRACKER_JSON_KEYS`, `TRACKER_COL_WIDTHS`, `STALE_LINKEDIN_JOB_ID_THRESHOLD`, `DEFAULT_TIER_A_THRESHOLD`. In `scripts/state.py` — `STATE_DIR`, `STATE_PATH`, `LEGACY_DATA_DIRS`. In `scripts/tracker_utils.py` — `HEADER_FILL`, `HEADER_FONT`, `A_TIER_FILL`, `THIN_BORDER`.
- Internal/helper functions: leading underscore. Example: `_write_tracker()` in `scripts/tracker_utils.py:264`.
- Versions: integer for schema version (`MASTER_TARGETS_VERSION = 3` in `scripts/schema.py:36`); semver string for plugin/skill (`"0.3.3"` in `.claude-plugin/plugin.json:3`).

**JSON keys:**
- Top-level config keys are `snake_case`: `data_dir`, `assessment_style`, `candidate`, `preferences`, `search`, `scoring` (`templates/config.json`).
- Nested keys also `snake_case`: `salary_minimum`, `companies_per_day`, `max_listings_per_run`, `pass_budgets`, `tier_a_threshold`, `connection_weight`.
- Tracker JSON keys mirror Python identifier style and are listed once in `scripts/schema.py:68` (`TRACKER_JSON_KEYS`) — `date_found`, `job_title`, `comp_range`, `match_notes`, etc. Display-side column names live in `TRACKER_COLUMNS` and use Title Case (`"Date Found"`, `"Job URL"`).

---

## Code Style

**Formatting:**
- No formatter config (`.prettierrc`, `pyproject.toml`, `ruff.toml`, etc.) is present.
- Python uses 4-space indents, double quotes for most strings, and trailing commas in multi-line list/dict literals (see `MASTER_TARGETS_COLUMNS` definition at `scripts/schema.py:22`).
- Line lengths are loose — long inline comments and URL strings are allowed (e.g. `scripts/schema.py:36`, the `MASTER_TARGETS_VERSION` line is ~270 chars).
- JSON files are 2-space indented (see `.claude-plugin/plugin.json`, `templates/config.json`).

**Linting:**
- None. There is no `flake8`, `pylint`, `ruff`, `mypy`, or pre-commit setup.
- The `.gitignore` is minimal — only `__pycache__/`, `*.pyc`, `.DS_Store`.

**Import organization (Python):**
1. Stdlib first (`import sys`, `import os`, `import json`, `import re`, `from datetime import datetime`).
2. Third-party imports wrapped in `try / except ImportError` with a friendly error message that tells the user the exact pip command:
   ```python
   try:
       import pandas as pd
   except ImportError:
       print("ERROR: pandas not installed. Run: pip install pandas --break-system-packages", file=sys.stderr)
       sys.exit(1)
   ```
   This pattern appears identically in `scripts/validate_data.py:26-30`, `scripts/mine_connections.py:22-26`, `scripts/consolidate_targets.py:23-27`, and `scripts/tracker_utils.py:26-32`. Reuse it for any new script that depends on a non-stdlib package.
3. Local imports last, with a sibling-script bootstrap so the module works whether invoked from the plugin root or the `scripts/` directory:
   ```python
   SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
   if SCRIPTS_DIR not in sys.path:
       sys.path.insert(0, SCRIPTS_DIR)

   from schema import MASTER_TARGETS_COLUMNS
   ```
   Used in `scripts/validate_data.py:33-41`, `scripts/tracker_utils.py:34-44`, `scripts/consolidate_targets.py:30-35`. **Always use this bootstrap before importing from `schema.py`** — never rely on the caller's `PYTHONPATH`.

---

## Error Handling

**Pattern: return `(ok, message)` tuples from validators.**
`scripts/validate_data.py` uses `(bool, str)` return tuples for every validator (`validate_config`, `validate_master_targets`, `validate_tracker`, `validate_daily_dir`) and aggregates them in `main()`:
```python
def validate_config(data_dir):
    config_path = os.path.join(data_dir, "config.json")
    if not os.path.isfile(config_path):
        return False, f"config.json missing at {config_path} — run /scout-setup"
    ...
    return True, "ok"
```
The CLI prints a JSON summary and exits `0` on success / `1` on first failure. Use this same shape for any new validator.

**Pattern: silent fallbacks with empty defaults.**
`scripts/state.py:39-47` swallows `OSError` and `json.JSONDecodeError` and returns `{}`:
```python
def read_state():
    if not os.path.exists(STATE_PATH):
        return {}
    try:
        with open(STATE_PATH, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
```
This is intentional: a missing/broken state pointer triggers the legacy-path fallback in `resolve_data_dir()`, which then exits `2` so callers know to send the user to `/scout-setup`. Distinguish `0` (success) / `1` (broken) / `2` (not configured) when adding new CLIs.

**Pattern: print `ERROR:` to stderr, `sys.exit(1)`.**
For unrecoverable conditions (missing dependency, missing required arg), prefix with `ERROR:`, write to `sys.stderr`, and exit nonzero. See `scripts/validate_data.py:29`, `scripts/tracker_utils.py:31`, `scripts/mine_connections.py:25`, `scripts/consolidate_targets.py:26`.

**Pattern: never delete user data.**
`scripts/validate_data.py:64-93` (`validate_master_targets`) only **adds** missing columns and only **reorders so canonical columns come first** — user-added extras are preserved at the end. Comment from `scripts/validate_data.py:88`: *"we never drop user columns"*. Apply this rule to every migration.

---

## Logging

**Framework:** None — plain `print()` to stdout/stderr. There is no `logging` module use anywhere in `scripts/`.

**Patterns:**
- Human-readable progress lines go to **stdout** during long-running scripts:
  ```python
  print(f"Processed {len(df)} connections across {len(sorted_companies)} companies")
  print(f"Top 10 by connection count:")
  ```
  See `scripts/mine_connections.py:121-125`, `scripts/consolidate_targets.py:215-272`.
- Errors and warnings go to **stderr** with an explicit prefix (`ERROR:`, `Warning:`):
  ```python
  print(f"  Warning: Could not read {filepath}: {e}", file=sys.stderr)
  ```
  See `scripts/consolidate_targets.py:55, 64`.
- Machine-consumable output (used by skill prompts to read structured data back) is the **last `print()` of a CLI command** and is always JSON. Examples:
  ```python
  print(json.dumps({"data_dir": data_dir, "ok": overall_ok, "checks": results}, indent=2))
  # scripts/validate_data.py:141
  print(json.dumps(ids))
  # scripts/tracker_utils.py:331
  ```
  Skill prompts capture this stdout into per-run files (e.g. `run_log.json`).

---

## Comments

**When to Comment:**
- Top-of-file docstring is **mandatory** for every Python module. It opens with the module name and a one-sentence purpose, then expands with usage. Pattern from `scripts/state.py:1-18`:
  ```python
  """
  state.py — Read/write the Job Scout state pointer.

  The state pointer lives at ~/.job-scout/state.json and tells /scout-run
  where the user's data directory is. /scout-setup writes it. /scout-run
  reads it.

  Usage from prompt:
      python3 scripts/state.py read           # prints data_dir or empty string
      python3 scripts/state.py write <data_dir>
  """
  ```
  Every file in `scripts/` follows this pattern.

- Section dividers using `# ===` banners delineate logical zones in longer files. See `scripts/schema.py:11-13`, `scripts/tracker_utils.py:47-48` (`# === FORMATTING CONSTANTS ===`).

- **Inline comments explain *why*, not *what*.** Strong examples:
  - `scripts/schema.py:36` — single-line comment justifies the schema version bump and what was trimmed.
  - `scripts/schema.py:96` — explains the magic threshold `4_200_000_000` ("LinkedIn job IDs below this threshold tend to be 6+ months old").
  - `scripts/tracker_utils.py:48` — *"These NEVER change. Every run uses exactly these values."* — flags determinism intent.
  - `scripts/state.py:32-36` — explains the rationale for the legacy fallback list ordering.

**Function docstrings:**
- One-line docstrings for small helpers: `def empty_master_target_row():\n    """Return a dict with every master_targets column set to empty string."""` (`scripts/schema.py:109-111`).
- Multi-line docstrings for non-trivial functions, including parameter shape examples for I/O-heavy ones. See the JSON-shape docstring for `append_rows` in `scripts/tracker_utils.py:152-173`.

---

## Function Design

**Size:**
- Helpers stay small (~5-15 lines): `extract_job_id`, `is_stale_by_id`, `empty_master_target_row`.
- Orchestration functions (`consolidate`, `_write_tracker`, `mine_connections`) are larger (~50-80 lines) and acceptable when they're a single conceptual sequence.

**Parameters:**
- Positional for required inputs, defaults for optional. Example: `write_state(data_dir, plugin_version=None)` in `scripts/state.py:50`.
- File paths are accepted as strings, expanded with `os.path.expanduser()` at the boundary (CLI entry or write helper). See `scripts/state.py:53`, `scripts/mine_connections.py:136`, `scripts/consolidate_targets.py:283-287`.
- Larger CLIs use `argparse` (`scripts/consolidate_targets.py:276-282`); smaller ones parse `sys.argv` manually with explicit `Usage:` strings on misuse.

**Return Values:**
- Validators return `(ok: bool, message: str)`.
- CLI commands print JSON to stdout and rely on exit codes (0/1/2) for status.
- Pure helpers return native Python types (dict, list, set, int, tuple).

---

## Module Design

**Single source of truth for shared knowledge.**
This is the strongest convention in the codebase and is repeated in prompts:
- **Schema lives in `scripts/schema.py`.** Every column list (`MASTER_TARGETS_COLUMNS`, `TRACKER_COLUMNS`, `TRACKER_JSON_KEYS`, `TRACKER_COL_WIDTHS`) is defined there and imported elsewhere. Quoted from `scripts/schema.py:3-9`: *"ALL Python scripts and prompt documents reference column names from here. Do NOT inline column lists anywhere else."*
- **File paths live in `skills/job-scout/references/file-contract.md`.** Quoted from that doc: *"Every file the scout reads or writes lives at exactly one path. **No alternate paths. No fallbacks. No 'or'.**"*
- **Config values live in `<data_dir>/config.json`.** Skill prompts must read them verbatim and never hardcode (`skills/scout-run/SKILL.md:37`).

**Side-effect-free modules:**
`scripts/schema.py` is explicitly import-only with no CLI (`scripts/schema.py:9` — *"This module is import-only — it has no side effects and no CLI."*). All other scripts have a `if __name__ == "__main__":` guard.

**CLI exposure:**
Each script that has a CLI ends with a clear command dispatcher. Pattern from `scripts/tracker_utils.py:320-346`:
```python
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 tracker_utils.py <command> <tracker_path> [args...]")
        print("Commands: dedup-set, append, rebuild")
        sys.exit(1)

    command = sys.argv[1]
    tracker_path = os.path.expanduser(sys.argv[2])

    if command == "dedup-set":
        ...
    elif command == "append":
        ...
```
Subcommand strings use `kebab-case` (`dedup-set`, `read-json`).

---

## Markdown Style (SKILL.md and references)

**Frontmatter (YAML) is required for `SKILL.md` files.** Three patterns observed:
- `skills/scout-run/SKILL.md:1-6` — uses single-line `description` and `allowed-tools` array:
  ```yaml
  ---
  name: scout-run
  description: Run a daily job search — broad sourcing across LinkedIn, ...
  allowed-tools: Read, Write, Edit, Bash, Glob, Grep, Agent, TodoWrite, mcp__Claude_in_Chrome__*
  version: 0.3.3
  ---
  ```
- `skills/job-scout/SKILL.md:1-10` — uses YAML block-folded description (`description: >`) for multi-line trigger phrasing.

**Required keys:** `name`, `description`, `version`. `allowed-tools` is required for invocable command skills (`scout-run`, `scout-setup`) and omitted for the knowledge-only skill (`job-scout`).

**Document structure inside SKILL.md:**
1. Frontmatter.
2. One-paragraph summary of what the skill does.
3. *"Read these before starting"* / *"Before doing anything else"* bullet list referencing other docs by `${CLAUDE_PLUGIN_ROOT}/...` path. See `skills/scout-run/SKILL.md:12-17`.
4. Numbered `## Step N: ...` sections. Each step is self-contained: bash blocks, file paths, decision branches.
5. Optional trailing `## Fallback Mode` / `## On-demand: ...` sections for non-default flows.

**Table-of-defaults style.**
When listing weights/thresholds/budgets, use a markdown table with a `Why` or `What to evaluate` column rather than prose. Examples: `README.md:97-105`, `skills/job-scout/SKILL.md:78-84`, `skills/scout-run/SKILL.md:148-153`, `skills/job-scout/references/search-config.md:114-120`. The right-hand column makes intent reviewable.

**Bash blocks must be executable verbatim.**
Every shell snippet in a skill prompt must be runnable with no edits — paths use `${CLAUDE_PLUGIN_ROOT}` or `<data_dir>` placeholders that the skill's prior step has already resolved. Example from `skills/scout-run/SKILL.md:24-26`:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/state.py resolve
```

**Emphasis convention:**
- `**bold**` for imperatives and warnings (*"**Hard cap: 10 A-tier listings per run.**"*, *"**Do NOT use LinkedIn's `f_C=` company-ID filter**"*).
- Backticks for file paths, column names, env vars, and CLI commands.
- `> blockquote` for things the skill should literally say to the user (e.g. `skills/scout-run/SKILL.md:215-216`).

---

## JSON / YAML Formatting

**JSON files:**
- 2-space indentation everywhere. See `templates/config.json`, `templates/candidate_profile.json`, `.claude-plugin/plugin.json`.
- Trailing newline at EOF (every JSON in the repo ends with `\n`).
- Top-level keys ordered conceptually, not alphabetically — `templates/config.json` orders as `version` → `created/updated` → `data_dir` → `candidate` → `preferences` → `search` → `scoring`. New configs should follow this conceptual ordering.
- Both templates carry an explicit `"version"` string at the top so future migrations have something to dispatch on.
- Empty values use the matching empty type: `""` for strings, `0` for numbers, `[]` for lists, never `null`. See `templates/candidate_profile.json`.

**YAML (skill frontmatter only):**
- 2-space indentation, no quotes around plain scalars.
- Use `>` block-folded scalars for long descriptions, plain strings for short ones.

---

## Version-Bumping Conventions

The plugin uses **two parallel version numbers** plus a schema integer:

| Version | Where | Format | Bump trigger |
|---|---|---|---|
| Plugin version | `.claude-plugin/plugin.json` `"version"` | Semver string (`"0.3.3"`) | Any user-visible behavior change. |
| Skill version | `skills/*/SKILL.md` frontmatter `version:` | Semver string (`0.3.3`, `0.3.1`, `0.3.0`) | When that specific skill's prompt or its referenced scripts change behavior. |
| Schema version | `scripts/schema.py` `MASTER_TARGETS_VERSION` | Integer (`3`) | Any add/rename/remove of a `MASTER_TARGETS_COLUMNS` entry. Must be paired with a migration in `scripts/validate_data.py`. |

**Observed practice:**
- Plugin version and the most-recently-changed skill version often track each other (current state: plugin `0.3.3`, `scout-run` `0.3.3`, `scout-setup` `0.3.1`, `job-scout` `0.3.0`).
- The skill `version` only bumps when that skill changes — `job-scout` has stayed at `0.3.0` while `scout-run` advanced to `0.3.3`.
- Commit messages encode the version: `de48749 v0.3.2: clean up locations and start running individual board searches`. Format: `vX.Y.Z: <short imperative description>`. See `git log --oneline`.
- README has a `## Versioning` section (`README.md:122-126`) that summarizes what changed at each minor — keep this in sync when bumping.

**Schema migration rule (from `scripts/schema.py:20-21`):**
> *"DO NOT add columns without bumping `MASTER_TARGETS_VERSION` and adding a migration in `validate_data.py`."*

---

## Helper Patterns Worth Preserving

1. **Sibling-script import bootstrap** — the `SCRIPTS_DIR` / `sys.path.insert(0, SCRIPTS_DIR)` block. Lets a script work whether invoked from the plugin root, the `scripts/` directory, or via `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/...`.
2. **Try/except ImportError with pip hint** — every third-party dependency surfaces the exact `pip install` command the user needs.
3. **Empty-row factories** — `empty_master_target_row()` and `empty_tracker_row()` in `scripts/schema.py:109-116` give every consumer a guaranteed-shape dict to fill in. Saves repeated boilerplate.
4. **Deterministic formatting constants** — `scripts/tracker_utils.py:51-62` declares `HEADER_FILL`, `A_TIER_FILL`, `STALE_FILL` etc. as module-level openpyxl style objects. Every tracker write reuses the same instances, making "did the colors change?" a non-question.
5. **CLI subcommand dispatch via `sys.argv[1]`** — `scripts/state.py:91-112` and `scripts/tracker_utils.py:326-346` both expose multiple operations behind a single script. New scripts with multiple actions should follow this rather than spawning N scripts.
6. **`os.path.expanduser()` at the boundary** — every CLI expands `~` exactly once when accepting a path argument, so internal code can assume absolute paths.

---

*Convention analysis: 2026-04-27*
